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

For a persistent, self-updating loop that keeps this current for as long as a
campaign is training, see `scripts/watch_campaign_outputs.py`, which imports
`refresh()` from this module rather than duplicating it.

Nothing here runs on a pod except reads. The exhibition builders deliberately
stay on the workstation -- they write into `exhibition/current/`, and running
them inside the pod's repository checkout would dirty the clean tree that the
pre-launch gate depends on.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

HISTORY_CSV = ROOT / "exhibition" / "data" / "continuation_history.csv"


# dicos.py's own HTTP/websocket calls are bounded (30-300s per request), but a
# stalled connect or a kernel that accepts a socket and never replies can still
# run out the clock across several internal retries. Nothing bounded the child
# process itself, so a single wedged pod request could block a watcher poll
# indefinitely without the loop ever crashing or logging an error -- flagged
# after the unexplained 6h50m gap in the 2026-08-05 watcher run. This timeout
# is a backstop above dicos.py's largest single-request timeout (300s), not a
# replacement for fixing the root cause inside dicos.py if one is found.
DICOS_SUBPROCESS_TIMEOUT_SECONDS = 360


def _dicos(args: list[str], config: str | None = None) -> str:
    command = [sys.executable, str(ROOT / "scripts" / "dicos.py"), *args]
    import os

    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src")
    if config:
        env["DICOS_CONFIG"] = config
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, env=env,
            timeout=DICOS_SUBPROCESS_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        raise SystemExit(
            f"dicos {' '.join(args)} timed out after "
            f"{DICOS_SUBPROCESS_TIMEOUT_SECONDS}s (pod unreachable or wedged)"
        )
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
    """Highest epoch with a diagnostic metric, asked of the pod first.

    Looking only at the local directory cannot bootstrap a new run tag: the
    refresh that populates it is the very thing being skipped. The pod is the
    authority while a campaign is live, so ask it, and fall back to whatever is
    already local when it cannot be reached.
    """
    try:
        listing = _dicos(
            ["exec", f"ls _diag/{tag}/metrics_epoch_*.json 2>/dev/null || true"],
            config=str(Path.home() / ".dicos" / "config_3090.json"),
        )
    except SystemExit:
        listing = ""
    remote = [
        int(name.rsplit("_", 1)[1].split(".")[0])
        for name in listing.split()
        if "metrics_epoch_" in name and name.endswith(".json")
    ]
    directory = ROOT / "exhibition" / "data" / "diagnostics" / tag
    local = (
        [int(path.stem.rsplit("_", 1)[1]) for path in directory.glob("metrics_epoch_*.json")]
        if directory.exists()
        else []
    )
    epochs = remote + local
    return max(epochs) if epochs else None


def _parent_tag_from_run_dir(run_dir: str, family: str) -> str:
    """`_runs/<family>_<tag>` -> `<tag>`, the naming convention used everywhere."""
    name = Path(run_dir).name
    prefix = f"{family}_"
    if not name.startswith(prefix):
        raise ValueError(f"run_dir {run_dir!r} does not start with {prefix!r}")
    return name[len(prefix):]


def fork_points(plan: dict, events: list[dict]) -> dict[str, list[tuple[str, str, int]]]:
    """`family -> [(parent_tag, child_tag, fork_epoch), ...]`, oldest first.

    A campaign segment resumes from its parent's BEST checkpoint, which is
    frequently an earlier epoch than the parent's own LAST epoch -- that is the
    whole point of resuming from best rather than last. So a segment's first new
    epoch can collide with an epoch the parent tag already wrote past the fork
    point: `dicos-c-03` resumed `calibrated_lr1e4_halfbatch` from `dicos-p7`'s
    best at epoch 21, but `dicos-p7` had already written its own epoch 22, so
    both tags have a row at epoch 22 and the duplicate-epoch guard in
    `build_continuation_loss_figures.py` is right to refuse it.

    The fork epoch is not guessed. `dicos_campaign.py`'s `verify_config_delta`
    records `provenance.parent_last_epoch` in every `segment_frozen` event, so
    this reads the campaign's own evidence for where each segment actually
    forked.
    """
    frozen_parent_epoch: dict[str, int] = {}
    for event in events:
        if event.get("kind") != "segment_frozen":
            continue
        tag = event.get("run_tag")
        delta = event.get("config_delta") or {}
        pair = delta.get("provenance.parent_last_epoch")
        if not tag or not pair:
            continue
        try:
            frozen_parent_epoch[tag] = int(float(pair[1]))
        except (TypeError, ValueError):
            continue

    result: dict[str, list[tuple[str, str, int]]] = {}
    for family, tags in segments_by_family(events).items():
        spec = plan.get("families", {}).get(family)
        if not spec:
            continue
        previous_tag = _parent_tag_from_run_dir(spec["parent_run_dir"], family)
        chain: list[tuple[str, str, int]] = []
        for tag in tags:
            fork_epoch = frozen_parent_epoch.get(tag)
            if fork_epoch is not None:
                chain.append((previous_tag, tag, fork_epoch))
            previous_tag = tag
        if chain:
            result[family] = chain
    return result


def prune_superseded_rows(
    history_path: Path, forks: dict[str, list[tuple[str, str, int]]]
) -> list[str]:
    """Drop history rows left on a branch a later segment forked past.

    Per family, a row from `parent_tag` is superseded exactly when
    `child_tag` forked from `parent_tag` at `fork_epoch` and the row's own
    epoch is beyond that fork point -- the row describes a continuation of
    `parent_tag` that is no longer the live lineage.

    Returns one description per dropped row so the caller can log it. A row
    disappearing from evidence with no record would be worse than leaving the
    duplicate for the guard to catch; this is the resolution the guard exists
    to force, done from the campaign's own recorded fork points rather than by
    guessing which branch is live.
    """
    if not history_path.exists():
        return []
    with history_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        return []
    fieldnames = list(rows[0].keys())
    dropped: list[str] = []
    kept: list[dict] = []
    for row in rows:
        family = row.get("variant")
        tag = row.get("run_tag")
        try:
            epoch = int(row.get("epoch", ""))
        except (TypeError, ValueError):
            kept.append(row)
            continue
        superseded = False
        for parent_tag, child_tag, fork_epoch in forks.get(family, []):
            if tag == parent_tag and epoch > fork_epoch:
                dropped.append(
                    f"{family}/{tag} epoch {epoch} dropped from history: off "
                    f"the live lineage, superseded by {child_tag} forking from "
                    f"{parent_tag} at epoch {fork_epoch}"
                )
                superseded = True
                break
        if not superseded:
            kept.append(row)
    if not dropped:
        return []
    tmp = history_path.with_suffix(".csv.tmp")
    with tmp.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(kept)
    tmp.replace(history_path)
    return dropped


def family_bests(history_path: Path = HISTORY_CSV) -> dict[str, tuple[float, int, str]]:
    """`family -> (best_loss, epoch, run_tag)`, the lowest validation loss on record.

    Shared with `scripts/watch_campaign_outputs.py` rather than duplicated, so
    the two scripts cannot compute two different answers to "who is winning."
    """
    if not history_path.exists():
        return {}
    best: dict[str, tuple[float, int, str]] = {}
    with history_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            try:
                family = row["variant"]
                loss = float(row["validation_loss"])
                epoch = int(row["epoch"])
                tag = row["run_tag"]
            except (KeyError, ValueError):
                continue
            current = best.get(family)
            if current is None or loss < current[0]:
                best[family] = (loss, epoch, tag)
    return best


def _run_builder(name: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ROOT / "exhibition" / name), *args],
        cwd=str(ROOT), capture_output=True, text=True,
    )


def refresh(plan: dict, scratch: Path, *, dry_run: bool = False) -> dict:
    """Run one full refresh pass and return a structured summary.

    Separated from `main()` so `scripts/watch_campaign_outputs.py` can call it
    repeatedly and inspect what changed, instead of shelling out to this file
    and re-parsing its stdout.
    """
    campaign_id = plan["campaign_id"]
    state, events = read_campaign(campaign_id, scratch)

    result: dict = {
        "campaign_id": campaign_id,
        "status": state.get("status"),
        "chain_index": state.get("chain_index"),
        "segments_run": state.get("segments_run"),
        "families": {},
        "catalog_ok": None,
        "exit_code": 0,
    }

    produced = segments_by_family(events)
    if not produced:
        return result

    exit_code = 0
    for family, tags in produced.items():
        prefix = plan["families"].get(family, {}).get("diagnostic_lineage", [])
        lineage = [*prefix, *tags]
        newest = tags[-1]
        epoch = latest_epoch(family, newest)
        entry: dict = {
            "tags": tags,
            "newest_tag": newest,
            "epoch": epoch,
            "refreshed": False,
            "returncode": None,
        }
        result["families"][family] = entry
        if epoch is None:
            # The consumer may not have written this tag's first metric yet.
            # Refreshing without it would assert against evidence that does not
            # exist, so say so rather than fail obscurely.
            continue
        command = [
            sys.executable, str(ROOT / "scripts" / "refresh_continuation_outputs.py"),
            "--family", family,
            "--run-tag", newest,
            "--run-dir", f"_runs/{family}_{newest}",
            "--expected-epoch", str(epoch),
            "--lineage", *lineage,
        ]
        entry["command"] = " ".join(command)
        if dry_run:
            continue
        proc = subprocess.run(command, cwd=str(ROOT), capture_output=True, text=True)
        entry["refreshed"] = True
        entry["returncode"] = proc.returncode
        entry["stdout"] = proc.stdout
        entry["stderr"] = proc.stderr
        exit_code = exit_code or proc.returncode

    pruned: list[str] = []
    if not dry_run:
        forks = fork_points(plan, events)
        pruned = prune_superseded_rows(HISTORY_CSV, forks)
    result["pruned_history_rows"] = pruned

    if not dry_run:
        # `refresh_continuation_outputs.py` already rebuilds everything --
        # loss figures, diagnostic trends, metric trends, exhibition manifest,
        # catalog -- as the LAST thing each per-family subprocess call above
        # does, using that family's own correct lineage. A second, no-argument
        # pass here is not just redundant: `build_all_metric_trends.py` and
        # `build_diagnostic_trend_figure.py` default their run-tag lineage to
        # `["dicos-p9", "dicos-p10"]` when called with none, so it would
        # SILENTLY OVERWRITE whichever family's correct state the per-family
        # loop had just written with that stale default. That happened once,
        # 2026-08-05: `all_metric_trends.json` reverted to epochs [16..40]
        # after a halfbatch refresh had just correctly written [22..27].
        #
        # What genuinely needs a second pass: prune_superseded_rows() above
        # can remove rows from continuation_history.csv that a per-family
        # subprocess already read before pruning happened, and the shared
        # current-diagnostics slot (diagnostic_summary.json /
        # all_metric_trends.json) holds exactly one lineage, so whichever
        # family this loop's dict iteration order happened to process LAST
        # decides what that lineage is -- not necessarily the campaign's
        # actual current best. Both are fixed by explicitly re-targeting the
        # shared slot at the real champion's own lineage, then re-running the
        # exhibition/catalog rebuild once more so it validates that state.
        bests = family_bests(HISTORY_CSV)
        processed = [f for f, e in result["families"].items() if e["epoch"] is not None]
        champion = min(
            (f for f in processed if f in bests), key=lambda f: bests[f][0], default=None
        )
        if champion is not None:
            prefix = plan["families"].get(champion, {}).get("diagnostic_lineage", [])
            champion_lineage = [*prefix, *result["families"][champion]["tags"]]
            result["champion_family"] = champion
            result["champion_lineage"] = champion_lineage

            loss_fig = _run_builder("build_continuation_loss_figures.py")
            choice_fig = _run_builder("build_family_choice_figure.py")
            trend_fig = _run_builder("build_diagnostic_trend_figure.py", *champion_lineage)
            metric_trends = _run_builder("build_all_metric_trends.py", *champion_lineage)
            for proc in (loss_fig, choice_fig, trend_fig, metric_trends):
                exit_code = exit_code or proc.returncode

            external_data = ROOT / "exhibition/current/external_metrics/source_data"
            if any(external_data.glob("*/epoch_*/manifest.json")):
                ext_fig = _run_builder("build_external_metric_figures.py")
                exit_code = exit_code or ext_fig.returncode

            exhibit = _run_builder("build_exhibition.py")
            exit_code = exit_code or exhibit.returncode

        catalog = _run_builder("build_metrics_catalog.py")
        exit_code = exit_code or catalog.returncode
        result["catalog_ok"] = catalog.returncode == 0
        result["catalog_stdout"] = catalog.stdout
        result["catalog_stderr"] = catalog.stderr

    result["exit_code"] = exit_code
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path,
                        default=ROOT / "configs" / "campaigns" / "campaign_20260805.json")
    parser.add_argument("--scratch", type=Path, default=ROOT / ".campaign_scratch")
    parser.add_argument("--dry-run", action="store_true",
                        help="print what would be refreshed and stop")
    args = parser.parse_args(argv)

    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    result = refresh(plan, args.scratch, dry_run=args.dry_run)

    print(f"campaign {result['campaign_id']} status={result['status']} "
          f"segments_run={result['segments_run']} chain_index={result['chain_index']}")

    if not result["families"]:
        print("no segment has launched yet; nothing to refresh")
        return 0

    for family, entry in result["families"].items():
        if entry["epoch"] is None:
            print(f"{family}/{entry['newest_tag']}: no diagnostics imported yet, skipping")
            continue
        print(f"\n=== refreshing {family}/{entry['newest_tag']} at epoch {entry['epoch']} ===")
        if args.dry_run:
            print("dry run:", entry.get("command"))
            continue
        if entry.get("stdout"):
            print(entry["stdout"], end="")
        if entry.get("stderr"):
            print(entry["stderr"], end="", file=sys.stderr)

    if result.get("pruned_history_rows"):
        print("\npruned off-lineage history rows:")
        for line in result["pruned_history_rows"]:
            print(" ", line)

    if not args.dry_run:
        print("\nrebuilding the exhibition catalog")
        if result.get("catalog_stdout"):
            print(result["catalog_stdout"], end="")
        if result.get("catalog_stderr"):
            print(result["catalog_stderr"], end="", file=sys.stderr)

    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
