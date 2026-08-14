"""Adversarial update isolation and the gradient-ratio controller.

These are the checks that decide whether an adversarial result means anything.
If a generator update silently moved critic parameters, or a D1 update moved the
profile flow, the experiment would be uninterpretable.
"""

from __future__ import annotations

import pytest
import torch
from torch import nn

from cbsc_zdc.training.adversarial import (
    LAMBDA_MAX,
    LAMBDA_MIN,
    OBSERVED_RATIO_ABORT,
    RATIO_EMA_DECAY,
    GradientRatioController,
    critic_logistic_loss,
    freeze_parameters,
    generator_direct_loss,
    generator_feature_matching_loss,
    parameters_changed,
    restore_parameters,
    snapshot,
)


class TinyGenerator(nn.Module):
    """Two independent 'modules' standing in for the share and profile flows."""

    def __init__(self) -> None:
        super().__init__()
        self.share = nn.Linear(4, 4)
        self.profile = nn.Linear(4, 4)

    def forward(self, x, which):
        return getattr(self, which)(x)


class TinyCritic(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.net = nn.Linear(4, 1)

    def forward(self, x):
        return self.net(x).squeeze(-1)

    def features(self, x):
        return self.net(x)


def setup():
    torch.manual_seed(0)
    return TinyGenerator(), TinyCritic(), torch.randn(6, 4)


def test_critic_update_detaches_fake_and_changes_only_critic() -> None:
    generator, critic, x = setup()
    optimizer = torch.optim.Adam(critic.parameters(), lr=1e-2)
    before_generator = snapshot(generator)
    before_critic = snapshot(critic)

    fake = generator(x, "share").detach()  # detached: critic cannot move the generator
    loss = critic_logistic_loss(critic(torch.randn(6, 4)), critic(fake))
    optimizer.zero_grad()
    loss.backward()
    optimizer.step()

    assert parameters_changed(before_critic, critic)
    assert parameters_changed(before_generator, generator) == []
    assert all(p.grad is None for p in generator.parameters())


def test_generator_update_freezes_critic_parameters_without_no_grad() -> None:
    generator, critic, x = setup()
    optimizer = torch.optim.Adam(generator.parameters(), lr=1e-2)
    before_critic = snapshot(critic)

    previous = freeze_parameters(critic)
    assert all(not p.requires_grad for p in critic.parameters())

    fake = generator(x, "share")
    loss = generator_direct_loss(critic(fake))
    optimizer.zero_grad()
    loss.backward()
    optimizer.step()

    # The gradient still reached the generator *through* the critic, which a
    # torch.no_grad() wrapper would have severed.
    assert any(p.grad is not None and p.grad.abs().sum() > 0 for p in generator.share.parameters())
    assert all(p.grad is None for p in critic.parameters())
    assert parameters_changed(before_critic, critic) == []

    restore_parameters(critic, previous)
    assert all(p.requires_grad for p in critic.parameters())


def test_d1_generator_update_changes_only_share_flow() -> None:
    generator, critic, x = setup()
    optimizer = torch.optim.Adam(generator.parameters(), lr=1e-2)
    before = snapshot(generator)
    freeze_parameters(critic)

    loss = generator_direct_loss(critic(generator(x, "share")))
    optimizer.zero_grad()
    loss.backward()
    optimizer.step()

    changed = parameters_changed(before, generator)
    assert changed and all(name.startswith("share.") for name in changed), changed


def test_d2_generator_update_changes_only_profile_flow() -> None:
    generator, critic, x = setup()
    optimizer = torch.optim.Adam(generator.parameters(), lr=1e-2)
    before = snapshot(generator)
    freeze_parameters(critic)

    loss = generator_direct_loss(critic(generator(x, "profile")))
    optimizer.zero_grad()
    loss.backward()
    optimizer.step()

    changed = parameters_changed(before, generator)
    assert changed and all(name.startswith("profile.") for name in changed), changed


def test_direct_loss_has_nonzero_input_gradient() -> None:
    _, critic, x = setup()
    fake = x.clone().requires_grad_(True)
    generator_direct_loss(critic(fake)).backward()
    assert fake.grad is not None and fake.grad.abs().sum() > 0


def test_feature_loss_has_nonzero_input_gradient() -> None:
    _, critic, x = setup()
    fake = x.clone().requires_grad_(True)
    real = torch.randn(6, 4)
    generator_feature_matching_loss(critic.features(real), critic.features(fake)).backward()
    assert fake.grad is not None and fake.grad.abs().sum() > 0


def test_gradient_ratio_formula_matches_hand_fixture() -> None:
    # A parameter whose base gradient norm is 4 and adversarial norm is 2, with
    # rho_target 0.10, gives lambda_raw = 0.10 * 4 / 2 = 0.2.
    parameter = nn.Parameter(torch.zeros(1))
    base = (parameter * 4.0).sum()
    adversarial = (parameter * 2.0).sum()
    controller = GradientRatioController(rho_target=0.10, ema_decay=0.0)
    record = controller.update(base, adversarial, [parameter])
    assert record["base_grad_norm"] == pytest.approx(4.0)
    assert record["adversarial_grad_norm"] == pytest.approx(2.0)
    assert record["lambda_raw"] == pytest.approx(0.2)
    assert record["lambda"] == pytest.approx(0.2)  # ema_decay 0 -> take the new value
    assert record["rho_observed"] == pytest.approx(0.1)


def test_ratio_controller_ema_and_clamps_are_exact() -> None:
    assert RATIO_EMA_DECAY == 0.9
    parameter = nn.Parameter(torch.zeros(1))
    controller = GradientRatioController(rho_target=0.10, ema_decay=0.9)
    controller.lambda_value = 1.0
    record = controller.update((parameter * 4.0).sum(), (parameter * 2.0).sum(), [parameter])
    # 0.9 * 1.0 + 0.1 * 0.2 = 0.92
    assert record["lambda"] == pytest.approx(0.92)

    # clamps: a vanishing adversarial gradient must not produce an unbounded weight
    huge = GradientRatioController(rho_target=1e9, ema_decay=0.0)
    r = huge.update((parameter * 1.0).sum(), (parameter * 1e-12).sum(), [parameter])
    assert r["lambda"] == pytest.approx(LAMBDA_MAX)
    tiny = GradientRatioController(rho_target=1e-12, ema_decay=0.0)
    r = tiny.update((parameter * 1.0).sum(), (parameter * 1e9).sum(), [parameter])
    assert r["lambda"] == pytest.approx(LAMBDA_MIN)


def test_observed_ratio_above_0_25_is_reported_as_failure() -> None:
    assert OBSERVED_RATIO_ABORT == 0.25
    parameter = nn.Parameter(torch.zeros(1))
    controller = GradientRatioController(rho_target=0.5, ema_decay=0.0)
    record = controller.update((parameter * 1.0).sum(), (parameter * 1.0).sum(), [parameter])
    assert record["rho_observed"] > OBSERVED_RATIO_ABORT
    assert record["failed"] is True
    # and a healthy ratio is not reported as a failure
    ok = GradientRatioController(rho_target=0.10, ema_decay=0.0)
    healthy = ok.update((parameter * 4.0).sum(), (parameter * 2.0).sum(), [parameter])
    assert healthy["failed"] is False


def test_controller_logs_component_cosines() -> None:
    parameter = nn.Parameter(torch.zeros(1))
    controller = GradientRatioController(rho_target=0.10, ema_decay=0.0)
    record = controller.update(
        (parameter * 4.0).sum(), (parameter * 2.0).sum(), [parameter],
        component_losses={"aligned": (parameter * 1.0).sum(), "opposed": (parameter * -1.0).sum()},
    )
    assert record["component_cosines"]["aligned"] == pytest.approx(1.0)
    assert record["component_cosines"]["opposed"] == pytest.approx(-1.0)


def test_controller_state_round_trips() -> None:
    controller = GradientRatioController(rho_target=0.2, ema_decay=0.5)
    controller.lambda_value = 0.37
    controller.measurements = 5
    restored = GradientRatioController()
    restored.load_state_dict(controller.state_dict())
    assert restored.lambda_value == pytest.approx(0.37)
    assert restored.rho_target == pytest.approx(0.2)
    assert restored.measurements == 5


def test_measure_interval_is_every_sixteen_updates() -> None:
    controller = GradientRatioController()
    assert controller.should_measure(0)
    assert not controller.should_measure(1)
    assert controller.should_measure(16)
    assert controller.should_measure(32)
