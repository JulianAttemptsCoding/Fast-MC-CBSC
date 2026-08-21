"""Fail-closed tests for the detached full-pipeline controller."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "v3_full_pipeline_controller", ROOT / "scripts/v3_full_pipeline_controller.py"
)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(module)


def test_s4_parent_checkpoint_matches_the_protected_run_directory() -> None:
    assert module.S4_CHECKPOINT == Path(
        "_runs/v3_S4_activity_ar/checkpoints/best.pt"
    )


def test_b0_parent_preflight_binds_config_and_checkpoint_hashes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    controller = _controller(tmp_path)
    config = tmp_path / module.B0_CONFIG
    checkpoint = tmp_path / module.B0_CHECKPOINT
    config.parent.mkdir(parents=True, exist_ok=True)
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    config.write_text("frozen: true\n", encoding="utf-8")
    checkpoint.write_bytes(b"checkpoint")
    monkeypatch.setattr(module, "B0_CONFIG_SHA256", module.sha256_file(config))
    monkeypatch.setattr(
        module, "B0_CHECKPOINT_SHA256", module.sha256_file(checkpoint)
    )
    evidence = controller.verify_b0_parent()
    assert evidence["frozen_config"]["sha256"] == module.sha256_file(config)
    checkpoint.write_bytes(b"changed")
    with pytest.raises(RuntimeError, match="checkpoint hash mismatch"):
        controller.verify_b0_parent()


def test_declared_matrix_coverage_is_exact_through_conditional_d12() -> None:
    coverage = module.verify_declared_matrix(
        ROOT / "specs/improvement_v3/experiment_matrix.csv"
    )
    assert coverage["declared_rows"] == 28
    assert coverage["through_d12_rows"] == 25
    assert coverage["through_d12_test_access_rows"] == 0
    dispositions = coverage["dispositions"]
    assert set(dispositions) == {
        row["id"]
        for row in __import__("csv").DictReader(
            (ROOT / "specs/improvement_v3/experiment_matrix.csv").open(
                newline="", encoding="utf-8"
            )
        )
    }
    assert dispositions["D12"] == (
        "controller_conditional_after_both_frozen_cross_seed_aggregates"
    )
    assert dispositions["D3-triggered"] == "triggered_only_outside_current_goal"
    assert coverage["s7_controller_alias"] == "S7-profile-ot-cfm"


def test_declared_matrix_coverage_rejects_an_unaccounted_row(tmp_path: Path) -> None:
    source = ROOT / "specs/improvement_v3/experiment_matrix.csv"
    changed = tmp_path / "matrix.csv"
    changed.write_text(
        source.read_text(encoding="utf-8")
        + "28,UNDECLARED,B0,pilot,one,x,none,0,none\n",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="coverage mismatch"):
        module.verify_declared_matrix(changed)


def test_event_appends_log_and_writes_json_md_audit_twin(tmp_path: Path) -> None:
    controller = _controller(tmp_path)
    controller.event("QA_VERIFIED", command=["python", "-m", "pytest"], passed=3)
    payload = json.loads(controller.events_path.read_text(encoding="utf-8").splitlines()[-1])
    evidence_id = payload["evidence_id"]
    audit_json = controller.audit / f"{evidence_id}.json"
    audit_md = controller.audit / f"{evidence_id}.md"
    assert audit_json.is_file()
    assert audit_md.is_file()
    assert json.loads(audit_json.read_text(encoding="utf-8")) == payload
    assert "QA_VERIFIED" in audit_md.read_text(encoding="utf-8")
    evidence_log = (tmp_path / "logs.md").read_text(encoding="utf-8")
    assert f"{evidence_id}.{{json,md}}" in evidence_log
    assert "test events used: 0" in evidence_log


def test_command_records_bounded_environment_and_artifact_hashes(tmp_path: Path) -> None:
    controller = _controller(tmp_path)
    script = tmp_path / "write_output.py"
    output = tmp_path / "result.txt"
    script.write_text(
        "from pathlib import Path\nimport sys\nPath(sys.argv[1]).write_text('ok', encoding='utf-8')\n",
        encoding="utf-8",
    )
    controller.command([sys.executable, str(script), str(output)], "evidence-command")
    events = [
        json.loads(line)
        for line in controller.events_path.read_text(encoding="utf-8").splitlines()
    ]
    start, end = events[-2:]
    assert start["event"] == "COMMAND_START"
    assert start["environment"]["python_no_user_site"] == "1"
    assert start["environment"]["cwd"] == str(tmp_path)
    assert start["artifact_hashes_before"] == {
        "write_output.py": module.sha256_file(script)
    }
    assert end["event"] == "COMMAND_END"
    assert end["artifact_hashes_after"] == {
        "result.txt": module.sha256_file(output),
        "write_output.py": module.sha256_file(script),
    }


def test_s4_handoff_binds_state_battery_config_and_checkpoint(tmp_path: Path) -> None:
    controller = _controller(tmp_path)
    config = tmp_path / module.S4_CONFIG
    checkpoint = tmp_path / module.S4_CHECKPOINT
    battery = tmp_path / "_v3/battery/s4.json"
    config.parent.mkdir(parents=True, exist_ok=True)
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    battery.parent.mkdir(parents=True, exist_ok=True)
    config.write_text("frozen: true\n", encoding="utf-8")
    checkpoint.write_bytes(b"checkpoint")
    checkpoint_hash = module.sha256_file(checkpoint)
    payload = _battery_report(
        controller,
        run_tag="v3-s4-activity-ar",
        epoch=7,
        checkpoint=checkpoint,
        frozen=config,
    )
    battery.write_text(json.dumps(payload), encoding="utf-8")
    state = {
        "selected_epoch": 7,
        "checkpoint_sha256": checkpoint_hash,
        "battery": "_v3/battery/s4.json",
        "battery_sha256": module.sha256_file(battery),
    }
    report = controller.verify_s4_handoff(state)
    assert report["identity"]["epoch"] == 7
    assert "S4_HANDOFF_INDEPENDENTLY_VERIFIED" in controller.events_path.read_text(
        encoding="utf-8"
    )


def test_s4_handoff_rejects_full_battery_identity_drift(tmp_path: Path) -> None:
    controller = _controller(tmp_path)
    config = tmp_path / module.S4_CONFIG
    checkpoint = tmp_path / module.S4_CHECKPOINT
    battery = tmp_path / "_v3/battery/s4.json"
    config.parent.mkdir(parents=True, exist_ok=True)
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    battery.parent.mkdir(parents=True, exist_ok=True)
    config.write_text("frozen: true\n", encoding="utf-8")
    checkpoint.write_bytes(b"checkpoint")
    payload = _battery_report(
        controller,
        run_tag="v3-s4-activity-ar",
        epoch=7,
        checkpoint=checkpoint,
        frozen=config,
    )
    payload["identity"]["evaluation_role"] = "test"
    battery.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(RuntimeError, match="battery identity mismatch"):
        controller.verify_s4_handoff({
            "selected_epoch": 7,
            "checkpoint_sha256": module.sha256_file(checkpoint),
            "battery": "_v3/battery/s4.json",
            "battery_sha256": module.sha256_file(battery),
        })


def test_s4_handoff_rejects_checkpoint_hash_mismatch(tmp_path: Path) -> None:
    controller = _controller(tmp_path)
    config = tmp_path / module.S4_CONFIG
    checkpoint = tmp_path / module.S4_CHECKPOINT
    battery = tmp_path / "_v3/battery/s4.json"
    config.parent.mkdir(parents=True, exist_ok=True)
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    battery.parent.mkdir(parents=True, exist_ok=True)
    config.write_text("frozen: true\n", encoding="utf-8")
    checkpoint.write_bytes(b"checkpoint")
    battery.write_text("{}", encoding="utf-8")
    with pytest.raises(RuntimeError, match="checkpoint hash"):
        controller.verify_s4_handoff({
            "selected_epoch": 0,
            "checkpoint_sha256": "0" * 64,
            "battery": "_v3/battery/s4.json",
            "battery_sha256": module.sha256_file(battery),
        })


def _controller(
    tmp_path: Path,
    *,
    gate_status: str = "proposed_validation_selection_rules",
    aggregate_status: str = "owner_definition_required",
):
    snapshot = tmp_path / "snapshot"
    (snapshot / "configs").mkdir(parents=True)
    (snapshot / "specs/improvement_v3").mkdir(parents=True)
    (snapshot / "DEPLOYMENT_MANIFEST.json").write_text(
        json.dumps({"kind": "test-deployment-manifest"}), encoding="utf-8"
    )
    validation_manifest = tmp_path / "_v3/validation_bank.json"
    validation_manifest.parent.mkdir(parents=True)
    validation_manifest.write_text(
        json.dumps({"content_sha256": "a" * 64}), encoding="utf-8"
    )
    (snapshot / "configs/v3_validation_battery_contract.json").write_text(
        json.dumps({
            "status": "immutable after first autonomous launch",
            "split": "validation",
            "test_events_used": 0,
            "validation_manifest": "_v3/validation_bank.json",
            "validation_manifest_sha256": "a" * 64,
            "validation_manifest_file_sha256": module.sha256_file(
                validation_manifest
            ),
            "data_manifest_sha256": "b" * 64,
            "splits_sha256": "c" * 64,
            "generator_seed": 11,
            "evaluator_seeds": [12, 13, 14],
            "energy_bin_edges_gev": [50.0, 250.0001],
            "profile_steps": 8,
            "share_steps": 8,
            "precision": "fp32",
            "batch_size": 8,
            "evaluation_role": "diagnostic",
            "device": "cuda",
            "bootstrap_replicates": 1000,
            "bootstrap_confidence": 0.95,
            "memorization_reference_events": 2000,
            "structural_subsample_events": 10000,
            "pairs": 10000,
            "evaluator_corpus_examples": 20000,
            "scientific_status": "PHYSICS VALIDATION NOT ESTABLISHED",
        }), encoding="utf-8"
    )
    (snapshot / "specs/improvement_v3/acceptance_gates.yaml").write_text(
        "schema_version: 1\n"
        f"status: {gate_status}\n"
        "paired_candidate:\n"
        "  targeted_distance_delta_ci_upper_lt: 0.0\n"
        "critic_candidate:\n"
        "  external_c2st_auc_min_absolute_reduction: 0.02\n"
        "  critic_parameter_generator_gradients: 0\n"
        "replication_aggregate:\n"
        f"  status: {aggregate_status}\n"
        "  artifact_kind: cbsc-zdc-v3-critic-replication-aggregate\n"
        "  rule_id: test-frozen-cross-seed-rule\n"
        "  required_seeds: [20260723, 20260724, 20260725]\n"
        "  required_checks:\n"
        "    - selected_arm_identity_verified\n"
        "    - all_seed_report_hashes_verified\n"
        "    - validation_only_zero_test_events\n"
        "    - cross_seed_benefit_replicated_under_frozen_rule\n",
        encoding="utf-8",
    )
    return module.Controller(tmp_path, snapshot, 1)


def _completed_training_run(tmp_path: Path, run_tag: str) -> Path:
    run_dir = tmp_path / "_runs" / run_tag
    for directory in ("logs", "checkpoints", "reports"):
        (run_dir / directory).mkdir(parents=True, exist_ok=True)
    history = "epoch,validation_loss\n" + "".join(
        f"{epoch},{10.0 - epoch / 10.0}\n"
        for epoch in range(module.EXPECTED_EPOCHS)
    )
    (run_dir / "logs/history.csv").write_text(history, encoding="utf-8")
    for epoch in range(module.EXPECTED_EPOCHS):
        (run_dir / f"reports/invariant_epoch_{epoch:04d}.json").write_text(
            json.dumps({"pass": True}), encoding="utf-8"
        )
    (run_dir / "reports/training_postflight.json").write_text(
        json.dumps({"pass": True}), encoding="utf-8"
    )
    for relative, contents in {
        "checkpoints/best.pt": b"best",
        "checkpoints/last.pt": b"last",
        "runtime_config.yaml": b"runtime: true\n",
        "environment.json": b"{}\n",
        "result.json": b'{"status":"ok"}\n',
    }.items():
        (run_dir / relative).write_bytes(contents)
    return run_dir


def _trainer_argv(controller, frozen: Path, run_dir: Path) -> list[str]:
    return [
        str(controller.python),
        str(controller.snapshot / "scripts/dicos_train.py"),
        "--config", str(frozen),
        "--run-dir", str(run_dir),
        "--staged-root", str(controller.root),
        "--postflight",
    ]


def test_completed_run_receipt_allows_exact_restart_reuse(tmp_path: Path) -> None:
    controller = _controller(tmp_path)
    row_id, run_tag = "S5-count-ar", "v3-s5-count-ar"
    frozen = tmp_path / "frozen.yaml"
    frozen.write_text("frozen: true\n", encoding="utf-8")
    run_dir = _completed_training_run(tmp_path, run_tag)
    controller.authorize_run(
        row_id, run_tag, run_dir, frozen,
        _trainer_argv(controller, frozen, run_dir),
    )
    controller.complete_run_receipt(row_id, run_tag, run_dir, frozen)
    controller.verify_reusable_run(row_id, run_tag, run_dir, frozen)
    events = controller.events_path.read_text(encoding="utf-8")
    assert "RUN_COMPLETION_RECEIPT_VERIFIED" in events
    assert "COMPLETED_RUN_REUSED" in events


def test_completed_run_receipt_rejects_artifact_or_config_drift(tmp_path: Path) -> None:
    controller = _controller(tmp_path)
    row_id, run_tag = "S5-count-ar", "v3-s5-count-ar"
    frozen = tmp_path / "frozen.yaml"
    frozen.write_text("frozen: true\n", encoding="utf-8")
    run_dir = _completed_training_run(tmp_path, run_tag)
    controller.authorize_run(
        row_id, run_tag, run_dir, frozen,
        _trainer_argv(controller, frozen, run_dir),
    )
    controller.complete_run_receipt(row_id, run_tag, run_dir, frozen)
    (run_dir / "checkpoints/best.pt").write_bytes(b"altered")
    with pytest.raises(RuntimeError, match="completed run receipt mismatch"):
        controller.verify_reusable_run(row_id, run_tag, run_dir, frozen)
    (run_dir / "checkpoints/best.pt").write_bytes(b"best")
    frozen.write_text("changed: true\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="completed run receipt mismatch"):
        controller.verify_reusable_run(row_id, run_tag, run_dir, frozen)


def test_existing_run_without_completed_receipt_fails_closed(tmp_path: Path) -> None:
    controller = _controller(tmp_path)
    run_tag = "v3-s5-count-ar"
    _completed_training_run(tmp_path, run_tag)
    frozen = tmp_path / "frozen.yaml"
    frozen.write_text("frozen: true\n", encoding="utf-8")
    controller.prove_no_writer = lambda: None
    with pytest.raises(RuntimeError, match="no completed controller receipt"):
        controller.train_row("S5-count-ar", run_tag, frozen)


def _prepared_artifacts(controller, tmp_path: Path, run_tag: str):
    template, frozen, checkpoint, report, receipt = controller._preparation_paths(
        run_tag, screening=False
    )
    for path in (template, frozen, checkpoint, report):
        path.parent.mkdir(parents=True, exist_ok=True)
    template.write_text("template: true\n", encoding="utf-8")
    checkpoint.write_bytes(b"initial")
    frozen.write_text(
        "training:\n"
        f"  initialize_from_relative: {controller._project_relative(checkpoint)}\n"
        f"  initialize_from_sha256: {module.sha256_file(checkpoint)}\n",
        encoding="utf-8",
    )
    report.write_text(json.dumps({
        "template_sha256": module.sha256_file(template),
        "frozen_sha256": module.sha256_file(frozen),
        "initial_checkpoint_sha256": module.sha256_file(checkpoint),
    }), encoding="utf-8")
    return template, frozen, checkpoint, report, receipt


def test_preparation_receipt_reuses_only_exact_frozen_artifacts(tmp_path: Path) -> None:
    controller = _controller(tmp_path)
    parent_config = tmp_path / "parent.yaml"
    parent_checkpoint = tmp_path / "parent.pt"
    parent_config.write_text("parent: true\n", encoding="utf-8")
    parent_checkpoint.write_bytes(b"parent")
    run_tag = "v3-c0"
    paths = _prepared_artifacts(controller, tmp_path, run_tag)
    identity = controller._preparation_identity(
        "C0", run_tag, parent_config, parent_checkpoint,
        preparation_kind="partition_matched",
    )
    controller.record_preparation(identity, *paths)
    assert controller.reuse_preparation(identity, *paths) is True
    paths[0].write_text("altered: true\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="prepared artifact identity mismatch"):
        controller.reuse_preparation(identity, *paths)


def test_partial_preparation_never_gets_overwritten(tmp_path: Path) -> None:
    controller = _controller(tmp_path)
    parent_config = tmp_path / "parent.yaml"
    parent_checkpoint = tmp_path / "parent.pt"
    parent_config.write_text("parent: true\n", encoding="utf-8")
    parent_checkpoint.write_bytes(b"parent")
    paths = controller._preparation_paths("v3-c0", screening=False)
    paths[0].parent.mkdir(parents=True, exist_ok=True)
    paths[0].write_text("partial: true\n", encoding="utf-8")
    identity = controller._preparation_identity(
        "C0", "v3-c0", parent_config, parent_checkpoint,
        preparation_kind="partition_matched",
    )
    with pytest.raises(RuntimeError, match="partial prepared row"):
        controller.reuse_preparation(identity, *paths)


def test_validation_manifest_contract_binds_remote_file_and_content(
    tmp_path: Path,
) -> None:
    controller = _controller(tmp_path)
    evidence = controller.verify_validation_manifest_contract()
    assert evidence["path"] == "_v3/validation_bank.json"
    assert evidence["content_sha256"] == "a" * 64
    (tmp_path / "_v3/validation_bank.json").write_text(
        json.dumps({"content_sha256": "a" * 64, "changed": True}),
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="file hash mismatch"):
        controller.verify_validation_manifest_contract()


def test_validation_manifest_contract_rejects_path_escape(tmp_path: Path) -> None:
    controller = _controller(tmp_path)
    controller.contract["validation_manifest"] = "../outside.json"
    with pytest.raises(RuntimeError, match="not project-relative"):
        controller.verify_validation_manifest_contract()


def _battery_identity(
    controller,
    *,
    run_tag: str,
    epoch: int,
    checkpoint: Path,
    frozen: Path,
) -> dict:
    return {
        "run_tag": run_tag,
        "epoch": epoch,
        "checkpoint_embedded_epoch": epoch,
        "checkpoint_sha256": module.sha256_file(checkpoint),
        "frozen_config_sha256": module.sha256_file(frozen),
        "validation_manifest_sha256": controller.contract["validation_manifest_sha256"],
        "data_manifest_sha256": controller.contract["data_manifest_sha256"],
        "splits_sha256": controller.contract["splits_sha256"],
        "generator_seed": controller.contract["generator_seed"],
        "evaluator_seeds": controller.contract["evaluator_seeds"],
        "energy_bin_edges_gev": controller.contract["energy_bin_edges_gev"],
        "profile_steps": controller.contract["profile_steps"],
        "share_steps": controller.contract["share_steps"],
        "precision": controller.contract["precision"],
        "batch_size": controller.contract["batch_size"],
        "evaluation_role": controller.contract["evaluation_role"],
        "device": controller.contract["device"],
        "output_namespace": f"v3-battery/{run_tag}",
    }


def _battery_report(
    controller,
    *,
    run_tag: str,
    epoch: int,
    checkpoint: Path,
    frozen: Path,
) -> dict:
    contract = controller.contract
    return {
        "schema_version": 3,
        "kind": "cbsc-zdc-v3-validation-battery",
        "split": "validation",
        "selection_role": "descriptive validation evidence",
        "scientific_status": contract["scientific_status"],
        "pairs": contract["pairs"],
        "evaluator_corpus_examples": contract["evaluator_corpus_examples"],
        "validation_events_used": contract["pairs"],
        "train_events_used": contract["memorization_reference_events"],
        "test_events_used": 0,
        "data_usage": {
            "validation_truth_events": contract["pairs"],
            "generated_events": contract["pairs"],
            "training_reference_events": contract["memorization_reference_events"],
            "training_reference_role": "memorization nearest-neighbour reference only",
            "test_events": 0,
        },
        "structural_invariants": {"pass": True},
        "bootstrap": {
            "replicates": contract["bootstrap_replicates"],
            "confidence": contract["bootstrap_confidence"],
            "stratified_by": "primary energy bin",
            "paired": True,
        },
        "topology": {"subsample_events": contract["structural_subsample_events"]},
        "identity": _battery_identity(
            controller,
            run_tag=run_tag,
            epoch=epoch,
            checkpoint=checkpoint,
            frozen=frozen,
        ),
    }


def test_battery_report_reuse_binds_every_frozen_input(tmp_path: Path) -> None:
    controller = _controller(tmp_path)
    checkpoint = tmp_path / "best.pt"
    frozen = tmp_path / "frozen.yaml"
    checkpoint.write_bytes(b"checkpoint")
    frozen.write_text("frozen: true\n", encoding="utf-8")
    report = _battery_report(
        controller,
        run_tag="v3-row",
        epoch=7,
        checkpoint=checkpoint,
        frozen=frozen,
    )
    controller.verify_battery_report(
        report,
        run_tag="v3-row",
        epoch=7,
        checkpoint=checkpoint,
        frozen=frozen,
    )


@pytest.mark.parametrize(
    ("field", "wrong"),
    [
        ("checkpoint_sha256", "0" * 64),
        ("frozen_config_sha256", "1" * 64),
        ("splits_sha256", "2" * 64),
        ("evaluation_role", "test"),
    ],
)
def test_battery_report_reuse_rejects_identity_drift(
    tmp_path: Path,
    field: str,
    wrong,
) -> None:
    controller = _controller(tmp_path)
    checkpoint = tmp_path / "best.pt"
    frozen = tmp_path / "frozen.yaml"
    checkpoint.write_bytes(b"checkpoint")
    frozen.write_text("frozen: true\n", encoding="utf-8")
    identity = _battery_identity(
        controller,
        run_tag="v3-row",
        epoch=7,
        checkpoint=checkpoint,
        frozen=frozen,
    )
    identity[field] = wrong
    report = _battery_report(
        controller,
        run_tag="v3-row",
        epoch=7,
        checkpoint=checkpoint,
        frozen=frozen,
    )
    report["identity"] = identity
    with pytest.raises(RuntimeError, match="battery identity mismatch"):
        controller.verify_battery_report(
            report,
            run_tag="v3-row",
            epoch=7,
            checkpoint=checkpoint,
            frozen=frozen,
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda report: report.update(schema_version=2), "report contract mismatch"),
        (
            lambda report: report["data_usage"].update(test_events=1),
            "report contract mismatch",
        ),
        (
            lambda report: report["bootstrap"].update(replicates=999),
            "report contract mismatch",
        ),
        (
            lambda report: report["topology"].update(subsample_events=9999),
            "report contract mismatch",
        ),
    ],
)
def test_battery_report_reuse_rejects_internal_accounting_drift(
    tmp_path: Path,
    mutation,
    message: str,
) -> None:
    controller = _controller(tmp_path)
    checkpoint = tmp_path / "best.pt"
    frozen = tmp_path / "frozen.yaml"
    checkpoint.write_bytes(b"checkpoint")
    frozen.write_text("frozen: true\n", encoding="utf-8")
    report = _battery_report(
        controller,
        run_tag="v3-row",
        epoch=7,
        checkpoint=checkpoint,
        frozen=frozen,
    )
    mutation(report)
    with pytest.raises(RuntimeError, match=message):
        controller.verify_battery_report(
            report,
            run_tag="v3-row",
            epoch=7,
            checkpoint=checkpoint,
            frozen=frozen,
        )


def test_promotion_decision_fails_closed_without_complete_gate(tmp_path: Path) -> None:
    controller = _controller(tmp_path)
    report = tmp_path / "report.json"
    report.write_text(json.dumps({"split": "validation", "test_events_used": 0}), encoding="utf-8")
    assert controller.decision("S4-activity-ar", report, candidate_kind="supervised") is False
    decision = json.loads((controller.decisions / "S4-activity-ar.json").read_text(encoding="utf-8"))
    assert decision["decision"] == "NOT_PROMOTED_UNRESOLVED"
    assert decision["test_events_used"] == 0


def test_promotion_requires_every_exact_affirmative_field(tmp_path: Path) -> None:
    controller = _controller(
        tmp_path, gate_status="frozen_validation_selection_rules"
    )
    report = tmp_path / "report.json"
    report.write_text(json.dumps({"promotion_gate": {
        "schema_version": 1,
        "gate_family": "paired_candidate",
        "acceptance_gates_sha256": module.sha256_file(
            controller.acceptance_gates_path
        ),
        "paired_bootstrap_replicates": 1000,
        "target_delta_95_upper_below_zero": True,
        "all_guards_pass": True,
        "c2st_increase_at_most_0_01": True,
        "sampling_time_guard_pass": True,
        "decision": "PROMOTE",
    }}), encoding="utf-8")
    assert controller.decision("S4-activity-ar", report, candidate_kind="supervised") is True


def test_supervised_candidate_cannot_promote_from_proposed_gate_source(
    tmp_path: Path,
) -> None:
    controller = _controller(tmp_path)
    report = tmp_path / "report.json"
    report.write_text(json.dumps({"promotion_gate": {
        "schema_version": 1,
        "gate_family": "paired_candidate",
        "acceptance_gates_sha256": module.sha256_file(
            controller.acceptance_gates_path
        ),
        "paired_bootstrap_replicates": 1000,
        "target_delta_95_upper_below_zero": True,
        "all_guards_pass": True,
        "c2st_increase_at_most_0_01": True,
        "sampling_time_guard_pass": True,
        "decision": "PROMOTE",
    }}), encoding="utf-8")
    assert controller.decision(
        "S4-activity-ar", report, candidate_kind="supervised"
    ) is False


def test_supervised_candidate_rejects_wrong_gate_source_hash(tmp_path: Path) -> None:
    controller = _controller(
        tmp_path, gate_status="frozen_validation_selection_rules"
    )
    report = tmp_path / "report.json"
    report.write_text(json.dumps({"promotion_gate": {
        "schema_version": 1,
        "gate_family": "paired_candidate",
        "acceptance_gates_sha256": "0" * 64,
        "paired_bootstrap_replicates": 1000,
        "target_delta_95_upper_below_zero": True,
        "all_guards_pass": True,
        "c2st_increase_at_most_0_01": True,
        "sampling_time_guard_pass": True,
        "decision": "PROMOTE",
    }}), encoding="utf-8")
    assert controller.decision(
        "S4-activity-ar", report, candidate_kind="supervised"
    ) is False


def test_critic_candidate_rejects_affirmative_supervised_gate(tmp_path: Path) -> None:
    controller = _controller(tmp_path)
    report = tmp_path / "report.json"
    report.write_text(json.dumps({"promotion_gate": {
        "schema_version": 1,
        "paired_bootstrap_replicates": 1000,
        "target_delta_95_upper_below_zero": True,
        "all_guards_pass": True,
        "c2st_increase_at_most_0_01": True,
        "sampling_time_guard_pass": True,
        "decision": "PROMOTE",
    }}), encoding="utf-8")
    assert controller.decision("D2-direct-r10", report, candidate_kind="critic-D2") is False
    decision = json.loads((controller.decisions / "D2-direct-r10.json").read_text(
        encoding="utf-8"
    ))
    assert decision["gate_family"] == "critic_candidate"
    assert decision["acceptance_gates_status"] == "proposed_validation_selection_rules"
    assert decision["decision"] == "NOT_PROMOTED_UNRESOLVED"


def test_critic_candidate_cannot_promote_from_proposed_gate_source(tmp_path: Path) -> None:
    controller = _controller(tmp_path)
    fields = set(controller.acceptance_gates["critic_candidate"])
    report = tmp_path / "report.json"
    report.write_text(json.dumps({"promotion_gate": {
        "schema_version": 1,
        "gate_family": "critic_candidate",
        "acceptance_gates_sha256": module.sha256_file(controller.acceptance_gates_path),
        "critic_candidate_checks": {field: True for field in fields},
        "decision": "PROMOTE",
    }}), encoding="utf-8")
    assert controller.decision("D1-direct-r05", report, candidate_kind="critic-D1") is False


def test_s4_unresolved_gate_skips_s5s6s7_but_v3sup_and_c0_still_attempt(
    tmp_path: Path,
) -> None:
    """An unpromoted S4 is ineligible as S5's parent, but V3-SUP/C0 declare a
    different parent (experiment_matrix.csv: `retained_supervised` /
    `V3-SUP`, not `selected_S4`) and must not be skipped along with it."""
    controller = _controller(tmp_path)
    report = tmp_path / "s4.json"
    report.write_text(json.dumps({"split": "validation", "test_events_used": 0}), encoding="utf-8")
    span_report = tmp_path / "span.json"
    span_report.write_text(json.dumps({"split": "validation", "test_events_used": 0}), encoding="utf-8")
    prepared = []
    trained = []
    controller.verify_snapshot = lambda: None
    controller.wait_for_s4 = lambda: {"battery": "s4.json"}
    controller.verify_s4_handoff = lambda state: json.loads(
        report.read_text(encoding="utf-8")
    )
    controller.prepare_screening = lambda row, tag: (
        prepared.append((row, tag)) or (tmp_path / "span.yaml", tmp_path / "init.pt")
    )
    controller.train_row = lambda row, tag, frozen: (
        trained.append((row, tag, frozen)) or (tmp_path / "span-run", span_report)
    )
    role = tmp_path / "role-partition.json"
    controller.build_role_partition = lambda: role
    partition_calls = []

    def prepare_partition(row, tag, parent_config, parent_checkpoint, role_path, **kwargs):
        partition_calls.append((row, tag))
        frozen = tmp_path / f"frozen_{tag}.yaml"
        frozen.write_text("frozen: true\n", encoding="utf-8")
        return frozen

    controller.prepare_partition_row = prepare_partition
    controller.run()

    # The matched ablation always runs, and is correctly not the primary
    # promotion candidate on a minimal report.
    assert prepared[0] == ("S4-activity-span", "v3-s4-activity-span")
    assert trained[0][:2] == ("S4-activity-span", "v3-s4-activity-span")
    disposition = json.loads(
        (controller.decisions / "S4-activity-span.json").read_text(encoding="utf-8")
    )
    assert disposition["decision"] == "REPORTED_NOT_PRIMARY_PROMOTION_CANDIDATE"

    # S5/S6/S7 declare selected_S4 as their parent and must not run.
    prepared_rows = [row for row, _ in prepared]
    assert "S5-count-ar" not in prepared_rows
    for row_id, _ in module.S6_ROWS:
        assert row_id not in prepared_rows
    assert module.S7_ROW[0] not in prepared_rows
    events = controller.events_path.read_text(encoding="utf-8")
    assert "DEPENDENT_SUPERVISED_CHAIN_SKIPPED" in events
    assert "STABLE_BLOCKER" in events

    # V3-SUP and C0 declare a different parent and must still be attempted.
    assert ("V3-SUP", "v3-sup-composite-init") in prepared
    assert ("V3-SUP", "v3-sup") in partition_calls
    assert ("C0", "v3-c0") in partition_calls
    assert ("V3-SUP", "v3-sup") in [(r, t) for r, t, _ in trained]
    assert ("C0", "v3-c0") in [(r, t) for r, t, _ in trained]

    # C0's own minimal report cannot promote critics -- that is a genuine,
    # separate blocker, not the S4 gate reappearing.
    state = json.loads(controller.state_path.read_text(encoding="utf-8"))
    assert state["status"] == "BLOCKED_C0_NOT_PROMOTED"
    assert state["test_events_used"] == 0


def _mock_supervised_rows(controller, tmp_path: Path, decisions: dict[str, bool]):
    prepared = []
    trained = []

    def prepare(row, tag):
        prepared.append((row, tag, controller.parent_row))
        return tmp_path / f"{tag}.yaml", tmp_path / f"{tag}-init.pt"

    def train(row, tag, frozen):
        trained.append((row, tag, frozen))
        report = tmp_path / f"{tag}-battery.json"
        report.write_text("{}", encoding="utf-8")
        return tmp_path / f"{tag}-run", report

    controller.prepare_screening = prepare
    controller.train_row = train
    controller.decision = lambda row, report, candidate_kind: decisions.get(row, False)
    return prepared, trained


def test_s5_failure_skips_s6_and_s7_but_keeps_v3sup_eligible(tmp_path: Path) -> None:
    controller = _controller(tmp_path)
    controller.promoted = ["S4-activity-ar"]
    controller.parent_row = "S4-activity-ar"
    prepared, trained = _mock_supervised_rows(controller, tmp_path, {})
    result = controller.run_dependent_supervised_chain()
    assert [row for row, _, _ in prepared] == ["S5-count-ar"]
    assert [row for row, _, _ in trained] == ["S5-count-ar"]
    assert result == {"s5_promoted": False, "selected_s6": None, "s7_run": False}
    assert controller.parent_row == "S4-activity-ar"
    assert "DEPENDENT_ROWS_SKIPPED" in controller.events_path.read_text(encoding="utf-8")


def test_s6_grid_uses_one_s5_parent_and_ambiguous_result_skips_s7(tmp_path: Path) -> None:
    controller = _controller(tmp_path)
    controller.promoted = ["S4-activity-ar"]
    controller.parent_row = "S4-activity-ar"
    decisions = {
        "S5-count-ar": True,
        "S6-temp-025": True,
        "S6-temp-050": True,
    }
    prepared, _ = _mock_supervised_rows(controller, tmp_path, decisions)
    result = controller.run_dependent_supervised_chain()
    rows = [row for row, _, _ in prepared]
    assert rows == ["S5-count-ar", *[row for row, _ in module.S6_ROWS]]
    assert all(parent == "S5-count-ar" for _, _, parent in prepared[1:])
    assert result == {"s5_promoted": True, "selected_s6": None, "s7_run": False}
    assert controller.promoted == ["S4-activity-ar", "S5-count-ar"]
    assert controller.parent_row == "S5-count-ar"
    assert "S6_SELECTION_UNRESOLVED_RETAIN_S5" in controller.events_path.read_text(
        encoding="utf-8"
    )


def test_exactly_one_s6_selection_is_the_only_parent_allowed_for_s7(tmp_path: Path) -> None:
    controller = _controller(tmp_path)
    controller.promoted = ["S4-activity-ar"]
    controller.parent_row = "S4-activity-ar"
    decisions = {"S5-count-ar": True, "S6-temp-050": True}
    prepared, _ = _mock_supervised_rows(controller, tmp_path, decisions)
    result = controller.run_dependent_supervised_chain()
    assert prepared[-1] == (
        "S7-profile-ot-cfm", "v3-s7-profile-ot-cfm", "S6-temp-050"
    )
    assert result == {
        "s5_promoted": True, "selected_s6": "S6-temp-050", "s7_run": True,
    }
    assert controller.promoted == [
        "S4-activity-ar", "S5-count-ar", "S6-temp-050",
    ]
    assert controller.parent_row == "S6-temp-050"
    events = controller.events_path.read_text(encoding="utf-8")
    assert "S6_SELECTED" in events
    assert "S7_NOT_PROMOTED_PARENT_RETAINED" in events


def test_c0_without_affirmative_gate_blocks_all_critic_work(tmp_path: Path) -> None:
    controller = _controller(tmp_path)
    report = tmp_path / "c0.json"
    report.write_text("{}", encoding="utf-8")
    controller.decision = lambda row, path, candidate_kind: False
    assert controller.c0_allows_critics(report) is False
    state = json.loads(controller.state_path.read_text(encoding="utf-8"))
    assert state["status"] == "BLOCKED_C0_NOT_PROMOTED"
    assert state["test_events_used"] == 0
    assert "C0_NOT_PROMOTED" in controller.events_path.read_text(encoding="utf-8")


def test_d2_replication_runs_when_d1_has_no_selected_arm(tmp_path: Path) -> None:
    controller = _controller(tmp_path)
    d2_config = tmp_path / "d2.yaml"
    d2_config.write_text("stage: D2\n", encoding="utf-8")
    d2_run = tmp_path / "d2-screen-run"
    role = tmp_path / "roles.json"
    c0_config = tmp_path / "c0.yaml"
    c0_run = tmp_path / "c0-run"
    prepared = []
    trained = []

    def prepare(row, tag, parent_config, parent_checkpoint, role_path, **kwargs):
        prepared.append((row, tag, kwargs["stage"], kwargs["seed"]))
        frozen = tmp_path / f"{tag}.yaml"
        frozen.write_text("frozen: true\n", encoding="utf-8")
        return frozen

    def train(row, tag, frozen):
        trained.append((row, tag))
        report = tmp_path / f"{tag}.json"
        report.write_text("{}", encoding="utf-8")
        return tmp_path / f"{tag}-run", report

    controller.prepare_partition_row = prepare
    controller.train_row = train
    controller.decision = lambda row, path, candidate_kind: False
    reports = controller.run_independent_critic_replications(
        {"D1": [], "D2": [("D2-direct-r10", d2_config, d2_run)]},
        c0_config, c0_run, role,
    )
    assert reports["D1"] == []
    assert [seed for _, _, stage, seed in prepared if stage == "D2"] == [
        20260723, 20260724, 20260725,
    ]
    assert len(trained) == 3
    assert len(reports["D2"]) == 3
    assert "CRITIC_REPLICATION_SKIPPED" in controller.events_path.read_text(
        encoding="utf-8"
    )


def _replication_fixture(controller, tmp_path: Path, stage: str):
    selected_row = f"{stage}-direct-r10"
    selected_config = tmp_path / f"{stage.lower()}-selected.yaml"
    selected_config.write_text(f"stage: {stage}\n", encoding="utf-8")
    selected_run = tmp_path / f"{stage.lower()}-screen-run"
    reports = []
    for seed in module.REPLICATION_SEEDS:
        report = tmp_path / f"{stage.lower()}-seed{seed}.json"
        report.write_text(json.dumps({"seed": seed}), encoding="utf-8")
        reports.append({
            "seed": seed,
            "report": str(report.relative_to(tmp_path)).replace("\\", "/"),
            "report_sha256": module.sha256_file(report),
            "single_run_gate": True,
        })
    return (selected_row, selected_config, selected_run), reports


def _write_replication_aggregate(
    controller,
    stage: str,
    selected_row: str,
    selected_config: Path,
    reports: list[dict],
) -> Path:
    rule = controller.acceptance_gates["replication_aggregate"]
    output = (
        controller.root
        / f"_v3/replication_aggregates/{stage.lower()}-selected-3seed.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({
        "schema_version": 1,
        "kind": rule["artifact_kind"],
        "stage": stage,
        "row_id": f"{stage}-selected-3seed",
        "selected_row": selected_row,
        "selected_config_sha256": module.sha256_file(selected_config),
        "acceptance_gates_sha256": module.sha256_file(
            controller.acceptance_gates_path
        ),
        "aggregation_rule_id": rule["rule_id"],
        "required_seeds": list(module.REPLICATION_SEEDS),
        "seed_reports": [
            {key: row[key] for key in ("seed", "report", "report_sha256")}
            for row in reports
        ],
        "split": "validation",
        "test_events_used": 0,
        "checks": {field: True for field in rule["required_checks"]},
        "decision": "PROMOTE",
    }), encoding="utf-8")
    return output


def test_replication_aggregate_cannot_promote_from_unfrozen_source(
    tmp_path: Path,
) -> None:
    controller = _controller(tmp_path)
    candidate, reports = _replication_fixture(controller, tmp_path, "D2")
    _write_replication_aggregate(
        controller, "D2", candidate[0], candidate[1], reports
    )
    aggregate, blocker = controller.verify_replication_aggregate(
        "D2", reports, candidate[0], candidate[1]
    )
    assert aggregate is None
    assert blocker == "D2_REPLICATION_AGGREGATION_RULE_NOT_OWNER_FROZEN"


def test_replication_aggregate_binds_seed_reports_selected_arm_and_rule(
    tmp_path: Path,
) -> None:
    controller = _controller(
        tmp_path,
        gate_status="frozen_validation_selection_rules",
        aggregate_status="frozen_cross_seed_selection_rule",
    )
    candidate, reports = _replication_fixture(controller, tmp_path, "D1")
    aggregate_path = _write_replication_aggregate(
        controller, "D1", candidate[0], candidate[1], reports
    )
    aggregate, blocker = controller.verify_replication_aggregate(
        "D1", reports, candidate[0], candidate[1]
    )
    assert blocker is None
    assert aggregate is not None and aggregate["decision"] == "PROMOTE"
    payload = json.loads(aggregate_path.read_text(encoding="utf-8"))
    payload["seed_reports"][0]["report_sha256"] = "0" * 64
    aggregate_path.write_text(json.dumps(payload), encoding="utf-8")
    aggregate, blocker = controller.verify_replication_aggregate(
        "D1", reports, candidate[0], candidate[1]
    )
    assert aggregate is None
    assert blocker == "D1_REPLICATION_AGGREGATE_NOT_AFFIRMATIVE"


def test_d12_runs_only_after_both_exact_frozen_replication_aggregates(
    tmp_path: Path,
) -> None:
    controller = _controller(
        tmp_path,
        gate_status="frozen_validation_selection_rules",
        aggregate_status="frozen_cross_seed_selection_rule",
    )
    candidates = {}
    reports = {}
    for stage in ("D1", "D2"):
        candidate, stage_reports = _replication_fixture(controller, tmp_path, stage)
        candidates[stage] = [candidate]
        reports[stage] = stage_reports
        _write_replication_aggregate(
            controller, stage, candidate[0], candidate[1], stage_reports
        )
    calls = []
    d12_config = tmp_path / "frozen-d12.yaml"
    d12_config.write_text("stage: D12\n", encoding="utf-8")
    d12_report = tmp_path / "d12-report.json"
    d12_report.write_text("{}", encoding="utf-8")

    def prepare(row, tag, parent_config, parent_checkpoint, role_path, **kwargs):
        calls.append(("prepare", row, tag, kwargs))
        return d12_config

    controller.prepare_partition_row = prepare
    controller.train_row = lambda row, tag, frozen: (
        calls.append(("train", row, tag, frozen))
        or (tmp_path / "d12-run", d12_report)
    )
    controller.decision = lambda row, path, candidate_kind: True
    result, blockers = controller.run_d12_if_eligible(
        candidates,
        reports,
        tmp_path / "c0.yaml",
        tmp_path / "c0-run",
        tmp_path / "roles.json",
    )
    assert blockers == []
    assert result is not None and result["promoted"] is True
    assert calls[0][0:3] == ("prepare", "D12", "d12")
    assert calls[0][3]["stage"] == "D12"
    assert calls[0][3]["selected_d1_config"] == candidates["D1"][0][1]
    assert calls[0][3]["selected_d2_config"] == candidates["D2"][0][1]
    assert calls[1][0:3] == ("train", "D12", "d12")
    assert "D12_COMPLETE" in controller.events_path.read_text(encoding="utf-8")


def test_v3sup_and_c0_are_both_derived_on_exact_role_partition(tmp_path: Path) -> None:
    controller = _controller(tmp_path)
    composite_config = tmp_path / "frozen_v3-sup-composite-init.yaml"
    composite_checkpoint = tmp_path / "v3-sup-composite-init.pt"
    role = tmp_path / "role-partition.json"
    calls = []

    def prepare_screening(row, tag):
        calls.append(("composite", row, tag))
        return composite_config, composite_checkpoint

    def prepare_partition(row, tag, parent_config, parent_checkpoint, role_path, **kwargs):
        calls.append((
            "partition", row, tag, parent_config, parent_checkpoint, role_path,
        ))
        frozen = tmp_path / f"frozen_{tag}.yaml"
        frozen.write_text("frozen: true\n", encoding="utf-8")
        return frozen

    def train(row, tag, frozen):
        calls.append(("train", row, tag, frozen))
        run = tmp_path / f"{tag}-run"
        report = tmp_path / f"{tag}-report.json"
        report.write_text("{}", encoding="utf-8")
        return run, report

    controller.prepare_screening = prepare_screening
    controller.build_role_partition = lambda: role
    controller.prepare_partition_row = prepare_partition
    controller.train_row = train
    controller.c0_allows_critics = lambda report: True
    result = controller.run_partition_controls()
    assert calls[0] == ("composite", "V3-SUP", "v3-sup-composite-init")
    v3sup_partition = calls[1]
    assert v3sup_partition == (
        "partition", "V3-SUP", "v3-sup", composite_config,
        composite_checkpoint, role,
    )
    assert calls[2][0:3] == ("train", "V3-SUP", "v3-sup")
    c0_partition = calls[3]
    assert c0_partition[0:3] == ("partition", "C0", "v3-c0")
    assert c0_partition[3] == tmp_path / "frozen_v3-sup.yaml"
    assert c0_partition[4] == tmp_path / "v3-sup-run/checkpoints/best.pt"
    assert calls[4][0:3] == ("train", "C0", "v3-c0")
    assert result == (
        tmp_path / "frozen_v3-c0.yaml", tmp_path / "v3-c0-run", role,
    )


def test_controller_state_namespace_cannot_escape_project_root(tmp_path: Path) -> None:
    snapshot = tmp_path / "snapshot"
    (snapshot / "configs").mkdir(parents=True)
    (snapshot / "configs/v3_validation_battery_contract.json").write_text(
        json.dumps({"split": "validation", "test_events_used": 0}), encoding="utf-8"
    )
    outside = tmp_path.parent / "outside-controller-state"
    try:
        module.Controller(tmp_path, snapshot, 1, outside)
    except ValueError as error:
        assert "inside the project root" in str(error)
    else:
        raise AssertionError("outside controller state directory was accepted")


def test_failed_postlaunch_writer_proof_terminates_owned_processes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    controller = _controller(tmp_path)
    frozen = tmp_path / "frozen.yaml"
    frozen.write_text("frozen: true\n", encoding="utf-8")
    controller.prove_no_writer = lambda: None
    controller.prove_one_writer = lambda: (_ for _ in ()).throw(
        RuntimeError("writer proof failed")
    )
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    processes = []

    class FakeProcess:
        def __init__(self, argv, **kwargs):
            self.argv = argv
            self.returncode = None
            processes.append(self)

        def poll(self):
            return self.returncode

        def terminate(self):
            self.returncode = -15

        def kill(self):
            self.returncode = -9

        def wait(self, timeout=None):
            return self.returncode

    monkeypatch.setattr(module.subprocess, "Popen", FakeProcess)
    with pytest.raises(RuntimeError, match="writer proof failed"):
        controller.train_row("S4-activity-span", "v3-s4-activity-span", frozen)
    assert len(processes) == 2
    assert all(process.returncode == -15 for process in processes)
    events = controller.events_path.read_text(encoding="utf-8")
    assert "TRAIN_ABORTED_FAIL_CLOSED" in events
