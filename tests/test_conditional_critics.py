"""D1/D2 conditional projection critics."""

from __future__ import annotations

import math

import torch
from torch import nn

from cbsc_zdc.models.critics import ProfileCritic, ProjectionHead, ShareCritic
from cbsc_zdc.training.adversarial import (
    DEFAULT_R1_GAMMA,
    DEFAULT_R1_INTERVAL,
    critic_logistic_loss,
    lazy_r1_multiplier,
    r1_penalty,
)

N_LAYERS, PER_LAYER = 4, 3
N_NODES = N_LAYERS * PER_LAYER
COND, NODE_DIM, EDGE_DIM, AXIS = 8, 5, 3, 4


def geometry():
    layer_index = torch.arange(N_LAYERS).repeat_interleave(PER_LAYER)
    edges = [[int(a), int(b)]
             for layer in range(N_LAYERS)
             for a in torch.nonzero(layer_index == layer).flatten()
             for b in torch.nonzero(layer_index == layer).flatten() if a != b]
    edge_index = torch.tensor(edges, dtype=torch.long).T
    return (
        torch.randn(N_NODES, NODE_DIM),
        edge_index,
        torch.randn(edge_index.shape[1], EDGE_DIM),
        layer_index,
        torch.ones(N_NODES, dtype=torch.bool),
    )


def share_critic() -> ShareCritic:
    torch.manual_seed(0)
    return ShareCritic(NODE_DIM, EDGE_DIM, COND, N_LAYERS, AXIS, hidden=16, blocks=2,
                       heads=2, context_layers=2, embed_dim=16)


def share_inputs(b: int = 3):
    nodes, edge_index, edge_features, layer_index, valid = geometry()
    cell = torch.rand(b, N_NODES).abs()
    layer_energy = torch.full((b, N_LAYERS), 2.0)
    support = torch.ones(b, N_NODES, dtype=torch.bool)
    axis = torch.randn(b, N_NODES, AXIS)
    return dict(
        cell_energy=cell, layer_energy=layer_energy, support_mask=support,
        node_features=nodes, axis=axis, edge_index=edge_index,
        edge_features=edge_features, layer_index=layer_index, valid_mask=valid,
    )


def test_projection_logit_has_batch_shape() -> None:
    critic = share_critic()
    cond = torch.randn(3, COND)
    score = critic(cond, **share_inputs(3))
    assert score.shape == (3,)
    assert torch.isfinite(score).all()

    profile = ProfileCritic(COND, N_LAYERS, token_width=16, heads=2, context_layers=1, embed_dim=16)
    p_score = profile(cond, torch.rand(3, N_LAYERS), torch.full((3,), 5.0),
                      torch.ones(3, N_LAYERS, dtype=torch.bool))
    assert p_score.shape == (3,)


def test_condition_shuffle_changes_projection_score() -> None:
    # A critic that ignores its condition would score identically under a
    # permuted condition; projection conditioning must prevent that.
    critic = share_critic()
    cond = torch.randn(3, COND)
    inputs = share_inputs(3)
    base = critic(cond, **inputs)
    shuffled = critic(cond.flip(0), **inputs)
    assert not torch.allclose(base, shuffled)


def test_all_declared_linear_projections_have_spectral_parametrization() -> None:
    for critic in (
        share_critic(),
        ProfileCritic(COND, N_LAYERS, token_width=16, heads=2, context_layers=1, embed_dim=16),
    ):
        head = critic.head
        for name in ("unconditional", "condition"):
            module = getattr(head, name)
            assert torch.nn.utils.parametrize.is_parametrized(module, "weight"), name


def test_projection_head_matches_hand_calculation() -> None:
    head = ProjectionHead(embed_dim=3, cond_dim=2)
    with torch.no_grad():
        torch.nn.utils.parametrize.remove_parametrizations(head.unconditional, "weight")
        torch.nn.utils.parametrize.remove_parametrizations(head.condition, "weight")
        head.unconditional.weight.copy_(torch.tensor([[1.0, 0.0, 0.0]]))
        head.unconditional.bias.zero_()
        head.condition.weight.copy_(torch.eye(3, 2))
        head.condition.bias.zero_()
    embedding = torch.tensor([[2.0, 3.0, 4.0]])
    cond = torch.tensor([[1.0, 1.0]])
    # u(h) = 2 ; <h, W c> with W c = [1,1,0] -> 2*1 + 3*1 + 4*0 = 5 ; total 7
    assert torch.allclose(head(embedding, cond), torch.tensor([7.0]))


def test_critic_logistic_loss_matches_hand_calculation() -> None:
    real = torch.tensor([2.0, -1.0])
    fake = torch.tensor([0.5, 1.5])
    expected = (
        (math.log1p(math.exp(-2.0)) + math.log1p(math.exp(1.0))) / 2
        + (math.log1p(math.exp(0.5)) + math.log1p(math.exp(1.5))) / 2
    )
    assert float(critic_logistic_loss(real, fake)) == round(expected, 6) or abs(
        float(critic_logistic_loss(real, fake)) - expected
    ) < 1e-6


def test_lazy_r1_multiplier_preserves_declared_expected_coefficient() -> None:
    assert DEFAULT_R1_INTERVAL == 16
    assert DEFAULT_R1_GAMMA == 1.0
    multipliers = [lazy_r1_multiplier(i) for i in range(64)]
    applied = [m for m in multipliers if m != 0.0]
    assert len(applied) == 4  # once every 16 updates
    assert all(m == 16.0 for m in applied)
    # expected coefficient over the window equals gamma * 1.0
    assert sum(multipliers) / len(multipliers) == 1.0


def test_r1_penalty_is_positive_and_uses_real_inputs_only() -> None:
    torch.manual_seed(1)
    linear = nn.Linear(4, 1)
    real = torch.randn(5, 4, requires_grad=True)
    scores = linear(real).squeeze(-1)
    penalty = r1_penalty(scores, [real], gamma=DEFAULT_R1_GAMMA)
    assert torch.isfinite(penalty) and float(penalty) > 0


def test_critic_monitor_state_is_not_shared_with_live_critic() -> None:
    live, monitor = share_critic(), share_critic()
    with torch.no_grad():
        for p in monitor.parameters():
            p.add_(1.0)
    live_params = dict(live.named_parameters())
    for name, p in monitor.named_parameters():
        assert p.data_ptr() != live_params[name].data_ptr()
        assert not torch.equal(p, live_params[name])


def test_share_critic_transformer_runs_over_layer_tokens_not_nodes() -> None:
    # The layer-context Transformer must see 65-style layer tokens. If it ever
    # received node tokens the sequence length would be N_NODES.
    critic = share_critic()
    assert critic.context.n_layers == N_LAYERS
    assert critic.layer_embedding.num_embeddings == N_LAYERS
    assert N_NODES != N_LAYERS  # the fixture would not detect a swap otherwise


def test_empty_layer_pooling_is_defined() -> None:
    # A layer with no valid channel must pool to zeros, not NaN or -inf.
    critic = share_critic()
    inputs = share_inputs(2)
    inputs["valid_mask"] = inputs["valid_mask"].clone()
    inputs["valid_mask"][:PER_LAYER] = False  # blank out layer 0
    score = critic(torch.randn(2, COND), **inputs)
    assert torch.isfinite(score).all()
