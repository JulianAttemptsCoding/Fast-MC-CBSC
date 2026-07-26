from __future__ import annotations

import torch

from .contracts import validate_p4


def p4_features(p4: torch.Tensor, energy_scale_gev: float = 1.0) -> torch.Tensor:
    """Return the minimal deterministic condition ``[log(E/E0), ux, uy, uz]``."""
    if energy_scale_gev <= 0:
        raise ValueError("energy_scale_gev must be positive")
    validate_p4(p4)
    e, px, py, pz = p4.unbind(-1)
    momentum = torch.sqrt(px.square() + py.square() + pz.square()).clamp_min(1e-12)
    direction = torch.stack((px / momentum, py / momentum, pz / momentum), dim=-1)
    log_energy = torch.log(e / energy_scale_gev).unsqueeze(-1)
    return torch.cat((log_energy, direction), dim=-1)
