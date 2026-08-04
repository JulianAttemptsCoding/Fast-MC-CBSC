"""Safely feed completed training checkpoints to a namespaced DiCOS queue.

Run this on the RTX 4090 beside one trainer. The RTX 3090 consumer is
``scripts/dicos_diagnostics.py --watch-dir``. This producer never generates
events and never reads the test split: it only copies a completed ``last.pt``
and names the queued copy from the epoch embedded in that copy.

The run tag is mandatory because different continuation branches reuse absolute
epoch numbers. A flat ``_diag/`` directory previously overwrote valid evidence.

Example, from the DiCOS workdir::

    PYTHONNOUSERSITE=1 .venv/bin/python repo/scripts/dicos_diag_producer.py \
      --run-dir _runs/calibrated_lr1e4_dicos-p11 \
      --wrapper-log _runs/p11lr1e4.log --run-tag dicos-p11
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import socket
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

import torch


RUN_TAG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
EXIT_PATTERN = re.compile(r"^EXIT=(-?\d+)\s*$", re.MULTILINE)


class CheckpointNotAccepted(RuntimeError):
    """Checkpoint exists but lacks the completed epoch acceptance marker."""


def log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def resolve_under(root: Path, value: str | Path, label: str) -> Path:
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"{label} must be a safe workdir-relative path")
    root = root.resolve()
    resolved = (root / relative).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"{label} escapes the DiCOS workdir") from exc
    return resolved


def validate_run_tag(run_tag: str) -> str:
    if not RUN_TAG_PATTERN.fullmatch(run_tag):
        raise ValueError(
            "run tag must contain lowercase letters, digits, and hyphens only"
        )
    return run_tag


def already_handled(queue: Path, done: Path, metrics: Path, epoch: int) -> bool:
    name = f"ckpt_epoch_{epoch:04d}.pt"
    return (
        (queue / name).exists()
        or (done / name).exists()
        or (done / f"{name}.failed").exists()
        or (metrics / f"metrics_epoch_{epoch:04d}.json").exists()
        or (metrics / f"metrics_epoch_{epoch:04d}.failed.json").exists()
    )


@dataclass(frozen=True)
class QueueResult:
    epoch: int
    queued: bool
    path: Path | None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def queue_checkpoint(last: Path, reports: Path, metrics: Path) -> QueueResult:
    """Queue only a checkpoint proved accepted by its per-epoch marker.

    The trainer writes ``last.pt`` before its required visualization gate, but
    writes the progress marker only after that gate succeeds.  Matching the
    marker's hash to the copied bytes prevents a failed or racing checkpoint
    from reaching the independent diagnostic consumer.
    """
    queue = metrics / "queue"
    done = queue / "done"
    queue.mkdir(parents=True, exist_ok=True)
    done.mkdir(parents=True, exist_ok=True)
    staging = queue / f".staging-{os.getpid()}.pt"
    staging.unlink(missing_ok=True)
    try:
        shutil.copy2(last, staging)
        payload = torch.load(staging, map_location="cpu", weights_only=False)
        if not isinstance(payload, dict):
            raise ValueError("checkpoint payload is not a mapping")
        epoch = int(payload.get("epoch", -1))
        if epoch < 0:
            raise ValueError("checkpoint contains no valid epoch")
        checkpoint_sha256 = _sha256(staging)
        marker_path = reports / f"progress_epoch_{epoch:04d}.json"
        if not marker_path.is_file():
            raise CheckpointNotAccepted(
                f"epoch {epoch} has no completed progress marker"
            )
        try:
            marker = json.loads(marker_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CheckpointNotAccepted(
                f"epoch {epoch} progress marker is unreadable"
            ) from exc
        if int(marker.get("epoch", -1)) != epoch:
            raise CheckpointNotAccepted("progress marker epoch does not match checkpoint")
        if marker.get("last_checkpoint_sha256") != checkpoint_sha256:
            raise CheckpointNotAccepted(
                "progress marker hash does not match copied checkpoint"
            )
        if already_handled(queue, done, metrics, epoch):
            staging.unlink(missing_ok=True)
            return QueueResult(epoch=epoch, queued=False, path=None)
        destination = queue / f"ckpt_epoch_{epoch:04d}.pt"
        staging.replace(destination)
        return QueueResult(epoch=epoch, queued=True, path=destination)
    except Exception:
        staging.unlink(missing_ok=True)
        raise


def wrapper_finished(wrapper_log: Path) -> bool:
    return wrapper_exit_code(wrapper_log) is not None


def wrapper_exit_code(wrapper_log: Path) -> int | None:
    if not wrapper_log.is_file():
        return None
    matches = EXIT_PATTERN.findall(
        wrapper_log.read_text(encoding="utf-8", errors="ignore")
    )
    return int(matches[-1]) if matches else None


def write_json_atomic(payload: dict, destination: Path) -> Path:
    temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(destination)
    return destination


def write_producer_failure(
    metrics: Path,
    *,
    exit_code: int | None,
    last: Path,
    error: Exception,
) -> Path:
    payload = {
        "kind": "cbsc-zdc-diagnostic-producer-failure",
        "schema_version": 1,
        "scientific_status": "quarantined; not accepted for diagnostics or selection",
        "wrapper_exit_code": exit_code,
        "checkpoint_exists": last.is_file(),
        "error_type": type(error).__name__,
        "error": str(error),
    }
    if last.is_file():
        try:
            payload["checkpoint_sha256"] = _sha256(last)
            checkpoint = torch.load(last, map_location="cpu", weights_only=False)
            payload["checkpoint_epoch"] = int(checkpoint.get("epoch", -1))
        except Exception as inspect_error:  # preserve the primary failure too
            payload["checkpoint_inspection_error"] = repr(inspect_error)
    metrics.mkdir(parents=True, exist_ok=True)
    return write_json_atomic(payload, metrics / "producer_failure.json")


def write_stop(queue: Path) -> Path:
    temporary = queue / f".STOP-{os.getpid()}.tmp"
    destination = queue / "STOP"
    temporary.write_text("training finished; drain queue before exit\n", encoding="utf-8")
    temporary.replace(destination)
    return destination


class ProducerLock:
    """One producer per run tag, using an atomic shared-filesystem create."""

    def __init__(self, path: Path):
        self.path = path
        self.acquired = False
        self.owner = {
            "hostname": socket.gethostname(),
            "pid": os.getpid(),
            "nonce": uuid.uuid4().hex,
        }

    @staticmethod
    def _pid_alive(pid: int) -> bool:
        if pid <= 0:
            return False
        if os.name == "nt":
            # Never use os.kill(pid, 0) as a liveness probe on Windows: its
            # implementation can terminate the process being inspected.
            import ctypes

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.OpenProcess.argtypes = [
                ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32
            ]
            kernel32.OpenProcess.restype = ctypes.c_void_p
            kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
            kernel32.CloseHandle.restype = ctypes.c_int
            handle = kernel32.OpenProcess(0x1000, False, int(pid))
            if handle:
                kernel32.CloseHandle(handle)
                return True
            return ctypes.get_last_error() == 5
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    def _reclaim_if_provably_stale(self) -> bool:
        try:
            owner = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        if owner.get("hostname") != self.owner["hostname"]:
            return False
        try:
            pid = int(owner["pid"])
        except (KeyError, TypeError, ValueError):
            return False
        if self._pid_alive(pid):
            return False
        self.path.unlink(missing_ok=True)
        return True

    def __enter__(self) -> "ProducerLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        for attempt in range(2):
            try:
                descriptor = os.open(
                    self.path,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                    0o644,
                )
                break
            except FileExistsError as exc:
                if attempt == 0 and self._reclaim_if_provably_stale():
                    continue
                raise RuntimeError(
                    f"diagnostic producer lock already exists: {self.path}"
                ) from exc
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(self.owner, handle, sort_keys=True)
            handle.write("\n")
        self.acquired = True
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        if self.acquired:
            try:
                current = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                current = None
            if current == self.owner:
                self.path.unlink(missing_ok=True)
            self.acquired = False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--wrapper-log", required=True)
    parser.add_argument("--run-tag", required=True)
    parser.add_argument("--workdir", type=Path, default=Path.cwd())
    parser.add_argument("--poll-seconds", type=float, default=60.0)
    parser.add_argument("--final-retries", type=int, default=3)
    parser.add_argument("--final-retry-seconds", type=float, default=5.0)
    args = parser.parse_args(argv)

    if args.poll_seconds <= 0:
        parser.error("--poll-seconds must be positive")
    if args.final_retries < 0 or args.final_retry_seconds <= 0:
        parser.error("final retries must be non-negative and retry seconds positive")
    run_tag = validate_run_tag(args.run_tag)
    root = args.workdir.resolve()
    run = resolve_under(root, args.run_dir, "run directory")
    wrapper_log = resolve_under(root, args.wrapper_log, "wrapper log")
    metrics = resolve_under(root, Path("_diag") / run_tag, "diagnostic directory")
    queue = metrics / "queue"
    last = run / "checkpoints" / "last.pt"
    reports = run / "reports"

    if (queue / "STOP").exists():
        raise RuntimeError(
            f"diagnostic queue already contains STOP; use a new run tag: {queue}"
        )

    with ProducerLock(metrics / "producer.lock"):
        log(f"watching {run}; writing namespaced queue {queue}")
        final_failures = 0
        while True:
            exit_code = wrapper_exit_code(wrapper_log)
            finished = exit_code is not None
            latest: QueueResult | None = None
            checkpoint_error: Exception | None = None
            if last.is_file():
                try:
                    latest = queue_checkpoint(last, reports, metrics)
                    if latest.queued:
                        log(f"queued embedded epoch {latest.epoch}")
                except Exception as exc:  # transient concurrent checkpoint write
                    checkpoint_error = exc
                    log(f"checkpoint copy not yet valid: {type(exc).__name__}: {exc}")
                    if finished:
                        final_failures += 1
                        if final_failures <= args.final_retries:
                            log(
                                "wrapper finished but final checkpoint is not safely "
                                f"queued; final retry {final_failures}/{args.final_retries}"
                            )
                            time.sleep(args.final_retry_seconds)
                            continue
            if finished and latest is not None and exit_code == 0:
                write_stop(queue)
                log("wrapper succeeded; accepted final checkpoint inspected; STOP written")
                return 0
            if finished:
                failure = checkpoint_error or RuntimeError(
                    "wrapper failed" if exit_code else "wrapper ended without an accepted checkpoint"
                )
                write_producer_failure(
                    metrics, exit_code=exit_code, last=last, error=failure
                )
                write_stop(queue)
                log("wrapper/final checkpoint failed; evidence quarantined; STOP written")
                return 1
            time.sleep(args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
