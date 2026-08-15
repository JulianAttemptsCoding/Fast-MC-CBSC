"""The v3 validation battery's contract: fail closed, and never touch test.

The metric implementations are unit-tested elsewhere.  What is tested here is
the wiring that makes them usable: that the battery refuses to infer anything
that moves a number, that its evaluation bank is fixed and hash-verified, and
that no code path can construct a test loader.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import numpy as np
import pytest
import torch

from cbsc_zdc.data.split import create_split
from cbsc_zdc.data.synthetic import create_synthetic_dataset
from cbsc_zdc.eval import v3_battery as battery
from cbsc_zdc.eval.v3_battery import (
    BOOTSTRAP_CONFIDENCE,
    BOOTSTRAP_REPLICATES,
    EVALUATION_SPLIT,
    REQUIRED_INPUTS,
    REQUIRED_PAIRS,
    REQUIRED_PAIRS_PER_BIN,
    BatteryContractError,
    BatteryRequest,
    build_validation_manifest,
    load_validation_manifest,
)

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "run_v3_validation_battery.py"
MODULE = ROOT / "src" / "cbsc_zdc" / "eval" / "v3_battery.py"


# --------------------------------------------------------------------------
# the sealed test split
# --------------------------------------------------------------------------

def test_the_evaluation_split_is_a_constant_not_a_parameter():
    assert EVALUATION_SPLIT == "validation"


def test_no_battery_source_file_ever_names_the_test_split():
    """`"test"` must not appear as a split literal in either file.

    A battery that can be pointed at test is one typo from ending the project's
    ability to make an untouched-test claim, so the guard is syntactic and
    absolute rather than a runtime check that a caller could route around.
    """
    for path in (MODULE, CLI):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        literals = [
            node.value for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        ]
        offenders = [value for value in literals if value == "test"]
        assert not offenders, f"{path.name} contains a bare 'test' split literal"


def _cli_option_names() -> set[str]:
    """Every literal option string the CLI registers with argparse."""
    tree = ast.parse(CLI.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "add_argument":
            for argument in node.args:
                if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                    names.add(argument.value)
            for element in (
                e for a in node.args if isinstance(a, (ast.Tuple, ast.List))
                for e in a.elts
            ):
                if isinstance(element, ast.Constant):
                    names.add(element.value)
    # The loop over a tuple of path options registers them too.
    for node in ast.walk(tree):
        if isinstance(node, ast.For) and isinstance(node.iter, (ast.Tuple, ast.List)):
            for element in node.iter.elts:
                if isinstance(element, ast.Constant) and isinstance(element.value, str):
                    names.add(element.value)
    return names


def test_the_cli_exposes_no_split_selection_option():
    """`--splits` names the split manifest; there must be no split *chooser*."""
    options = _cli_option_names()
    assert "--split" not in options
    assert "--evaluation-split" not in options
    # The split-manifest path is a different thing and must still be there.
    assert "--splits" in options
    assert "--evaluation-role" in options


def test_the_cli_only_ever_constructs_validation_or_train_datasets():
    """Every ShardedSparseDataset split argument must be EVALUATION_SPLIT or train.

    The train reference exists solely for the memorization floor; memorization
    is closeness to training data by definition.
    """
    tree = ast.parse(CLI.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "ShardedSparseDataset":
            split = node.args[2]
            if isinstance(split, ast.Constant):
                assert split.value == "train", split.value
            else:
                assert getattr(split, "id", "") == "EVALUATION_SPLIT"


# --------------------------------------------------------------------------
# the fail-closed input contract
# --------------------------------------------------------------------------

def _request(tmp_path: Path, **overrides) -> BatteryRequest:
    present = tmp_path / "present"
    present.write_text("{}", encoding="utf-8")
    base = dict(
        checkpoint=present, frozen_config=present,
        validation_manifest=present, geometry_manifest=present,
        data_manifest_sha256="a" * 64, splits_sha256="b" * 64,
        generator_seed=20260723, evaluator_seeds=(1, 2, 3),
        energy_bin_edges_gev=(50.0, 100.0, 150.0, 200.0, 250.0),
        profile_steps=8, share_steps=8, precision="fp32",
        output_namespace="v3-battery/test", evaluation_role="diagnostic",
    )
    base.update(overrides)
    return BatteryRequest(**base)


def test_a_complete_request_validates(tmp_path):
    _request(tmp_path).validate()


@pytest.mark.parametrize("field", REQUIRED_INPUTS)
def test_every_required_input_fails_closed_when_absent(tmp_path, field):
    empty = {"evaluator_seeds": (), "energy_bin_edges_gev": ()}.get(field, None)
    if field in {"generator_seed", "profile_steps", "share_steps"}:
        empty = 0
    with pytest.raises(BatteryContractError, match="refuses to infer"):
        _request(tmp_path, **{field: empty}).validate()


def test_an_unknown_evaluation_role_is_rejected(tmp_path):
    with pytest.raises(BatteryContractError, match="evaluation_role"):
        _request(tmp_path, evaluation_role="whatever").validate()


def test_exactly_three_evaluator_seeds_are_required(tmp_path):
    with pytest.raises(BatteryContractError, match="three external evaluator seeds"):
        _request(tmp_path, evaluator_seeds=(1, 2)).validate()


def test_duplicate_evaluator_seeds_are_rejected(tmp_path):
    with pytest.raises(BatteryContractError, match="distinct"):
        _request(tmp_path, evaluator_seeds=(1, 1, 2)).validate()


def test_a_non_fp32_precision_is_rejected(tmp_path):
    with pytest.raises(BatteryContractError, match="FP32"):
        _request(tmp_path, precision="fp16").validate()


def test_unsorted_energy_bin_edges_are_rejected(tmp_path):
    with pytest.raises(BatteryContractError, match="increasing"):
        _request(tmp_path, energy_bin_edges_gev=(250.0, 50.0)).validate()


def test_the_declared_bootstrap_settings_cannot_be_lowered(tmp_path):
    """1000 replicates at 95% is frozen; a cheaper run is a different claim."""
    with pytest.raises(BatteryContractError, match="1000 bootstrap"):
        _request(tmp_path, bootstrap_replicates=100).validate()
    with pytest.raises(BatteryContractError, match="confidence"):
        _request(tmp_path, bootstrap_confidence=0.9).validate()


def test_a_missing_declared_file_is_rejected(tmp_path):
    with pytest.raises(BatteryContractError, match="does not exist"):
        _request(tmp_path, checkpoint=tmp_path / "absent.pt").validate()


def test_frozen_constants_match_the_gate_file():
    gates = (ROOT / "configs" / "gates_primary.yaml").read_text(encoding="utf-8")
    assert f"min_total_evaluation_events: {REQUIRED_PAIRS}" in gates
    assert f"min_events_per_energy_bin: {REQUIRED_PAIRS_PER_BIN}" in gates
    assert f"bootstrap" not in gates or BOOTSTRAP_REPLICATES == 1000
    assert BOOTSTRAP_CONFIDENCE == 0.95


# --------------------------------------------------------------------------
# the fixed bank
# --------------------------------------------------------------------------

@pytest.fixture(scope="module")
def synthetic(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("battery-bank")
    created = create_synthetic_dataset(
        tmp_path / "synthetic",
        n_events=400, n_layers=4, nodes_per_layer=4, shard_size=100, seed=17,
    )
    splits_path = tmp_path / "synthetic" / "splits.json"
    create_split(
        created["manifest"], splits_path,
        fractions=(0.4, 0.4, 0.2), seed=19, group_by="event_hash",
    )
    return created, splits_path, tmp_path


def _build_small_bank(synthetic, output_name="bank.json", pairs=40, per_bin=5):
    created, splits_path, tmp_path = synthetic
    return build_validation_manifest(
        data_manifest=Path(created["manifest"]),
        splits=splits_path,
        n_nodes=int(created["n_nodes"]),
        kinetic_range_gev=(0.0, 300.0),
        energy_bin_edges_gev=(0.0, 75.0, 150.0, 225.0, 300.0),
        output=tmp_path / output_name,
        pairs=pairs,
        pairs_per_bin=per_bin,
    )


def test_the_bank_records_validation_only_and_zero_test_events(synthetic):
    bank = _build_small_bank(synthetic)
    assert bank["split"] == "validation"
    assert bank["test_events_used"] == 0
    assert bank["train_events_used"] == 0


def test_the_bank_pairs_one_geant4_and_one_fastmc_event_per_condition(synthetic):
    bank = _build_small_bank(synthetic)
    assert bank["geant4_examples"] == bank["pairs"]
    assert bank["fastmc_examples"] == bank["pairs"]
    assert bank["evaluator_corpus_examples"] == 2 * bank["pairs"]


def test_the_bank_meets_its_per_bin_floor(synthetic):
    bank = _build_small_bank(synthetic)
    for name, count in bank["pairs_per_bin"].items():
        assert count >= bank["minimum_pairs_per_bin"], name


def test_bank_selection_is_deterministic(synthetic):
    first = _build_small_bank(synthetic, "bank_a.json")
    second = _build_small_bank(synthetic, "bank_b.json")
    assert first["content_sha256"] == second["content_sha256"]
    assert [e["event_id"] for e in first["events"]] == [
        e["event_id"] for e in second["events"]
    ]


def test_bank_event_ids_are_unique(synthetic):
    bank = _build_small_bank(synthetic)
    ids = [e["event_id"] for e in bank["events"]]
    assert len(set(ids)) == len(ids)


def test_a_bank_that_cannot_meet_the_per_bin_floor_is_fatal(synthetic):
    """An under-filled bin is an empty-bin condition, not a sampling problem."""
    with pytest.raises(BatteryContractError, match="per-bin floor"):
        _build_small_bank(synthetic, "bank_short.json", pairs=400, per_bin=10_000)


def test_a_bank_smaller_than_its_floor_requirement_is_fatal(synthetic):
    with pytest.raises(BatteryContractError, match="more than the declared bank size"):
        _build_small_bank(synthetic, "bank_tiny.json", pairs=4, per_bin=5)


def test_loading_verifies_the_bank_hash(synthetic):
    created, splits_path, tmp_path = synthetic
    _build_small_bank(synthetic, "bank_load.json")
    path = tmp_path / "bank_load.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    # A bank below the frozen 10,000 minimum is refused on load even when its
    # hash is intact, which is why these fixtures build a small bank and assert
    # the refusal rather than pretending 40 pairs is a production bank.
    with pytest.raises(BatteryContractError, match="below the frozen minimum"):
        load_validation_manifest(path)

    payload["events"][0]["event_id"] = -1
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(BatteryContractError, match="hash mismatch"):
        load_validation_manifest(path)


def test_a_bank_declaring_any_other_split_is_refused(synthetic, tmp_path):
    _build_small_bank(synthetic, "bank_split.json")
    _, _, base = synthetic
    payload = json.loads((base / "bank_split.json").read_text(encoding="utf-8"))
    payload["split"] = "train"
    path = tmp_path / "wrong_split.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(BatteryContractError, match="only 'validation'"):
        load_validation_manifest(path)


# --------------------------------------------------------------------------
# metric-family behaviour that the wiring is responsible for
# --------------------------------------------------------------------------

def test_zero_cause_decomposition_separates_the_two_mechanisms():
    """The marginal zero rate cannot tell the two apart; the split must."""
    visible = np.array([True, True, False, False])
    total = np.array([1.0, 0.0, 0.0, 0.0])
    report = battery._zero_cause_decomposition(visible, total)
    assert report["zero_fraction"] == pytest.approx(0.75)
    assert report["zero_from_visibility_hurdle"] == pytest.approx(0.5)
    # The one visible event that produced nothing is the second zero atom that
    # the S2 bounded spline exists to remove.
    assert report["zero_from_positive_branch"] == pytest.approx(0.25)


def test_zero_causes_sum_to_the_zero_fraction():
    rng = np.random.default_rng(3)
    visible = rng.random(500) > 0.3
    total = np.where(visible & (rng.random(500) > 0.2), rng.random(500) + 0.1, 0.0)
    report = battery._zero_cause_decomposition(visible, total)
    assert report["zero_from_visibility_hurdle"] + report[
        "zero_from_positive_branch"
    ] == pytest.approx(report["zero_fraction"])


def test_first_layer_report_finds_the_ecal_start_prevalence():
    layer_energy = np.array([
        [1.0, 0.0, 0.0, 0.0],   # starts in ECAL (layer 0)
        [0.0, 0.0, 2.0, 0.0],   # starts in HCAL
        [0.0, 0.0, 0.0, 0.0],   # no active layer
    ])
    report = battery._first_layer_report(layer_energy, ecal_layers=1)
    assert report["ecal_start_prevalence"] == pytest.approx(0.5)
    assert report["events_with_no_active_layer"] == 1


def test_activity_report_counts_gaps_between_first_and_last():
    layer_energy = np.array([[1.0, 0.0, 1.0, 0.0]])
    report = battery._activity_report(layer_energy)
    assert report["mean_active_layers"] == pytest.approx(2.0)
    assert report["mean_span"] == pytest.approx(3.0)
    assert report["mean_gaps"] == pytest.approx(1.0)


def test_truth_half_floor_is_deterministic_and_nonnegative():
    from cbsc_zdc.eval.metrics import wasserstein_1d

    values = np.linspace(0.0, 10.0, 200)
    ids = list(range(200))
    first = battery._truth_half_floor(values, ids, wasserstein_1d)
    second = battery._truth_half_floor(values, ids, wasserstein_1d)
    assert first == second
    assert first >= 0.0


def test_memorization_is_not_computed_against_validation_truth():
    """Silently substituting validation truth would relabel a different metric.

    Memorization is nearest-neighbour closeness to TRAINING events. Measuring
    generated events against the validation truth they were conditioned on is
    reconstruction accuracy, which the battery reports separately.
    """
    source = MODULE.read_text(encoding="utf-8")
    assert "train_reference" in source
    assert "would measure reconstruction" in source


# --------------------------------------------------------------------------
# end to end: every metric family must actually compute on real tensors
# --------------------------------------------------------------------------

def test_battery_report_computes_every_family_on_real_generated_events(
    synthetic, tmp_path
):
    """Run the orchestration on a real model's output, not on stubs.

    The contract tests above prove the battery refuses bad input. They cannot
    prove it produces anything, which is precisely the gap that let the v3
    format-4 defect survive: the helper was tested, the caller was not.
    """
    from cbsc_zdc.data.dataset import ShardedSparseDataset, load_geometry
    from cbsc_zdc.eval.v3_battery import battery_report, reduce_invariants
    from cbsc_zdc.models.system import CBSCZDC

    created, splits_path, _ = synthetic
    bank = _build_small_bank(synthetic, "bank_e2e.json", pairs=24, per_bin=3)

    config = {
        "geometry": {
            "path": str(created["geometry"]), "n_nodes": int(created["n_nodes"]),
            "n_layers": 4, "ecal_layers": 1,
        },
        "model": {
            "condition_dim": 16, "hidden_dim": 16, "response_hidden": 24,
            "response_components": 2, "response_scale_gev": 10.0,
            "profile_hidden": 16, "count_hidden": 24, "graph_blocks": 1,
            "attention_heads": 4, "attention_layers": 1,
            "layer_context": "bidirectional", "dropout": 0.0,
        },
        "data": {
            "target_mode": "raw_deposit", "threshold_gev": 0.0,
            "response_cap_ratio": 2.0, "response_cap_absolute_gev": 500.0,
        },
        "evaluation": {
            "profile_steps": 1, "share_steps": 1, "closure_tolerance_gev": 2e-5,
        },
    }
    geometry = load_geometry(created["geometry"], "cpu")
    model = CBSCZDC(geometry, config).eval()

    dataset = ShardedSparseDataset(
        created["manifest"], splits_path, EVALUATION_SPLIT, (0.0, 300.0),
        int(created["n_nodes"]),
    )
    indices = [int(row["dataset_index"]) for row in bank["events"]]
    events = [dataset[i] for i in indices]
    p4 = torch.stack([e["p4_total_gev"] for e in events])
    truth = np.stack([e["cell_energy_gev"].numpy() for e in events])
    kinetic = np.array([float(e["kinetic_energy_gev"]) for e in events])

    with torch.no_grad():
        out = model.sample(p4, 1, 1, 20260723, True)
    generated = out.cell_energy.numpy()

    request = _request(
        tmp_path,
        energy_bin_edges_gev=tuple(bank["energy_bin_edges_gev"]),
    )
    report = battery_report(
        request=request,
        bank=bank,
        truth=truth,
        generated=generated,
        kinetic=kinetic,
        truth_visible=truth.sum(axis=1) > 0,
        generated_visible=generated.sum(axis=1) > 0,
        event_ids=[int(row["event_id"]) for row in bank["events"]],
        strata=[str(row["energy_bin"]) for row in bank["events"]],
        layer_index=model.layer_index.numpy(),
        positions=geometry["positions_mm"].numpy(),
        ecal_layers=1,
        invariants=reduce_invariants([{"pass": True, "negative": 0}]),
        edge_index=getattr(model, "edge_index", None),
        timing={"total_seconds": 0.0},
    )

    for family in (
        "visibility_and_zero_response", "positive_response", "first_layer",
        "activity", "counts", "correlations", "distribution_metrics", "c2st",
        "reconstruction", "bootstrap", "truth_half_floors", "memorization",
    ):
        assert family in report, f"battery omitted {family}"

    assert report["split"] == "validation"
    assert report["test_events_used"] == 0
    assert report["evaluator_corpus_examples"] == 2 * len(truth)
    assert report["scientific_status"] == "PHYSICS VALIDATION NOT ESTABLISHED"

    # Every C2ST family reported separately, each with its own gate identity.
    assert set(report["c2st"]) == {
        "high_level", "low_level", "profile_aware", "condition_only"
    }
    assert report["c2st"]["high_level"]["gate"] == "max_high_level_c2st_auc"
    assert report["c2st"]["high_level"]["gate_value"] == 0.65
    assert report["c2st"]["low_level"]["gate"] is None
    # The condition-only control compares a sample against itself and must sit
    # at chance; a departure means the evaluator is leaking the label.
    assert report["c2st"]["condition_only"]["auroc_mean"] == pytest.approx(0.5, abs=1e-9)

    assert report["bootstrap"]["replicates"] == BOOTSTRAP_REPLICATES
    assert report["bootstrap"]["confidence"] == BOOTSTRAP_CONFIDENCE
    assert report["bootstrap"]["paired"] is True
    for name, interval in report["bootstrap"]["intervals"].items():
        assert interval["low"] <= interval["high"], name
        assert interval["replicates"] == BOOTSTRAP_REPLICATES, name

    # Memorization must refuse to run without a training reference.
    assert report["memorization"]["computed"] is False
    assert "TRAINING" in report["memorization"]["reason"]

    for key in ("generator_seed", "evaluator_seeds", "precision", "evaluation_role",
                "validation_manifest_sha256", "profile_steps", "share_steps"):
        assert key in report["identity"], key


def test_the_c2st_families_are_never_merged_into_one_number(synthetic, tmp_path):
    """High-level and low-level C2ST answer to different gates.

    The 0.65 project diagnostic is named max_high_level_c2st_auc. The D1/D2
    promotion rule names low-level. Reporting one blended AUROC is how a
    schedule change gets compared against an adversarial gate it never met.
    """
    source = MODULE.read_text(encoding="utf-8")
    assert "max_high_level_c2st_auc" in source
    assert "the D1/D2 promotion rule names this family" in source


def test_every_request_attribute_the_cli_uses_actually_exists():
    """Catch `request.geometry` when the field is `geometry_manifest`.

    The contract tests construct a BatteryRequest but never execute the CLI's
    evaluate path, so an attribute typo there survived them -- the same shape of
    gap as the v3 format-4 defect, where the helper was tested and the caller
    was not. This walks the CLI's AST and checks every `request.<name>` against
    the dataclass's real fields.
    """
    import dataclasses

    tree = ast.parse(CLI.read_text(encoding="utf-8"))
    used = {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "request"
    }
    fields = {f.name for f in dataclasses.fields(BatteryRequest)}
    methods = {name for name in dir(BatteryRequest) if not name.startswith("_")}
    unknown = used - fields - methods
    assert not unknown, f"CLI references non-existent BatteryRequest attributes: {sorted(unknown)}"


# --------------------------------------------------------------------------
# the declared structural subsample
# --------------------------------------------------------------------------

def test_structural_subsample_is_evenly_spaced_and_deterministic():
    """An evenly spaced stride keeps the bank's energy composition.

    The bank is emitted in digest order, so taking the first N would not be
    energy-stratified even though the bank itself is.
    """
    first = battery.structural_subsample(10_000, 1_000)
    second = battery.structural_subsample(10_000, 1_000)
    assert first == second
    assert len(first) == 1_000
    assert first == sorted(first)
    assert len(set(first)) == len(first)
    gaps = {b - a for a, b in zip(first, first[1:])}
    assert gaps <= {10}, gaps


def test_structural_subsample_degenerates_to_everything_when_not_smaller():
    assert battery.structural_subsample(50, 0) == list(range(50))
    assert battery.structural_subsample(50, 500) == list(range(50))


def test_the_subsample_is_recorded_with_its_reason(synthetic, tmp_path):
    """Reporting a subsampled family without saying so would be dishonest."""
    source = MODULE.read_text(encoding="utf-8")
    assert "subsample_rule" in source
    assert "subsample_reason" in source


def test_the_structural_families_default_to_the_whole_bank():
    """0 means everything. The earlier default of 1000 rested on a wrong
    diagnosis, and the module records that so it is not repeated."""
    assert battery.STRUCTURAL_SUBSAMPLE_EVENTS == 0
    source = MODULE.read_text(encoding="utf-8")
    assert "That diagnosis was wrong" in source


def test_c2st_and_bootstrap_never_use_the_subsample():
    """The frozen event minimum governs these families; they take every pair."""
    source = MODULE.read_text(encoding="utf-8")
    c2st_block = source[source.index('c2st = {'):source.index('response_wasserstein = ')]
    assert "index" not in c2st_block
    assert "picks" not in c2st_block
