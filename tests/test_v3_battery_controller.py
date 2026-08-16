from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "v3_battery_controller", ROOT / "scripts" / "v3_battery_controller.py"
)
assert SPEC and SPEC.loader
CONTROLLER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONTROLLER)


def test_contract_is_validation_only_and_fully_explicit() -> None:
    contract = CONTROLLER.load_contract()
    assert contract["split"] == "validation"
    assert contract["test_events_used"] == 0
    assert len(contract["evaluator_seeds"]) == 3
    assert contract["pairs"] == 10_000
    assert contract["bootstrap_replicates"] == 1_000
    assert contract["validation_manifest_sha256"] != contract[
        "validation_manifest_file_sha256"
    ]


def test_current_complete_rows_are_eligible_and_partial_s2_is_not() -> None:
    rows = CONTROLLER.eligible_rows(CONTROLLER.load_registry())
    ids = {row["row_id"] for row in rows}
    assert {"M0-fresh", "S1-axis"} <= ids
    assert "S2-response" not in ids
    m0 = next(row for row in rows if row["row_id"] == "M0-fresh")
    assert m0["selected_epoch"] == 19
    assert m0["selected_validation_loss"] == pytest.approx(4.513572058600877)


def test_battery_queue_places_frozen_b0_first() -> None:
    rows = CONTROLLER.battery_rows(CONTROLLER.load_registry())
    assert rows[0]["row_id"] == "B0"
    assert rows[0]["selected_epoch"] == 90
    assert rows[0]["selected_validation_loss"] == pytest.approx(4.483767619419238)
    assert len(rows[0]["checkpoint_sha256"]) == 64
    assert len(rows[0]["frozen_config_sha256"]) == 64


def test_incomplete_or_noncontiguous_history_cannot_be_eligible(tmp_path, monkeypatch) -> None:
    root = tmp_path
    row = {
        "row_id": "X", "run_tag": "x", "run_dir": "_runs/x",
        "frozen_config": "prep/x.yaml", "horizon_epochs": 2,
    }
    history = root / "exhibition" / "data" / "v3_screening" / "x" / "history.csv"
    history.parent.mkdir(parents=True)
    with history.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["epoch", "validation_loss"])
        writer.writeheader(); writer.writerow({"epoch": 0, "validation_loss": 1.0})
    monkeypatch.setattr(CONTROLLER, "ROOT", root)
    assert CONTROLLER.eligible_rows({"rows": [row]}) == []


def test_report_validation_rejects_test_use_and_identity_mismatch() -> None:
    report = json.loads(
        (ROOT / "exhibition" / "data" / "v3_battery" / "quarantine"
         / "dicos-f-02_epoch90.zero-truth-relative-error.json")
        .read_text(encoding="utf-8")
    )
    contract = CONTROLLER.load_contract()
    row = {"run_tag": "dicos-f-02", "selected_epoch": 90}
    identity = {
        "checkpoint_sha256": report["identity"].get("checkpoint_sha256", "a" * 64),
        "checkpoint_embedded_epoch": 90,
        "frozen_config_sha256": report["identity"].get("frozen_config_sha256", "b" * 64),
    }
    with pytest.raises(ValueError, match="schema_version"):
        CONTROLLER.validate_report(report, row, contract, identity)
    report["schema_version"] = 2
    report.pop("reconstruction")
    report["paired_response"] = {
        "kind": "paired_detector_response_residual",
        "normalization": "incident_kinetic_energy_gev",
        "response_delta_over_kinetic_rmse": 0.25,
        "response_delta_over_kinetic_mean": 0.01,
        "response_delta_over_kinetic_median_absolute": 0.1,
        "events_included": 10_000,
        "zero_truth_events": 100,
    }
    for field in ("checkpoint_sha256", "checkpoint_embedded_epoch",
                  "frozen_config_sha256"):
        report["identity"][field] = identity[field]
    CONTROLLER.validate_report(report, row, contract, identity)
    report["test_events_used"] = 1
    with pytest.raises(ValueError, match="test_events_used"):
        CONTROLLER.validate_report(report, row, contract, identity)


def test_report_validation_requires_checkpoint_and_config_provenance() -> None:
    report = json.loads(
        (ROOT / "exhibition" / "data" / "v3_battery" / "quarantine"
         / "dicos-f-02_epoch90.zero-truth-relative-error.json")
        .read_text(encoding="utf-8")
    )
    report["schema_version"] = 2
    report.pop("reconstruction")
    report["paired_response"] = {
        "kind": "paired_detector_response_residual",
        "normalization": "incident_kinetic_energy_gev",
        "response_delta_over_kinetic_rmse": 0.25,
        "response_delta_over_kinetic_mean": 0.01,
        "response_delta_over_kinetic_median_absolute": 0.1,
        "events_included": 10_000,
        "zero_truth_events": 100,
    }
    identity = {
        "checkpoint_sha256": "a" * 64,
        "checkpoint_embedded_epoch": 90,
        "frozen_config_sha256": "b" * 64,
    }
    row = {"run_tag": "dicos-f-02", "selected_epoch": 90}
    with pytest.raises(ValueError, match="checkpoint_sha256"):
        CONTROLLER.validate_report(report, row, CONTROLLER.load_contract(), identity)


def test_provenance_sidecar_is_atomic_idempotent_and_conflict_checked(
    monkeypatch, tmp_path
) -> None:
    row = {
        "run_tag": "x", "selected_epoch": 7,
        "selected_validation_loss": 4.2,
    }
    identity = {
        "checkpoint_sha256": "a" * 64,
        "checkpoint_embedded_epoch": 7,
        "checkpoint_best_metric": 4.2,
        "frozen_config_sha256": "b" * 64,
    }
    monkeypatch.setattr(CONTROLLER, "LOCAL_BATTERY", tmp_path)
    assert CONTROLLER.ensure_provenance(row, identity, "c" * 64) is True
    assert CONTROLLER.ensure_provenance(row, identity, "c" * 64) is False
    sidecar = CONTROLLER.provenance_path(row)
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    payload["report_sha256"] = "d" * 64
    sidecar.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(RuntimeError, match="provenance conflict"):
        CONTROLLER.ensure_provenance(row, identity, "c" * 64)


def test_evaluation_command_has_no_split_selector_and_records_every_seed() -> None:
    contract = CONTROLLER.load_contract()
    row = {
        "run_tag": "v3-m0-fresh", "run_dir": "_runs/v3_M0_fresh",
        "frozen_config": "prep/configs/frozen_v3_M0_fresh.yaml",
        "selected_epoch": 19,
    }
    command = CONTROLLER.evaluation_command(row, contract)
    assert "--split " not in command
    assert "--evaluation-split" not in command
    assert "--evaluator-seeds 20260804 20260805 20260806" in command
    assert "--memorization-reference-events 2000" in command
    assert "--structural-subsample-events 10000" in command


def test_a_finished_transaction_without_report_is_not_retried(monkeypatch, tmp_path) -> None:
    row = {
        "row_id": "M0-fresh", "run_tag": "v3-m0-fresh",
        "run_dir": "_runs/v3_M0_fresh", "frozen_config": "prep/x.yaml",
        "selected_epoch": 19, "selected_validation_loss": 1.0,
    }
    monkeypatch.setattr(CONTROLLER, "LOCAL_BATTERY", tmp_path)
    monkeypatch.setattr(CONTROLLER, "load_contract", lambda: {})
    monkeypatch.setattr(CONTROLLER, "load_registry", lambda: {})
    monkeypatch.setattr(CONTROLLER, "battery_rows", lambda registry: [row])
    monkeypatch.setattr(CONTROLLER, "import_remote_report", lambda *a: False)
    monkeypatch.setattr(CONTROLLER, "jobs", lambda: {
        CONTROLLER.job_name(row): "finished"
    })
    monkeypatch.setattr(CONTROLLER, "remote_sha256", lambda path: None)
    with pytest.raises(RuntimeError, match="automatic retry/overwrite is forbidden"):
        CONTROLLER.advance()
