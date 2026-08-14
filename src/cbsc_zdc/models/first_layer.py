"""Hierarchical first-active-layer head.

v2.2 predicts the first active layer with one flat 65-way categorical.  Layer 0
(an ECAL start) is rare, so a flat softmax underproduces it by roughly two
orders of magnitude in the cited diagnostics -- the rare class is simply not
worth any probability mass to a flat cross-entropy.

v3 factorizes the decision:

    p_E = sigmoid(g_E([c, log1p(T)]))        # does the shower start in ECAL?
    Z_E ~ Bernoulli(p_E)
    if Z_E = 1:  f = 0
    else:        f ~ Categorical(g_H([c, log1p(T)])) over {1, ..., 64}
    if V = 0:    f = -1 and no layer may be activated

giving the rare branch its own calibrated Bernoulli instead of making it compete
inside a 65-way softmax.

Losses stay unweighted in the first experiment.  Focal or class weighting is
deliberately *not* applied: prevalence and calibration are the physical targets,
and reweighting would trade calibration for recall before we have measured
whether the factorization alone fixes the prevalence.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import nn
from torch.nn import functional as F


@dataclass
class FirstLayerOutput:
    first_layer: torch.Tensor  # [B] long, -1 when invisible
    ecal_start: torch.Tensor  # [B] bool
    ecal_logits: torch.Tensor  # [B]
    hcal_logits: torch.Tensor  # [B, n_layers-1]


class HierarchicalFirstLayerHead(nn.Module):
    def __init__(self, cond_dim: int = 128, n_layers: int = 65, hidden: int = 128) -> None:
        super().__init__()
        self.n_layers = int(n_layers)
        self.ecal = nn.Sequential(
            nn.Linear(cond_dim + 1, hidden), nn.SiLU(), nn.Linear(hidden, 1)
        )
        self.hcal = nn.Sequential(
            nn.Linear(cond_dim + 1, hidden), nn.SiLU(), nn.Linear(hidden, self.n_layers - 1)
        )

    def _features(self, cond: torch.Tensor, total: torch.Tensor) -> torch.Tensor:
        return torch.cat([cond, torch.log1p(total.clamp_min(0))[:, None].to(cond.dtype)], dim=-1)

    def logits(self, cond: torch.Tensor, total: torch.Tensor):
        x = self._features(cond, total)
        return self.ecal(x).squeeze(-1), self.hcal(x)

    def losses(
        self,
        cond: torch.Tensor,
        total: torch.Tensor,
        first_truth: torch.Tensor,
        visible_truth: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Return ``(ecal_start_bce, hcal_first_ce)``.

        The ECAL term uses visible events only.  The HCAL term uses visible
        non-ECAL events only -- including an ECAL start there would ask the
        categorical to explain a layer it structurally cannot emit.
        """
        ecal_logits, hcal_logits = self.logits(cond, total)
        visible = visible_truth.bool()
        if not visible.any():
            zero = cond.new_zeros(())
            return zero, zero
        is_ecal = (first_truth == 0) & visible
        ecal_bce = F.binary_cross_entropy_with_logits(
            ecal_logits[visible], is_ecal[visible].to(cond.dtype), reduction="mean"
        )
        hcal_mask = visible & (first_truth > 0)
        if not hcal_mask.any():
            return ecal_bce, cond.new_zeros(())
        hcal_ce = F.cross_entropy(
            hcal_logits[hcal_mask], (first_truth[hcal_mask] - 1).long(), reduction="mean"
        )
        return ecal_bce, hcal_ce

    @torch.no_grad()
    def sample(
        self, cond: torch.Tensor, total: torch.Tensor, visible: torch.Tensor,
        stochastic: bool = True,
    ) -> FirstLayerOutput:
        ecal_logits, hcal_logits = self.logits(cond, total)
        if stochastic:
            ecal_start = torch.bernoulli(torch.sigmoid(ecal_logits)).bool()
            hcal_choice = torch.distributions.Categorical(logits=hcal_logits).sample()
        else:
            ecal_start = ecal_logits > 0
            hcal_choice = hcal_logits.argmax(dim=-1)
        first = torch.where(ecal_start, torch.zeros_like(hcal_choice), hcal_choice + 1)
        visible_bool = visible.bool()
        # An invisible event has no first layer at all, and neither branch is
        # permitted to activate one.
        first = torch.where(visible_bool, first, torch.full_like(first, -1))
        ecal_start = ecal_start & visible_bool
        return FirstLayerOutput(first.long(), ecal_start, ecal_logits, hcal_logits)


def ecal_start_diagnostics(
    ecal_logits: torch.Tensor, first_truth: torch.Tensor, visible_truth: torch.Tensor,
    *, reliability_bins: int = 10,
) -> dict[str, object]:
    """Prevalence, Brier score, reliability bins and precision/recall.

    Prevalence and calibration are the physical targets; recall alone is not, so
    all four are reported together.
    """
    visible = visible_truth.bool()
    if not visible.any():
        return {"visible_events": 0}
    probs = torch.sigmoid(ecal_logits[visible]).double()
    truth = ((first_truth == 0) & visible)[visible].double()
    predicted = probs >= 0.5
    true_positive = float((predicted & truth.bool()).sum())
    predicted_positive = float(predicted.sum())
    actual_positive = float(truth.sum())
    bins = []
    for index in range(reliability_bins):
        low = index / reliability_bins
        high = (index + 1) / reliability_bins
        inside = (probs >= low) & (probs < high if index + 1 < reliability_bins else probs <= high)
        count = int(inside.sum())
        bins.append({
            "bin": [low, high],
            "count": count,
            "mean_predicted": float(probs[inside].mean()) if count else None,
            "observed_frequency": float(truth[inside].mean()) if count else None,
        })
    return {
        "visible_events": int(visible.sum()),
        "truth_prevalence": float(truth.mean()),
        "predicted_prevalence": float(probs.mean()),
        "brier_score": float(((probs - truth) ** 2).mean()),
        "precision": (true_positive / predicted_positive) if predicted_positive else None,
        "recall": (true_positive / actual_positive) if actual_positive else None,
        "reliability_bins": bins,
    }
