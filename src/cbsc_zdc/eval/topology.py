"""Low-level support-topology metrics.

The existing diagnostics compare aggregate distributions (total response, hit
count, longitudinal profile).  They cannot see whether the *set of lit cells*
looks like a shower: a generated event with the right hit count but scattered
hits scores identically to one with a compact core.

These metrics look at the support itself -- connectivity, co-occupancy, spatial
spread -- so a topology failure has somewhere to show up.

Every metric here is descriptive.  None of them selects a checkpoint.
"""

from __future__ import annotations

from typing import Any

import torch


def connected_components(
    support: torch.Tensor, edge_index: torch.Tensor
) -> tuple[torch.Tensor, list[list[int]]]:
    """Count connected components of the lit sub-graph, per event.

    Returns ``(counts[B], sizes_per_event)``.  An event with no lit cell has
    zero components rather than an undefined value.
    """
    b, n = support.shape
    src, dst = edge_index
    counts = torch.zeros(b, dtype=torch.long)
    sizes: list[list[int]] = []
    for event in range(b):
        lit = support[event].bool()
        if not lit.any():
            sizes.append([])
            continue
        parent = list(range(n))

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        keep = lit[src] & lit[dst]
        for a, c in zip(src[keep].tolist(), dst[keep].tolist()):
            ra, rc = find(a), find(c)
            if ra != rc:
                parent[ra] = rc
        roots: dict[int, int] = {}
        for node in torch.nonzero(lit).flatten().tolist():
            roots[find(node)] = roots.get(find(node), 0) + 1
        counts[event] = len(roots)
        sizes.append(sorted(roots.values(), reverse=True))
    return counts, sizes


def edge_cooccupancy(support: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
    """Fraction of graph edges whose endpoints are both lit, per event."""
    src, dst = edge_index
    both = (support[:, src] & support[:, dst]).sum(dim=1).to(torch.float64)
    return both / max(int(edge_index.shape[1]), 1)


def distance_binned_cooccupancy(
    support: torch.Tensor, positions_mm: torch.Tensor, bin_edges_mm: list[float]
) -> torch.Tensor:
    """Co-occupancy of lit pairs by separation distance, per event.

    Shape ``[B, len(bin_edges)-1]``.  Bins with no candidate pair report zero.
    """
    b = support.shape[0]
    out = torch.zeros(b, len(bin_edges_mm) - 1, dtype=torch.float64)
    distance = torch.cdist(positions_mm.double(), positions_mm.double())
    triu = torch.triu(torch.ones_like(distance, dtype=torch.bool), diagonal=1)
    for index in range(len(bin_edges_mm) - 1):
        low, high = bin_edges_mm[index], bin_edges_mm[index + 1]
        in_bin = triu & (distance >= low) & (distance < high)
        total = int(in_bin.sum())
        if total == 0:
            continue
        rows, cols = torch.nonzero(in_bin, as_tuple=True)
        both = (support[:, rows] & support[:, cols]).sum(dim=1).to(torch.float64)
        out[:, index] = both / total
    return out


def nearest_neighbor_distances(
    support: torch.Tensor, positions_mm: torch.Tensor
) -> list[torch.Tensor]:
    """Per-event nearest-neighbour distance among lit cells.

    An event with fewer than two lit cells yields an empty tensor rather than a
    fabricated value.
    """
    out = []
    for event in range(support.shape[0]):
        ids = torch.nonzero(support[event].bool()).flatten()
        if ids.numel() < 2:
            out.append(torch.empty(0, dtype=torch.float64))
            continue
        points = positions_mm[ids].double()
        distance = torch.cdist(points, points)
        distance.fill_diagonal_(float("inf"))
        out.append(distance.min(dim=1).values)
    return out


def radial_eccentricity(
    support: torch.Tensor, positions_mm: torch.Tensor, weights: torch.Tensor | None = None
) -> torch.Tensor:
    """Transverse spread of the lit set about its own centroid, per event.

    Rotation invariant about the beam axis because it is computed from
    distances to the centroid, not from absolute coordinates.
    """
    b = support.shape[0]
    out = torch.zeros(b, dtype=torch.float64)
    for event in range(b):
        ids = torch.nonzero(support[event].bool()).flatten()
        if ids.numel() == 0:
            continue
        points = positions_mm[ids, :2].double()
        w = (
            weights[event, ids].double()
            if weights is not None
            else torch.ones(ids.numel(), dtype=torch.float64)
        )
        w = w / w.sum().clamp_min(1e-12)
        centroid = (points * w[:, None]).sum(dim=0)
        delta = points - centroid
        out[event] = torch.sqrt(((delta**2).sum(dim=1) * w).sum())
    return out


def topology_report(
    support: torch.Tensor,
    positions_mm: torch.Tensor,
    edge_index: torch.Tensor,
    *,
    distance_bins_mm: list[float] | None = None,
    weights: torch.Tensor | None = None,
) -> dict[str, Any]:
    counts, sizes = connected_components(support, edge_index)
    neighbours = nearest_neighbor_distances(support, positions_mm)
    flat = torch.cat([t for t in neighbours if t.numel()]) if any(
        t.numel() for t in neighbours
    ) else torch.empty(0, dtype=torch.float64)
    bins = distance_bins_mm or [0.0, 10.0, 25.0, 50.0, 100.0]
    return {
        "events": int(support.shape[0]),
        "hit_count_mean": float(support.sum(dim=1).double().mean()),
        "edge_cooccupancy_mean": float(edge_cooccupancy(support, edge_index).mean()),
        "distance_binned_cooccupancy_mean": distance_binned_cooccupancy(
            support, positions_mm, bins
        ).mean(dim=0).tolist(),
        "distance_bins_mm": bins,
        "connected_components_mean": float(counts.double().mean()),
        "largest_component_fraction_mean": float(
            torch.tensor(
                [(s[0] / sum(s)) if s else 0.0 for s in sizes], dtype=torch.float64
            ).mean()
        ),
        "nearest_neighbor_distance_mean": float(flat.mean()) if flat.numel() else None,
        "radial_eccentricity_mean": float(radial_eccentricity(support, positions_mm, weights).mean()),
    }
