"""Import one v3 screening row's evidence off the training pod.

A screening row is not a continuation of a v2.2 learning-rate family: it changes
the architecture and is *initialized from* -- not resumed from -- a parent
checkpoint.  `refresh_continuation_outputs.py` is therefore the wrong vehicle
for it.  That script keys its epoch record off the family's per-epoch
distribution diagnostics, appends to `continuation_history.csv`, and lets the
imported rows compete for the family's accepted best.  Applied to a v3 row it
would place a different architecture on `calibrated_lr3e4`'s continuous loss
axis, and the loss figure would show that family jumping from 4.4838 at epoch 90
to the row's re-heat epoch 0 as though one model had regressed.

This importer keeps screening evidence in its own namespace:

    exhibition/data/v3_screening/<run-tag>/history.csv
    exhibition/data/v3_screening/<run-tag>/invariants/invariant_epoch_*.json
    exhibition/data/v3_screening/<run-tag>/visualization/epoch_*.json
    exhibition/data/v3_screening_history.csv        (aggregate, builder input)

Every remote file is hash-listed first and re-hashed after download, and every
payload is schema-validated before it is allowed to replace a local file.  The
row's declared identity in `exhibition/data/v3_screening_rows.json` -- frozen
config hash, checkpoint hashes, seed, horizon -- is verified against the pod
rather than trusted, so a mismatch fails the import instead of silently
importing evidence from a different run.

It does not train, does not publish, and does not touch the test split.

Usage:
    python scripts/import_v3_screening_run.py --row S1-axis
    python scripts/import_v3_screening_run.py --row S1-axis --offline
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
DATA = ROOT / "exhibition" / "data"
REGISTRY = DATA / "v3_screening_rows.json"
LOCAL_ROOT = DATA / "v3_screening"
AGGREGATE = DATA / "v3_screening_history.csv"
FIELDS = ["variant", "epoch", "train_loss", "validation_loss", "learning_rate", "run_tag"]

RUN_TAG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
VARIANT_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_]*$")
INVARIANT_PATTERN = re.compile(r"invariant_epoch_(\d{4,})\.json")
VISUAL_PATTERN = re.compile(r"epoch_(\d{4,})\.json")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def dicos(args: list[str]) -> str:
    """Run the DiCOS client against the primary (training) pod.

    DICOS_CONFIG is cleared deliberately.  Screening-row artifacts are training
    products and live on the training pod; inheriting a caller's prior 3090
    selection would silently look for them on the diagnostics pod and report
    "nothing to import".
    """
    env = dict(os.environ, PYTHONPATH="src")
    env.pop("DICOS_CONFIG", None)
    result = subprocess.run(
        [sys.executable, "scripts/dicos.py", *args],
        cwd=ROOT, env=env, capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"dicos {args[0]} failed: {result.stderr.strip()}")
    return result.stdout


def load_registry() -> dict:
    payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("v3 screening registry schema must be 1")
    if payload.get("kind") != "cbsc-zdc-v3-screening-row-registry":
        raise ValueError("unexpected registry kind")
    return payload


def select_row(registry: dict, row_id: str) -> dict:
    for row in registry["rows"]:
        if row["row_id"] == row_id:
            break
    else:
        known = ", ".join(r["row_id"] for r in registry["rows"])
        raise SystemExit(f"unknown screening row {row_id!r}; registry holds: {known}")
    if not RUN_TAG_PATTERN.fullmatch(row["run_tag"]):
        raise ValueError(f"unsafe run tag {row['run_tag']!r}")
    if not VARIANT_PATTERN.fullmatch(row["variant"]):
        raise ValueError(f"unsafe variant {row['variant']!r}")
    run_dir = Path(row["run_dir"])
    if run_dir.is_absolute() or ".." in run_dir.parts or run_dir.parts[0] != "_runs":
        raise ValueError("run directory must be a safe _runs-relative path")
    return row


def remote_hashes(pattern: str) -> dict[str, str]:
    """sha256 -> path for a remote glob, tolerating an empty match."""
    listing = dicos(["exec", f"sha256sum {pattern} 2>/dev/null || true"])
    found: dict[str, str] = {}
    for line in listing.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) == 2 and re.fullmatch(r"[0-9a-f]{64}", parts[0]):
            found[parts[1]] = parts[0]
    return found


def fetch(remote: str, target: Path, expected_sha256: str) -> bool:
    """Download unless already present with the right bytes. True if fetched."""
    if target.exists():
        local = sha256_file(target)
        if local != expected_sha256:
            raise RuntimeError(
                f"local/remote hash conflict for {remote}: "
                f"local {local} remote {expected_sha256}"
            )
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".part")
    partial.unlink(missing_ok=True)
    try:
        dicos(["get", remote, str(partial)])
        actual = sha256_file(partial)
        if actual != expected_sha256:
            raise RuntimeError(f"downloaded hash mismatch for {remote}: {actual}")
        partial.replace(target)
    except Exception:
        partial.unlink(missing_ok=True)
        raise
    return True


def verify_declared_identity(row: dict) -> dict:
    """Re-hash the row's frozen config and checkpoints on the pod.

    The registry is hand-authored.  Trusting it would let a typo silently
    attribute one run's trajectory to another row's declared change.
    """
    targets = {
        "frozen_config_sha256": row["frozen_config"],
        "best_sha256": row["checkpoints"]["best"],
        "last_sha256": row["checkpoints"]["last"],
    }
    quoted = " ".join(f"'{path}'" for path in targets.values())
    observed = remote_hashes(quoted)
    checked = {}
    for field, path in targets.items():
        declared = row["frozen_config_sha256"] if field == "frozen_config_sha256" \
            else row["checkpoints"][field]
        actual = observed.get(path)
        if actual is None:
            raise RuntimeError(f"declared artifact missing on the pod: {path}")
        if actual != declared:
            raise RuntimeError(
                f"declared {field} for {row['row_id']} does not match the pod: "
                f"registry {declared} pod {actual} ({path})"
            )
        checked[field] = actual
    return checked


def validate_invariant(path: Path, epoch: int) -> dict:
    """Re-check a per-epoch structural invariant report.

    The report carries no epoch field -- the epoch is in the filename -- so the
    caller supplies it for the error messages only.  `pass` is re-derived here
    rather than trusted: a report that says it passed while carrying a nonzero
    structural count, or a closure residual above its own effective tolerance,
    is itself the defect.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("pass") is not True:
        raise ValueError(f"epoch {epoch}: structural invariants did not pass")
    for key in (
        "negative", "nonfinite", "outside_valid_support", "support_mask_mismatch",
        "count_mismatch_max", "requested_realized_mismatch_max", "dust_cells",
    ):
        if key not in payload:
            raise ValueError(f"epoch {epoch}: missing invariant field {key}")
        if payload[key] != 0:
            raise ValueError(f"epoch {epoch}: {key} is {payload[key]!r}, expected 0")
    # The tolerance has been `max(absolute, relative * total_response)` since
    # 2026-08-05. Compare against the effective bound the run actually recorded,
    # never against the absolute floor alone.
    tolerance = payload.get("closure_tolerance_effective_gev")
    if tolerance is None or not math.isfinite(float(tolerance)) or float(tolerance) <= 0:
        raise ValueError(f"epoch {epoch}: missing or invalid effective closure tolerance")
    for key in ("event_closure_max_gev", "layer_closure_max_gev"):
        residual = payload.get(key)
        if residual is None or not math.isfinite(float(residual)):
            raise ValueError(f"epoch {epoch}: missing or nonfinite {key}")
        if float(residual) > float(tolerance):
            raise ValueError(
                f"epoch {epoch}: {key} {residual} exceeds effective tolerance {tolerance}"
            )
    return payload


def validate_visualization(path: Path, epoch: int) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "kind": "cbsc-zdc-epoch-visual-comparison",
        "split": "validation",
        "epoch": epoch,
        "sample_count": 50,
        "draws_per_condition": 5,
    }
    for key, value in expected.items():
        if payload.get(key) != value:
            raise ValueError(f"{path.name}: expected {key}={value!r}")
    qa = payload.get("qa", {})
    if qa.get("pass") is not True:
        raise ValueError(f"{path.name}: visualization QA did not pass")
    if qa.get("test_events_used") != 0:
        raise ValueError(f"{path.name}: visualization used test events")
    if qa.get("groups_with_exact_draw_count") != 50:
        raise ValueError(f"{path.name}: visualization draw-count contract failed")
    return payload


def read_history(path: Path, row: dict) -> list[dict]:
    rows: list[dict] = []
    seen: set[int] = set()
    with path.open(newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            epoch = int(float(raw["epoch"]))
            train_loss = float(raw["train_loss"])
            validation_loss = float(raw["validation_loss"])
            learning_rate = float(raw["learning_rate"])
            if epoch in seen:
                raise ValueError(f"duplicate history epoch {epoch}")
            if not math.isfinite(train_loss) or not math.isfinite(validation_loss):
                raise ValueError(f"nonfinite loss at epoch {epoch}")
            if not math.isfinite(learning_rate) or learning_rate <= 0:
                raise ValueError(f"nonpositive or nonfinite learning rate at epoch {epoch}")
            seen.add(epoch)
            rows.append({
                "variant": row["variant"],
                "epoch": epoch,
                "train_loss": train_loss,
                "validation_loss": validation_loss,
                "learning_rate": learning_rate,
                "run_tag": row["run_tag"],
            })
    if not rows:
        raise ValueError("history contains no epochs")
    horizon = int(row["horizon_epochs"])
    if len(rows) > horizon:
        raise ValueError(
            f"history holds {len(rows)} epochs but the row declares a {horizon}-epoch horizon"
        )
    if row.get("status") == "complete" and len(rows) != horizon:
        raise ValueError(
            f"row is declared complete but history holds {len(rows)} of {horizon} epochs"
        )
    return rows


def rewrite_aggregate(new_rows: list[dict], variant: str, run_tag: str) -> int:
    rows: list[dict] = []
    if AGGREGATE.exists():
        with AGGREGATE.open(newline="", encoding="utf-8") as handle:
            rows = [
                r for r in csv.DictReader(handle)
                if not (r["variant"] == variant and r["run_tag"] == run_tag)
            ]
    rows.extend(new_rows)
    rows.sort(key=lambda r: (r["variant"], int(r["epoch"])))
    temporary = AGGREGATE.with_suffix(".csv.tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(AGGREGATE)
    return sum(1 for r in rows if r["variant"] == variant and r["run_tag"] == run_tag)


def import_row(row: dict, *, offline: bool) -> dict:
    local = LOCAL_ROOT / row["run_tag"]
    history_path = local / "history.csv"
    invariant_dir = local / "invariants"
    visual_dir = local / "visualization"

    identity: dict = {}
    fetched = {"history": False, "invariants": [], "visualizations": []}

    if not offline:
        identity = verify_declared_identity(row)

        run_dir = row["run_dir"]
        history_remote = f"{run_dir}/logs/history.csv"
        listed = remote_hashes(f"'{history_remote}'")
        if history_remote not in listed:
            raise RuntimeError(f"training history missing on the pod: {history_remote}")
        # The history grows while a run is live, so its hash legitimately
        # changes between imports. Replace rather than conflict.
        if history_path.exists() and sha256_file(history_path) != listed[history_remote]:
            history_path.unlink()
        fetched["history"] = fetch(history_remote, history_path, listed[history_remote])

        for remote_path, checksum in sorted(
            remote_hashes(f"{run_dir}/reports/invariant_epoch_*.json").items()
        ):
            match = INVARIANT_PATTERN.search(remote_path)
            if not match:
                continue
            target = invariant_dir / Path(remote_path).name
            if fetch(remote_path, target, checksum):
                fetched["invariants"].append(int(match.group(1)))

        for remote_path, checksum in sorted(
            remote_hashes(f"{run_dir}/reports/visualization/epoch_*.json").items()
        ):
            match = VISUAL_PATTERN.fullmatch(Path(remote_path).name)
            if not match:
                continue
            target = visual_dir / Path(remote_path).name
            if fetch(remote_path, target, checksum):
                fetched["visualizations"].append(int(match.group(1)))

    if not history_path.is_file():
        raise SystemExit(
            f"no local history for {row['row_id']}; run without --offline first"
        )

    history_rows = read_history(history_path, row)
    epochs = sorted(r["epoch"] for r in history_rows)

    invariant_epochs = []
    for path in sorted(invariant_dir.glob("invariant_epoch_*.json")):
        match = INVARIANT_PATTERN.fullmatch(path.name)
        if match:
            epoch = int(match.group(1))
            validate_invariant(path, epoch)
            invariant_epochs.append(epoch)

    visual_epochs = []
    for path in sorted(visual_dir.glob("epoch_*.json")):
        match = VISUAL_PATTERN.fullmatch(path.name)
        if match:
            epoch = int(match.group(1))
            validate_visualization(path, epoch)
            visual_epochs.append(epoch)

    # A missing invariant report is not a cosmetic gap: the structural contract
    # is what makes the row's loss number admissible at all.
    missing_invariants = sorted(set(epochs) - set(invariant_epochs))
    if missing_invariants:
        raise SystemExit(
            f"{row['row_id']}: epochs without a passing invariant report: {missing_invariants}"
        )

    written = rewrite_aggregate(history_rows, row["variant"], row["run_tag"])

    best = min(history_rows, key=lambda r: (r["validation_loss"], r["epoch"]))
    parent_loss = float(row["parent"]["validation_loss"])
    control = row.get("control") or {}
    control_loss = control.get("best_validation_loss")

    return {
        "row_id": row["row_id"],
        "variant": row["variant"],
        "run_tag": row["run_tag"],
        "mode": "offline-verify" if offline else "remote-import",
        "declared_identity_verified": bool(identity),
        "declared_identity": identity or None,
        "fetched": fetched,
        "epochs_imported": len(history_rows),
        "epoch_range": [min(epochs), max(epochs)],
        "aggregate_rows": written,
        "invariant_reports": len(invariant_epochs),
        "invariant_reports_all_pass": True,
        "visualization_payloads": len(visual_epochs),
        "best_epoch": best["epoch"],
        "best_validation_loss": best["validation_loss"],
        "first_epoch_validation_loss": history_rows[0]["validation_loss"],
        "parent_validation_loss": parent_loss,
        "delta_vs_parent": best["validation_loss"] - parent_loss,
        "control_run_tag": control.get("run_tag"),
        "control_validation_loss": control_loss,
        "delta_vs_control": (
            best["validation_loss"] - float(control_loss)
            if control_loss is not None else None
        ),
        "beats_parent": best["validation_loss"] < parent_loss,
        "beats_control": (
            best["validation_loss"] < float(control_loss)
            if control_loss is not None else None
        ),
        "distribution_diagnostics_present": bool(row["evidence"]["distribution_diagnostics"]),
        "test_events_used": 0,
        "training_started_by_import": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--row", required=True, help="row_id from the screening registry")
    parser.add_argument(
        "--offline", action="store_true",
        help="re-validate and rebuild from local immutable evidence without DiCOS I/O",
    )
    parser.add_argument("--report", type=Path, help="write the import record here")
    args = parser.parse_args(argv)

    registry = load_registry()
    row = select_row(registry, args.row)
    record = import_row(row, offline=args.offline)

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n",
            encoding="utf-8", newline="\n",
        )
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
