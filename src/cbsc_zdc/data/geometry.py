from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from .root_io import channel_key, collection_hits, iter_root_chunks, load_branch_schema
from ..contracts import DetectorSpec
from ..utils import dump_json, sha256_file, sha256_json


def _cluster_axis(values: np.ndarray, tolerance_mm: float) -> np.ndarray:
    if values.size == 0:
        return np.empty(0, dtype=np.float64)
    ordered = np.sort(values.astype(np.float64))
    groups: list[list[float]] = [[float(ordered[0])]]
    for value in ordered[1:]:
        if abs(float(value) - np.mean(groups[-1])) <= tolerance_mm:
            groups[-1].append(float(value))
        else:
            groups.append([float(value)])
    return np.array([np.median(group) for group in groups], dtype=np.float64)


def _nearest_layer(z: float, centers: np.ndarray) -> int:
    return int(np.argmin(np.abs(centers - z)))


def build_edges(
    positions_mm: np.ndarray,
    layer_index: np.ndarray,
    lateral_k: int = 8,
    longitudinal_k: int = 4,
) -> tuple[np.ndarray, np.ndarray]:
    sources: list[int] = []
    targets: list[int] = []
    features: list[list[float]] = []
    n_layers = int(layer_index.max()) + 1
    scale = np.std(positions_mm, axis=0)
    scale[scale < 1e-6] = 1.0

    def add_edge(source: int, target: int, edge_type: float) -> None:
        delta = (positions_mm[target] - positions_mm[source]) / scale
        distance = float(np.linalg.norm(delta))
        sources.append(source)
        targets.append(target)
        features.append([float(delta[0]), float(delta[1]), float(delta[2]), distance, edge_type])

    for layer in range(n_layers):
        ids = np.where(layer_index == layer)[0]
        if ids.size <= 1:
            continue
        xy = positions_mm[ids, :2]
        distance2 = ((xy[:, None, :] - xy[None, :, :]) ** 2).sum(axis=-1)
        np.fill_diagonal(distance2, np.inf)
        k = min(lateral_k, ids.size - 1)
        neighbors = np.argpartition(distance2, kth=k - 1, axis=1)[:, :k]
        for row, local_neighbors in enumerate(neighbors):
            for neighbor in local_neighbors:
                add_edge(int(ids[row]), int(ids[neighbor]), 0.0)

    for layer in range(n_layers - 1):
        source_ids = np.where(layer_index == layer)[0]
        target_ids = np.where(layer_index == layer + 1)[0]
        if source_ids.size == 0 or target_ids.size == 0:
            continue
        distance2 = (
            (positions_mm[source_ids, None, :2] - positions_mm[target_ids][None, :, :2]) ** 2
        ).sum(axis=-1)
        k = min(longitudinal_k, target_ids.size)
        neighbors = np.argpartition(distance2, kth=k - 1, axis=1)[:, :k]
        for row, local_neighbors in enumerate(neighbors):
            for neighbor in local_neighbors:
                add_edge(int(source_ids[row]), int(target_ids[neighbor]), 1.0)
                add_edge(int(target_ids[neighbor]), int(source_ids[row]), -1.0)

    edge_index = np.asarray([sources, targets], dtype=np.int64)
    edge_features = np.asarray(features, dtype=np.float32)
    return edge_index, edge_features


def geometry_hash(arrays: dict[str, np.ndarray]) -> str:
    payload = {}
    for key in sorted(arrays):
        value = np.ascontiguousarray(arrays[key])
        payload[key] = {
            "shape": list(value.shape),
            "dtype": str(value.dtype),
            "sha256": __import__("hashlib").sha256(value.tobytes()).hexdigest(),
        }
    return sha256_json(payload)


def _merge_physical_positions(
    observation: dict[str, Any],
    positions_mm: np.ndarray,
    tolerance_mm: float,
) -> None:
    """Record distinct physical centers contributing to one readout channel.

    Production HCAL readout IDs can gang multiple physical scintillator positions.
    Repeated hits at one physical position must be stable, but distinct positions
    sharing a readout ID are retained and later represented by their unweighted
    centroid. Weighting by hit frequency would leak shower-distribution information
    into static geometry.
    """
    if tolerance_mm <= 0:
        raise ValueError("position tolerance must be positive")
    quantized = np.rint(
        positions_mm.astype(np.float64, copy=False) / tolerance_mm
    ).astype(np.int64)
    unique_quantized, first_indices = np.unique(
        quantized, axis=0, return_index=True
    )
    physical = observation.setdefault("physical_positions", {})
    for rounded, index in zip(unique_quantized, first_indices):
        rounded_key = tuple(int(value) for value in rounded)
        position = positions_mm[int(index)].astype(np.float64, copy=True)
        previous = physical.get(rounded_key)
        if previous is not None and float(np.max(np.abs(previous - position))) > (
            2.0 * tolerance_mm
        ):
            raise ValueError(
                "a physical position changed within its tolerance bucket"
            )
        physical.setdefault(rounded_key, position)


def scan_geometry(
    root_paths: list[str | Path],
    schema_path: str | Path,
    output_dir: str | Path,
    strict_project_counts: bool = True,
    position_tolerance_mm: float = 1e-3,
    z_tolerance_mm: float = 1e-2,
    step_size: int = 2048,
) -> dict[str, Any]:
    schema = load_branch_schema(schema_path)
    observations: dict[tuple[int, int | None, int], dict[str, Any]] = {}
    collection_names = [(0, schema.ecal), (1, schema.hcal)]
    for source, start, arrays in iter_root_chunks(root_paths, schema, step_size=step_size):
        if start % max(step_size * 25, 1) == 0:
            print(
                f"geometry-scan source={source.name} entry_start={start}",
                flush=True,
            )
        for subdetector, collection in collection_names:
            cell_id, layer_id, _, x, y, z = collection_hits(arrays, collection, schema)
            try:
                import awkward as ak  # type: ignore
            except ImportError as exc:
                raise RuntimeError("awkward is required for geometry scanning") from exc
            flat_id = ak.to_numpy(ak.flatten(cell_id, axis=None))
            flat_layer = (
                ak.to_numpy(ak.flatten(layer_id, axis=None))
                if layer_id is not None
                else np.full(flat_id.shape, -1, dtype=np.int64)
            )
            flat_x = ak.to_numpy(ak.flatten(x, axis=None))
            flat_y = ak.to_numpy(ak.flatten(y, axis=None))
            flat_z = ak.to_numpy(ak.flatten(z, axis=None))
            if flat_id.size == 0:
                continue
            order = np.lexsort((flat_id, flat_layer))
            ordered_id = flat_id[order]
            ordered_layer = flat_layer[order]
            ordered_positions = np.stack(
                [flat_x[order], flat_y[order], flat_z[order]], axis=1
            ).astype(np.float64, copy=False)
            starts = np.concatenate(
                [
                    np.array([0], dtype=np.int64),
                    np.where(
                        (ordered_id[1:] != ordered_id[:-1])
                        | (ordered_layer[1:] != ordered_layer[:-1])
                    )[0]
                    + 1,
                ]
            )
            counts = np.diff(np.append(starts, len(ordered_id)))
            for group_index, start_index in enumerate(starts):
                end_index = (
                    int(starts[group_index + 1])
                    if group_index + 1 < len(starts)
                    else len(ordered_id)
                )
                cid = ordered_id[start_index]
                raw_layer = ordered_layer[start_index]
                source_layer = int(raw_layer) if layer_id is not None else None
                key = (subdetector, source_layer, int(cid))
                if key not in observations:
                    observations[key] = {
                        "count": int(counts[group_index]),
                    }
                else:
                    record = observations[key]
                    record["count"] += int(counts[group_index])
                _merge_physical_positions(
                    observations[key],
                    ordered_positions[start_index:end_index],
                    position_tolerance_mm,
                )

    if not observations:
        raise ValueError("no valid calorimeter cells were observed")
    records = []
    for (subdetector, source_layer, cell_id), observation in observations.items():
        physical_positions = np.stack(
            list(observation["physical_positions"].values())
        )
        center = physical_positions.mean(axis=0)
        records.append(
            (
                subdetector,
                source_layer,
                cell_id,
                *center.tolist(),
                int(len(physical_positions)),
            )
        )

    ecal_z = _cluster_axis(np.array([r[5] for r in records if r[0] == 0]), z_tolerance_mm)
    hcal_z = _cluster_axis(np.array([r[5] for r in records if r[0] == 1]), z_tolerance_mm)
    hcal_source_layers = sorted(
        {int(r[1]) for r in records if r[0] == 1 and r[1] is not None}
    )
    hcal_has_unlayered = any(r[0] == 1 and r[1] is None for r in records)
    if hcal_source_layers and hcal_has_unlayered:
        raise ValueError("HCAL geometry mixes explicit and implicit layer identifiers")
    if ecal_z.size == 0 or (not hcal_source_layers and hcal_z.size == 0):
        raise ValueError("both ECAL and HCAL geometry must be observed")
    source_layer_to_index = {
        source_layer: index + 1 for index, source_layer in enumerate(hcal_source_layers)
    }
    rows = []
    for subdetector, source_layer, cell_id, x, y, z, physical_count in records:
        if subdetector == 0:
            layer = 0
        elif source_layer is not None:
            layer = source_layer_to_index[int(source_layer)]
        else:
            layer = 1 + _nearest_layer(z, hcal_z)
        rows.append(
            (
                layer,
                y,
                x,
                cell_id,
                subdetector,
                z,
                source_layer,
                physical_count,
            )
        )
    rows.sort()
    layer_index = np.array([row[0] for row in rows], dtype=np.int64)
    cell_id = np.array([row[3] for row in rows], dtype=np.uint64)
    subdetector = np.array([row[4] for row in rows], dtype=np.int8)
    positions = np.array([[row[2], row[1], row[5]] for row in rows], dtype=np.float32)
    source_layer_id = np.array(
        [-1 if row[6] is None else int(row[6]) for row in rows], dtype=np.int64
    )
    physical_position_count = np.array(
        [int(row[7]) for row in rows], dtype=np.int32
    )
    valid_mask = np.ones(len(rows), dtype=np.bool_)

    spec = DetectorSpec()
    layer_counts = np.bincount(layer_index, minlength=int(layer_index.max()) + 1)
    if strict_project_counts:
        if len(rows) != spec.n_nodes:
            raise ValueError(f"expected {spec.n_nodes} cells, observed {len(rows)}")
        expected = np.asarray(spec.expected_layer_counts, dtype=np.int64)
        if layer_counts.shape != expected.shape or not np.array_equal(layer_counts, expected):
            raise ValueError(
                f"layer counts do not match project contract: observed={layer_counts.tolist()}"
            )

    normalized = positions.astype(np.float64)
    mean = normalized.mean(axis=0)
    std = normalized.std(axis=0)
    std[std < 1e-6] = 1.0
    xyz = ((normalized - mean) / std).astype(np.float32)
    layer_fraction = (layer_index / max(int(layer_index.max()), 1)).astype(np.float32)[:, None]
    is_ecal = (subdetector == 0).astype(np.float32)[:, None]
    is_hcal = (subdetector == 1).astype(np.float32)[:, None]
    node_features = np.concatenate([xyz, layer_fraction, is_ecal, is_hcal], axis=1)
    edge_index, edge_features = build_edges(positions, layer_index)
    arrays = {
        "cell_id": cell_id,
        "subdetector": subdetector,
        "positions_mm": positions,
        "node_features": node_features,
        "layer_index": layer_index,
        "source_layer_id": source_layer_id,
        "physical_position_count": physical_position_count,
        "valid_mask": valid_mask,
        "edge_index": edge_index,
        "edge_features": edge_features,
    }
    digest = geometry_hash(arrays)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output / "geometry.npz", **arrays)
    cell_map = {}
    for index in range(len(cell_id)):
        raw_layer = int(source_layer_id[index])
        key = channel_key(
            int(subdetector[index]),
            int(cell_id[index]),
            raw_layer if raw_layer >= 0 else None,
        )
        if key in cell_map:
            raise ValueError(f"duplicate frozen channel key: {key}")
        cell_map[key] = int(index)
    dump_json(cell_map, output / "cell_map.json")
    metadata = {
        "geometry_hash": digest,
        "schema_sha256": sha256_file(schema_path),
        "source_files": [
            {"path": str(Path(p).resolve()), "sha256": sha256_file(p)} for p in root_paths
        ],
        "n_nodes": int(len(rows)),
        "n_layers": int(layer_index.max()) + 1,
        "layer_counts": layer_counts.tolist(),
        "n_edges": int(edge_index.shape[1]),
        "channel_key_contract": (
            "subdetector:layer_id:cell_id"
            if hcal_source_layers
            else "subdetector:cell_id"
        ),
        "hcal_source_layer_ids": hcal_source_layers,
        "ganged_channel_count": int(np.sum(physical_position_count > 1)),
        "max_physical_positions_per_channel": int(physical_position_count.max()),
        "physical_position_count_histogram": {
            str(int(value)): int(np.sum(physical_position_count == value))
            for value in np.unique(physical_position_count)
        },
        "channel_position_contract": (
            "unweighted centroid of distinct stable physical positions sharing "
            "the readout key; hit-frequency weighting is forbidden"
        ),
        "node_feature_names": ["x_norm", "y_norm", "z_norm", "layer_fraction", "is_ecal", "is_hcal"],
        "edge_feature_names": ["dx_norm", "dy_norm", "dz_norm", "distance_norm", "edge_type"],
    }
    dump_json(metadata, output / "geometry_manifest.json")
    return metadata
