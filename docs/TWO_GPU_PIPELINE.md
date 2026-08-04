# Exact DiCOS two-GPU work pipeline

This is the executable operating sequence for future CBSC-ZDC work. It does
not authorize a run. `docs/FOCUSED_OPERATING_RULES.md` is the short rule index;
`AGENTS.md` remains binding.

## Fixed topology

| Location | Sole responsibility | Environment |
|---|---|---|
| workstation | freeze/review inputs; refresh evidence; build/QA figures and sites; log and audit | repository environment |
| RTX 4090 | one training writer; checkpoint and required fixed-bank visualization acceptance gate | `.venv` |
| RTX 3090 | consume accepted checkpoints; generate 4,000 validation events per epoch; calculate diagnostic metrics | `.venv_3090` and `config_3090.json` |
| shared filesystem | namespaced immutable handoff state | project workdir only |

The 4090's 50-condition × 5-draw visualization stays inline and fatal. It is
the required structural acceptance gate and the dashboard payload. The 3090
does the large independent per-epoch generation used for diagnostic metrics
and figures. Moving the fatal visualization gate off the trainer would require
a new acknowledgement protocol and is not an organization-only change.

Test data never enters this loop. Both generated products use validation data.
Diagnostics and visuals are descriptive evidence, not checkpoint-selection
metrics and not Geant4 fidelity validation.

## State machine for every epoch

| State | Writer | Required evidence | Next state |
|---|---|---|---|
| training | 4090 trainer | validation loss and invariant report | checkpoint candidate |
| candidate | 4090 trainer | atomically written `best.pt`/`last.pt` | visualization gate |
| visualization gate | 4090 trainer | fixed selection hash; 50 × 5 draws; finite/nonnegative/support/closure QA | accepted or quarantined |
| accepted | 4090 callback | `reports/progress_epoch_NNNN.json` whose `last_checkpoint_sha256` matches `last.pt` | queued |
| queued | 4090 producer | atomic `_diag/<tag>/queue/ckpt_epoch_NNNN.pt`, epoch read from copied checkpoint | 3090 diagnostic |
| diagnosed | 3090 consumer | 4,000 validation events; zero train/test; complete bins; finite/nonnegative; `qa.pass=true` | refreshable |
| refreshed | workstation | remote/local hashes match; history and payload checks pass; figures and internal dashboard rebuilt | selection review |
| selected | workstation/operator | lowest independently verified validation loss for its family | public release candidate |
| published | public-site workflow | tests/build/deploy/live URL verified | logged release |

Failure is a terminal evidence state for that artifact, not a reason to relax a
check. Visualization failure means there is no progress marker, so the producer
cannot queue the checkpoint. Producer/wrapper failures write
`producer_failure.json`. Diagnostic exceptions preserve the checkpoint as
`.failed`; diagnostic QA failure writes `metrics_epoch_NNNN.failed.json`.
The consumer finishes draining but exits nonzero if any item was quarantined.
Ordinary refresh ignores neither condition: it imports only normal QA-passing
metrics and fails if accepted metric, visualization, epoch, or checkpoint hashes
disagree.

## One-time declaration before a launch

1. State the scientific question, family, seed, parent, additional epoch count,
   unique run tag, and unique job names.
2. Use only an accepted, hash-verified parent. `dicos-p10` epoch 40 is currently
   quarantined and is not a parent.
3. Change an unfrozen template/builder, generate the config, freeze it with the
   repository CLI, record hashes, and diff it. `training.epochs` is the absolute
   target: `parent_last_epoch + 1 + additional_epochs`.
4. Verify the canonical 612,482/76,158/76,300 split, pilot
   26,624/6,656/0 split, fixed visualization selection hash, data/geometry
   hashes, and zero new test use.
5. Append the declaration and evidence to `logs.md` and update the relevant
   JSON/Markdown audit twins before submission.

## Pre-launch gate

All checks must pass in the same session immediately before launch:

1. local and shared `repo/` commit identities match and both are clean;
2. 4090 and 3090 authenticate without printing credentials;
3. GPU identity, memory, utilization, and process trees show no conflicting
   trainer, producer, or consumer;
4. the target run directory, `_diag/<tag>/`, train log/PID, producer log/PID,
   and consumer log/PID do not already exist;
5. the frozen config and parent hashes match their recorded values;
6. the training run lock can have exactly one writer;
7. commands use `.venv` on 4090, `.venv_3090` plus explicit
   `DICOS_CONFIG` on 3090, and only workdir-relative paths.

Never infer liveness from a PID file or log alone. Probe the process tree. Never
reuse a tag or job name; old `EXIT` or `STOP` state is deliberately fatal.

## Exact start order

Replace every angle-bracket value with a declared value. These are templates,
not commands to run during the current no-training phase.

### 1. Start and verify the 3090 consumer

```bash
DICOS_CONFIG=$HOME/.dicos/config_3090.json PYTHONPATH=src \
python scripts/dicos.py start \
  'PYTHONNOUSERSITE=1 PYTHONPATH=repo/src .venv_3090/bin/python repo/scripts/dicos_diagnostics.py --n-events 4000 --selection-seed 20260803 --watch-dir _diag/<tag>/queue --output-dir _diag/<tag> --device cuda' \
  --name <tag>diag
```

Confirm its process on the 3090. Initial shard verification and validation-pool
construction can take minutes. Do not mistake a quiet log for a failed start.

### 2. Start and verify the 4090 producer

```bash
PYTHONPATH=src python scripts/dicos.py start \
  'PYTHONNOUSERSITE=1 .venv/bin/python repo/scripts/dicos_diag_producer.py --run-dir _runs/<family>_<tag> --wrapper-log _runs/<tag>train.log --run-tag <tag>' \
  --name <tag>prod
```

The producer waits. It cannot admit a checkpoint until the trainer has written
a matching post-visualization progress marker.

### 3. Start the 4090 trainer last, once

```bash
PYTHONPATH=src python scripts/dicos.py start \
  'PYTHONNOUSERSITE=1 PYTHONPATH=repo/src .venv/bin/python repo/scripts/dicos_train.py --config prep/configs/<frozen>.yaml --run-dir _runs/<family>_<tag> --device cuda --postflight' \
  --name <tag>train
```

`dicos.py start` now owns the terminal `EXIT=<code>` line. It rejects an
explicit shell `exec`, which could bypass that sentinel. Do not resubmit if the
client response is unclear: inspect `jobs`, logs, and the process tree first.

## Per-epoch refresh and review

After the 3090 writes a normal metric, run:

```bash
python scripts/refresh_continuation_outputs.py \
  --family <family> --run-tag <tag> \
  --run-dir _runs/<family>_<tag> \
  --lineage <oldest-tag> ... <tag> \
  --expected-epoch <absolute-epoch>
```

That single command now:

1. uses only the explicit 3090 config for diagnostics;
2. compares remote SHA-256 values with any existing local evidence;
3. downloads atomically and validates the validation-only 4,000-event contract;
4. atomically pulls/replaces the 4090 history rows;
5. downloads only visualization payloads whose checkpoint hashes match accepted
   3090 metrics, then merges them immutably into the internal dashboard;
6. rebuilds train/validation loss vs epoch and accepted running-best loss vs
   epoch;
7. rebuilds every 3090 metric vs epoch and the same metrics for the accepted
   validation-loss best-so-far checkpoint;
8. resolves all current-best graphics mechanically from standings plus the
   dashboard manifest, rebuilds `exhibition/current/model/index.html`, and rejects missing
   or ambiguous payloads;
9. rebuilds `exhibition/current/index.html`, `exhibition/archive/index.html`,
   the root router, and `metrics_catalog.json`, cataloging every
   scientific PNG/SVG while keeping historical test evidence visibly isolated;
10. writes immutable per-epoch audit twins plus
    `audit/current_epoch_pipeline.{json,md}`. The exact expected epoch must be
    present; a different/latest epoch cannot silently satisfy the refresh.

### Accepted-best external metrics

If—and only if—the refreshed epoch establishes a new accepted validation-loss
best, the refresh persists an external-metric transaction before allowing the
public release. It uses the same fixed validation selection with zero test
events and runs two downstream descriptions:

- four-momentum reconstruction through the hash-pinned
  `M1_xgb_focus_only` model from `ML ZDC all 1`, reported for Geant4 and Fast-MC
  so the channel-summed adapter has an explicit domain control;
- low-level C2ST AUROC through the hash-pinned `Fast-MC-tester` code, using
  exact-pair grouped internal train/validation/monitor partitions and three
  independent evaluator seeds.

These values never select, tune, gate, or stop CBSC. The historical 40,000-test-
event C2ST remains isolated and is not reused by this monitor. A new best's
public release stays pending until the validation-bank manifest, evaluator
manifest, artifact hashes, figures, and catalog all pass. A later refresh
continues the persisted transaction even though `family_choice.json` already
contains that best.

Manual status/recovery uses the same controller contract:

```bash
PYTHONPATH=src python scripts/dicos_external_metrics_controller.py status \
  --family <family> --run-tag <tag> --epoch <best-epoch> \
  --validation-loss <exact-loss> --checkpoint-sha256 <sha256>
```

`start` advances one detached stage per call. When export is running, a second
`start` installs an evaluator waiter so workstation shutdown cannot break the
handoff. `pull` is legal only after `results/manifest.json` exists. The
controller always forces `~/.dicos/config_3090.json`, validates every pinned
dependency hash, archives failed attempts, and never starts generator training.
The evaluator contract additionally requires deterministic PyTorch algorithms,
deterministic cuDNN, disabled cuDNN benchmarking, and
`CUBLAS_WORKSPACE_CONFIG=:4096:8`; seeded CUDA without that contract is not
accepted as reproducible.

For QA without DiCOS I/O or event generation, add `--offline`. This exercises
the same ordered rebuild and audit path from already-local immutable evidence.

Visually inspect changed figures and the internal dashboard. Then append the
epoch, losses, hashes, QA, timing, GPU/process state, failures, and decision to
`logs.md`; update current metrics/status and audit twins. Preserve every failed
epoch in its namespace.

The epoch audit reports `public_release_required=true` only when the new epoch
is accepted and lowers that family's validation-loss best. That flag is a
mandatory release handoff: update the one-snapshot-per-family public allowlist,
export, test, build, commit/push, verify the Pages workflow and live URL, then
record deployment. The refresh command automatically derives the allowlist and
prepares/tests/builds the sibling public repository when that flag is true;
commit/push and live deployment verification remain explicit. Override its
location with `--public-repo`. Diagnostic metrics never decide this flag.

## Selection and website boundary

Validation loss alone selects the checkpoint under the frozen rule. The 4,000-
event monitor and fixed-bank visuals may expose a failure and quarantine an
artifact, but may not tune or select it. Never consult test data.

The internal dashboard can acquire every accepted epoch for QA. The public
repository and [live site](https://julianattemptscoding.github.io/Fast-MC-Visual-Tests/)
change only when the family's lowest independently verified validation-loss
checkpoint changes. For such a change: sync the selected immutable payload,
run source/dashboard/public tests and builds, visually QA it, commit/push,
verify deployment rather than assuming it, verify the live URL, then update
`logs.md`, handoff/current status, metrics, and audit twins.

## Normal termination and recovery

- The trainer launcher writes `EXIT=0` or a nonzero code.
- On success, the producer verifies the final accepted checkpoint and writes
  namespaced `STOP` atomically.
- On wrapper or final-checkpoint failure, it writes quarantined failure evidence,
  writes `STOP`, and exits nonzero.
- The 3090 always drains queued checkpoints before honoring `STOP`.
- After draining, the 3090 exits nonzero if any checkpoint or metric was
  quarantined, so preserved negative evidence cannot look like a clean job.
- A same-host producer lock is reclaimed only when its recorded PID is provably
  dead; unreadable or other-host locks fail closed.
- A restarted refresh is hash-idempotent. A restarted producer/consumer is not
  launched blindly: inspect locks, process trees, `STOP`, done/failed files, and
  existing immutable metrics first. A new scientific attempt gets a new tag.

Training is complete only after producer/consumer termination, final refresh,
postflight, all QA, evidence/log/audit updates, and—only if selection changed—
verified public deployment.
