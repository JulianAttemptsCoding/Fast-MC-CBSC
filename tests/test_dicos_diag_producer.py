from __future__ import annotations

from pathlib import Path

import pytest
import torch

from scripts.dicos_diag_producer import (
    ProducerLock,
    already_handled,
    queue_checkpoint,
    resolve_under,
    validate_run_tag,
    wrapper_finished,
    write_stop,
)


def test_paths_and_run_tags_fail_closed(tmp_path: Path) -> None:
    assert resolve_under(tmp_path, "_runs/run", "run") == tmp_path / "_runs/run"
    with pytest.raises(ValueError, match="safe workdir-relative"):
        resolve_under(tmp_path, "../other", "run")
    with pytest.raises(ValueError, match="lowercase"):
        validate_run_tag("DICOS p11")
    assert validate_run_tag("dicos-p11") == "dicos-p11"


def test_checkpoint_is_named_from_its_embedded_epoch_and_deduplicated(
    tmp_path: Path,
) -> None:
    metrics = tmp_path / "_diag" / "dicos-p11"
    last = tmp_path / "last.pt"
    torch.save({"epoch": 41, "weights": [1, 2, 3]}, last)

    result = queue_checkpoint(last, metrics)
    assert result.queued
    assert result.epoch == 41
    assert result.path == metrics / "queue" / "ckpt_epoch_0041.pt"
    assert result.path.is_file()

    duplicate = queue_checkpoint(last, metrics)
    assert duplicate.epoch == 41
    assert not duplicate.queued
    assert not list((metrics / "queue").glob(".staging-*.pt"))


def test_existing_metric_or_failed_checkpoint_counts_as_handled(tmp_path: Path) -> None:
    metrics = tmp_path / "_diag" / "dicos-p11"
    queue = metrics / "queue"
    done = queue / "done"
    done.mkdir(parents=True)
    (metrics / "metrics_epoch_0042.json").write_text("{}\n", encoding="utf-8")
    assert already_handled(queue, done, metrics, 42)
    (done / "ckpt_epoch_0043.pt.failed").write_text("failed\n", encoding="utf-8")
    assert already_handled(queue, done, metrics, 43)


def test_stop_is_atomic_and_only_wrapper_exit_marks_finished(tmp_path: Path) -> None:
    log = tmp_path / "wrapper.log"
    log.write_text("START\n", encoding="utf-8")
    assert not wrapper_finished(log)
    log.write_text("START\nEXIT=1\n", encoding="utf-8")
    assert wrapper_finished(log)
    queue = tmp_path / "queue"
    queue.mkdir()
    stop = write_stop(queue)
    assert stop.read_text(encoding="utf-8").startswith("training finished")
    assert not list(queue.glob(".STOP-*.tmp"))


def test_only_one_producer_can_hold_a_run_tag_lock(tmp_path: Path) -> None:
    lock_path = tmp_path / "producer.lock"
    with ProducerLock(lock_path):
        assert lock_path.is_file()
        with pytest.raises(RuntimeError, match="already exists"):
            with ProducerLock(lock_path):
                pass
    assert not lock_path.exists()
