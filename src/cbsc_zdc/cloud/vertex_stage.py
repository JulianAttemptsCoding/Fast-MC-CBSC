from __future__ import annotations

import argparse
import json
import shutil
import traceback
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import numpy as np
import torch

from ..config import validate_config
from ..contracts import NEUTRON_MASS_GEV
from ..data.dataset import load_geometry
from ..eval.benchmark import benchmark_model
from ..eval.evaluator import evaluate_checkpoint
from ..eval.invariants import closure_tolerances, invariant_report
from ..models.system import CBSCZDC
from ..training.checkpoint import load_checkpoint
from ..training.trainer import train_from_config
from ..utils import (
    dump_json,
    dump_yaml,
    environment_snapshot,
    load_yaml,
    sha256_file,
)


def _parse_gs(uri: str) -> tuple[str, str]:
    parsed = urlparse(uri)
    if parsed.scheme != "gs" or not parsed.netloc:
        raise ValueError(f"expected gs://bucket/prefix, got {uri}")
    return parsed.netloc, parsed.path.lstrip("/").rstrip("/")


def _listing_prefix(prefix: str) -> str:
    """Return an object-prefix boundary that cannot match sibling directories."""
    return f"{prefix}/" if prefix else ""


def download_prefix(
    uri: str,
    destination: Path,
    *,
    fail_on_existing: bool = False,
) -> list[dict]:
    try:
        from google.cloud import storage  # type: ignore
    except ImportError as exc:
        raise RuntimeError("install the cloud extra: pip install '.[cloud]'") from exc
    bucket_name, prefix = _parse_gs(uri)
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    listing_prefix = _listing_prefix(prefix)
    found = 0
    manifest = []
    for blob in client.list_blobs(bucket, prefix=listing_prefix):
        if blob.name.endswith("/"):
            continue
        relative = (
            blob.name[len(listing_prefix):] if listing_prefix else blob.name
        )
        target = destination / relative
        if fail_on_existing and target.exists():
            raise RuntimeError(
                f"overlay collision for {relative} while downloading {uri}"
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        blob.download_to_filename(target)
        manifest.append(
            {
                "source_prefix": uri,
                "name": blob.name,
                "generation": str(blob.generation),
                "size": int(blob.size or 0),
                "crc32c": blob.crc32c,
                "relative_path": relative,
            }
        )
        found += 1
    if found == 0:
        raise RuntimeError(f"no objects found under {uri}")
    return manifest


def upload_directory(source: Path, uri: str) -> None:
    try:
        from google.cloud import storage  # type: ignore
    except ImportError as exc:
        raise RuntimeError("install the cloud extra: pip install '.[cloud]'") from exc
    bucket_name, prefix = _parse_gs(uri)
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(source).as_posix()
        name = f"{prefix}/{relative}" if prefix else relative
        bucket.blob(name).upload_from_filename(path)


def upload_directory_once(source: Path, uri: str) -> None:
    """Upload an immutable snapshot, failing on any pre-existing object."""
    try:
        from google.cloud import storage  # type: ignore
    except ImportError as exc:
        raise RuntimeError("install the cloud extra: pip install '.[cloud]'") from exc
    bucket_name, prefix = _parse_gs(uri)
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(source).as_posix()
        name = f"{prefix}/{relative}" if prefix else relative
        bucket.blob(name).upload_from_filename(path, if_generation_match=0)


def _resolve_staged_checkpoints(config: dict[str, Any], downloaded_root: Path) -> None:
    training = config["training"]
    for field in (
        "initialize_from",
        "resume_from",
        "resume_progress_from",
        "resume_best_from",
    ):
        relative_field = f"{field}_relative"
        hash_field = f"{field}_sha256"
        relative = training.get(relative_field)
        if relative is None:
            continue
        target = (downloaded_root / str(relative)).resolve()
        try:
            target.relative_to(downloaded_root.resolve())
        except ValueError as exc:
            raise RuntimeError(
                f"training.{relative_field} escapes the staged input root"
            ) from exc
        if not target.is_file():
            raise FileNotFoundError(
                f"staged checkpoint not found for training.{relative_field}: {target}"
            )
        expected = str(training[hash_field])
        actual = sha256_file(target)
        if actual != expected:
            raise RuntimeError(
                f"staged checkpoint hash mismatch for {relative}: "
                f"expected {expected}, got {actual}"
            )
        training[field] = str(target)


def build_runtime_config(
    downloaded_root: Path,
    config_relative: str,
    manifest_relative: str,
    splits_relative: str,
    geometry_relative: str,
    run_dir: Path,
    output_path: Path,
    device: str,
    resolve_training_checkpoints: bool = True,
) -> dict:
    template_path = downloaded_root / config_relative
    config = load_yaml(template_path)
    config["data"]["manifest"] = str((downloaded_root / manifest_relative).resolve())
    config["data"]["splits"] = str((downloaded_root / splits_relative).resolve())
    config["geometry"]["path"] = str((downloaded_root / geometry_relative).resolve())
    config["project"]["run_dir"] = str(run_dir.resolve())
    config["training"]["device"] = device
    config.setdefault("provenance", {})["vertex_staged_config_source"] = str(template_path)
    if resolve_training_checkpoints:
        _resolve_staged_checkpoints(config, downloaded_root)
    validate_config(config)
    dump_yaml(config, output_path)
    return config


def run_smoke_postflight(config: dict, training_result: dict, run_dir: Path) -> dict:
    device = torch.device(config["training"]["device"])
    geometry = load_geometry(config["geometry"]["path"], device)
    model = CBSCZDC(geometry, config).to(device).eval()
    load_checkpoint(training_result["best_checkpoint"], model, map_location=device)

    kinetic = torch.tensor(
        [0.0, 50.0, 150.0, 250.0, 300.0],
        device=device,
        dtype=torch.float64,
    )
    total = kinetic + NEUTRON_MASS_GEV
    momentum = torch.sqrt(torch.clamp(total.square() - NEUTRON_MASS_GEV**2, min=0.0))
    p4 = torch.stack(
        [total, torch.zeros_like(total), torch.zeros_like(total), momentum], dim=1
    ).to(torch.float32)
    output = model.sample(p4, profile_steps=1, share_steps=1, seed=20260724)
    _absolute, _relative = closure_tolerances(config)
    invariants = invariant_report(
        output,
        model.layer_index,
        model.valid_mask,
        model.threshold_gev,
        _absolute,
        _relative,
    )
    dump_json(invariants, run_dir / "reports/smoke_invariants.json")
    if not invariants["pass"]:
        raise RuntimeError("Vertex smoke checkpoint reload/sample invariant gate failed")

    np.savez_compressed(
        run_dir / "reports/smoke_samples.npz",
        p4_total_gev=p4.cpu().numpy(),
        kinetic_energy_gev=kinetic.cpu().numpy().astype(np.float32),
        cell_energy_gev=output.cell_energy.cpu().numpy(),
        layer_energy_gev=output.layer_energy.cpu().numpy(),
        counts=output.realized_counts.cpu().numpy(),
        support_mask=output.support_mask.cpu().numpy(),
    )
    timing = benchmark_model(
        model,
        p4[:2],
        warmup=1,
        iterations=2,
        profile_steps=1,
        share_steps=1,
    )
    dump_json(timing, run_dir / "reports/smoke_timing.json")
    validation = evaluate_checkpoint(
        training_result["best_checkpoint"],
        config["geometry"]["path"],
        config["data"]["manifest"],
        config["data"]["splits"],
        "validation",
        run_dir / "reports/smoke_validation.json",
        device=str(device),
        batch_size=16,
        max_events=None,
        gates_path=None,
        seed=int(config["training"]["seed"]),
    )
    if device.type != "cuda":
        raise RuntimeError("Vertex target-hardware smoke unexpectedly ran without CUDA")
    total_memory = int(torch.cuda.get_device_properties(device).total_memory)
    peak_memory = int(torch.cuda.max_memory_allocated(device))
    headroom_fraction = 1.0 - (peak_memory / max(total_memory, 1))
    resource_report = {
        "device": str(device),
        "device_name": torch.cuda.get_device_name(device),
        "total_memory_bytes": total_memory,
        "peak_memory_bytes": peak_memory,
        "headroom_fraction": headroom_fraction,
        "minimum_headroom_fraction": 0.15,
        "pass": headroom_fraction >= 0.15,
    }
    dump_json(resource_report, run_dir / "reports/smoke_resources.json")
    if not resource_report["pass"]:
        raise RuntimeError(
            "Vertex smoke GPU memory headroom gate failed: "
            f"headroom={headroom_fraction:.3%}"
        )
    return {
        "pass": True,
        "invariants": invariants,
        "timing": timing,
        "validation_events": validation["n_events"],
        "resources": resource_report,
    }


def run_training_postflight(
    config: dict, training_result: dict, run_dir: Path
) -> dict:
    """Reload a training checkpoint and run full configured structural/timing QA."""
    device = torch.device(config["training"]["device"])
    geometry = load_geometry(config["geometry"]["path"], device)
    model = CBSCZDC(geometry, config).to(device).eval()
    load_checkpoint(training_result["best_checkpoint"], model, map_location=device)
    kinetic = torch.tensor(
        [0.0, 50.0, 100.0, 150.0, 200.0, 250.0, 300.0],
        device=device,
        dtype=torch.float64,
    )
    total = kinetic + NEUTRON_MASS_GEV
    momentum = torch.sqrt(torch.clamp(total.square() - NEUTRON_MASS_GEV**2, min=0.0))
    p4 = torch.stack(
        [total, torch.zeros_like(total), torch.zeros_like(total), momentum], dim=1
    ).to(torch.float32)
    profile_steps = int(config["evaluation"].get("profile_steps", 8))
    share_steps = int(config["evaluation"].get("share_steps", 8))
    output = model.sample(
        p4,
        profile_steps=profile_steps,
        share_steps=share_steps,
        seed=int(config["training"]["seed"]),
    )
    _absolute, _relative = closure_tolerances(config)
    invariants = invariant_report(
        output,
        model.layer_index,
        model.valid_mask,
        model.threshold_gev,
        _absolute,
        _relative,
    )
    dump_json(invariants, run_dir / "reports/training_postflight_invariants.json")
    if not invariants["pass"]:
        raise RuntimeError("training checkpoint reload/sample invariant gate failed")
    timing = benchmark_model(
        model,
        p4[:2],
        warmup=1,
        iterations=2,
        profile_steps=profile_steps,
        share_steps=share_steps,
    )
    dump_json(timing, run_dir / "reports/training_postflight_timing.json")
    if device.type != "cuda":
        raise RuntimeError("training postflight unexpectedly ran without CUDA")
    total_memory = int(torch.cuda.get_device_properties(device).total_memory)
    peak_memory = int(torch.cuda.max_memory_allocated(device))
    headroom_fraction = 1.0 - (peak_memory / max(total_memory, 1))
    resources = {
        "device": str(device),
        "device_name": torch.cuda.get_device_name(device),
        "total_memory_bytes": total_memory,
        "peak_memory_bytes": peak_memory,
        "headroom_fraction": headroom_fraction,
        "minimum_headroom_fraction": 0.15,
        "pass": headroom_fraction >= 0.15,
    }
    dump_json(resources, run_dir / "reports/training_postflight_resources.json")
    if not resources["pass"]:
        raise RuntimeError(
            "training postflight GPU memory headroom gate failed: "
            f"headroom={headroom_fraction:.3%}"
        )
    result = {
        "pass": True,
        "checkpoint_reloaded": training_result["best_checkpoint"],
        "fixed_conditions_kinetic_gev": kinetic.cpu().tolist(),
        "invariants": invariants,
        "timing": timing,
        "resources": resources,
    }
    dump_json(result, run_dir / "reports/training_postflight.json")
    return result


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Stage CBSC-ZDC artifacts from GCS, train, and upload the run")
    parser.add_argument("--input-prefix", required=True, help="gs:// bucket prefix containing frozen inputs")
    parser.add_argument(
        "--overlay-prefix",
        action="append",
        default=[],
        help="additional gs:// prefix downloaded over the base input; collisions fail",
    )
    parser.add_argument("--output-prefix", required=True, help="gs:// bucket prefix for run artifacts")
    parser.add_argument("--config-relative", required=True)
    parser.add_argument("--manifest-relative", default="artifacts/data/dataset_manifest.json")
    parser.add_argument("--splits-relative", default="artifacts/splits.json")
    parser.add_argument("--geometry-relative", default="artifacts/geometry")
    parser.add_argument("--work-dir", default="/tmp/cbsc_zdc")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--postflight-smoke", action="store_true")
    parser.add_argument("--postflight-training", action="store_true")
    args = parser.parse_args(argv)

    work = Path(args.work_dir)
    downloaded = work / "input"
    run_dir = work / "run"
    downloaded.mkdir(parents=True, exist_ok=True)
    staged_inputs = download_prefix(args.input_prefix, downloaded)
    for overlay_prefix in args.overlay_prefix:
        staged_inputs.extend(
            download_prefix(
                overlay_prefix,
                downloaded,
                fail_on_existing=True,
            )
        )
    runtime_path = work / "runtime_config.yaml"
    config = build_runtime_config(
        downloaded, args.config_relative, args.manifest_relative, args.splits_relative,
        args.geometry_relative, run_dir, runtime_path, args.device,
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    dump_yaml(config, run_dir / "runtime_config.yaml")
    dump_json(staged_inputs, run_dir / "staged_input_manifest.json")
    try:
        def upload_epoch_snapshot(epoch, run, row):
            snapshot = {
                "epoch": int(epoch),
                "row": row,
                "best_checkpoint_sha256": sha256_file(run.checkpoints / "best.pt"),
                "last_checkpoint_sha256": sha256_file(run.checkpoints / "last.pt"),
            }
            dump_json(
                snapshot,
                run.reports / f"progress_epoch_{epoch:04d}.json",
            )
            upload_directory_once(
                run.root,
                f"{args.output_prefix}/progress/epoch_{epoch:04d}",
            )

        def upload_mid_epoch_snapshot(progress, run, progress_path):
            epoch = int(progress["epoch"])
            updates = int(progress["updates"])
            snapshot_root = (
                work
                / "mid_epoch_upload"
                / f"epoch_{epoch:04d}"
                / f"update_{updates:08d}"
            )
            checkpoint_root = snapshot_root / "checkpoints"
            checkpoint_root.mkdir(parents=True, exist_ok=False)
            local_progress = checkpoint_root / "progress.pt"
            shutil.copy2(progress_path, local_progress)
            best_path = run.checkpoints / "best.pt"
            best_hash = None
            if best_path.exists():
                shutil.copy2(best_path, checkpoint_root / "best.pt")
                best_hash = sha256_file(best_path)
            dump_json(
                {
                    "progress": progress,
                    "progress_checkpoint_sha256": sha256_file(local_progress),
                    "best_checkpoint_sha256": best_hash,
                    "stage": str(config["training"].get("stage", "joint")),
                    "config_sha256": sha256_file(runtime_path),
                },
                snapshot_root / "progress.json",
            )
            upload_directory_once(
                snapshot_root,
                (
                    f"{args.output_prefix}/progress/"
                    f"inflight_epoch_{epoch:04d}/update_{updates:08d}"
                ),
            )

        result = train_from_config(
            config,
            epoch_callback=upload_epoch_snapshot,
            progress_callback=upload_mid_epoch_snapshot,
        )
        smoke_postflight = (
            run_smoke_postflight(config, result, run_dir)
            if args.postflight_smoke
            else None
        )
        training_postflight = (
            run_training_postflight(config, result, run_dir)
            if args.postflight_training
            else None
        )
        dump_json(
            {
                "runtime_config": str(runtime_path),
                "training": result,
                "smoke_postflight": smoke_postflight,
                "training_postflight": training_postflight,
            },
            run_dir / "vertex_result.json",
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
            run_dir / "vertex_failure.json",
        )
        upload_directory_once(run_dir, args.output_prefix)
        raise
    upload_directory_once(run_dir, args.output_prefix)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
