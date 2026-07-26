from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import yaml


COMPONENTS = {
    "visible",
    "response",
    "first_layer",
    "active",
    "profile_flow",
    "count",
    "support_bce",
    "support_rank",
    "share_flow",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def verify(
    root: Path,
    expected_files: int,
    expected_bytes: int,
    expected_checkpoint_sha256: str,
    expected_overlay_suffix: str,
    expected_staged_count: int,
) -> dict[str, Any]:
    files = sorted(path for path in root.rglob("*") if path.is_file())
    assert len(files) == expected_files, len(files)
    total_bytes = sum(path.stat().st_size for path in files)
    assert total_bytes == expected_bytes, total_bytes
    assert not (root / "vertex_failure.json").exists()
    hashes = {
        path.relative_to(root).as_posix(): _sha256(path) for path in files
    }
    assert set(hashes) == {
        "environment.json",
        "runtime_config.yaml",
        "staged_input_manifest.json",
        "reports/calibration_resources.json",
        "reports/loss_weight_calibration.json",
        "vertex_calibration_result.json",
    }

    runtime = yaml.safe_load(
        (root / "runtime_config.yaml").read_text(encoding="utf-8")
    )
    assert runtime["training"]["stage"] == "joint"
    assert runtime["training"]["device"] == "cuda"
    assert runtime["training"]["amp"] is False
    assert int(runtime["training"]["seed"]) == 20260723
    assert runtime["training"]["initialize_from"] is None
    assert runtime["training"]["initialize_from_relative"].endswith(
        "checkpoints/share_best.pt"
    )

    staged = _json(root / "staged_input_manifest.json")
    assert len(staged) == expected_staged_count
    relative_paths = [str(item["relative_path"]) for item in staged]
    assert len(relative_paths) == len(set(relative_paths))
    assert not any("legacy" in path.lower() for path in relative_paths)
    assert not any(
        part.lower() == "test"
        for path in relative_paths
        for part in Path(path).parts
    )
    assert sum(
        item["source_prefix"].endswith("prep-20260724-r5") for item in staged
    ) == 205
    assert sum(
        item["source_prefix"].endswith(expected_overlay_suffix) for item in staged
    ) == expected_staged_count - 205

    report = _json(root / "reports/loss_weight_calibration.json")
    assert report["pass"] is True
    assert report["method"] == "fixed_gradient_norm_calibration"
    assert report["scientific_status"] == (
        "train-only proposal; not validation selection"
    )
    assert report["split"] == "train"
    assert int(report["test_events_used"]) == 0
    assert int(report["max_batches"]) == 64
    assert int(report["batches_consumed"]) == 64
    assert [float(value) for value in report["clip"]] == [0.25, 4.0]
    assert set(report["measured_components"]) == COMPONENTS
    assert report["memory_bounded_loss_groups"] == [
        "response",
        "profile",
        "count",
        "support",
        "share",
    ]
    assert report["gradient_norm_observations"] == {
        name: 64 for name in COMPONENTS
    }
    medians = {
        name: float(value)
        for name, value in report["gradient_norm_median"].items()
    }
    weights = {name: float(value) for name, value in report["weights"].items()}
    assert set(medians) == COMPONENTS
    assert set(weights) == COMPONENTS
    assert all(math.isfinite(value) and value > 0 for value in medians.values())
    assert all(math.isfinite(value) and value > 0 for value in weights.values())

    geometric = math.exp(
        sum(math.log(value) for value in medians.values()) / len(medians)
    )
    raw = {
        name: max(0.25, min(4.0, geometric / value))
        for name, value in medians.items()
    }
    scale = len(raw) / sum(raw.values())
    recomputed = {name: value * scale for name, value in raw.items()}
    for name in COMPONENTS:
        assert math.isclose(
            weights[name], recomputed[name], rel_tol=0, abs_tol=1e-12
        ), name
    assert math.isclose(
        sum(weights.values()) / len(weights), 1.0, rel_tol=0, abs_tol=1e-12
    )

    checkpoint = report["checkpoint"]
    assert checkpoint["sha256"] == expected_checkpoint_sha256
    assert checkpoint["stage"] == "joint"
    assert int(checkpoint["epoch"]) == 2
    assert math.isfinite(float(checkpoint["best_metric"]))
    preflight = report["preflight"]
    expected_provenance = {
        "geometry_sha256": preflight["hashes"]["geometry_npz_sha256"],
        "manifest_sha256": preflight["hashes"]["dataset_manifest_sha256"],
        "splits_sha256": preflight["hashes"]["split_manifest_sha256"],
        "seed": 20260723,
    }
    assert checkpoint["provenance"] == expected_provenance

    assert preflight["pass"] is True
    assert preflight["synthetic"] is False
    assert int(preflight["verified_shards"]) == 187
    assert preflight["selection_counts"] == {
        "train": 26624,
        "validation": 4096,
        "test": 0,
    }

    resources = _json(root / "reports/calibration_resources.json")
    assert resources == report["resources"]
    assert resources["pass"] is True
    assert resources["device"] == "cuda"
    assert resources["device_name"] == "Tesla T4"
    assert float(resources["headroom_fraction"]) >= 0.15
    assert int(resources["peak_memory_bytes"]) <= int(
        resources["total_memory_bytes"]
    )
    assert math.isfinite(float(report["elapsed_seconds"]))
    assert float(report["elapsed_seconds"]) > 0

    result = _json(root / "vertex_calibration_result.json")
    assert result["pass"] is True
    assert result["calibration"] == report
    assert result["runtime_config_sha256"] == hashes["runtime_config.yaml"]

    return {
        "pass": True,
        "files": len(files),
        "bytes": total_bytes,
        "sha256": hashes,
        "checkpoint": checkpoint,
        "gradient_norm_median": medians,
        "proposed_weights": weights,
        "resources": resources,
        "preflight": preflight,
        "staged_count": len(staged),
        "scientific_status": (
            "train-only gradient-scale proposal; validation selection and "
            "physics fidelity not established"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--expected-files", type=int, required=True)
    parser.add_argument("--expected-bytes", type=int, required=True)
    parser.add_argument("--expected-checkpoint-sha256", required=True)
    parser.add_argument("--expected-overlay-suffix", required=True)
    parser.add_argument("--expected-staged-count", type=int, default=209)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = verify(
        args.root,
        args.expected_files,
        args.expected_bytes,
        args.expected_checkpoint_sha256,
        args.expected_overlay_suffix,
        args.expected_staged_count,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(args.output)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
