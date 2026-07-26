from __future__ import annotations

import math

import pytest
import torch

from cbsc_zdc.models.response import ResponseHead


def test_continuous_response_nll_can_be_negative_without_failure() -> None:
    """A narrow, valid density has negative NLL at its mode.

    This guards against treating zero as a lower bound for continuous-density
    negative log likelihood or wrapping the response NLL in abs().
    """
    head = ResponseHead(cond_dim=2, hidden=4, components=1)
    target_scale = 0.1
    raw_scale = math.log(math.expm1(target_scale - 0.05))

    with torch.no_grad():
        for parameter in head.parameters():
            parameter.zero_()
        # The output is chunked as mixture logits, location, raw scale.
        head.mixture[-1].bias[2] = raw_scale

    condition = torch.zeros(8, 2)
    total_gev = torch.zeros(8)
    visible_truth = torch.ones(8, dtype=torch.bool)
    _, response_nll = head.nll(condition, total_gev, visible_truth)

    expected_nll = math.log(target_scale * math.sqrt(2.0 * math.pi))
    assert torch.isfinite(response_nll)
    assert response_nll.item() < 0.0
    assert response_nll.item() == pytest.approx(expected_nll, abs=1.0e-6)
