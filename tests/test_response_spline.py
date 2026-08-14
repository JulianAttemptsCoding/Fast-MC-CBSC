"""Bounded conditional rational-quadratic response spline."""

from __future__ import annotations

import pytest
import torch

from cbsc_zdc.models.response_v3 import BoundedResponseHead
from cbsc_zdc.models.splines import (
    DEFAULT_BINS,
    MIN_BIN_HEIGHT,
    MIN_BIN_WIDTH,
    MIN_DERIVATIVE,
    ConditionalRationalQuadraticSpline,
    rational_quadratic_transform,
)

COND_DIM = 8


def spline(dtype=torch.float64) -> ConditionalRationalQuadraticSpline:
    torch.manual_seed(3)
    return ConditionalRationalQuadraticSpline(COND_DIM, 32, DEFAULT_BINS).to(dtype)


def cond(n: int = 12, dtype=torch.float64) -> torch.Tensor:
    g = torch.Generator().manual_seed(5)
    return torch.randn(n, COND_DIM, generator=g, dtype=torch.float64).to(dtype)


def test_widths_heights_and_derivatives_respect_minima() -> None:
    model = spline()
    p = model.normalized_parameters(cond())
    assert (p["widths"] >= MIN_BIN_WIDTH - 1e-12).all()
    assert (p["heights"] >= MIN_BIN_HEIGHT - 1e-12).all()
    assert (p["derivatives"] >= MIN_DERIVATIVE - 1e-12).all()
    assert torch.allclose(p["widths"].sum(-1), torch.ones(p["widths"].shape[0], dtype=torch.float64))
    assert torch.allclose(p["heights"].sum(-1), torch.ones(p["heights"].shape[0], dtype=torch.float64))
    assert p["derivatives"].shape[-1] == DEFAULT_BINS + 1


def test_float64_forward_inverse_roundtrip_max_abs_lt_1e_8() -> None:
    model = spline(torch.float64)
    c = cond(dtype=torch.float64)
    base = torch.linspace(1e-4, 1 - 1e-4, c.shape[0], dtype=torch.float64)
    out, _ = model(base, c, inverse=False)
    back, _ = model(out, c, inverse=True)
    assert (back - base).abs().max().item() < 1e-8


def test_float32_forward_inverse_roundtrip_max_abs_lt_1e_5() -> None:
    model = spline(torch.float32)
    c = cond(dtype=torch.float32)
    base = torch.linspace(1e-3, 1 - 1e-3, c.shape[0], dtype=torch.float32)
    out, _ = model(base, c, inverse=False)
    back, _ = model(out, c, inverse=True)
    assert (back - base).abs().max().item() < 1e-5


def test_transform_is_strictly_monotone_and_inside_the_unit_interval() -> None:
    model = spline()
    c = cond(1).expand(64, COND_DIM).contiguous()
    base = torch.linspace(1e-6, 1 - 1e-6, 64, dtype=torch.float64)
    out, _ = model(base, c, inverse=False)
    assert (out > 0).all() and (out < 1).all()
    assert (out[1:] > out[:-1]).all()


def test_analytic_log_jacobian_matches_central_finite_difference() -> None:
    model = spline()
    c = cond(6)
    base = torch.full((6,), 0.4, dtype=torch.float64)
    _, logabsdet = model(base, c, inverse=False)
    h = 1e-6
    up, _ = model(base + h, c, inverse=False)
    down, _ = model(base - h, c, inverse=False)
    numeric = torch.log((up - down) / (2 * h))
    assert (logabsdet - numeric).abs().max().item() < 1e-6


def test_inverse_log_jacobian_is_the_negated_forward_one() -> None:
    model = spline()
    c = cond(6)
    base = torch.full((6,), 0.3, dtype=torch.float64)
    out, forward = model(base, c, inverse=False)
    _, inverse = model(out, c, inverse=True)
    assert (forward + inverse).abs().max().item() < 1e-9


def test_torch_gradcheck_passes_for_interior_points() -> None:
    torch.manual_seed(0)
    bins = 4
    widths = torch.randn(3, bins, dtype=torch.float64, requires_grad=True)
    heights = torch.randn(3, bins, dtype=torch.float64, requires_grad=True)
    derivatives = torch.randn(3, bins + 1, dtype=torch.float64, requires_grad=True)
    inputs = torch.full((3,), 0.37, dtype=torch.float64, requires_grad=True)

    def fn(x, w, h, d):
        out, _ = rational_quadratic_transform(x, w, h, d)
        return out

    assert torch.autograd.gradcheck(fn, (inputs, widths, heights, derivatives), eps=1e-6, atol=1e-7)


def test_visible_samples_are_strictly_positive_and_below_cap() -> None:
    torch.manual_seed(1)
    head = BoundedResponseHead(COND_DIM, 32).to(torch.float64)
    c = cond(256)
    cap = torch.full((256,), 40.0, dtype=torch.float64)
    # force every event visible so the positive branch is exercised alone
    with torch.no_grad():
        head.visible[-1].bias.fill_(30.0)
    out = head.sample(c, cap)
    assert out.visible.all()
    assert (out.total_response > 0).all()
    assert (out.total_response < cap).all()


def test_invisible_samples_are_exact_zero() -> None:
    torch.manual_seed(2)
    head = BoundedResponseHead(COND_DIM, 32).to(torch.float64)
    c = cond(128)
    cap = torch.full((128,), 40.0, dtype=torch.float64)
    with torch.no_grad():
        head.visible[-1].bias.fill_(-30.0)
    out = head.sample(c, cap)
    assert not out.visible.any()
    assert torch.equal(out.total_response, torch.zeros_like(out.total_response))


def test_positive_branch_never_changes_visibility() -> None:
    # Across many draws the visible count must equal the hurdle's own draw --
    # the positive branch may never clear a visible event, which is the second
    # zero atom the v2.2 head produced.
    torch.manual_seed(4)
    head = BoundedResponseHead(COND_DIM, 32).to(torch.float64)
    c = cond(512)
    cap = torch.full((512,), 5.0, dtype=torch.float64)
    out = head.sample(c, cap)
    positive = out.total_response > 0
    assert torch.equal(positive, out.visible)
    zero_and_visible = (out.total_response == 0) & out.visible
    assert not zero_and_visible.any()


def test_nll_and_parameter_gradients_are_finite() -> None:
    torch.manual_seed(6)
    head = BoundedResponseHead(COND_DIM, 32).to(torch.float64)
    c = cond(32)
    cap = torch.full((32,), 50.0, dtype=torch.float64)
    total = torch.full((32,), 12.0, dtype=torch.float64)
    visible = torch.ones(32, dtype=torch.bool)
    bce, nll = head.nll(c, total, visible, cap)
    assert torch.isfinite(bce) and torch.isfinite(nll)
    (bce + nll).backward()
    grads = [p.grad for p in head.parameters() if p.grad is not None]
    assert grads
    assert all(torch.isfinite(g).all() for g in grads)


def test_a_target_outside_the_envelope_is_fatal_not_clamped() -> None:
    head = BoundedResponseHead(COND_DIM, 32).to(torch.float64)
    c = cond(4)
    cap = torch.full((4,), 10.0, dtype=torch.float64)
    visible = torch.ones(4, dtype=torch.bool)
    with pytest.raises(ValueError, match="outside its train-built envelope"):
        head.nll(c, torch.full((4,), 10.0, dtype=torch.float64), visible, cap)
    with pytest.raises(ValueError, match="outside its train-built envelope"):
        head.nll(c, torch.full((4,), 25.0, dtype=torch.float64), visible, cap)


def test_no_visible_event_yields_a_zero_positive_term() -> None:
    head = BoundedResponseHead(COND_DIM, 32).to(torch.float64)
    c = cond(4)
    cap = torch.full((4,), 10.0, dtype=torch.float64)
    bce, nll = head.nll(c, torch.zeros(4, dtype=torch.float64), torch.zeros(4, dtype=torch.bool), cap)
    assert torch.isfinite(bce)
    assert float(nll) == 0.0
