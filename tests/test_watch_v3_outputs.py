"""The v3 watcher: one holder, safe beside a live trainer, honest logging."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def watcher():
    spec = importlib.util.spec_from_file_location(
        "watch_v3_outputs", ROOT / "scripts" / "watch_v3_outputs.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_live_holder_blocks_a_second_watcher(watcher, tmp_path, monkeypatch):
    lock = tmp_path / "watch.lock"
    monkeypatch.setattr(watcher, "STATE_DIR", tmp_path)
    monkeypatch.setattr(watcher, "LOCK_PATH", lock)
    monkeypatch.setattr(watcher, "LOG_PATH", tmp_path / "watch.log")
    # A different pid: acquire_lock is deliberately re-entrant for the
    # current process, so reusing our own pid would test nothing.
    lock.write_text(json.dumps({"pid": os.getpid() + 1, "acquired": "x"}), encoding="utf-8")
    monkeypatch.setattr(watcher, "pid_alive", lambda pid: True)
    with pytest.raises(SystemExit, match="another v3 watcher"):
        watcher.acquire_lock()


def test_a_stale_lock_does_not_block_forever(watcher, tmp_path, monkeypatch):
    """A killed watcher must not wedge the next run.

    Presence of a lock file is not evidence of a live holder, which is the same
    discipline AGENTS.md requires of a DiCOS trainer.
    """
    lock = tmp_path / "watch.lock"
    monkeypatch.setattr(watcher, "STATE_DIR", tmp_path)
    monkeypatch.setattr(watcher, "LOCK_PATH", lock)
    monkeypatch.setattr(watcher, "LOG_PATH", tmp_path / "watch.log")
    lock.write_text(json.dumps({"pid": 999999, "acquired": "x"}), encoding="utf-8")
    monkeypatch.setattr(watcher, "pid_alive", lambda pid: False)
    watcher.acquire_lock()
    assert json.loads(lock.read_text(encoding="utf-8"))["pid"] == os.getpid()


def test_pid_alive_rejects_a_nonsense_pid(watcher):
    assert watcher.pid_alive(-1) is False
    assert watcher.pid_alive(0) is False


def test_the_watcher_only_touches_running_rows(watcher):
    """A completed row's evidence is immutable; re-importing it is not the job."""
    source = (ROOT / "scripts" / "watch_v3_outputs.py").read_text(encoding="utf-8")
    assert 'row["status"] != "running"' in source


def test_the_watcher_never_writes_to_a_pod(watcher):
    """Read-only against the pods, so it is safe beside a live trainer."""
    source = (ROOT / "scripts" / "watch_v3_outputs.py").read_text(encoding="utf-8")
    for forbidden in ("dicos.py put", "dicos.py start", "dicos.py mkdir", "dicos.py stop"):
        assert forbidden not in source


def test_an_import_failure_does_not_kill_the_loop(watcher, monkeypatch, tmp_path):
    """One unreachable pass must not stop every later refresh."""
    monkeypatch.setattr(watcher, "run", lambda *a, **k: (1, "", "boom"))
    monkeypatch.setattr(watcher, "STATE_DIR", tmp_path)
    monkeypatch.setattr(watcher, "LOG_PATH", tmp_path / "watch.log")
    assert watcher.refresh_row("M0-fresh") is None


def test_a_completed_horizon_asks_for_a_disposition_not_a_verdict(watcher):
    source = (ROOT / "scripts" / "watch_v3_outputs.py").read_text(encoding="utf-8")
    assert "a negative result is a result" in source
    assert "retains the\n                \"simpler parent" in source or "simpler parent" in source
