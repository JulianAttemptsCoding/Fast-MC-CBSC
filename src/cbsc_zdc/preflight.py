from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from .data.dataset import ShardedSparseDataset
from .data.geometry import geometry_hash
from .utils import load_json, sha256_file


def _contains_unfrozen(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_contains_unfrozen(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_unfrozen(item) for item in value)
    return isinstance(value, str) and value == "UNFROZEN"


def validate_frozen_artifacts(
    config: dict[str, Any],
    *,
    verify_shards: bool = True,
) -> dict[str, Any]:
    """Fail closed when staged artifacts do not match the frozen experiment.

    This validates runtime path rewrites against the hashes and geometry identity
    frozen before upload. It deliberately does not inspect test metrics or make
    any model-selection decision.
    """
    if _contains_unfrozen(config):
        raise RuntimeError("configuration still contains UNFROZEN values")

    provenance = config.get("provenance", {})
    required_provenance = {
        "geometry_manifest_sha256",
        "dataset_manifest_sha256",
        "split_manifest_sha256",
        "dataset_geometry_hash",
        "split_assignment_sha256",
    }
    missing = sorted(required_provenance - set(provenance))
    if missing:
        raise RuntimeError(f"frozen provenance is incomplete: {missing}")

    geometry_dir = Path(config["geometry"]["path"])
    geometry_npz = geometry_dir / "geometry.npz" if geometry_dir.is_dir() else geometry_dir
    geometry_manifest_path = (
        geometry_dir / "geometry_manifest.json"
        if geometry_dir.is_dir()
        else geometry_dir.with_name("geometry_manifest.json")
    )
    manifest_path = Path(config["data"]["manifest"])
    split_path = Path(config["data"]["splits"])
    assignment_path: Path | None = None

    for path in (geometry_npz, geometry_manifest_path, manifest_path, split_path):
        if not path.is_file():
            raise FileNotFoundError(f"required frozen artifact is missing: {path}")

    actual_hashes = {
        "geometry_manifest_sha256": sha256_file(geometry_manifest_path),
        "dataset_manifest_sha256": sha256_file(manifest_path),
        "split_manifest_sha256": sha256_file(split_path),
    }
    for name, actual in actual_hashes.items():
        if actual != provenance[name]:
            raise RuntimeError(
                f"{name} mismatch: frozen={provenance[name]} staged={actual}"
            )

    geometry_manifest = load_json(geometry_manifest_path)
    dataset_manifest = load_json(manifest_path)
    split_manifest = load_json(split_path)
    assignment_path = split_path.parent / split_manifest["assignment_file"]
    if not assignment_path.is_file():
        raise FileNotFoundError(f"split assignment is missing: {assignment_path}")
    assignment_hash = sha256_file(assignment_path)
    if assignment_hash != provenance["split_assignment_sha256"]:
        raise RuntimeError(
            "split assignment hash mismatch: "
            f"frozen={provenance['split_assignment_sha256']} staged={assignment_hash}"
        )
    if assignment_hash != split_manifest.get("assignment_sha256"):
        raise RuntimeError("split manifest contains the wrong assignment hash")

    with np.load(geometry_npz, allow_pickle=False) as archive:
        geometry_arrays = {name: archive[name] for name in archive.files}
    computed_geometry_hash = geometry_hash(geometry_arrays)
    geometry_identities = {
        "computed": computed_geometry_hash,
        "geometry_manifest": geometry_manifest.get("geometry_hash"),
        "dataset_manifest": dataset_manifest.get("geometry_hash"),
        "config": config["geometry"].get("geometry_hash"),
        "frozen_provenance": provenance.get("dataset_geometry_hash"),
    }
    if len(set(geometry_identities.values())) != 1:
        raise RuntimeError(f"geometry identity mismatch: {geometry_identities}")

    expected_nodes = int(config["geometry"]["n_nodes"])
    expected_layers = int(config["geometry"]["n_layers"])
    if int(geometry_manifest["n_nodes"]) != expected_nodes:
        raise RuntimeError("configured node count does not match geometry manifest")
    if int(geometry_manifest["n_layers"]) != expected_layers:
        raise RuntimeError("configured layer count does not match geometry manifest")
    if int(dataset_manifest["n_nodes"]) != expected_nodes:
        raise RuntimeError("dataset node count does not match frozen geometry")
    if int(dataset_manifest["n_layers"]) != expected_layers:
        raise RuntimeError("dataset layer count does not match frozen geometry")
    if dataset_manifest.get("target_mode") != config["data"]["target_mode"]:
        raise RuntimeError("dataset target mode does not match frozen configuration")
    if float(dataset_manifest.get("threshold_gev", 0.0)) != float(
        config["data"].get("threshold_gev", 0.0)
    ):
        raise RuntimeError("dataset threshold does not match frozen configuration")

    dataset = ShardedSparseDataset(
        manifest_path,
        split_path,
        "train",
        tuple(float(x) for x in config["data"]["train_kinetic_gev"]),
        expected_nodes,
    )
    validation = ShardedSparseDataset(
        manifest_path,
        split_path,
        "validation",
        tuple(float(x) for x in config["data"]["evaluation_kinetic_gev"]),
        expected_nodes,
    )
    test = ShardedSparseDataset(
        manifest_path,
        split_path,
        "test",
        tuple(float(x) for x in config["data"]["evaluation_kinetic_gev"]),
        expected_nodes,
    )
    counts = {
        "train": len(dataset),
        "validation": len(validation),
        "test": len(test),
    }
    required_counts = (
        ("train", "validation")
        if bool(config.get("project", {}).get("pilot", False))
        else ("train", "validation", "test")
    )
    if any(counts[name] <= 0 for name in required_counts):
        raise RuntimeError(f"frozen split/range selection is empty: {counts}")

    verified_shards = 0
    if verify_shards:
        for shard_index in range(len(dataset.shards)):
            dataset._load_shard(shard_index)
            verified_shards += 1

    return {
        "pass": True,
        "geometry_hash": computed_geometry_hash,
        "hashes": {
            **actual_hashes,
            "split_assignment_sha256": assignment_hash,
            "geometry_npz_sha256": sha256_file(geometry_npz),
        },
        "selection_counts": counts,
        "verified_shards": verified_shards,
        "verify_shards": verify_shards,
        "group_by": split_manifest.get("group_by"),
        "synthetic": bool(dataset_manifest.get("synthetic", False)),
    }
