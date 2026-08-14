"""Diversity at repeated conditions, and train-set memorization.

A generator can score well on every distribution metric by memorizing a handful
of training showers and replaying them.  Two checks make that visible:

**Diversity.**  Draw repeatedly at an identical ``p4`` and measure spread.  A
model that has collapsed produces near-identical draws, and its support Jaccard
approaches 1.  The comparison point is the *truth* spread at matched conditions,
so "less diverse than Geant4" is a statement with a scale.

**Memorization.**  Compare each generated shower to its nearest training
neighbour and compare that distance against the truth-to-truth nearest-neighbour
floor.  Generated events closer to training data than training data is to itself
indicates copying.
"""

from __future__ import annotations

from typing import Any

import torch


def support_jaccard(a: torch.Tensor, b: torch.Tensor) -> torch.Tensor:
    """Pairwise Jaccard between Boolean supports, elementwise over the batch."""
    intersection = (a & b).sum(dim=-1).double()
    union = (a | b).sum(dim=-1).double().clamp_min(1e-12)
    return intersection / union


def repeated_condition_diversity(draws: torch.Tensor) -> dict[str, float]:
    """Spread across repeated draws at one condition.

    ``draws`` has shape ``[R, N]`` for ``R`` repeats of the same condition.
    """
    if draws.shape[0] < 2:
        return {"repeats": int(draws.shape[0])}
    x = draws.double()
    per_cell_std = x.std(dim=0)
    pairwise = torch.cdist(x, x)
    triu = torch.triu(torch.ones_like(pairwise, dtype=torch.bool), diagonal=1)
    return {
        "repeats": int(draws.shape[0]),
        "mean_cell_std": float(per_cell_std.mean()),
        "mean_pairwise_distance": float(pairwise[triu].mean()),
        "min_pairwise_distance": float(pairwise[triu].min()),
    }


def repeated_support_jaccard(supports: torch.Tensor) -> dict[str, float]:
    """Mean pairwise support Jaccard across repeats; 1.0 means collapse."""
    repeats = supports.shape[0]
    if repeats < 2:
        return {"repeats": repeats}
    values = []
    for i in range(repeats):
        for j in range(i + 1, repeats):
            values.append(float(support_jaccard(supports[i], supports[j])))
    tensor = torch.tensor(values, dtype=torch.float64)
    return {
        "repeats": repeats,
        "mean_jaccard": float(tensor.mean()),
        "max_jaccard": float(tensor.max()),
        "pairs": len(values),
    }


def nearest_neighbour_distance(
    query: torch.Tensor, reference: torch.Tensor, *, exclude_self: bool = False
) -> torch.Tensor:
    """Distance from each query row to its closest reference row."""
    distance = torch.cdist(query.double(), reference.double())
    if exclude_self:
        n = min(distance.shape)
        distance[torch.arange(n), torch.arange(n)] = float("inf")
    return distance.min(dim=1).values


def memorization_report(
    generated: torch.Tensor, train: torch.Tensor, *, truth_floor_sample: torch.Tensor | None = None
) -> dict[str, Any]:
    """Nearest-neighbour distances against a truth-to-truth floor."""
    generated_nn = nearest_neighbour_distance(generated, train)
    report: dict[str, Any] = {
        "generated_events": int(generated.shape[0]),
        "train_events": int(train.shape[0]),
        "generated_to_train_nn_mean": float(generated_nn.mean()),
        "generated_to_train_nn_min": float(generated_nn.min()),
    }
    floor_source = truth_floor_sample if truth_floor_sample is not None else train
    truth_nn = nearest_neighbour_distance(floor_source, train, exclude_self=True)
    finite = truth_nn[torch.isfinite(truth_nn)]
    if finite.numel():
        floor = float(finite.mean())
        report["truth_to_train_nn_floor_mean"] = floor
        report["ratio_to_floor"] = report["generated_to_train_nn_mean"] / floor if floor > 0 else None
        # Below the floor means generated events sit closer to training data
        # than training data sits to itself: the memorization signature.
        report["below_truth_floor"] = bool(report["generated_to_train_nn_mean"] < floor)
    return report
