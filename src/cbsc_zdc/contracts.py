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

    @property
    def expected_layer_counts(self) -> tuple[int, ...]:
        return (400, *([100] * 63), 90)


def total_energy_from_momentum(momentum_gev: torch.Tensor, mass_gev: float = NEUTRON_MASS_GEV) -> torch.Tensor:
    return torch.sqrt(momentum_gev.to(torch.float64).square().sum(dim=-1) + mass_gev**2)


def kinetic_energy_from_p4(p4_total_gev: torch.Tensor, mass_gev: float = NEUTRON_MASS_GEV) -> torch.Tensor:
    if p4_total_gev.shape[-1] != 4:
        raise ValueError("p4_total_gev must end in four components [E_total,px,py,pz]")
    return (p4_total_gev[..., 0].to(torch.float64) - mass_gev).clamp_min(0.0)


def validate_p4_total(
    p4_total_gev: torch.Tensor,
    relative_energy_tolerance: float = 1e-5,
    require_forward_pz: bool = False,
) -> None:
    if p4_total_gev.ndim != 2 or p4_total_gev.shape[-1] != 4:
        raise ValueError(f"p4_total_gev must have shape [B,4], got {tuple(p4_total_gev.shape)}")
    if not torch.is_floating_point(p4_total_gev):
        raise ValueError("p4_total_gev must use a floating dtype")
    if not torch.isfinite(p4_total_gev).all():
        raise ValueError("p4_total_gev contains NaN or infinity")
    p4 = p4_total_gev.to(torch.float64)
    energy = p4[:, 0]
    momentum = p4[:, 1:]
    # Float32 cannot represent the neutron mass constant exactly.  Accept a
    # micro-GeV serialization tolerance while still rejecting physically
    # impossible four-vectors.
    if (energy < NEUTRON_MASS_GEV - 1e-6).any():
        raise ValueError("neutron total energy cannot be below the neutron rest mass")
    expected = total_energy_from_momentum(momentum)
    residual = (energy - expected).abs() / expected.clamp_min(1e-12)
    if (residual > relative_energy_tolerance).any():
        raise ValueError(
            "neutron mass-shell residual exceeds tolerance: "
            f"max={residual.max().item():.3e}, tolerance={relative_energy_tolerance:.3e}"
        )
    if require_forward_pz and (p4[:, 3] <= 0).any():
        raise ValueError("the fixed ZDC convention requires pz > 0")


def mass_shell_diagnostics(p4_total_gev: torch.Tensor) -> dict[str, torch.Tensor]:
    p4 = p4_total_gev.to(torch.float64)
    energy = p4[:, 0]
    momentum2 = p4[:, 1:].square().sum(dim=-1)
    expected = torch.sqrt(momentum2 + NEUTRON_MASS_GEV**2)
    return {
        "relative_energy_residual": (energy - expected).abs() / expected.clamp_min(1e-12),
        "mass_squared_residual_gev2": energy.square() - momentum2 - NEUTRON_MASS_GEV**2,
        "kinetic_energy_gev": (energy - NEUTRON_MASS_GEV).clamp_min(0.0),
    }
