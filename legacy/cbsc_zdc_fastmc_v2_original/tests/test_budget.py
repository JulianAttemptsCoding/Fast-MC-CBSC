import torch

from cbsc_zdc.models.profile import LongitudinalProfileModel


def test_profile_identity_and_nonmonotone_deposits_allowed():
    torch.manual_seed(3)
    model = LongitudinalProfileModel(cond_dim=8, latent_dim=4, n_layers=5)
    cond = torch.randn(32, 8)
    incident = torch.full((32, 1), 100.0)
    out = model.sample(incident, cond, stochastic=True)
    assert torch.all(out.total >= 0)
    assert torch.all(out.total <= incident)
    assert torch.all(out.layer_energy >= 0)
    assert torch.all(out.reserve >= 0)
    assert torch.allclose(
        out.layer_energy.sum(dim=-1, keepdim=True) + out.reserve,
        out.total,
        atol=1e-5,
    )
    assert torch.all(out.layer_energy[out.active_layers == 0] == 0)
    assert out.layer_energy.shape == (32, 5)


def test_first_visible_layer_is_active_and_preceding_layers_are_inactive():
    torch.manual_seed(9)
    model = LongitudinalProfileModel(cond_dim=8, latent_dim=4, n_layers=7)
    cond = torch.randn(64, 8)
    incident = torch.full((64, 1), 80.0)
    out = model.sample(incident, cond, stochastic=True)
    visible_rows = out.visible.squeeze(-1) > 0
    for event in torch.where(visible_rows)[0]:
        start = int(out.first_visible_layer[event].item())
        assert out.active_layers[event, start] == 1
        assert torch.all(out.active_layers[event, :start] == 0)


def test_profile_accepts_explicit_event_latent():
    torch.manual_seed(4)
    model = LongitudinalProfileModel(cond_dim=8, latent_dim=4, n_layers=5)
    cond = torch.randn(3, 8)
    incident = torch.full((3, 1), 60.0)
    z_event = torch.zeros(3, 4)
    out = model.sample(incident, cond, z_event=z_event, stochastic=False)
    assert out.layer_energy.shape == (3, 5)
