"""Contracts for the winner's solo continuation.

The comparison phase deliberately widened `early_stopping_patience` from 3 to 6
so no family could stop early while all four ran the same six epochs. That
widening must not survive into the solo continuation, whose whole point is to
run until validation stops it. These tests exist because that is exactly the
kind of setting that gets carried forward by accident.
"""

from pathlib import Path

import pytest
import yaml

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import build_final_continuation as builder  # noqa: E402


def _parent(tmp_path: Path) -> Path:
    config = {
        "project": {"name": "calibrated_lr3e4-compute-extension-r1-dicos-r2",
                    "run_dir": "runs/x"},
        "data": {"manifest": "m", "splits": "s"},
        "geometry": {"path": "g"},
        "training": {
            "device": "cuda",
            "epochs": 11,
            "early_stopping_patience": 6,
            "learning_rate": 3e-4,
            "batch_size": 6,
            "gradient_accumulation": 4,
            "num_workers": 4,
            "amp": False,
            "seed": 20260728,
            "restart_scheduler_on_resume": True,
            "resume_from_relative": "checkpoints/calibrated_lr3e4_last.pt",
            "resume_from_sha256": "a" * 64,
            "resume_best_from_relative": "checkpoints/calibrated_lr3e4_best.pt",
            "resume_best_from_sha256": "b" * 64,
        },
    }
    path = tmp_path / "parent.yaml"
    path.write_text(yaml.safe_dump(config, sort_keys=False))
    return path


def _build(tmp_path: Path):
    return builder.build(
        family="calibrated_lr3e4",
        parent_path=_parent(tmp_path),
        last_sha256="c" * 64,
        best_sha256="d" * 64,
        output_dir=tmp_path / "out",
    )


def test_early_stopping_is_restored_to_three(tmp_path: Path) -> None:
    """The comparison phase's widened patience must not be inherited."""
    built = _build(tmp_path)
    config = yaml.safe_load(built.path.read_text())
    assert builder.EARLY_STOPPING_PATIENCE == 3
    assert config["training"]["early_stopping_patience"] == 3


def test_the_epoch_target_is_absolute_and_leaves_room_to_improve(
    tmp_path: Path,
) -> None:
    """`epochs` is an absolute target: the trainer resumes at
    checkpoint_epoch + 1 and runs range(start, epochs). The target must exceed
    the parent's last epoch by enough that early stopping, not the ceiling,
    is what ends the run."""
    assert builder.PARENT_LAST_EPOCH == 10
    start_epoch = builder.PARENT_LAST_EPOCH + 1
    assert builder.EPOCHS > start_epoch + builder.EARLY_STOPPING_PATIENCE
    built = _build(tmp_path)
    config = yaml.safe_load(built.path.read_text())
    assert config["training"]["epochs"] == builder.EPOCHS


def test_it_resumes_from_the_wave_three_checkpoints(tmp_path: Path) -> None:
    """Resuming from the comparison wave's own output, hash-verified, is the
    only thing that makes this a continuation rather than a new run."""
    built = _build(tmp_path)
    training = yaml.safe_load(built.path.read_text())["training"]
    assert training["resume_from_relative"] == "checkpoints/calibrated_lr3e4_r3_last.pt"
    assert training["resume_from_sha256"] == "c" * 64
    assert training["resume_best_from_relative"] == "checkpoints/calibrated_lr3e4_r3_best.pt"
    assert training["resume_best_from_sha256"] == "d" * 64


def test_the_science_carries_over_untouched(tmp_path: Path) -> None:
    """The backend-portability contract lists these as invariant. A
    continuation may change the horizon and the resume pair, nothing else."""
    built = _build(tmp_path)
    parent = yaml.safe_load(_parent(tmp_path).read_text())["training"]
    child = yaml.safe_load(built.path.read_text())["training"]
    for key in ("learning_rate", "batch_size", "gradient_accumulation",
                "num_workers", "amp", "seed"):
        assert child[key] == parent[key], key


def test_paths_are_returned_to_unfrozen_for_refreezing(tmp_path: Path) -> None:
    """Frozen configs are never hand-edited; freeze-config re-pins them."""
    built = _build(tmp_path)
    config = yaml.safe_load(built.path.read_text())
    assert config["data"]["manifest"] == "UNFROZEN"
    assert config["data"]["splits"] == "UNFROZEN"
    assert config["geometry"]["path"] == "UNFROZEN"


def test_the_parent_lineage_is_recorded(tmp_path: Path) -> None:
    built = _build(tmp_path)
    provenance = yaml.safe_load(built.path.read_text())["provenance"]
    assert provenance["parent_project_name"].endswith("dicos-r2")
    assert len(provenance["parent_config_sha256"]) == 64


def test_a_bad_hash_is_refused(tmp_path: Path) -> None:
    """A resume hash is the only thing standing between this run and silently
    training from the wrong checkpoint."""
    with pytest.raises(ValueError, match="sha256"):
        builder.build(
            family="calibrated_lr3e4",
            parent_path=_parent(tmp_path),
            last_sha256="not-a-hash",
            best_sha256="d" * 64,
            output_dir=tmp_path / "out",
        )
