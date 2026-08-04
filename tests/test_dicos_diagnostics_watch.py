from __future__ import annotations

from pathlib import Path

from scripts import dicos_diagnostics
from cbsc_zdc.utils import sha256_file


def _result(epoch: int, checkpoint: Path) -> dict:
    return {
        "epoch": epoch,
        "checkpoint_sha256": sha256_file(checkpoint),
        "n_events": 4000,
        "trend": {"response_bias_fraction": 0.1},
        "trend_stderr": {"response_bias_fraction": 0.01},
        "qa": {"pass": True},
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
        return _result(int(checkpoint.stem.rsplit("_", 1)[1]), checkpoint)

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
    assert dicos_diagnostics.watch(object(), queue, output) == 1
    assert (queue / "done" / "ckpt_epoch_0041.pt.failed").is_file()
    assert not (output / "metrics_epoch_0041.json").exists()


def test_epoch_mismatch_and_failed_qa_are_quarantined(
    tmp_path: Path, monkeypatch,
) -> None:
    queue = tmp_path / "_diag" / "dicos-p11" / "queue"
    output = queue.parent
    queue.mkdir(parents=True)
    first = queue / "ckpt_epoch_0041.pt"
    second = queue / "ckpt_epoch_0042.pt"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    (queue / "STOP").write_text("finished\n", encoding="utf-8")

    def result(context, checkpoint: Path) -> dict:
        if checkpoint == first:
            return _result(99, checkpoint)
        payload = _result(42, checkpoint)
        payload["qa"]["pass"] = False
        return payload

    monkeypatch.setattr(dicos_diagnostics, "run_one", result)
    assert dicos_diagnostics.watch(object(), queue, output) == 1
    assert (queue / "done" / "ckpt_epoch_0041.pt.failed").is_file()
    assert (queue / "done" / "ckpt_epoch_0042.pt.failed").is_file()
    assert not (output / "metrics_epoch_0099.json").exists()
    assert (output / "metrics_epoch_0042.failed.json").is_file()
