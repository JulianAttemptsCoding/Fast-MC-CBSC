from __future__ import annotations

from dataclasses import dataclass
import torch
from torch import nn
from .blocks import SinusoidalTimeEmbedding
from .graph import LayerContext


@dataclass
class ProfileOutput:
    first_positive_layer: torch.Tensor
    active_layers: torch.Tensor
    layer_energy: torch.Tensor
    profile_state: torch.Tensor


class LayerShareFlow(nn.Module):
    def __init__(self,cond_dim:int,n_layers:int,hidden:int=128,heads:int=4,context_layers:int=2,mode:str='bidirectional'):
        super().__init__(); self.n_layers=n_layers
        self.layer_embedding=nn.Embedding(n_layers,hidden); self.time=SinusoidalTimeEmbedding(hidden)
        self.in_proj=nn.Linear(1+1+1+cond_dim+hidden+hidden,hidden)
        self.context=LayerContext(hidden,n_layers,heads,context_layers,mode); self.out=nn.Linear(hidden,1)
    def forward(self,state,t,cond,total,active):
        b,l=state.shape; ids=torch.arange(l,device=state.device); emb=self.layer_embedding(ids)[None].expand(b,-1,-1)
        time=self.time(t.reshape(b,-1)[:,:1])[:,None].expand(-1,l,-1); c=cond[:,None].expand(-1,l,-1)
        total_feature=torch.log1p(total)[:,None,None].expand(-1,l,1)
        x=torch.cat([state[...,None],active.to(state.dtype)[...,None],total_feature,c,emb,time],dim=-1)
        return self.out(self.context(self.in_proj(x))).squeeze(-1)*active.to(state.dtype)


class LongitudinalProfileModel(nn.Module):
    def __init__(self,cond_dim:int,n_layers:int,hidden:int=128,mode:str='bidirectional'):
        super().__init__(); self.n_layers=n_layers
        self.first=nn.Sequential(nn.Linear(cond_dim+1,hidden),nn.SiLU(),nn.Linear(hidden,n_layers))
        self.layer_embedding=nn.Embedding(n_layers,24)
        self.active=nn.Sequential(nn.Linear(cond_dim+1+24+24,hidden),nn.SiLU(),nn.Linear(hidden,1))
        self.first_embedding=nn.Embedding(n_layers,24)
        self.flow=LayerShareFlow(cond_dim,n_layers,hidden,4,2,mode)
    def first_logits(self,cond,total): return self.first(torch.cat([cond,torch.log1p(total)[:,None]],dim=-1))
    def active_logits(self,cond,total,first):
        b=cond.shape[0]; ids=torch.arange(self.n_layers,device=cond.device); le=self.layer_embedding(ids)[None].expand(b,-1,-1)
        fe=self.first_embedding(first.clamp(0,self.n_layers-1))[:,None].expand(-1,self.n_layers,-1)
        c=cond[:,None].expand(-1,self.n_layers,-1); t=torch.log1p(total)[:,None,None].expand(-1,self.n_layers,1)
        return self.active(torch.cat([c,t,le,fe],dim=-1)).squeeze(-1)
    @torch.no_grad()
    def sample(self,cond,total,visible,steps:int=8,stochastic:bool=True):
        first_logits=self.first_logits(cond,total)
        first=torch.distributions.Categorical(logits=first_logits).sample() if stochastic else first_logits.argmax(dim=-1)
        logits=self.active_logits(cond,total,first); probs=torch.sigmoid(logits)
        active=torch.bernoulli(probs).bool() if stochastic else probs>0.5
        layer_ids=torch.arange(self.n_layers,device=cond.device)[None]
        active &= layer_ids>=first[:,None]; active.scatter_(1,first[:,None],True); active &= visible[:,None]
        state=torch.randn_like(active,dtype=cond.dtype) if stochastic else torch.zeros_like(active,dtype=cond.dtype)
        dt=1.0/steps
        for s in range(steps):
            t=torch.full((cond.shape[0],1),(s+0.5)/steps,device=cond.device,dtype=cond.dtype)
            state=(state+dt*self.flow(state,t,cond,total,active))*active.to(cond.dtype)
        masked=state.masked_fill(~active,torch.finfo(state.dtype).min); weights=torch.softmax(masked,dim=-1)
        weights=torch.where(visible[:,None],weights,torch.zeros_like(weights)); layer_energy=weights*total[:,None]
        first=torch.where(visible,first,torch.full_like(first,-1))
        return ProfileOutput(first,active,layer_energy,state)
