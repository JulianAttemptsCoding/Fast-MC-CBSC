from __future__ import annotations

import json
from pathlib import Path

from scripts.analyze_viability_wave import analyze, dominates


def _row(name: str, loss: float, response: float, throughput: float) -> dict:
    return {
        "name": name,
        "weight_family": "default" if name == "default_control" else "calibrated",
        "values": {
            "validation_loss": loss,
            "response_bias_abs": response,
            "hit_count_bias_abs": 0.1,
            "profile_relative_l1": 0.25,
            "examples_per_second": throughput,
            "headroom_fraction": 0.3,
        },
    }


def _report(loss: float, response: float, throughput: float) -> dict:
    return {
        "pass": True,
        "terminal": True,
        "stage": "joint",
        "epoch": 0,
        "history": [
            {
                "validation_loss": loss,
                "examples_per_second": throughput,
            }
        ],
        "checkpoint": {"source_sha256": "a" * 64},
        "visualization": {
            "selection_sha256": "b" * 64,
            "trend": {
                "response_bias_fraction": response,
                "hit_count_bias_fraction": -0.1,
                "mean_longitudinal_profile_relative_l1": 0.25,
            },
            "population": {
                "truth_zero_response_fraction": 0.02,
                "generated_zero_response_fraction": 0.1,
                "groups_with_multiple_unique_deposits": 50,
                "mean_within_condition_response_std_gev": 2.0,
            },
        },
        "postflight": {
            "pass": True,
            "resources": {"headroom_fraction": 0.3},
            "timing": {"milliseconds_per_event": 250.0},
        },
    }


def test_cross_weight_aggregate_is_not_used_for_dominance():
    default = _row("default_control", loss=1.0, response=0.1, throughput=6.0)
    calibrated = _row("calibrated_lr1e4", loss=100.0, response=0.1, throughput=6.0)
    assert not dominates(default, calibrated)


def test_same_weight_candidate_can_dominate():
    better = _row("calibrated_lr1e4", loss=9.0, response=0.1, throughput=6.5)
    worse = _row("calibrated_lr3e5", loss=10.0, response=0.2, throughput=6.0)
    assert dominates(better, worse)


def test_analysis_selects_at_most_two(tmp_path: Path):
    names = [
        "default_control",
        "calibrated_lr3e5",
        "calibrated_lr1e4",
        "calibrated_lr3e4",
        "calibrated_lr1e4_halfbatch",
    ]
    specs = []
    for index, name in enumerate(names):
        path = tmp_path / f"{name}.json"
        path.write_text(
            json.dumps(
                _report(
                    loss=10.0 + index,
                    response=0.1 + index * 0.03,
                    throughput=6.5 - index * 0.1,
                )
            ),
            encoding="utf-8",
        )
        specs.append((name, path))
    report = analyze(specs)
    assert report["pass"] is True
    assert len(report["selected_for_two_epoch_continuation"]) <= 2
    assert report["test_events_used"] == 0
