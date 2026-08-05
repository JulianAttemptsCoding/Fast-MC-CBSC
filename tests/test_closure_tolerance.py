"""Contracts for the energy-scaled closure tolerance.

`dicos-p10` died at epoch 40 of a 39..62 horizon because one visual condition of
fifty reported `layer_closure_max_gev` 2.6702880859375e-05 against an absolute
2e-5, with every structural field exactly zero. That residual is seven float32
units in the last place at the event's 33.1646 GeV magnitude: the error floor of
summing thousands of float32 cells, not a model defect.

The measured evidence, from the 100 per-position rows of
`_diag/dicos-p10/viz_invariants_epoch_{0040,0039_control}.json`:

    residual / ULP(total_response)   max 7      p99 7     p95 5    median 1
    residual / total_response        max 8.052e-07        median 8.377e-08

The residual is ULP-quantized, so it scales with the magnitude being compared
while the tolerance bounding it did not. These tests pin the correction and,
just as importantly, pin that the correction stays far below any residual a
genuine decoder defect would produce.
"""

from __future__ import annotations

import math

import pytest

torch = pytest.importorskip("torch")

from cbsc_zdc.eval.invariants import invariant_report  # noqa: E402


#: The exact residual and magnitude that ended dicos-p10, from
#: audit/p10_failure_20260804_terminal_analysis.json.
P10_RESIDUAL_GEV = 2.6702880859375e-05
P10_RESPONSE_GEV = 33.164573669433594

#: The frozen absolute floor. Unchanged by this work.
ABSOLUTE_FLOOR_GEV = 2e-5

#: The declared relative term. 1e-5 sits 12x above the largest measured float32
#: residual (8.052e-07 relative) and roughly two orders of magnitude below the
#: smallest residual a single mis-decoded cell could produce.
RELATIVE = 1e-5


class _Output:
    """Minimal stand-in for `CBSCOutput` carrying only what the report reads."""

    def __init__(self, cell_energy, layer_energy, total_response):
        self.cell_energy = cell_energy
        self.layer_energy = layer_energy
        self.total_response = total_response
        self.support_mask = cell_energy > 0
        counts = self.support_mask.long().sum(dim=1, keepdim=True)
        self.realized_counts = counts
        self.requested_counts = counts


def _single_layer_case(residual_gev: float, response_gev: float):
    """One event, one layer, whose cell sum misses its budget by `residual_gev`.

    The cells carry the whole response so that `total_response` is the magnitude
    the float32 reduction actually ran over, which is the scale the measured
    ULP counts were taken against.
    """
    cell = torch.tensor([[response_gev]], dtype=torch.float64)
    layer_energy = torch.tensor([[response_gev - residual_gev]], dtype=torch.float64)
    total = torch.tensor([response_gev], dtype=torch.float64)
    layer_index = torch.zeros(1, dtype=torch.long)
    valid_mask = torch.ones(1, dtype=torch.bool)
    return _Output(cell, layer_energy, total), layer_index, valid_mask


def _report(residual_gev, response_gev, *, relative):
    output, layer_index, valid_mask = _single_layer_case(residual_gev, response_gev)
    return invariant_report(
        output=output,
        layer_index=layer_index,
        valid_mask=valid_mask,
        threshold_gev=0.0,
        tolerance=ABSOLUTE_FLOOR_GEV,
        relative_tolerance=relative,
    )


def test_default_relative_tolerance_reproduces_the_historical_absolute_behaviour():
    """Zero relative term must leave every pre-2026-08-05 run bit-reproducible.

    Old frozen configs do not carry the new key, so the default decides whether
    they still mean what they meant. It must reject p10's residual exactly as
    the run that died did.
    """
    report = _report(P10_RESIDUAL_GEV, P10_RESPONSE_GEV, relative=0.0)
    assert report["layer_closure_max_gev"] == pytest.approx(P10_RESIDUAL_GEV)
    assert report["closure_tolerance_effective_gev"] == ABSOLUTE_FLOOR_GEV
    assert report["pass"] is False


def test_default_is_zero_when_the_caller_omits_the_relative_term_entirely():
    output, layer_index, valid_mask = _single_layer_case(
        P10_RESIDUAL_GEV, P10_RESPONSE_GEV
    )
    report = invariant_report(
        output=output,
        layer_index=layer_index,
        valid_mask=valid_mask,
        tolerance=ABSOLUTE_FLOOR_GEV,
    )
    assert report["closure_tolerance_relative"] == 0.0
    assert report["closure_tolerance_effective_gev"] == ABSOLUTE_FLOOR_GEV
    assert report["pass"] is False


def test_the_declared_relative_term_admits_the_residual_that_killed_p10():
    report = _report(P10_RESIDUAL_GEV, P10_RESPONSE_GEV, relative=RELATIVE)
    expected = RELATIVE * P10_RESPONSE_GEV
    assert report["closure_tolerance_effective_gev"] == pytest.approx(expected)
    assert report["pass"] is True
    # Headroom is the point: admitting it by a hair would only move the coin
    # flip, not remove it.
    assert expected / P10_RESIDUAL_GEV > 10


def test_the_report_records_every_term_so_a_verdict_can_be_recomputed():
    report = _report(P10_RESIDUAL_GEV, P10_RESPONSE_GEV, relative=RELATIVE)
    assert report["closure_tolerance_absolute_gev"] == ABSOLUTE_FLOOR_GEV
    assert report["closure_tolerance_relative"] == RELATIVE
    assert report["closure_scale_gev"] == pytest.approx(P10_RESPONSE_GEV)
    assert report["closure_tolerance_effective_gev"] == pytest.approx(
        max(ABSOLUTE_FLOOR_GEV, RELATIVE * P10_RESPONSE_GEV)
    )


def test_a_deliberately_negative_tolerance_is_not_raised_to_zero():
    """A negative absolute tolerance must stay negative and reject everything.

    `tests/test_epoch_visualization.py` forces the invariant decision to fail by
    setting `closure_tolerance_gev` to -1.0 without touching the production
    threshold. A naive `max(absolute, relative * scale)` lifts that to 0.0 when
    the relative term is zero, which makes an exact-zero residual pass and
    silently disarms that test. This pins the guard both ways.
    """
    for relative in (0.0, RELATIVE):
        report = _report(0.0, 5.0, relative=relative)
        report_negative = invariant_report(
            output=_single_layer_case(0.0, 5.0)[0],
            layer_index=_single_layer_case(0.0, 5.0)[1],
            valid_mask=_single_layer_case(0.0, 5.0)[2],
            threshold_gev=0.0,
            tolerance=-1.0,
            relative_tolerance=relative,
        )
        assert report["pass"] is True
        if relative == 0.0:
            assert report_negative["closure_tolerance_effective_gev"] == -1.0
            assert report_negative["pass"] is False


def test_the_absolute_floor_still_binds_below_the_crossover():
    """Below 2 GeV the floor dominates, so low-energy events keep the old rule.

    The crossover is exactly `absolute / relative` = 2e-5 / 1e-5 = 2 GeV.
    """
    report = _report(1e-6, 1.0, relative=RELATIVE)
    assert report["closure_tolerance_effective_gev"] == ABSOLUTE_FLOOR_GEV
    assert report["pass"] is True

    too_big_for_the_floor = _report(3e-5, 1.0, relative=RELATIVE)
    assert too_big_for_the_floor["closure_tolerance_effective_gev"] == ABSOLUTE_FLOOR_GEV
    assert too_big_for_the_floor["pass"] is False


def test_a_real_decoder_defect_is_still_caught_at_every_magnitude():
    """The tolerance must stay far below a single mis-decoded cell.

    A dropped or misplaced cell shifts a layer budget by of order the cell
    energy, which is orders of magnitude above float32 noise. If this test ever
    fails the relative term has been widened into uselessness.
    """
    for response, defect in ((33.164573669433594, 0.05), (300.0, 0.5), (5.0, 0.01)):
        report = _report(defect, response, relative=RELATIVE)
        assert report["pass"] is False, (response, defect)
        assert defect / report["closure_tolerance_effective_gev"] > 15


def test_the_relative_term_tracks_the_measured_ulp_ceiling_across_the_range():
    """Seven ULP of the compared magnitude must fit at every trained energy.

    float32 ULP(x) is at most x * 2**-23, so seven ULP is at most
    8.35e-07 relative -- which is what the 100 measured rows show. The declared
    relative term must dominate that everywhere in 0..300 GeV, which an absolute
    2e-5 does not: at 300 GeV a single ULP is 3.05e-05 and already exceeds it.
    """
    seven_ulp_relative = 7 * 2.0**-23
    for response in (2.0, 10.0, 33.164573669433594, 100.0, 250.0, 300.0):
        residual = seven_ulp_relative * response
        report = _report(residual, response, relative=RELATIVE)
        assert report["pass"] is True, response

        old_rule = _report(residual, response, relative=0.0)
        if residual > ABSOLUTE_FLOOR_GEV:
            assert old_rule["pass"] is False, (
                f"{response} GeV should demonstrate the old rule failing"
            )

    # The concrete claim from the p10 analysis, restated as an executable fact.
    assert math.isclose(2.0**-18 * 7, P10_RESIDUAL_GEV, rel_tol=0, abs_tol=0)
    one_ulp_at_300 = 2.0 ** (math.floor(math.log2(300.0)) - 23)
    assert one_ulp_at_300 > ABSOLUTE_FLOOR_GEV
