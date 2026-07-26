import torch

from cbsc_zdc.training.flow_matching import (
    flow_matching_mse,
    linear_flow_matching_batch,
)


def test_linear_flow_matching_tuple_identity_and_condition_passthrough_contract():
    torch.manual_seed(11)
    target = torch.randn(4, 3, 2)
    condition = torch.randn(4, 5)
    x_t, t, velocity = linear_flow_matching_batch(target, condition)
    source = target - velocity
    assert x_t.shape == target.shape
    assert t.shape == (4, 1, 1)
    assert torch.all((t >= 0) & (t < 1))
    assert torch.allclose(x_t, (1 - t) * source + t * target)
    assert torch.allclose(velocity, target - source)


def test_flow_matching_mse_masked_and_unmasked():
    predicted = torch.tensor([[[1.0], [4.0]], [[2.0], [8.0]]])
    target = torch.zeros_like(predicted)
    assert torch.allclose(flow_matching_mse(predicted, target), predicted.square().mean())
    mask = torch.tensor([[1.0, 0.0], [1.0, 0.0]])
    expected = torch.tensor((1.0**2 + 2.0**2) / 2.0)
    assert torch.allclose(flow_matching_mse(predicted, target, mask), expected)
    zero_mask = torch.zeros_like(mask)
    assert flow_matching_mse(predicted, target, zero_mask).item() == 0.0
