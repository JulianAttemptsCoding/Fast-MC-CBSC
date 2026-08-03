"""Every repository metric, plotted against epoch, from the large validation sample.

The published per-epoch payload carries a handful of these from 250 events
(50 conditions x 5 draws). These come from a much larger fixed validation
sample generated alongside training, so the same quantities arrive with error
bars small enough to read a trend from.

Four figures:

  bias_vs_epoch          the nine high-level observables' mean bias, with
                         standard errors and a zero reference
  wasserstein_vs_epoch   the same nine as Wasserstein distances, each against
                         its own truth-half floor -- the distance you get
                         comparing truth to itself, below which a value is not
                         distinguishable from sampling noise
  headline_vs_epoch      classifier two-sample AUROC, normalised response and
                         hit-count Wasserstein, profile L1, zero fractions
  energy_bins_vs_epoch   mean bias and resolution difference per energy bin

Input is `exhibition/data/diagnostics/metrics_epoch_*.json`. Figures are built
to be partial while a run is in flight. Output goes to
exhibition/diagnostics_20260803/, outside exhibition/manifest.json, so the
23-visual exhibition contract is untouched.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
DATA = HERE / "data" / "diagnostics"
OUT = HERE / "diagnostics_20260803"

NAVY = "#0f2a43"
ACCENT = "#d2691e"
FLOOR = "#00a06d"
MUTED = "#6b7f92"
GATE = "#c02f1d"

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


def load() -> list[dict]:
    if not DATA.is_dir():
        return []
    rows = [json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(DATA.glob("metrics_epoch_*.json"))]
    rows.sort(key=lambda r: int(r["epoch"]))
    return rows


def style() -> None:
    plt.rcParams.update({
        "figure.dpi": 160, "savefig.dpi": 160, "font.size": 10,
        "axes.edgecolor": NAVY, "axes.labelcolor": NAVY, "text.color": NAVY,
        "xtick.color": NAVY, "ytick.color": NAVY,
        "axes.spines.top": False, "axes.spines.right": False,
    })


def _finish(fig, epochs, title, subtitle, name) -> Path:
    # Positions in inches converted to figure fractions, not fixed fractions.
    # These figures range from 4.8 to 12 inches tall, and a fraction that
    # looks right on the tall ones puts the subtitle through the title on the
    # short ones.
    height = fig.get_size_inches()[1]
    fig.suptitle(title, x=0.02, ha="left", fontsize=16, fontweight="bold",
                 color=NAVY, y=1 - 0.36 / height)
    fig.text(0.02, 1 - 0.66 / height, subtitle, ha="left", va="top",
             fontsize=9.5, color=MUTED, wrap=True)
    fig.text(0.02, 0.16 / height,
             "Validation split only, zero test events. Descriptive "
             "diagnostics, not a fidelity gate and not Geant4 validation.",
             ha="left", fontsize=9, color=MUTED)
    OUT.mkdir(parents=True, exist_ok=True)
    png = OUT / f"{name}.png"
    fig.savefig(png)
    fig.savefig(OUT / f"{name}.svg")
    plt.close(fig)
    return png


def _layout(fig, **kwargs) -> None:
    """Reserve fixed inch bands for the title block and for the footer plus
    the bottom row's tick labels and axis label."""
    height = fig.get_size_inches()[1]
    fig.subplots_adjust(
        top=1 - 1.10 / height, bottom=0.90 / height, **kwargs
    )


def _ticks(ax, epochs) -> None:
    if len(epochs) <= 14:
        ax.set_xticks(epochs)
    ax.grid(axis="y", color="#dde5ec", lw=0.8)
    ax.set_axisbelow(True)


def bias_figure(rows, epochs, subtitle) -> Path:
    fig, axes = plt.subplots(3, 3, figsize=(13.333, 9.5))
    for ax, (key, label) in zip(axes.ravel(), FEATURES):
        values, errors = [], []
        for r in rows:
            fb = r.get("evaluation", {}).get("feature_bias", {}).get(key)
            values.append(fb["bias_fraction"] if fb else None)
            errors.append(fb["bias_fraction_stderr"] if fb else None)
        pairs = [(e, v, s) for e, v, s in zip(epochs, values, errors) if v is not None]
        if pairs:
            xs, ys, es = zip(*pairs)
            ax.errorbar(xs, ys, yerr=es, color=ACCENT, marker="o", ms=4, lw=1.8,
                        capsize=2.5, ecolor=MUTED, elinewidth=1)
        ax.axhline(0.0, color=NAVY, lw=1, ls=":", zorder=0)
        ax.set_title(label, loc="left", fontsize=11, fontweight="bold")
        ax.set_ylabel("bias fraction")
        _ticks(ax, epochs)
    for ax in axes[-1]:
        ax.set_xlabel("Completed epoch")
    _layout(fig, left=0.07, right=0.98, hspace=0.42, wspace=0.26)
    return _finish(fig, epochs, "Mean bias vs epoch, nine high-level observables",
                   subtitle, "bias_vs_epoch")


def wasserstein_figure(rows, epochs, subtitle) -> Path:
    panels = FEATURES + [("positive_cell_energy_gev", "Positive cell energy")]
    fig, axes = plt.subplots(4, 3, figsize=(13.333, 12))
    for ax, (key, label) in zip(axes.ravel(), panels):
        values, floors = [], []
        for r in rows:
            dm = r.get("evaluation", {}).get("distribution_metrics", {})
            entry = dm.get(key) or {}
            values.append(entry.get("wasserstein"))
            floor = (dm.get("truth_half_floor") or {}).get(key) or {}
            floors.append(floor.get("wasserstein"))
        pairs = [(e, v) for e, v in zip(epochs, values) if v is not None]
        if pairs:
            xs, ys = zip(*pairs)
            ax.plot(xs, ys, color=ACCENT, marker="o", ms=4, lw=1.8,
                    label="Fast-MC vs Geant4")
        fpairs = [(e, v) for e, v in zip(epochs, floors) if v is not None]
        if fpairs:
            fxs, fys = zip(*fpairs)
            ax.plot(fxs, fys, color=FLOOR, lw=1.6, ls="--",
                    label="truth-half floor")
        ax.set_title(label, loc="left", fontsize=11, fontweight="bold")
        ax.set_ylabel("Wasserstein")
        _ticks(ax, epochs)
    for ax in axes.ravel()[len(panels):]:
        ax.axis("off")
    axes.ravel()[0].legend(loc="best", frameon=False, fontsize=8.5)
    for ax in axes[-1]:
        ax.set_xlabel("Completed epoch")
    _layout(fig, left=0.07, right=0.98, hspace=0.45, wspace=0.26)
    return _finish(
        fig, epochs, "Wasserstein distance vs epoch, against the truth-half floor",
        subtitle + "  Dashed green = truth vs itself; at or below it is "
        "indistinguishable from sampling noise.",
        "wasserstein_vs_epoch",
    )


def headline_figure(rows, epochs, subtitle) -> Path:
    fig, axes = plt.subplots(2, 3, figsize=(13.333, 7))
    ax = axes[0][0]
    values = [r.get("evaluation", {}).get("high_level_c2st_auc") for r in rows]
    pairs = [(e, v) for e, v in zip(epochs, values) if v is not None]
    if pairs:
        xs, ys = zip(*pairs)
        ax.plot(xs, ys, color=ACCENT, marker="o", ms=4, lw=1.8)
    ax.axhline(0.5, color=FLOOR, lw=1.6, ls="--")
    ax.axhline(0.65, color=GATE, lw=1.2, ls=":")
    ax.set_title("Classifier two-sample AUROC", loc="left", fontsize=11,
                 fontweight="bold")
    ax.set_ylabel("AUROC")
    ax.text(0.02, 0.06, "0.5 = indistinguishable", transform=ax.transAxes,
            fontsize=8, color=FLOOR)
    _ticks(ax, epochs)

    simple = [
        (axes[0][1], "response_wasserstein_normalized",
         "Response Wasserstein / sigma", 0.15),
        (axes[0][2], "hit_count_wasserstein_normalized",
         "Hit-count Wasserstein / sigma", 0.15),
    ]
    for ax, key, label, gate in simple:
        values = [r.get("evaluation", {}).get(key) for r in rows]
        pairs = [(e, v) for e, v in zip(epochs, values) if v is not None]
        if pairs:
            xs, ys = zip(*pairs)
            ax.plot(xs, ys, color=ACCENT, marker="o", ms=4, lw=1.8)
        ax.axhline(gate, color=GATE, lw=1.2, ls=":")
        ax.set_title(label, loc="left", fontsize=11, fontweight="bold")
        _ticks(ax, epochs)

    ax = axes[1][0]
    values = [r["trend"]["mean_longitudinal_profile_relative_l1"] for r in rows]
    ax.plot(epochs, values, color=ACCENT, marker="o", ms=4, lw=1.8)
    ax.set_title("Longitudinal profile relative L1", loc="left", fontsize=11,
                 fontweight="bold")
    _ticks(ax, epochs)

    ax = axes[1][1]
    for key, colour, label in (
        ("truth_zero_fraction", NAVY, "Geant4"),
        ("generated_zero_fraction", ACCENT, "Fast-MC"),
    ):
        values = [r.get("evaluation", {}).get(key) for r in rows]
        pairs = [(e, v) for e, v in zip(epochs, values) if v is not None]
        if pairs:
            xs, ys = zip(*pairs)
            ax.plot(xs, ys, color=colour, marker="o", ms=4, lw=1.8, label=label)
    ax.set_title("Zero-response fraction", loc="left", fontsize=11,
                 fontweight="bold")
    ax.legend(frameon=False, fontsize=8.5)
    _ticks(ax, epochs)

    ax = axes[1][2]
    values = [r["trend"]["response_bias_fraction"] for r in rows]
    errors = [r.get("trend_stderr", {}).get("response_bias_fraction") for r in rows]
    if all(e is not None for e in errors):
        ax.errorbar(epochs, values, yerr=errors, color=ACCENT, marker="o", ms=4,
                    lw=1.8, capsize=2.5, ecolor=MUTED, elinewidth=1)
    else:
        ax.plot(epochs, values, color=ACCENT, marker="o", ms=4, lw=1.8)
    ax.axhline(0.0, color=NAVY, lw=1, ls=":", zorder=0)
    ax.set_title("Total response bias", loc="left", fontsize=11,
                 fontweight="bold")
    _ticks(ax, epochs)

    for ax in axes[-1]:
        ax.set_xlabel("Completed epoch")
    _layout(fig, left=0.07, right=0.98, hspace=0.45, wspace=0.26)
    return _finish(fig, epochs, "Headline distribution metrics vs epoch",
                   subtitle + "  Dotted red = predeclared threshold.",
                   "headline_vs_epoch")


def energy_bin_figure(rows, epochs, subtitle) -> Path | None:
    bins = rows[-1].get("evaluation", {}).get("response_bins")
    if not bins:
        return None
    fig, axes = plt.subplots(1, 2, figsize=(13.333, 4.8))
    colours = plt.cm.viridis([i / max(len(bins) - 1, 1) for i in range(len(bins))])
    for key, ax, label, gate in (
        ("mean_bias_fraction", axes[0], "Mean response bias per energy bin", 0.05),
        ("resolution_difference_fraction", axes[1],
         "Resolution difference per energy bin", 0.10),
    ):
        for index, colour in enumerate(colours):
            # NaN rather than a skipped point: an absent bin must break the
            # line visibly instead of being interpolated across, which would
            # hide that a bin was empty at that epoch.
            series = []
            for row in rows:
                rb = row.get("evaluation", {}).get("response_bins")
                value = None
                if rb and index < len(rb):
                    value = rb[index].get(key)
                series.append(float("nan") if value is None else value)
            if not all(v != v for v in series):
                edge = bins[index]
                ax.plot(epochs, series, color=colour, marker="o", ms=3, lw=1.5,
                        label=f"{edge['low']:.0f}-{edge['high']:.0f} GeV")
        ax.axhline(0.0, color=NAVY, lw=1, ls=":", zorder=0)
        ax.axhline(gate, color=GATE, lw=1, ls=":")
        ax.axhline(-gate, color=GATE, lw=1, ls=":")
        ax.set_title(label, loc="left", fontsize=11, fontweight="bold")
        ax.set_xlabel("Completed epoch")
        _ticks(ax, epochs)
    axes[0].legend(frameon=False, fontsize=7.5, ncol=2)
    _layout(fig, left=0.06, right=0.98, wspace=0.20)
    return _finish(fig, epochs, "Energy-resolved response vs epoch",
                   subtitle + "  Dotted red = predeclared thresholds.",
                   "energy_bins_vs_epoch")


def build() -> list[Path]:
    rows = load()
    if not rows:
        print("no diagnostic metrics yet")
        return []
    style()
    epochs = [int(r["epoch"]) for r in rows]
    latest = rows[-1]
    subtitle = (
        f"calibrated_lr1e4 continuation (dicos-p8). "
        f"{latest['n_events']:,} fixed validation events per epoch, drawn from a "
        f"{latest['validation_pool']:,}-event pool, against the site's 250."
    )

    produced = [
        bias_figure(rows, epochs, subtitle),
        wasserstein_figure(rows, epochs, subtitle),
        headline_figure(rows, epochs, subtitle),
    ]
    energy = energy_bin_figure(rows, epochs, subtitle)
    if energy:
        produced.append(energy)

    summary = {
        "epochs": epochs,
        "n_events_per_epoch": latest["n_events"],
        "validation_pool": latest["validation_pool"],
        "kinetic_range_gev": latest["kinetic_range_gev"],
        "selection_seed": latest["selection_seed"],
        "test_events_used": 0,
        "high_level_c2st_auc": [
            r.get("evaluation", {}).get("high_level_c2st_auc") for r in rows
        ],
        "trend": {
            key: [r["trend"][key] for r in rows]
            for key in latest["trend"]
        },
        "feature_bias_fraction": {
            key: [
                r.get("evaluation", {}).get("feature_bias", {})
                 .get(key, {}).get("bias_fraction")
                for r in rows
            ]
            for key, _ in FEATURES
        },
        "figures": [p.name for p in produced],
    }
    (OUT / "diagnostic_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return produced


if __name__ == "__main__":
    for path in build():
        print(path)
