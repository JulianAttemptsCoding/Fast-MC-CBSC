"""Layer correlation, transitions, truth halves and stratified bootstrap."""

from __future__ import annotations

import numpy as np
import pytest
import torch

from cbsc_zdc.eval.correlations import (
    activity_transition_matrix,
    bootstrap_interval,
    correlation_report,
    count_transition_correlation,
    deterministic_truth_halves,
    frobenius_distance,
    layer_correlation,
    layer_covariance,
    stratified_bootstrap_indices,
)
from cbsc_zdc.eval.diversity import (
    memorization_report,
    repeated_condition_diversity,
    repeated_support_jaccard,
    support_jaccard,
)


def sample(n: int = 200, layers: int = 5, seed: int = 0) -> torch.Tensor:
    g = torch.Generator().manual_seed(seed)
    return torch.randn(n, layers, generator=g, dtype=torch.float64)


def test_covariance_and_correlation_match_numpy_fixture() -> None:
    x = sample(120, 4)
    assert torch.allclose(
        layer_covariance(x), torch.from_numpy(np.cov(x.numpy(), rowvar=False)), atol=1e-10
    )
    correlation, degenerate = layer_correlation(x)
    assert degenerate == []
    assert torch.allclose(
        correlation, torch.from_numpy(np.corrcoef(x.numpy(), rowvar=False)), atol=1e-10
    )


def test_zero_variance_layer_is_handled_and_flagged() -> None:
    x = sample(50, 4)
    x[:, 2] = 3.0  # a layer that never varies
    correlation, degenerate = layer_correlation(x)
    assert degenerate == [2]
    assert torch.isfinite(correlation).all()
    assert float(correlation[2].abs().sum()) == 0.0


def test_frobenius_distance_is_zero_for_identical_matrices() -> None:
    x = sample(60, 4)
    assert frobenius_distance(layer_covariance(x), layer_covariance(x)) == pytest.approx(0.0)


def test_activity_and_count_transitions_match_fixture() -> None:
    active = torch.tensor([[True, True, False, False]])
    matrix = activity_transition_matrix(active)
    # transitions: T->T, T->F, F->F  => each 1/3
    assert matrix[1, 1] == pytest.approx(1 / 3)
    assert matrix[1, 0] == pytest.approx(1 / 3)
    assert matrix[0, 0] == pytest.approx(1 / 3)
    assert matrix.sum() == pytest.approx(1.0)

    rising = torch.tensor([[1, 2, 3, 4], [2, 3, 4, 5]], dtype=torch.float64)
    assert count_transition_correlation(rising) == pytest.approx(1.0, abs=1e-9)


def test_truth_half_split_is_deterministic_and_disjoint() -> None:
    ids = list(range(100))
    a1, b1 = deterministic_truth_halves(ids)
    a2, b2 = deterministic_truth_halves(list(reversed(ids)))
    assert a1 == a2 and b1 == b2  # order independent
    assert not set(a1) & set(b1)  # disjoint
    assert sorted(a1 + b1) == ids  # exhaustive
    assert abs(len(a1) - len(b1)) <= 1


def test_bootstrap_preserves_energy_strata() -> None:
    strata = ["low"] * 30 + ["high"] * 10
    draws = stratified_bootstrap_indices(strata, replicates=8, seed=1)
    assert len(draws) == 8
    for draw in draws:
        assert len(draw) == len(strata)
        picked = [strata[i] for i in draw]
        # composition preserved exactly, not just approximately
        assert picked.count("low") == 30
        assert picked.count("high") == 10


def test_bootstrap_interval_brackets_the_mean() -> None:
    values = [float(v) for v in range(100)]
    interval = bootstrap_interval(values, confidence=0.95)
    assert interval["low"] < interval["mean"] < interval["high"]
    assert interval["replicates"] == 100
    assert bootstrap_interval([])["replicates"] == 0


def test_correlation_report_includes_a_truth_half_floor() -> None:
    generated, truth = sample(150, 5, seed=1), sample(150, 5, seed=2)
    half_a, half_b = sample(75, 5, seed=3), sample(75, 5, seed=4)
    report = correlation_report(generated, truth, truth_half_a=half_a, truth_half_b=half_b)
    assert report["correlation_frobenius"] > 0
    assert report["truth_half_floor_correlation_frobenius"] > 0
    assert report["correlation_frobenius_over_floor"] is not None


def test_support_jaccard_and_collapse_detection() -> None:
    a = torch.tensor([[True, True, False, False]])
    b = torch.tensor([[True, False, True, False]])
    assert float(support_jaccard(a, b)) == pytest.approx(1 / 3)

    identical = torch.ones(4, 6, dtype=torch.bool)
    collapsed = repeated_support_jaccard(identical)
    assert collapsed["mean_jaccard"] == pytest.approx(1.0)  # total collapse
    assert collapsed["pairs"] == 6


def test_repeated_condition_diversity_reports_spread() -> None:
    g = torch.Generator().manual_seed(5)
    draws = torch.randn(8, 12, generator=g, dtype=torch.float64)
    report = repeated_condition_diversity(draws)
    assert report["repeats"] == 8
    assert report["mean_cell_std"] > 0
    assert report["min_pairwise_distance"] > 0
    identical = torch.ones(4, 12, dtype=torch.float64)
    assert repeated_condition_diversity(identical)["mean_pairwise_distance"] == pytest.approx(0.0)


def test_memorization_report_compares_against_the_truth_floor() -> None:
    g = torch.Generator().manual_seed(6)
    train = torch.randn(40, 8, generator=g, dtype=torch.float64)
    # a generator that copies training rows sits below the truth-to-truth floor
    copied = train[:10].clone()
    report = memorization_report(copied, train)
    assert report["generated_to_train_nn_mean"] == pytest.approx(0.0)
    assert report["below_truth_floor"] is True

    # A generator that is clearly *not* copying sits above the floor. An offset
    # is used rather than an independent draw from the same distribution: at
    # n=10 in 8 dimensions the latter lands on either side of the floor by
    # chance, which would make this assertion a coin flip rather than a check.
    distinct = torch.randn(10, 8, generator=g, dtype=torch.float64) + 25.0
    healthy = memorization_report(distinct, train)
    assert healthy["generated_to_train_nn_mean"] > healthy["truth_to_train_nn_floor_mean"]
    assert healthy["below_truth_floor"] is False
    assert healthy["ratio_to_floor"] > 1.0
