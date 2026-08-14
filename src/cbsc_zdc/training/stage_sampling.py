"""Differentiable stage samplers for adversarial training.

The production sampler ``CBSCZDC.sample`` is ``@torch.no_grad()`` and contains
Bernoulli draws, a categorical, a sort and a Boolean top-k.  A critic attached
to its output cannot supply ordinary end-to-end generator gradients, and simply
deleting the ``no_grad`` decorator would not help: the discrete operations have
zero or undefined gradient regardless.

The fix is not to relax the discrete operations but to **avoid crossing them**.
Each stage sampler truth-forces every discrete variable and generates only one
continuous stage:

``sample_share_for_loss``
    truth-forces ``V, T, f, A, D, k, S`` and integrates only the share flow, so
    gradients reach the share field alone.

``sample_profile_for_loss``
    truth-forces ``V, T, A`` and integrates only the profile flow, so gradients
    reach the profile field alone.

Both take their source noise explicitly.  That makes a run reproducible across
resume and lets a gradient test hold the noise fixed while varying parameters.

Neither may call ``sample_exact()``.  The exact sampler keeps its ``no_grad``
decorator and its structural semantics untouched.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch

from ..models.support import decode_exact_support


@dataclass
class DifferentiableShareOutput:
    cell_energy: torch.Tensor
    share_state: torch.Tensor
    support_mask: torch.Tensor
    layer_energy: torch.Tensor


@dataclass
class DifferentiableProfileOutput:
    layer_energy: torch.Tensor
    profile_state: torch.Tensor
    active_layers: torch.Tensor


@dataclass
class TruthStructure:
    """Discrete structure taken from truth, never generated, never differentiated."""

    visible: torch.Tensor
    total_response: torch.Tensor
    first_layer: torch.Tensor
    active_layers: torch.Tensor
    layer_energy: torch.Tensor
    requested_counts: torch.Tensor
    support_mask: torch.Tensor


def _assert_no_grad(name: str, tensor: torch.Tensor) -> None:
    if tensor is not None and tensor.requires_grad:
        raise ValueError(
            f"{name} is truth-forced structure and must not require grad; "
            "a gradient here would flow into a discrete variable"
        )


def sample_share_for_loss(
    model,
    p4_total_gev: torch.Tensor,
    truth: TruthStructure,
    share_noise: torch.Tensor,
    share_steps: int = 8,
) -> DifferentiableShareOutput:
    """Integrate the share flow on a truth-forced support.

    Gradients flow to the share field only.  ``share_noise`` is the explicit
    source noise, shaped like the support logits.
    """
    for name in ("visible", "total_response", "first_layer", "active_layers",
                 "layer_energy", "requested_counts", "support_mask"):
        _assert_no_grad(f"truth.{name}", getattr(truth, name))

    cond = model.encode_condition(p4_total_gev)
    support_mask = truth.support_mask
    mask_dtype = support_mask.to(cond.dtype)
    # The support logits are needed by the decoder for ordering only; the mask
    # itself is preselected from truth so no top-k is crossed.
    with torch.no_grad():
        support_logits = model.support_logits(cond, truth.layer_energy, truth.requested_counts)

    state = share_noise.to(cond.dtype) * mask_dtype
    dt = 1.0 / share_steps
    for step in range(share_steps):
        t = torch.full(
            (cond.shape[0], 1), (step + 0.5) / share_steps, device=cond.device, dtype=cond.dtype
        )
        velocity = model.share_velocity(
            state, t, cond, truth.layer_energy, truth.requested_counts, support_mask
        )
        state = (state + dt * velocity) * mask_dtype

    decoded = decode_exact_support(
        support_logits,
        state,
        truth.layer_energy,
        truth.requested_counts,
        model.layer_index,
        model.valid_mask,
        model.threshold_gev,
        False,
        preselected_support_mask=support_mask,
    )
    return DifferentiableShareOutput(
        decoded.cell_energy, state, decoded.support_mask, truth.layer_energy
    )


def sample_profile_for_loss(
    model,
    p4_total_gev: torch.Tensor,
    truth_total: torch.Tensor,
    truth_active: torch.Tensor,
    profile_noise: torch.Tensor,
    profile_steps: int = 8,
) -> DifferentiableProfileOutput:
    """Integrate the profile flow on truth-forced activity.

    Gradients flow to the profile field only.
    """
    _assert_no_grad("truth_total", truth_total)
    _assert_no_grad("truth_active", truth_active)

    cond = model.encode_condition(p4_total_gev)
    active = truth_active.bool()
    active_dtype = active.to(cond.dtype)
    state = profile_noise.to(cond.dtype) * active_dtype
    dt = 1.0 / profile_steps
    for step in range(profile_steps):
        t = torch.full(
            (cond.shape[0], 1), (step + 0.5) / profile_steps, device=cond.device, dtype=cond.dtype
        )
        state = (state + dt * model.profile.flow(state, t, cond, truth_total, active)) * active_dtype

    # Masked softmax over active layers, then scale to the truth total.  The
    # masked-fill uses finfo.min rather than -inf so an all-inactive row cannot
    # produce NaN.
    masked = state.masked_fill(~active, torch.finfo(state.dtype).min)
    weights = torch.softmax(masked, dim=-1)
    weights = weights * active_dtype
    denominator = weights.sum(dim=-1, keepdim=True).clamp_min(torch.finfo(state.dtype).tiny)
    layer_energy = (weights / denominator) * truth_total[:, None].to(cond.dtype)
    layer_energy = layer_energy * active_dtype
    return DifferentiableProfileOutput(layer_energy, state, active)
