"""Train-only 25-GeV maximum-response envelope."""

from __future__ import annotations

import pytest

from cbsc_zdc.models.response_envelope import (
    ADDITIVE_MARGIN_GEV,
    MAX_MARGIN_FACTOR,
    ResponseEnvelopeError,
    bin_edges,
    bin_index,
    build_response_envelope,
    cap_for_kinetic,
    report_out_of_support,
    rescan_training_population,
)


def full_support(scale: float = 1.0):
    """One visible event in every 25-GeV bin."""
    rows = []
    for low in range(0, 300, 25):
        centre = low + 12.5
        rows.append((centre, scale * (low + 25.0), True))
    return rows


def test_assignment_uses_train_ids_only() -> None:
    with pytest.raises(ResponseEnvelopeError, match="only be built from train"):
        build_response_envelope(full_support(), split="validation")
    with pytest.raises(ResponseEnvelopeError, match="only be built from train"):
        build_response_envelope(full_support(), split="test")
    build_response_envelope(full_support(), split="train")


def test_bins_are_25gev_and_include_300_in_last_bin() -> None:
    edges = bin_edges()
    assert edges[0] == 0.0 and edges[-1] == 300.0
    assert len(edges) - 1 == 12
    assert all(abs((b - a) - 25.0) < 1e-12 for a, b in zip(edges, edges[1:]))
    assert bin_index(0.0) == 0
    assert bin_index(24.999) == 0
    assert bin_index(25.0) == 1
    # 300 belongs to the last bin rather than opening a thirteenth.
    assert bin_index(300.0) == 11
    assert bin_index(299.9) == 11
    with pytest.raises(ResponseEnvelopeError):
        bin_index(300.1)
    with pytest.raises(ResponseEnvelopeError):
        bin_index(-0.1)


def test_caps_are_cumulative_nondecreasing() -> None:
    # A deliberately non-monotone set of maxima must still yield monotone caps.
    rows = []
    for i, low in enumerate(range(0, 300, 25)):
        peak = 100.0 if i == 3 else 10.0
        rows.append((low + 12.5, peak, True))
    envelope = build_response_envelope(rows, split="train")
    caps = envelope["monotone_caps_gev"]
    assert all(b >= a for a, b in zip(caps, caps[1:])), caps
    # once bin 3 sets a high cap it never drops back
    assert caps[4] == caps[3] == pytest.approx(MAX_MARGIN_FACTOR * 100.0 + ADDITIVE_MARGIN_GEV)


def test_every_visible_training_response_is_strictly_below_cap() -> None:
    rows = full_support()
    envelope = build_response_envelope(rows, split="train")
    result = rescan_training_population(envelope, rows)
    assert result["training_envelope_exceedances"] == 0
    assert result["visible_events_checked"] == len(rows)
    for kinetic, total, _ in rows:
        assert 0.0 < total < cap_for_kinetic(envelope, kinetic)


def test_a_training_response_at_or_above_the_cap_is_fatal() -> None:
    rows = full_support()
    envelope = build_response_envelope(rows, split="train")
    poisoned = rows + [(12.5, cap_for_kinetic(envelope, 12.5), True)]
    with pytest.raises(ResponseEnvelopeError, match="strictly inside"):
        rescan_training_population(envelope, poisoned)


def test_empty_production_bin_is_fatal() -> None:
    rows = [r for r in full_support() if bin_index(r[0]) != 5]
    with pytest.raises(ResponseEnvelopeError, match="empty bins"):
        build_response_envelope(rows, split="train")
    relaxed = build_response_envelope(rows, split="train", require_full_support=False)
    assert relaxed["production_ready"] is False
    assert 5 in relaxed["empty_visible_bins"]


def test_an_invisible_event_does_not_contribute_a_maximum() -> None:
    rows = full_support() + [(12.5, 10_000.0, False)]
    envelope = build_response_envelope(rows, split="train")
    assert envelope["raw_maxima_gev"][0] == pytest.approx(25.0)


def test_a_visible_nonpositive_training_response_is_fatal() -> None:
    rows = full_support() + [(12.5, 0.0, True)]
    with pytest.raises(ResponseEnvelopeError, match="nonpositive"):
        build_response_envelope(rows, split="train")


def test_validation_out_of_support_is_reported_not_clipped() -> None:
    envelope = build_response_envelope(full_support(), split="train")
    over = cap_for_kinetic(envelope, 12.5) * 2.0
    report = report_out_of_support(
        envelope, [(12.5, 1.0, True), (12.5, over, True)], split="validation"
    )
    assert report["out_of_support_events"] == 1
    assert report["clipped"] is False
    assert report["examples"][0]["total_gev"] == pytest.approx(over)
    # the reported value is the original, unmodified response
    assert report["examples"][0]["total_gev"] > report["examples"][0]["cap_gev"]


def test_envelope_is_hashed_and_records_provenance() -> None:
    envelope = build_response_envelope(
        full_support(), split="train", source_hashes={"splits_sha256": "a" * 64}
    )
    assert len(envelope["envelope_sha256"]) == 64
    assert envelope["source_hashes"]["splits_sha256"] == "a" * 64
    assert envelope["source_split"] == "train"
    assert envelope["production_ready"] is True
