"""Bounded memory, throughput and resume preflight for the v3 critic paths.

This measures feasibility.  It does not authorize a campaign and it trains
nothing that is kept: every run here is a bounded smoke in an isolated
namespace.

Probes, each at production shape (6,790 channels, 65 layers):

1. v3 supervised generator update
2. D1 critic update
3. D1 generator-through-frozen-critic update
4. D2 critic update
5. D2 generator-through-frozen-critic update

If the declared critic batch size 4 does not fit, the path is reported
``RESOURCE_PREFLIGHT_FAIL``.  It is **not** silently reduced -- lowering the
batch, shrinking replay, removing R1 or dropping spectral normalization would
change the declared experiment while appearing to succeed.  Other batch sizes
may be benchmarked as labelled diagnostic evidence only.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path
from typing import Any, Callable

import torch

from cbsc_zdc.models.critics import ProfileCritic, ShareCritic
from cbsc_zdc.models.system import CBSCZDC
from cbsc_zdc.training.adversarial import (
    critic_logistic_loss,
    freeze_parameters,
    generator_direct_loss,
    restore_parameters,
)
from cbsc_zdc.training.stage_sampling import (
    TruthStructure,
    sample_profile_for_loss,
    sample_share_for_loss,
)

N_NODES = 6790
N_LAYERS = 65
ECAL_CHANNELS = 400
COND_DIM = 128
NEUTRON_MASS_GEV = 0.93956542052


def production_geometry(device: torch.device) -> dict[str, torch.Tensor]:
    """Production-shaped geometry: 400 ECAL + 6,390 HCAL over 65 layers.

    Node and edge *features* are synthetic; the shapes, layer partition and
    edge count are what drive memory and time.
    """
    hcal_per_layer = (N_NODES - ECAL_CHANNELS) // (N_LAYERS - 1)
    layer_index = torch.cat(
        [torch.zeros(ECAL_CHANNELS, dtype=torch.long)]
        + [torch.full((hcal_per_layer,), i, dtype=torch.long) for i in range(1, N_LAYERS)]
    )
    remainder = N_NODES - layer_index.numel()
    if remainder > 0:
        layer_index = torch.cat([layer_index, torch.full((remainder,), N_LAYERS - 1, dtype=torch.long)])
    layer_index = layer_index[:N_NODES]

    # A k-nearest-style intra-layer ring keeps the edge count realistic without
    # materializing a dense within-layer graph.
    src, dst = [], []
    for layer in range(N_LAYERS):
        ids = torch.nonzero(layer_index == layer).flatten().tolist()
        for offset in (1, 2, 3):
            for i, node in enumerate(ids):
                neighbour = ids[(i + offset) % len(ids)]
                src.append(node)
                dst.append(neighbour)
                src.append(neighbour)
                dst.append(node)
    edge_index = torch.tensor([src, dst], dtype=torch.long)
    return {
        "node_features": torch.randn(N_NODES, 8),
        "layer_index": layer_index,
        "valid_mask": torch.ones(N_NODES, dtype=torch.bool),
        "edge_index": edge_index,
        "edge_features": torch.randn(edge_index.shape[1], 4),
    }


def build_model(geometry: dict[str, torch.Tensor], device: torch.device) -> CBSCZDC:
    config = {
        "model": {
            "condition_dim": COND_DIM, "hidden_dim": 96, "graph_blocks": 3,
            "attention_heads": 4, "attention_layers": 2, "profile_hidden": 128,
            "count_hidden": 192, "response_hidden": 192,
        },
        "data": {"target_mode": "raw_deposit", "threshold_gev": 0.0},
    }
    return CBSCZDC({k: v.to(device) for k, v in geometry.items()}, config).to(device)


def p4(batch: int, device: torch.device, energy: float = 150.0) -> torch.Tensor:
    total = torch.full((batch,), energy, dtype=torch.float64)
    momentum = torch.sqrt(total.square() - NEUTRON_MASS_GEV**2)
    return torch.stack(
        [total, torch.zeros_like(total), torch.zeros_like(total), momentum], dim=1
    ).float().to(device)


def make_truth(batch: int, model: CBSCZDC, device: torch.device) -> TruthStructure:
    counts = torch.zeros(batch, N_LAYERS, dtype=torch.long, device=device)
    support = torch.zeros(batch, N_NODES, dtype=torch.bool, device=device)
    for layer in range(N_LAYERS):
        ids = torch.nonzero(model.layer_index == layer).flatten()
        take = max(1, min(int(ids.numel()) // 4, 24))
        counts[:, layer] = take
        support[:, ids[:take]] = True
    return TruthStructure(
        visible=torch.ones(batch, dtype=torch.bool, device=device),
        total_response=torch.full((batch,), 60.0, device=device),
        first_layer=torch.zeros(batch, dtype=torch.long, device=device),
        active_layers=torch.ones(batch, N_LAYERS, dtype=torch.bool, device=device),
        layer_energy=torch.full((batch, N_LAYERS), 60.0 / N_LAYERS, device=device),
        requested_counts=counts,
        support_mask=support,
    )


def measure(name: str, step: Callable[[], None], device: torch.device, *, warmup: int, measured: int) -> dict[str, Any]:
    """Run ``warmup`` then ``measured`` synchronized steps, reporting peak memory."""
    if device.type == "cuda":
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats(device)
        free_before, total = torch.cuda.mem_get_info(device)
    else:
        free_before = total = 0
    try:
        for _ in range(warmup):
            step()
        if device.type == "cuda":
            torch.cuda.synchronize(device)
        start = time.perf_counter()
        for _ in range(measured):
            step()
        if device.type == "cuda":
            torch.cuda.synchronize(device)
        elapsed = time.perf_counter() - start
    except torch.cuda.OutOfMemoryError as exc:  # pragma: no cover - hardware dependent
        return {
            "probe": name, "status": "RESOURCE_PREFLIGHT_FAIL", "reason": "CUDA out of memory",
            "detail": str(exc)[:300],
            "note": "batch size, replay capacity, R1 and spectral norm are declared; "
                    "they are not reduced to obtain a pass",
        }
    except Exception as exc:  # noqa: BLE001
        return {"probe": name, "status": "ERROR", "detail": f"{type(exc).__name__}: {exc}"[:300]}

    result = {
        "probe": name,
        "status": "ok",
        "updates_measured": measured,
        "warmup_updates": warmup,
        "seconds_total": elapsed,
        "seconds_per_update": elapsed / measured,
        "updates_per_second": measured / elapsed,
    }
    if device.type == "cuda":
        free_after, _ = torch.cuda.mem_get_info(device)
        result.update({
            "peak_allocated_gib": torch.cuda.max_memory_allocated(device) / 1024**3,
            "peak_reserved_gib": torch.cuda.max_memory_reserved(device) / 1024**3,
            "device_total_gib": total / 1024**3,
            "device_free_before_gib": free_before / 1024**3,
            "device_free_after_gib": free_after / 1024**3,
        })
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--generator-batch", type=int, default=6)
    parser.add_argument("--critic-batch", type=int, default=4)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--measured", type=int, default=100)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output", type=Path, default=Path("audit/v3_resource_preflight_20260814.json"))
    args = parser.parse_args()

    device = torch.device(args.device if torch.cuda.is_available() or args.device == "cpu" else "cpu")
    torch.manual_seed(20260814)
    geometry = production_geometry(device)
    model = build_model(geometry, device)
    gb, cb = args.generator_batch, args.critic_batch

    truth = make_truth(cb, model, device)
    cond_p4 = p4(cb, device)
    axis = torch.randn(cb, N_NODES, 4, device=device)

    share_critic = ShareCritic(
        geometry["node_features"].shape[1], geometry["edge_features"].shape[1],
        COND_DIM, N_LAYERS, 4, hidden=96, blocks=2, heads=4, context_layers=2, embed_dim=128,
    ).to(device)
    profile_critic = ProfileCritic(COND_DIM, N_LAYERS, 128, 4, 2, 128).to(device)
    gen_opt = torch.optim.Adam(model.parameters(), lr=1e-4)
    share_opt = torch.optim.Adam(share_critic.parameters(), lr=1e-4, betas=(0.0, 0.99))
    profile_opt = torch.optim.Adam(profile_critic.parameters(), lr=1e-4, betas=(0.0, 0.99))

    def share_score(cell):
        return share_critic(
            model.encode_condition(cond_p4), cell_energy=cell, layer_energy=truth.layer_energy,
            support_mask=truth.support_mask, node_features=model.node_features, axis=axis,
            edge_index=model.edge_index, edge_features=model.edge_features,
            layer_index=model.layer_index, valid_mask=model.valid_mask,
        )

    def profile_score(layer_energy):
        return profile_critic(
            model.encode_condition(cond_p4), layer_energy, truth.total_response, truth.active_layers
        )

    def supervised_step():
        out = sample_profile_for_loss(
            model, cond_p4, truth.total_response, truth.active_layers,
            torch.randn(cb, N_LAYERS, device=device), profile_steps=8,
        )
        gen_opt.zero_grad(set_to_none=True)
        out.layer_energy.square().sum().backward()
        gen_opt.step()

    def d1_critic_step():
        fake = sample_share_for_loss(
            model, cond_p4, truth, torch.randn(cb, N_NODES, device=device), share_steps=8
        )
        share_opt.zero_grad(set_to_none=True)
        critic_logistic_loss(
            share_score(torch.rand(cb, N_NODES, device=device).abs()),
            share_score(fake.cell_energy.detach()),
        ).backward()
        share_opt.step()

    def d1_generator_step():
        previous = freeze_parameters(share_critic)
        fake = sample_share_for_loss(
            model, cond_p4, truth, torch.randn(cb, N_NODES, device=device), share_steps=8
        )
        gen_opt.zero_grad(set_to_none=True)
        generator_direct_loss(share_score(fake.cell_energy)).backward()
        gen_opt.step()
        restore_parameters(share_critic, previous)

    def d2_critic_step():
        out = sample_profile_for_loss(
            model, cond_p4, truth.total_response, truth.active_layers,
            torch.randn(cb, N_LAYERS, device=device), profile_steps=8,
        )
        profile_opt.zero_grad(set_to_none=True)
        critic_logistic_loss(
            profile_score(torch.rand(cb, N_LAYERS, device=device)),
            profile_score(out.layer_energy.detach()),
        ).backward()
        profile_opt.step()

    def d2_generator_step():
        previous = freeze_parameters(profile_critic)
        out = sample_profile_for_loss(
            model, cond_p4, truth.total_response, truth.active_layers,
            torch.randn(cb, N_LAYERS, device=device), profile_steps=8,
        )
        gen_opt.zero_grad(set_to_none=True)
        generator_direct_loss(profile_score(out.layer_energy)).backward()
        gen_opt.step()
        restore_parameters(profile_critic, previous)

    probes = [
        ("v3_supervised_generator", supervised_step),
        ("d1_critic_update", d1_critic_step),
        ("d1_generator_through_frozen_critic", d1_generator_step),
        ("d2_critic_update", d2_critic_step),
        ("d2_generator_through_frozen_critic", d2_generator_step),
    ]

    results = []
    for name, step in probes:
        repeats = []
        for _ in range(args.repeats):
            repeats.append(measure(name, step, device, warmup=args.warmup, measured=args.measured))
            if repeats[-1]["status"] != "ok":
                break
        ok = [r for r in repeats if r["status"] == "ok"]
        if not ok:
            results.append(repeats[-1])
            continue
        per_update = [r["seconds_per_update"] for r in ok]
        results.append({
            "probe": name,
            "status": "ok",
            "repeats": len(ok),
            "seconds_per_update_median": statistics.median(per_update),
            "seconds_per_update_min": min(per_update),
            "seconds_per_update_max": max(per_update),
            "peak_allocated_gib": max(r.get("peak_allocated_gib", 0.0) for r in ok),
            "peak_reserved_gib": max(r.get("peak_reserved_gib", 0.0) for r in ok),
            "device_total_gib": ok[0].get("device_total_gib"),
            "updates_measured_each": args.measured,
            "warmup_updates": args.warmup,
        })

    payload = {
        "schema_version": 1,
        "kind": "cbsc-zdc-v3-resource-preflight",
        "device": str(device),
        "device_name": torch.cuda.get_device_name(device) if device.type == "cuda" else "cpu",
        "torch": torch.__version__,
        "generator_batch": gb,
        "critic_batch": cb,
        "channels": N_NODES,
        "layers": N_LAYERS,
        "edges": int(geometry["edge_index"].shape[1]),
        "probes": results,
        "authorization": "measurement only; this does not authorize a training campaign",
        "declared_values_not_adjusted": [
            "critic batch size 4", "replay capacity 65536", "R1 gamma 1.0",
            "spectral normalization", "65 detector layers",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
