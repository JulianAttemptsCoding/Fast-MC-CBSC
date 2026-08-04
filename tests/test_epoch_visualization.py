from __future__ import annotations

from pathlib import Path

import pytest
import torch

from cbsc_zdc.data.dataset import load_geometry
from cbsc_zdc.data.split import create_split
from cbsc_zdc.data.synthetic import create_synthetic_dataset
from cbsc_zdc.eval.visualization import (
    export_epoch_visualization,
    fixed_validation_indices,
)
from cbsc_zdc.models.system import CBSCZDC
from cbsc_zdc.training.weights import DEFAULT_LOSS_WEIGHTS
from cbsc_zdc.utils import load_json


def _config(created: dict, splits: Path) -> dict:
    return {
        "project": {"name": "visualization-test", "run_dir": "unused"},
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
            "n_layers": 4,
        },
        "model": {
            "condition_dim": 16,
            "hidden_dim": 16,
            "response_hidden": 24,
            "response_components": 2,
            "response_scale_gev": 10.0,
            "profile_hidden": 16,
            "count_hidden": 24,
            "graph_blocks": 1,
            "attention_heads": 4,
            "attention_layers": 1,
            "layer_context": "bidirectional",
            "dropout": 0.0,
        },
        "training": {
            "stage": "joint",
            "seed": 7,
            "batch_size": 2,
            "gradient_accumulation": 1,
            "epochs": 1,
        },
        "loss_weights": dict(DEFAULT_LOSS_WEIGHTS),
        "evaluation": {
            "profile_steps": 1,
            "share_steps": 1,
            "closure_tolerance_gev": 2e-5,
            "visualization": {
                "enabled": True,
                "split": "validation",
                "sample_count": 4,
                "draws_per_condition": 2,
                "selection_seed": 11,
                "generation_seed": 13,
                "required": True,
            },
        },
    }


def test_fixed_validation_indices_are_unique_and_reproducible() -> None:
    first = fixed_validation_indices(100, 50, 19)
    second = fixed_validation_indices(100, 50, 19)
    assert first == second
    assert len(first) == len(set(first)) == 50


def test_epoch_visualization_exports_same_p4_five_draw_contract(tmp_path: Path) -> None:
    created = create_synthetic_dataset(
        tmp_path / "synthetic",
        n_events=256,
        n_layers=4,
        nodes_per_layer=4,
        shard_size=64,
        seed=5,
    )
    splits = tmp_path / "synthetic" / "splits.json"
    create_split(created["manifest"], splits, seed=17, group_by="source_group")
    config = _config(created, splits)
    geometry = load_geometry(created["geometry"])
    model = CBSCZDC(geometry, config).eval()
    checkpoint = tmp_path / "last.pt"
    torch.save({"synthetic_test_only": True}, checkpoint)

    result = export_epoch_visualization(
        model,
        config,
        epoch=0,
        destination=tmp_path / "visualization",
        checkpoint_path=checkpoint,
    )

    artifact = load_json(tmp_path / "visualization" / "epoch_0000.json")
    assert result["qa_pass"]
    assert artifact["split"] == "validation"
    assert artifact["qa"]["test_events_used"] == 0
    assert artifact["qa"]["pass"]
    assert artifact["qa"]["invariants"]["pass"]
    assert artifact["sample_count"] == 4
    assert artifact["draws_per_condition"] == 2
    assert all(len(group["fast_mc"]) == 2 for group in artifact["groups"])
    assert all(len(group["p4_total_gev"]) == 4 for group in artifact["groups"])
    assert "component-stage" not in artifact["scientific_status"]


def test_epoch_visualization_writes_evidence_when_invariants_fail(
    tmp_path: Path,
) -> None:
    created = create_synthetic_dataset(
        tmp_path / "synthetic",
        n_events=256,
        n_layers=4,
        nodes_per_layer=4,
        shard_size=64,
        seed=5,
    )
    splits = tmp_path / "synthetic" / "splits.json"
    create_split(created["manifest"], splits, seed=17, group_by="source_group")
    config = _config(created, splits)
    # Force the existing invariant decision to fail without changing its
    # implementation. The production threshold remains untouched.
    config["evaluation"]["closure_tolerance_gev"] = -1.0
    geometry = load_geometry(created["geometry"])
    model = CBSCZDC(geometry, config).eval()
    checkpoint = tmp_path / "last.pt"
    torch.save({"synthetic_test_only": True}, checkpoint)
    destination = tmp_path / "visualization"

    with pytest.raises(
        RuntimeError,
        match="epoch 7 visualization generation failed structural invariants",
    ):
        export_epoch_visualization(
            model,
            config,
            epoch=7,
            destination=destination,
            checkpoint_path=checkpoint,
        )

    evidence = load_json(destination / "invariant_failure_epoch_0007.json")
    assert evidence["kind"] == "cbsc-zdc-epoch-visualization-invariant-failure"
    assert evidence["scientific_status"].startswith("artifact quarantined")
    assert evidence["split"] == "validation"
    assert evidence["test_events_used"] == 0
    assert evidence["tolerance_gev"] == -1.0
    assert not evidence["invariants"]["pass"]
    assert len(evidence["checkpoint_sha256"]) == 64
    assert len(evidence["rows"]) == 4
    assert [row["selection_position"] for row in evidence["rows"]] == list(range(4))
    assert all("dataset_index" in row for row in evidence["rows"])
    assert all("global_index" in row for row in evidence["rows"])
    assert all("event_id" in row for row in evidence["rows"])
    assert all("generation_seed" in row for row in evidence["rows"])
    assert all("kinetic_energy_gev" in row for row in evidence["rows"])
    assert not (destination / "epoch_0007.json").exists()
