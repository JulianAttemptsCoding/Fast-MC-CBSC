"""The v3 screening record, and the guards that keep it separate from v2.2.

A screening row changes the architecture and is initialized from -- not resumed
from -- its parent.  Two failure modes are worth pinning:

* a screening row leaking into `continuation_history.csv`, where it would be
  drawn on a v2.2 family's continuous loss axis and could compete for that
  family's accepted best;
* a status carrier outliving the condition it describes, which is how epochs
  91-114 stayed marked `unmeasured` after their diagnostics had been replayed.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "exhibition" / "data"
REGISTRY = DATA / "v3_screening_rows.json"
SCREENING_CSV = DATA / "v3_screening_history.csv"
CONTINUATION_CSV = DATA / "continuation_history.csv"
STATUS = DATA / "continuation_status.json"
GAPS = DATA / "diagnostic_gaps.json"
DIAGNOSTICS = DATA / "diagnostics"
SUMMARY = ROOT / "exhibition" / "current" / "v3_screening" / "screening_summary.json"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def importer():
    return _load("import_v3_screening_run", ROOT / "scripts" / "import_v3_screening_run.py")


@pytest.fixture(scope="module")
def builder():
    return _load("build_v3_screening_figure",
                 ROOT / "exhibition" / "build_v3_screening_figure.py")


@pytest.fixture(scope="module")
def registry() -> dict:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# registry integrity
# --------------------------------------------------------------------------

def test_registry_schema_and_unique_identifiers(registry):
    assert registry["schema_version"] == 1
    assert registry["kind"] == "cbsc-zdc-v3-screening-row-registry"
    row_ids = [row["row_id"] for row in registry["rows"]]
    variants = [row["variant"] for row in registry["rows"]]
    run_tags = [row["run_tag"] for row in registry["rows"]]
    assert len(set(row_ids)) == len(row_ids)
    assert len(set(variants)) == len(variants)
    assert len(set(run_tags)) == len(run_tags)


def test_registry_rows_declare_a_parent_and_a_single_change(registry):
    for row in registry["rows"]:
        assert row["parent"]["validation_loss"] > 0
        assert row["declared_change"]
        assert row["architecture_version"] == "cbsc-zdc-v3"
        # Exactly one feature may differ from the v2.2 defaults, or the row's
        # result cannot be attributed to its declared change.
        features = row["features_enabled"]
        non_default = [
            key for key, value in features.items()
            if not (value is False or value == "v2")
        ]
        if row.get("standalone_control"):
            # A zero-ablation control necessarily declares the feature it is
            # ablating plus the ablation itself. That pair is one change: it
            # keeps the axis path and its parameters while removing only the
            # information the columns carry.
            assert set(non_default) == {"axis_features", "axis_zero_ablation"}, (
                f"{row['row_id']} enables {non_default}"
            )
        else:
            assert len(non_default) == 1, f"{row['row_id']} enables {non_default}"


def test_registry_row_identifiers_are_filesystem_safe(importer, registry):
    for row in registry["rows"]:
        assert importer.RUN_TAG_PATTERN.fullmatch(row["run_tag"])
        assert importer.VARIANT_PATTERN.fullmatch(row["variant"])
        run_dir = Path(row["run_dir"])
        assert not run_dir.is_absolute()
        assert ".." not in run_dir.parts
        assert run_dir.parts[0] == "_runs"


def test_unpromoted_rows_do_not_claim_promotion(registry):
    """A finished row that is not promoted must say why.

    A running or queued row has no disposition yet, and demanding a reason from
    it would push the agent to write a conclusion before the evidence exists.
    """
    for row in registry["rows"]:
        if row["status"] != "complete":
            assert "disposition" not in row, (
                f"{row['row_id']} is {row['status']} but already claims a disposition"
            )
            continue
        if row.get("disposition") != "promoted":
            assert row.get("disposition_reason"), row["row_id"]


def test_every_registered_row_has_a_known_status(registry):
    for row in registry["rows"]:
        assert row["status"] in {"queued", "running", "complete"}, row["row_id"]


def test_running_and_queued_rows_carry_no_measured_evidence(registry):
    """Evidence flags must not be set before the evidence is imported."""
    for row in registry["rows"]:
        if row["status"] == "complete":
            continue
        assert not any(row["evidence"].values()), row["row_id"]


# --------------------------------------------------------------------------
# the separation guard
# --------------------------------------------------------------------------

def test_screening_variants_never_enter_the_v2_continuation_history(registry):
    screening = {row["variant"] for row in registry["rows"]}
    screening_tags = {row["run_tag"] for row in registry["rows"]}
    with CONTINUATION_CSV.open(newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            assert raw["variant"] not in screening, (
                f"screening variant {raw['variant']} leaked into the v2.2 continuation "
                "history, where it would be drawn on a family's continuous loss axis"
            )
            assert raw["run_tag"] not in screening_tags


def test_screening_variants_are_not_v2_exhibition_families(registry):
    exhibition = _load("build_exhibition", ROOT / "exhibition" / "build_exhibition.py")
    for row in registry["rows"]:
        assert row["variant"] not in exhibition.VARIANTS


def test_screening_history_only_holds_registered_rows(registry):
    if not SCREENING_CSV.is_file():
        pytest.skip("no screening history imported yet")
    known = {(row["variant"], row["run_tag"]) for row in registry["rows"]}
    with SCREENING_CSV.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    for raw in rows:
        assert (raw["variant"], raw["run_tag"]) in known


def test_screening_history_epochs_are_unique_and_finite():
    if not SCREENING_CSV.is_file():
        pytest.skip("no screening history imported yet")
    seen: set[tuple[str, int]] = set()
    with SCREENING_CSV.open(newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            key = (raw["variant"], int(raw["epoch"]))
            assert key not in seen, f"duplicate epoch row {key}"
            seen.add(key)
            assert math.isfinite(float(raw["train_loss"]))
            assert math.isfinite(float(raw["validation_loss"]))
            assert float(raw["learning_rate"]) > 0


# --------------------------------------------------------------------------
# status carriers must not outlive the condition they describe
# --------------------------------------------------------------------------

def _local_diagnostic_epochs(run_tag: str) -> set[int]:
    directory = DIAGNOSTICS / run_tag
    if not directory.is_dir():
        return set()
    epochs = set()
    for path in directory.glob("metrics_epoch_*.json"):
        epochs.add(int(path.stem.rsplit("_", 1)[1]))
    return epochs


def test_no_unmeasured_override_survives_its_diagnostics():
    """An epoch marked `unmeasured` must not have local diagnostics.

    This is the exact defect that kept dicos-f-03 epochs 91-114 reported as
    unmeasured after the 3090 had replayed every one of them: the override
    outlived its cause, so measured evidence was reported as missing and the
    epochs stayed ineligible to be an accepted best.
    """
    payload = json.loads(STATUS.read_text(encoding="utf-8"))
    stale = []
    for override in payload.get("overrides", []):
        if override.get("status") != "unmeasured":
            continue
        epoch = int(override["epoch"])
        if epoch in _local_diagnostic_epochs(override["run_tag"]):
            stale.append((override["run_tag"], epoch))
    assert not stale, (
        f"epochs marked unmeasured that do have imported diagnostics: {stale}"
    )


def test_no_declared_gap_survives_its_diagnostics():
    """A declared diagnostics gap must not cover epochs that are now measured."""
    payload = json.loads(GAPS.read_text(encoding="utf-8"))
    stale = []
    for gap in payload.get("gaps", []):
        first = int(gap["first_epoch_without_diagnostics"])
        last = int(gap["last_epoch_without_diagnostics"])
        for run_tag in gap["run_tags"]:
            measured = _local_diagnostic_epochs(run_tag)
            covered = {e for e in range(first, last + 1) if e in measured}
            if covered:
                stale.append((run_tag, sorted(covered)[:5], len(covered)))
    assert not stale, f"declared gaps covering measured epochs: {stale}"


def test_closed_gaps_are_retained_as_visible_history():
    """Closing a gap must record it, not erase it."""
    payload = json.loads(GAPS.read_text(encoding="utf-8"))
    for closed in payload.get("closed_gaps", []):
        assert closed.get("closed_on")
        assert closed.get("closure_evidence")
        assert closed.get("reason")


# --------------------------------------------------------------------------
# invariant-report validation
# --------------------------------------------------------------------------

BASE_INVARIANT = {
    "pass": True,
    "negative": 0,
    "nonfinite": 0,
    "outside_valid_support": 0,
    "support_mask_mismatch": 0,
    "count_mismatch_max": 0,
    "requested_realized_mismatch_max": 0,
    "dust_cells": 0,
    "closure_tolerance_absolute_gev": 2e-05,
    "closure_tolerance_relative": 1e-05,
    "closure_tolerance_effective_gev": 1.2e-04,
    "event_closure_max_gev": 4.76837158203125e-07,
    "layer_closure_max_gev": 9.5367431640625e-07,
}


def _write_invariant(tmp_path: Path, **overrides) -> Path:
    payload = dict(BASE_INVARIANT, **overrides)
    path = tmp_path / "invariant_epoch_0007.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_invariant_validation_accepts_a_clean_report(importer, tmp_path):
    assert importer.validate_invariant(_write_invariant(tmp_path), 7)["pass"] is True


def test_invariant_validation_rejects_a_failed_report(importer, tmp_path):
    with pytest.raises(ValueError, match="did not pass"):
        importer.validate_invariant(_write_invariant(tmp_path, **{"pass": False}), 7)


@pytest.mark.parametrize("field", [
    "negative", "nonfinite", "outside_valid_support", "support_mask_mismatch",
    "count_mismatch_max", "requested_realized_mismatch_max", "dust_cells",
])
def test_invariant_validation_rejects_a_nonzero_structural_count(importer, tmp_path, field):
    """`pass: true` is re-derived, never trusted."""
    with pytest.raises(ValueError, match=field):
        importer.validate_invariant(_write_invariant(tmp_path, **{field: 1}), 7)


def test_invariant_validation_rejects_closure_above_the_effective_tolerance(
    importer, tmp_path
):
    with pytest.raises(ValueError, match="exceeds effective tolerance"):
        importer.validate_invariant(
            _write_invariant(tmp_path, layer_closure_max_gev=1.0), 7
        )


def test_invariant_validation_uses_the_effective_not_the_absolute_tolerance(
    importer, tmp_path
):
    """The bound has been max(absolute, relative * response) since 2026-08-05.

    A residual above the 2e-5 absolute floor but below the effective bound is
    legitimate float32 rounding at that event's energy, and must not be
    rejected -- that misreading is what ended dicos-p10 on a structurally
    perfect epoch.
    """
    payload = importer.validate_invariant(
        _write_invariant(
            tmp_path,
            closure_tolerance_effective_gev=1.2e-04,
            layer_closure_max_gev=2.67e-05,
        ),
        7,
    )
    assert payload["layer_closure_max_gev"] > payload["closure_tolerance_absolute_gev"]


def test_invariant_validation_rejects_a_missing_effective_tolerance(importer, tmp_path):
    payload = dict(BASE_INVARIANT)
    payload.pop("closure_tolerance_effective_gev")
    path = tmp_path / "invariant_epoch_0007.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="effective closure tolerance"):
        importer.validate_invariant(path, 7)


# --------------------------------------------------------------------------
# visualization-payload validation
# --------------------------------------------------------------------------

BASE_VISUAL = {
    "kind": "cbsc-zdc-epoch-visual-comparison",
    "split": "validation",
    "epoch": 7,
    "sample_count": 50,
    "draws_per_condition": 5,
    "qa": {"pass": True, "test_events_used": 0, "groups_with_exact_draw_count": 50},
}


def _write_visual(tmp_path: Path, **overrides) -> Path:
    payload = dict(BASE_VISUAL)
    payload.update(overrides)
    path = tmp_path / "epoch_0007.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_visualization_validation_accepts_a_clean_payload(importer, tmp_path):
    assert importer.validate_visualization(_write_visual(tmp_path), 7)["epoch"] == 7


def test_visualization_validation_rejects_test_events(importer, tmp_path):
    qa = dict(BASE_VISUAL["qa"], test_events_used=1)
    with pytest.raises(ValueError, match="test events"):
        importer.validate_visualization(_write_visual(tmp_path, qa=qa), 7)


def test_visualization_validation_rejects_the_train_split(importer, tmp_path):
    with pytest.raises(ValueError, match="split"):
        importer.validate_visualization(_write_visual(tmp_path, split="train"), 7)


def test_visualization_validation_rejects_a_short_draw_count(importer, tmp_path):
    qa = dict(BASE_VISUAL["qa"], groups_with_exact_draw_count=49)
    with pytest.raises(ValueError, match="draw-count"):
        importer.validate_visualization(_write_visual(tmp_path, qa=qa), 7)


# --------------------------------------------------------------------------
# history reading
# --------------------------------------------------------------------------

def _history(tmp_path: Path, rows: list[tuple]) -> Path:
    path = tmp_path / "history.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["epoch", "train_loss", "validation_loss", "learning_rate"])
        writer.writerows(rows)
    return path


ROW_STUB = {
    "variant": "v3_test", "run_tag": "v3-test",
    "horizon_epochs": 3, "status": "running",
}


def test_read_history_rejects_a_duplicate_epoch(importer, tmp_path):
    path = _history(tmp_path, [(0, 4.7, 4.6, 3e-4), (0, 4.6, 4.5, 2e-4)])
    with pytest.raises(ValueError, match="duplicate history epoch"):
        importer.read_history(path, ROW_STUB)


def test_read_history_rejects_a_nonfinite_loss(importer, tmp_path):
    path = _history(tmp_path, [(0, 4.7, float("nan"), 3e-4)])
    with pytest.raises(ValueError, match="nonfinite"):
        importer.read_history(path, ROW_STUB)


def test_read_history_rejects_a_nonpositive_learning_rate(importer, tmp_path):
    path = _history(tmp_path, [(0, 4.7, 4.6, 0.0)])
    with pytest.raises(ValueError, match="learning rate"):
        importer.read_history(path, ROW_STUB)


def test_read_history_rejects_more_epochs_than_the_declared_horizon(importer, tmp_path):
    path = _history(tmp_path, [(e, 4.7, 4.6, 3e-4) for e in range(5)])
    with pytest.raises(ValueError, match="24-epoch|3-epoch horizon"):
        importer.read_history(path, ROW_STUB)


def test_read_history_rejects_a_short_complete_row(importer, tmp_path):
    """A row declared complete must actually hold its whole horizon."""
    path = _history(tmp_path, [(0, 4.7, 4.6, 3e-4)])
    with pytest.raises(ValueError, match="declared complete"):
        importer.read_history(path, dict(ROW_STUB, status="complete"))


# --------------------------------------------------------------------------
# summary arithmetic and wording
# --------------------------------------------------------------------------

def test_classify_uses_the_run_to_run_band(builder):
    reference = builder.RUN_TO_RUN_REFERENCE
    assert builder.classify(-2 * reference) == "better"
    assert builder.classify(2 * reference) == "worse"
    assert builder.classify(reference / 2) == "within_run_to_run_reference"
    assert builder.classify(0.0) == "within_run_to_run_reference"


def test_summary_reports_the_reference_as_a_reproducibility_figure(builder):
    """The band must never be described as a sigma, p-value, or interval."""
    registry = builder.load_registry()
    summary = builder.summarize(registry, builder.load_history())
    meaning = summary["run_to_run_reference_meaning"].lower()
    assert "not a standard error" in meaning
    assert summary["test_events_used"] == 0
    assert summary["scientific_status"] == "PHYSICS VALIDATION NOT ESTABLISHED"


def test_baseline_battery_is_exposed_without_collapsing_c2st_families(builder):
    summary = builder.summarize(builder.load_registry(), builder.load_history())
    battery = summary["baseline"]["battery"]
    if battery is None:
        quarantined = (
            ROOT / "exhibition" / "data" / "v3_battery" / "quarantine"
            / "dicos-f-02_epoch90.zero-truth-relative-error.json"
        )
        assert quarantined.is_file()
        return
    assert battery["pairs"] == 10_000
    assert battery["evaluator_corpus_examples"] == 20_000
    assert battery["test_events_used"] == 0
    assert set(battery["c2st_auroc_mean"]) == {
        "high_level", "low_level", "profile_aware", "condition_only"
    }


def test_battery_summary_requires_a_matching_provenance_sidecar(
    builder, monkeypatch, tmp_path
):
    data = tmp_path / "exhibition" / "data"
    battery_dir = data / "v3_battery"
    battery_dir.mkdir(parents=True)
    report_path = battery_dir / "x_epoch7.json"
    report = {
        "schema_version": 3,
        "kind": "cbsc-zdc-v3-validation-battery",
        "split": "validation",
        "pairs": 10_000,
        "evaluator_corpus_examples": 20_000,
        "validation_events_used": 10_000,
        "train_events_used": 2_000,
        "test_events_used": 0,
        "data_usage": {
            "validation_truth_events": 10_000,
            "generated_events": 10_000,
            "training_reference_events": 2_000,
            "training_reference_role": "memorization nearest-neighbour reference only",
            "test_events": 0,
        },
        "memorization": {"train_reference_events": 2_000},
        "scientific_status": "PHYSICS VALIDATION NOT ESTABLISHED",
        "structural_invariants": {"pass": True},
        "paired_response": {
            "kind": "paired_detector_response_residual",
            "normalization": "incident_kinetic_energy_gev",
            "events_included": 10_000,
            "zero_truth_events": 100,
        },
        "c2st": {name: {"auroc_mean": 0.5} for name in (
            "high_level", "low_level", "profile_aware", "condition_only"
        )},
        "identity": {
            "run_tag": "x", "epoch": 7, "checkpoint_embedded_epoch": 7,
            "checkpoint_sha256": "a" * 64, "frozen_config_sha256": "b" * 64,
            "evaluation_role": "diagnostic",
        },
    }
    report_path.write_text(json.dumps(report), encoding="utf-8")
    sidecar = {
        "kind": "cbsc-zdc-v3-battery-provenance-sidecar",
        "report": report_path.name,
        "report_sha256": builder.sha256_file(report_path),
        "selected_validation_loss": 4.2,
        "test_events_used": 0,
        "scientific_status": "PHYSICS VALIDATION NOT ESTABLISHED",
        "checkpoint_sha256": "a" * 64,
        "checkpoint_embedded_epoch": 7,
        "frozen_config_sha256": "b" * 64,
    }
    sidecar_path = report_path.with_suffix(".provenance.json")
    sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")
    monkeypatch.setattr(builder, "DATA", data)
    monkeypatch.setattr(builder, "ROOT", tmp_path)
    assert builder.load_battery_report("x")["selected_validation_loss"] == 4.2
    sidecar_path.unlink()
    with pytest.raises(ValueError, match="provenance sidecar is missing"):
        builder.load_battery_report("x")


def test_summary_deltas_match_the_registry_and_history(builder):
    registry = builder.load_registry()
    series = builder.load_history()
    summary = builder.summarize(registry, series)
    for record in summary["rows"]:
        history = series.get(record["variant"])
        if not history:
            continue
        best = min(history, key=lambda r: (r["validation_loss"], r["epoch"]))
        offset = builder.loss_measure_offset(
            next(r for r in registry["rows"] if r["row_id"] == record["row_id"])
        )
        assert record["raw_best_validation_loss"] == best["validation_loss"]
        assert record["best_validation_loss"] == pytest.approx(
            best["validation_loss"] + offset
        )
        assert record["best_epoch"] == best["epoch"]
        assert record["delta_vs_parent"] == pytest.approx(
            record["best_validation_loss"] - record["parent_validation_loss"]
        )


def test_cross_response_mode_comparison_uses_common_measure(builder):
    registry = builder.load_registry()
    summary = builder.summarize(registry, builder.load_history())
    s2 = next(r for r in summary["rows"] if r["row_id"] == "S2-response")
    assert s2["raw_best_validation_loss"] == s2["best_validation_loss"]
    assert s2["comparator_validation_loss"] == pytest.approx(4.935508412921843)
    assert s2["delta_vs_comparator"] == pytest.approx(
        s2["best_validation_loss"] - 4.935508412921843
    )
    assert registry["comparator_rule"]["cross_measure_raw_comparison_allowed"] is False


def test_historical_values_are_preserved_beside_common_measure(builder):
    summary = builder.summarize(builder.load_registry(), builder.load_history())
    m0 = next(r for r in summary["rows"] if r["row_id"] == "M0-fresh")
    assert m0["raw_best_validation_loss"] == pytest.approx(4.513572058600877)
    assert m0["best_validation_loss"] == pytest.approx(4.935508412921843)
    assert m0["loss_measure_offset"] == pytest.approx(0.42193635432096555)


def test_a_row_worse_than_its_parent_is_not_promoted(builder):
    summary = builder.summarize(builder.load_registry(), builder.load_history())
    for record in summary["rows"]:
        if record.get("direction_vs_parent") == "worse":
            assert record["disposition"] != "promoted", record["row_id"]
    assert summary["promoted_rows"] == []


def test_s1_is_a_negative_result_whose_causal_question_is_now_resolved(builder):
    """S1 stays not promoted, and its cause is now attributed rather than open.

    The configuration lost to both references, so the promotion rule retains the
    simpler parent. What changed on 2026-08-15 is the *reason*: M0-fresh isolated
    the fresh optimizer, and the axis feature turned out to be neutral.
    """
    summary = builder.summarize(builder.load_registry(), builder.load_history())
    s1 = next(r for r in summary["rows"] if r["row_id"] == "S1-axis")
    assert s1["disposition"] == "S1_CONFIGURATION_NOT_PROMOTED"
    assert s1["causal_status"] == "S1_AXIS_CAUSAL_EFFECT_RESOLVED_NEUTRAL"
    assert s1["direction_vs_parent"] == "worse"
    # The confound that kept it open must remain on the record.
    assert s1["optimizer_state_transferred"] is False


def test_the_axis_effect_is_below_the_run_to_run_reference(builder):
    """M0 and S1 differ by less than the reproducibility band, so axis is neutral."""
    registry = builder.load_registry()
    m0 = next(r for r in registry["rows"] if r["row_id"] == "M0-fresh")
    result = m0["result"]["vs_s1_axis"]
    assert abs(result["difference"]) < builder.RUN_TO_RUN_REFERENCE
    assert result["within_reference"] is True


def test_the_fresh_optimizer_cost_is_recorded_and_attributed(builder):
    """The shortfall must be attributed, not left as an unexplained delta."""
    registry = builder.load_registry()
    m0 = next(r for r in registry["rows"] if r["row_id"] == "M0-fresh")
    attribution = m0["result"]["attribution_of_s1_shortfall"]
    total = attribution["total_vs_f_03"]
    parts = attribution["from_fresh_optimizer"] + attribution["from_axis_feature"]
    assert parts == pytest.approx(total, abs=1e-9)
    assert attribution["from_fresh_optimizer"] > attribution["from_axis_feature"] * 10


def test_the_comparator_rule_points_at_m0_not_b0(builder):
    """Every screening row pays the optimizer restart, so B0 is the wrong yardstick."""
    registry = builder.load_registry()
    rule = registry["comparator_rule"]
    assert "M0-fresh" in rule["statement"]
    assert "NOT B0" in rule["statement"]
    assert rule["measured_fresh_optimizer_cost"] > 0


def test_a_control_row_is_not_treated_as_a_promotion_candidate(builder):
    registry = builder.load_registry()
    m0 = next(r for r in registry["rows"] if r["row_id"] == "M0-fresh")
    assert m0["disposition"] == "M0_CONTROL_COMPLETE"
    assert m0["standalone_control"] is True
    summary = builder.summarize(registry, builder.load_history())
    assert "M0-fresh" not in summary["promoted_rows"]


def test_published_summary_matches_a_fresh_rebuild(builder):
    """The committed summary must be what the builder produces today."""
    if not SUMMARY.is_file():
        pytest.skip("screening summary not built yet")
    on_disk = json.loads(SUMMARY.read_text(encoding="utf-8"))
    rebuilt = builder.summarize(builder.load_registry(), builder.load_history())
    assert on_disk == rebuilt


# --------------------------------------------------------------------------
# inheritance must be declared, and only from promoted rows
# --------------------------------------------------------------------------

@pytest.fixture(scope="module")
def config_builder():
    return _load("build_v3_screening_configs",
                 ROOT / "scripts" / "build_v3_screening_configs.py")


def test_no_row_inherits_a_feature_by_default(config_builder, registry):
    """A screening row changes exactly one thing unless inheritance is declared.

    The original matrix listed S1..S5 as a cumulative chain on the assumption
    that each row promotes. S1-axis did not -- it lost to both its parent and
    its matched control. A blind cumulative build would hand its axis feature to
    S2, S3 and every later row, stacking a rejected change while each row still
    reported only its own declared change.
    """
    rows = {row["id"]: row for row in config_builder.ROWS}
    s2 = rows["S2-response"]
    assert set(s2["model"]) == {"response_mode"}
    assert "axis_features" not in s2["model"]


def test_the_registry_records_s1_as_unpromoted_so_nothing_may_inherit_it(registry):
    s1 = next(r for r in registry["rows"] if r["row_id"] == "S1-axis")
    assert s1["disposition"] != "promoted"


def test_a_standalone_control_cannot_be_inherited_from(config_builder):
    m0 = next(r for r in config_builder.ROWS if r["id"] == "M0-fresh")
    assert m0.get("standalone") is True


def test_every_matrix_row_changes_exactly_one_thing(config_builder):
    for row in config_builder.ROWS:
        if row.get("standalone"):
            continue
        assert len(row["model"]) == 1, f"{row['id']} declares {row['model']}"
