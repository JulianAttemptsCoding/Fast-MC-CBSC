"""One-off diagnostic: paired Geant4/Fast-MC HCAL comparison sample.

Draws N random events from the full prepared corpus (explicitly including the
sealed test split, by deliberate user instruction for this one-off task
only -- see logs.md for the disclosure this run requires), and for each one
generates exactly one Fast-MC event from the same incident four-momentum
using a single accepted checkpoint. Writes raw per-event arrays; no plots are
built here, since plotting needs no GPU and happens locally afterward.

This module is a new sibling entrypoint, not a modification of vertex_stage.py:
its container `command` is overridden at submission time
(`["python", "-m", "cbsc_zdc.cloud.paired_diagnostics"]`) rather than the
default ENTRYPOINT, so the existing training path is untouched.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path

import numpy as np
import torch

from ..data.dataset import ShardedSparseDataset, load_geometry
from ..eval.visualization import fixed_validation_indices
from ..models.system import CBSCZDC
from ..utils import dump_json, environment_snapshot, sha256_file
from .vertex_stage import download_prefix, upload_directory

LOCAL_ROOT = Path("/tmp/paired_diagnostics")


def _log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def _download_blob(uri: str, destination: Path) -> None:
    from google.cloud import storage  # type: ignore
    from urllib.parse import urlparse

    parsed = urlparse(uri)
    if parsed.scheme != "gs" or not parsed.netloc:
        raise ValueError(f"expected gs://bucket/object, got {uri}")
    bucket_name = parsed.netloc
    blob_name = parsed.path.lstrip("/")
    destination.parent.mkdir(parents=True, exist_ok=True)
    storage.Client().bucket(bucket_name).blob(blob_name).download_to_filename(destination)


def load_model(checkpoint_path: Path, geometry: dict, device: torch.device) -> CBSCZDC:
    payload = torch.load(checkpoint_path, map_location=device, weights_only=False)
    model = CBSCZDC(geometry, payload["config"]).to(device).eval()
    model.load_state_dict(payload["model_state"])
    return model


def generate_paired_sample(
    dataset: ShardedSparseDataset,
    model: CBSCZDC,
    device: torch.device,
    seed: int,
    batch_size: int = 32,
    profile_steps: int = 8,
    share_steps: int = 8,
    log=_log,
) -> dict[str, np.ndarray]:
    """Batch through `dataset` (already restricted to the selected indices),
    generating one paired Fast-MC event per real event."""
    n_events = len(dataset)
    truth = np.zeros((n_events, model.n_nodes), dtype=np.float32)
    generated = np.zeros((n_events, model.n_nodes), dtype=np.float32)
    p4_total = np.zeros((n_events, 4), dtype=np.float32)
    kinetic = np.zeros(n_events, dtype=np.float32)
    global_index = np.zeros(n_events, dtype=np.int64)

    start = 0
    current_batch = int(batch_size)
    while start < n_events:
        stop = min(start + current_batch, n_events)
        items = [dataset[i] for i in range(start, stop)]
        p4 = torch.stack([item["p4_total_gev"] for item in items]).to(device)
        try:
            with torch.no_grad():
                output = model.sample(
                    p4, profile_steps=profile_steps, share_steps=share_steps,
                    seed=seed + start, stochastic=True,
                )
        except torch.cuda.OutOfMemoryError:
            if current_batch <= 1:
                raise
            current_batch = max(1, current_batch // 2)
            torch.cuda.empty_cache()
            log(f"CUDA OOM: reducing generation batch to {current_batch}")
            continue
        truth[start:stop] = torch.stack([item["cell_energy_gev"] for item in items]).numpy()
        generated[start:stop] = output.cell_energy.detach().cpu().numpy()
        p4_total[start:stop] = p4.detach().cpu().numpy()
        kinetic[start:stop] = torch.stack([item["kinetic_energy_gev"] for item in items]).numpy()
        global_index[start:stop] = torch.stack([item["global_index"] for item in items]).numpy()
        log(f"generated {stop}/{n_events} (batch={current_batch})")
        start = stop

    return {
        "truth_cell_energy_gev": truth,
        "generated_cell_energy_gev": generated,
        "p4_total_gev": p4_total,
        "kinetic_energy_gev": kinetic,
        "global_index": global_index,
    }


def hcal_summary(cell_energy: np.ndarray, n_ecal: int, n_nodes: int) -> dict[str, np.ndarray]:
    """Per-event HCAL total/hit-count, and the pooled nonzero cell-energy spectrum."""
    hcal = cell_energy[:, n_ecal:n_nodes]
    total = hcal.sum(axis=1)
    hits = (hcal > 0).sum(axis=1)
    positive = hcal[hcal > 0]
    return {"total": total, "hits": hits, "positive_cells": positive}


def split_counts(global_index: np.ndarray, split_code: np.ndarray) -> dict[str, int]:
    codes = split_code[global_index]
    return {
        "train": int((codes == 0).sum()),
        "validation": int((codes == 1).sum()),
        "test": int((codes == 2).sum()),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-prefix", required=True, help="prep-.../artifacts prefix")
    parser.add_argument("--checkpoint-uri", required=True)
    parser.add_argument("--checkpoint-sha256", required=True)
    parser.add_argument("--output-prefix", required=True)
    parser.add_argument("--n-events", type=int, default=2000)
    parser.add_argument("--selection-seed", type=int, default=20260730)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--device", default="cuda")
    args = parser.parse_args(argv)

    started = time.time()
    data_root = LOCAL_ROOT / "data"
    output_root = LOCAL_ROOT / "output"
    output_root.mkdir(parents=True, exist_ok=True)

    result = {
        "schema_version": 1,
        "experiment": "paired_geant4_fastmc_hcal_diagnostics",
        "note": (
            "Deliberate exception, explicitly authorized by the project owner: "
            "sampled from the FULL prepared corpus, which includes the sealed "
            "test split. This feeds no preprocessing, threshold, architecture, "
            "loss-weight, learning-rate, stopping, or checkpoint-selection "
            "decision -- see logs.md for the full disclosure. See "
            "'split_counts' below for the exact train/validation/test "
            "breakdown of the events actually sampled."
        ),
        "data_prefix": args.data_prefix,
        "checkpoint_uri": args.checkpoint_uri,
        "output_prefix": args.output_prefix,
        "environment": environment_snapshot(),
    }
    try:
        _log("staging prepared corpus")
        result["data_inventory_count"] = len(download_prefix(args.data_prefix, data_root))

        _log("staging checkpoint")
        checkpoint_path = output_root / "checkpoint.pt"
        _download_blob(args.checkpoint_uri, checkpoint_path)
        checkpoint_sha256 = sha256_file(checkpoint_path)
        if checkpoint_sha256 != args.checkpoint_sha256:
            raise ValueError(
                f"checkpoint hash mismatch: got {checkpoint_sha256}, expected {args.checkpoint_sha256}"
            )
        result["checkpoint_sha256"] = checkpoint_sha256

        manifest_path = data_root / "data" / "dataset_manifest.json"
        geometry_dir = data_root / "geometry"
        splits_path = data_root / "splits.json"
        splits_manifest = json.loads(splits_path.read_text("utf-8"))
        dataset_manifest_sha256 = sha256_file(manifest_path)
        if splits_manifest.get("manifest_sha256") != dataset_manifest_sha256:
            raise RuntimeError("splits.json does not match the staged dataset manifest")
        assignment_path = splits_path.parent / splits_manifest["assignment_file"]
        if sha256_file(assignment_path) != splits_manifest.get("assignment_sha256"):
            raise RuntimeError(f"split assignment hash mismatch: {assignment_path}")
        split_code = np.load(assignment_path)["split_code"]
        result["dataset_manifest_sha256"] = dataset_manifest_sha256
        result["splits_manifest_sha256"] = sha256_file(splits_path)

        device = torch.device(args.device)
        if device.type == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("cuda requested but unavailable")

        geometry = load_geometry(geometry_dir, device)
        n_ecal = int((geometry["subdetector"] == 0).sum())
        n_nodes = int(geometry["subdetector"].shape[0])

        full = ShardedSparseDataset(manifest_path, None, None, None, n_nodes)
        total_events = len(full)
        if len(split_code) != total_events:
            raise RuntimeError(
                f"split assignment length {len(split_code)} does not match corpus {total_events}"
            )
        selected = fixed_validation_indices(total_events, args.n_events, args.selection_seed)
        full.indices = np.asarray(sorted(selected), dtype=np.int64)
        _log(f"selected {len(full)} events from the full {total_events}-event corpus")

        model = load_model(checkpoint_path, geometry, device)
        sample = generate_paired_sample(
            full, model, device, seed=args.selection_seed, batch_size=args.batch_size, log=_log,
        )

        counts = split_counts(sample["global_index"], split_code)
        result["split_counts"] = counts
        _log(f"split breakdown of sampled events: {counts}")

        truth_hcal = hcal_summary(sample["truth_cell_energy_gev"], n_ecal, n_nodes)
        generated_hcal = hcal_summary(sample["generated_cell_energy_gev"], n_ecal, n_nodes)

        np.savez_compressed(
            output_root / "results.npz",
            kinetic_energy_gev=sample["kinetic_energy_gev"],
            global_index=sample["global_index"],
            split_code_per_event=split_code[sample["global_index"]],
            truth_hcal_total_gev=truth_hcal["total"],
            truth_hcal_hits=truth_hcal["hits"],
            truth_hcal_positive_cells_gev=truth_hcal["positive_cells"],
            generated_hcal_total_gev=generated_hcal["total"],
            generated_hcal_hits=generated_hcal["hits"],
            generated_hcal_positive_cells_gev=generated_hcal["positive_cells"],
        )

        result["state"] = "SUCCEEDED"
        result["n_events_sampled"] = len(full)
        result["n_ecal"] = n_ecal
        result["n_nodes"] = n_nodes
    except Exception as exc:  # noqa: BLE001 - the failure itself is evidence
        result["state"] = "FAILED"
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["traceback"] = traceback.format_exc()
        _log(result["traceback"])
    finally:
        result["seconds"] = time.time() - started
        dump_json(result, output_root / "vertex_result.json")
        try:
            upload_directory(output_root, args.output_prefix)
        except Exception as exc:  # noqa: BLE001
            _log(f"upload failed: {exc}")
            return 2
    return 0 if result["state"] == "SUCCEEDED" else 1


if __name__ == "__main__":
    sys.exit(main())
