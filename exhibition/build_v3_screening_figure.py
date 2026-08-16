"""Figures and summary for the v3 architecture screening rows.

A screening row asks one question: does exactly one architectural change lower
the validation loss relative to its declared comparator? Historical v2 response
losses were logged in transformed log-energy space, while the spline loss is a
density in GeV. This builder preserves the raw values but applies the audited,
target-only v2 Jacobian offset before plotting or comparing any row.

These rows are deliberately absent from
``exhibition/current/continuation/``.  That view is the four v2.2 learning-rate
families on one continuous axis; a v3 row changes the architecture and is
*initialized from* rather than *resumed from* its parent, so drawing it there
would imply a continuation that did not happen and would let it compete for a
v2.2 family's accepted best.

Output goes to ``exhibition/current/v3_screening/``.  Nothing here selects a
checkpoint, publishes, or reads the test split.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = HERE / "data"
REGISTRY = DATA / "v3_screening_rows.json"
HISTORY = DATA / "v3_screening_history.csv"
OUT = HERE / "current" / "v3_screening"

NAVY = "#0f2a43"
MUTED = "#627d98"
PARENT = "#d2691e"
CONTROL = "#7a5195"
GRID = "#d9e2ec"
#: One colour per screening row, assigned by declaration order so a row keeps
#: its colour as later rows are added.
ROW_COLORS = ["#0f7fbf", "#00a06d", "#c1121f", "#b5179e", "#4f772d", "#bc6c25"]

#: A row whose best validation loss is worse than its parent by less than this
#: is reported as unresolved rather than worse. It is the run-to-run reference
#: measured from dicos-f-03 against dicos-f-04 on the epochs where their
#: learning rates agree within 2 percent (mean absolute 0.000654, max
#: 0.001259); the larger figure is used so the band is not optimistic.
#: It is a reproducibility reference, NOT a standard error, and it does not
#: license a significance claim in either direction.
RUN_TO_RUN_REFERENCE = 0.001259


def loss_measure_offset(record: dict) -> float:
    """Target-only offset from a record's reported loss to the common measure."""
    measure = record.get("loss_measure") or {}
    if "total_validation_loss_offset" not in measure:
        raise ValueError("every compared loss must declare its loss measure offset")
    value = float(measure["total_validation_loss_offset"])
    if not (-100.0 < value < 100.0):
        raise ValueError("loss measure offset is nonfinite or implausible")
    return value


def common_loss(value: float, record: dict) -> float:
    return float(value) + loss_measure_offset(record)


def style() -> None:
    plt.rcParams.update({
        "figure.dpi": 160,
        "savefig.dpi": 160,
        "font.size": 11,
        "axes.edgecolor": NAVY,
        "axes.labelcolor": NAVY,
        "text.color": NAVY,
        "xtick.color": NAVY,
        "ytick.color": NAVY,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "svg.hashsalt": "cbsc-zdc-v3-screening",
    })


def load_registry() -> dict:
    payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("v3 screening registry schema must be 1")
    return payload


def load_history() -> dict[str, list[dict]]:
    if not HISTORY.is_file():
        return {}
    series: dict[str, list[dict]] = {}
    with HISTORY.open(newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            series.setdefault(raw["variant"], []).append({
                "epoch": int(raw["epoch"]),
                "train_loss": float(raw["train_loss"]),
                "validation_loss": float(raw["validation_loss"]),
                "learning_rate": float(raw["learning_rate"]),
                "run_tag": raw["run_tag"],
            })
    for rows in series.values():
        rows.sort(key=lambda r: r["epoch"])
    return series


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def load_battery_report(run_tag: str) -> dict | None:
    """Load one accepted fixed-bank diagnostic report for a screening row."""
    root = DATA / "v3_battery"
    candidates = sorted(root.glob(f"{run_tag}_epoch*.json"))
    candidates = [p for p in candidates if not p.name.endswith(".provenance.json")]
    if not candidates:
        return None
    if len(candidates) != 1:
        raise ValueError(f"{run_tag} has multiple active battery reports")
    path = candidates[0]
    payload = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "schema_version": 3,
        "kind": "cbsc-zdc-v3-validation-battery",
        "split": "validation",
        "pairs": 10_000,
        "evaluator_corpus_examples": 20_000,
        "validation_events_used": 10_000,
        "train_events_used": 2_000,
        "test_events_used": 0,
        "scientific_status": "PHYSICS VALIDATION NOT ESTABLISHED",
    }
    for field, value in expected.items():
        if payload.get(field) != value:
            raise ValueError(f"{path.name}: expected {field}={value!r}")
    if payload.get("data_usage") != {
        "validation_truth_events": 10_000,
        "generated_events": 10_000,
        "training_reference_events": 2_000,
        "training_reference_role": "memorization nearest-neighbour reference only",
        "test_events": 0,
    }:
        raise ValueError(f"{path.name}: data-usage accounting mismatch")
    if payload.get("memorization", {}).get("train_reference_events") != 2_000:
        raise ValueError(f"{path.name}: memorization reference accounting mismatch")
    if payload.get("structural_invariants", {}).get("pass") is not True:
        raise ValueError(f"{path.name}: structural battery QA did not pass")
    if "reconstruction" in payload:
        raise ValueError(f"{path.name}: contains superseded truth-relative metric")
    paired = payload.get("paired_response", {})
    if paired.get("kind") != "paired_detector_response_residual":
        raise ValueError(f"{path.name}: paired-response contract is missing")
    if paired.get("normalization") != "incident_kinetic_energy_gev":
        raise ValueError(f"{path.name}: paired-response normalization is invalid")
    if paired.get("events_included") != int(payload["pairs"]):
        raise ValueError(f"{path.name}: paired-response event accounting mismatch")
    c2st = payload.get("c2st", {})
    if set(c2st) != {"high_level", "low_level", "profile_aware", "condition_only"}:
        raise ValueError(f"{path.name}: incomplete C2ST family set")
    means = {name: float(row["auroc_mean"]) for name, row in c2st.items()}
    if any(not math.isfinite(v) or not 0 <= v <= 1 for v in means.values()):
        raise ValueError(f"{path.name}: invalid C2ST AUROC")
    identity = payload.get("identity", {})
    for field in ("checkpoint_sha256", "frozen_config_sha256"):
        value = identity.get(field)
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
            raise ValueError(f"{path.name}: missing or invalid {field}")
    embedded_epoch = identity.get("checkpoint_embedded_epoch")
    if embedded_epoch != identity.get("epoch"):
        raise ValueError(f"{path.name}: embedded and reported epochs disagree")
    name_match = re.fullmatch(re.escape(run_tag) + r"_epoch([0-9]+)\.json", path.name)
    if not name_match or int(name_match.group(1)) != int(identity["epoch"]):
        raise ValueError(f"{path.name}: filename and reported epochs disagree")
    sidecar_path = path.with_suffix(".provenance.json")
    if not sidecar_path.is_file():
        raise ValueError(f"{path.name}: provenance sidecar is missing")
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    for field, value in {
        "kind": "cbsc-zdc-v3-battery-provenance-sidecar",
        "report": path.name,
        "report_sha256": sha256_file(path),
        "test_events_used": 0,
        "scientific_status": "PHYSICS VALIDATION NOT ESTABLISHED",
        "checkpoint_sha256": identity["checkpoint_sha256"],
        "checkpoint_embedded_epoch": identity["checkpoint_embedded_epoch"],
        "frozen_config_sha256": identity["frozen_config_sha256"],
    }.items():
        if sidecar.get(field) != value:
            raise ValueError(f"{sidecar_path.name}: expected {field}={value!r}")
    return {
        "report": path.relative_to(ROOT).as_posix(),
        "report_sha256": sha256_file(path),
        "epoch": int(payload["identity"]["epoch"]),
        "pairs": int(payload["pairs"]),
        "evaluator_corpus_examples": int(payload["evaluator_corpus_examples"]),
        "structural_pass": True,
        "c2st_auroc_mean": means,
        "evaluation_role": payload["identity"]["evaluation_role"],
        "selected_validation_loss": float(sidecar["selected_validation_loss"]),
        "test_events_used": 0,
        "scientific_status": payload["scientific_status"],
    }


def classify(delta: float) -> str:
    """Direction of a row against a reference, using the reproducibility band."""
    if delta < -RUN_TO_RUN_REFERENCE:
        return "better"
    if delta > RUN_TO_RUN_REFERENCE:
        return "worse"
    return "within_run_to_run_reference"


def summarize(registry: dict, series: dict[str, list[dict]]) -> dict:
    baseline = dict(registry["baseline"])
    baseline["raw_validation_loss"] = float(baseline["validation_loss"])
    baseline["common_measure_validation_loss"] = common_loss(
        baseline["validation_loss"], baseline
    )
    baseline["battery"] = load_battery_report(baseline["run_tag"])
    if baseline["battery"] is not None:
        if baseline["battery"]["epoch"] != int(baseline["epoch"]):
            raise ValueError("baseline battery did not evaluate the frozen B0 epoch")
        if not math.isclose(
            baseline["battery"]["selected_validation_loss"],
            float(baseline["validation_loss"]), rel_tol=0.0, abs_tol=1e-12,
        ):
            raise ValueError("baseline battery selection loss disagrees with B0")
    rows = []
    for index, row in enumerate(registry["rows"]):
        history = series.get(row["variant"], [])
        offset = loss_measure_offset(row)
        battery = load_battery_report(row["run_tag"])
        if battery is not None:
            if not history:
                raise ValueError(f"{row['row_id']} battery has no local history")
            best = min(history, key=lambda point: (point["validation_loss"], point["epoch"]))
            if battery["epoch"] != best["epoch"] or not math.isclose(
                battery["selected_validation_loss"], best["validation_loss"],
                rel_tol=0.0, abs_tol=1e-12,
            ):
                raise ValueError(f"{row['row_id']} battery is not the loss-selected best")
        local_run = DATA / "v3_screening" / row["run_tag"]
        invariant_count = len(list((local_run / "invariants").glob("invariant_epoch_*.json")))
        visualization_count = len(list((local_run / "visualization").glob("epoch_*.json")))
        observed_evidence = dict(row["evidence"])
        if history:
            observed_evidence.update({
                "validation_loss_per_epoch": True,
                "structural_invariants_per_epoch": invariant_count >= len(history),
                "fixed_condition_visualizations": visualization_count >= len(history),
            })
        if battery is not None:
            observed_evidence["validation_metric_battery"] = True
        evidence_gap = row.get("evidence_gap")
        if history and row["status"] == "running":
            evidence_gap = (
                f"in progress: {len(history)}/{row['horizon_epochs']} loss epochs, "
                f"{invariant_count}/{len(history)} invariant reports, "
                f"{visualization_count}/{len(history)} visualization payloads; "
                "distribution diagnostics and the fixed-bank battery wait for the "
                "selected completed checkpoint"
            )
        record = {
            "row_id": row["row_id"],
            "variant": row["variant"],
            "run_tag": row["run_tag"],
            "declared_change": row["declared_change"],
            "scientific_question": row["scientific_question"],
            "status": row["status"],
            "disposition": row.get("disposition"),
            "causal_status": row.get("causal_status"),
            "color": ROW_COLORS[index % len(ROW_COLORS)],
            "epochs_observed": len(history),
            "horizon_epochs": row["horizon_epochs"],
            "optimizer_state_transferred": row["initialization"]["optimizer_state_transferred"],
            "declared_evidence_at_last_manual_disposition": row["evidence"],
            "evidence": observed_evidence,
            "evidence_gap": evidence_gap,
            "invariant_reports_observed": invariant_count,
            "visualization_payloads_observed": visualization_count,
            "battery": battery,
            "loss_measure": row["loss_measure"],
            "loss_measure_offset": offset,
        }
        if history:
            best = min(history, key=lambda r: (r["validation_loss"], r["epoch"]))
            raw_best = float(best["validation_loss"])
            best_loss = common_loss(raw_best, row)
            raw_parent_loss = float(row["parent"]["validation_loss"])
            parent_loss = common_loss(raw_parent_loss, row["parent"])
            record.update({
                "raw_first_epoch_validation_loss": history[0]["validation_loss"],
                "first_epoch_validation_loss": common_loss(
                    history[0]["validation_loss"], row
                ),
                "best_epoch": best["epoch"],
                "raw_best_validation_loss": raw_best,
                "best_validation_loss": best_loss,
                "final_epoch": history[-1]["epoch"],
                "raw_final_validation_loss": history[-1]["validation_loss"],
                "final_validation_loss": common_loss(
                    history[-1]["validation_loss"], row
                ),
                "final_train_loss": history[-1]["train_loss"],
                # The gap is the overfitting signal, and it is reported per row
                # because a row that lowers train while raising validation has
                # not improved the model even if its train curve looks good.
                "raw_reported_final_generalization_gap": (
                    history[-1]["validation_loss"] - history[-1]["train_loss"]
                ),
                "raw_parent_validation_loss": raw_parent_loss,
                "parent_validation_loss": parent_loss,
                "delta_vs_parent": best_loss - parent_loss,
                "direction_vs_parent": classify(best_loss - parent_loss),
            })
            control = row.get("control") or {}
            if control.get("best_validation_loss") is not None:
                raw_control_loss = float(control["best_validation_loss"])
                control_loss = common_loss(raw_control_loss, control)
                record.update({
                    "control_run_tag": control.get("run_tag"),
                    "raw_control_validation_loss": raw_control_loss,
                    "control_validation_loss": control_loss,
                    "delta_vs_control": best_loss - control_loss,
                    "direction_vs_control": classify(best_loss - control_loss),
                    "control_mismatch": control.get("mismatch"),
                })
            comparator = row.get("comparator") or {}
            if comparator.get("validation_loss") is not None:
                raw_comparator_loss = float(comparator["validation_loss"])
                comparator_loss = common_loss(raw_comparator_loss, comparator)
                record.update({
                    "comparator_row_id": comparator.get("row_id"),
                    "comparator_run_tag": comparator.get("run_tag"),
                    "raw_comparator_validation_loss": raw_comparator_loss,
                    "comparator_validation_loss": comparator_loss,
                    "delta_vs_comparator": best_loss - comparator_loss,
                    "direction_vs_comparator": classify(best_loss - comparator_loss),
                })
        rows.append(record)
    return {
        "schema_version": 1,
        "kind": "cbsc-zdc-v3-screening-summary",
        "baseline": baseline,
        "loss_measure_contract": registry["loss_measure_contract"],
        "promotion_rule": registry["promotion_rule"],
        "run_to_run_reference": RUN_TO_RUN_REFERENCE,
        "run_to_run_reference_meaning": (
            "largest absolute per-epoch validation-loss difference between two runs "
            "from the same checkpoint at matched learning rates; a reproducibility "
            "reference, not a standard error, confidence interval, or p-value"
        ),
        "rows": rows,
        "promoted_rows": [r["row_id"] for r in rows if r.get("disposition") == "promoted"],
        "test_events_used": 0,
        "selection_role": "development screening evidence; selects nothing and publishes nothing",
        "scientific_status": "PHYSICS VALIDATION NOT ESTABLISHED",
    }


def trajectory_figure(summary: dict, series: dict[str, list[dict]], output: Path) -> Path:
    style()
    figure, axes = plt.subplots(figsize=(9.5, 5.6))
    baseline = summary["baseline"]

    axes.axhline(
        baseline["common_measure_validation_loss"],
        color=PARENT, linewidth=1.6, linestyle="--",
        label=f"{baseline['label']} parent · {baseline['run_tag']} e{baseline['epoch']} "
              f"· {baseline['common_measure_validation_loss']:.6f} common",
    )
    seen_control: set[str] = set()
    for record in summary["rows"]:
        history = series.get(record["variant"], [])
        if not history:
            continue
        axes.plot(
            [r["epoch"] for r in history],
            [
                r["validation_loss"] + record["loss_measure_offset"]
                for r in history
            ],
            color=record["color"], linewidth=1.9, marker="o", markersize=3.2,
            label=f"{record['row_id']} · best {record['best_validation_loss']:.6f} "
                  f"@ e{record['best_epoch']}",
        )
        axes.plot(
            record["best_epoch"], record["best_validation_loss"],
            marker="*", markersize=13, color=record["color"],
            markeredgecolor="white", markeredgewidth=0.8, zorder=5,
        )
        control_loss = record.get(
            "comparator_validation_loss", record.get("control_validation_loss")
        )
        tag = record.get("comparator_run_tag", record.get("control_run_tag"))
        if control_loss is not None and tag not in seen_control:
            seen_control.add(tag)
            axes.axhline(
                control_loss, color=CONTROL, linewidth=1.4, linestyle=":",
                label=f"declared comparator/control · {tag} · {control_loss:.6f}",
            )

    axes.set_xlabel("Row-local epoch")
    axes.set_ylabel("Common-measure validation loss")
    axes.set_title(
        "v3 architecture screening — one declared change per row",
        color=NAVY, fontsize=13, pad=12,
    )
    axes.grid(True, color=GRID, linewidth=0.8, alpha=0.9)
    axes.set_axisbelow(True)
    axes.legend(frameon=False, fontsize=8.5, loc="upper right")
    figure.text(
        0.01, 0.015,
        "Screening rows are initialized from the parent, not resumed from it; row epochs restart at 0.\n"
        "Promotion requires target improvement and every declared guard. Historical v2 totals "
        "include the audited target-Jacobian offset.\nPHYSICS VALIDATION NOT ESTABLISHED.",
        fontsize=7.4, color=MUTED,
    )
    figure.tight_layout(rect=(0, 0.095, 1, 1))
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output)
    plt.close(figure)
    return output


def delta_figure(summary: dict, output: Path) -> Path:
    style()
    rows = [r for r in summary["rows"] if "delta_vs_parent" in r]
    figure, axes = plt.subplots(figsize=(9.5, 4.4))
    if not rows:
        axes.text(0.5, 0.5, "no screening rows with imported evidence",
                  ha="center", va="center", color=MUTED)
        axes.set_axis_off()
    else:
        labels, parent_deltas, control_deltas, colors = [], [], [], []
        for record in rows:
            labels.append(record["row_id"])
            parent_deltas.append(record["delta_vs_parent"])
            control_deltas.append(
                record.get("delta_vs_comparator", record.get("delta_vs_control"))
            )
            colors.append(record["color"])
        positions = range(len(labels))
        width = 0.36
        axes.bar([p - width / 2 for p in positions], parent_deltas, width,
                 color=colors, edgecolor=NAVY, linewidth=0.6, label="vs parent (B0)")
        present = [(p, d) for p, d in zip(positions, control_deltas) if d is not None]
        if present:
            axes.bar([p + width / 2 for p, _ in present], [d for _, d in present], width,
                     color="white", edgecolor=CONTROL, linewidth=1.4, hatch="///",
                     label="vs declared comparator/control")
        axes.axhline(0, color=NAVY, linewidth=1.0)
        axes.axhspan(-RUN_TO_RUN_REFERENCE, RUN_TO_RUN_REFERENCE,
                     color=MUTED, alpha=0.18,
                     label=f"run-to-run reference ±{RUN_TO_RUN_REFERENCE:g}")
        axes.set_xticks(list(positions))
        axes.set_xticklabels(labels)
        axes.set_ylabel("Δ common-measure validation loss\n(negative is better)")
        axes.grid(True, axis="y", color=GRID, linewidth=0.8, alpha=0.9)
        axes.set_axisbelow(True)
        axes.legend(frameon=False, fontsize=8.5)
    axes.set_title("Screening rows against parent and declared comparator",
                   color=NAVY, fontsize=13, pad=12)
    figure.text(
        0.01, 0.02,
        "The shaded band is a reproducibility reference from two runs sharing a checkpoint at "
        "matched learning rates.\nIt is not a standard error and supports no significance claim. "
        "All deltas use the common GeV response-density measure.",
        fontsize=7.4, color=MUTED,
    )
    figure.tight_layout(rect=(0.02, 0.095, 1, 1))
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output)
    plt.close(figure)
    return output


def main() -> int:
    registry = load_registry()
    series = load_history()
    summary = summarize(registry, series)

    OUT.mkdir(parents=True, exist_ok=True)
    figures = [
        trajectory_figure(summary, series, OUT / "screening_validation_loss.png"),
        delta_figure(summary, OUT / "screening_deltas.png"),
    ]
    summary_path = OUT / "screening_summary.json"
    temporary = summary_path.with_name(f".{summary_path.name}.tmp")
    temporary.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )
    temporary.replace(summary_path)

    print(json.dumps({
        "rows": len(summary["rows"]),
        "rows_with_evidence": sum(1 for r in summary["rows"] if "best_validation_loss" in r),
        "promoted": summary["promoted_rows"],
        "figures": [f.relative_to(ROOT).as_posix() for f in figures],
        "summary": summary_path.relative_to(ROOT).as_posix(),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
