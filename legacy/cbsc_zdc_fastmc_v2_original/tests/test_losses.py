import torch

from cbsc_zdc.training.losses import positive_log_energy_loss


def test_positive_spectrum_loss_uses_common_quantiles_for_unequal_counts():
    generated = torch.tensor([[1.0, 2.0, 3.0, 4.0]])
    truth = torch.tensor([[1.0, 4.0]])
    generated_mask = torch.ones_like(generated, dtype=torch.bool)
    truth_mask = torch.ones_like(truth, dtype=torch.bool)
    loss = positive_log_energy_loss(
        generated, truth, generated_mask, truth_mask
    )
    assert torch.isfinite(loss)
    assert loss >= 0


def test_loss_helpers_and_empty_positive_spectrum():
    from cbsc_zdc.training.losses import (
        count_cross_entropy,
        dust_fraction,
        support_binary_cross_entropy,
    )

    cell = torch.tensor([[0.0, 0.005, 0.02]])
    assert dust_fraction(cell, 0.0).item() == 0.0
    assert torch.isclose(dust_fraction(cell, 0.01), torch.tensor(1.0 / 3.0))
    support_loss = support_binary_cross_entropy(
        torch.tensor([[0.0, 1.0]]), torch.tensor([[False, True]])
    )
    assert torch.isfinite(support_loss)
    count_loss = count_cross_entropy(
        torch.tensor([[[2.0, 0.0], [0.0, 2.0]]]), torch.tensor([[0, 1]])
    )
    assert torch.isfinite(count_loss)
    empty = positive_log_energy_loss(
        torch.zeros(1, 2),
        torch.zeros(1, 2),
        torch.zeros(1, 2, dtype=torch.bool),
        torch.zeros(1, 2, dtype=torch.bool),
    )
    assert empty.item() == 0.0
