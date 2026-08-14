"""Frozen support-sampling temperature over the exact hard top-k."""

from __future__ import annotations

import pytest
import torch

from cbsc_zdc.models.support import SUPPORT_TEMPERATURE_DEFAULT, exact_k_mask


def logits(b: int = 8, n: int = 20) -> torch.Tensor:
    g = torch.Generator().manual_seed(9)
    return torch.randn(b, n, generator=g, dtype=torch.float64)


def test_temperature_default_is_one() -> None:
    assert SUPPORT_TEMPERATURE_DEFAULT == 1.0


def test_selected_count_equals_k_for_every_layer_and_temperature() -> None:
    a = logits(16, 30)
    for temperature in (0.25, 0.5, 1.0, 2.0):
        for k_value in (0, 1, 7, 30):
            k = torch.full((16,), k_value, dtype=torch.long)
            mask = exact_k_mask(a, k, stochastic=True, temperature=temperature)
            assert torch.equal(mask.sum(dim=-1), k)


def test_deterministic_topk_order_is_temperature_invariant() -> None:
    # Temperature scales the logits; without noise the ordering, and therefore
    # the selected set, cannot change.
    a = logits(8, 25)
    k = torch.full((8,), 6, dtype=torch.long)
    reference = exact_k_mask(a, k, stochastic=False, temperature=1.0)
    for temperature in (0.1, 0.25, 2.0, 10.0):
        assert torch.equal(exact_k_mask(a, k, stochastic=False, temperature=temperature), reference)


def test_fixed_noise_lower_temperature_increases_logit_dominance() -> None:
    # With the noise held fixed, a lower temperature must agree more often with
    # the noiseless (logit-determined) selection.
    a = logits(64, 40)
    k = torch.full((64,), 8, dtype=torch.long)
    noiseless = exact_k_mask(a, k, stochastic=False)

    def agreement(temperature: float) -> float:
        torch.manual_seed(0)  # identical Gumbel draw for every temperature
        mask = exact_k_mask(a, k, stochastic=True, temperature=temperature)
        return float((mask & noiseless).sum()) / float(noiseless.sum())

    low, mid, high = agreement(0.25), agreement(1.0), agreement(2.0)
    assert low > mid > high


def test_temperature_must_be_finite_and_strictly_positive() -> None:
    a = logits(4, 10)
    k = torch.full((4,), 3, dtype=torch.long)
    for bad in (0.0, -1.0, float("inf"), float("nan")):
        with pytest.raises(ValueError, match="temperature"):
            exact_k_mask(a, k, stochastic=True, temperature=bad)


def test_invalid_nodes_are_never_selected() -> None:
    # Invalid channels arrive already masked to finfo.min by support_logits();
    # they must never win a slot while any valid channel remains.
    a = logits(4, 12)
    a[:, 6:] = torch.finfo(a.dtype).min
    k = torch.full((4,), 6, dtype=torch.long)
    for temperature in (0.25, 1.0, 2.0):
        mask = exact_k_mask(a, k, stochastic=True, temperature=temperature)
        assert not mask[:, 6:].any()
        assert torch.equal(mask.sum(dim=-1), k)


def test_zero_k_selects_nothing_and_full_k_selects_everything() -> None:
    a = logits(4, 9)
    empty = exact_k_mask(a, torch.zeros(4, dtype=torch.long), stochastic=True)
    assert not empty.any()
    full = exact_k_mask(a, torch.full((4,), 9, dtype=torch.long), stochastic=True)
    assert full.all()


def test_infeasible_k_is_rejected() -> None:
    a = logits(4, 9)
    with pytest.raises(ValueError, match="infeasible"):
        exact_k_mask(a, torch.full((4,), 10, dtype=torch.long))
    with pytest.raises(ValueError, match="infeasible"):
        exact_k_mask(a, torch.full((4,), -1, dtype=torch.long))


def test_forward_output_is_a_hard_boolean_mask() -> None:
    # The forward path stays exact hard top-k; no relaxation is introduced.
    a = logits(4, 10)
    mask = exact_k_mask(a, torch.full((4,), 4, dtype=torch.long), stochastic=True, temperature=0.5)
    assert mask.dtype == torch.bool
    assert set(mask.unique().tolist()) <= {False, True}
