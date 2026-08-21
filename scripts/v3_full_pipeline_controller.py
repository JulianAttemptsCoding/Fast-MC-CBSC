"""Detached, fail-closed controller for the remaining declared v3 pipeline.

The controller is designed to outlive the workstation. It waits for the
already-running S4 follower, then runs one generator at a time. Every row is
prepared and frozen by audited builders, trained through the one-writer runner,
postflight checked, evaluated on the fixed validation bank, and conservatively
gated. A change without explicit paired promotion proof is not inherited.

The controller never opens test data. D1 runs only if the activation-checkpointed
production resource preflight passes at the unchanged declared shapes. D12 and
three-seed critic repeats run only after their independent predecessor gates.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml


B0_CONFIG = Path("prep/configs/frozen_calibrated_lr3e4_dicos-f-02.yaml")
B0_CHECKPOINT = Path("_runs/calibrated_lr3e4_dicos-f-02/checkpoints/best.pt")
B0_CONFIG_SHA256 = "116bc8c220b07ce54ae07196bdd6ed8e835775c8c937182a209a799dc94ae9c5"
B0_CHECKPOINT_SHA256 = "491284c7423f365230d34b0443f95aa4888ec770bdc673c4c979897bad8acbce"
B0_ROW = "B0"
S4_CONFIG = Path("prep/configs/frozen_v3_S4_activity_ar.yaml")
S4_CHECKPOINT = Path("_runs/v3_S4_activity_ar/checkpoints/best.pt")
EXPECTED_EPOCHS = 24
REPLICATION_SEEDS = (20260723, 20260724, 20260725)
S5_ROW = ("S5-count-ar", "v3-s5-count-ar")
S6_ROWS = [
    ("S6-temp-025", "v3-s6-temp-025"),
    ("S6-temp-050", "v3-s6-temp-050"),
    ("S6-temp-100", "v3-s6-temp-100"),
    ("S6-temp-200", "v3-s6-temp-200"),
]
S7_ROW = ("S7-profile-ot-cfm", "v3-s7-profile-ot-cfm")
CRITIC_ROWS = [
    ("D1-feature-r05", "D1", "feature_matching", 0.05),
    ("D1-direct-r05", "D1", "direct_non_saturating", 0.05),
    ("D1-direct-r10", "D1", "direct_non_saturating", 0.10),
    ("D1-direct-r20", "D1", "direct_non_saturating", 0.20),
    ("D2-feature-r05", "D2", "feature_matching", 0.05),
    ("D2-direct-r05", "D2", "direct_non_saturating", 0.05),
    ("D2-direct-r10", "D2", "direct_non_saturating", 0.10),
    ("D2-direct-r20", "D2", "direct_non_saturating", 0.20),
]
MATRIX_RELATIVE = Path("specs/improvement_v3/experiment_matrix.csv")
DECLARED_ROW_DISPOSITIONS = {
    "B0": "completed_frozen_reference",
    "S1-axis": "completed_not_promoted",
    "S2-response": "completed_not_promoted",
    "S3-first": "completed_not_promoted",
    "S4-activity-span": "controller_required_matched_ablation",
    "S4-activity-ar": "active_external_writer_then_controller_gate",
    "S5-count-ar": "controller_conditional_on_selected_s4",
    "S6-temp-025": "controller_matched_grid_conditional_on_s5",
    "S6-temp-050": "controller_matched_grid_conditional_on_s5",
    "S6-temp-100": "controller_matched_grid_conditional_on_s5",
    "S6-temp-200": "controller_matched_grid_conditional_on_s5",
    "S7-ot-profile": "controller_alias_s7_profile_ot_cfm_conditional_on_unique_s6",
    "V3-SUP": "controller_partition_matched_supervised_composite",
    "C0": "controller_partition_matched_no_critic_control",
    "D1-feature-r05": "controller_critic_screen_resource_gated",
    "D1-direct-r05": "controller_critic_screen_resource_gated",
    "D1-direct-r10": "controller_critic_screen_resource_gated",
    "D1-direct-r20": "controller_critic_screen_resource_gated",
    "D2-feature-r05": "controller_independent_critic_screen",
    "D2-direct-r05": "controller_independent_critic_screen",
    "D2-direct-r10": "controller_independent_critic_screen",
    "D2-direct-r20": "controller_independent_critic_screen",
    "D1-selected-3seed": "controller_three_seed_repeat_after_unique_d1",
    "D2-selected-3seed": "controller_three_seed_repeat_after_unique_d2",
    "D12": "controller_conditional_after_both_frozen_cross_seed_aggregates",
    "D3-triggered": "triggered_only_outside_current_goal",
    "FINAL-V3-SUP": "outside_current_goal_test_sealed",
    "FINAL-V3-CRITIC": "outside_current_goal_test_sealed",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def atomic_json(path: Path, payload: dict) -> None:
    atomic_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def verify_declared_matrix(path: Path) -> dict[str, object]:
    """Prove every declared row has an explicit controller-era disposition."""
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    ids = [row["id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise RuntimeError("experiment matrix contains duplicate row IDs")
    if set(ids) != set(DECLARED_ROW_DISPOSITIONS):
        missing = sorted(set(ids) - set(DECLARED_ROW_DISPOSITIONS))
        extra = sorted(set(DECLARED_ROW_DISPOSITIONS) - set(ids))
        raise RuntimeError(
            f"controller/matrix coverage mismatch; missing={missing}, extra={extra}"
        )
    orders = [int(row["order"]) for row in rows]
    if orders != list(range(len(rows))):
        raise RuntimeError("experiment matrix order is not contiguous from zero")
    in_goal = rows[:25]
    if [int(row["order"]) for row in in_goal] != list(range(25)):
        raise RuntimeError("through-D12 goal rows are not matrix orders 0..24")
    if any(row["test_access"] != "none" for row in in_goal):
        raise RuntimeError("a through-D12 row declares test access")

    by_id = {row["id"]: row for row in rows}
    for row_id, stage, objective, ratio in CRITIC_ROWS:
        row = by_id[row_id]
        if row["parent"] != "C0" or row["critic_objective"] != objective:
            raise RuntimeError(f"critic matrix contract mismatch for {row_id}")
        if float(row["gradient_ratio"]) != ratio:
            raise RuntimeError(f"critic ratio mismatch for {row_id}")
        expected_change = "share_critic" if stage == "D1" else "profile_critic"
        if row["change"] != expected_change:
            raise RuntimeError(f"critic stage mismatch for {row_id}")
    for row_id in ("D1-selected-3seed", "D2-selected-3seed"):
        if by_id[row_id]["seeds"] != "20260723|20260724|20260725":
            raise RuntimeError(f"three-seed contract mismatch for {row_id}")
    if by_id["D12"]["parent"] != "selected_D1_D2":
        raise RuntimeError("D12 parent is not selected_D1_D2")
    if by_id["S7-ot-profile"]["parent"] != "selected_S6":
        raise RuntimeError("S7 matrix parent is not selected_S6")
    return {
        "matrix": str(MATRIX_RELATIVE).replace("\\", "/"),
        "matrix_sha256": sha256_file(path),
        "declared_rows": len(rows),
        "through_d12_rows": len(in_goal),
        "through_d12_test_access_rows": 0,
        "dispositions": dict(DECLARED_ROW_DISPOSITIONS),
        "s7_controller_alias": "S7-profile-ot-cfm",
        "test_events_used": 0,
    }


class Controller:
    def __init__(
        self, root: Path, snapshot: Path, poll_seconds: int,
        state_dir: Path | None = None,
    ):
        self.root = root
        self.snapshot = snapshot
        self.poll_seconds = poll_seconds
        requested_state = state_dir or Path("_autonomous/v3_full_pipeline")
        self.state_dir = (
            requested_state if requested_state.is_absolute() else root / requested_state
        ).resolve()
        if self.state_dir != root and root not in self.state_dir.parents:
            raise ValueError("controller state directory must stay inside the project root")
        self.state_path = self.state_dir / "state.json"
        self.events_path = self.state_dir / "events.jsonl"
        self.decisions = self.state_dir / "decisions"
        self.templates = self.state_dir / "templates"
        self.configs = self.state_dir / "configs"
        self.checkpoints = self.state_dir / "checkpoints"
        self.reports = self.state_dir / "reports"
        self.logs = self.state_dir / "logs"
        self.audit = self.state_dir / "audit"
        self.run_receipts = self.state_dir / "run_receipts"
        self.preparation_receipts = self.state_dir / "preparation_receipts"
        self.evidence_log = self.root / "logs.md"
        self.event_sequence = 0
        self.python = root / ".venv/bin/python"
        self.contract = json.loads(
            (snapshot / "configs/v3_validation_battery_contract.json").read_text(encoding="utf-8")
        )
        self.acceptance_gates_path = snapshot / "specs/improvement_v3/acceptance_gates.yaml"
        self.acceptance_gates = yaml.safe_load(
            self.acceptance_gates_path.read_text(encoding="utf-8")
        )
        self.promoted: list[str] = []
        self.parent_row = B0_ROW
        self.parent_config = root / B0_CONFIG
        self.parent_checkpoint = root / B0_CHECKPOINT

    def state(self, status: str, **details: object) -> None:
        atomic_json(self.state_path, {
            "schema_version": 1,
            "kind": "cbsc-zdc-v3-full-pipeline-controller-state",
            "status": status,
            "updated_utc": utc_now(),
            "promoted_supervised_rows": self.promoted,
            "retained_parent_row": self.parent_row,
            "test_events_used": 0,
            **details,
        })

    def event(self, event: str, **details: object) -> None:
        timestamp = utc_now()
        self.event_sequence += 1
        compact_time = timestamp.replace("-", "").replace(":", "").replace(".", "")
        compact_time = compact_time.replace("Z", "Z")
        slug = "".join(character.lower() if character.isalnum() else "_" for character in event)
        evidence_id = f"event_{compact_time}_{os.getpid()}_{self.event_sequence:06d}_{slug}"
        payload = {
            "schema_version": 1,
            "kind": "cbsc-zdc-v3-controller-event",
            "timestamp_utc": timestamp,
            "event": event,
            "evidence_id": evidence_id,
            "test_events_used": 0,
            **details,
        }
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        with self.events_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")
            handle.flush(); os.fsync(handle.fileno())
        audit_json = self.audit / f"{evidence_id}.json"
        audit_md = self.audit / f"{evidence_id}.md"
        atomic_json(audit_json, payload)
        atomic_text(audit_md, (
            f"# V3 controller event: {event}\n\n"
            f"Timestamp: `{timestamp}`  \n"
            f"Evidence ID: `{evidence_id}`  \n"
            "Test events used: 0. Physics validation established: no.\n\n"
            "## Evidence\n\n```json\n"
            f"{json.dumps(payload, indent=2, sort_keys=True)}\n```\n"
        ))
        relative_audit = audit_json.relative_to(self.root).with_suffix("")
        with self.evidence_log.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(
                f"\n- {timestamp} remote v3 controller `{event}`; evidence twin "
                f"`{str(relative_audit).replace(os.sep, '/')}.{{json,md}}`; "
                "test events used: 0; physics validation established: no.\n"
            )
            handle.flush(); os.fsync(handle.fileno())

    def environment_evidence(self, env: dict[str, str]) -> dict[str, object]:
        """Record only bounded, non-secret runtime identity fields."""
        return {
            "cwd": str(self.root),
            "python_executable": str(self.python),
            "python_version": sys.version,
            "python_no_user_site": env.get("PYTHONNOUSERSITE"),
            "python_path": env.get("PYTHONPATH"),
            "cuda_visible_devices": env.get("CUDA_VISIBLE_DEVICES"),
        }

    def artifact_hashes(self, argv: list[str]) -> dict[str, str]:
        """Hash file arguments only when they resolve inside the project root."""
        hashes: dict[str, str] = {}
        for value in argv[1:]:
            candidate = Path(value)
            path = (candidate if candidate.is_absolute() else self.root / candidate).resolve()
            try:
                relative = path.relative_to(self.root)
            except ValueError:
                continue
            if path.is_file():
                hashes[str(relative).replace("\\", "/")] = sha256_file(path)
        return dict(sorted(hashes.items()))

    def command(self, argv: list[str], name: str, *, allow_failure: bool = False) -> subprocess.CompletedProcess:
        log_path = self.logs / f"{name}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ, PYTHONNOUSERSITE="1",
                   PYTHONPATH=f"{self.snapshot / 'src'}:{self.root / 'repo/src'}")
        self.event(
            "COMMAND_START", name=name, argv=argv,
            log=str(log_path.relative_to(self.root)),
            environment=self.environment_evidence(env),
            artifact_hashes_before=self.artifact_hashes(argv),
        )
        with log_path.open("a", encoding="utf-8", newline="\n") as log:
            result = subprocess.run(argv, cwd=self.root, env=env, stdout=log, stderr=subprocess.STDOUT)
        self.event(
            "COMMAND_END", name=name, returncode=result.returncode,
            log_sha256=sha256_file(log_path),
            artifact_hashes_after=self.artifact_hashes(argv),
        )
        if result.returncode and not allow_failure:
            raise RuntimeError(f"{name} exited {result.returncode}; see {log_path}")
        return result

    def verify_snapshot(self) -> None:
        manifest_path = self.snapshot / "DEPLOYMENT_MANIFEST.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for relative, expected in manifest["files"].items():
            path = self.snapshot / relative
            if not path.is_file() or sha256_file(path) != expected:
                raise RuntimeError(f"snapshot hash mismatch: {relative}")
        if self.contract.get("split") != "validation" or self.contract.get("test_events_used") != 0:
            raise RuntimeError("validation battery contract is not test-sealed")
        b0_parent = self.verify_b0_parent()
        validation_manifest = self.verify_validation_manifest_contract()
        coverage = verify_declared_matrix(self.snapshot / MATRIX_RELATIVE)
        self.event(
            "SNAPSHOT_VERIFIED", manifest_sha256=sha256_file(manifest_path),
            file_count=len(manifest["files"]),
            declared_stage_coverage=coverage,
            b0_parent=b0_parent,
            validation_manifest=validation_manifest,
            environment=self.environment_evidence(dict(os.environ)),
        )

    def verify_b0_parent(self) -> dict[str, object]:
        """Bind the initial parent to the accepted B0 battery provenance."""
        observed = {}
        for label, relative, expected in (
            ("frozen_config", B0_CONFIG, B0_CONFIG_SHA256),
            ("checkpoint", B0_CHECKPOINT, B0_CHECKPOINT_SHA256),
        ):
            path = self.root / relative
            if not path.is_file():
                raise RuntimeError(f"B0 {label} is absent")
            actual = sha256_file(path)
            if actual != expected:
                raise RuntimeError(f"B0 {label} hash mismatch")
            observed[label] = {
                "path": str(relative).replace("\\", "/"),
                "sha256": actual,
            }
        return observed

    def verify_validation_manifest_contract(self) -> dict[str, object]:
        """Bind the actual remote validation bank to the immutable contract."""
        if self.contract.get("status") != "immutable after first autonomous launch":
            raise RuntimeError("validation battery contract is not immutable")
        relative = Path(str(self.contract.get("validation_manifest", "")))
        if not relative.parts or relative.is_absolute() or ".." in relative.parts:
            raise RuntimeError("validation manifest path is not project-relative")
        path = (self.root / relative).resolve()
        try:
            path.relative_to(self.root)
        except ValueError as error:
            raise RuntimeError("validation manifest path escapes the project root") from error
        if not path.is_file():
            raise RuntimeError("validation manifest file is absent")
        observed_file_hash = sha256_file(path)
        expected_file_hash = self.contract.get("validation_manifest_file_sha256")
        if observed_file_hash != expected_file_hash:
            raise RuntimeError("validation manifest file hash mismatch")
        bank = json.loads(path.read_text(encoding="utf-8"))
        expected_content_hash = self.contract.get("validation_manifest_sha256")
        if bank.get("content_sha256") != expected_content_hash:
            raise RuntimeError("validation manifest content identity mismatch")
        return {
            "path": str(relative).replace("\\", "/"),
            "file_sha256": observed_file_hash,
            "content_sha256": expected_content_hash,
        }

    def wait_for_s4(self) -> dict:
        path = self.root / "_autonomous/v3_s4_followup/state.json"
        while True:
            state = json.loads(path.read_text(encoding="utf-8"))
            self.state("WAITING_FOR_S4", s4=state)
            if state.get("status") == "COMPLETE":
                self.event("S4_FOLLOWER_COMPLETE", state=state)
                return state
            if state.get("status") == "FAILED_NO_RETRY":
                raise RuntimeError(f"S4 follower failed: {state.get('error')}")
            time.sleep(self.poll_seconds)

    def verify_s4_handoff(self, state: dict) -> dict:
        """Independently bind the follower state to the exact parent artifacts."""
        required = {
            "selected_epoch", "checkpoint_sha256", "battery", "battery_sha256",
        }
        missing = sorted(required - set(state))
        if missing:
            raise RuntimeError(f"S4 COMPLETE state omits {missing}")
        battery_relative = Path(str(state["battery"]))
        if battery_relative.is_absolute() or ".." in battery_relative.parts:
            raise RuntimeError("S4 battery path is not project-relative")
        battery_path = (self.root / battery_relative).resolve()
        try:
            battery_path.relative_to(self.root)
        except ValueError as error:
            raise RuntimeError("S4 battery path escapes the project root") from error
        config_path = self.root / S4_CONFIG
        checkpoint_path = self.root / S4_CHECKPOINT
        for label, path in (
            ("battery", battery_path),
            ("frozen config", config_path),
            ("selected checkpoint", checkpoint_path),
        ):
            if not path.is_file():
                raise RuntimeError(f"S4 {label} is absent: {path}")
        if sha256_file(battery_path) != state["battery_sha256"]:
            raise RuntimeError("S4 battery hash disagrees with follower state")
        if sha256_file(checkpoint_path) != state["checkpoint_sha256"]:
            raise RuntimeError("S4 checkpoint hash disagrees with follower state")
        report = json.loads(battery_path.read_text(encoding="utf-8"))
        identity = report.get("identity") or {}
        expected = {
            "run_tag": "v3-s4-activity-ar",
            "epoch": int(state["selected_epoch"]),
            "checkpoint_sha256": state["checkpoint_sha256"],
            "frozen_config_sha256": sha256_file(config_path),
        }
        for field, value in expected.items():
            if identity.get(field) != value:
                raise RuntimeError(f"S4 battery identity mismatch for {field}")
        self.verify_battery_report(
            report,
            run_tag="v3-s4-activity-ar",
            epoch=int(state["selected_epoch"]),
            checkpoint=checkpoint_path,
            frozen=config_path,
        )
        self.event(
            "S4_HANDOFF_INDEPENDENTLY_VERIFIED",
            battery=str(battery_relative).replace("\\", "/"),
            battery_sha256=state["battery_sha256"],
            checkpoint_sha256=state["checkpoint_sha256"],
            selected_epoch=int(state["selected_epoch"]),
            test_events_used=0,
        )
        return report

    def prove_no_writer(self) -> None:
        result = subprocess.run(
            ["sh", "_watch/probe_train_tree.sh"], cwd=self.root,
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"trainer process-tree probe failed: {result.stderr.strip()}")
        if result.stdout.strip():
            raise RuntimeError(f"trainer already exists:\n{result.stdout}")

    def prove_one_writer(self) -> str:
        result = subprocess.run(
            ["sh", "_watch/probe_train_tree.sh"], cwd=self.root,
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"trainer process-tree probe failed: {result.stderr.strip()}")
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        processes: list[tuple[int, int]] = []
        for line in lines:
            fields = line.split(None, 2)
            if len(fields) < 2:
                raise RuntimeError(f"unparseable trainer process row: {line!r}")
            processes.append((int(fields[0]), int(fields[1])))
        pids = {pid for pid, _ in processes}
        roots = [(pid, ppid) for pid, ppid in processes if ppid not in pids]
        if len(roots) != 1:
            raise RuntimeError(
                f"expected one trainer-root writer, found {len(roots)}:\n{result.stdout}"
            )
        return result.stdout

    def validate_training(self, run_dir: Path) -> tuple[int, float]:
        history_path = run_dir / "logs/history.csv"
        with history_path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        if len(rows) != EXPECTED_EPOCHS:
            raise RuntimeError(f"{run_dir} has {len(rows)}/{EXPECTED_EPOCHS} epochs")
        epochs = [int(float(row["epoch"])) for row in rows]
        if epochs != list(range(EXPECTED_EPOCHS)):
            raise RuntimeError(f"{run_dir} history is noncontiguous")
        for epoch, row in enumerate(rows):
            value = float(row["validation_loss"])
            if not math.isfinite(value):
                raise RuntimeError(f"nonfinite validation loss at epoch {epoch}")
            invariant = json.loads(
                (run_dir / f"reports/invariant_epoch_{epoch:04d}.json").read_text(encoding="utf-8")
            )
            if invariant.get("pass") is not True:
                raise RuntimeError(f"invariant failure at epoch {epoch}")
        postflight = json.loads((run_dir / "reports/training_postflight.json").read_text(encoding="utf-8"))
        if postflight.get("pass") is not True:
            raise RuntimeError("training postflight failed")
        best = min(rows, key=lambda row: (float(row["validation_loss"]), int(float(row["epoch"]))))
        return int(float(best["epoch"])), float(best["validation_loss"])

    def verify_battery_report(
        self,
        report: dict,
        *,
        run_tag: str,
        epoch: int,
        checkpoint: Path,
        frozen: Path,
    ) -> None:
        """Bind a reusable battery report to every frozen evaluation input."""
        if report.get("split") != "validation" or report.get("test_events_used") != 0:
            raise RuntimeError("battery violated split contract")
        if report.get("structural_invariants", {}).get("pass") is not True:
            raise RuntimeError("battery structural invariants failed")
        expected_selection_role = (
            "descriptive validation evidence"
            if self.contract["evaluation_role"] == "diagnostic"
            else "declared selection evidence"
        )
        report_contract = {
            "schema_version": 3,
            "kind": "cbsc-zdc-v3-validation-battery",
            "selection_role": expected_selection_role,
            "scientific_status": self.contract["scientific_status"],
            "pairs": self.contract["pairs"],
            "evaluator_corpus_examples": self.contract["evaluator_corpus_examples"],
            "validation_events_used": self.contract["pairs"],
            "train_events_used": self.contract["memorization_reference_events"],
            "test_events_used": 0,
        }
        report_mismatches = {
            field: {"expected": value, "observed": report.get(field)}
            for field, value in report_contract.items()
            if report.get(field) != value
        }
        expected_usage = {
            "validation_truth_events": self.contract["pairs"],
            "generated_events": self.contract["pairs"],
            "training_reference_events": self.contract["memorization_reference_events"],
            "training_reference_role": "memorization nearest-neighbour reference only",
            "test_events": 0,
        }
        usage = report.get("data_usage")
        if usage != expected_usage:
            report_mismatches["data_usage"] = {
                "expected": expected_usage,
                "observed": usage,
            }
        bootstrap = report.get("bootstrap") or {}
        expected_bootstrap = {
            "replicates": self.contract["bootstrap_replicates"],
            "confidence": self.contract["bootstrap_confidence"],
            "stratified_by": "primary energy bin",
            "paired": True,
        }
        observed_bootstrap = {
            field: bootstrap.get(field) for field in expected_bootstrap
        }
        if observed_bootstrap != expected_bootstrap:
            report_mismatches["bootstrap"] = {
                "expected": expected_bootstrap,
                "observed": observed_bootstrap,
            }
        observed_structural_events = (report.get("topology") or {}).get(
            "subsample_events"
        )
        if observed_structural_events != self.contract["structural_subsample_events"]:
            report_mismatches["structural_subsample_events"] = {
                "expected": self.contract["structural_subsample_events"],
                "observed": observed_structural_events,
            }
        if report_mismatches:
            raise RuntimeError(f"battery report contract mismatch: {report_mismatches}")
        identity = report.get("identity") or {}
        expected = {
            "run_tag": run_tag,
            "epoch": epoch,
            "checkpoint_embedded_epoch": epoch,
            "checkpoint_sha256": sha256_file(checkpoint),
            "frozen_config_sha256": sha256_file(frozen),
            "validation_manifest_sha256": self.contract["validation_manifest_sha256"],
            "data_manifest_sha256": self.contract["data_manifest_sha256"],
            "splits_sha256": self.contract["splits_sha256"],
            "generator_seed": self.contract["generator_seed"],
            "evaluator_seeds": self.contract["evaluator_seeds"],
            "energy_bin_edges_gev": self.contract["energy_bin_edges_gev"],
            "profile_steps": self.contract["profile_steps"],
            "share_steps": self.contract["share_steps"],
            "precision": self.contract["precision"],
            "batch_size": self.contract["batch_size"],
            "evaluation_role": self.contract["evaluation_role"],
            "device": self.contract["device"],
            "output_namespace": f"v3-battery/{run_tag}",
        }
        mismatches = {
            field: {"expected": value, "observed": identity.get(field)}
            for field, value in expected.items()
            if identity.get(field) != value
        }
        if mismatches:
            raise RuntimeError(f"battery identity mismatch: {mismatches}")

    def battery(self, row_id: str, run_tag: str, run_dir: Path, frozen: Path) -> Path:
        epoch, loss = self.validate_training(run_dir)
        output = self.root / f"_v3/battery/{run_tag}_epoch{epoch}.json"
        if not output.exists():
            argv = [
                str(self.python), str(self.snapshot / "scripts/run_v3_validation_battery.py"),
                "evaluate", "--checkpoint", str(run_dir / "checkpoints/best.pt"),
                "--frozen-config", str(frozen),
                "--validation-manifest", str(self.root / self.contract["validation_manifest"]),
                "--geometry", str(self.root / self.contract["geometry_manifest"]),
                "--output", str(output),
                "--data-manifest-sha256", self.contract["data_manifest_sha256"],
                "--splits-sha256", self.contract["splits_sha256"],
                "--generator-seed", str(self.contract["generator_seed"]),
                "--evaluator-seeds", *[str(value) for value in self.contract["evaluator_seeds"]],
                "--energy-bin-edges-gev", *[str(value) for value in self.contract["energy_bin_edges_gev"]],
                "--profile-steps", str(self.contract["profile_steps"]),
                "--share-steps", str(self.contract["share_steps"]),
                "--precision", self.contract["precision"],
                "--output-namespace", f"v3-battery/{run_tag}",
                "--evaluation-role", self.contract["evaluation_role"],
                "--run-tag", run_tag, "--epoch", str(epoch),
                "--device", self.contract["device"],
                "--batch-size", str(self.contract["batch_size"]),
                "--bootstrap-replicates", str(self.contract["bootstrap_replicates"]),
                "--bootstrap-confidence", str(self.contract["bootstrap_confidence"]),
                "--memorization-reference-events", str(self.contract["memorization_reference_events"]),
                "--memorization-reference-seed", str(self.contract["memorization_reference_seed"]),
                "--structural-subsample-events", str(self.contract["structural_subsample_events"]),
            ]
            self.command(argv, f"battery-{run_tag}-e{epoch}")
        report = json.loads(output.read_text(encoding="utf-8"))
        self.verify_battery_report(
            report,
            run_tag=run_tag,
            epoch=epoch,
            checkpoint=run_dir / "checkpoints/best.pt",
            frozen=frozen,
        )
        self.event("BATTERY_VERIFIED", row_id=row_id, run_tag=run_tag, epoch=epoch,
                   selected_validation_loss=loss, report=str(output.relative_to(self.root)),
                   report_sha256=sha256_file(output))
        return output

    def decision(self, row_id: str, report_path: Path, *, candidate_kind: str) -> bool:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        gate = report.get("promotion_gate")
        gate_source_sha256 = sha256_file(self.acceptance_gates_path)
        gate_source_status = self.acceptance_gates.get("status")
        if candidate_kind.startswith("critic-"):
            # The critic rule is not the paired supervised rule.  In particular,
            # an affirmative supervised gate must never select D1/D2.  The live
            # acceptance-gates source still labels the critic rule ``proposed``,
            # and the fixed validation battery does not yet emit its complete
            # external-C2ST/diversity/memorization/gradient/replay proof.  Keep
            # this branch explicit and fail closed until a hash-bound frozen
            # source and a matching machine-readable report exist.
            critic_fields = set(self.acceptance_gates.get("critic_candidate", {}))
            checks = gate.get("critic_candidate_checks") if isinstance(gate, dict) else None
            promoted = bool(
                gate_source_status == "frozen_validation_selection_rules"
                and isinstance(gate, dict)
                and gate.get("schema_version") == 1
                and gate.get("gate_family") == "critic_candidate"
                and gate.get("acceptance_gates_sha256") == gate_source_sha256
                and isinstance(checks, dict)
                and set(checks) == critic_fields
                and all(checks.get(field) is True for field in critic_fields)
                and gate.get("decision") == "PROMOTE"
            )
            unresolved_reason = (
                "critic promotion requires the distinct hash-bound critic_candidate "
                "gate; its current source is proposed and/or the report omits the "
                "complete external-C2ST, gradient-isolation, replay, diversity, "
                "memorization, and gradient-ratio proof"
            )
            gate_family = "critic_candidate"
        else:
            promoted = bool(
                gate_source_status == "frozen_validation_selection_rules"
                and isinstance(gate, dict)
                and gate.get("schema_version") == 1
                and gate.get("gate_family") == "paired_candidate"
                and gate.get("acceptance_gates_sha256") == gate_source_sha256
                and gate.get("paired_bootstrap_replicates") == 1000
                and gate.get("target_delta_95_upper_below_zero") is True
                and gate.get("all_guards_pass") is True
                and gate.get("c2st_increase_at_most_0_01") is True
                and gate.get("sampling_time_guard_pass") is True
                and gate.get("decision") == "PROMOTE"
            )
            unresolved_reason = (
                "paired promotion requires a hash-bound owner-frozen paired_candidate "
                "gate source and complete affirmative report proof; the simpler parent "
                "is retained"
            )
            gate_family = "paired_candidate"
        payload = {
            "schema_version": 1,
            "kind": "cbsc-zdc-v3-automatic-promotion-decision",
            "row_id": row_id,
            "candidate_kind": candidate_kind,
            "gate_family": gate_family,
            "acceptance_gates_source": str(
                self.acceptance_gates_path.relative_to(self.snapshot)
            ).replace("\\", "/"),
            "acceptance_gates_sha256": gate_source_sha256,
            "acceptance_gates_status": gate_source_status,
            "decision": "PROMOTED" if promoted else "NOT_PROMOTED_UNRESOLVED",
            "reason": (
                f"all exact {gate_family} gates passed"
                if promoted else unresolved_reason
            ),
            "report": str(report_path.relative_to(self.root)),
            "report_sha256": sha256_file(report_path),
            "test_events_used": 0,
            "timestamp_utc": utc_now(),
        }
        path = self.decisions / f"{row_id}.json"
        atomic_json(path, payload)
        self.event("PROMOTION_DECISION", **payload)
        return promoted

    def _preparation_identity(
        self, row_id: str, run_tag: str, parent_config: Path,
        parent_checkpoint: Path, **details: object,
    ) -> dict[str, object]:
        return {
            "schema_version": 1,
            "kind": "cbsc-zdc-v3-preparation-receipt",
            "status": "COMPLETE_VERIFIED_REUSABLE",
            "row_id": row_id,
            "run_tag": run_tag,
            "parent_config": self._project_relative(parent_config),
            "parent_config_sha256": sha256_file(parent_config),
            "parent_checkpoint": self._project_relative(parent_checkpoint),
            "parent_checkpoint_sha256": sha256_file(parent_checkpoint),
            "deployment_manifest_sha256": sha256_file(
                self.snapshot / "DEPLOYMENT_MANIFEST.json"
            ),
            "test_events_used": 0,
            **details,
        }

    def _preparation_paths(
        self, run_tag: str, *, screening: bool,
    ) -> tuple[Path, Path, Path, Path, Path]:
        template = (
            self.templates / run_tag / f"v3_{run_tag[3:].replace('-', '_')}.yaml"
            if screening else self.templates / f"{run_tag}.yaml"
        )
        frozen = self.configs / f"frozen_{run_tag}.yaml"
        checkpoint = self.checkpoints / f"{run_tag}_init.pt"
        report = self.reports / f"prepare_{run_tag}.json"
        receipt = self.preparation_receipts / f"{run_tag}.json"
        return template, frozen, checkpoint, report, receipt

    def _verify_preparation_artifacts(
        self, template: Path, frozen: Path, checkpoint: Path, report_path: Path,
    ) -> dict[str, str]:
        paths = {
            "template": template,
            "frozen_config": frozen,
            "initial_checkpoint": checkpoint,
            "preparation_report": report_path,
        }
        for label, path in paths.items():
            if not path.is_file():
                raise RuntimeError(f"prepared row is missing {label}: {path}")
        hashes = {label: sha256_file(path) for label, path in paths.items()}
        report = json.loads(report_path.read_text(encoding="utf-8"))
        expected_report_hashes = {
            "template_sha256": hashes["template"],
            "frozen_sha256": hashes["frozen_config"],
            "initial_checkpoint_sha256": hashes["initial_checkpoint"],
        }
        mismatches = {
            field: {"expected": value, "observed": report.get(field)}
            for field, value in expected_report_hashes.items()
            if report.get(field) != value
        }
        frozen_payload = yaml.safe_load(frozen.read_text(encoding="utf-8"))
        training = frozen_payload.get("training", {})
        expected_checkpoint = self._project_relative(checkpoint)
        if training.get("initialize_from_relative") != expected_checkpoint:
            mismatches["initialize_from_relative"] = {
                "expected": expected_checkpoint,
                "observed": training.get("initialize_from_relative"),
            }
        if training.get("initialize_from_sha256") != hashes["initial_checkpoint"]:
            mismatches["initialize_from_sha256"] = {
                "expected": hashes["initial_checkpoint"],
                "observed": training.get("initialize_from_sha256"),
            }
        if mismatches:
            raise RuntimeError(f"prepared artifact identity mismatch: {mismatches}")
        return hashes

    def reuse_preparation(
        self, identity: dict[str, object], template: Path, frozen: Path,
        checkpoint: Path, report: Path, receipt: Path,
    ) -> bool:
        candidates = (template, frozen, checkpoint, report, receipt)
        if not any(path.exists() for path in candidates):
            return False
        if not all(path.is_file() for path in candidates):
            raise RuntimeError("partial prepared row exists; refusing to overwrite it")
        recorded = json.loads(receipt.read_text(encoding="utf-8"))
        mismatches = {
            field: {"expected": value, "observed": recorded.get(field)}
            for field, value in identity.items() if recorded.get(field) != value
        }
        hashes = self._verify_preparation_artifacts(
            template, frozen, checkpoint, report
        )
        if recorded.get("artifact_sha256") != hashes:
            mismatches["artifact_sha256"] = {
                "expected": recorded.get("artifact_sha256"), "observed": hashes,
            }
        if mismatches:
            raise RuntimeError(f"preparation receipt mismatch: {mismatches}")
        self.event(
            "PREPARATION_REUSED", row_id=identity["row_id"],
            run_tag=identity["run_tag"], receipt=self._project_relative(receipt),
            receipt_sha256=sha256_file(receipt),
        )
        return True

    def record_preparation(
        self, identity: dict[str, object], template: Path, frozen: Path,
        checkpoint: Path, report: Path, receipt: Path,
    ) -> None:
        payload = {
            **identity,
            "artifact_sha256": self._verify_preparation_artifacts(
                template, frozen, checkpoint, report
            ),
            "completed_utc": utc_now(),
        }
        atomic_json(receipt, payload)
        self.event(
            "PREPARATION_VERIFIED", row_id=identity["row_id"],
            run_tag=identity["run_tag"], receipt=self._project_relative(receipt),
            receipt_sha256=sha256_file(receipt),
        )

    def prepare_screening(self, row_id: str, run_tag: str) -> tuple[Path, Path]:
        output_dir = self.templates / row_id
        template, frozen, checkpoint, report, receipt = self._preparation_paths(
            run_tag, screening=True
        )
        # The screening builder names its output from the matrix row, not the tag.
        template = output_dir / f"v3_{row_id.replace('-', '_')}.yaml"
        identity = self._preparation_identity(
            row_id, run_tag, self.parent_config, self.parent_checkpoint,
            preparation_kind="supervised_screening",
            inherited_rows=list(self.promoted),
        )
        if self.reuse_preparation(
            identity, template, frozen, checkpoint, report, receipt
        ):
            return frozen, checkpoint
        argv = [
            str(self.python), str(self.snapshot / "scripts/build_v3_screening_configs.py"),
            "--parent", str(self.root / B0_CONFIG), "--envelope", str(self.root / "_v3/envelope_pilot_full.json"),
            "--output-dir", str(output_dir), "--only", row_id,
            "--horizon", str(EXPECTED_EPOCHS),
        ]
        if self.promoted:
            argv += ["--inherit", *self.promoted]
        self.command(argv, f"build-{run_tag}")
        self.command([
            str(self.python), str(self.snapshot / "scripts/v3_prepare_screening_run.py"),
            "--template", str(template), "--parent-checkpoint", str(self.parent_checkpoint),
            "--frozen-output", str(frozen), "--checkpoint-output", str(checkpoint),
            "--report", str(report), "--audit", str(self.root / "prep/train_data_audit_pilot.json"),
            "--checkpoint-relative", str(checkpoint.relative_to(self.root)),
        ], f"prepare-{run_tag}")
        self.record_preparation(
            identity, template, frozen, checkpoint, report, receipt
        )
        return frozen, checkpoint

    def _project_relative(self, path: Path) -> str:
        resolved = path.resolve()
        try:
            return str(resolved.relative_to(self.root.resolve())).replace("\\", "/")
        except ValueError as error:
            raise RuntimeError(f"artifact escapes the project root: {path}") from error

    def _training_artifact_hashes(self, run_dir: Path) -> dict[str, str]:
        relative_paths = (
            "logs/history.csv",
            "checkpoints/best.pt",
            "checkpoints/last.pt",
            "reports/training_postflight.json",
            "runtime_config.yaml",
            "environment.json",
            "result.json",
        )
        hashes: dict[str, str] = {}
        for relative in relative_paths:
            path = run_dir / relative
            if not path.is_file():
                raise RuntimeError(f"completed run is missing required artifact: {path}")
            hashes[relative] = sha256_file(path)
        return hashes

    def _receipt_path(self, run_tag: str) -> Path:
        return self.run_receipts / f"{run_tag}.json"

    def authorize_run(
        self, row_id: str, run_tag: str, run_dir: Path, frozen: Path,
        trainer_argv: list[str],
    ) -> None:
        manifest = self.snapshot / "DEPLOYMENT_MANIFEST.json"
        payload = {
            "schema_version": 1,
            "kind": "cbsc-zdc-v3-training-run-receipt",
            "status": "AUTHORIZED_NOT_REUSABLE",
            "row_id": row_id,
            "run_tag": run_tag,
            "run_dir": self._project_relative(run_dir),
            "frozen_config": self._project_relative(frozen),
            "frozen_config_sha256": sha256_file(frozen),
            "trainer_argv": trainer_argv,
            "deployment_manifest_sha256": sha256_file(manifest),
            "expected_epochs": EXPECTED_EPOCHS,
            "test_events_used": 0,
            "timestamp_utc": utc_now(),
        }
        atomic_json(self._receipt_path(run_tag), payload)
        self.event(
            "RUN_AUTHORIZED", row_id=row_id, run_tag=run_tag,
            receipt=self._project_relative(self._receipt_path(run_tag)),
            receipt_sha256=sha256_file(self._receipt_path(run_tag)),
            frozen_config_sha256=payload["frozen_config_sha256"],
        )

    def complete_run_receipt(
        self, row_id: str, run_tag: str, run_dir: Path, frozen: Path,
    ) -> None:
        receipt_path = self._receipt_path(run_tag)
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        expected = {
            "status": "AUTHORIZED_NOT_REUSABLE",
            "row_id": row_id,
            "run_tag": run_tag,
            "run_dir": self._project_relative(run_dir),
            "frozen_config": self._project_relative(frozen),
            "frozen_config_sha256": sha256_file(frozen),
            "trainer_argv": [
                str(self.python), str(self.snapshot / "scripts/dicos_train.py"),
                "--config", str(frozen), "--run-dir", str(run_dir),
                "--staged-root", str(self.root), "--postflight",
            ],
            "deployment_manifest_sha256": sha256_file(
                self.snapshot / "DEPLOYMENT_MANIFEST.json"
            ),
            "expected_epochs": EXPECTED_EPOCHS,
            "test_events_used": 0,
        }
        mismatches = {
            field: {"expected": value, "observed": receipt.get(field)}
            for field, value in expected.items() if receipt.get(field) != value
        }
        if mismatches:
            raise RuntimeError(f"run authorization receipt mismatch: {mismatches}")
        epoch, loss = self.validate_training(run_dir)
        receipt.update({
            "status": "COMPLETE_VERIFIED_REUSABLE",
            "selected_epoch": epoch,
            "selected_validation_loss": loss,
            "artifact_sha256": self._training_artifact_hashes(run_dir),
            "completed_utc": utc_now(),
        })
        atomic_json(receipt_path, receipt)
        self.event(
            "RUN_COMPLETION_RECEIPT_VERIFIED", row_id=row_id, run_tag=run_tag,
            receipt=self._project_relative(receipt_path),
            receipt_sha256=sha256_file(receipt_path), selected_epoch=epoch,
            selected_validation_loss=loss,
        )

    def verify_reusable_run(
        self, row_id: str, run_tag: str, run_dir: Path, frozen: Path,
    ) -> None:
        receipt_path = self._receipt_path(run_tag)
        if not receipt_path.is_file():
            raise RuntimeError(
                f"existing run has no completed controller receipt: {run_dir}"
            )
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        expected = {
            "schema_version": 1,
            "kind": "cbsc-zdc-v3-training-run-receipt",
            "status": "COMPLETE_VERIFIED_REUSABLE",
            "row_id": row_id,
            "run_tag": run_tag,
            "run_dir": self._project_relative(run_dir),
            "frozen_config": self._project_relative(frozen),
            "frozen_config_sha256": sha256_file(frozen),
            "trainer_argv": [
                str(self.python), str(self.snapshot / "scripts/dicos_train.py"),
                "--config", str(frozen), "--run-dir", str(run_dir),
                "--staged-root", str(self.root), "--postflight",
            ],
            "deployment_manifest_sha256": sha256_file(
                self.snapshot / "DEPLOYMENT_MANIFEST.json"
            ),
            "expected_epochs": EXPECTED_EPOCHS,
            "test_events_used": 0,
        }
        mismatches = {
            field: {"expected": value, "observed": receipt.get(field)}
            for field, value in expected.items() if receipt.get(field) != value
        }
        current_hashes = self._training_artifact_hashes(run_dir)
        if receipt.get("artifact_sha256") != current_hashes:
            mismatches["artifact_sha256"] = {
                "expected": receipt.get("artifact_sha256"),
                "observed": current_hashes,
            }
        epoch, loss = self.validate_training(run_dir)
        for field, value in {
            "selected_epoch": epoch,
            "selected_validation_loss": loss,
        }.items():
            if receipt.get(field) != value:
                mismatches[field] = {"expected": receipt.get(field), "observed": value}
        if mismatches:
            raise RuntimeError(f"completed run receipt mismatch: {mismatches}")
        self.event(
            "COMPLETED_RUN_REUSED", row_id=row_id, run_tag=run_tag,
            receipt=self._project_relative(receipt_path),
            receipt_sha256=sha256_file(receipt_path), selected_epoch=epoch,
            selected_validation_loss=loss,
        )

    def train_row(self, row_id: str, run_tag: str, frozen: Path) -> tuple[Path, Path]:
        self.prove_no_writer()
        run_dir = self.root / f"_runs/{run_tag}"
        trainer_argv = [
            str(self.python), str(self.snapshot / "scripts/dicos_train.py"),
            "--config", str(frozen), "--run-dir", str(run_dir),
            "--staged-root", str(self.root), "--postflight",
        ]
        if run_dir.exists():
            self.verify_reusable_run(row_id, run_tag, run_dir, frozen)
            report = self.battery(row_id, run_tag, run_dir, frozen)
            return run_dir, report
        self.authorize_run(row_id, run_tag, run_dir, frozen, trainer_argv)
        self.state("TRAINING", row_id=row_id, run_tag=run_tag)
        trainer_log = self.logs / f"train-{run_tag}.log"
        trainer_log.parent.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ, PYTHONNOUSERSITE="1",
                   PYTHONPATH=f"{self.snapshot / 'src'}:{self.root / 'repo/src'}")
        live_output = self.state_dir / f"live_metrics/{run_tag}"
        watcher_argv = [
            str(self.python), str(self.snapshot / "scripts/v3_remote_live_metrics.py"),
            "--history", str(run_dir / "logs/history.csv"),
            "--reports", str(run_dir / "reports"),
            "--output", str(live_output), "--run-tag", run_tag,
            "--evidence-log", str(self.evidence_log),
            "--poll-seconds", str(self.poll_seconds),
        ]
        self.event(
            "TRAIN_LAUNCH", row_id=row_id, run_tag=run_tag,
            argv=trainer_argv, log=str(trainer_log.relative_to(self.root)),
            environment=self.environment_evidence(env),
            artifact_hashes_before=self.artifact_hashes(trainer_argv),
        )
        watcher = subprocess.Popen(
            watcher_argv, cwd=self.root, env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        try:
            with trainer_log.open("a", encoding="utf-8", newline="\n") as log:
                trainer = subprocess.Popen(
                    trainer_argv, cwd=self.root, env=env, stdout=log,
                    stderr=subprocess.STDOUT,
                )
                try:
                    time.sleep(10)
                    if trainer.poll() is not None:
                        raise RuntimeError(
                            f"trainer exited before liveness proof with {trainer.returncode}"
                        )
                    tree = self.prove_one_writer()
                    self.event("ONE_WRITER_PROVED", row_id=row_id, run_tag=run_tag,
                               process_tree=tree)
                    returncode = trainer.wait()
                except BaseException:
                    if trainer.poll() is None:
                        trainer.terminate()
                        try:
                            trainer.wait(timeout=30)
                        except subprocess.TimeoutExpired:
                            trainer.kill(); trainer.wait()
                    self.event("TRAIN_ABORTED_FAIL_CLOSED", row_id=row_id,
                               run_tag=run_tag, returncode=trainer.returncode)
                    raise
        finally:
            if watcher.poll() is None:
                watcher.terminate()
                try:
                    watcher.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    watcher.kill(); watcher.wait()
        output_argv = [
            "artifacts", str(run_dir / "logs/history.csv"),
            str(run_dir / "checkpoints/best.pt"),
            str(run_dir / "reports/training_postflight.json"),
        ]
        self.event(
            "TRAIN_END", row_id=row_id, run_tag=run_tag,
            returncode=returncode, log_sha256=sha256_file(trainer_log),
            artifact_hashes_after=self.artifact_hashes(output_argv),
        )
        if returncode:
            raise RuntimeError(f"training {run_tag} exited {returncode}; see {trainer_log}")
        self.complete_run_receipt(row_id, run_tag, run_dir, frozen)
        self.command([
            str(self.python), str(self.snapshot / "scripts/v3_remote_live_metrics.py"),
            "--history", str(run_dir / "logs/history.csv"),
            "--reports", str(run_dir / "reports"),
            "--output", str(live_output), "--run-tag", run_tag, "--once",
            "--evidence-log", str(self.evidence_log),
        ], f"live-metrics-final-{run_tag}")
        report = self.battery(row_id, run_tag, run_dir, frozen)
        return run_dir, report

    def record_matched_ablation(self, row_id: str, report_path: Path) -> None:
        payload = {
            "schema_version": 1,
            "kind": "cbsc-zdc-v3-matched-ablation-disposition",
            "row_id": row_id,
            "decision": "REPORTED_NOT_PRIMARY_PROMOTION_CANDIDATE",
            "reason": (
                "the frozen train-only compact-fraction rule selected "
                "S4-activity-ar as primary; span/gaps remains the required matched ablation"
            ),
            "report": str(report_path.relative_to(self.root)),
            "report_sha256": sha256_file(report_path),
            "test_events_used": 0,
            "timestamp_utc": utc_now(),
        }
        atomic_json(self.decisions / f"{row_id}.json", payload)
        self.event("MATCHED_ABLATION_RECORDED", **payload)

    def build_role_partition(self) -> Path:
        output = self.state_dir / "role_partition.json"
        if not output.exists():
            self.command([
                str(self.python), str(self.snapshot / "scripts/build_v3_role_partition.py"),
                "--manifest", str(self.root / "prep/data/dataset_manifest.json"),
                "--splits", str(self.root / "prep/splits.json"),
                "--output", str(output),
            ], "build-role-partition")
        role = json.loads(output.read_text(encoding="utf-8"))
        if role.get("counts") != {"generator_train": 551234, "critic_real_train": 30624,
                                  "critic_monitor_holdout": 30624}:
            raise RuntimeError("role partition counts failed")
        return output

    def prepare_partition_row(
        self, row_id: str, run_tag: str, parent_config: Path, parent_checkpoint: Path,
        role_path: Path, *, stage: str | None = None, objective: str | None = None,
        ratio: float | None = None, seed: int | None = None,
        selected_d1_config: Path | None = None,
        selected_d2_config: Path | None = None,
    ) -> Path:
        template, frozen, checkpoint, report, receipt = self._preparation_paths(
            run_tag, screening=False
        )
        identity_details: dict[str, object] = {
            "preparation_kind": "partition_matched",
            "role_partition": self._project_relative(role_path),
            "role_partition_sha256": sha256_file(role_path),
            "stage": stage,
            "objective": objective,
            "gradient_ratio_target": ratio,
            "seed": seed,
        }
        if selected_d1_config is not None:
            identity_details.update({
                "selected_d1_config": self._project_relative(selected_d1_config),
                "selected_d1_config_sha256": sha256_file(selected_d1_config),
            })
        if selected_d2_config is not None:
            identity_details.update({
                "selected_d2_config": self._project_relative(selected_d2_config),
                "selected_d2_config_sha256": sha256_file(selected_d2_config),
            })
        identity = self._preparation_identity(
            row_id, run_tag, parent_config, parent_checkpoint, **identity_details
        )
        if self.reuse_preparation(
            identity, template, frozen, checkpoint, report, receipt
        ):
            return frozen
        argv = [
            str(self.python), str(self.snapshot / "scripts/build_v3_partition_template.py"),
            "--parent", str(parent_config), "--output", str(template), "--row-id", row_id,
            "--role-partition", str(role_path), "--full-splits", str(self.root / "prep/splits.json"),
            "--full-audit", str(self.root / "prep/train_data_audit.json"),
            "--horizon", str(EXPECTED_EPOCHS),
        ]
        if seed is not None:
            argv += ["--seed", str(seed)]
        if stage == "D12":
            if not selected_d1_config or not selected_d2_config:
                raise RuntimeError("D12 preparation requires selected D1 and D2 configs")
            contract_hash = sha256_file(self.snapshot / "specs/improvement_v3/contract_live_20260814.yaml")
            argv += [
                "--critic-stage", "D12",
                "--selected-d1-config", str(selected_d1_config),
                "--selected-d2-config", str(selected_d2_config),
                "--experiment-contract-sha256", contract_hash,
            ]
        elif stage:
            contract_hash = sha256_file(self.snapshot / "specs/improvement_v3/contract_live_20260814.yaml")
            argv += ["--critic-stage", stage, "--objective", str(objective),
                     "--gradient-ratio-target", str(ratio),
                     "--experiment-contract-sha256", contract_hash]
        self.command(argv, f"build-{run_tag}")
        self.command([
            str(self.python), str(self.snapshot / "scripts/v3_prepare_screening_run.py"),
            "--template", str(template), "--parent-checkpoint", str(parent_checkpoint),
            "--frozen-output", str(frozen), "--checkpoint-output", str(checkpoint),
            "--report", str(report),
            "--audit", str(self.root / "prep/train_data_audit.json"),
            "--checkpoint-relative", str(checkpoint.relative_to(self.root)),
        ], f"prepare-{run_tag}")
        self.record_preparation(
            identity, template, frozen, checkpoint, report, receipt
        )
        return frozen

    def d1_resource_pass(self) -> bool:
        output = self.reports / "d1_activation_checkpointed_resource_preflight.json"
        result = self.command([
            str(self.python), str(self.snapshot / "scripts/v3_d1_production_preflight.py"),
            "--geometry", str(self.root / "prep/geometry_frozen"),
            "--frozen-config", str(self.root / B0_CONFIG), "--device", "cuda",
            "--critic-batch", "4", "--generator-batch", "6", "--warmup", "2",
            "--measured", "4", "--repeats", "1", "--r1-gamma", "1.0",
            "--activation-checkpointing", "--output", str(output),
        ], "d1-resource-preflight", allow_failure=True)
        report = json.loads(output.read_text(encoding="utf-8")) if output.exists() else {}
        passed = result.returncode == 0 and report.get("d1_fits_declared_batch") is True
        self.event("D1_RESOURCE_DECISION", passed=passed, report=str(output.relative_to(self.root)),
                   report_sha256=sha256_file(output) if output.exists() else None)
        return passed

    def retain_supervised_parent(
        self, row_id: str, frozen: Path, run_dir: Path,
    ) -> None:
        self.promoted.append(row_id)
        self.parent_row = row_id
        self.parent_config = frozen
        self.parent_checkpoint = run_dir / "checkpoints/best.pt"

    def run_dependent_supervised_chain(self) -> dict[str, object]:
        """Run only rows whose declared supervised prerequisites are satisfied."""
        s5_row, s5_tag = S5_ROW
        s5_frozen, _ = self.prepare_screening(s5_row, s5_tag)
        s5_run, s5_report = self.train_row(s5_row, s5_tag, s5_frozen)
        if not self.decision(s5_row, s5_report, candidate_kind="supervised"):
            skipped = [row for row, _ in S6_ROWS] + [S7_ROW[0]]
            reason = (
                "S5 was not affirmatively promoted; every S6 row requires the "
                "selected S5 parent and S7 requires a selected S6, so those "
                "dependent rows are ineligible. V3-SUP retains the selected S4."
            )
            self.event("DEPENDENT_ROWS_SKIPPED", after=s5_row, skipped=skipped, reason=reason)
            return {"s5_promoted": False, "selected_s6": None, "s7_run": False}
        self.retain_supervised_parent(s5_row, s5_frozen, s5_run)

        # Every temperature is a matched arm against the same selected S5.
        # Do not update the parent while the mutually exclusive grid is running.
        selected_s6: list[tuple[str, Path, Path]] = []
        for row_id, run_tag in S6_ROWS:
            frozen, _ = self.prepare_screening(row_id, run_tag)
            run_dir, report = self.train_row(row_id, run_tag, frozen)
            if self.decision(row_id, report, candidate_kind="supervised"):
                selected_s6.append((row_id, frozen, run_dir))

        if len(selected_s6) != 1:
            reason = (
                "no S6 arm passed" if not selected_s6 else
                "multiple S6 arms passed and no frozen tie-breaker selects one"
            )
            self.event(
                "S6_SELECTION_UNRESOLVED_RETAIN_S5",
                passing_rows=[row[0] for row in selected_s6],
                skipped=[S7_ROW[0]], reason=(
                    f"{reason}; retain the simpler selected S5 and skip S7, "
                    "whose declared parent is selected_S6"
                ),
            )
            return {"s5_promoted": True, "selected_s6": None, "s7_run": False}

        s6_row, s6_frozen, s6_run = selected_s6[0]
        self.retain_supervised_parent(s6_row, s6_frozen, s6_run)
        self.event("S6_SELECTED", row_id=s6_row)

        s7_row, s7_tag = S7_ROW
        s7_frozen, _ = self.prepare_screening(s7_row, s7_tag)
        s7_run, s7_report = self.train_row(s7_row, s7_tag, s7_frozen)
        if self.decision(s7_row, s7_report, candidate_kind="supervised"):
            self.retain_supervised_parent(s7_row, s7_frozen, s7_run)
        else:
            self.event(
                "S7_NOT_PROMOTED_PARENT_RETAINED", retained_parent=self.parent_row,
            )
        return {"s5_promoted": True, "selected_s6": s6_row, "s7_run": True}

    def run_independent_critic_replications(
        self,
        promoted_critics: dict[str, list[tuple[str, Path, Path]]],
        c0_config: Path,
        c0_run: Path,
        role_path: Path,
    ) -> dict[str, list[dict]]:
        """Repeat each uniquely selected critic stage independently."""
        replication_reports: dict[str, list[dict]] = {"D1": [], "D2": []}
        for stage in ("D1", "D2"):
            candidates = promoted_critics[stage]
            if len(candidates) != 1:
                reason = (
                    "no arm passed its single-run gate" if not candidates else
                    "multiple arms passed and no frozen tie-breaker selects one"
                )
                self.event(
                    "CRITIC_REPLICATION_SKIPPED", stage=stage,
                    passing_rows=[row[0] for row in candidates], reason=reason,
                )
                continue
            selected_row, selected_config, _ = candidates[0]
            selected_spec = next(row for row in CRITIC_ROWS if row[0] == selected_row)
            _, _, objective, ratio = selected_spec
            for seed_value in REPLICATION_SEEDS:
                run_tag = f"{stage.lower()}-selected-seed{seed_value}"
                frozen = self.prepare_partition_row(
                    f"{stage}-selected-3seed", run_tag, c0_config,
                    c0_run / "checkpoints/best.pt", role_path,
                    stage=stage, objective=objective, ratio=ratio, seed=seed_value,
                )
                _, report = self.train_row(
                    f"{stage}-selected-3seed", run_tag, frozen
                )
                replication_reports[stage].append({
                    "seed": seed_value,
                    "report": str(report.relative_to(self.root)),
                    "report_sha256": sha256_file(report),
                    "single_run_gate": self.decision(
                        f"{stage}-selected-seed{seed_value}", report,
                        candidate_kind=f"critic-{stage}-replication",
                    ),
                })
        return replication_reports

    def verify_replication_aggregate(
        self,
        stage: str,
        replication_reports: list[dict],
        selected_row: str,
        selected_config: Path,
    ) -> tuple[dict | None, str | None]:
        """Verify owner-frozen cross-seed evidence without inventing its rule."""
        rule = self.acceptance_gates.get("replication_aggregate") or {}
        source_hash = sha256_file(self.acceptance_gates_path)
        required_seeds = list(REPLICATION_SEEDS)
        aggregate_path = (
            self.root / f"_v3/replication_aggregates/{stage.lower()}-selected-3seed.json"
        )
        source_ready = bool(
            self.acceptance_gates.get("status") == "frozen_validation_selection_rules"
            and rule.get("status") == "frozen_cross_seed_selection_rule"
            and isinstance(rule.get("rule_id"), str)
            and rule.get("rule_id")
            and rule.get("artifact_kind") == "cbsc-zdc-v3-critic-replication-aggregate"
            and rule.get("required_seeds") == required_seeds
            and isinstance(rule.get("required_checks"), list)
            and rule.get("required_checks")
        )
        if not source_ready:
            blocker = f"{stage}_REPLICATION_AGGREGATION_RULE_NOT_OWNER_FROZEN"
            self.event(
                "REPLICATION_AGGREGATE_BLOCKED",
                stage=stage,
                blocker=blocker,
                acceptance_gates_status=self.acceptance_gates.get("status"),
                replication_rule_status=rule.get("status"),
                acceptance_gates_sha256=source_hash,
            )
            return None, blocker

        seeds = [row.get("seed") for row in replication_reports]
        if seeds != required_seeds:
            blocker = f"{stage}_REPLICATION_REPORT_SET_INCOMPLETE_OR_REORDERED"
            self.event(
                "REPLICATION_AGGREGATE_BLOCKED", stage=stage,
                blocker=blocker, expected_seeds=required_seeds,
                observed_seeds=seeds,
            )
            return None, blocker
        if not aggregate_path.is_file():
            blocker = f"{stage}_OWNER_FROZEN_REPLICATION_AGGREGATE_ABSENT"
            self.event(
                "REPLICATION_AGGREGATE_BLOCKED", stage=stage,
                blocker=blocker,
                expected_path=str(aggregate_path.relative_to(self.root)).replace("\\", "/"),
            )
            return None, blocker

        aggregate = json.loads(aggregate_path.read_text(encoding="utf-8"))
        expected_seed_reports = [
            {
                "seed": row["seed"],
                "report": row["report"],
                "report_sha256": row["report_sha256"],
            }
            for row in replication_reports
        ]
        expected = {
            "schema_version": 1,
            "kind": rule["artifact_kind"],
            "stage": stage,
            "row_id": f"{stage}-selected-3seed",
            "selected_row": selected_row,
            "selected_config_sha256": sha256_file(selected_config),
            "acceptance_gates_sha256": source_hash,
            "aggregation_rule_id": rule["rule_id"],
            "required_seeds": required_seeds,
            "seed_reports": expected_seed_reports,
            "split": "validation",
            "test_events_used": 0,
        }
        mismatches = {
            field: {"expected": value, "observed": aggregate.get(field)}
            for field, value in expected.items()
            if aggregate.get(field) != value
        }
        required_checks = set(rule["required_checks"])
        checks = aggregate.get("checks")
        checks_pass = bool(
            isinstance(checks, dict)
            and set(checks) == required_checks
            and all(checks.get(field) is True for field in required_checks)
        )
        promoted = bool(
            not mismatches and checks_pass and aggregate.get("decision") == "PROMOTE"
        )
        evidence = {
            "schema_version": 1,
            "kind": "cbsc-zdc-v3-replication-aggregate-decision",
            "stage": stage,
            "selected_row": selected_row,
            "aggregate": str(aggregate_path.relative_to(self.root)).replace("\\", "/"),
            "aggregate_sha256": sha256_file(aggregate_path),
            "acceptance_gates_sha256": source_hash,
            "mismatches": mismatches,
            "required_checks_exact_and_true": checks_pass,
            "decision": "PROMOTE" if promoted else "NOT_PROMOTED_UNRESOLVED",
            "test_events_used": 0,
            "timestamp_utc": utc_now(),
        }
        atomic_json(self.decisions / f"{stage}-replication-aggregate.json", evidence)
        self.event("REPLICATION_AGGREGATE_DECISION", **evidence)
        if not promoted:
            return None, f"{stage}_REPLICATION_AGGREGATE_NOT_AFFIRMATIVE"
        return aggregate, None

    def run_d12_if_eligible(
        self,
        promoted_critics: dict[str, list[tuple[str, Path, Path]]],
        replication_reports: dict[str, list[dict]],
        c0_config: Path,
        c0_run: Path,
        role_path: Path,
    ) -> tuple[dict | None, list[str]]:
        """Run D12 only after exact, frozen D1 and D2 cross-seed aggregates."""
        blockers: list[str] = []
        selected: dict[str, tuple[str, Path, Path]] = {}
        for stage in ("D1", "D2"):
            candidates = promoted_critics[stage]
            if len(candidates) != 1:
                blockers.append(
                    f"{stage}_SELECTION_NOT_UNIQUE_FOR_D12"
                    if candidates else f"NO_INDEPENDENT_{stage}_PROMOTION_FOR_D12"
                )
                continue
            selected[stage] = candidates[0]
            aggregate, blocker = self.verify_replication_aggregate(
                stage,
                replication_reports[stage],
                candidates[0][0],
                candidates[0][1],
            )
            if aggregate is None and blocker is not None:
                blockers.append(blocker)
        if blockers:
            self.event("D12_SKIPPED_FAIL_CLOSED", blockers=blockers)
            return None, blockers

        d12_config = self.prepare_partition_row(
            "D12", "d12", c0_config, c0_run / "checkpoints/best.pt", role_path,
            stage="D12", selected_d1_config=selected["D1"][1],
            selected_d2_config=selected["D2"][1],
        )
        d12_run, d12_report = self.train_row("D12", "d12", d12_config)
        promoted = self.decision("D12", d12_report, candidate_kind="critic-D12")
        result = {
            "row_id": "D12",
            "run_dir": str(d12_run.relative_to(self.root)).replace("\\", "/"),
            "frozen_config": str(d12_config.relative_to(self.root)).replace("\\", "/"),
            "report": str(d12_report.relative_to(self.root)).replace("\\", "/"),
            "report_sha256": sha256_file(d12_report),
            "promoted": promoted,
            "test_events_used": 0,
        }
        self.event("D12_COMPLETE", **result)
        if not promoted:
            blockers.append("D12_COMPLETE_NOT_AFFIRMATIVELY_PROMOTED")
        return result, blockers

    def c0_allows_critics(self, c0_report: Path) -> bool:
        if self.decision("C0", c0_report, candidate_kind="partition-control"):
            return True
        reason = (
            "C0 did not provide complete affirmative frozen validation-gate "
            "proof; every D1/D2 row requires the promoted partition-matched "
            "no-critic control"
        )
        self.state("BLOCKED_C0_NOT_PROMOTED", reason=reason)
        self.event("STABLE_BLOCKER", blocker="C0_NOT_PROMOTED", reason=reason)
        return False

    def run_partition_controls(self) -> tuple[Path, Path, Path] | None:
        """Build the composite, then train V3-SUP and C0 on the exact partition."""
        composite_config, composite_checkpoint = self.prepare_screening(
            "V3-SUP", "v3-sup-composite-init"
        )
        role_path = self.build_role_partition()
        v3sup_config = self.prepare_partition_row(
            "V3-SUP", "v3-sup", composite_config, composite_checkpoint, role_path
        )
        v3sup_run, v3sup_report = self.train_row("V3-SUP", "v3-sup", v3sup_config)
        self.event("V3_SUP_COMPLETE", report_sha256=sha256_file(v3sup_report))

        c0_config = self.prepare_partition_row(
            "C0", "v3-c0", v3sup_config,
            v3sup_run / "checkpoints/best.pt", role_path,
        )
        c0_run, c0_report = self.train_row("C0", "v3-c0", c0_config)
        self.event("C0_COMPLETE", report_sha256=sha256_file(c0_report))
        if not self.c0_allows_critics(c0_report):
            return None
        return c0_config, c0_run, role_path

    def run(self) -> None:
        self.verify_snapshot()
        s4 = self.wait_for_s4()
        self.verify_s4_handoff(s4)
        span_config, _ = self.prepare_screening(
            "S4-activity-span", "v3-s4-activity-span"
        )
        _, span_report = self.train_row(
            "S4-activity-span", "v3-s4-activity-span", span_config
        )
        self.record_matched_ablation("S4-activity-span", span_report)
        s4_promoted = self.decision(
            "S4-activity-ar", self.root / s4["battery"], candidate_kind="supervised"
        )
        if s4_promoted:
            self.retain_supervised_parent(
                "S4-activity-ar", self.root / S4_CONFIG,
                (self.root / S4_CHECKPOINT).parents[1],
            )
            self.run_dependent_supervised_chain()
        else:
            # S5/S6/S7 declare `selected_S4` as their parent in
            # experiment_matrix.csv, so they are genuinely ineligible without a
            # promoted S4 and are skipped below. V3-SUP, C0, and every critic
            # row declare a different parent (`retained_supervised` /
            # `V3-SUP`), not `selected_S4` -- they remain eligible against
            # whichever parent is currently retained (B0, unchanged, if
            # nothing has been promoted) and are attempted regardless. This is
            # a control-flow correction, not a new or relaxed scientific rule:
            # it stops conflating "S4 was not promoted" with "nothing else can
            # run," which are different claims for different declared rows.
            reason = (
                "the immutable S4 battery does not contain complete affirmative "
                "paired candidate-vs-control gate proof; S5 requires a selected S4 "
                "parent, so S5/S6/S7 are not scientifically eligible and are "
                "skipped. The required span/gaps matched ablation has "
                "nevertheless completed. V3-SUP, C0, and the critic rows declare "
                "a different parent and remain independently eligible against "
                "the still-retained parent."
            )
            self.state("BLOCKED_S4_PROMOTION_GATE_UNRESOLVED", reason=reason)
            self.event("STABLE_BLOCKER", blocker="S4_PROMOTION_GATE_UNRESOLVED", reason=reason)
            self.event(
                "DEPENDENT_SUPERVISED_CHAIN_SKIPPED",
                skipped=["S5-count-ar", *[row for row, _ in S6_ROWS], S7_ROW[0]],
                reason="S4-activity-ar was not promoted; S5/S6/S7 declare selected_S4 as parent",
            )

        partition_controls = self.run_partition_controls()
        if partition_controls is None:
            return
        c0_config, c0_run, role_path = partition_controls

        d1_pass = self.d1_resource_pass()
        promoted_critics: dict[str, list[tuple[str, Path, Path]]] = {"D1": [], "D2": []}
        for row_id, stage, objective, ratio in CRITIC_ROWS:
            if stage == "D1" and not d1_pass:
                self.event("ROW_BLOCKED_RESOURCE", row_id=row_id, stage=stage,
                           reason="activation-checkpointed D1 production preflight failed at unchanged shapes")
                continue
            run_tag = row_id.lower()
            frozen = self.prepare_partition_row(
                row_id, run_tag, c0_config, c0_run / "checkpoints/best.pt", role_path,
                stage=stage, objective=objective, ratio=ratio,
            )
            run_dir, report = self.train_row(row_id, run_tag, frozen)
            if self.decision(row_id, report, candidate_kind=f"critic-{stage}"):
                promoted_critics[stage].append((row_id, frozen, run_dir))

        replication_reports = self.run_independent_critic_replications(
            promoted_critics, c0_config, c0_run, role_path,
        )
        d12_result, d12_blockers = self.run_d12_if_eligible(
            promoted_critics, replication_reports, c0_config, c0_run, role_path,
        )
        blockers = []
        if not s4_promoted:
            blockers.append("S4_PROMOTION_GATE_UNRESOLVED_S5_S6_S7_SKIPPED")
        if not d1_pass:
            blockers.append("D1_RESOURCE_PREFLIGHT_FAIL_ON_24_GIB")
        for stage in ("D1", "D2"):
            count = len(promoted_critics[stage])
            if count == 0:
                blockers.append(f"NO_INDEPENDENT_{stage}_PROMOTION")
            elif count > 1:
                blockers.append(f"{stage}_SELECTION_AMBIGUOUS_NO_FROZEN_TIEBREAKER")
        blockers.extend(d12_blockers)
        self.state(
            "COMPLETE_ALL_ELIGIBLE_ROWS_STABLE_BLOCKERS",
            blockers=blockers, replication_reports=replication_reports,
            d12_result=d12_result,
        )
        self.event(
            "PIPELINE_TERMINAL", blockers=blockers,
            replication_reports=replication_reports, d12_result=d12_result,
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--poll-seconds", type=int, default=300)
    parser.add_argument(
        "--state-dir", type=Path, default=Path("_autonomous/v3_full_pipeline"),
        help="project-relative controller state namespace",
    )
    parser.add_argument(
        "--preflight-only", action="store_true",
        help="verify the immutable deployment snapshot and report S4 state without taking the controller lock",
    )
    args = parser.parse_args()
    controller = Controller(
        args.root.resolve(), args.snapshot.resolve(), args.poll_seconds, args.state_dir
    )
    if args.preflight_only:
        controller.verify_snapshot()
        s4_path = controller.root / "_autonomous/v3_s4_followup/state.json"
        s4 = json.loads(s4_path.read_text(encoding="utf-8"))
        print(json.dumps({
            "snapshot": "VERIFIED",
            "s4_status": s4.get("status"),
            "test_events_used": 0,
        }, sort_keys=True))
        return 0
    lock = controller.state_dir / "controller.lock"
    try:
        lock.mkdir(parents=True)
    except FileExistsError as error:
        raise RuntimeError("full-pipeline controller already owns its lock") from error
    atomic_json(lock / "owner.json", {"pid": os.getpid(), "started_utc": utc_now()})
    try:
        controller.state("STARTING")
        controller.run()
        return 0
    except Exception as error:
        controller.state("FAILED_NO_RETRY", error=repr(error))
        controller.event("FAILED_NO_RETRY", error=repr(error))
        raise
    finally:
        # Retain terminal state/events; release only the live-owner lock.
        try:
            (lock / "owner.json").unlink(); lock.rmdir()
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
