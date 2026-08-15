"""The v3 heads are reachable from the trainer, and v2.2 is untouched.

Unit tests prove each head in isolation; this proves the epoch loop actually
calls them, produces every declared loss key, and backpropagates into the new
parameters.  Without this, a head could be perfectly correct and never run.
"""

from __future__ import annotations

import pytest
import torch

from cbsc_zdc.config import ARCHITECTURE_V3, V3_LOSS_WEIGHTS
from cbsc_zdc.contracts import NEUTRON_MASS_GEV
from cbsc_zdc.models.system import CBSCZDC
from cbsc_zdc.training.trainer import (
    STAGE_LOSSES,
    V3_STAGE_LOSSES,
    compute_component_losses,
    stage_losses_for,
)
from cbsc_zdc.training.weights import weighted_total

# Every v3 head turned on at once. Individual rows of the experiment matrix
# enable exactly one of these; ALL_V3 is what the final composite looks like.
ALL_V3 = dict(
    response_mode="spline",
    first_layer_mode="hierarchical",
    activity_head_mode="span_gaps",
    count_mode="autoregressive",
)

N_LAYERS, PER_LAYER = 4, 4
N_NODES = N_LAYERS * PER_LAYER


def geometry() -> dict[str, torch.Tensor]:
    layer_index = torch.arange(N_LAYERS).repeat_interleave(PER_LAYER)
    edges = [[int(a), int(b)]
             for layer in range(N_LAYERS)
             for a in torch.nonzero(layer_index == layer).flatten()
             for b in torch.nonzero(layer_index == layer).flatten() if a != b]
    edge_index = torch.tensor(edges, dtype=torch.long).T
    return {
        "node_features": torch.randn(N_NODES, 5),
        "layer_index": layer_index,
        "valid_mask": torch.ones(N_NODES, dtype=torch.bool),
        "edge_index": edge_index,
        "edge_features": torch.randn(edge_index.shape[1], 3),
    }


def config(version: str | None, **model_extra) -> dict:
    model = {
        "condition_dim": 16, "hidden_dim": 16, "graph_blocks": 1,
        "attention_heads": 2, "attention_layers": 1, "profile_hidden": 16,
        "count_hidden": 16, "response_hidden": 16, "activity_hidden": 16,
        "first_layer_hidden": 16, "response_spline_bins": 8,
    }
    if version:
        model["architecture_version"] = version
    model.update(model_extra)
    return {"model": model, "data": {"target_mode": "raw_deposit", "threshold_gev": 0.0}}


def model(version: str | None = None, **extra) -> CBSCZDC:
    torch.manual_seed(0)
    return CBSCZDC(geometry(), config(version, **extra))


def batch(n: int = 4) -> dict[str, torch.Tensor]:
    total = torch.full((n,), 120.0, dtype=torch.float64)
    momentum = torch.sqrt(total.square() - NEUTRON_MASS_GEV**2)
    p4 = torch.stack(
        [total, torch.zeros_like(total), torch.zeros_like(total), momentum], dim=1
    ).float()
    g = torch.Generator().manual_seed(4)
    cell = torch.rand(n, N_NODES, generator=g).abs() * 3.0
    cell[cell < 0.6] = 0.0
    cell[0] = 0.0  # one invisible event, which every stage must tolerate
    return {"p4_total_gev": p4, "cell_energy_gev": cell}


# --- v2.2 is untouched --------------------------------------------------

def test_a_config_without_architecture_version_uses_the_v2_path() -> None:
    m = model()
    assert m.is_v3 is False
    assert not hasattr(m, "response_v3")
    assert stage_losses_for(m) is STAGE_LOSSES
    losses, _ = compute_component_losses(m, batch(), "joint")
    assert set(losses) == STAGE_LOSSES["joint"]


def test_v2_loss_values_are_unchanged_by_the_v3_code_path() -> None:
    # The profile and share flow losses draw their interpolation noise inside
    # the call, so the RNG must be pinned immediately before each one; otherwise
    # this compares two different noise draws rather than two code paths.
    a, b = model(), model()
    torch.manual_seed(123)
    la, _ = compute_component_losses(a, batch(), "joint")
    torch.manual_seed(123)
    lb, _ = compute_component_losses(b, batch(), "joint")
    for key in la:
        assert torch.allclose(la[key], lb[key]), key


# --- v3 reaches every declared head ------------------------------------

def test_v3_features_default_off_so_each_row_is_attributable() -> None:
    # A bare v3 declaration must behave exactly like v2.2. The matrix screens one
    # change per row, so enabling everything on the version switch alone would
    # make every row after the first unattributable.
    m = model(ARCHITECTURE_V3)
    assert m.is_v3 is True
    assert (m.response_mode, m.first_layer_mode, m.count_mode, m.activity_head_mode) == (
        "v2", "v2", "v2", "v2",
    )
    for attr in ("response_v3", "first_layer", "activity", "counts_ar"):
        assert not hasattr(m, attr), attr
    assert stage_losses_for(m) is STAGE_LOSSES
    losses, _ = compute_component_losses(m, batch(), "joint")
    assert set(losses) == STAGE_LOSSES["joint"]


def test_v3_feature_modes_require_the_v3_architecture() -> None:
    with pytest.raises(ValueError, match="require model.architecture_version"):
        CBSCZDC(geometry(), config(None, response_mode="spline"))


def test_an_unknown_feature_mode_is_rejected() -> None:
    with pytest.raises(ValueError, match="response_mode"):
        CBSCZDC(geometry(), config(ARCHITECTURE_V3, response_mode="magic"))


def test_v3_model_builds_every_new_head_when_all_are_declared() -> None:
    m = model(ARCHITECTURE_V3, **ALL_V3)
    for attr in ("response_v3", "first_layer", "activity", "counts_ar"):
        assert hasattr(m, attr), attr
    # the v2.2 modules remain so a migrated checkpoint keeps its parameter names
    for attr in ("response", "profile", "counts"):
        assert hasattr(m, attr), attr


def test_v3_joint_stage_emits_exactly_the_declared_loss_keys() -> None:
    m = model(ARCHITECTURE_V3, **ALL_V3)
    losses, _ = compute_component_losses(m, batch(), "joint")
    assert set(losses) == V3_STAGE_LOSSES["joint"]
    # and the emitted keys are exactly what the config schema weights
    assert set(losses) == V3_LOSS_WEIGHTS


def test_enabling_one_feature_adds_only_its_own_keys() -> None:
    # S3 turns on the hierarchical first layer and nothing else; the activity
    # keys must not appear, or S4's change would already be in S3's key set.
    m = model(ARCHITECTURE_V3, first_layer_mode="hierarchical")
    losses, _ = compute_component_losses(m, batch(), "joint")
    assert {"ecal_start", "hcal_first"} <= set(losses)
    assert not {"active_last", "active_gap"} & set(losses)

    # and the count head swap adds no new key at all, it replaces one
    c = model(ARCHITECTURE_V3, count_mode="autoregressive")
    closses, _ = compute_component_losses(c, batch(), "joint")
    assert set(closses) == STAGE_LOSSES["joint"]


def test_v3_losses_are_finite_and_weightable() -> None:
    m = model(ARCHITECTURE_V3, **ALL_V3)
    losses, _ = compute_component_losses(m, batch(), "joint")
    for key, value in losses.items():
        assert torch.isfinite(value), key
    total = weighted_total(losses, {name: 1.0 for name in V3_LOSS_WEIGHTS})
    assert torch.isfinite(total)


def test_v3_backward_reaches_the_new_heads() -> None:
    m = model(ARCHITECTURE_V3, **ALL_V3)
    losses, _ = compute_component_losses(m, batch(), "joint")
    weighted_total(losses, {name: 1.0 for name in V3_LOSS_WEIGHTS}).backward()
    for name in ("response_v3", "first_layer", "activity", "counts_ar"):
        module = getattr(m, name)
        grads = [p.grad for p in module.parameters() if p.grad is not None]
        assert grads, f"{name} received no gradient"
        assert any(g.abs().sum() > 0 for g in grads), f"{name} gradient is all zero"


def test_autoregressive_activity_mode_is_selectable_and_zeroes_the_other_term() -> None:
    m = model(ARCHITECTURE_V3, activity_head_mode="autoregressive")
    losses, _ = compute_component_losses(m, batch(), "joint")
    # Only the activity keys are added: this row does not turn on the
    # hierarchical first layer, so its keys must be absent.
    assert set(losses) == STAGE_LOSSES["joint"] | {"active_last", "active_gap"}
    # the span/gap term is emitted as an exact zero, not omitted
    assert float(losses["active_gap"]) == 0.0
    assert torch.isfinite(losses["active_last"])


def test_span_gap_mode_produces_both_activity_terms() -> None:
    m = model(ARCHITECTURE_V3, activity_head_mode="span_gaps")
    losses, _ = compute_component_losses(m, batch(), "joint")
    assert torch.isfinite(losses["active_last"])
    assert torch.isfinite(losses["active_gap"])


def test_every_v3_stage_emits_only_its_declared_subset() -> None:
    m = model(ARCHITECTURE_V3, **ALL_V3)
    for stage, expected in V3_STAGE_LOSSES.items():
        losses, _ = compute_component_losses(m, batch(), stage)
        assert set(losses) == expected, stage


# --- the response envelope is a hard requirement for production ---------

def test_a_v3_run_without_an_envelope_fails_preflight() -> None:
    m = model(ARCHITECTURE_V3, response_mode="spline")
    with pytest.raises(ValueError, match="response_envelope_caps_gev"):
        m.preflight_v3_envelope()


def test_a_v2_run_needs_no_envelope() -> None:
    model().preflight_v3_envelope()  # must not raise


def test_an_installed_envelope_is_used_and_validated() -> None:
    caps = [float(10 + 5 * i) for i in range(12)]
    m = model(ARCHITECTURE_V3, response_mode="spline", response_envelope_caps_gev=caps)
    m.preflight_v3_envelope()
    kinetic = torch.tensor([0.0, 30.0, 120.0, 299.0])
    got = m.response_cap_for(kinetic)
    assert torch.allclose(got, torch.tensor([caps[0], caps[1], caps[4], caps[11]]))
    # beyond the last bin clamps to the last cap rather than indexing out
    assert float(m.response_cap_for(torch.tensor([1e4]))[0]) == caps[-1]


def test_a_nonmonotone_or_nonpositive_envelope_is_rejected() -> None:
    bad = model(ARCHITECTURE_V3, response_mode="spline", response_envelope_caps_gev=[10.0, 9.0, 20.0])
    with pytest.raises(ValueError, match="nondecreasing"):
        bad.preflight_v3_envelope()
    worse = model(ARCHITECTURE_V3, response_mode="spline", response_envelope_caps_gev=[10.0, 0.0, 20.0])
    with pytest.raises(ValueError, match="strictly positive"):
        worse.preflight_v3_envelope()


def test_v3_response_loss_uses_the_envelope_cap() -> None:
    # With an envelope installed the response NLL must run through the bounded
    # spline; a target above the cap is fatal rather than clamped.
    caps = [1e-3] * 12  # absurdly tight so every truth response is outside it
    m = model(ARCHITECTURE_V3, response_mode="spline", response_envelope_caps_gev=caps)
    with pytest.raises(ValueError, match="outside its train-built envelope"):
        compute_component_losses(m, batch(), "response")


# --- incident-axis features are opt-in and actually reach the fields ----

def geometry_with_positions() -> dict[str, torch.Tensor]:
    g = geometry()
    # a simple layered detector: layers advance in z, cells spread in xy
    layer = g["layer_index"].float()
    within = torch.arange(N_NODES).float() % PER_LAYER
    g["cell_positions_mm"] = torch.stack(
        [(within - 1.5) * 20.0, (within % 2) * 15.0, layer * 40.0], dim=1
    )
    g["generator_vertex_mm"] = torch.zeros(3)
    return g


def axis_model(**extra) -> CBSCZDC:
    torch.manual_seed(0)
    return CBSCZDC(geometry_with_positions(), config(ARCHITECTURE_V3, axis_features=True, **extra))


def test_axis_features_are_off_by_default_even_under_v3() -> None:
    m = model(ARCHITECTURE_V3)
    assert m.axis_enabled is False
    assert m.support.axis_dim == 0
    # and the model runs without any position geometry at all
    compute_component_losses(m, batch(), "joint")


def test_axis_features_enable_only_when_declared() -> None:
    m = axis_model()
    assert m.axis_enabled is True
    assert m.support.axis_dim == 4
    assert m.share.axis_dim == 4


def test_enabling_axis_without_positions_fails_closed() -> None:
    with pytest.raises(ValueError, match="cell_positions_mm"):
        CBSCZDC(geometry(), config(ARCHITECTURE_V3, axis_features=True))


def test_axis_features_reach_the_support_and_share_fields() -> None:
    m = axis_model()
    b = batch()
    axis = m.axis_for(b["p4_total_gev"])
    assert axis is not None
    assert axis.shape == (b["p4_total_gev"].shape[0], N_NODES, 4)
    assert torch.isfinite(axis).all()
    # the field must refuse to run without them once declared
    cond = m.encode_condition(b["p4_total_gev"])
    counts = torch.ones(b["p4_total_gev"].shape[0], N_LAYERS, dtype=torch.long)
    energy = torch.ones(b["p4_total_gev"].shape[0], N_LAYERS)
    with pytest.raises(ValueError, match="axis features are declared"):
        m.support_logits(cond, energy, counts, axis=None)
    logits = m.support_logits(cond, energy, counts, axis=axis)
    assert torch.isfinite(logits[:, m.valid_mask]).all()


def test_a_field_without_axis_rejects_supplied_axis() -> None:
    m = model(ARCHITECTURE_V3)
    b = batch()
    cond = m.encode_condition(b["p4_total_gev"])
    counts = torch.ones(b["p4_total_gev"].shape[0], N_LAYERS, dtype=torch.long)
    energy = torch.ones(b["p4_total_gev"].shape[0], N_LAYERS)
    stray = torch.zeros(b["p4_total_gev"].shape[0], N_NODES, 4)
    with pytest.raises(ValueError, match="does not declare them"):
        m.support_logits(cond, energy, counts, axis=stray)


def test_axis_model_samples_and_holds_every_invariant() -> None:
    from cbsc_zdc.eval.invariants import invariant_report

    m = axis_model().eval()
    out = m.sample(batch()["p4_total_gev"], profile_steps=2, share_steps=2, seed=5)
    report = invariant_report(out, m.layer_index, m.valid_mask, m.threshold_gev)
    assert report["pass"], report


def test_axis_scales_come_from_geometry_and_are_floored() -> None:
    m = axis_model()
    assert m.axis_s_scale_mm >= 1.0
    assert m.axis_r_scale_mm >= 1.0
    # scales are frozen geometry, not per-batch statistics
    assert isinstance(m.axis_s_scale_mm, float)


def test_axis_enabled_run_computes_every_loss_and_backpropagates() -> None:
    # Regression: the support and share losses did not pass axis features, so an
    # axis-enabled run raised "axis features are declared but were not supplied"
    # on its very first update while the sampler worked fine.
    m = axis_model(**ALL_V3, response_envelope_caps_gev=[500.0] * 12)
    losses, _ = compute_component_losses(m, batch(), "joint")
    assert set(losses) == V3_STAGE_LOSSES["joint"]
    for key, value in losses.items():
        assert torch.isfinite(value), key
    weighted_total(losses, {name: 1.0 for name in V3_LOSS_WEIGHTS}).backward()
    # gradients reach the expanded input projections, which is where the axis
    # columns actually live
    for field in (m.support, m.share):
        grad = field.input[0].weight.grad
        assert grad is not None and grad.abs().sum() > 0


def test_axis_columns_receive_gradient_in_the_expanded_projection() -> None:
    m = axis_model(**ALL_V3, response_envelope_caps_gev=[500.0] * 12)
    losses, _ = compute_component_losses(m, batch(), "joint")
    weighted_total(losses, {name: 1.0 for name in V3_LOSS_WEIGHTS}).backward()
    node_dim = m.node_features.shape[1]
    for field in (m.support, m.share):
        axis_block = field.input[0].weight.grad[:, node_dim : node_dim + 4]
        assert axis_block.abs().sum() > 0, "axis columns received no gradient"


def test_axis_features_require_the_frozen_generator_vertex() -> None:
    # Defaulting to the origin would compute s and rho about the wrong point --
    # the production vertex sits about 35.5 m downstream in z -- and the features
    # would be meaningless while still looking perfectly valid.
    g = geometry_with_positions()
    del g["generator_vertex_mm"]
    with pytest.raises(ValueError, match="frozen generator vertex"):
        CBSCZDC(g, config(ARCHITECTURE_V3, axis_features=True))


def test_the_vertex_may_be_supplied_through_the_config() -> None:
    g = geometry_with_positions()
    del g["generator_vertex_mm"]
    m = CBSCZDC(
        g, config(ARCHITECTURE_V3, axis_features=True,
                  generator_vertex_mm=[-917.4075317382812, -30.0, 35488.90625])
    )
    assert torch.allclose(
        m.generator_vertex_mm,
        torch.tensor([-917.4075317382812, -30.0, 35488.90625]),
        atol=1e-3,
    )


def test_axis_coordinates_are_measured_from_the_declared_vertex() -> None:
    # Moving the vertex must move the coordinates; if it did not, the vertex
    # would be decorative and the origin bug would be invisible.
    g = geometry_with_positions()
    near = CBSCZDC(g, config(ARCHITECTURE_V3, axis_features=True))
    far_geometry = dict(g, generator_vertex_mm=torch.tensor([0.0, 0.0, 1000.0]))
    far = CBSCZDC(far_geometry, config(ARCHITECTURE_V3, axis_features=True))
    p4 = batch()["p4_total_gev"]
    assert not torch.allclose(near.axis_for(p4), far.axis_for(p4))


# ---------------------------------------------------------------------------
# M0-fresh: the zero-axis ablation control
# ---------------------------------------------------------------------------

def test_zero_ablation_keeps_the_axis_path_and_zeroes_only_the_values() -> None:
    """M0-fresh must differ from S1 only in what the axis columns carry."""
    ablated = axis_model(axis_zero_ablation=True)
    live = axis_model()
    # Same architecture, same parameter count: a row that merely disabled axis
    # features would differ in parameters too, so a loss difference could not be
    # attributed to the geometry the axis encodes.
    assert sum(p.numel() for p in ablated.parameters()) == sum(
        p.numel() for p in live.parameters()
    )
    assert ablated.axis_enabled is True

    p4 = torch.tensor([[150.0, 0.0, 0.0, 149.997]], dtype=torch.float32)
    zero_axis = ablated.axis_for(p4)
    real_axis = live.axis_for(p4)
    assert zero_axis.shape == real_axis.shape
    assert torch.count_nonzero(zero_axis) == 0
    # The live axis must actually carry information, or the control is vacuous.
    assert torch.count_nonzero(real_axis) > 0


def test_zero_ablation_without_axis_features_fails_closed() -> None:
    # axis_model() forces axis_features on, so build the config directly.
    with pytest.raises(ValueError, match="requires model.axis_features"):
        CBSCZDC(
            geometry_with_positions(),
            config(ARCHITECTURE_V3, axis_zero_ablation=True),
        )


def test_zero_ablation_is_off_by_default_under_v3() -> None:
    assert axis_model().axis_zero_ablation is False


def test_m0_is_standalone_and_does_not_leak_into_later_rows() -> None:
    """A control must not become a feature every later row inherits.

    The screening builder is cumulative by design: each row keeps what its
    predecessors turned on. M0-fresh sits first in that list, so without the
    standalone guard its axis_zero_ablation would be inherited by S1, S2 and
    every row after them -- silently converting each into a zero-axis ablation
    while still reporting itself under its original name.
    """
    import importlib.util
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "build_v3_screening_configs", root / "scripts" / "build_v3_screening_configs.py"
    )
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)

    m0 = next(r for r in builder.ROWS if r["id"] == "M0-fresh")
    assert m0["standalone"] is True
    assert m0["model"]["axis_zero_ablation"] is True

    # Replay the builder's cumulative accumulation exactly.
    cumulative: dict = {}
    inherited_by: dict[str, dict] = {}
    for row in builder.ROWS:
        if not row.get("standalone"):
            cumulative.update(row["model"])
        inherited_by[row["id"]] = dict(cumulative)
    for row_id, inherited in inherited_by.items():
        if row_id == "M0-fresh":
            continue
        assert "axis_zero_ablation" not in inherited, (
            f"{row_id} inherited the M0 control's ablation flag"
        )
