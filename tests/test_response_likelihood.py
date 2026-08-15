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
    head = ResponseHead(
        cond_dim=2, hidden=4, components=1, response_scale_gev=1.0
    )
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

    expected_nll = math.log(target_scale * math.sqrt(2.0 * math.pi)) + math.log(1.0)
    assert torch.isfinite(response_nll)
    assert response_nll.item() < 0.0
    assert response_nll.item() == pytest.approx(expected_nll, abs=1.0e-6)


def test_response_nll_is_a_density_in_deposited_energy_gev() -> None:
    head = ResponseHead(
        cond_dim=2, hidden=4, components=1, response_scale_gev=10.0
    )
    target_scale = 0.2
    raw_scale = math.log(math.expm1(target_scale - 0.05))
    with torch.no_grad():
        for parameter in head.parameters():
            parameter.zero_()
        head.mixture[-1].bias[2] = raw_scale

    condition = torch.zeros(1, 2)
    total_gev = torch.tensor([10.0])
    visible_truth = torch.ones(1, dtype=torch.bool)
    _, response_nll = head.nll(condition, total_gev, visible_truth)

    y = math.log1p(10.0 / 10.0)
    nll_y = math.log(target_scale * math.sqrt(2.0 * math.pi)) + 0.5 * (y / target_scale) ** 2
    expected_gev = nll_y + math.log(10.0 + 10.0)
    assert response_nll.item() == pytest.approx(expected_gev, abs=2e-6)


def test_target_jacobian_does_not_change_parameter_gradients() -> None:
    head = ResponseHead(cond_dim=2, hidden=4, components=1)
    condition = torch.randn(5, 2)
    total_gev = torch.linspace(1.0, 5.0, 5)
    visible_truth = torch.ones(5, dtype=torch.bool)
    _, nll_gev = head.nll(condition, total_gev, visible_truth)
    correction = torch.log(total_gev + head.response_scale_gev).mean()
    parameters = [p for p in head.mixture.parameters() if p.requires_grad]
    gev_grads = torch.autograd.grad(nll_gev, parameters, retain_graph=True)
    transformed_grads = torch.autograd.grad(nll_gev - correction, parameters)
    for observed, expected in zip(gev_grads, transformed_grads):
        assert torch.equal(observed, expected)
