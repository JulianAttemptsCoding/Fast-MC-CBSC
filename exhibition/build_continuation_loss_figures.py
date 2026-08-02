"""Per-family loss graphs covering every epoch actually run.

The exhibition's own figures compare the four families over an identical epoch
range, which is what makes them comparable -- so they stop at epoch 10. This
builds the complementary view: one panel per family showing its whole training
history, including the solo continuation that only one family has.

Output goes to exhibition/continuation_20260802/, deliberately outside
exhibition/manifest.json, so the 23-visual exhibition contract is untouched.
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
OUT = HERE / "continuation_20260802"

NAVY = "#0f2a43"
COLORS = {
    "calibrated_lr3e5": "#0f7fbf",
    "calibrated_lr1e4": "#00a06d",
    "calibrated_lr3e4": "#d2691e",
    "calibrated_lr1e4_halfbatch": "#cc7fa8",
}
LABELS = {
    "calibrated_lr3e5": r"Calibrated $\cdot$ LR $3\times10^{-5}$",
    "calibrated_lr1e4": r"Calibrated $\cdot$ LR $1\times10^{-4}$",
    "calibrated_lr3e4": r"Calibrated $\cdot$ LR $3\times10^{-4}$",
    "calibrated_lr1e4_halfbatch": r"Calibrated $\cdot$ LR $1\times10^{-4}$ $\cdot$ half batch",
}
ORDER = ["calibrated_lr3e5", "calibrated_lr1e4", "calibrated_lr3e4",
         "calibrated_lr1e4_halfbatch"]

#: Epochs 11-16 of calibrated_lr1e4_halfbatch: the solo continuation
#: (dicos-final-r2), six epochs of a fresh cosine anneal from the epoch-10
#: checkpoint. It ended at 4.715659, which does NOT beat the epoch-10 best of
#: 4.710829.
#:
#: An earlier attempt (dicos-final) covered epochs 11-13 under patience 3 and
#: was stopped without improving; it is deliberately not plotted, because it
#: occupies the same epoch numbers and two series at one epoch would misread as
#: contradictory data rather than as one superseded run.
CONTINUATION = {
    "calibrated_lr1e4_halfbatch": [
        {"epoch": 11, "train_loss": 4.909868, "validation_loss": 4.785943},
        {"epoch": 12, "train_loss": 4.878609, "validation_loss": 4.765122},
        {"epoch": 13, "train_loss": 4.859714, "validation_loss": 4.755307},
        {"epoch": 14, "train_loss": 4.805463, "validation_loss": 4.757107},
        {"epoch": 15, "train_loss": 4.789202, "validation_loss": 4.722938},
        {"epoch": 16, "train_loss": 4.772677, "validation_loss": 4.715659},
    ]
}

#: Where each phase's epochs came from, for the shaded bands.
PHASES = [(0, 4, "T4 / Vertex", "#f2f5f8"), (5, 10, "RTX 4090 / DiCOS", "#eef3ee")]


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
    })


def read_history() -> dict[str, list[dict[str, float]]]:
    rows: dict[str, list[dict[str, float]]] = {}
    path = ROOT / "exhibition" / "data" / "training_history.csv"
    with path.open(newline="", encoding="utf-8") as stream:
        for raw in csv.DictReader(stream):
            variant = raw["variant"]
            rows.setdefault(variant, []).append({
                "epoch": int(raw["epoch"]),
                "train_loss": float(raw["train_loss"]),
                "validation_loss": float(raw["validation_loss"]),
            })
    for variant, series in rows.items():
        series.extend(CONTINUATION.get(variant, []))
        series.sort(key=lambda r: r["epoch"])
        seen = [r["epoch"] for r in series]
        if len(seen) != len(set(seen)):
            raise ValueError(f"{variant}: duplicate epoch in history {seen}")
    return rows


def build() -> Path:
    style()
    history = read_history()
    fig, axes = plt.subplots(2, 2, figsize=(13.333, 7.5))
    fig.suptitle(
        "Loss across every epoch run, for all four calibrated families",
        x=0.02, ha="left", fontsize=17, fontweight="bold", color=NAVY, y=0.975,
    )
    fig.text(
        0.02, 0.945,
        "Solid = training, dashed = validation. Epochs 0-4 on T4, 5-10 on the "
        "RTX 4090.\nOnly the half-batch family has 11-16, its solo "
        "continuation: it ended at 4.7157 and did not beat its epoch-10 best "
        "of 4.7108.",
        ha="left", va="top", fontsize=10.5, color="#4a6178", linespacing=1.5,
    )

    for ax, variant in zip(axes.ravel(), ORDER):
        series = history[variant]
        epochs = [r["epoch"] for r in series]
        train = [r["train_loss"] for r in series]
        validation = [r["validation_loss"] for r in series]

        for start, stop, _label, shade in PHASES:
            ax.axvspan(start - 0.5, stop + 0.5, color=shade, zorder=0)
        if variant in CONTINUATION:
            ax.axvspan(10.5, 16.5, color="#faf0ee", zorder=0)

        ax.plot(epochs, train, color=COLORS[variant], marker="o", lw=2.2, ms=5,
                label="Training")
        ax.plot(epochs, validation, color=NAVY, marker="s", lw=2.2, ms=4.5,
                ls="--", label="Validation")

        best = min(series, key=lambda r: r["validation_loss"])
        ax.scatter([best["epoch"]], [best["validation_loss"]], s=150,
                   facecolors="none", edgecolors="#c02f1d", lw=2, zorder=5)
        # Above the marker, not below: below collides with the x tick labels,
        # which made the value unreadable.
        ax.annotate(
            f"best {best['validation_loss']:.4f} @ e{best['epoch']}",
            (best["epoch"], best["validation_loss"]),
            xytext=(0, 16), textcoords="offset points",
            ha="center", fontsize=9, color="#c02f1d",
            bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="none", alpha=0.85),
        )

        ax.set_title(LABELS[variant], loc="left", fontsize=12, fontweight="bold")
        ax.set_xlabel("Completed epoch")
        ax.set_ylabel("Weighted joint loss")
        ax.set_xticks(epochs)
        ax.set_xlim(min(epochs) - 0.6, max(epochs) + 0.6)
        ax.grid(axis="y", color="#dde5ec", lw=0.9)
        ax.set_axisbelow(True)

    axes.ravel()[0].legend(loc="upper right", frameon=False, fontsize=10)
    fig.subplots_adjust(left=0.07, right=0.97, top=0.835, bottom=0.09,
                        hspace=0.42, wspace=0.20)
    fig.text(
        0.02, 0.015,
        "Lower is better for this frozen weighted objective. Pilot bank only "
        "(26,624 train / 6,656 validation); the test split is unopened. "
        "Optimization evidence, not Geant4 fidelity.",
        ha="left", fontsize=9.5, color="#6b7f92",
    )

    OUT.mkdir(parents=True, exist_ok=True)
    png = OUT / "loss_all_families_every_epoch.png"
    fig.savefig(png)
    fig.savefig(OUT / "loss_all_families_every_epoch.svg")
    plt.close(fig)

    summary = {
        variant: {
            "epochs": [r["epoch"] for r in series],
            "final_validation_loss": series[-1]["validation_loss"],
            "best_validation_loss": min(r["validation_loss"] for r in series),
            "best_epoch": min(series, key=lambda r: r["validation_loss"])["epoch"],
        }
        for variant, series in history.items()
    }
    (OUT / "loss_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return png


if __name__ == "__main__":
    print(build())
