from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import nn

from ..features import p4_features
from .blocks import ConditionEncoder
from .counts import LayerCountHead
from .profile import LongitudinalProfileModel
from .spatial import ParallelCausalSpatialField
from .support import DecodeOutput, threshold_safe_layer_decoder


@dataclass
class CBSCOutput:
    cell_energy: torch.Tensor
    total: torch.Tensor
    layer_energy: torch.Tensor
    reserve: torch.Tensor
    subthreshold_residual: torch.Tensor
    requested_counts: torch.Tensor
    realized_counts: torch.Tensor
    support_mask: torch.Tensor
    first_visible_layer: torch.Tensor
    active_layers: torch.Tensor


class CBSCZDC(nn.Module):
    """Reference sampler for the revised CBSC-ZDC factorization.

    This class is an executable architecture scaffold. It is not a trained simulator and
    does not implement the complete Vertex training pipeline by itself.
    """

    def __init__(
        self,
        node_features: torch.Tensor,
        layer_index: torch.Tensor,
        valid_mask: torch.Tensor,
        edge_index: torch.Tensor | None = None,
        edge_features: torch.Tensor | None = None,
        cond_dim: int = 128,
        latent_dim: int = 32,
        threshold_gev: float = 0.0,
    ):
        super().__init__()
        if threshold_gev < 0:
            raise ValueError("threshold_gev must be nonnegative")
        if node_features.ndim != 2:
            raise ValueError("node_features must have shape [nodes,features]")
        n_nodes = node_features.shape[0]
        if layer_index.shape != (n_nodes,) or valid_mask.shape != (n_nodes,):
            raise ValueError("layer_index and valid_mask must have shape [nodes]")
        if (layer_index < 0).any():
            raise ValueError("layer_index must be nonnegative")
        if not valid_mask.any():
            raise ValueError("the detector must contain at least one valid node")
        self.threshold_gev = float(threshold_gev)
        self.register_buffer("node_features", node_features.float())
        self.register_buffer("layer_index", layer_index.long())
        self.register_buffer("valid_mask", valid_mask.bool())
        if (edge_index is None) != (edge_features is None):
            raise ValueError("edge_index and edge_features must be supplied together")
        if edge_index is None:
            edge_index = torch.empty(2, 0, dtype=torch.long)
            edge_features = torch.empty(0, 4, dtype=torch.float32)
        self.register_buffer("edge_index", edge_index.long())
        self.register_buffer("edge_features", edge_features.float())
        n_layers = int(layer_index.max().item()) + 1
        self.n_layers = n_layers
        max_counts = [
            int(((layer_index == layer) & valid_mask).sum().item())
            for layer in range(n_layers)
        ]
        if any(count <= 0 for count in max_counts):
            raise ValueError("every modeled layer must contain at least one valid node")
        self.register_buffer("max_counts", torch.tensor(max_counts, dtype=torch.long))
        self.condition = ConditionEncoder(cond_dim)
        self.profile = LongitudinalProfileModel(
            cond_dim=cond_dim, latent_dim=latent_dim, n_layers=n_layers
        )
        self.counts = LayerCountHead(
            cond_dim=cond_dim, n_layers=n_layers, max_counts=max_counts
        )
        self.spatial = ParallelCausalSpatialField(
            node_dim=node_features.shape[1],
            edge_dim=edge_features.shape[1],
            cond_dim=cond_dim,
            n_layers=n_layers,
        )

    @torch.no_grad()
    def sample(
        self,
        p4: torch.Tensor,
        steps: int = 8,
        seed: int | None = None,
        stochastic: bool = True,
    ) -> CBSCOutput:
        if steps <= 0:
            raise ValueError("steps must be positive")
        devices = [p4.device] if p4.is_cuda else []
        with torch.random.fork_rng(devices=devices):
            if seed is not None:
                torch.manual_seed(seed)
            cond = self.condition(p4_features(p4))
            incident_e = p4[:, :1]
            profile = self.profile.sample(
                incident_e, cond, stochastic=stochastic
            )
            requested_counts, _ = self.counts.sample(
                cond,
                profile.layer_energy,
                profile.active_layers,
                threshold_gev=self.threshold_gev,
                stochastic=stochastic,
            )
            if stochastic:
                state = torch.randn(
                    p4.shape[0],
                    self.node_features.shape[0],
                    2,
                    device=p4.device,
                    dtype=p4.dtype,
                )
            else:
                state = torch.zeros(
                    p4.shape[0],
                    self.node_features.shape[0],
                    2,
                    device=p4.device,
                    dtype=p4.dtype,
                )
            dt = 1.0 / steps
            for step in range(steps):
                t = torch.full(
                    (p4.shape[0], 1),
                    step / steps,
                    device=p4.device,
                    dtype=p4.dtype,
                )
                velocity = self.spatial(
                    state,
                    t,
                    cond,
                    self.node_features,
                    self.layer_index,
                    profile.layer_energy,
                    requested_counts,
                    self.max_counts,
                    self.valid_mask,
                    self.edge_index,
                    self.edge_features,
                )
                state = state + dt * velocity

            decoded: DecodeOutput = threshold_safe_layer_decoder(
                support_logits=state[..., 0],
                share_logits=state[..., 1],
                layer_budget=profile.layer_energy,
                requested_counts=requested_counts,
                layer_index=self.layer_index,
                valid_mask=self.valid_mask,
                threshold_gev=self.threshold_gev,
                stochastic_support=stochastic,
            )
            return CBSCOutput(
                cell_energy=decoded.cell_energy,
                total=profile.total,
                layer_energy=profile.layer_energy,
                reserve=profile.reserve,
                subthreshold_residual=decoded.subthreshold_residual,
                requested_counts=requested_counts,
                realized_counts=decoded.realized_counts,
                support_mask=decoded.support_mask,
                first_visible_layer=profile.first_visible_layer,
                active_layers=profile.active_layers,
            )
