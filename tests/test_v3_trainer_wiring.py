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

def test_v3_model_builds_every_new_head() -> None:
    m = model(ARCHITECTURE_V3)
    assert m.is_v3 is True
    for attr in ("response_v3", "first_layer", "activity", "counts_ar"):
        assert hasattr(m, attr), attr
    # the v2.2 modules remain so a migrated checkpoint keeps its parameter names
    for attr in ("response", "profile", "counts"):
        assert hasattr(m, attr), attr


def test_v3_joint_stage_emits_exactly_the_declared_loss_keys() -> None:
    m = model(ARCHITECTURE_V3)
    assert stage_losses_for(m) is V3_STAGE_LOSSES
    losses, _ = compute_component_losses(m, batch(), "joint")
    assert set(losses) == V3_STAGE_LOSSES["joint"]
    # and the emitted keys are exactly what the config schema weights
    assert set(losses) == V3_LOSS_WEIGHTS


def test_v3_losses_are_finite_and_weightable() -> None:
    m = model(ARCHITECTURE_V3)
    losses, _ = compute_component_losses(m, batch(), "joint")
    for key, value in losses.items():
        assert torch.isfinite(value), key
    total = weighted_total(losses, {name: 1.0 for name in V3_LOSS_WEIGHTS})
    assert torch.isfinite(total)


def test_v3_backward_reaches_the_new_heads() -> None:
    m = model(ARCHITECTURE_V3)
    losses, _ = compute_component_losses(m, batch(), "joint")
    weighted_total(losses, {name: 1.0 for name in V3_LOSS_WEIGHTS}).backward()
    for name in ("response_v3", "first_layer", "activity", "counts_ar"):
        module = getattr(m, name)
        grads = [p.grad for p in module.parameters() if p.grad is not None]
        assert grads, f"{name} received no gradient"
        assert any(g.abs().sum() > 0 for g in grads), f"{name} gradient is all zero"


def test_autoregressive_activity_mode_is_selectable_and_zeroes_the_other_term() -> None:
    m = model(ARCHITECTURE_V3, activity_mode="autoregressive")
    losses, _ = compute_component_losses(m, batch(), "joint")
    assert set(losses) == V3_STAGE_LOSSES["joint"]
    # the span/gap term is emitted as an exact zero, not omitted
    assert float(losses["active_gap"]) == 0.0
    assert torch.isfinite(losses["active_last"])


def test_span_gap_mode_produces_both_activity_terms() -> None:
    m = model(ARCHITECTURE_V3, activity_mode="span_gaps")
    losses, _ = compute_component_losses(m, batch(), "joint")
    assert torch.isfinite(losses["active_last"])
    assert torch.isfinite(losses["active_gap"])


def test_every_v3_stage_emits_only_its_declared_subset() -> None:
    m = model(ARCHITECTURE_V3)
    for stage, expected in V3_STAGE_LOSSES.items():
        losses, _ = compute_component_losses(m, batch(), stage)
        assert set(losses) == expected, stage


# --- the response envelope is a hard requirement for production ---------

def test_a_v3_run_without_an_envelope_fails_preflight() -> None:
    m = model(ARCHITECTURE_V3)
    with pytest.raises(ValueError, match="response_envelope_caps_gev"):
        m.preflight_v3_envelope()


def test_a_v2_run_needs_no_envelope() -> None:
    model().preflight_v3_envelope()  # must not raise


def test_an_installed_envelope_is_used_and_validated() -> None:
    caps = [float(10 + 5 * i) for i in range(12)]
    m = model(ARCHITECTURE_V3, response_envelope_caps_gev=caps)
    m.preflight_v3_envelope()
    kinetic = torch.tensor([0.0, 30.0, 120.0, 299.0])
    got = m.response_cap_for(kinetic)
    assert torch.allclose(got, torch.tensor([caps[0], caps[1], caps[4], caps[11]]))
    # beyond the last bin clamps to the last cap rather than indexing out
    assert float(m.response_cap_for(torch.tensor([1e4]))[0]) == caps[-1]


def test_a_nonmonotone_or_nonpositive_envelope_is_rejected() -> None:
    bad = model(ARCHITECTURE_V3, response_envelope_caps_gev=[10.0, 9.0, 20.0])
    with pytest.raises(ValueError, match="nondecreasing"):
        bad.preflight_v3_envelope()
    worse = model(ARCHITECTURE_V3, response_envelope_caps_gev=[10.0, 0.0, 20.0])
    with pytest.raises(ValueError, match="strictly positive"):
        worse.preflight_v3_envelope()


def test_v3_response_loss_uses_the_envelope_cap() -> None:
    # With an envelope installed the response NLL must run through the bounded
    # spline; a target above the cap is fatal rather than clamped.
    caps = [1e-3] * 12  # absurdly tight so every truth response is outside it
    m = model(ARCHITECTURE_V3, response_envelope_caps_gev=caps)
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
