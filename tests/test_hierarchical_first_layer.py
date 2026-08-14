"""Hierarchical ECAL-start / HCAL-first-layer head."""

from __future__ import annotations

import torch

from cbsc_zdc.models.first_layer import HierarchicalFirstLayerHead, ecal_start_diagnostics

COND, LAYERS = 8, 65


def head() -> HierarchicalFirstLayerHead:
    torch.manual_seed(0)
    return HierarchicalFirstLayerHead(COND, LAYERS, 32).to(torch.float64)


def cond(n: int = 32) -> torch.Tensor:
    g = torch.Generator().manual_seed(1)
    return torch.randn(n, COND, generator=g, dtype=torch.float64)


def test_invisible_event_returns_minus_one_and_no_active_layer() -> None:
    model, c = head(), cond(16)
    total = torch.zeros(16, dtype=torch.float64)
    visible = torch.zeros(16, dtype=torch.bool)
    out = model.sample(c, total, visible)
    assert (out.first_layer == -1).all()
    assert not out.ecal_start.any()


def test_ecal_branch_returns_exact_layer_zero() -> None:
    model, c = head(), cond(64)
    with torch.no_grad():
        model.ecal[-1].bias.fill_(40.0)
    out = model.sample(c, torch.full((64,), 10.0, dtype=torch.float64), torch.ones(64, dtype=torch.bool))
    assert out.ecal_start.all()
    assert (out.first_layer == 0).all()


def test_hcal_branch_returns_only_layers_one_through_64() -> None:
    model, c = head(), cond(256)
    with torch.no_grad():
        model.ecal[-1].bias.fill_(-40.0)
    out = model.sample(c, torch.full((256,), 10.0, dtype=torch.float64), torch.ones(256, dtype=torch.bool))
    assert not out.ecal_start.any()
    assert (out.first_layer >= 1).all()
    assert (out.first_layer <= LAYERS - 1).all()


def test_hcal_logits_cover_exactly_64_classes() -> None:
    model, c = head(), cond(4)
    _, hcal = model.logits(c, torch.ones(4, dtype=torch.float64))
    assert hcal.shape == (4, LAYERS - 1)


def test_ecal_loss_uses_visible_events_only() -> None:
    model, c = head(), cond(8)
    total = torch.full((8,), 5.0, dtype=torch.float64)
    first = torch.zeros(8, dtype=torch.long)
    visible = torch.tensor([1, 1, 1, 1, 0, 0, 0, 0], dtype=torch.bool)
    ecal_a, _ = model.losses(c, total, first, visible)
    # Changing the *invisible* rows' truth must not move the ECAL term.
    first_changed = first.clone()
    first_changed[4:] = 7
    ecal_b, _ = model.losses(c, total, first_changed, visible)
    assert torch.allclose(ecal_a, ecal_b)


def test_hcal_loss_excludes_ecal_and_invisible_events() -> None:
    model, c = head(), cond(8)
    total = torch.full((8,), 5.0, dtype=torch.float64)
    visible = torch.tensor([1, 1, 1, 1, 0, 0, 0, 0], dtype=torch.bool)
    first = torch.tensor([0, 0, 3, 5, 2, 2, 2, 2], dtype=torch.long)
    _, hcal_a = model.losses(c, total, first, visible)
    # rows 0,1 are ECAL starts and rows 4-7 invisible; only 2 and 3 count
    first_changed = first.clone()
    first_changed[0] = 0
    first_changed[4:] = 9
    _, hcal_b = model.losses(c, total, first_changed, visible)
    assert torch.allclose(hcal_a, hcal_b)


def test_hcal_loss_is_zero_when_every_visible_event_starts_in_ecal() -> None:
    model, c = head(), cond(4)
    total = torch.full((4,), 5.0, dtype=torch.float64)
    _, hcal = model.losses(c, total, torch.zeros(4, dtype=torch.long), torch.ones(4, dtype=torch.bool))
    assert float(hcal) == 0.0


def test_sampled_first_layer_is_forced_active() -> None:
    # The sampler must never return a visible event whose first layer is -1,
    # which downstream stages read as "no active layer".
    model, c = head(), cond(128)
    out = model.sample(c, torch.full((128,), 3.0, dtype=torch.float64), torch.ones(128, dtype=torch.bool))
    assert (out.first_layer >= 0).all()


def test_losses_and_gradients_are_finite() -> None:
    model, c = head(), cond(16)
    total = torch.full((16,), 4.0, dtype=torch.float64)
    first = torch.randint(0, LAYERS, (16,))
    ecal, hcal = model.losses(c, total, first, torch.ones(16, dtype=torch.bool))
    assert torch.isfinite(ecal) and torch.isfinite(hcal)
    (ecal + hcal).backward()
    assert all(torch.isfinite(p.grad).all() for p in model.parameters() if p.grad is not None)


def test_diagnostics_report_prevalence_calibration_and_recall() -> None:
    logits = torch.tensor([3.0, -3.0, 3.0, -3.0], dtype=torch.float64)
    first = torch.tensor([0, 5, 0, 7], dtype=torch.long)
    visible = torch.ones(4, dtype=torch.bool)
    report = ecal_start_diagnostics(logits, first, visible)
    assert report["truth_prevalence"] == 0.5
    assert report["precision"] == 1.0
    assert report["recall"] == 1.0
    assert report["brier_score"] < 0.01
    assert len(report["reliability_bins"]) == 10
