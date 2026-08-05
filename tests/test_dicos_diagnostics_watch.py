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


def test_watch_root_follows_every_run_tag_and_writes_into_each_namespace(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """A campaign starts a new run tag per segment.

    A consumer bound to one queue directory stops serving the moment the
    campaign advances, and it cannot be restarted from inside the training pod.
    This mode discovers tags instead, and each tag's metrics must land in its
    own namespace -- a flat directory already cost dicos-p8 its epochs 17-22.
    """
    root = tmp_path / "_diag"
    for tag, epochs in (("dicos-c-01", (23, 24)), ("dicos-c-02", (44,))):
        queue = root / tag / "queue"
        queue.mkdir(parents=True)
        for epoch in epochs:
            (queue / f"ckpt_epoch_{epoch:04d}.pt").write_bytes(f"{tag} {epoch}".encode())
        (queue / "STOP").write_text("finished\n", encoding="utf-8")
    (root / "CAMPAIGN_STOP").write_text("operator\n", encoding="utf-8")

    def fake_run_one(context, checkpoint: Path) -> dict:
        return _result(int(checkpoint.stem.rsplit("_", 1)[1]), checkpoint)

    monkeypatch.setattr(dicos_diagnostics, "run_one", fake_run_one)
    assert dicos_diagnostics.watch_root(object(), root) == 0

    assert (root / "dicos-c-01" / "metrics_epoch_0023.json").is_file()
    assert (root / "dicos-c-01" / "metrics_epoch_0024.json").is_file()
    assert (root / "dicos-c-02" / "metrics_epoch_0044.json").is_file()
    # Namespaced, not flattened.
    assert not (root / "metrics_epoch_0023.json").exists()
    assert not (root / "dicos-c-02" / "metrics_epoch_0023.json").exists()


def test_watch_root_exits_only_on_campaign_stop_not_a_per_tag_stop(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """A finished segment must not end the consumer for the whole campaign."""
    root = tmp_path / "_diag"
    queue = root / "dicos-c-01" / "queue"
    queue.mkdir(parents=True)
    (queue / "ckpt_epoch_0023.pt").write_bytes(b"epoch 23")
    (queue / "STOP").write_text("segment done\n", encoding="utf-8")

    calls = {"n": 0}

    def fake_run_one(context, checkpoint: Path) -> dict:
        return _result(int(checkpoint.stem.rsplit("_", 1)[1]), checkpoint)

    def fake_sleep(_seconds):
        # The first idle pass proves a per-tag STOP did not end the loop; then
        # the operator's campaign stop is planted so the test terminates.
        calls["n"] += 1
        (root / "CAMPAIGN_STOP").write_text("operator\n", encoding="utf-8")

    monkeypatch.setattr(dicos_diagnostics, "run_one", fake_run_one)
    monkeypatch.setattr(dicos_diagnostics.time, "sleep", fake_sleep)
    assert dicos_diagnostics.watch_root(object(), root) == 0
    assert calls["n"] >= 1, "a per-tag STOP ended the campaign consumer"
    assert (root / "dicos-c-01" / "metrics_epoch_0023.json").is_file()
