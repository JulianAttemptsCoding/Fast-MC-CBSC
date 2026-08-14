"""Autoregressive per-layer positive-cell count head.

v2.2 predicts every layer's count independently, so realized counts carry no
longitudinal correlation.  v3 conditions layer ``l`` on the previous layer's
count through a GRU.

Every feasibility mask from v2.2 is retained exactly:

* an inactive layer may only take ``k = 0``;
* an active layer in raw-deposit mode takes ``1 <= k <= M_l`` where ``M_l`` is
  that layer's channel count;
* in thresholded mode it additionally satisfies ``k * tau <= D_l``.

The inactive-layer loss weight stays at 0.2 for the first matched comparison so
the only difference against the v2.2 control is the autoregression itself.
"""

from __future__ import annotations

import torch
from torch import nn
from torch.nn import functional as F

INACTIVE_LOSS_WEIGHT = 0.2


class AutoregressiveCountHead(nn.Module):
    def __init__(
        self, cond_dim: int, n_layers: int, max_counts: list[int], hidden: int = 192
    ) -> None:
        super().__init__()
        self.n_layers = int(n_layers)
        self.hidden = int(hidden)
        self.register_buffer("max_counts", torch.tensor(max_counts, dtype=torch.long))
        self.max_global = int(max(max_counts))
        self.layer_embedding = nn.Embedding(self.n_layers, 24)
        self.cell = nn.GRUCell(cond_dim + 1 + 1 + 24 + 1, self.hidden)
        self.out = nn.Linear(self.hidden, self.max_global + 1)

    def _step_input(self, cond, layer_energy, active, layer, previous_fraction):
        b = cond.shape[0]
        ids = torch.full((b,), layer, device=cond.device, dtype=torch.long)
        return torch.cat(
            [
                cond,
                torch.log1p(layer_energy[:, layer].clamp_min(0))[:, None].to(cond.dtype),
                active[:, layer][:, None].to(cond.dtype),
                self.layer_embedding(ids),
                previous_fraction[:, None].to(cond.dtype),
            ],
            dim=-1,
        )

    def _feasible(self, layer_energy, active, layer, threshold_gev: float):
        b = layer_energy.shape[0]
        classes = torch.arange(self.max_global + 1, device=layer_energy.device)[None]
        feasible = classes <= self.max_counts[layer]
        feasible = feasible.expand(b, -1).clone()
        if threshold_gev > 0:
            budget = torch.floor(layer_energy[:, layer] / threshold_gev).long()[:, None]
            feasible &= classes <= budget
        is_active = active[:, layer][:, None]
        feasible &= torch.where(is_active, classes > 0, classes == 0)
        return feasible

    def logits_teacher_forced(
        self, cond, layer_energy, active, count_truth, threshold_gev: float = 0.0
    ):
        b = cond.shape[0]
        h = cond.new_zeros(b, self.hidden)
        previous = cond.new_zeros(b)
        out = []
        for layer in range(self.n_layers):
            h = self.cell(self._step_input(cond, layer_energy, active, layer, previous), h)
            logits = self.out(h)
            feasible = self._feasible(layer_energy, active, layer, threshold_gev)
            out.append(logits.masked_fill(~feasible, torch.finfo(logits.dtype).min))
            denominator = self.max_counts[layer].clamp_min(1).to(cond.dtype)
            previous = count_truth[:, layer].to(cond.dtype) / denominator  # teacher forcing
        return torch.stack(out, dim=1)

    def loss(self, cond, layer_energy, active, count_truth, threshold_gev: float = 0.0):
        logits = self.logits_teacher_forced(
            cond, layer_energy, active, count_truth, threshold_gev
        )
        b, l, _ = logits.shape
        flat = logits.reshape(b * l, -1)
        target = count_truth.reshape(b * l).long()
        per_item = F.cross_entropy(flat, target, reduction="none")
        weight = torch.where(
            active.reshape(b * l).bool(),
            torch.ones_like(per_item),
            torch.full_like(per_item, INACTIVE_LOSS_WEIGHT),
        )
        return (per_item * weight).sum() / weight.sum().clamp_min(1e-12)

    @torch.no_grad()
    def sample(self, cond, layer_energy, active, threshold_gev: float = 0.0, stochastic: bool = True):
        b = cond.shape[0]
        h = cond.new_zeros(b, self.hidden)
        previous = cond.new_zeros(b)
        counts = torch.zeros(b, self.n_layers, dtype=torch.long, device=cond.device)
        all_logits = []
        for layer in range(self.n_layers):
            h = self.cell(self._step_input(cond, layer_energy, active, layer, previous), h)
            logits = self.out(h)
            feasible = self._feasible(layer_energy, active, layer, threshold_gev)
            logits = logits.masked_fill(~feasible, torch.finfo(logits.dtype).min)
            drawn = (
                torch.distributions.Categorical(logits=logits).sample()
                if stochastic
                else logits.argmax(dim=-1)
            )
            counts[:, layer] = drawn
            all_logits.append(logits)
            denominator = self.max_counts[layer].clamp_min(1).to(cond.dtype)
            previous = drawn.to(cond.dtype) / denominator  # sampled feedback
        return counts, torch.stack(all_logits, dim=1)
