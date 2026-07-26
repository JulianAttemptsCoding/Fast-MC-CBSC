from __future__ import annotations

import torch

from .contracts import kinetic_energy_from_p4, validate_p4_total


def p4_condition_features(
    p4_total_gev: torch.Tensor,
    kinetic_scale_gev: float = 100.0,
) -> torch.Tensor:
    """Return deterministic condition features.

    Output columns are [log1p(K_inc / scale), ux, uy, uz, log(E_total / 1 GeV)].
    K_inc is kinetic energy; E_total is the time component of the four-vector.
    """
    if kinetic_scale_gev <= 0:
        raise ValueError("kinetic_scale_gev must be positive")
    validate_p4_total(p4_total_gev)
    p4 = p4_total_gev.to(torch.float32)
    momentum = p4[:, 1:]
    norm = momentum.norm(dim=-1, keepdim=True).clamp_min(1e-12)
    direction = momentum / norm
    kinetic = kinetic_energy_from_p4(p4_total_gev).to(p4.dtype)
    log_kinetic = torch.log1p(kinetic / kinetic_scale_gev).unsqueeze(-1)
    log_total = torch.log(p4[:, :1].clamp_min(1e-12))
    return torch.cat((log_kinetic, direction, log_total), dim=-1)
