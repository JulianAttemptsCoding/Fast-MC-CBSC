#!/usr/bin/env python3
from __future__ import annotations

import argparse

from google.cloud import aiplatform
from google.cloud.aiplatform_v1.types import custom_job


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Submit full production ROOT preparation as a Vertex CustomJob"
    )
    parser.add_argument("--project", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--staging-bucket", required=True)
    parser.add_argument("--container-uri", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--root-uri", required=True)
    parser.add_argument("--expected-generation", required=True)
    parser.add_argument("--expected-size", required=True, type=int)
    parser.add_argument("--expected-crc32c", required=True)
    parser.add_argument("--output-prefix", required=True)
    parser.add_argument("--service-account")
    parser.add_argument("--machine-type", default="n1-highmem-8")
    parser.add_argument("--boot-disk-type", default="pd-ssd")
    parser.add_argument("--boot-disk-size-gb", type=int, default=200)
    parser.add_argument("--timeout-seconds", type=int, default=86400)
    parser.add_argument("--seed", type=int, default=20260723)
    parser.add_argument("--reuse-geometry-prefix")
    args = parser.parse_args()

    aiplatform.init(
        project=args.project,
        location=args.region,
        staging_bucket=args.staging_bucket,
    )
    container_args = [
        "--root-uri",
        args.root_uri,
        "--output-prefix",
        args.output_prefix,
        "--expected-generation",
        args.expected_generation,
        "--expected-size",
        str(args.expected_size),
        "--expected-crc32c",
        args.expected_crc32c,
        "--seed",
        str(args.seed),
    ]
    if args.reuse_geometry_prefix:
        container_args.extend(
            ["--reuse-geometry-prefix", args.reuse_geometry_prefix]
        )
    worker_pool_specs = [
        {
            "machine_spec": {"machine_type": args.machine_type},
            "replica_count": 1,
            "disk_spec": {
                "boot_disk_type": args.boot_disk_type,
                "boot_disk_size_gb": args.boot_disk_size_gb,
            },
            "container_spec": {
                "image_uri": args.container_uri,
                "command": [
                    "python",
                    "-m",
                    "cbsc_zdc.cloud.vertex_prepare",
                ],
                "args": container_args,
            },
        }
    ]
    job = aiplatform.CustomJob(
        display_name=args.display_name,
        worker_pool_specs=worker_pool_specs,
        staging_bucket=args.staging_bucket,
    )
    job.run(
        service_account=args.service_account,
        timeout=args.timeout_seconds,
        scheduling_strategy=custom_job.Scheduling.Strategy.ON_DEMAND,
        sync=True,
    )
    print(f"Vertex production preparation job: {job.resource_name}")


if __name__ == "__main__":
    main()
