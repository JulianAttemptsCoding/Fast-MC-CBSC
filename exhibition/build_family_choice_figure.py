"""Accepted family standings and recent within-family validation trends.

This figure is deliberately descriptive.  It separates accepted checkpoints
from quarantined observations and never turns a short-window slope into a
cross-family selection rule.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from build_continuation_loss_figures import (  # noqa: E402
    COLORS,
    NAVY,
    ORDER,
    _thinned_ticks,
    read_history,
    save_png_atomic,
    save_svg_clean,
    style,
    write_json_atomic,
)

HERE = Path(__file__).resolve().parent
OUT = HERE / "continuation_20260802"

SHORT = {
    "calibrated_lr3e5": r"LR $3\times10^{-5}$",
    "calibrated_lr1e4": r"LR $1\times10^{-4}$",
    "calibrated_lr3e4": r"LR $3\times10^{-4}$",
    "calibrated_lr1e4_halfbatch": r"LR $1\times10^{-4}$ half batch",
}

# Two same-configuration runs differed by 0.016 on byte-identical data.
# A 0.02 band is therefore descriptive measurement resolution, not a gate.
NOISE_FLOOR = 0.02


def accepted(series: list[dict]) -> list[dict]:
    return [row for row in series if row.get("status", "accepted") == "accepted"]


def slope_per_epoch(series: list[dict], last: int = 3) -> float:
    """Least-squares slope over the final accepted observations."""
    tail = series[-last:]
    if len(tail) < 2:
        return 0.0
    x = np.asarray([row["epoch"] for row in tail], dtype=float)
    y = np.asarray([row["validation_loss"] for row in tail], dtype=float)
    return float(np.polyfit(x, y, 1)[0])


def build() -> Path:
    style()
    history, _continuation = read_history()
    fig = plt.figure(figsize=(13.333, 7.5))
    grid = fig.add_gridspec(
        2,
        2,
        width_ratios=[1.55, 1],
        height_ratios=[1, 1],
        left=0.07,
        right=0.965,
        top=0.80,
        bottom=0.14,
        hspace=0.58,
        wspace=0.30,
    )
    ax_curves = fig.add_subplot(grid[:, 0])
    ax_best = fig.add_subplot(grid[0, 1])
    ax_slope = fig.add_subplot(grid[1, 1])

    fig.suptitle(
        "Current accepted standings and recent within-family trend",
        x=0.02,
        ha="left",
        fontsize=17,
        fontweight="bold",
        color=NAVY,
        y=0.975,
    )
    fig.text(
        0.02,
        0.945,
        "Validation loss only. Best and slope panels exclude quarantined checkpoints; "
        "all observed points remain visible at left.\nRecent slope describes each "
        "family's own final three accepted epochs and is not a cross-family gate.",
        ha="left",
        va="top",
        fontsize=10.5,
        color="#4a6178",
        linespacing=1.5,
    )

    all_epochs = sorted(
        {int(row["epoch"]) for series in history.values() for row in series}
    )
    for variant in ORDER:
        series = history[variant]
        xs = [row["epoch"] for row in series]
        ys = [row["validation_loss"] for row in series]
        ax_curves.plot(
            xs,
            ys,
            color=COLORS[variant],
            marker="o",
            lw=2.1,
            ms=4.5,
            label=SHORT[variant],
        )
        rejected = [row for row in series if row.get("status") == "quarantined"]
        if rejected:
            ax_curves.scatter(
                [row["epoch"] for row in rejected],
                [row["validation_loss"] for row in rejected],
                marker="x",
                s=95,
                linewidths=2.3,
                color="#7b2cbf",
                zorder=6,
            )
    ax_curves.set_xlabel("Completed epoch")
    ax_curves.set_ylabel("Validation loss")
    ax_curves.set_xticks(_thinned_ticks(all_epochs))
    ax_curves.set_xlim(min(all_epochs) - 0.6, max(all_epochs) + 0.6)
    ax_curves.grid(axis="y", color="#dde5ec", lw=0.9)
    ax_curves.set_axisbelow(True)
    ax_curves.legend(frameon=False, fontsize=9, loc="lower left")

    best_rows = []
    slope_rows = []
    for variant in ORDER:
        valid = accepted(history[variant])
        best = min(valid, key=lambda row: row["validation_loss"])
        best_rows.append((variant, best))
        slope_rows.append((variant, slope_per_epoch(valid)))

    best_rows.sort(key=lambda pair: pair[1]["validation_loss"])
    labels = [SHORT[variant] for variant, _ in best_rows][::-1]
    values = [row["validation_loss"] for _, row in best_rows][::-1]
    colors = [COLORS[variant] for variant, _ in best_rows][::-1]
    ax_best.barh(labels, values, color=colors, height=0.6)
    low = min(values)
    high = max(values)
    ax_best.set_xlim(low - 0.06, high + 0.035)
    ax_best.axvline(low, color="#c02f1d", lw=1.2, ls="--")
    ax_best.axvspan(low, low + NOISE_FLOOR, color="#c02f1d", alpha=0.10)
    for index, value in enumerate(values):
        ax_best.text(
            value - 0.004,
            index,
            f"{value:.4f}",
            va="center",
            ha="right",
            fontsize=9,
            color="white",
            fontweight="bold",
        )
    ax_best.set_title(
        "Best accepted validation loss — lower is better",
        loc="left",
        fontsize=11,
        fontweight="bold",
    )
    ax_best.set_xlabel("Validation loss")
    ax_best.tick_params(labelsize=9)
    ax_best.grid(axis="x", color="#dde5ec", lw=0.9)
    ax_best.set_axisbelow(True)

    slope_rows.sort(key=lambda pair: pair[1])
    labels = [SHORT[variant] for variant, _ in slope_rows][::-1]
    values = [value for _, value in slope_rows][::-1]
    colors = [COLORS[variant] for variant, _ in slope_rows][::-1]
    ax_slope.barh(labels, values, color=colors, height=0.6)
    ax_slope.axvline(0, color=NAVY, lw=1.2)
    for index, value in enumerate(values):
        offset = -0.0012 if value < 0 else 0.0012
        ax_slope.text(
            value + offset,
            index,
            f"{value:+.4f}",
            va="center",
            ha="right" if value < 0 else "left",
            fontsize=9,
            color=NAVY,
        )
    span = max(max(abs(value) for value in values) * 1.9, 0.004)
    ax_slope.set_xlim(-span, span)
    ax_slope.set_title(
        "Final 3 accepted epochs — negative is descending",
        loc="left",
        fontsize=11,
        fontweight="bold",
    )
    ax_slope.set_xlabel("Validation-loss change per epoch")
    ax_slope.tick_params(labelsize=9)
    ax_slope.grid(axis="x", color="#dde5ec", lw=0.9)
    ax_slope.set_axisbelow(True)

    fig.text(
        0.02,
        0.018,
        f"Red band = {NOISE_FLOOR:.2f} measured run-to-run resolution, not a "
        "selection threshold. Purple × = quarantined QA failure.\nTraining and "
        "selection used zero test events; historical isolated test studies are "
        "documented separately.",
        ha="left",
        fontsize=8.8,
        color="#6b7f92",
        linespacing=1.35,
    )

    OUT.mkdir(parents=True, exist_ok=True)
    png = OUT / "family_choice.png"
    save_png_atomic(fig, png)
    save_svg_clean(fig, OUT / "family_choice.svg")
    plt.close(fig)

    table = {"schema_version": 2, "noise_resolution": NOISE_FLOOR, "families": {}}
    for variant in ORDER:
        series = history[variant]
        valid = accepted(series)
        best = min(valid, key=lambda row: row["validation_loss"])
        latest_accepted = valid[-1]
        latest_observed = series[-1]
        table["families"][variant] = {
            "best_accepted_epoch": best["epoch"],
            "best_accepted_run_tag": best.get("run_tag"),
            "best_accepted_validation_loss": best["validation_loss"],
            "latest_accepted_epoch": latest_accepted["epoch"],
            "latest_accepted_validation_loss": latest_accepted["validation_loss"],
            "latest_observed_epoch": latest_observed["epoch"],
            "latest_observed_validation_loss": latest_observed["validation_loss"],
            "latest_observed_status": latest_observed.get("status", "accepted"),
            "slope_final_3_accepted_epochs": slope_per_epoch(valid),
            "quarantined_epochs": [
                row["epoch"] for row in series if row.get("status") == "quarantined"
            ],
        }
    write_json_atomic(OUT / "family_choice.json", table)
    return png


if __name__ == "__main__":
    print(build())
