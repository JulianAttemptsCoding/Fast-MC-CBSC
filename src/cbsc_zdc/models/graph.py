from __future__ import annotations

import torch
from torch import nn


class EdgeMessageBlock(nn.Module):
    def __init__(self,hidden:int,edge_dim:int,edge_chunk_size:int=16384):
        super().__init__(); self.edge_dim=edge_dim; self.edge_chunk_size=edge_chunk_size
        self.message=nn.Sequential(nn.Linear(hidden*2+edge_dim,hidden*2),nn.SiLU(),nn.Linear(hidden*2,hidden))
        self.update=nn.Sequential(nn.LayerNorm(hidden*2),nn.Linear(hidden*2,hidden*2),nn.SiLU(),nn.Linear(hidden*2,hidden))
    def forward(self,h,edge_index,edge_features):
        if edge_index.ndim!=2 or edge_index.shape[0]!=2: raise ValueError('edge_index must be [2,E]')
        if edge_features.shape!=(edge_index.shape[1],self.edge_dim): raise ValueError('edge feature shape mismatch')
        aggregate=torch.zeros_like(h); src_all,dst_all=edge_index
        for start in range(0,edge_index.shape[1],self.edge_chunk_size):
            stop=min(start+self.edge_chunk_size,edge_index.shape[1]); src=src_all[start:stop]; dst=dst_all[start:stop]
            edge=edge_features[start:stop][None].expand(h.shape[0],-1,-1)
            msg=self.message(torch.cat([h[:,src],h[:,dst],edge],dim=-1))
            aggregate.index_add_(1,dst,msg)
        return h+self.update(torch.cat([h,aggregate],dim=-1))


def layer_pool(h:torch.Tensor,layer_index:torch.Tensor,n_layers:int)->torch.Tensor:
    out=torch.zeros(h.shape[0],n_layers,h.shape[-1],device=h.device,dtype=h.dtype)
    out.index_add_(1,layer_index,h)
    counts=torch.bincount(layer_index,minlength=n_layers).to(h.dtype).clamp_min(1)[None,:,None]
    return out/counts


class LayerContext(nn.Module):
    def __init__(self,hidden:int,n_layers:int,heads:int=4,layers:int=2,mode:str='bidirectional'):
        super().__init__(); self.n_layers=n_layers; self.mode=mode
        encoder_layer=nn.TransformerEncoderLayer(d_model=hidden,nhead=heads,dim_feedforward=hidden*4,dropout=0.0,batch_first=True,norm_first=True,activation='gelu')
        self.encoder=nn.TransformerEncoder(encoder_layer,num_layers=layers)
    def forward(self,tokens):
        mask=None
        if self.mode=='causal': mask=torch.triu(torch.full((self.n_layers,self.n_layers),float('-inf'),device=tokens.device,dtype=tokens.dtype),diagonal=1)
        return self.encoder(tokens,mask=mask)
