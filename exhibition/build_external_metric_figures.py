"""Validate, trend, and exhibit accepted-best external metric transactions."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "exhibition"
DATA = HERE / "current" / "external_metrics" / "source_data"
OUT = HERE / "current" / "external_metrics"
CHOICE = HERE / "current" / "continuation" / "family_choice.json"
HISTORY = HERE / "data" / "continuation_history.csv"
NAVY = "#0f2a43"
ACCENT = "#8f4aa8"
MUTED = "#6b7f92"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def write_json_atomic(path: Path, payload: dict) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def load_transactions() -> list[tuple[Path, dict]]:
    transactions = []
    for path in sorted(DATA.glob("*/epoch_*/manifest.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        expected = {
            "schema_version": 1,
            "kind": "cbsc-zdc-accepted-best-external-metrics-transaction",
            "status": "complete",
            "source_split": "validation",
            "cbsc_test_events_used": 0,
            "external_metrics_may_select_or_tune_cbsc": False,
        }
        for key, value in expected.items():
            if payload.get(key) != value:
                raise ValueError(f"{path}: expected {key}={value!r}")
        for artifact in payload["artifacts"]:
            if artifact.get("availability") == "remote_only":
                if artifact.get("purpose") != (
                    "evaluator checkpoint; never a CBSC generator checkpoint"
                ):
                    raise ValueError("remote-only artifact lacks evaluator-only label")
                continue
            target = path.parent / artifact["path"]
            if (
                not target.is_file()
                or target.stat().st_size != artifact["bytes"]
                or sha256_file(target) != artifact["sha256"]
            ):
                raise ValueError(f"external metric artifact mismatch: {target}")
        transactions.append((path.parent, payload))
    return transactions


def _headline(payload: dict) -> dict:
    four = payload["outputs"]["four_momentum"]
    auroc = payload["outputs"]["auroc"]
    return {
        "epoch": int(payload["epoch"]),
        "run_tag": payload["run_tag"],
        # Carried through so downstream consumers can resolve the accepted best
        # of the right family instead of assuming one.
        "family": payload.get("family"),
        "validation_loss": float(payload["validation_loss"]),
        "checkpoint_sha256": payload["checkpoint_sha256"],
        "auroc_mean": auroc["models"]["hybrid"]["ensemble"]["auroc_mean"],
        "auroc_std": auroc["models"]["hybrid"]["ensemble"]["auroc_std"],
        "condition_only_auroc": auroc["models"]["condition_only_control"]["auroc"],
        "high_level_auroc": auroc["models"]["high_level_gbm_control"]["auroc"],
        "four_momentum_macro_rms": four["fast_mc"][
            "macro_rms_relative_fourvector_error"
        ],
        "geant4_reference_macro_rms": four["geant4_reference"][
            "macro_rms_relative_fourvector_error"
        ],
        "energy_relative_rmse": four["fast_mc"]["energy_relative_rmse"],
        "angular_median_mrad": four["fast_mc"]["angular_median_mrad"],
    }


def _save(fig, name: str) -> Path:
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


def trend_figure(rows: list[dict]) -> Path:
    fig, axes = plt.subplots(2, 2, figsize=(13.333, 7.5))
    quantities = [
        ("auroc_mean", "Low-level C2ST AUROC", 0.5),
        ("four_momentum_macro_rms", "Macro RMS relative four-vector error", None),
        ("energy_relative_rmse", "Energy relative RMSE", None),
        ("angular_median_mrad", "Angular median [mrad]", None),
    ]
    epochs = [row["epoch"] for row in rows]
    for ax, (key, title, reference) in zip(axes.ravel(), quantities, strict=True):
        ax.plot(epochs, [row[key] for row in rows], color=ACCENT, marker="o", lw=2)
        if reference is not None:
            ax.axhline(reference, color="#167c5a", ls="--", lw=1.5)
        ax.set_title(title, loc="left")
        ax.set_xlabel("Accepted-best epoch")
        ax.grid(axis="y", alpha=0.25)
    fig.suptitle(
        "External downstream metrics at each new accepted validation-loss best",
        x=0.06,
        ha="left",
        fontsize=16,
        fontweight="bold",
    )
    fig.text(
        0.06,
        0.02,
        "CBSC validation bank only; zero test events. Metrics are descriptive and never select checkpoints.",
        color=MUTED,
    )
    fig.tight_layout(rect=(0.04, 0.06, 1, 0.94))
    return _save(fig, "external_metrics_at_new_accepted_bests")


def current_figure(row: dict) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(13.333, 4.8))
    labels = ["Low-level", "High-level", "Condition only"]
    values = [row["auroc_mean"], row["high_level_auroc"], row["condition_only_auroc"]]
    bars = axes[0].bar(labels, values, color=[ACCENT, NAVY, "#167c5a"])
    axes[0].axhline(0.5, color="#167c5a", ls="--", lw=1.2)
    axes[0].bar_label(bars, fmt="%.4f")
    axes[0].set_ylim(0.45, 1.02)
    axes[0].set_ylabel("Monitoring-holdout AUROC")
    axes[0].set_title("Classifier two-sample controls", loc="left")
    axes[0].grid(axis="y", alpha=0.25)

    labels = ["Geant4 reference", "Fast-MC"]
    values = [row["geant4_reference_macro_rms"], row["four_momentum_macro_rms"]]
    bars = axes[1].bar(labels, values, color=[NAVY, ACCENT])
    axes[1].bar_label(bars, fmt="%.4f")
    axes[1].set_ylabel("Macro RMS relative four-vector error")
    axes[1].set_title("Downstream reconstruction control", loc="left")
    axes[1].grid(axis="y", alpha=0.25)
    fig.suptitle(
        f"Current accepted best: {row['run_tag']} epoch {row['epoch']}",
        x=0.06,
        ha="left",
        fontsize=16,
        fontweight="bold",
    )
    fig.text(
        0.06,
        0.02,
        "Fixed validation bank. High AUROC proves separability; chance-level AUROC is not proof of fidelity.",
        color=MUTED,
    )
    fig.tight_layout(rect=(0.04, 0.08, 1, 0.92))
    return _save(fig, "current_accepted_best_external_metrics")


def build() -> dict:
    transactions = load_transactions()
    if not transactions:
        raise RuntimeError("no complete accepted-best external metric transaction")
    # Sort the transactions and their headline rows together; indexing a sorted
    # row list against the unsorted transaction list points at two different
    # transactions once more than one family is present.
    paired = sorted(
        ((_headline(payload), directory, payload) for directory, payload in transactions),
        key=lambda item: (item[0]["epoch"], item[0]["run_tag"]),
    )
    rows = [row for row, _directory, _payload in paired]
    transactions = [(directory, payload) for _row, directory, payload in paired]
    current = rows[-1]
    # The family must come from the transaction itself. A hardcoded family only
    # happens to work while the newest transaction belongs to it; once a second
    # family is evaluated the check compares the newest transaction against an
    # unrelated family's accepted best and fails for the wrong reason.
    current_family = transactions[-1][1].get("family")
    if not current_family:
        raise ValueError(
            f"external metric transaction for {current['run_tag']} epoch "
            f"{current['epoch']} does not record its family"
        )
    families = json.loads(CHOICE.read_text(encoding="utf-8"))["families"]
    if current_family not in families:
        raise ValueError(f"unknown family in external metric transaction: {current_family}")
    choice = families[current_family]
    if (
        current["epoch"] != int(choice["best_accepted_epoch"])
        or current["run_tag"] != choice["best_accepted_run_tag"]
        or current["validation_loss"] != float(choice["best_accepted_validation_loss"])
    ):
        raise ValueError(
            f"latest external metric transaction ({current['run_tag']} epoch "
            f"{current['epoch']}, loss {current['validation_loss']}) is not the current "
            f"accepted best for {current_family} ({choice['best_accepted_run_tag']} epoch "
            f"{choice['best_accepted_epoch']}, loss {choice['best_accepted_validation_loss']})"
        )

    produced = [trend_figure(rows), current_figure(current)]
    current_directory, current_payload = transactions[-1]
    copied = []
    for artifact in current_payload["artifacts"]:
        if not artifact["path"].endswith((".png", ".svg")):
            continue
        source = current_directory / artifact["path"]
        destination = OUT / f"current_{source.name}"
        shutil.copyfile(source, destination)
        if sha256_file(destination) != artifact["sha256"]:
            raise RuntimeError("copied external figure hash mismatch")
        copied.append(destination)

    payload = {
        "schema_version": 1,
        "kind": "cbsc-zdc-accepted-best-external-metric-summary",
        "source_split": "validation",
        "test_events_used": 0,
        "selection_quantity": "accepted validation loss only",
        "external_metrics_may_select_or_tune_cbsc": False,
        "transactions": rows,
        "current": current,
        "figures": [path.name for path in [*produced, *copied]],
        "scientific_status": (
            "downstream validation monitors; not a fidelity gate or final test evidence"
        ),
    }
    write_json_atomic(OUT / "external_metric_summary.json", payload)
    return payload


if __name__ == "__main__":
    result = build()
    print(json.dumps({"transactions": len(result["transactions"]), "figures": len(result["figures"])}))
