from __future__ import annotations

from dataclasses import dataclass

import torch


@dataclass
class DecodeOutput:
    cell_energy: torch.Tensor
    resolved_layer_energy: torch.Tensor
    subthreshold_residual: torch.Tensor
    realized_counts: torch.Tensor
    support_mask: torch.Tensor


def _sample_gumbel_like(x: torch.Tensor, eps: float = 1e-8) -> torch.Tensor:
    u = torch.rand_like(x).clamp_(eps, 1.0 - eps)
    return -torch.log(-torch.log(u))


def gumbel_topk_mask(
    logits: torch.Tensor,
    k: int,
    stochastic: bool = True,
) -> torch.Tensor:
    """Return an exact k-hot mask for one score vector."""
    if logits.ndim != 1:
        raise ValueError("gumbel_topk_mask expects a one-dimensional score vector")
    if k < 0 or k > logits.numel():
        raise ValueError("k is outside the available support")
    mask = torch.zeros_like(logits, dtype=torch.bool)
    if k == 0:
        return mask
    scores = logits + _sample_gumbel_like(logits) if stochastic else logits
    selected = torch.topk(scores, k=k).indices
    mask[selected] = True
    return mask


def _batched_exact_k_mask(
    logits: torch.Tensor,
    k: torch.Tensor,
    stochastic: bool,
) -> torch.Tensor:
    """Vectorized exact-k support selection for a batch of score vectors."""
    if logits.ndim != 2 or k.ndim != 1 or logits.shape[0] != k.shape[0]:
        raise ValueError("batched top-k shape mismatch")
    if (k < 0).any() or (k > logits.shape[1]).any():
        raise ValueError("batched top-k request is infeasible")
    scores = logits + _sample_gumbel_like(logits) if stochastic else logits
    order = torch.argsort(scores, dim=1, descending=True)
    rank_selected = torch.arange(logits.shape[1], device=logits.device)[None, :] < k[:, None]
    mask = torch.zeros_like(logits, dtype=torch.bool)
    mask.scatter_(1, order, rank_selected)
    return mask


def threshold_safe_layer_decoder(
    support_logits: torch.Tensor,
    share_logits: torch.Tensor,
    layer_budget: torch.Tensor,
    requested_counts: torch.Tensor,
    layer_index: torch.Tensor,
    valid_mask: torch.Tensor,
    threshold_gev: float = 0.0,
    stochastic_support: bool = True,
) -> DecodeOutput:
    """Decode exact sparse cell energies without low-energy dust.

    For each layer with budget B and realized count K, selected cells obey

        e_i = tau + (B - K*tau) * softmax(r)_i,

    and every unselected cell is exactly zero. If B < tau, no above-threshold
    cell is possible; B is retained as a layer-level subthreshold residual.

    The hard support operation is intended for sampling and evaluation. During
    training, support logits require a supervised or relaxed discrete objective;
    this decoder alone does not provide gradients through the selected indices.
    """
    if threshold_gev < 0:
        raise ValueError("threshold_gev must be nonnegative")
    if support_logits.ndim != 2:
        raise ValueError("support_logits must have shape [batch,nodes]")
    batch, n_nodes = support_logits.shape
    if share_logits.shape != (batch, n_nodes):
        raise ValueError("share_logits shape mismatch")
    if layer_index.shape != (n_nodes,) or valid_mask.shape != (n_nodes,):
        raise ValueError("layer_index and valid_mask must have shape [nodes]")
    if layer_budget.shape != requested_counts.shape:
        raise ValueError("layer_budget and requested_counts must have the same shape")

    n_layers = layer_budget.shape[1]
    cell = torch.zeros_like(share_logits)
    support = torch.zeros_like(support_logits, dtype=torch.bool)
    resolved = torch.zeros_like(layer_budget)
    residual = torch.zeros_like(layer_budget)
    realized_counts = torch.zeros_like(requested_counts)

    for layer in range(n_layers):
        ids = torch.where((layer_index == layer) & valid_mask)[0]
        budget = layer_budget[:, layer]
        requested = requested_counts[:, layer].long().clamp_min(0)
        if ids.numel() == 0:
            residual[:, layer] = budget
            continue

        if threshold_gev > 0:
            feasible_by_budget = torch.floor(budget / threshold_gev).long()
        else:
            feasible_by_budget = torch.where(
                budget > 0,
                torch.full_like(requested, ids.numel()),
                torch.zeros_like(requested),
            )
        k = torch.minimum(requested, feasible_by_budget)
        k = torch.minimum(k, torch.full_like(k, ids.numel())).clamp_min(0)

        local_support = _batched_exact_k_mask(
            support_logits[:, ids], k, stochastic=stochastic_support
        )
        support[:, ids] = local_support
        realized_counts[:, layer] = k

        selected_share_logits = share_logits[:, ids]
        # Stable masked softmax that remains exactly zero when k=0.
        selected_for_max = torch.where(
            local_support, selected_share_logits, torch.zeros_like(selected_share_logits)
        )
        row_max = selected_for_max.max(dim=1, keepdim=True).values
        exponent = torch.exp(
            torch.where(
                local_support,
                selected_share_logits - row_max,
                torch.full_like(selected_share_logits, -torch.inf),
            )
        )
        shares = exponent / exponent.sum(dim=1, keepdim=True).clamp_min(1e-30)

        base = threshold_gev * k.to(budget.dtype)
        allocatable = (budget - base).clamp_min(0.0)
        values = local_support.to(budget.dtype) * (
            threshold_gev + allocatable[:, None] * shares
        )
        cell[:, ids] = values
        resolved[:, layer] = values.sum(dim=1)
        residual[:, layer] = budget - resolved[:, layer]

    return DecodeOutput(
        cell_energy=cell,
        resolved_layer_energy=resolved,
        subthreshold_residual=residual,
        realized_counts=realized_counts,
        support_mask=support,
    )
