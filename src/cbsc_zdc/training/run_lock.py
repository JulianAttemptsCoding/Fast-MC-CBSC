"""Exactly one live writer per run directory.

Both training pods mount the same shared filesystem, so "don't start it twice"
is not something a single machine can enforce and not something an operator can
be relied on to remember. Without this, two trainers share a run directory and
the checkpoint writer -- which builds a fixed `progress.pt.tmp` and renames it
-- kills whichever process renames second, leaving the survivor's artifacts with
unprovable provenance.

The lock is a small JSON file created with O_EXCL, naming its holder so the
next reader can tell a live run from a leftover.
"""

from __future__ import annotations

import json
import os
import socket
import time
from dataclasses import dataclass
from pathlib import Path

LOCK_NAME = "run.lock"


class RunLockError(RuntimeError):
    """Raised when a run directory already has a writer, or the lock is broken."""


def _lock_path(run_dir: Path | str) -> Path:
    return Path(run_dir) / LOCK_NAME


def read_run_lock(run_dir: Path | str) -> dict:
    path = _lock_path(run_dir)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise
    except (ValueError, OSError) as error:
        raise RunLockError(
            f"run lock at {path} is unreadable ({error}). Inspect it by hand: "
            "it names the process that should be writing here."
        ) from error


#: Windows raises OSError(winerror=87, "The parameter is incorrect") for a pid
#: that does not exist, where POSIX raises ProcessLookupError. Without this the
#: reclaim path never fires on Windows and every crashed run stays locked.
_WINDOWS_NO_SUCH_PROCESS = 87


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, owned by someone else
    except OSError as error:
        if getattr(error, "winerror", None) == _WINDOWS_NO_SUCH_PROCESS:
            return False
        return True
    return True


@dataclass
class RunLock:
    path: Path

    def release(self) -> None:
        self.path.unlink(missing_ok=True)


def acquire_run_lock(run_dir: Path | str) -> RunLock:
    """Claim `run_dir`, or explain who already holds it.

    A stale lock from a dead process *on this host* is reclaimed, so a crashed
    run does not block its own relaunch -- otherwise people learn to delete
    locks by hand, which defeats the guard. A lock from another host is never
    reclaimed: this process cannot know whether that pid is alive, and that
    host mounts the very same directory.
    """
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    path = _lock_path(run_dir)
    payload = {
        "pid": os.getpid(),
        "host": socket.gethostname(),
        "run_dir": str(run_dir.resolve()),
        "acquired_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    body = json.dumps(payload, indent=2, sort_keys=True) + "\n"

    try:
        handle = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        held = read_run_lock(run_dir)  # raises RunLockError if corrupt
        holder_host = held.get("host")
        holder_pid = int(held.get("pid", -1))
        if holder_host != socket.gethostname():
            raise RunLockError(
                f"{run_dir} is already being written by pid {holder_pid} on "
                f"another host ({holder_host}), since {held.get('acquired_utc')}. "
                "Both hosts share this filesystem. Stop that run before starting "
                f"here, or remove {path} only after confirming it is dead."
            )
        if _pid_alive(holder_pid):
            raise RunLockError(
                f"{run_dir} is already being written by pid {holder_pid} on this "
                f"host since {held.get('acquired_utc')}. Refusing to start a "
                "second writer."
            )
        path.unlink(missing_ok=True)
        handle = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)

    with os.fdopen(handle, "w", encoding="utf-8") as stream:
        stream.write(body)
    return RunLock(path)
