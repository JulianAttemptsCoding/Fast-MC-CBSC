import torch

from cbsc_zdc.models.support import threshold_safe_layer_decoder


def test_threshold_safe_decoder_has_no_dust_and_exact_budget():
    layer_index = torch.tensor([0, 0, 0, 1, 1, 1, 1])
    valid = torch.ones(7, dtype=torch.bool)
    support_logits = torch.tensor([[4.0, 3.0, 2.0, 1.0, 0.0, -1.0, -2.0]])
    share_logits = torch.tensor([[0.0, 1.0, 2.0, 0.0, 0.5, 1.0, 1.5]])
    budget = torch.tensor([[0.050, 0.100]])
    counts = torch.tensor([[2, 3]])
    threshold = 0.010
    out = threshold_safe_layer_decoder(
        support_logits,
        share_logits,
        budget,
        counts,
        layer_index,
        valid,
        threshold_gev=threshold,
        stochastic_support=False,
    )
    positive = out.cell_energy[out.cell_energy > 0]
    assert positive.numel() == 5
    assert torch.all(positive >= threshold)
    assert torch.allclose(out.resolved_layer_energy, budget, atol=1e-7)
    assert torch.allclose(out.subthreshold_residual, torch.zeros_like(budget), atol=1e-7)
    assert torch.equal(out.support_mask.sum(dim=-1), out.realized_counts.sum(dim=-1))


def test_budget_below_threshold_becomes_residual_not_dust():
    layer_index = torch.tensor([0, 0, 0])
    valid = torch.ones(3, dtype=torch.bool)
    out = threshold_safe_layer_decoder(
        support_logits=torch.zeros(1, 3),
        share_logits=torch.zeros(1, 3),
        layer_budget=torch.tensor([[0.005]]),
        requested_counts=torch.tensor([[1]]),
        layer_index=layer_index,
        valid_mask=valid,
        threshold_gev=0.010,
        stochastic_support=False,
    )
    assert torch.equal(out.cell_energy, torch.zeros_like(out.cell_energy))
    assert torch.allclose(out.subthreshold_residual, torch.tensor([[0.005]]))
    assert out.realized_counts.item() == 0


def test_vectorized_decoder_handles_mixed_zero_and_positive_counts():
    layer_index = torch.tensor([0, 0, 0, 1, 1])
    valid = torch.ones(5, dtype=torch.bool)
    out = threshold_safe_layer_decoder(
        support_logits=torch.tensor([[2.0, 1.0, 0.0, 2.0, 1.0], [1.0, 2.0, 0.0, 1.0, 2.0]]),
        share_logits=torch.zeros(2, 5),
        layer_budget=torch.tensor([[0.0, 0.03], [0.02, 0.0]]),
        requested_counts=torch.tensor([[0, 2], [2, 0]]),
        layer_index=layer_index,
        valid_mask=valid,
        threshold_gev=0.01,
        stochastic_support=False,
    )
    assert torch.equal(out.realized_counts, torch.tensor([[0, 2], [2, 0]]))
    assert torch.allclose(out.cell_energy.sum(dim=1), torch.tensor([0.03, 0.02]))
    assert torch.all(out.cell_energy[(out.cell_energy > 0)] >= 0.01)


def test_single_vector_gumbel_topk_and_decoder_validation_paths():
    import pytest

    from cbsc_zdc.models.support import gumbel_topk_mask

    logits = torch.tensor([3.0, 2.0, 1.0])
    assert gumbel_topk_mask(logits, 0, stochastic=False).sum() == 0
    assert gumbel_topk_mask(logits, 2, stochastic=False).tolist() == [True, True, False]
    assert gumbel_topk_mask(logits, 2, stochastic=True).sum() == 2
    with pytest.raises(ValueError, match="one-dimensional"):
        gumbel_topk_mask(logits[None], 1)
    with pytest.raises(ValueError, match="outside"):
        gumbel_topk_mask(logits, 4)

    base = dict(
        support_logits=torch.zeros(1, 3),
        share_logits=torch.zeros(1, 3),
        layer_budget=torch.zeros(1, 1),
        requested_counts=torch.zeros(1, 1, dtype=torch.long),
        layer_index=torch.zeros(3, dtype=torch.long),
        valid_mask=torch.ones(3, dtype=torch.bool),
    )
    with pytest.raises(ValueError, match="nonnegative"):
        threshold_safe_layer_decoder(**base, threshold_gev=-1.0)
    bad = dict(base)
    bad["support_logits"] = torch.zeros(3)
    with pytest.raises(ValueError, match="support_logits"):
        threshold_safe_layer_decoder(**bad)
    bad = dict(base)
    bad["share_logits"] = torch.zeros(1, 2)
    with pytest.raises(ValueError, match="share_logits"):
        threshold_safe_layer_decoder(**bad)
    bad = dict(base)
    bad["valid_mask"] = torch.ones(2, dtype=torch.bool)
    with pytest.raises(ValueError, match="layer_index"):
        threshold_safe_layer_decoder(**bad)
    bad = dict(base)
    bad["requested_counts"] = torch.zeros(1, 2, dtype=torch.long)
    with pytest.raises(ValueError, match="same shape"):
        threshold_safe_layer_decoder(**bad)


def test_decoder_routes_budget_for_layer_with_no_valid_nodes():
    out = threshold_safe_layer_decoder(
        support_logits=torch.zeros(1, 2),
        share_logits=torch.zeros(1, 2),
        layer_budget=torch.tensor([[0.0, 0.4]]),
        requested_counts=torch.tensor([[0, 1]]),
        layer_index=torch.tensor([0, 0]),
        valid_mask=torch.ones(2, dtype=torch.bool),
        threshold_gev=0.0,
        stochastic_support=False,
    )
    assert torch.allclose(out.subthreshold_residual, torch.tensor([[0.0, 0.4]]))


def test_batched_topk_private_validation_paths():
    import pytest

    from cbsc_zdc.models.support import _batched_exact_k_mask

    logits = torch.zeros(2, 3)
    with pytest.raises(ValueError, match="shape mismatch"):
        _batched_exact_k_mask(logits[0], torch.tensor([1, 1]), stochastic=False)
    with pytest.raises(ValueError, match="infeasible"):
        _batched_exact_k_mask(logits, torch.tensor([1, 4]), stochastic=False)
