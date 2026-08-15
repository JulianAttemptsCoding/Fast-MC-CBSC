"""Start, inspect, or pull the accepted-best external metric transaction.

The controller always uses the RTX-3090 DiCOS credential, validates the pinned
external dependency hashes, and advances at most one detached stage per call:
event-bank export, then downstream evaluator execution, then immutable pull.
It never starts or resumes CBSC generator training.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "configs" / "external_metric_dependencies.json"
RUN_TAG = re.compile(r"^[a-z0-9][a-z0-9-]*$")
FAMILY = re.compile(r"^[a-z0-9][a-z0-9_]*$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def dicos(args: list[str]) -> str:
    env = dict(os.environ)
    env["PYTHONPATH"] = "src"
    env["DICOS_CONFIG"] = str(Path.home() / ".dicos" / "config_3090.json")
    result = subprocess.run(
        [sys.executable, "scripts/dicos.py", *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout


def validate_args(args) -> None:
    if not RUN_TAG.fullmatch(args.run_tag):
        raise ValueError("unsafe run tag")
    if not FAMILY.fullmatch(args.family):
        raise ValueError("unsafe family")
    if not HEX64.fullmatch(args.checkpoint_sha256):
        raise ValueError("checkpoint SHA-256 must be lowercase hex")
    if args.epoch < 0 or not (0.0 < args.validation_loss < 100.0):
        raise ValueError("invalid accepted-best epoch/loss")


def remote_paths(args) -> dict[str, str]:
    base = f"_external_metrics/runs/{args.run_tag}/epoch_{args.epoch:04d}"
    return {
        "base": base,
        "bank": f"{base}/validation_bank.npz",
        "bank_manifest": f"{base}/validation_bank.manifest.json",
        "results": f"{base}/results",
        "result_manifest": f"{base}/results/manifest.json",
        "checkpoint": (
            f"_diag/{args.run_tag}/queue/done/ckpt_epoch_{args.epoch:04d}.pt"
        ),
    }


def verify_dependencies() -> dict:
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    expected: dict[str, str] = {
        path: row["sha256"] for path, row in lock["source_archives"].items()
    }
    model_root = "_external_metrics/deps/reco_model/models/M1_xgb_focus_only"
    expected.update(
        {
            f"{model_root}/{name}": digest
            for name, digest in lock["reconstruction_contract"][
                "model_artifacts"
            ].items()
        }
    )
    command = "sha256sum " + " ".join(shlex.quote(path) for path in expected)
    observed = {}
    for line in dicos(["exec", command]).splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})\s+(.+)", line.strip())
        if match:
            observed[match.group(2)] = match.group(1)
    if observed != expected:
        raise RuntimeError(
            f"external dependency lock mismatch: expected={expected}, observed={observed}"
        )
    return lock


def _stage_state(base: str, stage: str) -> dict:
    pid_path = f"{base}/{stage}.pid"
    exit_path = f"{base}/{stage}.exit"
    command = (
        f"if [ -f {shlex.quote(exit_path)} ]; then "
        f"echo EXIT=$(cat {shlex.quote(exit_path)}); "
        f"elif [ -f {shlex.quote(pid_path)} ]; then "
        f"p=$(cat {shlex.quote(pid_path)}); "
        'if kill -0 "$p" 2>/dev/null; then echo RUNNING=$p; '
        "else echo STALE_PID=$p; fi; else echo NOT_STARTED; fi"
    )
    output = dicos(["exec", command]).strip()
    if output.startswith("EXIT="):
        return {"state": "complete" if output == "EXIT=0" else "failed", "raw": output}
    if output.startswith("RUNNING="):
        return {"state": "running", "pid": int(output.split("=", 1)[1])}
    if output.startswith("STALE_PID="):
        return {"state": "stale", "pid": int(output.split("=", 1)[1])}
    return {"state": "not_started"}


def status(args) -> dict:
    paths = remote_paths(args)
    flags = dicos(
        [
            "exec",
            (
                f"test -f {shlex.quote(paths['bank_manifest'])} && echo BANK_READY || echo BANK_MISSING; "
                f"test -f {shlex.quote(paths['result_manifest'])} && echo RESULTS_READY || echo RESULTS_MISSING"
            ),
        ]
    ).splitlines()
    return {
        "schema_version": 1,
        "kind": "cbsc-zdc-external-metric-controller-status",
        "family": args.family,
        "run_tag": args.run_tag,
        "epoch": args.epoch,
        "checkpoint_sha256": args.checkpoint_sha256,
        "bank_ready": "BANK_READY" in flags,
        "results_ready": "RESULTS_READY" in flags,
        "export": _stage_state(paths["base"], "export"),
        "evaluate": _stage_state(paths["base"], "evaluate"),
        "cbsc_training_started": False,
        "cbsc_test_events_used": 0,
    }


def _launch(base: str, stage: str, command: str) -> None:
    pid_path = f"{base}/{stage}.pid"
    exit_path = f"{base}/{stage}.exit"
    log_path = f"{base}/{stage}.log"
    attempts = f"{base}/attempts"
    partial_outputs = (
        [f"{base}/validation_bank.npz", f"{base}/validation_bank.manifest.json"]
        if stage == "export"
        else [f"{base}/results"]
    )
    archived_paths = [pid_path, exit_path, log_path, *partial_outputs]
    archive = (
        f"stamp=$(date -u +%Y%m%dT%H%M%SZ)-$$; "
        f"mkdir -p {shlex.quote(attempts)}; "
        f"for f in {' '.join(shlex.quote(path) for path in archived_paths)}; do "
        f"if [ -e \"$f\" ]; then name=$(basename \"$f\"); "
        f"mv \"$f\" {shlex.quote(attempts)}/\"$stamp.$name\"; fi; done"
    )
    logged_command = (
        f"( {command} ); code=$?; "
        f"printf '%s\\n' \"$code\" > {shlex.quote(exit_path)}; exit \"$code\""
    )
    wrapper = (
        f"mkdir -p {shlex.quote(base)}; {archive}; "
        f"nohup sh -c {shlex.quote(logged_command)} "
        f"> {shlex.quote(log_path)} 2>&1 & "
        f"printf '%s\\n' \"$!\" > {shlex.quote(pid_path)}"
    )
    dicos(["exec", wrapper])


def _evaluation_command(lock: dict, paths: dict[str, str]) -> str:
    reco_commit = next(
        row["commit"]
        for path, row in lock["source_archives"].items()
        if "ml-zdc" in path
    )
    auroc_commit = next(
        row["commit"]
        for path, row in lock["source_archives"].items()
        if "fastmc-tester" in path
    )
    return " ".join(
        [
            "env PYTHONPATH=repo/src:repo MPLBACKEND=Agg CUBLAS_WORKSPACE_CONFIG=:4096:8",
            ".venv_3090/bin/python",
            "_external_metrics/runtime/run_external_accepted_best_metrics.py",
            "--bank",
            shlex.quote(paths["bank"]),
            "--bank-manifest",
            shlex.quote(paths["bank_manifest"]),
            "--output-dir",
            shlex.quote(paths["results"]),
            "--mode all --device cuda",
            "--geometry-json repo/dashboard/public/data/geometry.json",
            "--reco-repo _external_metrics/deps/ml_zdc",
            "--reco-commit",
            reco_commit,
            "--reco-model-dir _external_metrics/deps/reco_model/models/M1_xgb_focus_only",
            "--reco-config _external_metrics/deps/ml_zdc/configs/legacy_vertex_default.yaml",
            "--reco-frame-report _external_metrics/deps/ml_zdc/outputs/preflight/accepted_inspection_report.json",
            "--auroc-repo _external_metrics/deps/fastmc_tester",
            "--auroc-commit",
            auroc_commit,
            "--auroc-config _external_metrics/runtime/external_metrics_accepted_best.json",
            "--auroc-geometry prep/geometry_frozen",
        ]
    )


def start(args) -> dict:
    lock = verify_dependencies()
    paths = remote_paths(args)
    current = status(args)
    if current["results_ready"]:
        return {**current, "action": "none; results already complete"}
    if current["export"]["state"] == "stale" or current["evaluate"]["state"] == "stale":
        raise RuntimeError(f"external metric stage has a stale pid: {current}")
    if not current["bank_ready"]:
        if current["export"]["state"] == "running":
            if current["evaluate"]["state"] == "running":
                return {**current, "action": "none; export and evaluator waiter running"}
            wait_command = (
                f"while [ ! -f {shlex.quote(paths['bank_manifest'])} ]; do "
                f"if [ -f {shlex.quote(paths['base'] + '/export.exit')} ] && "
                f"[ \"$(cat {shlex.quote(paths['base'] + '/export.exit')})\" != 0 ]; "
                "then exit 1; fi; sleep 15; done; "
                + _evaluation_command(lock, paths)
            )
            _launch(paths["base"], "evaluate", wait_command)
            return {**status(args), "action": "started evaluator waiter"}
        checkpoint_probe = dicos(
            ["exec", f"sha256sum {shlex.quote(paths['checkpoint'])}"]
        ).strip()
        if not checkpoint_probe.startswith(args.checkpoint_sha256 + "  "):
            raise RuntimeError("remote accepted-best checkpoint hash mismatch")
        command = " ".join(
            [
                "env PYTHONPATH=repo/src:repo",
                ".venv_3090/bin/python",
                "_external_metrics/runtime/export_external_validation_bank.py",
                "--checkpoint",
                shlex.quote(paths["checkpoint"]),
                "--checkpoint-sha256",
                args.checkpoint_sha256,
                "--family",
                args.family,
                "--run-tag",
                args.run_tag,
                "--epoch",
                str(args.epoch),
                "--validation-loss",
                repr(args.validation_loss),
                "--output",
                shlex.quote(paths["bank"]),
                "--n-events 4000 --selection-seed 20260803 --batch-size 128 --device cuda",
            ]
        )
        _launch(paths["base"], "export", command)
        return {**status(args), "action": "started validation-bank export"}

    if current["evaluate"]["state"] == "running":
        return {**current, "action": "none; external evaluators running"}
    _launch(paths["base"], "evaluate", _evaluation_command(lock, paths))
    return {**status(args), "action": "started four-momentum and AUROC evaluators"}


def pull(args) -> dict:
    paths = remote_paths(args)
    current = status(args)
    if not current["results_ready"]:
        raise RuntimeError(f"external results are not complete: {current}")
    listing = dicos(
        [
            "exec",
            (
                f"find {shlex.quote(paths['results'])} -type f ! -name best_evaluator.pt "
                "-exec sha256sum {} + | sort"
            ),
        ]
    )
    prefix = paths["results"] + "/"
    remote: dict[str, str] = {}
    for line in listing.splitlines():
        if not line.strip():
            continue
        match = re.fullmatch(r"([0-9a-f]{64})\s+(.+)", line.strip())
        if not match or not match.group(2).startswith(prefix):
            raise RuntimeError(f"unsafe external result listing: {line!r}")
        relative = match.group(2)[len(prefix) :]
        if not relative or ".." in Path(relative).parts:
            raise RuntimeError("external result listing escaped its namespace")
        remote[relative] = match.group(1)
    destination = (
        ROOT
        / "exhibition"
        / "current"
        / "external_metrics"
        / "source_data"
        / args.run_tag
        / f"epoch_{args.epoch:04d}"
    )
    pulled = []
    for relative, digest in sorted(remote.items()):
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_file():
            if sha256_file(target) != digest:
                raise RuntimeError(f"local external result conflicts: {target}")
            continue
        partial = target.with_name(f".{target.name}.part")
        partial.unlink(missing_ok=True)
        dicos(["get", prefix + relative, str(partial)])
        if sha256_file(partial) != digest:
            partial.unlink(missing_ok=True)
            raise RuntimeError(f"external result download hash mismatch: {relative}")
        partial.replace(target)
        pulled.append(relative)
    return {
        **current,
        "action": "pulled immutable external metric evidence",
        "destination": destination.relative_to(ROOT).as_posix(),
        "files": sorted(remote),
        "new_files": pulled,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("status", "start", "pull"))
    parser.add_argument("--family", required=True)
    parser.add_argument("--run-tag", required=True)
    parser.add_argument("--epoch", type=int, required=True)
    parser.add_argument("--validation-loss", type=float, required=True)
    parser.add_argument("--checkpoint-sha256", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    validate_args(args)
    functions = {"status": status, "start": start, "pull": pull}
    print(json.dumps(functions[args.action](args), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
