#!/usr/bin/env python
"""Advance provenance-checked v3 validation batteries on the RTX 3090.

The workstation v3 watcher calls this once per refresh. A call may import any
completed report and may launch at most one new battery. It never trains a
generator, never reads the test split, never selects an epoch from battery
metrics, and never retries or overwrites a failed transaction.

Eligibility is mechanical: a screening row must have its complete declared
horizon locally imported with passing per-epoch structural evidence. The best
epoch is selected solely by that row's validation loss. A read-only remote
probe then requires ``best.pt`` to embed the same epoch and metric before a
battery can start. The battery itself repeats the epoch check and writes its
report atomically.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "exhibition" / "data" / "v3_screening_rows.json"
LOCAL_BATTERY = ROOT / "exhibition" / "data" / "v3_battery"
CONTRACT_PATH = ROOT / "configs" / "v3_validation_battery_contract.json"
DICOS_CONFIG = Path.home() / ".dicos" / "config_3090.json"

RUN_TAG = re.compile(r"^[a-z0-9][a-z0-9-]*$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
REQUIRED_C2ST = {"high_level", "low_level", "profile_aware", "condition_only"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def dicos(args: list[str]) -> str:
    env = dict(os.environ, PYTHONPATH="src", DICOS_CONFIG=str(DICOS_CONFIG))
    result = subprocess.run(
        [sys.executable, "scripts/dicos.py", *args], cwd=ROOT, env=env,
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout


def load_contract() -> dict:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    required = {
        "validation_manifest", "validation_manifest_sha256",
        "validation_manifest_file_sha256", "geometry_manifest",
        "data_manifest_sha256", "splits_sha256", "generator_seed",
        "evaluator_seeds", "energy_bin_edges_gev", "profile_steps", "share_steps",
        "precision", "evaluation_role", "device", "batch_size",
        "bootstrap_replicates", "bootstrap_confidence",
        "memorization_reference_events", "memorization_reference_seed",
        "structural_subsample_events", "pairs", "evaluator_corpus_examples",
        "split", "test_events_used",
    }
    missing = sorted(required - set(contract))
    if missing:
        raise ValueError(f"battery contract is missing {missing}")
    if contract["split"] != "validation" or contract["test_events_used"] != 0:
        raise ValueError("battery contract must be validation-only with zero test events")
    if len(contract["evaluator_seeds"]) != 3:
        raise ValueError("battery contract requires exactly three evaluator seeds")
    for field in (
        "validation_manifest_sha256", "validation_manifest_file_sha256",
        "data_manifest_sha256", "splits_sha256",
    ):
        if not HEX64.fullmatch(str(contract[field])):
            raise ValueError(f"invalid {field}")
    return contract


def load_registry() -> dict:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def history_for(row: dict) -> list[dict]:
    path = ROOT / "exhibition" / "data" / "v3_screening" / row["run_tag"] / "history.csv"
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        rows = [{
            "epoch": int(float(raw["epoch"])),
            "validation_loss": float(raw["validation_loss"]),
        } for raw in csv.DictReader(handle)]
    if len({r["epoch"] for r in rows}) != len(rows):
        raise ValueError(f"{row['row_id']} history contains duplicate epochs")
    if any(not math.isfinite(r["validation_loss"]) for r in rows):
        raise ValueError(f"{row['row_id']} history contains nonfinite loss")
    return sorted(rows, key=lambda r: r["epoch"])


def eligible_rows(registry: dict) -> list[dict]:
    eligible = []
    for row in registry["rows"]:
        if not RUN_TAG.fullmatch(row["run_tag"]):
            raise ValueError(f"unsafe run tag {row['run_tag']!r}")
        history = history_for(row)
        if len(history) != int(row["horizon_epochs"]):
            continue
        expected_epochs = list(range(int(row["horizon_epochs"])))
        if [r["epoch"] for r in history] != expected_epochs:
            raise ValueError(f"{row['row_id']} full history is not contiguous")
        local = ROOT / "exhibition" / "data" / "v3_screening" / row["run_tag"]
        invariants = list((local / "invariants").glob("invariant_epoch_*.json"))
        if len(invariants) != len(history):
            raise ValueError(f"{row['row_id']} is missing invariant reports")
        best = min(history, key=lambda r: (r["validation_loss"], r["epoch"]))
        eligible.append({**row, "selected_epoch": best["epoch"],
                         "selected_validation_loss": best["validation_loss"]})
    return eligible


def battery_rows(registry: dict) -> list[dict]:
    """B0 plus screening rows whose complete validation horizon is admissible."""
    baseline = registry["baseline"]
    gate_path = ROOT / baseline["gate"]
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    if gate.get("decision") != "B0_FROZEN" or gate.get("items_failing") != 0:
        raise ValueError("B0 cannot enter the battery queue without its passing gate")
    b0 = {
        "row_id": "B0",
        "run_tag": baseline["run_tag"],
        "run_dir": f"_runs/{baseline['family']}_{baseline['run_tag']}",
        "frozen_config": (
            f"prep/configs/frozen_{baseline['family']}_{baseline['run_tag']}.yaml"
        ),
        "selected_epoch": int(baseline["epoch"]),
        "selected_validation_loss": float(baseline["validation_loss"]),
        "checkpoint_sha256": baseline["checkpoint_sha256"],
        "frozen_config_sha256": baseline["frozen_config_sha256"],
    }
    return [b0, *eligible_rows(registry)]


def remote_report_path(row: dict) -> str:
    return f"_v3/battery/{row['run_tag']}_epoch{row['selected_epoch']}.json"


def local_report_path(row: dict) -> Path:
    return LOCAL_BATTERY / Path(remote_report_path(row)).name


def provenance_path(row: dict) -> Path:
    return local_report_path(row).with_suffix(".provenance.json")


def remote_sha256(path: str) -> str | None:
    output = dicos(["exec", f"sha256sum {shlex.quote(path)} 2>/dev/null || true"])
    for line in output.splitlines():
        parts = line.split(None, 1)
        if len(parts) == 2 and HEX64.fullmatch(parts[0]):
            return parts[0]
    return None


def checkpoint_identity(row: dict) -> dict:
    checkpoint = f"{row['run_dir']}/checkpoints/best.pt"
    command = " ".join([
        "env PYTHONPATH=repo/src:repo .venv_3090/bin/python",
        "repo/scripts/v3_battery_checkpoint_identity.py",
        "--checkpoint", shlex.quote(checkpoint),
        "--frozen-config", shlex.quote(row["frozen_config"]),
        "--expected-epoch", str(row["selected_epoch"]),
    ])
    output = dicos(["exec", command])
    start = output.find("{")
    if start < 0:
        raise RuntimeError("checkpoint identity probe returned no JSON")
    identity = json.loads(output[start:])
    required = {
        "checkpoint_sha256", "checkpoint_embedded_epoch",
        "checkpoint_best_metric", "frozen_config_sha256",
    }
    if required - set(identity):
        raise RuntimeError("checkpoint identity probe omitted required provenance")
    for field in ("checkpoint_sha256", "frozen_config_sha256"):
        if not HEX64.fullmatch(str(identity[field])):
            raise RuntimeError(f"checkpoint identity returned invalid {field}")
    if identity["frozen_config_sha256"] != row["frozen_config_sha256"]:
        raise RuntimeError("frozen config hash does not match the row registry")
    expected_checkpoint = row.get("checkpoint_sha256")
    if expected_checkpoint and identity["checkpoint_sha256"] != expected_checkpoint:
        raise RuntimeError("checkpoint hash does not match the frozen baseline registry")
    if not math.isclose(
        float(identity["checkpoint_best_metric"]),
        float(row["selected_validation_loss"]), rel_tol=0.0, abs_tol=1e-12,
    ):
        raise RuntimeError("best.pt metric does not match selected validation history")
    return identity


def validate_report(report: dict, row: dict, contract: dict, identity: dict) -> None:
    expected = {
        "schema_version": 1,
        "kind": "cbsc-zdc-v3-validation-battery",
        "split": "validation",
        "pairs": int(contract["pairs"]),
        "evaluator_corpus_examples": int(contract["evaluator_corpus_examples"]),
        "test_events_used": 0,
        "scientific_status": "PHYSICS VALIDATION NOT ESTABLISHED",
    }
    for field, value in expected.items():
        if report.get(field) != value:
            raise ValueError(f"battery report expected {field}={value!r}")
    if report.get("structural_invariants", {}).get("pass") is not True:
        raise ValueError("battery report structural invariants did not pass")
    reconstruction = report.get("reconstruction", {})
    positive = reconstruction.get("events_with_positive_truth")
    excluded = reconstruction.get("events_excluded_zero_truth")
    if not isinstance(positive, int) or not isinstance(excluded, int):
        raise ValueError(
            "battery report predates the zero-truth reconstruction correction"
        )
    if positive + excluded != int(contract["pairs"]):
        raise ValueError("reconstruction positive/excluded event accounting mismatch")
    relative_rmse = reconstruction.get("energy_relative_rmse")
    if relative_rmse is not None and (
        not math.isfinite(float(relative_rmse)) or float(relative_rmse) < 0
    ):
        raise ValueError("invalid corrected energy relative RMSE")
    if set(report.get("c2st", {})) != REQUIRED_C2ST:
        raise ValueError("battery report does not contain the four separate C2ST families")
    for family in REQUIRED_C2ST:
        value = float(report["c2st"][family]["auroc_mean"])
        if not math.isfinite(value) or not 0.0 <= value <= 1.0:
            raise ValueError(f"invalid {family} AUROC")
    metadata = report.get("identity", {})
    for field, value in {
        "run_tag": row["run_tag"],
        "epoch": row["selected_epoch"],
        "generator_seed": contract["generator_seed"],
        "evaluator_seeds": contract["evaluator_seeds"],
        "precision": contract["precision"],
        "evaluation_role": contract["evaluation_role"],
        "validation_manifest_sha256": contract["validation_manifest_sha256"],
    }.items():
        if metadata.get(field) != value:
            raise ValueError(f"battery identity expected {field}={value!r}")
    for field in ("checkpoint_sha256", "checkpoint_embedded_epoch", "frozen_config_sha256"):
        if metadata.get(field) != identity[field]:
            raise ValueError(f"battery embedded {field} disagrees with external identity")


def ensure_provenance(row: dict, identity: dict, checksum: str) -> bool:
    """Create the sidecar once, or prove the existing one is identical."""
    target = local_report_path(row)
    sidecar = {
        "schema_version": 1,
        "kind": "cbsc-zdc-v3-battery-provenance-sidecar",
        "report": target.name,
        "report_sha256": checksum,
        "selected_by": "lowest validation loss over the complete declared horizon",
        "selected_validation_loss": row["selected_validation_loss"],
        **identity,
        "test_events_used": 0,
        "scientific_status": "PHYSICS VALIDATION NOT ESTABLISHED",
    }
    destination = provenance_path(row)
    if destination.is_file():
        existing = json.loads(destination.read_text(encoding="utf-8"))
        if existing != sidecar:
            raise RuntimeError(f"battery provenance conflict for {destination.name}")
        return False
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(sidecar, indent=2, sort_keys=True) + "\n",
                         encoding="utf-8", newline="\n")
    temporary.replace(destination)
    return True


def import_remote_report(row: dict, contract: dict) -> bool:
    remote = remote_report_path(row)
    checksum = remote_sha256(remote)
    if checksum is None:
        return False
    identity = checkpoint_identity(row)
    target = local_report_path(row)
    if target.is_file() and sha256_file(target) == checksum:
        report = json.loads(target.read_text(encoding="utf-8"))
        validate_report(report, row, contract, identity)
        return ensure_provenance(row, identity, checksum)
    if target.exists():
        raise RuntimeError(f"local/remote battery hash conflict for {target.name}")
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(".json.part")
    partial.unlink(missing_ok=True)
    try:
        dicos(["get", remote, str(partial)])
        if sha256_file(partial) != checksum:
            raise RuntimeError("downloaded battery report hash mismatch")
        report = json.loads(partial.read_text(encoding="utf-8"))
        validate_report(report, row, contract, identity)
        partial.replace(target)
    except Exception:
        partial.unlink(missing_ok=True)
        raise
    ensure_provenance(row, identity, checksum)
    return True


def jobs() -> dict[str, str]:
    found = {}
    for line in dicos(["jobs"]).splitlines():
        match = re.match(r"\s*([A-Za-z0-9._-]+)\s+(RUNNING|finished)\s+", line)
        if match:
            found[match.group(1)] = match.group(2)
    return found


def job_name(row: dict) -> str:
    return f"v3bat-{row['run_tag']}-e{row['selected_epoch']}"


def evaluation_command(row: dict, contract: dict) -> str:
    values = [
        "env PYTHONPATH=repo/src:repo .venv_3090/bin/python",
        "repo/scripts/run_v3_validation_battery.py", "evaluate",
        "--checkpoint", shlex.quote(f"{row['run_dir']}/checkpoints/best.pt"),
        "--frozen-config", shlex.quote(row["frozen_config"]),
        "--validation-manifest", shlex.quote(contract["validation_manifest"]),
        "--geometry", shlex.quote(contract["geometry_manifest"]),
        "--output", shlex.quote(remote_report_path(row)),
        "--data-manifest-sha256", contract["data_manifest_sha256"],
        "--splits-sha256", contract["splits_sha256"],
        "--generator-seed", str(contract["generator_seed"]),
        "--evaluator-seeds", *[str(v) for v in contract["evaluator_seeds"]],
        "--energy-bin-edges-gev", *[str(v) for v in contract["energy_bin_edges_gev"]],
        "--profile-steps", str(contract["profile_steps"]),
        "--share-steps", str(contract["share_steps"]),
        "--precision", contract["precision"],
        "--output-namespace", shlex.quote(f"v3-battery/{row['run_tag']}"),
        "--evaluation-role", contract["evaluation_role"],
        "--run-tag", row["run_tag"],
        "--epoch", str(row["selected_epoch"]),
        "--device", contract["device"],
        "--batch-size", str(contract["batch_size"]),
        "--bootstrap-replicates", str(contract["bootstrap_replicates"]),
        "--bootstrap-confidence", str(contract["bootstrap_confidence"]),
        "--memorization-reference-events", str(contract["memorization_reference_events"]),
        "--memorization-reference-seed", str(contract["memorization_reference_seed"]),
        "--structural-subsample-events", str(contract["structural_subsample_events"]),
    ]
    return " ".join(values)


def write_request(row: dict, contract: dict, identity: dict, command: str) -> Path:
    path = LOCAL_BATTERY / "requests" / f"{row['run_tag']}_epoch{row['selected_epoch']}.json"
    payload = {
        "schema_version": 1,
        "kind": "cbsc-zdc-v3-validation-battery-request",
        "row_id": row["row_id"],
        "run_tag": row["run_tag"],
        "epoch": row["selected_epoch"],
        "selected_validation_loss": row["selected_validation_loss"],
        "selection_quantity": "validation_loss_only",
        "contract_sha256": sha256_file(CONTRACT_PATH),
        "contract": contract,
        "identity": identity,
        "remote_output": remote_report_path(row),
        "command": command,
        "test_events_used": 0,
        "scientific_status": "PHYSICS VALIDATION NOT ESTABLISHED",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                         encoding="utf-8", newline="\n")
    temporary.replace(path)
    return path


def advance() -> dict:
    contract = load_contract()
    registry = load_registry()
    rows = battery_rows(registry)
    changed = []
    for row in rows:
        if import_remote_report(row, contract):
            changed.append(row["row_id"])

    states = jobs()
    active = sorted(name for name, state in states.items()
                    if state == "RUNNING" and (name == "battery5" or name.startswith("v3bat-")))
    if active:
        return {"action": "wait", "active_battery_jobs": active,
                "reports_imported": changed, "changed": bool(changed),
                "test_events_used": 0}

    for row in rows:
        if local_report_path(row).is_file() or remote_sha256(remote_report_path(row)):
            continue
        name = job_name(row)
        if name in states:
            raise RuntimeError(
                f"battery transaction {name} finished without a valid report; "
                "automatic retry/overwrite is forbidden"
            )
        identity = checkpoint_identity(row)
        bank_hash = remote_sha256(contract["validation_manifest"])
        if bank_hash != contract["validation_manifest_file_sha256"]:
            raise RuntimeError("remote fixed validation bank hash mismatch")
        command = evaluation_command(row, contract)
        request = write_request(row, contract, identity, command)
        remote_request_dir = "_v3/battery/requests"
        dicos(["mkdir", remote_request_dir])
        dicos(["put", str(request), f"{remote_request_dir}/{request.name}"])
        dicos(["start", command, "--name", name])
        return {"action": "launched", "job": name, "row_id": row["row_id"],
                "epoch": row["selected_epoch"], "reports_imported": changed,
                "changed": True, "test_events_used": 0}

    return {"action": "none", "reports_imported": changed,
            "changed": bool(changed), "test_events_used": 0}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--advance", action="store_true")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args(argv)
    if not (args.advance or args.status):
        parser.error("one of --advance or --status is required")
    if args.status:
        contract = load_contract()
        rows = battery_rows(load_registry())
        payload = {
            "eligible": [{"row_id": r["row_id"], "epoch": r["selected_epoch"],
                          "local_report": local_report_path(r).is_file()}
                         for r in rows],
            "jobs": jobs(),
            "contract_sha256": sha256_file(CONTRACT_PATH),
            "test_events_used": 0,
        }
    else:
        payload = advance()
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
