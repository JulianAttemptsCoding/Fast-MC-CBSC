"""Run validation-only downstream metrics for an accepted CBSC checkpoint.

The event bank must come from ``export_external_validation_bank.py``.  Two
independent, read-only evaluators are used:

* ``ML ZDC all 1`` supplies the frozen M1 XGBoost reconstruction model and its
  exact feature/physics metric implementation;
* ``Fast-MC-tester`` supplies the geometry-aware hybrid C2ST implementation,
  training loop, uncertainty statistics, and controls.

Neither output may select or tune a CBSC checkpoint.  The bank's CBSC source
split is validation; the C2ST creates a pair-grouped evaluator-internal
train/validation/monitoring-holdout partition inside that bank.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ENERGY_EDGES = np.asarray([50, 75, 100, 125, 150, 175, 200, 225, 250.0001], float)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def load_bank(bank_path: Path, manifest_path: Path) -> tuple[dict, dict[str, np.ndarray]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = {
        "schema_version": 1,
        "kind": "cbsc-zdc-paired-validation-external-metric-bank",
        "split": "validation",
        "cbsc_test_events_used": 0,
    }
    for key, value in expected.items():
        if manifest.get(key) != value:
            raise ValueError(f"event-bank manifest expected {key}={value!r}")
    if manifest.get("bank_file") != bank_path.name:
        raise ValueError("event-bank filename does not match its manifest")
    if manifest.get("bank_sha256") != sha256_file(bank_path):
        raise ValueError("event-bank SHA-256 does not match its manifest")
    if manifest.get("qa", {}).get("pass") is not True:
        raise ValueError("event-bank manifest QA did not pass")
    with np.load(bank_path, allow_pickle=False) as source:
        arrays = {name: source[name] for name in source.files}
    required = {
        "event_ptr",
        "cell_index",
        "cell_energy_gev",
        "p4_total_gev",
        "label",
        "family_id",
        "source_event_id",
        "pair_id",
        "cbsc_source_split_code",
    }
    if set(arrays) != required:
        raise ValueError(f"event-bank arrays differ from contract: {sorted(set(arrays) ^ required)}")
    n_events = len(arrays["event_ptr"]) - 1
    if n_events != int(manifest["n_events"]):
        raise ValueError("event-bank event count differs from manifest")
    if not np.all(arrays["cbsc_source_split_code"] == 1):
        raise ValueError("event-bank contains a non-validation CBSC source event")
    if int(np.sum(arrays["label"] == 1)) != int(manifest["n_pairs"]):
        raise ValueError("event-bank Geant4 class count is not one per pair")
    if int(np.sum(arrays["label"] == 0)) != int(manifest["n_pairs"]):
        raise ValueError("event-bank Fast-MC class count is not one per pair")
    return manifest, arrays


def paired_stratified_partitions(
    pair_id: np.ndarray,
    p4_total_gev: np.ndarray,
    *,
    seed: int,
    fractions: tuple[float, float, float] = (0.7, 0.15, 0.15),
) -> np.ndarray:
    """Assign complete pairs, stratified by energy, to evaluator partitions."""
    pair_id = np.asarray(pair_id, dtype=np.int64)
    p4 = np.asarray(p4_total_gev, dtype=float)
    if pair_id.shape != (len(p4),):
        raise ValueError("pair_id and p4 lengths differ")
    if abs(sum(fractions) - 1.0) > 1e-12:
        raise ValueError("partition fractions must sum to one")
    unique, first, counts = np.unique(pair_id, return_index=True, return_counts=True)
    if not np.all(counts == 2):
        raise ValueError("every event-bank pair must contain exactly two class members")
    for value in unique:
        idx = np.flatnonzero(pair_id == value)
        if not np.allclose(p4[idx], p4[idx[0]], rtol=0.0, atol=0.0):
            raise ValueError("paired events do not carry identical incident four-vectors")
    kinetic = p4[first, 0] - 0.93956542052
    bins = np.digitize(kinetic, ENERGY_EDGES[1:-1], right=False)
    rng = np.random.default_rng(seed)
    pair_partition: dict[int, int] = {}
    for bin_id in np.unique(bins):
        positions = np.flatnonzero(bins == bin_id)
        rng.shuffle(positions)
        n = len(positions)
        n_train = int(round(fractions[0] * n))
        n_validation = int(round(fractions[1] * n))
        for pos in positions[:n_train]:
            pair_partition[int(unique[pos])] = 0
        for pos in positions[n_train : n_train + n_validation]:
            pair_partition[int(unique[pos])] = 1
        for pos in positions[n_train + n_validation :]:
            pair_partition[int(unique[pos])] = 2
    partition = np.asarray([pair_partition[int(value)] for value in pair_id], dtype=np.int8)
    for value in unique:
        if len(np.unique(partition[pair_id == value])) != 1:
            raise RuntimeError("a paired condition crossed evaluator partitions")
    return partition


def _environment() -> dict:
    snapshot = {"python": sys.version, "platform": platform.platform()}
    for module_name in ("numpy", "torch", "pandas", "xgboost", "sklearn"):
        try:
            module = __import__(module_name)
            snapshot[module_name] = getattr(module, "__version__", "unknown")
        except ImportError:
            snapshot[module_name] = None
    try:
        import torch

        snapshot["cuda_available"] = bool(torch.cuda.is_available())
        if torch.cuda.is_available():
            snapshot["cuda_device"] = torch.cuda.get_device_name(0)
    except ImportError:
        snapshot["cuda_available"] = False
    return snapshot


def _reco_features(
    arrays: dict[str, np.ndarray],
    indices: np.ndarray,
    geometry_payload: dict,
    frame_payload: dict,
    feature_config: dict,
):
    import pandas as pd
    from zdc_reco.features import build_event_features
    from zdc_reco.geometry import DetectorFrame, validate_frame

    positions_cm = np.asarray(geometry_payload["positions_mm"], dtype=float) * 0.1
    subdetector = np.asarray(geometry_payload["subdetector"], dtype=np.int8)
    frame = DetectorFrame(
        origin=tuple(frame_payload["origin"]),
        x_axis=tuple(frame_payload["x_axis"]),
        y_axis=tuple(frame_payload["y_axis"]),
        z_axis=tuple(frame_payload["z_axis"]),
        ecal_z_bounds=tuple(frame_payload["ecal_z_bounds"]),
        hcal_z_bounds=tuple(frame_payload["hcal_z_bounds"]),
    )
    validate_frame(frame)
    rows = []
    ptr = arrays["event_ptr"]
    for event in indices:
        low, high = int(ptr[event]), int(ptr[event + 1])
        cells = arrays["cell_index"][low:high]
        signal = arrays["cell_energy_gev"][low:high]
        ecal = subdetector[cells] == 0
        hcal = ~ecal
        rows.append(
            build_event_features(
                ecal_x=positions_cm[cells[ecal], 0],
                ecal_y=positions_cm[cells[ecal], 1],
                ecal_z=positions_cm[cells[ecal], 2],
                ecal_signal_gev=signal[ecal],
                hcal_x=positions_cm[cells[hcal], 0],
                hcal_y=positions_cm[cells[hcal], 1],
                hcal_z=positions_cm[cells[hcal], 2],
                hcal_signal_gev=signal[hcal],
                frame=frame,
                ecal_threshold_gev=0.0,
                hcal_threshold_gev=0.0,
                ecal_depth_groups=int(feature_config["ecal_depth_groups"]),
                hcal_depth_groups=int(feature_config["hcal_depth_groups"]),
                top_hit_counts=tuple(feature_config["top_hit_counts"]),
                density_edges_gev=tuple(feature_config["hit_energy_density_edges_gev"]),
            )
        )
    return pd.DataFrame(rows)


def _fourvector_bundle(true: np.ndarray, predicted: np.ndarray) -> dict:
    from zdc_reco.metrics import (
        evaluate_fourvectors,
        macro_rms_by_energy_bin,
        relative_fourvector_error,
    )

    mass = 0.93956542052
    errors = relative_fourvector_error(true, predicted)
    kinetic = true[:, 0] - mass
    metrics = evaluate_fourvectors(true, predicted, mass_gev=mass)
    metrics["macro_rms_relative_fourvector_error"] = macro_rms_by_energy_bin(
        errors, kinetic, ENERGY_EDGES
    )
    component_residual = (predicted - true) / true[:, [0]]
    metrics["component_normalized_bias"] = {
        name: float(np.mean(component_residual[:, i]))
        for i, name in enumerate(("E", "px", "py", "pz"))
    }
    metrics["component_normalized_rmse"] = {
        name: float(np.sqrt(np.mean(component_residual[:, i] ** 2)))
        for i, name in enumerate(("E", "px", "py", "pz"))
    }
    metrics["fraction_within_relative_fourvector_error"] = {
        str(tolerance): float(np.mean(errors <= tolerance))
        for tolerance in (0.01, 0.05, 0.10, 0.20)
    }
    energy_error = np.abs(predicted[:, 0] - true[:, 0])
    relative_energy_error = energy_error / true[:, 0]
    metrics["fraction_energy_within_gev"] = {
        str(tolerance): float(np.mean(energy_error <= tolerance))
        for tolerance in (1.0, 5.0, 10.0)
    }
    metrics["fraction_energy_within_relative"] = {
        str(tolerance): float(np.mean(relative_energy_error <= tolerance))
        for tolerance in (0.01, 0.05, 0.10)
    }
    metrics["per_energy_bin"] = []
    for low, high in zip(ENERGY_EDGES[:-1], ENERGY_EDGES[1:], strict=True):
        mask = (kinetic >= low) & (kinetic < high)
        metrics["per_energy_bin"].append(
            {
                "low_gev": float(low),
                "high_gev": float(high),
                "n_events": int(mask.sum()),
                "rms_relative_fourvector_error": float(
                    np.sqrt(np.mean(errors[mask] ** 2))
                ),
                "energy_relative_rmse": float(
                    np.sqrt(np.mean(((predicted[mask, 0] / true[mask, 0]) - 1.0) ** 2))
                ),
            }
        )
    return metrics


def _plot_four_momentum(output_dir: Path, metrics: dict) -> list[Path]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figures = output_dir / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    produced = []
    labels = ["Geant4 reference", "Fast-MC"]
    sources = [metrics["geant4_reference"], metrics["fast_mc"]]

    fig, axes = plt.subplots(2, 2, figsize=(12, 7.5))
    quantities = [
        ("macro_rms_relative_fourvector_error", "Macro RMS relative 4-vector error"),
        ("energy_relative_rmse", "Energy relative RMSE"),
        ("energy_mae_gev", "Energy MAE [GeV]"),
        ("angular_median_mrad", "Angular median [mrad]"),
    ]
    for ax, (key, title) in zip(axes.ravel(), quantities, strict=True):
        values = [source[key] for source in sources]
        bars = ax.bar(labels, values, color=["#1f3552", "#8f4aa8"])
        ax.set_title(title, loc="left")
        ax.bar_label(bars, fmt="%.4g")
        ax.grid(axis="y", alpha=0.25)
    fig.suptitle("Accepted-best downstream four-momentum reconstruction", x=0.06, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    path = figures / "four_momentum_accuracy.png"
    fig.savefig(path, dpi=160, metadata={"Date": None})
    plt.close(fig)
    produced.append(path)

    fig, ax = plt.subplots(figsize=(10.5, 5.5))
    for label, source, colour in zip(labels, sources, ("#1f3552", "#8f4aa8"), strict=True):
        bins = source["per_energy_bin"]
        centers = [(row["low_gev"] + row["high_gev"]) / 2 for row in bins]
        values = [row["rms_relative_fourvector_error"] for row in bins]
        ax.plot(centers, values, marker="o", lw=2, label=label, color=colour)
    ax.set_xlabel("Incident kinetic energy [GeV]")
    ax.set_ylabel("RMS relative four-vector error")
    ax.set_title("Four-momentum accuracy vs incident energy", loc="left")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    path = figures / "four_momentum_vs_energy.png"
    fig.savefig(path, dpi=160, metadata={"Date": None})
    plt.close(fig)
    produced.append(path)
    return produced


def run_four_momentum(args, manifest: dict, arrays: dict[str, np.ndarray]) -> dict:
    sys.path.insert(0, str(args.reco_repo / "src"))
    from zdc_reco.config import load_config
    from zdc_reco.physics import fourvector_from_kinetic_direction, unit_direction
    from zdc_reco.pipeline import _load_prediction_model, _predict_loaded

    geometry = json.loads(args.geometry_json.read_text(encoding="utf-8"))
    if geometry.get("geometry_sha256") != manifest.get("geometry_file_sha256"):
        raise ValueError("event-bank and reconstruction-adapter geometry hashes differ")
    frame_doc = json.loads(args.reco_frame_report.read_text(encoding="utf-8"))
    frame_payload = frame_doc["detector_frame"]
    cfg = load_config(args.reco_config)
    model, metadata, kind = _load_prediction_model(
        args.reco_model_dir.parents[1], args.reco_model_dir.name
    )
    calibration = json.loads((args.reco_model_dir / "calibration.json").read_text("utf-8"))
    mass = float(cfg["physics"]["neutron_mass_gev"])

    result = {}
    for key, label_value in (("geant4_reference", 1), ("fast_mc", 0)):
        indices = np.flatnonzero(arrays["label"] == label_value)
        features = _reco_features(
            arrays, indices, geometry, frame_payload, cfg["features"]
        )
        missing = sorted(set(metadata["feature_cols"]) - set(features.columns))
        if missing:
            raise ValueError(f"reconstruction adapter omitted model features: {missing}")
        predicted = _predict_loaded(model, metadata, kind, features, mass)
        direction, valid = unit_direction(predicted[:, 1:])
        direction[~valid] = np.asarray([0.0, 0.0, 1.0])
        corrected_total = np.maximum(
            float(calibration["energy_response_slope"]) * predicted[:, 0]
            + float(calibration["energy_response_intercept"]),
            mass,
        )
        corrected = fourvector_from_kinetic_direction(corrected_total - mass, direction, mass)
        result[key] = _fourvector_bundle(arrays["p4_total_gev"][indices], corrected)

    result["schema_version"] = 1
    result["kind"] = "cbsc-zdc-accepted-best-four-momentum-monitor"
    result["source_split"] = "validation"
    result["cbsc_test_events_used"] = 0
    result["checkpoint_sha256"] = manifest["checkpoint_sha256"]
    result["epoch"] = manifest["epoch"]
    result["run_tag"] = manifest["run_tag"]
    result["model_id"] = metadata["model_id"]
    result["model_artifact_hashes"] = {
        path.name: sha256_file(path) for path in sorted(args.reco_model_dir.iterdir()) if path.is_file()
    }
    result["external_repo_commit"] = args.reco_commit
    result["selection_role"] = "descriptive downstream evaluation only"
    result["adapter_note"] = (
        "Both Geant4 and Fast-MC deposits use the same frozen 6,790-channel readout adapter; "
        "the Geant4 result is the domain/reference control for interpreting Fast-MC accuracy."
    )
    paths = _plot_four_momentum(args.output_dir / "four_momentum", result)
    result["figures"] = [path.name for path in paths]
    write_json_atomic(args.output_dir / "four_momentum" / "metrics.json", result)
    return result


def _scored_report(labels, scores, p4, *, bootstrap: int, permutations: int, seed: int):
    from fastmc_tester.analysis import per_energy_report
    from fastmc_tester.metrics import full_report, indistinguishable

    report = full_report(
        labels, scores, n_bootstrap=bootstrap, n_permutations=permutations, seed=seed
    )
    report["per_energy_bin"] = per_energy_report(
        labels,
        scores,
        p4,
        edges=tuple(ENERGY_EDGES.tolist()),
        min_events=20,
    )
    report["statistically_indistinguishable"] = indistinguishable(report)
    return report


def _plot_auroc(output_dir: Path, results: dict) -> list[Path]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figures = output_dir / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    produced = []
    reports = results["models"]["hybrid"]["per_seed"]
    values = [row["auroc"] for row in reports]
    fig, ax = plt.subplots(figsize=(9, 5.2))
    ax.scatter(range(len(values)), values, color="#8f4aa8", s=55, label="Hybrid seeds")
    ax.axhline(results["models"]["hybrid"]["ensemble"]["auroc_mean"], color="#1f3552", lw=2, label="Seed mean")
    ax.axhline(0.5, color="#4c8b63", ls="--", lw=1.5, label="Chance")
    ax.set_xticks(range(len(values)), [str(row["seed"]) for row in reports])
    ax.set_xlabel("Independent evaluator seed")
    ax.set_ylabel("Monitoring-holdout AUROC")
    ax.set_title("Accepted-best low-level C2ST seed spread", loc="left")
    ax.set_ylim(0.45, 1.01)
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    path = figures / "auroc_seed_spread.png"
    fig.savefig(path, dpi=160, metadata={"Date": None})
    plt.close(fig)
    produced.append(path)

    fig, ax = plt.subplots(figsize=(10.5, 5.5))
    rows = reports[0]["per_energy_bin"]
    rows = [row for row in rows if row["auroc"] is not None]
    centers = [(row["low_gev"] + row["high_gev"]) / 2 for row in rows]
    ax.plot(centers, [row["auroc"] for row in rows], marker="o", color="#8f4aa8", lw=2)
    ax.axhline(0.5, color="#4c8b63", ls="--", lw=1.5)
    ax.set_xlabel("Incident kinetic energy [GeV]")
    ax.set_ylabel("Monitoring-holdout AUROC")
    ax.set_title("Accepted-best separability vs incident energy", loc="left")
    ax.set_ylim(0.45, 1.01)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    path = figures / "auroc_vs_energy.png"
    fig.savefig(path, dpi=160, metadata={"Date": None})
    plt.close(fig)
    produced.append(path)

    fig, ax = plt.subplots(figsize=(10.5, 5.5))
    for row in reports:
        history = row["history"]
        ax.plot(
            [entry["epoch"] for entry in history],
            [entry["validation_loss"] for entry in history],
            lw=1.6,
            label=f"seed {row['seed']}",
        )
    ax.set_xlabel("Evaluator training epoch")
    ax.set_ylabel("Evaluator validation BCE")
    ax.set_title("C2ST evaluator validation loss", loc="left")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=False, ncol=2)
    fig.tight_layout()
    path = figures / "auroc_evaluator_training.png"
    fig.savefig(path, dpi=160, metadata={"Date": None})
    plt.close(fig)
    produced.append(path)
    return produced


def monitoring_corpus_summary(summary: dict) -> dict:
    """Rename the evaluator library's code-2 partition for scientific clarity."""
    counts = dict(summary.get("partition_counts", {}))
    if set(counts) != {"train", "validation", "test"}:
        raise ValueError("unexpected evaluator partition-count schema")
    normalized = dict(summary)
    normalized["partition_counts"] = {
        "train": counts["train"],
        "validation": counts["validation"],
        "monitoring_holdout": counts["test"],
    }
    return normalized


def configure_deterministic_evaluator(torch) -> dict:
    """Fail closed on nondeterministic evaluator operations."""
    torch.use_deterministic_algorithms(True)
    if torch.cuda.is_available():
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = True
    return {
        "torch_deterministic_algorithms": True,
        "cudnn_benchmark": bool(torch.backends.cudnn.benchmark),
        "cudnn_deterministic": bool(torch.backends.cudnn.deterministic),
        "cublas_workspace_config": os.environ.get("CUBLAS_WORKSPACE_CONFIG"),
    }


def run_auroc(args, manifest: dict, arrays: dict[str, np.ndarray]) -> dict:
    sys.path.insert(0, str(args.auroc_repo / "src"))
    import torch
    from fastmc_tester.analysis import seed_ensemble
    from fastmc_tester.corpus import SparseCorpus, summarise
    from fastmc_tester.geometry import load_geometry
    from fastmc_tester.train import TrainConfig, gradient_boosting_control, train_discriminator

    config = json.loads(args.auroc_config.read_text(encoding="utf-8"))
    determinism = configure_deterministic_evaluator(torch)
    if args.device.startswith("cuda") and determinism["cublas_workspace_config"] not in {
        ":4096:8",
        ":16:8",
    }:
        raise RuntimeError("CUDA evaluator requires deterministic CUBLAS workspace config")
    partition = paired_stratified_partitions(
        arrays["pair_id"],
        arrays["p4_total_gev"],
        seed=int(config["partition_seed"]),
        fractions=tuple(config["partition_fractions"]),
    )
    corpus = SparseCorpus(
        event_ptr=arrays["event_ptr"],
        cell_index=arrays["cell_index"],
        cell_energy_gev=arrays["cell_energy_gev"],
        p4_total_gev=arrays["p4_total_gev"],
        label=arrays["label"],
        family_id=arrays["family_id"],
        source_event_id=arrays["source_event_id"],
        partition=partition,
    )
    geometry = load_geometry(args.auroc_geometry, verify_hash=True)
    corpus.validate(geometry.n_nodes)
    for code in (0, 1, 2):
        selected = partition == code
        if int(np.sum(arrays["label"][selected] == 1)) != int(
            np.sum(arrays["label"][selected] == 0)
        ):
            raise RuntimeError("evaluator partition is not class balanced")

    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested for AUROC monitor but is unavailable")
    train_kwargs = dict(config["train"])
    bootstrap = int(config["n_bootstrap"])
    permutations = int(config["n_permutations"])
    hybrid_reports = []
    hybrid_results = []
    for seed in config["seeds"]:
        trained = train_discriminator(
            corpus,
            geometry,
            TrainConfig(model="hybrid", seed=int(seed), **train_kwargs),
            device,
            log=print,
        )
        report = _scored_report(
            trained.test_labels,
            trained.test_scores,
            corpus.p4_total_gev[partition == 2],
            bootstrap=bootstrap,
            permutations=permutations,
            seed=int(seed),
        )
        report.update(
            {
                "seed": int(seed),
                "best_validation_loss": trained.best_validation_loss,
                "best_epoch": trained.best_epoch,
                "history": trained.history,
                "parameters": trained.parameters,
                "seconds": trained.seconds,
            }
        )
        hybrid_reports.append(report)
        hybrid_results.append(trained)

    best_index = int(np.argmin([row.best_validation_loss for row in hybrid_results]))
    best = hybrid_results[best_index]
    evaluator_path = args.output_dir / "auroc" / "best_evaluator.pt"
    evaluator_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "state_dict": best.state_dict,
            "seed": int(config["seeds"][best_index]),
            "best_validation_loss": best.best_validation_loss,
            "train_config": asdict(
                TrainConfig(
                    model="hybrid", seed=int(config["seeds"][best_index]), **train_kwargs
                )
            ),
            "not_a_cbsc_generator_checkpoint": True,
        },
        evaluator_path,
    )

    condition = train_discriminator(
        corpus,
        geometry,
        TrainConfig(model="condition_only", seed=0, **train_kwargs),
        device,
        log=print,
    )
    condition_report = _scored_report(
        condition.test_labels,
        condition.test_scores,
        corpus.p4_total_gev[partition == 2],
        bootstrap=bootstrap,
        permutations=permutations,
        seed=0,
    )
    condition_report.update(
        {
            "best_validation_loss": condition.best_validation_loss,
            "best_epoch": condition.best_epoch,
            "history": condition.history,
        }
    )
    gbm = gradient_boosting_control(corpus, geometry)
    high_level = _scored_report(
        gbm["test_labels"],
        gbm["test_scores"],
        corpus.p4_total_gev[partition == 2],
        bootstrap=bootstrap,
        permutations=permutations,
        seed=0,
    )
    high_level["feature_names"] = gbm["feature_names"]

    results = {
        "schema_version": 1,
        "kind": "cbsc-zdc-accepted-best-validation-c2st-monitor",
        "source_split": "validation",
        "evaluator_partitions": {
            "train": int(np.sum(partition == 0)),
            "validation": int(np.sum(partition == 1)),
            "monitoring_holdout": int(np.sum(partition == 2)),
            "pair_grouped": True,
            "energy_stratified": True,
            "seed": int(config["partition_seed"]),
        },
        "cbsc_test_events_used": 0,
        "checkpoint_sha256": manifest["checkpoint_sha256"],
        "epoch": manifest["epoch"],
        "run_tag": manifest["run_tag"],
        "external_repo_commit": args.auroc_commit,
        "determinism": determinism,
        "selection_role": "descriptive downstream evaluation only",
        "interpretation": (
            "High AUROC proves separability; low AUROC means only that this evaluator "
            "failed to separate the samples at this representation and sample size."
        ),
        "corpus": monitoring_corpus_summary(summarise(corpus)),
        "models": {
            "hybrid": {
                "per_seed": hybrid_reports,
                "ensemble": seed_ensemble(hybrid_reports),
                "selected_seed": int(config["seeds"][best_index]),
                "selected_validation_loss": best.best_validation_loss,
                "evaluator_checkpoint_sha256": sha256_file(evaluator_path),
            },
            "condition_only_control": condition_report,
            "high_level_gbm_control": high_level,
        },
    }
    paths = _plot_auroc(args.output_dir / "auroc", results)
    results["figures"] = [path.name for path in paths]
    write_json_atomic(args.output_dir / "auroc" / "metrics.json", results)
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bank", type=Path, required=True)
    parser.add_argument("--bank-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--mode", choices=("all", "four-momentum", "auroc"), default="all"
    )
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--geometry-json", type=Path, required=True)
    parser.add_argument("--reco-repo", type=Path, required=True)
    parser.add_argument("--reco-commit", required=True)
    parser.add_argument("--reco-model-dir", type=Path, required=True)
    parser.add_argument("--reco-config", type=Path, required=True)
    parser.add_argument("--reco-frame-report", type=Path, required=True)
    parser.add_argument("--auroc-repo", type=Path, required=True)
    parser.add_argument("--auroc-commit", required=True)
    parser.add_argument("--auroc-config", type=Path, required=True)
    parser.add_argument("--auroc-geometry", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    started = time.time()
    manifest, arrays = load_bank(args.bank, args.bank_manifest)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    result = {
        "schema_version": 1,
        "kind": "cbsc-zdc-accepted-best-external-metrics-transaction",
        "status": "complete",
        "checkpoint_sha256": manifest["checkpoint_sha256"],
        "family": manifest["family"],
        "run_tag": manifest["run_tag"],
        "epoch": manifest["epoch"],
        "validation_loss": manifest["validation_loss"],
        "bank_sha256": manifest["bank_sha256"],
        "source_split": "validation",
        "cbsc_test_events_used": 0,
        "checkpoint_selection_quantity": "accepted validation loss only",
        "external_metrics_may_select_or_tune_cbsc": False,
        "environment": _environment(),
        "outputs": {},
    }
    if args.mode in ("all", "four-momentum"):
        result["outputs"]["four_momentum"] = run_four_momentum(args, manifest, arrays)
    if args.mode in ("all", "auroc"):
        result["outputs"]["auroc"] = run_auroc(args, manifest, arrays)
    result["seconds"] = time.time() - started
    tracked = sorted(
        path
        for path in args.output_dir.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    )
    result["artifacts"] = [
        {
            "path": path.relative_to(args.output_dir).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
            "availability": (
                "remote_only" if path.name == "best_evaluator.pt" else "exhibition"
            ),
            "purpose": (
                "evaluator checkpoint; never a CBSC generator checkpoint"
                if path.name == "best_evaluator.pt"
                else "accepted-best downstream metric evidence"
            ),
        }
        for path in tracked
    ]
    write_json_atomic(args.output_dir / "manifest.json", result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
