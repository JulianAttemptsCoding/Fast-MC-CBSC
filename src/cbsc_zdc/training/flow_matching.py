from __future__ import annotations
import torch


def linear_flow_tuple(target:torch.Tensor,mask:torch.Tensor|None=None):
    source=torch.randn_like(target)
    if mask is not None: source=source*mask.to(source.dtype); target=target*mask.to(target.dtype)
    shape=(target.shape[0],)+(1,)*(target.ndim-1); t=torch.rand(shape,device=target.device,dtype=target.dtype)
    state=(1-t)*source+t*target; velocity=target-source
    return state,t,velocity


def masked_mse(prediction,target,mask=None):
    error=(prediction-target).square()
    if mask is None: return error.mean()
    while mask.ndim<error.ndim: mask=mask.unsqueeze(-1)
    weighted=error*mask.to(error.dtype); return weighted.sum()/mask.expand_as(error).sum().clamp_min(1)
