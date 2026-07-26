from pathlib import Path

import torch

from cbsc_zdc.data.dataset import ShardedSparseDataset, load_geometry
from cbsc_zdc.data.synthetic import create_synthetic_dataset
from cbsc_zdc.models.system import CBSCZDC
from cbsc_zdc.training.trainer import (
    _restart_cosine_scheduler,
    compute_component_losses,
)
from cbsc_zdc.training.weights import calibrate_loss_weights, weighted_total


class Tiny(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.condition = torch.nn.Linear(2, 2, bias=False)


def test_scheduler_restart_rebases_lr_and_remaining_horizon():
    parameter = torch.nn.Parameter(torch.tensor(1.0))
    optimizer = torch.optim.AdamW([parameter], lr=0.1)
    old_scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer,
        T_max=2,
        eta_min=0.01,
    )
    for _ in range(2):
        parameter.grad = torch.tensor(1.0)
        optimizer.step()
        old_scheduler.step()
    assert optimizer.param_groups[0]["lr"] == 0.01
    exp_avg_before = optimizer.state[parameter]["exp_avg"].clone()

    scheduler = _restart_cosine_scheduler(
        optimizer,
        learning_rate=0.05,
        minimum_learning_rate=0.005,
        remaining_updates=4,
    )

    assert optimizer.param_groups[0]["lr"] == 0.05
    assert optimizer.param_groups[0]["initial_lr"] == 0.05
    assert scheduler.T_max == 4
    assert torch.equal(optimizer.state[parameter]["exp_avg"], exp_avg_before)
    observed = []
    for _ in range(4):
        optimizer.step()
        scheduler.step()
        observed.append(optimizer.param_groups[0]["lr"])
    assert observed == sorted(observed, reverse=True)
    assert abs(observed[-1] - 0.005) < 1e-12


def test_scheduler_restart_rejects_invalid_horizon_and_lr():
    parameter = torch.nn.Parameter(torch.tensor(1.0))
    optimizer = torch.optim.AdamW([parameter], lr=0.1)
    for arguments in (
        {
            "learning_rate": 0.1,
            "minimum_learning_rate": 0.01,
            "remaining_updates": 0,
        },
        {
            "learning_rate": 0.01,
            "minimum_learning_rate": 0.1,
            "remaining_updates": 1,
        },
    ):
        try:
            _restart_cosine_scheduler(optimizer, **arguments)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid scheduler restart was accepted")


def test_weighted_total_and_calibration_are_finite():
    model = Tiny()
    batches = [{"x": torch.tensor([[1.0, 2.0]])} for _ in range(3)]

    def losses(batch):
        y = model.condition(batch["x"])
        return {"a": y.square().mean(), "b": (3 * y).square().mean()}

    report = calibrate_loss_weights(model, batches, losses, max_batches=3)
    assert set(report["weights"]) == {"a", "b"}
    assert abs(sum(report["weights"].values()) / 2 - 1.0) < 1e-6
    assert report["batches_consumed"] == 3
    total = weighted_total({"a": torch.tensor(1.0), "b": torch.tensor(2.0)}, report["weights"])
    assert torch.isfinite(total)


def test_calibration_rejects_out_of_protocol_batch_count():
    model = Tiny()
    with torch.no_grad():
        for parameter in model.parameters():
            parameter.fill_(1.0)

    def losses(batch):
        value = model.condition(batch["x"]).square().mean()
        return {"a": value}

    batches = [{"x": torch.tensor([[1.0, 2.0]])}]
    for invalid in (0, 65):
        try:
            calibrate_loss_weights(model, batches, losses, max_batches=invalid)
        except ValueError as exc:
            assert "[1,64]" in str(exc)
        else:
            raise AssertionError(f"max_batches={invalid} did not fail")


def test_calibration_rejects_invalid_clip_bounds():
    model = Tiny()
    batches = [{"x": torch.tensor([[1.0, 2.0]])}]

    def losses(batch):
        return {"a": model.condition(batch["x"]).square().mean()}

    for invalid in ((0.0, 1.0), (2.0, 1.0), (float("nan"), 1.0)):
        try:
            calibrate_loss_weights(model, batches, losses, clip=invalid)
        except ValueError as exc:
            assert "clip bounds" in str(exc)
        else:
            raise AssertionError(f"clip={invalid} did not fail")


def test_calibration_can_release_independent_loss_group_graphs():
    model = Tiny()
    batches = [{"x": torch.tensor([[1.0, 2.0]])} for _ in range(2)]
    observed = []

    def grouped_losses(batch):
        for name, scale in (("a", 1.0), ("b", 3.0)):
            observed.append(name)
            value = model.condition(batch["x"])
            yield {name: (scale * value).square().mean()}

    report = calibrate_loss_weights(
        model,
        batches,
        None,
        max_batches=2,
        expected_losses={"a", "b"},
        compute_loss_groups=grouped_losses,
    )
    assert observed == ["a", "b", "a", "b"]
    assert report["measured_components"] == ["a", "b"]
    assert report["batches_consumed"] == 2


def test_grouped_production_losses_match_joint_values_and_gradients(
    tmp_path: Path,
):
    made = create_synthetic_dataset(
        tmp_path,
        n_events=8,
        n_layers=4,
        nodes_per_layer=4,
        seed=17,
    )
    geometry = load_geometry(made["geometry"])
    config = {
        "data": {"target_mode": "raw_deposit", "threshold_gev": 0.0},
        "model": {
            "condition_dim": 24,
            "hidden_dim": 24,
            "response_hidden": 32,
            "response_components": 2,
            "response_scale_gev": 10.0,
            "profile_hidden": 24,
            "count_hidden": 32,
            "graph_blocks": 1,
            "attention_heads": 4,
            "attention_layers": 1,
            "layer_context": "bidirectional",
            "dropout": 0.0,
        },
    }
    model = CBSCZDC(geometry, config).train()
    dataset = ShardedSparseDataset(
        made["manifest"],
        n_nodes=16,
    )
    batch = {
        key: torch.stack([dataset[0][key], dataset[1][key]])
        for key in dataset[0]
    }
    params = list(model.condition.parameters())

    def values_and_norms(groups):
        values = {}
        norms = {}
        for losses in groups:
            items = list(losses.items())
            for index, (name, loss) in enumerate(items):
                values[name] = loss.detach()
                gradients = torch.autograd.grad(
                    loss,
                    params,
                    retain_graph=index < len(items) - 1,
                    allow_unused=True,
                )
                norms[name] = torch.sqrt(
                    sum(
                        (
                            gradient.detach().square().sum()
                            for gradient in gradients
                            if gradient is not None
                        ),
                        start=torch.tensor(0.0),
                    )
                )
        return values, norms

    torch.manual_seed(123)
    joint_values, joint_norms = values_and_norms(
        (compute_component_losses(model, batch, "joint")[0],)
    )
    torch.manual_seed(123)
    grouped_values, grouped_norms = values_and_norms(
        (
            compute_component_losses(model, batch, stage)[0]
            for stage in ("response", "profile", "count", "support", "share")
        )
    )
    assert grouped_values.keys() == joint_values.keys()
    for name in joint_values:
        assert torch.allclose(grouped_values[name], joint_values[name])
        assert torch.allclose(grouped_norms[name], joint_norms[name])
