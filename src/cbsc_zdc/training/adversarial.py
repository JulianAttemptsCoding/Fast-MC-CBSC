"""Adversarial update mechanics: losses, lazy R1, and the gradient-ratio controller.

Three things here are easy to get subtly wrong, so each is isolated and tested:

**Update isolation.**  The critic update sees *detached* fakes, so it can only
move critic parameters.  The generator update then freezes the critic by
clearing ``requires_grad`` on its parameters -- **not** by wrapping it in
``torch.no_grad()``, which would also stop the gradient reaching the generator
through the critic's input and leave the generator with no signal at all.

**Lazy R1.**  The gradient penalty is applied every ``interval`` critic updates
and multiplied by ``interval``, so its expected contribution is unchanged while
costing a fraction of the double-backward passes.

**Gradient ratio.**  The adversarial weight is set from measured gradient norms
rather than guessed, targeting ``rho`` = |lambda * g_adv| / |g_base|.  It is
measured every 16 updates and held constant in between, and an observed ratio
above 0.25 is reported as a failed artifact rather than silently rescaled.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

import torch
from torch import nn
from torch.nn import functional as F

DEFAULT_R1_GAMMA = 1.0
DEFAULT_R1_INTERVAL = 16
DEFAULT_RATIO_TARGET = 0.10
RATIO_MEASURE_INTERVAL = 16
RATIO_EMA_DECAY = 0.9
LAMBDA_MIN = 1e-5
LAMBDA_MAX = 10.0
OBSERVED_RATIO_ABORT = 0.25


def critic_logistic_loss(real_scores: torch.Tensor, fake_scores: torch.Tensor) -> torch.Tensor:
    """Non-saturating logistic critic loss.

    ``softplus(-d_real) + softplus(d_fake)``: zero when the critic is certain and
    correct, growing when it is wrong.  Fakes must already be detached.
    """
    return F.softplus(-real_scores).mean() + F.softplus(fake_scores).mean()


def generator_direct_loss(fake_scores: torch.Tensor) -> torch.Tensor:
    """Non-saturating generator loss: push fakes toward "real"."""
    return F.softplus(-fake_scores).mean()


def generator_feature_matching_loss(
    real_features: torch.Tensor, fake_features: torch.Tensor
) -> torch.Tensor:
    """Squared distance between mean critic embeddings.

    The stability control for the direct objective.  It is a *separate*
    experiment, never summed with the direct loss in the same run.
    """
    return (real_features.mean(dim=0) - fake_features.mean(dim=0)).pow(2).sum()


def r1_penalty(
    critic_scores: torch.Tensor, real_inputs: Iterable[torch.Tensor], gamma: float = DEFAULT_R1_GAMMA
) -> torch.Tensor:
    """``gamma/2 * E||grad_real D||^2``, computed on real inputs only."""
    inputs = [t for t in real_inputs if t.requires_grad]
    if not inputs:
        raise ValueError("R1 requires at least one real input with requires_grad=True")
    grads = torch.autograd.grad(
        critic_scores.sum(), inputs, create_graph=True, retain_graph=True
    )
    squared = sum(g.pow(2).flatten(1).sum(dim=1) for g in grads)
    return (gamma / 2.0) * squared.mean()


def lazy_r1_multiplier(update_index: int, interval: int = DEFAULT_R1_INTERVAL) -> float:
    """Return ``interval`` on an R1 step and ``0.0`` otherwise.

    Applying the penalty on one update in ``interval`` and scaling it by
    ``interval`` leaves the expected coefficient at ``gamma``.
    """
    if interval <= 0:
        raise ValueError("R1 interval must be positive")
    return float(interval) if (update_index % interval == 0) else 0.0


def freeze_parameters(module: nn.Module) -> list[torch.Tensor]:
    """Clear ``requires_grad`` on a module, returning the previous flags.

    Used to freeze the critic during a generator update.  Deliberately not
    ``torch.no_grad()``: the generator's gradient must still flow *through* the
    critic's input, and a no-grad context would sever it.
    """
    previous = [p.requires_grad for p in module.parameters()]
    for p in module.parameters():
        p.requires_grad_(False)
    return previous


def restore_parameters(module: nn.Module, previous: list[bool]) -> None:
    for p, flag in zip(module.parameters(), previous):
        p.requires_grad_(flag)


def _flat_grad_norm(
    loss: torch.Tensor, parameters: list[torch.nn.Parameter]
) -> tuple[float, list[torch.Tensor]]:
    grads = torch.autograd.grad(
        loss, parameters, retain_graph=True, allow_unused=True, create_graph=False
    )
    filled = [g if g is not None else torch.zeros_like(p) for g, p in zip(grads, parameters)]
    norm = torch.sqrt(sum(g.pow(2).sum() for g in filled)).item()
    return norm, filled


@dataclass
class GradientRatioController:
    """Sets the adversarial weight from measured gradient norms."""

    rho_target: float = DEFAULT_RATIO_TARGET
    measure_interval: int = RATIO_MEASURE_INTERVAL
    ema_decay: float = RATIO_EMA_DECAY
    lambda_min: float = LAMBDA_MIN
    lambda_max: float = LAMBDA_MAX
    abort_threshold: float = OBSERVED_RATIO_ABORT
    lambda_value: float = 1.0
    measurements: int = 0
    history: list[dict] = field(default_factory=list)

    def should_measure(self, update_index: int) -> bool:
        return update_index % self.measure_interval == 0

    def update(
        self,
        base_loss: torch.Tensor,
        adversarial_loss: torch.Tensor,
        parameters: list[torch.nn.Parameter],
        *,
        component_losses: dict[str, torch.Tensor] | None = None,
    ) -> dict:
        """Measure both gradients and refresh ``lambda`` by EMA.

        ``lambda_raw = rho_target * |g_base| / |g_adv|`` is clamped, then blended
        with the previous value so the weight cannot jump on one noisy batch.
        """
        base_norm, base_grads = _flat_grad_norm(base_loss, parameters)
        adv_norm, adv_grads = _flat_grad_norm(adversarial_loss, parameters)
        lambda_raw = self.rho_target * base_norm / (adv_norm + 1e-12)
        lambda_new = min(max(lambda_raw, self.lambda_min), self.lambda_max)
        self.lambda_value = self.ema_decay * self.lambda_value + (1 - self.ema_decay) * lambda_new
        observed = self.lambda_value * adv_norm / (base_norm + 1e-12)

        cosines = {}
        if component_losses:
            adv_flat = torch.cat([g.flatten() for g in adv_grads])
            adv_norm_t = adv_flat.norm()
            for name, component in component_losses.items():
                _, component_grads = _flat_grad_norm(component, parameters)
                flat = torch.cat([g.flatten() for g in component_grads])
                cosines[name] = float(
                    (adv_flat * flat).sum() / (adv_norm_t * flat.norm() + 1e-12)
                )

        record = {
            "base_grad_norm": base_norm,
            "adversarial_grad_norm": adv_norm,
            "lambda_raw": lambda_raw,
            "lambda_new": lambda_new,
            "lambda": self.lambda_value,
            "rho_target": self.rho_target,
            "rho_observed": observed,
            "component_cosines": cosines,
            "nonfinite": not (
                torch.isfinite(torch.tensor(base_norm)) and torch.isfinite(torch.tensor(adv_norm))
            ),
        }
        record["failed"] = bool(
            record["nonfinite"] or observed > self.abort_threshold
        )
        self.measurements += 1
        self.history.append(record)
        return record

    def state_dict(self) -> dict:
        return {
            "rho_target": self.rho_target,
            "measure_interval": self.measure_interval,
            "ema_decay": self.ema_decay,
            "lambda_value": self.lambda_value,
            "measurements": self.measurements,
        }

    def load_state_dict(self, state: dict) -> None:
        self.rho_target = float(state["rho_target"])
        self.measure_interval = int(state["measure_interval"])
        self.ema_decay = float(state["ema_decay"])
        self.lambda_value = float(state["lambda_value"])
        self.measurements = int(state["measurements"])


def parameters_changed(before: dict[str, torch.Tensor], module: nn.Module) -> list[str]:
    """Names whose values moved, for proving update isolation."""
    changed = []
    for name, parameter in module.named_parameters():
        if name in before and not torch.equal(before[name], parameter.detach()):
            changed.append(name)
    return changed


def snapshot(module: nn.Module) -> dict[str, torch.Tensor]:
    return {name: p.detach().clone() for name, p in module.named_parameters()}
