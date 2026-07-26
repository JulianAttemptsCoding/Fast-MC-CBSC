from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


EXPECTED_VARIANTS = {
    "default_control",
    "calibrated_lr3e5",
    "calibrated_lr1e4",
    "calibrated_lr3e4",
    "calibrated_lr1e4_halfbatch",
}
LOWER_TOLERANCES = {
    "response_bias_abs": 0.01,
    "hit_count_bias_abs": 0.01,
    "profile_relative_l1": 0.01,
}
HIGHER_TOLERANCES = {
    "examples_per_second": ("relative", 0.05),
    "headroom_fraction": ("absolute", 0.05),
}


def _parse_result(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise ValueError("--result must be NAME=PATH")
    name, path = value.split("=", 1)
    if not name or not path:
        raise ValueError("--result must be NAME=PATH")
    return name, Path(path)


def _row(name: str, report: dict[str, Any]) -> dict[str, Any]:
    assert report["pass"] is True
    assert report["terminal"] is True
    assert report["stage"] == "joint"
    assert int(report["epoch"]) == 0
    history = report["history"]
    assert len(history) == 1
    trend = report["visualization"]["trend"]
    population = report["visualization"]["population"]
    postflight = report["postflight"]
    assert postflight["pass"] is True
    values = {
        "validation_loss": float(history[0]["validation_loss"]),
        "response_bias_abs": abs(float(trend["response_bias_fraction"])),
        "hit_count_bias_abs": abs(float(trend["hit_count_bias_fraction"])),
        "profile_relative_l1": float(
            trend["mean_longitudinal_profile_relative_l1"]
        ),
        "examples_per_second": float(history[0]["examples_per_second"]),
        "headroom_fraction": float(postflight["resources"]["headroom_fraction"]),
        "milliseconds_per_event_8x8": float(
            postflight["timing"]["milliseconds_per_event"]
        ),
        "truth_zero_response_fraction": float(
            population["truth_zero_response_fraction"]
        ),
        "generated_zero_response_fraction": float(
            population["generated_zero_response_fraction"]
        ),
        "groups_with_multiple_unique_deposits": int(
            population["groups_with_multiple_unique_deposits"]
        ),
        "mean_within_condition_response_std_gev": float(
            population["mean_within_condition_response_std_gev"]
        ),
    }
    assert all(
        math.isfinite(value)
        for value in values.values()
        if isinstance(value, float)
    )
    assert values["groups_with_multiple_unique_deposits"] > 0
    return {
        "name": name,
        "weight_family": (
            "default" if name == "default_control" else "calibrated"
        ),
        "source_checkpoint_sha256": report["checkpoint"]["source_sha256"],
        "selection_sha256": report["visualization"]["selection_sha256"],
        "values": values,
    }


def _no_worse_lower(a: float, b: float, tolerance: float) -> bool:
    return a <= b + tolerance


def _better_lower(a: float, b: float, tolerance: float) -> bool:
    return a < b - tolerance


def _no_worse_higher(
    a: float,
    b: float,
    kind: str,
    tolerance: float,
) -> bool:
    return a >= (b * (1.0 - tolerance) if kind == "relative" else b - tolerance)


def _better_higher(
    a: float,
    b: float,
    kind: str,
    tolerance: float,
) -> bool:
    return a > (b * (1.0 + tolerance) if kind == "relative" else b + tolerance)


def dominates(a: dict[str, Any], b: dict[str, Any]) -> bool:
    a_values = a["values"]
    b_values = b["values"]
    no_worse = []
    better = []
    if a["weight_family"] == b["weight_family"]:
        tolerance = 0.01 * abs(b_values["validation_loss"])
        no_worse.append(
            _no_worse_lower(
                a_values["validation_loss"],
                b_values["validation_loss"],
                tolerance,
            )
        )
        better.append(
            _better_lower(
                a_values["validation_loss"],
                b_values["validation_loss"],
                tolerance,
            )
        )
    for metric, tolerance in LOWER_TOLERANCES.items():
        no_worse.append(
            _no_worse_lower(a_values[metric], b_values[metric], tolerance)
        )
        better.append(
            _better_lower(a_values[metric], b_values[metric], tolerance)
        )
    for metric, (kind, tolerance) in HIGHER_TOLERANCES.items():
        no_worse.append(
            _no_worse_higher(
                a_values[metric], b_values[metric], kind, tolerance
            )
        )
        better.append(
            _better_higher(a_values[metric], b_values[metric], kind, tolerance)
        )
    return all(no_worse) and any(better)


def _rank_score(row: dict[str, Any], rows: list[dict[str, Any]]) -> float:
    metrics = [
        ("response_bias_abs", False),
        ("hit_count_bias_abs", False),
        ("profile_relative_l1", False),
        ("examples_per_second", True),
        ("headroom_fraction", True),
    ]
    if row["weight_family"] == "calibrated":
        metrics.append(("validation_loss", False))
    percentiles = []
    for metric, higher_is_better in metrics:
        peers = (
            [item for item in rows if item["weight_family"] == "calibrated"]
            if metric == "validation_loss"
            else rows
        )
        ordered = sorted(
            peers,
            key=lambda item: item["values"][metric],
            reverse=higher_is_better,
        )
        rank = next(
            index for index, item in enumerate(ordered) if item["name"] == row["name"]
        )
        percentiles.append(rank / max(1, len(ordered) - 1))
    return max(percentiles)


def analyze(result_specs: list[tuple[str, Path]]) -> dict[str, Any]:
    assert len(result_specs) == 5
    assert {name for name, _ in result_specs} == EXPECTED_VARIANTS
    rows = [
        _row(name, json.loads(path.read_text(encoding="utf-8")))
        for name, path in result_specs
    ]
    assert len({row["source_checkpoint_sha256"] for row in rows}) == 1
    assert len({row["selection_sha256"] for row in rows}) == 1
    dominated_by = {
        row["name"]: sorted(
            other["name"]
            for other in rows
            if other["name"] != row["name"] and dominates(other, row)
        )
        for row in rows
    }
    nondominated = [row for row in rows if not dominated_by[row["name"]]]
    scores = {row["name"]: _rank_score(row, rows) for row in nondominated}
    selected = sorted(
        nondominated,
        key=lambda row: (scores[row["name"]], row["name"]),
    )[:2]
    return {
        "pass": True,
        "scientific_status": (
            "validation-only wave-1 selection; physics fidelity not established"
        ),
        "source_checkpoint_sha256": rows[0]["source_checkpoint_sha256"],
        "selection_sha256": rows[0]["selection_sha256"],
        "rows": rows,
        "dominated_by": dominated_by,
        "nondominated": sorted(row["name"] for row in nondominated),
        "worst_normalized_rank": scores,
        "selected_for_two_epoch_continuation": [
            row["name"] for row in selected
        ],
        "test_events_used": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", action="append", default=[], required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = analyze([_parse_result(value) for value in args.result])
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
