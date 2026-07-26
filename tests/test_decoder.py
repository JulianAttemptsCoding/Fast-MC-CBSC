import pytest
import torch

from cbsc_zdc.models.support import decode_exact_support, exact_k_mask


def geometry():
    layer_index = torch.tensor([0, 0, 0, 1, 1], dtype=torch.long)
    valid = torch.ones(5, dtype=torch.bool)
    return layer_index, valid


def test_exact_k_mask_handles_zero_and_full_support():
    logits = torch.randn(2, 4)
    mask = exact_k_mask(logits, torch.tensor([0, 4]), stochastic=False)
    assert mask[0].sum().item() == 0
    assert mask[1].sum().item() == 4


def test_raw_decoder_exact_count_zeros_and_closure():
    layer_index, valid = geometry()
    support_logits = torch.tensor([[5.0, 3.0, 1.0, 2.0, -1.0]])
    share_logits = torch.tensor([[0.2, -0.4, 0.1, 1.0, -1.0]])
    budgets = torch.tensor([[4.0, 2.0]])
    counts = torch.tensor([[2, 1]])
    out = decode_exact_support(
        support_logits, share_logits, budgets, counts, layer_index, valid,
        threshold_gev=0.0, stochastic_support=False,
    )
    assert out.realized_counts.tolist() == [[2, 1]]
    assert torch.equal(out.support_mask, out.cell_energy > 0)
    assert out.cell_energy[~out.support_mask].abs().sum().item() == 0
    assert out.cell_energy[:, :3].sum().item() == pytest.approx(4.0, abs=1e-6)
    assert out.cell_energy[:, 3:].sum().item() == pytest.approx(2.0, abs=1e-6)


def test_threshold_decoder_has_no_dust():
    layer_index, valid = geometry()
    logits = torch.tensor([[3.0, 2.0, 1.0, 4.0, 0.0]])
    budgets = torch.tensor([[3.5, 1.2]])
    counts = torch.tensor([[2, 1]])
    out = decode_exact_support(
        logits, torch.zeros_like(logits), budgets, counts, layer_index, valid,
        threshold_gev=1.0, stochastic_support=False,
    )
    positive = out.cell_energy[out.cell_energy > 0]
    assert positive.min().item() >= 1.0
    assert not ((out.cell_energy > 0) & (out.cell_energy < 1.0)).any()
    assert out.cell_energy.sum().item() == pytest.approx(4.7, abs=1e-6)


def test_preselected_support_is_used_once():
    layer_index, valid = geometry()
    logits = torch.tensor([[9.0, 8.0, 7.0, 6.0, 5.0]])
    preselected = torch.tensor([[False, True, False, False, True]])
    out = decode_exact_support(
        logits, torch.zeros_like(logits), torch.tensor([[2.0, 3.0]]),
        torch.tensor([[1, 1]]), layer_index, valid, preselected_support_mask=preselected,
    )
    assert torch.equal(out.support_mask, preselected)


def test_threshold_infeasible_count_is_rejected():
    layer_index, valid = geometry()
    with pytest.raises(ValueError, match="threshold-infeasible"):
        decode_exact_support(
            torch.zeros(1, 5), torch.zeros(1, 5), torch.tensor([[1.0, 0.0]]),
            torch.tensor([[2, 0]]), layer_index, valid, threshold_gev=1.0,
        )
