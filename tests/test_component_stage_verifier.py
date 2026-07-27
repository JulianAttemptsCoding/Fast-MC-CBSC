from __future__ import annotations

import pytest
import torch

from scripts.verify_component_stage_output import (
    EXPECTED_PREDECESSOR_FILENAME,
    _assert_cross_epoch_visual_contract,
    _assert_weighted_history,
    _compare_model_state,
    _expected_scheduler_step,
    _read_history,
    _visualization_population_metrics,
)


def _payload() -> dict:
    return {
        "model_state": {
            "condition.weight": torch.tensor([1.0, 2.0]),
            "response.weight": torch.tensor([3.0]),
            "profile.weight": torch.tensor([4.0, 5.0]),
        }
    }


def test_component_verifier_accepts_only_stage_tensor_changes():
    source = _payload()
    candidate = _payload()
    candidate["model_state"]["profile.weight"][0] += 1

    changed, frozen_mismatches = _compare_model_state(
        source, candidate, "profile."
    )

    assert changed == ["profile.weight"]
    assert frozen_mismatches == []


def test_component_verifier_rejects_frozen_tensor_change():
    source = _payload()
    candidate = _payload()
    candidate["model_state"]["condition.weight"][0] += 1

    with pytest.raises(AssertionError):
        _compare_model_state(source, candidate, "profile.")


def test_joint_verifier_accepts_changes_across_model():
    source = _payload()
    candidate = _payload()
    candidate["model_state"]["condition.weight"][0] += 1
    candidate["model_state"]["profile.weight"][0] += 1

    changed, frozen_mismatches = _compare_model_state(source, candidate, None)

    assert changed == ["condition.weight", "profile.weight"]
    assert frozen_mismatches == []


def test_weighted_history_reconstructs_joint_total():
    components = {
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
    weights = {name: float(index + 1) for index, name in enumerate(sorted(components))}
    row = {f"train_{name}": "0.5" for name in components}
    row.update(epoch="0", train_loss=str(0.5 * sum(weights.values())))
    _assert_weighted_history([row], "joint", weights)


def test_weighted_history_rejects_inconsistent_total():
    with pytest.raises(AssertionError):
        _assert_weighted_history(
            [{"epoch": "0", "train_count": "1.0", "train_loss": "2.0"}],
            "count",
            {"count": 1.0},
        )


def _visualization(epoch: int = 0) -> dict:
    offset = epoch * 1_000_003
    group = {
        "dataset_index": 1,
        "event_id": 2,
        "global_index": 3,
        "kinetic_energy_gev": 100.0,
        "p4_total_gev": [100.94, 0.0, 0.0, 100.0],
        "selection_position": 0,
        "source_group": 4,
        "geant4": {"fixed": True},
        "fast_mc": [
            {
                "draw": draw,
                "seed_group": 99 + offset,
                "summary": {
                    "total_response_gev": 5.0,
                    "layer_energy_gev": [2.0, 3.0],
                    "hit_count": 2,
                },
                "deposit": {
                    "cell_index": [1, 2],
                    "energy_gev": [2.0, 3.0],
                },
            }
            for draw in range(5)
        ],
    }
    return {
        "epoch": epoch,
        "selection_sha256": "fixed",
        "generation_seeds": [value + offset for value in range(50)],
        "groups": [
            {**group, "selection_position": index}
            for index in range(50)
        ],
    }


def test_cross_epoch_visual_contract():
    reference = _visualization(epoch=0)
    candidate = _visualization(epoch=1)
    result = _assert_cross_epoch_visual_contract(reference, candidate)
    assert result == {
        "fixed_truth_conditions": 50,
        "independent_fast_mc_draws": 250,
        "generation_seed_offset": 1_000_003,
    }


def test_cross_epoch_visual_contract_rejects_seed_reuse():
    reference = _visualization(epoch=0)
    candidate = _visualization(epoch=1)
    candidate["generation_seeds"] = reference["generation_seeds"]
    with pytest.raises(AssertionError):
        _assert_cross_epoch_visual_contract(reference, candidate)


def test_visualization_population_metrics_detects_diversity_and_zeros():
    visualization = _visualization(epoch=0)
    for index, group in enumerate(visualization["groups"]):
        group["geant4"] = {
            "summary": {
                "total_response_gev": 0.0 if index == 0 else 5.0
            }
        }
        for draw_index, draw in enumerate(group["fast_mc"]):
            draw["summary"]["total_response_gev"] = (
                0.0 if draw_index == 0 else float(draw_index)
            )
            draw["deposit"]["energy_gev"] = [float(draw_index), 3.0]

    metrics = _visualization_population_metrics(visualization)

    assert metrics["truth_zero_response_fraction"] == 1 / 50
    assert metrics["generated_zero_response_fraction"] == 1 / 5
    assert metrics["groups_with_multiple_unique_deposits"] == 50
    assert metrics["minimum_unique_deposits_per_condition"] == 5
    assert metrics["mean_within_condition_response_std_gev"] > 0


def test_component_predecessor_filenames_follow_stage_order():
    assert EXPECTED_PREDECESSOR_FILENAME == {
        "profile": "response_best.pt",
        "count": "profile_best.pt",
        "support": "count_best.pt",
        "share": "support_best.pt",
        "joint": "share_best.pt",
    }


def test_resume_history_starts_after_parent_epoch(tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "history.csv").write_text(
        "epoch,stage,train_loss,validation_loss,learning_rate,seconds,"
        "examples_per_second,train_count\n"
        "1,count,1.0,0.9,0.001,10.0,20.0,1.0\n"
        "2,count,0.8,0.7,0.0001,11.0,19.0,0.8\n",
        encoding="utf-8",
    )

    history = _read_history(
        tmp_path,
        "count",
        expected_epoch=2,
        expected_start_epoch=1,
    )
    assert [int(row["epoch"]) for row in history] == [1, 2]
    with pytest.raises(AssertionError):
        _read_history(tmp_path, "count", expected_epoch=2)


def test_scheduler_steps_restart_without_resetting_optimizer_epochs():
    assert _expected_scheduler_step(100, 0, 1, True) == 100
    assert _expected_scheduler_step(100, 1, 1, True) == 100
    assert _expected_scheduler_step(100, 2, 1, True) == 200
    assert _expected_scheduler_step(100, 2, 1, False) == 300
