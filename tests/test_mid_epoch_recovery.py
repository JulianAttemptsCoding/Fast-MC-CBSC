from __future__ import annotations

import csv
from pathlib import Path

import torch

from cbsc_zdc.data.split import create_split
from cbsc_zdc.data.synthetic import create_synthetic_dataset
from cbsc_zdc.training.trainer import train_from_config
from cbsc_zdc.training.weights import DEFAULT_LOSS_WEIGHTS
from cbsc_zdc.utils import load_json, sha256_file


class _IntentionalInterruption(RuntimeError):
    pass


def _frozen_config(
    created: dict,
    splits_path: Path,
    run_dir: Path,
) -> dict:
    geometry_dir = Path(created["geometry"])
    manifest_path = Path(created["manifest"])
    split_manifest = load_json(splits_path)
    assignment_path = splits_path.parent / split_manifest["assignment_file"]
    dataset_manifest = load_json(manifest_path)
    return {
        "project": {
            "name": "mid-epoch-recovery-test",
            "run_dir": str(run_dir),
            "pilot": True,
        },
        "data": {
            "manifest": str(manifest_path),
            "splits": str(splits_path),
            "target_mode": "raw_deposit",
            "threshold_gev": 0.0,
            "train_kinetic_gev": [0.0, 300.0],
            "evaluation_kinetic_gev": [0.0, 300.0],
            "split_fraction": [0.8, 0.1, 0.1],
            "response_cap_ratio": 2.0,
            "response_cap_absolute_gev": 500.0,
        },
        "geometry": {
            "path": str(geometry_dir),
            "n_nodes": int(created["n_nodes"]),
            "n_layers": 4,
            "geometry_hash": dataset_manifest["geometry_hash"],
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
            "stage": "response",
            "seed": 37,
            "device": "cpu",
            "batch_size": 8,
            "gradient_accumulation": 2,
            "num_workers": 0,
            "epochs": 1,
            "learning_rate": 1e-3,
            "min_learning_rate": 1e-5,
            "betas": [0.9, 0.999],
            "eps": 1e-8,
            "weight_decay": 0.01,
            "gradient_clip_norm": 1.0,
            "amp": False,
            "deterministic_debug": True,
            "early_stopping_patience": 2,
            "initialize_from": None,
            "resume_from": None,
            "train_condition_encoder": True,
            "checkpoint_interval_updates": 0,
        },
        "loss_weights": dict(DEFAULT_LOSS_WEIGHTS),
        "evaluation": {
            "profile_steps": 1,
            "share_steps": 1,
            "closure_tolerance_gev": 2e-5,
        },
        "provenance": {
            "geometry_manifest_sha256": sha256_file(
                geometry_dir / "geometry_manifest.json"
            ),
            "dataset_manifest_sha256": sha256_file(manifest_path),
            "split_manifest_sha256": sha256_file(splits_path),
            "dataset_geometry_hash": dataset_manifest["geometry_hash"],
            "split_assignment_sha256": sha256_file(assignment_path),
        },
    }


def _checkpoint_model_state(path: Path) -> dict[str, torch.Tensor]:
    payload = torch.load(path, map_location="cpu", weights_only=False)
    return payload["model_state"]


def test_mid_epoch_interruption_resume_matches_uninterrupted_training(
    tmp_path: Path,
) -> None:
    created = create_synthetic_dataset(
        tmp_path / "synthetic",
        n_events=160,
        n_layers=4,
        nodes_per_layer=4,
        shard_size=40,
        seed=29,
    )
    splits_path = tmp_path / "synthetic" / "splits.json"
    create_split(
        created["manifest"],
        splits_path,
        fractions=(0.8, 0.1, 0.1),
        seed=31,
        group_by="event_hash",
    )

    uninterrupted = _frozen_config(
        created, splits_path, tmp_path / "uninterrupted"
    )
    uninterrupted_result = train_from_config(uninterrupted)

    interrupted = _frozen_config(
        created, splits_path, tmp_path / "interrupted"
    )
    interrupted["training"]["checkpoint_interval_updates"] = 1

    def stop_after_first_snapshot(progress, run, path):
        assert int(progress["next_step"]) == 2
        assert path == run.checkpoints / "progress.pt"
        raise _IntentionalInterruption("simulated worker interruption")

    try:
        train_from_config(
            interrupted,
            progress_callback=stop_after_first_snapshot,
        )
    except _IntentionalInterruption:
        pass
    else:
        raise AssertionError("training did not reach the interruption callback")

    progress_path = tmp_path / "interrupted" / "checkpoints" / "progress.pt"
    assert progress_path.is_file()
    progress_payload = torch.load(
        progress_path, map_location="cpu", weights_only=False
    )
    assert progress_payload["progress"]["optimizer_boundary"] is True
    assert int(progress_payload["progress"]["next_step"]) == 2
    assert int(progress_payload["progress"]["train_count"]) == 2

    resumed = _frozen_config(created, splits_path, tmp_path / "resumed")
    resumed["training"]["resume_progress_from"] = str(progress_path)
    resumed_result = train_from_config(resumed)

    uninterrupted_state = _checkpoint_model_state(
        Path(uninterrupted_result["last_checkpoint"])
    )
    resumed_state = _checkpoint_model_state(Path(resumed_result["last_checkpoint"]))
    assert uninterrupted_state.keys() == resumed_state.keys()
    assert all(
        torch.equal(uninterrupted_state[name], resumed_state[name])
        for name in uninterrupted_state
    )

    with (
        (tmp_path / "uninterrupted/logs/history.csv").open(
            newline="", encoding="utf-8"
        ) as first_handle,
        (tmp_path / "resumed/logs/history.csv").open(
            newline="", encoding="utf-8"
        ) as second_handle,
    ):
        first = list(csv.DictReader(first_handle))
        second = list(csv.DictReader(second_handle))
    assert len(first) == len(second) == 1
    for field in (
        "train_loss",
        "validation_loss",
        "learning_rate",
        "train_visible",
        "train_response",
    ):
        assert first[0][field] == second[0][field]
    assert int(uninterrupted_result["updates"]) == int(resumed_result["updates"])
    assert not (tmp_path / "resumed/checkpoints/progress.pt").exists()
