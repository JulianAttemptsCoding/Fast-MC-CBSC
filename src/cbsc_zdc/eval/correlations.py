"""Layer-energy correlation, transition matrices, truth halves and bootstrap.

Two things this module exists to fix:

**Correlation is invisible to marginal metrics.**  A generator can match every
per-layer marginal while getting the joint structure wrong.  The 65x65 layer
covariance and correlation, compared by Frobenius distance, sees that.

**A distance needs a floor.**  A Frobenius distance of 0.3 means nothing on its
own.  Splitting the *truth* into two deterministic disjoint halves and measuring
truth-vs-truth gives the irreducible sampling floor, so generated-vs-truth can
be read against something.  A generated distance at the truth-half floor is as
good as the statistic can resolve.

Bootstrap resampling is stratified by energy bin so a replicate cannot silently
change the energy composition of the sample.
"""

from __future__ import annotations

import hashlib
from typing import Any

import torch


def layer_covariance(layer_energy: torch.Tensor) -> torch.Tensor:
    x = layer_energy.double()
    centred = x - x.mean(dim=0, keepdim=True)
    n = max(x.shape[0] - 1, 1)
    return centred.T @ centred / n


def layer_correlation(layer_energy: torch.Tensor) -> tuple[torch.Tensor, list[int]]:
    """Correlation matrix plus the indices of zero-variance layers.

    A layer that never fires has undefined correlation; it is set to zero and
    reported rather than silently producing NaN.
    """
    covariance = layer_covariance(layer_energy)
    deviation = torch.sqrt(torch.diagonal(covariance).clamp_min(0))
    degenerate = torch.nonzero(deviation <= 1e-12).flatten().tolist()
    safe = deviation.clamp_min(1e-12)
    correlation = covariance / (safe[:, None] * safe[None, :])
    if degenerate:
        index = torch.tensor(degenerate, dtype=torch.long)
        correlation[index, :] = 0.0
        correlation[:, index] = 0.0
    return correlation, degenerate


def frobenius_distance(a: torch.Tensor, b: torch.Tensor) -> float:
    return float(torch.linalg.matrix_norm(a.double() - b.double(), ord="fro"))


def activity_transition_matrix(active: torch.Tensor) -> torch.Tensor:
    rows = active.bool()
    previous = rows[:, :-1].reshape(-1).long()
    following = rows[:, 1:].reshape(-1).long()
    matrix = torch.zeros(2, 2, dtype=torch.float64)
    for a in (0, 1):
        for b in (0, 1):
            matrix[a, b] = float(((previous == a) & (following == b)).sum())
    total = matrix.sum().clamp_min(1)
    return matrix / total


def count_transition_correlation(counts: torch.Tensor) -> float:
    """Pearson correlation between adjacent-layer counts."""
    a = counts[:, :-1].reshape(-1).double()
    b = counts[:, 1:].reshape(-1).double()
    if a.numel() < 2:
        return 0.0
    a_c, b_c = a - a.mean(), b - b.mean()
    denominator = (a_c.norm() * b_c.norm()).clamp_min(1e-12)
    return float((a_c * b_c).sum() / denominator)


def deterministic_truth_halves(event_ids: list[int], salt: str = "cbsc-v3-truth-half") -> tuple[list[int], list[int]]:
    """Split truth into two disjoint halves by digest, reproducibly."""
    keyed = sorted(
        event_ids, key=lambda e: hashlib.sha256(f"{salt}:{e}".encode("utf-8")).hexdigest()
    )
    middle = len(keyed) // 2
    return sorted(keyed[:middle]), sorted(keyed[middle:])


def stratified_bootstrap_indices(
    strata: list[str], replicates: int, seed: int = 20260813
) -> list[list[int]]:
    """Resample within each stratum so energy composition is preserved."""
    generator = torch.Generator().manual_seed(seed)
    buckets: dict[str, list[int]] = {}
    for index, name in enumerate(strata):
        buckets.setdefault(name, []).append(index)
    out = []
    for _ in range(replicates):
        draw: list[int] = []
        for name in sorted(buckets):
            pool = buckets[name]
            picks = torch.randint(
                0, len(pool), (len(pool),), generator=generator
            ).tolist()
            draw.extend(pool[p] for p in picks)
        out.append(sorted(draw))
    return out


def bootstrap_interval(
    values: list[float], confidence: float = 0.95
) -> dict[str, float]:
    if not values:
        return {"mean": 0.0, "low": 0.0, "high": 0.0, "replicates": 0}
    ordered = sorted(values)
    alpha = (1.0 - confidence) / 2.0
    low = ordered[min(int(alpha * len(ordered)), len(ordered) - 1)]
    high = ordered[min(int((1 - alpha) * len(ordered)), len(ordered) - 1)]
    return {
        "mean": sum(values) / len(values),
        "low": low,
        "high": high,
        "replicates": len(values),
        "confidence": confidence,
    }


def correlation_report(
    generated_layer_energy: torch.Tensor,
    truth_layer_energy: torch.Tensor,
    *,
    truth_half_a: torch.Tensor | None = None,
    truth_half_b: torch.Tensor | None = None,
) -> dict[str, Any]:
    generated_corr, generated_degenerate = layer_correlation(generated_layer_energy)
    truth_corr, truth_degenerate = layer_correlation(truth_layer_energy)
    report: dict[str, Any] = {
        "covariance_frobenius": frobenius_distance(
            layer_covariance(generated_layer_energy), layer_covariance(truth_layer_energy)
        ),
        "correlation_frobenius": frobenius_distance(generated_corr, truth_corr),
        "generated_zero_variance_layers": generated_degenerate,
        "truth_zero_variance_layers": truth_degenerate,
    }
    if truth_half_a is not None and truth_half_b is not None:
        half_a, _ = layer_correlation(truth_half_a)
        half_b, _ = layer_correlation(truth_half_b)
        floor = frobenius_distance(half_a, half_b)
        report["truth_half_floor_correlation_frobenius"] = floor
        report["correlation_frobenius_over_floor"] = (
            report["correlation_frobenius"] / floor if floor > 0 else None
        )
    return report
