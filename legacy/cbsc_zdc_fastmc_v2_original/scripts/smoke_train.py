"""Run one synthetic forward sample and print algebraic invariant diagnostics."""

from __future__ import annotations

import argparse
from pathlib import Path

import torch
import yaml

from cbsc_zdc.eval.diagnostics import invariant_report
from cbsc_zdc.models.system import CBSCZDC

NEUTRON_MASS_GEV = 0.93956542052


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("configs/pilot.yaml"))
    parser.add_argument(
        "--nodes",
        type=int,
        default=None,
        help="Optional smaller synthetic node count; must be at least the layer count.",
    )
    parser.add_argument("--steps", type=int, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with args.config.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)

    n_layers = int(config["detector"]["n_layers"])
    n_nodes = int(args.nodes or config["detector"]["n_nodes"])
    if n_nodes < n_layers:
        raise ValueError("synthetic node count must be at least the layer count")
    steps = int(args.steps or config["sampling"]["steps"])

    layer_index = torch.arange(n_nodes) % n_layers
    node_features = torch.randn(n_nodes, 8)
    valid_mask = torch.ones(n_nodes, dtype=torch.bool)
    model = CBSCZDC(
        node_features,
        layer_index,
        valid_mask,
        cond_dim=int(config["model"]["condition_dim"]),
        latent_dim=int(config["model"]["event_latent_dim"]),
    ).eval()

    momentum = torch.tensor([[0.0, 0.0, 99.995586]])
    energy = torch.sqrt(momentum.square().sum(dim=-1) + NEUTRON_MASS_GEV**2).unsqueeze(-1)
    p4 = torch.cat((energy, momentum), dim=-1)
    output = model.sample(p4, steps=steps, seed=7)
    print(invariant_report(p4, output, layer_index=layer_index))


if __name__ == "__main__":
    main()
