from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "archive_exhibition_snapshot.py"


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def make_source(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    (source / "exhibition" / "nested").mkdir(parents=True)
    (source / "exhibition" / "figure.svg").write_text("<svg/>\n", encoding="utf-8")
    (source / "exhibition" / "nested" / "metrics.json").write_text(
        '{"loss": 1.0}\n', encoding="utf-8"
    )
    git(source, "init")
    git(source, "config", "user.email", "qa@example.invalid")
    git(source, "config", "user.name", "QA")
    git(source, "remote", "add", "origin", "https://example.invalid/source.git")
    git(source, "add", ".")
    git(source, "commit", "-m", "fixture")
    return source


def run_script(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def test_create_and_verify_snapshot(tmp_path: Path) -> None:
    source = make_source(tmp_path)
    snapshot = tmp_path / "archive" / "snapshot-a"
    created = run_script(
        "create",
        "--source-root",
        str(source),
        "--destination",
        str(snapshot),
        "--snapshot-id",
        "snapshot-a",
        "--source-label",
        "test source",
        "--captured-at",
        "2026-08-04T00:00:00+00:00",
    )
    payload = json.loads(created.stdout)
    assert payload["file_count"] == 2
    assert payload["source_git"]["dirty"] is False
    verified = json.loads(
        run_script("verify", "--snapshot-root", str(snapshot)).stdout
    )
    assert verified["status"] == "pass"
    assert verified["sha256s_verified"] == 4


def test_refuses_to_overwrite_snapshot(tmp_path: Path) -> None:
    source = make_source(tmp_path)
    snapshot = tmp_path / "already-there"
    snapshot.mkdir()
    with pytest.raises(subprocess.CalledProcessError):
        run_script(
            "create",
            "--source-root",
            str(source),
            "--destination",
            str(snapshot),
            "--snapshot-id",
            "snapshot-a",
            "--source-label",
            "test source",
            "--captured-at",
            "2026-08-04T00:00:00+00:00",
        )


def test_verify_detects_tampering(tmp_path: Path) -> None:
    source = make_source(tmp_path)
    snapshot = tmp_path / "snapshot-a"
    run_script(
        "create",
        "--source-root",
        str(source),
        "--destination",
        str(snapshot),
        "--snapshot-id",
        "snapshot-a",
        "--source-label",
        "test source",
        "--captured-at",
        "2026-08-04T00:00:00+00:00",
    )
    (snapshot / "exhibition" / "figure.svg").write_text("tampered\n", encoding="utf-8")
    with pytest.raises(subprocess.CalledProcessError):
        run_script("verify", "--snapshot-root", str(snapshot))
