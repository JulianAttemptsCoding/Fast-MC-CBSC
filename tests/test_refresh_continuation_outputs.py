from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from scripts import refresh_continuation_outputs as refresh


def test_dicos_config_role_is_explicit(monkeypatch) -> None:
    calls = []

    class Result:
        returncode = 0
        stdout = "ok"
        stderr = ""

    def fake_run(*args, **kwargs):
        calls.append(kwargs["env"])
        return Result()

    monkeypatch.setenv("DICOS_CONFIG", "wrong-inherited-config.json")
    monkeypatch.setattr(refresh.subprocess, "run", fake_run)
    refresh.dicos(["info"])
    refresh.dicos(["info"], "config_3090.json")
    assert "DICOS_CONFIG" not in calls[0]
    assert calls[1]["DICOS_CONFIG"].endswith(".dicos\\config_3090.json")


def _metric(epoch: int) -> dict:
    return {
        "schema_version": 1,
        "kind": "cbsc-zdc-large-validation-diagnostic",
        "split": "validation",
        "epoch": epoch,
        "n_events": 4000,
        "split_counts": {"train": 0, "validation": 4000, "test": 0},
        "qa": {
            "test_events_used": 0,
            "train_events_used": 0,
            "generated_nonfinite": 0,
            "generated_negative": 0,
            "truth_nonfinite": 0,
            "truth_negative": 0,
            "events_outside_energy_bins": 0,
            "empty_energy_bins": 0,
            "pass": True,
        },
    }


def test_refresh_inputs_fail_closed() -> None:
    refresh.validate_inputs("calibrated_lr1e4", "dicos-p11", "_runs/run", "config_3090.json")
    with pytest.raises(ValueError, match="3090"):
        refresh.validate_inputs("calibrated_lr1e4", "dicos-p11", "_runs/run", "config.json")
    with pytest.raises(ValueError, match="_runs"):
        refresh.validate_inputs("calibrated_lr1e4", "dicos-p11", "../run", "config_3090.json")
    with pytest.raises(ValueError, match="run tag"):
        refresh.validate_inputs("calibrated_lr1e4", "p11;rm", "_runs/run", "config_3090.json")


def test_pull_diagnostic_verifies_hash_and_scientific_contract(
    tmp_path: Path, monkeypatch,
) -> None:
    raw = (json.dumps(_metric(41), sort_keys=True) + "\n").encode()
    checksum = hashlib.sha256(raw).hexdigest()
    monkeypatch.setattr(refresh, "DIAG_LOCAL", tmp_path / "diagnostics")

    def fake_dicos(args: list[str], config: str | None = None) -> str:
        if args[0] == "exec":
            return f"{checksum}  _diag/dicos-p11/metrics_epoch_0041.json\n"
        assert args[:2] == ["get", "_diag/dicos-p11/metrics_epoch_0041.json"]
        Path(args[2]).write_bytes(raw)
        return ""

    monkeypatch.setattr(refresh, "dicos", fake_dicos)
    assert refresh.pull_diagnostics("config_3090.json", "dicos-p11") == [41]
    target = tmp_path / "diagnostics/dicos-p11/metrics_epoch_0041.json"
    assert target.is_file()
    assert not list(target.parent.glob("*.part"))
    assert refresh.pull_diagnostics("config_3090.json", "dicos-p11") == []

    target.write_text("tampered\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="hash conflict"):
        refresh.pull_diagnostics("config_3090.json", "dicos-p11")


def test_failed_metric_contract_is_never_published(tmp_path: Path) -> None:
    path = tmp_path / "metrics_epoch_0041.json"
    payload = _metric(41)
    payload["qa"]["test_events_used"] = 1
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="test_events_used"):
        refresh.validate_metric(path, 41)


def test_visualization_must_match_accepted_checkpoint(tmp_path: Path) -> None:
    path = tmp_path / "epoch_0041.json"
    payload = {
        "kind": "cbsc-zdc-epoch-visual-comparison",
        "split": "validation",
        "epoch": 41,
        "sample_count": 50,
        "draws_per_condition": 5,
        "checkpoint_sha256": "a" * 64,
        "qa": {
            "pass": True,
            "test_events_used": 0,
            "groups_with_exact_draw_count": 50,
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    refresh.validate_visualization(path, 41, "a" * 64)
    with pytest.raises(ValueError, match="checkpoint_sha256"):
        refresh.validate_visualization(path, 41, "b" * 64)


def test_history_rewrite_is_validated_and_atomic(tmp_path: Path, monkeypatch) -> None:
    continuation = tmp_path / "continuation_history.csv"
    monkeypatch.setattr(refresh, "CONTINUATION_CSV", continuation)
    history = tmp_path / "history.csv"
    history.write_text(
        "epoch,train_loss,validation_loss\n41,4.2,4.1\n42,4.0,3.9\n",
        encoding="utf-8",
    )
    assert refresh.rewrite_continuation(
        history, "calibrated_lr1e4", "dicos-p11"
    ) == 2
    with continuation.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert [int(row["epoch"]) for row in rows] == [41, 42]
    assert not continuation.with_suffix(".csv.tmp").exists()

    history.write_text(
        "epoch,train_loss,validation_loss\n41,4.2,4.1\n41,4.0,3.9\n",
        encoding="utf-8",
    )
    before = continuation.read_bytes()
    with pytest.raises(ValueError, match="duplicate history epoch"):
        refresh.rewrite_continuation(history, "calibrated_lr1e4", "dicos-p11")
    assert continuation.read_bytes() == before
