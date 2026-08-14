"""Incident-axis-relative node geometry.

The v2.2 node features are expressed in detector coordinates only, so the model
cannot see where a cell sits *relative to the incoming neutron*.  This module
adds four per-event, per-node coordinates.

For each event, build a stable orthonormal basis around the incident direction
``u``::

    a  = (0,0,1) if |u_z| < 0.9 else (0,1,0)      # avoid a degenerate cross product
    e1 = normalize(a - (a . u) u)
    e2 = u x e1

then for cell centre ``r_i`` and the frozen generator vertex ``r_0``::

    delta_i = r_i - r_0
    s_i     = delta_i . u        # longitudinal depth along the incident axis
    x_i     = delta_i . e1       # transverse
    y_i     = delta_i . e2       # transverse
    rho_i   = sqrt(x_i^2 + y_i^2)

Normalization uses frozen geometry-derived scales only -- never per-batch
statistics, which would leak batch composition into the features::

    s_scale = max_i |(r_i - r_0) . z_hat|, at least 1 mm
    r_scale = max_i ||(r_i - r_0)_xy||,    at least 1 mm

The reference-vector switch at ``|u_z| = 0.9`` makes the basis well defined for
every direction including exactly parallel to global z or y.  It also means the
basis convention (and therefore the sign of ``x`` and ``y``) changes across that
boundary; ``s`` and ``rho`` are convention-independent.
"""

from __future__ import annotations

import math
from typing import Any

import torch

PARALLEL_SWITCH_ABS_UZ = 0.9
MIN_SCALE_MM = 1.0
AXIS_FEATURE_NAMES = ("longitudinal_s", "transverse_x", "transverse_y", "transverse_radius")
AXIS_FEATURE_DIM = len(AXIS_FEATURE_NAMES)


class AxisGeometryError(ValueError):
    """Raised when the geometry cannot support incident-axis features."""


def incident_basis(direction: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Return ``(u, e1, e2)`` for unit incident directions ``[B,3]``.

    The reference vector switches away from global z when the direction is
    nearly parallel to it, so ``a - (a.u)u`` never approaches the zero vector.
    """
    if direction.ndim != 2 or direction.shape[-1] != 3:
        raise AxisGeometryError("incident direction must have shape [B,3]")
    norm = direction.norm(dim=-1, keepdim=True).clamp_min(1e-12)
    u = direction / norm
    near_z = u[:, 2].abs() >= PARALLEL_SWITCH_ABS_UZ
    reference = torch.where(
        near_z[:, None],
        torch.tensor([0.0, 1.0, 0.0], dtype=u.dtype, device=u.device).expand_as(u),
        torch.tensor([0.0, 0.0, 1.0], dtype=u.dtype, device=u.device).expand_as(u),
    )
    projected = reference - (reference * u).sum(dim=-1, keepdim=True) * u
    e1 = projected / projected.norm(dim=-1, keepdim=True).clamp_min(1e-12)
    e2 = torch.cross(u, e1, dim=-1)
    return u, e1, e2


def geometry_scales(cell_positions_mm: torch.Tensor, vertex_mm: torch.Tensor) -> dict[str, float]:
    """Frozen normalization scales derived from geometry alone."""
    delta = cell_positions_mm - vertex_mm[None]
    s_scale = float(delta[:, 2].abs().max().item())
    r_scale = float(delta[:, :2].norm(dim=-1).max().item())
    return {
        "s_scale_mm": max(s_scale, MIN_SCALE_MM),
        "r_scale_mm": max(r_scale, MIN_SCALE_MM),
    }


def resolve_frozen_vertex(
    vertices_mm: torch.Tensor, *, tolerance_mm: float = 1e-3
) -> torch.Tensor:
    """Return the single frozen generator vertex, or fail closed.

    The production data contract states the generator vertex is fixed.  If the
    supplied vertices are not identical within ``tolerance_mm`` the contract is
    not satisfied and axis features cannot be defined from a single origin; the
    data contract must be expanded before training rather than silently taking a
    mean.
    """
    if vertices_mm.ndim == 1:
        return vertices_mm
    spread = (vertices_mm - vertices_mm[0][None]).abs().max().item()
    if spread > tolerance_mm:
        raise AxisGeometryError(
            f"generator vertex is not fixed: maximum deviation {spread:.6g} mm "
            f"exceeds {tolerance_mm:.6g} mm. The production contract declares a "
            "fixed vertex; expand the data contract before training."
        )
    return vertices_mm[0]


def axis_features(
    cell_positions_mm: torch.Tensor,
    vertex_mm: torch.Tensor,
    direction: torch.Tensor,
    scales: dict[str, float],
) -> torch.Tensor:
    """Compute ``x_axis`` with shape ``[B, N, 4]``.

    ``cell_positions_mm`` is ``[N,3]``, ``vertex_mm`` is ``[3]``, ``direction``
    is ``[B,3]``.
    """
    if cell_positions_mm.ndim != 2 or cell_positions_mm.shape[-1] != 3:
        raise AxisGeometryError("cell positions must have shape [N,3]")
    u, e1, e2 = incident_basis(direction)
    delta = (cell_positions_mm[None] - vertex_mm[None, None]).to(u.dtype)  # [B,N,3]
    s = (delta * u[:, None]).sum(dim=-1)
    x = (delta * e1[:, None]).sum(dim=-1)
    y = (delta * e2[:, None]).sum(dim=-1)
    rho = torch.sqrt(x * x + y * y)
    s_scale = float(scales["s_scale_mm"])
    r_scale = float(scales["r_scale_mm"])
    return torch.stack([s / s_scale, x / r_scale, y / r_scale, rho / r_scale], dim=-1)


def geometry_manifest(
    cell_positions_mm: torch.Tensor, vertex_mm: torch.Tensor, scales: dict[str, float]
) -> dict[str, Any]:
    """Provenance for the axis basis, hashed by the caller with other artifacts."""
    return {
        "schema_version": 1,
        "kind": "cbsc-zdc-v3-axis-geometry",
        "vertex_mm": [float(v) for v in vertex_mm.tolist()],
        "s_scale_mm": float(scales["s_scale_mm"]),
        "r_scale_mm": float(scales["r_scale_mm"]),
        "parallel_switch_abs_uz": PARALLEL_SWITCH_ABS_UZ,
        "min_scale_mm": MIN_SCALE_MM,
        "feature_names": list(AXIS_FEATURE_NAMES),
        "n_nodes": int(cell_positions_mm.shape[0]),
        "basis_convention": (
            "a = (0,0,1) when |u_z| < 0.9 else (0,1,0); e1 = normalize(a - (a.u)u); e2 = u x e1"
        ),
    }
