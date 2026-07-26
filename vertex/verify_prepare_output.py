#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import numpy as np
from google.cloud import storage


EXPECTED_LAYER_COUNTS = [400, *([100] * 63), 90]


def parse_prefix(uri: str) -> tuple[str, str]:
    parsed = urlparse(uri)
    if parsed.scheme != "gs" or not parsed.netloc:
        raise ValueError(f"expected gs://bucket/prefix, got {uri}")
    return parsed.netloc, parsed.path.lstrip("/").rstrip("/")


def download_json(bucket, prefix: str, relative: str, root: Path) -> dict:
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    blob = bucket.blob(f"{prefix}/{relative}")
    if not blob.exists():
        raise FileNotFoundError(f"missing preparation artifact: gs://{bucket.name}/{blob.name}")
    blob.download_to_filename(target)
    with target.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {relative}")
    return value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify full-ROOT Vertex preparation artifacts before GPU use"
    )
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--expected-generation", required=True)
    parser.add_argument("--expected-size", required=True, type=int)
    parser.add_argument("--expected-crc32c", required=True)
    parser.add_argument("--expected-entries", required=True, type=int)
    parser.add_argument("--output")
    args = parser.parse_args()

    bucket_name, prefix = parse_prefix(args.prefix)
    bucket = storage.Client().bucket(bucket_name)
    with tempfile.TemporaryDirectory(prefix="cbsc-verify-prep-") as temporary:
        root = Path(temporary)
        result = download_json(bucket, prefix, "prepare_result.json", root)
        identity = download_json(bucket, prefix, "source_identity.json", root)
        inspection = download_json(
            bucket, prefix, "artifacts/root_inspection.json", root
        )
        geometry = download_json(
            bucket, prefix, "artifacts/geometry/geometry_manifest.json", root
        )
        manifest = download_json(
            bucket, prefix, "artifacts/data/dataset_manifest.json", root
        )
        splits = download_json(bucket, prefix, "artifacts/splits.json", root)
        audit = download_json(
            bucket, prefix, "artifacts/train_data_audit.json", root
        )
        pilot_splits = download_json(
            bucket, prefix, "artifacts/pilot_splits.json", root
        )
        pilot_audit = download_json(
            bucket, prefix, "artifacts/pilot_train_data_audit.json", root
        )
        pilot_preflight = download_json(
            bucket, prefix, "artifacts/pilot_preflight.json", root
        )

        require(result.get("pass") is True, "prepare_result did not pass")
        require(
            identity.get("generation") == args.expected_generation,
            "production ROOT generation mismatch",
        )
        require(
            int(identity.get("size", -1)) == args.expected_size,
            "production ROOT size mismatch",
        )
        require(
            identity.get("crc32c") == args.expected_crc32c,
            "production ROOT CRC32C mismatch",
        )
        require(
            int(inspection.get("entries", -1)) == args.expected_entries,
            "ROOT entry count mismatch",
        )
        require(not inspection.get("missing_branches"), "ROOT schema has missing branches")
        require(int(geometry.get("n_nodes", -1)) == 6790, "geometry node count mismatch")
        require(int(geometry.get("n_layers", -1)) == 65, "geometry layer count mismatch")
        require(
            geometry.get("layer_counts") == EXPECTED_LAYER_COUNTS,
            "geometry per-layer counts mismatch",
        )
        require(
            int(geometry.get("ganged_channel_count", 0)) > 0
            and int(geometry.get("max_physical_positions_per_channel", 0)) > 1,
            "HCAL ganged-readout geometry was not recorded",
        )
        require(
            "hit-frequency weighting is forbidden"
            in geometry.get("channel_position_contract", ""),
            "geometry does not state the unweighted ganged-position contract",
        )
        require(
            int(manifest.get("n_events", -1)) == args.expected_entries,
            "converted event count mismatch",
        )
        require(manifest.get("target_mode") == "raw_deposit", "wrong target mode")
        require(float(manifest.get("threshold_gev", -1)) == 0.0, "wrong threshold")
        require(
            all(int(value) == 0 for value in manifest.get("rejected", {}).values()),
            f"conversion rejected events: {manifest.get('rejected')}",
        )
        require(
            float(manifest.get("event_total_residual_max_gev", float("inf"))) <= 1e-6,
            "all-hit stored event-total closure gate failed",
        )
        require(
            float(
                manifest.get("modeled_readout_residual_max_gev", float("inf"))
            )
            <= 1e-6,
            "mapped readout/non-sentinel hit closure gate failed",
        )
        require(
            manifest.get("event_total_reference_semantics")
            == "all stored deposits including sentinel non-readout hits",
            "event-total reference semantics are missing or wrong",
        )
        require(
            manifest.get("modeled_target_semantics")
            == "raw non-sentinel readout deposits",
            "modeled target semantics are missing or wrong",
        )
        require(
            int(manifest.get("excluded_sentinel_event_count", 0)) > 0
            and float(manifest.get("excluded_sentinel_energy_total_gev", 0.0)) > 0,
            "production sentinel exclusion evidence is missing",
        )
        require(splits.get("group_by") == "event_hash", "full split is not event_hash")
        for split_name in ("train", "validation", "test"):
            require(
                int(splits.get("counts", {}).get(split_name, 0)) > 0,
                f"empty full split: {split_name}",
            )
            bins = splits.get("energy_bin_counts", {}).get(split_name, [])
            require(
                len(bins) == 13 and all(int(value) > 0 for value in bins),
                f"empty full split energy bin: {split_name}={bins}",
            )
        require(audit.get("split") == "train", "full audit is not train-only")
        require(
            int(audit.get("negative_response_count", -1)) == 0,
            "negative response in full train audit",
        )
        require(
            len(audit.get("response_cap_by_energy_bin_gev", [])) == 13
            and all(
                value is not None
                and np.isfinite(float(value))
                for value in audit["response_cap_by_energy_bin_gev"]
            ),
            "full train audit has an empty/nonfinite energy bin",
        )
        require(pilot_splits.get("pilot") is True, "pilot marker missing")
        require(
            pilot_splits.get("test_data_used") is False,
            "pilot reports test-data use",
        )
        require(
            pilot_splits.get("counts", {}).get("train") == 338
            and pilot_splits.get("counts", {}).get("validation") == 104
            and pilot_splits.get("counts", {}).get("test") == 0,
            f"unexpected pilot counts: {pilot_splits.get('counts')}",
        )
        require(pilot_audit.get("split") == "train", "pilot audit is not train-only")
        require(
            int(pilot_audit.get("negative_response_count", -1)) == 0,
            "negative response in pilot train audit",
        )
        require(pilot_preflight.get("pass") is True, "pilot preflight did not pass")
        require(
            pilot_preflight.get("verify_shards") is True
            and int(pilot_preflight.get("verified_shards", 0))
            == len(manifest.get("shards", [])),
            "pilot preflight did not verify every shard",
        )
        require(
            pilot_preflight.get("synthetic") is False,
            "production pilot is incorrectly marked synthetic",
        )

        report = {
            "pass": True,
            "prefix": args.prefix,
            "source_identity": identity,
            "entries": inspection["entries"],
            "geometry_hash": geometry["geometry_hash"],
            "n_nodes": geometry["n_nodes"],
            "n_layers": geometry["n_layers"],
            "ganged_channel_count": geometry["ganged_channel_count"],
            "max_physical_positions_per_channel": geometry[
                "max_physical_positions_per_channel"
            ],
            "n_shards": len(manifest["shards"]),
            "split_counts": splits["counts"],
            "pilot_counts": pilot_splits["counts"],
            "pilot_selection_counts": pilot_preflight["selection_counts"],
            "verified_shards": pilot_preflight["verified_shards"],
            "event_total_residual_max_gev": manifest[
                "event_total_residual_max_gev"
            ],
            "modeled_readout_residual_max_gev": manifest[
                "modeled_readout_residual_max_gev"
            ],
            "excluded_sentinel_event_count": manifest[
                "excluded_sentinel_event_count"
            ],
            "excluded_sentinel_energy_total_gev": manifest[
                "excluded_sentinel_energy_total_gev"
            ],
            "excluded_sentinel_energy_max_gev": manifest[
                "excluded_sentinel_energy_max_gev"
            ],
        }
        rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
        if args.output:
            Path(args.output).write_text(rendered, encoding="utf-8")
        print(rendered, end="")


if __name__ == "__main__":
    main()
