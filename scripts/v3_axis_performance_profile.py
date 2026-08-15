"""Attribute the axis-feature epoch-cost overhead on the production graph.

S1-axis measured **1735.8 s/epoch** against the v2.2 rate of **779.6 s/epoch** --
a factor of **2.23**.  Four static node columns causing that is suspicious
enough to attribute before it is accepted as an unavoidable trade-off.

Reading the code first rules out the obvious cause: `CBSCZDC.axis_for` is
already hoisted.  `sample()` computes it once per batch *before* the share-flow
loop and passes the same tensor into every solver step, and the trainer computes
it once per loss evaluation.  Nothing recomputes it per step, per loss
component, or per message block.

What remains is the widened input projection: the axis block is concatenated
into the node-field input, taking it from roughly 136 to 140 columns.  That is a
~3% change on one Linear, which cannot arithmetically produce 2.23x.  This
script measures each component at production shape so the discrepancy is
attributed rather than guessed at.

Measurement only. It trains nothing and writes no checkpoint.
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
from cbsc_zdc.models.system import CBSCZDC

NEUTRON_MASS_GEV = 0.93956542052


def p4(batch: int, device: torch.device, energy: float = 150.0) -> torch.Tensor:
    total = torch.full((batch,), energy, dtype=torch.float64)
    momentum = torch.sqrt(total.square() - NEUTRON_MASS_GEV**2)
    return torch.stack(
        [total, torch.zeros_like(total), torch.zeros_like(total), momentum], dim=1
    ).float().to(device)


def timed(name: str, step: Callable[[], Any], device: torch.device,
          warmup: int, measured: int) -> dict[str, Any]:
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
    except torch.cuda.OutOfMemoryError as exc:
        return {"component": name, "status": "OOM", "detail": str(exc)[:200]}
    except Exception as exc:  # noqa: BLE001
        return {"component": name, "status": "ERROR",
                "detail": f"{type(exc).__name__}: {exc}"[:250]}
    return {
        "component": name, "status": "ok",
        "seconds_per_call": elapsed / measured,
        "calls": measured,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--geometry", type=Path, required=True)
    parser.add_argument("--frozen-config", type=Path, required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--batch", type=int, default=6)
    parser.add_argument("--share-steps", type=int, default=8)
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--measured", type=int, default=20)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    device = torch.device(args.device)
    torch.manual_seed(20260815)
    base = yaml.safe_load(args.frozen_config.read_text(encoding="utf-8"))
    geometry = load_geometry(str(args.geometry), device)
    n_nodes = int(geometry["layer_index"].numel())
    n_edges = int(geometry["edge_index"].shape[1])

    manifest_vertex = base.get("model", {}).get("generator_vertex_mm")
    if manifest_vertex is None:
        manifest_vertex = [-917.4075317382812, -30.0, 35488.90625]

    def build(axis_on: bool) -> CBSCZDC:
        config = json.loads(json.dumps(base))
        model_cfg = config.setdefault("model", {})
        if axis_on:
            model_cfg["architecture_version"] = "cbsc-zdc-v3"
            model_cfg["axis_features"] = True
            model_cfg["generator_vertex_mm"] = manifest_vertex
        else:
            model_cfg.pop("axis_features", None)
            model_cfg.pop("architecture_version", None)
        return CBSCZDC(geometry, config).to(device).eval()

    results: dict[str, Any] = {
        "schema_version": 1,
        "kind": "cbsc-zdc-v3-axis-performance-profile",
        "recorded_at": "2026-08-15",
        "device": args.device,
        "device_name": torch.cuda.get_device_name(device) if device.type == "cuda" else "cpu",
        "torch": torch.__version__,
        "graph": {"nodes": n_nodes, "edges": n_edges},
        "batch": args.batch,
        "share_steps": args.share_steps,
        "reported_epoch_rates": {
            "v2_2_seconds_per_epoch": 779.6,
            "s1_axis_seconds_per_epoch": 1735.8,
            "observed_factor": 2.2265,
        },
        "code_findings": {
            "axis_computed_once_per_batch": True,
            "axis_recomputed_per_solver_step": False,
            "axis_recomputed_per_loss_component": False,
            "axis_recomputed_per_message_block": False,
            "call_sites": [
                "models/system.py sample(): once, before the share-flow loop",
                "training/trainer.py compute_component_losses(): once per evaluation",
            ],
            "note": "the hoist the profile would have recommended is already in place",
        },
        "components": [],
    }

    for axis_on in (False, True):
        model = build(axis_on)
        cond_p4 = p4(args.batch, device)
        label = "with_axis" if axis_on else "without_axis"

        with torch.no_grad():
            cond = model.encode_condition(cond_p4)
        axis = model.axis_for(cond_p4) if axis_on else None

        def axis_construction():
            with torch.no_grad():
                model.axis_for(cond_p4)

        layer_energy = torch.full((args.batch, model.n_layers), 1.0, device=device)
        counts = torch.full((args.batch, model.n_layers), 8, dtype=torch.long, device=device)

        def support_call():
            with torch.no_grad():
                model.support_logits(cond, layer_energy, counts, axis=axis)

        support_mask = torch.zeros(args.batch, n_nodes, dtype=torch.bool, device=device)
        support_mask[:, ::8] = True
        state = torch.randn(args.batch, n_nodes, device=device) * support_mask
        t = torch.full((args.batch, 1), 0.5, device=device)

        def share_call():
            with torch.no_grad():
                model.share_velocity(
                    state, t, cond, layer_energy, counts, support_mask, axis=axis
                )

        def full_sample():
            with torch.no_grad():
                model.sample(cond_p4, 8, args.share_steps, 20260815, True)

        if axis_on:
            results["components"].append(
                {**timed("axis_construction", axis_construction, device,
                         args.warmup, args.measured), "variant": label}
            )
        for name, fn in (
            ("support_field_forward", support_call),
            ("share_field_forward", share_call),
            ("full_sample", full_sample),
        ):
            results["components"].append(
                {**timed(name, fn, device, args.warmup, max(3, args.measured // 4)
                         if name == "full_sample" else args.measured),
                 "variant": label}
            )
        del model
        if device.type == "cuda":
            torch.cuda.empty_cache()

    # Attribute: ratio per component between the two variants.
    def find(name: str, variant: str):
        for row in results["components"]:
            if row.get("component") == name and row.get("variant") == variant:
                return row.get("seconds_per_call")
        return None

    ratios = {}
    for name in ("support_field_forward", "share_field_forward", "full_sample"):
        off, on = find(name, "without_axis"), find(name, "with_axis")
        if off and on:
            ratios[name] = round(on / off, 4)
    results["axis_overhead_ratio_by_component"] = ratios
    results["attribution"] = {
        "explains_the_2_23x_epoch_factor": (
            bool(ratios.get("full_sample", 0) >= 1.8)
            if "full_sample" in ratios else None
        ),
        "reading": (
            "A full_sample ratio near 2.2 attributes the epoch cost to the forward "
            "path and makes the 2.23x an inherent cost of the feature at this graph "
            "size. A ratio near 1.0 means the epoch-rate difference came from "
            "somewhere other than the axis arithmetic, and the 1735.8 s/epoch figure "
            "must not be attributed to the feature."
        ),
    }
    results["scientific_status"] = "PHYSICS VALIDATION NOT ESTABLISHED"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(results, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
