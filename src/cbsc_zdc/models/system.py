from __future__ import annotations

from dataclasses import dataclass
import torch
from torch import nn

from ..contracts import kinetic_energy_from_p4
from ..features import p4_condition_features
from .blocks import ConditionEncoder
from .counts import LayerCountHead
from .node_fields import ShareFlowField,SupportScoreField
from .profile import LongitudinalProfileModel
from .response import ResponseHead
from .support import decode_exact_support


@dataclass
class CBSCOutput:
    cell_energy: torch.Tensor
    visible: torch.Tensor
    total_response: torch.Tensor
    first_positive_layer: torch.Tensor
    active_layers: torch.Tensor
    layer_energy: torch.Tensor
    requested_counts: torch.Tensor
    realized_counts: torch.Tensor
    support_mask: torch.Tensor
    support_logits: torch.Tensor
    share_state: torch.Tensor


class CBSCZDC(nn.Module):
    def __init__(self,geometry:dict[str,torch.Tensor],config:dict):
        super().__init__(); m=config['model']; d=config['data']
        # Absence of the key means v2.2. Nothing below the v3 branches changes
        # for a configuration that does not declare it.
        self.architecture_version=str(m.get('architecture_version','cbsc-zdc-v2.2'))
        self.is_v3=self.architecture_version=='cbsc-zdc-v3'
        self.threshold_gev=float(d.get('threshold_gev',0.0)); self.target_mode=d['target_mode']
        for name in ['node_features','layer_index','valid_mask','edge_index','edge_features']:
            self.register_buffer(name,geometry[name].clone())
        self.n_layers=int(self.layer_index.max())+1; self.n_nodes=self.node_features.shape[0]
        max_counts=[int(((self.layer_index==i)&self.valid_mask).sum()) for i in range(self.n_layers)]
        cond_dim=int(m.get('condition_dim',128)); hidden=int(m.get('hidden_dim',96)); mode=m.get('layer_context','bidirectional')
        self.condition=ConditionEncoder(5,cond_dim,float(m.get('dropout',0.0)))
        self.response=ResponseHead(cond_dim,int(m.get('response_hidden',192)),int(m.get('response_components',4)),float(m.get('response_scale_gev',10.0)))
        self.profile=LongitudinalProfileModel(cond_dim,self.n_layers,int(m.get('profile_hidden',128)),mode)
        self.counts=LayerCountHead(cond_dim,self.n_layers,max_counts,int(m.get('count_hidden',192)))
        field_args=dict(node_dim=self.node_features.shape[1],edge_dim=self.edge_features.shape[1],cond_dim=cond_dim,n_layers=self.n_layers,hidden=hidden,blocks=int(m.get('graph_blocks',3)),heads=int(m.get('attention_heads',4)),context_layers=int(m.get('attention_layers',2)),mode=mode)
        self.support=SupportScoreField(**field_args); self.share=ShareFlowField(**field_args)
        self.register_buffer('max_counts',torch.tensor(max_counts,dtype=torch.long))
        self.response_cap_ratio=float(d.get('response_cap_ratio',2.0)); self.response_cap_absolute_gev=float(d.get('response_cap_absolute_gev',500.0))
        self.support_temperature=float(m.get('support_temperature',1.0))
        self.activity_mode=str(m.get('activity_mode','span_gaps'))
        if self.is_v3:
            # v3 heads live alongside the v2.2 ones rather than replacing them in
            # place, so a migrated checkpoint can carry both and the v2.2 modules
            # keep their exact parameter names.
            from .activity import AutoregressiveActivityHead,SpanGapActivityHead
            from .counts_ar import AutoregressiveCountHead
            from .first_layer import HierarchicalFirstLayerHead
            from .response_v3 import BoundedResponseHead
            self.response_v3=BoundedResponseHead(cond_dim,int(m.get('response_hidden',192)),int(m.get('response_spline_bins',16)))
            self.first_layer=HierarchicalFirstLayerHead(cond_dim,self.n_layers,int(m.get('first_layer_hidden',128)))
            if self.activity_mode=='autoregressive':
                self.activity=AutoregressiveActivityHead(cond_dim,self.n_layers,int(m.get('activity_hidden',128)))
            else:
                self.activity=SpanGapActivityHead(cond_dim,self.n_layers,int(m.get('activity_hidden',128)))
            self.counts_ar=AutoregressiveCountHead(cond_dim,self.n_layers,max_counts,int(m.get('count_hidden',192)))
            # The bounded response head needs C(K) from the train-only envelope.
            # It is registered as a buffer so it is checkpointed with the model
            # and cannot silently differ between a run and its resume.
            caps=m.get('response_envelope_caps_gev')
            if caps is None:
                # No envelope supplied: fall back to the v2.2 cap rule so the
                # model is still constructible for smoke and unit tests. A
                # production v3 run must supply the measured envelope, which
                # preflight_v3_envelope() below asserts.
                self.register_buffer('response_envelope_caps_gev',torch.zeros(0))
            else:
                self.register_buffer('response_envelope_caps_gev',torch.tensor([float(c) for c in caps],dtype=torch.float32))
            self.response_envelope_sha256=m.get('response_envelope_sha256')

    def response_cap_for(self,kinetic_gev:torch.Tensor)->torch.Tensor:
        """C(K) per event from the frozen 25-GeV envelope.

        Falls back to the v2.2 cap rule only when no envelope is installed, which
        is the unit-test path; ``preflight_v3_envelope`` refuses that for a
        production run.
        """
        caps=getattr(self,'response_envelope_caps_gev',None)
        if caps is None or caps.numel()==0:
            return torch.minimum(torch.full_like(kinetic_gev,self.response_cap_absolute_gev),self.response_cap_ratio*kinetic_gev.clamp_min(1.0))
        index=torch.clamp((kinetic_gev/25.0).floor().long(),0,caps.numel()-1)
        return caps.to(kinetic_gev.dtype)[index]

    def preflight_v3_envelope(self)->None:
        """Fail closed if a v3 run has no measured response envelope."""
        if not self.is_v3:
            return
        caps=getattr(self,'response_envelope_caps_gev',None)
        if caps is None or caps.numel()==0:
            raise ValueError(
                'a v3 run requires model.response_envelope_caps_gev from the '
                'train-only envelope; the v2.2 quantile cap is not spline support'
            )
        if not bool(torch.isfinite(caps).all()) or bool((caps<=0).any()):
            raise ValueError('response envelope caps must be finite and strictly positive')
        if bool((caps[1:]<caps[:-1]).any()):
            raise ValueError('response envelope caps must be nondecreasing')
    def encode_condition(self,p4): return self.condition(p4_condition_features(p4))
    def support_logits(self,cond,layer_energy,counts):
        fraction=counts.to(cond.dtype)/self.max_counts[None].clamp_min(1)
        logits=self.support(self.node_features,self.edge_index,self.edge_features,self.layer_index,cond,layer_energy,fraction)
        return logits.masked_fill(~self.valid_mask[None],torch.finfo(logits.dtype).min)
    def share_velocity(self,state,t,cond,layer_energy,counts,support_mask):
        fraction=counts.to(cond.dtype)/self.max_counts[None].clamp_min(1)
        return self.share(self.node_features,self.edge_index,self.edge_features,self.layer_index,cond,layer_energy,fraction,state,t,support_mask)
    @torch.no_grad()
    def sample(self,p4_total_gev,profile_steps:int=8,share_steps:int=8,seed:int|None=None,stochastic:bool=True):
        devices=[p4_total_gev.device] if p4_total_gev.is_cuda else []
        with torch.random.fork_rng(devices=devices):
            if seed is not None: torch.manual_seed(seed)
            cond=self.encode_condition(p4_total_gev); kinetic=kinetic_energy_from_p4(p4_total_gev).to(cond.dtype)
            visible,total=self.response.sample(cond,kinetic,self.response_cap_ratio,self.response_cap_absolute_gev,stochastic)
            profile=self.profile.sample(cond,total,visible,profile_steps,stochastic)
            counts,_=self.counts.sample(cond,profile.layer_energy,profile.active_layers,self.threshold_gev,stochastic)
            support_logits=self.support_logits(cond,profile.layer_energy,counts)
            # Draw the support once; share flow is deterministic conditional on its source noise and selected mask.
            from .support import exact_k_mask
            support_mask=torch.zeros_like(support_logits,dtype=torch.bool)
            for layer in range(self.n_layers):
                ids=torch.where((self.layer_index==layer)&self.valid_mask)[0]
                support_mask[:,ids]=exact_k_mask(support_logits[:,ids],counts[:,layer],stochastic)
            state=torch.randn_like(support_logits) if stochastic else torch.zeros_like(support_logits)
            state*=support_mask.to(state.dtype); dt=1/share_steps
            for step in range(share_steps):
                t=torch.full((cond.shape[0],1),(step+0.5)/share_steps,device=cond.device,dtype=cond.dtype)
                state=(state+dt*self.share_velocity(state,t,cond,profile.layer_energy,counts,support_mask))*support_mask.to(state.dtype)
            decoded=decode_exact_support(support_logits,state,profile.layer_energy,counts,self.layer_index,self.valid_mask,self.threshold_gev,False,preselected_support_mask=support_mask)
            return CBSCOutput(decoded.cell_energy,visible,total,profile.first_positive_layer,profile.active_layers,profile.layer_energy,counts,decoded.realized_counts,decoded.support_mask,support_logits,state)
