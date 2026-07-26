from __future__ import annotations

from dataclasses import dataclass

import torch

NEUTRON_MASS_GEV = 0.93956542052


@dataclass(frozen=True)
class DetectorSpec:
    n_layers: int = 65
    n_nodes: int = 6790
    n_ecal: int = 400
    n_hcal: int = 6390


def validate_p4(p4: torch.Tensor, rtol_energy: float = 1e-5) -> None:
    """Validate a neutron four-vector using a numerically stable mass-shell test.

    Directly subtracting ``E**2 - |p|**2`` is ill-conditioned for 50--300 GeV
    float32 inputs because two large nearly equal numbers are subtracted.  The
    implementation therefore compares ``E`` with ``sqrt(|p|**2 + m_n**2)`` in
    float64.  A signed mass-squared residual can still be reported separately for QA.
    """
    if p4.ndim != 2 or p4.shape[-1] != 4:
        raise ValueError(f"p4 must have shape [B,4], got {tuple(p4.shape)}")
    if not torch.is_floating_point(p4):
        raise ValueError("p4 must use a floating-point dtype")
    if not torch.isfinite(p4).all():
        raise ValueError("p4 contains NaN/Inf")
    p4_64 = p4.to(torch.float64)
    e = p4_64[:, 0]
    momentum = p4_64[:, 1:]
    if (e <= 0).any():
        raise ValueError("incident energy must be positive")
    expected_e = torch.sqrt(momentum.square().sum(dim=-1) + NEUTRON_MASS_GEV**2)
    relative_energy_residual = (e - expected_e).abs() / e.clamp_min(1e-12)
    if (relative_energy_residual > rtol_energy).any():
        raise ValueError(
            "neutron mass-shell energy residual exceeds tolerance: "
            f"{relative_energy_residual.max().item():.3e}"
        )


def mass_shell_diagnostics(p4: torch.Tensor) -> dict[str, torch.Tensor]:
    """Return stable and conventional neutron mass-shell diagnostics."""
    if p4.ndim != 2 or p4.shape[-1] != 4:
        raise ValueError(f"p4 must have shape [B,4], got {tuple(p4.shape)}")
    p4_64 = p4.to(torch.float64)
    e = p4_64[:, 0]
    momentum2 = p4_64[:, 1:].square().sum(dim=-1)
    expected_e = torch.sqrt(momentum2 + NEUTRON_MASS_GEV**2)
    return {
        "relative_energy_residual": (e - expected_e).abs() / e.clamp_min(1e-12),
        "mass_squared_residual_gev2": e.square() - momentum2 - NEUTRON_MASS_GEV**2,
    }
