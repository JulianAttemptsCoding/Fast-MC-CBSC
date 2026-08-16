"""The v3 metric battery, wired to the frozen production validation bank.

Unit-tested metric functions that cannot consume the production validation bank
are not a battery.  `topology.py`, `correlations.py` and `diversity.py` have
been implemented and unit-tested since the v3 overlay landed, but nothing could
run them against real checkpoints, so the project could say its fidelity was bad
without being able to say *how*.  This module is the missing wiring.  It adds no
new metric formulas: every quantity is computed by the existing implementation.

Two properties matter more than the metric list.

**The evaluation bank is fixed and immutable.**  One manifest of exactly 10,000
validation conditions, selected by a documented deterministic digest order and
energy-stratified so every primary bin holds at least 500, hashed before any
checkpoint is evaluated, and reused byte-identically for every comparison.  A
battery that reselects its events per checkpoint measures the selection as much
as the model.

**It fails closed.**  Every input that can change a number -- checkpoint, frozen
config, event manifest, geometry, split hashes, seeds, bin definition, solver
steps, precision -- must be supplied explicitly or resolved from a hash-verified
frozen manifest.  Nothing defaults.  Constructing a test loader is fatal, not
discouraged.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import torch

from ..data.dataset import ShardedSparseDataset, load_geometry
from ..models.system import CBSCZDC
from ..utils import sha256_json
from .correlations import (
    bootstrap_interval,
    correlation_report,
    deterministic_truth_halves,
    stratified_bootstrap_indices,
)
from .diversity import memorization_report
from .invariants import closure_tolerances, invariant_report
from .metrics import (
    c2st_auc,
    distribution_metrics,
    high_level_features,
    layer_sums,
    response_bins,
    wasserstein_1d,
)
from .topology import topology_report

SCHEMA_VERSION = 1
REPORT_SCHEMA_VERSION = 2
MANIFEST_KIND = "cbsc-zdc-v3-fixed-validation-bank"
BATTERY_KIND = "cbsc-zdc-v3-validation-battery"

#: The frozen evaluation split. Never "test", never "train", and never a
#: parameter -- a battery that can be pointed at test is one typo from ending
#: the project's ability to make an untouched-test claim.
EVALUATION_SPLIT = "validation"

#: Frozen gate values, mirrored from configs/gates_primary.yaml. Duplicated as
#: constants only so the manifest builder can refuse to emit a bank that would
#: fail them; the gate file remains the source of truth for evaluation.
REQUIRED_PAIRS = 10_000
REQUIRED_PAIRS_PER_BIN = 500
BOOTSTRAP_REPLICATES = 1_000
BOOTSTRAP_CONFIDENCE = 0.95

#: Events used by the structural families (topology, memorization). 0 means the
#: whole bank, which is the default and the scientifically preferable setting.
#:
#: An earlier revision defaulted this to 1000 on the diagnosis that
#: `connected_components`, with its Python union-find per event, could not scale.
#: **That diagnosis was wrong and is recorded here so it is not repeated.**
#: Measured on the production graph: connected_components 5.1 s per 1,000
#: events, nearest_neighbor_distances 3.1 s, distance_binned_cooccupancy 1.0 s,
#: memorization 0.8 s -- roughly three minutes for the full bank across truth
#: and generated together.
#:
#: The real bottleneck was `wasserstein_1d`, which was quadratic and took hours
#: on the several-million-entry positive-cell array. That is fixed at the
#: source, so the structural families need no subsample. The knob remains for a
#: deliberate quick pass, and whatever it is set to is recorded in the output.
STRUCTURAL_SUBSAMPLE_EVENTS = 0

#: Selection salt. Changing it changes the bank, which is a new declared
#: experiment; it is recorded in the manifest so a bank can never be silently
#: reselected under the same name.
SELECTION_SALT = "cbsc-v3-fixed-validation-bank-20260815"

#: Everything the battery refuses to guess. Each entry is a hard input.
REQUIRED_INPUTS = (
    "checkpoint",
    "frozen_config",
    "validation_manifest",
    "geometry_manifest",
    "data_manifest_sha256",
    "splits_sha256",
    "generator_seed",
    "evaluator_seeds",
    "energy_bin_edges_gev",
    "profile_steps",
    "share_steps",
    "precision",
    "output_namespace",
    "evaluation_role",
)

#: A battery run is either a monitor or selection evidence, and it must say
#: which. Under the frozen contract nothing here may select a checkpoint, so
#: "selection" additionally requires the caller to have owner authorization
#: recorded elsewhere; the field exists so the claim is explicit in the output.
EVALUATION_ROLES = ("diagnostic", "selection")


class BatteryContractError(ValueError):
    """An input the battery refuses to infer was missing or inconsistent."""


@dataclass(frozen=True)
class BatteryRequest:
    """Every declared input, with no defaults for anything that moves a number."""

    checkpoint: Path
    frozen_config: Path
    validation_manifest: Path
    geometry_manifest: Path
    data_manifest_sha256: str
    splits_sha256: str
    generator_seed: int
    evaluator_seeds: tuple[int, ...]
    energy_bin_edges_gev: tuple[float, ...]
    profile_steps: int
    share_steps: int
    precision: str
    output_namespace: str
    evaluation_role: str
    device: str = "cpu"
    batch_size: int = 8
    bootstrap_replicates: int = BOOTSTRAP_REPLICATES
    bootstrap_confidence: float = BOOTSTRAP_CONFIDENCE
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        missing = [name for name in REQUIRED_INPUTS if not getattr(self, name, None)]
        if missing:
            raise BatteryContractError(
                "the v3 validation battery refuses to infer these inputs: "
                f"{sorted(missing)}"
            )
        if self.evaluation_role not in EVALUATION_ROLES:
            raise BatteryContractError(
                f"evaluation_role must be one of {EVALUATION_ROLES}, "
                f"got {self.evaluation_role!r}"
            )
        if len(self.evaluator_seeds) != 3:
            raise BatteryContractError(
                "exactly three external evaluator seeds are declared by the frozen "
                f"contract; got {len(self.evaluator_seeds)}"
            )
        if len(set(self.evaluator_seeds)) != 3:
            raise BatteryContractError("evaluator seeds must be distinct")
        if self.precision != "fp32":
            raise BatteryContractError(
                "the frozen contract declares FP32 execution; "
                f"got precision {self.precision!r}"
            )
        if len(self.energy_bin_edges_gev) < 2:
            raise BatteryContractError("energy_bin_edges_gev needs at least two edges")
        if list(self.energy_bin_edges_gev) != sorted(self.energy_bin_edges_gev):
            raise BatteryContractError("energy_bin_edges_gev must be increasing")
        if self.bootstrap_replicates != BOOTSTRAP_REPLICATES:
            raise BatteryContractError(
                f"the frozen contract declares {BOOTSTRAP_REPLICATES} bootstrap "
                f"replicates; got {self.bootstrap_replicates}"
            )
        if abs(self.bootstrap_confidence - BOOTSTRAP_CONFIDENCE) > 1e-12:
            raise BatteryContractError(
                f"the frozen contract declares {BOOTSTRAP_CONFIDENCE} confidence"
            )
        for path in (
            self.checkpoint, self.frozen_config,
            self.validation_manifest, self.geometry_manifest,
        ):
            if not Path(path).exists():
                raise BatteryContractError(f"declared input does not exist: {path}")


def _selection_metadata(dataset: ShardedSparseDataset):
    """Yield (event_id, kinetic_energy_gev) per dataset row, shard by shard.

    Reads only the two scalar columns the selection needs.  `__getitem__` would
    scatter a dense 6,790-channel target for each of tens of thousands of
    candidates just to read them, which is pure waste when the bank is being
    frozen rather than evaluated.  Order matches `dataset[i]` exactly, so the
    recorded `dataset_index` stays valid.
    """
    for position in range(len(dataset)):
        global_index = int(dataset.indices[position])
        shard_index, local_index = dataset._locate(global_index)
        shard = dataset._load_shard(shard_index)
        yield int(shard["event_id"][local_index]), float(
            shard["kinetic_energy_gev"][local_index]
        )


def _digest(*parts: Any) -> str:
    return hashlib.sha256(":".join(str(p) for p in parts).encode("utf-8")).hexdigest()


def _bin_label(value: float, edges: tuple[float, ...]) -> str | None:
    """Name the primary-domain bin holding this kinetic energy, or None."""
    for low, high in zip(edges, edges[1:]):
        if low <= value < high:
            return f"{low:g}-{high:g}"
    if value == edges[-1]:
        low = edges[-2]
        return f"{low:g}-{edges[-1]:g}"
    return None


def build_validation_manifest(
    *,
    data_manifest: Path,
    splits: Path,
    n_nodes: int,
    kinetic_range_gev: tuple[float, float],
    energy_bin_edges_gev: tuple[float, ...],
    output: Path,
    pairs: int = REQUIRED_PAIRS,
    pairs_per_bin: int = REQUIRED_PAIRS_PER_BIN,
    salt: str = SELECTION_SALT,
) -> dict:
    """Freeze one immutable, energy-stratified bank of validation conditions.

    Selection is a pure function of (salt, event_id): every candidate is keyed by
    its digest, bins are filled in digest order to the per-bin floor first, and
    the remainder is taken in global digest order.  The result does not depend on
    shard order, on how many workers read the data, or on when it was built.

    The bank holds `pairs` conditions.  Each contributes one held Geant4 event
    and one generated Fast-MC event, so the evaluator corpus is 2 x `pairs`
    examples -- above the frozen 10,000 minimum under either convention.
    """
    dataset = ShardedSparseDataset(
        data_manifest, splits, EVALUATION_SPLIT, kinetic_range_gev, n_nodes
    )
    # Selection needs only event_id and kinetic energy. Going through
    # __getitem__ would materialize a dense 6,790-channel target for every
    # candidate -- tens of thousands of them -- purely to read two scalars.
    candidates = []
    for index, (event_id, kinetic) in enumerate(_selection_metadata(dataset)):
        candidates.append({
            "index": index,
            "event_id": int(event_id),
            "kinetic_energy_gev": float(kinetic),
            "bin": _bin_label(float(kinetic), energy_bin_edges_gev),
            "digest": _digest(salt, int(event_id)),
        })

    by_bin: dict[str, list[dict]] = {}
    for row in candidates:
        if row["bin"] is not None:
            by_bin.setdefault(row["bin"], []).append(row)
    for rows in by_bin.values():
        rows.sort(key=lambda r: (r["digest"], r["event_id"]))

    expected_bins = [
        f"{low:g}-{high:g}"
        for low, high in zip(energy_bin_edges_gev, energy_bin_edges_gev[1:])
    ]
    short = {
        name: len(by_bin.get(name, []))
        for name in expected_bins
        if len(by_bin.get(name, [])) < pairs_per_bin
    }
    if short:
        raise BatteryContractError(
            "the validation split cannot supply the frozen per-bin floor of "
            f"{pairs_per_bin}; short bins {short}. An under-filled bin is a fatal "
            "empty-bin condition, not something to sample around."
        )

    selected: dict[int, dict] = {}
    for name in expected_bins:
        for row in by_bin[name][:pairs_per_bin]:
            selected[row["event_id"]] = row
    if len(selected) > pairs:
        raise BatteryContractError(
            f"the per-bin floor alone needs {len(selected)} conditions, "
            f"more than the declared bank size {pairs}"
        )
    remainder = sorted(
        (r for r in candidates if r["bin"] is not None and r["event_id"] not in selected),
        key=lambda r: (r["digest"], r["event_id"]),
    )
    for row in remainder:
        if len(selected) >= pairs:
            break
        selected[row["event_id"]] = row
    if len(selected) != pairs:
        raise BatteryContractError(
            f"validation split supplied {len(selected)} in-domain conditions, "
            f"fewer than the declared bank size {pairs}"
        )

    rows = sorted(selected.values(), key=lambda r: (r["digest"], r["event_id"]))
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["bin"]] = counts.get(row["bin"], 0) + 1

    payload = {
        "schema_version": SCHEMA_VERSION,
        "kind": MANIFEST_KIND,
        "split": EVALUATION_SPLIT,
        "selection_salt": salt,
        "selection_algorithm": (
            "key every in-domain validation event by sha256(salt + ':' + event_id); "
            "fill each primary energy bin to the floor in ascending (digest, event_id) "
            "order; take the remainder in global ascending (digest, event_id) order; "
            "emit sorted by (digest, event_id)"
        ),
        "pairs": len(rows),
        "geant4_examples": len(rows),
        "fastmc_examples": len(rows),
        "evaluator_corpus_examples": 2 * len(rows),
        "energy_bin_edges_gev": list(energy_bin_edges_gev),
        "kinetic_range_gev": list(kinetic_range_gev),
        "pairs_per_bin": counts,
        "minimum_pairs_per_bin": pairs_per_bin,
        "data_manifest": str(Path(data_manifest).resolve()).replace("\\", "/"),
        "splits": str(Path(splits).resolve()).replace("\\", "/"),
        "n_nodes": int(n_nodes),
        "test_events_used": 0,
        "train_events_used": 0,
        "events": [
            {
                "event_id": row["event_id"],
                "dataset_index": row["index"],
                "kinetic_energy_gev": row["kinetic_energy_gev"],
                "energy_bin": row["bin"],
            }
            for row in rows
        ],
    }
    payload["content_sha256"] = sha256_json(
        {k: v for k, v in payload.items() if k != "content_sha256"}
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )
    temporary.replace(output)
    return payload


def load_validation_manifest(path: Path) -> dict:
    """Read a frozen bank and re-derive its hash before anything uses it."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("kind") != MANIFEST_KIND:
        raise BatteryContractError(f"{path} is not a {MANIFEST_KIND}")
    if payload.get("split") != EVALUATION_SPLIT:
        raise BatteryContractError(
            f"the fixed bank declares split {payload.get('split')!r}; only "
            f"{EVALUATION_SPLIT!r} is permitted"
        )
    if payload.get("test_events_used") != 0:
        raise BatteryContractError("the fixed bank records test events")
    recorded = payload.get("content_sha256")
    actual = sha256_json({k: v for k, v in payload.items() if k != "content_sha256"})
    if recorded != actual:
        raise BatteryContractError(
            f"fixed bank hash mismatch: recorded {recorded}, actual {actual}"
        )
    if int(payload["pairs"]) < REQUIRED_PAIRS:
        raise BatteryContractError(
            f"the fixed bank holds {payload['pairs']} pairs, below the frozen "
            f"minimum of {REQUIRED_PAIRS}"
        )
    short = {
        name: count
        for name, count in payload["pairs_per_bin"].items()
        if count < int(payload["minimum_pairs_per_bin"])
    }
    if short:
        raise BatteryContractError(f"fixed bank has under-filled bins: {short}")
    return payload


def _zero_cause_decomposition(
    visible: np.ndarray, total: np.ndarray
) -> dict[str, float]:
    """Split the zero-response rate into its two mechanisms.

    A zero event is either invisible -- the visibility hurdle fired -- or visible
    with a positive branch that produced nothing.  The marginal zero rate alone
    cannot distinguish them, and the two have completely different fixes: the
    first is the visibility head, the second is the second zero atom that the
    v2.2 clamped mixture creates and the S2 bounded spline exists to remove.
    """
    zero = total <= 0.0
    invisible = ~visible.astype(bool)
    return {
        "zero_fraction": float(np.mean(zero)),
        "invisible_fraction": float(np.mean(invisible)),
        "zero_from_visibility_hurdle": float(np.mean(zero & invisible)),
        "zero_from_positive_branch": float(np.mean(zero & ~invisible)),
    }


def _first_layer_report(
    layer_energy: np.ndarray, ecal_layers: int
) -> dict[str, float]:
    """ECAL-start prevalence and layer-0 energy, the S3 target family."""
    active = layer_energy > 0.0
    has_any = active.any(axis=1)
    first = np.where(has_any, active.argmax(axis=1), -1)
    started_in_ecal = (first >= 0) & (first < ecal_layers)
    return {
        "ecal_start_prevalence": float(np.mean(started_in_ecal[has_any]))
        if has_any.any() else 0.0,
        "mean_first_active_layer": float(np.mean(first[has_any]))
        if has_any.any() else 0.0,
        "layer_zero_mean_energy_gev": float(np.mean(layer_energy[:, 0])),
        "events_with_no_active_layer": int(np.sum(~has_any)),
    }


def _activity_report(layer_energy: np.ndarray) -> dict[str, float]:
    active = layer_energy > 0.0
    counts = active.sum(axis=1)
    has_any = counts > 0
    first = np.where(has_any, active.argmax(axis=1), 0)
    last = np.where(has_any, active.shape[1] - 1 - active[:, ::-1].argmax(axis=1), 0)
    span = np.where(has_any, last - first + 1, 0)
    gaps = np.where(has_any, span - counts, 0)
    return {
        "mean_active_layers": float(np.mean(counts)),
        "mean_span": float(np.mean(span[has_any])) if has_any.any() else 0.0,
        "mean_gaps": float(np.mean(gaps[has_any])) if has_any.any() else 0.0,
        "gap_fraction": float(np.mean(gaps[has_any] > 0)) if has_any.any() else 0.0,
        "mean_last_active_layer": float(np.mean(last[has_any])) if has_any.any() else 0.0,
    }


def _count_report(cell_energy: np.ndarray, layer_index: np.ndarray) -> dict[str, float]:
    hits = (cell_energy > 0.0)
    per_event = hits.sum(axis=1)
    total = cell_energy.sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        per_hit = np.where(per_event > 0, total / np.maximum(per_event, 1), 0.0)
    return {
        "mean_hit_count": float(np.mean(per_event)),
        "hit_count_std": float(np.std(per_event)),
        "mean_energy_per_hit_gev": float(np.mean(per_hit[per_event > 0]))
        if (per_event > 0).any() else 0.0,
    }


def _paired_response_report(
    kinetic: np.ndarray, truth_total: np.ndarray, generated_total: np.ndarray
) -> dict[str, float]:
    """Paired response residual normalized by incident kinetic energy.

    A detector can have zero or arbitrarily small deposited truth response, so
    dividing by the event's truth deposit is undefined or numerically unstable.
    The fixed bank is restricted to positive 50--250 GeV incident kinetic
    energy, which is the predeclared conditioning scale and is never selected
    from model output. This is a paired response diagnostic, not downstream
    four-momentum reconstruction accuracy.
    """
    kinetic = np.asarray(kinetic, dtype=float)
    if len(kinetic) == 0 or np.any(~np.isfinite(kinetic)) or np.any(kinetic <= 0):
        raise BatteryContractError(
            "paired response normalization requires finite positive kinetic energy"
        )
    normalized = (generated_total - truth_total) / kinetic
    return {
        "kind": "paired_detector_response_residual",
        "normalization": "incident_kinetic_energy_gev",
        "response_delta_over_kinetic_rmse": float(
            np.sqrt(np.mean(normalized ** 2))
        ),
        "response_delta_over_kinetic_mean": float(np.mean(normalized)),
        "response_delta_over_kinetic_median_absolute": float(
            np.median(np.abs(normalized))
        ),
        "events_included": int(len(kinetic)),
        "zero_truth_events": int(np.sum(truth_total <= 0)),
        "mean_kinetic_gev": float(np.mean(kinetic)),
        "interpretation": (
            "paired stochastic response residual; not downstream reconstruction"
        ),
    }


def _truth_half_floor(
    truth_total: np.ndarray, event_ids: list[int], metric
) -> float:
    """Deterministic truth-vs-truth floor for a distance family.

    Every distance between two finite samples is positive even when both are
    drawn from the same distribution.  Reporting a Fast-MC distance without this
    floor invites reading sampling noise as a physics discrepancy.
    """
    left, right = deterministic_truth_halves(event_ids)
    position = {event: index for index, event in enumerate(event_ids)}
    a = truth_total[[position[e] for e in left]]
    b = truth_total[[position[e] for e in right]]
    if len(a) == 0 or len(b) == 0:
        return 0.0
    return float(metric(a, b))


def battery_report(
    *,
    request: BatteryRequest,
    bank: dict,
    truth: np.ndarray,
    generated: np.ndarray,
    kinetic: np.ndarray,
    truth_visible: np.ndarray,
    generated_visible: np.ndarray,
    event_ids: list[int],
    strata: list[str],
    layer_index: np.ndarray,
    positions: np.ndarray,
    ecal_layers: int,
    invariants: dict,
    edge_index: torch.Tensor | None = None,
    train_reference: np.ndarray | None = None,
    structural_events: int = STRUCTURAL_SUBSAMPLE_EVENTS,
    timing: dict | None = None,
    verbose: bool = True,
) -> dict:
    """Assemble every metric family over an already-generated paired sample."""
    stage = StageTimer(verbose)
    truth_total = truth.sum(axis=1)
    generated_total = generated.sum(axis=1)
    truth_layers = stage("layer_sums truth", lambda: layer_sums(truth, layer_index))
    generated_layers = stage("layer_sums generated", lambda: layer_sums(generated, layer_index))
    edges = np.array(request.energy_bin_edges_gev)

    # C2ST, reported per family and never merged. The frozen 0.65 diagnostic is
    # named max_high_level_c2st_auc and applies to the high-level family alone.
    truth_high = stage("high_level_features truth",
                       lambda: high_level_features(truth, layer_index, positions))
    generated_high = stage("high_level_features generated",
                           lambda: high_level_features(generated, layer_index, positions))
    c2st = stage("c2st all families", lambda: {
        "high_level": {
            "auroc_per_seed": [
                float(c2st_auc(truth_high, generated_high, seed))
                for seed in request.evaluator_seeds
            ],
            "gate": "max_high_level_c2st_auc",
            "gate_value": 0.65,
        },
        "low_level": {
            "auroc_per_seed": [
                float(c2st_auc(truth, generated, seed))
                for seed in request.evaluator_seeds
            ],
            "gate": None,
            "note": "no frozen project gate; the D1/D2 promotion rule names this family",
        },
        "profile_aware": {
            "auroc_per_seed": [
                float(c2st_auc(truth_layers, generated_layers, seed))
                for seed in request.evaluator_seeds
            ],
            "gate": None,
        },
        "condition_only": {
            "auroc_per_seed": [
                float(c2st_auc(
                    kinetic.reshape(-1, 1), kinetic.reshape(-1, 1), seed
                ))
                for seed in request.evaluator_seeds
            ],
            "gate": None,
            "note": "sanity control; must sit at chance",
        },
    })
    for family in c2st.values():
        values = family["auroc_per_seed"]
        family["auroc_mean"] = float(np.mean(values))
        family["auroc_std"] = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0

    response_wasserstein = stage("response wasserstein",
                                 lambda: wasserstein_1d(truth_total, generated_total))
    hits_truth = (truth > 0).sum(axis=1).astype(float)
    hits_generated = (generated > 0).sum(axis=1).astype(float)

    # Paired, energy-stratified bootstrap over the declared replicate count.
    draws = stage("bootstrap draws", lambda: stratified_bootstrap_indices(
        strata, request.bootstrap_replicates, seed=request.generator_seed
    ))
    bootstrapped: dict[str, list[float]] = {
        "response_wasserstein_gev": [],
        "hit_count_wasserstein": [],
        "response_delta_over_kinetic_mean": [],
        "zero_fraction_difference": [],
    }
    bootstrap_start = __import__("time").perf_counter()
    for draw in draws:
        picks = np.array(draw)
        bootstrapped["response_wasserstein_gev"].append(
            float(wasserstein_1d(truth_total[picks], generated_total[picks]))
        )
        bootstrapped["hit_count_wasserstein"].append(
            float(wasserstein_1d(hits_truth[picks], hits_generated[picks]))
        )
        bootstrapped["response_delta_over_kinetic_mean"].append(
            float(np.mean(
                (generated_total[picks] - truth_total[picks]) / kinetic[picks]
            ))
        )
        bootstrapped["zero_fraction_difference"].append(
            float(np.mean(generated_total[picks] <= 0) - np.mean(truth_total[picks] <= 0))
        )
    stage.seconds["bootstrap replicates"] = (
        __import__("time").perf_counter() - bootstrap_start
    )
    if verbose:
        print(f"[battery] {'bootstrap replicates':34s} "
              f"{stage.seconds['bootstrap replicates']:8.1f} s", flush=True)
    intervals = {
        name: bootstrap_interval(values, request.bootstrap_confidence)
        for name, values in bootstrapped.items()
    }

    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "kind": BATTERY_KIND,
        "identity": {
            "checkpoint": str(request.checkpoint).replace("\\", "/"),
            "frozen_config": str(request.frozen_config).replace("\\", "/"),
            "validation_manifest": str(request.validation_manifest).replace("\\", "/"),
            "validation_manifest_sha256": bank["content_sha256"],
            "geometry_manifest": str(request.geometry_manifest).replace("\\", "/"),
            "data_manifest_sha256": request.data_manifest_sha256,
            "splits_sha256": request.splits_sha256,
            "generator_seed": request.generator_seed,
            "evaluator_seeds": list(request.evaluator_seeds),
            "energy_bin_edges_gev": list(request.energy_bin_edges_gev),
            "profile_steps": request.profile_steps,
            "share_steps": request.share_steps,
            "precision": request.precision,
            "batch_size": request.batch_size,
            "device": request.device,
            "output_namespace": request.output_namespace,
            "evaluation_role": request.evaluation_role,
            **request.metadata,
        },
        "split": EVALUATION_SPLIT,
        "pairs": int(len(truth)),
        "evaluator_corpus_examples": int(2 * len(truth)),
        "test_events_used": 0,
        "train_events_used": 0,
        "structural_invariants": invariants,
        "visibility_and_zero_response": {
            "truth": _zero_cause_decomposition(truth_visible, truth_total),
            "generated": _zero_cause_decomposition(generated_visible, generated_total),
        },
        "positive_response": {
            "truth_mean_gev": float(np.mean(truth_total[truth_total > 0]))
            if (truth_total > 0).any() else 0.0,
            "generated_mean_gev": float(np.mean(generated_total[generated_total > 0]))
            if (generated_total > 0).any() else 0.0,
            "response_bins": response_bins(kinetic, truth_total, generated_total, edges),
            "response_wasserstein_gev": float(response_wasserstein),
            "response_wasserstein_normalized": float(
                response_wasserstein / max(np.std(truth_total), 1e-9)
            ),
        },
        "first_layer": {
            "truth": _first_layer_report(truth_layers, ecal_layers),
            "generated": _first_layer_report(generated_layers, ecal_layers),
        },
        "activity": {
            "truth": _activity_report(truth_layers),
            "generated": _activity_report(generated_layers),
        },
        "counts": {
            "truth": _count_report(truth, layer_index),
            "generated": _count_report(generated, layer_index),
            "hit_count_wasserstein": float(wasserstein_1d(hits_truth, hits_generated)),
        },
        "correlations": correlation_report(
            torch.from_numpy(generated_layers).float(),
            torch.from_numpy(truth_layers).float(),
            **_truth_half_tensors(truth_layers, event_ids),
        ),
        "distribution_metrics": stage("distribution_metrics", lambda: distribution_metrics(
            truth, generated, layer_index, positions, request.generator_seed
        )),
        "c2st": c2st,
        "paired_response": _paired_response_report(
            kinetic, truth_total, generated_total
        ),
        "bootstrap": {
            "replicates": request.bootstrap_replicates,
            "confidence": request.bootstrap_confidence,
            "stratified_by": "primary energy bin",
            "paired": True,
            "intervals": intervals,
        },
        "truth_half_floors": {
            "response_wasserstein_gev": _truth_half_floor(
                truth_total, event_ids, wasserstein_1d
            ),
            "hit_count_wasserstein": _truth_half_floor(
                hits_truth, event_ids, wasserstein_1d
            ),
            "meaning": (
                "deterministic truth-versus-truth distance on two disjoint halves of "
                "the same bank; a Fast-MC distance at or below its floor is not "
                "distinguishable from sampling noise"
            ),
        },
        "timing": {**(timing or {}), "stage_seconds": stage.seconds},
        "selection_role": (
            "descriptive validation evidence"
            if request.evaluation_role == "diagnostic"
            else "declared selection evidence"
        ),
        "scientific_status": "PHYSICS VALIDATION NOT ESTABLISHED",
    }
    if edge_index is not None:
        picks = structural_subsample(len(truth), structural_events)
        index = np.array(picks)
        position_tensor = torch.from_numpy(positions).float()
        # Every structural input here is built from numpy and therefore lives on
        # the CPU, while `model.edge_index` is on whatever device the model was
        # loaded to. `connected_components` indexes one with the other, so a
        # CUDA edge_index raises "indices should be either on cpu or on the same
        # device as the indexed tensor" and kills the run after an hour of
        # completed work. Coerce once, here, rather than at each call site.
        edge_index = edge_index.detach().cpu()
        # topology_report takes one support set, so truth and generated are
        # measured separately and compared here. The truth column IS the floor
        # for this family: these are structural counts, not distances, so a
        # deterministic truth-truth split would not bound them.
        report["topology"] = {
            "generated": stage("topology generated", lambda: topology_report(
                torch.from_numpy(generated[index] > 0), position_tensor, edge_index
            )),
            "truth": stage("topology truth", lambda: topology_report(
                torch.from_numpy(truth[index] > 0), position_tensor, edge_index
            )),
            "subsample_events": len(picks),
            "subsample_rule": (
                "evenly spaced stride over the frozen bank, preserving its energy "
                "composition; a pure function of (bank size, subsample size)"
            ),
            "subsample_reason": (
                "0 means the whole bank, which is the default. The knob exists for a "
                "deliberate quick pass; the structural families are fast enough for "
                "the full bank once wasserstein_1d is not quadratic."
            ),
        }

    if train_reference is not None:
        # Memorization is closeness to TRAINING data. Measuring generated events
        # against the validation truth they were conditioned on would answer a
        # different question entirely -- that is reconstruction accuracy, which
        # this battery already reports separately.
        picks = structural_subsample(len(generated), structural_events)
        memorization = stage("memorization", lambda: memorization_report(
            torch.from_numpy(generated[np.array(picks)]).float(),
            torch.from_numpy(train_reference).float(),
        ))
        memorization["subsample_events"] = len(picks)
        memorization["train_reference_events"] = int(train_reference.shape[0])
        report["memorization"] = memorization
    else:
        report["memorization"] = {
            "computed": False,
            "reason": (
                "no training reference sample was supplied. Memorization is "
                "nearest-neighbour closeness to TRAINING events; running it "
                "against the validation truth would measure reconstruction "
                "accuracy under a memorization label."
            ),
        }
    return report


class StageTimer:
    """Record how long each metric family takes, and say so as it goes.

    The battery ran for over an hour per checkpoint with no output, and finding
    out where required guessing three times. Every family is now timed, the
    timings are written into the report, and each one prints as it completes so
    a live run is observable rather than opaque.
    """

    def __init__(self, verbose: bool = True) -> None:
        self.verbose = verbose
        self.seconds: dict[str, float] = {}

    def __call__(self, name: str, fn):
        import time as _time
        start = _time.perf_counter()
        try:
            return fn()
        finally:
            elapsed = _time.perf_counter() - start
            self.seconds[name] = elapsed
            if self.verbose:
                print(f"[battery] {name:34s} {elapsed:8.1f} s", flush=True)


def structural_subsample(total: int, count: int) -> list[int]:
    """Evenly spaced indices over the bank, preserving its energy composition.

    The bank is emitted in digest order, so taking the first N would not be
    energy-stratified. An evenly spaced stride keeps every bin represented in
    proportion and is a pure function of (total, count).
    """
    if count <= 0 or count >= total:
        return list(range(total))
    step = total / count
    return sorted({min(total - 1, int(i * step)) for i in range(count)})


def _truth_half_tensors(
    truth_layer_energy: np.ndarray, event_ids: list[int]
) -> dict[str, torch.Tensor]:
    """Two disjoint deterministic halves of truth, for the correlation floor."""
    left, right = deterministic_truth_halves(event_ids)
    position = {event: index for index, event in enumerate(event_ids)}
    if not left or not right:
        return {}
    return {
        "truth_half_a": torch.from_numpy(
            truth_layer_energy[[position[e] for e in left]]
        ).float(),
        "truth_half_b": torch.from_numpy(
            truth_layer_energy[[position[e] for e in right]]
        ).float(),
    }


def resolve_runtime_config(checkpoint_config: dict, request: BatteryRequest) -> dict:
    """Point a checkpoint's frozen config at this host's paths, nothing else."""
    runtime = copy.deepcopy(checkpoint_config)
    runtime["geometry"]["path"] = str(Path(request.geometry_manifest).resolve())
    return runtime


def build_model(geometry: dict, config: dict, checkpoint: dict, device: str):
    model = CBSCZDC(geometry, config).to(device).eval()
    model.load_state_dict(checkpoint["model_state"])
    return model


def reduce_invariants(reports: list[dict]) -> dict:
    if not reports:
        return {"pass": False, "reports": 0}
    reduced: dict[str, Any] = {"pass": all(r["pass"] for r in reports), "reports": len(reports)}
    for key in reports[0]:
        if key == "pass":
            continue
        reduced[key] = max(r[key] for r in reports)
    return reduced


__all__ = [
    "BATTERY_KIND",
    "BOOTSTRAP_CONFIDENCE",
    "BOOTSTRAP_REPLICATES",
    "BatteryContractError",
    "BatteryRequest",
    "EVALUATION_ROLES",
    "EVALUATION_SPLIT",
    "MANIFEST_KIND",
    "REQUIRED_INPUTS",
    "REQUIRED_PAIRS",
    "REQUIRED_PAIRS_PER_BIN",
    "SELECTION_SALT",
    "StageTimer",
    "STRUCTURAL_SUBSAMPLE_EVENTS",
    "battery_report",
    "build_model",
    "build_validation_manifest",
    "closure_tolerances",
    "invariant_report",
    "load_geometry",
    "load_validation_manifest",
    "reduce_invariants",
    "resolve_runtime_config",
    "structural_subsample",
]
