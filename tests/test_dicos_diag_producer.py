from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import torch

from scripts.dicos_diag_producer import (
    ProducerLock,
    already_handled,
    main,
    queue_checkpoint,
    resolve_under,
    validate_run_tag,
    wrapper_exit_code,
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
    reports = tmp_path / "reports"
    reports.mkdir()
    torch.save({"epoch": 41, "weights": [1, 2, 3]}, last)
    checksum = hashlib.sha256(last.read_bytes()).hexdigest()
    (reports / "progress_epoch_0041.json").write_text(
        json.dumps({"epoch": 41, "last_checkpoint_sha256": checksum}),
        encoding="utf-8",
    )

    result = queue_checkpoint(last, reports, metrics)
    assert result.queued
    assert result.epoch == 41
    assert result.path == metrics / "queue" / "ckpt_epoch_0041.pt"
    assert result.path.is_file()

    duplicate = queue_checkpoint(last, reports, metrics)
    assert duplicate.epoch == 41
    assert not duplicate.queued
    assert not list((metrics / "queue").glob(".staging-*.pt"))


def test_checkpoint_requires_matching_completed_epoch_marker(tmp_path: Path) -> None:
    metrics = tmp_path / "_diag" / "dicos-p11"
    reports = tmp_path / "reports"
    reports.mkdir()
    last = tmp_path / "last.pt"
    torch.save({"epoch": 41}, last)

    with pytest.raises(RuntimeError, match="no completed progress marker"):
        queue_checkpoint(last, reports, metrics)
    (reports / "progress_epoch_0041.json").write_text(
        json.dumps({"epoch": 41, "last_checkpoint_sha256": "wrong"}),
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="hash does not match"):
        queue_checkpoint(last, reports, metrics)
    assert not list((metrics / "queue").glob("*.pt"))


def test_existing_metric_or_failed_checkpoint_counts_as_handled(tmp_path: Path) -> None:
    metrics = tmp_path / "_diag" / "dicos-p11"
    queue = metrics / "queue"
    done = queue / "done"
    done.mkdir(parents=True)
    (metrics / "metrics_epoch_0042.json").write_text("{}\n", encoding="utf-8")
    assert already_handled(queue, done, metrics, 42)
    (done / "ckpt_epoch_0043.pt.failed").write_text("failed\n", encoding="utf-8")
    assert already_handled(queue, done, metrics, 43)
    (metrics / "metrics_epoch_0044.failed.json").write_text("{}\n", encoding="utf-8")
    assert already_handled(queue, done, metrics, 44)


def test_stop_is_atomic_and_only_wrapper_exit_marks_finished(tmp_path: Path) -> None:
    log = tmp_path / "wrapper.log"
    log.write_text("START\n", encoding="utf-8")
    assert not wrapper_finished(log)
    log.write_text("START\nEXIT=1\n", encoding="utf-8")
    assert wrapper_finished(log)
    assert wrapper_exit_code(log) == 1
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


def test_same_host_dead_producer_lock_is_reclaimed(tmp_path: Path, monkeypatch) -> None:
    lock_path = tmp_path / "producer.lock"
    lock_path.write_text(
        json.dumps({"hostname": "test-host", "pid": 99999999, "nonce": "old"}),
        encoding="utf-8",
    )
    monkeypatch.setattr("scripts.dicos_diag_producer.socket.gethostname", lambda: "test-host")
    monkeypatch.setattr(ProducerLock, "_pid_alive", staticmethod(lambda pid: False))
    with ProducerLock(lock_path):
        owner = json.loads(lock_path.read_text(encoding="utf-8"))
        assert owner["nonce"] != "old"
    assert not lock_path.exists()


def _completed_epoch(tmp_path: Path, with_marker: bool = True) -> None:
    run = tmp_path / "_runs" / "family_dicos-p11"
    (run / "checkpoints").mkdir(parents=True)
    (run / "reports").mkdir()
    checkpoint = run / "checkpoints" / "last.pt"
    torch.save({"epoch": 41}, checkpoint)
    if with_marker:
        checksum = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
        (run / "reports" / "progress_epoch_0041.json").write_text(
            json.dumps({"epoch": 41, "last_checkpoint_sha256": checksum}),
            encoding="utf-8",
        )
    (tmp_path / "_runs" / "dicos-p11train.log").write_text(
        "done\nEXIT=0\n", encoding="utf-8"
    )


def test_producer_main_emits_stop_after_accepted_final_checkpoint(tmp_path: Path) -> None:
    _completed_epoch(tmp_path)
    assert main([
        "--workdir", str(tmp_path),
        "--run-dir", "_runs/family_dicos-p11",
        "--wrapper-log", "_runs/dicos-p11train.log",
        "--run-tag", "dicos-p11",
        "--poll-seconds", "0.001",
    ]) == 0
    metrics = tmp_path / "_diag" / "dicos-p11"
    assert (metrics / "queue" / "ckpt_epoch_0041.pt").is_file()
    assert (metrics / "queue" / "STOP").is_file()
    assert not (metrics / "producer_failure.json").exists()


def test_producer_main_quarantines_unaccepted_final_checkpoint(tmp_path: Path) -> None:
    _completed_epoch(tmp_path, with_marker=False)
    assert main([
        "--workdir", str(tmp_path),
        "--run-dir", "_runs/family_dicos-p11",
        "--wrapper-log", "_runs/dicos-p11train.log",
        "--run-tag", "dicos-p11",
        "--poll-seconds", "0.001",
        "--final-retries", "0",
        "--final-retry-seconds", "0.001",
    ]) == 1
    metrics = tmp_path / "_diag" / "dicos-p11"
    failure = json.loads((metrics / "producer_failure.json").read_text())
    assert failure["scientific_status"].startswith("quarantined")
    assert failure["checkpoint_epoch"] == 41
    assert (metrics / "queue" / "STOP").is_file()
    assert not list((metrics / "queue").glob("*.pt"))
