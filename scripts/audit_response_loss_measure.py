#!/usr/bin/env python
"""Audit the validation-loss measure used by the legacy v2 response head.

The v2 head models ``y = log1p(T / s)`` and historically logged ``-log p(y)``.
The bounded v3 head logs a density in deposited-energy units, ``-log p(T)``.
Those numbers are not comparable until the v2 target-only Jacobian is restored:

    -log p(T) = -log p(y) + log(s + T).

Training averages one scalar per validation batch, so this audit deliberately
reproduces that batch-wise reduction (including an empty-visible batch and the
final partial batch).  It reads the validation split only and records zero test
events used.  The correction is independent of model parameters and therefore
does not alter gradients or the epoch selected within a fixed v2 run.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Iterable

import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from cbsc_zdc.config import load_config  # noqa: E402
from cbsc_zdc.data.dataset import load_geometry  # noqa: E402
from cbsc_zdc.training.trainer import _make_loader  # noqa: E402
from cbsc_zdc.training.truth import derive_truth  # noqa: E402
from cbsc_zdc.utils import sha256_file  # noqa: E402


def batchwise_log_jacobian(
    batches: Iterable[tuple[torch.Tensor, torch.Tensor]],
    response_scale_gev: float,
) -> dict[str, float | int]:
    """Return the trainer-equivalent mean of ``log(scale + visible T)``."""
    scale = float(response_scale_gev)
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError("response_scale_gev must be finite and positive")

    correction_sum = 0.0
    batch_count = 0
    event_count = 0
    visible_count = 0
    empty_visible_batches = 0
    for total, visible in batches:
        if total.ndim != 1 or visible.shape != total.shape:
            raise ValueError("total and visible must be same-shape rank-one tensors")
        if not torch.isfinite(total).all() or bool((total < 0).any()):
            raise ValueError("response totals must be finite and nonnegative")
        mask = visible.bool()
        if bool(mask.any()):
            correction = torch.log(total[mask].to(torch.float32) + scale).mean()
            if not torch.isfinite(correction):
                raise ValueError("nonfinite response Jacobian correction")
            correction_sum += float(correction)
            visible_count += int(mask.sum())
        else:
            empty_visible_batches += 1
        event_count += int(total.numel())
        batch_count += 1

    if batch_count == 0:
        raise ValueError("validation loader produced no batches")
    return {
        "batch_mean_log_jacobian": correction_sum / batch_count,
        "validation_batches": batch_count,
        "validation_events": event_count,
        "visible_validation_events": visible_count,
        "empty_visible_batches": empty_visible_batches,
    }


def audit(config_path: Path) -> dict:
    config = load_config(config_path)
    model = config["model"]
    response_mode = str(model.get("response_mode", "v2"))
    if response_mode != "v2":
        raise ValueError(
            "this correction applies only to response_mode=v2; "
            f"got {response_mode!r}"
        )

    geometry = load_geometry(config["geometry"]["path"], "cpu")
    loader = _make_loader(config, "validation", False)

    def truth_batches():
        with torch.no_grad():
            for batch in loader:
                truth = derive_truth(
                    batch["cell_energy_gev"],
                    geometry["layer_index"],
                    int(config["geometry"]["n_layers"]),
                    float(config["data"].get("threshold_gev", 0.0)),
                )
                yield truth["total"], truth["visible"]

    scale = float(model["response_scale_gev"])
    reduction = batchwise_log_jacobian(truth_batches(), scale)
    weight = float(config["loss_weights"]["response"])
    weighted_offset = weight * float(reduction["batch_mean_log_jacobian"])
    if not math.isfinite(weighted_offset):
        raise ValueError("nonfinite weighted response-measure offset")

    return {
        "schema_version": 1,
        "kind": "cbsc-zdc-response-loss-measure-audit",
        "config": str(config_path),
        "config_sha256": sha256_file(config_path),
        "manifest_sha256": sha256_file(config["data"]["manifest"]),
        "splits_sha256": sha256_file(config["data"]["splits"]),
        "split": "validation",
        "test_events_used": 0,
        "response_mode": response_mode,
        "legacy_reported_measure": "negative log density in y=log1p(T/scale)",
        "common_measure": "negative log density in deposited-energy GeV",
        "identity": "NLL_T = NLL_y + log(response_scale_gev + T)",
        "response_scale_gev": scale,
        "response_loss_weight": weight,
        **reduction,
        "weighted_total_validation_loss_offset": weighted_offset,
        "gradient_effect": "none; correction depends only on frozen targets",
        "within_run_checkpoint_selection_effect": (
            "none; validation set, order, batch size, and target correction are fixed"
        ),
        "pass": True,
        "scientific_status": "PHYSICS VALIDATION NOT ESTABLISHED",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    report = audit(args.config)
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_name(f".{args.output.name}.tmp")
        temporary.write_text(encoded, encoding="utf-8", newline="\n")
        temporary.replace(args.output)
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
