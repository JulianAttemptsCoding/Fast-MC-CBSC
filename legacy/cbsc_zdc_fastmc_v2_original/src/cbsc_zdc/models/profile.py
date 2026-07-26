from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import nn
from torch.distributions import Beta, Categorical


@dataclass
class ProfileOutput:
    visible: torch.Tensor
    response_fraction: torch.Tensor
    total: torch.Tensor
    first_visible_layer: torch.Tensor
    active_layers: torch.Tensor
    layer_energy: torch.Tensor
    reserve: torch.Tensor
    layer_weights: torch.Tensor


class VisibleResponseHead(nn.Module):
    """Bernoulli hurdle for events with no modeled visible response."""

    def __init__(self, cond_dim: int = 128, latent_dim: int = 32, hidden: int = 128):
        super().__init__()
        self.latent_dim = latent_dim
        self.net = nn.Sequential(
            nn.Linear(cond_dim + latent_dim, hidden),
            nn.SiLU(),
            nn.Linear(hidden, 1),
        )

    def forward(self, cond: torch.Tensor, z: torch.Tensor) -> torch.Tensor:
        return self.net(torch.cat((cond, z), dim=-1))


class MixtureBetaResponse(nn.Module):
    """Bounded mixture model for rho = E_dep / E_inc in [0, 1].

    This support is appropriate only after the stored target has been audited as raw
    deposited energy with no legitimate overflow beyond incident total energy.
    """

    def __init__(
        self,
        cond_dim: int = 128,
        latent_dim: int = 32,
        hidden: int = 192,
        components: int = 4,
        concentration_floor: float = 0.2,
    ):
        super().__init__()
        self.components = components
        self.concentration_floor = concentration_floor
        self.net = nn.Sequential(
            nn.Linear(cond_dim + latent_dim, hidden),
            nn.SiLU(),
            nn.Linear(hidden, hidden),
            nn.SiLU(),
            nn.Linear(hidden, 3 * components),
        )

    def parameters_from_condition(
        self, cond: torch.Tensor, z: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        raw = self.net(torch.cat((cond, z), dim=-1))
        mix_logits, raw_alpha, raw_beta = raw.chunk(3, dim=-1)
        alpha = torch.nn.functional.softplus(raw_alpha) + self.concentration_floor
        beta = torch.nn.functional.softplus(raw_beta) + self.concentration_floor
        return mix_logits, alpha, beta

    def sample(
        self,
        cond: torch.Tensor,
        z: torch.Tensor,
        stochastic: bool = True,
    ) -> torch.Tensor:
        mix_logits, alpha, beta = self.parameters_from_condition(cond, z)
        if stochastic:
            component = Categorical(logits=mix_logits).sample()
        else:
            component = mix_logits.argmax(dim=-1)
        chosen_alpha = alpha.gather(1, component[:, None]).squeeze(1)
        chosen_beta = beta.gather(1, component[:, None]).squeeze(1)
        if stochastic:
            response = Beta(chosen_alpha, chosen_beta).sample()
        else:
            response = chosen_alpha / (chosen_alpha + chosen_beta)
        return response[:, None]


class FirstVisibleLayerHazard(nn.Module):
    """Discrete survival/hazard model for the first visible detector layer."""

    def __init__(
        self,
        cond_dim: int = 128,
        latent_dim: int = 32,
        n_layers: int = 65,
        hidden: int = 192,
    ):
        super().__init__()
        self.n_layers = n_layers
        self.net = nn.Sequential(
            nn.Linear(cond_dim + latent_dim + 1, hidden),
            nn.SiLU(),
            nn.Linear(hidden, hidden),
            nn.SiLU(),
            nn.Linear(hidden, n_layers),
        )

    def conditional_start_logits(
        self, cond: torch.Tensor, z: torch.Tensor, response_fraction: torch.Tensor
    ) -> torch.Tensor:
        hazard_logits = self.net(torch.cat((cond, z, response_fraction), dim=-1))
        log_hazard = torch.nn.functional.logsigmoid(hazard_logits)
        log_survival = torch.nn.functional.logsigmoid(-hazard_logits)
        prefix = torch.cat(
            (
                torch.zeros_like(log_survival[:, :1]),
                torch.cumsum(log_survival[:, :-1], dim=-1),
            ),
            dim=-1,
        )
        # Categorical sampling normalizes over starts that occur inside the detector.
        return log_hazard + prefix


class LayerActivityHead(nn.Module):
    """Correlated layer-activity logits conditioned on a shared event latent.

    The output is a stochastic binary support over ECAL + HCAL layers. Exact inactive
    layers are generated before positive layer-energy allocation, avoiding the dense
    positive support induced by a plain softmax.
    """

    def __init__(
        self,
        cond_dim: int = 128,
        latent_dim: int = 32,
        n_layers: int = 65,
        hidden: int = 192,
    ):
        super().__init__()
        self.n_layers = n_layers
        self.net = nn.Sequential(
            nn.Linear(cond_dim + latent_dim + 1, hidden),
            nn.SiLU(),
            nn.Linear(hidden, hidden),
            nn.SiLU(),
            nn.Linear(hidden, n_layers),
        )

    def forward(
        self, cond: torch.Tensor, z: torch.Tensor, response_fraction: torch.Tensor
    ) -> torch.Tensor:
        return self.net(torch.cat((cond, z, response_fraction), dim=-1))


class MaskedSimplexProfile(nn.Module):
    """Stochastic positive allocation over active layers plus a reserve channel.

    The current implementation is a logistic-normal reference sampler. The research
    specification permits replacing this module with a low-dimensional conditional flow
    matching model over the same masked-simplex target without changing the decoder.
    """

    def __init__(
        self,
        cond_dim: int = 128,
        latent_dim: int = 32,
        n_layers: int = 65,
        hidden: int = 256,
    ):
        super().__init__()
        self.n_layers = n_layers
        self.net = nn.Sequential(
            nn.Linear(cond_dim + latent_dim + 1, hidden),
            nn.SiLU(),
            nn.Linear(hidden, hidden),
            nn.SiLU(),
            nn.Linear(hidden, n_layers + 1),
        )

    def forward(
        self,
        cond: torch.Tensor,
        z: torch.Tensor,
        total: torch.Tensor,
        active_layers: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        raw = self.net(torch.cat((cond, z, total), dim=-1))
        layer_logits = raw[:, : self.n_layers]
        reserve_logit = raw[:, self.n_layers :]
        neg_inf = torch.finfo(layer_logits.dtype).min
        masked_layer_logits = torch.where(
            active_layers.bool(), layer_logits, torch.full_like(layer_logits, neg_inf)
        )
        logits = torch.cat((masked_layer_logits, reserve_logit), dim=-1)
        weights = torch.softmax(logits, dim=-1)
        layer_energy = total * weights[:, : self.n_layers]
        reserve = total * weights[:, self.n_layers :]
        return layer_energy, reserve, weights


class LongitudinalProfileModel(nn.Module):
    """Hurdle + bounded response + exact-zero layer support + simplex allocation."""

    def __init__(
        self,
        cond_dim: int = 128,
        latent_dim: int = 32,
        n_layers: int = 65,
        response_components: int = 4,
    ):
        super().__init__()
        self.latent_dim = latent_dim
        self.n_layers = n_layers
        self.visible_head = VisibleResponseHead(cond_dim, latent_dim)
        self.response = MixtureBetaResponse(
            cond_dim, latent_dim, components=response_components
        )
        self.start = FirstVisibleLayerHazard(cond_dim, latent_dim, n_layers)
        self.activity = LayerActivityHead(cond_dim, latent_dim, n_layers)
        self.profile = MaskedSimplexProfile(cond_dim, latent_dim, n_layers)

    def sample(
        self,
        incident_e: torch.Tensor,
        cond: torch.Tensor,
        z_event: torch.Tensor | None = None,
        stochastic: bool = True,
    ) -> ProfileOutput:
        batch = cond.shape[0]
        if z_event is None:
            if stochastic:
                z_event = torch.randn(
                    batch,
                    self.latent_dim,
                    device=cond.device,
                    dtype=cond.dtype,
                )
            else:
                z_event = torch.zeros(
                    batch,
                    self.latent_dim,
                    device=cond.device,
                    dtype=cond.dtype,
                )
        visible_prob = torch.sigmoid(self.visible_head(cond, z_event))
        if stochastic:
            visible = torch.bernoulli(visible_prob)
        else:
            visible = (visible_prob >= 0.5).to(cond.dtype)

        rho = self.response.sample(cond, z_event, stochastic=stochastic)
        rho = rho * visible
        total = incident_e * rho

        start_logits = self.start.conditional_start_logits(cond, z_event, rho)
        if stochastic:
            first_visible = Categorical(logits=start_logits).sample()
        else:
            first_visible = start_logits.argmax(dim=-1)
        first_visible = torch.where(
            visible.squeeze(-1) > 0, first_visible, torch.full_like(first_visible, -1)
        )

        activity_logits = self.activity(cond, z_event, rho)
        activity_prob = torch.sigmoid(activity_logits)
        if stochastic:
            active = torch.bernoulli(activity_prob)
        else:
            active = (activity_prob >= 0.5).to(cond.dtype)
        layer_ids = torch.arange(self.n_layers, device=cond.device)[None]
        before_start = layer_ids < first_visible.clamp_min(0)[:, None]
        active = active.masked_fill(before_start, 0.0) * visible
        visible_rows = visible.squeeze(-1) > 0
        if visible_rows.any():
            active[visible_rows, first_visible[visible_rows]] = 1.0

        layer_energy, reserve, weights = self.profile(
            cond, z_event, total, active
        )
        return ProfileOutput(
            visible=visible,
            response_fraction=rho,
            total=total,
            first_visible_layer=first_visible,
            active_layers=active,
            layer_energy=layer_energy,
            reserve=reserve,
            layer_weights=weights,
        )
