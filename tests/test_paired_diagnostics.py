from __future__ import annotations

from pathlib import Path

import numpy as np
import torch

from cbsc_zdc.cloud.paired_diagnostics import (
    generate_paired_sample,
    hcal_summary,
    load_model,
    split_counts,
)
from cbsc_zdc.data.dataset import ShardedSparseDataset, load_geometry
from cbsc_zdc.data.split import create_split
from cbsc_zdc.data.synthetic import create_synthetic_dataset
from cbsc_zdc.eval.visualization import fixed_validation_indices
from cbsc_zdc.models.system import CBSCZDC
from cbsc_zdc.training.weights import DEFAULT_LOSS_WEIGHTS


def _config(created: dict) -> dict:
    return {
        "data": {
            "target_mode": "raw_deposit",
            "threshold_gev": 0.0,
            "response_cap_ratio": 2.0,
            "response_cap_absolute_gev": 500.0,
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
        "loss_weights": dict(DEFAULT_LOSS_WEIGHTS),
    }


def _build(tmp_path: Path):
    created = create_synthetic_dataset(
        tmp_path / "synthetic", n_events=200, n_layers=4, nodes_per_layer=4,
        shard_size=37, seed=3,
    )
    splits = tmp_path / "synthetic" / "splits.json"
    create_split(created["manifest"], splits, seed=17, group_by="source_group")
    config = _config(created)
    geometry = load_geometry(created["geometry"])
    model = CBSCZDC(geometry, config).eval()
    checkpoint = tmp_path / "checkpoint.pt"
    torch.save({"config": config, "model_state": model.state_dict()}, checkpoint)
    return created, splits, geometry, checkpoint


def test_load_model_round_trips_state_dict(tmp_path: Path) -> None:
    _created, _splits, geometry, checkpoint = _build(tmp_path)
    model = load_model(checkpoint, geometry, torch.device("cpu"))
    assert isinstance(model, CBSCZDC)
    assert model.n_nodes == geometry["node_features"].shape[0]


def test_generate_paired_sample_and_hcal_summary_end_to_end(tmp_path: Path) -> None:
    created, splits, geometry, checkpoint = _build(tmp_path)
    model = load_model(checkpoint, geometry, torch.device("cpu"))

    full = ShardedSparseDataset(created["manifest"], None, None, None, created["n_nodes"])
    total_events = len(full)
    assert total_events == 200

    selected = fixed_validation_indices(total_events, 30, seed=5)
    full.indices = np.asarray(sorted(selected), dtype=np.int64)

    sample = generate_paired_sample(full, model, torch.device("cpu"), seed=5, batch_size=8)
    assert sample["truth_cell_energy_gev"].shape == (30, created["n_nodes"])
    assert sample["generated_cell_energy_gev"].shape == (30, created["n_nodes"])
    assert sample["p4_total_gev"].shape == (30, 4)
    expected_p4 = np.stack([full[i]["p4_total_gev"].numpy() for i in range(len(full))])
    np.testing.assert_array_equal(sample["p4_total_gev"], expected_p4)
    assert len(set(sample["global_index"].tolist())) == 30

    n_ecal = int((geometry["subdetector"] == 0).sum())
    truth_hcal = hcal_summary(sample["truth_cell_energy_gev"], n_ecal, created["n_nodes"])
    generated_hcal = hcal_summary(sample["generated_cell_energy_gev"], n_ecal, created["n_nodes"])
    # HCAL-only: fewer columns summed than the whole detector, never negative.
    assert (truth_hcal["total"] >= 0).all()
    assert (generated_hcal["total"] >= 0).all()
    assert (truth_hcal["hits"] >= 0).all()
    # A zero-hit HCAL event must not crash the positive-cell pooling.
    assert truth_hcal["positive_cells"].ndim == 1

    import json

    manifest = json.loads(splits.read_text("utf-8"))
    assignment = np.load(splits.parent / manifest["assignment_file"])["split_code"]
    counts = split_counts(sample["global_index"], assignment)
    assert sum(counts.values()) == 30
    assert set(counts) == {"train", "validation", "test"}


def test_hcal_summary_handles_an_all_zero_event() -> None:
    cell = np.zeros((3, 20), dtype=np.float32)
    cell[0, 5] = 1.5  # only the first event has any HCAL energy
    summary = hcal_summary(cell, n_ecal=4, n_nodes=20)
    assert summary["total"].tolist() == [1.5, 0.0, 0.0]
    assert summary["hits"].tolist() == [1, 0, 0]
    assert summary["positive_cells"].tolist() == [1.5]
