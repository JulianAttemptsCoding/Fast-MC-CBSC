"""wasserstein_1d: exact, fast, and equivalent to the formulation it replaces.

The original evaluated `np.quantile` on a linspace of max(n_a, n_b) points and
measured quadratic -- 0.10 s at n=10,000, 7.29 s at 100,000, 114.41 s at
400,000. The positive-cell array of a 10,000-event validation bank holds several
million entries, which extrapolated to hours for one call and stalled the v3
battery.

Replacing it is only legitimate if it computes the same number, because every
historical per-epoch diagnostic in this project used the old one and those
values must stay comparable.
"""

from __future__ import annotations

import numpy as np
import pytest

from cbsc_zdc.eval.metrics import wasserstein_1d


def reference_grid_wasserstein(a, b):
    """The formulation being replaced, kept here as the comparison target."""
    a = np.sort(np.asarray(a, dtype=float))
    b = np.sort(np.asarray(b, dtype=float))
    if a.size == 0 or b.size == 0:
        return None
    q = np.linspace(0, 1, max(a.size, b.size))
    return float(np.trapezoid(np.abs(np.quantile(a, q) - np.quantile(b, q)), q))


@pytest.mark.parametrize("seed", [0, 1, 2, 3, 4])
def test_agrees_with_the_grid_formulation_it_replaces(seed):
    rng = np.random.default_rng(seed)
    a = rng.normal(5.0, 2.0, 4000)
    b = rng.normal(5.3, 2.2, 4000)
    assert wasserstein_1d(a, b) == pytest.approx(
        reference_grid_wasserstein(a, b), rel=2e-3
    )


def test_agrees_on_unequal_sample_sizes():
    rng = np.random.default_rng(7)
    a = rng.exponential(1.0, 3000)
    b = rng.exponential(1.4, 5000)
    assert wasserstein_1d(a, b) == pytest.approx(
        reference_grid_wasserstein(a, b), rel=5e-3
    )


def test_shifted_uniform_matches_the_analytic_answer():
    """A pure translation has W1 exactly equal to the shift."""
    grid = np.linspace(0.0, 1.0, 20001)
    assert wasserstein_1d(grid, grid + 0.25) == pytest.approx(0.25, abs=1e-4)


def test_identical_samples_are_zero():
    values = np.linspace(0.0, 10.0, 500)
    assert wasserstein_1d(values, values) == 0.0


def test_symmetric():
    rng = np.random.default_rng(11)
    a, b = rng.random(800), rng.random(1200) * 2
    assert wasserstein_1d(a, b) == pytest.approx(wasserstein_1d(b, a))


def test_nonnegative_and_finite():
    rng = np.random.default_rng(3)
    value = wasserstein_1d(rng.random(500), rng.random(700) + 3)
    assert value >= 0 and np.isfinite(value)


def test_empty_input_returns_none_not_a_fabricated_zero():
    assert wasserstein_1d([], [1.0, 2.0]) is None
    assert wasserstein_1d([1.0, 2.0], []) is None


def test_single_shared_value_is_zero():
    assert wasserstein_1d([2.0, 2.0], [2.0]) == 0.0


def test_scales_subquadratically():
    """The defect being fixed was quadratic growth, so pin the scaling itself."""
    import time

    rng = np.random.default_rng(5)

    def timed(n):
        a, b = rng.random(n), rng.random(n)
        start = time.perf_counter()
        wasserstein_1d(a, b)
        return time.perf_counter() - start

    timed(20_000)  # warm up numpy
    small = timed(50_000)
    large = timed(400_000)
    # 8x the input under the old quadratic behaviour cost ~64x. Allow a very
    # generous ceiling so this pins the complexity class, not the machine.
    assert large < max(small, 1e-3) * 25, f"small={small:.3f}s large={large:.3f}s"
