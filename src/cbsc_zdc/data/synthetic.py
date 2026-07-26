from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np

from ..contracts import NEUTRON_MASS_GEV
from ..utils import dump_json, sha256_file
from .geometry import build_edges, geometry_hash


def _synthetic_geometry(n_layers: int, nodes_per_layer: int, seed: int):
    rng = np.random.default_rng(seed)
    positions = []
    layer_index = []
    cell_id = []
    subdetector = []
    for layer in range(n_layers):
        side = int(math.ceil(math.sqrt(nodes_per_layer)))
        for local in range(nodes_per_layer):
            x = (local % side - (side - 1) / 2) * 10.0
            y = (local // side - (side - 1) / 2) * 10.0
            z = layer * 25.0
            positions.append((x, y, z))
            layer_index.append(layer)
            cell_id.append(layer * 100000 + local)
            subdetector.append(0 if layer == 0 else 1)
    positions = np.asarray(positions, dtype=np.float32)
    layer_index = np.asarray(layer_index, dtype=np.int64)
    cell_id = np.asarray(cell_id, dtype=np.uint64)
    subdetector = np.asarray(subdetector, dtype=np.int8)
    mean = positions.mean(axis=0)
    std = positions.std(axis=0)
    std[std < 1e-6] = 1.0
    xyz = (positions - mean) / std
    layer_fraction = (layer_index / max(n_layers - 1, 1)).astype(np.float32)[:, None]
    node_features = np.concatenate(
        [
            xyz.astype(np.float32),
            layer_fraction,
            (subdetector == 0).astype(np.float32)[:, None],
            (subdetector == 1).astype(np.float32)[:, None],
        ],
        axis=1,
    )
    edge_index, edge_features = build_edges(positions, layer_index, lateral_k=4, longitudinal_k=2)
    arrays = {
        "cell_id": cell_id,
        "subdetector": subdetector,
        "positions_mm": positions,
        "node_features": node_features,
        "layer_index": layer_index,
        "valid_mask": np.ones(len(cell_id), dtype=np.bool_),
        "edge_index": edge_index,
        "edge_features": edge_features,
    }
    return arrays


def create_synthetic_dataset(
    output_dir: str | Path,
    n_events: int = 512,
    n_layers: int = 8,
    nodes_per_layer: int = 16,
    shard_size: int = 128,
    seed: int = 20260723,
) -> dict[str, Any]:
    output = Path(output_dir)
    geometry_dir = output / "geometry"
    data_dir = output / "data"
    geometry_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    arrays = _synthetic_geometry(n_layers, nodes_per_layer, seed)
    np.savez_compressed(geometry_dir / "geometry.npz", **arrays)
    digest = geometry_hash(arrays)
    dump_json(
        {
            "geometry_hash": digest,
            "n_nodes": int(len(arrays["cell_id"])),
            "n_layers": n_layers,
            "layer_counts": [nodes_per_layer] * n_layers,
            "n_edges": int(arrays["edge_index"].shape[1]),
            "synthetic": True,
        },
        geometry_dir / "geometry_manifest.json",
    )
    rng = np.random.default_rng(seed)
    shards = []
    n_nodes = n_layers * nodes_per_layer
    global_event = 0
    for shard_id, begin in enumerate(range(0, n_events, shard_size)):
        count = min(shard_size, n_events - begin)
        kinetic = rng.uniform(0, 300, size=count).astype(np.float32)
        theta_x = rng.normal(0, 0.01, size=count)
        theta_y = rng.normal(0, 0.01, size=count)
        total = kinetic.astype(np.float64) + NEUTRON_MASS_GEV
        p_abs = np.sqrt(np.maximum(total * total - NEUTRON_MASS_GEV**2, 0.0))
        direction = np.stack([theta_x, theta_y, np.ones(count)], axis=-1)
        direction /= np.linalg.norm(direction, axis=-1, keepdims=True)
        momentum = direction * p_abs[:, None]
        p4 = np.concatenate([total[:, None], momentum], axis=-1).astype(np.float32)
        event_ptr = [0]
        all_index = []
        all_energy = []
        for event in range(count):
            if kinetic[event] < 1e-6 or rng.random() < 0.03:
                event_ptr.append(len(all_index))
                continue
            response = kinetic[event] * rng.beta(2.5, 5.0)
            first = int(rng.integers(0, max(1, n_layers // 2)))
            active = np.arange(first, n_layers)
            center = first + rng.uniform(1, max(2, n_layers / 2))
            width = rng.uniform(1.0, max(1.5, n_layers / 3))
            profile = np.exp(-0.5 * ((active - center) / width) ** 2)
            profile *= rng.lognormal(0, 0.3, size=profile.size)
            profile /= profile.sum()
            for layer, layer_fraction in zip(active, profile):
                budget = response * layer_fraction
                max_hits = nodes_per_layer
                hits = int(np.clip(rng.poisson(2 + 0.04 * budget), 1, max_hits))
                local = rng.choice(nodes_per_layer, size=hits, replace=False)
                shares = rng.dirichlet(np.full(hits, 0.8))
                all_index.extend((layer * nodes_per_layer + local).tolist())
                all_energy.extend((budget * shares).tolist())
            event_ptr.append(len(all_index))
        path = data_dir / f"shard_{shard_id:05d}.npz"
        np.savez_compressed(
            path,
            p4_total_gev=p4,
            kinetic_energy_gev=kinetic,
            event_id=np.arange(global_event, global_event + count, dtype=np.int64),
            source_group=(np.arange(global_event, global_event + count) // 32).astype(np.int64),
            event_ptr=np.asarray(event_ptr, dtype=np.int64),
            cell_index=np.asarray(all_index, dtype=np.int32),
            cell_energy_gev=np.asarray(all_energy, dtype=np.float32),
        )
        shards.append(
            {
                "path": path.name,
                "n_events": count,
                "n_hits": len(all_index),
                "sha256": sha256_file(path),
            }
        )
        global_event += count
    manifest = {
        "format_version": 1,
        "target_mode": "raw_deposit",
        "threshold_gev": 0.0,
        "n_events": n_events,
        "n_nodes": n_nodes,
        "n_layers": n_layers,
        "geometry_hash": digest,
        "shards": shards,
        "synthetic": True,
    }
    dump_json(manifest, data_dir / "dataset_manifest.json")
    return {
        "geometry": str(geometry_dir),
        "manifest": str(data_dir / "dataset_manifest.json"),
        "n_events": n_events,
        "n_nodes": n_nodes,
    }
