"""Contracts for selecting which family is continued alone.

The criterion is the user's: the largest improvement in validation loss from the
beginning of the six-epoch continuation to its end. "Beginning" is the parent's
epoch-4 validation loss, not the continuation's first epoch -- epoch 5 has
already had a full epoch of training, so using it would hide exactly the
progress being measured.

A cosine restart raises validation loss before it lowers it, so a mid-run
number means nothing here; only the endpoints do. These tests pin the algebra
so the choice cannot quietly become "whichever ran last".
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import rank_continuation_families as ranker  # noqa: E402


def _run(root: Path, family: str, values: list[float]) -> None:
    reports = root / f"{family}_dicos-r3" / "reports"
    reports.mkdir(parents=True)
    for offset, value in enumerate(values):
        epoch = ranker.FIRST_EPOCH + offset
        (reports / f"progress_epoch_{epoch:04d}.json").write_text(
            json.dumps(
                {
                    "epoch": epoch,
                    "row": {"validation_loss": value, "train_loss": value + 0.1},
                    "elapsed_seconds": 60.0 * (offset + 1),
                }
            )
        )


def test_improvement_is_measured_against_the_parent_not_the_first_epoch(
    tmp_path: Path,
) -> None:
    _run(tmp_path, "calibrated_lr3e4", [4.90, 4.80, 4.70, 4.60, 4.50, 4.40])
    result = ranker.summarise("calibrated_lr3e4", tmp_path)
    assert result.parent_validation_loss == ranker.PARENT_VALIDATION["calibrated_lr3e4"]
    assert result.final_validation_loss == pytest.approx(4.40)
    assert result.improvement == pytest.approx(
        ranker.PARENT_VALIDATION["calibrated_lr3e4"] - 4.40
    )


def test_a_family_that_got_worse_has_a_negative_improvement(tmp_path: Path) -> None:
    """A cosine restart can leave a family worse than it started. That must
    read as negative, never as an absolute value or a zero floor."""
    _run(tmp_path, "calibrated_lr3e5", [5.5, 5.4, 5.3, 5.2, 5.1, 5.0])
    result = ranker.summarise("calibrated_lr3e5", tmp_path)
    assert result.improvement < 0


def test_the_winner_is_the_largest_improvement(tmp_path: Path) -> None:
    _run(tmp_path, "calibrated_lr3e4", [4.9, 4.8, 4.7, 4.6, 4.5, 4.70])
    _run(tmp_path, "calibrated_lr1e4", [4.9, 4.8, 4.7, 4.6, 4.5, 4.40])
    ranked = ranker.rank(["calibrated_lr3e4", "calibrated_lr1e4"], tmp_path)
    assert ranked[0].family == "calibrated_lr1e4"
    assert ranked[0].improvement > ranked[1].improvement


def test_the_best_epoch_is_reported_alongside_the_final_epoch(tmp_path: Path) -> None:
    """Ranking uses the endpoint, as specified. But if the best epoch is not
    the last, that disagreement has to be visible rather than silently
    discarded."""
    _run(tmp_path, "calibrated_lr3e4", [4.9, 4.8, 4.30, 4.6, 4.5, 4.55])
    result = ranker.summarise("calibrated_lr3e4", tmp_path)
    assert result.best_validation_loss == pytest.approx(4.30)
    assert result.best_epoch == ranker.FIRST_EPOCH + 2
    assert result.final_validation_loss == pytest.approx(4.55)
    assert result.best_differs_from_final is True


def test_an_incomplete_family_is_refused_not_ranked(tmp_path: Path) -> None:
    """Ranking four families over "the same six epochs" is the entire premise.
    A family that ran fewer epochs is not comparable and must not be silently
    compared."""
    _run(tmp_path, "calibrated_lr3e4", [4.9, 4.8, 4.7])
    with pytest.raises(ValueError, match="incomplete"):
        ranker.summarise("calibrated_lr3e4", tmp_path)


def test_a_missing_family_is_refused(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        ranker.summarise("calibrated_lr1e4", tmp_path)


def test_the_parent_baselines_match_the_published_training_history() -> None:
    """The baselines decide the winner, so they must come from the same record
    the public site publishes -- not from a number copied into a docstring."""
    import csv

    history = Path(__file__).resolve().parents[1] / "exhibition" / "data" / "training_history.csv"
    published = {
        row["variant"]: round(float(row["validation_loss"]), 6)
        for row in csv.DictReader(history.open(encoding="utf-8"))
        if int(row["epoch"]) == ranker.PARENT_LAST_EPOCH
    }
    assert published == ranker.PARENT_VALIDATION


def test_the_expected_epoch_span_matches_the_builder(tmp_path: Path) -> None:
    """If the builder's horizon and the ranker's expectation ever disagree, the
    ranker would reject every complete run or accept a short one."""
    import build_dicos_continuations as builder

    assert ranker.FIRST_EPOCH == builder.PARENT_LAST_EPOCH + 1
    assert ranker.LAST_EPOCH == builder.EPOCHS - 1
    assert ranker.EXPECTED_EPOCHS == builder.ADDITIONAL_EPOCHS
