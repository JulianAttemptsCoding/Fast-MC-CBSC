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
        --output _diag/metrics.json

Watch, which is how it is used alongside a training run -- build the dataset
once, then process each epoch's checkpoint as it is dropped into the queue:

    .venv_3090/bin/python repo/scripts/dicos_diagnostics.py \
        --n-events 4000 --watch-dir _diag/queue --output-dir _diag

Building the dataset verifies all 187 shards and reads every one to apply the
kinetic filter, which takes minutes; watch mode pays that once rather than per
epoch, and holding one context also fixes the sampled events across epochs,
which is what makes the epoch-to-epoch comparison like-for-like.
"""

from __future__ import annotations

import argparse
import json
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
from cbsc_zdc.eval.visualization import fixed_validation_indices  # noqa: E402
from cbsc_zdc.utils import dump_json, environment_snapshot, sha256_file  # noqa: E402


def _log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


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


def run_one(context: DiagnosticContext, checkpoint: Path) -> dict:
    started = time.time()
    payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
    epoch = int(payload.get("epoch", -1))
    del payload
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
    result["qa"]["pass"] = (
        result["qa"]["test_events_used"] == 0
        and result["qa"]["generated_nonfinite"] == 0
        and result["qa"]["generated_negative"] == 0
    )
    return result


def watch(context: DiagnosticContext, queue_dir: Path, output_dir: Path) -> int:
    """Process checkpoints dropped into `queue_dir` until a `STOP` file appears.

    The producer copies an epoch's checkpoint in; this consumes it and leaves a
    metrics file behind. A failed checkpoint is set aside rather than retried
    forever, so one bad file cannot stall the queue.
    """
    queue_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    done_dir = queue_dir / "done"
    done_dir.mkdir(exist_ok=True)
    _log(f"watching {queue_dir}")

    while True:
        if (queue_dir / "STOP").exists():
            _log("STOP seen, exiting")
            return 0
        pending = sorted(p for p in queue_dir.glob("*.pt") if p.is_file())
        if not pending:
            time.sleep(20)
            continue
        for checkpoint in pending:
            try:
                result = run_one(context, checkpoint)
            except Exception as exc:  # noqa: BLE001 -- recorded, loop continues
                _log(f"FAILED {checkpoint.name}: {type(exc).__name__}: {exc}")
                checkpoint.rename(done_dir / (checkpoint.name + ".failed"))
                continue
            out = output_dir / f"metrics_epoch_{result['epoch']:04d}.json"
            dump_json(result, out)
            _log(
                f"wrote {out.name} epoch={result['epoch']} n={result['n_events']} "
                f"response_bias={result['trend']['response_bias_fraction']:+.6f} "
                f"+/- {result['trend_stderr']['response_bias_fraction']:.6f}"
            )
            checkpoint.rename(done_dir / checkpoint.name)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, help="one-shot mode")
    parser.add_argument("--watch-dir", type=Path, help="watch mode queue directory")
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
    parser.add_argument("--device", default="cuda")
    args = parser.parse_args(argv)

    if bool(args.checkpoint) == bool(args.watch_dir):
        parser.error("give exactly one of --checkpoint or --watch-dir")
    if args.checkpoint and not args.output:
        parser.error("--checkpoint requires --output")
    if args.watch_dir and not args.output_dir:
        parser.error("--watch-dir requires --output-dir")

    context = DiagnosticContext(args)

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
