from __future__ import annotations

from pathlib import Path

from scripts import dicos_diagnostics


def _result(epoch: int) -> dict:
    return {
        "epoch": epoch,
        "n_events": 4000,
        "trend": {"response_bias_fraction": 0.1},
        "trend_stderr": {"response_bias_fraction": 0.01},
    }


def test_stop_present_at_start_does_not_skip_pending_checkpoints(
    tmp_path: Path,
    monkeypatch,
) -> None:
    queue = tmp_path / "_diag" / "dicos-p11" / "queue"
    output = queue.parent
    queue.mkdir(parents=True)
    (queue / "ckpt_epoch_0041.pt").write_bytes(b"epoch 41")
    (queue / "ckpt_epoch_0042.pt").write_bytes(b"epoch 42")
    (queue / "STOP").write_text("finished\n", encoding="utf-8")

    def fake_run_one(context, checkpoint: Path) -> dict:
        return _result(int(checkpoint.stem.rsplit("_", 1)[1]))

    monkeypatch.setattr(dicos_diagnostics, "run_one", fake_run_one)
    assert dicos_diagnostics.watch(object(), queue, output) == 0
    assert (output / "metrics_epoch_0041.json").is_file()
    assert (output / "metrics_epoch_0042.json").is_file()
    assert (queue / "done" / "ckpt_epoch_0041.pt").is_file()
    assert (queue / "done" / "ckpt_epoch_0042.pt").is_file()
    assert not list(queue.glob("*.pt"))


def test_failed_checkpoint_is_preserved_and_does_not_block_stop(
    tmp_path: Path,
    monkeypatch,
) -> None:
    queue = tmp_path / "_diag" / "dicos-p11" / "queue"
    output = queue.parent
    queue.mkdir(parents=True)
    checkpoint = queue / "ckpt_epoch_0041.pt"
    checkpoint.write_bytes(b"bad checkpoint")
    (queue / "STOP").write_text("finished\n", encoding="utf-8")

    def fail(context, path: Path) -> dict:
        raise RuntimeError("synthetic diagnostic failure")

    monkeypatch.setattr(dicos_diagnostics, "run_one", fail)
    assert dicos_diagnostics.watch(object(), queue, output) == 0
    assert (queue / "done" / "ckpt_epoch_0041.pt.failed").is_file()
    assert not (output / "metrics_epoch_0041.json").exists()
