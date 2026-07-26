from __future__ import annotations

import torch
from torch import nn

from .blocks import FiLM
from .graph import EdgeMessageBlock


class ParallelCausalSpatialField(nn.Module):
    """Parallel time-dependent graph field with causal longitudinal layer attention.

    Every solver step updates all nodes simultaneously. Edge-conditioned message passing
    represents local detector geometry. Layer l may attend to itself and earlier layers
    through a causal mask, preserving longitudinal context without a 65-call rollout.
    """

    def __init__(
        self,
        node_dim: int = 8,
        edge_dim: int = 4,
        cond_dim: int = 128,
        hidden: int = 96,
        n_layers: int = 65,
        graph_blocks: int = 2,
        transformer_blocks: int = 3,
        heads: int = 4,
        edge_chunk_size: int = 16384,
    ):
        super().__init__()
        if hidden % heads != 0:
            raise ValueError("hidden dimension must be divisible by the number of heads")
        self.n_layers = n_layers
        self.edge_dim = edge_dim
        self.node_in = nn.Linear(node_dim + 2 + 2, hidden)
        self.time_embed = nn.Sequential(
            nn.Linear(1, hidden), nn.SiLU(), nn.Linear(hidden, hidden)
        )
        self.film = FiLM(cond_dim, hidden)
        self.graph_blocks = nn.ModuleList(
            [
                EdgeMessageBlock(
                    hidden=hidden,
                    edge_dim=edge_dim,
                    edge_chunk_size=edge_chunk_size,
                )
                for _ in range(graph_blocks)
            ]
        )
        encoder_layer = nn.TransformerEncoderLayer(
            hidden,
            heads,
            hidden * 4,
            batch_first=True,
            norm_first=True,
            activation="gelu",
        )
        self.layer_mixer = nn.TransformerEncoder(
            encoder_layer, transformer_blocks
        )
        self.node_out = nn.Sequential(
            nn.LayerNorm(hidden),
            nn.Linear(hidden, hidden),
            nn.SiLU(),
            nn.Linear(hidden, 2),
        )
        causal = torch.triu(
            torch.ones(n_layers, n_layers, dtype=torch.bool), diagonal=1
        )
        self.register_buffer("causal_layer_mask", causal)

    def forward(
        self,
        x_t: torch.Tensor,
        t: torch.Tensor,
        cond: torch.Tensor,
        node_features: torch.Tensor,
        layer_index: torch.Tensor,
        layer_budget: torch.Tensor,
        layer_counts: torch.Tensor,
        max_counts: torch.Tensor,
        valid_mask: torch.Tensor | None = None,
        edge_index: torch.Tensor | None = None,
        edge_features: torch.Tensor | None = None,
    ) -> torch.Tensor:
        batch, n_nodes, state_dim = x_t.shape
        if state_dim != 2:
            raise ValueError("x_t must have two node-state channels")
        if node_features.shape[0] != n_nodes or layer_index.shape != (n_nodes,):
            raise ValueError("node geometry shape mismatch")
        if valid_mask is None:
            valid_mask = torch.ones(n_nodes, dtype=torch.bool, device=x_t.device)
        if valid_mask.shape != (n_nodes,):
            raise ValueError("valid_mask must have shape [nodes]")
        if (edge_index is None) != (edge_features is None):
            raise ValueError("edge_index and edge_features must be supplied together")

        node_static = node_features[None].expand(batch, -1, -1)
        expanded_layer = layer_index[None].expand(batch, -1)
        budget_node = layer_budget.gather(1, expanded_layer)
        count_fraction = (
            layer_counts.float() / max_counts[None].clamp_min(1).float()
        ).gather(1, expanded_layer)
        dynamic = torch.stack((torch.log1p(budget_node), count_fraction), dim=-1)
        h = self.node_in(torch.cat((x_t, node_static, dynamic), dim=-1))
        h = h + self.time_embed(t.reshape(batch, 1))[:, None, :]
        h = self.film(h, cond)
        h = h * valid_mask[None, :, None].to(h.dtype)

        if edge_index is not None and edge_features is not None:
            for block in self.graph_blocks:
                h = block(h, edge_index, edge_features)
                h = h * valid_mask[None, :, None].to(h.dtype)

        layer_sum = torch.zeros(
            batch, self.n_layers, h.shape[-1], device=h.device, dtype=h.dtype
        )
        gather_index = layer_index.view(1, n_nodes, 1).expand(
            batch, n_nodes, h.shape[-1]
        )
        layer_sum.scatter_add_(1, gather_index, h)
        valid_count = torch.zeros(
            self.n_layers, device=h.device, dtype=h.dtype
        )
        valid_count.scatter_add_(0, layer_index, valid_mask.to(h.dtype))
        layer_tokens = layer_sum / valid_count.clamp_min(1).view(1, -1, 1)
        layer_tokens = self.layer_mixer(
            layer_tokens, mask=self.causal_layer_mask
        )
        h = h + layer_tokens.gather(1, gather_index)
        out = self.node_out(h)
        return out * valid_mask[None, :, None].to(out.dtype)
