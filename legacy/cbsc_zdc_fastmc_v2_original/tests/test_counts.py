import pytest
import torch

from cbsc_zdc.models.counts import LayerCountHead


def test_count_head_masks_geometry_threshold_and_activity():
    with pytest.raises(ValueError, match="length"):
        LayerCountHead(cond_dim=4, n_layers=2, max_counts=[3])
    head = LayerCountHead(cond_dim=4, n_layers=2, max_counts=[3, 2], hidden=8)
    cond = torch.zeros(1, 4)
    energy = torch.tensor([[0.025, 0.0]])
    active = torch.tensor([[1.0, 0.0]])
    logits = head.logits(cond, energy, active, threshold_gev=0.01)
    finite = torch.isfinite(logits) & (logits > torch.finfo(logits.dtype).min / 2)
    assert not finite[0, 0, 0]
    assert finite[0, 0, 1]
    assert finite[0, 0, 2]
    assert not finite[0, 0, 3]
    assert finite[0, 1, 0]
    assert not finite[0, 1, 1:].any()
    deterministic, _ = head.sample(cond, energy, active, threshold_gev=0.01, stochastic=False)
    stochastic, _ = head.sample(cond, energy, active, threshold_gev=0.01, stochastic=True)
    assert deterministic.shape == stochastic.shape == (1, 2)
    with pytest.raises(ValueError, match="layer dimension"):
        head.logits(cond, torch.zeros(1, 3), torch.zeros(1, 3))
