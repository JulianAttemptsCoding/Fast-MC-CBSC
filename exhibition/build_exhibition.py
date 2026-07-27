#!/usr/bin/env python3
"""Build presentation-ready CBSC-ZDC figures from verified local evidence.

This script is deliberately read-only outside ``exhibition/``. It uses compact
verification records and the already-synced validation visualization payloads;
it never reads test data or the legacy tree.
"""

from __future__ import annotations

import csv
import hashlib
import html
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import patches
from matplotlib.colors import LogNorm
from matplotlib.lines import Line2D


ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "exhibition"
DATA = HERE / "data"
FIG = HERE / "figures"
AUDIT = ROOT / "audit"
DASH = ROOT / "dashboard" / "public" / "data"

VARIANTS = [
    "calibrated_lr3e5",
    "calibrated_lr1e4",
    "calibrated_lr3e4",
    "calibrated_lr1e4_halfbatch",
]
LABELS = {
    "calibrated_lr3e5": r"Calibrated · LR $3\times10^{-5}$",
    "calibrated_lr1e4": r"Calibrated · LR $1\times10^{-4}$",
    "calibrated_lr3e4": r"Calibrated · LR $3\times10^{-4}$",
    "calibrated_lr1e4_halfbatch": r"Calibrated · LR $1\times10^{-4}$ · half batch",
}
SHORT = {
    "calibrated_lr3e5": r"LR $3\times10^{-5}$",
    "calibrated_lr1e4": r"LR $1\times10^{-4}$",
    "calibrated_lr3e4": r"LR $3\times10^{-4}$",
    "calibrated_lr1e4_halfbatch": r"LR $1\times10^{-4}$ · half batch",
}
COLORS = {
    "calibrated_lr3e5": "#0072B2",
    "calibrated_lr1e4": "#009E73",
    "calibrated_lr3e4": "#D55E00",
    "calibrated_lr1e4_halfbatch": "#CC79A7",
}
NAVY = "#102A43"
MUTED = "#627D98"
GRID = "#D9E2EC"
LIGHT = "#F4F7FA"
PASS = "#16835B"
WARN = "#C47F00"
BLOCK = "#B42318"

BEST_FILES = {
    "calibrated_lr3e5": "compute-extension-r1-calibrated-lr3e5_joint_epoch_0002.json",
    "calibrated_lr1e4": "compute-extension-r1-calibrated-lr1e4_joint_epoch_0002.json",
    "calibrated_lr3e4": "compute-extension-r1-calibrated-lr3e4_joint_epoch_0004.json",
    "calibrated_lr1e4_halfbatch": "compute-extension-r1-calibrated-lr1e4-halfbatch_joint_epoch_0004.json",
}

COMPONENTS = [
    ("train_visible", "Visible BCE"),
    ("train_response", "Response NLL"),
    ("train_first_layer", "First-layer CE"),
    ("train_active", "Active-layer BCE"),
    ("train_profile_flow", "Profile flow MSE"),
    ("train_count", "Count CE"),
    ("train_support_bce", "Support BCE"),
    ("train_support_rank", "Support rank"),
    ("train_share_flow", "Share flow MSE"),
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_history() -> dict[str, list[dict[str, float]]]:
    rows: dict[str, list[dict[str, float]]] = {v: [] for v in VARIANTS}
    with (DATA / "training_history.csv").open(newline="", encoding="utf-8") as stream:
        for raw in csv.DictReader(stream):
            variant = raw.pop("variant")
            parsed = {k: float(v) for k, v in raw.items()}
            parsed["epoch"] = int(parsed["epoch"])
            rows[variant].append(parsed)
    for variant, series in rows.items():
        series.sort(key=lambda x: x["epoch"])
        expected = list(range(3 if variant in VARIANTS[:2] else 5))
        actual = [r["epoch"] for r in series]
        assert actual == expected, (variant, actual, expected)
        assert all(math.isfinite(value) for row in series for value in row.values())
    return rows


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def style() -> None:
    mpl.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 11,
            "axes.titlesize": 14,
            "axes.titleweight": "bold",
            "axes.labelsize": 11,
            "axes.edgecolor": NAVY,
            "axes.labelcolor": NAVY,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "text.color": NAVY,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.18,
            "svg.fonttype": "none",
        }
    )


def clean_axis(ax: mpl.axes.Axes, *, grid: str = "y") -> None:
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis=grid, color=GRID, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)


def title(fig: mpl.figure.Figure, heading: str, subheading: str) -> None:
    fig.suptitle(heading, x=0.055, y=0.985, ha="left", fontsize=22, fontweight="bold", color=NAVY)
    fig.text(0.055, 0.943, subheading, ha="left", va="top", fontsize=11, color=MUTED)


def footer(fig: mpl.figure.Figure, text: str) -> None:
    fig.text(0.055, 0.018, text, ha="left", va="bottom", fontsize=8.5, color=MUTED)


def save(fig: mpl.figure.Figure, stem: str, *, svg: bool = True) -> list[Path]:
    paths = [FIG / f"{stem}.png"]
    fig.savefig(paths[0], dpi=180)
    if svg:
        paths.append(FIG / f"{stem}.svg")
        fig.savefig(paths[-1])
    plt.close(fig)
    return paths


def fig01_loss_small_multiples(history: dict) -> list[Path]:
    fig, axes = plt.subplots(2, 2, figsize=(13.333, 7.5), sharey=True)
    title(
        fig,
        "Training and validation loss across every completed epoch",
        "Four calibrated continuation families · bounded 26,624-train / 6,656-validation bank · test split unopened",
    )
    for ax, variant in zip(axes.flat, VARIANTS):
        rows = history[variant]
        x = [r["epoch"] for r in rows]
        tr = [r["train_loss"] for r in rows]
        va = [r["validation_loss"] for r in rows]
        ax.plot(x, tr, color=COLORS[variant], marker="o", lw=2.2, label="Train")
        ax.plot(x, va, color=NAVY, marker="s", lw=2.2, ls="--", label="Validation")
        ax.set_title(LABELS[variant], loc="left", fontsize=12)
        ax.set_xticks(x)
        ax.set_xlabel("Completed epoch")
        ax.set_ylabel("Weighted joint loss")
        clean_axis(ax)
        for xx, yy in [(x[-1], tr[-1]), (x[-1], va[-1])]:
            ax.annotate(f"{yy:.3f}", (xx, yy), xytext=(5, 4), textcoords="offset points", fontsize=8.5)
    handles = [
        Line2D([0], [0], color=COLORS[VARIANTS[0]], marker="o", lw=2.2, label="Training"),
        Line2D([0], [0], color=NAVY, marker="s", lw=2.2, ls="--", label="Validation"),
    ]
    fig.legend(handles=handles, loc="upper right", bbox_to_anchor=(0.955, 0.915), frameon=False, ncol=2)
    fig.subplots_adjust(left=0.07, right=0.96, top=0.86, bottom=0.10, hspace=0.34, wspace=0.18)
    footer(fig, "Lower is better for this frozen weighted objective. Curves are short screening continuations, not converged final training.")
    return save(fig, "01_train_validation_loss_each_model")


def fig02_validation_comparison(history: dict) -> list[Path]:
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(13.333, 7.5), gridspec_kw={"width_ratios": [1.65, 1]})
    title(
        fig,
        "More T4 compute lowered validation loss in all four calibrated families",
        "Absolute trajectories at left; total change from each family’s first completed epoch at right",
    )
    for variant in VARIANTS:
        rows = history[variant]
        x = np.array([r["epoch"] for r in rows])
        y = np.array([r["validation_loss"] for r in rows])
        ax.plot(x, y, marker="o", lw=2.6, ms=6, color=COLORS[variant])
        ax.text(x[-1] + 0.06, y[-1], f"{SHORT[variant]}  {y[-1]:.3f}", va="center", fontsize=9.5)
    clean_axis(ax)
    ax.set_xlabel("Completed epoch")
    ax.set_ylabel("Validation loss")
    ax.set_xticks(range(5))
    ax.set_xlim(-0.1, 5.35)
    changes = []
    for variant in VARIANTS:
        rows = history[variant]
        initial, final = rows[0]["validation_loss"], rows[-1]["validation_loss"]
        changes.append(100 * (initial - final) / initial)
    order = np.argsort(changes)
    ordered_v = [VARIANTS[i] for i in order]
    ordered_c = [changes[i] for i in order]
    bars = ax2.barh(range(4), ordered_c, color=[COLORS[v] for v in ordered_v], height=0.55)
    ax2.set_yticks(range(4), [SHORT[v] for v in ordered_v])
    ax2.set_xlabel("Loss reduction from first epoch (%)")
    ax2.set_xlim(0, max(ordered_c) * 1.32)
    clean_axis(ax2, grid="x")
    for bar, value in zip(bars, ordered_c):
        ax2.text(value + 0.035, bar.get_y() + bar.get_height() / 2, f"{value:.2f}%", va="center", fontweight="bold")
    fig.subplots_adjust(left=0.075, right=0.95, top=0.84, bottom=0.11, wspace=0.32)
    footer(fig, "Result: 4/4 final epochs beat their family’s first completed epoch. This supports optimization progress, not Geant4 fidelity.")
    return save(fig, "02_validation_loss_comparison")


def fig03_component_heatmaps(history: dict) -> list[Path]:
    fig, axes = plt.subplots(2, 2, figsize=(13.333, 7.5))
    title(
        fig,
        "Which objective components moved during continuation training",
        "Cell value = change from epoch 0 as a percentage of |epoch-0 value| · blue/lower is an objective decrease",
    )
    vmax = 25.0
    for ax, variant in zip(axes.flat, VARIANTS):
        rows = history[variant]
        matrix = []
        for key, _ in COMPONENTS:
            values = np.array([r[key] for r in rows], dtype=float)
            denom = max(abs(values[0]), 1e-12)
            matrix.append(100 * (values - values[0]) / denom)
        matrix = np.array(matrix)
        im = ax.imshow(matrix, aspect="auto", cmap="RdBu_r", vmin=-vmax, vmax=vmax)
        ax.set_title(SHORT[variant], loc="left", fontsize=11)
        ax.set_xticks(range(len(rows)), [f"E{r['epoch']}" for r in rows])
        ax.set_yticks(range(len(COMPONENTS)), [label for _, label in COMPONENTS], fontsize=8.5)
        for i in range(matrix.shape[0]):
            for j in range(matrix.shape[1]):
                val = matrix[i, j]
                ax.text(j, i, f"{val:+.0f}", ha="center", va="center", fontsize=7.5, color="white" if abs(val) > 13 else NAVY)
        ax.tick_params(length=0)
    cbar = fig.colorbar(im, ax=axes.ravel().tolist(), fraction=0.024, pad=0.02)
    cbar.set_label("Relative change from epoch 0 (%)")
    fig.subplots_adjust(left=0.13, right=0.91, top=0.84, bottom=0.10, hspace=0.30, wspace=0.30)
    footer(fig, "Response NLL may be negative; lower (more negative) is still better. These are raw component losses before frozen loss weights.")
    return save(fig, "03_objective_component_evolution")


def visualization_payloads() -> dict[str, dict[int, dict]]:
    manifest = load_json(DASH / "manifest.json")
    selected: dict[str, dict[int, dict]] = {v: {} for v in VARIANTS}
    token_map = {
        "calibrated_lr3e5": "calibrated-lr3e5",
        "calibrated_lr1e4": "calibrated-lr1e4:",
        "calibrated_lr3e4": "calibrated-lr3e4",
        "calibrated_lr1e4_halfbatch": "calibrated-lr1e4-halfbatch",
    }
    for entry in manifest["epochs"]:
        ident = entry["id"]
        for variant, token in token_map.items():
            if token not in ident:
                continue
            if variant == "calibrated_lr1e4" and "halfbatch" in ident:
                continue
            if "viability-r1-" not in ident and "viability-wave2-r1-" not in ident and "compute-extension-r1-" not in ident:
                continue
            epoch = int(entry["epoch"])
            current = selected[variant].get(epoch)
            priority = 3 if "compute-extension-r1-" in ident else 2 if "viability-wave2-r1-" in ident else 1
            current_priority = current["_priority"] if current else -1
            if priority >= current_priority:
                payload = load_json(DASH / entry["path"])
                payload["_priority"] = priority
                payload["_path"] = entry["path"]
                selected[variant][epoch] = payload
    expected = {
        "calibrated_lr3e5": [0, 1, 2],
        "calibrated_lr1e4": [0, 1, 2],
        "calibrated_lr3e4": [0, 1, 2, 3, 4],
        "calibrated_lr1e4_halfbatch": [0, 1, 2, 3, 4],
    }
    for variant, epochs in expected.items():
        assert sorted(selected[variant]) == epochs, (variant, sorted(selected[variant]), epochs)
    return selected


def fig04_proxy_trajectories(payloads: dict) -> list[Path]:
    metrics = [
        ("response_bias_fraction", "|Response bias|", "%"),
        ("hit_count_bias_fraction", "|Hit-count bias|", "%"),
        ("mean_longitudinal_profile_relative_l1", "Longitudinal profile L1", ""),
    ]
    fig, axes = plt.subplots(3, 1, figsize=(13.333, 7.5), sharex=True)
    title(
        fig,
        "Fixed-sample visual proxies do not move monotonically with objective loss",
        "Same 50 validation conditions and five generated draws per condition at every epoch",
    )
    for ax, (key, label, unit) in zip(axes, metrics):
        for variant in VARIANTS:
            epochs = sorted(payloads[variant])
            values = [abs(payloads[variant][e]["aggregate"]["trend"][key]) for e in epochs]
            if unit == "%":
                values = [100 * x for x in values]
            ax.plot(epochs, values, marker="o", lw=2, color=COLORS[variant], label=SHORT[variant])
        ax.set_ylabel(f"{label}{' (%)' if unit == '%' else ''}")
        ax.set_xticks(range(5))
        clean_axis(ax)
    axes[-1].set_xlabel("Completed epoch")
    handles = [Line2D([0], [0], color=COLORS[v], marker="o", lw=2, label=SHORT[v]) for v in VARIANTS]
    fig.legend(handles=handles, loc="upper right", bbox_to_anchor=(0.96, 0.915), frameon=False, ncol=2)
    fig.subplots_adjust(left=0.10, right=0.96, top=0.84, bottom=0.10, hspace=0.23)
    footer(fig, "Descriptive fixed-sample diagnostics only; stochastic single-checkpoint snapshots are not tuned gates and do not establish physics validity.")
    return save(fig, "04_fixed_sample_proxy_trajectories")


def fig05_proxy_change(payloads: dict, history: dict) -> list[Path]:
    metric_info = [
        ("response_bias_fraction", "Absolute response bias", 100.0, "percentage points"),
        ("hit_count_bias_fraction", "Absolute hit-count bias", 100.0, "percentage points"),
        ("mean_longitudinal_profile_relative_l1", "Longitudinal profile L1", 1.0, "absolute"),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(13.333, 7.5))
    title(
        fig,
        "Optimization progress and visual-proxy progress are different questions",
        "Bars show final minus initial fixed-sample proxy; negative is an improvement",
    )
    for ax, (key, label, scale, unit) in zip(axes, metric_info):
        values = []
        for variant in VARIANTS:
            epochs = sorted(payloads[variant])
            start = abs(payloads[variant][epochs[0]]["aggregate"]["trend"][key])
            end = abs(payloads[variant][epochs[-1]]["aggregate"]["trend"][key])
            values.append(scale * (end - start))
        bars = ax.bar(range(4), values, color=[COLORS[v] for v in VARIANTS], width=0.62)
        ax.axhline(0, color=NAVY, lw=1)
        ax.set_title(label, loc="left", fontsize=11)
        ax.set_xticks(range(4), [r"$3e{-5}$", r"$1e{-4}$", r"$3e{-4}$", "half"], rotation=0)
        ax.set_ylabel(f"Final − initial ({unit})")
        clean_axis(ax)
        for b, value in zip(bars, values):
            ax.text(b.get_x() + b.get_width() / 2, value + (0.015 if value >= 0 else -0.015) * max(1, max(abs(v) for v in values)), f"{value:+.3f}", ha="center", va="bottom" if value >= 0 else "top", fontsize=8.5)
    fig.subplots_adjust(left=0.075, right=0.96, top=0.82, bottom=0.13, wspace=0.36)
    footer(fig, "All four validation losses improved; visual proxies were mixed. This is why lower weighted loss alone cannot open the physics or A100 gate.")
    return save(fig, "05_loss_vs_visual_proxy_boundary")


def fig06_compute_budget(terminal: dict) -> list[Path]:
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(13.333, 7.5), gridspec_kw={"width_ratios": [1.7, 1]})
    title(
        fig,
        "Four continuation jobs ran concurrently on on-demand T4 GPUs",
        "Server-side Vertex execution preserved local storage and completed within the $100 conservative ceiling",
    )
    variants = terminal["variants"]
    starts = [datetime.fromisoformat(v["start_time"].replace("Z", "+00:00")) for v in variants]
    t0 = min(starts)
    for i, v in enumerate(variants):
        start = (datetime.fromisoformat(v["start_time"].replace("Z", "+00:00")) - t0).total_seconds() / 3600
        end = (datetime.fromisoformat(v["end_time"].replace("Z", "+00:00")) - t0).total_seconds() / 3600
        ax.barh(i, end - start, left=start, height=0.46, color=COLORS[v["name"]])
        ax.text(end + 0.03, i, f"{v['hours']:.2f} h", va="center", fontsize=9)
    ax.set_yticks(range(4), [SHORT[v["name"]] for v in variants])
    ax.invert_yaxis()
    ax.set_xlabel(f"Hours since {t0.strftime('%H:%M')} UTC on 2026-07-27")
    ax.set_xlim(0, max((datetime.fromisoformat(v["end_time"].replace("Z", "+00:00")) - t0).total_seconds() / 3600 for v in variants) + 0.5)
    clean_axis(ax, grid="x")
    cost = terminal["cost"]
    spent = cost["conservative_total_usd"]
    remain = cost["remaining_under_100_usd"]
    ax2.bar(0, spent, color="#2F80ED", width=0.56, label="Conservative ledger")
    ax2.bar(0, remain, bottom=spent, color=GRID, width=0.56, label="Remaining ceiling")
    ax2.axhline(100, color=NAVY, lw=1.5)
    ax2.text(0, spent / 2, f"${spent:.2f}\naccounted", ha="center", va="center", color="white", fontweight="bold", fontsize=14)
    ax2.text(0, spent + remain / 2, f"${remain:.2f}\nremaining", ha="center", va="center", color=NAVY, fontweight="bold", fontsize=13)
    ax2.set_xlim(-0.7, 0.7)
    ax2.set_ylim(0, 105)
    ax2.set_xticks([])
    ax2.set_ylabel("USD")
    clean_axis(ax2, grid="y")
    ax2.set_title(f"{cost['extension_total_t4_hours']:.2f} T4-hours in this extension", loc="left", fontsize=11)
    fig.subplots_adjust(left=0.12, right=0.95, top=0.82, bottom=0.13, wspace=0.32)
    footer(fig, "On-demand NVIDIA T4 only; no Spot, CPU fallback, test evaluation, or extra Vertex job was used to produce this exhibition.")
    return save(fig, "06_vertex_compute_and_budget")


def rounded_box(ax, xy, width, height, text, face, *, fontsize=10, edge=None, lw=1.2):
    edge = edge or face
    box = patches.FancyBboxPatch(
        xy,
        width,
        height,
        boxstyle="round,pad=0.015,rounding_size=0.025",
        facecolor=face,
        edgecolor=edge,
        linewidth=lw,
    )
    ax.add_patch(box)
    ax.text(xy[0] + width / 2, xy[1] + height / 2, text.replace("\\n", "\n"), ha="center", va="center", fontsize=fontsize, color=NAVY)
    return box


def arrow(ax, start, end, text=None, *, color=MUTED):
    ax.annotate("", xy=end, xytext=start, arrowprops=dict(arrowstyle="-|>", lw=1.5, color=color, shrinkA=2, shrinkB=2))
    if text:
        ax.text((start[0] + end[0]) / 2, (start[1] + end[1]) / 2 + 0.018, text, ha="center", va="bottom", fontsize=8.5, color=MUTED)


def fig07_architecture() -> list[Path]:
    fig, ax = plt.subplots(figsize=(13.333, 7.5))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    title(
        fig,
        "CBSC-ZDC: a budgeted stochastic cascade with exact decoding",
        "One neutron four-vector conditions a sparse, nonnegative 6,790-channel calorimeter shower",
    )
    rounded_box(ax, (0.035, 0.67), 0.13, 0.15, "Input\\n$[E,p_x,p_y,p_z]$", "#D6EAF8", fontsize=12)
    rounded_box(ax, (0.205, 0.67), 0.13, 0.15, "Condition encoder\\n5 scaled features\\n128-d context", "#E8F1F8")
    arrow(ax, (0.165, 0.745), (0.205, 0.745))
    xs = [0.39, 0.53, 0.67, 0.81]
    top = [
        ("Visible + response", "Bernoulli +\\n4-component mixture"),
        ("Longitudinal", "first layer + activity\\nprofile flow"),
        ("Multiplicity", "categorical hit count\\nper active layer"),
        ("Geometry support", "3 graph blocks +\\n2-layer Transformer"),
    ]
    for x, (head, sub) in zip(xs, top):
        rounded_box(ax, (x, 0.67), 0.115, 0.15, f"{head}\\n{sub}", "#EAF7F1", fontsize=8.8)
    arrow(ax, (0.335, 0.745), (0.39, 0.745), "context")
    for left, right in zip(xs[:-1], xs[1:]):
        arrow(ax, (left + 0.115, 0.745), (right, 0.745))
    rounded_box(ax, (0.39, 0.37), 0.255, 0.15, "Exact support selection\\nGumbel-Top-$k$: exactly $K_\\ell$ cells\\nwithout replacement", "#FFF3D6")
    rounded_box(ax, (0.695, 0.37), 0.255, 0.15, "Energy-share flow + decoder\\nsoftmax shares × layer budget\\nraw deposited energy", "#FCE8F3")
    arrow(ax, (0.868, 0.67), (0.765, 0.52))
    arrow(ax, (0.645, 0.445), (0.695, 0.445))
    rounded_box(ax, (0.29, 0.10), 0.42, 0.14, "Generated shower $\\hat{Y}\\in\\mathbb{R}_{+}^{6790}$\\n65 layers · 400 ECAL + 6,390 HCAL channels", "#E7E9FC", fontsize=12)
    arrow(ax, (0.822, 0.37), (0.71, 0.24))
    invariants = [
        r"$\#\{i:\hat{Y}_i>0\}=\sum_\ell K_\ell$",
        r"$\sum_{i\in\ell}\hat{Y}_i=D_\ell$",
        r"$\sum_i\hat{Y}_i=T$",
    ]
    ax.text(0.76, 0.17, "Exact by construction", fontsize=10, fontweight="bold", color=PASS)
    for j, text_ in enumerate(invariants):
        ax.text(0.76, 0.135 - j * 0.035, text_, fontsize=9, color=NAVY)
    fig.subplots_adjust(left=0.02, right=0.98, top=0.91, bottom=0.02)
    footer(fig, "Training uses teacher-forced upstream quantities; generation runs the full stochastic cascade freely.")
    return save(fig, "07_model_architecture_and_exact_decoder")


def fig08_data_geometry() -> list[Path]:
    fig, ax = plt.subplots(figsize=(13.333, 7.5))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    title(
        fig,
        "Production data, detector geometry, and the sealed evaluation boundary",
        "Full ROOT conversion and immutable geometry feed train/validation screening; test remains closed",
    )
    boxes = [
        (0.04, "ROOT source\\n764,940 events\\n24.5 GB archived in GCS", "#D6EAF8"),
        (0.24, "Canonical shards\\n187 / 187 verified\\nsparse cell deposits", "#E8F1F8"),
        (0.44, "Frozen split\\n612,482 train\\n76,158 val\\n76,300 test", "#EAF7F1"),
        (0.64, "Screening bank\\n26,624 train\\n6,656 validation\\n0 test", "#FFF3D6"),
        (0.84, "Epoch QA\\nlosses · hashes · reload\\ninvariants · timing", "#FCE8F3"),
    ]
    for x, text_, color in boxes:
        rounded_box(ax, (x, 0.60), 0.145, 0.18, text_, color, fontsize=9.5)
    for a, b in zip(boxes[:-1], boxes[1:]):
        arrow(ax, (a[0] + 0.145, 0.69), (b[0], 0.69))
    ax.text(0.04, 0.48, "Authoritative geometry", fontsize=13, fontweight="bold")
    ax.add_patch(patches.Rectangle((0.04, 0.22), 0.37, 0.18, facecolor=LIGHT, edgecolor=GRID))
    ax.add_patch(patches.Rectangle((0.055, 0.245), 0.09, 0.13, facecolor="#56B4E9", edgecolor="none"))
    for i in range(16):
        x = 0.165 + (i % 8) * 0.027
        y = 0.25 + (i // 8) * 0.06
        ax.add_patch(patches.Rectangle((x, y), 0.019, 0.045, facecolor="#E69F00", alpha=0.55 + 0.02 * i, edgecolor="none"))
    ax.text(0.10, 0.305, "ECAL\n400", ha="center", va="center", color="white", fontweight="bold")
    ax.text(0.275, 0.315, "HCAL · 64 layers\n6,390 channels", ha="center", va="center", fontsize=10)
    ax.text(0.04, 0.18, "65 layers · 6,790 channels · positions in mm · target energy in GeV", fontsize=9.5, color=MUTED)
    rounded_box(ax, (0.49, 0.22), 0.19, 0.18, "Primary claim domain\\n$50\\!\\leq K_{inc}\\!\\leq250$ GeV\\nvalidation-only screening", "#EAF7F1", fontsize=11)
    rounded_box(ax, (0.75, 0.22), 0.19, 0.18, "Final test split\\n76,300 events\\nSEALED", "#FBE8E7", fontsize=11, edge=BLOCK)
    arrow(ax, (0.68, 0.31), (0.75, 0.31), "only after protocol freeze", color=BLOCK)
    fig.subplots_adjust(left=0.02, right=0.98, top=0.90, bottom=0.04)
    footer(fig, "No legacy data and no test events were used for preprocessing, model selection, thresholds, loss weights, or these figures.")
    return save(fig, "08_data_geometry_and_split_contract")


def fig09_claim_boundary() -> list[Path]:
    fig, ax = plt.subplots(figsize=(13.333, 7.5))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    title(
        fig,
        "What the current evidence establishes — and what it does not",
        "A concise claim boundary for deciding whether larger-cluster training is justified",
    )
    rows = [
        ("Structural execution", "PASS", "T4 runtime, real production data, finite gradients, checkpoint reload, invariant checks", PASS),
        ("Optimization continuation", "PASS", "All 4 calibrated families ended below their first completed validation loss", PASS),
        ("Resource feasibility", "PASS", "On-demand T4, 25–62% memory headroom, conservative ledger $48.68 / $100", PASS),
        ("Fixed-sample visual QA", "MIXED", "Some showers look credible; response, hit-count, and profile proxies are non-monotonic", WARN),
        ("Physics validation", "NOT ESTABLISHED", "Conditional distribution agreement, correlations, C2ST, and reconstruction closure not proven", BLOCK),
        ("A100 scale-up gate", "NO-GO", "Frozen screening gate remains closed; lower weighted loss alone is insufficient", BLOCK),
        ("Final test evaluation", "SEALED", "0 test events opened; final protocol and three-seed runs are not complete", BLOCK),
    ]
    y0, row_h = 0.80, 0.092
    for i, (name, status, detail, color) in enumerate(rows):
        y = y0 - i * row_h
        ax.add_patch(patches.Rectangle((0.055, y - 0.055), 0.89, 0.072, facecolor=LIGHT if i % 2 == 0 else "white", edgecolor="none"))
        ax.add_patch(patches.Circle((0.085, y - 0.018), 0.011, facecolor=color, edgecolor="none"))
        ax.text(0.112, y - 0.018, name, va="center", fontweight="bold", fontsize=11)
        ax.text(0.36, y - 0.018, status, va="center", fontweight="bold", fontsize=10, color=color)
        ax.text(0.52, y - 0.018, detail, va="center", fontsize=9, color=MUTED)
    fig.subplots_adjust(left=0.01, right=0.99, top=0.90, bottom=0.04)
    footer(fig, "Scientific integrity permits a negative conclusion. A structural pass must never be relabeled as Geant4 fidelity.")
    return save(fig, "09_evidence_and_claim_boundary")


def common_group(best: dict[str, dict]) -> tuple[int, dict]:
    reference = best["calibrated_lr1e4_halfbatch"]
    candidates = []
    for group in reference["groups"]:
        summary = group["geant4"]["summary"]
        score = abs(group["kinetic_energy_gev"] - 150.0) / 50.0 + abs(summary["hit_count"] - 1700.0) / 1700.0
        candidates.append((score, group["selection_position"], group))
    _, position, group = min(candidates)
    ids = []
    for payload in best.values():
        match = next(g for g in payload["groups"] if g["selection_position"] == position)
        ids.append((match["event_id"], match["global_index"], match["p4_total_gev"]))
    assert all(x == ids[0] for x in ids), ids
    return position, group


def fig10_longitudinal(best: dict[str, dict], position: int) -> list[Path]:
    fig, axes = plt.subplots(2, 2, figsize=(13.333, 7.5), sharex=True)
    group0 = next(g for g in best["calibrated_lr1e4_halfbatch"]["groups"] if g["selection_position"] == position)
    kin = group0["kinetic_energy_gev"]
    title(
        fig,
        "Same incident neutron, five stochastic Fast-MC showers per checkpoint",
        f"Longitudinal energy profile for one fixed validation condition · $K_{{inc}}={kin:.1f}$ GeV · Geant4 reference is identical in every panel",
    )
    for ax, variant in zip(axes.flat, VARIANTS):
        group = next(g for g in best[variant]["groups"] if g["selection_position"] == position)
        truth = np.array(group["geant4"]["summary"]["layer_energy_gev"])
        draws = np.array([x["summary"]["layer_energy_gev"] for x in group["fast_mc"]])
        x = np.arange(65)
        ax.fill_between(x, draws.min(axis=0), draws.max(axis=0), color=COLORS[variant], alpha=0.18, label="Fast MC draw range")
        ax.plot(x, draws.mean(axis=0), color=COLORS[variant], lw=2.0, label="Fast MC mean")
        ax.plot(x, truth, color=NAVY, lw=2.0, ls="--", label="Geant4")
        ax.set_yscale("symlog", linthresh=1e-4)
        ax.set_title(f"{SHORT[variant]} · E{best[variant]['epoch']}", loc="left", fontsize=11)
        ax.set_xlabel("Detector layer")
        ax.set_ylabel("Deposited energy (GeV)")
        clean_axis(ax)
    handles = [
        Line2D([0], [0], color=NAVY, lw=2, ls="--", label="Geant4"),
        Line2D([0], [0], color=COLORS[VARIANTS[0]], lw=2, label="Fast MC mean"),
        patches.Patch(facecolor=COLORS[VARIANTS[0]], alpha=0.18, label="Five-draw range"),
    ]
    fig.legend(handles=handles, loc="upper right", bbox_to_anchor=(0.96, 0.915), frameon=False, ncol=3)
    fig.subplots_adjust(left=0.08, right=0.96, top=0.84, bottom=0.10, hspace=0.31, wspace=0.22)
    footer(fig, "One condition is illustrative, not statistically representative. The five outputs differ because the generator is stochastic.")
    return save(fig, "10_same_condition_longitudinal_profiles")


def fig11_distributions(best: dict[str, dict]) -> list[Path]:
    variant = "calibrated_lr1e4_halfbatch"
    payload = best[variant]
    truth_summaries = [g["geant4"]["summary"] for g in payload["groups"]]
    fast_summaries = [d["summary"] for g in payload["groups"] for d in g["fast_mc"]]
    metrics = [
        ("total_response_gev", "Total detector response", "GeV"),
        ("hit_count", "Positive-cell count", "cells"),
        ("depth_centroid_layer", "Depth centroid", "layer"),
        ("radial_rms_mm", "Radial RMS", "mm"),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(13.333, 7.5))
    title(
        fig,
        "Best current visual family: distribution checks on fixed validation samples",
        r"Calibrated LR $1\times10^{-4}$ half batch · epoch 4 · 50 Geant4 events vs 250 conditional Fast-MC draws",
    )
    for ax, (key, label, unit) in zip(axes.flat, metrics):
        truth = np.array([x[key] for x in truth_summaries], dtype=float)
        fast = np.array([x[key] for x in fast_summaries], dtype=float)
        lo = min(np.percentile(truth, 1), np.percentile(fast, 1))
        hi = max(np.percentile(truth, 99), np.percentile(fast, 99))
        bins = np.linspace(lo, hi, 18)
        ax.hist(truth, bins=bins, density=True, histtype="step", lw=2.2, color=NAVY, label="Geant4")
        ax.hist(fast, bins=bins, density=True, alpha=0.36, color=COLORS[variant], label="Fast MC")
        ax.axvline(np.mean(truth), color=NAVY, ls="--", lw=1.2)
        ax.axvline(np.mean(fast), color=COLORS[variant], ls="-", lw=1.2)
        ax.set_title(label, loc="left", fontsize=11)
        ax.set_xlabel(unit)
        ax.set_ylabel("Density")
        clean_axis(ax)
        ax.text(0.98, 0.94, f"mean: G4 {np.mean(truth):.2f}\nFast {np.mean(fast):.2f}", transform=ax.transAxes, ha="right", va="top", fontsize=8.5, color=MUTED)
    axes[0, 0].legend(frameon=False)
    fig.subplots_adjust(left=0.08, right=0.96, top=0.83, bottom=0.10, hspace=0.33, wspace=0.23)
    footer(fig, "Descriptive validation sample only. Unequal sample counts are shown as density; selection remains fixed across epochs.")
    return save(fig, "11_best_model_sample_distributions")


def sparse_points(deposit: dict, geometry: dict, max_points: int = 1000):
    idx = np.asarray(deposit["cell_index"], dtype=int)
    energy = np.asarray(deposit["energy_gev"], dtype=float)
    if len(idx) > max_points:
        keep = np.argpartition(energy, -max_points)[-max_points:]
        idx, energy = idx[keep], energy[keep]
    pos = np.asarray(geometry["positions_mm"], dtype=float)[idx]
    return pos, energy


def fig12_shower_3d(best: dict[str, dict], geometry: dict, position: int) -> list[Path]:
    variant = "calibrated_lr1e4_halfbatch"
    group = next(g for g in best[variant]["groups"] if g["selection_position"] == position)
    deposits = [group["geant4"]["deposit"]] + [d["deposit"] for d in group["fast_mc"]]
    labels = ["Geant4"] + [f"Fast MC draw {i}" for i in range(1, 6)]
    all_energy = np.concatenate([np.asarray(d["energy_gev"], dtype=float) for d in deposits])
    positive = all_energy[all_energy > 0]
    vmin = max(float(np.percentile(positive, 5)), 1e-7)
    vmax = float(np.percentile(positive, 99.5))
    norm = LogNorm(vmin=vmin, vmax=vmax)
    fig = plt.figure(figsize=(13.333, 7.5))
    title(
        fig,
        "One Geant4 shower and five Fast-MC draws under the same four-momentum",
        f"Best current visual family · epoch {best[variant]['epoch']} · $K_{{inc}}={group['kinetic_energy_gev']:.1f}$ GeV · top 1,000 cells by deposited energy per panel",
    )
    axes = []
    for i, (deposit, label) in enumerate(zip(deposits, labels), start=1):
        ax = fig.add_subplot(2, 3, i, projection="3d")
        axes.append(ax)
        pos, energy = sparse_points(deposit, geometry)
        z = pos[:, 2] - np.min(np.asarray(geometry["positions_mm"])[:, 2])
        size = 4 + 34 * np.sqrt(np.clip(energy / vmax, 0, 1))
        ax.scatter(z, pos[:, 0], pos[:, 1], c=energy, s=size, cmap="viridis", norm=norm, alpha=0.72, linewidths=0, rasterized=True)
        ax.set_title(label, fontsize=10, pad=2)
        ax.set_xlabel("depth", labelpad=-2, fontsize=8)
        ax.set_ylabel("x", labelpad=-2, fontsize=8)
        ax.set_zlabel("y", labelpad=-2, fontsize=8)
        ax.tick_params(labelsize=6, pad=-2)
        ax.view_init(elev=21, azim=-62)
        ax.set_box_aspect((1.8, 1, 1))
        ax.xaxis.pane.set_alpha(0.03)
        ax.yaxis.pane.set_alpha(0.03)
        ax.zaxis.pane.set_alpha(0.03)
    sm = mpl.cm.ScalarMappable(norm=norm, cmap="viridis")
    cbar = fig.colorbar(sm, ax=axes, fraction=0.018, pad=0.02)
    cbar.set_label("Cell deposited energy (GeV, log scale)")
    fig.subplots_adjust(left=0.02, right=0.91, top=0.83, bottom=0.06, hspace=0.02, wspace=-0.05)
    footer(fig, "Sparse display preserves the highest-energy cells for legibility. Axes are detector coordinates in mm; depth is offset from the front face.")
    return save(fig, "12_same_condition_3d_energy_deposits", svg=False)


def make_gallery(files: list[Path]) -> Path:
    cards = []
    for path in sorted(p for p in files if p.suffix == ".png"):
        stem = path.stem
        human = stem.split("_", 1)[1].replace("_", " ").title()
        cards.append(
            f'<figure><a href="figures/{html.escape(path.name)}"><img loading="lazy" src="figures/{html.escape(path.name)}" alt="{html.escape(human)}"></a><figcaption>{html.escape(human)}</figcaption></figure>'
        )
    document = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>CBSC-ZDC exhibition figures</title>
<style>
:root{color-scheme:light;font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;color:#102a43;background:#f4f7fa}
*{box-sizing:border-box}body{margin:0}main{max-width:1480px;margin:auto;padding:48px 28px 64px}
h1{font-size:clamp(30px,4vw,52px);letter-spacing:-.035em;margin:0 0 10px}p{color:#627d98;margin:0 0 34px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,560px),1fr));gap:24px}
figure{margin:0;background:#fff;border:1px solid #d9e2ec}img{width:100%;height:auto;display:block}
figcaption{padding:13px 16px;font-size:14px;font-weight:600;border-top:1px solid #d9e2ec}
a{color:inherit;text-decoration:none}a:focus-visible{outline:3px solid #2f80ed;outline-offset:3px}
</style></head><body><main><h1>CBSC-ZDC model exhibition</h1>
<p>Presentation-ready figures generated from verified training and fixed validation evidence. Physics validation is not established.</p>
<div class="grid">""" + "".join(cards) + "</div></main></body></html>"
    path = HERE / "index.html"
    path.write_text(document, encoding="utf-8")
    return path


def main() -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    style()
    history = read_history()
    terminal = load_json(AUDIT / "compute_extension_20260727_r1_terminal_analysis.json")
    assert terminal["test_events_used"] == 0
    payloads = visualization_payloads()
    best = {variant: load_json(DASH / filename) for variant, filename in BEST_FILES.items()}
    hashes = {p["selection_sha256"] for p in best.values()}
    assert len(hashes) == 1, hashes
    assert all(p["split"] == "validation" and p["sample_count"] == 50 and p["draws_per_condition"] == 5 for p in best.values())
    assert all(p["synthetic_source"] is False for p in best.values())
    geometry = load_json(DASH / "geometry.json")
    assert geometry["n_nodes"] == 6790
    assert len(set(geometry["layer_index"])) == 65
    position, _ = common_group(best)

    generated: list[Path] = []
    generated += fig01_loss_small_multiples(history)
    generated += fig02_validation_comparison(history)
    generated += fig03_component_heatmaps(history)
    generated += fig04_proxy_trajectories(payloads)
    generated += fig05_proxy_change(payloads, history)
    generated += fig06_compute_budget(terminal)
    generated += fig07_architecture()
    generated += fig08_data_geometry()
    generated += fig09_claim_boundary()
    generated += fig10_longitudinal(best, position)
    generated += fig11_distributions(best)
    generated += fig12_shower_3d(best, geometry, position)
    gallery = make_gallery(generated)

    source_files = [
        DATA / "training_history.csv",
        AUDIT / "compute_extension_20260727_r1_terminal_analysis.json",
        DASH / "manifest.json",
        DASH / "geometry.json",
        *[DASH / name for name in BEST_FILES.values()],
    ]
    manifest = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "test_events_used": 0,
        "selected_validation_position": position,
        "selection_sha256": next(iter(hashes)),
        "source_files": [
            {"path": str(path.relative_to(ROOT)).replace("\\", "/"), "bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in source_files
        ],
        "visuals": [
            {"path": str(path.relative_to(HERE)).replace("\\", "/"), "bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in generated
        ],
        "gallery": {"path": gallery.name, "bytes": gallery.stat().st_size, "sha256": sha256(gallery)},
        "qa": {
            "four_loss_series_complete": True,
            "epochs_by_variant": {v: [r["epoch"] for r in history[v]] for v in VARIANTS},
            "all_numeric_values_finite": True,
            "best_payloads_are_validation_only": True,
            "best_payload_sample_contract": "50 conditions x 5 draws",
            "selection_hash_identical_across_best_payloads": True,
            "same_condition_event_identity_identical": True,
            "geometry_nodes": geometry["n_nodes"],
            "geometry_layers": len(set(geometry["layer_index"])),
            "synthetic_source": False,
            "physics_validation": "NOT_ESTABLISHED",
        },
    }
    (HERE / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"visual_count": len(generated), "selected_validation_position": position, "manifest": str(HERE / "manifest.json")}, indent=2))


if __name__ == "__main__":
    main()
