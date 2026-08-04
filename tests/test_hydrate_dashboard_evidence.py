from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.hydrate_dashboard_evidence import hydrate_manifest


def _payload(epoch: int, checkpoint: str) -> bytes:
    value = {
        "schema_version": 1,
        "split": "validation",
        "qa": {"pass": True, "test_events_used": 0},
        "sample_count": 1,
        "draws_per_condition": 5,
        "groups": [{"fast_mc": [{}, {}, {}, {}, {}]}],
        "epoch": epoch,
        "checkpoint_sha256": checkpoint,
    }
    return json.dumps(value, sort_keys=True).encode()


def _row(path: str, content: bytes, transport: str = "gcs") -> dict:
    row = {
        "id": "run:joint:0001",
        "path": path,
        "epoch": 1,
        "checkpoint_sha256": "a" * 64,
        "sha256": hashlib.sha256(content).hexdigest(),
    }
    if transport == "gcs":
        row.update({"gcs_object": "object", "gcs_generation": "123"})
    else:
        row["dicos_object"] = "_runs/run/epoch_0001.json"
    return row


def _manifest(path: Path, row: dict) -> Path:
    path.write_text(json.dumps({"epochs": [row]}), encoding="utf-8")
    return path


def test_downloads_and_then_verifies_existing_payload(tmp_path: Path) -> None:
    content = _payload(1, "a" * 64)
    manifest = _manifest(tmp_path / "manifest.json", _row("epoch.json", content))
    destination = tmp_path / "data"
    fetched = []

    def fetch(row: dict) -> bytes:
        fetched.append(row["id"])
        return content

    first = hydrate_manifest(manifest, destination, fetch, fetch)
    second = hydrate_manifest(manifest, destination, fetch, fetch)
    assert first == {"verified": 0, "downloaded_gcs": 1, "downloaded_dicos": 0}
    assert second == {"verified": 1, "downloaded_gcs": 0, "downloaded_dicos": 0}
    assert fetched == ["run:joint:0001"]


def test_uses_dicos_transport(tmp_path: Path) -> None:
    content = _payload(1, "a" * 64)
    manifest = _manifest(
        tmp_path / "manifest.json", _row("epoch.json", content, "dicos")
    )
    result = hydrate_manifest(
        manifest,
        tmp_path / "data",
        lambda _: pytest.fail("GCS fetch must not run"),
        lambda _: content,
    )
    assert result["downloaded_dicos"] == 1


@pytest.mark.parametrize("bad_path", ["../escape.json", "nested/escape.json", "/x"])
def test_rejects_unsafe_destination(tmp_path: Path, bad_path: str) -> None:
    content = _payload(1, "a" * 64)
    manifest = _manifest(tmp_path / "manifest.json", _row(bad_path, content))
    with pytest.raises(RuntimeError, match="unsafe dashboard payload path"):
        hydrate_manifest(manifest, tmp_path / "data", lambda _: content, lambda _: content)


def test_hash_mismatch_leaves_no_payload(tmp_path: Path) -> None:
    content = _payload(1, "a" * 64)
    row = _row("epoch.json", content)
    row["sha256"] = "0" * 64
    manifest = _manifest(tmp_path / "manifest.json", row)
    destination = tmp_path / "data"
    with pytest.raises(RuntimeError, match="immutable payload hash mismatch"):
        hydrate_manifest(manifest, destination, lambda _: content, lambda _: content)
    assert not (destination / "epoch.json").exists()
