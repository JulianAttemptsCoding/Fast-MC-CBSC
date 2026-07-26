from __future__ import annotations

import math
import torch
from torch import nn


class ResidualMLP(nn.Module):
    def __init__(self, dim:int, hidden:int, blocks:int=2, dropout:float=0.0):
        super().__init__()
        self.blocks=nn.ModuleList([nn.Sequential(nn.LayerNorm(dim),nn.Linear(dim,hidden),nn.SiLU(),nn.Dropout(dropout),nn.Linear(hidden,dim)) for _ in range(blocks)])
    def forward(self,x:torch.Tensor)->torch.Tensor:
        for block in self.blocks: x=x+block(x)
        return x


class ConditionEncoder(nn.Module):
    def __init__(self,input_dim:int=5,out_dim:int=128,dropout:float=0.0):
        super().__init__()
        self.net=nn.Sequential(nn.Linear(input_dim,out_dim),nn.SiLU(),ResidualMLP(out_dim,out_dim*2,2,dropout),nn.LayerNorm(out_dim))
    def forward(self,x): return self.net(x)


class SinusoidalTimeEmbedding(nn.Module):
    def __init__(self,dim:int):
        super().__init__(); self.dim=dim
    def forward(self,t:torch.Tensor)->torch.Tensor:
        if t.ndim==1: t=t[:,None]
        half=self.dim//2
        freq=torch.exp(torch.arange(half,device=t.device,dtype=t.dtype)*(-math.log(10000.0)/max(half-1,1)))
        angles=t*freq[None]
        out=torch.cat([torch.sin(angles),torch.cos(angles)],dim=-1)
        if out.shape[-1]<self.dim: out=torch.nn.functional.pad(out,(0,self.dim-out.shape[-1]))
        return out


class FiLM(nn.Module):
    def __init__(self,cond_dim:int,feat_dim:int):
        super().__init__(); self.proj=nn.Linear(cond_dim,2*feat_dim)
    def forward(self,x:torch.Tensor,cond:torch.Tensor)->torch.Tensor:
        gain,bias=self.proj(cond).chunk(2,dim=-1)
        while gain.ndim<x.ndim: gain=gain.unsqueeze(1); bias=bias.unsqueeze(1)
        return x*(1+gain)+bias
