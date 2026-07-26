from __future__ import annotations

import json
from pathlib import Path

import yaml

from scripts.verify_loss_calibration_output import COMPONENTS, _sha256, verify


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def test_loss_calibration_terminal_verifier_recomputes_contract(tmp_path: Path):
    root = tmp_path / "terminal"
    runtime = {
        "training": {
            "stage": "joint",
            "device": "cuda",
            "amp": False,
            "seed": 20260723,
            "initialize_from": None,
            "initialize_from_relative": "checkpoints/share_best.pt",
        }
    }
    (root / "runtime_config.yaml").parent.mkdir(parents=True)
    (root / "runtime_config.yaml").write_text(
        yaml.safe_dump(runtime, sort_keys=False),
        encoding="utf-8",
    )
    _write_json(root / "environment.json", {"python": "test"})
    staged = [
        {
            "source_prefix": (
                "gs://bucket/cbsc-v2-2/prep-20260724-r5"
                if index < 205
                else "gs://bucket/cbsc-v2-2/calibration-r1"
            ),
            "relative_path": f"artifact_{index:03d}",
        }
        for index in range(209)
    ]
    _write_json(root / "staged_input_manifest.json", staged)

    medians = {name: 1.0 for name in COMPONENTS}
    weights = {name: 1.0 for name in COMPONENTS}
    preflight = {
        "pass": True,
        "synthetic": False,
        "verified_shards": 187,
        "selection_counts": {"train": 26624, "validation": 4096, "test": 0},
        "hashes": {
            "geometry_npz_sha256": "1" * 64,
            "dataset_manifest_sha256": "2" * 64,
            "split_manifest_sha256": "3" * 64,
        },
    }
    resources = {
        "pass": True,
        "device": "cuda",
        "device_name": "Tesla T4",
        "headroom_fraction": 0.2,
        "peak_memory_bytes": 80,
        "total_memory_bytes": 100,
    }
    checkpoint = {
        "sha256": "4" * 64,
        "stage": "joint",
        "epoch": 2,
        "best_metric": 9.0,
        "provenance": {
            "geometry_sha256": "1" * 64,
            "manifest_sha256": "2" * 64,
            "splits_sha256": "3" * 64,
            "seed": 20260723,
        },
    }
    report = {
        "pass": True,
        "method": "fixed_gradient_norm_calibration",
        "scientific_status": "train-only proposal; not validation selection",
        "split": "train",
        "test_events_used": 0,
        "max_batches": 64,
        "batches_consumed": 64,
        "clip": [0.25, 4.0],
        "measured_components": sorted(COMPONENTS),
        "memory_bounded_loss_groups": [
            "response",
            "profile",
            "count",
            "support",
            "share",
        ],
        "gradient_norm_observations": {
            name: 64 for name in COMPONENTS
        },
        "gradient_norm_median": medians,
        "weights": weights,
        "checkpoint": checkpoint,
        "preflight": preflight,
        "resources": resources,
        "elapsed_seconds": 1.0,
    }
    _write_json(root / "reports/loss_weight_calibration.json", report)
    _write_json(root / "reports/calibration_resources.json", resources)
    _write_json(
        root / "vertex_calibration_result.json",
        {
            "pass": True,
            "calibration": report,
            "runtime_config_sha256": _sha256(root / "runtime_config.yaml"),
        },
    )
    files = [path for path in root.rglob("*") if path.is_file()]
    result = verify(
        root,
        expected_files=6,
        expected_bytes=sum(path.stat().st_size for path in files),
        expected_checkpoint_sha256="4" * 64,
        expected_overlay_suffix="calibration-r1",
        expected_staged_count=209,
    )
    assert result["pass"] is True
    assert result["proposed_weights"] == weights
