"""Conditional projection critics for the D1 (share) and D2 (profile) stages.

Both critics score a shower against its condition with a projection logit

    d(Y, P) = u(h_Y) + <h_Y, h_P>,   h_P = Linear(cond_dim, H)(c)

where larger ``d`` means "more Geant4-like".  Projection conditioning keeps the
condition from being ignored, which an unconditional critic would happily do.

Every output linear projection is spectrally normalized.  Critic parameters are
never shared with the generator.

**Sequence length.**  The D1 critic's Transformer runs over the 65 *layer*
tokens, not the 6,790 node tokens.  Self-attention over 6,790 tokens would be
quadratic in a number that makes the critic more expensive than the generator it
supervises.  Nodes are handled by edge-message blocks, then pooled per layer.
"""

from __future__ import annotations

import torch
from torch import nn
from torch.nn.utils.parametrizations import spectral_norm

from .graph import EdgeMessageBlock, LayerContext


def _masked_mean_max(
    values: torch.Tensor, mask: torch.Tensor, dim: int
) -> tuple[torch.Tensor, torch.Tensor]:
    """Mean and max over ``dim`` restricted to ``mask``.

    An empty group yields zeros rather than NaN or -inf, so a layer with no
    valid channel cannot poison the pooled embedding.
    """
    weight = mask.to(values.dtype).unsqueeze(-1)
    total = (values * weight).sum(dim=dim)
    count = weight.sum(dim=dim).clamp_min(1e-12)
    mean = total / count
    very_negative = torch.finfo(values.dtype).min
    masked = values.masked_fill(~mask.unsqueeze(-1), very_negative)
    maximum = masked.max(dim=dim).values
    maximum = torch.where(mask.any(dim=dim).unsqueeze(-1), maximum, torch.zeros_like(maximum))
    return mean, maximum


class ProjectionHead(nn.Module):
    """Shared projection-conditioning tail: ``u(h) + <h, W c>``."""

    def __init__(self, embed_dim: int, cond_dim: int) -> None:
        super().__init__()
        self.unconditional = spectral_norm(nn.Linear(embed_dim, 1))
        self.condition = spectral_norm(nn.Linear(cond_dim, embed_dim))

    def forward(self, embedding: torch.Tensor, cond: torch.Tensor) -> torch.Tensor:
        projected = self.condition(cond)
        return self.unconditional(embedding).squeeze(-1) + (embedding * projected).sum(dim=-1)


class ShareCritic(nn.Module):
    """D1: scores the within-layer energy shares on a fixed truth support."""

    def __init__(
        self,
        node_dim: int,
        edge_dim: int,
        cond_dim: int,
        n_layers: int,
        axis_dim: int = 4,
        hidden: int = 96,
        blocks: int = 2,
        heads: int = 4,
        context_layers: int = 2,
        embed_dim: int = 128,
    ) -> None:
        super().__init__()
        self.n_layers = int(n_layers)
        # per node: log1p(E), E/layer budget, support flag, static features, axis features
        self.input = nn.Sequential(
            nn.Linear(3 + node_dim + axis_dim, hidden), nn.SiLU(), nn.Linear(hidden, hidden)
        )
        self.blocks = nn.ModuleList([EdgeMessageBlock(hidden, edge_dim) for _ in range(blocks)])
        self.layer_token = nn.Linear(hidden * 2, hidden)
        self.layer_embedding = nn.Embedding(self.n_layers, hidden)
        self.context = LayerContext(hidden, self.n_layers, heads, context_layers, "bidirectional")
        self.embed = nn.Sequential(
            nn.LayerNorm(hidden * 4), nn.Linear(hidden * 4, embed_dim), nn.SiLU()
        )
        self.head = ProjectionHead(embed_dim, cond_dim)

    def embedding(
        self, cell_energy, layer_energy, support_mask, node_features, axis, edge_index,
        edge_features, layer_index, valid_mask,
    ) -> torch.Tensor:
        b, n = cell_energy.shape
        budget = layer_energy[:, layer_index].clamp_min(1e-12)
        pieces = [
            torch.log1p(cell_energy.clamp_min(0))[..., None],
            (cell_energy / budget)[..., None],
            support_mask.to(cell_energy.dtype)[..., None],
            node_features[None].expand(b, -1, -1),
            axis,
        ]
        h = self.input(torch.cat(pieces, dim=-1))
        for block in self.blocks:
            h = block(h, edge_index, edge_features)

        # Pool nodes into 65 layer tokens; the Transformer never sees n nodes.
        tokens = []
        for layer in range(self.n_layers):
            ids = torch.nonzero((layer_index == layer) & valid_mask).flatten()
            if ids.numel() == 0:
                tokens.append(h.new_zeros(b, h.shape[-1] * 2))
                continue
            group = h[:, ids]
            mask = torch.ones(b, ids.numel(), dtype=torch.bool, device=h.device)
            mean, maximum = _masked_mean_max(group, mask, dim=1)
            tokens.append(torch.cat([mean, maximum], dim=-1))
        layer_tokens = self.layer_token(torch.stack(tokens, dim=1))
        ids = torch.arange(self.n_layers, device=h.device)
        layer_tokens = layer_tokens + self.layer_embedding(ids)[None]
        contextual = self.context(layer_tokens)

        layer_mask = torch.ones(b, self.n_layers, dtype=torch.bool, device=h.device)
        layer_mean, layer_max = _masked_mean_max(contextual, layer_mask, dim=1)
        node_mask = valid_mask[None].expand(b, -1)
        node_mean, node_max = _masked_mean_max(h, node_mask, dim=1)
        return self.embed(torch.cat([layer_mean, layer_max, node_mean, node_max], dim=-1))

    def forward(self, cond, *args, **kwargs) -> torch.Tensor:
        return self.head(self.embedding(*args, **kwargs), cond)


class ProfileCritic(nn.Module):
    """D2: scores the 65 continuous layer budgets."""

    def __init__(
        self,
        cond_dim: int,
        n_layers: int,
        token_width: int = 128,
        heads: int = 4,
        context_layers: int = 2,
        embed_dim: int = 128,
    ) -> None:
        super().__init__()
        self.n_layers = int(n_layers)
        self.input = nn.Linear(3, token_width)
        self.layer_embedding = nn.Embedding(self.n_layers, token_width)
        self.context = LayerContext(
            token_width, self.n_layers, heads, context_layers, "bidirectional"
        )
        self.embed = nn.Sequential(
            nn.LayerNorm(token_width * 2), nn.Linear(token_width * 2, embed_dim), nn.SiLU()
        )
        self.head = ProjectionHead(embed_dim, cond_dim)

    def embedding(self, layer_energy, total_response, active) -> torch.Tensor:
        b = layer_energy.shape[0]
        total = total_response[:, None].clamp_min(1e-12)
        tokens = torch.stack(
            [
                layer_energy / total,
                torch.log1p(layer_energy.clamp_min(0)),
                active.to(layer_energy.dtype),
            ],
            dim=-1,
        )
        h = self.input(tokens)
        ids = torch.arange(self.n_layers, device=h.device)
        h = h + self.layer_embedding(ids)[None]
        h = self.context(h)
        mask = torch.ones(b, self.n_layers, dtype=torch.bool, device=h.device)
        mean, maximum = _masked_mean_max(h, mask, dim=1)
        return self.embed(torch.cat([mean, maximum], dim=-1))

    def forward(self, cond, layer_energy, total_response, active) -> torch.Tensor:
        return self.head(self.embedding(layer_energy, total_response, active), cond)
