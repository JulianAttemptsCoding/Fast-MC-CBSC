import torch

from cbsc_zdc.models.spatial import ParallelCausalSpatialField


def test_spatial_field_depends_on_flow_time():
    torch.manual_seed(4)
    n_layers = 3
    nodes_per_layer = 2
    n_nodes = n_layers * nodes_per_layer
    model = ParallelCausalSpatialField(
        node_dim=5,
        cond_dim=8,
        hidden=16,
        n_layers=n_layers,
        transformer_blocks=1,
        heads=4,
        graph_blocks=1,
        edge_dim=3,
    ).eval()
    x = torch.randn(2, n_nodes, 2)
    cond = torch.randn(2, 8)
    node_features = torch.randn(n_nodes, 5)
    layer_index = torch.arange(n_nodes) // nodes_per_layer
    budget = torch.rand(2, n_layers)
    counts = torch.ones(2, n_layers, dtype=torch.long)
    max_counts = torch.full((n_layers,), nodes_per_layer, dtype=torch.long)
    edge_index = torch.tensor([[0, 1, 2, 3], [1, 2, 3, 4]])
    edge_features = torch.randn(4, 3)
    with torch.no_grad():
        a = model(x, torch.zeros(2, 1), cond, node_features, layer_index, budget, counts, max_counts, edge_index=edge_index, edge_features=edge_features)
        b = model(x, torch.ones(2, 1), cond, node_features, layer_index, budget, counts, max_counts, edge_index=edge_index, edge_features=edge_features)
    assert not torch.allclose(a, b)


def test_spatial_field_validation_and_default_valid_mask():
    import pytest

    with pytest.raises(ValueError, match="divisible"):
        ParallelCausalSpatialField(hidden=10, heads=4)

    model = ParallelCausalSpatialField(
        node_dim=3,
        edge_dim=2,
        cond_dim=4,
        hidden=8,
        n_layers=2,
        graph_blocks=0,
        transformer_blocks=1,
        heads=2,
    ).eval()
    x = torch.zeros(1, 4, 2)
    t = torch.zeros(1, 1)
    cond = torch.zeros(1, 4)
    nodes = torch.zeros(4, 3)
    layers = torch.tensor([0, 0, 1, 1])
    budget = torch.ones(1, 2)
    counts = torch.ones(1, 2, dtype=torch.long)
    maxima = torch.tensor([2, 2])
    with torch.no_grad():
        out = model(x, t, cond, nodes, layers, budget, counts, maxima)
    assert out.shape == x.shape

    with pytest.raises(ValueError, match="two node-state"):
        model(torch.zeros(1, 4, 1), t, cond, nodes, layers, budget, counts, maxima)
    with pytest.raises(ValueError, match="geometry"):
        model(x, t, cond, nodes[:3], layers, budget, counts, maxima)
    with pytest.raises(ValueError, match="valid_mask"):
        model(x, t, cond, nodes, layers, budget, counts, maxima, valid_mask=torch.ones(3, dtype=torch.bool))
    with pytest.raises(ValueError, match="supplied together"):
        model(x, t, cond, nodes, layers, budget, counts, maxima, edge_index=torch.empty(2, 0, dtype=torch.long))
