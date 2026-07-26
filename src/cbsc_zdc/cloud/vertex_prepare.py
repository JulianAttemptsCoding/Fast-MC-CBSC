from __future__ import annotations

import argparse
import faulthandler
import json
import shutil
import traceback
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from ..cli import command_freeze_config
from ..data.audit import audit_dataset
from ..data.convert import convert_root_corpus
from ..data.dataset import ShardedSparseDataset
from ..data.geometry import geometry_hash, scan_geometry
from ..data.root_io import inspect_root_file, load_branch_schema
from ..data.split import SPLIT_NAMES, _energy_bins, create_split
from ..preflight import validate_frozen_artifacts
from ..utils import (
    dump_json,
    dump_yaml,
    environment_snapshot,
    load_json,
    load_yaml,
    sha256_file,
)
from .vertex_stage import _parse_gs, download_prefix, upload_directory


def download_object(
    uri: str,
    destination: Path,
    *,
    expected_generation: str | None = None,
    expected_size: int | None = None,
    expected_crc32c: str | None = None,
) -> dict:
    try:
        from google.cloud import storage  # type: ignore
    except ImportError as exc:
        raise RuntimeError("install the cloud extra") from exc
    bucket_name, object_name = _parse_gs(uri)
    if not object_name:
        raise ValueError("production ROOT URI must name one object")
    client = storage.Client()
    blob = client.bucket(bucket_name).blob(
        object_name,
        generation=int(expected_generation) if expected_generation else None,
    )
    blob.reload()
    observed_generation = str(blob.generation)
    observed_size = int(blob.size or 0)
    observed_crc32c = blob.crc32c
    if expected_generation and observed_generation != expected_generation:
        raise RuntimeError(
            "production ROOT generation mismatch: "
            f"expected={expected_generation} observed={observed_generation}"
        )
    if expected_size is not None and observed_size != expected_size:
        raise RuntimeError(
            "production ROOT size mismatch: "
            f"expected={expected_size} observed={observed_size}"
        )
    if expected_crc32c and observed_crc32c != expected_crc32c:
        raise RuntimeError(
            "production ROOT CRC32C mismatch: "
            f"expected={expected_crc32c} observed={observed_crc32c}"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    blob.download_to_filename(destination)
    return {
        "uri": uri,
        "bucket": bucket_name,
        "name": object_name,
        "generation": observed_generation,
        "size": observed_size,
        "crc32c": observed_crc32c,
        "local_sha256": sha256_file(destination),
    }


def create_pilot_split(
    manifest_path: Path,
    full_split_path: Path,
    output_path: Path,
    *,
    seed: int,
    train_per_energy_bin: int,
    validation_per_energy_bin: int,
) -> dict:
    dataset = ShardedSparseDataset(manifest_path)
    kinetic = dataset._all_kinetic().astype(np.float64, copy=False)
    bins = _energy_bins(kinetic)
    full_split = load_json(full_split_path)
    full_assignment_path = full_split_path.parent / full_split["assignment_file"]
    full_assignment = np.load(full_assignment_path, allow_pickle=False)["split_code"]
    pilot_assignment = np.full(len(full_assignment), 3, dtype=np.int8)
    requested = {0: train_per_energy_bin, 1: validation_per_energy_bin}
    selected_counts = {}
    for split_code, per_bin in requested.items():
        selected_counts[SPLIT_NAMES[split_code]] = []
        for bin_index in range(13):
            candidates = np.where(
                (full_assignment == split_code) & (bins == bin_index)
            )[0]
            if len(candidates) < per_bin:
                raise RuntimeError(
                    f"pilot selection lacks split={SPLIT_NAMES[split_code]} "
                    f"energy_bin={bin_index}: have={len(candidates)} need={per_bin}"
                )
            rng = np.random.default_rng(seed + split_code * 1000 + bin_index)
            chosen = np.sort(rng.choice(candidates, size=per_bin, replace=False))
            pilot_assignment[chosen] = split_code
            selected_counts[SPLIT_NAMES[split_code]].append(int(len(chosen)))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    assignment_path = output_path.with_name(output_path.stem + "_assignments.npz")
    np.savez_compressed(assignment_path, split_code=pilot_assignment)
    report = {
        "format_version": 1,
        "pilot": True,
        "test_data_used": False,
        "manifest_path": str(manifest_path.resolve()),
        "manifest_sha256": sha256_file(manifest_path),
        "assignment_file": assignment_path.name,
        "assignment_sha256": sha256_file(assignment_path),
        "seed": seed,
        "group_by": "copied_event_hash_split_train_validation_only",
        "parent_split_manifest_sha256": sha256_file(full_split_path),
        "parent_assignment_sha256": full_split["assignment_sha256"],
        "counts": {
            "train": int(np.sum(pilot_assignment == 0)),
            "validation": int(np.sum(pilot_assignment == 1)),
            "test": 0,
            "excluded": int(np.sum(pilot_assignment == 3)),
        },
        "energy_bin_counts": {
            "train": np.bincount(
                bins[pilot_assignment == 0], minlength=13
            ).tolist(),
            "validation": np.bincount(
                bins[pilot_assignment == 1], minlength=13
            ).tolist(),
            "test": [0] * 13,
        },
        "selected_per_bin": selected_counts,
    }
    dump_json(report, output_path)
    return report


def main(argv=None) -> None:
    faulthandler.enable(all_threads=True)
    parser = argparse.ArgumentParser(
        description="Prepare the complete production ROOT corpus for frozen Vertex training"
    )
    parser.add_argument("--root-uri", required=True)
    parser.add_argument("--expected-generation", required=True)
    parser.add_argument("--expected-size", required=True, type=int)
    parser.add_argument("--expected-crc32c", required=True)
    parser.add_argument("--output-prefix", required=True)
    parser.add_argument(
        "--schema",
        default="configs/schema_production_myTree.yaml",
    )
    parser.add_argument("--work-dir", default="/tmp/cbsc_zdc_prepare")
    parser.add_argument("--seed", type=int, default=20260723)
    parser.add_argument("--geometry-step-size", type=int, default=2048)
    parser.add_argument("--conversion-step-size", type=int, default=128)
    parser.add_argument("--reuse-geometry-prefix")
    parser.add_argument("--shard-size", type=int, default=4096)
    parser.add_argument("--pilot-train-per-bin", type=int, default=26)
    parser.add_argument("--pilot-validation-per-bin", type=int, default=8)
    args = parser.parse_args(argv)

    work = Path(args.work_dir)
    source_path = work / "source/production.root"
    output_root = work / "output"
    artifacts = output_root / "artifacts"
    configs = output_root / "configs"
    output_root.mkdir(parents=True, exist_ok=True)
    configs.mkdir(parents=True, exist_ok=True)
    dump_json(environment_snapshot(), output_root / "prepare_environment.json")

    try:
        source_identity = download_object(
            args.root_uri,
            source_path,
            expected_generation=args.expected_generation,
            expected_size=args.expected_size,
            expected_crc32c=args.expected_crc32c,
        )
        dump_json(source_identity, output_root / "source_identity.json")
        print(json.dumps(source_identity, indent=2, sort_keys=True), flush=True)

        schema_path = Path(args.schema).resolve()
        schema = load_branch_schema(schema_path)
        inspection = inspect_root_file(source_path, schema)
        dump_json(inspection, artifacts / "root_inspection.json")
        if inspection.get("missing_branches"):
            raise RuntimeError(
                f"production schema mismatch: {inspection['missing_branches']}"
            )

        geometry_dir = artifacts / "geometry"
        if args.reuse_geometry_prefix:
            reused_root = work / "reused_geometry"
            download_prefix(args.reuse_geometry_prefix, reused_root)
            reused_identity = load_json(reused_root / "source_identity.json")
            for identity_key in ("uri", "generation", "size", "crc32c", "local_sha256"):
                if reused_identity.get(identity_key) != source_identity.get(identity_key):
                    raise RuntimeError(
                        "reused geometry source mismatch for "
                        f"{identity_key}: reused={reused_identity.get(identity_key)} "
                        f"current={source_identity.get(identity_key)}"
                    )
            reused_gate = load_json(reused_root / "geometry_gate.json")
            if reused_gate.get("pass") is not True:
                raise RuntimeError("reused geometry gate did not pass")
            reused_geometry = reused_root / "artifacts/geometry"
            reused_manifest_path = reused_geometry / "geometry_manifest.json"
            reused_manifest = load_json(reused_manifest_path)
            if reused_manifest.get("schema_sha256") != sha256_file(schema_path):
                raise RuntimeError("reused geometry schema hash mismatch")
            if (
                int(reused_manifest.get("n_nodes", -1)) != 6790
                or int(reused_manifest.get("n_layers", -1)) != 65
                or reused_manifest.get("layer_counts")
                != [400, *([100] * 63), 90]
            ):
                raise RuntimeError("reused geometry violates strict project counts")
            if not reused_manifest.get("source_files") or (
                reused_manifest["source_files"][0].get("sha256")
                != source_identity["local_sha256"]
            ):
                raise RuntimeError("reused geometry source SHA-256 mismatch")
            with np.load(reused_geometry / "geometry.npz", allow_pickle=False) as archive:
                reused_arrays = {name: archive[name] for name in archive.files}
            if geometry_hash(reused_arrays) != reused_manifest.get("geometry_hash"):
                raise RuntimeError("reused geometry content hash mismatch")
            shutil.copytree(reused_geometry, geometry_dir, dirs_exist_ok=True)
        else:
            scan_geometry(
                [source_path],
                schema_path,
                geometry_dir,
                strict_project_counts=True,
                position_tolerance_mm=1e-3,
                z_tolerance_mm=1e-2,
                step_size=args.geometry_step_size,
            )
        geometry_manifest_path = geometry_dir / "geometry_manifest.json"
        dump_json(
            {
                "pass": True,
                "geometry_manifest_sha256": sha256_file(geometry_manifest_path),
                "geometry_npz_sha256": sha256_file(geometry_dir / "geometry.npz"),
                "source_identity": source_identity,
                "reused_from": args.reuse_geometry_prefix,
            },
            output_root / "geometry_gate.json",
        )
        # Preserve the last passed expensive gate even if native conversion code
        # later terminates before Python can upload a failure report.
        upload_directory(output_root, args.output_prefix)
        data_dir = artifacts / "data"
        convert_root_corpus(
            [source_path],
            schema_path,
            geometry_dir,
            data_dir,
            target_mode="raw_deposit",
            threshold_gev=0.0,
            min_kinetic_gev=0.0,
            max_kinetic_gev=300.0,
            shard_size=args.shard_size,
            step_size=args.conversion_step_size,
            fixed_vertex_tolerance_mm=1e-3,
        )

        manifest_path = data_dir / "dataset_manifest.json"
        split_path = artifacts / "splits.json"
        create_split(
            manifest_path,
            split_path,
            fractions=(0.8, 0.1, 0.1),
            seed=args.seed,
            group_by="event_hash",
        )
        full_audit_path = artifacts / "train_data_audit.json"
        audit_dataset(
            manifest_path,
            split_path,
            "train",
            full_audit_path,
            kinetic_range_gev=(0.0, 300.0),
        )

        pilot_split_path = artifacts / "pilot_splits.json"
        create_pilot_split(
            manifest_path,
            split_path,
            pilot_split_path,
            seed=args.seed,
            train_per_energy_bin=args.pilot_train_per_bin,
            validation_per_energy_bin=args.pilot_validation_per_bin,
        )
        pilot_audit_path = artifacts / "pilot_train_data_audit.json"
        audit_dataset(
            manifest_path,
            pilot_split_path,
            "train",
            pilot_audit_path,
            kinetic_range_gev=(0.0, 300.0),
        )

        template = load_yaml("configs/templates/train_full_0_300_raw.yaml")
        template["project"].update(
            {
                "name": "cbsc-zdc-v2-2-production-full-architecture-smoke",
                "run_dir": "runs/production_full_architecture_smoke",
                "pilot": True,
            }
        )
        template["training"].update(
            {
                "seed": args.seed,
                "epochs": 1,
                "gradient_accumulation": 1,
                "early_stopping_patience": 2,
            }
        )
        pilot_template_path = configs / "pilot_full_architecture_template.yaml"
        dump_yaml(template, pilot_template_path)
        frozen_pilot_path = configs / "frozen_production_full_architecture_smoke.yaml"
        command_freeze_config(
            SimpleNamespace(
                template=str(pilot_template_path),
                audit=str(pilot_audit_path),
                geometry=str(geometry_dir),
                manifest=str(manifest_path),
                splits=str(pilot_split_path),
                output=str(frozen_pilot_path),
            )
        )
        frozen_pilot = load_yaml(frozen_pilot_path)
        pilot_preflight = validate_frozen_artifacts(
            frozen_pilot, verify_shards=True
        )
        dump_json(pilot_preflight, artifacts / "pilot_preflight.json")
        dump_json(
            {
                "pass": True,
                "production_root": source_identity,
                "inspection_entries": inspection["entries"],
                "geometry_manifest_sha256": sha256_file(
                    geometry_dir / "geometry_manifest.json"
                ),
                "dataset_manifest_sha256": sha256_file(manifest_path),
                "split_manifest_sha256": sha256_file(split_path),
                "train_audit_sha256": sha256_file(full_audit_path),
                "pilot_config_sha256": sha256_file(frozen_pilot_path),
                "test_data_used_for_pilot": False,
            },
            output_root / "prepare_result.json",
        )
    except Exception as exc:
        dump_json(
            {
                "pass": False,
                "exception_type": type(exc).__name__,
                "message": str(exc),
                "traceback": traceback.format_exc(),
                "environment": environment_snapshot(),
            },
            output_root / "prepare_failure.json",
        )
        upload_directory(output_root, args.output_prefix)
        raise

    upload_directory(output_root, args.output_prefix)
    print("production preparation completed", flush=True)


if __name__ == "__main__":
    main()
