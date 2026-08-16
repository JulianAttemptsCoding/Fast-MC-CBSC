import copy
import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "migrate_v3_battery_data_usage",
    ROOT / "scripts" / "migrate_v3_battery_data_usage.py",
)
MIGRATE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MIGRATE)


def source_report():
    return {
        "schema_version": 2,
        "kind": "cbsc-zdc-v3-validation-battery",
        "split": "validation",
        "pairs": 10_000,
        "evaluator_corpus_examples": 20_000,
        "train_events_used": 0,
        "test_events_used": 0,
        "paired_response": {"response_delta_over_kinetic_rmse": 0.04},
        "memorization": {
            "train_events": 2_000,
            "train_reference_events": 2_000,
            "below_truth_floor": False,
        },
    }


def test_migration_corrects_only_schema_and_data_usage_metadata():
    source = source_report()
    original = copy.deepcopy(source)
    migrated = MIGRATE.migrate(source, "a" * 64)
    assert source == original
    assert migrated["schema_version"] == 3
    assert migrated["validation_events_used"] == 10_000
    assert migrated["train_events_used"] == 2_000
    assert migrated["test_events_used"] == 0
    assert migrated["data_usage"]["training_reference_events"] == 2_000
    assert migrated["schema_migration"]["source_report_sha256"] == "a" * 64
    for key, value in original.items():
        if key not in {"schema_version", "train_events_used"}:
            assert migrated[key] == value


def test_migration_rejects_ambiguous_or_non_validation_sources():
    report = source_report()
    report["memorization"]["train_events"] = 1_999
    with pytest.raises(ValueError, match="counts disagree"):
        MIGRATE.migrate(report, "a" * 64)
    report = source_report()
    report["test_events_used"] = 1
    with pytest.raises(ValueError, match="validation-only"):
        MIGRATE.migrate(report, "a" * 64)
