"""Autoregressive per-layer count head with the v2.2 feasibility masks intact."""

from __future__ import annotations

import torch

from cbsc_zdc.models.counts_ar import INACTIVE_LOSS_WEIGHT, AutoregressiveCountHead

COND, LAYERS = 8, 5
MAX_COUNTS = [4, 6, 3, 8, 2]


def head() -> AutoregressiveCountHead:
    torch.manual_seed(0)
    return AutoregressiveCountHead(COND, LAYERS, MAX_COUNTS, 16).to(torch.float64)


def cond(n: int = 16) -> torch.Tensor:
    g = torch.Generator().manual_seed(3)
    return torch.randn(n, COND, generator=g, dtype=torch.float64)


def energies(n: int = 16, value: float = 4.0) -> torch.Tensor:
    return torch.full((n, LAYERS), value, dtype=torch.float64)


def test_inactive_layer_has_only_zero_feasible() -> None:
    model, c = head(), cond(32)
    active = torch.zeros(32, LAYERS, dtype=torch.bool)
    counts, _ = model.sample(c, energies(32), active)
    assert torch.equal(counts, torch.zeros_like(counts))


def test_active_raw_layer_has_only_one_to_geometry_max_feasible() -> None:
    model, c = head(), cond(64)
    active = torch.ones(64, LAYERS, dtype=torch.bool)
    counts, _ = model.sample(c, energies(64), active)
    assert (counts >= 1).all()
    for layer, maximum in enumerate(MAX_COUNTS):
        assert int(counts[:, layer].max()) <= maximum


def test_output_counts_respect_all_layer_geometry_sizes() -> None:
    model, c = head(), cond(128)
    active = torch.ones(128, LAYERS, dtype=torch.bool)
    counts, logits = model.sample(c, energies(128), active)
    assert logits.shape == (128, LAYERS, max(MAX_COUNTS) + 1)
    # Infeasible classes are masked with finfo.min rather than -inf, matching the
    # v2.2 convention: a genuine -inf makes softmax produce NaN when a whole row
    # is masked, which happens for k=0 on an inactive layer.
    floor = torch.finfo(logits.dtype).min
    for layer, maximum in enumerate(MAX_COUNTS):
        infeasible = logits[:, layer, maximum + 1 :]
        assert (infeasible == floor).all()
        assert int(counts[:, layer].max()) <= maximum


def test_threshold_mode_enforces_k_tau_le_budget() -> None:
    model, c = head(), cond(32)
    active = torch.ones(32, LAYERS, dtype=torch.bool)
    # budget 2.0 GeV with tau 1.0 GeV allows at most k = 2
    counts, _ = model.sample(c, energies(32, 2.0), active, threshold_gev=1.0)
    assert (counts <= 2).all()
    assert (counts >= 1).all()


def test_teacher_forcing_uses_truth_previous_count() -> None:
    model, c = head(), cond(8)
    active = torch.ones(8, LAYERS, dtype=torch.bool)
    e = energies(8)
    truth_a = torch.ones(8, LAYERS, dtype=torch.long)
    truth_b = torch.full((8, LAYERS), 2, dtype=torch.long)
    la = model.logits_teacher_forced(c, e, active, truth_a)
    lb = model.logits_teacher_forced(c, e, active, truth_b)
    # layer 0 cannot differ (no previous count yet) but later layers must
    assert torch.allclose(la[:, 0], lb[:, 0])
    assert not torch.allclose(la[:, 1:], lb[:, 1:])


def test_exact_sampling_uses_sampled_previous_count() -> None:
    # Two different seeds must be able to produce different sequences; the feed
    # is the sampled count, not a constant.
    model, c = head(), cond(64)
    active = torch.ones(64, LAYERS, dtype=torch.bool)
    torch.manual_seed(1)
    a, _ = model.sample(c, energies(64), active)
    torch.manual_seed(2)
    b, _ = model.sample(c, energies(64), active)
    assert not torch.equal(a, b)


def test_deterministic_sampling_is_reproducible() -> None:
    model, c = head(), cond(16)
    active = torch.ones(16, LAYERS, dtype=torch.bool)
    a, _ = model.sample(c, energies(16), active, stochastic=False)
    b, _ = model.sample(c, energies(16), active, stochastic=False)
    assert torch.equal(a, b)


def test_loss_weights_inactive_layers_at_the_declared_fraction() -> None:
    assert INACTIVE_LOSS_WEIGHT == 0.2
    model, c = head(), cond(8)
    e = energies(8)
    active = torch.ones(8, LAYERS, dtype=torch.bool)
    truth = torch.ones(8, LAYERS, dtype=torch.long)
    loss = model.loss(c, e, active, truth)
    assert torch.isfinite(loss)
    loss.backward()
    assert all(torch.isfinite(p.grad).all() for p in model.parameters() if p.grad is not None)


def test_mixed_active_inactive_loss_is_finite() -> None:
    model, c = head(), cond(8)
    active = torch.zeros(8, LAYERS, dtype=torch.bool)
    active[:, 1:3] = True
    truth = torch.zeros(8, LAYERS, dtype=torch.long)
    truth[:, 1:3] = 2
    loss = model.loss(c, energies(8), active, truth)
    assert torch.isfinite(loss)
