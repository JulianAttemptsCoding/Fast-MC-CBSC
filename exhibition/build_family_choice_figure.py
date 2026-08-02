"""Which calibrated family is worth continuing: the three views that decide it.

Absolute quality, improvement so far, and remaining momentum are different
questions and rank the families differently. Showing only one of them is how a
continuation gets started on the wrong model, so all three are drawn together.

Output goes to exhibition/continuation_20260802/, outside
exhibition/manifest.json, so the 23-visual exhibition contract is untouched.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from build_continuation_loss_figures import (  # noqa: E402
    COLORS, CONTINUATION, NAVY, ORDER, read_history, style,
)

HERE = Path(__file__).resolve().parent
OUT = HERE / "continuation_20260802"

SHORT = {
    "calibrated_lr3e5": r"LR $3\times10^{-5}$",
    "calibrated_lr1e4": r"LR $1\times10^{-4}$",
    "calibrated_lr3e4": r"LR $3\times10^{-4}$",
    "calibrated_lr1e4_halfbatch": r"LR $1\times10^{-4}$ half batch",
}

#: Two runs of the same config on this hardware differed by 0.016 on
#: byte-identical data, so differences below roughly this are not resolvable.
NOISE_FLOOR = 0.02

#: Validation loss of each family's accepted epoch-4 parent, the baseline the
#: six-epoch comparison measured improvement from.
PARENT = {
    "calibrated_lr3e5": 4.897327,
    "calibrated_lr1e4": 4.827105,
    "calibrated_lr3e4": 4.738041,
    "calibrated_lr1e4_halfbatch": 4.845029,
}


def slope_per_epoch(series, last: int = 3) -> float:
    """Average change in validation loss per epoch over the final epochs.

    Negative means still descending. Fitted rather than differenced end to end,
    so one noisy final epoch does not decide it.
    """
    tail = series[-last:]
    x = np.array([r["epoch"] for r in tail], dtype=float)
    y = np.array([r["validation_loss"] for r in tail], dtype=float)
    return float(np.polyfit(x, y, 1)[0])


def build() -> Path:
    style()
    history = read_history()
    fig = plt.figure(figsize=(13.333, 7.5))
    grid = fig.add_gridspec(2, 2, width_ratios=[1.55, 1], height_ratios=[1, 1],
                            left=0.07, right=0.965, top=0.80, bottom=0.10,
                            hspace=0.55, wspace=0.28)
    ax_curves = fig.add_subplot(grid[:, 0])
    ax_final = fig.add_subplot(grid[0, 1])
    ax_slope = fig.add_subplot(grid[1, 1])

    fig.suptitle(
        "Which family is worth continuing: quality, gain, and remaining momentum",
        x=0.02, ha="left", fontsize=17, fontweight="bold", color=NAVY, y=0.975,
    )
    fig.text(
        0.02, 0.945,
        "Validation loss only. The three panels rank the families differently, "
        "which is the point:\nlowest loss, largest gain, and still-falling are "
        "not the same question.",
        ha="left", va="top", fontsize=10.5, color="#4a6178", linespacing=1.5,
    )

    # ---- left: trajectories -------------------------------------------------
    for variant in ORDER:
        series = history[variant]
        base = [r for r in series if r["epoch"] <= 10]
        ax_curves.plot([r["epoch"] for r in base],
                       [r["validation_loss"] for r in base],
                       color=COLORS[variant], marker="o", lw=2.4, ms=5,
                       label=SHORT[variant])
        extra = [r for r in series if r["epoch"] >= 10]
        if len(extra) > 1:
            ax_curves.plot([r["epoch"] for r in extra],
                           [r["validation_loss"] for r in extra],
                           color=COLORS[variant], marker="o", lw=2.0, ms=4.5,
                           ls=":", alpha=0.85)
    ax_curves.axvspan(10.5, 16.5, color="#faf0ee", zorder=0)
    ax_curves.text(13.5, ax_curves.get_ylim()[1], "solo continuation\n(half batch only)",
                   ha="center", va="top", fontsize=9, color="#9a6a72")
    ax_curves.set_xlabel("Completed epoch")
    ax_curves.set_ylabel("Validation loss")
    ax_curves.set_xticks(range(0, 17))
    ax_curves.grid(axis="y", color="#dde5ec", lw=0.9)
    ax_curves.set_axisbelow(True)
    ax_curves.legend(frameon=False, fontsize=9.5, loc="lower left")

    # ---- top right: absolute quality ---------------------------------------
    finals = [(v, history[v][-1]["validation_loss"]) for v in ORDER]
    finals.sort(key=lambda t: t[1])
    ax_final.barh([SHORT[v] for v, _ in finals][::-1],
                  [x for _, x in finals][::-1],
                  color=[COLORS[v] for v, _ in finals][::-1], height=0.6)
    low = min(x for _, x in finals)
    ax_final.set_xlim(low - 0.06, max(x for _, x in finals) + 0.03)
    ax_final.axvline(low, color="#c02f1d", lw=1.2, ls="--")
    ax_final.axvspan(low, low + NOISE_FLOOR, color="#c02f1d", alpha=0.10)
    for index, (variant, value) in enumerate(finals[::-1]):
        ax_final.text(value - 0.004, index, f"{value:.4f}", va="center",
                      ha="right", fontsize=9, color="white", fontweight="bold")
    ax_final.set_title("Latest validation loss — lower is better",
                       loc="left", fontsize=11, fontweight="bold")
    ax_final.set_xlabel("Validation loss")
    ax_final.tick_params(labelsize=9)
    ax_final.grid(axis="x", color="#dde5ec", lw=0.9)
    ax_final.set_axisbelow(True)

    # ---- bottom right: momentum --------------------------------------------
    slopes = [(v, slope_per_epoch(history[v])) for v in ORDER]
    slopes.sort(key=lambda t: t[1])
    ax_slope.barh([SHORT[v] for v, _ in slopes][::-1],
                  [s for _, s in slopes][::-1],
                  color=[COLORS[v] for v, _ in slopes][::-1], height=0.6)
    ax_slope.axvline(0, color=NAVY, lw=1.2)
    for index, (variant, value) in enumerate(slopes[::-1]):
        offset = -0.0012 if value < 0 else 0.0012
        ax_slope.text(value + offset, index, f"{value:+.4f}", va="center",
                      ha="right" if value < 0 else "left", fontsize=9,
                      color=NAVY)
    span = max(abs(s) for _, s in slopes) * 1.9
    ax_slope.set_xlim(-span, span)
    ax_slope.set_title("Trend over final 3 epochs — negative is still falling",
                       loc="left", fontsize=11, fontweight="bold")
    ax_slope.set_xlabel("Change in validation loss per epoch")
    ax_slope.tick_params(labelsize=9)
    ax_slope.grid(axis="x", color="#dde5ec", lw=0.9)
    ax_slope.set_axisbelow(True)

    fig.text(
        0.02, 0.015,
        f"Shaded band on the middle panel is {NOISE_FLOOR:.2f}, the measured "
        "run-to-run resolution: families inside it are not distinguishable. "
        "Pilot bank only; test split unopened.",
        ha="left", fontsize=9.5, color="#6b7f92",
    )

    OUT.mkdir(parents=True, exist_ok=True)
    png = OUT / "family_choice.png"
    fig.savefig(png)
    fig.savefig(OUT / "family_choice.svg")
    plt.close(fig)

    table = {
        variant: {
            "parent_epoch4": PARENT[variant],
            "latest_epoch": history[variant][-1]["epoch"],
            "latest_validation_loss": history[variant][-1]["validation_loss"],
            "best_validation_loss": min(r["validation_loss"] for r in history[variant]),
            "improvement_from_parent": PARENT[variant] - history[variant][-1]["validation_loss"],
            "slope_last_3_epochs": slope_per_epoch(history[variant]),
        }
        for variant in ORDER
    }
    (OUT / "family_choice.json").write_text(
        json.dumps(table, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return png


if __name__ == "__main__":
    print(build())
