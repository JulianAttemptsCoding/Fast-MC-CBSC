from __future__ import annotations

import json
from pathlib import Path

import yaml

from scripts.build_viability_continuations import build


def test_continuation_builder_preserves_variant_and_restarts_scheduler(
    tmp_path: Path,
):
    name = "calibrated_lr1e4"
    analysis = tmp_path / "analysis.json"
    analysis.write_text(
        json.dumps(
            {
                "pass": True,
                "test_events_used": 0,
                "nondominated": [name],
                "selected_for_two_epoch_continuation": [name],
            }
        ),
        encoding="utf-8",
    )
    result = tmp_path / "result.json"
    result.write_text(
        json.dumps(
            {
                "pass": True,
                "terminal": True,
                "stage": "joint",
                "epoch": 0,
                "checkpoint": {
                    "best_sha256": "a" * 64,
                    "last_sha256": "b" * 64,
                },
            }
        ),
        encoding="utf-8",
    )
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    template = {
        "project": {"name": "candidate", "run_dir": "runs/candidate"},
        "training": {
            "stage": "joint",
            "epochs": 1,
            "amp": False,
            "learning_rate": 1e-4,
            "batch_size": 6,
            "gradient_accumulation": 4,
            "checkpoint_interval_updates": 50,
            "initialize_from": None,
            "initialize_from_relative": "checkpoints/joint_best.pt",
            "initialize_from_sha256": "c" * 64,
            "resume_from": None,
        },
        "viability": {"successive_halving_wave": 1},
    }
    (template_dir / f"{name}.yaml").write_text(
        yaml.safe_dump(template),
        encoding="utf-8",
    )
    output_dir = tmp_path / "output"

    manifest = build(
        analysis,
        [(name, result)],
        template_dir,
        output_dir,
    )

    continuation = yaml.safe_load(
        (output_dir / f"{name}_continuation.yaml").read_text()
    )
    training = continuation["training"]
    assert manifest["variant_count"] == 1
    assert training["epochs"] == 3
    assert training["initialize_from_relative"] is None
    assert training["resume_from_sha256"] == "b" * 64
    assert training["resume_best_from_sha256"] == "a" * 64
    assert training["restart_scheduler_on_resume"] is True
    assert continuation["viability"]["continuation_epochs"] == 2
    assert manifest["test_events_used"] == 0


def test_continuation_builder_refuses_unselected_result(tmp_path: Path):
    analysis = tmp_path / "analysis.json"
    analysis.write_text(
        json.dumps(
            {
                "pass": True,
                "test_events_used": 0,
                "nondominated": ["calibrated_lr1e4"],
                "selected_for_two_epoch_continuation": ["calibrated_lr1e4"],
            }
        ),
        encoding="utf-8",
    )
    result = tmp_path / "result.json"
    result.write_text("{}", encoding="utf-8")
    try:
        build(
            analysis,
            [("default_control", result)],
            tmp_path,
            tmp_path / "output",
        )
    except AssertionError:
        pass
    else:
        raise AssertionError("unselected result was accepted")
