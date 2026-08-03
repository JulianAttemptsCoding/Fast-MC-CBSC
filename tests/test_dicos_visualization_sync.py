"""Contracts for merging DiCOS epoch visualisations into the dashboard.

The DiCOS-produced epochs already in `dashboard/public/data/manifest.json` were
assembled by hand, because the Vertex sync speaks GCS only. These tests exist
so the replacement carries the same guarantees the Vertex path does -- an
immutable snapshot cannot be rewritten, and a payload from a different
geometry or a different fixed selection cannot be published beside the
existing epochs, because that is what makes them comparable at all.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import sync_dicos_visualizations as sync  # noqa: E402

GEOMETRY = "c" * 64
SELECTION = "f" * 64


def _payload(epoch: int, geometry: str = GEOMETRY, selection: str = SELECTION) -> dict:
    return {
        "schema_version": 1,
        "kind": "cbsc-zdc-epoch-visual-comparison",
        "split": "validation",
        "epoch": epoch,
        "stage": "joint",
        "sample_count": 1,
        "draws_per_condition": 5,
        "elapsed_seconds": 1.0,
        "checkpoint_sha256": "a" * 64,
        "geometry_sha256": geometry,
        "selection_sha256": selection,
        "groups": [{"fast_mc": [1, 2, 3, 4, 5]}],
        "aggregate": {"trend": {"response_bias_fraction": 0.1}},
        "qa": {"pass": True, "test_events_used": 0},
    }


def _destination(tmp_path: Path) -> Path:
    destination = tmp_path / "data"
    destination.mkdir()
    (destination / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 3,
                "geometry_sha256": GEOMETRY,
                "selection_sha256": SELECTION,
                "epochs": [],
            }
        ),
        encoding="utf-8",
    )
    return destination


def _write(tmp_path: Path, name: str, payload: dict) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_a_payload_is_published_with_dicos_provenance(tmp_path: Path) -> None:
    destination = _destination(tmp_path)
    payload = _write(tmp_path, "e15.json", _payload(15))
    result = sync.sync(
        destination, "dicos-p6-calibrated-lr3e4", [(payload, "_runs/x/e15.json")]
    )
    assert result["written"] == 1
    manifest = json.loads((destination / "manifest.json").read_text())
    row = manifest["epochs"][0]
    assert row["id"] == "dicos-p6-calibrated-lr3e4:joint:0015"
    assert row["path"] == "dicos-p6-calibrated-lr3e4_joint_epoch_0015.json"
    assert row["dicos_object"] == "_runs/x/e15.json"
    assert row["qa_pass"] is True
    assert (destination / row["path"]).is_file()


def test_a_different_selection_is_refused(tmp_path: Path) -> None:
    """The published epochs are only comparable because every one draws the
    same fixed 50 validation conditions."""
    destination = _destination(tmp_path)
    payload = _write(tmp_path, "e15.json", _payload(15, selection="d" * 64))
    with pytest.raises(RuntimeError, match="selection changed"):
        sync.sync(destination, "dicos-p6-x", [(payload, "_runs/x/e15.json")])


def test_a_different_geometry_is_refused(tmp_path: Path) -> None:
    destination = _destination(tmp_path)
    payload = _write(tmp_path, "e15.json", _payload(15, geometry="e" * 64))
    with pytest.raises(RuntimeError, match="geometry changed"):
        sync.sync(destination, "dicos-p6-x", [(payload, "_runs/x/e15.json")])


def test_a_published_snapshot_is_immutable(tmp_path: Path) -> None:
    """Republishing the same snapshot ID with different content would silently
    change what the site claims was verified."""
    destination = _destination(tmp_path)
    first = _write(tmp_path, "e15.json", _payload(15))
    sync.sync(destination, "dicos-p6-x", [(first, "_runs/x/e15.json")])

    mutated = _payload(15)
    mutated["elapsed_seconds"] = 999.0
    second = _write(tmp_path, "e15b.json", mutated)
    with pytest.raises(RuntimeError, match="immutable snapshot"):
        sync.sync(destination, "dicos-p6-x", [(second, "_runs/x/e15.json")])


def test_test_split_use_is_refused(tmp_path: Path) -> None:
    """The site must never carry a test event."""
    destination = _destination(tmp_path)
    tainted = _payload(15)
    tainted["qa"]["test_events_used"] = 1
    payload = _write(tmp_path, "e15.json", tainted)
    with pytest.raises(RuntimeError, match="QA/test-data contract"):
        sync.sync(destination, "dicos-p6-x", [(payload, "_runs/x/e15.json")])


def test_a_failed_qa_payload_is_refused(tmp_path: Path) -> None:
    destination = _destination(tmp_path)
    failed = _payload(15)
    failed["qa"]["pass"] = False
    payload = _write(tmp_path, "e15.json", failed)
    with pytest.raises(RuntimeError, match="QA/test-data contract"):
        sync.sync(destination, "dicos-p6-x", [(payload, "_runs/x/e15.json")])


def test_prior_rows_are_preserved_and_new_ones_appended(tmp_path: Path) -> None:
    destination = _destination(tmp_path)
    manifest_path = destination / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["epochs"] = [
        {
            "id": "dicos-r3-calibrated-lr3e4:joint:0010",
            "epoch": 10,
            "stage": "joint",
            "path": "old.json",
            "sha256": "b" * 64,
        }
    ]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    payload = _write(tmp_path, "e15.json", _payload(15))
    sync.sync(destination, "dicos-p6-calibrated-lr3e4", [(payload, "_runs/x/e15.json")])

    rows = json.loads(manifest_path.read_text())["epochs"]
    assert [r["id"] for r in rows] == [
        "dicos-r3-calibrated-lr3e4:joint:0010",
        "dicos-p6-calibrated-lr3e4:joint:0015",
    ]


def test_it_refuses_to_invent_a_manifest(tmp_path: Path) -> None:
    """Creating one from scratch would drop every previously published epoch."""
    destination = tmp_path / "empty"
    destination.mkdir()
    payload = _write(tmp_path, "e15.json", _payload(15))
    with pytest.raises(RuntimeError, match="from scratch"):
        sync.sync(destination, "dicos-p6-x", [(payload, "_runs/x/e15.json")])
