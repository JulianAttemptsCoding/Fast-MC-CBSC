import torch

from cbsc_zdc.training.weights import calibrate_loss_weights, weighted_total


class Tiny(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.condition = torch.nn.Linear(2, 2, bias=False)


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
