"""Migrate one schema-v2 battery report to explicit schema-v3 data accounting.

This changes provenance metadata only. Metric payloads remain byte-for-byte
equivalent after removing the schema/accounting fields added by this migration.
The source report must be preserved in quarantine and named by its SHA-256.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def migrate(report: dict, source_sha256: str) -> dict:
    if report.get("schema_version") != 2:
        raise ValueError("migration requires report schema_version 2")
    if report.get("kind") != "cbsc-zdc-v3-validation-battery":
        raise ValueError("unexpected battery kind")
    pairs = int(report.get("pairs", -1))
    if pairs <= 0 or report.get("evaluator_corpus_examples") != 2 * pairs:
        raise ValueError("invalid validation-pair accounting")
    if report.get("split") != "validation" or report.get("test_events_used") != 0:
        raise ValueError("migration requires validation-only evidence")
    if report.get("train_events_used") != 0:
        raise ValueError("schema-v2 source no longer has the known accounting defect")
    train_reference = report.get("memorization", {}).get("train_reference_events")
    train_events = report.get("memorization", {}).get("train_events")
    if not isinstance(train_reference, int) or train_reference <= 0:
        raise ValueError("missing positive memorization train-reference count")
    if train_events != train_reference:
        raise ValueError("memorization train counts disagree")

    migrated = copy.deepcopy(report)
    migrated["schema_version"] = 3
    migrated["validation_events_used"] = pairs
    migrated["train_events_used"] = train_reference
    migrated["data_usage"] = {
        "validation_truth_events": pairs,
        "generated_events": pairs,
        "training_reference_events": train_reference,
        "training_reference_role": "memorization nearest-neighbour reference only",
        "test_events": 0,
    }
    migrated["schema_migration"] = {
        "source_schema_version": 2,
        "source_report_sha256": source_sha256,
        "reason": (
            "correct top-level training-reference accounting; metric values unchanged"
        ),
    }
    return migrated


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-input-sha256", required=True)
    args = parser.parse_args(argv)
    actual = sha256_file(args.input)
    if actual != args.expected_input_sha256:
        raise SystemExit("input SHA-256 does not match the declared quarantined report")
    if args.output.exists():
        raise SystemExit("refusing to overwrite migration output")
    report = json.loads(args.input.read_text(encoding="utf-8"))
    migrated = migrate(report, actual)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(migrated, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )
    print(json.dumps({
        "input_sha256": actual,
        "output": str(args.output),
        "output_sha256": sha256_file(args.output),
        "source_schema_version": 2,
        "output_schema_version": 3,
        "metric_values_changed": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
