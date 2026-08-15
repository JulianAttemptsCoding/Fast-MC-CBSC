from __future__ import annotations

from dataclasses import dataclass
import torch
from torch import nn


@dataclass
class ResponseDistribution:
    visible_logits: torch.Tensor
    mixture_logits: torch.Tensor
    loc: torch.Tensor
    scale: torch.Tensor


class ResponseHead(nn.Module):
    """Zero-inflated response mixture with NLL reported in deposited-energy GeV.

    The mixture is parameterized in ``y = log1p(T / response_scale_gev)`` for
    numerical convenience.  Its likelihood is converted back to a density in
    ``T`` before reduction, so it is dimensionally comparable with the bounded
    spline response head.  The target-only Jacobian changes reported loss
    values but has no model-parameter gradient.
    """
    def __init__(self,cond_dim:int=128,hidden:int=192,components:int=4,response_scale_gev:float=10.0):
        super().__init__(); self.components=components; self.response_scale_gev=float(response_scale_gev)
        self.visible=nn.Sequential(nn.Linear(cond_dim,hidden),nn.SiLU(),nn.Linear(hidden,1))
        self.mixture=nn.Sequential(nn.Linear(cond_dim,hidden),nn.SiLU(),nn.Linear(hidden,hidden),nn.SiLU(),nn.Linear(hidden,components*3))
    def distribution(self,cond)->ResponseDistribution:
        raw=self.mixture(cond); logits,loc,raw_scale=raw.chunk(3,dim=-1)
        return ResponseDistribution(self.visible(cond),logits,loc,torch.nn.functional.softplus(raw_scale)+0.05)
    def nll(self,cond,total_gev,visible_truth):
        dist=self.distribution(cond); visible=visible_truth.to(cond.dtype)
        bce=torch.nn.functional.binary_cross_entropy_with_logits(dist.visible_logits.squeeze(-1),visible,reduction='mean')
        mask=visible_truth.bool()
        if not mask.any(): return bce,cond.new_zeros(())
        y=torch.log1p(total_gev[mask]/self.response_scale_gev)
        normal=torch.distributions.Normal(dist.loc[mask],dist.scale[mask])
        log_prob_y=torch.log_softmax(dist.mixture_logits[mask],dim=-1)+normal.log_prob(y[:,None])
        nll_y=-torch.logsumexp(log_prob_y,dim=-1)
        # dy/dT = 1 / (response_scale_gev + T), hence
        # -log p(T) = -log p(y) + log(response_scale_gev + T).
        # Do not omit this term: without it v2 and spline response losses are
        # expressed against different base measures and their totals cannot be
        # compared.  It depends only on the frozen target, so gradients and the
        # selected epoch within a fixed run are unchanged.
        nll_gev=nll_y+torch.log(total_gev[mask]+self.response_scale_gev)
        return bce,nll_gev.mean()
    @torch.no_grad()
    def sample(self,cond,kinetic_gev,cap_ratio:float,cap_absolute_gev:float,stochastic:bool=True):
        dist=self.distribution(cond)
        if stochastic:
            visible=torch.bernoulli(torch.sigmoid(dist.visible_logits)).bool().squeeze(-1)
            component=torch.distributions.Categorical(logits=dist.mixture_logits).sample()
            chosen_loc=dist.loc.gather(1,component[:,None]).squeeze(1); chosen_scale=dist.scale.gather(1,component[:,None]).squeeze(1)
            y=chosen_loc+chosen_scale*torch.randn_like(chosen_loc)
        else:
            visible=(dist.visible_logits.squeeze(-1)>0); component=dist.mixture_logits.argmax(dim=-1)
            y=dist.loc.gather(1,component[:,None]).squeeze(1)
        total=torch.expm1(y).clamp_min(0)*self.response_scale_gev
        cap=torch.minimum(torch.full_like(total,float(cap_absolute_gev)),float(cap_ratio)*kinetic_gev.clamp_min(1.0))
        total=torch.minimum(total,cap)
        # A sampled continuous component can land below zero and be clamped to
        # exactly zero.  Such an event belongs to the no-response atom; keeping
        # V=True would make downstream active layers request positive counts for
        # a zero budget.
        visible=visible & (kinetic_gev>0) & (total>0)
        return visible,total*visible.to(total.dtype)
