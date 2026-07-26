#!/usr/bin/env python3
from __future__ import annotations

import argparse

from google.cloud import aiplatform
from google.cloud.aiplatform_v1.types import custom_job


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--staging-bucket", required=True)
    parser.add_argument("--container-uri", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--input-prefix", required=True)
    parser.add_argument("--overlay-prefix", action="append", default=[])
    parser.add_argument("--output-prefix", required=True)
    parser.add_argument("--config-relative", required=True)
    parser.add_argument("--manifest-relative", default="artifacts/data/dataset_manifest.json")
    parser.add_argument("--splits-relative", default="artifacts/splits.json")
    parser.add_argument("--geometry-relative", default="artifacts/geometry")
    parser.add_argument("--checkpoint-relative", required=True)
    parser.add_argument("--checkpoint-sha256", required=True)
    parser.add_argument("--max-batches", type=int, default=64)
    parser.add_argument("--clip-min", type=float, default=0.25)
    parser.add_argument("--clip-max", type=float, default=4.0)
    parser.add_argument("--timeout-seconds", type=int, default=3600)
    parser.add_argument("--service-account", required=True)
    parser.add_argument("--async-submit", action="store_true")
    args = parser.parse_args()

    aiplatform.init(
        project=args.project,
        location=args.region,
        staging_bucket=args.staging_bucket,
    )
    job = aiplatform.CustomContainerTrainingJob(
        display_name=args.display_name,
        container_uri=args.container_uri,
        command=["python", "-m", "cbsc_zdc.cloud.vertex_calibrate"],
    )
    container_args = [
        "--input-prefix",
        args.input_prefix,
        "--output-prefix",
        args.output_prefix,
        "--config-relative",
        args.config_relative,
        "--manifest-relative",
        args.manifest_relative,
        "--splits-relative",
        args.splits_relative,
        "--geometry-relative",
        args.geometry_relative,
        "--checkpoint-relative",
        args.checkpoint_relative,
        "--checkpoint-sha256",
        args.checkpoint_sha256,
        "--max-batches",
        str(args.max_batches),
        "--clip-min",
        str(args.clip_min),
        "--clip-max",
        str(args.clip_max),
        "--device",
        "cuda",
    ]
    for overlay in args.overlay_prefix:
        container_args.extend(["--overlay-prefix", overlay])
    job.run(
        args=container_args,
        replica_count=1,
        machine_type="n1-standard-8",
        accelerator_type="NVIDIA_TESLA_T4",
        accelerator_count=1,
        boot_disk_type="pd-ssd",
        boot_disk_size_gb=100,
        timeout=args.timeout_seconds,
        service_account=args.service_account,
        scheduling_strategy=custom_job.Scheduling.Strategy.ON_DEMAND,
        sync=not args.async_submit,
    )
    if args.async_submit:
        print(
            "Vertex calibration submission accepted asynchronously; "
            f"display name: {args.display_name}"
        )
    else:
        print(f"Vertex calibration custom job: {job.resource_name}")


if __name__ == "__main__":
    main()
