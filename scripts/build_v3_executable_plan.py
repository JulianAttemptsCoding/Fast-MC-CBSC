"""Re-cost the v3 experiment matrix from measured preflight numbers.

``specs/improvement_v3/experiment_matrix.csv`` is the scientific hypothesis and
decision registry.  It is **never** edited here.  This builder emits a separate
versioned *executable* plan that adds eligibility, authorization and measured
cost, so a schedule can be discussed without touching the science.

Nothing in the emitted plan is launched by this script.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

SOURCE_MATRIX = Path("specs/improvement_v3/experiment_matrix.csv")

GENERATOR_PARTITION = 551234
FULL_TRAIN = 612482
PILOT_BANK = 26624
BASELINE_EVENTS_PER_SECOND = 34.15  # measured v2.2 rate on this card

ELIGIBILITY_VALUES = {
    "eligible",
    "conditional_predecessor",
    "conditional_metric_trigger",
    "not_promoted",
    "resource_blocked",
    "deferred_budget",
    "completed_existing_evidence",
}

COLUMNS = [
    "order", "id", "parent", "implementation_status", "eligibility", "trigger",
    "required_control", "bank", "seed_count", "epoch_or_stop_rule",
    "measured_seconds_per_update", "projected_gpu_hours_low",
    "projected_gpu_hours_central", "projected_gpu_hours_high",
    "peak_memory_gib", "authorization_status", "evidence_sha256", "next_command",
]


def bank_events(name: str) -> int:
    return {
        "pilot": PILOT_BANK,
        "critic_generator_partition": GENERATOR_PARTITION,
        "full_train": FULL_TRAIN,
    }.get(name, PILOT_BANK)


def load_preflight(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    probes = {p["probe"]: p for p in payload["probes"] if p.get("status") == "ok"}
    batch = int(payload["critic_batch"])
    supervised = batch / BASELINE_EVENTS_PER_SECOND
    d1 = (
        probes["d1_critic_update"]["seconds_per_update_median"]
        + probes["d1_generator_through_frozen_critic"]["seconds_per_update_median"]
    )
    d2 = (
        probes["d2_critic_update"]["seconds_per_update_median"]
        + probes["d2_generator_through_frozen_critic"]["seconds_per_update_median"]
    )
    return {
        "batch": batch,
        "supervised_seconds": supervised,
        "d1_seconds": d1,
        "d2_seconds": d2,
        "d1_peak_gib": max(
            probes["d1_critic_update"]["peak_allocated_gib"],
            probes["d1_generator_through_frozen_critic"]["peak_allocated_gib"],
        ),
        "d2_peak_gib": max(
            probes["d2_critic_update"]["peak_allocated_gib"],
            probes["d2_generator_through_frozen_critic"]["peak_allocated_gib"],
        ),
        "supervised_peak_gib": probes["v3_supervised_generator"]["peak_allocated_gib"],
        "device_total_gib": probes["d1_critic_update"].get("device_total_gib"),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def kind_of(row: dict[str, str]) -> str:
    change = row["change"]
    if row["id"].startswith("D1") or "share_critic" in change:
        return "d1"
    if row["id"].startswith("D2") or "profile_critic" in change:
        return "d2"
    if row["id"] == "D12":
        return "d12"
    if row["id"].startswith("D3"):
        return "d3"
    return "supervised"


def classify(row: dict[str, str]) -> tuple[str, str, str, str]:
    """Return ``(eligibility, trigger, required_control, authorization)``."""
    rid = row["id"]
    if rid == "B0":
        return (
            "completed_existing_evidence",
            "section 3 terminal-evidence gate",
            "none",
            "no run required; dicos-f-02 epoch 90 pending only Stage B metrics",
        )
    if rid.startswith(("S1", "S2", "S3", "S4", "S5", "S6", "S7")):
        return (
            "deferred_budget",
            "software implemented; awaiting a GPU budget",
            "B0",
            "not authorized by the current prompt",
        )
    if rid in {"V3-SUP", "C0"}:
        return (
            "deferred_budget",
            "required control for every critic run",
            "none",
            "not authorized by the current prompt",
        )
    if rid.startswith("D1") or rid.startswith("D2"):
        if "3seed" in rid:
            return (
                "conditional_predecessor",
                "single-seed arm must meet its predeclared criteria first",
                "C0",
                "not authorized by the current prompt",
            )
        return (
            "conditional_predecessor",
            "requires a promoted C0 and a resource pass",
            "C0",
            "not authorized by the current prompt",
        )
    if rid == "D12":
        return (
            "conditional_predecessor",
            "independent three-seed replication of D1 and D2",
            "C0",
            "not authorized by the current prompt",
        )
    if rid.startswith("D3"):
        return (
            "conditional_metric_trigger",
            "support-topology distance above the truth-half floor and a leading "
            "C2ST feature family, plus tiny-geometry estimator QA",
            "C0",
            "not authorized by the current prompt",
        )
    return (
        "conditional_predecessor",
        "frozen validation selection and three seeds",
        "C0",
        "not authorized; the test split is not opened by the current prompt",
    )


def build(preflight: Path, output: Path, report: Path) -> dict[str, Any]:
    measured = load_preflight(preflight)
    rows_out: list[dict[str, Any]] = []
    with SOURCE_MATRIX.open(newline="", encoding="utf-8") as handle:
        source_rows = [r for r in csv.DictReader(handle) if r.get("id")]

    for row in source_rows:
        kind = kind_of(row)
        events = bank_events(row["train_bank"])
        seeds = 3 if "|" in row["seeds"] else 1
        per_batch = measured["supervised_seconds"]
        peak = measured["supervised_peak_gib"]
        if kind == "d1":
            per_batch += measured["d1_seconds"]
            peak = measured["d1_peak_gib"]
        elif kind == "d2":
            per_batch += measured["d2_seconds"]
            peak = measured["d2_peak_gib"]
        elif kind in {"d12", "d3"}:
            per_batch += measured["d1_seconds"] + measured["d2_seconds"]
            peak = measured["d1_peak_gib"]
        rate = measured["batch"] / per_batch
        epochs = 24
        central = events / rate * epochs / 3600 * seeds
        eligibility, trigger, control, authorization = classify(row)
        rows_out.append(
            {
                "order": row["order"],
                "id": row["id"],
                "parent": row["parent"],
                "implementation_status": "implemented",
                "eligibility": eligibility,
                "trigger": trigger,
                "required_control": control,
                "bank": row["train_bank"],
                "seed_count": seeds,
                "epoch_or_stop_rule": f"{epochs} epochs or the frozen stop rule",
                "measured_seconds_per_update": round(per_batch, 5),
                # +/-25% covers dataloader variation, checkpoint and validation
                # cost, and the fact that the probes truth-force the stages the
                # critic does not train.
                "projected_gpu_hours_low": round(central * 0.75, 1),
                "projected_gpu_hours_central": round(central, 1),
                "projected_gpu_hours_high": round(central * 1.25, 1),
                "peak_memory_gib": round(peak, 2),
                "authorization_status": authorization,
                "evidence_sha256": measured["sha256"][:16],
                "next_command": "awaiting owner GPU budget",
            }
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows_out)

    bad = [r["eligibility"] for r in rows_out if r["eligibility"] not in ELIGIBILITY_VALUES]
    if bad:
        raise SystemExit(f"invalid eligibility values: {sorted(set(bad))}")

    counts: dict[str, int] = {}
    for r in rows_out:
        counts[r["eligibility"]] = counts.get(r["eligibility"], 0) + 1
    payload = {
        "schema_version": 1,
        "kind": "cbsc-zdc-v3-executable-plan",
        "source_matrix": str(SOURCE_MATRIX).replace("\\", "/"),
        "source_matrix_sha256": hashlib.sha256(SOURCE_MATRIX.read_bytes()).hexdigest(),
        "source_matrix_unmodified": True,
        "plan_path": str(output).replace("\\", "/"),
        "plan_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "preflight_evidence_sha256": measured["sha256"],
        "device_total_gib": measured["device_total_gib"],
        "measured": {
            "critic_batch": measured["batch"],
            "supervised_seconds_per_batch": round(measured["supervised_seconds"], 5),
            "d1_added_seconds_per_batch": round(measured["d1_seconds"], 5),
            "d2_added_seconds_per_batch": round(measured["d2_seconds"], 5),
            "d1_peak_gib": round(measured["d1_peak_gib"], 2),
            "d2_peak_gib": round(measured["d2_peak_gib"], 2),
        },
        "rows": len(rows_out),
        "eligibility_counts": counts,
        "total_projected_gpu_hours_central": round(
            sum(r["projected_gpu_hours_central"] for r in rows_out), 1
        ),
        "authorization": "no row is launched by this builder",
    }
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight", type=Path, default=Path("audit/v3_resource_preflight_20260814.json"))
    parser.add_argument("--output", type=Path, default=Path("specs/improvement_v3/executable_plan_20260814.csv"))
    parser.add_argument("--report", type=Path, default=Path("audit/v3_executable_plan_20260814.json"))
    args = parser.parse_args()
    payload = build(args.preflight, args.output, args.report)
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
