from __future__ import annotations

import torch


def invariant_report(
    p4: torch.Tensor,
    out,
    threshold_gev: float = 0.0,
    layer_index: torch.Tensor | None = None,
    atol: float = 1e-5,
) -> dict[str, float | int]:
    cell = out.cell_energy
    positive = cell > 0
    dust = (
        positive & (cell < threshold_gev)
        if threshold_gev > 0
        else torch.zeros_like(positive)
    )
    modeled_accounting = (
        cell.sum(dim=-1, keepdim=True)
        + out.subthreshold_residual.sum(dim=-1, keepdim=True)
        + out.reserve
    )
    report: dict[str, float | int] = {
        "nonfinite": int((~torch.isfinite(cell)).sum().item()),
        "negative": int((cell < 0).sum().item()),
        "dust_cells": int(dust.sum().item()),
        "total_over_incident": int(
            (out.total.squeeze(-1) > p4[:, 0] + atol).sum().item()
        ),
        "accounting_identity_max": float(
            (modeled_accounting - out.total).abs().max().item()
        ),
        "support_count_mismatch_max": float(
            (
                out.support_mask.sum(dim=-1)
                - out.realized_counts.sum(dim=-1)
            )
            .abs()
            .max()
            .item()
        ),
    }
    if layer_index is not None:
        n_layers = out.layer_energy.shape[1]
        cell_by_layer = torch.zeros_like(out.layer_energy)
        cell_by_layer.scatter_add_(
            1,
            layer_index[None].expand(cell.shape[0], -1),
            cell,
        )
        resolved_target = out.layer_energy - out.subthreshold_residual
        report["resolved_layer_mismatch_max"] = float(
            (cell_by_layer - resolved_target).abs().max().item()
        )
    return report
