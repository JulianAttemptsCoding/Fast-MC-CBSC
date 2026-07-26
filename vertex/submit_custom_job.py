#!/usr/bin/env python3
from __future__ import annotations

import argparse
from google.cloud import aiplatform
from google.cloud.aiplatform_v1.types import custom_job


def main() -> None:
    p = argparse.ArgumentParser(description="Submit a CBSC-ZDC custom-container training job")
    p.add_argument("--project", required=True)
    p.add_argument("--region", required=True)
    p.add_argument("--staging-bucket", required=True)
    p.add_argument("--container-uri", required=True)
    p.add_argument("--display-name", required=True)
    p.add_argument("--input-prefix", required=True)
    p.add_argument(
        "--overlay-prefix",
        action="append",
        default=[],
        help="additional staged-input prefix; may be repeated",
    )
    p.add_argument("--output-prefix", required=True)
    p.add_argument("--config-relative", required=True)
    p.add_argument(
        "--manifest-relative",
        default="artifacts/data/dataset_manifest.json",
    )
    p.add_argument("--splits-relative", default="artifacts/splits.json")
    p.add_argument("--geometry-relative", default="artifacts/geometry")
    p.add_argument("--machine-type", default="n1-standard-8")
    p.add_argument("--accelerator-type", default="NVIDIA_TESLA_T4")
    p.add_argument("--accelerator-count", type=int, default=1)
    p.add_argument("--boot-disk-type", default="pd-ssd")
    p.add_argument("--boot-disk-size-gb", type=int, default=100)
    p.add_argument("--timeout-seconds", type=int)
    p.add_argument("--postflight-smoke", action="store_true")
    p.add_argument("--postflight-training", action="store_true")
    p.add_argument(
        "--async-submit",
        action="store_true",
        help="submit server-side and return without waiting for completion",
    )
    p.add_argument("--service-account")
    args = p.parse_args()

    aiplatform.init(project=args.project, location=args.region, staging_bucket=args.staging_bucket)
    job = aiplatform.CustomContainerTrainingJob(
        display_name=args.display_name,
        container_uri=args.container_uri,
    )
    container_args = [
        "--input-prefix", args.input_prefix,
        "--output-prefix", args.output_prefix,
        "--config-relative", args.config_relative,
        "--manifest-relative", args.manifest_relative,
        "--splits-relative", args.splits_relative,
        "--geometry-relative", args.geometry_relative,
        "--device", "cuda",
    ]
    for overlay_prefix in args.overlay_prefix:
        container_args.extend(["--overlay-prefix", overlay_prefix])
    if args.postflight_smoke:
        container_args.append("--postflight-smoke")
    if args.postflight_training:
        container_args.append("--postflight-training")
    job.run(
        args=container_args,
        replica_count=1,
        machine_type=args.machine_type,
        accelerator_type=args.accelerator_type,
        accelerator_count=args.accelerator_count,
        boot_disk_type=args.boot_disk_type,
        boot_disk_size_gb=args.boot_disk_size_gb,
        timeout=args.timeout_seconds,
        service_account=args.service_account,
        scheduling_strategy=custom_job.Scheduling.Strategy.ON_DEMAND,
        sync=not args.async_submit,
    )
    if args.async_submit:
        print(
            "Vertex submission accepted asynchronously; "
            f"display name: {args.display_name}"
        )
    else:
        print(f"Vertex custom job: {job.resource_name}")


if __name__ == "__main__":
    main()
