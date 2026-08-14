"""Support-topology metrics."""

from __future__ import annotations

import torch

from cbsc_zdc.eval.topology import (
    connected_components,
    distance_binned_cooccupancy,
    edge_cooccupancy,
    nearest_neighbor_distances,
    radial_eccentricity,
    topology_report,
)


def chain_graph(n: int = 6) -> torch.Tensor:
    """0-1-2-3-4-5 undirected chain."""
    pairs = [(i, i + 1) for i in range(n - 1)]
    edges = [[a, b] for a, b in pairs] + [[b, a] for a, b in pairs]
    return torch.tensor(edges, dtype=torch.long).T


def positions(n: int = 6) -> torch.Tensor:
    return torch.stack(
        [torch.arange(n, dtype=torch.float64) * 10.0, torch.zeros(n), torch.zeros(n)], dim=1
    )


def test_connected_components_match_hand_graph() -> None:
    edge_index = chain_graph()
    # one contiguous block 1-2-3
    support = torch.tensor([[False, True, True, True, False, False]])
    counts, sizes = connected_components(support, edge_index)
    assert int(counts[0]) == 1
    assert sizes[0] == [3]

    # two blocks separated by a hole at index 2
    support = torch.tensor([[True, True, False, True, True, False]])
    counts, sizes = connected_components(support, edge_index)
    assert int(counts[0]) == 2
    assert sorted(sizes[0]) == [2, 2]

    # empty support is defined, not undefined
    counts, sizes = connected_components(torch.zeros(1, 6, dtype=torch.bool), edge_index)
    assert int(counts[0]) == 0
    assert sizes[0] == []


def test_edge_cooccupancy_matches_hand_graph() -> None:
    edge_index = chain_graph()  # 10 directed edges
    support = torch.tensor([[True, True, False, False, False, False]])
    # only the 0-1 pair is lit at both ends, in both directions: 2 of 10
    assert float(edge_cooccupancy(support, edge_index)[0]) == 0.2
    full = torch.ones(1, 6, dtype=torch.bool)
    assert float(edge_cooccupancy(full, edge_index)[0]) == 1.0


def test_pair_and_nearest_neighbor_distances_match_fixture() -> None:
    support = torch.tensor([[True, True, False, True, False, False]])
    out = nearest_neighbor_distances(support, positions())
    # lit at x = 0, 10, 30; nearest neighbours are 10, 10, 20
    assert torch.allclose(out[0], torch.tensor([10.0, 10.0, 20.0], dtype=torch.float64))


def test_single_hit_and_empty_layers_have_defined_outputs() -> None:
    support = torch.tensor([[True, False, False, False, False, False], [False] * 6])
    out = nearest_neighbor_distances(support, positions())
    assert out[0].numel() == 0  # a single hit has no neighbour distance
    assert out[1].numel() == 0
    report = topology_report(support, positions(), chain_graph())
    assert report["nearest_neighbor_distance_mean"] is None
    assert report["events"] == 2


def test_eccentricity_is_rotation_invariant() -> None:
    n = 6
    g = torch.Generator().manual_seed(4)
    xy = torch.rand(n, 2, generator=g, dtype=torch.float64) * 50
    pos = torch.cat([xy, torch.zeros(n, 1, dtype=torch.float64)], dim=1)
    support = torch.ones(1, n, dtype=torch.bool)
    before = radial_eccentricity(support, pos)

    angle = 0.7
    rot = torch.tensor(
        [[torch.cos(torch.tensor(angle)), -torch.sin(torch.tensor(angle))],
         [torch.sin(torch.tensor(angle)), torch.cos(torch.tensor(angle))]],
        dtype=torch.float64,
    )
    rotated = torch.cat([xy @ rot.T, torch.zeros(n, 1, dtype=torch.float64)], dim=1)
    after = radial_eccentricity(support, rotated)
    assert torch.allclose(before, after, atol=1e-10)


def test_distance_binned_cooccupancy_is_defined_for_empty_bins() -> None:
    support = torch.ones(1, 6, dtype=torch.bool)
    out = distance_binned_cooccupancy(support, positions(), [0.0, 5.0, 15.0, 1000.0])
    assert out.shape == (1, 3)
    assert float(out[0, 0]) == 0.0  # no pair closer than 5 mm
    assert float(out[0, 1]) == 1.0  # every 10 mm pair is lit at both ends
    assert torch.isfinite(out).all()


def test_topology_report_is_finite_and_complete() -> None:
    support = torch.tensor([[True, True, True, False, False, False]])
    report = topology_report(support, positions(), chain_graph())
    for key in (
        "hit_count_mean", "edge_cooccupancy_mean", "connected_components_mean",
        "largest_component_fraction_mean", "radial_eccentricity_mean",
    ):
        assert report[key] is not None
    assert report["largest_component_fraction_mean"] == 1.0
