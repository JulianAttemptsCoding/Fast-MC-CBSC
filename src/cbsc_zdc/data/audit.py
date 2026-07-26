from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from .dataset import ShardedSparseDataset
from ..contracts import NEUTRON_MASS_GEV
from ..utils import dump_json, sha256_file


def audit_dataset(
    manifest_path: str | Path,
    split_manifest_path: str | Path,
    split: str,
    output_path: str | Path,
    kinetic_range_gev: tuple[float,float] | None = None,
) -> dict[str,Any]:
    ds=ShardedSparseDataset(manifest_path,split_manifest_path,split,kinetic_range_gev)
    if len(ds)==0: raise ValueError("dataset audit selection is empty")
    kinetic_parts=[]; total_parts=[]; hit_parts=[]; shell_parts=[]
    per_bin=[[] for _ in range(13)]
    edges=np.array([0,10,25,50,75,100,125,150,175,200,225,250,275,300.0001])
    selected = np.zeros(ds.offsets[-1], dtype=bool)
    selected[ds.indices] = True
    for shard_index in range(len(ds.shards)):
        if shard_index % 25 == 0:
            print(
                f"dataset-audit shard={shard_index}/{len(ds.shards)}",
                flush=True,
            )
        shard = ds._load_shard(shard_index)
        begin = ds.offsets[shard_index]
        stop = ds.offsets[shard_index + 1]
        local_selected = selected[begin:stop]
        if not local_selected.any():
            continue
        ptr = shard["event_ptr"].astype(np.int64, copy=False)
        energy = shard["cell_energy_gev"].astype(np.float64, copy=False)
        if not np.isfinite(energy).all() or (energy < 0).any():
            raise ValueError(f"shard {shard_index} contains invalid hit energy")
        prefix = np.concatenate(
            [np.array([0.0], dtype=np.float64), np.cumsum(energy, dtype=np.float64)]
        )
        shard_totals = prefix[ptr[1:]] - prefix[ptr[:-1]]
        positive_prefix = np.concatenate(
            [
                np.array([0], dtype=np.int64),
                np.cumsum(energy > 0, dtype=np.int64),
            ]
        )
        shard_hits = positive_prefix[ptr[1:]] - positive_prefix[ptr[:-1]]
        shard_kinetic = shard["kinetic_energy_gev"].astype(np.float64, copy=False)
        p4 = shard["p4_total_gev"].astype(np.float64, copy=False)
        shell = np.abs(
            p4[:, 0] ** 2
            - np.square(p4[:, 1:]).sum(axis=1)
            - NEUTRON_MASS_GEV**2
        )
        selected_kinetic = shard_kinetic[local_selected]
        selected_totals = shard_totals[local_selected]
        kinetic_parts.append(selected_kinetic)
        total_parts.append(selected_totals)
        hit_parts.append(shard_hits[local_selected])
        shell_parts.append(shell[local_selected])
        selected_bins = np.clip(np.digitize(selected_kinetic, edges) - 1, 0, 12)
        for bin_index in range(13):
            values = selected_totals[selected_bins == bin_index]
            if values.size:
                per_bin[bin_index].append(values)
    kinetic=np.concatenate(kinetic_parts); totals=np.concatenate(total_parts); hits=np.concatenate(hit_parts); shell=np.concatenate(shell_parts)
    ratio=totals/np.maximum(kinetic,1.0)
    # Conservative finite sampling caps from the complete audited training selection.
    ratio_cap=float(max(np.quantile(ratio,0.9999)*1.20,1e-3))
    absolute_cap=float(max(np.quantile(totals,0.9999)*1.20,1e-3))
    bin_caps=[]
    for value_parts in per_bin:
        if value_parts:
            values = np.concatenate(value_parts)
            bin_caps.append(float(max(np.quantile(values,0.999)*1.25,1e-4)))
        else: bin_caps.append(None)
    result={
      'manifest_sha256':sha256_file(manifest_path),'split_manifest_sha256':sha256_file(split_manifest_path),
      'split':split,'n_events':len(ds),'kinetic_range_gev':list(kinetic_range_gev) if kinetic_range_gev else None,
      'kinetic_min_gev':float(kinetic.min()),'kinetic_max_gev':float(kinetic.max()),
      'zero_response_fraction':float(np.mean(totals==0)),'negative_response_count':int(np.sum(totals<0)),
      'total_response_quantiles_gev':{str(q):float(np.quantile(totals,q)) for q in [0,0.5,0.9,0.99,0.999,0.9999,1]},
      'hit_count_quantiles':{str(q):float(np.quantile(hits,q)) for q in [0,0.5,0.9,0.99,0.999,1]},
      'response_ratio_quantiles':{str(q):float(np.quantile(ratio,q)) for q in [0,0.5,0.9,0.99,0.999,0.9999,1]},
      'response_cap_ratio':ratio_cap,'response_cap_absolute_gev':absolute_cap,'response_cap_by_energy_bin_gev':bin_caps,
      'mass_shell_residual_max_gev2':float(np.max(shell)),
      'normalization':{'kinetic_mean_gev':float(kinetic.mean()),'kinetic_std_gev':float(kinetic.std()),'total_mean_gev':float(totals.mean()),'total_std_gev':float(totals.std())},
    }
    dump_json(result,output_path); return result
