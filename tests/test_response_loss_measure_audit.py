from __future__ import annotations

import importlib.util
import math
from pathlib import Path

import pytest
import torch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "audit_response_loss_measure",
    ROOT / "scripts" / "audit_response_loss_measure.py",
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_batchwise_correction_matches_trainer_reduction() -> None:
    batches = [
        (torch.tensor([0.0, 10.0, 30.0]), torch.tensor([False, True, True])),
        (torch.tensor([0.0, 0.0]), torch.tensor([False, False])),
        (torch.tensor([90.0]), torch.tensor([True])),
    ]
    result = MODULE.batchwise_log_jacobian(batches, 10.0)
    expected = ((math.log(20.0) + math.log(40.0)) / 2.0 + 0.0 + math.log(100.0)) / 3.0
    assert result["batch_mean_log_jacobian"] == pytest.approx(expected, abs=2e-7)
    assert result["validation_batches"] == 3
    assert result["validation_events"] == 6
    assert result["visible_validation_events"] == 3
    assert result["empty_visible_batches"] == 1


@pytest.mark.parametrize("scale", [0.0, -1.0, float("inf"), float("nan")])
def test_invalid_scale_fails_closed(scale: float) -> None:
    with pytest.raises(ValueError, match="finite and positive"):
        MODULE.batchwise_log_jacobian([], scale)


def test_invalid_response_values_fail_closed() -> None:
    with pytest.raises(ValueError, match="finite and nonnegative"):
        MODULE.batchwise_log_jacobian(
            [(torch.tensor([float("nan")]), torch.tensor([True]))], 10.0
        )
    with pytest.raises(ValueError, match="same-shape rank-one"):
        MODULE.batchwise_log_jacobian(
            [(torch.tensor([[1.0]]), torch.tensor([True]))], 10.0
        )
