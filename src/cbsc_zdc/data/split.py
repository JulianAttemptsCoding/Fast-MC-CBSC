from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import numpy as np

from .dataset import ShardedSparseDataset
from ..utils import dump_json, load_json, sha256_file

SPLIT_NAMES = {0: "train", 1: "validation", 2: "test"}


def _stable_hash(value: str, seed: int) -> int:
    digest = hashlib.blake2b(f"{seed}:{value}".encode(), digest_size=8).digest()
    return int.from_bytes(digest, "little")


def _energy_bins(kinetic: np.ndarray) -> np.ndarray:
    edges = np.array([0, 10, 25, 50, 75, 100, 125, 150, 175, 200, 225, 250, 275, 300.0001])
    return np.clip(np.digitize(kinetic, edges) - 1, 0, len(edges) - 2)


def create_split(
    manifest_path: str | Path,
    output_json: str | Path,
    fractions: tuple[float, float, float] = (0.8, 0.1, 0.1),
    seed: int = 20260723,
    group_by: str = "source_group",
) -> dict[str, Any]:
    if abs(sum(fractions)-1.0)>1e-9 or any(x<=0 for x in fractions):
        raise ValueError("fractions must be positive and sum to one")
    ds=ShardedSparseDataset(manifest_path)
    kinetic=[]; groups=[]; event_ids=[]
    for shard_i in range(len(ds.shards)):
        shard=ds._load_shard(shard_i)
        kinetic.append(shard['kinetic_energy_gev'])
        groups.append(shard['source_group'])
        event_ids.append(shard['event_id'])
    kinetic=np.concatenate(kinetic).astype(np.float64)
    groups=np.concatenate(groups).astype(np.int64)
    event_ids=np.concatenate(event_ids).astype(np.int64)
    n=len(kinetic)
    assignment=np.full(n,-1,dtype=np.int8)
    if group_by == "event_hash":
        thresholds=np.cumsum(fractions)
        for i,eid in enumerate(event_ids):
            u=_stable_hash(str(int(eid)),seed)/2**64
            assignment[i]=0 if u<thresholds[0] else (1 if u<thresholds[1] else 2)
    elif group_by == "source_group":
        bins=_energy_bins(kinetic)
        unique=np.unique(groups)
        # Deterministic greedy stratified group allocation.
        group_stats=[]
        for g in unique:
            idx=np.where(groups==g)[0]
            hist=np.bincount(bins[idx],minlength=13).astype(np.float64)
            group_stats.append((int(g),idx,hist))
        group_stats.sort(key=lambda x:(-len(x[1]),_stable_hash(str(x[0]),seed)))
        total_hist=np.bincount(bins,minlength=13).astype(np.float64)
        target=np.asarray(fractions)[:,None]*total_hist[None,:]
        current=np.zeros_like(target)
        count_target=np.asarray(fractions)*n
        current_count=np.zeros(3)
        for order,(g,idx,hist) in enumerate(group_stats):
            # Seed each partition once so small synthetic or pilot corpora cannot collapse.
            if order < 3:
                chosen = order
            else:
                scores=[]
                for s in range(3):
                    trial=current.copy(); trial[s]+=hist
                    hist_error=((trial-target)/(target+1.0))**2
                    count_error=((current_count.copy()+np.eye(3)[s]*len(idx)-count_target)/(count_target+1.0))**2
                    scores.append(float(hist_error.mean()+0.2*count_error.mean()))
                chosen=int(np.argmin(scores))
            assignment[idx]=chosen; current[chosen]+=hist; current_count[chosen]+=len(idx)
    else:
        raise ValueError("group_by must be source_group or event_hash")
    if (assignment<0).any() or any(np.sum(assignment==s)==0 for s in range(3)):
        raise RuntimeError("split creation produced an unassigned or empty partition")
    output=Path(output_json); output.parent.mkdir(parents=True,exist_ok=True)
    assignment_path=output.with_name(output.stem+'_assignments.npz')
    np.savez_compressed(assignment_path,split_code=assignment)
    report={
        'format_version':1,'manifest_path':str(Path(manifest_path).resolve()),
        'manifest_sha256':sha256_file(manifest_path),'assignment_file':assignment_path.name,
        'assignment_sha256':sha256_file(assignment_path),'seed':seed,'group_by':group_by,
        'fractions_requested':list(fractions),
        'counts':{SPLIT_NAMES[s]:int(np.sum(assignment==s)) for s in range(3)},
        'fractions_realized':{SPLIT_NAMES[s]:float(np.mean(assignment==s)) for s in range(3)},
        'energy_bin_counts':{SPLIT_NAMES[s]:np.bincount(_energy_bins(kinetic[assignment==s]),minlength=13).tolist() for s in range(3)},
    }
    dump_json(report,output); return report
