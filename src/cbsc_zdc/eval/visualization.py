from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch

from ..contracts import mass_shell_diagnostics, validate_p4_total
from ..data.dataset import ShardedSparseDataset, load_geometry
from ..utils import load_json, sha256_file, sha256_json
from .invariants import closure_tolerances, invariant_report
from .metrics import distribution_metrics, high_level_features, layer_sums


SCHEMA_VERSION = 1
FEATURE_NAMES = [
    "total_response_gev",
    "hit_count",
    "depth_centroid_layer",
    "x_centroid_mm",
    "y_centroid_mm",
    "radial_rms_mm",
    "top1_fraction",
    "ecal_fraction",
    "late_fraction",
]


def _write_json_atomic(payload: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, separators=(",", ":"), sort_keys=True)
        handle.write("\n")
    temporary.replace(path)


def fixed_validation_indices(length: int, count: int, seed: int) -> list[int]:
    if length <= 0:
        raise ValueError("visualization validation selection is empty")
    if count <= 0:
        raise ValueError("visualization sample_count must be positive")
    if count > length:
        raise ValueError(
            f"visualization sample_count={count} exceeds validation events={length}"
        )
    rng = np.random.default_rng(seed)
    return [int(value) for value in rng.choice(length, size=count, replace=False)]


def _sparse_event(cell_energy: np.ndarray) -> dict[str, Any]:
    indices = np.flatnonzero(cell_energy > 0)
    energy = cell_energy[indices].astype(np.float32, copy=False)
    return {
        "cell_index": indices.astype(np.int32, copy=False).tolist(),
        "energy_gev": energy.tolist(),
    }


def _event_summary(
    cell_energy: np.ndarray,
    layer_index: np.ndarray,
    positions_mm: np.ndarray,
) -> dict[str, Any]:
    feature_values = high_level_features(
        cell_energy[None], layer_index, positions_mm
    )[0]
    layers = layer_sums(cell_energy[None], layer_index)[0]
    return {
        **{
            name: float(value)
            for name, value in zip(FEATURE_NAMES, feature_values, strict=True)
        },
        "layer_energy_gev": layers.astype(np.float32, copy=False).tolist(),
    }


def _reduce_invariants(reports: list[dict[str, Any]]) -> dict[str, Any]:
    if not reports:
        raise ValueError("no invariant reports were produced")
    reduced: dict[str, Any] = {"pass": all(bool(row["pass"]) for row in reports)}
    for key in reports[0]:
        if key == "pass":
            continue
        reduced[key] = max(row[key] for row in reports)
    return reduced


def _geometry_payload(
    geometry: dict[str, torch.Tensor],
    geometry_hash: str,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "geometry_sha256": geometry_hash,
        "n_nodes": int(geometry["positions_mm"].shape[0]),
        "positions_mm": geometry["positions_mm"].cpu().numpy().tolist(),
        "layer_index": geometry["layer_index"].cpu().numpy().tolist(),
        "subdetector": geometry["subdetector"].cpu().numpy().tolist(),
    }


def export_epoch_visualization(
    model,
    config: dict[str, Any],
    epoch: int,
    destination: str | Path,
    checkpoint_path: str | Path,
) -> dict[str, Any]:
    """Export a fixed validation bank with five conditional draws per event.

    This artifact is descriptive validation evidence. It is never a checkpoint
    selection metric and never reads the test split.
    """
    settings = config.get("evaluation", {}).get("visualization", {})
    if not bool(settings.get("enabled", False)):
        return {"enabled": False}
    if settings.get("split", "validation") != "validation":
        raise ValueError("epoch visualization is restricted to validation data")

    started = time.perf_counter()
    sample_count = int(settings.get("sample_count", 50))
    draws = int(settings.get("draws_per_condition", 5))
    selection_seed = int(settings.get("selection_seed", 20260725))
    generation_seed = int(settings.get("generation_seed", 20260725))
    profile_steps = int(config["evaluation"].get("profile_steps", 8))
    share_steps = int(config["evaluation"].get("share_steps", 8))
    tolerance, relative_tolerance = closure_tolerances(config)
    stage = str(config["training"].get("stage", "joint"))
    device = model.node_features.device
    output_dir = Path(destination)
    output_path = output_dir / f"epoch_{epoch:04d}.json"
    if output_path.exists():
        raise FileExistsError(f"visualization epoch artifact already exists: {output_path}")
    checkpoint_hash = sha256_file(checkpoint_path)

    data = config["data"]
    dataset = ShardedSparseDataset(
        data["manifest"],
        data["splits"],
        "validation",
        tuple(float(value) for value in data["evaluation_kinetic_gev"]),
        int(config["geometry"]["n_nodes"]),
    )
    synthetic_source = bool(dataset.manifest.get("synthetic", False))
    selected = fixed_validation_indices(len(dataset), sample_count, selection_seed)
    items = [dataset[index] for index in selected]
    p4 = torch.stack([item["p4_total_gev"] for item in items])
    validate_p4_total(p4)
    truth = torch.stack([item["cell_energy_gev"] for item in items]).numpy()
    if not np.isfinite(truth).all() or (truth < 0).any():
        raise RuntimeError("visualization truth contains nonfinite or negative energy")

    geometry = load_geometry(config["geometry"]["path"], "cpu")
    positions = geometry["positions_mm"].numpy()
    layer_index = geometry["layer_index"].numpy()
    geometry_source = Path(config["geometry"]["path"])
    if geometry_source.is_dir():
        geometry_source = geometry_source / "geometry.npz"
    geometry_hash = sha256_file(geometry_source)

    geometry_path = output_dir / "geometry.json"
    if not geometry_path.exists():
        _write_json_atomic(_geometry_payload(geometry, geometry_hash), geometry_path)
    else:
        existing_geometry = load_json(geometry_path)
        if existing_geometry.get("geometry_sha256") != geometry_hash:
            raise RuntimeError("visualization geometry hash changed inside one run")

    generated = np.empty(
        (sample_count, draws, int(config["geometry"]["n_nodes"])),
        dtype=np.float32,
    )
    invariant_rows: list[dict[str, Any]] = []
    generation_seeds: list[int] = []
    model.eval()
    with torch.no_grad():
        for event_position, item in enumerate(items):
            seed = generation_seed + epoch * 1_000_003 + event_position * 10_007
            generation_seeds.append(seed)
            repeated_p4 = item["p4_total_gev"].to(device).repeat(draws, 1)
            output = model.sample(
                repeated_p4,
                profile_steps=profile_steps,
                share_steps=share_steps,
                seed=seed,
                stochastic=True,
            )
            invariant_row = invariant_report(
                output,
                model.layer_index,
                model.valid_mask,
                model.threshold_gev,
                tolerance,
                relative_tolerance,
            )
            invariant_row.update(
                {
                    "selection_position": int(event_position),
                    "dataset_index": int(selected[event_position]),
                    "global_index": int(item["global_index"]),
                    "event_id": int(item["event_id"]),
                    "generation_seed": int(seed),
                    "kinetic_energy_gev": float(item["kinetic_energy_gev"]),
                    "total_response_max_gev": float(output.total_response.max()),
                }
            )
            invariant_rows.append(invariant_row)
            generated[event_position] = output.cell_energy.cpu().numpy()

    if not np.isfinite(generated).all() or (generated < 0).any():
        raise RuntimeError("visualization generation contains nonfinite or negative energy")
    invariants = _reduce_invariants(invariant_rows)
    if not invariants["pass"]:
        _write_json_atomic(
            {
                "schema_version": SCHEMA_VERSION,
                "kind": "cbsc-zdc-epoch-visualization-invariant-failure",
                "scientific_status": (
                    "artifact quarantined; required validation visualization "
                    "failed structural invariants"
                ),
                "epoch": int(epoch),
                "split": "validation",
                "test_events_used": 0,
                "checkpoint_sha256": checkpoint_hash,
                "tolerance_gev": tolerance,
                "closure_tolerance_relative": relative_tolerance,
                "sample_count": sample_count,
                "draws_per_condition": draws,
                "profile_steps": profile_steps,
                "share_steps": share_steps,
                "invariants": invariants,
                "rows": invariant_rows,
            },
            output_dir / f"invariant_failure_epoch_{epoch:04d}.json",
        )
        raise RuntimeError(
            f"epoch {epoch} visualization generation failed structural invariants"
        )

    groups = []
    for position, item in enumerate(items):
        fast_mc = []
        for draw in range(draws):
            cells = generated[position, draw]
            fast_mc.append(
                {
                    "draw": draw,
                    "seed_group": generation_seeds[position],
                    "deposit": _sparse_event(cells),
                    "summary": _event_summary(cells, layer_index, positions),
                }
            )
        truth_cells = truth[position]
        groups.append(
            {
                "selection_position": position,
                "dataset_index": selected[position],
                "global_index": int(item["global_index"]),
                "event_id": int(item["event_id"]),
                "source_group": int(item["source_group"]),
                "kinetic_energy_gev": float(item["kinetic_energy_gev"]),
                "p4_total_gev": item["p4_total_gev"].tolist(),
                "geant4": {
                    "deposit": _sparse_event(truth_cells),
                    "summary": _event_summary(truth_cells, layer_index, positions),
                },
                "fast_mc": fast_mc,
            }
        )

    per_draw_metrics = [
        distribution_metrics(
            truth,
            generated[:, draw],
            layer_index,
            positions,
            selection_seed + draw,
        )
        for draw in range(draws)
    ]
    truth_features = high_level_features(truth, layer_index, positions)
    generated_features = high_level_features(
        generated.reshape(sample_count * draws, generated.shape[-1]),
        layer_index,
        positions,
    )
    truth_response_mean = float(truth_features[:, 0].mean())
    generated_response_mean = float(generated_features[:, 0].mean())
    truth_hit_mean = float(truth_features[:, 1].mean())
    generated_hit_mean = float(generated_features[:, 1].mean())
    trend = {
        "truth_response_mean_gev": truth_response_mean,
        "generated_response_mean_gev": generated_response_mean,
        "response_bias_fraction": (
            (generated_response_mean - truth_response_mean)
            / max(abs(truth_response_mean), 1e-9)
        ),
        "truth_hit_count_mean": truth_hit_mean,
        "generated_hit_count_mean": generated_hit_mean,
        "hit_count_bias_fraction": (
            (generated_hit_mean - truth_hit_mean) / max(abs(truth_hit_mean), 1e-9)
        ),
        "mean_longitudinal_profile_relative_l1": float(
            np.mean(
                [
                    row["mean_longitudinal_profile"]["relative_l1"]
                    for row in per_draw_metrics
                ]
            )
        ),
    }
    mass_shell = mass_shell_diagnostics(p4)
    selection_contract = {
        "split": "validation",
        "evaluation_kinetic_gev": [
            float(value) for value in data["evaluation_kinetic_gev"]
        ],
        "selection_seed": selection_seed,
        "dataset_indices": selected,
        "global_indices": [int(item["global_index"]) for item in items],
        "event_ids": [int(item["event_id"]) for item in items],
    }
    selection_hash = sha256_json(selection_contract)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "kind": "cbsc-zdc-epoch-visual-comparison",
        "scientific_status": (
            "synthetic interface QA fixture; not Geant4 and not physics validation"
            if synthetic_source
            else (
                "joint-stage validation visualization; descriptive, not a fidelity gate"
                if stage == "joint"
                else "component-stage structural diagnostic; full cascade fidelity is not established"
            )
        ),
        "synthetic_source": synthetic_source,
        "epoch": int(epoch),
        "stage": stage,
        "checkpoint_sha256": checkpoint_hash,
        "geometry_sha256": geometry_hash,
        "manifest_sha256": sha256_file(data["manifest"]),
        "splits_sha256": sha256_file(data["splits"]),
        "split": "validation",
        "sample_count": sample_count,
        "draws_per_condition": draws,
        "profile_steps": profile_steps,
        "share_steps": share_steps,
        "selection": selection_contract,
        "selection_sha256": selection_hash,
        "generation_seeds": generation_seeds,
        "groups": groups,
        "aggregate": {
            "feature_names": FEATURE_NAMES,
            "per_draw_distribution_metrics": per_draw_metrics,
            "trend": trend,
        },
        "qa": {
            "pass": True,
            "test_events_used": 0,
            "selection_unique": len(set(selected)) == sample_count,
            "groups_with_exact_draw_count": sum(
                len(group["fast_mc"]) == draws for group in groups
            ),
            "truth_nonfinite": int((~np.isfinite(truth)).sum()),
            "generated_nonfinite": int((~np.isfinite(generated)).sum()),
            "truth_negative": int((truth < 0).sum()),
            "generated_negative": int((generated < 0).sum()),
            "mass_shell_relative_residual_max": float(
                mass_shell["relative_energy_residual"].max()
            ),
            "invariants": invariants,
        },
        "elapsed_seconds": time.perf_counter() - started,
    }
    _write_json_atomic(payload, output_path)

    manifest_path = output_dir / "manifest.json"
    manifest = (
        load_json(manifest_path)
        if manifest_path.exists()
        else {
            "schema_version": SCHEMA_VERSION,
            "geometry_path": "geometry.json",
            "geometry_sha256": geometry_hash,
            "selection_sha256": selection_hash,
            "epochs": [],
        }
    )
    if manifest.get("geometry_sha256") != geometry_hash:
        raise RuntimeError("visualization manifest geometry hash mismatch")
    if manifest.get("selection_sha256") != selection_hash:
        raise RuntimeError("visualization validation selection changed across epochs")
    manifest["epochs"].append(
        {
            "epoch": int(epoch),
            "stage": stage,
            "path": output_path.name,
            "sha256": sha256_file(output_path),
            "checkpoint_sha256": checkpoint_hash,
            "qa_pass": True,
            "elapsed_seconds": payload["elapsed_seconds"],
            "trend": trend,
        }
    )
    manifest["latest_epoch"] = int(epoch)
    _write_json_atomic(manifest, manifest_path)
    return manifest["epochs"][-1]
