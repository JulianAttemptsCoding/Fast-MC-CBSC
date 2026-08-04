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
import os
import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

import torch


RUN_TAG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")


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
    )


@dataclass(frozen=True)
class QueueResult:
    epoch: int
    queued: bool
    path: Path | None


def queue_checkpoint(last: Path, metrics: Path) -> QueueResult:
    """Copy ``last`` atomically and trust only the epoch inside the copy."""
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
    return wrapper_log.is_file() and "EXIT=" in wrapper_log.read_text(
        encoding="utf-8", errors="ignore"
    )


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

    def __enter__(self) -> "ProducerLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(
                self.path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o644,
            )
        except FileExistsError as exc:
            raise RuntimeError(f"diagnostic producer lock already exists: {self.path}") from exc
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(f"pid={os.getpid()}\n")
        self.acquired = True
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        if self.acquired:
            self.path.unlink(missing_ok=True)
            self.acquired = False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--wrapper-log", required=True)
    parser.add_argument("--run-tag", required=True)
    parser.add_argument("--workdir", type=Path, default=Path.cwd())
    parser.add_argument("--poll-seconds", type=float, default=60.0)
    args = parser.parse_args(argv)

    if args.poll_seconds <= 0:
        parser.error("--poll-seconds must be positive")
    run_tag = validate_run_tag(args.run_tag)
    root = args.workdir.resolve()
    run = resolve_under(root, args.run_dir, "run directory")
    wrapper_log = resolve_under(root, args.wrapper_log, "wrapper log")
    metrics = resolve_under(root, Path("_diag") / run_tag, "diagnostic directory")
    queue = metrics / "queue"
    last = run / "checkpoints" / "last.pt"

    if (queue / "STOP").exists():
        raise RuntimeError(
            f"diagnostic queue already contains STOP; use a new run tag: {queue}"
        )

    with ProducerLock(metrics / "producer.lock"):
        log(f"watching {run}; writing namespaced queue {queue}")
        while True:
            finished = wrapper_finished(wrapper_log)
            latest: QueueResult | None = None
            if last.is_file():
                try:
                    latest = queue_checkpoint(last, metrics)
                    if latest.queued:
                        log(f"queued embedded epoch {latest.epoch}")
                except Exception as exc:  # transient concurrent checkpoint write
                    log(f"checkpoint copy not yet valid: {type(exc).__name__}: {exc}")
                    if finished:
                        log("wrapper finished but final checkpoint is not safely queued; retrying")
            if finished and (not last.exists() or latest is not None):
                write_stop(queue)
                log("wrapper finished; STOP written after latest checkpoint inspection")
                return 0
            time.sleep(args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
