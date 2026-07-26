from __future__ import annotations

import torch
from torch import nn


class EdgeMessageBlock(nn.Module):
    """Residual edge-conditioned message passing using only core PyTorch operations.

    The geometry builder, not this block, is responsible for supplying physically valid
    lateral and directed longitudinal edges. Edge processing is chunked to limit memory.
    """

    def __init__(
        self,
        hidden: int,
        edge_dim: int,
        message_hidden: int | None = None,
        edge_chunk_size: int = 16384,
    ):
        super().__init__()
        message_hidden = message_hidden or hidden * 2
        self.edge_dim = edge_dim
        self.edge_chunk_size = edge_chunk_size
        self.message = nn.Sequential(
            nn.Linear(hidden * 2 + edge_dim, message_hidden),
            nn.SiLU(),
            nn.Linear(message_hidden, hidden),
        )
        self.update = nn.Sequential(
            nn.LayerNorm(hidden * 2),
            nn.Linear(hidden * 2, hidden * 2),
            nn.SiLU(),
            nn.Linear(hidden * 2, hidden),
        )

    def forward(
        self,
        h: torch.Tensor,
        edge_index: torch.Tensor,
        edge_features: torch.Tensor,
    ) -> torch.Tensor:
        if edge_index.ndim != 2 or edge_index.shape[0] != 2:
            raise ValueError("edge_index must have shape [2,E]")
        if edge_features.shape != (edge_index.shape[1], self.edge_dim):
            raise ValueError("edge feature shape mismatch")
        batch, n_nodes, hidden = h.shape
        if edge_index.numel() and (
            edge_index.min() < 0 or edge_index.max() >= n_nodes
        ):
            raise ValueError("edge_index contains an invalid node id")

        aggregate = torch.zeros_like(h)
        source_all, target_all = edge_index
        for start in range(0, edge_index.shape[1], self.edge_chunk_size):
            stop = min(start + self.edge_chunk_size, edge_index.shape[1])
            source = source_all[start:stop]
            target = target_all[start:stop]
            edge = edge_features[start:stop][None].expand(batch, -1, -1)
            msg = self.message(
                torch.cat((h[:, source], h[:, target], edge), dim=-1)
            )
            aggregate.index_add_(1, target, msg)
        return h + self.update(torch.cat((h, aggregate), dim=-1))
