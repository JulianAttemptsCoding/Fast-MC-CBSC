from __future__ import annotations

import torch


def linear_flow_matching_batch(
    target: torch.Tensor,
    condition: torch.Tensor | None = None,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Construct a straight-line conditional flow-matching training tuple.

    x_0 ~ N(0, I), t ~ U(0, 1), x_t = (1-t)x_0 + t x_1,
    and the target velocity is u_t = x_1 - x_0.
    """
    del condition  # condition is consumed by the caller's vector field
    source = torch.randn_like(target)
    t_shape = (target.shape[0],) + (1,) * (target.ndim - 1)
    t = torch.rand(t_shape, device=target.device, dtype=target.dtype)
    x_t = (1.0 - t) * source + t * target
    velocity_target = target - source
    return x_t, t, velocity_target


def flow_matching_mse(
    predicted_velocity: torch.Tensor,
    target_velocity: torch.Tensor,
    mask: torch.Tensor | None = None,
) -> torch.Tensor:
    error = (predicted_velocity - target_velocity).square()
    if mask is not None:
        while mask.ndim < error.ndim:
            mask = mask.unsqueeze(-1)
        error = error * mask
        denominator = mask.expand_as(error).sum().clamp_min(1)
        return error.sum() / denominator
    return error.mean()
