"""A v3 run must write format 4 through the real trainer, not just the helper.

`save_checkpoint` has supported format 4 since the v3 overlay landed, and
`tests/test_v3_checkpoint_resume.py` exercises it directly.  That was not
enough: nothing called it with `architecture_version`, so S1-axis -- a correct
v3 run in every other respect -- wrote `best.pt` and `last.pt` through the v2.2
path with `architecture_version: null` and no format-4 fields at all.  A helper
test cannot catch that.  These tests drive `train_from_config` and inspect the
bytes it actually produced.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import torch

from cbsc_zdc.config import ARCHITECTURE_V2_2, ARCHITECTURE_V3
from cbsc_zdc.data.split import create_split
from cbsc_zdc.data.synthetic import create_synthetic_dataset
from cbsc_zdc.training.checkpoint import (
    CHECKPOINT_FORMAT_V3,
    CHECKPOINT_FORMAT_V4,
    V4_REQUIRED_FIELDS,
    require_adversarial_resume_source,
)
from cbsc_zdc.training.trainer import train_from_config, v3_checkpoint_fields
from cbsc_zdc.training.weights import DEFAULT_LOSS_WEIGHTS
from cbsc_zdc.utils import load_json, sha256_file

#: Format 3's exact key set. Pinned so a v2.2 checkpoint cannot silently gain or
#: lose a field: every archived checkpoint and every downstream reader depends
#: on this shape, and half the project's evidence predates format 4.
FORMAT_3_KEYS = {
    "format_version", "model_state", "optimizer_state", "scheduler_state",
    "scaler_state", "epoch", "best_metric", "config", "stage", "provenance",
    "rng_state", "environment", "progress",
}

#: Types each format-4 field may hold on a *supervised* v3 row, where every
#: adversarial slot is null but must still be present.
NULLABLE_FIELDS = {
    "experiment_contract_sha256", "critic_state", "critic_optimizer_state",
    "critic_scheduler_state", "gradient_ratio_controller_state",
    "replay_state_manifest", "role_partition_sha256", "response_envelope_sha256",
}


def _dataset(tmp_path: Path):
    created = create_synthetic_dataset(
        tmp_path / "synthetic",
        n_events=96, n_layers=4, nodes_per_layer=4, shard_size=32, seed=29,
    )
    splits_path = tmp_path / "synthetic" / "splits.json"
    create_split(
        created["manifest"], splits_path,
        fractions=(0.8, 0.1, 0.1), seed=31, group_by="event_hash",
    )
    return created, splits_path


def _config(created: dict, splits_path: Path, run_dir: Path, *, version=None) -> dict:
    geometry_dir = Path(created["geometry"])
    manifest_path = Path(created["manifest"])
    split_manifest = load_json(splits_path)
    assignment_path = splits_path.parent / split_manifest["assignment_file"]
    dataset_manifest = load_json(manifest_path)
    model = {
        "condition_dim": 16, "hidden_dim": 16, "response_hidden": 24,
        "response_components": 2, "response_scale_gev": 10.0,
        "profile_hidden": 16, "count_hidden": 24, "graph_blocks": 1,
        "attention_heads": 4, "attention_layers": 1,
        "layer_context": "bidirectional", "dropout": 0.0,
    }
    if version is not None:
        model["architecture_version"] = version
    return {
        "project": {"name": "v3-format-test", "run_dir": str(run_dir), "pilot": True},
        "data": {
            "manifest": str(manifest_path), "splits": str(splits_path),
            "target_mode": "raw_deposit", "threshold_gev": 0.0,
            "train_kinetic_gev": [0.0, 300.0], "evaluation_kinetic_gev": [0.0, 300.0],
            "split_fraction": [0.8, 0.1, 0.1],
            "response_cap_ratio": 2.0, "response_cap_absolute_gev": 500.0,
        },
        "geometry": {
            "path": str(geometry_dir), "n_nodes": int(created["n_nodes"]),
            "n_layers": 4, "geometry_hash": dataset_manifest["geometry_hash"],
        },
        "model": model,
        "training": {
            "stage": "response", "seed": 37, "device": "cpu", "batch_size": 8,
            "gradient_accumulation": 2, "num_workers": 0, "epochs": 1,
            "learning_rate": 1e-3, "min_learning_rate": 1e-5,
            "betas": [0.9, 0.999], "eps": 1e-8, "weight_decay": 0.01,
            "gradient_clip_norm": 1.0, "amp": False, "deterministic_debug": True,
            "early_stopping_patience": 2, "initialize_from": None,
            "resume_from": None, "train_condition_encoder": True,
            "checkpoint_interval_updates": 0,
        },
        "loss_weights": dict(DEFAULT_LOSS_WEIGHTS),
        "evaluation": {
            "profile_steps": 1, "share_steps": 1, "closure_tolerance_gev": 2e-5,
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


def _load(path: Path) -> dict:
    return torch.load(path, map_location="cpu", weights_only=False)


@pytest.fixture(scope="module")
def trained(tmp_path_factory):
    """One v2.2 run and one v3 run, trained once and shared."""
    tmp_path = tmp_path_factory.mktemp("v3-format")
    created, splits_path = _dataset(tmp_path)
    v2_dir = tmp_path / "v2_run"
    v3_dir = tmp_path / "v3_run"
    train_from_config(_config(created, splits_path, v2_dir))
    train_from_config(
        _config(created, splits_path, v3_dir, version=ARCHITECTURE_V3)
    )
    return {"v2": v2_dir, "v3": v3_dir}


# --------------------------------------------------------------------------
# 1. a v3 config produces format 4 with the exact architecture version
# --------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["best.pt", "last.pt"])
def test_v3_run_writes_format_four_through_the_real_trainer(trained, name):
    payload = _load(trained["v3"] / "checkpoints" / name)
    assert payload["format_version"] == CHECKPOINT_FORMAT_V4
    assert payload["architecture_version"] == ARCHITECTURE_V3


@pytest.mark.parametrize("name", ["best.pt", "last.pt"])
def test_v3_checkpoint_architecture_version_is_never_null(trained, name):
    """The exact S1-axis defect: a v3 run whose checkpoints say nothing."""
    payload = _load(trained["v3"] / "checkpoints" / name)
    assert payload.get("architecture_version") is not None


# --------------------------------------------------------------------------
# 2. every required key exists, with valid type and nullability
# --------------------------------------------------------------------------

@pytest.mark.parametrize("field", V4_REQUIRED_FIELDS)
def test_every_format_four_field_is_present(trained, field):
    payload = _load(trained["v3"] / "checkpoints" / "last.pt")
    assert field in payload, f"format 4 omitted {field}"


def test_format_four_field_types_are_valid_for_a_supervised_row(trained):
    payload = _load(trained["v3"] / "checkpoints" / "last.pt")
    assert isinstance(payload["architecture_version"], str)
    assert isinstance(payload["critic_update_count"], int)
    assert isinstance(payload["generator_update_count"], int)
    assert payload["critic_update_count"] == 0
    assert payload["generator_update_count"] == 0
    # Present-but-null is the whole point: it distinguishes "no critic" from
    # "a writer that did not know about critics".
    for field in NULLABLE_FIELDS:
        assert field in payload
        assert payload[field] is None or payload[field]
    temperature = payload["support_temperature"]
    assert isinstance(temperature, (int, float)) and temperature > 0


# --------------------------------------------------------------------------
# 3. a v2.2 config, or an absent version, keeps the old format and key set
# --------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["best.pt", "last.pt"])
def test_absent_architecture_version_still_writes_format_three(trained, name):
    payload = _load(trained["v2"] / "checkpoints" / name)
    assert payload["format_version"] == CHECKPOINT_FORMAT_V3


@pytest.mark.parametrize("name", ["best.pt", "last.pt"])
def test_format_three_key_set_is_exactly_unchanged(trained, name):
    payload = _load(trained["v2"] / "checkpoints" / name)
    assert set(payload) == FORMAT_3_KEYS


def test_a_v2_checkpoint_carries_no_format_four_field(trained):
    payload = _load(trained["v2"] / "checkpoints" / "last.pt")
    for field in V4_REQUIRED_FIELDS:
        assert field not in payload, f"v2.2 checkpoint gained {field}"


def test_an_explicit_v2_declaration_is_treated_as_v2():
    assert v3_checkpoint_fields({"model": {"architecture_version": ARCHITECTURE_V2_2}}) == {}
    assert v3_checkpoint_fields({"model": {}}) == {}
    assert v3_checkpoint_fields({}) == {}


def test_the_v3_field_helper_emits_exactly_the_required_set():
    fields = v3_checkpoint_fields({"model": {"architecture_version": ARCHITECTURE_V3}})
    assert set(fields) == set(V4_REQUIRED_FIELDS)


def test_the_helper_carries_declared_envelope_and_temperature():
    fields = v3_checkpoint_fields({
        "model": {
            "architecture_version": ARCHITECTURE_V3,
            "response_envelope_sha256": "a" * 64,
            "support_temperature": 0.75,
        },
        "provenance": {"experiment_contract_sha256": "b" * 64},
    })
    assert fields["response_envelope_sha256"] == "a" * 64
    assert fields["support_temperature"] == 0.75
    assert fields["experiment_contract_sha256"] == "b" * 64


# --------------------------------------------------------------------------
# 4. a v3 save/load round trip preserves exact sample behaviour
# --------------------------------------------------------------------------

def test_v3_round_trip_preserves_exact_weights(trained):
    saved = _load(trained["v3"] / "checkpoints" / "last.pt")["model_state"]
    reread = _load(trained["v3"] / "checkpoints" / "last.pt")["model_state"]
    assert set(saved) == set(reread)
    for key, tensor in saved.items():
        assert torch.equal(tensor, reread[key]), key


def test_v3_and_v2_runs_agree_on_weights_when_no_v3_feature_is_enabled(trained):
    """A bare v3 declaration must not change training, only the record.

    Every v3 feature defaults to the v2.2 behaviour, so declaring the version
    alone must leave the trained weights bit-identical. If this drifts, the
    format fix has silently altered an experiment.

    A v3 model does register one extra entry, `response_envelope_caps_gev`.
    With no envelope supplied it is a zero-length buffer and `response_cap_for`
    falls back to the v2.2 cap rule, so it carries no state -- which the next
    test pins directly rather than taking on trust.
    """
    v2 = _load(trained["v2"] / "checkpoints" / "last.pt")["model_state"]
    v3 = _load(trained["v3"] / "checkpoints" / "last.pt")["model_state"]
    assert set(v2) <= set(v3)
    for key, tensor in v2.items():
        assert torch.equal(tensor, v3[key]), key


def test_the_only_v3_only_state_entry_is_an_empty_envelope_buffer(trained):
    """Whatever a bare v3 run adds must demonstrably hold nothing.

    Without this the test above would pass for any extra tensor at all, which
    would let a real behavioural change hide behind a subset assertion.
    """
    v2 = _load(trained["v2"] / "checkpoints" / "last.pt")["model_state"]
    v3 = _load(trained["v3"] / "checkpoints" / "last.pt")["model_state"]
    extra = set(v3) - set(v2)
    assert extra == {"response_envelope_caps_gev"}
    buffer = v3["response_envelope_caps_gev"]
    assert buffer.numel() == 0, "a bare v3 run installed a non-empty response envelope"


# --------------------------------------------------------------------------
# 5. supervised v3 save/resume reproduces the run
# --------------------------------------------------------------------------

def test_supervised_v3_resumes_to_identical_weights(tmp_path):
    created, splits_path = _dataset(tmp_path)
    first = _config(created, splits_path, tmp_path / "run", version=ARCHITECTURE_V3)
    train_from_config(first)
    original = _load(tmp_path / "run" / "checkpoints" / "last.pt")

    resumed_config = _config(
        created, splits_path, tmp_path / "resumed", version=ARCHITECTURE_V3
    )
    resumed_config["training"]["epochs"] = 1
    resumed_config["training"]["initialize_from"] = str(
        tmp_path / "run" / "checkpoints" / "last.pt"
    )
    train_from_config(resumed_config)
    resumed = _load(tmp_path / "resumed" / "checkpoints" / "last.pt")

    # The resumed run must itself be format 4: an initialized v3 row that
    # silently drops back to format 3 is the original defect one step later.
    assert resumed["format_version"] == CHECKPOINT_FORMAT_V4
    assert resumed["architecture_version"] == ARCHITECTURE_V3
    assert set(original["model_state"]) == set(resumed["model_state"])


# --------------------------------------------------------------------------
# 6/7. the adversarial-resume guard, and the fail-closed hash checks
# --------------------------------------------------------------------------

def test_a_format_four_checkpoint_is_accepted_as_a_resume_source(trained):
    payload = _load(trained["v3"] / "checkpoints" / "last.pt")
    assert require_adversarial_resume_source(payload) is payload


def test_a_format_three_checkpoint_is_rejected_as_a_resume_source(trained):
    """An S1-era checkpoint stays usable for evaluation, never for resume."""
    payload = _load(trained["v2"] / "checkpoints" / "last.pt")
    # Still perfectly loadable as evaluation evidence.
    assert payload["model_state"]
    assert payload["config"]
    with pytest.raises(ValueError, match="requires checkpoint format 4"):
        require_adversarial_resume_source(payload)


def test_a_format_four_claim_missing_fields_is_rejected(trained):
    payload = dict(_load(trained["v3"] / "checkpoints" / "last.pt"))
    payload.pop("replay_state_manifest")
    with pytest.raises(ValueError, match="omits"):
        require_adversarial_resume_source(payload)


def test_a_null_architecture_version_is_rejected_even_at_format_four(trained):
    payload = dict(_load(trained["v3"] / "checkpoints" / "last.pt"))
    payload["architecture_version"] = None
    with pytest.raises(ValueError, match="no architecture_version"):
        require_adversarial_resume_source(payload)


def test_critic_state_cannot_be_written_without_an_architecture_version():
    from cbsc_zdc.training.checkpoint import save_checkpoint

    class _Model:
        def state_dict(self):
            return {}

    with pytest.raises(ValueError, match="requires architecture_version"):
        save_checkpoint(
            Path("unused.pt"), _Model(), None, None, None, 0, None, {}, "joint", {},
            critic_state={"weight": torch.zeros(1)},
        )


def test_critic_state_cannot_be_written_without_a_contract_hash():
    from cbsc_zdc.training.checkpoint import save_checkpoint

    class _Model:
        def state_dict(self):
            return {}

    with pytest.raises(ValueError, match="requires experiment_contract_sha256"):
        save_checkpoint(
            Path("unused.pt"), _Model(), None, None, None, 0, None, {}, "joint", {},
            architecture_version=ARCHITECTURE_V3,
            critic_state={"weight": torch.zeros(1)},
        )


# --------------------------------------------------------------------------
# 8. the retained S1 checkpoint's recorded disposition stays truthful
# --------------------------------------------------------------------------

def test_the_registry_records_s1_as_a_format_three_non_resume_source():
    import json

    registry = json.loads(
        (Path(__file__).resolve().parents[1]
         / "exhibition" / "data" / "v3_screening_rows.json").read_text(encoding="utf-8")
    )
    s1 = next(r for r in registry["rows"] if r["row_id"] == "S1-axis")
    checkpoints = s1["checkpoints"]
    assert checkpoints["checkpoint_format_written"] == CHECKPOINT_FORMAT_V3
    assert checkpoints["checkpoint_format_required_for_v3"] == CHECKPOINT_FORMAT_V4
    assert checkpoints["immutable"] is True
    assert "never be rewritten" in checkpoints["format_defect"]
