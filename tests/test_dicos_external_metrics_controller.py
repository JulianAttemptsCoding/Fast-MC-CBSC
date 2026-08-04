from types import SimpleNamespace

from scripts import dicos_external_metrics_controller as controller


def _args() -> SimpleNamespace:
    return SimpleNamespace(
        family="calibrated_lr1e4",
        run_tag="dicos-p9",
        epoch=38,
        validation_loss=4.635219681489869,
        checkpoint_sha256="a" * 64,
    )


def test_detached_launcher_archives_attempt_and_uses_nohup(monkeypatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(controller, "dicos", lambda args: calls.append(args) or "")

    controller._launch("runs/example", "export", "python exporter.py")

    assert calls and calls[0][0] == "exec"
    wrapper = calls[0][1]
    assert "nohup sh -c" in wrapper
    assert "runs/example/attempts" in wrapper
    assert "mv \"$f\"" in wrapper
    assert "validation_bank.npz" in wrapper
    assert "validation_bank.manifest.json" in wrapper
    assert "runs/example/export.exit" in wrapper


def test_start_retries_failed_export_without_accepting_partial_state(monkeypatch) -> None:
    args = _args()
    launched: list[tuple[str, str, str]] = []
    failed = {
        "schema_version": 1,
        "kind": "status",
        "family": args.family,
        "run_tag": args.run_tag,
        "epoch": args.epoch,
        "checkpoint_sha256": args.checkpoint_sha256,
        "bank_ready": False,
        "results_ready": False,
        "export": {"state": "failed", "raw": "EXIT=130"},
        "evaluate": {"state": "not_started"},
        "cbsc_training_started": False,
        "cbsc_test_events_used": 0,
    }
    running = {**failed, "export": {"state": "running", "pid": 123}}
    states = iter([failed, running])
    monkeypatch.setattr(controller, "verify_dependencies", lambda: {})
    monkeypatch.setattr(controller, "status", lambda _args: next(states))
    monkeypatch.setattr(
        controller,
        "dicos",
        lambda command: f"{args.checkpoint_sha256}  checkpoint.pt\n",
    )
    monkeypatch.setattr(
        controller,
        "_launch",
        lambda base, stage, command: launched.append((base, stage, command)),
    )

    result = controller.start(args)

    assert result["action"] == "started validation-bank export"
    assert result["export"]["state"] == "running"
    assert len(launched) == 1
    assert launched[0][1] == "export"
    assert "--n-events 4000" in launched[0][2]
    assert "--batch-size 128" in launched[0][2]
    assert "config_4090" not in launched[0][2]


def test_start_can_leave_unattended_evaluator_waiter(monkeypatch) -> None:
    args = _args()
    launched: list[tuple[str, str, str]] = []
    running = {
        "schema_version": 1,
        "kind": "status",
        "family": args.family,
        "run_tag": args.run_tag,
        "epoch": args.epoch,
        "checkpoint_sha256": args.checkpoint_sha256,
        "bank_ready": False,
        "results_ready": False,
        "export": {"state": "running", "pid": 123},
        "evaluate": {"state": "not_started"},
        "cbsc_training_started": False,
        "cbsc_test_events_used": 0,
    }
    both_running = {
        **running,
        "evaluate": {"state": "running", "pid": 456},
    }
    states = iter([running, both_running])
    lock = {
        "source_archives": {
            "ml-zdc.zip": {"commit": "1" * 40},
            "fastmc-tester.zip": {"commit": "2" * 40},
        }
    }
    monkeypatch.setattr(controller, "verify_dependencies", lambda: lock)
    monkeypatch.setattr(controller, "status", lambda _args: next(states))
    monkeypatch.setattr(
        controller,
        "_launch",
        lambda base, stage, command: launched.append((base, stage, command)),
    )

    result = controller.start(args)

    assert result["action"] == "started evaluator waiter"
    assert result["evaluate"]["state"] == "running"
    assert launched[0][1] == "evaluate"
    assert "while [ ! -f" in launched[0][2]
    assert "export.exit" in launched[0][2]
    assert "run_external_accepted_best_metrics.py" in launched[0][2]
    assert "MPLBACKEND=Agg" in launched[0][2]
    assert "CUBLAS_WORKSPACE_CONFIG=:4096:8" in launched[0][2]


def test_pull_ignores_transport_blank_lines(tmp_path, monkeypatch) -> None:
    args = _args()
    content = b"evidence\n"
    digest = __import__("hashlib").sha256(content).hexdigest()
    status = {
        "results_ready": True,
        "bank_ready": True,
        "export": {"state": "complete"},
        "evaluate": {"state": "complete"},
    }
    monkeypatch.setattr(controller, "ROOT", tmp_path)
    monkeypatch.setattr(controller, "status", lambda _args: status)

    def fake_dicos(command: list[str]) -> str:
        if command[0] == "exec":
            return f"\n{digest}  _external_metrics/runs/dicos-p9/epoch_0038/results/report.json\n\n"
        assert command[0] == "get"
        from pathlib import Path
        Path(command[2]).write_bytes(content)
        return ""

    monkeypatch.setattr(controller, "dicos", fake_dicos)
    result = controller.pull(args)
    assert result["files"] == ["report.json"]
    assert result["new_files"] == ["report.json"]
