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
if str(ROOT) not in sys.path:
    # Invoked as a bare script (this file's own path, not `-m`), including from
    # refresh_campaign_outputs.py's subprocess call. `scripts` is only
    # importable as a package once ROOT -- its parent -- is on sys.path, which
    # `pull_and_sync_visualizations`'s `from scripts.sync_dicos_visualizations
    # import sync` requires.
    sys.path.insert(0, str(ROOT))
DIAG_LOCAL = ROOT / "exhibition" / "data" / "diagnostics"
VISUAL_LOCAL = ROOT / "exhibition" / "data" / "visualizations"
CONTINUATION_CSV = ROOT / "exhibition" / "data" / "continuation_history.csv"
CONTINUATION_STATUS = ROOT / "exhibition" / "data" / "continuation_status.json"
DASHBOARD_DATA = ROOT / "dashboard" / "public" / "data"
EXTERNAL_STATE = ROOT / "audit" / "current_external_metrics.json"
FIELDS = ["variant", "epoch", "train_loss", "validation_loss", "run_tag"]
RUN_TAG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
#: A --lineage entry may additionally carry `:MAX_EPOCH`, forwarded verbatim
#: to build_diagnostic_trend_figure.py / build_all_metric_trends.py to cap a
#: superseded tag at its own fork point (see the matching comment in
#: refresh_campaign_outputs.py's bound_lineage()). Never applies to the tag
#: itself elsewhere in this file -- checked below at the same point --run_tag
#: is compared against, so only an earlier, non-live lineage entry ever
#: carries one.
LINEAGE_TAG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*(:[0-9]+)?$")
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


def checkpoint_status(family: str, run_tag: str, epoch: int) -> str:
    if not CONTINUATION_STATUS.is_file():
        return "accepted"
    payload = json.loads(CONTINUATION_STATUS.read_text(encoding="utf-8"))
    for row in payload.get("overrides", []):
        if (
            row.get("variant") == family
            and row.get("run_tag") == run_tag
            and int(row.get("epoch", -1)) == epoch
        ):
            return str(row["status"])
    return str(payload.get("default_status", "accepted"))


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
            metric = validate_metric(path, epoch)
            if checkpoint_status(family, run_tag, epoch) == "accepted":
                accepted[epoch] = metric
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


def _write_json_atomic(path: Path, payload: dict) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def _external_controller(action: str, identity: dict) -> dict:
    command = [
        sys.executable,
        "scripts/dicos_external_metrics_controller.py",
        action,
        "--family", identity["family"],
        "--run-tag", identity["run_tag"],
        "--epoch", str(identity["epoch"]),
        "--validation-loss", repr(identity["validation_loss"]),
        "--checkpoint-sha256", identity["checkpoint_sha256"],
    ]
    env = dict(os.environ, PYTHONPATH="src")
    result = subprocess.run(
        command, cwd=ROOT, env=env, capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"external metric controller {action} failed: "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    return json.loads(result.stdout)


def advance_external_metrics(
    family: str,
    previous_best: dict | None,
    *,
    offline: bool,
) -> dict | None:
    """Advance the validation-only external transaction for a new best.

    A persisted matching pending state lets a later refresh finish the release
    even though the family-choice file already contains the newly selected best.
    """
    current = _read_best(family)
    if current is None:
        raise RuntimeError(f"rebuilt standings omit family {family}")
    best_changed = previous_best is not None and (
        previous_best.get("best_accepted_epoch")
        != current.get("best_accepted_epoch")
        or previous_best.get("best_accepted_validation_loss")
        != current.get("best_accepted_validation_loss")
    )
    prior_state = (
        json.loads(EXTERNAL_STATE.read_text(encoding="utf-8"))
        if EXTERNAL_STATE.is_file()
        else None
    )
    run_tag = current.get("best_accepted_run_tag")
    epoch = int(current["best_accepted_epoch"])
    validation_loss = float(current["best_accepted_validation_loss"])
    same_pending = bool(
        prior_state
        and prior_state.get("family") == family
        and prior_state.get("run_tag") == run_tag
        and int(prior_state.get("epoch", -1)) == epoch
        and prior_state.get("status") != "complete"
    )
    if not best_changed and not same_pending:
        return prior_state
    if not run_tag:
        raise RuntimeError("new accepted best has no run tag for external metrics")
    metric_path = DIAG_LOCAL / run_tag / f"metrics_epoch_{epoch:04d}.json"
    metric = validate_metric(metric_path, epoch)
    identity = {
        "family": family,
        "run_tag": run_tag,
        "epoch": epoch,
        "validation_loss": validation_loss,
        "checkpoint_sha256": metric["checkpoint_sha256"],
    }
    state = {
        "schema_version": 1,
        "kind": "cbsc-zdc-current-external-metrics-state",
        **identity,
        "source_split": "validation",
        "cbsc_test_events_used": 0,
        "selection_role": "descriptive only; may not select or tune CBSC",
        "release_pending": bool(
            best_changed or (prior_state and prior_state.get("release_pending"))
        ),
        "status": "pending_offline" if offline else "pending_remote",
    }
    if not offline:
        outcome = _external_controller("start", identity)
        if outcome.get("action") == "started validation-bank export":
            # The second call installs a detached evaluator waiter, allowing the
            # transaction to finish through a workstation disconnect.
            outcome = _external_controller("start", identity)
        if outcome.get("results_ready"):
            outcome = _external_controller("pull", identity)
        state["controller"] = outcome
        manifest = (
            ROOT / "exhibition" / "current" / "external_metrics"
            / "source_data" / run_tag
            / f"epoch_{epoch:04d}" / "manifest.json"
        )
        state["status"] = "complete" if manifest.is_file() else "running_remote"
        state["local_manifest"] = (
            manifest.relative_to(ROOT).as_posix() if manifest.is_file() else None
        )
    _write_json_atomic(EXTERNAL_STATE, state)
    return state


def mark_external_release_prepared(state: dict | None) -> None:
    if not state or state.get("release_pending") is not True:
        return
    updated = dict(state)
    updated["release_pending"] = False
    updated["public_release_prepared_and_qa_passed"] = True
    _write_json_atomic(EXTERNAL_STATE, updated)


def _read_best(family: str) -> dict | None:
    path = ROOT / "exhibition/current/continuation/family_choice.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8")).get("families", {}).get(family)


def write_epoch_record(
    *, family: str, run_tag: str, lineage: list[str], expected_epoch: int,
    offline: bool, previous_best: dict | None,
    public_release_prepared: bool = False,
    external_state: dict | None = None,
) -> dict:
    diagnostics_path = ROOT / "exhibition/current/diagnostics/diagnostic_summary.json"
    diagnostics = json.loads(diagnostics_path.read_text(encoding="utf-8"))
    per_epoch = {int(row["epoch"]): row for row in diagnostics["per_epoch"]}
    if expected_epoch not in per_epoch:
        raise RuntimeError(
            f"expected epoch {expected_epoch} missing from rebuilt diagnostics"
        )
    current_best = _read_best(family)
    if current_best is None:
        raise RuntimeError(f"rebuilt standings omit family {family}")
    best_changed = previous_best is not None and (
        previous_best.get("best_accepted_epoch")
        != current_best.get("best_accepted_epoch")
        or previous_best.get("best_accepted_validation_loss")
        != current_best.get("best_accepted_validation_loss")
    )
    tracked = [
        ROOT / "exhibition/current/continuation/loss_summary.json",
        ROOT / "exhibition/current/continuation/family_choice.json",
        diagnostics_path,
        ROOT / "exhibition/manifest.json",
        ROOT / "exhibition/metrics_catalog.json",
        ROOT / "exhibition/current/index.html",
    ]
    record = {
        "schema_version": 1,
        "kind": "cbsc-zdc-epoch-evidence-refresh",
        "family": family,
        "run_tag": run_tag,
        "lineage": lineage,
        "epoch": expected_epoch,
        "mode": "offline-rebuild" if offline else "remote-refresh",
        "training_started": False,
        "event_generation_started_by_refresh": False,
        "test_events_used": 0,
        "epoch_status": per_epoch[expected_epoch]["status"],
        "best_before_refresh": previous_best,
        "best_after_refresh": current_best,
        "best_changed": best_changed,
        "external_metrics": external_state,
        "public_release_pending_external_metrics": bool(
            external_state
            and external_state.get("release_pending") is True
            and external_state.get("status") != "complete"
        ),
        "public_release_required": (
            not offline
            and bool(external_state and external_state.get("release_pending") is True)
            and external_state.get("status") == "complete"
            and current_best["best_accepted_epoch"] == expected_epoch
            and per_epoch[expected_epoch]["status"] == "accepted"
        ),
        "public_release_prepared_and_qa_passed": public_release_prepared,
        "artifacts": [
            {
                "path": path.relative_to(ROOT).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in tracked
        ],
        "scientific_status": (
            "optimization and descriptive validation evidence only; "
            "Geant4 fidelity is not established"
        ),
    }
    audit_dir = ROOT / "audit"
    json_path = audit_dir / f"epoch_{run_tag}_{expected_epoch:04d}.json"
    md_path = audit_dir / f"epoch_{run_tag}_{expected_epoch:04d}.md"
    current_json = ROOT / "audit/current_epoch_pipeline.json"
    current_md = ROOT / "audit/current_epoch_pipeline.md"
    json_text = json.dumps(record, indent=2, sort_keys=True) + "\n"
    markdown = (
        f"# Epoch evidence refresh: {run_tag} e{expected_epoch}\n\n"
        f"- Mode: `{record['mode']}`\n"
        f"- Checkpoint status: `{record['epoch_status']}`\n"
        f"- Best accepted: e{current_best['best_accepted_epoch']} / "
        f"{current_best['best_accepted_validation_loss']:.12g}\n"
        f"- Best changed: `{str(best_changed).lower()}`\n"
        f"- External accepted-best metrics: "
        f"`{external_state.get('status') if external_state else 'not-required'}`\n"
        f"- Public release waiting on external metrics: "
        f"`{str(record['public_release_pending_external_metrics']).lower()}`\n"
        f"- Public release required: "
        f"`{str(record['public_release_required']).lower()}`\n"
        f"- Public candidate prepared and QA-passed: "
        f"`{str(public_release_prepared).lower()}`\n"
        "- Test events used: `0`\n\n"
        "All figures, metric summaries, the complete exhibition index, and "
        "their hashes are recorded in the JSON twin. These are descriptive "
        "validation/optimization artifacts, not Geant4 fidelity.\n"
    )
    for path, content in (
        (json_path, json_text), (current_json, json_text),
        (md_path, markdown), (current_md, markdown),
    ):
        temporary = path.with_name(f".{path.name}.tmp")
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(path)
    return record


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family", required=True)
    parser.add_argument("--run-tag", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--diag-config", default="config_3090.json")
    parser.add_argument(
        "--expected-epoch", required=True, type=int,
        help="exact epoch whose 3090 evidence must be present after refresh",
    )
    parser.add_argument(
        "--offline", action="store_true",
        help="rebuild and verify from local immutable evidence without DiCOS I/O",
    )
    parser.add_argument(
        "--public-repo",
        type=Path,
        default=ROOT.parent / "Fast-MC-Visual-Tests",
        help=(
            "public repository prepared and QA-tested automatically if this "
            "epoch establishes a new accepted validation-loss best"
        ),
    )
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
        if not LINEAGE_TAG_PATTERN.fullmatch(tag):
            parser.error(f"unsafe lineage run tag: {tag!r}")
    if lineage[-1] != args.run_tag:
        lineage.append(args.run_tag)

    previous_best = _read_best(args.family)
    if not args.offline:
        pulled = pull_diagnostics(args.diag_config, args.run_tag)
        print(f"diagnostics pulled: {pulled or 'none new'}")

        history = ROOT / ".refresh_history.csv"
        try:
            pull_history(args.run_dir, history)
            written = rewrite_continuation(history, args.family, args.run_tag)
            print(f"continuation rows for {args.family}/{args.run_tag}: {written}")
        finally:
            history.unlink(missing_ok=True)

        visuals = pull_and_sync_visualizations(
            args.run_dir, args.run_tag, args.family
        )
        print(f"visualizations imported: {visuals or 'none new'}")

    print(rebuild("exhibition/build_continuation_loss_figures.py"))
    print(rebuild("exhibition/build_family_choice_figure.py"))
    print(rebuild("exhibition/build_diagnostic_trend_figure.py", *lineage))
    print(rebuild("exhibition/build_all_metric_trends.py", *lineage))
    external_state = advance_external_metrics(
        args.family, previous_best, offline=args.offline,
    )
    if external_state:
        print(
            "external metrics: "
            f"{external_state.get('run_tag')} e{external_state.get('epoch')} "
            f"status={external_state.get('status')}"
        )
    external_data = ROOT / "exhibition/current/external_metrics/source_data"
    if any(external_data.glob("*/epoch_*/manifest.json")):
        print(rebuild("exhibition/build_external_metric_figures.py"))
    print(rebuild("exhibition/build_exhibition.py"))
    print(rebuild("exhibition/build_metrics_catalog.py"))

    summary = ROOT / "exhibition/current/diagnostics/diagnostic_summary.json"  # noqa: E501
    if summary.is_file():
        payload = json.loads(summary.read_text(encoding="utf-8"))
        print(f"diagnostic epochs: {payload['epochs']}")
    record = write_epoch_record(
        family=args.family,
        run_tag=args.run_tag,
        lineage=lineage,
        expected_epoch=args.expected_epoch,
        offline=args.offline,
        previous_best=previous_best,
        external_state=external_state,
    )
    if record["public_release_required"]:
        print(
            rebuild(
                "scripts/prepare_public_best_release.py",
                "--public-repo",
                str(args.public_repo),
            )
        )
        record = write_epoch_record(
            family=args.family,
            run_tag=args.run_tag,
            lineage=lineage,
            expected_epoch=args.expected_epoch,
            offline=args.offline,
            previous_best=previous_best,
            public_release_prepared=True,
            external_state=external_state,
        )
        mark_external_release_prepared(external_state)
    print(
        "epoch evidence: "
        f"e{record['epoch']} status={record['epoch_status']} "
        f"best_changed={record['best_changed']} "
        f"public_release_required={record['public_release_required']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
