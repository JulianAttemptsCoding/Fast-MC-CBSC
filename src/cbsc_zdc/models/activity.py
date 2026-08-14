"""Longitudinal layer activity: span-plus-gaps and autoregressive modes.

v2.2 samples each layer's activity independently given the condition, which
cannot represent longitudinal dependence: a shower is a contiguous object, and
independent Bernoullis produce implausible interior holes.

Two replacements are implemented so the unselected one remains a matched
ablation:

``span_gaps``
    Predict the last active layer ``q`` over ``{f..64}``, then predict interior
    gaps.  ``A_l = 1[f <= l <= q] * (1 - G_l)`` with ``G_f = G_q = 0``.  Cheap
    and exactly right when showers are near-contiguous.

``autoregressive``
    A GRU over 65 layer tokens conditioned on the previous layer's activity.
    Strictly more general, and the honest choice when interior gaps are common.

The choice is made by a **predeclared train-only statistic**, never by looking
at test data and never by whichever scores better downstream::

    compact_fraction = fraction of visible showers with
                       gap_count <= 2 and max_gap_length <= 2

``compact_fraction >= 0.99`` selects ``span_gaps``; otherwise ``autoregressive``.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import nn
from torch.nn import functional as F

COMPACT_FRACTION_THRESHOLD = 0.99
MAX_GAP_COUNT = 2
MAX_GAP_LENGTH = 2


@dataclass
class ActivityStatistics:
    compact_fraction: float
    gap_counts: list[int]
    max_gap_lengths: list[int]
    selected_mode: str
    n_visible: int


def span_and_gaps(active_row: torch.Tensor) -> tuple[int, int, int, int]:
    """Return ``(first, last, gap_count, max_gap_length)`` for one shower.

    A gap is an inactive layer strictly inside ``[first, last]``.  An invisible
    or empty shower returns ``(-1, -1, 0, 0)``.
    """
    idx = torch.nonzero(active_row.bool(), as_tuple=False).flatten()
    if idx.numel() == 0:
        return -1, -1, 0, 0
    first, last = int(idx[0]), int(idx[-1])
    interior = active_row[first : last + 1].bool()
    gap_count = 0
    max_run = 0
    run = 0
    for value in interior.tolist():
        if value:
            if run:
                gap_count += 1
                max_run = max(max_run, run)
                run = 0
        else:
            run += 1
    if run:  # cannot happen because `last` is active, but keeps the loop total
        gap_count += 1
        max_run = max(max_run, run)
    return first, last, gap_count, max_run


def activity_statistics(
    active: torch.Tensor, visible: torch.Tensor | None = None
) -> ActivityStatistics:
    """Compute the frozen selection statistic over a truth batch."""
    rows = active.bool()
    if visible is not None:
        rows = rows[visible.bool()]
    gap_counts: list[int] = []
    max_gap_lengths: list[int] = []
    compact = 0
    for row in rows:
        _, _, gaps, longest = span_and_gaps(row)
        gap_counts.append(gaps)
        max_gap_lengths.append(longest)
        if gaps <= MAX_GAP_COUNT and longest <= MAX_GAP_LENGTH:
            compact += 1
    n = len(gap_counts)
    fraction = (compact / n) if n else 1.0
    mode = "span_gaps" if fraction >= COMPACT_FRACTION_THRESHOLD else "autoregressive"
    return ActivityStatistics(fraction, gap_counts, max_gap_lengths, mode, n)


class SpanGapActivityHead(nn.Module):
    """Last-active-layer categorical plus interior gap Bernoullis."""

    def __init__(self, cond_dim: int = 128, n_layers: int = 65, hidden: int = 128) -> None:
        super().__init__()
        self.n_layers = int(n_layers)
        self.first_embedding = nn.Embedding(self.n_layers, 24)
        self.layer_embedding = nn.Embedding(self.n_layers, 24)
        self.last = nn.Sequential(
            nn.Linear(cond_dim + 1 + 24, hidden), nn.SiLU(), nn.Linear(hidden, self.n_layers)
        )
        self.gap = nn.Sequential(
            nn.Linear(cond_dim + 1 + 24 + 24 + 24, hidden), nn.SiLU(), nn.Linear(hidden, 1)
        )

    def last_logits(self, cond, total, first):
        x = torch.cat(
            [cond, torch.log1p(total.clamp_min(0))[:, None].to(cond.dtype),
             self.first_embedding(first.clamp_min(0))],
            dim=-1,
        )
        logits = self.last(x)
        # q >= f is the only feasible region.
        ids = torch.arange(self.n_layers, device=cond.device)[None]
        return logits.masked_fill(ids < first.clamp_min(0)[:, None], torch.finfo(logits.dtype).min)

    def gap_logits(self, cond, total, first, last):
        b = cond.shape[0]
        ids = torch.arange(self.n_layers, device=cond.device)
        x = torch.cat(
            [
                cond[:, None].expand(-1, self.n_layers, -1),
                torch.log1p(total.clamp_min(0))[:, None, None].expand(-1, self.n_layers, 1).to(cond.dtype),
                self.first_embedding(first.clamp_min(0))[:, None].expand(-1, self.n_layers, -1),
                self.first_embedding(last.clamp_min(0))[:, None].expand(-1, self.n_layers, -1),
                self.layer_embedding(ids)[None].expand(b, -1, -1),
            ],
            dim=-1,
        )
        return self.gap(x).squeeze(-1)

    def losses(self, cond, total, first_truth, active_truth, visible_truth):
        visible = visible_truth.bool()
        if not visible.any():
            zero = cond.new_zeros(())
            return zero, zero
        last_truth = torch.stack(
            [torch.tensor(span_and_gaps(row)[1], device=cond.device) for row in active_truth]
        ).long()
        valid = visible & (last_truth >= 0) & (first_truth >= 0)
        if not valid.any():
            zero = cond.new_zeros(())
            return zero, zero
        last_ce = F.cross_entropy(
            self.last_logits(cond, total, first_truth)[valid], last_truth[valid], reduction="mean"
        )
        logits = self.gap_logits(cond, total, first_truth, last_truth)
        ids = torch.arange(self.n_layers, device=cond.device)[None]
        # interior positions only: strictly between f and q
        interior = (ids > first_truth[:, None]) & (ids < last_truth[:, None]) & valid[:, None]
        if not interior.any():
            return last_ce, cond.new_zeros(())
        gap_truth = (~active_truth.bool()).to(cond.dtype)
        gap_bce = F.binary_cross_entropy_with_logits(
            logits[interior], gap_truth[interior], reduction="mean"
        )
        return last_ce, gap_bce

    @torch.no_grad()
    def sample(self, cond, total, first, visible, stochastic: bool = True):
        logits = self.last_logits(cond, total, first)
        last = (
            torch.distributions.Categorical(logits=logits).sample()
            if stochastic
            else logits.argmax(dim=-1)
        )
        last = torch.maximum(last, first.clamp_min(0))
        gap = self.gap_logits(cond, total, first, last)
        drop = (
            torch.bernoulli(torch.sigmoid(gap)).bool()
            if stochastic
            else torch.sigmoid(gap) > 0.5
        )
        ids = torch.arange(self.n_layers, device=cond.device)[None]
        inside = (ids >= first.clamp_min(0)[:, None]) & (ids <= last[:, None])
        # G_f = G_q = 0: the endpoints of the span are active by definition.
        endpoint = (ids == first.clamp_min(0)[:, None]) | (ids == last[:, None])
        active = inside & (~drop | endpoint)
        active &= visible.bool()[:, None]
        return active


class AutoregressiveActivityHead(nn.Module):
    """One-layer GRU over 65 layer tokens."""

    def __init__(self, cond_dim: int = 128, n_layers: int = 65, hidden: int = 128) -> None:
        super().__init__()
        self.n_layers = int(n_layers)
        self.hidden = int(hidden)
        self.first_embedding = nn.Embedding(self.n_layers, 24)
        self.layer_embedding = nn.Embedding(self.n_layers, 24)
        self.cell = nn.GRUCell(cond_dim + 1 + 24 + 24 + 1, self.hidden)
        self.out = nn.Linear(self.hidden, 1)

    def _step_input(self, cond, total, first, layer, previous):
        b = cond.shape[0]
        ids = torch.full((b,), layer, device=cond.device, dtype=torch.long)
        return torch.cat(
            [
                cond,
                torch.log1p(total.clamp_min(0))[:, None].to(cond.dtype),
                self.first_embedding(first.clamp_min(0)),
                self.layer_embedding(ids),
                previous[:, None].to(cond.dtype),
            ],
            dim=-1,
        )

    def logits_teacher_forced(self, cond, total, first, active_truth):
        b = cond.shape[0]
        h = cond.new_zeros(b, self.hidden)
        previous = cond.new_zeros(b)
        out = []
        for layer in range(self.n_layers):
            h = self.cell(self._step_input(cond, total, first, layer, previous), h)
            out.append(self.out(h).squeeze(-1))
            previous = active_truth[:, layer].to(cond.dtype)  # teacher forcing
        return torch.stack(out, dim=1)

    def loss(self, cond, total, first_truth, active_truth, visible_truth):
        visible = visible_truth.bool()
        if not visible.any():
            return cond.new_zeros(())
        logits = self.logits_teacher_forced(cond, total, first_truth, active_truth)
        ids = torch.arange(self.n_layers, device=cond.device)[None]
        feasible = (ids >= first_truth.clamp_min(0)[:, None]) & visible[:, None]
        if not feasible.any():
            return cond.new_zeros(())
        return F.binary_cross_entropy_with_logits(
            logits[feasible], active_truth.to(cond.dtype)[feasible], reduction="mean"
        )

    @torch.no_grad()
    def sample(self, cond, total, first, visible, stochastic: bool = True):
        b = cond.shape[0]
        h = cond.new_zeros(b, self.hidden)
        previous = cond.new_zeros(b)
        active = torch.zeros(b, self.n_layers, dtype=torch.bool, device=cond.device)
        first_clamped = first.clamp_min(0)
        for layer in range(self.n_layers):
            h = self.cell(self._step_input(cond, total, first_clamped, layer, previous), h)
            logit = self.out(h).squeeze(-1)
            draw = (
                torch.bernoulli(torch.sigmoid(logit)).bool()
                if stochastic
                else torch.sigmoid(logit) > 0.5
            )
            before_first = layer < first_clamped
            at_first = layer == first_clamped
            step = torch.where(at_first, torch.ones_like(draw), draw)
            step = torch.where(before_first, torch.zeros_like(step), step)
            step &= visible.bool()
            active[:, layer] = step
            previous = step.to(cond.dtype)  # free-running feedback
        return active


def transition_matrix(active: torch.Tensor) -> torch.Tensor:
    """Adjacent-layer activity transition counts, shape ``[2,2]``."""
    rows = active.bool()
    previous = rows[:, :-1].reshape(-1).long()
    following = rows[:, 1:].reshape(-1).long()
    matrix = torch.zeros(2, 2, dtype=torch.long)
    for a in (0, 1):
        for b in (0, 1):
            matrix[a, b] = int(((previous == a) & (following == b)).sum())
    return matrix
