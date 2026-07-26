import random
from pathlib import Path

import numpy as np
import pytest
import torch

from cbsc_zdc.cloud.vertex_stage import _listing_prefix, build_runtime_config
from cbsc_zdc.cloud.vertex_calibrate import (
    _assert_checkpoint_provenance,
    _resolve_staged_file,
)
from cbsc_zdc.config import validate_config
from cbsc_zdc.training.checkpoint import (
    _cpu_byte_rng_tensor,
    restore_rng_state,
    rng_state,
)
from cbsc_zdc.training.trainer import (
    _legacy_mid_epoch_contract_sha256,
    _mid_epoch_contract_sha256,
    _restore_resume_best,
    _validate_mid_epoch_progress,
)
from cbsc_zdc.training.weights import calibrate_loss_weights
from cbsc_zdc.utils import dump_yaml, load_yaml, sha256_file
from scripts.verify_vertex_staging import _checkpoint_spec


def _template() -> dict:
    return load_yaml("configs/templates/pilot_full_architecture_smoke_fp32.yaml")


def test_vertex_gcs_listing_prefix_is_directory_bounded():
    assert _listing_prefix("cbsc-v2-2/prep-20260724-r5") == (
        "cbsc-v2-2/prep-20260724-r5/"
    )
    assert not "cbsc-v2-2/prep-20260724-r5-fp32/object".startswith(
        _listing_prefix("cbsc-v2-2/prep-20260724-r5")
    )
    assert _listing_prefix("") == ""


def test_vertex_staging_extra_checkpoint_spec_is_strict():
    assert _checkpoint_spec("checkpoints/joint_best.pt=" + "a" * 64) == (
        "checkpoints/joint_best.pt",
        "a" * 64,
    )
    for invalid in (
        "checkpoints/joint_best.pt",
        "../joint_best.pt=" + "a" * 64,
        "/joint_best.pt=" + "a" * 64,
        "checkpoints/joint_best.pt=" + "A" * 64,
        "checkpoints/joint_best.pt=abc",
    ):
        with pytest.raises(ValueError):
            _checkpoint_spec(invalid)


def test_vertex_calibration_staged_file_is_bounded_and_hash_checked(
    tmp_path: Path,
):
    root = tmp_path / "input"
    checkpoint = root / "checkpoints" / "joint_best.pt"
    checkpoint.parent.mkdir(parents=True)
    checkpoint.write_bytes(b"accepted joint checkpoint")
    digest = sha256_file(checkpoint)
    assert (
        _resolve_staged_file(root, "checkpoints/joint_best.pt", digest)
        == checkpoint.resolve()
    )
    with pytest.raises(RuntimeError, match="escapes input root"):
        _resolve_staged_file(root, "../outside.pt", digest)
    with pytest.raises(RuntimeError, match="hash mismatch"):
        _resolve_staged_file(root, "checkpoints/joint_best.pt", "0" * 64)


def test_vertex_calibration_checkpoint_provenance_is_exact(tmp_path: Path):
    geometry = tmp_path / "geometry"
    geometry.mkdir()
    (geometry / "geometry.npz").write_bytes(b"geometry")
    manifest = tmp_path / "manifest.json"
    splits = tmp_path / "splits.json"
    manifest.write_bytes(b"manifest")
    splits.write_bytes(b"splits")
    config = {
        "geometry": {"path": str(geometry)},
        "data": {"manifest": str(manifest), "splits": str(splits)},
        "training": {"seed": 20260723},
    }
    expected = {
        "geometry_sha256": sha256_file(geometry / "geometry.npz"),
        "manifest_sha256": sha256_file(manifest),
        "splits_sha256": sha256_file(splits),
        "seed": 20260723,
    }
    assert _assert_checkpoint_provenance(config, {"provenance": expected}) == expected
    for field in expected:
        changed = dict(expected)
        changed[field] = 20260724 if field == "seed" else "0" * 64
        with pytest.raises(RuntimeError, match="provenance mismatch"):
            _assert_checkpoint_provenance(config, {"provenance": changed})


def test_vertex_runtime_resolves_and_hashes_staged_checkpoint(tmp_path: Path):
    staged = tmp_path / "input"
    checkpoint = staged / "job" / "previous.pt"
    checkpoint.parent.mkdir(parents=True)
    checkpoint.write_bytes(b"immutable checkpoint")
    config = _template()
    config["training"].update(
        {
            "initialize_from_relative": "job/previous.pt",
            "initialize_from_sha256": sha256_file(checkpoint),
        }
    )
    config_path = staged / "job" / "frozen.yaml"
    dump_yaml(config, config_path)
    runtime_path = tmp_path / "runtime.yaml"
    runtime = build_runtime_config(
        staged,
        "job/frozen.yaml",
        "artifacts/data/dataset_manifest.json",
        "artifacts/splits.json",
        "artifacts/geometry",
        tmp_path / "run",
        runtime_path,
        "cuda",
    )
    assert runtime["training"]["initialize_from"] == str(checkpoint.resolve())
    assert runtime["training"]["initialize_from_sha256"] == sha256_file(checkpoint)


def test_vertex_runtime_stops_on_staged_checkpoint_hash_mismatch(tmp_path: Path):
    staged = tmp_path / "input"
    checkpoint = staged / "job" / "previous.pt"
    checkpoint.parent.mkdir(parents=True)
    checkpoint.write_bytes(b"wrong")
    config = _template()
    config["training"].update(
        {
            "initialize_from_relative": "job/previous.pt",
            "initialize_from_sha256": "0" * 64,
        }
    )
    config_path = staged / "job" / "frozen.yaml"
    dump_yaml(config, config_path)
    with pytest.raises(RuntimeError, match="staged checkpoint hash mismatch"):
        build_runtime_config(
            staged,
            "job/frozen.yaml",
            "artifacts/data/dataset_manifest.json",
            "artifacts/splits.json",
            "artifacts/geometry",
            tmp_path / "run",
            tmp_path / "runtime.yaml",
            "cuda",
        )


def test_vertex_calibration_runtime_skips_historical_initializer(tmp_path: Path):
    staged = tmp_path / "input"
    config = _template()
    config["training"].update(
        {
            "stage": "joint",
            "initialize_from": None,
            "initialize_from_relative": "checkpoints/historical_share_best.pt",
            "initialize_from_sha256": "1" * 64,
        }
    )
    config_path = staged / "job" / "frozen.yaml"
    config_path.parent.mkdir(parents=True)
    dump_yaml(config, config_path)
    runtime = build_runtime_config(
        staged,
        "job/frozen.yaml",
        "artifacts/data/dataset_manifest.json",
        "artifacts/splits.json",
        "artifacts/geometry",
        tmp_path / "run",
        tmp_path / "runtime.yaml",
        "cuda",
        resolve_training_checkpoints=False,
    )
    assert runtime["training"]["initialize_from"] is None
    assert (
        runtime["training"]["initialize_from_relative"]
        == "checkpoints/historical_share_best.pt"
    )


def test_vertex_runtime_resolves_paired_resume_checkpoints(tmp_path: Path):
    staged = tmp_path / "input"
    last_checkpoint = staged / "job" / "last.pt"
    best_checkpoint = staged / "job" / "best.pt"
    last_checkpoint.parent.mkdir(parents=True)
    last_checkpoint.write_bytes(b"immutable last")
    best_checkpoint.write_bytes(b"immutable best")
    config = _template()
    config["training"].update(
        {
            "resume_from_relative": "job/last.pt",
            "resume_from_sha256": sha256_file(last_checkpoint),
            "resume_best_from_relative": "job/best.pt",
            "resume_best_from_sha256": sha256_file(best_checkpoint),
        }
    )
    config_path = staged / "job" / "frozen.yaml"
    dump_yaml(config, config_path)
    runtime = build_runtime_config(
        staged,
        "job/frozen.yaml",
        "artifacts/data/dataset_manifest.json",
        "artifacts/splits.json",
        "artifacts/geometry",
        tmp_path / "run",
        tmp_path / "runtime.yaml",
        "cuda",
    )
    assert runtime["training"]["resume_from"] == str(last_checkpoint.resolve())
    assert runtime["training"]["resume_best_from"] == str(best_checkpoint.resolve())


def test_resume_requires_paired_best_checkpoint():
    config = _template()
    config["training"].update(
        {
            "resume_from_relative": "job/last.pt",
            "resume_from_sha256": "0" * 64,
        }
    )
    with pytest.raises(ValueError, match="must be paired"):
        validate_config(config)


def test_mid_epoch_resume_allows_no_prior_best_but_cannot_mix_resume_modes():
    config = _template()
    config["training"].update(
        {
            "resume_progress_from_relative": "job/progress.pt",
            "resume_progress_from_sha256": "0" * 64,
            "checkpoint_interval_updates": 10,
        }
    )
    validate_config(config)
    config["training"].update(
        {
            "resume_from_relative": "job/last.pt",
            "resume_from_sha256": "1" * 64,
        }
    )
    with pytest.raises(ValueError, match="cannot use resume_from"):
        validate_config(config)


def test_mid_epoch_progress_contract_accepts_optimizer_boundary_and_stops_drift():
    config = _template()
    contract_hash = _mid_epoch_contract_sha256(config)
    progress = {
        "epoch": 1,
        "next_step": 8,
        "loader_batches": 20,
        "gradient_accumulation": 4,
        "batch_size": 6,
        "epoch_seed": 20260724,
        "optimizer_boundary": True,
        "train_sum": 12.5,
        "train_count": 8,
        "component_sum": {"response": 10.0, "visible": 2.5},
        "updates": 7,
        "elapsed_seconds": 22.0,
        "contract_sha256": contract_hash,
    }
    payload = {"epoch": 1, "progress": progress}
    actual = _validate_mid_epoch_progress(
        payload,
        loader_batches=20,
        accumulation=4,
        batch_size=6,
        seed=20260723,
        contract_sha256=contract_hash,
    )
    assert actual is progress
    with pytest.raises(ValueError, match="DataLoader length changed"):
        _validate_mid_epoch_progress(
            payload,
            loader_batches=21,
            accumulation=4,
            batch_size=6,
            seed=20260723,
            contract_sha256=contract_hash,
        )
    bad_boundary = dict(progress, next_step=6, train_count=6)
    with pytest.raises(ValueError, match="accumulation boundary"):
        _validate_mid_epoch_progress(
            {"epoch": 1, "progress": bad_boundary},
            loader_batches=20,
            accumulation=4,
            batch_size=6,
            seed=20260723,
            contract_sha256=contract_hash,
        )
    with pytest.raises(ValueError, match="training contract changed"):
        _validate_mid_epoch_progress(
            payload,
            loader_batches=20,
            accumulation=4,
            batch_size=6,
            seed=20260723,
            contract_sha256="f" * 64,
        )


def test_mid_epoch_contract_allows_new_resume_template_but_stops_scientific_drift():
    interrupted = _template()
    interrupted["provenance"] = {
        "template_sha256": "1" * 64,
        "dataset_manifest_sha256": "2" * 64,
        "geometry_manifest_sha256": "3" * 64,
        "split_manifest_sha256": "4" * 64,
        "split_assignment_sha256": "5" * 64,
        "dataset_geometry_hash": "6" * 64,
    }
    resumed = _template()
    resumed["provenance"] = dict(interrupted["provenance"])
    resumed["provenance"]["template_sha256"] = "7" * 64
    resumed["training"].update(
        {
            "initialize_from_relative": None,
            "initialize_from_sha256": None,
            "resume_progress_from_relative": "checkpoints/progress.pt",
            "resume_progress_from_sha256": "8" * 64,
        }
    )

    interrupted_hash = _mid_epoch_contract_sha256(interrupted)
    assert _mid_epoch_contract_sha256(resumed) == interrupted_hash

    resumed["training"]["learning_rate"] = 3.0e-4
    assert _mid_epoch_contract_sha256(resumed) != interrupted_hash
    resumed["training"]["learning_rate"] = interrupted["training"]["learning_rate"]
    resumed["provenance"]["dataset_manifest_sha256"] = "9" * 64
    assert _mid_epoch_contract_sha256(resumed) != interrupted_hash


def test_mid_epoch_contract_accepts_embedded_legacy_source_without_waiving_drift():
    interrupted = _template()
    interrupted["provenance"] = {
        "template_sha256": "1" * 64,
        "dataset_manifest_sha256": "2" * 64,
        "geometry_manifest_sha256": "3" * 64,
        "split_manifest_sha256": "4" * 64,
        "split_assignment_sha256": "5" * 64,
        "dataset_geometry_hash": "6" * 64,
    }
    resumed = _template()
    resumed["provenance"] = dict(interrupted["provenance"])
    resumed["provenance"]["template_sha256"] = "7" * 64
    normalized_hash = _mid_epoch_contract_sha256(resumed)
    progress = {
        "epoch": 0,
        "next_step": 8,
        "loader_batches": 20,
        "gradient_accumulation": 4,
        "batch_size": 6,
        "epoch_seed": 20260723,
        "optimizer_boundary": True,
        "train_sum": 12.5,
        "train_count": 8,
        "component_sum": {"response": 10.0, "visible": 2.5},
        "updates": 2,
        "elapsed_seconds": 22.0,
        "contract_sha256": _legacy_mid_epoch_contract_sha256(interrupted),
    }
    payload = {"epoch": 0, "progress": progress, "config": interrupted}

    assert (
        _validate_mid_epoch_progress(
            payload,
            loader_batches=20,
            accumulation=4,
            batch_size=6,
            seed=20260723,
            contract_sha256=normalized_hash,
        )
        is progress
    )

    resumed["training"]["weight_decay"] = 0.0
    with pytest.raises(ValueError, match="training contract changed"):
        _validate_mid_epoch_progress(
            payload,
            loader_batches=20,
            accumulation=4,
            batch_size=6,
            seed=20260723,
            contract_sha256=_mid_epoch_contract_sha256(resumed),
        )


def test_resume_best_restore_requires_matching_metric_and_provenance(tmp_path: Path):
    provenance = {"manifest_sha256": "a" * 64, "seed": 20260723}
    best_path = tmp_path / "source_best.pt"
    destination = tmp_path / "run" / "checkpoints" / "best.pt"
    destination.parent.mkdir(parents=True)
    torch.save(
        {
            "stage": "response",
            "epoch": 1,
            "best_metric": -0.5,
            "provenance": provenance,
        },
        best_path,
    )
    last_payload = {
        "stage": "response",
        "epoch": 2,
        "best_metric": -0.5,
        "provenance": provenance,
    }
    restored = _restore_resume_best(
        best_path, last_payload, "response", destination
    )
    assert restored == -0.5
    assert destination.read_bytes() == best_path.read_bytes()
    mismatch = dict(last_payload, best_metric=-0.4)
    with pytest.raises(ValueError, match="metric mismatch"):
        _restore_resume_best(best_path, mismatch, "response", destination)


def test_checkpoint_rng_state_restores_python_numpy_and_torch():
    random.seed(11)
    np.random.seed(12)
    torch.manual_seed(13)
    state = rng_state()
    expected = (random.random(), np.random.random(), torch.rand(3))
    random.seed(99)
    np.random.seed(99)
    torch.manual_seed(99)
    restore_rng_state(state)
    actual = (random.random(), np.random.random(), torch.rand(3))
    assert actual[0] == expected[0]
    assert actual[1] == expected[1]
    assert torch.equal(actual[2], expected[2])


def test_checkpoint_rng_state_normalizes_to_cpu_byte_tensor():
    mapped_like_state = torch.arange(16, dtype=torch.int64)
    normalized = _cpu_byte_rng_tensor(mapped_like_state, "test")
    assert normalized.device.type == "cpu"
    assert normalized.dtype == torch.uint8
    with pytest.raises(TypeError, match="must be a torch tensor"):
        _cpu_byte_rng_tensor([1, 2, 3], "test")


def test_checkpoint_relative_path_cannot_escape_staging_root():
    config = _template()
    config["training"].update(
        {
            "resume_from_relative": "../outside.pt",
            "resume_from_sha256": "0" * 64,
        }
    )
    with pytest.raises(ValueError, match="safe relative path"):
        validate_config(config)


class _Tiny(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.condition = torch.nn.Linear(2, 2, bias=False)


def test_calibration_stops_when_any_expected_component_is_missing():
    model = _Tiny()
    batches = [{"x": torch.tensor([[1.0, 2.0]])}]

    def losses(batch):
        value = model.condition(batch["x"]).square().mean()
        return {"visible": value}

    with pytest.raises(RuntimeError, match="missing=.*response"):
        calibrate_loss_weights(
            model,
            batches,
            losses,
            max_batches=1,
            expected_losses={"visible", "response"},
        )
