"""Build comprehensive per-epoch metric data and omitted diagnostic figures.

The headline builder intentionally presents a compact scientific subset.  This
companion guarantees that every numeric diagnostic leaf is still refreshed and
cataloged on every epoch, and adds figures for feature moments/resolutions,
energy-bin moments, longitudinal profiles, and QA/gate state.  Each figure has
an accepted-validation-loss-best-so-far counterpart.
"""

from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
DATA_ROOT = HERE / "data" / "diagnostics"
OUT = HERE / "diagnostics_20260803"
STATUS = HERE / "data" / "continuation_status.json"
RUN_TAGS = sys.argv[1:] or ["dicos-p9", "dicos-p10"]
NAVY = "#0f2a43"
FAST = "#d2691e"
TRUTH = "#167c5a"
MUTED = "#6b7f92"
QUARANTINE = "#7b2cbf"
FEATURES = [
    ("total_response_gev", "Total response"),
    ("hit_count", "Hit count"),
    ("depth_centroid_layer", "Depth centroid"),
    ("x_centroid_mm", "x centroid"),
    ("y_centroid_mm", "y centroid"),
    ("radial_rms_mm", "Radial RMS"),
    ("top1_fraction", "Leading-cell fraction"),
    ("ecal_fraction", "ECAL fraction"),
    ("late_fraction", "Late fraction"),
]


def load_rows() -> list[dict]:
    rows: dict[int, dict] = {}
    for tag in RUN_TAGS:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", tag):
            raise ValueError(f"unsafe run tag: {tag!r}")
        for path in sorted((DATA_ROOT / tag).glob("metrics_epoch_*.json")):
            row = json.loads(path.read_text(encoding="utf-8"))
            if row.get("split") != "validation" or row.get("qa", {}).get(
                "test_events_used"
            ) != 0:
                raise ValueError(f"non-validation diagnostic: {path}")
            row["run_tag"] = tag
            rows[int(row["epoch"])] = row
    return [rows[key] for key in sorted(rows)]


def best_rows(rows: list[dict]) -> tuple[list[dict], list[int]]:
    try:
        from exhibition.build_diagnostic_trend_figure import best_loss_so_far_rows
    except ModuleNotFoundError:
        from build_diagnostic_trend_figure import best_loss_so_far_rows

    selected, epochs, _trace, _missing = best_loss_so_far_rows(
        rows, "calibrated_lr1e4"
    )
    return selected, epochs


def flatten_numeric(value, prefix=""):
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else key
            yield from flatten_numeric(child, path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from flatten_numeric(child, f"{prefix}[{index}]")
    elif isinstance(value, bool):
        yield prefix, int(value)
    elif isinstance(value, (int, float)) and math.isfinite(float(value)):
        yield prefix, float(value)


def metric_registry(rows: list[dict]) -> dict:
    roots = (
        "evaluation",
        "hcal",
        "trend",
        "trend_stderr",
        "truth_longitudinal_profile_gev",
        "generated_longitudinal_profile_gev",
    )
    paths: set[str] = set()
    flattened = []
    for row in rows:
        values = {}
        for root in roots:
            values.update(dict(flatten_numeric(row[root], root)))
        flattened.append(values)
        paths.update(values)
    missing = {
        path: [int(rows[i]["epoch"]) for i, values in enumerate(flattened) if path not in values]
        for path in sorted(paths)
    }
    missing = {path: epochs for path, epochs in missing.items() if epochs}
    if missing:
        raise ValueError(f"numeric metric coverage is incomplete: {missing}")
    return {
        path: {
            "values": [values[path] for values in flattened],
            "latest": flattened[-1][path],
            "complete_epochs": len(rows),
        }
        for path in sorted(paths)
    }


def _quarantined() -> list[int]:
    payload = json.loads(STATUS.read_text(encoding="utf-8"))
    return [
        int(row["epoch"])
        for row in payload.get("overrides", [])
        if row.get("run_tag") in RUN_TAGS and row.get("status") == "quarantined"
    ]


def _style_axes(axes, epochs):
    for ax in np.asarray(axes).ravel():
        if not ax.axison:
            continue
        ax.grid(axis="y", color="#dde5ec", lw=0.8)
        ax.spines[["top", "right"]].set_visible(False)
        for epoch in _quarantined():
            if epoch in epochs:
                ax.axvline(epoch, color=QUARANTINE, ls="--", lw=1)


def _finish(fig, name: str, title: str, subtitle: str) -> Path:
    fig.suptitle(title, x=0.04, y=0.985, ha="left", fontsize=16, fontweight="bold")
    fig.text(0.04, 0.952, subtitle, ha="left", color=MUTED, fontsize=9)
    fig.text(
        0.04,
        0.012,
        "Fixed CBSC validation events; zero test use. Purple dashed = quarantined. "
        "Descriptive monitoring only; external metrics cannot select checkpoints.",
        ha="left",
        color=MUTED,
        fontsize=8.5,
    )
    fig.subplots_adjust(top=0.90, bottom=0.09, left=0.07, right=0.98, hspace=0.42, wspace=0.28)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}.png"
    fig.savefig(path, dpi=160, metadata={"Date": None})
    svg_path = OUT / f"{name}.svg"
    fig.savefig(svg_path, metadata={"Date": None})
    svg_text = svg_path.read_text(encoding="utf-8")
    svg_path.write_text(
        "\n".join(line.rstrip() for line in svg_text.splitlines()) + "\n",
        encoding="utf-8",
    )
    plt.close(fig)
    return path


def feature_moments(rows: list[dict], epochs: list[int], suffix: str, title: str):
    fig, axes = plt.subplots(3, 3, figsize=(13.333, 9.4), sharex=True)
    for ax, (key, label) in zip(axes.ravel(), FEATURES, strict=True):
        feature = [row["evaluation"]["feature_bias"][key] for row in rows]
        ax.plot(epochs, [row["truth_mean"] for row in feature], color=TRUTH, marker="o", ms=3, label="Geant4 mean")
        ax.plot(epochs, [row["generated_mean"] for row in feature], color=FAST, marker="o", ms=3, label="Fast-MC mean")
        ax.set_title(label, loc="left", fontsize=10.5)
    axes[0, 0].legend(frameon=False, fontsize=8)
    for ax in axes[-1]:
        ax.set_xlabel("Completed epoch")
    _style_axes(axes, epochs)
    return _finish(fig, f"feature_moments{suffix}", title, "Every high-level generated/truth mean recorded by the 3090 diagnostic.")


def feature_resolutions(rows: list[dict], epochs: list[int], suffix: str, title: str):
    fig, axes = plt.subplots(3, 3, figsize=(13.333, 9.4), sharex=True)
    for ax, (key, label) in zip(axes.ravel(), FEATURES, strict=True):
        feature = [row["evaluation"]["feature_bias"][key] for row in rows]
        ax.plot(epochs, [row["truth_std"] for row in feature], color=TRUTH, marker="o", ms=3, label="Geant4 std")
        ax.plot(epochs, [row["generated_std"] for row in feature], color=FAST, marker="o", ms=3, label="Fast-MC std")
        ax.set_title(label, loc="left", fontsize=10.5)
    axes[0, 0].legend(frameon=False, fontsize=8)
    for ax in axes[-1]:
        ax.set_xlabel("Completed epoch")
    _style_axes(axes, epochs)
    return _finish(fig, f"feature_resolutions{suffix}", title, "Every high-level generated/truth standard deviation recorded by the 3090 diagnostic.")


def energy_bin_moments(rows: list[dict], epochs: list[int], suffix: str, title: str):
    bins = rows[-1]["evaluation"]["response_bins"]
    fig, axes = plt.subplots(4, 2, figsize=(13.333, 11.3), sharex=True)
    for index, (ax, edge) in enumerate(zip(axes.ravel(), bins, strict=True)):
        series = [row["evaluation"]["response_bins"][index] for row in rows]
        ax.plot(epochs, [row["truth_mean"] for row in series], color=TRUTH, marker="o", ms=3, label="Geant4 mean")
        ax.plot(epochs, [row["generated_mean"] for row in series], color=FAST, marker="o", ms=3, label="Fast-MC mean")
        ax.plot(epochs, [row["truth_std"] for row in series], color=TRUTH, ls=":", lw=1.5, label="Geant4 std")
        ax.plot(epochs, [row["generated_std"] for row in series], color=FAST, ls=":", lw=1.5, label="Fast-MC std")
        ax.set_title(f"{edge['low']:.0f}–{edge['high']:.0f} GeV", loc="left", fontsize=10.5)
    axes[0, 0].legend(frameon=False, fontsize=7.5, ncol=2)
    for ax in axes[-1]:
        ax.set_xlabel("Completed epoch")
    _style_axes(axes, epochs)
    return _finish(fig, f"energy_bin_moments{suffix}", title, "Solid = response mean; dotted = response standard deviation in each predeclared energy bin.")


def profiles_and_qa(rows: list[dict], epochs: list[int], suffix: str, title: str):
    truth = np.asarray([row["truth_longitudinal_profile_gev"] for row in rows])
    generated = np.asarray([row["generated_longitudinal_profile_gev"] for row in rows])
    relative = (generated - truth) / np.maximum(truth, 1e-9)
    fig, axes = plt.subplots(2, 2, figsize=(13.333, 8.1))
    image = axes[0, 0].imshow(relative, aspect="auto", origin="lower", cmap="coolwarm", vmin=-1, vmax=1, extent=[0, 64, epochs[0] - 0.5, epochs[-1] + 0.5])
    axes[0, 0].set_title("Longitudinal profile relative difference", loc="left")
    axes[0, 0].set_xlabel("Layer")
    axes[0, 0].set_ylabel("Completed epoch")
    fig.colorbar(image, ax=axes[0, 0], label="(Fast-MC − Geant4) / Geant4")

    gate_names = sorted(rows[-1]["evaluation"]["gate_checks"]["checks"])
    gate = np.asarray([[int(row["evaluation"]["gate_checks"]["checks"][key]) for key in gate_names] for row in rows])
    axes[0, 1].imshow(gate, aspect="auto", origin="lower", cmap="RdYlGn", vmin=0, vmax=1, extent=[-0.5, len(gate_names) - 0.5, epochs[0] - 0.5, epochs[-1] + 0.5])
    axes[0, 1].set_xticks(range(len(gate_names)), [name.replace("_", " ") for name in gate_names], rotation=45, ha="right", fontsize=7)
    axes[0, 1].set_title("Informational gate checks", loc="left")
    axes[0, 1].set_ylabel("Completed epoch")

    for key, colour, label in (("truth_zero_fraction", TRUTH, "Geant4 zero"), ("generated_zero_fraction", FAST, "Fast-MC zero")):
        axes[1, 0].plot(epochs, [row["evaluation"][key] for row in rows], color=colour, marker="o", ms=3, label=label)
    axes[1, 0].plot(epochs, [row["evaluation"]["distribution_metrics"]["positive_cell_energy_gev"]["generated_mean"] for row in rows], color=NAVY, marker="s", ms=3, label="Generated positive-cell mean [GeV]")
    axes[1, 0].set_title("Zero response and positive-cell energy", loc="left")
    axes[1, 0].set_xlabel("Completed epoch")
    axes[1, 0].legend(frameon=False, fontsize=8)

    axes[1, 1].plot(epochs, [row["hcal"]["truth_total_mean_gev"] for row in rows], color=TRUTH, marker="o", ms=3, label="HCAL Geant4 total")
    axes[1, 1].plot(epochs, [row["hcal"]["generated_total_mean_gev"] for row in rows], color=FAST, marker="o", ms=3, label="HCAL Fast-MC total")
    axes[1, 1].plot(epochs, [row["hcal"]["truth_hits_mean"] / 1000 for row in rows], color=TRUTH, ls=":", label="HCAL Geant4 hits / 1000")
    axes[1, 1].plot(epochs, [row["hcal"]["generated_hits_mean"] / 1000 for row in rows], color=FAST, ls=":", label="HCAL Fast-MC hits / 1000")
    axes[1, 1].set_title("HCAL response and occupancy", loc="left")
    axes[1, 1].set_xlabel("Completed epoch")
    axes[1, 1].legend(frameon=False, fontsize=7.5)
    _style_axes(axes[1], epochs)
    return _finish(fig, f"profiles_and_qa{suffix}", title, "All 65 profile layers, every informational gate result, zero-response rates, pooled cell energy, and HCAL summaries.")


def build() -> dict:
    rows = load_rows()
    if not rows:
        raise RuntimeError("no diagnostic rows")
    epochs = [int(row["epoch"]) for row in rows]
    registry = metric_registry(rows)
    best, best_epochs = best_rows(rows)
    produced = [
        feature_moments(rows, epochs, "_vs_epoch", "Feature means vs epoch"),
        feature_resolutions(rows, epochs, "_vs_epoch", "Feature resolutions vs epoch"),
        energy_bin_moments(rows, epochs, "_vs_epoch", "Energy-bin response moments vs epoch"),
        profiles_and_qa(rows, epochs, "_vs_epoch", "Profiles, QA, and detector summaries vs epoch"),
    ]
    if best:
        produced.extend(
            [
                feature_moments(best, best_epochs, "_of_best_loss_so_far", "Feature means of accepted validation-loss best so far"),
                feature_resolutions(best, best_epochs, "_of_best_loss_so_far", "Feature resolutions of accepted validation-loss best so far"),
                energy_bin_moments(best, best_epochs, "_of_best_loss_so_far", "Energy-bin moments of accepted validation-loss best so far"),
                profiles_and_qa(best, best_epochs, "_of_best_loss_so_far", "Profiles and QA of accepted validation-loss best so far"),
            ]
        )
    payload = {
        "schema_version": 1,
        "kind": "cbsc-zdc-all-numeric-diagnostic-metric-trends",
        "run_tags": RUN_TAGS,
        "epochs": epochs,
        "source_split": "validation",
        "test_events_used": 0,
        "numeric_metric_leaf_count": len(registry),
        "all_numeric_metric_leaves_complete_every_epoch": True,
        "metrics": registry,
        "best_loss_so_far": {
            "selection_quantity": "accepted validation loss only",
            "completed_epochs": best_epochs,
        },
        "figures": [path.name for path in produced],
    }
    temporary = OUT / ".all_metric_trends.json.tmp"
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(OUT / "all_metric_trends.json")
    return payload


if __name__ == "__main__":
    summary = build()
    print(
        json.dumps(
            {
                "epochs": summary["epochs"],
                "numeric_metric_leaf_count": summary["numeric_metric_leaf_count"],
                "figures": len(summary["figures"]),
            }
        )
    )
