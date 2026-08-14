"""v3 bounded response head: one and only one zero atom.

The v2.2 head samples a continuous variable, exponentiates it, and clamps at
zero.  A draw landing below zero therefore produces an exact zero *after* the
visibility hurdle already said the event was visible, so the sampler had to
clear ``V`` afterwards.  That created a second, unintended zero atom whose mass
was a function of the mixture tail rather than of the learned visibility
probability -- and Fast-MC emits roughly twice as many zero-response events as
Geant4.

v3 removes that path entirely:

* ``V ~ Bernoulli(sigmoid(o_V(c)))`` is the *only* source of zeros.
* If ``V = 1`` the response is ``T = C(K) * S_theta(u_0; c)`` with
  ``u_0 ~ Uniform(eps, 1-eps)`` and ``S_theta`` a monotone spline onto ``(0,1)``.
  Both factors are strictly positive, so ``0 < T < C(K)`` by construction with
  no clamp anywhere.
* Sampling never re-examines ``V``.

The negative log-likelihood of a visible response is

    L_response = -log|d S_theta^{-1}(r_T) / d r_T| + log C(K),   r_T = T / C(K)

because the base density is uniform on ``(0,1)`` and the change of variables
from ``r_T`` to ``T`` contributes ``log C(K)``.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import nn
from torch.nn import functional as F

from .splines import ConditionalRationalQuadraticSpline

BASE_EPSILON = 1e-6


@dataclass
class ResponseV3Output:
    visible: torch.Tensor
    total_response: torch.Tensor


class BoundedResponseHead(nn.Module):
    """Hurdle visibility plus a bounded conditional spline for the positive branch."""

    def __init__(
        self,
        cond_dim: int = 128,
        hidden: int = 192,
        bins: int = 16,
        epsilon: float = BASE_EPSILON,
    ) -> None:
        super().__init__()
        self.epsilon = float(epsilon)
        self.visible = nn.Sequential(
            nn.Linear(cond_dim, hidden), nn.SiLU(), nn.Linear(hidden, 1)
        )
        self.spline = ConditionalRationalQuadraticSpline(cond_dim, hidden, bins)

    def visibility_logits(self, cond: torch.Tensor) -> torch.Tensor:
        return self.visible(cond).squeeze(-1)

    def nll(
        self,
        cond: torch.Tensor,
        total_gev: torch.Tensor,
        visible_truth: torch.Tensor,
        cap_gev: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Return ``(visibility_bce, positive_response_nll)``.

        The two remain distinct logged losses; they are never summed here.
        """
        logits = self.visibility_logits(cond)
        bce = F.binary_cross_entropy_with_logits(
            logits, visible_truth.to(cond.dtype), reduction="mean"
        )
        mask = visible_truth.bool()
        if not mask.any():
            return bce, cond.new_zeros(())

        cap = cap_gev[mask].to(cond.dtype)
        target = total_gev[mask].to(cond.dtype)
        ratio = target / cap
        # No clamp: an out-of-support training target is a fatal contract error,
        # not something to squeeze into range.
        if not bool(((ratio > 0.0) & (ratio < 1.0)).all()):
            worst = ratio.detach()
            raise ValueError(
                "a visible training response is outside its train-built envelope "
                f"(min ratio {worst.min().item():.6g}, max ratio {worst.max().item():.6g}); "
                "rebuild the envelope rather than clamping the target"
            )
        _, logabsdet = self.spline(ratio, cond[mask], inverse=True)
        # logabsdet here is d(base)/d(ratio); the density of ratio is its
        # exponential, and dividing by cap moves it to the density of T.
        nll = -(logabsdet - torch.log(cap))
        return bce, nll.mean()

    @torch.no_grad()
    def sample(
        self, cond: torch.Tensor, cap_gev: torch.Tensor, stochastic: bool = True
    ) -> ResponseV3Output:
        logits = self.visibility_logits(cond)
        if stochastic:
            visible = torch.bernoulli(torch.sigmoid(logits)).bool()
            base = torch.rand_like(logits).clamp(self.epsilon, 1.0 - self.epsilon)
        else:
            visible = logits > 0
            base = torch.full_like(logits, 0.5)
        ratio, _ = self.spline(base, cond, inverse=False)
        total = ratio.to(cap_gev.dtype) * cap_gev
        # Visibility is decided once, by the hurdle. The positive branch is
        # strictly inside (0, cap) and can never clear it.
        total = torch.where(visible, total, torch.zeros_like(total))
        return ResponseV3Output(visible, total)
