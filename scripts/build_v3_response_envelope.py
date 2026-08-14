"""Build the train-only 25-GeV response envelope from the production shards.

Reads the **training assignment only**.  Validation and test never influence
``C(K)``; that is enforced by the split loader and asserted in the output.

The envelope is a numerical support contract for the bounded response spline,
not a claim about physics.  A validation response above it is an out-of-support
finding, never a clipped value.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch

from cbsc_zdc.contracts import kinetic_energy_from_p4
from cbsc_zdc.data.dataset import ShardedSparseDataset, load_geometry
from cbsc_zdc.models.response_envelope import (
    build_response_envelope,
    rescan_training_population,
)
from cbsc_zdc.utils import load_yaml


def rows_from_split(config: dict, split: str, limit: int | None):
    """Yield ``(kinetic_gev, total_response_gev, visible)`` for one split.

    ``split`` is passed to the dataset, so the training assignment is enforced by
    the same loader training uses rather than by a filter written here.
    """
    if split != "train":
        raise SystemExit(f"the response envelope is train-only; refusing split {split!r}")
    geometry = load_geometry(config["geometry"]["path"])
    n_nodes = int(geometry["node_features"].shape[0])
    dataset = ShardedSparseDataset(
        config["data"]["manifest"],
        split_manifest_path=config["data"]["splits"],
        split=split,
        kinetic_range_gev=tuple(config["data"]["train_kinetic_gev"]),
        n_nodes=n_nodes,
    )
    threshold = float(config["data"].get("threshold_gev", 0.0))
    total_events = len(dataset)
    stop = total_events if limit is None else min(limit, total_events)
    for index in range(stop):
        item = dataset[index]
        p4 = item["p4_total_gev"].reshape(1, 4)
        kinetic = float(kinetic_energy_from_p4(p4)[0])
        cell = item["cell_energy_gev"]
        total = float(cell[cell > threshold].sum())
        yield kinetic, total, total > 0.0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=None,
                        help="cap the scanned training events; a production envelope uses all of them")
    parser.add_argument("--allow-empty-bins", action="store_true",
                        help="mark the envelope non-production instead of failing on an empty bin")
    args = parser.parse_args()

    config = load_yaml(args.config)
    rows = list(rows_from_split(config, "train", args.limit))
    envelope = build_response_envelope(
        rows,
        split="train",
        source_hashes={
            "config_sha256": config.get("provenance", {}).get("config_sha256", ""),
            "manifest": str(config["data"]["manifest"]),
        },
        require_full_support=not args.allow_empty_bins,
    )
    envelope["rescan"] = rescan_training_population(envelope, rows)
    envelope["scanned_events"] = len(rows)
    envelope["limit_applied"] = args.limit
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(envelope, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({
        "output": str(args.output),
        "scanned_events": envelope["scanned_events"],
        "production_ready": envelope["production_ready"],
        "empty_visible_bins": envelope["empty_visible_bins"],
        "monotone_caps_gev": [round(c, 4) for c in envelope["monotone_caps_gev"]],
        "training_envelope_exceedances": envelope["rescan"]["training_envelope_exceedances"],
        "envelope_sha256": envelope["envelope_sha256"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
