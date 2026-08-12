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

import subprocess

from scripts.refresh_campaign_outputs import (
    _dicos,
    _parent_tag_from_run_dir,
    bound_lineage,
    fork_points,
    prune_superseded_rows,
    segments_by_family,
)


# --------------------------------------------------------------------------
# _dicos -- a wedged pod call must not hang the caller forever
# --------------------------------------------------------------------------


def test_dicos_converts_a_subprocess_timeout_into_a_catchable_system_exit(monkeypatch):
    """A stalled pod request must fail fast, not hang the watcher loop.

    `latest_epoch()` already catches `SystemExit` from `_dicos()` and falls
    back to local data; `run_loop()` already catches `SystemExit` around a
    whole refresh pass and retries next interval. Both only help if a wedged
    subprocess actually raises instead of blocking forever, which is what the
    2026-08-05 6h50m watcher gap was flagged as being consistent with.
    """
    def _wedged(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs.get("timeout"))

    monkeypatch.setattr(subprocess, "run", _wedged)
    try:
        _dicos(["exec", "ls"])
        assert False, "expected SystemExit"
    except SystemExit as error:
        assert "timed out after" in str(error)


def test_dicos_passes_a_bounded_timeout_to_subprocess_run(monkeypatch):
    captured = {}

    def _fake_run(command, **kwargs):
        captured.update(kwargs)
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)
    assert _dicos(["exec", "ls"]) == "ok"
    assert isinstance(captured.get("timeout"), (int, float))
    assert 0 < captured["timeout"] <= 600


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
        {"variant": "calibrated_lr1e4_halfbatch", "epoch": "22", "train_loss": "4.6",
         "validation_loss": "4.690804", "run_tag": "dicos-c-03"},
    ])
    dropped = prune_superseded_rows(
        path, {"calibrated_lr1e4_halfbatch": [("dicos-p7", "dicos-c-03", 21)]}
    )
    assert len(dropped) == 1
    assert "calibrated_lr1e4_halfbatch" in dropped[0]
    remaining = _read_csv(path)
    lr3e4_rows = [r for r in remaining if r["variant"] == "calibrated_lr3e4"]
    assert len(lr3e4_rows) == 1  # untouched


def test_prune_ignores_a_fork_whose_child_wrote_no_real_epoch(tmp_path: Path) -> None:
    """The real dicos-e-01 incident, 2026-08-10.

    dicos-e-01 froze a segment continuing calibrated_lr3e4 from dicos-c-02's
    best (epoch 34) -- a real segment_frozen event with a real fork epoch --
    then crashed on a CUDA-driver mismatch before writing a single epoch.
    Nothing ever superseded dicos-c-02's own epochs past 34: they are still
    the live lineage, and pruning them destroyed real evidence for no reason.
    A fork only justifies dropping the parent's rows if the child actually
    produced at least one row of its own.
    """
    path = tmp_path / "continuation_history.csv"
    _write_csv(path, [
        {"variant": "calibrated_lr3e4", "epoch": "34", "train_loss": "4.6",
         "validation_loss": "4.550331", "run_tag": "dicos-c-02"},
        {"variant": "calibrated_lr3e4", "epoch": "35", "train_loss": "4.6",
         "validation_loss": "4.572274", "run_tag": "dicos-c-02"},
        {"variant": "calibrated_lr3e4", "epoch": "42", "train_loss": "4.6",
         "validation_loss": "4.595299", "run_tag": "dicos-c-02"},
    ])
    forks = {"calibrated_lr3e4": [("dicos-c-02", "dicos-e-01", 34)]}

    dropped = prune_superseded_rows(path, forks)

    assert dropped == []
    remaining = _read_csv(path)
    epochs = sorted(int(r["epoch"]) for r in remaining if r["run_tag"] == "dicos-c-02")
    assert epochs == [34, 35, 42]


def test_prune_bridges_an_empty_intermediate_tag_to_the_real_restart(tmp_path: Path) -> None:
    """The other half of the real 2026-08-10 incident: dicos-e-02 (the real
    restart) forked from dicos-c-02 at the same epoch 34 the aborted
    dicos-e-01 did, so fork_points()'s tag-by-tag chain records the edge as
    (dicos-e-01, dicos-e-02, 34) -- dicos-e-01 is next-in-list, not
    data-bearing, so it has no rows to prune and dicos-c-02's real
    supersession by dicos-e-02 is never expressed unless the empty hop is
    bridged.
    """
    path = tmp_path / "continuation_history.csv"
    _write_csv(path, [
        {"variant": "calibrated_lr3e4", "epoch": "34", "train_loss": "4.6",
         "validation_loss": "4.550331", "run_tag": "dicos-c-02"},
        {"variant": "calibrated_lr3e4", "epoch": "35", "train_loss": "4.6",
         "validation_loss": "4.572274", "run_tag": "dicos-c-02"},
        {"variant": "calibrated_lr3e4", "epoch": "36", "train_loss": "4.6",
         "validation_loss": "4.606194", "run_tag": "dicos-c-02"},
        {"variant": "calibrated_lr3e4", "epoch": "35", "train_loss": "4.6",
         "validation_loss": "4.565918", "run_tag": "dicos-e-02"},
        {"variant": "calibrated_lr3e4", "epoch": "36", "train_loss": "4.6",
         "validation_loss": "4.605922", "run_tag": "dicos-e-02"},
    ])
    forks = {
        "calibrated_lr3e4": [
            ("dicos-c-02", "dicos-e-01", 34),
            ("dicos-e-01", "dicos-e-02", 34),
        ]
    }

    dropped = prune_superseded_rows(path, forks)

    assert len(dropped) == 2
    remaining = _read_csv(path)
    epochs_by_tag = [(r["run_tag"], int(r["epoch"])) for r in remaining]
    assert ("dicos-c-02", 35) not in epochs_by_tag
    assert ("dicos-c-02", 36) not in epochs_by_tag
    assert ("dicos-c-02", 34) in epochs_by_tag       # at-or-before the fork: kept
    assert ("dicos-e-02", 35) in epochs_by_tag
    assert ("dicos-e-02", 36) in epochs_by_tag
    epochs = [e for _tag, e in epochs_by_tag]
    assert len(epochs) == len(set(epochs))           # no duplicate epoch survives


def test_prune_still_drops_when_the_forking_child_has_real_data(tmp_path: Path) -> None:
    """A genuine fork (the child DID write epochs) still prunes correctly --
    the fix above must not blanket-disable pruning, only the zero-data case.
    """
    path = tmp_path / "continuation_history.csv"
    _write_csv(path, [
        {"variant": "calibrated_lr1e4_halfbatch", "epoch": "21", "train_loss": "4.6",
         "validation_loss": "4.673036", "run_tag": "dicos-p7"},
        {"variant": "calibrated_lr1e4_halfbatch", "epoch": "22", "train_loss": "4.6",
         "validation_loss": "4.678376", "run_tag": "dicos-p7"},
        {"variant": "calibrated_lr1e4_halfbatch", "epoch": "22", "train_loss": "4.6",
         "validation_loss": "4.690804", "run_tag": "dicos-c-03"},
    ])
    forks = {"calibrated_lr1e4_halfbatch": [("dicos-p7", "dicos-c-03", 21)]}

    dropped = prune_superseded_rows(path, forks)

    assert len(dropped) == 1
    remaining = _read_csv(path)
    epochs_by_tag = [(r["run_tag"], int(r["epoch"])) for r in remaining]
    assert ("dicos-p7", 22) not in epochs_by_tag
    assert ("dicos-p7", 21) in epochs_by_tag
    assert ("dicos-c-03", 22) in epochs_by_tag


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


# --------------------------------------------------------------------------
# bound_lineage -- capping a superseded tag at its own fork point for the
# diagnostic-trend builders (2026-08-12)
# --------------------------------------------------------------------------


def test_bound_lineage_caps_a_tag_a_later_lineage_member_forks_from():
    """The real dicos-f-01 incident: dicos-e-02 ran to epoch 54 in full
    before dicos-f-01 forked from it at epoch 47. Without a bound,
    build_diagnostic_trend_figure.py's "later tag wins if present" leaves
    dicos-e-02's now-superseded 48-54 visible until dicos-f-01 catches up,
    which can be hours into a live anneal.
    """
    forks = [("dicos-e-02", "dicos-f-01", 47)]
    assert bound_lineage(
        ["dicos-c-01", "dicos-c-02", "dicos-e-02", "dicos-f-01"], forks
    ) == ["dicos-c-01", "dicos-c-02", "dicos-e-02:47", "dicos-f-01"]


def test_bound_lineage_leaves_the_final_tag_unbounded():
    """The live/newest tag is never anyone's parent within its own lineage,
    so it must never come back with a suffix -- refresh_continuation_outputs.py
    compares the lineage's last entry against the bare --run-tag verbatim.
    """
    forks = [("dicos-c-02", "dicos-e-02", 34)]
    result = bound_lineage(["dicos-c-01", "dicos-c-02", "dicos-e-02"], forks)
    assert result[-1] == "dicos-e-02"


def test_bound_lineage_ignores_a_fork_outside_this_lineage():
    """A fork pair for a different family, or a segment not part of the
    lineage being plotted, must not bound anything here."""
    forks = [("dicos-p7", "dicos-c-03", 21)]  # a different family entirely
    tags = ["dicos-c-01", "dicos-c-02", "dicos-e-02"]
    assert bound_lineage(tags, forks) == tags


def test_bound_lineage_takes_the_tightest_bound_if_a_tag_forked_twice():
    """Defensive: if a tag somehow appears as the parent in two recorded
    forks (not expected in practice, but the function must not silently
    pick the looser one), the smaller fork_epoch wins."""
    forks = [("dicos-e-02", "dicos-e-01", 40), ("dicos-e-02", "dicos-f-01", 34)]
    result = bound_lineage(["dicos-e-02", "dicos-e-01", "dicos-f-01"], forks)
    assert result[0] == "dicos-e-02:34"


def test_bound_lineage_passes_through_a_lineage_with_no_forks():
    tags = ["dicos-p9", "dicos-p10"]
    assert bound_lineage(tags, []) == tags
