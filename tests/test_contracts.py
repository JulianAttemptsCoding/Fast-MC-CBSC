import math
import pytest
import torch

from cbsc_zdc.contracts import (
    NEUTRON_MASS_GEV,
    kinetic_energy_from_p4,
    validate_p4_total,
)
from cbsc_zdc.features import p4_condition_features


def p4_from_kinetic(k):
    total = torch.tensor(k + NEUTRON_MASS_GEV, dtype=torch.float64)
    pz = torch.sqrt(total.square() - NEUTRON_MASS_GEV**2)
    return torch.tensor([[float(total), 0.0, 0.0, float(pz)]], dtype=torch.float32)


def test_total_energy_and_kinetic_are_not_conflated():
    p4 = p4_from_kinetic(50.0)
    validate_p4_total(p4)
    assert kinetic_energy_from_p4(p4).item() == pytest.approx(50.0, rel=2e-6)
    assert p4[0, 0].item() > 50.0


def test_float32_rest_mass_serialization_is_accepted():
    p4 = torch.tensor([[NEUTRON_MASS_GEV, 0.0, 0.0, 0.0]], dtype=torch.float32)
    validate_p4_total(p4)
    features = p4_condition_features(p4)
    assert torch.isfinite(features).all()
    assert features.shape == (1, 5)


def test_off_shell_vector_is_rejected():
    p4 = p4_from_kinetic(100.0)
    p4[0, 1] = 20.0
    with pytest.raises(ValueError, match="mass-shell"):
        validate_p4_total(p4)
