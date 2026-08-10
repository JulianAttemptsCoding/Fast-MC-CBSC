#!/usr/bin/env python
"""Unattended multi-segment training campaign supervisor for the DiCOS 4090.

Runs as one long-lived process under `scripts/dicos.py start`, so it survives
the client disconnecting -- though not the pod's own end time, which kills every
process inside it. On a fresh pod, re-launching this against the same plan picks
the campaign up from its recorded state.

What it does, per segment:

  1. resolve the parent checkpoint and its embedded epoch, verifying hashes;
  2. stage the parent into `prep/checkpoints/<family>_<stem>_{last,best}.pt`;
  3. generate a continuation template with `build_final_continuation.build`;
  4. freeze it through `cbsc_zdc.cli freeze-config` -- never hand-edited;
  5. **read its own diff** against the parent frozen config and refuse to launch
     if anything outside the allowed continuation delta moved;
  6. refuse to launch if the run directory exists or another trainer is running;
  7. launch the trainer and the diagnostic producer;
  8. classify the outcome from recorded evidence and decide what happens next.

The decision logic lives in `cbsc_zdc.training.campaign` and is unit-tested
without a GPU. This file is the I/O around it.

Everything it does is appended to `_campaign/<id>/events.jsonl` and summarised in
`_campaign/<id>/state.json`, because a run whose evidence was never written down
is a run that did not happen.

Usage:
    python scripts/dicos_campaign.py --plan configs/campaigns/<plan>.json \\
        --workdir . [--dry-run]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

import yaml  # noqa: E402

from cbsc_zdc.training.campaign import (  # noqa: E402
    CampaignError,
    SegmentPlan,
    SegmentResult,
    absolute_epoch_target,
    classify,
    verify_config_delta,
)

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from build_final_continuation import build as build_continuation  # noqa: E402


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utcnow() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class Journal:
    """Append-only event log plus a rewritten state summary."""

    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.events = self.directory / "events.jsonl"
        self.state_path = self.directory / "state.json"

    def event(self, kind: str, **payload) -> None:
        record = {"at": utcnow(), "kind": kind, **payload}
        with self.events.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        print(f"[{record['at']}] {kind}: {json.dumps(payload, sort_keys=True)}",
              flush=True)

    def state(self, **payload) -> None:
        payload["updated_at"] = utcnow()
        tmp = self.state_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
        tmp.replace(self.state_path)

    def load_state(self) -> dict:
        if self.state_path.exists():
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        return {}


def checkpoint_epoch(path: Path) -> int:
    """Read the epoch embedded in a checkpoint without building a model."""
    import torch

    payload = torch.load(path, map_location="cpu", weights_only=False)
    return int(payload["epoch"])


def other_trainer_running() -> list[tuple[int, str]]:
    """Scan /proc for another trainer, without matching this probe itself.

    A probe whose command line contains the string it searches for matches its
    own entry. That produced a phantom trainer once, and the kill that followed
    killed the probe. The token is therefore assembled at runtime and this
    process and its parent are excluded.
    """
    needle = "dicos_" + "train"
    mine = {os.getpid(), os.getppid()}
    hits: list[tuple[int, str]] = []
    for entry in Path("/proc").glob("[0-9]*"):
        try:
            pid = int(entry.name)
        except ValueError:
            continue
        if pid in mine:
            continue
        try:
            raw = (entry / "cmdline").read_bytes().decode("utf-8", "replace")
        except OSError:
            continue
        command = raw.replace("\0", " ").strip()
        if needle in command and "dicos_campaign" not in command:
            hits.append((pid, command[:160]))
    return hits


def other_supervisor_running(plan_name: str) -> list[tuple[int, str]]:
    """Scan /proc for another dicos_campaign.py supervisor on this same plan.

    Found the hard way 2026-08-10: a supervisor whose own trainer had already
    crashed can still be alive for minutes afterward doing its own
    post-launch bookkeeping (reading history, hashing checkpoints,
    classifying the outcome). A `dicos.py stop` on it does not guarantee it
    has actually exited by the time a caller checks GPU memory and concludes
    it is safe to relaunch. Two supervisors then both write to the same
    `_campaign/<id>/state.json` -- last write wins, with no lock -- and
    whichever one finishes its own (possibly much slower, crash-path)
    bookkeeping last silently overwrites the other's correct, live state
    with a stale verdict.

    Matched on the `--plan` file's own name rather than the campaign_id
    inside it: the id is not yet loaded at the point this must run, but the
    plan path is always present verbatim in every invocation's cmdline.
    Mirrors `other_trainer_running()`'s discipline: built at runtime so this
    probe cannot match its own /proc entry.
    """
    needle = "dicos_" + "campaign"
    mine = {os.getpid(), os.getppid()}
    hits: list[tuple[int, str]] = []
    for entry in Path("/proc").glob("[0-9]*"):
        try:
            pid = int(entry.name)
        except ValueError:
            continue
        if pid in mine:
            continue
        try:
            raw = (entry / "cmdline").read_bytes().decode("utf-8", "replace")
        except OSError:
            continue
        command = raw.replace("\0", " ").strip()
        if needle in command and plan_name in command:
            hits.append((pid, command[:200]))
    return hits


def read_history(run_dir: Path) -> list[dict]:
    """Epoch rows from the run's own history.csv."""
    history = run_dir / "logs" / "history.csv"
    if not history.exists():
        return []
    import csv

    with history.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    parsed = []
    for row in rows:
        try:
            parsed.append(
                {
                    "epoch": int(row["epoch"]),
                    "train_loss": float(row["train_loss"]),
                    "validation_loss": float(row["validation_loss"]),
                }
            )
        except (KeyError, TypeError, ValueError):
            continue
    return parsed


def invariant_failure_recorded(run_dir: Path) -> bool:
    directory = run_dir / "reports" / "visualization"
    if not directory.exists():
        return False
    return any(directory.glob("invariant_failure_epoch_*.json"))


def freeze(paths: dict, template: Path, output: Path) -> Path:
    command = [
        sys.executable, "-m", "cbsc_zdc.cli", "freeze-config",
        "--template", str(template),
        "--audit", str(paths["audit"]),
        "--geometry", str(paths["geometry"]),
        "--manifest", str(paths["manifest"]),
        "--splits", str(paths["splits"]),
        "--output", str(output),
    ]
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    result = subprocess.run(command, capture_output=True, text=True, env=env)
    if result.returncode != 0:
        raise CampaignError(
            f"freeze-config failed ({result.returncode}): {result.stderr.strip()}"
        )
    if not output.exists():
        raise CampaignError(f"freeze-config reported success but {output} is absent")
    return output


def prepare_segment(plan: SegmentPlan, workdir: Path, paths: dict,
                    journal: Journal, campaign: dict) -> tuple[Path, dict]:
    """Stage, build, freeze and verify. Returns the frozen config and its hashes."""
    parent_run = workdir / plan.parent_run_dir
    source_best = parent_run / "checkpoints" / "best.pt"
    source_last = parent_run / "checkpoints" / "last.pt"
    for path, expected, label in (
        (source_best, plan.parent_best_sha256, "best"),
        (source_last, plan.parent_last_sha256, "last"),
    ):
        if not path.exists():
            raise CampaignError(f"parent {label} checkpoint missing: {path}")
        actual = sha256_file(path)
        if expected and actual != expected:
            raise CampaignError(
                f"parent {label} checkpoint hash mismatch at {path}: "
                f"expected {expected}, found {actual}"
            )

    # Resume from the BEST checkpoint on both slots. dicos-p9 improved 0.067 by
    # resuming from its best rather than a later, worse last.pt; dicos-p8
    # resumed differently and gained nothing over the same nominal horizon.
    staged_dir = workdir / "prep" / "checkpoints"
    staged_dir.mkdir(parents=True, exist_ok=True)
    staged = {}
    for slot in ("last", "best"):
        target = staged_dir / f"{plan.family}_{plan.resume_from_stem}_{slot}.pt"
        target.write_bytes(source_best.read_bytes())
        staged[slot] = {"path": str(target), "sha256": sha256_file(target)}
    resume_sha = staged["best"]["sha256"]

    template_dir = REPO_ROOT / "configs" / "templates" / f"campaign_{campaign['campaign_id']}"
    parent_template = Path(campaign["families"][plan.family]["parent_template"])
    if not parent_template.is_absolute():
        parent_template = REPO_ROOT / parent_template
    if not parent_template.exists():
        raise CampaignError(f"parent template missing: {parent_template}")
    built = build_continuation(
        family=plan.family,
        parent_path=parent_template,
        last_sha256=resume_sha,
        best_sha256=resume_sha,
        output_dir=template_dir,
        patience=plan.patience,
        epochs=plan.epochs_absolute,
        run_tag=plan.run_tag,
        parent_last_epoch=plan.parent_last_epoch,
        checkpoint_stem=plan.resume_from_stem,
        selected_by=plan.reason,
        restart_scheduler=False,
    )

    frozen_dir = workdir / "prep" / "configs"
    frozen_dir.mkdir(parents=True, exist_ok=True)
    frozen = frozen_dir / f"frozen_{plan.family}_{plan.run_tag}.yaml"

    # A pod expires, the campaign is relaunched, and this segment is prepared
    # again. Freezing is deterministic given the same template and artifacts, so
    # an existing config is reusable exactly when re-freezing reproduces it byte
    # for byte. Anything else is a real disagreement and must stop the campaign
    # rather than be overwritten -- a frozen config is never edited in place.
    candidate = frozen_dir / f".frozen_{plan.family}_{plan.run_tag}.candidate.yaml"
    candidate.unlink(missing_ok=True)
    freeze(paths, built.path, candidate)
    if frozen.exists():
        existing_sha = sha256_file(frozen)
        candidate_sha = sha256_file(candidate)
        if existing_sha != candidate_sha:
            candidate.unlink(missing_ok=True)
            raise CampaignError(
                f"frozen config {frozen} already exists with sha256 {existing_sha} "
                f"but re-freezing this segment produces {candidate_sha}. Refusing "
                "to overwrite a frozen config; resolve which is correct by hand."
            )
        candidate.unlink(missing_ok=True)
        journal.event("frozen_config_reused", run_tag=plan.run_tag,
                      path=str(frozen), sha256=existing_sha)
    else:
        candidate.replace(frozen)

    parent_frozen = Path(campaign["families"][plan.family]["parent_frozen"])
    if not parent_frozen.is_absolute():
        parent_frozen = workdir / parent_frozen
    delta = verify_config_delta(
        yaml.safe_load(parent_frozen.read_text(encoding="utf-8")),
        yaml.safe_load(frozen.read_text(encoding="utf-8")),
    )

    hashes = {
        "template_sha256": built.sha256,
        "frozen_sha256": sha256_file(frozen),
        "parent_frozen": str(parent_frozen),
        "parent_frozen_sha256": sha256_file(parent_frozen),
        "resume_sha256": resume_sha,
        "staged": staged,
        "config_delta": {k: [str(v[0]), str(v[1])] for k, v in sorted(delta.items())},
    }
    journal.event("segment_frozen", run_tag=plan.run_tag, **hashes)
    return frozen, hashes


def launch(plan: SegmentPlan, workdir: Path, frozen: Path,
           journal: Journal) -> SegmentResult:
    run_dir = workdir / "_runs" / f"{plan.family}_{plan.run_tag}"
    if run_dir.exists():
        raise CampaignError(f"run directory already exists: {run_dir}")
    conflicting = other_trainer_running()
    if conflicting:
        raise CampaignError(f"another trainer is already running: {conflicting}")

    venv_python = workdir / ".venv" / "bin" / "python"
    trainer = [
        str(venv_python), str(workdir / "repo" / "scripts" / "dicos_train.py"),
        "--config", str(frozen),
        "--run-dir", str(run_dir),
        "--device", "cuda",
        "--postflight",
    ]
    env = dict(os.environ)
    env["PYTHONPATH"] = str(workdir / "repo" / "src")
    env["PYTHONNOUSERSITE"] = "1"
    # Every accepted run since dicos-r2 was archived as `aborted_r2_slow_loader`
    # has used this. It makes each loader worker hold all 187 shards resident
    # instead of 4, so a shard is verified once per worker rather than
    # thousands of times -- never zero times. It is a transport property, proven
    # byte-identical over 400 samples through both cache sizes, and it is
    # recorded in each run's environment.json.
    env.setdefault("CBSC_ZDC_SHARD_CACHE", "0")
    # Some pod images ship a 0-byte stub at the default multiarch libcuda.so.1
    # path, shadowing the real, correctly versioned driver library that only
    # exists under /usr/lib64. Confirmed on the L40S/CUDA13 pod that replaced
    # the retired 4090: torch imported fine but every CUDA call failed with
    # cudaErrorSystemDriverMismatch (803) until /usr/lib64 was searched first.
    # Prepending is a no-op on a pod that does not have this problem.
    existing_ld_path = env.get("LD_LIBRARY_PATH", "")
    env["LD_LIBRARY_PATH"] = "/usr/lib64" + (
        ":" + existing_ld_path if existing_ld_path else ""
    )

    train_log = workdir / "_runs" / f"{plan.run_tag}train.log"
    journal.event("segment_launch", run_tag=plan.run_tag, run_dir=str(run_dir),
                  command=" ".join(trainer), log=str(train_log))

    producer = None
    diag_dir = workdir / "_diag" / plan.run_tag
    diag_dir.mkdir(parents=True, exist_ok=True)
    producer_script = workdir / "repo" / "scripts" / "dicos_diag_producer.py"
    with train_log.open("ab") as handle:
        handle.write(f"=== {plan.family} {plan.run_tag} START {utcnow()}\n".encode())
        handle.flush()
        started = time.time()
        process = subprocess.Popen(trainer, stdout=handle, stderr=subprocess.STDOUT,
                                   cwd=str(workdir), env=env)
        if producer_script.exists():
            # The producer rejects absolute paths outright: it resolves both
            # arguments under the workdir and refuses anything that escapes it.
            # Passing absolute paths killed it instantly on the first launch,
            # and because nothing waits on it until the trainer exits, it sat as
            # a zombie while the campaign looked healthy -- no checkpoint would
            # ever have reached the 3090.
            producer = subprocess.Popen(
                [str(venv_python), str(producer_script),
                 "--run-dir", str(run_dir.relative_to(workdir)),
                 "--wrapper-log", str(train_log.relative_to(workdir)),
                 "--run-tag", plan.run_tag],
                stdout=(workdir / "_runs" / f"{plan.run_tag}prod.log").open("ab"),
                stderr=subprocess.STDOUT, cwd=str(workdir), env=env,
            )
            # A dead producer means no diagnostics for the entire campaign, so
            # it is verified rather than assumed.
            time.sleep(5)
            if producer.poll() is not None:
                process.terminate()
                log_tail = ""
                producer_log = workdir / "_runs" / f"{plan.run_tag}prod.log"
                if producer_log.exists():
                    log_tail = producer_log.read_text(
                        encoding="utf-8", errors="replace")[-800:]
                raise CampaignError(
                    f"diagnostic producer exited immediately "
                    f"({producer.returncode}); refusing to train blind. "
                    f"Producer log tail: {log_tail}"
                )
            journal.event("producer_started", run_tag=plan.run_tag, pid=producer.pid)
        exit_code = process.wait()
        elapsed = round(time.time() - started, 3)
        handle.write(f"=== {plan.family} {plan.run_tag} EXIT={exit_code} "
                     f"{utcnow()} wall {elapsed}s\n".encode())

    if producer is not None:
        try:
            producer.wait(timeout=180)
        except subprocess.TimeoutExpired:
            producer.terminate()
            journal.event("producer_terminated", run_tag=plan.run_tag)

    epochs = read_history(run_dir)
    failure = invariant_failure_recorded(run_dir)
    last_written = None
    checkpoint = run_dir / "checkpoints" / "last.pt"
    if checkpoint.exists():
        try:
            last_written = checkpoint_epoch(checkpoint)
        except Exception as error:  # pragma: no cover - defensive
            journal.event("checkpoint_unreadable", run_tag=plan.run_tag,
                          error=repr(error))

    result = SegmentResult(exit_code=exit_code, epochs=epochs,
                           invariant_failure=failure, last_epoch_written=last_written)
    journal.event("segment_finished", run_tag=plan.run_tag, exit_code=exit_code,
                  wall_seconds=elapsed, epochs_completed=len(epochs),
                  latest_epoch=result.latest_epoch,
                  best=list(result.best()) if result.best() else None,
                  invariant_failure=failure)
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--workdir", default=".", type=Path)
    parser.add_argument("--dry-run", action="store_true",
                        help="freeze and verify the next segment, then stop "
                             "without launching a trainer")
    args = parser.parse_args(argv)

    conflicting = other_supervisor_running(Path(args.plan).name)
    if conflicting:
        raise CampaignError(
            f"another supervisor for {args.plan.name} is already running: "
            f"{conflicting} -- confirm it has fully exited (it may still be "
            "finishing post-launch bookkeeping after its own trainer already "
            "died) before starting a second one"
        )

    workdir = args.workdir.resolve()
    campaign = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    journal = Journal(workdir / "_campaign" / campaign["campaign_id"])

    paths = {key: (workdir / value) for key, value in campaign["artifacts"].items()}
    for label, path in paths.items():
        if not path.exists():
            raise CampaignError(f"campaign artifact {label} missing: {path}")

    state = journal.load_state()
    chain = list(campaign["chain"])
    index = int(state.get("chain_index", 0))
    segment_number = int(state.get("segments_run", 0))
    parent = state.get("parent")
    window = int(campaign.get("improvement_window", 6))
    additional = int(campaign.get("segment_epochs", 20))
    max_segments = int(campaign.get("max_segments", 24))

    journal.event("campaign_start", campaign_id=campaign["campaign_id"],
                  chain=chain, chain_index=index, segments_run=segment_number,
                  improvement_window=window, segment_epochs=additional,
                  dry_run=bool(args.dry_run))

    while index < len(chain) and segment_number < max_segments:
        family = chain[index]
        spec = campaign["families"][family]
        if parent is None or parent.get("family") != family:
            parent = {
                "family": family,
                "run_dir": spec["parent_run_dir"],
                "last_epoch": int(spec["parent_last_epoch"]),
                "best_sha256": spec["parent_best_sha256"],
                "last_sha256": spec["parent_last_sha256"],
            }
        segment_number += 1
        run_tag = f"{campaign['run_tag_prefix']}-{segment_number:02d}"
        plan = SegmentPlan(
            family=family,
            run_tag=run_tag,
            parent_run_dir=parent["run_dir"],
            parent_last_epoch=int(parent["last_epoch"]),
            parent_best_sha256=parent["best_sha256"],
            parent_last_sha256=parent["last_sha256"],
            resume_from_stem=run_tag.replace("-", ""),
            epochs_absolute=absolute_epoch_target(int(parent["last_epoch"]), additional),
            patience=additional,
            additional_epochs=additional,
            reason=parent.get("reason", "first segment of the declared chain"),
        )
        journal.state(campaign_id=campaign["campaign_id"], chain_index=index,
                      segments_run=segment_number - 1, parent=parent,
                      current=plan.as_dict(), status="preparing")

        frozen, hashes = prepare_segment(plan, workdir, paths, journal, campaign)
        if args.dry_run:
            journal.event("dry_run_stop", run_tag=run_tag, frozen=str(frozen))
            journal.state(campaign_id=campaign["campaign_id"], chain_index=index,
                          segments_run=segment_number - 1, parent=parent,
                          current=plan.as_dict(), status="dry_run_complete",
                          frozen=str(frozen), hashes=hashes)
            return 0

        journal.state(campaign_id=campaign["campaign_id"], chain_index=index,
                      segments_run=segment_number, parent=parent,
                      current=plan.as_dict(), status="training", hashes=hashes)
        result = launch(plan, workdir, frozen, journal)

        has_next = index + 1 < len(chain)
        outcome, reason = classify(result, window=window, has_next_family=has_next)
        journal.event("segment_decision", run_tag=run_tag, outcome=outcome,
                      reason=reason)

        run_dir = f"_runs/{family}_{run_tag}"
        if outcome == "continue_same_family":
            best_epoch, _ = result.best()
            parent = {
                "family": family, "run_dir": run_dir,
                "last_epoch": best_epoch,
                "best_sha256": sha256_file(workdir / run_dir / "checkpoints" / "best.pt"),
                "last_sha256": sha256_file(workdir / run_dir / "checkpoints" / "last.pt"),
                "reason": reason,
            }
        elif outcome == "resume_same_segment":
            latest = result.latest_epoch
            parent = {
                "family": family, "run_dir": run_dir, "last_epoch": latest,
                "best_sha256": sha256_file(workdir / run_dir / "checkpoints" / "best.pt"),
                "last_sha256": sha256_file(workdir / run_dir / "checkpoints" / "last.pt"),
                "reason": reason,
            }
        elif outcome == "advance_family":
            index += 1
            parent = None
        else:
            journal.state(campaign_id=campaign["campaign_id"], chain_index=index,
                          segments_run=segment_number, parent=parent,
                          status=outcome, reason=reason)
            journal.event("campaign_end", outcome=outcome, reason=reason)
            return 0 if outcome == "campaign_complete" else 1

    journal.event("campaign_end", outcome="exhausted",
                  reason=f"chain_index={index} segments_run={segment_number}")
    journal.state(campaign_id=campaign["campaign_id"], chain_index=index,
                  segments_run=segment_number, parent=parent, status="exhausted")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CampaignError as error:
        print(f"CAMPAIGN REFUSED: {error}", file=sys.stderr, flush=True)
        raise SystemExit(2)
