from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path

import numpy as np
import torch

from .config import load_config, validate_config
from .contracts import NEUTRON_MASS_GEV
from .data.audit import audit_dataset
from .data.convert import convert_root_corpus
from .data.dataset import ShardedSparseDataset, load_geometry
from .data.geometry import scan_geometry
from .data.root_io import inspect_root_file, load_branch_schema
from .data.split import create_split
from .data.synthetic import create_synthetic_dataset
from .eval.benchmark import benchmark_model
from .eval.evaluator import evaluate_checkpoint
from .eval.invariants import invariant_report
from .models.system import CBSCZDC
from .preflight import validate_frozen_artifacts
from .training.checkpoint import load_checkpoint
from .training.trainer import compute_component_losses, train_from_config
from .training.weights import calibrate_loss_weights
from .utils import deep_merge, dump_json, dump_yaml, environment_snapshot, load_json, load_yaml, sha256_file


def _print(payload):
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))


def command_doctor(args):
    optional = {}
    for name in ["uproot", "awkward", "sklearn", "google.cloud.aiplatform"]:
        try:
            __import__(name)
            optional[name] = "available"
        except Exception as exc:
            optional[name] = f"missing: {type(exc).__name__}"
    _print({"environment": environment_snapshot(), "optional_dependencies": optional})


def command_inspect_root(args):
    schema = load_branch_schema(args.schema) if args.schema else None
    result = inspect_root_file(args.path, schema)
    if args.output:
        dump_json(result, args.output)
    _print(result)
    if schema is not None and result.get("missing_branches"):
        raise SystemExit(2)


def command_scan_geometry(args):
    result = scan_geometry(
        args.paths,
        args.schema,
        args.output,
        strict_project_counts=not args.no_strict_counts,
        position_tolerance_mm=args.position_tolerance_mm,
        z_tolerance_mm=args.z_tolerance_mm,
        step_size=args.step_size,
    )
    _print(result)


def command_convert(args):
    result = convert_root_corpus(
        args.paths,
        args.schema,
        args.geometry,
        args.output,
        target_mode=args.target_mode,
        threshold_gev=args.threshold_gev,
        min_kinetic_gev=args.min_kinetic_gev,
        max_kinetic_gev=args.max_kinetic_gev,
        shard_size=args.shard_size,
        step_size=args.step_size,
        fixed_vertex_tolerance_mm=args.fixed_vertex_tolerance_mm,
    )
    _print(result)


def command_make_synthetic(args):
    _print(create_synthetic_dataset(args.output, args.events, args.layers, args.nodes_per_layer, args.shard_size, args.seed))


def command_split(args):
    _print(create_split(args.manifest, args.output, tuple(args.fractions), args.seed, args.group_by))


def command_audit_dataset(args):
    kinetic = tuple(args.kinetic_range) if args.kinetic_range else None
    _print(audit_dataset(args.manifest, args.splits, args.split, args.output, kinetic))


def command_freeze_config(args):
    template = load_yaml(args.template)
    audit = load_json(args.audit)
    geometry_manifest_path = Path(args.geometry) / "geometry_manifest.json"
    geometry_manifest = load_json(geometry_manifest_path)
    manifest = load_json(args.manifest)
    split = load_json(args.splits)
    assignment_path = Path(args.splits).parent / split["assignment_file"]
    actual_manifest_hash = sha256_file(args.manifest)
    actual_split_hash = sha256_file(args.splits)
    actual_assignment_hash = sha256_file(assignment_path)
    if manifest["geometry_hash"] != geometry_manifest["geometry_hash"]:
        raise RuntimeError("dataset and geometry manifests have different geometry hashes")
    if split.get("manifest_sha256") != actual_manifest_hash:
        raise RuntimeError("split manifest does not match the dataset manifest hash")
    if split.get("assignment_sha256") != actual_assignment_hash:
        raise RuntimeError("split assignment hash does not match the split manifest")
    if audit.get("manifest_sha256") != actual_manifest_hash:
        raise RuntimeError("data audit does not match the dataset manifest")
    if audit.get("split_manifest_sha256") != actual_split_hash:
        raise RuntimeError("data audit does not match the split manifest")
    if audit.get("split") != "train":
        raise RuntimeError("configuration may only be frozen from a train-split audit")
    if int(audit.get("negative_response_count", -1)) != 0:
        raise RuntimeError("training audit contains negative detector response")
    if manifest.get("target_mode") != template["data"].get("target_mode"):
        raise RuntimeError("template target mode does not match the dataset")
    if float(manifest.get("threshold_gev", 0.0)) != float(
        template["data"].get("threshold_gev", 0.0)
    ):
        raise RuntimeError("template threshold does not match the dataset")
    if not manifest.get("synthetic", False) and any(
        value is None for value in audit.get("response_cap_by_energy_bin_gev", [])
    ):
        raise RuntimeError("production train audit contains an empty energy bin")
    override = {
        "data": {
            "manifest": str(Path(args.manifest).resolve()),
            "splits": str(Path(args.splits).resolve()),
            "response_cap_ratio": float(audit["response_cap_ratio"]),
            "response_cap_absolute_gev": float(audit["response_cap_absolute_gev"]),
        },
        "geometry": {
            "path": str(Path(args.geometry).resolve()),
            "n_nodes": int(geometry_manifest["n_nodes"]),
            "n_layers": int(geometry_manifest["n_layers"]),
            "geometry_hash": geometry_manifest["geometry_hash"],
        },
        "provenance": {
            "template_sha256": sha256_file(args.template),
            "audit_sha256": sha256_file(args.audit),
            "geometry_manifest_sha256": sha256_file(geometry_manifest_path),
            "dataset_manifest_sha256": actual_manifest_hash,
            "split_manifest_sha256": actual_split_hash,
            "dataset_geometry_hash": manifest["geometry_hash"],
            "split_assignment_sha256": actual_assignment_hash,
        },
    }
    frozen = deep_merge(template, override)
    validate_config(frozen)
    dump_yaml(frozen, args.output)
    _print({"output": str(Path(args.output).resolve()), "sha256": sha256_file(args.output)})


def command_train(args):
    config = load_config(args.config)
    if args.device:
        config["training"]["device"] = args.device
    if args.resume:
        config["training"]["resume_from"] = args.resume
    _print(train_from_config(config))


def command_preflight(args):
    config = load_config(args.config)
    report = validate_frozen_artifacts(config, verify_shards=not args.skip_shard_hashes)
    if args.output:
        dump_json(report, args.output)
    _print(report)


def _load_model(checkpoint, geometry, device):
    payload = torch.load(checkpoint, map_location=device, weights_only=False)
    config = payload["config"]
    geom = load_geometry(geometry, device)
    model = CBSCZDC(geom, config).to(device).eval()
    model.load_state_dict(payload["model_state"])
    return model, config, geom


def _p4_from_kinetic(kinetic, direction):
    kinetic = np.asarray(kinetic, dtype=np.float64)
    direction = np.asarray(direction, dtype=np.float64)
    direction = direction / np.linalg.norm(direction)
    total = kinetic + NEUTRON_MASS_GEV
    momentum = np.sqrt(np.maximum(total**2 - NEUTRON_MASS_GEV**2, 0.0))
    return np.concatenate([total[:, None], momentum[:, None] * direction[None]], axis=1).astype(np.float32)


def command_sample(args):
    device = torch.device(args.device)
    model, config, _ = _load_model(args.checkpoint, args.geometry, device)
    p4 = torch.from_numpy(_p4_from_kinetic(args.kinetic_gev, args.direction)).to(device)
    with torch.no_grad():
        out = model.sample(p4, args.profile_steps, args.share_steps, args.seed, not args.deterministic)
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        destination,
        p4_total_gev=p4.cpu().numpy(),
        kinetic_energy_gev=np.asarray(args.kinetic_gev, dtype=np.float32),
        cell_energy_gev=out.cell_energy.cpu().numpy(),
        total_response_gev=out.total_response.cpu().numpy(),
        layer_energy_gev=out.layer_energy.cpu().numpy(),
        counts=out.realized_counts.cpu().numpy(),
        support_mask=out.support_mask.cpu().numpy(),
    )
    _print({"output": str(destination.resolve()), "events": len(args.kinetic_gev)})


def command_qa(args):
    device = torch.device(args.device)
    model, config, _ = _load_model(args.checkpoint, args.geometry, device)
    kinetic = [0, 50, 100, 150, 200, 250, 300]
    p4 = torch.from_numpy(_p4_from_kinetic(kinetic, [0, 0, 1])).to(device)
    with torch.no_grad():
        out = model.sample(p4, args.profile_steps, args.share_steps, args.seed, True)
    report = invariant_report(out, model.layer_index, model.valid_mask, model.threshold_gev, args.tolerance)
    if args.output:
        dump_json(report, args.output)
    _print(report)
    if not report["pass"]:
        raise SystemExit(2)


def command_evaluate(args):
    report = evaluate_checkpoint(
        args.checkpoint, args.geometry, args.manifest, args.splits, args.split,
        args.output, args.device, args.batch_size, args.max_events, args.gates, args.seed,
    )
    _print(report)
    if args.require_pass and not report.get("decision", {}).get("pass", False):
        raise SystemExit(3)


def command_benchmark(args):
    device = torch.device(args.device)
    model, _, _ = _load_model(args.checkpoint, args.geometry, device)
    p4 = torch.from_numpy(_p4_from_kinetic([args.kinetic_gev] * args.batch_size, args.direction)).to(device)
    report = benchmark_model(model, p4, args.warmup, args.iterations, args.profile_steps, args.share_steps)
    if args.output:
        dump_json(report, args.output)
    _print(report)


def command_calibrate_weights(args):
    config = load_config(args.config)
    device = torch.device(args.device)
    geom = load_geometry(config["geometry"]["path"], device)
    model = CBSCZDC(geom, config).to(device)
    if args.checkpoint:
        load_checkpoint(args.checkpoint, model, map_location=device)
    d = config["data"]
    ds = ShardedSparseDataset(d["manifest"], d["splits"], "train", tuple(d["train_kinetic_gev"]), config["geometry"]["n_nodes"])
    generator = torch.Generator().manual_seed(int(config["training"]["seed"]))
    loader = torch.utils.data.DataLoader(
        ds,
        batch_size=config["training"]["batch_size"],
        shuffle=True,
        num_workers=0,
        generator=generator,
    )
    model.train()

    def batches():
        for batch in loader:
            yield {k: v.to(device) for k, v in batch.items()}

    def losses(batch):
        return compute_component_losses(model, batch, "joint")[0]

    report = calibrate_loss_weights(
        model,
        batches(),
        losses,
        args.max_batches,
        (args.clip_min, args.clip_max),
        expected_losses=set(config["loss_weights"]),
    )
    dump_json(report, args.output)
    _print(report)


def build_parser():
    parser = argparse.ArgumentParser(prog="cbsc-zdc", description="CBSC-ZDC v2.2 CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("doctor"); p.set_defaults(func=command_doctor)
    p = sub.add_parser("inspect-root"); p.add_argument("path"); p.add_argument("--schema"); p.add_argument("--output"); p.set_defaults(func=command_inspect_root)
    p = sub.add_parser("scan-geometry"); p.add_argument("paths", nargs="+"); p.add_argument("--schema", required=True); p.add_argument("--output", required=True); p.add_argument("--no-strict-counts", action="store_true"); p.add_argument("--position-tolerance-mm", type=float, default=1e-3); p.add_argument("--z-tolerance-mm", type=float, default=1e-2); p.add_argument("--step-size", type=int, default=2048); p.set_defaults(func=command_scan_geometry)
    p = sub.add_parser("convert"); p.add_argument("paths", nargs="+"); p.add_argument("--schema", required=True); p.add_argument("--geometry", required=True); p.add_argument("--output", required=True); p.add_argument("--target-mode", choices=["raw_deposit", "thresholded_readout"], default="raw_deposit"); p.add_argument("--threshold-gev", type=float, default=0.0); p.add_argument("--min-kinetic-gev", type=float, default=0.0); p.add_argument("--max-kinetic-gev", type=float, default=300.0); p.add_argument("--shard-size", type=int, default=4096); p.add_argument("--step-size", type=int, default=2048); p.add_argument("--fixed-vertex-tolerance-mm", type=float, default=1e-3); p.set_defaults(func=command_convert)
    p = sub.add_parser("make-synthetic"); p.add_argument("--output", required=True); p.add_argument("--events", type=int, default=512); p.add_argument("--layers", type=int, default=8); p.add_argument("--nodes-per-layer", type=int, default=16); p.add_argument("--shard-size", type=int, default=128); p.add_argument("--seed", type=int, default=20260723); p.set_defaults(func=command_make_synthetic)
    p = sub.add_parser("split"); p.add_argument("--manifest", required=True); p.add_argument("--output", required=True); p.add_argument("--fractions", type=float, nargs=3, default=[0.8, 0.1, 0.1]); p.add_argument("--seed", type=int, default=20260723); p.add_argument("--group-by", choices=["source_group", "event_hash"], default="source_group"); p.set_defaults(func=command_split)
    p = sub.add_parser("audit-dataset"); p.add_argument("--manifest", required=True); p.add_argument("--splits", required=True); p.add_argument("--split", choices=["train", "validation", "test"], default="train"); p.add_argument("--kinetic-range", type=float, nargs=2); p.add_argument("--output", required=True); p.set_defaults(func=command_audit_dataset)
    p = sub.add_parser("freeze-config"); p.add_argument("--template", required=True); p.add_argument("--audit", required=True); p.add_argument("--geometry", required=True); p.add_argument("--manifest", required=True); p.add_argument("--splits", required=True); p.add_argument("--output", required=True); p.set_defaults(func=command_freeze_config)
    p = sub.add_parser("preflight"); p.add_argument("--config", required=True); p.add_argument("--output"); p.add_argument("--skip-shard-hashes", action="store_true"); p.set_defaults(func=command_preflight)
    p = sub.add_parser("train"); p.add_argument("--config", required=True); p.add_argument("--device"); p.add_argument("--resume"); p.set_defaults(func=command_train)
    p = sub.add_parser("sample"); p.add_argument("--checkpoint", required=True); p.add_argument("--geometry", required=True); p.add_argument("--kinetic-gev", type=float, nargs="+", required=True); p.add_argument("--direction", type=float, nargs=3, default=[0,0,1]); p.add_argument("--profile-steps", type=int, default=8); p.add_argument("--share-steps", type=int, default=8); p.add_argument("--seed", type=int, default=20260723); p.add_argument("--deterministic", action="store_true"); p.add_argument("--output", required=True); p.add_argument("--device", default="cpu"); p.set_defaults(func=command_sample)
    p = sub.add_parser("qa"); p.add_argument("--checkpoint", required=True); p.add_argument("--geometry", required=True); p.add_argument("--profile-steps", type=int, default=8); p.add_argument("--share-steps", type=int, default=8); p.add_argument("--seed", type=int, default=20260723); p.add_argument("--tolerance", type=float, default=2e-5); p.add_argument("--output"); p.add_argument("--device", default="cpu"); p.set_defaults(func=command_qa)
    p = sub.add_parser("evaluate"); p.add_argument("--checkpoint", required=True); p.add_argument("--geometry", required=True); p.add_argument("--manifest", required=True); p.add_argument("--splits", required=True); p.add_argument("--split", choices=["validation", "test"], default="validation"); p.add_argument("--gates"); p.add_argument("--output", required=True); p.add_argument("--device", default="cpu"); p.add_argument("--batch-size", type=int, default=16); p.add_argument("--max-events", type=int); p.add_argument("--seed", type=int, default=20260723); p.add_argument("--require-pass", action="store_true"); p.set_defaults(func=command_evaluate)
    p = sub.add_parser("benchmark"); p.add_argument("--checkpoint", required=True); p.add_argument("--geometry", required=True); p.add_argument("--kinetic-gev", type=float, default=150.0); p.add_argument("--direction", type=float, nargs=3, default=[0,0,1]); p.add_argument("--batch-size", type=int, default=1); p.add_argument("--warmup", type=int, default=10); p.add_argument("--iterations", type=int, default=50); p.add_argument("--profile-steps", type=int, default=8); p.add_argument("--share-steps", type=int, default=8); p.add_argument("--device", default="cpu"); p.add_argument("--output"); p.set_defaults(func=command_benchmark)
    p = sub.add_parser("calibrate-loss-weights"); p.add_argument("--config", required=True); p.add_argument("--checkpoint"); p.add_argument("--max-batches", type=int, default=64); p.add_argument("--clip-min", type=float, default=0.25); p.add_argument("--clip-max", type=float, default=4.0); p.add_argument("--output", required=True); p.add_argument("--device", default="cpu"); p.set_defaults(func=command_calibrate_weights)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
