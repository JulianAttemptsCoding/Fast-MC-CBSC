"""Architecture-version compatibility between v2.2 and v3.

The binding requirement is that no existing frozen v2.2 configuration changes
meaning.  Absence of ``model.architecture_version`` means ``cbsc-zdc-v2.2``, and
the loss-weight schema is selected by architecture version rather than being
widened for everyone.
"""

from __future__ import annotations

import pytest

from cbsc_zdc.config import (
    ARCHITECTURE_V2_2,
    ARCHITECTURE_V3,
    EXPECTED_LOSS_WEIGHTS,
    V3_LOSS_WEIGHTS,
    architecture_version,
    expected_loss_weights,
    validate_config,
)
from cbsc_zdc.training.weights import DEFAULT_LOSS_WEIGHTS


def base() -> dict:
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


def v3_base() -> dict:
    config = base()
    config["model"]["architecture_version"] = ARCHITECTURE_V3
    config["loss_weights"] = {name: 1.0 for name in V3_LOSS_WEIGHTS}
    return config


def test_old_config_without_architecture_version_selects_v2_2() -> None:
    config = base()
    assert "architecture_version" not in config["model"]
    assert architecture_version(config) == ARCHITECTURE_V2_2
    validate_config(config)


def test_old_loss_key_set_is_unchanged() -> None:
    # The v2.2 schema is frozen.  If this set ever changes, every historical
    # frozen config silently changes meaning.
    assert EXPECTED_LOSS_WEIGHTS == {
        "visible",
        "response",
        "first_layer",
        "active",
        "profile_flow",
        "count",
        "support_bce",
        "support_rank",
        "share_flow",
    }
    assert expected_loss_weights(ARCHITECTURE_V2_2) == EXPECTED_LOSS_WEIGHTS
    validate_config(base())


def test_v3_loss_key_set_is_version_selected() -> None:
    assert expected_loss_weights(ARCHITECTURE_V3) == V3_LOSS_WEIGHTS
    # v3 adds heads that v2.2 does not have, and keeps every v2.2 component.
    assert EXPECTED_LOSS_WEIGHTS < V3_LOSS_WEIGHTS
    for added in ("ecal_start", "hcal_first", "active_last", "active_gap"):
        assert added in V3_LOSS_WEIGHTS
    validate_config(v3_base())


def test_a_v2_config_carrying_v3_only_loss_keys_is_rejected() -> None:
    config = base()
    config["loss_weights"]["ecal_start"] = 1.0
    with pytest.raises(ValueError, match="loss_weights"):
        validate_config(config)


def test_a_v3_config_missing_a_v3_loss_key_is_rejected() -> None:
    config = v3_base()
    del config["loss_weights"]["ecal_start"]
    with pytest.raises(ValueError, match="loss_weights"):
        validate_config(config)


def test_an_unknown_architecture_version_is_rejected() -> None:
    config = base()
    config["model"]["architecture_version"] = "cbsc-zdc-v9"
    with pytest.raises(ValueError, match="architecture_version"):
        validate_config(config)


def test_v3_support_temperature_must_be_finite_and_positive() -> None:
    for bad in (0.0, -1.0, float("inf"), float("nan")):
        config = v3_base()
        config["model"]["support_temperature"] = bad
        with pytest.raises(ValueError, match="support_temperature"):
            validate_config(config)


def test_v3_activity_mode_is_restricted_to_the_declared_pair() -> None:
    for good in ("span_gaps", "autoregressive"):
        config = v3_base()
        config["model"]["activity_mode"] = good
        validate_config(config)
    config = v3_base()
    config["model"]["activity_mode"] = "something_else"
    with pytest.raises(ValueError, match="activity_mode"):
        validate_config(config)


def test_v2_config_ignores_v3_only_model_keys_for_schema_selection() -> None:
    # A v2.2 config that happens to carry an unrelated model key is still v2.2
    # and still validates against the frozen v2.2 loss schema.
    config = base()
    config["model"]["support_temperature"] = 0.25
    assert architecture_version(config) == ARCHITECTURE_V2_2
    validate_config(config)
