from __future__ import annotations

import json
from pathlib import Path

import yaml

from scripts.build_viability_matrix import COMPONENTS, generate_matrix


def _calibration(path: Path) -> None:
    report = {
        "pass": True,
        "scientific_status": "train-only proposal; not validation selection",
        "split": "train",
        "test_events_used": 0,
        "max_batches": 64,
        "batches_consumed": 64,
        "memory_bounded_loss_groups": [
            "response",
            "profile",
            "count",
            "support",
            "share",
        ],
        "measured_components": sorted(COMPONENTS),
        "gradient_norm_observations": {
            name: 64 for name in COMPONENTS
        },
        "weights": {name: 1.0 for name in COMPONENTS},
    }
    path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def test_viability_wave_is_complete_and_checkpoint_bound(tmp_path: Path):
    calibration = tmp_path / "calibration.json"
    _calibration(calibration)
    source = Path("configs/templates/pilot_stage_joint_fp32.yaml")
    output = tmp_path / "matrix"
    checkpoint = "a" * 64
    manifest = generate_matrix(source, calibration, checkpoint, output)
    assert manifest["variant_count"] == 5
    assert manifest["parallel_wave_limit"] == 5
    assert manifest["estimated_epoch_poll_seconds"] == 4200
    assert manifest["test_events_used"] == 0
    assert len(list(output.glob("*.yaml"))) == 5
    variants = {item["name"]: item for item in manifest["variants"]}
    assert set(variants) == {
        "default_control",
        "calibrated_lr3e5",
        "calibrated_lr1e4",
        "calibrated_lr3e4",
        "calibrated_lr1e4_halfbatch",
    }
    assert variants["default_control"]["weights"] == "default"
    assert variants["calibrated_lr1e4_halfbatch"]["effective_batch"] == 12
    for item in manifest["variants"]:
        template = yaml.safe_load((output / item["template"]).read_text())
        assert template["training"]["epochs"] == 1
        assert template["training"]["amp"] is False
        assert template["training"]["checkpoint_interval_updates"] == 50
        assert template["training"]["initialize_from_relative"] == (
            "checkpoints/joint_best.pt"
        )
        assert template["training"]["initialize_from_sha256"] == checkpoint
        assert template["evaluation"]["visualization"]["sample_count"] == 50
        assert template["evaluation"]["visualization"]["draws_per_condition"] == 5
        assert template["viability"]["test_events_used"] == 0


def test_viability_wave_rejects_test_contaminated_calibration(tmp_path: Path):
    calibration = tmp_path / "calibration.json"
    _calibration(calibration)
    report = json.loads(calibration.read_text(encoding="utf-8"))
    report["test_events_used"] = 1
    calibration.write_text(json.dumps(report), encoding="utf-8")
    try:
        generate_matrix(
            Path("configs/templates/pilot_stage_joint_fp32.yaml"),
            calibration,
            "a" * 64,
            tmp_path / "matrix",
        )
    except ValueError as exc:
        assert "train-only" in str(exc)
    else:
        raise AssertionError("test-contaminated calibration was accepted")
