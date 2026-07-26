from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import torch
import yaml

from cbsc_zdc.training.trainer import (
    _legacy_mid_epoch_contract_sha256,
    _mid_epoch_contract_sha256,
)


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
INVARIANT_ZERO_FIELDS = {
    "nonfinite",
    "negative",
    "outside_valid_support",
    "support_mask_mismatch",
    "count_mismatch_max",
    "requested_realized_mismatch_max",
    "dust_cells",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _optimizer_steps(payload: dict[str, Any]) -> set[int]:
    steps: set[int] = set()
    for state in payload["optimizer_state"]["state"].values():
        if "step" not in state:
            continue
        value = state["step"]
        steps.add(int(value.item() if torch.is_tensor(value) else value))
    return steps


def _same_model_state(first: dict[str, Any], second: dict[str, Any]) -> bool:
    left = first["model_state"]
    right = second["model_state"]
    return left.keys() == right.keys() and all(
        torch.equal(left[name].cpu(), right[name].cpu()) for name in left
    )


def _assert_invariants(report: dict[str, Any], tolerance: float) -> None:
    assert report["pass"] is True
    for field in INVARIANT_ZERO_FIELDS:
        assert int(report[field]) == 0, (field, report[field])
    assert float(report["layer_closure_max_gev"]) <= tolerance
    assert float(report["event_closure_max_gev"]) <= tolerance


def _assert_visualization(
    root: Path,
    checkpoint_sha256: str,
    tolerance: float,
    comparison_path: Path,
) -> dict[str, Any]:
    path = root / "reports/visualization/epoch_0000.json"
    candidate = _json(path)
    comparison = _json(comparison_path)
    assert candidate["schema_version"] == 1
    assert candidate["split"] == "validation"
    assert candidate["synthetic_source"] is False
    assert candidate["stage"] == "joint"
    assert int(candidate["epoch"]) == 0
    assert int(candidate["sample_count"]) == 50
    assert int(candidate["draws_per_condition"]) == 5
    assert int(candidate["profile_steps"]) == 8
    assert int(candidate["share_steps"]) == 8
    assert candidate["checkpoint_sha256"] == checkpoint_sha256
    assert len(candidate["groups"]) == 50
    assert len(candidate["generation_seeds"]) == 50
    assert len(set(candidate["generation_seeds"])) == 50
    assert len(set(candidate["selection"]["dataset_indices"])) == 50
    assert len(set(candidate["selection"]["global_indices"])) == 50
    assert len(set(candidate["selection"]["event_ids"])) == 50
    assert all(len(group["p4_total_gev"]) == 4 for group in candidate["groups"])
    assert all(len(group["fast_mc"]) == 5 for group in candidate["groups"])
    assert all(
        all(
            int(draw["seed_group"])
            == int(candidate["generation_seeds"][position])
            for draw in group["fast_mc"]
        )
        for position, group in enumerate(candidate["groups"])
    )
    qa = candidate["qa"]
    assert qa["pass"] is True
    assert int(qa["test_events_used"]) == 0
    assert qa["selection_unique"] is True
    assert int(qa["groups_with_exact_draw_count"]) == 50
    assert int(qa["truth_nonfinite"]) == 0
    assert int(qa["generated_nonfinite"]) == 0
    assert int(qa["truth_negative"]) == 0
    assert int(qa["generated_negative"]) == 0
    _assert_invariants(qa["invariants"], tolerance)
    assert all(
        math.isfinite(float(value))
        for value in candidate["aggregate"]["trend"].values()
    )

    assert candidate["selection_sha256"] == comparison["selection_sha256"]
    assert candidate["geometry_sha256"] == comparison["geometry_sha256"]
    assert candidate["selection"] == comparison["selection"]
    assert candidate["generation_seeds"] == comparison["generation_seeds"]
    for expected, actual in zip(
        comparison["groups"], candidate["groups"], strict=True
    ):
        for field in (
            "selection_position",
            "dataset_index",
            "global_index",
            "event_id",
            "source_group",
            "kinetic_energy_gev",
            "p4_total_gev",
            "geant4",
        ):
            assert actual[field] == expected[field], field

    manifest = _json(root / "reports/visualization/manifest.json")
    assert int(manifest["latest_epoch"]) == 0
    assert len(manifest["epochs"]) == 1
    assert manifest["epochs"][0]["sha256"] == _sha256(path)
    assert manifest["selection_sha256"] == candidate["selection_sha256"]
    assert manifest["geometry_sha256"] == candidate["geometry_sha256"]
    return candidate


def verify(
    root: Path,
    source_progress_path: Path,
    comparison_visualization: Path,
    expected_files: int,
    expected_bytes: int,
    expected_source_sha256: str,
    expected_staged_count: int,
    expected_overlay_suffix: str,
) -> dict[str, Any]:
    files = sorted(path for path in root.rglob("*") if path.is_file())
    assert len(files) == expected_files, len(files)
    total_bytes = sum(path.stat().st_size for path in files)
    assert total_bytes == expected_bytes, total_bytes
    assert not (root / "vertex_failure.json").exists()
    assert not (root / "checkpoints/progress.pt").exists()
    hashes = {
        path.relative_to(root).as_posix(): _sha256(path) for path in files
    }

    duplicate_pairs = [
        ("checkpoints/best.pt", "progress/epoch_0000/checkpoints/best.pt"),
        ("checkpoints/last.pt", "progress/epoch_0000/checkpoints/last.pt"),
        ("environment.json", "progress/epoch_0000/environment.json"),
        ("logs/history.csv", "progress/epoch_0000/logs/history.csv"),
        (
            "reports/invariant_epoch_0000.json",
            "progress/epoch_0000/reports/invariant_epoch_0000.json",
        ),
        ("reports/preflight.json", "progress/epoch_0000/reports/preflight.json"),
        (
            "reports/progress_epoch_0000.json",
            "progress/epoch_0000/reports/progress_epoch_0000.json",
        ),
        (
            "reports/visualization/epoch_0000.json",
            "progress/epoch_0000/reports/visualization/epoch_0000.json",
        ),
        (
            "reports/visualization/geometry.json",
            "progress/epoch_0000/reports/visualization/geometry.json",
        ),
        (
            "reports/visualization/manifest.json",
            "progress/epoch_0000/reports/visualization/manifest.json",
        ),
        ("resolved_config.json", "progress/epoch_0000/resolved_config.json"),
        ("runtime_config.yaml", "progress/epoch_0000/runtime_config.yaml"),
        (
            "staged_input_manifest.json",
            "progress/epoch_0000/staged_input_manifest.json",
        ),
    ]
    for terminal, progress in duplicate_pairs:
        assert hashes[terminal] == hashes[progress], (terminal, progress)

    source_hash = _sha256(source_progress_path)
    assert source_hash == expected_source_sha256
    source = torch.load(
        source_progress_path, map_location="cpu", weights_only=False
    )
    source_state = source["progress"]
    assert source["stage"] == "joint"
    assert int(source["epoch"]) == 0
    assert math.isinf(float(source["best_metric"]))
    assert float(source["best_metric"]) > 0
    assert int(source_state["epoch"]) == 0
    assert int(source_state["next_step"]) == 1000
    assert int(source_state["train_count"]) == 1000
    assert int(source_state["loader_batches"]) == 4437
    assert int(source_state["gradient_accumulation"]) == 4
    assert int(source_state["batch_size"]) == 6
    assert int(source_state["epoch_seed"]) == 20260723
    assert source_state["optimizer_boundary"] is True
    assert int(source_state["updates"]) == 250
    assert _optimizer_steps(source) == {250}
    assert int(source["scheduler_state"]["last_epoch"]) == 250
    assert source.get("rng_state", {}).get("torch") is not None
    assert source.get("rng_state", {}).get("cuda") is not None
    assert set(source_state["component_sum"]) == COMPONENTS
    assert all(
        math.isfinite(float(value))
        for value in [
            source_state["train_sum"],
            source_state["elapsed_seconds"],
            *source_state["component_sum"].values(),
        ]
    )
    assert (
        _legacy_mid_epoch_contract_sha256(source["config"])
        == source_state["contract_sha256"]
    )

    with (root / "logs/history.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        history = list(csv.DictReader(handle))
    assert len(history) == 1
    row = history[0]
    assert int(row["epoch"]) == 0
    assert row["stage"] == "joint"
    numeric_history = {
        key: float(value)
        for key, value in row.items()
        if key not in {"epoch", "stage"} and value not in {"", None}
    }
    assert all(math.isfinite(value) for value in numeric_history.values())
    assert {key.removeprefix("train_") for key in row if key.startswith("train_")} == (
        COMPONENTS | {"loss"}
    )

    runtime = yaml.safe_load(
        (root / "runtime_config.yaml").read_text(encoding="utf-8")
    )
    training = runtime["training"]
    assert training["stage"] == "joint"
    assert training["amp"] is False
    assert training["train_condition_encoder"] is True
    assert int(training["epochs"]) == 1
    assert int(training["batch_size"]) == 6
    assert int(training["gradient_accumulation"]) == 4
    assert int(training["checkpoint_interval_updates"]) == 50
    assert training["resume_progress_from_sha256"] == source_hash
    assert str(training["resume_progress_from"]).endswith("checkpoints/progress.pt")
    assert training.get("resume_from") is None
    assert training.get("resume_best_from") is None
    assert _mid_epoch_contract_sha256(runtime) == _mid_epoch_contract_sha256(
        source["config"]
    )

    weighted = sum(
        float(runtime["loss_weights"][name]) * float(row[f"train_{name}"])
        for name in COMPONENTS
    )
    assert math.isclose(
        weighted, float(row["train_loss"]), rel_tol=1e-8, abs_tol=1e-8
    )
    assert float(row["seconds"]) > float(source_state["elapsed_seconds"])
    assert math.isclose(
        float(row["examples_per_second"]),
        26624 / float(row["seconds"]),
        rel_tol=1e-12,
        abs_tol=1e-12,
    )

    best_path = root / "checkpoints/best.pt"
    last_path = root / "checkpoints/last.pt"
    best = torch.load(best_path, map_location="cpu", weights_only=False)
    last = torch.load(last_path, map_location="cpu", weights_only=False)
    assert best["stage"] == last["stage"] == "joint"
    assert int(best["epoch"]) == int(last["epoch"]) == 0
    assert math.isfinite(float(best["best_metric"]))
    assert math.isclose(
        float(best["best_metric"]),
        float(row["validation_loss"]),
        rel_tol=0,
        abs_tol=1e-12,
    )
    assert math.isclose(
        float(last["best_metric"]),
        float(row["validation_loss"]),
        rel_tol=0,
        abs_tol=1e-12,
    )
    assert best["provenance"] == last["provenance"] == source["provenance"]
    assert _same_model_state(best, last)
    assert best.get("progress") is None
    assert last.get("progress") is None
    assert _optimizer_steps(best) == _optimizer_steps(last) == {1110}
    assert int(best["scheduler_state"]["last_epoch"]) == 1110
    assert int(last["scheduler_state"]["last_epoch"]) == 1110
    assert 1110 - int(source_state["updates"]) == 860
    assert best.get("rng_state", {}).get("torch") is not None
    assert best.get("rng_state", {}).get("cuda") is not None

    summary = _json(root / "reports/training_summary.json")
    assert summary["stage"] == "joint"
    assert int(summary["updates"]) == 1110
    assert math.isclose(
        float(summary["best_validation_loss"]),
        float(row["validation_loss"]),
        rel_tol=0,
        abs_tol=1e-12,
    )
    progress_report = _json(root / "reports/progress_epoch_0000.json")
    assert int(progress_report["epoch"]) == 0
    assert progress_report["row"]["stage"] == "joint"
    assert progress_report["best_checkpoint_sha256"] == hashes[
        "checkpoints/best.pt"
    ]
    assert progress_report["last_checkpoint_sha256"] == hashes[
        "checkpoints/last.pt"
    ]

    preflight = _json(root / "reports/preflight.json")
    assert preflight["pass"] is True
    assert preflight["synthetic"] is False
    assert int(preflight["verified_shards"]) == 187
    assert preflight["selection_counts"] == {
        "train": 26624,
        "validation": 4096,
        "test": 0,
    }
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

    tolerance = float(runtime["evaluation"]["closure_tolerance_gev"])
    epoch_invariants = _json(root / "reports/invariant_epoch_0000.json")
    reload_invariants = _json(
        root / "reports/training_postflight_invariants.json"
    )
    _assert_invariants(epoch_invariants, tolerance)
    _assert_invariants(reload_invariants, tolerance)
    postflight = _json(root / "reports/training_postflight.json")
    assert postflight["pass"] is True
    resources = postflight["resources"]
    assert resources["pass"] is True
    assert resources["device"] == "cuda"
    assert resources["device_name"] == "Tesla T4"
    assert float(resources["headroom_fraction"]) >= 0.15
    timing = postflight["timing"]
    assert timing["device"] == "cuda:0"
    assert int(timing["profile_steps"]) == 8
    assert int(timing["share_steps"]) == 8
    assert int(timing["iterations"]) == 2
    assert int(timing["batch_size"]) == 2

    visualization = _assert_visualization(
        root,
        hashes["checkpoints/last.pt"],
        tolerance,
        comparison_visualization,
    )
    vertex_result = _json(root / "vertex_result.json")
    assert vertex_result["training"]["stage"] == "joint"
    assert int(vertex_result["training"]["updates"]) == 1110
    assert vertex_result["training_postflight"]["pass"] is True

    return {
        "pass": True,
        "files": len(files),
        "bytes": total_bytes,
        "sha256": hashes,
        "source_progress": {
            "sha256": source_hash,
            "legacy_contract_sha256": source_state["contract_sha256"],
            "normalized_contract_sha256": _mid_epoch_contract_sha256(
                source["config"]
            ),
            "next_step": int(source_state["next_step"]),
            "updates": int(source_state["updates"]),
            "optimizer_steps": sorted(_optimizer_steps(source)),
            "scheduler_step": int(source["scheduler_state"]["last_epoch"]),
        },
        "recovered": {
            "best_sha256": hashes["checkpoints/best.pt"],
            "last_sha256": hashes["checkpoints/last.pt"],
            "optimizer_steps": sorted(_optimizer_steps(last)),
            "scheduler_step": int(last["scheduler_state"]["last_epoch"]),
            "new_updates": 860,
            "history": {
                key: (
                    value
                    if key in {"epoch", "stage"}
                    else float(value)
                    if value not in {"", None}
                    else None
                )
                for key, value in row.items()
            },
        },
        "invariants": {
            "epoch": epoch_invariants,
            "fresh_reload": reload_invariants,
        },
        "postflight": postflight,
        "visualization": {
            "sha256": hashes["reports/visualization/epoch_0000.json"],
            "selection_sha256": visualization["selection_sha256"],
            "sample_count": visualization["sample_count"],
            "draws_per_condition": visualization["draws_per_condition"],
            "trend": visualization["aggregate"]["trend"],
            "qa": visualization["qa"],
        },
        "scientific_status": (
            "mid-epoch structural/recovery proof only; physics validation "
            "not established"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--source-progress", type=Path, required=True)
    parser.add_argument("--comparison-visualization", type=Path, required=True)
    parser.add_argument("--expected-files", type=int, required=True)
    parser.add_argument("--expected-bytes", type=int, required=True)
    parser.add_argument("--expected-source-sha256", required=True)
    parser.add_argument("--expected-staged-count", type=int, default=209)
    parser.add_argument("--expected-overlay-suffix", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = verify(
        args.root,
        args.source_progress,
        args.comparison_visualization,
        args.expected_files,
        args.expected_bytes,
        args.expected_source_sha256,
        args.expected_staged_count,
        args.expected_overlay_suffix,
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
