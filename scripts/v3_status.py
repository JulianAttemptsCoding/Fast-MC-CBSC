"""One command to see whether anything is still running, and how it is doing.

Reports both pods: GPU state, live writers, the newest epoch and loss of each
active run, and the diagnostics queue depth.  Read-only -- it starts, stops and
changes nothing.

    python scripts/v3_status.py
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WORKDIR = "/dicos_ui_home/julianjuan/sharedfs/work/IOP/julian/Fast MC CBSC"

# Tokens are assembled by awk so the probe's own command line cannot contain
# the contiguous strings it searches for.  ``ps`` is the only permitted
# process-tree interface: process-filesystem inspection is outside scope.
WRITER_PROBE = (
    "command -v ps >/dev/null 2>&1 || "
    "{ echo PROCESS_TREE_UNAVAILABLE; exit 2; }; "
    "ps -eo pid=,ppid=,args= | awk '"
    "BEGIN { a=\"dicos_\" \"train\"; b=\"dicos_\" \"campaign\"; "
    "c=\"dicos_\" \"diagnostics\" } "
    "index($0,a) || index($0,b) || index($0,c) { print }'"
)


def pod(command: str, config: str | None = None) -> str:
    env = dict(os.environ, PYTHONPATH="src", MSYS_NO_PATHCONV="1")
    if config:
        env["DICOS_CONFIG"] = config
    result = subprocess.run(
        [sys.executable, "scripts/dicos.py", "exec", command],
        cwd=REPO, env=env, capture_output=True, text=True, timeout=180,
    )
    return (result.stdout or result.stderr).strip()


def section(title: str) -> None:
    print(f"\n{'=' * 4} {title} {'=' * (58 - len(title))}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--diagnostics-config", default="C:/Users/Julia/.dicos/config_3090.json")
    args = parser.parse_args()

    section("TRAINING POD (RTX 4090)")
    try:
        print(pod("nvidia-smi --query-gpu=name,utilization.gpu,memory.used --format=csv,noheader"))
        print("live writers:", pod(WRITER_PROBE))
        runs = pod(
            "for d in _runs/v3_*/; do "
            "  f=\"$d/logs/history.csv\"; "
            "  if [ -f \"$f\" ]; then echo \"== $d\"; head -1 \"$f\" | cut -d, -f1-5; tail -2 \"$f\" | cut -d, -f1-5; "
            "  else echo \"== $d (no history yet)\"; fi; done"
        )
        print(runs or "no v3 run directories")
    except Exception as exc:  # noqa: BLE001
        print(f"training pod unreachable: {exc}")

    section("DIAGNOSTICS POD (RTX 3090)")
    try:
        print(pod("nvidia-smi --query-gpu=name,utilization.gpu,memory.used --format=csv,noheader",
                  config=args.diagnostics_config))
        print("live writers:", pod(WRITER_PROBE, config=args.diagnostics_config))
        print(pod(
            "for d in _diag/*/; do q=$(ls $d/queue/*.pt 2>/dev/null | wc -l); "
            "m=$(ls $d/metrics_epoch_*.json 2>/dev/null | wc -l); "
            "if [ \"$q\" != \"0\" ]; then echo \"$d queued=$q metrics=$m\"; fi; done",
            config=args.diagnostics_config,
        ) or "no queues outstanding")
    except Exception as exc:  # noqa: BLE001
        print(f"diagnostics pod unreachable: {exc}")

    section("LOCAL STANDINGS")
    choice = REPO / "exhibition/current/continuation/family_choice.json"
    if choice.is_file():
        families = json.loads(choice.read_text(encoding="utf-8"))["families"]
        for name, row in sorted(families.items(), key=lambda kv: kv[1]["best_accepted_validation_loss"]):
            print(f"  {name:<28} {row['best_accepted_validation_loss']:.6f}  "
                  f"e{row['best_accepted_epoch']}  {row['best_accepted_run_tag']}")
    print("\nB0 (frozen): calibrated_lr3e4 / dicos-f-02 / epoch 90 / 4.483767619419238")
    print("S1 beats B0 only if its best validation loss is below that number.")
    print("\nPHYSICS VALIDATION NOT ESTABLISHED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
