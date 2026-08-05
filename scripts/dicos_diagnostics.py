"""Larger validation-only diagnostic sample per epoch, on DiCOS.

The published per-epoch payload rests on 50 conditions x 5 draws = 250 events,
which is thin for distribution metrics. This generates an arbitrarily larger
paired Geant4/Fast-MC sample from the **validation partition only** and reports
the same `trend` quantities the site already carries, so the two are directly
comparable and the larger sample simply has tighter errors. It also reports the
standard error on each bias fraction, which is the point of sampling more.

Differences from `cbsc_zdc.cloud.paired_diagnostics`, whose helpers this reuses:

  * that module is GCS-coupled; this reads and writes the shared filesystem;
  * that module deliberately sampled the FULL corpus **including the sealed
    test split**, as a one-off authorised on 2026-07-30. **This one never
    does.** The dataset is constructed with `split="validation"`, which filters
    on the split code at construction, and the train and test counts are then
    asserted zero from the assignment array as an independent check.

Two modes. One-shot:

    .venv_3090/bin/python repo/scripts/dicos_diagnostics.py \
        --checkpoint prep/checkpoints/x.pt --n-events 2000 \
        --output _diag/<run-tag>/metrics.json

Watch, which is how it is used alongside a training run -- build the dataset
once, then process each epoch's checkpoint as it is dropped into the queue:

    .venv_3090/bin/python repo/scripts/dicos_diagnostics.py \
        --n-events 4000 --watch-dir _diag/<run-tag>/queue \
        --output-dir _diag/<run-tag>

Building the dataset verifies all 187 shards and reads every one to apply the
kinetic filter, which takes minutes; watch mode pays that once rather than per
epoch, and holding one context also fixes the sampled events across epochs,
which is what makes the epoch-to-epoch comparison like-for-like.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import numpy as np
import torch

REPO_SRC = Path(__file__).resolve().parents[1] / "src"
if str(REPO_SRC) not in sys.path:
    sys.path.insert(0, str(REPO_SRC))

from cbsc_zdc.cloud.paired_diagnostics import (  # noqa: E402
    generate_paired_sample,
    hcal_summary,
    load_model,
)
from cbsc_zdc.data.dataset import ShardedSparseDataset, load_geometry  # noqa: E402
from cbsc_zdc.eval.metrics import (  # noqa: E402
    c2st_auc,
    high_level_features,
    response_bins,
    wasserstein_1d,
)
from cbsc_zdc.eval.visualization import FEATURE_NAMES, fixed_validation_indices  # noqa: E402
from cbsc_zdc.utils import dump_json, environment_snapshot, load_yaml, sha256_file  # noqa: E402


def _log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


#: `wasserstein_1d` evaluates `np.quantile` at `max(a.size, b.size)` points, so
#: its cost is quadratic-ish in the array length. That is fine for the nine
#: per-event observables (one value per event) but pathological for the pooled
#: positive-cell spectrum, which is one value per *hit*: 4,000 events at ~1,600
#: hits each is ~6.4 million, and the call did not return in ten minutes.
#: Above this cap the spectrum is subsampled deterministically before the
#: comparison, and the cap is recorded in the output. This changes nothing for
#: the per-event metrics, which are never near it.
POOLED_SPECTRUM_CAP = 200_000
QUEUED_CHECKPOINT_PATTERN = re.compile(r"^ckpt_epoch_(\d{4,})\.pt$")


def _subsample(values: np.ndarray, cap: int, seed: int) -> np.ndarray:
    if values.size <= cap:
        return values
    rng = np.random.default_rng(seed)
    return values[rng.choice(values.size, size=cap, replace=False)]


def longitudinal_profile(
    cell_energy: np.ndarray, layer_index: np.ndarray, n_layers: int
) -> np.ndarray:
    """Per-event energy summed within each layer."""
    profile = np.zeros((cell_energy.shape[0], n_layers), dtype=np.float64)
    for layer in range(n_layers):
        mask = layer_index == layer
        if mask.any():
            profile[:, layer] = cell_energy[:, mask].sum(axis=1)
    return profile


class DiagnosticContext:
    """Geometry, the fixed validation sample, and the split arrays.

    Built once and reused for every checkpoint. Construction is expensive -- it
    verifies all 187 shards and reads every shard once to apply the kinetic
    filter -- so a per-epoch loop must not rebuild it.
    """

    def __init__(self, args) -> None:
        self.device = torch.device(args.device)
        if self.device.type == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("cuda requested but unavailable")

        self.geometry = load_geometry(args.geometry, self.device)
        self.n_nodes = int(self.geometry["subdetector"].shape[0])
        self.n_ecal = int((self.geometry["subdetector"] == 0).sum())
        self.layer_index = self.geometry["layer_index"].cpu().numpy()
        self.n_layers = int(self.layer_index.max()) + 1
        self.selection_seed = int(args.selection_seed)
        self.batch_size = int(args.batch_size)
        self.kinetic_range = (float(args.kinetic_low), float(args.kinetic_high))

        # split="validation" filters on the split code at construction. This is
        # the guarantee that no test event can enter the sample.
        self.dataset = ShardedSparseDataset(
            args.manifest, args.splits, "validation", self.kinetic_range, self.n_nodes
        )
        self.pool = len(self.dataset)
        _log(f"validation pool in {list(self.kinetic_range)} GeV: {self.pool}")

        count = min(int(args.n_events), self.pool)
        chosen = fixed_validation_indices(self.pool, count, self.selection_seed)
        self.dataset.indices = self.dataset.indices[
            np.asarray(sorted(chosen), dtype=np.int64)
        ]
        _log(f"fixed sample of {len(self.dataset)} validation events")

        splits_manifest = json.loads(Path(args.splits).read_text("utf-8"))
        self.assignment = np.load(
            Path(args.splits).parent / splits_manifest["assignment_file"],
            allow_pickle=False,
        )["split_code"]

        # Only to report how many sampled events the model was selected on. The
        # pilot validation partition is a subset of this one, so most of the
        # sample is genuinely unseen.
        self.pilot_assignment = None
        pilot_path = Path(args.pilot_splits)
        if pilot_path.is_file():
            pilot_manifest = json.loads(pilot_path.read_text("utf-8"))
            self.pilot_assignment = np.load(
                pilot_path.parent / pilot_manifest["assignment_file"],
                allow_pickle=False,
            )["split_code"]

        self.positions = self.geometry["positions_mm"].cpu().numpy()
        self.energy_bin_edges = [float(v) for v in args.energy_bin_edges]
        self.gates = (
            load_yaml(args.gates) if args.gates and Path(args.gates).is_file() else None
        )


def run_one(context: DiagnosticContext, checkpoint: Path) -> dict:
    started = time.time()
    payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
    epoch = int(payload.get("epoch", -1))
    # Take the bin edges from the frozen config that produced this checkpoint,
    # never from a default. A hand-written default silently dropped the whole
    # 225-250 GeV bin, because the frozen edges end at 250.0001 -- just above
    # the range, so the half-open [low, high) still catches events at exactly
    # 250 -- and a default stopping at 225 leaves that bin uncovered.
    config_edges = (
        payload.get("config", {}).get("evaluation", {}).get("energy_bin_edges_gev")
    )
    del payload
    edges = [float(v) for v in (config_edges or context.energy_bin_edges)]
    low, high = context.kinetic_range
    if edges[0] > low or edges[-1] <= high:
        raise RuntimeError(
            f"energy bins {edges[0]}..{edges[-1]} do not cover the sampled "
            f"kinetic range [{low}, {high}]; events would be silently dropped"
        )
    model = load_model(checkpoint, context.geometry, context.device)

    sample = generate_paired_sample(
        context.dataset, model, context.device, seed=context.selection_seed,
        batch_size=context.batch_size, log=_log,
    )
    del model
    if context.device.type == "cuda":
        torch.cuda.empty_cache()

    # Independent check that the split filter did what it claims.
    codes = context.assignment[sample["global_index"]]
    counts = {
        "train": int((codes == 0).sum()),
        "validation": int((codes == 1).sum()),
        "test": int((codes == 2).sum()),
    }
    if counts["test"] != 0 or counts["train"] != 0:
        raise RuntimeError(f"non-validation events entered the sample: {counts}")

    seen_in_pilot = (
        int((context.pilot_assignment[sample["global_index"]] == 1).sum())
        if context.pilot_assignment is not None
        else None
    )

    truth = sample["truth_cell_energy_gev"]
    generated = sample["generated_cell_energy_gev"]
    truth_hcal = hcal_summary(truth, context.n_ecal, context.n_nodes)
    generated_hcal = hcal_summary(generated, context.n_ecal, context.n_nodes)

    truth_total = truth.sum(axis=1)
    generated_total = generated.sum(axis=1)
    truth_hits = (truth > 0).sum(axis=1)
    generated_hits = (generated > 0).sum(axis=1)

    truth_profile = longitudinal_profile(
        truth, context.layer_index, context.n_layers
    ).mean(axis=0)
    generated_profile = longitudinal_profile(
        generated, context.layer_index, context.n_layers
    ).mean(axis=0)
    denominator = max(float(np.abs(truth_profile).sum()), 1e-9)
    profile_relative_l1 = float(
        np.abs(generated_profile - truth_profile).sum() / denominator
    )

    truth_response_mean = float(truth_total.mean())
    generated_response_mean = float(generated_total.mean())
    truth_hit_mean = float(truth_hits.mean())
    generated_hit_mean = float(generated_hits.mean())

    trend = {
        "truth_response_mean_gev": truth_response_mean,
        "generated_response_mean_gev": generated_response_mean,
        "response_bias_fraction": (
            (generated_response_mean - truth_response_mean)
            / max(abs(truth_response_mean), 1e-9)
        ),
        "truth_hit_count_mean": truth_hit_mean,
        "generated_hit_count_mean": generated_hit_mean,
        "hit_count_bias_fraction": (
            (generated_hit_mean - truth_hit_mean) / max(abs(truth_hit_mean), 1e-9)
        ),
        "mean_longitudinal_profile_relative_l1": profile_relative_l1,
    }

    # Standard error on the two bias fractions, which is the whole point of a
    # larger sample: the mean's error falls as 1/sqrt(n).
    n = len(context.dataset)
    trend_stderr = {
        "response_bias_fraction": float(
            generated_total.std(ddof=1) / np.sqrt(n)
            / max(abs(truth_response_mean), 1e-9)
        ),
        "hit_count_bias_fraction": float(
            generated_hits.std(ddof=1) / np.sqrt(n) / max(abs(truth_hit_mean), 1e-9)
        ),
    }

    # Everything the repository's own evaluator computes. The metric functions
    # are reused rather than `evaluate_checkpoint` itself, because that wrapper
    # re-verifies all 187 shards on every call -- two minutes of pure waste per
    # epoch when the dataset is already built and fixed.
    truth_features = high_level_features(truth, context.layer_index, context.positions)
    generated_features = high_level_features(
        generated, context.layer_index, context.positions
    )
    w_response = wasserstein_1d(truth_total, generated_total)
    w_hits = wasserstein_1d(truth_hits, generated_hits)
    kinetic = sample["kinetic_energy_gev"]

    evaluation = {
        "n_events": n,
        "truth_zero_fraction": float(np.mean(truth_total == 0)),
        "generated_zero_fraction": float(np.mean(generated_total == 0)),
        "energy_bin_edges_gev": edges,
        "energy_bin_events_covered": int(
            ((kinetic >= edges[0]) & (kinetic < edges[-1])).sum()
        ),
        "response_bins": response_bins(
            kinetic, truth_total, generated_total, np.array(edges),
        ),
        "response_wasserstein_gev": w_response,
        "response_wasserstein_normalized": float(
            w_response / max(np.std(truth_total), 1e-9)
        ),
        "hit_count_wasserstein": w_hits,
        "hit_count_wasserstein_normalized": float(
            w_hits / max(np.std(truth_hits), 1e-9)
        ),
        "high_level_c2st_auc": c2st_auc(
            truth_features, generated_features, context.selection_seed
        ),
    }

    # distribution_metrics() is not called wholesale: its pooled positive-cell
    # Wasserstein does not return at this sample size (see POOLED_SPECTRUM_CAP).
    # The per-feature parts are computed here with the same definitions.
    per_feature = {}
    half = len(truth_features) // 2
    order = np.random.default_rng(context.selection_seed).permutation(
        len(truth_features)
    )
    for index, name in enumerate(FEATURE_NAMES):
        t = truth_features[:, index]
        g = generated_features[:, index]
        per_feature[name] = {
            "wasserstein": wasserstein_1d(t, g),
            "truth_mean": float(t.mean()),
            "generated_mean": float(g.mean()),
        }
    # Truth compared with itself: the distance below which a value is not
    # distinguishable from sampling noise at this sample size.
    truth_half_floor = {
        name: {
            "wasserstein": wasserstein_1d(
                truth_features[order[:half], index],
                truth_features[order[half:2 * half], index],
            )
        }
        for index, name in enumerate(FEATURE_NAMES)
    } if half >= 2 else None

    positive_t = _subsample(
        truth[truth > 0], POOLED_SPECTRUM_CAP, context.selection_seed
    )
    positive_g = _subsample(
        generated[generated > 0], POOLED_SPECTRUM_CAP, context.selection_seed + 1
    )
    per_feature["positive_cell_energy_gev"] = {
        "wasserstein": wasserstein_1d(positive_t, positive_g),
        "truth_mean": float(positive_t.mean()) if positive_t.size else 0.0,
        "generated_mean": float(positive_g.mean()) if positive_g.size else 0.0,
        "subsampled_to": int(POOLED_SPECTRUM_CAP),
        "truth_positive_cells": int((truth > 0).sum()),
        "generated_positive_cells": int((generated > 0).sum()),
    }
    per_feature["mean_longitudinal_profile"] = {
        "relative_l1": profile_relative_l1,
    }
    per_feature["truth_half_floor"] = truth_half_floor
    evaluation["distribution_metrics"] = per_feature

    # Per-feature mean bias, so every one of the nine observables has a
    # "[metric] vs epoch" series rather than only response and hit count.
    feature_bias = {}
    for index, name in enumerate(FEATURE_NAMES):
        t = truth_features[:, index]
        g = generated_features[:, index]
        t_mean = float(t.mean())
        g_mean = float(g.mean())
        feature_bias[name] = {
            "truth_mean": t_mean,
            "generated_mean": g_mean,
            "bias_fraction": (g_mean - t_mean) / max(abs(t_mean), 1e-9),
            "bias_fraction_stderr": float(
                g.std(ddof=1) / np.sqrt(n) / max(abs(t_mean), 1e-9)
            ),
            "truth_std": float(t.std(ddof=1)),
            "generated_std": float(g.std(ddof=1)),
            "resolution_difference_fraction": float(
                (g.std(ddof=1) - t.std(ddof=1)) / max(abs(t.std(ddof=1)), 1e-9)
            ),
        }
    evaluation["feature_bias"] = feature_bias

    if context.gates is not None:
        gates = context.gates
        bins = evaluation["response_bins"]
        minimum = int(gates.get("min_events_per_energy_bin", 2))
        coverage = all(row["n"] >= minimum for row in bins)
        auc = evaluation["high_level_c2st_auc"]
        checks = {
            "evaluation_event_count": n >= int(
                gates.get("min_total_evaluation_events", 1)
            ),
            "energy_bin_coverage": coverage,
            "mean_bias_bins": coverage and all(
                abs(row["mean_bias_fraction"])
                <= float(gates["max_abs_mean_bias_fraction"]) for row in bins
            ),
            "resolution_bins": coverage and all(
                abs(row["resolution_difference_fraction"])
                <= float(gates["max_abs_resolution_difference_fraction"])
                for row in bins
            ),
            "zero_response": abs(
                evaluation["generated_zero_fraction"]
                - evaluation["truth_zero_fraction"]
            ) <= float(gates["max_zero_fraction_absolute_difference"]),
            "response_wasserstein": evaluation["response_wasserstein_normalized"]
            <= float(gates["max_response_wasserstein_normalized"]),
            "hit_count_wasserstein": evaluation["hit_count_wasserstein_normalized"]
            <= float(gates["max_hit_count_wasserstein_normalized"]),
            "high_level_c2st": auc is not None and np.isfinite(auc)
            and auc <= float(gates["max_high_level_c2st_auc"]),
        }
        evaluation["gate_checks"] = {
            "checks": checks,
            "pass": all(checks.values()),
            "note": (
                "INFORMATIONAL ONLY. These thresholds were predeclared for a "
                "final controlled study on at least "
                f"{gates.get('min_total_evaluation_events')} events; this is a "
                f"{n}-event per-epoch monitor, so evaluation_event_count is "
                "expected to fail and the verdict is not a gate result. No "
                "threshold was altered."
            ),
        }

    result = {
        "schema_version": 1,
        "kind": "cbsc-zdc-large-validation-diagnostic",
        "split": "validation",
        "epoch": epoch,
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": sha256_file(checkpoint),
        "n_events": n,
        "validation_pool": context.pool,
        "kinetic_range_gev": list(context.kinetic_range),
        "selection_seed": context.selection_seed,
        "split_counts": counts,
        "events_also_in_pilot_validation": seen_in_pilot,
        "trend": trend,
        "trend_stderr": trend_stderr,
        "evaluation": evaluation,
        "hcal": {
            "truth_total_mean_gev": float(truth_hcal["total"].mean()),
            "generated_total_mean_gev": float(generated_hcal["total"].mean()),
            "truth_hits_mean": float(truth_hcal["hits"].mean()),
            "generated_hits_mean": float(generated_hcal["hits"].mean()),
        },
        "truth_longitudinal_profile_gev": truth_profile.tolist(),
        "generated_longitudinal_profile_gev": generated_profile.tolist(),
        "qa": {
            "test_events_used": 0,
            "train_events_used": 0,
            "truth_nonfinite": int((~np.isfinite(truth)).sum()),
            "generated_nonfinite": int((~np.isfinite(generated)).sum()),
            "truth_negative": int((truth < 0).sum()),
            "generated_negative": int((generated < 0).sum()),
        },
        "scientific_status": (
            "validation-only descriptive diagnostic; not a fidelity gate and "
            "not Geant4 validation"
        ),
        "environment": environment_snapshot(),
        "seconds": time.time() - started,
    }
    # Every sampled event must fall inside a bin. A bin range that does not
    # span the sampled range drops events silently, which is how the 225-250
    # GeV bin went missing once.
    uncovered = n - evaluation["energy_bin_events_covered"]
    result["qa"]["events_outside_energy_bins"] = int(uncovered)
    result["qa"]["energy_bins_cover_sample"] = uncovered == 0
    result["qa"]["empty_energy_bins"] = int(
        sum(1 for row in evaluation["response_bins"] if row["n"] == 0)
    )
    result["qa"]["pass"] = (
        result["qa"]["test_events_used"] == 0
        and result["qa"]["generated_nonfinite"] == 0
        and result["qa"]["generated_negative"] == 0
        and uncovered == 0
        and result["qa"]["empty_energy_bins"] == 0
    )
    return result


def drain_once(context: DiagnosticContext, queue_dir: Path, output_dir: Path) -> int:
    """Consume every checkpoint currently queued. Returns the failure count.

    Shared by single-queue `watch` and campaign-wide `watch_root`, so the two
    modes cannot drift apart in how they deduplicate, quarantine, or record.
    """
    queue_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    done_dir = queue_dir / "done"
    done_dir.mkdir(exist_ok=True)
    failures = 0
    pending = sorted(p for p in queue_dir.glob("*.pt") if p.is_file())
    if True:
        for checkpoint in pending:
            try:
                match = QUEUED_CHECKPOINT_PATTERN.fullmatch(checkpoint.name)
                if match is None:
                    raise ValueError("queued checkpoint name does not encode its epoch")
                filename_epoch = int(match.group(1))
                expected_output = output_dir / f"metrics_epoch_{filename_epoch:04d}.json"
                if expected_output.exists():
                    existing = json.loads(expected_output.read_text(encoding="utf-8"))
                    if (
                        int(existing.get("epoch", -1)) != filename_epoch
                        or existing.get("checkpoint_sha256") != sha256_file(checkpoint)
                    ):
                        raise RuntimeError(
                            "existing metric conflicts with queued checkpoint; refusing overwrite"
                        )
                    _log(f"deduplicated {checkpoint.name} against immutable metric")
                    checkpoint.rename(done_dir / checkpoint.name)
                    continue
                result = run_one(context, checkpoint)
                if int(result.get("epoch", -1)) != filename_epoch:
                    raise ValueError(
                        f"checkpoint filename epoch {filename_epoch} does not match "
                        f"generated result epoch {result.get('epoch')!r}"
                    )
            except Exception as exc:  # noqa: BLE001 -- recorded, loop continues
                failures += 1
                _log(f"FAILED {checkpoint.name}: {type(exc).__name__}: {exc}")
                checkpoint.rename(done_dir / (checkpoint.name + ".failed"))
                continue
            out = output_dir / f"metrics_epoch_{result['epoch']:04d}.json"
            qa_passed = result.get("qa", {}).get("pass") is True
            if not qa_passed:
                failures += 1
                failed_out = output_dir / f"metrics_epoch_{result['epoch']:04d}.failed.json"
                dump_json(result, failed_out)
                _log(f"QUARANTINED {checkpoint.name}: diagnostic QA did not pass")
                checkpoint.rename(done_dir / (checkpoint.name + ".failed"))
                continue
            dump_json(result, out)  # dump_json publishes atomically
            _log(
                f"wrote {out.name} epoch={result['epoch']} n={result['n_events']} "
                f"response_bias={result['trend']['response_bias_fraction']:+.6f} "
                f"+/- {result['trend_stderr']['response_bias_fraction']:.6f}"
            )
            checkpoint.rename(done_dir / checkpoint.name)
    return failures


def watch(context: DiagnosticContext, queue_dir: Path, output_dir: Path) -> int:
    """Process checkpoints dropped into `queue_dir` until a `STOP` file appears.

    The producer copies an epoch's checkpoint in; this consumes it and leaves a
    metrics file behind. A failed checkpoint is set aside rather than retried
    forever, so one bad file cannot stall the queue.
    """
    queue_dir.mkdir(parents=True, exist_ok=True)
    failures = 0
    _log(f"watching {queue_dir}")
    while True:
        pending = [p for p in queue_dir.glob("*.pt") if p.is_file()]
        # Drain before stopping. Checking STOP first abandoned everything the
        # producer queued after the last pass -- the producer writes STOP as
        # soon as training exits, which is exactly when the last few epochs
        # are still waiting.
        if (queue_dir / "STOP").exists() and not pending:
            _log(f"STOP seen and queue drained, exiting failures={failures}")
            return 1 if failures else 0
        if not pending:
            time.sleep(20)
            continue
        failures += drain_once(context, queue_dir, output_dir)


def watch_root(context: DiagnosticContext, root: Path) -> int:
    """Follow every run tag under `root`, including tags that appear later.

    A campaign starts a new run tag per segment, and the 3090 consumer cannot be
    started from inside the 4090 pod, so a consumer bound to one queue directory
    would stop serving as soon as the campaign advanced a segment. This mode
    discovers `<root>/<run-tag>/queue` as tags appear and keeps the expensive
    `DiagnosticContext` -- shard verification and validation-pool construction --
    built exactly once.

    A per-tag `STOP` retires that tag only. The whole consumer exits when
    `<root>/CAMPAIGN_STOP` exists and every queue is drained, so an operator
    ends it deliberately rather than by a segment finishing.
    """
    root.mkdir(parents=True, exist_ok=True)
    failures = 0
    retired: set[Path] = set()
    _log(f"watching campaign root {root}")
    while True:
        queues = sorted(
            q for q in root.glob("*/queue") if q.is_dir() and q not in retired
        )
        pending_total = 0
        for queue_dir in queues:
            output_dir = queue_dir.parent
            pending = [p for p in queue_dir.glob("*.pt") if p.is_file()]
            pending_total += len(pending)
            if pending:
                _log(f"draining {queue_dir} ({len(pending)} queued)")
                failures += drain_once(context, queue_dir, output_dir)
            elif (queue_dir / "STOP").exists():
                retired.add(queue_dir)
                _log(f"retired {queue_dir}: STOP seen and queue drained")
        if (root / "CAMPAIGN_STOP").exists() and pending_total == 0:
            _log(f"CAMPAIGN_STOP seen and all queues drained, failures={failures}")
            return 1 if failures else 0
        if pending_total == 0:
            time.sleep(20)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, help="one-shot mode")
    parser.add_argument("--watch-dir", type=Path, help="watch mode queue directory")
    parser.add_argument(
        "--watch-root", type=Path,
        help="campaign mode: follow every <root>/<run-tag>/queue, including "
             "tags that appear later, and exit only on <root>/CAMPAIGN_STOP",
    )
    parser.add_argument("--output", type=Path, help="one-shot output file")
    parser.add_argument("--output-dir", type=Path, help="watch mode output directory")
    parser.add_argument("--manifest", default="prep/data/dataset_manifest.json")
    parser.add_argument("--splits", default="prep/splits.json")
    parser.add_argument("--geometry", default="prep/geometry_frozen")
    parser.add_argument("--pilot-splits", default="prep/training_pilot_splits.json")
    parser.add_argument("--n-events", type=int, default=2000)
    parser.add_argument("--selection-seed", type=int, default=20260803)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--kinetic-low", type=float, default=50.0)
    parser.add_argument("--kinetic-high", type=float, default=250.0)
    parser.add_argument(
        "--energy-bin-edges", type=float, nargs="+",
        default=[50, 75, 100, 125, 150, 175, 200, 225, 250.0001],
        help="fallback only; the checkpoint's own frozen config wins. The last "
             "edge sits just above the range so the half-open [low, high) "
             "still catches events at exactly 250",
    )
    parser.add_argument(
        "--gates", default="repo/configs/gates_primary.yaml",
        help="versioned diagnostic thresholds; reported informationally only",
    )
    parser.add_argument("--device", default="cuda")
    args = parser.parse_args(argv)

    modes = [bool(args.checkpoint), bool(args.watch_dir), bool(args.watch_root)]
    if sum(modes) != 1:
        parser.error("give exactly one of --checkpoint, --watch-dir or --watch-root")
    if args.checkpoint and not args.output:
        parser.error("--checkpoint requires --output")
    if args.watch_dir and not args.output_dir:
        parser.error("--watch-dir requires --output-dir")

    context = DiagnosticContext(args)

    if args.watch_root:
        return watch_root(context, args.watch_root)

    if args.watch_dir:
        return watch(context, args.watch_dir, args.output_dir)

    result = run_one(context, args.checkpoint)
    dump_json(result, args.output)
    _log(
        f"wrote {args.output} epoch={result['epoch']} n={result['n_events']} "
        f"response_bias={result['trend']['response_bias_fraction']:+.6f} "
        f"+/- {result['trend_stderr']['response_bias_fraction']:.6f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
