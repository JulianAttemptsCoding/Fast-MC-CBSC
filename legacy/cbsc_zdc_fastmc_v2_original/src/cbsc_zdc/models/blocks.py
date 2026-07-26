from __future__ import annotations

import torch
from torch import nn


class ResidualMLP(nn.Module):
    def __init__(self, dim: int, hidden: int, blocks: int = 2):
        super().__init__()
        self.blocks = nn.ModuleList(
            [
                nn.Sequential(
                    nn.LayerNorm(dim),
                    nn.Linear(dim, hidden),
                    nn.SiLU(),
                    nn.Linear(hidden, dim),
                )
                for _ in range(blocks)
            ]
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        for block in self.blocks:
            x = x + block(x)
        return x


class ConditionEncoder(nn.Module):
    def __init__(self, out_dim: int = 128):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(4, out_dim),
            nn.SiLU(),
            ResidualMLP(out_dim, out_dim * 2, 2),
            nn.LayerNorm(out_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class FiLM(nn.Module):
    def __init__(self, cond_dim: int, feat_dim: int):
        super().__init__()
        self.proj = nn.Linear(cond_dim, feat_dim * 2)

    def forward(self, x: torch.Tensor, condition: torch.Tensor) -> torch.Tensor:
        gain, bias = self.proj(condition).chunk(2, dim=-1)
        while gain.ndim < x.ndim:
            gain = gain.unsqueeze(1)
            bias = bias.unsqueeze(1)
        return x * (1 + gain) + bias
