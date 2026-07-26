#!/usr/bin/env python3
from __future__ import annotations

import argparse

from google.cloud import aiplatform
from google.cloud.aiplatform_v1.types import custom_job


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Submit the server-side preparation-to-T4 smoke coordinator"
    )
    parser.add_argument("--project", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--staging-bucket", required=True)
    parser.add_argument("--container-uri", required=True)
    parser.add_argument("--prepare-job", required=True)
    parser.add_argument("--prepare-prefix", required=True)
    parser.add_argument("--smoke-prefix", required=True)
    parser.add_argument("--status-prefix", required=True)
    parser.add_argument("--service-account", required=True)
    parser.add_argument("--expected-generation", required=True)
    parser.add_argument("--expected-size", required=True, type=int)
    parser.add_argument("--expected-crc32c", required=True)
    parser.add_argument("--expected-entries", required=True, type=int)
    parser.add_argument("--timeout-seconds", type=int, default=43200)
    args = parser.parse_args()

    aiplatform.init(
        project=args.project,
        location=args.region,
        staging_bucket=args.staging_bucket,
    )
    worker_pool_specs = [
        {
            "machine_spec": {"machine_type": "n1-standard-4"},
            "replica_count": 1,
            "disk_spec": {
                "boot_disk_type": "pd-standard",
                "boot_disk_size_gb": 100,
            },
            "container_spec": {
                "image_uri": args.container_uri,
                "command": ["python", "-m", "cbsc_zdc.cloud.auto_smoke"],
                "args": [
                    "--project",
                    args.project,
                    "--region",
                    args.region,
                    "--staging-bucket",
                    args.staging_bucket,
                    "--prepare-job",
                    args.prepare_job,
                    "--prepare-prefix",
                    args.prepare_prefix,
                    "--smoke-prefix",
                    args.smoke_prefix,
                    "--status-prefix",
                    args.status_prefix,
                    "--container-uri",
                    args.container_uri,
                    "--service-account",
                    args.service_account,
                    "--expected-generation",
                    args.expected_generation,
                    "--expected-size",
                    str(args.expected_size),
                    "--expected-crc32c",
                    args.expected_crc32c,
                    "--expected-entries",
                    str(args.expected_entries),
                ],
            },
        }
    ]
    job = aiplatform.CustomJob(
        display_name="cbsc-v2-2-auto-t4-smoke-20260724-r2",
        worker_pool_specs=worker_pool_specs,
        staging_bucket=args.staging_bucket,
    )
    job.submit(
        service_account=args.service_account,
        timeout=args.timeout_seconds,
        scheduling_strategy=custom_job.Scheduling.Strategy.ON_DEMAND,
    )
    print(f"Vertex smoke coordinator: {job.resource_name}")


if __name__ == "__main__":
    main()
