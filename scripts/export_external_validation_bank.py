"""Export the fixed paired validation bank used by accepted-best evaluators.

This is a one-shot RTX-3090 operation.  It generates one Fast-MC event for each
of the same 4,000 fixed validation events used by ``dicos_diagnostics.py`` and
writes a sparse, pair-grouped bank plus a self-contained provenance manifest.
The bank is downstream evidence only: it cannot select a CBSC checkpoint.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for entry in (ROOT, SRC):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from cbsc_zdc.cloud.paired_diagnostics import generate_paired_sample, load_model  # noqa: E402
from cbsc_zdc.utils import environment_snapshot, sha256_file  # noqa: E402
from scripts.dicos_diagnostics import DiagnosticContext  # noqa: E402


BANK_KIND = "cbsc-zdc-paired-validation-external-metric-bank"


def dense_pairs_to_sparse_arrays(
    truth: np.ndarray,
    generated: np.ndarray,
    p4_total_gev: np.ndarray,
    global_index: np.ndarray,
) -> dict[str, np.ndarray]:
    """Convert paired dense deposits into the Fast-MC-tester CSR contract."""
    truth = np.asarray(truth, dtype=np.float32)
    generated = np.asarray(generated, dtype=np.float32)
    p4 = np.asarray(p4_total_gev, dtype=np.float32)
    pair_id = np.asarray(global_index, dtype=np.int64)
    if truth.shape != generated.shape or truth.ndim != 2:
        raise ValueError("truth and generated deposits must have matching 2D shapes")
    n_pairs = truth.shape[0]
    if p4.shape != (n_pairs, 4) or pair_id.shape != (n_pairs,):
        raise ValueError("p4/global_index do not match the paired event count")
    if not np.isfinite(truth).all() or not np.isfinite(generated).all():
        raise ValueError("event bank contains nonfinite deposits")
    if np.any(truth < 0) or np.any(generated < 0):
        raise ValueError("event bank contains negative deposits")
    if len(np.unique(pair_id)) != n_pairs:
        raise ValueError("paired validation source indices are not unique")

    dense = np.concatenate([truth, generated], axis=0)
    rows, cols = np.nonzero(dense > 0)
    counts = np.bincount(rows, minlength=2 * n_pairs)
    event_ptr = np.zeros(2 * n_pairs + 1, dtype=np.int64)
    np.cumsum(counts, out=event_ptr[1:])
    return {
        "event_ptr": event_ptr,
        "cell_index": cols.astype(np.int32, copy=False),
        "cell_energy_gev": dense[rows, cols].astype(np.float32, copy=False),
        "p4_total_gev": np.concatenate([p4, p4], axis=0),
        "label": np.concatenate(
            [np.ones(n_pairs, dtype=np.int8), np.zeros(n_pairs, dtype=np.int8)]
        ),
        "family_id": np.concatenate(
            [-np.ones(n_pairs, dtype=np.int8), np.zeros(n_pairs, dtype=np.int8)]
        ),
        "source_event_id": np.concatenate(
            [pair_id, -np.ones(n_pairs, dtype=np.int64)]
        ),
        "pair_id": np.concatenate([pair_id, pair_id]),
        "cbsc_source_split_code": np.ones(2 * n_pairs, dtype=np.int8),
    }


def _write_npz_atomic(path: Path, arrays: dict[str, np.ndarray]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.npz")
    temporary.unlink(missing_ok=True)
    np.savez_compressed(temporary, **arrays)
    os.replace(temporary, path)


def _write_json_atomic(path: Path, payload: dict) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def export(args: argparse.Namespace) -> dict:
    checkpoint_hash = sha256_file(args.checkpoint)
    if checkpoint_hash != args.checkpoint_sha256:
        raise ValueError("checkpoint SHA-256 does not match the accepted-best contract")
    payload = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    epoch = int(payload.get("epoch", -1))
    embedded_metric = float(payload.get("best_metric", float("nan")))
    if epoch != args.epoch:
        raise ValueError(f"checkpoint epoch {epoch} != expected {args.epoch}")
    if not np.isclose(embedded_metric, args.validation_loss, rtol=0.0, atol=1e-12):
        raise ValueError("checkpoint best_metric does not match accepted validation loss")

    context = DiagnosticContext(args)
    model = load_model(args.checkpoint, context.geometry, context.device)
    sample = generate_paired_sample(
        context.dataset,
        model,
        context.device,
        seed=context.selection_seed,
        batch_size=context.batch_size,
        log=print,
    )
    del model
    if context.device.type == "cuda":
        torch.cuda.empty_cache()

    codes = context.assignment[sample["global_index"]]
    split_counts = {
        "train": int((codes == 0).sum()),
        "validation": int((codes == 1).sum()),
        "test": int((codes == 2).sum()),
    }
    if split_counts != {"train": 0, "validation": len(codes), "test": 0}:
        raise RuntimeError(f"non-validation event entered external bank: {split_counts}")

    arrays = dense_pairs_to_sparse_arrays(
        sample["truth_cell_energy_gev"],
        sample["generated_cell_energy_gev"],
        sample["p4_total_gev"],
        sample["global_index"],
    )
    _write_npz_atomic(args.output, arrays)
    geometry_file = Path(args.geometry) / "geometry.npz"
    manifest = {
        "schema_version": 1,
        "kind": BANK_KIND,
        "bank_file": args.output.name,
        "bank_sha256": sha256_file(args.output),
        "bank_bytes": args.output.stat().st_size,
        "family": args.family,
        "run_tag": args.run_tag,
        "epoch": epoch,
        "validation_loss": args.validation_loss,
        "checkpoint_sha256": checkpoint_hash,
        "split": "validation",
        "split_counts_source_pairs": split_counts,
        "cbsc_test_events_used": 0,
        "n_pairs": int(len(codes)),
        "n_events": int(2 * len(codes)),
        "n_nodes": int(context.n_nodes),
        "selection_seed": int(context.selection_seed),
        "selection_global_index_sha256": __import__("hashlib").sha256(
            np.asarray(sample["global_index"], dtype="<i8").tobytes()
        ).hexdigest(),
        "geometry_file_sha256": (
            sha256_file(geometry_file) if geometry_file.is_file() else None
        ),
        "environment": environment_snapshot(),
        "selection_role": "descriptive downstream evaluation only",
        "checkpoint_selection_quantity": "accepted validation loss only",
        "scientific_status": (
            "fixed CBSC validation bank; not a fidelity gate and not final test evidence"
        ),
        "qa": {
            "pass": True,
            "pair_ids_unique": True,
            "class_balance_exact": True,
            "nonfinite_deposits": 0,
            "negative_deposits": 0,
            "cbsc_test_events_used": 0,
        },
    }
    manifest_path = args.output.with_suffix(".manifest.json")
    _write_json_atomic(manifest_path, manifest)
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--checkpoint-sha256", required=True)
    parser.add_argument("--family", required=True)
    parser.add_argument("--run-tag", required=True)
    parser.add_argument("--epoch", type=int, required=True)
    parser.add_argument("--validation-loss", type=float, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", default="prep/data/dataset_manifest.json")
    parser.add_argument("--splits", default="prep/splits.json")
    parser.add_argument("--geometry", default="prep/geometry_frozen")
    parser.add_argument("--pilot-splits", default="prep/training_pilot_splits.json")
    parser.add_argument("--n-events", type=int, default=4000)
    parser.add_argument("--selection-seed", type=int, default=20260803)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--kinetic-low", type=float, default=50.0)
    parser.add_argument("--kinetic-high", type=float, default=250.0)
    parser.add_argument(
        "--energy-bin-edges",
        type=float,
        nargs="+",
        default=[50, 75, 100, 125, 150, 175, 200, 225, 250.0001],
    )
    parser.add_argument("--gates", default="repo/configs/gates_primary.yaml")
    parser.add_argument("--device", default="cuda")
    return parser


def main(argv: list[str] | None = None) -> int:
    manifest = export(build_parser().parse_args(argv))
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
