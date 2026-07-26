from __future__ import annotations

import bisect
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch.utils.data import Dataset

from ..utils import load_json, sha256_file


def load_geometry(path: str | Path, device: str | torch.device = "cpu") -> dict[str, torch.Tensor]:
    source = Path(path)
    if source.is_dir():
        source = source / "geometry.npz"
    arrays = np.load(source, allow_pickle=False)
    result = {
        "cell_id": torch.from_numpy(arrays["cell_id"].astype(np.int64, copy=False)).to(device),
        "subdetector": torch.from_numpy(arrays["subdetector"].astype(np.int64, copy=False)).to(device),
        "positions_mm": torch.from_numpy(arrays["positions_mm"].astype(np.float32, copy=False)).to(device),
        "node_features": torch.from_numpy(arrays["node_features"].astype(np.float32, copy=False)).to(device),
        "layer_index": torch.from_numpy(arrays["layer_index"].astype(np.int64, copy=False)).to(device),
        "valid_mask": torch.from_numpy(arrays["valid_mask"].astype(bool, copy=False)).to(device),
        "edge_index": torch.from_numpy(arrays["edge_index"].astype(np.int64, copy=False)).to(device),
        "edge_features": torch.from_numpy(arrays["edge_features"].astype(np.float32, copy=False)).to(device),
    }
    return result


class ShardedSparseDataset(Dataset):
    """Random-access dataset over compressed sparse event shards.

    Each shard stores p4_total_gev, event_ptr, cell_index, cell_energy_gev, event_id,
    source_group, and kinetic_energy_gev. Dense 6,790-channel targets are materialized only
    for the requested event/batch.
    """

    def __init__(
        self,
        manifest_path: str | Path,
        split_manifest_path: str | Path | None = None,
        split: str | None = None,
        kinetic_range_gev: tuple[float, float] | None = None,
        n_nodes: int | None = None,
    ):
        self.manifest_path = Path(manifest_path)
        self.manifest = load_json(self.manifest_path)
        self.root = self.manifest_path.parent
        self.shards = self.manifest["shards"]
        self.offsets = [0]
        for shard in self.shards:
            self.offsets.append(self.offsets[-1] + int(shard["n_events"]))
        manifest_nodes = int(self.manifest["n_nodes"])
        if n_nodes is not None and int(n_nodes) != manifest_nodes:
            raise RuntimeError(
                f"configured n_nodes={int(n_nodes)} does not match manifest n_nodes={manifest_nodes}"
            )
        self.n_nodes = manifest_nodes
        total = self.offsets[-1]
        if total != int(self.manifest["n_events"]):
            raise RuntimeError(
                f"manifest event count {self.manifest['n_events']} does not match shards {total}"
            )
        selected = np.arange(total, dtype=np.int64)
        if split_manifest_path is not None:
            split_manifest = load_json(split_manifest_path)
            actual_manifest_hash = sha256_file(self.manifest_path)
            if split_manifest.get("manifest_sha256") != actual_manifest_hash:
                raise RuntimeError("split manifest does not match dataset manifest hash")
            assignment_path = Path(split_manifest_path).parent / split_manifest["assignment_file"]
            if sha256_file(assignment_path) != split_manifest.get("assignment_sha256"):
                raise RuntimeError(f"split assignment hash mismatch: {assignment_path}")
            assignments = np.load(assignment_path, allow_pickle=False)["split_code"]
            if len(assignments) != total:
                raise RuntimeError(
                    f"split assignment length {len(assignments)} does not match dataset {total}"
                )
            if not np.isin(assignments, [0, 1, 2, 3]).all():
                raise RuntimeError("split assignment contains an invalid split code")
            names = {"train": 0, "validation": 1, "test": 2}
            if split not in names:
                raise ValueError("split must be train, validation, or test")
            selected = selected[assignments == names[split]]
        if kinetic_range_gev is not None:
            low, high = kinetic_range_gev
            kinetic = self._all_kinetic()
            selected = selected[(kinetic[selected] >= low) & (kinetic[selected] <= high)]
        self.indices = selected

    @lru_cache(maxsize=4)
    def _load_shard(self, shard_index: int) -> dict[str, np.ndarray]:
        shard = self.shards[shard_index]
        path = self.root / shard["path"]
        if "sha256" in shard and sha256_file(path) != shard["sha256"]:
            raise RuntimeError(f"shard hash mismatch: {path}")
        arrays = np.load(path, allow_pickle=False)
        return {key: arrays[key] for key in arrays.files}

    def _all_kinetic(self) -> np.ndarray:
        values = []
        for index in range(len(self.shards)):
            values.append(self._load_shard(index)["kinetic_energy_gev"])
        return np.concatenate(values).astype(np.float32, copy=False)

    def __len__(self) -> int:
        return int(self.indices.size)

    def _locate(self, global_index: int) -> tuple[int, int]:
        shard_index = bisect.bisect_right(self.offsets, global_index) - 1
        return shard_index, global_index - self.offsets[shard_index]

    def __getitem__(self, item: int) -> dict[str, torch.Tensor]:
        global_index = int(self.indices[item])
        shard_index, local_index = self._locate(global_index)
        shard = self._load_shard(shard_index)
        start = int(shard["event_ptr"][local_index])
        stop = int(shard["event_ptr"][local_index + 1])
        dense = np.zeros(self.n_nodes, dtype=np.float32)
        np.add.at(
            dense,
            shard["cell_index"][start:stop].astype(np.int64, copy=False),
            shard["cell_energy_gev"][start:stop].astype(np.float32, copy=False),
        )
        return {
            "p4_total_gev": torch.from_numpy(shard["p4_total_gev"][local_index].astype(np.float32, copy=False)),
            "kinetic_energy_gev": torch.tensor(float(shard["kinetic_energy_gev"][local_index]), dtype=torch.float32),
            "cell_energy_gev": torch.from_numpy(dense),
            "event_id": torch.tensor(int(shard["event_id"][local_index]), dtype=torch.int64),
            "source_group": torch.tensor(int(shard["source_group"][local_index]), dtype=torch.int64),
            "global_index": torch.tensor(global_index, dtype=torch.int64),
        }
