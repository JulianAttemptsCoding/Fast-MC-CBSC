from __future__ import annotations

from dataclasses import dataclass
import math
import torch


@dataclass
class DecodeOutput:
    cell_energy: torch.Tensor
    support_mask: torch.Tensor
    realized_counts: torch.Tensor
    layer_closure_error: torch.Tensor


SUPPORT_TEMPERATURE_DEFAULT = 1.0


def exact_k_mask(logits:torch.Tensor,k:torch.Tensor,stochastic:bool=True,temperature:float=SUPPORT_TEMPERATURE_DEFAULT)->torch.Tensor:
    """Select exactly ``k`` channels per row by perturbed top-k.

    ``temperature`` divides the logits before the Gumbel noise is added, so a
    lower value lets the learned logits dominate the draw and a higher value
    lets the noise dominate.  It is a frozen sampling constant, not a learned
    parameter, and it cannot change the deterministic ordering: with
    ``stochastic=False`` a positive scale leaves the argsort untouched.

    The forward output is an exact hard boolean mask.  No relaxation is
    introduced here; a structured estimator is a separate, triggered piece of
    work (D3) with its own estimator QA.
    """
    b,n=logits.shape
    if k.shape!=(b,): raise ValueError('k shape mismatch')
    if (k<0).any() or (k>n).any(): raise ValueError('infeasible k')
    temperature=float(temperature)
    if not math.isfinite(temperature) or temperature<=0:
        raise ValueError(f'support temperature must be finite and strictly positive, got {temperature!r}')
    scores=logits/temperature
    if stochastic:
        u=torch.rand_like(logits).clamp_(1e-7,1-1e-7); scores=scores-torch.log(-torch.log(u))
    order=scores.argsort(dim=-1,descending=True); rank=torch.empty_like(order); rank.scatter_(1,order,torch.arange(n,device=logits.device)[None].expand(b,-1))
    return rank<k[:,None]


def decode_exact_support(support_logits,share_logits,layer_budget,requested_counts,layer_index,valid_mask,threshold_gev:float=0.0,stochastic_support:bool=True,tolerance:float=2e-5,preselected_support_mask:torch.Tensor|None=None):
    b,n=support_logits.shape; l=layer_budget.shape[1]
    if preselected_support_mask is not None:
        if preselected_support_mask.shape != support_logits.shape:
            raise ValueError('preselected support shape mismatch')
        if (preselected_support_mask & (~valid_mask[None])).any():
            raise ValueError('preselected support contains an invalid node')
    cell=torch.zeros_like(share_logits); support=torch.zeros_like(support_logits,dtype=torch.bool); realized=torch.zeros_like(requested_counts)
    closure=[]
    for layer in range(l):
        ids=torch.where((layer_index==layer)&valid_mask)[0]; k=requested_counts[:,layer].long(); budget=layer_budget[:,layer]
        if ids.numel()==0:
            if (k!=0).any() or (budget.abs()>tolerance).any(): raise ValueError('budget/count assigned to empty layer')
            closure.append(budget); continue
        if (k>ids.numel()).any(): raise ValueError('count exceeds layer geometry')
        if threshold_gev>0 and (budget+ tolerance < k.to(budget.dtype)*threshold_gev).any(): raise ValueError('threshold-infeasible count')
        local=(preselected_support_mask[:,ids] if preselected_support_mask is not None else exact_k_mask(support_logits[:,ids],k,stochastic_support))
        if (local.sum(dim=-1) != k).any():
            raise ValueError('preselected support does not match requested count')
        support[:,ids]=local; realized[:,layer]=local.sum(dim=-1)
        local_logits=share_logits[:,ids]
        # A conventional softmax over all -inf values is NaN when k=0.  The
        # masked exponential below is defined as exactly zero for an empty
        # support and as an ordinary softmax over selected cells otherwise.
        safe_logits=local_logits.masked_fill(~local,torch.finfo(local_logits.dtype).min)
        row_max=safe_logits.max(dim=-1,keepdim=True).values
        row_max=torch.where(local.any(dim=-1,keepdim=True),row_max,torch.zeros_like(row_max))
        numerator=torch.exp(safe_logits-row_max)*local.to(local_logits.dtype)
        weights=numerator/numerator.sum(dim=-1,keepdim=True).clamp_min(torch.finfo(local_logits.dtype).tiny)
        if threshold_gev==0:
            values=weights*budget[:,None]
        else:
            residual=(budget-k.to(budget.dtype)*threshold_gev).clamp_min(0)
            values=local.to(budget.dtype)*threshold_gev+weights*residual[:,None]
        cell[:,ids]=values; closure.append(values.sum(dim=-1)-budget)
    error=torch.stack(closure,dim=1)
    if error.abs().max()>tolerance: raise RuntimeError(f'decoder closure exceeded tolerance: {error.abs().max().item():.3e}')
    return DecodeOutput(cell,support,realized,error)
