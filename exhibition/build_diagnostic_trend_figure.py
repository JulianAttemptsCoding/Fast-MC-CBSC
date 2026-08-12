"""Every repository metric, plotted against epoch, from the large validation sample.

The published per-epoch payload carries a handful of these from 250 events
(50 conditions x 5 draws). These come from a much larger fixed validation
sample generated alongside training, so the same quantities arrive with error
bars small enough to read a trend from.

Eight figures in four paired metric families:

  bias_vs_epoch          the nine high-level observables' mean bias, with
                         standard errors and a zero reference
  wasserstein_vs_epoch   the same nine as Wasserstein distances, each against
                         its own truth-half floor -- the distance you get
                         comparing truth to itself, below which a value is not
                         distinguishable from sampling noise
  headline_vs_epoch      classifier two-sample AUROC, normalised response and
                         hit-count Wasserstein, profile L1, zero fractions
  energy_bins_vs_epoch   mean bias and resolution difference per energy bin

Each family has an ``*_of_best_loss_so_far`` counterpart. At every completed
epoch that counterpart shows the 3090 metrics of the accepted checkpoint with
the lowest validation loss available so far. Diagnostic metrics never select
the checkpoint.

Input is `exhibition/data/diagnostics/<run-tag>/metrics_epoch_*.json`. Figures
are built to be partial while a run is in flight. Output goes to
``exhibition/current/diagnostics/``. The compact current gallery manifest
remains separate, while the comprehensive exhibition index catalogs these
files on every refresh.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
DATA_ROOT = HERE / "data" / "diagnostics"
OUT = HERE / "current" / "diagnostics"
STATUS_PATH = HERE / "data" / "continuation_status.json"

#: Diagnostics are namespaced per run tag: two runs of one family overlap in
#: epoch number, and the metrics filenames carry only the epoch.
#:
#: Several tags may be given, oldest first. They are read as one LINEAGE --
#: p9 covering epochs 16..38 and p10 continuing from 39 are the same model,
#: and plotting them as one trend is the whole point of a metric-vs-epoch
#: figure. Where two tags carry the same epoch, the LATER tag wins: it is on
#: the live branch, and the earlier one was superseded when the new run
#: resumed from a best checkpoint rather than a last one.
#:
#: "Later tag wins" only resolves overlap where the later tag has actually
#: reached that epoch. dicos-f-01 (2026-08-12) forked from dicos-e-02 at
#: epoch 47 and resumed the anneal there, but dicos-e-02 itself had already
#: run all the way to epoch 54 before the fork -- so for the epochs between
#: dicos-f-01's fork point and wherever it has trained *to so far*,
#: dicos-e-02's now-superseded tail was still the only file on disk, and
#: "later wins if present" silently kept showing it. A tag may therefore be
#: given as `TAG:MAX_EPOCH` to cap what is read from it at its own fork
#: point, independent of whether anything downstream has caught up yet.
#: Bare `TAG` (no colon) is unchanged and reads that tag's full range.
#:
#: `RUN_TAGS` reads `sys.argv[1:]` at import time -- pre-existing, not
#: introduced here -- so this module gets whatever argv belongs to whatever
#: imports it, pytest included. A pytest node id like
#: `path::test_name` lands in `sys.argv[1]` and contains a colon; matched
#: strictly (only `lowercase-tag:digits`) so anything else, argv noise
#: included, falls back to being read as a single bare tag exactly as before
#: this feature existed -- one that will not match a real directory and is
#: silently skipped by the `directory.is_dir()` check in load(), not one that
#: raises. A loose `partition(":")` + bare `int()` here crashed on exactly
#: that pytest invocation the first time this was written.
_RUN_TAG_BOUND_PATTERN = re.compile(r"^([a-z0-9][a-z0-9-]*):([0-9]+)$")


def _parse_run_tag(arg: str) -> tuple[str, int | None]:
    match = _RUN_TAG_BOUND_PATTERN.fullmatch(arg)
    return (match.group(1), int(match.group(2))) if match else (arg, None)


_PARSED_RUN_TAGS = [_parse_run_tag(arg) for arg in sys.argv[1:]] or [
    ("dicos-p9", None), ("dicos-p10", None),
]
RUN_TAGS = [tag for tag, _bound in _PARSED_RUN_TAGS]
RUN_TAG_MAX_EPOCH = {tag: bound for tag, bound in _PARSED_RUN_TAGS if bound is not None}
RUN_TAG = "+".join(RUN_TAGS)

NAVY = "#0f2a43"
ACCENT = "#d2691e"
FLOOR = "#00a06d"
MUTED = "#6b7f92"
GATE = "#c02f1d"
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


def family_for_run_tags(run_tags: list[str]) -> str:
    """Which calibrated family a set of run tags belongs to.

    `best_loss_so_far_rows` needs a family name to overlay a lineage's own
    best-so-far trajectory. That was hardcoded to `calibrated_lr1e4` back when
    it was the only family with 3090 diagnostics; with a campaign now producing
    diagnostics for several families concurrently, hardcoding it silently
    overlaid the WRONG family's history and returned zero matching rows for
    every family except lr1e4 (`diagnostic.get(key)` could never find a key
    from another family's rows). The family is read off the tags actually being
    plotted instead.
    """
    try:
        from exhibition.build_continuation_loss_figures import read_history
    except ModuleNotFoundError:  # direct ``python exhibition/script.py`` entry
        from build_continuation_loss_figures import read_history

    history, _ = read_history()
    for family, rows in history.items():
        if any(str(row.get("run_tag")) in run_tags for row in rows):
            return family
    raise ValueError(f"no family found in continuation history for tags {run_tags}")


def best_loss_so_far_rows(
    rows: list[dict], family: str,
) -> tuple[list[dict], list[int], list[dict], list[int]]:
    """Return 3090 metrics for the accepted validation-loss best at each epoch.

    A historical best without a 4,000-event 3090 diagnostic is reported as
    unavailable rather than backfilled from the smaller 250-draw visual bank.
    Once a diagnosed epoch becomes the best, its metrics are carried forward
    until a later accepted epoch improves validation loss.
    """
    try:
        from exhibition.build_continuation_loss_figures import read_history
    except ModuleNotFoundError:  # direct ``python exhibition/script.py`` entry
        from build_continuation_loss_figures import read_history

    history, _ = read_history()
    family_rows = history[family]
    diagnostic = {
        (str(row["run_tag"]), int(row["epoch"])): row for row in rows
    }
    selected_rows: list[dict] = []
    selected_epochs: list[int] = []
    selection: list[dict] = []
    unavailable: list[int] = []
    for observed in rows:
        completed_epoch = int(observed["epoch"])
        eligible = [
            row for row in family_rows
            if int(row["epoch"]) <= completed_epoch
            and row.get("status", "accepted") == "accepted"
        ]
        best = min(eligible, key=lambda row: float(row["validation_loss"]))
        key = (str(best.get("run_tag")), int(best["epoch"]))
        metric_row = diagnostic.get(key)
        record = {
            "completed_epoch": completed_epoch,
            "best_checkpoint_epoch": int(best["epoch"]),
            "best_checkpoint_run_tag": best.get("run_tag"),
            "best_validation_loss": float(best["validation_loss"]),
            "metric_available_from_3090": metric_row is not None,
        }
        selection.append(record)
        if metric_row is None:
            unavailable.append(completed_epoch)
            continue
        selected_rows.append(metric_row)
        selected_epochs.append(completed_epoch)
    return selected_rows, selected_epochs, selection, unavailable


def _validate_metric(path: Path, row: dict, expected_epoch: int) -> None:
    expected = {
        "schema_version": 1,
        "kind": "cbsc-zdc-large-validation-diagnostic",
        "split": "validation",
        "epoch": expected_epoch,
        "n_events": 4000,
        "validation_pool": 50877,
        "selection_seed": 20260803,
        "kinetic_range_gev": [50.0, 250.0],
        "split_counts": {"train": 0, "validation": 4000, "test": 0},
    }
    for key, value in expected.items():
        if row.get(key) != value:
            raise ValueError(f"{path}: expected {key}={value!r}")
    checkpoint = row.get("checkpoint_sha256", "")
    if not re.fullmatch(r"[0-9a-f]{64}", checkpoint):
        raise ValueError(f"{path}: invalid checkpoint_sha256")
    qa = row.get("qa", {})
    required_qa = {
        "test_events_used": 0,
        "train_events_used": 0,
        "generated_nonfinite": 0,
        "generated_negative": 0,
        "truth_nonfinite": 0,
        "truth_negative": 0,
        "events_outside_energy_bins": 0,
        "empty_energy_bins": 0,
        "pass": True,
    }
    for key, value in required_qa.items():
        if qa.get(key) != value:
            raise ValueError(f"{path}: diagnostic QA {key} failed")


def load() -> list[dict]:
    by_epoch: dict[int, dict] = {}
    for tag in RUN_TAGS:
        directory = DATA_ROOT / tag
        if not directory.is_dir():
            continue
        max_epoch = RUN_TAG_MAX_EPOCH.get(tag)
        for path in sorted(directory.glob("metrics_epoch_*.json")):
            match = re.fullmatch(r"metrics_epoch_(\d{4,})\.json", path.name)
            if not match:
                continue
            expected_epoch = int(match.group(1))
            if max_epoch is not None and expected_epoch > max_epoch:
                # Superseded by a later tag's fork point, whether or not that
                # tag has produced a replacement for this epoch yet.
                continue
            row = json.loads(path.read_text(encoding="utf-8"))
            _validate_metric(path, row, expected_epoch)
            row["run_tag"] = tag
            # Later tag wins: it is the live branch for that epoch.
            by_epoch[int(row["epoch"])] = row
    return [by_epoch[e] for e in sorted(by_epoch)]


def quarantined_epochs() -> list[int]:
    if not STATUS_PATH.is_file():
        return []
    payload = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    return sorted({
        int(row["epoch"])
        for row in payload.get("overrides", [])
        if row.get("run_tag") in RUN_TAGS and row.get("status") == "quarantined"
    })


def status_for(run_tag: str, epoch: int) -> tuple[str, str | None]:
    if not STATUS_PATH.is_file():
        return "accepted", None
    payload = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    for row in payload.get("overrides", []):
        if row.get("run_tag") == run_tag and int(row.get("epoch", -1)) == epoch:
            return row["status"], row.get("reason")
    return payload.get("default_status", "accepted"), None


def style() -> None:
    plt.rcParams.update({
        "figure.dpi": 160, "savefig.dpi": 160, "font.size": 10,
        "axes.edgecolor": NAVY, "axes.labelcolor": NAVY, "text.color": NAVY,
        "xtick.color": NAVY, "ytick.color": NAVY,
        "axes.spines.top": False, "axes.spines.right": False,
        "svg.hashsalt": "cbsc-zdc-diagnostics",
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
             "Validation split only, zero test events in these diagnostics. "
             "Purple dashed = quarantined checkpoint. Descriptive diagnostics, "
             "not a fidelity gate and not Geant4 validation.",
             ha="left", fontsize=9, color=MUTED)
    for ax in fig.axes:
        if not ax.axison:
            continue
        for epoch in quarantined_epochs():
            if epoch in epochs:
                ax.axvline(epoch, color=QUARANTINE, lw=1.2, ls="--", zorder=0)
    OUT.mkdir(parents=True, exist_ok=True)
    png = OUT / f"{name}.png"
    save_png_atomic(fig, png)
    save_svg_clean(fig, OUT / f"{name}.svg")
    plt.close(fig)
    return png


def _layout(fig, **kwargs) -> None:
    """Reserve fixed inch bands for the title block and for the footer plus
    the bottom row's tick labels and axis label."""
    height = fig.get_size_inches()[1]
    fig.subplots_adjust(
        top=1 - 1.35 / height, bottom=0.90 / height, **kwargs
    )


def _ticks(ax, epochs) -> None:
    if len(epochs) <= 14:
        ax.set_xticks(epochs)
    ax.grid(axis="y", color="#dde5ec", lw=0.8)
    ax.set_axisbelow(True)


def bias_figure(rows, epochs, subtitle, *, best_so_far: bool = False) -> Path:
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
    heading = (
        "Best-so-far checkpoint bias vs epoch"
        if best_so_far else "Mean bias vs epoch, nine high-level observables"
    )
    name = "bias_of_best_loss_so_far" if best_so_far else "bias_vs_epoch"
    return _finish(fig, epochs, heading, subtitle, name)


def wasserstein_figure(rows, epochs, subtitle, *, best_so_far: bool = False) -> Path:
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
    heading = (
        "Best-so-far checkpoint Wasserstein vs epoch"
        if best_so_far else "Wasserstein distance vs epoch, against the truth-half floor"
    )
    name = (
        "wasserstein_of_best_loss_so_far"
        if best_so_far else "wasserstein_vs_epoch"
    )
    return _finish(
        fig, epochs, heading,
        subtitle + "  Dashed green = truth vs itself; at or below it is "
        "indistinguishable from sampling noise.",
        name,
    )


def headline_figure(rows, epochs, subtitle, *, best_so_far: bool = False) -> Path:
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
    heading = (
        "Best-so-far checkpoint headline metrics vs epoch"
        if best_so_far else "Headline distribution metrics vs epoch"
    )
    name = "headline_of_best_loss_so_far" if best_so_far else "headline_vs_epoch"
    return _finish(
        fig, epochs, heading,
        subtitle + "  Dotted red = predeclared threshold.", name,
    )


def energy_bin_figure(
    rows, epochs, subtitle, *, best_so_far: bool = False,
) -> Path | None:
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
    heading = (
        "Best-so-far checkpoint energy-bin response vs epoch"
        if best_so_far else "Energy-resolved response vs epoch"
    )
    name = (
        "energy_bins_of_best_loss_so_far"
        if best_so_far else "energy_bins_vs_epoch"
    )
    return _finish(
        fig, epochs, heading,
        subtitle + "  Dotted red = predeclared thresholds.", name,
    )


def build() -> list[Path]:
    rows = load()
    if not rows:
        print("no diagnostic metrics yet")
        return []
    style()
    epochs = [int(r["epoch"]) for r in rows]
    latest = rows[-1]
    family = family_for_run_tags(RUN_TAGS)
    subtitle = (
        f"{family} continuation ({RUN_TAG}). "
        f"{latest['n_events']:,} fixed validation events per epoch, drawn from a "
        f"{latest['validation_pool']:,}-event pool, against the site's 250. "
        "Quarantined checkpoints remain visible as negative evidence."
    )

    produced = [
        bias_figure(rows, epochs, subtitle),
        wasserstein_figure(rows, epochs, subtitle),
        headline_figure(rows, epochs, subtitle),
    ]
    energy = energy_bin_figure(rows, epochs, subtitle)
    if energy:
        produced.append(energy)

    best_rows, best_epochs, best_selection, unavailable = best_loss_so_far_rows(
        rows, family
    )
    best_produced: list[Path] = []
    if best_rows:
        best_subtitle = (
            f"{family} continuation ({RUN_TAG}); 4,000 fixed validation "
            "events. At each completed epoch, show 3090 metrics from the accepted "
            "validation-loss best so far.\nMetrics never select the checkpoint; "
            "an early best with no matching 3090 diagnostic is skipped, so this "
            f"historical trace begins at e{best_epochs[0]}."
        )
        best_produced = [
            bias_figure(best_rows, best_epochs, best_subtitle, best_so_far=True),
            wasserstein_figure(
                best_rows, best_epochs, best_subtitle, best_so_far=True
            ),
            headline_figure(
                best_rows, best_epochs, best_subtitle, best_so_far=True
            ),
        ]
        best_energy = energy_bin_figure(
            best_rows, best_epochs, best_subtitle, best_so_far=True
        )
        if best_energy:
            best_produced.append(best_energy)
        produced.extend(best_produced)

    per_epoch = []
    for row in rows:
        status, reason = status_for(row["run_tag"], int(row["epoch"]))
        per_epoch.append({
            "epoch": int(row["epoch"]),
            "run_tag": row["run_tag"],
            "checkpoint_sha256": row["checkpoint_sha256"],
            "status": status,
            "status_reason": reason,
            "qa_pass": row["qa"]["pass"],
            "split_counts": row["split_counts"],
        })
    summary = {
        "schema_version": 2,
        "run_tag": RUN_TAG,
        "run_tags": RUN_TAGS,
        "epochs_by_run_tag": {
            tag: [int(r["epoch"]) for r in rows if r.get("run_tag") == tag]
            for tag in RUN_TAGS
        },
        "epochs": epochs,
        "n_events_per_epoch": latest["n_events"],
        "validation_pool": latest["validation_pool"],
        "kinetic_range_gev": latest["kinetic_range_gev"],
        "selection_seed": latest["selection_seed"],
        "test_events_used": 0,
        "quarantined_epochs": quarantined_epochs(),
        "per_epoch": per_epoch,
        "scientific_status": (
            "descriptive validation diagnostics; not a fidelity gate and not "
            "Geant4 validation"
        ),
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
        "best_loss_so_far": {
            "selection_quantity": "accepted validation loss only",
            "selection_trace": best_selection,
            "completed_epochs_without_matching_3090_metric": unavailable,
            "figures": [p.name for p in best_produced],
        },
        "figures": [p.name for p in produced],
    }
    write_json_atomic(OUT / "diagnostic_summary.json", summary)
    return produced


if __name__ == "__main__":
    for path in build():
        print(path)
