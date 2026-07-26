from __future__ import annotations

import torch
from torch import nn


class LayerCountHead(nn.Module):
    """Finite-support categorical hit-count model for each detector layer.

    A categorical count model avoids the Poisson mean=variance restriction and permits
    exact masking of impossible counts when a positive readout threshold is used.
    """

    def __init__(
        self,
        cond_dim: int = 128,
        n_layers: int = 65,
        max_counts: list[int] | None = None,
        hidden: int = 192,
        layer_embedding_dim: int = 24,
    ):
        super().__init__()
        self.n_layers = n_layers
        default_counts = [400] + [100] * 63 + [90]
        max_counts = max_counts or default_counts
        if len(max_counts) != n_layers:
            raise ValueError("max_counts length must equal n_layers")
        self.register_buffer("max_counts", torch.tensor(max_counts, dtype=torch.long))
        self.max_global = int(max(max_counts))
        self.layer_embedding = nn.Embedding(n_layers, layer_embedding_dim)
        self.net = nn.Sequential(
            nn.Linear(cond_dim + 2 + layer_embedding_dim, hidden),
            nn.SiLU(),
            nn.Linear(hidden, hidden),
            nn.SiLU(),
            nn.Linear(hidden, self.max_global + 1),
        )

    def logits(
        self,
        cond: torch.Tensor,
        layer_energy: torch.Tensor,
        active_layers: torch.Tensor,
        threshold_gev: float = 0.0,
    ) -> torch.Tensor:
        batch, n_layers = layer_energy.shape
        if n_layers != self.n_layers:
            raise ValueError("layer_energy has the wrong layer dimension")
        layer_ids = torch.arange(self.n_layers, device=cond.device)
        emb = self.layer_embedding(layer_ids)[None].expand(batch, -1, -1)
        cond_expanded = cond[:, None, :].expand(-1, self.n_layers, -1)
        features = torch.cat(
            (
                cond_expanded,
                torch.log1p(layer_energy)[..., None],
                active_layers[..., None],
                emb,
            ),
            dim=-1,
        )
        logits = self.net(features)

        counts = torch.arange(self.max_global + 1, device=cond.device)
        max_by_geometry = self.max_counts[None, :, None]
        feasible = counts[None, None, :] <= max_by_geometry
        if threshold_gev > 0:
            max_by_budget = torch.floor(layer_energy / threshold_gev).long()
            feasible = feasible & (counts[None, None, :] <= max_by_budget[..., None])
        # Inactive layers must have count zero. Active positive-budget layers must have
        # at least one hit whenever the threshold permits one.
        inactive = active_layers <= 0
        feasible = torch.where(
            inactive[..., None], counts[None, None, :] == 0, feasible
        )
        can_resolve = (layer_energy >= threshold_gev) if threshold_gev > 0 else (layer_energy > 0)
        require_positive = (~inactive) & can_resolve
        feasible = feasible & ~(
            require_positive[..., None] & (counts[None, None, :] == 0)
        )
        return logits.masked_fill(~feasible, torch.finfo(logits.dtype).min)

    def sample(
        self,
        cond: torch.Tensor,
        layer_energy: torch.Tensor,
        active_layers: torch.Tensor,
        threshold_gev: float = 0.0,
        stochastic: bool = True,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        logits = self.logits(cond, layer_energy, active_layers, threshold_gev)
        if stochastic:
            flat = torch.distributions.Categorical(
                logits=logits.reshape(-1, logits.shape[-1])
            ).sample()
            counts = flat.reshape(logits.shape[:-1])
        else:
            counts = logits.argmax(dim=-1)
        return counts.long(), logits
