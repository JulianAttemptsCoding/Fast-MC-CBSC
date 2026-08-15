"""Figures and summary for the v3 architecture screening rows.

A screening row asks one question: does exactly one architectural change lower
the validation loss relative to the parent it was initialized from?  Each row is
plotted against two horizontal references -- the parent's accepted validation
loss, and the matched control's best where one exists -- because a row that
merely beats its own first epoch has shown nothing.

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
import json
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


def classify(delta: float) -> str:
    """Direction of a row against a reference, using the reproducibility band."""
    if delta < -RUN_TO_RUN_REFERENCE:
        return "better"
    if delta > RUN_TO_RUN_REFERENCE:
        return "worse"
    return "within_run_to_run_reference"


def summarize(registry: dict, series: dict[str, list[dict]]) -> dict:
    baseline = registry["baseline"]
    rows = []
    for index, row in enumerate(registry["rows"]):
        history = series.get(row["variant"], [])
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
            "evidence": row["evidence"],
            "evidence_gap": row.get("evidence_gap"),
        }
        if history:
            best = min(history, key=lambda r: (r["validation_loss"], r["epoch"]))
            parent_loss = float(row["parent"]["validation_loss"])
            record.update({
                "first_epoch_validation_loss": history[0]["validation_loss"],
                "best_epoch": best["epoch"],
                "best_validation_loss": best["validation_loss"],
                "final_epoch": history[-1]["epoch"],
                "final_validation_loss": history[-1]["validation_loss"],
                "final_train_loss": history[-1]["train_loss"],
                # The gap is the overfitting signal, and it is reported per row
                # because a row that lowers train while raising validation has
                # not improved the model even if its train curve looks good.
                "final_generalization_gap": (
                    history[-1]["validation_loss"] - history[-1]["train_loss"]
                ),
                "parent_validation_loss": parent_loss,
                "delta_vs_parent": best["validation_loss"] - parent_loss,
                "direction_vs_parent": classify(best["validation_loss"] - parent_loss),
            })
            control = row.get("control") or {}
            if control.get("best_validation_loss") is not None:
                control_loss = float(control["best_validation_loss"])
                record.update({
                    "control_run_tag": control.get("run_tag"),
                    "control_validation_loss": control_loss,
                    "delta_vs_control": best["validation_loss"] - control_loss,
                    "direction_vs_control": classify(best["validation_loss"] - control_loss),
                    "control_mismatch": control.get("mismatch"),
                })
        rows.append(record)
    return {
        "schema_version": 1,
        "kind": "cbsc-zdc-v3-screening-summary",
        "baseline": baseline,
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
        baseline["validation_loss"], color=PARENT, linewidth=1.6, linestyle="--",
        label=f"{baseline['label']} parent · {baseline['run_tag']} e{baseline['epoch']} "
              f"· {baseline['validation_loss']:.6f}",
    )
    seen_control: set[str] = set()
    for record in summary["rows"]:
        history = series.get(record["variant"], [])
        if not history:
            continue
        axes.plot(
            [r["epoch"] for r in history], [r["validation_loss"] for r in history],
            color=record["color"], linewidth=1.9, marker="o", markersize=3.2,
            label=f"{record['row_id']} · best {record['best_validation_loss']:.6f} "
                  f"@ e{record['best_epoch']}",
        )
        axes.plot(
            record["best_epoch"], record["best_validation_loss"],
            marker="*", markersize=13, color=record["color"],
            markeredgecolor="white", markeredgewidth=0.8, zorder=5,
        )
        control_loss = record.get("control_validation_loss")
        tag = record.get("control_run_tag")
        if control_loss is not None and tag not in seen_control:
            seen_control.add(tag)
            axes.axhline(
                control_loss, color=CONTROL, linewidth=1.4, linestyle=":",
                label=f"matched control · {tag} · {control_loss:.6f}",
            )

    axes.set_xlabel("Row-local epoch")
    axes.set_ylabel("Validation loss")
    axes.set_title(
        "v3 architecture screening — one declared change per row",
        color=NAVY, fontsize=13, pad=12,
    )
    axes.grid(True, color=GRID, linewidth=0.8, alpha=0.9)
    axes.set_axisbelow(True)
    axes.legend(frameon=False, fontsize=8.5, loc="upper right")
    figure.text(
        0.01, 0.015,
        "Screening rows are initialized from the parent, not resumed from it, so epoch numbering "
        "restarts at 0.\nA row is promoted only when its declared target improves and every declared "
        "guard passes. PHYSICS VALIDATION NOT ESTABLISHED.",
        fontsize=7.4, color=MUTED,
    )
    figure.tight_layout(rect=(0, 0.055, 1, 1))
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
            control_deltas.append(record.get("delta_vs_control"))
            colors.append(record["color"])
        positions = range(len(labels))
        width = 0.36
        axes.bar([p - width / 2 for p in positions], parent_deltas, width,
                 color=colors, edgecolor=NAVY, linewidth=0.6, label="vs parent (B0)")
        present = [(p, d) for p, d in zip(positions, control_deltas) if d is not None]
        if present:
            axes.bar([p + width / 2 for p, _ in present], [d for _, d in present], width,
                     color="white", edgecolor=CONTROL, linewidth=1.4, hatch="///",
                     label="vs matched control")
        axes.axhline(0, color=NAVY, linewidth=1.0)
        axes.axhspan(-RUN_TO_RUN_REFERENCE, RUN_TO_RUN_REFERENCE,
                     color=MUTED, alpha=0.18,
                     label=f"run-to-run reference ±{RUN_TO_RUN_REFERENCE:g}")
        axes.set_xticks(list(positions))
        axes.set_xticklabels(labels)
        axes.set_ylabel("Δ validation loss  (negative is better)")
        axes.grid(True, axis="y", color=GRID, linewidth=0.8, alpha=0.9)
        axes.set_axisbelow(True)
        axes.legend(frameon=False, fontsize=8.5)
    axes.set_title("Screening rows against parent and matched control",
                   color=NAVY, fontsize=13, pad=12)
    figure.text(
        0.01, 0.02,
        "The shaded band is a reproducibility reference measured between two runs from the same "
        "checkpoint at matched learning rates.\nIt is not a standard error and supports no "
        "significance claim.",
        fontsize=7.4, color=MUTED,
    )
    figure.tight_layout(rect=(0, 0.07, 1, 1))
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
