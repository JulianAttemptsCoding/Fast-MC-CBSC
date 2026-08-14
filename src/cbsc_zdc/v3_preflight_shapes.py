"""Production-shaped synthetic geometry for bounded v3 preflight measurement.

Shared by ``scripts/v3_resource_preflight.py`` and ``scripts/v3_resume_soak.py``
so both measure the same thing.

The node and edge *features* here are synthetic.  What matters for memory and
timing -- and what is reproduced exactly -- is the shape: 6,790 channels split
400 ECAL plus 6,390 HCAL across 65 layers, with a realistic intra-layer edge
count.  This module never reads the production dataset and never constructs a
data loader of any split.
"""

from __future__ import annotations

import torch

from .models.system import CBSCZDC

N_NODES = 6790
N_LAYERS = 65
ECAL_CHANNELS = 400
COND_DIM = 128
NEUTRON_MASS_GEV = 0.93956542052


def production_geometry(device: torch.device | None = None) -> dict[str, torch.Tensor]:
    hcal_per_layer = (N_NODES - ECAL_CHANNELS) // (N_LAYERS - 1)
    layer_index = torch.cat(
        [torch.zeros(ECAL_CHANNELS, dtype=torch.long)]
        + [torch.full((hcal_per_layer,), i, dtype=torch.long) for i in range(1, N_LAYERS)]
    )
    remainder = N_NODES - layer_index.numel()
    if remainder > 0:
        layer_index = torch.cat(
            [layer_index, torch.full((remainder,), N_LAYERS - 1, dtype=torch.long)]
        )
    layer_index = layer_index[:N_NODES]

    src, dst = [], []
    for layer in range(N_LAYERS):
        ids = torch.nonzero(layer_index == layer).flatten().tolist()
        for offset in (1, 2, 3):
            for i, node in enumerate(ids):
                neighbour = ids[(i + offset) % len(ids)]
                src.extend((node, neighbour))
                dst.extend((neighbour, node))
    edge_index = torch.tensor([src, dst], dtype=torch.long)

    geometry = {
        "node_features": torch.randn(N_NODES, 8),
        "layer_index": layer_index,
        "valid_mask": torch.ones(N_NODES, dtype=torch.bool),
        "edge_index": edge_index,
        "edge_features": torch.randn(edge_index.shape[1], 4),
    }
    if device is not None:
        geometry = {k: v.to(device) for k, v in geometry.items()}
    return geometry


def build_model(geometry: dict[str, torch.Tensor], device: torch.device) -> CBSCZDC:
    config = {
        "model": {
            "condition_dim": COND_DIM, "hidden_dim": 96, "graph_blocks": 3,
            "attention_heads": 4, "attention_layers": 2, "profile_hidden": 128,
            "count_hidden": 192, "response_hidden": 192,
        },
        "data": {"target_mode": "raw_deposit", "threshold_gev": 0.0},
    }
    return CBSCZDC({k: v.to(device) for k, v in geometry.items()}, config).to(device)
