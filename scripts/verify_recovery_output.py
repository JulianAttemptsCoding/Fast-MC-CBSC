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


EXPECTED_INVARIANT_ZERO_FIELDS = {
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


def _assert_invariants(report: dict[str, Any], tolerance: float) -> None:
    assert report["pass"] is True
    for field in EXPECTED_INVARIANT_ZERO_FIELDS:
        assert int(report[field]) == 0, (field, report[field])
    assert float(report["layer_closure_max_gev"]) <= tolerance
    assert float(report["event_closure_max_gev"]) <= tolerance


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


def verify(
    root: Path,
    source_best_path: Path,
    source_last_path: Path,
    expected_files: int,
    expected_bytes: int,
) -> dict[str, Any]:
    files = sorted(path for path in root.rglob("*") if path.is_file())
    assert len(files) == expected_files, len(files)
    total_bytes = sum(path.stat().st_size for path in files)
    assert total_bytes == expected_bytes, total_bytes
    assert not (root / "vertex_failure.json").exists()

    file_hashes = {
        path.relative_to(root).as_posix(): _sha256(path) for path in files
    }
    duplicate_pairs = [
        ("checkpoints/best.pt", "progress/epoch_0003/checkpoints/best.pt"),
        ("checkpoints/last.pt", "progress/epoch_0003/checkpoints/last.pt"),
        ("environment.json", "progress/epoch_0003/environment.json"),
        ("logs/history.csv", "progress/epoch_0003/logs/history.csv"),
        (
            "reports/invariant_epoch_0003.json",
            "progress/epoch_0003/reports/invariant_epoch_0003.json",
        ),
        ("reports/preflight.json", "progress/epoch_0003/reports/preflight.json"),
        (
            "reports/progress_epoch_0003.json",
            "progress/epoch_0003/reports/progress_epoch_0003.json",
        ),
        (
            "reports/visualization/epoch_0003.json",
            "progress/epoch_0003/reports/visualization/epoch_0003.json",
        ),
        (
            "reports/visualization/geometry.json",
            "progress/epoch_0003/reports/visualization/geometry.json",
        ),
        (
            "reports/visualization/manifest.json",
            "progress/epoch_0003/reports/visualization/manifest.json",
        ),
        ("resolved_config.json", "progress/epoch_0003/resolved_config.json"),
        ("runtime_config.yaml", "progress/epoch_0003/runtime_config.yaml"),
        (
            "staged_input_manifest.json",
            "progress/epoch_0003/staged_input_manifest.json",
        ),
    ]
    for terminal, progress in duplicate_pairs:
        assert file_hashes[terminal] == file_hashes[progress], (terminal, progress)

    history_path = root / "logs/history.csv"
    with history_path.open(newline="", encoding="utf-8") as handle:
        history = list(csv.DictReader(handle))
    assert len(history) == 1
    row = history[0]
    assert int(row["epoch"]) == 3
    assert row["stage"] == "response"
    for field in (
        "train_loss",
        "validation_loss",
        "learning_rate",
        "seconds",
        "examples_per_second",
        "train_visible",
        "train_response",
    ):
        assert math.isfinite(float(row[field])), field

    summary = _json(root / "reports/training_summary.json")
    assert summary["stage"] == "response"
    assert int(summary["updates"]) == 1110
    assert math.isclose(
        float(summary["best_validation_loss"]),
        float(row["validation_loss"]),
        rel_tol=0,
        abs_tol=1e-12,
    )

    progress_report = _json(root / "reports/progress_epoch_0003.json")
    assert int(progress_report["epoch"]) == 3
    assert progress_report["row"]["stage"] == "response"
    assert progress_report["best_checkpoint_sha256"] == file_hashes[
        "checkpoints/best.pt"
    ]
    assert progress_report["last_checkpoint_sha256"] == file_hashes[
        "checkpoints/last.pt"
    ]

    source_best_hash = _sha256(source_best_path)
    source_last_hash = _sha256(source_last_path)
    assert source_best_hash == (
        "2ace2bb53db11d1179907f50591e20371142e66baa133f106e16371860012b3e"
    )
    assert source_last_hash == (
        "c03f425e8f684a9ffa58117c6614ea93e3cf91dc8a85b68842c5c66975c170cf"
    )
    source_best = torch.load(source_best_path, map_location="cpu", weights_only=False)
    source_last = torch.load(source_last_path, map_location="cpu", weights_only=False)
    final_best = torch.load(
        root / "checkpoints/best.pt", map_location="cpu", weights_only=False
    )
    final_last = torch.load(
        root / "checkpoints/last.pt", map_location="cpu", weights_only=False
    )
    assert int(source_best["epoch"]) == 1
    assert int(source_last["epoch"]) == 2
    assert int(final_best["epoch"]) == 3
    assert int(final_last["epoch"]) == 3
    assert source_best["stage"] == source_last["stage"] == "response"
    assert final_best["stage"] == final_last["stage"] == "response"
    assert source_best["provenance"] == source_last["provenance"]
    assert final_best["provenance"] == source_last["provenance"]
    assert final_last["provenance"] == source_last["provenance"]
    assert math.isclose(
        float(source_best["best_metric"]),
        float(source_last["best_metric"]),
        rel_tol=0,
        abs_tol=1e-12,
    )
    assert math.isclose(
        float(final_best["best_metric"]),
        float(row["validation_loss"]),
        rel_tol=0,
        abs_tol=1e-12,
    )
    assert math.isclose(
        float(final_last["best_metric"]),
        float(row["validation_loss"]),
        rel_tol=0,
        abs_tol=1e-12,
    )
    assert _same_model_state(final_best, final_last)
    source_steps = _optimizer_steps(source_last)
    final_best_steps = _optimizer_steps(final_best)
    final_last_steps = _optimizer_steps(final_last)
    assert len(source_steps) == len(final_best_steps) == len(final_last_steps) == 1
    assert next(iter(final_best_steps)) - next(iter(source_steps)) == 1110
    assert final_best_steps == final_last_steps
    source_scheduler_step = int(source_last["scheduler_state"]["last_epoch"])
    final_scheduler_step = int(final_last["scheduler_state"]["last_epoch"])
    assert final_scheduler_step - source_scheduler_step == 1110
    for payload in (source_best, source_last, final_best, final_last):
        assert payload.get("rng_state")
        assert payload["rng_state"].get("torch") is not None
        assert payload["rng_state"].get("cuda") is not None

    runtime = yaml.safe_load((root / "runtime_config.yaml").read_text(encoding="utf-8"))
    training = runtime["training"]
    assert training["stage"] == "response"
    assert training["amp"] is False
    assert int(training["epochs"]) == 4
    assert training["resume_from_sha256"] == source_last_hash
    assert training["resume_best_from_sha256"] == source_best_hash
    assert str(training["resume_from"]).endswith("response_last_epoch2.pt")
    assert str(training["resume_best_from"]).endswith("response_best_epoch1.pt")

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
    assert len(staged) == 211
    relative_paths = [str(item["relative_path"]) for item in staged]
    assert len(relative_paths) == len(set(relative_paths))
    assert not any("legacy" in path.lower() for path in relative_paths)
    assert not any("/test" in path.lower() for path in relative_paths)
    assert sum(
        item["source_prefix"].endswith("prep-20260724-r5") for item in staged
    ) == 205
    assert sum(
        item["source_prefix"].endswith("recovery-20260725-r2-response-input")
        for item in staged
    ) == 6

    tolerance = 2e-5
    epoch_invariants = _json(root / "reports/invariant_epoch_0003.json")
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

    visualization_path = root / "reports/visualization/epoch_0003.json"
    visualization = _json(visualization_path)
    assert visualization["schema_version"] == 1
    assert visualization["split"] == "validation"
    assert visualization["synthetic_source"] is False
    assert visualization["stage"] == "response"
    assert int(visualization["epoch"]) == 3
    assert int(visualization["sample_count"]) == 50
    assert int(visualization["draws_per_condition"]) == 5
    assert int(visualization["profile_steps"]) == 8
    assert int(visualization["share_steps"]) == 8
    assert len(visualization["groups"]) == 50
    assert len(set(visualization["selection"]["dataset_indices"])) == 50
    assert len(set(visualization["selection"]["global_indices"])) == 50
    assert len(set(visualization["selection"]["event_ids"])) == 50
    assert len(visualization["generation_seeds"]) == 50
    assert len(set(visualization["generation_seeds"])) == 50
    assert all(len(group["p4_total_gev"]) == 4 for group in visualization["groups"])
    assert all(len(group["fast_mc"]) == 5 for group in visualization["groups"])
    assert all(
        all(
            int(draw["seed_group"]) == int(visualization["generation_seeds"][index])
            for draw in group["fast_mc"]
        )
        for index, group in enumerate(visualization["groups"])
    )
    qa = visualization["qa"]
    assert qa["pass"] is True
    assert int(qa["test_events_used"]) == 0
    assert qa["selection_unique"] is True
    assert int(qa["groups_with_exact_draw_count"]) == 50
    assert int(qa["truth_nonfinite"]) == 0
    assert int(qa["generated_nonfinite"]) == 0
    assert int(qa["truth_negative"]) == 0
    assert int(qa["generated_negative"]) == 0
    _assert_invariants(qa["invariants"], tolerance)
    trend = visualization["aggregate"]["trend"]
    assert all(math.isfinite(float(value)) for value in trend.values())

    visual_manifest = _json(root / "reports/visualization/manifest.json")
    assert int(visual_manifest["latest_epoch"]) == 3
    assert len(visual_manifest["epochs"]) == 1
    assert visual_manifest["epochs"][0]["sha256"] == _sha256(visualization_path)
    assert (
        visual_manifest["selection_sha256"] == visualization["selection_sha256"]
    )
    assert visual_manifest["geometry_sha256"] == visualization["geometry_sha256"]
    assert visualization["checkpoint_sha256"] == file_hashes["checkpoints/last.pt"]

    accepted_original_validation = -0.5895688564
    recovery_validation = float(row["validation_loss"])
    return {
        "pass": True,
        "files": len(files),
        "bytes": total_bytes,
        "sha256": file_hashes,
        "history": {
            key: (float(value) if key not in {"epoch", "stage"} else value)
            for key, value in row.items()
        },
        "checkpoint": {
            "source_best_sha256": source_best_hash,
            "source_last_sha256": source_last_hash,
            "final_best_sha256": file_hashes["checkpoints/best.pt"],
            "final_last_sha256": file_hashes["checkpoints/last.pt"],
            "source_optimizer_steps": sorted(source_steps),
            "final_optimizer_steps": sorted(final_last_steps),
            "source_scheduler_last_epoch": source_scheduler_step,
            "final_scheduler_last_epoch": final_scheduler_step,
            "model_state_best_last_equal": True,
        },
        "postflight": postflight,
        "visualization": {
            "sha256": _sha256(visualization_path),
            "selection_sha256": visualization["selection_sha256"],
            "sample_count": visualization["sample_count"],
            "draws_per_condition": visualization["draws_per_condition"],
            "elapsed_seconds": visualization["elapsed_seconds"],
            "trend": trend,
            "qa": qa,
        },
        "scientific_checkpoint_decision": {
            "accepted_original_validation_loss": accepted_original_validation,
            "recovery_validation_loss": recovery_validation,
            "recovery_minus_accepted": (
                recovery_validation - accepted_original_validation
            ),
            "use_original_response_best": recovery_validation
            >= accepted_original_validation,
            "original_response_best_sha256": (
                "d378de58ce310b9454620db3811e9cbba6760ba426fd7b3e4dd467c709119463"
            ),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--source-best", type=Path, required=True)
    parser.add_argument("--source-last", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-files", type=int, default=32)
    parser.add_argument("--expected-bytes", type=int, default=73664533)
    args = parser.parse_args()
    report = verify(
        args.root,
        args.source_best,
        args.source_last,
        args.expected_files,
        args.expected_bytes,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(args.output)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
