"""Pull new per-epoch artifacts off DiCOS and rebuild every derived output.

One command per epoch, so the refresh is repeatable rather than hand-assembled:

  1. pull any `_diag/metrics_epoch_*.json` not already local (3090 pod);
  2. pull the training run's `history.csv` (4090 pod);
  3. rewrite the continuation rows for this family in
     `exhibition/data/continuation_history.csv`;
  4. rebuild the loss figure and the diagnostic trend figure.

It does not publish. Publishing changes the selected checkpoint per family and
is a deliberate step, not something a refresh loop should do on its own.

Usage:
    python scripts/refresh_continuation_outputs.py \
        --family calibrated_lr1e4 --run-tag dicos-p8 \
        --run-dir _runs/calibrated_lr1e4_dicos-p8
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIAG_LOCAL = ROOT / "exhibition" / "data" / "diagnostics"
CONTINUATION_CSV = ROOT / "exhibition" / "data" / "continuation_history.csv"
FIELDS = ["variant", "epoch", "train_loss", "validation_loss", "run_tag"]


def dicos(args: list[str], config: str | None = None) -> str:
    env = dict(os.environ, PYTHONPATH="src")
    if config:
        env["DICOS_CONFIG"] = str(Path.home() / ".dicos" / config)
    result = subprocess.run(
        [sys.executable, "scripts/dicos.py", *args],
        cwd=ROOT, env=env, capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"dicos {args[0]} failed: {result.stderr.strip()}")
    return result.stdout


def pull_diagnostics(config: str, run_tag: str) -> list[int]:
    # Namespaced by run tag on BOTH sides. Two runs of the same family overlap
    # in epoch number -- p8 and p9 both covered 17..22, and p10 reruns p9's
    # epoch 39 because it resumes from the epoch-38 best -- and the metrics
    # filenames carry only the epoch, so a flat directory silently mixes them.
    # The host side was flat until 2026-08-04 and cost p8 its epochs 17..22.
    destination = DIAG_LOCAL / run_tag
    destination.mkdir(parents=True, exist_ok=True)
    remote_dir = f"_diag/{run_tag}"
    listing = dicos(
        ["exec", f"ls -1 '{remote_dir}/' 2>/dev/null | grep -o 'metrics_epoch_[0-9]*'"],
        config,
    )
    remote = sorted({line.strip() for line in listing.splitlines() if line.strip()})
    if not remote:
        # A flat _diag/ means a producer predating the namespacing, or a typo in
        # the run tag. Either way, silently pulling nothing would look like "no
        # new epochs" and the figures would quietly stop advancing.
        flat = dicos(
            ["exec", "ls -1 _diag/ 2>/dev/null | grep -o 'metrics_epoch_[0-9]*'"],
            config,
        )
        if flat.strip():
            raise RuntimeError(
                f"no metrics under {remote_dir}/ but _diag/ holds un-namespaced "
                "metrics files; move them under their run tag before refreshing, "
                "or the runs will be mixed"
            )
    pulled = []
    for stem in remote:
        target = destination / f"{stem}.json"
        if target.exists():
            continue
        dicos(["get", f"{remote_dir}/{stem}.json", str(target)], config)
        pulled.append(int(stem.rsplit("_", 1)[1]))
    return sorted(pulled)


def pull_history(run_dir: str, destination: Path) -> None:
    dicos(["get", f"{run_dir}/logs/history.csv", str(destination)])


def rewrite_continuation(history: Path, family: str, run_tag: str) -> int:
    rows: list[dict] = []
    if CONTINUATION_CSV.exists():
        with CONTINUATION_CSV.open(newline="", encoding="utf-8") as fh:
            rows = [r for r in csv.DictReader(fh)
                    if not (r["variant"] == family and r["run_tag"] == run_tag)]
    with history.open(newline="", encoding="utf-8") as fh:
        for raw in csv.DictReader(fh):
            rows.append({
                "variant": family,
                "epoch": int(float(raw["epoch"])),
                "train_loss": raw["train_loss"],
                "validation_loss": raw["validation_loss"],
                "run_tag": run_tag,
            })
    rows.sort(key=lambda r: (r["variant"], int(r["epoch"])))
    with CONTINUATION_CSV.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return sum(1 for r in rows if r["variant"] == family and r["run_tag"] == run_tag)


def rebuild(script: str, *args: str) -> str:
    result = subprocess.run(
        [sys.executable, script, *args], cwd=ROOT, capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"{script} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family", required=True)
    parser.add_argument("--run-tag", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--diag-config", default="config_3090.json")
    parser.add_argument(
        "--lineage",
        nargs="*",
        default=None,
        metavar="RUN_TAG",
        help=(
            "run tags to plot as one continuous trend, oldest first, ending "
            "with --run-tag. A continuation is the same model carrying on, so "
            "its diagnostics belong on one axis; without this the trend figure "
            "shows only the newest run and the earlier epochs vanish from the "
            "plot. Where tags share an epoch the later one wins. "
            "Defaults to --run-tag alone."
        ),
    )
    args = parser.parse_args(argv)

    lineage = list(args.lineage) if args.lineage else [args.run_tag]
    if lineage[-1] != args.run_tag:
        lineage.append(args.run_tag)

    pulled = pull_diagnostics(args.diag_config, args.run_tag)
    print(f"diagnostics pulled: {pulled or 'none new'}")

    history = ROOT / ".refresh_history.csv"
    try:
        pull_history(args.run_dir, history)
        written = rewrite_continuation(history, args.family, args.run_tag)
        print(f"continuation rows for {args.family}/{args.run_tag}: {written}")
    finally:
        history.unlink(missing_ok=True)

    print(rebuild("exhibition/build_continuation_loss_figures.py"))
    print(rebuild("exhibition/build_diagnostic_trend_figure.py", *lineage))

    summary = ROOT / "exhibition/diagnostics_20260803/diagnostic_summary.json"  # noqa: E501
    if summary.is_file():
        payload = json.loads(summary.read_text(encoding="utf-8"))
        print(f"diagnostic epochs: {payload['epochs']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
