"""Differentiable share/profile stage samplers used by the critics."""

from __future__ import annotations

import inspect

import pytest
import torch

from cbsc_zdc.contracts import NEUTRON_MASS_GEV
from cbsc_zdc.models.system import CBSCZDC
from cbsc_zdc.training.stage_sampling import (
    TruthStructure,
    sample_profile_for_loss,
    sample_share_for_loss,
)

N_LAYERS, PER_LAYER = 3, 4
N_NODES = N_LAYERS * PER_LAYER


def geometry() -> dict[str, torch.Tensor]:
    layer_index = torch.arange(N_LAYERS).repeat_interleave(PER_LAYER)
    edges = []
    for layer in range(N_LAYERS):
        ids = torch.nonzero(layer_index == layer).flatten()
        for a in ids:
            for b in ids:
                if a != b:
                    edges.append([int(a), int(b)])
    edge_index = torch.tensor(edges, dtype=torch.long).T
    return {
        "node_features": torch.randn(N_NODES, 5),
        "layer_index": layer_index,
        "valid_mask": torch.ones(N_NODES, dtype=torch.bool),
        "edge_index": edge_index,
        "edge_features": torch.randn(edge_index.shape[1], 3),
    }


def model() -> CBSCZDC:
    torch.manual_seed(0)
    config = {
        "model": {"condition_dim": 16, "hidden_dim": 16, "graph_blocks": 1,
                  "attention_heads": 2, "attention_layers": 1, "profile_hidden": 16,
                  "count_hidden": 16, "response_hidden": 16},
        "data": {"target_mode": "raw_deposit", "threshold_gev": 0.0},
    }
    return CBSCZDC(geometry(), config)


def truth(batch: int = 2) -> TruthStructure:
    counts = torch.full((batch, N_LAYERS), 2, dtype=torch.long)
    support = torch.zeros(batch, N_NODES, dtype=torch.bool)
    for layer in range(N_LAYERS):
        support[:, layer * PER_LAYER : layer * PER_LAYER + 2] = True
    return TruthStructure(
        visible=torch.ones(batch, dtype=torch.bool),
        total_response=torch.full((batch,), 6.0),
        first_layer=torch.zeros(batch, dtype=torch.long),
        active_layers=torch.ones(batch, N_LAYERS, dtype=torch.bool),
        layer_energy=torch.full((batch, N_LAYERS), 2.0),
        requested_counts=counts,
        support_mask=support,
    )


def p4(batch: int = 2, energy: float = 100.0) -> torch.Tensor:
    """A mass-shell four-momentum along +z, as the data contract requires.

    Built in float64 so the mass-shell residual is exact, then cast to float32
    for the model -- the convention the rest of the suite uses.
    """
    total = torch.full((batch,), energy, dtype=torch.float64)
    momentum = torch.sqrt(total.square() - NEUTRON_MASS_GEV**2)
    return torch.stack(
        [total, torch.zeros_like(total), torch.zeros_like(total), momentum], dim=1
    ).float()


def test_share_loss_sampler_has_no_no_grad_context() -> None:
    source = inspect.getsource(sample_share_for_loss)
    assert "@torch.no_grad" not in source
    # It must also never delegate to the exact sampler.
    assert "sample_exact" not in source
    assert "self.sample(" not in source


def test_profile_loss_sampler_has_no_no_grad_decorator() -> None:
    source = inspect.getsource(sample_profile_for_loss)
    assert "@torch.no_grad" not in source
    assert "sample_exact" not in source


# A plain .sum() is a degenerate objective for both stages: the decoder closes
# each layer onto its budget and the profile closes onto the total, so the sum
# is a constant and its analytic gradient is exactly zero. A critic scores the
# *shape* of the deposit, so the tests use a shape-sensitive objective.
def test_share_output_has_nonzero_gradient_to_share_only() -> None:
    m, t = model(), truth()
    noise = torch.randn(2, N_NODES)
    out = sample_share_for_loss(m, p4(), t, noise, share_steps=2)
    out.cell_energy.square().sum().backward()
    share_grad = [p.grad for p in m.share.parameters() if p.grad is not None]
    assert share_grad and any(g.abs().sum() > 0 for g in share_grad)
    # The profile and count heads are truth-forced and must be untouched.
    assert all(p.grad is None or p.grad.abs().sum() == 0 for p in m.profile.parameters())
    assert all(p.grad is None or p.grad.abs().sum() == 0 for p in m.counts.parameters())


def test_profile_output_has_nonzero_gradient_to_profile_flow_only() -> None:
    m = model()
    noise = torch.randn(2, N_LAYERS)
    out = sample_profile_for_loss(
        m, p4(), torch.full((2,), 6.0),
        torch.ones(2, N_LAYERS, dtype=torch.bool), noise, profile_steps=2,
    )
    out.layer_energy.square().sum().backward()
    flow_grad = [p.grad for p in m.profile.flow.parameters() if p.grad is not None]
    assert flow_grad and any(g.abs().sum() > 0 for g in flow_grad)
    assert all(p.grad is None or p.grad.abs().sum() == 0 for p in m.share.parameters())


def test_total_energy_is_closed_and_therefore_has_no_shape_gradient() -> None:
    # Documents why the tests above use a squared objective: closure makes the
    # summed energy independent of the flow, which is a property worth pinning.
    m = model()
    out = sample_profile_for_loss(
        m, p4(), torch.full((2,), 6.0),
        torch.ones(2, N_LAYERS, dtype=torch.bool), torch.randn(2, N_LAYERS), profile_steps=2,
    )
    out.layer_energy.sum().backward()
    grads = [p.grad for p in m.profile.flow.parameters() if p.grad is not None]
    assert grads
    assert all(g.abs().max() < 1e-6 for g in grads)


def test_truth_forced_discrete_tensors_receive_no_gradient() -> None:
    m, t = model(), truth()
    bad = TruthStructure(
        visible=t.visible, total_response=t.total_response.clone().requires_grad_(True),
        first_layer=t.first_layer, active_layers=t.active_layers,
        layer_energy=t.layer_energy, requested_counts=t.requested_counts,
        support_mask=t.support_mask,
    )
    with pytest.raises(ValueError, match="must not require grad"):
        sample_share_for_loss(m, p4(), bad, torch.randn(2, N_NODES), 2)


def test_explicit_noise_makes_stage_sampler_repeatable() -> None:
    m, t = model(), truth()
    noise = torch.randn(2, N_NODES)
    a = sample_share_for_loss(m, p4(), t, noise, share_steps=2)
    b = sample_share_for_loss(m, p4(), t, noise, share_steps=2)
    assert torch.allclose(a.cell_energy, b.cell_energy)
    different = sample_share_for_loss(
        m, p4(), t, torch.randn(2, N_NODES), share_steps=2
    )
    assert not torch.allclose(a.cell_energy, different.cell_energy)


def test_share_output_respects_the_truth_support_and_closes_on_budget() -> None:
    m, t = model(), truth()
    out = sample_share_for_loss(m, p4(), t, torch.randn(2, N_NODES), 2)
    # nothing outside the truth support
    assert torch.equal(out.support_mask, t.support_mask)
    assert (out.cell_energy[~t.support_mask] == 0).all()
    # every selected cell strictly positive in raw mode
    assert (out.cell_energy[t.support_mask] > 0).all()
    # per-layer closure against the truth budget
    for layer in range(N_LAYERS):
        ids = torch.nonzero(m.layer_index == layer).flatten()
        assert torch.allclose(
            out.cell_energy[:, ids].sum(-1), t.layer_energy[:, layer], atol=1e-5
        )


def test_profile_output_sums_to_the_truth_total() -> None:
    m = model()
    total = torch.full((2,), 6.0)
    out = sample_profile_for_loss(
        m, p4(), total, torch.ones(2, N_LAYERS, dtype=torch.bool),
        torch.randn(2, N_LAYERS), profile_steps=2,
    )
    assert torch.allclose(out.layer_energy.sum(-1), total, atol=1e-5)


def test_exact_sample_retains_no_grad_and_structural_semantics() -> None:
    m = model()
    assert "no_grad" in str(type(m.sample)) or hasattr(m.sample, "__wrapped__")
    out = m.sample(p4(), profile_steps=2, share_steps=2, seed=0)
    assert not out.cell_energy.requires_grad
    assert (out.cell_energy >= 0).all()
    assert torch.isfinite(out.cell_energy).all()
