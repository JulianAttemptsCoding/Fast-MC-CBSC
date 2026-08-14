"""Incident-axis-relative geometry features."""

from __future__ import annotations

import math

import pytest
import torch

from cbsc_zdc.models.axis_features import (
    AXIS_FEATURE_DIM,
    AxisGeometryError,
    axis_features,
    geometry_scales,
    incident_basis,
    resolve_frozen_vertex,
)


def cells(n: int = 40) -> torch.Tensor:
    g = torch.Generator().manual_seed(11)
    return torch.rand(n, 3, generator=g, dtype=torch.float64) * 200.0 - 100.0


def directions(n: int = 16) -> torch.Tensor:
    g = torch.Generator().manual_seed(7)
    d = torch.randn(n, 3, generator=g, dtype=torch.float64)
    return d / d.norm(dim=-1, keepdim=True)


def test_basis_is_orthonormal_for_random_mass_shell_directions() -> None:
    u, e1, e2 = incident_basis(directions())
    for v in (u, e1, e2):
        assert torch.allclose(v.norm(dim=-1), torch.ones(v.shape[0], dtype=v.dtype), atol=1e-12)
    assert (u * e1).sum(-1).abs().max() < 1e-12
    assert (u * e2).sum(-1).abs().max() < 1e-12
    assert (e1 * e2).sum(-1).abs().max() < 1e-12


def test_basis_is_orthonormal_in_float32_within_1e_6() -> None:
    u, e1, e2 = incident_basis(directions().to(torch.float32))
    assert (u.norm(dim=-1) - 1).abs().max() < 1e-6
    assert (u * e1).sum(-1).abs().max() < 1e-6
    assert (u * e2).sum(-1).abs().max() < 1e-6
    assert (e1 * e2).sum(-1).abs().max() < 1e-6


def test_basis_is_finite_for_parallel_z_and_y_directions() -> None:
    special = torch.tensor(
        [[0.0, 0.0, 1.0], [0.0, 0.0, -1.0], [0.0, 1.0, 0.0], [0.0, -1.0, 0.0],
         [1.0, 0.0, 0.0], [0.0, 0.6, 0.8], [0.0, 0.0, 0.9], [0.0, 0.0, 0.89]],
        dtype=torch.float64,
    )
    u, e1, e2 = incident_basis(special)
    for v in (u, e1, e2):
        assert torch.isfinite(v).all()
    assert torch.allclose(e1.norm(dim=-1), torch.ones(special.shape[0], dtype=torch.float64))
    assert (u * e1).sum(-1).abs().max() < 1e-12


def test_longitudinal_and_radius_match_direct_geometry() -> None:
    r = cells()
    r0 = torch.zeros(3, dtype=torch.float64)
    d = torch.tensor([[0.0, 0.0, 1.0]], dtype=torch.float64)
    scales = geometry_scales(r, r0)
    feats = axis_features(r, r0, d, scales)
    assert feats.shape == (1, r.shape[0], AXIS_FEATURE_DIM)
    # along +z the longitudinal coordinate is exactly the z offset
    assert torch.allclose(feats[0, :, 0] * scales["s_scale_mm"], r[:, 2], atol=1e-10)
    # and the transverse radius is the xy norm
    assert torch.allclose(
        feats[0, :, 3] * scales["r_scale_mm"], r[:, :2].norm(dim=-1), atol=1e-10
    )


def test_joint_rigid_rotation_preserves_axis_coordinates_under_basis_convention() -> None:
    r = cells()
    r0 = torch.tensor([1.0, -2.0, 3.0], dtype=torch.float64)
    d = torch.tensor([[0.3, 0.4, 0.5]], dtype=torch.float64)
    d = d / d.norm()
    scales = geometry_scales(r, r0)
    before = axis_features(r, r0, d, scales)

    # rotate cells, vertex and direction together about x by 0.37 rad
    a = 0.37
    rot = torch.tensor(
        [[1.0, 0.0, 0.0], [0.0, math.cos(a), -math.sin(a)], [0.0, math.sin(a), math.cos(a)]],
        dtype=torch.float64,
    )
    after = axis_features(r @ rot.T, r0 @ rot.T, d @ rot.T, scales)

    # s and rho are convention independent and must be invariant
    assert torch.allclose(before[0, :, 0], after[0, :, 0], atol=1e-10)
    assert torch.allclose(before[0, :, 3], after[0, :, 3], atol=1e-10)
    # x,y may rotate within the transverse plane but their radius is preserved
    r_before = before[0, :, 1:3].norm(dim=-1)
    r_after = after[0, :, 1:3].norm(dim=-1)
    assert torch.allclose(r_before, r_after, atol=1e-10)


def test_nonfixed_vertex_contract_fails_closed() -> None:
    fixed = torch.tensor([[1.0, 2.0, 3.0], [1.0, 2.0, 3.0]], dtype=torch.float64)
    assert torch.allclose(resolve_frozen_vertex(fixed), fixed[0])

    drifting = torch.tensor([[1.0, 2.0, 3.0], [1.0, 2.0, 3.5]], dtype=torch.float64)
    with pytest.raises(AxisGeometryError, match="not fixed"):
        resolve_frozen_vertex(drifting)


def test_scales_are_geometry_derived_and_floored() -> None:
    r = torch.zeros(4, 3, dtype=torch.float64)
    scales = geometry_scales(r, torch.zeros(3, dtype=torch.float64))
    # a degenerate geometry must not produce a zero divisor
    assert scales["s_scale_mm"] >= 1.0
    assert scales["r_scale_mm"] >= 1.0


def test_features_are_finite_for_every_random_direction() -> None:
    r = cells()
    r0 = torch.zeros(3, dtype=torch.float64)
    scales = geometry_scales(r, r0)
    feats = axis_features(r, r0, directions(64), scales)
    assert torch.isfinite(feats).all()
