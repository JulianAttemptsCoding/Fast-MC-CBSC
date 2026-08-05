#!/usr/bin/env python
"""Keep local figures and metrics current for as long as a campaign is training.

Wraps `scripts/refresh_campaign_outputs.refresh()` in a polling loop so the
exhibition never falls far behind a live run. **Runs on the workstation, not a
pod** -- the exhibition builders need matplotlib and Node, neither of which is
on DiCOS, and writing into a pod's repo checkout would dirty the tree the
pre-launch gate depends on. It follows from this that the loop only updates
anything while the workstation itself is on and this process is alive; it
cannot run unattended if the machine is shut down.

Every epoch that lands is one compact line appended to `logs.md`, per this
project's own rule (CLAUDE.md) to record evidence as it happens rather than at
the end of a session. A new family-level best, a family advancing, or the
campaign reaching a terminal state gets its own paragraph the same way a manual
session would write one.

Usage:
    python scripts/watch_campaign_outputs.py                    # foreground loop
    python scripts/watch_campaign_outputs.py --interval-seconds 300
    python scripts/watch_campaign_outputs.py --once             # single pass, no loop
    python scripts/watch_campaign_outputs.py --status           # report and exit
    python scripts/watch_campaign_outputs.py --stop             # ask a running watcher to exit

Only one instance may hold the lock at a time. A second launch checks the held
pid against the live process table -- not just the presence of a lock file --
before refusing to start, the same discipline `AGENTS.md` requires for a DiCOS
trainer.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import refresh_campaign_outputs as rco  # noqa: E402

STATE_DIR = ROOT / "_watch" / "campaign_refresh"
LOCK_PATH = STATE_DIR / "watch.lock"
STOP_PATH = STATE_DIR / "WATCH_STOP"
LOG_PATH = STATE_DIR / "watch.log"
LAST_KNOWN_PATH = STATE_DIR / "last_known.json"
LOGS_MD = ROOT / "logs.md"
HISTORY_CSV = ROOT / "exhibition" / "data" / "continuation_history.csv"

DEFAULT_INTERVAL_SECONDS = 300
SLEEP_TICK_SECONDS = 5
TERMINAL_STATUSES = {"halted", "campaign_complete", "exhausted"}


def utcnow() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def pid_alive(pid: int) -> bool:
    """True if `pid` names a live process. Windows and POSIX both handled.

    `os.kill(pid, 0)` is a liveness probe on POSIX (raises if the pid is gone)
    but is not meaningful the same way on Windows, so `tasklist` is used there
    instead of trusting a stale lock file's mere presence.
    """
    if pid <= 0:
        return False
    if sys.platform == "win32":
        out = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}"],
            capture_output=True, text=True,
        ).stdout
        return str(pid) in out
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def watch_log(message: str, *, log_path: Path = LOG_PATH, state_dir: Path = STATE_DIR,
             _print: bool = True) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    line = f"[{utcnow()}] {message}"
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    if _print:
        print(line, flush=True)


def append_logs_md(text: str, *, logs_path: Path = LOGS_MD) -> None:
    with logs_path.open("ab") as handle:
        handle.write(text.replace("\n", "\r\n").encode("utf-8"))


def acquire_lock(*, lock_path: Path = LOCK_PATH, state_dir: Path = STATE_DIR,
                 log_path: Path = LOG_PATH) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    if lock_path.exists():
        try:
            holder = json.loads(lock_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            holder = {}
        pid = int(holder.get("pid", -1))
        if pid_alive(pid):
            raise SystemExit(
                f"another watcher is already running: pid {pid}, started "
                f"{holder.get('started_at', '?')}. Use --status to inspect it "
                "or --stop to ask it to exit gracefully."
            )
        watch_log(f"reclaiming stale lock from dead pid {pid}", log_path=log_path,
                  state_dir=state_dir)
    lock_path.write_text(
        json.dumps({"pid": os.getpid(), "started_at": utcnow()}), encoding="utf-8"
    )


def release_lock(*, lock_path: Path = LOCK_PATH) -> None:
    lock_path.unlink(missing_ok=True)


def should_stop(*, stop_path: Path = STOP_PATH) -> bool:
    if stop_path.exists():
        stop_path.unlink(missing_ok=True)
        return True
    return False


def load_last_known(*, path: Path = LAST_KNOWN_PATH) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return {"families": {}, "chain_index": None, "status": None}


def save_last_known(state: dict, *, path: Path = LAST_KNOWN_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp.replace(path)


def read_bests(*, history_path: Path = HISTORY_CSV) -> dict[str, tuple[float, int, str]]:
    """`family -> (best_loss, epoch, run_tag)` read from the continuation history.

    Delegates to `refresh_campaign_outputs.family_bests` so this and the
    campaign's own end-of-pass champion selection can never compute two
    different answers to "who is winning." Kept as a thin wrapper (rather than
    calling `rco.family_bests` directly everywhere) so the override path stays
    a keyword-only `history_path`, matching every other function in this file.
    """
    return rco.family_bests(history_path=history_path)


def compute_deltas(
    previous: dict, result: dict, bests_before: dict, bests_after: dict
) -> list[str]:
    """Compact, one-line-per-change description of what one refresh pass moved.

    Pure and independent of the pod, the real filesystem, and the clock, so it
    is unit-testable in isolation from everything else in this file.
    """
    lines: list[str] = []
    prev_families = previous.get("families", {}) or {}

    for family, entry in (result.get("families") or {}).items():
        epoch = entry.get("epoch")
        if epoch is None:
            continue
        prev_epoch = (prev_families.get(family) or {}).get("epoch")
        if prev_epoch is not None and epoch <= prev_epoch:
            continue
        tag = entry.get("newest_tag")
        best_after = bests_after.get(family)
        best_before = bests_before.get(family)
        if best_after is not None and (
            best_before is None or best_after[0] < best_before[0] - 1e-12
        ):
            loss, best_epoch, best_tag = best_after
            improvement = (
                f", improving on {best_before[0]:.6f} by {best_before[0] - loss:.6f}"
                if best_before is not None else ""
            )
            lines.append(
                f"NEW BEST: {family} reached validation {loss:.6f} at epoch "
                f"{best_epoch} ({best_tag}){improvement}"
            )
        loss_text = ""
        if best_after is not None:
            loss, best_epoch, best_tag = best_after
            loss_text = f", best so far {loss:.6f} @ e{best_epoch} ({best_tag})"
        lines.append(f"{family}/{tag} epoch {epoch} imported{loss_text}")

    if result.get("chain_index") != previous.get("chain_index"):
        lines.append(
            f"campaign advanced: chain_index {previous.get('chain_index')} -> "
            f"{result.get('chain_index')}"
        )
    if result.get("status") != previous.get("status"):
        lines.append(
            f"campaign status: {previous.get('status')} -> {result.get('status')}"
        )
    return lines


def run_once(
    plan: dict, scratch: Path, last_known: dict, *, history_path: Path = HISTORY_CSV
) -> tuple[dict, list[str]]:
    bests_before = read_bests(history_path=history_path)
    result = rco.refresh(plan, scratch, dry_run=False)
    bests_after = read_bests(history_path=history_path)
    deltas = list(result.get("pruned_history_rows") or [])
    deltas += compute_deltas(last_known, result, bests_before, bests_after)
    return result, deltas


def run_loop(
    plan: dict,
    scratch: Path,
    interval_seconds: int,
    *,
    sleep_fn=time.sleep,
    run_once_fn=run_once,
    max_iterations: int | None = None,
    last_known_path: Path = LAST_KNOWN_PATH,
    log_path: Path = LOG_PATH,
    state_dir: Path = STATE_DIR,
    logs_path: Path = LOGS_MD,
    stop_path: Path = STOP_PATH,
) -> int:
    last_known = load_last_known(path=last_known_path)
    watch_log(
        f"watcher started, pid {os.getpid()}, interval {interval_seconds}s, "
        f"plan {plan['campaign_id']}",
        log_path=log_path, state_dir=state_dir,
    )
    append_logs_md(
        f"\n### {utcnow()[:10]} — campaign figure/metric watcher started\n\n"
        f"`scripts/watch_campaign_outputs.py` started against campaign "
        f"`{plan['campaign_id']}`, polling every {interval_seconds}s. It keeps "
        "figures and metrics current on the workstation for as long as the "
        "campaign is training and exits on its own once the campaign reaches a "
        "terminal state. It requires the workstation to stay on; nothing about "
        "it runs on a pod.\n",
        logs_path=logs_path,
    )

    iterations = 0
    exit_status = "stopped"
    stop_now = False

    while not stop_now:
        if should_stop(stop_path=stop_path):
            watch_log("stop requested, exiting", log_path=log_path, state_dir=state_dir)
            exit_status = "stop requested"
            break

        try:
            result, deltas = run_once_fn(plan, scratch, last_known)
        except SystemExit as error:
            watch_log(f"refresh failed, will retry next interval: {error}",
                      log_path=log_path, state_dir=state_dir)
            result, deltas = None, []
        except Exception as error:  # noqa: BLE001 -- keep the loop alive on any failure
            watch_log(f"refresh raised {type(error).__name__}: {error}; "
                      "will retry next interval", log_path=log_path, state_dir=state_dir)
            result, deltas = None, []

        if result is not None:
            if deltas:
                for line in deltas:
                    watch_log(line, log_path=log_path, state_dir=state_dir)
                append_logs_md(
                    "\n" + "\n".join(f"- {line}" for line in deltas) + "\n",
                    logs_path=logs_path,
                )
            else:
                watch_log("no new evidence this pass", log_path=log_path,
                          state_dir=state_dir)
            last_known = {
                "families": result.get("families", {}),
                "chain_index": result.get("chain_index"),
                "status": result.get("status"),
            }
            save_last_known(last_known, path=last_known_path)

            if result.get("status") in TERMINAL_STATUSES:
                watch_log(
                    f"campaign reached terminal status {result.get('status')!r}; "
                    "exiting",
                    log_path=log_path, state_dir=state_dir,
                )
                exit_status = f"campaign {result.get('status')}"
                break

        iterations += 1
        if max_iterations is not None and iterations >= max_iterations:
            exit_status = "max iterations reached"
            break

        waited = 0
        while waited < interval_seconds:
            if should_stop(stop_path=stop_path):
                watch_log("stop requested during sleep, exiting",
                          log_path=log_path, state_dir=state_dir)
                exit_status = "stop requested"
                stop_now = True
                break
            sleep_fn(min(SLEEP_TICK_SECONDS, interval_seconds - waited))
            waited += SLEEP_TICK_SECONDS

    watch_log(f"watcher exiting: {exit_status}", log_path=log_path, state_dir=state_dir)
    append_logs_md(
        f"\n### {utcnow()[:10]} — campaign figure/metric watcher stopped\n\n"
        f"Exit reason: {exit_status}.\n",
        logs_path=logs_path,
    )
    return 0


def status_report() -> int:
    if not LOCK_PATH.exists():
        print("no watcher lock present; not running (or never started)")
        return 1
    try:
        holder = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        print(f"lock file at {LOCK_PATH} is unreadable")
        return 1
    pid = int(holder.get("pid", -1))
    alive = pid_alive(pid)
    print(f"lock pid {pid}: {'ALIVE' if alive else 'DEAD (stale lock)'}")
    print(f"started at {holder.get('started_at', '?')}")
    if LOG_PATH.exists():
        lines = LOG_PATH.read_text(encoding="utf-8").splitlines()
        print(f"log has {len(lines)} lines; last 5:")
        for line in lines[-5:]:
            print(" ", line)
    return 0 if alive else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path,
                        default=ROOT / "configs" / "campaigns" / "campaign_20260805.json")
    parser.add_argument("--scratch", type=Path, default=ROOT / ".campaign_scratch")
    parser.add_argument("--interval-seconds", type=int, default=DEFAULT_INTERVAL_SECONDS)
    parser.add_argument("--once", action="store_true", help="single refresh pass, no loop")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--stop", action="store_true")
    args = parser.parse_args(argv)

    if args.status:
        return status_report()
    if args.stop:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        STOP_PATH.write_text(utcnow(), encoding="utf-8")
        print("stop requested")
        return 0

    plan = json.loads(args.plan.read_text(encoding="utf-8"))

    if args.once:
        last_known = load_last_known()
        result, deltas = run_once(plan, args.scratch, last_known)
        for line in deltas:
            print(line)
        if not deltas:
            print("no new evidence")
        save_last_known({
            "families": result.get("families", {}),
            "chain_index": result.get("chain_index"),
            "status": result.get("status"),
        })
        return result.get("exit_code", 0)

    acquire_lock()
    try:
        return run_loop(plan, args.scratch, args.interval_seconds)
    finally:
        release_lock()


if __name__ == "__main__":
    raise SystemExit(main())
