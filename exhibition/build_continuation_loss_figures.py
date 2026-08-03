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

#: Epochs beyond 10 live in their own CSV rather than in this file, and are
#: copied verbatim from each run's own `logs/history.csv` at full precision.
#: They are deliberately NOT in `exhibition/data/training_history.csv`, because
#: `build_exhibition.py` asserts that every variant there has exactly epochs
#: 0..10 -- appending would break the 23-visual exhibition contract.
#:
#: Superseded attempts are excluded: `dicos-final` covered epochs 11-13 under
#: patience 3 and was stopped without improving. It occupies the same epoch
#: numbers as `dicos-final-r2`, and two series at one epoch would read as
#: contradictory data rather than as one abandoned run.
CONTINUATION_CSV = ROOT / "exhibition" / "data" / "continuation_history.csv"

#: Where each phase's epochs came from, for the shaded bands. Epochs past 10
#: are shaded per family from the data, since families now diverge in both
#: epoch range and GPU.
PHASES = [(0, 4, "T4 / Vertex", "#f2f5f8"), (5, 10, "RTX 4090 / DiCOS", "#eef3ee")]
CONTINUATION_SHADE = "#faf0ee"


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


def read_continuation() -> dict[str, list[dict[str, float]]]:
    """Epochs past 10, per family, from each run's own history.csv."""
    rows: dict[str, list[dict[str, float]]] = {}
    if not CONTINUATION_CSV.is_file():
        return rows
    with CONTINUATION_CSV.open(newline="", encoding="utf-8") as stream:
        for raw in csv.DictReader(stream):
            rows.setdefault(raw["variant"], []).append({
                "epoch": int(raw["epoch"]),
                "train_loss": float(raw["train_loss"]),
                "validation_loss": float(raw["validation_loss"]),
                "run_tag": raw["run_tag"],
            })
    return rows


def read_history() -> tuple[
    dict[str, list[dict[str, float]]], dict[str, list[dict[str, float]]]
]:
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
    continuation = read_continuation()
    for variant, series in rows.items():
        series.extend(continuation.get(variant, []))
        series.sort(key=lambda r: r["epoch"])
        seen = [r["epoch"] for r in series]
        if len(seen) != len(set(seen)):
            raise ValueError(f"{variant}: duplicate epoch in history {seen}")
        # A gap would silently draw a straight line across epochs that were
        # never run, which reads as training that did not happen.
        if seen != list(range(seen[0], seen[-1] + 1)):
            raise ValueError(f"{variant}: non-contiguous epochs {seen}")
    return rows, continuation


def build() -> Path:
    style()
    history, continuation = read_history()
    fig, axes = plt.subplots(2, 2, figsize=(13.333, 7.5))
    fig.suptitle(
        "Loss across every epoch run, for all four calibrated families",
        x=0.02, ha="left", fontsize=17, fontweight="bold", color=NAVY, y=0.975,
    )
    fig.text(
        0.02, 0.945,
        "Solid = training, dashed = validation. Epochs 0-4 on T4, 5-10 on the "
        "RTX 4090; the shaded tail is each family's own continuation.\n"
        "Families differ in how far they were continued and on which GPU, so "
        "the tails are NOT a like-for-like comparison across panels.",
        ha="left", va="top", fontsize=10.5, color="#4a6178", linespacing=1.5,
    )

    for ax, variant in zip(axes.ravel(), ORDER):
        series = history[variant]
        epochs = [r["epoch"] for r in series]
        train = [r["train_loss"] for r in series]
        validation = [r["validation_loss"] for r in series]

        for start, stop, _label, shade in PHASES:
            ax.axvspan(start - 0.5, stop + 0.5, color=shade, zorder=0)
        tail = continuation.get(variant, [])
        if tail:
            tail_epochs = [r["epoch"] for r in tail]
            ax.axvspan(min(tail_epochs) - 0.5, max(tail_epochs) + 0.5,
                       color=CONTINUATION_SHADE, zorder=0)

        ax.plot(epochs, train, color=COLORS[variant], marker="o", lw=2.2, ms=5,
                label="Training")
        ax.plot(epochs, validation, color=NAVY, marker="s", lw=2.2, ms=4.5,
                ls="--", label="Validation")

        best = min(series, key=lambda r: r["validation_loss"])
        ax.scatter([best["epoch"]], [best["validation_loss"]], s=150,
                   facecolors="none", edgecolors="#c02f1d", lw=2, zorder=5)
        # Placed BELOW the marker, into headroom opened for it just below.
        # Above was tried and occludes the training curve: the best point is a
        # minimum, so both its neighbours sit above it and a label there lands
        # on the line. Below the minimum is the only guaranteed-empty region.
        # (An earlier version put it below without the headroom, where it
        # collided with the x tick labels instead.)
        low = min(min(train), min(validation))
        high = max(max(train), max(validation))
        span = max(high - low, 1e-9)
        ax.set_ylim(low - 0.20 * span, high + 0.08 * span)
        ax.annotate(
            f"best {best['validation_loss']:.4f} @ e{best['epoch']}",
            (best["epoch"], best["validation_loss"]),
            xytext=(0, -15), textcoords="offset points",
            ha="center", va="top", fontsize=9, color="#c02f1d",
            bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="none", alpha=0.85),
        )

        ax.set_title(LABELS[variant], loc="left", fontsize=12, fontweight="bold")
        if tail:
            tags = sorted({r["run_tag"] for r in tail})
            ax.set_xlabel(
                f"Completed epoch    ·    tail: {', '.join(tags)} "
                f"e{min(tail_epochs)}-{max(tail_epochs)}"
            )
        else:
            ax.set_xlabel("Completed epoch    ·    no continuation past e10")
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
            "continuation_run_tags": sorted(
                {r["run_tag"] for r in continuation.get(variant, [])}
            ),
            "continuation_epochs": [
                r["epoch"] for r in continuation.get(variant, [])
            ],
        }
        for variant, series in history.items()
    }
    (OUT / "loss_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return png


if __name__ == "__main__":
    print(build())
