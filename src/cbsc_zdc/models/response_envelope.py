"""Train-only maximum-response envelope for the bounded response spline.

The v3 response head maps a positive total response ``T`` onto ``r_T = T/C(K)``
in the open unit interval, so it needs an upper bound ``C(K)`` that is known
from *training data only*.

``C`` is built on 25-GeV kinetic-energy bins from 0 to 300 GeV::

    m_j = max positive training response in bin j
    c_j = max(1e-6 GeV, 1.10 * m_j + 1e-6 GeV)
    C_j = max_{h <= j} c_h            (monotone cumulative maximum)

The cumulative maximum makes ``C`` nondecreasing in energy, which keeps the
bound physically sensible across bins with sparse statistics.

This envelope is a **numerical support contract, not a physical claim**.  It
does not assert that larger responses are impossible.  A validation response
above the envelope is reported as an out-of-support finding and is never
clipped or hidden -- clipping would manufacture agreement.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable, Sequence
from typing import Any

BIN_WIDTH_GEV = 25.0
KINETIC_LOW_GEV = 0.0
KINETIC_HIGH_GEV = 300.0
MAX_MARGIN_FACTOR = 1.10
ADDITIVE_MARGIN_GEV = 1e-6
MIN_CAP_GEV = 1e-6
ALGORITHM_VERSION = "v3-response-envelope-1"


class ResponseEnvelopeError(ValueError):
    """Raised when an envelope would be unsound for production use."""


def bin_edges() -> list[float]:
    n = int(round((KINETIC_HIGH_GEV - KINETIC_LOW_GEV) / BIN_WIDTH_GEV))
    return [KINETIC_LOW_GEV + i * BIN_WIDTH_GEV for i in range(n + 1)]


def bin_index(kinetic_gev: float) -> int:
    """Bin for one kinetic energy.

    ``K = 300`` belongs to the last bin rather than opening a new one.
    """
    edges = bin_edges()
    n_bins = len(edges) - 1
    if kinetic_gev < KINETIC_LOW_GEV:
        raise ResponseEnvelopeError(f"kinetic energy {kinetic_gev} below the declared support")
    if kinetic_gev > KINETIC_HIGH_GEV:
        raise ResponseEnvelopeError(f"kinetic energy {kinetic_gev} above the declared support")
    index = int((kinetic_gev - KINETIC_LOW_GEV) // BIN_WIDTH_GEV)
    return min(index, n_bins - 1)


def build_response_envelope(
    samples: Iterable[tuple[float, float, bool]],
    *,
    split: str = "train",
    source_hashes: dict[str, str] | None = None,
    require_full_support: bool = True,
) -> dict[str, Any]:
    """Build the envelope from ``(kinetic_gev, total_response_gev, visible)`` rows.

    Only visible events contribute a maximum.  ``require_full_support`` makes an
    empty bin fatal, which is the production requirement; a pilot or fixture
    envelope may relax it explicitly and is then marked non-production.
    """
    if split != "train":
        raise ResponseEnvelopeError(
            f"the response envelope may only be built from train; got {split!r}"
        )
    edges = bin_edges()
    n_bins = len(edges) - 1
    maxima = [0.0] * n_bins
    counts = [0] * n_bins
    visible_counts = [0] * n_bins

    for kinetic_gev, total_gev, visible in samples:
        index = bin_index(float(kinetic_gev))
        counts[index] += 1
        if not visible:
            continue
        value = float(total_gev)
        if not math.isfinite(value):
            raise ResponseEnvelopeError("nonfinite response in the training population")
        if value <= 0.0:
            raise ResponseEnvelopeError(
                "a visible training event has a nonpositive response; the hurdle "
                "and the positive branch disagree"
            )
        visible_counts[index] += 1
        maxima[index] = max(maxima[index], value)

    empty = [i for i, c in enumerate(visible_counts) if c == 0]
    if empty and require_full_support:
        raise ResponseEnvelopeError(
            f"production response envelope has empty bins: {empty}; "
            "an empty bin cannot bound the response there"
        )

    caps: list[float] = []
    running = 0.0
    for index in range(n_bins):
        raw = MAX_MARGIN_FACTOR * maxima[index] + ADDITIVE_MARGIN_GEV
        cap = max(MIN_CAP_GEV, raw)
        running = max(running, cap)
        caps.append(running)

    envelope = {
        "schema_version": 1,
        "kind": "cbsc-zdc-v3-response-envelope",
        "algorithm_version": ALGORITHM_VERSION,
        "source_split": split,
        "bin_width_gev": BIN_WIDTH_GEV,
        "bin_edges_gev": edges,
        "raw_maxima_gev": maxima,
        "monotone_caps_gev": caps,
        "event_counts": counts,
        "visible_event_counts": visible_counts,
        "empty_visible_bins": empty,
        "production_ready": not empty,
        "max_margin_factor": MAX_MARGIN_FACTOR,
        "additive_margin_gev": ADDITIVE_MARGIN_GEV,
        "source_hashes": dict(source_hashes or {}),
        "note": (
            "numerical support contract for the bounded response spline; not a "
            "claim that larger physical responses are impossible"
        ),
    }
    envelope["envelope_sha256"] = hashlib.sha256(
        json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return envelope


def cap_for_kinetic(envelope: dict[str, Any], kinetic_gev: float) -> float:
    return float(envelope["monotone_caps_gev"][bin_index(float(kinetic_gev))])


def caps_for_kinetic(envelope: dict[str, Any], kinetic_gev: Sequence[float]) -> list[float]:
    return [cap_for_kinetic(envelope, float(k)) for k in kinetic_gev]


def rescan_training_population(
    envelope: dict[str, Any], samples: Iterable[tuple[float, float, bool]]
) -> dict[str, Any]:
    """Assert every visible training response is strictly inside its cap.

    The spline has no clamp, so a training target at or above the cap is a fatal
    train-contract error rather than something to squeeze into range.
    """
    exceedances = []
    checked = 0
    for kinetic_gev, total_gev, visible in samples:
        if not visible:
            continue
        checked += 1
        cap = cap_for_kinetic(envelope, float(kinetic_gev))
        if not 0.0 < float(total_gev) < cap:
            exceedances.append(
                {"kinetic_gev": float(kinetic_gev), "total_gev": float(total_gev), "cap_gev": cap}
            )
    if exceedances:
        raise ResponseEnvelopeError(
            f"{len(exceedances)} visible training events are not strictly inside "
            f"their cap; first={exceedances[0]}"
        )
    return {"visible_events_checked": checked, "training_envelope_exceedances": 0}


def report_out_of_support(
    envelope: dict[str, Any], samples: Iterable[tuple[float, float, bool]], *, split: str
) -> dict[str, Any]:
    """Report -- never clip -- responses outside the train-built envelope.

    Used for validation.  An out-of-support validation event is a finding about
    the envelope's coverage, not a value to be modified.
    """
    findings = []
    checked = 0
    for kinetic_gev, total_gev, visible in samples:
        if not visible:
            continue
        checked += 1
        cap = cap_for_kinetic(envelope, float(kinetic_gev))
        if float(total_gev) >= cap:
            findings.append(
                {"kinetic_gev": float(kinetic_gev), "total_gev": float(total_gev), "cap_gev": cap}
            )
    return {
        "split": split,
        "visible_events_checked": checked,
        "out_of_support_events": len(findings),
        "out_of_support_fraction": (len(findings) / checked) if checked else 0.0,
        "examples": findings[:20],
        "clipped": False,
        "disposition": "reported as an out-of-support finding; values are never clipped",
    }
