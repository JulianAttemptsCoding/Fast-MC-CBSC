from __future__ import annotations

import pytest

from scripts.sync_vertex_visualizations import (
    _normalize_existing_rows,
    _snapshot_id,
)


def test_snapshot_id_qualifies_repeated_epoch_by_stage() -> None:
    assert _snapshot_id("profile", 0) == "profile:0000"
    assert _snapshot_id("count", 0) == "count:0000"
    assert (
        _snapshot_id("joint", 0, "joint-resume-r1")
        == "joint-resume-r1:joint:0000"
    )


def test_legacy_manifest_rows_are_migrated_without_changing_paths() -> None:
    rows = _normalize_existing_rows(
        {
            "epochs": [
                {
                    "epoch": 2,
                    "stage": "profile",
                    "path": "epoch_0002.json",
                    "sha256": "abc",
                }
            ]
        }
    )
    assert rows == [
        {
            "id": "profile:0002",
            "epoch": 2,
            "stage": "profile",
            "path": "epoch_0002.json",
            "sha256": "abc",
        }
    ]


@pytest.mark.parametrize("stage", ["../count", "Count", "count:bad", ""])
def test_snapshot_id_rejects_unsafe_stage_names(stage: str) -> None:
    with pytest.raises(RuntimeError, match="unsafe visualization stage"):
        _snapshot_id(stage, 0)


@pytest.mark.parametrize("run_label", ["../resume", "Resume", "bad:run", ""])
def test_snapshot_id_rejects_unsafe_run_labels(run_label: str) -> None:
    with pytest.raises(RuntimeError, match="unsafe visualization run-label"):
        _snapshot_id("joint", 0, run_label)
