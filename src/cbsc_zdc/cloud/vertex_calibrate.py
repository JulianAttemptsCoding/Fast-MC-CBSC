from __future__ import annotations

import argparse
import json
import math
import time
import traceback
from pathlib import Path
from typing import Any

import torch

from ..data.dataset import ShardedSparseDataset, load_geometry
from ..models.system import CBSCZDC
from ..preflight import validate_frozen_artifacts
from ..training.checkpoint import load_checkpoint
from ..training.trainer import STAGE_LOSSES, compute_component_losses
from ..training.weights import calibrate_loss_weights
from ..utils import (
    dump_json,
    dump_yaml,
    environment_snapshot,
    seed_everything,
    sha256_file,
)
from .vertex_stage import (
    build_runtime_config,
    download_prefix,
    upload_directory_once,
)


def _resolve_staged_file(
    root: Path,
    relative: str,
    expected_sha256: str,
) -> Path:
    target = (root / relative).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError as exc:
        raise RuntimeError(
            f"staged calibration file escapes input root: {relative}"
        ) from exc
    if not target.is_file():
        raise FileNotFoundError(f"staged calibration file not found: {target}")
    actual = sha256_file(target)
    if actual != expected_sha256:
        raise RuntimeError(
            "staged calibration file hash mismatch: "
            f"expected={expected_sha256}, actual={actual}"
        )
    return target


def _assert_checkpoint_provenance(
    config: dict[str, Any],
    checkpoint_payload: dict[str, Any],
) -> dict[str, Any]:
    geometry_path = Path(config["geometry"]["path"])
    geometry_artifact = (
        geometry_path / "geometry.npz"
        if geometry_path.is_dir()
        else geometry_path
    )
    expected = {
        "geometry_sha256": sha256_file(geometry_artifact),
        "manifest_sha256": sha256_file(config["data"]["manifest"]),
        "splits_sha256": sha256_file(config["data"]["splits"]),
        "seed": int(config["training"]["seed"]),
    }
    actual = checkpoint_payload.get("provenance")
    if actual != expected:
        raise RuntimeError(
            "loss calibration checkpoint provenance mismatch: "
            f"expected={expected}, actual={actual}"
        )
    return expected


def run_calibration(
    config: dict[str, Any],
    checkpoint: Path,
    max_batches: int,
    clip_min: float,
    clip_max: float,
    report_dir: Path,
) -> dict[str, Any]:
    preflight = validate_frozen_artifacts(config, verify_shards=True)
    if preflight["selection_counts"]["test"] != 0:
        raise RuntimeError("loss calibration input must contain zero test events")
    if config["training"]["stage"] != "joint":
        raise RuntimeError("loss calibration requires a joint-stage config")
    device = torch.device(config["training"]["device"])
    if device.type != "cuda" or not torch.cuda.is_available():
        raise RuntimeError("loss calibration requires CUDA target hardware")
    seed = int(config["training"]["seed"])
    seed_everything(
        seed,
        bool(config["training"].get("deterministic_debug", False)),
    )
    geometry = load_geometry(config["geometry"]["path"], device)
    model = CBSCZDC(geometry, config).to(device)
    payload = load_checkpoint(
        checkpoint,
        model,
        map_location=device,
        expected_stage="joint",
    )
    checkpoint_provenance = _assert_checkpoint_provenance(config, payload)
    data = config["data"]
    dataset = ShardedSparseDataset(
        data["manifest"],
        data["splits"],
        "train",
        tuple(data["train_kinetic_gev"]),
        int(config["geometry"]["n_nodes"]),
    )
    generator = torch.Generator().manual_seed(seed)
    loader = torch.utils.data.DataLoader(
        dataset,
        batch_size=int(config["training"]["batch_size"]),
        shuffle=True,
        num_workers=0,
        generator=generator,
    )
    model.train()
    torch.cuda.reset_peak_memory_stats(device)

    def batches():
        for batch in loader:
            yield {key: value.to(device) for key, value in batch.items()}

    calibration_stages = ("response", "profile", "count", "support", "share")

    def loss_groups(batch):
        for stage in calibration_stages:
            yield compute_component_losses(model, batch, stage)[0]

    started = time.perf_counter()
    calibration = calibrate_loss_weights(
        model,
        batches(),
        None,
        max_batches=max_batches,
        clip=(clip_min, clip_max),
        expected_losses=STAGE_LOSSES["joint"],
        compute_loss_groups=loss_groups,
    )
    elapsed = time.perf_counter() - started
    total_memory = int(torch.cuda.get_device_properties(device).total_memory)
    peak_memory = int(torch.cuda.max_memory_allocated(device))
    headroom = 1.0 - peak_memory / max(total_memory, 1)
    resources = {
        "device": str(device),
        "device_name": torch.cuda.get_device_name(device),
        "total_memory_bytes": total_memory,
        "peak_memory_bytes": peak_memory,
        "headroom_fraction": headroom,
        "minimum_headroom_fraction": 0.15,
        "pass": headroom >= 0.15,
    }
    if not resources["pass"]:
        raise RuntimeError(
            "loss calibration GPU headroom gate failed: "
            f"headroom={headroom:.3%}"
        )
    if set(calibration["measured_components"]) != STAGE_LOSSES["joint"]:
        raise RuntimeError("loss calibration did not measure all nine components")
    if not all(
        math.isfinite(float(value)) and float(value) > 0
        for value in calibration["gradient_norm_median"].values()
    ):
        raise RuntimeError("loss calibration produced invalid gradient medians")
    if not all(
        math.isfinite(float(value)) and float(value) > 0
        for value in calibration["weights"].values()
    ):
        raise RuntimeError("loss calibration produced invalid proposed weights")
    report = {
        **calibration,
        "scientific_status": "train-only proposal; not validation selection",
        "split": "train",
        "test_events_used": 0,
        "memory_bounded_loss_groups": list(calibration_stages),
        "checkpoint": {
            "path": str(checkpoint),
            "sha256": sha256_file(checkpoint),
            "stage": payload["stage"],
            "epoch": int(payload["epoch"]),
            "best_metric": float(payload["best_metric"]),
            "provenance": checkpoint_provenance,
        },
        "elapsed_seconds": elapsed,
        "resources": resources,
        "preflight": preflight,
    }
    dump_json(report, report_dir / "loss_weight_calibration.json")
    dump_json(resources, report_dir / "calibration_resources.json")
    return report


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Run train-only CBSC-ZDC loss calibration on Vertex"
    )
    parser.add_argument("--input-prefix", required=True)
    parser.add_argument("--overlay-prefix", action="append", default=[])
    parser.add_argument("--output-prefix", required=True)
    parser.add_argument("--config-relative", required=True)
    parser.add_argument("--manifest-relative", default="artifacts/data/dataset_manifest.json")
    parser.add_argument("--splits-relative", default="artifacts/splits.json")
    parser.add_argument("--geometry-relative", default="artifacts/geometry")
    parser.add_argument("--checkpoint-relative", required=True)
    parser.add_argument("--checkpoint-sha256", required=True)
    parser.add_argument("--max-batches", type=int, default=64)
    parser.add_argument("--clip-min", type=float, default=0.25)
    parser.add_argument("--clip-max", type=float, default=4.0)
    parser.add_argument("--work-dir", default="/tmp/cbsc_zdc_calibration")
    parser.add_argument("--device", default="cuda")
    args = parser.parse_args(argv)

    work = Path(args.work_dir)
    downloaded = work / "input"
    output = work / "output"
    output.mkdir(parents=True, exist_ok=False)
    dump_json(environment_snapshot(), output / "environment.json")
    try:
        downloaded.mkdir(parents=True, exist_ok=False)
        staged = download_prefix(args.input_prefix, downloaded)
        for overlay in args.overlay_prefix:
            staged.extend(
                download_prefix(overlay, downloaded, fail_on_existing=True)
            )
        runtime_path = work / "runtime_config.yaml"
        config = build_runtime_config(
            downloaded,
            args.config_relative,
            args.manifest_relative,
            args.splits_relative,
            args.geometry_relative,
            output,
            runtime_path,
            args.device,
            resolve_training_checkpoints=False,
        )
        dump_yaml(config, output / "runtime_config.yaml")
        dump_json(staged, output / "staged_input_manifest.json")
        checkpoint = _resolve_staged_file(
            downloaded,
            args.checkpoint_relative,
            args.checkpoint_sha256,
        )
        report = run_calibration(
            config,
            checkpoint,
            args.max_batches,
            args.clip_min,
            args.clip_max,
            output / "reports",
        )
        dump_json(
            {
                "pass": True,
                "calibration": report,
                "runtime_config_sha256": sha256_file(runtime_path),
            },
            output / "vertex_calibration_result.json",
        )
    except Exception as exc:
        dump_json(
            {
                "pass": False,
                "exception_type": type(exc).__name__,
                "message": str(exc),
                "traceback": traceback.format_exc(),
                "environment": environment_snapshot(),
            },
            output / "vertex_failure.json",
        )
        upload_directory_once(output, args.output_prefix)
        raise
    upload_directory_once(output, args.output_prefix)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
