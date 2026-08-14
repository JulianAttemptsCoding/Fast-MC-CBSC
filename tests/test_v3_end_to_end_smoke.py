"""Synthetic v3 end-to-end smoke.

Covers, in one place, the minimum the specification requires: a supervised
update, an exact sample with every invariant, one D1 and one D2 critic and
generator update with isolation proved, checkpoint resume equivalence, and
proof that no test-split loader is ever constructed.
"""

from __future__ import annotations

from pathlib import Path

import torch
from torch import nn

from cbsc_zdc.contracts import NEUTRON_MASS_GEV
from cbsc_zdc.eval.invariants import invariant_report
from cbsc_zdc.models.critics import ProfileCritic, ShareCritic
from cbsc_zdc.models.response_v3 import BoundedResponseHead
from cbsc_zdc.models.system import CBSCZDC
from cbsc_zdc.training.adversarial import (
    GradientRatioController,
    critic_logistic_loss,
    freeze_parameters,
    generator_direct_loss,
    parameters_changed,
    restore_parameters,
    snapshot,
)
from cbsc_zdc.training.checkpoint import load_checkpoint, save_checkpoint
from cbsc_zdc.training.stage_sampling import (
    TruthStructure,
    sample_profile_for_loss,
    sample_share_for_loss,
)

N_LAYERS, PER_LAYER = 4, 3
N_NODES = N_LAYERS * PER_LAYER
COND = 16


def geometry():
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


def model() -> CBSCZDC:
    torch.manual_seed(0)
    return CBSCZDC(
        geometry(),
        {
            "model": {"condition_dim": COND, "hidden_dim": 16, "graph_blocks": 1,
                      "attention_heads": 2, "attention_layers": 1, "profile_hidden": 16,
                      "count_hidden": 16, "response_hidden": 16},
            "data": {"target_mode": "raw_deposit", "threshold_gev": 0.0},
        },
    )


def p4(batch: int = 4, energy: float = 120.0) -> torch.Tensor:
    total = torch.full((batch,), energy, dtype=torch.float64)
    momentum = torch.sqrt(total.square() - NEUTRON_MASS_GEV**2)
    return torch.stack([total, torch.zeros_like(total), torch.zeros_like(total), momentum], dim=1).float()


def truth(batch: int = 4) -> TruthStructure:
    support = torch.zeros(batch, N_NODES, dtype=torch.bool)
    for layer in range(N_LAYERS):
        support[:, layer * PER_LAYER : layer * PER_LAYER + 2] = True
    return TruthStructure(
        visible=torch.ones(batch, dtype=torch.bool),
        total_response=torch.full((batch,), 8.0),
        first_layer=torch.zeros(batch, dtype=torch.long),
        active_layers=torch.ones(batch, N_LAYERS, dtype=torch.bool),
        layer_energy=torch.full((batch, N_LAYERS), 2.0),
        requested_counts=torch.full((batch, N_LAYERS), 2, dtype=torch.long),
        support_mask=support,
    )


def test_synthetic_v3_supervised_forward_and_backward_are_finite() -> None:
    torch.manual_seed(1)
    head = BoundedResponseHead(COND, 32)
    cond = torch.randn(8, COND)
    cap = torch.full((8,), 60.0)
    bce, nll = head.nll(cond, torch.full((8,), 15.0), torch.ones(8, dtype=torch.bool), cap)
    total = bce + nll
    assert torch.isfinite(total)
    total.backward()
    grads = [p.grad for p in head.parameters() if p.grad is not None]
    assert grads and all(torch.isfinite(g).all() for g in grads)


def test_synthetic_exact_sample_passes_every_invariant() -> None:
    m = model().eval()
    out = m.sample(p4(), profile_steps=2, share_steps=2, seed=7)
    report = invariant_report(out, m.layer_index, m.valid_mask, m.threshold_gev)
    assert report["pass"], report
    assert report["negative"] == 0
    assert report["nonfinite"] == 0
    assert report["support_mask_mismatch"] == 0
    assert report["count_mismatch_max"] == 0


def test_one_d1_critic_and_generator_update_passes_isolation() -> None:
    torch.manual_seed(2)
    m, t = model(), truth()
    critic = ShareCritic(5, 3, COND, N_LAYERS, 4, hidden=16, blocks=1, heads=2,
                         context_layers=1, embed_dim=16)
    axis = torch.randn(4, N_NODES, 4)
    fake = sample_share_for_loss(m, p4(), t, torch.randn(4, N_NODES), share_steps=2)

    def score(cell):
        return critic(
            m.encode_condition(p4()), cell_energy=cell, layer_energy=t.layer_energy,
            support_mask=t.support_mask, node_features=m.node_features, axis=axis,
            edge_index=m.edge_index, edge_features=m.edge_features,
            layer_index=m.layer_index, valid_mask=m.valid_mask,
        )

    # --- critic update: fakes detached, only the critic may move
    before_gen, before_critic = snapshot(m), snapshot(critic)
    critic_opt = torch.optim.Adam(critic.parameters(), lr=1e-3)
    loss = critic_logistic_loss(score(torch.rand(4, N_NODES).abs()), score(fake.cell_energy.detach()))
    critic_opt.zero_grad()
    loss.backward()
    critic_opt.step()
    assert parameters_changed(before_critic, critic)
    assert parameters_changed(before_gen, m) == []

    # --- generator update: critic frozen by requires_grad, not no_grad
    before_gen, before_critic = snapshot(m), snapshot(critic)
    previous = freeze_parameters(critic)
    gen_opt = torch.optim.Adam(m.share.parameters(), lr=1e-3)
    fresh = sample_share_for_loss(m, p4(), t, torch.randn(4, N_NODES), share_steps=2)
    gen_loss = generator_direct_loss(score(fresh.cell_energy))
    gen_opt.zero_grad()
    gen_loss.backward()
    gen_opt.step()
    restore_parameters(critic, previous)

    changed = parameters_changed(before_gen, m)
    assert changed and all(n.startswith("share.") for n in changed), changed
    assert parameters_changed(before_critic, critic) == []


def test_one_d2_critic_and_generator_update_passes_isolation() -> None:
    torch.manual_seed(3)
    m = model()
    critic = ProfileCritic(COND, N_LAYERS, token_width=16, heads=2, context_layers=1, embed_dim=16)
    total = torch.full((4,), 8.0)
    active = torch.ones(4, N_LAYERS, dtype=torch.bool)
    out = sample_profile_for_loss(m, p4(), total, active, torch.randn(4, N_LAYERS), profile_steps=2)

    def score(layer_energy):
        return critic(m.encode_condition(p4()), layer_energy, total, active)

    before_gen, before_critic = snapshot(m), snapshot(critic)
    critic_opt = torch.optim.Adam(critic.parameters(), lr=1e-3)
    loss = critic_logistic_loss(score(torch.rand(4, N_LAYERS)), score(out.layer_energy.detach()))
    critic_opt.zero_grad()
    loss.backward()
    critic_opt.step()
    assert parameters_changed(before_critic, critic)
    assert parameters_changed(before_gen, m) == []

    before_gen, before_critic = snapshot(m), snapshot(critic)
    previous = freeze_parameters(critic)
    gen_opt = torch.optim.Adam(m.profile.flow.parameters(), lr=1e-3)
    fresh = sample_profile_for_loss(m, p4(), total, active, torch.randn(4, N_LAYERS), profile_steps=2)
    gen_opt.zero_grad()
    generator_direct_loss(score(fresh.layer_energy)).backward()
    gen_opt.step()
    restore_parameters(critic, previous)

    changed = parameters_changed(before_gen, m)
    assert changed and all(n.startswith("profile.flow.") for n in changed), changed
    assert parameters_changed(before_critic, critic) == []


def test_generator_updates_do_not_change_critic_parameters() -> None:
    torch.manual_seed(4)
    m = model()
    critic = ProfileCritic(COND, N_LAYERS, token_width=16, heads=2, context_layers=1, embed_dim=16)
    before = snapshot(critic)
    previous = freeze_parameters(critic)
    opt = torch.optim.Adam(m.profile.flow.parameters(), lr=1e-2)
    for _ in range(3):
        out = sample_profile_for_loss(
            m, p4(), torch.full((4,), 8.0), torch.ones(4, N_LAYERS, dtype=torch.bool),
            torch.randn(4, N_LAYERS), profile_steps=2,
        )
        opt.zero_grad()
        generator_direct_loss(
            critic(m.encode_condition(p4()), out.layer_energy, torch.full((4,), 8.0),
                   torch.ones(4, N_LAYERS, dtype=torch.bool))
        ).backward()
        opt.step()
    restore_parameters(critic, previous)
    assert parameters_changed(before, critic) == []


def test_checkpoint_resume_reproduces_next_update(tmp_path: Path) -> None:
    torch.manual_seed(5)
    m = model()
    opt = torch.optim.Adam(m.profile.flow.parameters(), lr=1e-3)
    controller = GradientRatioController()
    controller.lambda_value = 0.42

    def one_update(module, optimizer, noise):
        out = sample_profile_for_loss(
            module, p4(), torch.full((4,), 8.0), torch.ones(4, N_LAYERS, dtype=torch.bool),
            noise, profile_steps=2,
        )
        optimizer.zero_grad()
        out.layer_energy.square().sum().backward()
        optimizer.step()

    noise_a, noise_b = torch.randn(4, N_LAYERS), torch.randn(4, N_LAYERS)
    one_update(m, opt, noise_a)

    path = tmp_path / "v3.pt"
    save_checkpoint(
        path, m, opt, None, None, epoch=1, best_metric=1.0, config={}, stage="joint",
        provenance={}, architecture_version="cbsc-zdc-v3",
        experiment_contract_sha256="a" * 64,
        gradient_ratio_controller_state=controller.state_dict(),
        generator_update_count=1,
    )

    # uninterrupted
    one_update(m, opt, noise_b)
    uninterrupted = {k: v.detach().clone() for k, v in m.named_parameters()}

    # resumed
    resumed_model = model()
    resumed_opt = torch.optim.Adam(resumed_model.profile.flow.parameters(), lr=1e-3)
    payload = load_checkpoint(path, resumed_model, resumed_opt, expected_contract_sha256="a" * 64)
    resumed_controller = GradientRatioController()
    resumed_controller.load_state_dict(payload["gradient_ratio_controller_state"])
    one_update(resumed_model, resumed_opt, noise_b)

    worst = max(
        (uninterrupted[k] - v.detach()).abs().max().item()
        for k, v in resumed_model.named_parameters()
    )
    assert worst <= 1e-6, worst
    assert resumed_controller.lambda_value == controller.lambda_value
    assert payload["generator_update_count"] == 1


def test_no_test_split_loader_is_constructed() -> None:
    # Nothing in the v3 implementation may name the test split as a data source.
    import cbsc_zdc.training.replay as replay
    import cbsc_zdc.training.role_partition as role_partition
    import cbsc_zdc.training.stage_sampling as stage_sampling

    for module in (replay, role_partition, stage_sampling):
        source = Path(module.__file__).read_text(encoding="utf-8")
        lowered = source.lower()
        # 'test' may appear in prose and in guards that *forbid* it; what must
        # never appear is a loader or split selection that uses it.
        assert 'split="test"' not in lowered
        assert "split='test'" not in lowered
        assert "load_test" not in lowered

    # and the role partition actively rejects test ids
    from cbsc_zdc.training.role_partition import RolePartitionError, build_role_partition

    try:
        build_role_partition(
            [1, 2], counts={"generator_train": 1, "critic_real_train": 1},
            split_sha256="a" * 64, test_ids={2},
        )
    except RolePartitionError as exc:
        assert "test" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("test ids were not rejected")
