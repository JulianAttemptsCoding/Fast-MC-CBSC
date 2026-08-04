"""Pull new per-epoch artifacts off DiCOS and rebuild every derived output.

One command per epoch, so the refresh is repeatable rather than hand-assembled:

  1. pull any `_diag/metrics_epoch_*.json` not already local (3090 pod);
  2. pull the training run's `history.csv` (4090 pod);
  3. rewrite the continuation rows for this family in
     `exhibition/data/continuation_history.csv`;
  4. hash-match accepted visualization payloads to 3090 metrics and immutably
     merge them into the internal dashboard;
  5. rebuild the loss figure and the diagnostic trend figure.

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
import hashlib
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIAG_LOCAL = ROOT / "exhibition" / "data" / "diagnostics"
VISUAL_LOCAL = ROOT / "exhibition" / "data" / "visualizations"
CONTINUATION_CSV = ROOT / "exhibition" / "data" / "continuation_history.csv"
DASHBOARD_DATA = ROOT / "dashboard" / "public" / "data"
FIELDS = ["variant", "epoch", "train_loss", "validation_loss", "run_tag"]
RUN_TAG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
FAMILY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_]*$")
METRIC_PATTERN = re.compile(
    r"^([0-9a-f]{64})\s+_diag/([a-z0-9][a-z0-9-]*)/"
    r"(metrics_epoch_(\d{4,})\.json)$"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def validate_inputs(family: str, run_tag: str, run_dir: str, diag_config: str) -> None:
    if not FAMILY_PATTERN.fullmatch(family):
        raise ValueError("family must contain lowercase letters, digits, and underscores")
    if not RUN_TAG_PATTERN.fullmatch(run_tag):
        raise ValueError("run tag must contain lowercase letters, digits, and hyphens")
    path = Path(run_dir)
    if path.is_absolute() or ".." in path.parts or len(path.parts) < 2:
        raise ValueError("run directory must be a safe _runs-relative path")
    if path.parts[0] != "_runs":
        raise ValueError("run directory must live under _runs/")
    if diag_config != "config_3090.json":
        raise ValueError("diagnostic refresh must use the RTX 3090 config_3090.json")


def validate_metric(path: Path, epoch: int) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "schema_version": 1,
        "kind": "cbsc-zdc-large-validation-diagnostic",
        "split": "validation",
        "epoch": epoch,
        "n_events": 4000,
    }
    for key, value in expected.items():
        if payload.get(key) != value:
            raise ValueError(f"{path.name}: expected {key}={value!r}")
    counts = payload.get("split_counts", {})
    qa = payload.get("qa", {})
    if counts != {"train": 0, "validation": 4000, "test": 0}:
        raise ValueError(f"{path.name}: validation-only split counts failed")
    required_qa = {
        "test_events_used": 0,
        "train_events_used": 0,
        "generated_nonfinite": 0,
        "generated_negative": 0,
        "truth_nonfinite": 0,
        "truth_negative": 0,
        "events_outside_energy_bins": 0,
        "empty_energy_bins": 0,
        "pass": True,
    }
    for key, value in required_qa.items():
        if qa.get(key) != value:
            raise ValueError(f"{path.name}: diagnostic QA {key} failed")
    return payload


def validate_visualization(path: Path, epoch: int, checkpoint_sha256: str) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "kind": "cbsc-zdc-epoch-visual-comparison",
        "split": "validation",
        "epoch": epoch,
        "sample_count": 50,
        "draws_per_condition": 5,
        "checkpoint_sha256": checkpoint_sha256,
    }
    for key, value in expected.items():
        if payload.get(key) != value:
            raise ValueError(f"{path.name}: expected {key}={value!r}")
    qa = payload.get("qa", {})
    if qa.get("pass") is not True or qa.get("test_events_used") != 0:
        raise ValueError(f"{path.name}: visualization QA/split contract failed")
    if qa.get("groups_with_exact_draw_count") != 50:
        raise ValueError(f"{path.name}: visualization draw-count contract failed")
    return payload


def dicos(args: list[str], config: str | None = None) -> str:
    env = dict(os.environ, PYTHONPATH="src")
    if config:
        env["DICOS_CONFIG"] = str(Path.home() / ".dicos" / config)
    else:
        # History/visualizations are 4090 products. Do not inherit a caller's
        # prior 3090 selection into an implicit-primary command.
        env.pop("DICOS_CONFIG", None)
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
        ["exec", f"sha256sum {remote_dir}/metrics_epoch_*.json 2>/dev/null || true"],
        config,
    )
    remote: dict[int, tuple[str, str]] = {}
    for line in listing.splitlines():
        match = METRIC_PATTERN.fullmatch(line.strip())
        if not match:
            continue
        checksum, listed_tag, filename, epoch_text = match.groups()
        if listed_tag != run_tag:
            raise RuntimeError("remote diagnostic listing escaped requested namespace")
        epoch = int(epoch_text)
        if epoch in remote:
            raise RuntimeError(f"duplicate remote diagnostic epoch {epoch}")
        remote[epoch] = (checksum, filename)
    if not remote:
        # A flat _diag/ means a producer predating the namespacing, or a typo in
        # the run tag. Either way, silently pulling nothing would look like "no
        # new epochs" and the figures would quietly stop advancing.
        flat = dicos(
            ["exec", "sha256sum _diag/metrics_epoch_*.json 2>/dev/null || true"],
            config,
        )
        if flat.strip():
            raise RuntimeError(
                f"no metrics under {remote_dir}/ but _diag/ holds un-namespaced "
                "metrics files; move them under their run tag before refreshing, "
                "or the runs will be mixed"
            )
    pulled = []
    for epoch, (remote_checksum, filename) in sorted(remote.items()):
        target = destination / filename
        if target.exists():
            if sha256_file(target) != remote_checksum:
                raise RuntimeError(f"local/remote diagnostic hash conflict: {target}")
            validate_metric(target, epoch)
            continue
        partial = target.with_suffix(target.suffix + ".part")
        partial.unlink(missing_ok=True)
        try:
            dicos(["get", f"{remote_dir}/{filename}", str(partial)], config)
            if sha256_file(partial) != remote_checksum:
                raise RuntimeError(f"downloaded diagnostic hash mismatch: {filename}")
            validate_metric(partial, epoch)
            partial.replace(target)
        except Exception:
            partial.unlink(missing_ok=True)
            raise
        pulled.append(epoch)
    return sorted(pulled)


def pull_history(run_dir: str, destination: Path) -> None:
    dicos(["get", f"{run_dir}/logs/history.csv", str(destination)])


def pull_and_sync_visualizations(run_dir: str, run_tag: str, family: str) -> list[int]:
    """Import dashboard payloads only after matching 3090 metrics pass QA."""
    metric_dir = DIAG_LOCAL / run_tag
    accepted: dict[int, dict] = {}
    for path in sorted(metric_dir.glob("metrics_epoch_*.json")):
        match = re.fullmatch(r"metrics_epoch_(\d{4,})\.json", path.name)
        if match:
            epoch = int(match.group(1))
            accepted[epoch] = validate_metric(path, epoch)
    if not accepted:
        return []

    remote_dir = f"{run_dir}/reports/visualization"
    listing = dicos(
        ["exec", f"sha256sum {remote_dir}/epoch_*.json 2>/dev/null || true"]
    )
    pattern = re.compile(
        rf"^([0-9a-f]{{64}})\s+{re.escape(remote_dir)}/(epoch_(\d{{4,}})\.json)$"
    )
    remote: dict[int, tuple[str, str]] = {}
    for line in listing.splitlines():
        match = pattern.fullmatch(line.strip())
        if match:
            checksum, filename, epoch_text = match.groups()
            remote[int(epoch_text)] = (checksum, filename)
    missing = sorted(set(accepted) - set(remote))
    if missing:
        raise RuntimeError(
            f"accepted diagnostic epochs lack required visualization payloads: {missing}"
        )

    destination = VISUAL_LOCAL / run_tag
    destination.mkdir(parents=True, exist_ok=True)
    payloads: list[tuple[Path, str]] = []
    downloaded: list[int] = []
    for epoch in sorted(accepted):
        remote_checksum, filename = remote[epoch]
        target = destination / filename
        if target.exists():
            if sha256_file(target) != remote_checksum:
                raise RuntimeError(f"local/remote visualization hash conflict: {target}")
        else:
            partial = target.with_suffix(".json.part")
            partial.unlink(missing_ok=True)
            try:
                dicos(["get", f"{remote_dir}/{filename}", str(partial)])
                if sha256_file(partial) != remote_checksum:
                    raise RuntimeError(f"downloaded visualization hash mismatch: {filename}")
                partial.replace(target)
            except Exception:
                partial.unlink(missing_ok=True)
                raise
            downloaded.append(epoch)
        validate_visualization(
            target, epoch, str(accepted[epoch]["checkpoint_sha256"])
        )
        payloads.append((target, f"{remote_dir}/{filename}"))

    from scripts.sync_dicos_visualizations import sync

    run_label = f"{run_tag}-{family.replace('_', '-')}"
    sync(DASHBOARD_DATA, run_label, payloads)
    return downloaded


def rewrite_continuation(history: Path, family: str, run_tag: str) -> int:
    rows: list[dict] = []
    if CONTINUATION_CSV.exists():
        with CONTINUATION_CSV.open(newline="", encoding="utf-8") as fh:
            rows = [r for r in csv.DictReader(fh)
                    if not (r["variant"] == family and r["run_tag"] == run_tag)]
    with history.open(newline="", encoding="utf-8") as fh:
        seen_epochs: set[int] = set()
        for raw in csv.DictReader(fh):
            epoch = int(float(raw["epoch"]))
            train_loss = float(raw["train_loss"])
            validation_loss = float(raw["validation_loss"])
            if epoch in seen_epochs:
                raise ValueError(f"duplicate history epoch {epoch}")
            if not math.isfinite(train_loss) or not math.isfinite(validation_loss):
                raise ValueError(f"nonfinite history loss at epoch {epoch}")
            seen_epochs.add(epoch)
            rows.append({
                "variant": family,
                "epoch": epoch,
                "train_loss": train_loss,
                "validation_loss": validation_loss,
                "run_tag": run_tag,
            })
    if not seen_epochs:
        raise ValueError("remote history contains no epochs")
    rows.sort(key=lambda r: (r["variant"], int(r["epoch"])))
    temporary = CONTINUATION_CSV.with_suffix(".csv.tmp")
    with temporary.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(CONTINUATION_CSV)
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
    validate_inputs(args.family, args.run_tag, args.run_dir, args.diag_config)

    lineage = list(args.lineage) if args.lineage else [args.run_tag]
    for tag in lineage:
        if not RUN_TAG_PATTERN.fullmatch(tag):
            parser.error(f"unsafe lineage run tag: {tag!r}")
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

    visuals = pull_and_sync_visualizations(args.run_dir, args.run_tag, args.family)
    print(f"visualizations imported: {visuals or 'none new'}")

    print(rebuild("exhibition/build_continuation_loss_figures.py"))
    print(rebuild("exhibition/build_diagnostic_trend_figure.py", *lineage))

    summary = ROOT / "exhibition/diagnostics_20260803/diagnostic_summary.json"  # noqa: E501
    if summary.is_file():
        payload = json.loads(summary.read_text(encoding="utf-8"))
        print(f"diagnostic epochs: {payload['epochs']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
