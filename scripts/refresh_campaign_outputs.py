#!/usr/bin/env python
"""Bring every local output current from a running campaign, with no arguments.

`scripts/refresh_continuation_outputs.py` does the work but needs `--family`,
`--run-tag`, `--run-dir`, `--expected-epoch` and `--lineage` to be right, and a
wrong `--lineage` silently drops the earlier epochs from every trend figure.
A campaign creates a new run tag per segment, so those arguments change under
the operator. This derives them from the campaign's own recorded state.

Run it on the workstation whenever you want the local picture current:

    python scripts/refresh_campaign_outputs.py

It reads `_campaign/<id>/{state.json,events.jsonl}` off the pod, works out which
families have produced segments and in what order, and refreshes each family's
newest segment with the full lineage behind it. It does **not** publish: it will
report that a public release is required and leave the deliberate act to you.

Nothing here runs on a pod except reads. The exhibition builders deliberately
stay on the workstation -- they write into `exhibition/current/`, and running
them inside the pod's repository checkout would dirty the clean tree that the
pre-launch gate depends on.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))


def _dicos(args: list[str], config: str | None = None) -> str:
    command = [sys.executable, str(ROOT / "scripts" / "dicos.py"), *args]
    env_extra = {}
    if config:
        env_extra["DICOS_CONFIG"] = config
    import os

    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src")
    env.update(env_extra)
    result = subprocess.run(command, capture_output=True, text=True, env=env)
    if result.returncode != 0:
        raise SystemExit(
            f"dicos {' '.join(args)} failed ({result.returncode}):\n{result.stderr}"
        )
    return result.stdout


def read_campaign(campaign_id: str, scratch: Path) -> tuple[dict, list[dict]]:
    scratch.mkdir(parents=True, exist_ok=True)
    state_path = scratch / "state.json"
    events_path = scratch / "events.jsonl"
    _dicos(["get", f"_campaign/{campaign_id}/state.json", str(state_path)])
    _dicos(["get", f"_campaign/{campaign_id}/events.jsonl", str(events_path)])
    state = json.loads(state_path.read_text(encoding="utf-8"))
    events = [
        json.loads(line)
        for line in events_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return state, events


def segments_by_family(events: list[dict]) -> dict[str, list[str]]:
    """Run tags each family has produced, oldest first, deduplicated."""
    order: dict[str, list[str]] = {}
    for event in events:
        if event.get("kind") != "segment_launch":
            continue
        tag = event.get("run_tag")
        run_dir = event.get("run_dir", "")
        family = Path(run_dir).name.replace(f"_{tag}", "") if run_dir else None
        if not tag or not family:
            continue
        tags = order.setdefault(family, [])
        if tag not in tags:
            tags.append(tag)
    return order


def latest_epoch(family: str, tag: str) -> int | None:
    directory = ROOT / "exhibition" / "data" / "diagnostics" / tag
    if not directory.exists():
        return None
    epochs = [
        int(path.stem.rsplit("_", 1)[1])
        for path in directory.glob("metrics_epoch_*.json")
    ]
    return max(epochs) if epochs else None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path,
                        default=ROOT / "configs" / "campaigns" / "campaign_20260805.json")
    parser.add_argument("--scratch", type=Path, default=ROOT / ".campaign_scratch")
    parser.add_argument("--dry-run", action="store_true",
                        help="print what would be refreshed and stop")
    args = parser.parse_args(argv)

    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    campaign_id = plan["campaign_id"]
    state, events = read_campaign(campaign_id, args.scratch)

    print(f"campaign {campaign_id} status={state.get('status')} "
          f"segments_run={state.get('segments_run')} "
          f"chain_index={state.get('chain_index')}")

    produced = segments_by_family(events)
    if not produced:
        print("no segment has launched yet; nothing to refresh")
        return 0

    exit_code = 0
    for family, tags in produced.items():
        prefix = plan["families"].get(family, {}).get("diagnostic_lineage", [])
        lineage = [*prefix, *tags]
        newest = tags[-1]
        epoch = latest_epoch(family, newest)
        if epoch is None:
            # The consumer may not have written this tag's first metric yet.
            # Refreshing without it would assert against evidence that does not
            # exist, so say so rather than fail obscurely.
            print(f"{family}/{newest}: no diagnostics imported yet, skipping")
            continue
        command = [
            sys.executable, str(ROOT / "scripts" / "refresh_continuation_outputs.py"),
            "--family", family,
            "--run-tag", newest,
            "--run-dir", f"_runs/{family}_{newest}",
            "--expected-epoch", str(epoch),
            "--lineage", *lineage,
        ]
        print(f"\n=== refreshing {family}/{newest} at epoch {epoch} ===")
        print("lineage:", " ".join(lineage))
        if args.dry_run:
            print("dry run:", " ".join(command))
            continue
        result = subprocess.run(command, cwd=str(ROOT))
        exit_code = exit_code or result.returncode

    print("\nrebuilding the exhibition catalog")
    if not args.dry_run:
        for builder in ("build_metrics_catalog.py", "build_all_metric_trends.py"):
            result = subprocess.run(
                [sys.executable, str(ROOT / "exhibition" / builder)], cwd=str(ROOT)
            )
            exit_code = exit_code or result.returncode
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
