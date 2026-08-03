"""Per-epoch large-sample validation diagnostics for the running continuation.

The published per-epoch payload carries these same quantities from 250 events
(50 conditions x 5 draws). These come from a much larger fixed validation
sample generated alongside training, so the same numbers arrive with error
bars small enough to read a trend from.

Input is whatever `_diag/metrics_epoch_*.json` files have been pulled off the
host into `exhibition/data/diagnostics/`. The figure is rebuilt as epochs
land, so it is expected to be partial while a run is in flight.

Output goes to exhibition/diagnostics_20260803/, outside
exhibition/manifest.json, so the 23-visual exhibition contract is untouched.
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
MUTED = "#6b7f92"


def load() -> list[dict]:
    if not DATA.is_dir():
        return []
    rows = []
    for path in sorted(DATA.glob("metrics_epoch_*.json")):
        rows.append(json.loads(path.read_text(encoding="utf-8")))
    rows.sort(key=lambda r: int(r["epoch"]))
    return rows


def style() -> None:
    plt.rcParams.update({
        "figure.dpi": 160, "savefig.dpi": 160, "font.size": 11,
        "axes.edgecolor": NAVY, "axes.labelcolor": NAVY, "text.color": NAVY,
        "xtick.color": NAVY, "ytick.color": NAVY,
        "axes.spines.top": False, "axes.spines.right": False,
    })


def build() -> Path | None:
    rows = load()
    if not rows:
        print("no diagnostic metrics yet")
        return None

    style()
    epochs = [int(r["epoch"]) for r in rows]
    n_events = rows[-1]["n_events"]

    panels = [
        ("response_bias_fraction", "Total response bias", True),
        ("hit_count_bias_fraction", "Hit-count bias", True),
        ("mean_longitudinal_profile_relative_l1",
         "Longitudinal profile relative L1", False),
    ]

    fig, axes = plt.subplots(1, 3, figsize=(13.333, 4.4))
    fig.suptitle(
        "Validation diagnostics per epoch, from a larger fixed sample",
        x=0.02, ha="left", fontsize=16, fontweight="bold", color=NAVY, y=0.98,
    )
    fig.text(
        0.02, 0.90,
        f"calibrated_lr1e4 continuation (dicos-p8). {n_events:,} fixed "
        f"validation events per epoch, against the site's 250. "
        f"Error bars are the standard error of the mean.",
        ha="left", va="top", fontsize=10, color=MUTED,
    )

    for ax, (key, label, zero_line) in zip(axes, panels):
        values = [r["trend"][key] for r in rows]
        errors = [r.get("trend_stderr", {}).get(key) for r in rows]
        if all(e is not None for e in errors):
            ax.errorbar(epochs, values, yerr=errors, color=ACCENT, marker="o",
                        ms=5, lw=2, capsize=3, ecolor=MUTED, elinewidth=1.2)
        else:
            ax.plot(epochs, values, color=ACCENT, marker="o", ms=5, lw=2)
        if zero_line:
            ax.axhline(0.0, color=NAVY, lw=1, ls=":", zorder=0)
        ax.set_title(label, loc="left", fontsize=12, fontweight="bold")
        ax.set_xlabel("Completed epoch")
        ax.grid(axis="y", color="#dde5ec", lw=0.9)
        ax.set_axisbelow(True)
        if len(epochs) <= 14:
            ax.set_xticks(epochs)

    fig.subplots_adjust(left=0.06, right=0.98, top=0.72, bottom=0.16, wspace=0.26)
    fig.text(
        0.02, 0.02,
        "Validation split only, zero test events. Descriptive diagnostics, "
        "not a fidelity gate and not Geant4 validation.",
        ha="left", fontsize=9.5, color=MUTED,
    )

    OUT.mkdir(parents=True, exist_ok=True)
    png = OUT / "diagnostic_trend.png"
    fig.savefig(png)
    fig.savefig(OUT / "diagnostic_trend.svg")
    plt.close(fig)

    summary = {
        "epochs": epochs,
        "n_events_per_epoch": n_events,
        "validation_pool": rows[-1]["validation_pool"],
        "kinetic_range_gev": rows[-1]["kinetic_range_gev"],
        "selection_seed": rows[-1]["selection_seed"],
        "test_events_used": 0,
        "series": {
            key: [r["trend"][key] for r in rows] for key, _, _ in panels
        },
        "stderr": {
            key: [r.get("trend_stderr", {}).get(key) for r in rows]
            for key, _, _ in panels
            if any(r.get("trend_stderr", {}).get(key) is not None for r in rows)
        },
    }
    (OUT / "diagnostic_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return png


if __name__ == "__main__":
    print(build())
