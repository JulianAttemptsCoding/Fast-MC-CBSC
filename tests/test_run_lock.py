"""A run directory may have exactly one live writer.

Two trainers sharing a run directory corrupted three runs in one session: the
checkpoint writer builds a fixed `progress.pt.tmp` and renames it, so whichever
process renames second dies with FileNotFoundError, and the survivor's
artifacts have unprovable provenance. Both pods mount the same filesystem, so
the second writer can be on another machine entirely.

The lock is what makes "one writer" checkable instead of a thing to remember.
"""

import os
import socket
from pathlib import Path

import pytest

from cbsc_zdc.training.run_lock import RunLockError, acquire_run_lock, read_run_lock


def test_a_second_writer_is_refused(tmp_path: Path) -> None:
    acquire_run_lock(tmp_path)
    with pytest.raises(RunLockError, match="already being written"):
        acquire_run_lock(tmp_path)


def test_the_lock_records_who_holds_it(tmp_path: Path) -> None:
    """The error has to name the holder, or the next person cannot tell a live
    run from a leftover file and will just delete it."""
    acquire_run_lock(tmp_path)
    held = read_run_lock(tmp_path)
    assert held["pid"] == os.getpid()
    assert held["host"] == socket.gethostname()
    assert held["run_dir"] == str(tmp_path.resolve())


def test_a_lock_from_a_dead_process_on_this_host_is_reclaimed(tmp_path: Path) -> None:
    """A crashed run must not block its own relaunch forever -- that would push
    people toward deleting locks by hand, which defeats the guard."""
    acquire_run_lock(tmp_path)
    stale = read_run_lock(tmp_path)
    stale["pid"] = 2**22  # a pid that cannot be running
    (tmp_path / "run.lock").write_text(__import__("json").dumps(stale))

    acquire_run_lock(tmp_path)
    assert read_run_lock(tmp_path)["pid"] == os.getpid()


def test_a_lock_from_another_host_is_never_reclaimed(tmp_path: Path) -> None:
    """Liveness of a pid on a different machine is unknowable from here, and
    the other machine mounts this same directory. Refuse and say why."""
    acquire_run_lock(tmp_path)
    other = read_run_lock(tmp_path)
    other["host"] = "some-other-pod"
    other["pid"] = 2**22
    (tmp_path / "run.lock").write_text(__import__("json").dumps(other))

    with pytest.raises(RunLockError, match="another host"):
        acquire_run_lock(tmp_path)


def test_releasing_allows_a_later_run(tmp_path: Path) -> None:
    lock = acquire_run_lock(tmp_path)
    lock.release()
    acquire_run_lock(tmp_path)


def test_a_corrupt_lock_is_refused_not_ignored(tmp_path: Path) -> None:
    """Silently overwriting an unreadable lock is how a guard becomes theatre."""
    (tmp_path / "run.lock").write_text("{not json")
    with pytest.raises(RunLockError, match="unreadable"):
        acquire_run_lock(tmp_path)
