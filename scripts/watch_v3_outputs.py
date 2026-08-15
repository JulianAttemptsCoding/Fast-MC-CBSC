#!/usr/bin/env python
"""Keep the v3 screening figures and metrics current while rows are training.

`watch_campaign_outputs.py` does the same job for the v2.2 learning-rate
families.  It cannot cover v3: screening rows live in their own record --
`exhibition/data/v3_screening_rows.json` and `v3_screening_history.csv` --
precisely so a different architecture never lands on a v2.2 family's continuous
loss axis, and that record has its own importer and its own builder.

Each pass, for every row whose status is `running`:

  1. import whatever epochs have landed, hash-verified against the pod;
  2. rebuild the screening figures and summary;
  3. rebuild the metrics catalog so the gallery stays complete;
  4. append one compact line to `logs.md` per newly observed epoch, and a
     paragraph when a row reaches a new best or finishes its horizon.

**Runs on the workstation, not a pod.** The exhibition builders need matplotlib,
which is not installed on DiCOS, and writing into a pod's repo checkout would
dirty the tree the pre-launch gate depends on.  It therefore only updates while
this machine is on and this process is alive.

It is read-only with respect to the pods and never writes into a run directory,
so it is safe to run beside a live trainer.  The importer takes epochs from
`history.csv` and requires a passing invariant report for each, and the trainer
writes the invariant report *before* the history row, so a partially written
epoch is never imported.

Usage:
    python scripts/watch_v3_outputs.py                    # foreground loop
    python scripts/watch_v3_outputs.py --interval-seconds 600
    python scripts/watch_v3_outputs.py --once
    python scripts/watch_v3_outputs.py --status
    python scripts/watch_v3_outputs.py --stop
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REGISTRY = ROOT / "exhibition" / "data" / "v3_screening_rows.json"
SUMMARY = ROOT / "exhibition" / "current" / "v3_screening" / "screening_summary.json"
LOGS_MD = ROOT / "logs.md"
STATE_DIR = ROOT / "_watch" / "v3_refresh"
LOCK_PATH = STATE_DIR / "watch.lock"
STOP_PATH = STATE_DIR / "stop"
SEEN_PATH = STATE_DIR / "seen.json"
LOG_PATH = STATE_DIR / "watch.log"

DEFAULT_INTERVAL_SECONDS = 600


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def pid_alive(pid: int) -> bool:
    """True if the pid is a live process on this host."""
    if pid <= 0:
        return False
    if os.name == "nt":
        out = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True, text=True,
        ).stdout
        return str(pid) in out
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def watch_log(message: str) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(f"[{utcnow()}] {message}\n")
    print(f"[{utcnow()}] {message}", flush=True)


def append_logs_md(text: str) -> None:
    with LOGS_MD.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def acquire_lock() -> None:
    """Refuse a second watcher, but only against a genuinely live holder.

    A stale lock from a killed process must not block the next run forever, so
    the held pid is checked against the process table rather than the lock
    file's mere existence -- the same discipline AGENTS.md requires of a trainer.
    """
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if LOCK_PATH.exists():
        try:
            holder = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
            pid = int(holder.get("pid", -1))
        except Exception:
            pid = -1
        if pid_alive(pid) and pid != os.getpid():
            raise SystemExit(
                f"another v3 watcher holds {LOCK_PATH} (pid {pid}); "
                "use --stop to ask it to exit"
            )
        watch_log(f"clearing stale lock from pid {pid}")
    LOCK_PATH.write_text(
        json.dumps({"pid": os.getpid(), "acquired": utcnow()}) + "\n",
        encoding="utf-8", newline="\n",
    )


def release_lock() -> None:
    LOCK_PATH.unlink(missing_ok=True)


def should_stop() -> bool:
    if STOP_PATH.exists():
        STOP_PATH.unlink(missing_ok=True)
        return True
    return False


def load_seen() -> dict:
    if SEEN_PATH.is_file():
        try:
            return json.loads(SEEN_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_seen(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    temporary = SEEN_PATH.with_name(f".{SEEN_PATH.name}.tmp")
    temporary.write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )
    temporary.replace(SEEN_PATH)


def registry_rows() -> list[dict]:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))["rows"]


def run(script: str, *args: str) -> tuple[int, str, str]:
    env = dict(os.environ, PYTHONPATH="src")
    result = subprocess.run(
        [sys.executable, script, *args],
        cwd=ROOT, env=env, capture_output=True, text=True,
    )
    return result.returncode, result.stdout, result.stderr


def refresh_row(row_id: str) -> dict | None:
    """Import one row's epochs. Returns the import record, or None on failure.

    A failure is logged and swallowed rather than raised: a watcher that dies
    because one pass could not reach the pod stops updating everything else,
    and the next pass will retry.
    """
    code, out, err = run("scripts/import_v3_screening_run.py", "--row", row_id)
    if code != 0:
        watch_log(f"{row_id}: import failed: {(err or out).strip().splitlines()[-1:]}")
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        watch_log(f"{row_id}: import produced unparseable output")
        return None


def rebuild() -> bool:
    for script in (
        "exhibition/build_v3_screening_figure.py",
        "exhibition/build_metrics_catalog.py",
    ):
        code, out, err = run(script)
        if code != 0:
            watch_log(f"rebuild failed in {script}: {(err or out).strip()[-300:]}")
            return False
    return True


def run_once(seen: dict) -> dict:
    """One pass. Returns the updated seen-state."""
    updated = dict(seen)
    changed = False

    for row in registry_rows():
        if row["status"] != "running":
            continue
        row_id = row["row_id"]
        record = refresh_row(row_id)
        if record is None:
            continue

        previous = updated.get(row_id, {})
        last_epoch = int(previous.get("last_epoch", -1))
        best_loss = previous.get("best_validation_loss")
        newest = int(record["epoch_range"][1])
        if newest <= last_epoch:
            continue

        changed = True
        lines = [
            f"- {row_id} e{newest}: val {record['best_validation_loss']:.6f} best "
            f"@ e{record['best_epoch']}, {record['epochs_imported']}/"
            f"{row['horizon_epochs']} epochs, invariants "
            f"{record['invariant_reports']}/{record['epochs_imported']} pass"
        ]
        improved = best_loss is None or record["best_validation_loss"] < float(best_loss)
        if improved:
            lines.append(
                f"  new best for this row: {record['best_validation_loss']:.6f} "
                f"(parent {record['parent_validation_loss']:.6f}, "
                f"delta {record['delta_vs_parent']:+.6f})"
            )
        append_logs_md("\n".join(lines) + "\n")
        watch_log(
            f"{row_id}: {record['epochs_imported']} epochs, best "
            f"{record['best_validation_loss']:.6f} @ e{record['best_epoch']}"
        )

        updated[row_id] = {
            "last_epoch": newest,
            "epochs_imported": record["epochs_imported"],
            "best_epoch": record["best_epoch"],
            "best_validation_loss": record["best_validation_loss"],
            "delta_vs_parent": record["delta_vs_parent"],
            "updated": utcnow(),
        }

        if record["epochs_imported"] >= int(row["horizon_epochs"]):
            append_logs_md(
                f"\n**{row_id} reached its full {row['horizon_epochs']}-epoch horizon.** "
                f"Best validation loss {record['best_validation_loss']:.6f} at epoch "
                f"{record['best_epoch']}, against parent "
                f"{record['parent_validation_loss']:.6f} "
                f"({record['delta_vs_parent']:+.6f}). Set its `status` to `complete` "
                "and record a `disposition` in exhibition/data/v3_screening_rows.json; "
                "a negative result is a result, and the promotion rule retains the "
                "simpler parent when an improvement is unresolved.\n"
            )
            watch_log(f"{row_id}: horizon complete, awaiting a disposition")

    if changed:
        if rebuild():
            watch_log("figures, summary and metrics catalog rebuilt")
        save_seen(updated)
    return updated


def run_loop(interval_seconds: int) -> int:
    watch_log(f"v3 watcher started, interval {interval_seconds}s")
    seen = load_seen()
    try:
        while True:
            seen = run_once(seen)
            if should_stop():
                watch_log("stop requested; exiting")
                return 0
            # Keep watching while anything is queued. A queue script starts
            # the next row minutes after the previous one ends, and exiting on
            # that gap would stop the figures updating for the rest of the
            # tranche -- which is exactly what happened when M0 finished and S2
            # had not yet been marked running.
            pending = [
                r for r in registry_rows() if r["status"] in {"running", "queued"}
            ]
            if not pending:
                watch_log("no row is running or queued; exiting")
                return 0
            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        watch_log("interrupted; exiting")
        return 0


def status_report() -> int:
    if not LOCK_PATH.exists():
        print("no v3 watcher lock present")
    else:
        try:
            holder = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
            pid = int(holder.get("pid", -1))
            print(f"lock held by pid {pid}, alive={pid_alive(pid)}, "
                  f"acquired {holder.get('acquired')}")
        except Exception:
            print(f"lock file at {LOCK_PATH} is unreadable")
    for row_id, state in sorted(load_seen().items()):
        print(f"{row_id}: e{state['last_epoch']} best "
              f"{state['best_validation_loss']:.6f} @ e{state['best_epoch']} "
              f"({state['delta_vs_parent']:+.6f} vs parent)")
    for row in registry_rows():
        print(f"registry {row['row_id']}: {row['status']}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interval-seconds", type=int, default=DEFAULT_INTERVAL_SECONDS)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--stop", action="store_true")
    args = parser.parse_args(argv)

    if args.status:
        return status_report()
    if args.stop:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        STOP_PATH.write_text(utcnow() + "\n", encoding="utf-8", newline="\n")
        print(f"stop requested at {STOP_PATH}")
        return 0

    acquire_lock()
    try:
        if args.once:
            run_once(load_seen())
            rebuild()
            return 0
        return run_loop(args.interval_seconds)
    finally:
        release_lock()


if __name__ == "__main__":
    raise SystemExit(main())
