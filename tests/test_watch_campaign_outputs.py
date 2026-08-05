"""Contracts for the persistent campaign figure/metric watcher.

The pod, the process table, and the wall clock are never touched here.
`run_loop` takes its refresh call and its sleep function as injected
dependencies, the same pattern `dicos_diagnostics.watch()` uses elsewhere in
this project, so the loop's control flow -- stop handling, delta detection,
terminal-state exit -- is exercised without a live campaign.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import watch_campaign_outputs as watch


# --------------------------------------------------------------------------
# compute_deltas -- pure function, the core decision logic
# --------------------------------------------------------------------------


def _result(family="calibrated_lr3e4", tag="dicos-c-02", epoch=30, chain_index=0,
           status="training"):
    return {
        "families": {family: {"newest_tag": tag, "epoch": epoch}},
        "chain_index": chain_index,
        "status": status,
    }


def test_a_new_epoch_with_no_best_change_is_one_import_line():
    previous = {"families": {"calibrated_lr3e4": {"epoch": 29}},
               "chain_index": 0, "status": "training"}
    result = _result(epoch=30)
    bests = {"calibrated_lr3e4": (4.60, 22, "dicos-p7")}
    lines = watch.compute_deltas(previous, result, bests, bests)
    assert lines == [
        "calibrated_lr3e4/dicos-c-02 epoch 30 imported, best so far 4.600000 "
        "@ e22 (dicos-p7)"
    ]


def test_a_lower_loss_is_reported_as_new_best_with_the_improvement_size():
    previous = {"families": {"calibrated_lr3e4": {"epoch": 33}},
               "chain_index": 0, "status": "training"}
    result = _result(epoch=34)
    before = {"calibrated_lr3e4": (4.597152, 22, "dicos-p7")}
    after = {"calibrated_lr3e4": (4.550331, 34, "dicos-c-02")}
    lines = watch.compute_deltas(previous, result, before, after)
    assert any(line.startswith("NEW BEST:") for line in lines)
    best_line = next(line for line in lines if line.startswith("NEW BEST:"))
    assert "4.550331" in best_line
    assert "epoch 34" in best_line
    assert "improving on 4.597152 by 0.046821" in best_line
    # The import line still follows, carrying the new best forward.
    assert any("epoch 34 imported" in line and "4.550331" in line for line in lines)


def test_a_higher_loss_is_not_reported_as_a_new_best():
    """A worse epoch must not fire the headline path."""
    previous = {"families": {"calibrated_lr3e4": {"epoch": 24}},
               "chain_index": 0, "status": "training"}
    result = _result(epoch=25)
    before = {"calibrated_lr3e4": (4.597152, 22, "dicos-p7")}
    after = {"calibrated_lr3e4": (4.597152, 22, "dicos-p7")}  # unchanged: e25 was worse
    lines = watch.compute_deltas(previous, result, before, after)
    assert not any(line.startswith("NEW BEST:") for line in lines)
    assert any("epoch 25 imported" in line for line in lines)


def test_no_new_epoch_produces_no_lines():
    previous = {"families": {"calibrated_lr3e4": {"epoch": 30}},
               "chain_index": 0, "status": "training"}
    result = _result(epoch=30)  # unchanged
    lines = watch.compute_deltas(previous, result, {}, {})
    assert lines == []


def test_an_epoch_at_or_below_the_previous_one_is_not_reimported():
    """A refresh pass that returns stale-looking data must not repeat a line."""
    previous = {"families": {"calibrated_lr3e4": {"epoch": 30}},
               "chain_index": 0, "status": "training"}
    result = _result(epoch=29)  # went backwards somehow
    lines = watch.compute_deltas(previous, result, {}, {})
    assert lines == []


def test_family_with_no_diagnostics_yet_is_silently_skipped():
    previous = {"families": {}, "chain_index": 0, "status": "training"}
    result = {
        "families": {"calibrated_lr3e5": {"newest_tag": "dicos-c-04", "epoch": None}},
        "chain_index": 0, "status": "training",
    }
    assert watch.compute_deltas(previous, result, {}, {}) == []


def test_chain_advancing_is_reported():
    previous = {"families": {}, "chain_index": 0, "status": "training"}
    result = {"families": {}, "chain_index": 1, "status": "training"}
    lines = watch.compute_deltas(previous, result, {}, {})
    assert lines == ["campaign advanced: chain_index 0 -> 1"]


def test_terminal_status_transition_is_reported():
    previous = {"families": {}, "chain_index": 2, "status": "training"}
    result = {"families": {}, "chain_index": 2, "status": "campaign_complete"}
    lines = watch.compute_deltas(previous, result, {}, {})
    assert lines == ["campaign status: training -> campaign_complete"]


def test_first_run_with_no_prior_epoch_still_imports_and_can_be_a_best():
    """`previous` from a fresh `last_known.json` has no per-family entry at all."""
    previous = {"families": {}, "chain_index": 0, "status": None}
    result = _result(epoch=23)
    before = {}
    after = {"calibrated_lr3e4": (4.6, 23, "dicos-c-02")}
    lines = watch.compute_deltas(previous, result, before, after)
    assert any(line.startswith("NEW BEST:") for line in lines)
    assert "improving on" not in next(l for l in lines if l.startswith("NEW BEST:"))


# --------------------------------------------------------------------------
# read_bests -- CSV parsing against an explicit, injected path
# --------------------------------------------------------------------------


def test_read_bests_picks_the_lowest_loss_row_per_family(tmp_path: Path) -> None:
    csv_path = tmp_path / "continuation_history.csv"
    csv_path.write_text(
        "variant,epoch,train_loss,validation_loss,run_tag\n"
        "calibrated_lr3e4,22,4.6,4.597152,dicos-p7\n"
        "calibrated_lr3e4,34,4.5,4.550331,dicos-c-02\n"
        "calibrated_lr3e4,35,4.6,4.606194,dicos-c-02\n"
        "calibrated_lr1e4,38,4.6,4.635220,dicos-p9\n",
        encoding="utf-8",
    )
    bests = watch.read_bests(history_path=csv_path)
    assert bests["calibrated_lr3e4"] == (4.550331, 34, "dicos-c-02")
    assert bests["calibrated_lr1e4"] == (4.635220, 38, "dicos-p9")


def test_read_bests_on_a_missing_file_returns_empty(tmp_path: Path) -> None:
    assert watch.read_bests(history_path=tmp_path / "absent.csv") == {}


def test_read_bests_skips_unparseable_rows(tmp_path: Path) -> None:
    csv_path = tmp_path / "continuation_history.csv"
    csv_path.write_text(
        "variant,epoch,train_loss,validation_loss,run_tag\n"
        "calibrated_lr3e4,22,4.6,not_a_number,dicos-p7\n"
        "calibrated_lr3e4,23,4.6,4.6,dicos-p7\n",
        encoding="utf-8",
    )
    bests = watch.read_bests(history_path=csv_path)
    assert bests["calibrated_lr3e4"] == (4.6, 23, "dicos-p7")


# --------------------------------------------------------------------------
# lock / stop file coordination
# --------------------------------------------------------------------------


def test_acquire_lock_then_a_second_acquire_is_refused(tmp_path: Path) -> None:
    lock = tmp_path / "watch.lock"
    state_dir = tmp_path
    log = tmp_path / "watch.log"
    watch.acquire_lock(lock_path=lock, state_dir=state_dir, log_path=log)
    assert lock.exists()
    holder = json.loads(lock.read_text(encoding="utf-8"))
    assert holder["pid"] == __import__("os").getpid()

    # A second acquire from the same live process is refused rather than
    # silently taking over -- exactly the discipline AGENTS.md requires for a
    # DiCOS trainer: one writer, proved from the process table, not a file.
    with pytest.raises(SystemExit, match="already running"):
        watch.acquire_lock(lock_path=lock, state_dir=state_dir, log_path=log)


def test_a_stale_lock_from_a_dead_pid_is_reclaimed(tmp_path: Path) -> None:
    lock = tmp_path / "watch.lock"
    state_dir = tmp_path
    log = tmp_path / "watch.log"
    # PID 999999 is not a real process on any machine this test runs on.
    lock.write_text(json.dumps({"pid": 999999, "started_at": "2020-01-01T00:00:00Z"}),
                    encoding="utf-8")
    watch.acquire_lock(lock_path=lock, state_dir=state_dir, log_path=log)
    holder = json.loads(lock.read_text(encoding="utf-8"))
    assert holder["pid"] == __import__("os").getpid()
    assert "reclaiming stale lock" in log.read_text(encoding="utf-8")


def test_release_lock_removes_the_file(tmp_path: Path) -> None:
    lock = tmp_path / "watch.lock"
    lock.write_text("{}", encoding="utf-8")
    watch.release_lock(lock_path=lock)
    assert not lock.exists()


def test_release_lock_on_an_absent_file_does_not_raise(tmp_path: Path) -> None:
    watch.release_lock(lock_path=tmp_path / "never_existed.lock")


def test_should_stop_consumes_the_sentinel(tmp_path: Path) -> None:
    stop = tmp_path / "WATCH_STOP"
    assert watch.should_stop(stop_path=stop) is False
    stop.write_text("operator", encoding="utf-8")
    assert watch.should_stop(stop_path=stop) is True
    # Consumed, not merely read -- a second check must not see it again.
    assert not stop.exists()
    assert watch.should_stop(stop_path=stop) is False


# --------------------------------------------------------------------------
# run_loop -- the orchestration, with the refresh call and the clock injected
# --------------------------------------------------------------------------


def _paths(tmp_path: Path) -> dict:
    return dict(
        last_known_path=tmp_path / "last_known.json",
        log_path=tmp_path / "watch.log",
        state_dir=tmp_path,
        logs_path=tmp_path / "logs.md",
        stop_path=tmp_path / "WATCH_STOP",
    )


def test_run_loop_stops_on_terminal_campaign_status(tmp_path: Path) -> None:
    calls = {"n": 0}

    def fake_run_once(plan, scratch, last_known):
        calls["n"] += 1
        return (
            {"families": {}, "chain_index": 2, "status": "campaign_complete"},
            ["campaign status: training -> campaign_complete"],
        )

    exit_code = watch.run_loop(
        {"campaign_id": "camp-test"}, tmp_path, interval_seconds=60,
        sleep_fn=lambda s: None, run_once_fn=fake_run_once,
        **_paths(tmp_path),
    )
    assert exit_code == 0
    assert calls["n"] == 1  # exits immediately on the first terminal result
    logged = (tmp_path / "logs.md").read_text(encoding="utf-8")
    assert "watcher started" in logged
    assert "campaign campaign_complete" in logged or "watcher stopped" in logged


def test_run_loop_respects_the_stop_sentinel_between_iterations(tmp_path: Path) -> None:
    calls = {"n": 0}
    paths = _paths(tmp_path)

    def fake_run_once(plan, scratch, last_known):
        calls["n"] += 1
        if calls["n"] == 1:
            # Plant the stop request the first time the loop reaches sleep.
            paths["stop_path"].write_text("operator", encoding="utf-8")
        return ({"families": {}, "chain_index": 0, "status": "training"}, [])

    exit_code = watch.run_loop(
        {"campaign_id": "camp-test"}, tmp_path, interval_seconds=60,
        sleep_fn=lambda s: None, run_once_fn=fake_run_once,
        **paths,
    )
    assert exit_code == 0
    assert calls["n"] == 1
    logged = (tmp_path / "watch.log").read_text(encoding="utf-8")
    assert "stop requested during sleep" in logged


def test_run_loop_survives_a_refresh_exception_and_keeps_polling(tmp_path: Path) -> None:
    """A transient pod failure must not kill the loop."""
    calls = {"n": 0}

    def flaky_run_once(plan, scratch, last_known):
        calls["n"] += 1
        if calls["n"] == 1:
            raise SystemExit("dicos exec failed (1): connection refused")
        return (
            {"families": {}, "chain_index": 0, "status": "training"},
            [],
        )

    exit_code = watch.run_loop(
        {"campaign_id": "camp-test"}, tmp_path, interval_seconds=60,
        sleep_fn=lambda s: None, run_once_fn=flaky_run_once,
        max_iterations=2,
        **_paths(tmp_path),
    )
    assert exit_code == 0
    assert calls["n"] == 2
    logged = (tmp_path / "watch.log").read_text(encoding="utf-8")
    assert "refresh failed, will retry next interval" in logged


def test_run_loop_appends_one_logs_md_block_per_delta_batch(tmp_path: Path) -> None:
    def fake_run_once(plan, scratch, last_known):
        return (
            {"families": {"calibrated_lr3e4": {"newest_tag": "dicos-c-02", "epoch": 30}},
             "chain_index": 0, "status": "training"},
            ["calibrated_lr3e4/dicos-c-02 epoch 30 imported, best so far 4.6 @ e22 (dicos-p7)"],
        )

    watch.run_loop(
        {"campaign_id": "camp-test"}, tmp_path, interval_seconds=60,
        sleep_fn=lambda s: None, run_once_fn=fake_run_once,
        max_iterations=1,
        **_paths(tmp_path),
    )
    logged = (tmp_path / "logs.md").read_text(encoding="utf-8")
    assert "epoch 30 imported" in logged


def test_run_loop_persists_last_known_across_iterations(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    seen_previous = []

    def fake_run_once(plan, scratch, last_known):
        seen_previous.append(dict(last_known))
        epoch = 30 + len(seen_previous)
        return (
            {"families": {"calibrated_lr3e4": {"newest_tag": "dicos-c-02", "epoch": epoch}},
             "chain_index": 0, "status": "training"},
            [f"epoch {epoch} imported"],
        )

    watch.run_loop(
        {"campaign_id": "camp-test"}, tmp_path, interval_seconds=60,
        sleep_fn=lambda s: None, run_once_fn=fake_run_once,
        max_iterations=3,
        **paths,
    )
    # Second and third calls must see the previous call's result as `last_known`.
    assert seen_previous[1]["families"]["calibrated_lr3e4"]["epoch"] == 31
    assert seen_previous[2]["families"]["calibrated_lr3e4"]["epoch"] == 32
    assert json.loads(paths["last_known_path"].read_text(encoding="utf-8"))[
        "families"]["calibrated_lr3e4"]["epoch"] == 33


def test_run_loop_with_no_deltas_still_records_a_heartbeat(tmp_path: Path) -> None:
    def fake_run_once(plan, scratch, last_known):
        return ({"families": {}, "chain_index": 0, "status": "training"}, [])

    watch.run_loop(
        {"campaign_id": "camp-test"}, tmp_path, interval_seconds=60,
        sleep_fn=lambda s: None, run_once_fn=fake_run_once,
        max_iterations=1,
        **_paths(tmp_path),
    )
    logged = (tmp_path / "watch.log").read_text(encoding="utf-8")
    assert "no new evidence this pass" in logged
    # Heartbeats stay out of the permanent evidence record.
    logs_md = (tmp_path / "logs.md").read_text(encoding="utf-8")
    assert "no new evidence" not in logs_md
