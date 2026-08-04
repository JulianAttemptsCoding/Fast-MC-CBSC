"""Per-family loss graphs covering every observed epoch.

The exhibition's own figures compare the four families over an identical epoch
range, which is what makes them comparable -- so they stop at epoch 10. This
builds the complementary view: one panel per family showing its whole observed
training history. Quarantined observations remain visible but are excluded
from accepted-best and latest-accepted metrics.

Output goes to ``exhibition/current/continuation/``. It includes the ordinary
train/validation loss-vs-epoch view and an accepted running-best validation-loss
view. The compact current gallery manifest remains separate; the comprehensive
exhibition index catalogs both on every refresh.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = HERE / "current" / "continuation"

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
CONTINUATION_STATUS = ROOT / "exhibition" / "data" / "continuation_status.json"

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
        "svg.hashsalt": "cbsc-zdc-continuation",
    })


def save_svg_clean(fig, path: Path) -> None:
    temporary = path.with_name(f".{path.name}.tmp.svg")
    fig.savefig(temporary, metadata={"Date": None})
    lines = temporary.read_text(encoding="utf-8").splitlines()
    temporary.write_text(
        "\n".join(line.rstrip() for line in lines) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def save_png_atomic(fig, path: Path) -> None:
    temporary = path.with_name(f".{path.name}.tmp.png")
    fig.savefig(temporary)
    temporary.replace(path)


def write_json_atomic(path: Path, payload: dict) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def read_continuation() -> dict[str, list[dict[str, float]]]:
    """Epochs past 10, per family, from each run's own history.csv."""
    rows: dict[str, list[dict[str, float]]] = {}
    if not CONTINUATION_CSV.is_file():
        return rows
    statuses = {}
    if CONTINUATION_STATUS.is_file():
        payload = json.loads(CONTINUATION_STATUS.read_text(encoding="utf-8"))
        statuses = {
            (row["variant"], int(row["epoch"]), row["run_tag"]): row
            for row in payload.get("overrides", [])
        }
    with CONTINUATION_CSV.open(newline="", encoding="utf-8") as stream:
        for raw in csv.DictReader(stream):
            status = statuses.get(
                (raw["variant"], int(raw["epoch"]), raw["run_tag"]),
                {"status": "accepted", "reason": None},
            )
            rows.setdefault(raw["variant"], []).append({
                "epoch": int(raw["epoch"]),
                "train_loss": float(raw["train_loss"]),
                "validation_loss": float(raw["validation_loss"]),
                "run_tag": raw["run_tag"],
                "status": status["status"],
                "status_reason": status.get("reason"),
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


def _thinned_ticks(epochs: list[int]) -> list[int]:
    """Label every epoch while they fit, then every 2nd, 5th, 10th.

    A tick per epoch is readable to about 25 epochs in this panel width. Past
    that the labels run together into an unreadable band -- lr1e4 reached 40
    epochs and is heading for 62 -- so thin the labels rather than let the axis
    become decoration. The markers still show every epoch; only the labels thin.
    """
    span = max(epochs) - min(epochs) + 1
    step = 1 if span <= 25 else 2 if span <= 45 else 5 if span <= 90 else 10
    ticks = [e for e in epochs if e % step == 0]
    # Always label the last epoch: it is the one a reader looks for. Drop the
    # tick before it when they would sit closer than a full step, or the two
    # labels overlap -- e38 and e39 rendered as "3889" before this guard.
    if epochs[-1] not in ticks:
        while ticks and epochs[-1] - ticks[-1] < step:
            ticks.pop()
        ticks.append(epochs[-1])
    return ticks


def _tail_tags(tail: list[dict]) -> list[str]:
    """Run tags in the order they were RUN, not alphabetical order.

    Sorting alphabetically puts dicos-p10 before dicos-p6, which reads as a
    chronology and is wrong. Order by the first epoch each tag contributed.
    """
    first_epoch: dict[str, int] = {}
    for row in tail:
        tag = row["run_tag"]
        epoch = int(row["epoch"])
        if tag not in first_epoch or epoch < first_epoch[tag]:
            first_epoch[tag] = epoch
    return sorted(first_epoch, key=lambda t: (first_epoch[t], t))


def _running_best(series: list[dict]) -> list[float]:
    """Accepted running minimum at every observed epoch.

    Quarantined observations stay on the ordinary loss plot but cannot advance
    this trace.  The prior accepted minimum is carried forward instead.
    """
    values: list[float] = []
    current = float("inf")
    for row in series:
        if row.get("status", "accepted") == "accepted":
            current = min(current, float(row["validation_loss"]))
        if not math.isfinite(current):
            raise ValueError("running-best trace has no accepted starting epoch")
        values.append(current)
    return values


def build_running_best(history: dict[str, list[dict]]) -> Path:
    fig, ax = plt.subplots(figsize=(13.333, 6.2))
    fig.suptitle(
        "Accepted running-best validation loss vs epoch",
        x=0.02, ha="left", fontsize=17, fontweight="bold", color=NAVY, y=0.975,
    )
    fig.text(
        0.02, 0.925,
        "Each step is the lowest accepted validation loss available by that epoch. "
        "Quarantined observations remain in the full loss figure but never advance "
        "this best-so-far trace.",
        ha="left", va="top", fontsize=10.5, color="#4a6178",
    )
    all_epochs = sorted({int(row["epoch"]) for rows in history.values() for row in rows})
    for variant in ORDER:
        series = history[variant]
        epochs = [int(row["epoch"]) for row in series]
        best = _running_best(series)
        ax.step(
            epochs, best, where="post", color=COLORS[variant], lw=2.3,
            label=LABELS[variant],
        )
        ax.scatter(epochs, best, color=COLORS[variant], s=22, zorder=3)
    ax.set_xlabel("Completed epoch")
    ax.set_ylabel("Best accepted validation loss so far")
    ax.set_xticks(_thinned_ticks(all_epochs))
    ax.set_xlim(min(all_epochs) - 0.6, max(all_epochs) + 0.6)
    ax.grid(axis="y", color="#dde5ec", lw=0.9)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=9, ncol=2)
    fig.subplots_adjust(left=0.08, right=0.97, top=0.82, bottom=0.16)
    fig.text(
        0.02, 0.02,
        "Selection quantity only: validation loss on the frozen pilot validation "
        "split. Zero test events. Lower is better; this is not Geant4 fidelity.",
        ha="left", fontsize=8.8, color="#6b7f92",
    )
    png = OUT / "best_validation_loss_so_far_vs_epoch.png"
    save_png_atomic(fig, png)
    save_svg_clean(fig, OUT / "best_validation_loss_so_far_vs_epoch.svg")
    plt.close(fig)
    return png


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

        accepted = [r for r in series if r.get("status", "accepted") == "accepted"]
        best = min(accepted, key=lambda r: r["validation_loss"])
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
        quarantined = [r for r in series if r.get("status") == "quarantined"]
        if quarantined:
            ax.scatter(
                [r["epoch"] for r in quarantined],
                [r["validation_loss"] for r in quarantined],
                marker="x", s=85, linewidths=2.2, color="#7b2cbf", zorder=6,
                label="Quarantined QA failure",
            )

        ax.set_title(LABELS[variant], loc="left", fontsize=12, fontweight="bold")
        if tail:
            ax.set_xlabel(
                f"Completed epoch    ·    tail: {', '.join(_tail_tags(tail))} "
                f"e{min(tail_epochs)}-{max(tail_epochs)}"
            )
        else:
            ax.set_xlabel("Completed epoch    ·    no continuation past e10")
        ax.set_ylabel("Weighted joint loss")
        ax.set_xticks(_thinned_ticks(epochs))
        ax.set_xlim(min(epochs) - 0.6, max(epochs) + 0.6)
        ax.grid(axis="y", color="#dde5ec", lw=0.9)
        ax.set_axisbelow(True)

    handles, labels = axes.ravel()[1].get_legend_handles_labels()
    axes.ravel()[0].legend(handles, labels, loc="upper right", frameon=False, fontsize=9)
    fig.subplots_adjust(left=0.07, right=0.97, top=0.835, bottom=0.13,
                        hspace=0.42, wspace=0.20)
    fig.text(
        0.02, 0.015,
        "Lower is better for this frozen weighted objective. Purple × = "
        "quarantined QA failure. Pilot bank only (26,624 train / 6,656 "
        "validation).\nZero test events in training/selection. Optimization "
        "evidence, not Geant4 fidelity.",
        ha="left", fontsize=8.8, color="#6b7f92", linespacing=1.35,
    )

    OUT.mkdir(parents=True, exist_ok=True)
    png = OUT / "loss_all_families_every_epoch.png"
    save_png_atomic(fig, png)
    save_svg_clean(fig, OUT / "loss_all_families_every_epoch.svg")
    plt.close(fig)
    best_trace_png = build_running_best(history)

    summary = {"schema_version": 2, "families": {}}
    for variant, series in history.items():
        accepted = [
            row for row in series if row.get("status", "accepted") == "accepted"
        ]
        if not accepted:
            raise ValueError(f"{variant}: no accepted epochs")
        best = min(accepted, key=lambda row: row["validation_loss"])
        latest_accepted = accepted[-1]
        latest_observed = series[-1]
        summary["families"][variant] = {
            "observed_epochs": [r["epoch"] for r in series],
            "best_accepted_validation_loss": best["validation_loss"],
            "best_accepted_epoch": best["epoch"],
            "best_accepted_run_tag": best.get("run_tag"),
            "latest_accepted_epoch": latest_accepted["epoch"],
            "latest_accepted_validation_loss": latest_accepted["validation_loss"],
            "latest_observed_epoch": latest_observed["epoch"],
            "latest_observed_validation_loss": latest_observed["validation_loss"],
            "latest_observed_status": latest_observed.get("status", "accepted"),
            "continuation_run_tags": _tail_tags(continuation.get(variant, [])),
            "continuation_epochs": [
                r["epoch"] for r in continuation.get(variant, [])
            ],
            "quarantined_epochs": [
                r["epoch"] for r in continuation.get(variant, [])
                if r.get("status") == "quarantined"
            ],
            "running_best_validation_loss": _running_best(series),
        }
    summary["figures"] = [
        png.name,
        best_trace_png.name,
    ]
    write_json_atomic(OUT / "loss_summary.json", summary)
    return png


if __name__ == "__main__":
    print(build())
