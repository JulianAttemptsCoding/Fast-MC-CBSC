from __future__ import annotations

import argparse
import json
import time
import traceback
from datetime import datetime, timezone
from urllib.parse import urlparse

import numpy as np
from google.cloud import aiplatform, storage
from google.cloud.aiplatform_v1 import JobServiceClient
from google.cloud.aiplatform_v1.types import JobState, custom_job


EXPECTED_LAYER_COUNTS = [400, *([100] * 63), 90]


def _gs(uri: str) -> tuple[str, str]:
    parsed = urlparse(uri)
    if parsed.scheme != "gs" or not parsed.netloc:
        raise ValueError(f"expected gs:// URI, got {uri}")
    return parsed.netloc, parsed.path.lstrip("/").rstrip("/")


def _json_blob(bucket, name: str) -> dict:
    blob = bucket.blob(name)
    if not blob.exists():
        raise FileNotFoundError(f"missing gs://{bucket.name}/{name}")
    value = json.loads(blob.download_as_text())
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: gs://{bucket.name}/{name}")
    return value


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _pilot_counts_are_exact(counts: dict, total_entries: int) -> bool:
    selected = 338 + 104
    return (
        counts.get("train") == 338
        and counts.get("validation") == 104
        and counts.get("test") == 0
        and counts.get("excluded") == total_entries - selected
    )


def verify_prepare(
    client: storage.Client,
    prefix_uri: str,
    generation: str,
    size: int,
    crc32c: str,
    entries: int,
) -> dict:
    bucket_name, prefix = _gs(prefix_uri)
    bucket = client.bucket(bucket_name)

    def read(relative: str) -> dict:
        return _json_blob(bucket, f"{prefix}/{relative}")

    result = read("prepare_result.json")
    identity = read("source_identity.json")
    inspection = read("artifacts/root_inspection.json")
    geometry = read("artifacts/geometry/geometry_manifest.json")
    manifest = read("artifacts/data/dataset_manifest.json")
    splits = read("artifacts/splits.json")
    audit = read("artifacts/train_data_audit.json")
    pilot_splits = read("artifacts/pilot_splits.json")
    pilot_audit = read("artifacts/pilot_train_data_audit.json")
    pilot_preflight = read("artifacts/pilot_preflight.json")

    _require(result.get("pass") is True, "prepare_result did not pass")
    _require(identity.get("generation") == generation, "ROOT generation mismatch")
    _require(int(identity.get("size", -1)) == size, "ROOT size mismatch")
    _require(identity.get("crc32c") == crc32c, "ROOT CRC32C mismatch")
    _require(int(inspection.get("entries", -1)) == entries, "ROOT entries mismatch")
    _require(not inspection.get("missing_branches"), "ROOT schema is incomplete")
    _require(int(geometry.get("n_nodes", -1)) == 6790, "geometry node mismatch")
    _require(int(geometry.get("n_layers", -1)) == 65, "geometry layer mismatch")
    _require(
        geometry.get("layer_counts") == EXPECTED_LAYER_COUNTS,
        "geometry per-layer counts mismatch",
    )
    _require(
        int(geometry.get("ganged_channel_count", 0)) > 0
        and int(geometry.get("max_physical_positions_per_channel", 0)) > 1,
        "ganged geometry evidence missing",
    )
    _require(
        "hit-frequency weighting is forbidden"
        in geometry.get("channel_position_contract", ""),
        "unweighted ganged-position contract missing",
    )
    _require(int(manifest.get("n_events", -1)) == entries, "event count mismatch")
    _require(manifest.get("target_mode") == "raw_deposit", "wrong target mode")
    _require(float(manifest.get("threshold_gev", -1)) == 0.0, "wrong threshold")
    _require(
        all(int(value) == 0 for value in manifest.get("rejected", {}).values()),
        f"conversion rejection: {manifest.get('rejected')}",
    )
    _require(
        float(manifest.get("event_total_residual_max_gev", np.inf)) <= 1e-6,
        "all-hit event-total closure failed",
    )
    _require(
        float(manifest.get("modeled_readout_residual_max_gev", np.inf)) <= 1e-6,
        "mapped readout closure failed",
    )
    _require(
        manifest.get("event_total_reference_semantics")
        == "all stored deposits including sentinel non-readout hits",
        "event-total semantics mismatch",
    )
    _require(
        manifest.get("modeled_target_semantics")
        == "raw non-sentinel readout deposits",
        "modeled-target semantics mismatch",
    )
    _require(
        int(manifest.get("excluded_sentinel_event_count", 0)) > 0
        and float(manifest.get("excluded_sentinel_energy_total_gev", 0.0)) > 0,
        "sentinel exclusion evidence missing",
    )
    _require(splits.get("group_by") == "event_hash", "wrong split grouping")
    for split in ("train", "validation", "test"):
        _require(int(splits["counts"].get(split, 0)) > 0, f"empty {split} split")
        bins = splits["energy_bin_counts"].get(split, [])
        _require(
            len(bins) == 13 and all(int(value) > 0 for value in bins),
            f"empty {split} energy bin",
        )
    _require(audit.get("split") == "train", "full audit is not train-only")
    _require(
        int(audit.get("negative_response_count", -1)) == 0,
        "negative response in full audit",
    )
    caps = audit.get("response_cap_by_energy_bin_gev", [])
    _require(
        len(caps) == 13
        and all(value is not None and np.isfinite(float(value)) for value in caps),
        "full train audit contains an empty/nonfinite bin",
    )
    _require(pilot_splits.get("pilot") is True, "pilot marker missing")
    _require(pilot_splits.get("test_data_used") is False, "pilot used test data")
    _require(
        _pilot_counts_are_exact(pilot_splits.get("counts", {}), entries),
        f"pilot counts mismatch: {pilot_splits.get('counts')}",
    )
    _require(pilot_audit.get("split") == "train", "pilot audit is not train-only")
    _require(
        int(pilot_audit.get("negative_response_count", -1)) == 0,
        "negative response in pilot audit",
    )
    _require(pilot_preflight.get("pass") is True, "pilot preflight failed")
    _require(
        pilot_preflight.get("verify_shards") is True
        and int(pilot_preflight.get("verified_shards", 0))
        == len(manifest.get("shards", [])),
        "pilot preflight did not verify all shards",
    )
    _require(pilot_preflight.get("synthetic") is False, "pilot is synthetic")
    return {
        "pass": True,
        "geometry_hash": geometry["geometry_hash"],
        "n_shards": len(manifest["shards"]),
        "split_counts": splits["counts"],
        "pilot_counts": pilot_splits["counts"],
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
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Wait for full preparation, verify it, and submit one T4 smoke"
    )
    parser.add_argument("--project", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--staging-bucket", required=True)
    parser.add_argument("--prepare-job", required=True)
    parser.add_argument("--prepare-prefix", required=True)
    parser.add_argument("--smoke-prefix", required=True)
    parser.add_argument("--status-prefix", required=True)
    parser.add_argument("--container-uri", required=True)
    parser.add_argument("--service-account", required=True)
    parser.add_argument("--expected-generation", required=True)
    parser.add_argument("--expected-size", required=True, type=int)
    parser.add_argument("--expected-crc32c", required=True)
    parser.add_argument("--expected-entries", required=True, type=int)
    parser.add_argument("--poll-seconds", type=int, default=60)
    args = parser.parse_args()

    storage_client = storage.Client(project=args.project)
    status_bucket_name, status_prefix = _gs(args.status_prefix)
    status_bucket = storage_client.bucket(status_bucket_name)

    def status(name: str, payload: dict) -> None:
        payload = {
            **payload,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }
        status_bucket.blob(f"{status_prefix}/{name}").upload_from_string(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            content_type="application/json",
        )

    try:
        api = JobServiceClient(
            client_options={
                "api_endpoint": f"{args.region}-aiplatform.googleapis.com"
            }
        )
        while True:
            prepared = api.get_custom_job(name=args.prepare_job)
            state = prepared.state
            print(f"prepare state={JobState(state).name}", flush=True)
            if state == JobState.JOB_STATE_SUCCEEDED:
                break
            if state in {
                JobState.JOB_STATE_FAILED,
                JobState.JOB_STATE_CANCELLED,
                JobState.JOB_STATE_EXPIRED,
            }:
                raise RuntimeError(
                    f"preparation reached terminal state {JobState(state).name}: "
                    f"{prepared.error}"
                )
            time.sleep(args.poll_seconds)

        verification = verify_prepare(
            storage_client,
            args.prepare_prefix,
            args.expected_generation,
            args.expected_size,
            args.expected_crc32c,
            args.expected_entries,
        )
        status("prepare_verification.json", verification)

        smoke_bucket_name, smoke_prefix = _gs(args.smoke_prefix)
        smoke_bucket = storage_client.bucket(smoke_bucket_name)
        if next(storage_client.list_blobs(smoke_bucket, prefix=smoke_prefix), None):
            raise RuntimeError(f"smoke prefix is not empty: {args.smoke_prefix}")
        lock = smoke_bucket.blob(f"{smoke_prefix}/_submission_lock.json")
        lock.upload_from_string(
            json.dumps(
                {
                    "prepare_job": args.prepare_job,
                    "prepare_prefix": args.prepare_prefix,
                    "container_uri": args.container_uri,
                    "status": "claimed",
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            content_type="application/json",
            if_generation_match=0,
        )

        aiplatform.init(
            project=args.project,
            location=args.region,
            staging_bucket=args.staging_bucket,
        )
        job = aiplatform.CustomContainerTrainingJob(
            display_name="cbsc-v2-2-production-geometry-smoke-20260724-r1",
            container_uri=args.container_uri,
        )
        job.run(
            args=[
                "--input-prefix",
                args.prepare_prefix,
                "--output-prefix",
                args.smoke_prefix,
                "--config-relative",
                "configs/frozen_production_full_architecture_smoke.yaml",
                "--manifest-relative",
                "artifacts/data/dataset_manifest.json",
                "--splits-relative",
                "artifacts/pilot_splits.json",
                "--geometry-relative",
                "artifacts/geometry",
                "--device",
                "cuda",
                "--postflight-smoke",
            ],
            replica_count=1,
            machine_type="n1-standard-8",
            accelerator_type="NVIDIA_TESLA_T4",
            accelerator_count=1,
            boot_disk_type="pd-ssd",
            boot_disk_size_gb=100,
            timeout=21600,
            service_account=args.service_account,
            scheduling_strategy=custom_job.Scheduling.Strategy.ON_DEMAND,
            sync=True,
        )
        status(
            "orchestration_result.json",
            {
                "pass": True,
                "prepare_verification": verification,
                "smoke_job": job.resource_name,
                "smoke_prefix": args.smoke_prefix,
                "scheduling_strategy": "ON_DEMAND",
                "accelerator_type": "NVIDIA_TESLA_T4",
                "accelerator_count": 1,
            },
        )
        print(f"smoke job completed: {job.resource_name}", flush=True)
    except Exception as exc:
        status(
            "orchestration_failure.json",
            {
                "pass": False,
                "exception_type": type(exc).__name__,
                "message": str(exc),
                "traceback": traceback.format_exc(),
            },
        )
        raise


if __name__ == "__main__":
    main()
