import torch

from cbsc_zdc.eval.diagnostics import invariant_report
from cbsc_zdc.models.system import CBSCZDC


def test_sampling_invariants_small_geometry():
    n_layers = 5
    nodes_per_layer = 8
    n_nodes = n_layers * nodes_per_layer
    layer = torch.arange(n_nodes) // nodes_per_layer
    features = torch.randn(n_nodes, 8)
    valid = torch.ones(n_nodes, dtype=torch.bool)
    model = CBSCZDC(
        features,
        layer,
        valid,
        cond_dim=32,
        latent_dim=8,
        threshold_gev=0.001,
    )
    mass = 0.93956542052
    momentum = torch.tensor([[0.0, 0.0, 50.0], [1.0, 2.0, 100.0]])
    energy = torch.sqrt((momentum * momentum).sum(dim=-1) + mass**2)[:, None]
    p4 = torch.cat((energy, momentum), dim=-1)
    out = model.sample(p4, steps=2, seed=1)
    report = invariant_report(
        p4,
        out,
        threshold_gev=0.001,
        layer_index=layer,
    )
    assert report["nonfinite"] == 0
    assert report["negative"] == 0
    assert report["dust_cells"] == 0
    assert report["total_over_incident"] == 0
    assert report["accounting_identity_max"] < 1e-4
    assert report["support_count_mismatch_max"] == 0
    assert report["resolved_layer_mismatch_max"] < 1e-4


def test_seeded_sampling_is_reproducible():
    n_layers = 3
    nodes_per_layer = 4
    n_nodes = n_layers * nodes_per_layer
    layer = torch.arange(n_nodes) // nodes_per_layer
    features = torch.randn(n_nodes, 8)
    valid = torch.ones(n_nodes, dtype=torch.bool)
    model = CBSCZDC(features, layer, valid, cond_dim=16, latent_dim=4, threshold_gev=0.0)
    mass = 0.93956542052
    momentum = torch.tensor([[0.5, 1.0, 20.0]])
    energy = torch.sqrt((momentum * momentum).sum(dim=-1) + mass**2)[:, None]
    p4 = torch.cat((energy, momentum), dim=-1)
    a = model.sample(p4, steps=2, seed=17)
    b = model.sample(p4, steps=2, seed=17)
    assert torch.equal(a.support_mask, b.support_mask)
    assert torch.allclose(a.cell_energy, b.cell_energy)


def test_nonstochastic_sampling_is_deterministic_without_a_seed():
    n_layers = 3
    nodes_per_layer = 4
    n_nodes = n_layers * nodes_per_layer
    layer = torch.arange(n_nodes) // nodes_per_layer
    features = torch.randn(n_nodes, 8)
    valid = torch.ones(n_nodes, dtype=torch.bool)
    model = CBSCZDC(
        features,
        layer,
        valid,
        cond_dim=16,
        latent_dim=4,
        threshold_gev=0.0,
    ).eval()
    mass = 0.93956542052
    momentum = torch.tensor([[0.5, 1.0, 20.0]])
    energy = torch.sqrt((momentum * momentum).sum(dim=-1) + mass**2)[:, None]
    p4 = torch.cat((energy, momentum), dim=-1)
    a = model.sample(p4, steps=2, stochastic=False)
    b = model.sample(p4, steps=2, stochastic=False)
    assert torch.equal(a.support_mask, b.support_mask)
    assert torch.allclose(a.cell_energy, b.cell_energy)


def test_system_constructor_and_sampling_validation_paths():
    import pytest

    features = torch.zeros(4, 8)
    layers = torch.tensor([0, 0, 1, 1])
    valid = torch.ones(4, dtype=torch.bool)
    with pytest.raises(ValueError, match="nonnegative"):
        CBSCZDC(features, layers, valid, threshold_gev=-1.0)
    with pytest.raises(ValueError, match="node_features"):
        CBSCZDC(torch.zeros(4), layers, valid)
    with pytest.raises(ValueError, match="shape"):
        CBSCZDC(features, layers[:3], valid)
    with pytest.raises(ValueError, match="nonnegative"):
        CBSCZDC(features, torch.tensor([0, 0, -1, 1]), valid)
    with pytest.raises(ValueError, match="at least one valid"):
        CBSCZDC(features, layers, torch.zeros(4, dtype=torch.bool))
    with pytest.raises(ValueError, match="supplied together"):
        CBSCZDC(features, layers, valid, edge_index=torch.empty(2, 0, dtype=torch.long))
    with pytest.raises(ValueError, match="every modeled layer"):
        CBSCZDC(features, torch.tensor([0, 0, 2, 2]), valid)

    model = CBSCZDC(features, layers, valid, cond_dim=16, latent_dim=4)
    mass = 0.93956542052
    momentum = torch.tensor([[0.0, 0.0, 10.0]])
    energy = torch.sqrt((momentum * momentum).sum(dim=-1) + mass**2)[:, None]
    p4 = torch.cat((energy, momentum), dim=-1)
    with pytest.raises(ValueError, match="steps"):
        model.sample(p4, steps=0)


def test_invariant_report_without_layer_breakdown_and_explicit_empty_graph():
    n_nodes = 4
    features = torch.zeros(n_nodes, 8)
    layers = torch.tensor([0, 0, 1, 1])
    valid = torch.ones(n_nodes, dtype=torch.bool)
    model = CBSCZDC(
        features,
        layers,
        valid,
        cond_dim=16,
        latent_dim=4,
        edge_index=torch.empty(2, 0, dtype=torch.long),
        edge_features=torch.empty(0, 4),
    )
    mass = 0.93956542052
    momentum = torch.tensor([[0.0, 0.0, 10.0]])
    energy = torch.sqrt((momentum * momentum).sum(dim=-1) + mass**2)[:, None]
    p4 = torch.cat((energy, momentum), dim=-1)
    out = model.sample(p4, steps=1, stochastic=False)
    report = invariant_report(p4, out)
    assert "resolved_layer_mismatch_max" not in report
