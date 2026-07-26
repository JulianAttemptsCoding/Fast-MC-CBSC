from __future__ import annotations

import torch
from torch import nn


class LayerCountHead(nn.Module):
    def __init__(self,cond_dim:int,n_layers:int,max_counts:list[int],hidden:int=192):
        super().__init__(); self.n_layers=n_layers; self.register_buffer('max_counts',torch.tensor(max_counts,dtype=torch.long)); self.max_global=max(max_counts)
        self.layer_embedding=nn.Embedding(n_layers,24)
        self.net=nn.Sequential(nn.Linear(cond_dim+2+24,hidden),nn.SiLU(),nn.Linear(hidden,hidden),nn.SiLU(),nn.Linear(hidden,self.max_global+1))
    def logits(self,cond,layer_energy,active,threshold_gev:float=0.0):
        b,l=layer_energy.shape; ids=torch.arange(l,device=cond.device); emb=self.layer_embedding(ids)[None].expand(b,-1,-1)
        x=torch.cat([cond[:,None].expand(-1,l,-1),torch.log1p(layer_energy)[...,None],active.to(cond.dtype)[...,None],emb],dim=-1)
        logits=self.net(x); classes=torch.arange(self.max_global+1,device=cond.device)[None,None]
        feasible=(classes<=self.max_counts[None,:,None]).expand(b,-1,-1).clone()
        if threshold_gev>0: feasible &= classes<=torch.floor(layer_energy/threshold_gev).long()[...,None]
        feasible &= torch.where(active[...,None],classes>0,classes==0)
        return logits.masked_fill(~feasible,torch.finfo(logits.dtype).min)
    def sample(self,cond,layer_energy,active,threshold_gev=0.0,stochastic=True):
        logits=self.logits(cond,layer_energy,active,threshold_gev)
        counts=torch.distributions.Categorical(logits=logits).sample() if stochastic else logits.argmax(dim=-1)
        return counts,logits
