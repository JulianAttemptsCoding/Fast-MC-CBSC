"""Span/gap and autoregressive longitudinal activity modes."""

from __future__ import annotations

import torch

from cbsc_zdc.models.activity import (
    COMPACT_FRACTION_THRESHOLD,
    AutoregressiveActivityHead,
    SpanGapActivityHead,
    activity_statistics,
    span_and_gaps,
    transition_matrix,
)

COND, LAYERS = 8, 12


def cond(n: int = 16) -> torch.Tensor:
    g = torch.Generator().manual_seed(2)
    return torch.randn(n, COND, generator=g, dtype=torch.float64)


def row(*active: int) -> torch.Tensor:
    r = torch.zeros(LAYERS, dtype=torch.bool)
    for i in active:
        r[i] = True
    return r


def test_compact_fraction_definition_matches_hand_fixture() -> None:
    # contiguous 2..5: no gaps
    assert span_and_gaps(row(2, 3, 4, 5)) == (2, 5, 0, 0)
    # one interior hole of length 1
    assert span_and_gaps(row(2, 3, 5, 6)) == (2, 6, 1, 1)
    # two separate holes, longest 2
    assert span_and_gaps(row(1, 4, 5, 8)) == (1, 8, 2, 2)
    # single hit
    assert span_and_gaps(row(3)) == (3, 3, 0, 0)
    # empty
    assert span_and_gaps(row()) == (-1, -1, 0, 0)


def test_compact_rule_selects_span_at_or_above_0_99() -> None:
    compact = torch.stack([row(1, 2, 3) for _ in range(99)] + [row(0, 4, 8)])
    stats = activity_statistics(compact)
    assert stats.compact_fraction >= COMPACT_FRACTION_THRESHOLD
    assert stats.selected_mode == "span_gaps"

    # a fifth of showers with long ragged gaps must select the general model
    ragged = torch.stack([row(1, 2, 3) for _ in range(80)] + [row(0, 5, 11) for _ in range(20)])
    stats = activity_statistics(ragged)
    assert stats.compact_fraction < COMPACT_FRACTION_THRESHOLD
    assert stats.selected_mode == "autoregressive"


def test_statistics_use_visible_events_only() -> None:
    active = torch.stack([row(1, 2, 3), row(0, 5, 11)])
    visible = torch.tensor([True, False])
    stats = activity_statistics(active, visible)
    assert stats.n_visible == 1
    assert stats.compact_fraction == 1.0


def test_span_mode_enforces_first_and_last_active() -> None:
    torch.manual_seed(0)
    head = SpanGapActivityHead(COND, LAYERS, 32).to(torch.float64)
    c = cond(64)
    first = torch.full((64,), 3, dtype=torch.long)
    active = head.sample(c, torch.full((64,), 5.0, dtype=torch.float64), first, torch.ones(64, dtype=torch.bool))
    assert active[:, 3].all()  # f is always active
    for r in active:
        idx = torch.nonzero(r).flatten()
        assert int(idx[0]) == 3
        # the last active layer is an endpoint and therefore never dropped
        assert r[int(idx[-1])]


def test_span_mode_masks_outside_span() -> None:
    torch.manual_seed(1)
    head = SpanGapActivityHead(COND, LAYERS, 32).to(torch.float64)
    c = cond(64)
    first = torch.full((64,), 5, dtype=torch.long)
    active = head.sample(c, torch.full((64,), 5.0, dtype=torch.float64), first, torch.ones(64, dtype=torch.bool))
    assert not active[:, :5].any()  # nothing before f


def test_ar_mode_masks_before_first_and_forces_first() -> None:
    torch.manual_seed(2)
    head = AutoregressiveActivityHead(COND, LAYERS, 16).to(torch.float64)
    c = cond(64)
    first = torch.full((64,), 4, dtype=torch.long)
    active = head.sample(c, torch.full((64,), 5.0, dtype=torch.float64), first, torch.ones(64, dtype=torch.bool))
    assert not active[:, :4].any()
    assert active[:, 4].all()


def test_invisible_event_has_no_active_layers() -> None:
    torch.manual_seed(3)
    c = cond(32)
    total = torch.zeros(32, dtype=torch.float64)
    first = torch.zeros(32, dtype=torch.long)
    invisible = torch.zeros(32, dtype=torch.bool)
    for head in (
        SpanGapActivityHead(COND, LAYERS, 32).to(torch.float64),
        AutoregressiveActivityHead(COND, LAYERS, 16).to(torch.float64),
    ):
        assert not head.sample(c, total, first, invisible).any()


def test_ar_teacher_forcing_and_free_running_use_declared_previous_token() -> None:
    torch.manual_seed(4)
    head = AutoregressiveActivityHead(COND, LAYERS, 16).to(torch.float64)
    c = cond(8)
    total = torch.full((8,), 5.0, dtype=torch.float64)
    first = torch.zeros(8, dtype=torch.long)
    truth_a = torch.stack([row(0, 1, 2) for _ in range(8)])
    truth_b = torch.stack([row(0, 5, 9) for _ in range(8)])
    # Teacher forcing must actually feed the truth: different truth sequences
    # give different logits even with identical conditions.
    la = head.logits_teacher_forced(c, total, first, truth_a)
    lb = head.logits_teacher_forced(c, total, first, truth_b)
    assert not torch.allclose(la, lb)


def test_ar_loss_and_gradients_are_finite() -> None:
    torch.manual_seed(5)
    head = AutoregressiveActivityHead(COND, LAYERS, 16).to(torch.float64)
    c = cond(8)
    truth = torch.stack([row(1, 2, 3) for _ in range(8)])
    loss = head.loss(c, torch.full((8,), 5.0, dtype=torch.float64), torch.ones(8, dtype=torch.long), truth, torch.ones(8, dtype=torch.bool))
    assert torch.isfinite(loss)
    loss.backward()
    assert all(torch.isfinite(p.grad).all() for p in head.parameters() if p.grad is not None)


def test_span_losses_are_finite_and_backpropagate() -> None:
    torch.manual_seed(6)
    head = SpanGapActivityHead(COND, LAYERS, 32).to(torch.float64)
    c = cond(8)
    truth = torch.stack([row(1, 2, 4, 5) for _ in range(8)])
    last, gap = head.losses(
        c, torch.full((8,), 5.0, dtype=torch.float64), torch.ones(8, dtype=torch.long),
        truth, torch.ones(8, dtype=torch.bool),
    )
    assert torch.isfinite(last) and torch.isfinite(gap)
    (last + gap).backward()
    assert all(torch.isfinite(p.grad).all() for p in head.parameters() if p.grad is not None)


def test_transition_matrix_matches_hand_count() -> None:
    active = torch.tensor([[True, True, False, False]])
    m = transition_matrix(active)
    assert int(m[1, 1]) == 1  # T->T
    assert int(m[1, 0]) == 1  # T->F
    assert int(m[0, 0]) == 1  # F->F
    assert int(m[0, 1]) == 0
