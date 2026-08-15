"""Re-measure the D1 critic against the real production graph.

The 2026-08-14 preflight reported a D1 peak of 14.85 GiB, 63.1% of a 24 GB card,
and concluded D1 fits at the declared batch size.  That measurement used a
*synthetic* graph with **40,740 edges**.  The frozen production geometry carries
**107,920** -- 2.65x more -- and the D1 critic runs edge-message blocks over
every one of them.  The earlier number is therefore an underestimate for the
real geometry, and linearly scaling it would be an estimate, not a measurement.

This script loads the actual frozen geometry and the actual frozen model
dimensions, and escalates in a fixed order so an out-of-memory failure is
attributed to a specific shape rather than to the whole configuration:

    1. allocation and forward smoke at batch 1
    2. one complete D1 critic update at the declared critic batch
    3. one complete D1 generator-through-frozen-critic update at the training
       loop's generator batch
    4. only if all three fit: warmup + measured repeats

Batch size, replay capacity, R1 gamma, spectral normalization and the layer
count are declared values.  They are never reduced here to obtain a pass.  If
the declared path does not fit, the correct output is RESOURCE_PREFLIGHT_FAIL.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Callable

import torch
import yaml

from cbsc_zdc.data.dataset import load_geometry
from cbsc_zdc.models.critics import ShareCritic
from cbsc_zdc.models.system import CBSCZDC
from cbsc_zdc.training.adversarial import (
    freeze_parameters,
    lazy_r1_multiplier,
    r1_penalty,
    restore_parameters,
)
from cbsc_zdc.training.stage_sampling import TruthStructure, sample_share_for_loss

NEUTRON_MASS_GEV = 0.93956542052
EXPECTED_NODES = 6790
EXPECTED_EDGES = 107920
EXPECTED_LAYERS = 65


def p4(batch: int, device: torch.device, energy: float = 150.0) -> torch.Tensor:
    total = torch.full((batch,), energy, dtype=torch.float64)
    momentum = torch.sqrt(total.square() - NEUTRON_MASS_GEV**2)
    return torch.stack(
        [total, torch.zeros_like(total), torch.zeros_like(total), momentum], dim=1
    ).float().to(device)


def make_truth(batch: int, model: CBSCZDC, n_layers: int, device: torch.device) -> TruthStructure:
    counts = torch.zeros(batch, n_layers, dtype=torch.long, device=device)
    support = torch.zeros(batch, int(model.layer_index.numel()), dtype=torch.bool, device=device)
    for layer in range(n_layers):
        ids = torch.nonzero(model.layer_index == layer).flatten()
        if ids.numel() == 0:
            continue
        take = max(1, min(int(ids.numel()) // 4, 24))
        counts[:, layer] = take
        support[:, ids[:take]] = True
    return TruthStructure(
        visible=torch.ones(batch, dtype=torch.bool, device=device),
        total_response=torch.full((batch,), 60.0, device=device),
        first_layer=torch.zeros(batch, dtype=torch.long, device=device),
        active_layers=torch.ones(batch, n_layers, dtype=torch.bool, device=device),
        layer_energy=torch.full((batch, n_layers), 60.0 / n_layers, device=device),
        requested_counts=counts,
        support_mask=support,
    )


def memory_snapshot(device: torch.device) -> dict[str, float]:
    if device.type != "cuda":
        return {}
    free, total = torch.cuda.mem_get_info(device)
    return {
        "peak_allocated_gib": torch.cuda.max_memory_allocated(device) / 1024**3,
        "peak_reserved_gib": torch.cuda.max_memory_reserved(device) / 1024**3,
        "device_total_gib": total / 1024**3,
        "device_free_gib": free / 1024**3,
    }


def attempt(name: str, step: Callable[[], Any], device: torch.device) -> dict[str, Any]:
    """One escalation stage. An OOM here names the exact shape that failed."""
    if device.type == "cuda":
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats(device)
    began = time.perf_counter()
    try:
        step()
        if device.type == "cuda":
            torch.cuda.synchronize(device)
            torch.cuda.empty_cache()
    except torch.cuda.OutOfMemoryError as exc:
        return {
            "stage": name,
            "status": "RESOURCE_PREFLIGHT_FAIL",
            "reason": "CUDA out of memory",
            "detail": str(exc)[:400],
            "declared_values_not_reduced": [
                "critic batch size", "generator batch size", "replay capacity",
                "R1 gamma", "spectral normalization", "65 detector layers",
                "edge count",
            ],
            **memory_snapshot(device),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "stage": name, "status": "ERROR",
            "detail": f"{type(exc).__name__}: {exc}"[:400],
        }
    return {
        "stage": name, "status": "ok",
        "seconds": time.perf_counter() - began,
        **memory_snapshot(device),
    }


def measure(
    name: str, step: Callable[[], Any], device: torch.device,
    *, warmup: int, measured: int, repeats: int, batch: int,
) -> dict[str, Any]:
    per_repeat = []
    if device.type == "cuda":
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats(device)
    try:
        for _ in range(warmup):
            step()
        if device.type == "cuda":
            torch.cuda.synchronize(device)
        for _ in range(repeats):
            start = time.perf_counter()
            for _ in range(measured):
                step()
            if device.type == "cuda":
                torch.cuda.synchronize(device)
            per_repeat.append((time.perf_counter() - start) / measured)
    except torch.cuda.OutOfMemoryError as exc:
        return {
            "probe": name, "status": "RESOURCE_PREFLIGHT_FAIL",
            "reason": "CUDA out of memory during measurement",
            "detail": str(exc)[:400], **memory_snapshot(device),
        }
    ordered = sorted(per_repeat)
    return {
        "probe": name,
        "status": "ok",
        "repeats": repeats,
        "warmup_updates": warmup,
        "updates_measured_each": measured,
        "batch": batch,
        "seconds_per_update_median": ordered[len(ordered) // 2],
        "seconds_per_update_min": ordered[0],
        "seconds_per_update_max": ordered[-1],
        "examples_per_second": batch / ordered[len(ordered) // 2],
        **memory_snapshot(device),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--geometry", type=Path, required=True)
    parser.add_argument("--frozen-config", type=Path, required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--critic-batch", type=int, default=4)
    parser.add_argument("--generator-batch", type=int, default=6)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--measured", type=int, default=100)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--r1-gamma", type=float, default=1.0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    device = torch.device(args.device)
    torch.manual_seed(20260815)
    frozen = yaml.safe_load(args.frozen_config.read_text(encoding="utf-8"))

    geometry = load_geometry(str(args.geometry), device)
    n_nodes = int(geometry["layer_index"].numel())
    n_edges = int(geometry["edge_index"].shape[1])
    n_layers = int(geometry["layer_index"].max().item()) + 1

    report: dict[str, Any] = {
        "schema_version": 1,
        "kind": "cbsc-zdc-v3-d1-production-graph-preflight",
        "recorded_at": "2026-08-15",
        "supersedes": "audit/v3_resource_preflight_20260814.json D1 probes, which used a synthetic 40,740-edge graph",
        "device": args.device,
        "device_name": torch.cuda.get_device_name(device) if device.type == "cuda" else "cpu",
        "torch": torch.__version__,
        "geometry": {
            "path": str(args.geometry).replace("\\", "/"),
            "nodes": n_nodes,
            "edges": n_edges,
            "layers": n_layers,
            "expected_nodes": EXPECTED_NODES,
            "expected_edges": EXPECTED_EDGES,
            "expected_layers": EXPECTED_LAYERS,
            "is_production_graph": (
                n_nodes == EXPECTED_NODES
                and n_edges == EXPECTED_EDGES
                and n_layers == EXPECTED_LAYERS
            ),
            "synthetic_preflight_edges": 40740,
            "edge_ratio_vs_synthetic": round(n_edges / 40740, 4),
        },
        "frozen_config": str(args.frozen_config).replace("\\", "/"),
        "critic_batch": args.critic_batch,
        "generator_batch": args.generator_batch,
        "r1_gamma": args.r1_gamma,
        "authorization": "measurement only; this does not authorize a training campaign",
        "declared_values_not_adjusted": [
            f"critic batch size {args.critic_batch}",
            f"generator batch size {args.generator_batch}",
            "replay capacity 65536", f"R1 gamma {args.r1_gamma}",
            "spectral normalization", f"{n_layers} detector layers",
            f"{n_edges} production edges",
        ],
    }
    if not report["geometry"]["is_production_graph"]:
        report["status"] = "ERROR"
        report["error"] = (
            f"loaded geometry is {n_nodes} nodes / {n_edges} edges / {n_layers} layers, "
            f"not the frozen production {EXPECTED_NODES}/{EXPECTED_EDGES}/{EXPECTED_LAYERS}. "
            "A D1 production claim must be measured on the real graph."
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2, sort_keys=True))
        return 1

    model = CBSCZDC(geometry, frozen).to(device)
    cond_dim = int(frozen["model"]["condition_dim"])
    axis_dim = 4 if bool(frozen.get("model", {}).get("axis_features", False)) else 4

    share_critic = ShareCritic(
        int(model.node_features.shape[1]), int(model.edge_features.shape[1]),
        cond_dim, n_layers, axis_dim,
        hidden=96, blocks=2, heads=4, context_layers=2, embed_dim=128,
    ).to(device)
    gen_opt = torch.optim.Adam(model.parameters(), lr=1e-4)
    critic_opt = torch.optim.Adam(share_critic.parameters(), lr=1e-4, betas=(0.0, 0.99))

    stages = []

    def build(batch: int):
        truth = make_truth(batch, model, n_layers, device)
        cond = p4(batch, device)
        axis = torch.randn(batch, n_nodes, axis_dim, device=device)
        return truth, cond, axis

    def score(cell, truth, cond, axis):
        return share_critic(
            model.encode_condition(cond), cell_energy=cell,
            layer_energy=truth.layer_energy, support_mask=truth.support_mask,
            node_features=model.node_features, axis=axis,
            edge_index=model.edge_index, edge_features=model.edge_features,
            layer_index=model.layer_index, valid_mask=model.valid_mask,
        )

    # ---- stage 1: allocation and forward smoke at batch 1
    def smoke():
        truth, cond, axis = build(1)
        with torch.no_grad():
            score(truth.support_mask.float() * 0.1, truth, cond, axis)

    stages.append(attempt("allocation_and_forward_smoke_batch_1", smoke, device))

    truth_c, cond_c, axis_c = build(args.critic_batch)
    real_cells = truth_c.support_mask.float() * (60.0 / max(int(truth_c.support_mask.sum(1).max()), 1))

    def critic_update(with_r1: bool = True):
        critic_opt.zero_grad(set_to_none=True)
        fake = sample_share_for_loss(
            model, cond_c, truth_c, torch.randn(args.critic_batch, n_nodes, device=device),
            share_steps=8,
        ).cell_energy.detach()
        real = real_cells.clone().requires_grad_(with_r1)
        real_score = score(real, truth_c, cond_c, axis_c)
        fake_score = score(fake, truth_c, cond_c, axis_c)
        loss = torch.nn.functional.softplus(-real_score).mean() + \
            torch.nn.functional.softplus(fake_score).mean()
        if with_r1:
            loss = loss + args.r1_gamma * lazy_r1_multiplier(16, 16) * r1_penalty(real_score, real)
        loss.backward()
        critic_opt.step()

    # ---- stage 2: one complete D1 critic update at the declared critic batch,
    # including the lazy R1 term, which is where the second-order graph lives.
    stages.append(attempt(
        f"d1_critic_update_batch_{args.critic_batch}",
        lambda: critic_update(True), device,
    ))

    truth_g, cond_g, axis_g = build(args.generator_batch)

    def generator_update():
        # The critic is frozen by clearing requires_grad, never under no_grad:
        # no_grad would sever the generator's gradient path entirely.
        saved = freeze_parameters(share_critic)
        try:
            gen_opt.zero_grad(set_to_none=True)
            fake = sample_share_for_loss(
                model, cond_g, truth_g,
                torch.randn(args.generator_batch, n_nodes, device=device),
                share_steps=8,
            ).cell_energy
            adversarial = torch.nn.functional.softplus(
                -share_critic(
                    model.encode_condition(cond_g), cell_energy=fake,
                    layer_energy=truth_g.layer_energy, support_mask=truth_g.support_mask,
                    node_features=model.node_features, axis=axis_g,
                    edge_index=model.edge_index, edge_features=model.edge_features,
                    layer_index=model.layer_index, valid_mask=model.valid_mask,
                )
            ).mean()
            adversarial.backward()
            gen_opt.step()
        finally:
            restore_parameters(share_critic, saved)

    # ---- stage 3: the generator update at the TRAINING loop's batch, which the
    # 2026-08-14 preflight never measured -- it used the critic batch for both.
    stages.append(attempt(
        f"d1_generator_through_frozen_critic_batch_{args.generator_batch}",
        generator_update, device,
    ))

    report["stages"] = stages
    blocked = [s for s in stages if s["status"] != "ok"]
    if blocked:
        report["status"] = "RESOURCE_PREFLIGHT_FAIL"
        report["d1_fits_declared_batch"] = False
        report["first_failing_stage"] = blocked[0]["stage"]
        report["decision"] = "D1 is resource_blocked on this device at the declared shapes"
        report["permitted_next_steps"] = [
            "remove accidental tensor retention and duplicate graph copies",
            "reuse static geometry and edge tensors across updates",
            "activation-checkpoint the two message blocks and the 65-token Transformer, "
            "proving fixed-batch logits and losses match within 1e-6 absolute and gradients "
            "within the existing float32 gradient tolerance",
            "preserve R1 computation in stable float32",
        ]
        report["forbidden_next_steps"] = [
            "reducing batch size", "sampling edges", "removing message passing",
            "replacing D1 with a layer-only critic", "shrinking replay",
            "removing R1 or spectral normalization",
            "treating gradient accumulation as equivalent",
        ]
    else:
        report["status"] = "ok"
        report["d1_fits_declared_batch"] = True
        report["probes"] = [
            measure("d1_critic_update", lambda: critic_update(True), device,
                    warmup=args.warmup, measured=args.measured,
                    repeats=args.repeats, batch=args.critic_batch),
            measure("d1_generator_through_frozen_critic", generator_update, device,
                    warmup=args.warmup, measured=args.measured,
                    repeats=args.repeats, batch=args.generator_batch),
        ]
        peaks = [p.get("peak_allocated_gib", 0.0) for p in report["probes"]]
        total = report["probes"][0].get("device_total_gib", 0.0)
        report["d1_peak_allocated_gib"] = max(peaks) if peaks else None
        report["d1_peak_fraction_of_device"] = (
            round(max(peaks) / total, 4) if peaks and total else None
        )

    # ---- gradient isolation: a critic update must not move the generator, and
    # a generator update must not move the critic.
    #
    # This runs only when the declared shapes fit. Attempting it after an OOM
    # would crash the script before it could write the report naming the stage
    # that failed, which is the single most useful thing the run produces.
    if blocked:
        report["gradient_isolation"] = {
            "measured": False,
            "reason": "declared shapes did not fit; isolation is measured only on a "
                      "configuration that can actually run",
        }
        report["nonfinite_guard"] = {"measured": False}
    else:
        if device.type == "cuda":
            torch.cuda.empty_cache()
        try:
            before_gen = [p.detach().clone() for p in model.parameters()]
            critic_update(True)
            generator_moved = any(
                not torch.equal(a, b) for a, b in zip(before_gen, model.parameters())
            )
            del before_gen
            if device.type == "cuda":
                torch.cuda.empty_cache()
            before_critic = [p.detach().clone() for p in share_critic.parameters()]
            generator_update()
            critic_moved = any(
                not torch.equal(a, b) for a, b in zip(before_critic, share_critic.parameters())
            )
            report["gradient_isolation"] = {
                "measured": True,
                "generator_unchanged_by_critic_update": not generator_moved,
                "critic_unchanged_by_generator_update": not critic_moved,
                "pass": (not generator_moved) and (not critic_moved),
            }
            finite = all(
                torch.isfinite(p).all().item()
                for p in list(model.parameters()) + list(share_critic.parameters())
            )
            report["nonfinite_guard"] = {"all_parameters_finite": bool(finite)}
            if not report["gradient_isolation"]["pass"] or not finite:
                report["status"] = "ERROR"
        except torch.cuda.OutOfMemoryError as exc:
            report["gradient_isolation"] = {
                "measured": False,
                "reason": "CUDA out of memory during the isolation check",
                "detail": str(exc)[:300],
            }
            report["nonfinite_guard"] = {"measured": False}
            report["status"] = "RESOURCE_PREFLIGHT_FAIL"
            report["d1_fits_declared_batch"] = False

    report["scientific_status"] = "PHYSICS VALIDATION NOT ESTABLISHED"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
