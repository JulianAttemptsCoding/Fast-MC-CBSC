from pathlib import Path

import pytest
import yaml

from cbsc_zdc.config import validate_config
from cbsc_zdc.training.weights import DEFAULT_LOSS_WEIGHTS


def base():
    return {
        "project": {},
        "data": {
            "target_mode": "raw_deposit",
            "threshold_gev": 0.0,
            "split_fraction": [0.8, 0.1, 0.1],
            "train_kinetic_gev": [0.0, 300.0],
            "evaluation_kinetic_gev": [50.0, 250.0],
        },
        "geometry": {"n_nodes": 10, "n_layers": 2},
        "model": {},
        "training": {
            "stage": "joint",
            "batch_size": 2,
            "gradient_accumulation": 1,
            "epochs": 1,
        },
        "loss_weights": dict(DEFAULT_LOSS_WEIGHTS),
        "evaluation": {},
    }


def test_valid_raw_config():
    validate_config(base())


def test_raw_mode_rejects_threshold():
    cfg = base()
    cfg["data"]["threshold_gev"] = 0.1
    with pytest.raises(ValueError):
        validate_config(cfg)


def test_negative_weight_rejected():
    cfg = base()
    cfg["loss_weights"]["visible"] = -1
    with pytest.raises(ValueError):
        validate_config(cfg)


def test_validate_config_rejects_missing_loss_key():
    config = yaml.safe_load(
        (Path(__file__).parents[1] / "configs/templates/train_full_0_300_raw.yaml").read_text()
    )
    config["loss_weights"].pop("share_flow")
    with pytest.raises(ValueError, match="loss_weights keys mismatch"):
        validate_config(config)


def test_epoch_visualization_rejects_test_split():
    cfg = base()
    cfg["evaluation"]["visualization"] = {
        "enabled": True,
        "split": "test",
        "sample_count": 50,
        "draws_per_condition": 5,
    }
    with pytest.raises(ValueError, match="test is forbidden"):
        validate_config(cfg)


def test_epoch_visualization_bounds_sample_and_draw_counts():
    cfg = base()
    cfg["evaluation"]["visualization"] = {
        "enabled": True,
        "split": "validation",
        "sample_count": 201,
        "draws_per_condition": 5,
    }
    with pytest.raises(ValueError, match="sample_count"):
        validate_config(cfg)
    cfg["evaluation"]["visualization"]["sample_count"] = 50
    cfg["evaluation"]["visualization"]["draws_per_condition"] = 11
    with pytest.raises(ValueError, match="draws_per_condition"):
        validate_config(cfg)


def test_scheduler_restart_requires_paired_resume():
    cfg = base()
    cfg["training"]["restart_scheduler_on_resume"] = True
    with pytest.raises(ValueError, match="requires resume_from"):
        validate_config(cfg)

    cfg["training"].update(
        {
            "resume_from_relative": "checkpoints/last.pt",
            "resume_from_sha256": "a" * 64,
            "resume_best_from_relative": "checkpoints/best.pt",
            "resume_best_from_sha256": "b" * 64,
        }
    )
    validate_config(cfg)
