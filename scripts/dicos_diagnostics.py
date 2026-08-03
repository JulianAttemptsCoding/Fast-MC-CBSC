"""Larger validation-only diagnostic sample for one checkpoint, on DiCOS.

The published per-epoch payload rests on 50 conditions x 5 draws = 250 events,
which is thin for distribution metrics. This generates an arbitrarily larger
paired Geant4/Fast-MC sample from the **validation partition only** and reports
the same `trend` quantities the site already carries, so the two are directly
comparable and the larger sample simply has tighter errors.

Differences from `cbsc_zdc.cloud.paired_diagnostics`, which this reuses:

  * that module is GCS-coupled; this reads and writes the shared filesystem;
  * that module deliberately sampled the FULL corpus **including the sealed
    test split**, as a one-off authorised on 2026-07-30. **This one never
    does.** The dataset is constructed with `split="validation"`, which filters
    on the split code at construction, and the test count is asserted zero
    afterwards from the assignment array as an independent check.

Usage (on the host, from the workdir):
    .venv_3090/bin/python repo/scripts/dicos_diagnostics.py \
        --checkpoint _diag/ckpt_epoch_0017.pt \
        --n-events 2000 \
        --output _diag/metrics_epoch_0017.json
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


def longitudinal_profile(cell_energy: np.ndarray, layer_index: np.ndarray,
                         n_layers: int) -> np.ndarray:
    """Mean energy per layer, averaged over events."""
    profile = np.zeros((cell_energy.shape[0], n_layers), dtype=np.float64)
    for layer in range(n_layers):
        mask = layer_index == layer
        if mask.any():
            profile[:, layer] = cell_energy[:, mask].sum(axis=1)
    return profile


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--manifest", default="prep/data/dataset_manifest.json")
    parser.add_argument("--splits", default="prep/splits.json")
    parser.add_argument("--geometry", default="prep/geometry_frozen")
    parser.add_argument(
        "--pilot-splits",
        default="prep/training_pilot_splits.json",
        help="only to report how many sampled events the model was validated on",
    )
    parser.add_argument("--n-events", type=int, default=2000)
    parser.add_argument("--selection-seed", type=int, default=20260803)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--kinetic-low", type=float, default=50.0)
    parser.add_argument("--kinetic-high", type=float, default=250.0)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    started = time.time()
    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("cuda requested but unavailable")

    geometry = load_geometry(args.geometry, device)
    n_nodes = int(geometry["subdetector"].shape[0])
    n_ecal = int((geometry["subdetector"] == 0).sum())
    layer_index = geometry["layer_index"].cpu().numpy()
    n_layers = int(layer_index.max()) + 1

    # split="validation" filters on the split code at construction. This is the
    # guarantee that no test event can enter the sample.
    dataset = ShardedSparseDataset(
        args.manifest,
        args.splits,
        "validation",
        (args.kinetic_low, args.kinetic_high),
        n_nodes,
    )
    pool = len(dataset)
    _log(f"validation pool in [{args.kinetic_low}, {args.kinetic_high}] GeV: {pool}")

    count = min(int(args.n_events), pool)
    chosen = fixed_validation_indices(pool, count, args.selection_seed)
    dataset.indices = dataset.indices[np.asarray(sorted(chosen), dtype=np.int64)]
    _log(f"sampling {len(dataset)} validation events")

    payload = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    epoch = int(payload.get("epoch", -1))
    del payload
    model = load_model(args.checkpoint, geometry, device)

    sample = generate_paired_sample(
        dataset, model, device, seed=args.selection_seed,
        batch_size=args.batch_size, log=_log,
    )

    # Independent check that the split filter did what it claims.
    splits_manifest = json.loads(Path(args.splits).read_text("utf-8"))
    assignment = np.load(
        Path(args.splits).parent / splits_manifest["assignment_file"],
        allow_pickle=False,
    )["split_code"]
    codes = assignment[sample["global_index"]]
    counts = {
        "train": int((codes == 0).sum()),
        "validation": int((codes == 1).sum()),
        "test": int((codes == 2).sum()),
    }
    if counts["test"] != 0 or counts["train"] != 0:
        raise RuntimeError(f"non-validation events entered the sample: {counts}")

    # How many sampled events the model was actually validated on during
    # training. The pilot validation partition is a subset of this one, so most
    # of the sample is genuinely unseen.
    seen_in_pilot = None
    pilot_path = Path(args.pilot_splits)
    if pilot_path.is_file():
        pilot_manifest = json.loads(pilot_path.read_text("utf-8"))
        pilot_assignment = np.load(
            pilot_path.parent / pilot_manifest["assignment_file"], allow_pickle=False
        )["split_code"]
        seen_in_pilot = int(
            (pilot_assignment[sample["global_index"]] == 1).sum()
        )

    truth = sample["truth_cell_energy_gev"]
    generated = sample["generated_cell_energy_gev"]
    truth_hcal = hcal_summary(truth, n_ecal, n_nodes)
    generated_hcal = hcal_summary(generated, n_ecal, n_nodes)

    truth_total = truth.sum(axis=1)
    generated_total = generated.sum(axis=1)
    truth_hits = (truth > 0).sum(axis=1)
    generated_hits = (generated > 0).sum(axis=1)

    truth_profile = longitudinal_profile(truth, layer_index, n_layers).mean(axis=0)
    generated_profile = longitudinal_profile(
        generated, layer_index, n_layers
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
    # larger sample: with n events the mean's error falls as 1/sqrt(n).
    n = len(dataset)
    trend_stderr = {
        "response_bias_fraction": float(
            generated_total.std(ddof=1) / np.sqrt(n) / max(abs(truth_response_mean), 1e-9)
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
        "checkpoint": str(args.checkpoint),
        "checkpoint_sha256": sha256_file(args.checkpoint),
        "n_events": n,
        "validation_pool": pool,
        "kinetic_range_gev": [args.kinetic_low, args.kinetic_high],
        "selection_seed": args.selection_seed,
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

    dump_json(result, args.output)
    _log(f"wrote {args.output} epoch={epoch} n={n} "
         f"response_bias={trend['response_bias_fraction']:+.6f} "
         f"+/- {trend_stderr['response_bias_fraction']:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
