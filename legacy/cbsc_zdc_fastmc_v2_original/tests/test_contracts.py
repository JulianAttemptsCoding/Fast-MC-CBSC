import math

import pytest
import torch

from cbsc_zdc.contracts import mass_shell_diagnostics, validate_p4
from cbsc_zdc.features import p4_features


def neutron_p4(energy: float, dtype: torch.dtype = torch.float32) -> torch.Tensor:
    mass = 0.93956542052
    momentum = math.sqrt(energy**2 - mass**2)
    return torch.tensor([[energy, 0.0, 0.0, momentum]], dtype=dtype)


def test_high_energy_float32_mass_shell_is_not_rejected_by_cancellation():
    for energy in (50.0, 100.0, 250.0, 300.0):
        p4 = neutron_p4(energy)
        validate_p4(p4)
        diagnostics = mass_shell_diagnostics(p4)
        assert diagnostics["relative_energy_residual"].item() < 1e-6
        features = p4_features(p4)
        assert features.shape == (1, 4)
        assert torch.isfinite(features).all()


def test_malformed_four_vector_is_rejected():
    malformed = torch.tensor([[100.0, 0.0, 0.0, 90.0]])
    with pytest.raises(ValueError, match="mass-shell"):
        validate_p4(malformed)


def test_p4_validation_error_paths_and_feature_scale():
    with pytest.raises(ValueError, match="shape"):
        validate_p4(torch.zeros(4))
    with pytest.raises(ValueError, match="floating-point"):
        validate_p4(torch.tensor([[1, 0, 0, 0]]))
    with pytest.raises(ValueError, match="NaN/Inf"):
        validate_p4(torch.tensor([[float("nan"), 0.0, 0.0, 0.0]]))
    with pytest.raises(ValueError, match="positive"):
        validate_p4(torch.tensor([[0.0, 0.0, 0.0, 0.0]]))
    with pytest.raises(ValueError, match="shape"):
        mass_shell_diagnostics(torch.zeros(4))
    with pytest.raises(ValueError, match="energy_scale"):
        p4_features(neutron_p4(50.0), energy_scale_gev=0.0)
