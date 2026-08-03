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


def test_patience_can_be_widened_only_by_asking(tmp_path: Path) -> None:
    """Patience 3 cannot survive a high-LR scheduler restart: the resumed best
    was reached at lr 1e-6, so the first epochs after a 1e-4 restart are always
    worse and three of them exhaust the budget. Widening is therefore a real
    option -- but it must be an explicit argument, so it can never be inherited
    from the comparison phase by accident, which is what the default guards."""
    built = builder.build(
        family="calibrated_lr3e4",
        parent_path=_parent(tmp_path),
        last_sha256="c" * 64,
        best_sha256="d" * 64,
        output_dir=tmp_path / "out",
        patience=6,
        epochs=17,
    )
    training = yaml.safe_load(built.path.read_text())["training"]
    assert training["early_stopping_patience"] == 6
    assert training["epochs"] == 17


def test_an_inert_early_stop_is_recorded_not_hidden(tmp_path: Path) -> None:
    """A horizon no longer than the patience means early stopping can never
    fire. That is a legitimate declared choice -- the comparison wave used it to
    guarantee a fixed six epochs -- but getting it by accident is the hazard, so
    the config must say which it is."""
    inert = builder.build(
        family="calibrated_lr3e4", parent_path=_parent(tmp_path),
        last_sha256="c" * 64, best_sha256="d" * 64,
        output_dir=tmp_path / "inert", patience=6, epochs=17, run_tag="t-inert",
    )
    assert yaml.safe_load(inert.path.read_text())["provenance"][
        "early_stopping_can_fire"
    ] is False

    live = builder.build(
        family="calibrated_lr3e4", parent_path=_parent(tmp_path),
        last_sha256="c" * 64, best_sha256="d" * 64,
        output_dir=tmp_path / "live", patience=3, epochs=17, run_tag="t-live",
    )
    assert yaml.safe_load(live.path.read_text())["provenance"][
        "early_stopping_can_fire"
    ] is True


def test_a_horizon_with_no_epochs_is_refused(tmp_path: Path) -> None:
    """`epochs` is absolute, so a value at or below the parent's last epoch
    silently runs nothing at all -- the exact trap that wasted the first wave."""
    with pytest.raises(ValueError, match="no epochs to run"):
        builder.build(
            family="calibrated_lr3e4", parent_path=_parent(tmp_path),
            last_sha256="c" * 64, best_sha256="d" * 64,
            output_dir=tmp_path / "out", epochs=11,
        )


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


def test_a_later_parent_moves_the_horizon(tmp_path: Path) -> None:
    """A second continuation resumes from a later epoch, so the same absolute
    `epochs` value buys fewer epochs. The arithmetic must follow the parent
    actually being resumed, not the wave-three constant."""
    built = builder.build(
        family="calibrated_lr3e4", parent_path=_parent(tmp_path),
        last_sha256="c" * 64, best_sha256="d" * 64,
        output_dir=tmp_path / "out", patience=6, epochs=23,
        parent_last_epoch=16, run_tag="t-p7",
    )
    provenance = yaml.safe_load(built.path.read_text())["provenance"]
    assert provenance["parent_last_epoch"] == 16
    # epochs 17..22 inclusive
    assert provenance["epochs_available"] == 6
    assert provenance["early_stopping_can_fire"] is False


def test_a_later_parent_can_also_leave_no_epochs(tmp_path: Path) -> None:
    """The absolute-target trap does not disappear just because the parent
    moved; it moves with it."""
    with pytest.raises(ValueError, match="no epochs to run"):
        builder.build(
            family="calibrated_lr3e4", parent_path=_parent(tmp_path),
            last_sha256="c" * 64, best_sha256="d" * 64,
            output_dir=tmp_path / "out", epochs=17, parent_last_epoch=16,
        )


def test_the_checkpoint_stem_selects_the_resume_pair(tmp_path: Path) -> None:
    """Each phase stages its parent under a different name. Resuming from the
    wrong phase's checkpoint would silently continue the wrong model, so the
    stem is explicit and the default stays on wave three."""
    built = builder.build(
        family="calibrated_lr3e4", parent_path=_parent(tmp_path),
        last_sha256="c" * 64, best_sha256="d" * 64,
        output_dir=tmp_path / "out", patience=6, epochs=23,
        parent_last_epoch=16, checkpoint_stem="p6", run_tag="t-stem",
    )
    training = yaml.safe_load(built.path.read_text())["training"]
    assert training["resume_from_relative"] == "checkpoints/calibrated_lr3e4_p6_last.pt"
    assert training["resume_best_from_relative"] == "checkpoints/calibrated_lr3e4_p6_best.pt"


def test_defaults_are_unchanged_by_the_new_arguments(tmp_path: Path) -> None:
    """Omitting the new arguments must reproduce the wave-three behaviour
    exactly, so an old invocation cannot silently mean something new."""
    built = _build(tmp_path)
    config = yaml.safe_load(built.path.read_text())
    assert config["provenance"]["parent_last_epoch"] == builder.PARENT_LAST_EPOCH
    assert config["training"]["resume_from_relative"].endswith("_r3_last.pt")


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
