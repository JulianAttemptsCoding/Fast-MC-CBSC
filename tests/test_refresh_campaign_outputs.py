"""Contracts for the campaign-aware refresh, none of which touch a live pod.

The load-bearing case is the one that actually happened on 2026-08-05:
`dicos-c-03` resumed `calibrated_lr1e4_halfbatch` from `dicos-p7`'s BEST
checkpoint (epoch 21), but `dicos-p7`'s own history already reached epoch 22,
so both tags claim an epoch-22 row and
`exhibition/build_continuation_loss_figures.py` correctly refuses the
duplicate. These tests pin the resolution: the fork point is read from the
campaign's own recorded evidence, not guessed, and every dropped row is
reported rather than silently vanishing.
"""

from __future__ import annotations

import csv
from pathlib import Path

from scripts.refresh_campaign_outputs import (
    _parent_tag_from_run_dir,
    fork_points,
    prune_superseded_rows,
    segments_by_family,
)


# --------------------------------------------------------------------------
# _parent_tag_from_run_dir
# --------------------------------------------------------------------------


def test_parent_tag_strips_the_family_prefix():
    assert _parent_tag_from_run_dir(
        "_runs/calibrated_lr1e4_halfbatch_dicos-p7", "calibrated_lr1e4_halfbatch"
    ) == "dicos-p7"


def test_parent_tag_raises_on_a_mismatched_family():
    import pytest
    with pytest.raises(ValueError, match="does not start with"):
        _parent_tag_from_run_dir("_runs/calibrated_lr3e4_dicos-p7", "calibrated_lr1e4")


# --------------------------------------------------------------------------
# fork_points -- reconstructing fork epochs from campaign events
# --------------------------------------------------------------------------


def _segment_launch(family: str, tag: str) -> dict:
    return {"kind": "segment_launch", "run_tag": tag, "run_dir": f"_runs/{family}_{tag}"}


def _segment_frozen(tag: str, parent_last_epoch: int | str) -> dict:
    return {
        "kind": "segment_frozen",
        "run_tag": tag,
        "config_delta": {
            "provenance.parent_last_epoch": ["absent", str(parent_last_epoch)],
        },
    }


HALFBATCH_PLAN = {
    "families": {
        "calibrated_lr1e4_halfbatch": {
            "parent_run_dir": "_runs/calibrated_lr1e4_halfbatch_dicos-p7",
        }
    }
}


def test_fork_points_reconstructs_the_real_dicos_c_03_case():
    events = [
        _segment_frozen("dicos-c-03", 21),
        _segment_launch("calibrated_lr1e4_halfbatch", "dicos-c-03"),
    ]
    forks = fork_points(HALFBATCH_PLAN, events)
    assert forks == {
        "calibrated_lr1e4_halfbatch": [("dicos-p7", "dicos-c-03", 21)]
    }


def test_fork_points_chains_two_campaign_segments_of_the_same_family():
    """A family given a second segment forks from its own first campaign tag."""
    plan = {
        "families": {
            "calibrated_lr3e4": {"parent_run_dir": "_runs/calibrated_lr3e4_dicos-p7"}
        }
    }
    events = [
        _segment_frozen("dicos-c-02", 22),
        _segment_launch("calibrated_lr3e4", "dicos-c-02"),
        _segment_frozen("dicos-c-05", 34),
        _segment_launch("calibrated_lr3e4", "dicos-c-05"),
    ]
    forks = fork_points(plan, events)
    assert forks["calibrated_lr3e4"] == [
        ("dicos-p7", "dicos-c-02", 22),
        ("dicos-c-02", "dicos-c-05", 34),
    ]


def test_fork_points_is_empty_for_a_family_with_no_recorded_frozen_event():
    """A launch with no matching segment_frozen event yields no fork point.

    This is fail-safe by construction: with no known fork epoch there is
    nothing to prune, so a family is left untouched rather than pruned on a
    guess.
    """
    events = [_segment_launch("calibrated_lr1e4_halfbatch", "dicos-c-03")]
    assert fork_points(HALFBATCH_PLAN, events) == {}


def test_fork_points_ignores_a_family_absent_from_the_plan():
    events = [
        _segment_frozen("dicos-c-09", 5),
        _segment_launch("calibrated_unknown_family", "dicos-c-09"),
    ]
    assert fork_points(HALFBATCH_PLAN, events) == {}


def test_fork_points_ignores_a_non_numeric_parent_last_epoch():
    events = [
        {
            "kind": "segment_frozen", "run_tag": "dicos-c-03",
            "config_delta": {"provenance.parent_last_epoch": ["absent", "not-a-number"]},
        },
        _segment_launch("calibrated_lr1e4_halfbatch", "dicos-c-03"),
    ]
    assert fork_points(HALFBATCH_PLAN, events) == {}


# --------------------------------------------------------------------------
# prune_superseded_rows -- the actual CSV surgery
# --------------------------------------------------------------------------


def _write_csv(path: Path, rows: list[dict]) -> None:
    fieldnames = ["variant", "epoch", "train_loss", "validation_loss", "run_tag"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_prune_drops_exactly_the_real_off_lineage_row(tmp_path: Path) -> None:
    """The exact `dicos-p7`/`dicos-c-03` collision observed on 2026-08-05."""
    path = tmp_path / "continuation_history.csv"
    _write_csv(path, [
        {"variant": "calibrated_lr1e4_halfbatch", "epoch": "21",
         "train_loss": "4.6", "validation_loss": "4.673036", "run_tag": "dicos-p7"},
        {"variant": "calibrated_lr1e4_halfbatch", "epoch": "22",
         "train_loss": "4.6", "validation_loss": "4.678376", "run_tag": "dicos-p7"},
        {"variant": "calibrated_lr1e4_halfbatch", "epoch": "22",
         "train_loss": "4.6", "validation_loss": "4.690804", "run_tag": "dicos-c-03"},
        {"variant": "calibrated_lr1e4_halfbatch", "epoch": "23",
         "train_loss": "4.6", "validation_loss": "4.691913", "run_tag": "dicos-c-03"},
    ])
    forks = {"calibrated_lr1e4_halfbatch": [("dicos-p7", "dicos-c-03", 21)]}

    dropped = prune_superseded_rows(path, forks)

    assert len(dropped) == 1
    assert "dicos-p7 epoch 22 dropped" in dropped[0]
    assert "dicos-c-03" in dropped[0]
    remaining = _read_csv(path)
    epochs_by_tag = [(r["run_tag"], int(r["epoch"])) for r in remaining]
    assert ("dicos-p7", 22) not in epochs_by_tag
    assert ("dicos-p7", 21) in epochs_by_tag       # at-or-before the fork: kept
    assert ("dicos-c-03", 22) in epochs_by_tag      # the live branch: kept
    assert ("dicos-c-03", 23) in epochs_by_tag
    # No duplicate epoch survives for this family.
    epochs = [e for tag, e in epochs_by_tag]
    assert len(epochs) == len(set(epochs))


def test_prune_leaves_the_file_untouched_when_nothing_is_superseded(tmp_path: Path) -> None:
    path = tmp_path / "continuation_history.csv"
    rows = [
        {"variant": "calibrated_lr3e4", "epoch": "22", "train_loss": "4.6",
         "validation_loss": "4.597152", "run_tag": "dicos-p7"},
    ]
    _write_csv(path, rows)
    before = path.read_bytes()
    dropped = prune_superseded_rows(path, {"calibrated_lr3e4": [("dicos-p7", "dicos-c-02", 25)]})
    assert dropped == []
    assert path.read_bytes() == before  # not even rewritten


def test_prune_on_a_missing_file_returns_empty(tmp_path: Path) -> None:
    assert prune_superseded_rows(tmp_path / "absent.csv", {"x": [("a", "b", 1)]}) == []


def test_prune_only_touches_the_named_family(tmp_path: Path) -> None:
    """A fork point for one family must not affect another family's rows."""
    path = tmp_path / "continuation_history.csv"
    _write_csv(path, [
        {"variant": "calibrated_lr3e4", "epoch": "22", "train_loss": "4.6",
         "validation_loss": "4.6", "run_tag": "dicos-p7"},
        {"variant": "calibrated_lr1e4_halfbatch", "epoch": "22", "train_loss": "4.6",
         "validation_loss": "4.678376", "run_tag": "dicos-p7"},
    ])
    dropped = prune_superseded_rows(
        path, {"calibrated_lr1e4_halfbatch": [("dicos-p7", "dicos-c-03", 21)]}
    )
    assert len(dropped) == 1
    assert "calibrated_lr1e4_halfbatch" in dropped[0]
    remaining = _read_csv(path)
    lr3e4_rows = [r for r in remaining if r["variant"] == "calibrated_lr3e4"]
    assert len(lr3e4_rows) == 1  # untouched


def test_prune_keeps_a_row_from_a_tag_it_has_no_fork_point_for(tmp_path: Path) -> None:
    """Rows from a tag that never appears as a fork's parent are always kept,
    however high their epoch -- there is nothing recorded to prune them against.
    """
    path = tmp_path / "continuation_history.csv"
    _write_csv(path, [
        {"variant": "calibrated_lr3e5", "epoch": "40", "train_loss": "4.6",
         "validation_loss": "4.6", "run_tag": "dicos-r3"},
    ])
    dropped = prune_superseded_rows(
        path, {"calibrated_lr3e5": [("dicos-p7", "dicos-c-04", 5)]}
    )
    assert dropped == []
    assert len(_read_csv(path)) == 1


# --------------------------------------------------------------------------
# end-to-end: fork_points feeding straight into prune_superseded_rows
# --------------------------------------------------------------------------


def test_fork_points_and_prune_together_resolve_the_real_incident(tmp_path: Path) -> None:
    events = [
        _segment_frozen("dicos-c-03", 21),
        _segment_launch("calibrated_lr1e4_halfbatch", "dicos-c-03"),
    ]
    forks = fork_points(HALFBATCH_PLAN, events)

    path = tmp_path / "continuation_history.csv"
    _write_csv(path, [
        {"variant": "calibrated_lr1e4_halfbatch", "epoch": "21", "train_loss": "4.6",
         "validation_loss": "4.673036", "run_tag": "dicos-p7"},
        {"variant": "calibrated_lr1e4_halfbatch", "epoch": "22", "train_loss": "4.6",
         "validation_loss": "4.678376", "run_tag": "dicos-p7"},
        {"variant": "calibrated_lr1e4_halfbatch", "epoch": "22", "train_loss": "4.6",
         "validation_loss": "4.690804", "run_tag": "dicos-c-03"},
    ])
    dropped = prune_superseded_rows(path, forks)
    assert len(dropped) == 1

    rows = _read_csv(path)
    epochs = [int(r["epoch"]) for r in rows]
    assert len(epochs) == len(set(epochs)), "duplicate-epoch guard must now pass"
