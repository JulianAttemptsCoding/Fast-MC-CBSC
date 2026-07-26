from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

import torch

from cbsc_zdc.data.dataset import load_geometry
from cbsc_zdc.data.split import create_split
from cbsc_zdc.data.synthetic import create_synthetic_dataset
from cbsc_zdc.eval.visualization import export_epoch_visualization
from cbsc_zdc.models.system import CBSCZDC
from cbsc_zdc.training.weights import DEFAULT_LOSS_WEIGHTS


def _config(created: dict, splits: Path) -> dict:
    return {
        "project": {"name": "dashboard-interface-fixture", "run_dir": "unused"},
        "data": {
            "manifest": created["manifest"],
            "splits": str(splits),
            "target_mode": "raw_deposit",
            "threshold_gev": 0.0,
            "train_kinetic_gev": [0.0, 300.0],
            "evaluation_kinetic_gev": [50.0, 250.0],
            "split_fraction": [0.8, 0.1, 0.1],
            "response_cap_ratio": 2.0,
            "response_cap_absolute_gev": 500.0,
        },
        "geometry": {
            "path": created["geometry"],
            "n_nodes": created["n_nodes"],
            "n_layers": 8,
        },
        "model": {
            "condition_dim": 24,
            "hidden_dim": 24,
            "response_hidden": 32,
            "response_components": 2,
            "response_scale_gev": 10.0,
            "profile_hidden": 24,
            "count_hidden": 32,
            "graph_blocks": 1,
            "attention_heads": 4,
            "attention_layers": 1,
            "layer_context": "bidirectional",
            "dropout": 0.0,
        },
        "training": {
            "stage": "joint",
            "seed": 20260725,
            "batch_size": 4,
            "gradient_accumulation": 1,
            "epochs": 1,
        },
        "loss_weights": dict(DEFAULT_LOSS_WEIGHTS),
        "evaluation": {
            "profile_steps": 2,
            "share_steps": 2,
            "closure_tolerance_gev": 2e-5,
            "visualization": {
                "enabled": True,
                "split": "validation",
                "sample_count": 12,
                "draws_per_condition": 5,
                "selection_seed": 20260725,
                "generation_seed": 20260725,
                "required": True,
            },
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a clearly labeled synthetic fixture for dashboard UI QA"
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="cbsc_zdc_dashboard_fixture_") as temporary:
        root = Path(temporary)
        created = create_synthetic_dataset(
            root,
            n_events=512,
            n_layers=8,
            nodes_per_layer=25,
            shard_size=128,
            seed=20260725,
        )
        splits = root / "splits.json"
        create_split(created["manifest"], splits, seed=20260725, group_by="source_group")
        config = _config(created, splits)
        model = CBSCZDC(load_geometry(created["geometry"]), config).eval()
        checkpoint = root / "synthetic_untrained_checkpoint.pt"
        torch.save({"synthetic_interface_fixture_only": True}, checkpoint)
        export_epoch_visualization(
            model,
            config,
            epoch=0,
            destination=args.output,
            checkpoint_path=checkpoint,
        )


if __name__ == "__main__":
    main()
