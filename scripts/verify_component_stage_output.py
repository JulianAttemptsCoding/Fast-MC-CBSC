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


STAGE_PREFIX = {
    "profile": "profile.",
    "count": "counts.",
    "support": "support.",
    "share": "share.",
    "joint": None,
}
EXPECTED_PREVIOUS = {
    "profile": "response",
    "count": "profile",
    "support": "count",
    "share": "support",
    "joint": "share",
}
EXPECTED_PREDECESSOR_FILENAME = {
    "profile": "response_best.pt",
    "count": "profile_best.pt",
    "support": "count_best.pt",
    "share": "support_best.pt",
    "joint": "share_best.pt",
}
STAGE_COMPONENTS = {
    "profile": {"first_layer", "active", "profile_flow"},
    "count": {"count"},
    "support": {"support_bce", "support_rank"},
    "share": {"share_flow"},
    "joint": {
        "visible",
        "response",
        "first_layer",
        "active",
        "profile_flow",
        "count",
        "support_bce",
        "support_rank",
        "share_flow",
    },
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


def _assert_invariants(report: dict[str, Any], tolerance: float) -> None:
    assert report["pass"] is True
    for field in INVARIANT_ZERO_FIELDS:
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


def _compare_model_state(
    source: dict[str, Any],
    candidate: dict[str, Any],
    trainable_prefix: str | None,
) -> tuple[list[str], list[str]]:
    source_state = source["model_state"]
    candidate_state = candidate["model_state"]
    assert source_state.keys() == candidate_state.keys()
    changed: list[str] = []
    frozen_mismatches: list[str] = []
    for name in source_state:
        equal = torch.equal(
            source_state[name].detach().cpu(),
            candidate_state[name].detach().cpu(),
        )
        if not equal:
            changed.append(name)
            if trainable_prefix is not None and not name.startswith(trainable_prefix):
                frozen_mismatches.append(name)
    assert not frozen_mismatches, frozen_mismatches
    assert changed, "no model tensor changed from predecessor"
    if trainable_prefix is not None:
        assert all(name.startswith(trainable_prefix) for name in changed)
    return changed, frozen_mismatches


def _assert_weighted_history(
    history: list[dict[str, str]],
    stage: str,
    weights: dict[str, Any],
) -> None:
    components = STAGE_COMPONENTS[stage]
    for row in history:
        reconstructed = sum(
            float(row[f"train_{name}"]) * float(weights[name])
            for name in components
        )
        assert math.isclose(
            float(row["train_loss"]),
            reconstructed,
            rel_tol=1e-7,
            abs_tol=1e-7,
        ), (row["epoch"], row["train_loss"], reconstructed)


def _read_history(root: Path, stage: str, expected_epoch: int) -> list[dict[str, str]]:
    with (root / "logs/history.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        history = list(csv.DictReader(handle))
    assert len(history) == expected_epoch + 1, len(history)
    assert [int(row["epoch"]) for row in history] == list(
        range(expected_epoch + 1)
    )
    required_components = STAGE_COMPONENTS[stage]
    for row in history:
        assert row["stage"] == stage
        finite_fields = {
            "train_loss",
            "validation_loss",
            "learning_rate",
            "seconds",
            "examples_per_second",
            *{f"train_{name}" for name in required_components},
        }
        for field in finite_fields:
            assert field in row, field
            assert math.isfinite(float(row[field])), (field, row[field])
        assert float(row["seconds"]) > 0
        assert float(row["examples_per_second"]) > 0
        if row.get("cuda_peak_memory_bytes", ""):
            assert int(float(row["cuda_peak_memory_bytes"])) > 0
    return history


def _assert_visualization(
    root: Path,
    stage: str,
    expected_epoch: int,
    last_hash: str,
    tolerance: float,
    expected_selection_sha256: str | None,
) -> dict[str, Any]:
    path = root / f"reports/visualization/epoch_{expected_epoch:04d}.json"
    visualization = _json(path)
    assert visualization["schema_version"] == 1
    assert visualization["split"] == "validation"
    assert visualization["synthetic_source"] is False
    assert visualization["stage"] == stage
    assert int(visualization["epoch"]) == expected_epoch
    assert int(visualization["sample_count"]) == 50
    assert int(visualization["draws_per_condition"]) == 5
    assert int(visualization["profile_steps"]) == 8
    assert int(visualization["share_steps"]) == 8
    assert visualization["checkpoint_sha256"] == last_hash
    assert len(visualization["groups"]) == 50
    assert all(len(group["p4_total_gev"]) == 4 for group in visualization["groups"])
    assert all(len(group["fast_mc"]) == 5 for group in visualization["groups"])
    selection = visualization["selection"]
    assert len(set(selection["dataset_indices"])) == 50
    assert len(set(selection["global_indices"])) == 50
    assert len(set(selection["event_ids"])) == 50
    if expected_selection_sha256:
        assert visualization["selection_sha256"] == expected_selection_sha256
    qa = visualization["qa"]
    assert qa["pass"] is True
    assert int(qa["test_events_used"]) == 0
    assert qa["selection_unique"] is True
    assert int(qa["groups_with_exact_draw_count"]) == 50
    for field in (
        "truth_nonfinite",
        "generated_nonfinite",
        "truth_negative",
        "generated_negative",
    ):
        assert int(qa[field]) == 0, (field, qa[field])
    _assert_invariants(qa["invariants"], tolerance)
    trend = visualization["aggregate"]["trend"]
    assert all(math.isfinite(float(value)) for value in trend.values())
    manifest = _json(root / "reports/visualization/manifest.json")
    assert int(manifest["latest_epoch"]) == expected_epoch
    assert manifest["selection_sha256"] == visualization["selection_sha256"]
    assert manifest["geometry_sha256"] == visualization["geometry_sha256"]
    manifest_epochs = {int(row["epoch"]): row for row in manifest["epochs"]}
    assert expected_epoch in manifest_epochs
    assert manifest_epochs[expected_epoch]["sha256"] == _sha256(path)
    return visualization


def _assert_cross_epoch_visual_contract(
    reference: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, int]:
    assert reference["selection_sha256"] == candidate["selection_sha256"]
    epoch_delta = int(candidate["epoch"]) - int(reference["epoch"])
    assert epoch_delta > 0
    expected_offset = epoch_delta * 1_000_003
    assert [
        int(new) - int(old)
        for old, new in zip(
            reference["generation_seeds"],
            candidate["generation_seeds"],
            strict=True,
        )
    ] == [expected_offset] * 50
    assert len(reference["groups"]) == len(candidate["groups"]) == 50
    checked_draws = 0
    for old_group, new_group in zip(
        reference["groups"], candidate["groups"], strict=True
    ):
        for field in (
            "dataset_index",
            "event_id",
            "global_index",
            "kinetic_energy_gev",
            "p4_total_gev",
            "selection_position",
            "source_group",
            "geant4",
        ):
            assert old_group[field] == new_group[field], field
        assert len(old_group["fast_mc"]) == len(new_group["fast_mc"]) == 5
        for old_draw, new_draw in zip(
            old_group["fast_mc"], new_group["fast_mc"], strict=True
        ):
            assert old_draw["draw"] == new_draw["draw"]
            assert (
                int(new_draw["seed_group"]) - int(old_draw["seed_group"])
                == expected_offset
            )
            checked_draws += 1
    return {
        "fixed_truth_conditions": 50,
        "independent_fast_mc_draws": checked_draws,
        "generation_seed_offset": expected_offset,
    }


def verify(
    root: Path,
    source_checkpoint: Path,
    stage: str,
    expected_epoch: int,
    expected_source_sha256: str,
    expected_staged_count: int,
    expected_base_count: int,
    expected_overlay_suffix: str,
    expected_overlay_count: int,
    expected_selection_sha256: str | None,
    comparison_visualization: Path | None,
    terminal: bool,
    expected_batch_size: int,
    expected_gradient_accumulation: int,
) -> dict[str, Any]:
    assert stage in STAGE_PREFIX
    assert root.is_dir()
    assert not (root / "vertex_failure.json").exists()

    source_hash = _sha256(source_checkpoint)
    assert source_hash == expected_source_sha256
    source = torch.load(source_checkpoint, map_location="cpu", weights_only=False)
    assert source["stage"] == EXPECTED_PREVIOUS[stage]

    history = _read_history(root, stage, expected_epoch)
    current_row = history[-1]

    files = sorted(path for path in root.rglob("*") if path.is_file())
    file_hashes = {
        path.relative_to(root).as_posix(): _sha256(path) for path in files
    }
    best_path = root / "checkpoints/best.pt"
    last_path = root / "checkpoints/last.pt"
    best_hash = file_hashes["checkpoints/best.pt"]
    last_hash = file_hashes["checkpoints/last.pt"]
    best = torch.load(best_path, map_location="cpu", weights_only=False)
    last = torch.load(last_path, map_location="cpu", weights_only=False)

    assert best["stage"] == last["stage"] == stage
    assert 0 <= int(best["epoch"]) <= expected_epoch
    assert int(last["epoch"]) == expected_epoch
    validation_losses = [float(row["validation_loss"]) for row in history]
    selected_validation = min(validation_losses)
    assert math.isclose(
        float(best["best_metric"]), selected_validation, rel_tol=0, abs_tol=1e-12
    )
    assert math.isclose(
        float(last["best_metric"]), selected_validation, rel_tol=0, abs_tol=1e-12
    )
    assert best["provenance"] == last["provenance"]

    best_changed, _ = _compare_model_state(source, best, STAGE_PREFIX[stage])
    last_changed, _ = _compare_model_state(source, last, STAGE_PREFIX[stage])

    runtime = yaml.safe_load(
        (root / "runtime_config.yaml").read_text(encoding="utf-8")
    )
    training = runtime["training"]
    _assert_weighted_history(history, stage, runtime["loss_weights"])
    assert training["stage"] == stage
    assert training["amp"] is False
    assert training["train_condition_encoder"] is (stage == "joint")
    assert int(training["epochs"]) == 3
    assert int(training["batch_size"]) == expected_batch_size
    assert int(training["gradient_accumulation"]) == expected_gradient_accumulation
    assert int(training["checkpoint_interval_updates"]) == 0
    assert training["initialize_from_sha256"] == source_hash
    assert str(training["initialize_from"]).endswith(
        EXPECTED_PREDECESSOR_FILENAME[stage]
    )

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
    assert (
        sum(
            item["source_prefix"].endswith("prep-20260724-r5")
            for item in staged
        )
        == expected_base_count
    )
    assert (
        sum(
            item["source_prefix"].endswith(expected_overlay_suffix)
            for item in staged
        )
        == expected_overlay_count
    )

    batches_per_epoch = 26624 // int(training["batch_size"])
    updates_per_epoch = math.ceil(
        batches_per_epoch / int(training["gradient_accumulation"])
    )
    expected_last_step = updates_per_epoch * (expected_epoch + 1)
    last_steps = _optimizer_steps(last)
    assert last_steps == {expected_last_step}, last_steps
    assert int(last["scheduler_state"]["last_epoch"]) == expected_last_step
    best_expected_step = updates_per_epoch * (int(best["epoch"]) + 1)
    assert _optimizer_steps(best) == {best_expected_step}
    assert int(best["scheduler_state"]["last_epoch"]) == best_expected_step
    assert last.get("rng_state", {}).get("torch") is not None
    assert last.get("rng_state", {}).get("cuda") is not None

    tolerance = float(runtime["evaluation"]["closure_tolerance_gev"])
    epoch_invariants = _json(
        root / f"reports/invariant_epoch_{expected_epoch:04d}.json"
    )
    _assert_invariants(epoch_invariants, tolerance)
    progress = _json(root / f"reports/progress_epoch_{expected_epoch:04d}.json")
    assert int(progress["epoch"]) == expected_epoch
    assert progress["row"]["stage"] == stage
    assert progress["best_checkpoint_sha256"] == best_hash
    assert progress["last_checkpoint_sha256"] == last_hash

    visualization = _assert_visualization(
        root,
        stage,
        expected_epoch,
        last_hash,
        tolerance,
        expected_selection_sha256,
    )
    cross_epoch_contract = None
    if comparison_visualization is not None:
        cross_epoch_contract = _assert_cross_epoch_visual_contract(
            _json(comparison_visualization),
            visualization,
        )

    postflight: dict[str, Any] | None = None
    if terminal:
        summary = _json(root / "reports/training_summary.json")
        assert summary["stage"] == stage
        assert int(summary["updates"]) == expected_last_step
        assert math.isclose(
            float(summary["best_validation_loss"]),
            selected_validation,
            rel_tol=0,
            abs_tol=1e-12,
        )
        reload_invariants = _json(
            root / "reports/training_postflight_invariants.json"
        )
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
        vertex_result = _json(root / "vertex_result.json")
        assert vertex_result["training"]["stage"] == stage
        assert vertex_result["training_postflight"]["pass"] is True

    first_validation = float(history[0]["validation_loss"])
    last_validation = float(history[-1]["validation_loss"])
    return {
        "pass": True,
        "stage": stage,
        "epoch": expected_epoch,
        "terminal": terminal,
        "files": len(files),
        "bytes": sum(path.stat().st_size for path in files),
        "sha256": file_hashes,
        "checkpoint": {
            "source_sha256": source_hash,
            "best_sha256": best_hash,
            "last_sha256": last_hash,
            "best_epoch": int(best["epoch"]),
            "last_epoch": int(last["epoch"]),
            "best_changed_tensors": best_changed,
            "last_changed_tensors": last_changed,
            "frozen_tensor_mismatches": [],
            "last_optimizer_steps": sorted(last_steps),
            "last_scheduler_step": int(last["scheduler_state"]["last_epoch"]),
        },
        "history": history,
        "loss_trend": {
            "first_validation_loss": first_validation,
            "last_validation_loss": last_validation,
            "best_validation_loss": selected_validation,
            "last_minus_first": last_validation - first_validation,
            "improved_from_first": (
                expected_epoch == 0 or selected_validation < first_validation
            ),
        },
        "invariants": epoch_invariants,
        "visualization": {
            "sha256": _sha256(
                root
                / f"reports/visualization/epoch_{expected_epoch:04d}.json"
            ),
            "selection_sha256": visualization["selection_sha256"],
            "elapsed_seconds": visualization["elapsed_seconds"],
            "trend": visualization["aggregate"]["trend"],
            "qa": visualization["qa"],
            "cross_epoch_contract": cross_epoch_contract,
        },
        "postflight": postflight,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--source-checkpoint", type=Path, required=True)
    parser.add_argument("--stage", choices=sorted(STAGE_PREFIX), required=True)
    parser.add_argument("--expected-epoch", type=int, required=True)
    parser.add_argument("--expected-source-sha256", required=True)
    parser.add_argument("--expected-staged-count", type=int, required=True)
    parser.add_argument("--expected-base-count", type=int, default=205)
    parser.add_argument("--expected-overlay-suffix", required=True)
    parser.add_argument("--expected-overlay-count", type=int, required=True)
    parser.add_argument("--expected-batch-size", type=int, default=6)
    parser.add_argument("--expected-gradient-accumulation", type=int, default=4)
    parser.add_argument("--expected-selection-sha256")
    parser.add_argument("--comparison-visualization", type=Path)
    parser.add_argument("--terminal", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = verify(
        root=args.root,
        source_checkpoint=args.source_checkpoint,
        stage=args.stage,
        expected_epoch=args.expected_epoch,
        expected_source_sha256=args.expected_source_sha256,
        expected_staged_count=args.expected_staged_count,
        expected_base_count=args.expected_base_count,
        expected_overlay_suffix=args.expected_overlay_suffix,
        expected_overlay_count=args.expected_overlay_count,
        expected_selection_sha256=args.expected_selection_sha256,
        comparison_visualization=args.comparison_visualization,
        terminal=args.terminal,
        expected_batch_size=args.expected_batch_size,
        expected_gradient_accumulation=args.expected_gradient_accumulation,
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
