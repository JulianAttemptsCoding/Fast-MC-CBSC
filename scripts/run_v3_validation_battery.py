"""Run the v3 metric battery against the frozen validation bank.

Two subcommands:

    build-bank   freeze the immutable 10,000-pair energy-stratified manifest
    evaluate     run one checkpoint against a frozen bank

Everything that can change a number must be supplied explicitly or resolved
from a hash-verified frozen artifact.  There are no defaults for the checkpoint,
the frozen config, the bank, the geometry, the data or split hashes, the seeds,
the bin definition, the solver steps, the precision, the output namespace, or
the evaluation role.

The evaluation split is a constant, not a flag.  A battery that can be pointed
at the test split is one typo away from ending this project's ability to make an
untouched-test claim.

Neither subcommand trains, publishes, or selects a checkpoint.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader, Subset

from cbsc_zdc.data.dataset import ShardedSparseDataset, load_geometry
from cbsc_zdc.eval.v3_battery import (
    BOOTSTRAP_CONFIDENCE,
    BOOTSTRAP_REPLICATES,
    EVALUATION_ROLES,
    EVALUATION_SPLIT,
    REQUIRED_PAIRS,
    REQUIRED_PAIRS_PER_BIN,
    STRUCTURAL_SUBSAMPLE_EVENTS,
    BatteryContractError,
    BatteryRequest,
    battery_report,
    build_model,
    build_validation_manifest,
    closure_tolerances,
    invariant_report,
    load_validation_manifest,
    reduce_invariants,
    resolve_runtime_config,
)
from cbsc_zdc.utils import sha256_file


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )
    temporary.replace(path)


def checkpoint_identity(payload: dict, checkpoint: Path, frozen_config: Path,
                        expected_epoch: int) -> dict:
    """Prove that a checkpoint matches the epoch the report will claim."""
    try:
        embedded_epoch = int(payload["epoch"])
    except (KeyError, TypeError, ValueError) as exc:
        raise BatteryContractError(
            f"checkpoint has no valid embedded epoch: {checkpoint}"
        ) from exc
    if embedded_epoch != expected_epoch:
        raise BatteryContractError(
            "checkpoint provenance mismatch: "
            f"requested epoch {expected_epoch}, embedded epoch {embedded_epoch}, "
            f"checkpoint {checkpoint}"
        )
    return {
        "checkpoint_sha256": sha256_file(checkpoint),
        "checkpoint_embedded_epoch": embedded_epoch,
        "frozen_config_sha256": sha256_file(frozen_config),
    }


def build_bank(args) -> int:
    payload = build_validation_manifest(
        data_manifest=args.data_manifest,
        splits=args.splits,
        n_nodes=args.n_nodes,
        kinetic_range_gev=tuple(args.kinetic_range_gev),
        energy_bin_edges_gev=tuple(args.energy_bin_edges_gev),
        output=args.output,
        pairs=args.pairs,
        pairs_per_bin=args.pairs_per_bin,
    )
    print(json.dumps({
        "output": str(args.output).replace("\\", "/"),
        "content_sha256": payload["content_sha256"],
        "pairs": payload["pairs"],
        "evaluator_corpus_examples": payload["evaluator_corpus_examples"],
        "pairs_per_bin": payload["pairs_per_bin"],
        "split": payload["split"],
        "test_events_used": payload["test_events_used"],
    }, indent=2))
    return 0


def evaluate(args) -> int:
    request = BatteryRequest(
        checkpoint=args.checkpoint,
        frozen_config=args.frozen_config,
        validation_manifest=args.validation_manifest,
        geometry_manifest=args.geometry,
        data_manifest_sha256=args.data_manifest_sha256,
        splits_sha256=args.splits_sha256,
        generator_seed=args.generator_seed,
        evaluator_seeds=tuple(args.evaluator_seeds),
        energy_bin_edges_gev=tuple(args.energy_bin_edges_gev),
        profile_steps=args.profile_steps,
        share_steps=args.share_steps,
        precision=args.precision,
        output_namespace=args.output_namespace,
        evaluation_role=args.evaluation_role,
        device=args.device,
        batch_size=args.batch_size,
        bootstrap_replicates=args.bootstrap_replicates,
        bootstrap_confidence=args.bootstrap_confidence,
        metadata={"run_tag": args.run_tag, "epoch": args.epoch},
    )
    request.validate()

    bank = load_validation_manifest(request.validation_manifest)
    if sha256_file(bank["data_manifest"]) != request.data_manifest_sha256:
        raise BatteryContractError(
            "the declared data manifest hash does not match the manifest the bank "
            "was frozen against"
        )
    if sha256_file(bank["splits"]) != request.splits_sha256:
        raise BatteryContractError(
            "the declared splits hash does not match the splits the bank was "
            "frozen against"
        )

    payload = torch.load(request.checkpoint, map_location=request.device, weights_only=False)
    artifact_identity = checkpoint_identity(
        payload, request.checkpoint, request.frozen_config, args.epoch
    )
    config = payload["config"]
    geometry = load_geometry(request.geometry_manifest, request.device)
    runtime = resolve_runtime_config(config, request)
    model = build_model(geometry, config, payload, request.device)

    dataset = ShardedSparseDataset(
        bank["data_manifest"], bank["splits"], EVALUATION_SPLIT,
        tuple(bank["kinetic_range_gev"]), int(bank["n_nodes"]),
    )
    indices = [int(row["dataset_index"]) for row in bank["events"]]
    expected_ids = [int(row["event_id"]) for row in bank["events"]]
    loader = DataLoader(
        Subset(dataset, indices), batch_size=request.batch_size,
        shuffle=False, num_workers=0,
    )

    truth, generated, kinetic = [], [], []
    truth_visible, generated_visible, observed_ids = [], [], []
    invariants = []
    began = time.perf_counter()
    seen = 0
    with torch.no_grad():
        for batch in loader:
            p4 = batch["p4_total_gev"].to(request.device)
            out = model.sample(
                p4, request.profile_steps, request.share_steps,
                request.generator_seed + seen, True,
            )
            truth_cells = batch["cell_energy_gev"].numpy()
            generated_cells = out.cell_energy.cpu().numpy()
            truth.append(truth_cells)
            generated.append(generated_cells)
            kinetic.append(batch["kinetic_energy_gev"].numpy())
            truth_visible.append(truth_cells.sum(axis=1) > 0)
            generated_visible.append(generated_cells.sum(axis=1) > 0)
            observed_ids.extend(int(e) for e in batch["event_id"].tolist())
            absolute, relative = closure_tolerances(config)
            invariants.append(invariant_report(
                output=out, layer_index=model.layer_index,
                valid_mask=model.valid_mask, threshold_gev=model.threshold_gev,
                tolerance=absolute, relative_tolerance=relative,
            ))
            seen += len(p4)
    elapsed = time.perf_counter() - began

    if observed_ids != expected_ids:
        raise BatteryContractError(
            "the loaded events do not match the frozen bank order; the bank is "
            "the identity of the comparison and cannot be reordered"
        )

    truth = np.concatenate(truth)
    generated = np.concatenate(generated)
    kinetic = np.concatenate(kinetic)
    strata = [str(row["energy_bin"]) for row in bank["events"]]

    train_reference = None
    if args.memorization_reference_events:
        train_reference = _train_reference(
            bank, args.memorization_reference_events, args.memorization_reference_seed
        )

    report = battery_report(
        request=request,
        bank=bank,
        truth=truth,
        generated=generated,
        kinetic=kinetic,
        truth_visible=np.concatenate(truth_visible),
        generated_visible=np.concatenate(generated_visible),
        event_ids=expected_ids,
        strata=strata,
        layer_index=model.layer_index.cpu().numpy(),
        positions=geometry["positions_mm"].cpu().numpy(),
        ecal_layers=int(runtime.get("geometry", {}).get("ecal_layers", 1)),
        invariants=reduce_invariants(invariants),
        edge_index=getattr(model, "edge_index", None),
        train_reference=train_reference,
        structural_events=args.structural_subsample_events,
        timing={
            "total_seconds": float(elapsed),
            "seconds_per_event": float(elapsed / max(seen, 1)),
            "events": int(seen),
        },
    )
    report["identity"].update(artifact_identity)
    _write_json(args.output, report)
    print(json.dumps({
        "output": str(args.output).replace("\\", "/"),
        "pairs": report["pairs"],
        "evaluator_corpus_examples": report["evaluator_corpus_examples"],
        "test_events_used": report["test_events_used"],
        "structural_pass": report["structural_invariants"]["pass"],
        "high_level_c2st_auroc_mean": report["c2st"]["high_level"]["auroc_mean"],
        "low_level_c2st_auroc_mean": report["c2st"]["low_level"]["auroc_mean"],
        "condition_only_c2st_auroc_mean": report["c2st"]["condition_only"]["auroc_mean"],
        "evaluation_role": report["identity"]["evaluation_role"],
        "structural_subsample_events": report.get("topology", {}).get("subsample_events"),
        "scientific_status": report["scientific_status"],
    }, indent=2))
    return 0


def _train_reference(bank: dict, count: int, seed: int) -> np.ndarray:
    """A deterministic training sample, for the memorization floor only."""
    dataset = ShardedSparseDataset(
        bank["data_manifest"], bank["splits"], "train",
        tuple(bank["kinetic_range_gev"]), int(bank["n_nodes"]),
    )
    generator = torch.Generator().manual_seed(seed)
    order = torch.randperm(len(dataset), generator=generator)[:count].tolist()
    return np.stack([dataset[i]["cell_energy_gev"].numpy() for i in sorted(order)])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    bank = sub.add_parser("build-bank", help="freeze the fixed validation bank")
    bank.add_argument("--data-manifest", type=Path, required=True)
    bank.add_argument("--splits", type=Path, required=True)
    bank.add_argument("--n-nodes", type=int, required=True)
    bank.add_argument("--kinetic-range-gev", type=float, nargs=2, required=True)
    bank.add_argument("--energy-bin-edges-gev", type=float, nargs="+", required=True)
    bank.add_argument("--output", type=Path, required=True)
    bank.add_argument("--pairs", type=int, default=REQUIRED_PAIRS)
    bank.add_argument("--pairs-per-bin", type=int, default=REQUIRED_PAIRS_PER_BIN)
    bank.set_defaults(handler=build_bank)

    run = sub.add_parser("evaluate", help="run the battery on one checkpoint")
    for name in (
        "--checkpoint", "--frozen-config", "--validation-manifest",
        "--geometry", "--output",
    ):
        run.add_argument(name, type=Path, required=True)
    run.add_argument("--data-manifest-sha256", required=True)
    run.add_argument("--splits-sha256", required=True)
    run.add_argument("--generator-seed", type=int, required=True)
    run.add_argument("--evaluator-seeds", type=int, nargs=3, required=True)
    run.add_argument("--energy-bin-edges-gev", type=float, nargs="+", required=True)
    run.add_argument("--profile-steps", type=int, required=True)
    run.add_argument("--share-steps", type=int, required=True)
    run.add_argument("--precision", required=True, choices=["fp32"])
    run.add_argument("--output-namespace", required=True)
    run.add_argument("--evaluation-role", required=True, choices=list(EVALUATION_ROLES))
    run.add_argument("--run-tag", required=True)
    run.add_argument("--epoch", type=int, required=True)
    run.add_argument("--device", default="cpu")
    run.add_argument("--batch-size", type=int, default=8)
    run.add_argument("--bootstrap-replicates", type=int, default=BOOTSTRAP_REPLICATES)
    run.add_argument("--bootstrap-confidence", type=float, default=BOOTSTRAP_CONFIDENCE)
    run.add_argument(
        "--memorization-reference-events", type=int, default=0,
        help="size of the deterministic TRAIN sample used as the memorization "
             "reference; 0 records memorization as not computed rather than "
             "silently substituting validation truth",
    )
    run.add_argument("--memorization-reference-seed", type=int, default=20260815)
    run.add_argument(
        "--structural-subsample-events", type=int, default=STRUCTURAL_SUBSAMPLE_EVENTS,
        help="events used for the topology and memorization families, which run a "
             "Python union-find per event and pairwise distance matrices and do not "
             "scale to the full bank. Recorded in the output with its selection rule. "
             "The distribution and C2ST families always use every pair.",
    )
    run.set_defaults(handler=evaluate)

    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
