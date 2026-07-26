from __future__ import annotations

import torch
from torch import nn
from .blocks import SinusoidalTimeEmbedding
from .graph import EdgeMessageBlock, LayerContext, layer_pool


class GeometryAwareNodeField(nn.Module):
    def __init__(self,node_dim:int,edge_dim:int,cond_dim:int,n_layers:int,hidden:int=96,blocks:int=3,heads:int=4,context_layers:int=2,mode:str='bidirectional',state_dim:int=0):
        super().__init__(); self.n_layers=n_layers; self.state_dim=state_dim
        self.time=SinusoidalTimeEmbedding(32) if state_dim else None
        input_dim=node_dim+cond_dim+2+state_dim+(32 if state_dim else 0)
        self.input=nn.Sequential(nn.Linear(input_dim,hidden),nn.SiLU(),nn.Linear(hidden,hidden))
        self.blocks=nn.ModuleList([EdgeMessageBlock(hidden,edge_dim) for _ in range(blocks)])
        self.context=LayerContext(hidden,n_layers,heads,context_layers,mode)
        self.output=nn.Sequential(nn.LayerNorm(hidden*2),nn.Linear(hidden*2,hidden),nn.SiLU(),nn.Linear(hidden,1))
    def forward(self,node_features,edge_index,edge_features,layer_index,cond,layer_energy,count_fraction,state=None,t=None,support_mask=None):
        b=cond.shape[0]; n=node_features.shape[0]
        pieces=[node_features[None].expand(b,-1,-1),cond[:,None].expand(-1,n,-1),layer_energy[:,layer_index,None],count_fraction[:,layer_index,None]]
        if self.state_dim:
            if state is None or t is None: raise ValueError('state and t required')
            pieces.append(state[...,None] if state.ndim==2 else state)
            pieces.append(self.time(t.reshape(b,-1)[:,:1])[:,None].expand(-1,n,-1))
        h=self.input(torch.cat(pieces,dim=-1))
        if support_mask is not None: h=h*support_mask.to(h.dtype)[...,None]
        for block in self.blocks:
            h=block(h,edge_index,edge_features)
            if support_mask is not None: h=h*support_mask.to(h.dtype)[...,None]
        layer=self.context(layer_pool(h,layer_index,self.n_layers)); broadcast=layer[:,layer_index]
        out=self.output(torch.cat([h,broadcast],dim=-1)).squeeze(-1)
        if support_mask is not None: out=out*support_mask.to(out.dtype)
        return out


class SupportScoreField(GeometryAwareNodeField):
    def __init__(self,**kwargs): super().__init__(state_dim=0,**kwargs)


class ShareFlowField(GeometryAwareNodeField):
    def __init__(self,**kwargs): super().__init__(state_dim=1,**kwargs)
