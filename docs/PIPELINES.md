# Pipelines — every operation, end to end

Written 2026-08-15. This is the operational manual: every pipeline this project
has, in order, with the exact command for each step and what "working" looks
like. Commands marked **[verified 2026-08-15]** were executed on that date and
produced the stated output.

**Read order for a new agent:**
1. `AGENTS.md` — the binding contract. Non-negotiable.
2. `CLAUDE.md` — session rules for this host.
3. `docs/HANDOFF.md` §0 — the two corrections that change how older numbers read.
4. `docs/V3_FULL_REPORT.md` — the complete v3 record.
5. This file — how to actually run things.
6. `docs/WALKAWAY_RUNBOOK.md` — what is running right now.

Terminal status: **`PHYSICS VALIDATION NOT ESTABLISHED`**.

---

## 0. The rules that will bite you

These are the ones that have already cost this project real time. Full list in
`AGENTS.md`; these are the operational subset.

| Rule | Consequence of breaking it |
|---|---|
| **One writer per run directory**, proved from the process tree | Two trainers corrupt one run |
| A probe must **not match itself** — build the token at runtime, exclude own pid and parent | Phantom trainer; a `kill -9` once killed the probe |
| **`dicos.py stop` leaves children alive.** For a *chained* script, kill the **shell first**, then its child | The shell starts the next item; two jobs race one output path |
| **Never hand-edit a frozen config** | Edit a template, regenerate, freeze through the CLI, record both hashes |
| **Never weaken a test, threshold, guard or assertion to pass** | Fix what the guard caught |
| **Never touch the test split** | Sealed. Zero test events anywhere |
| **`LD_LIBRARY_PATH=/usr/lib64:` on the training pod** | Every CUDA call fails with error 803 |
| Git Bash mangles `/usr/lib64` → prefix `MSYS_NO_PATHCONV=1` | Which also disables `~`, so pass `DICOS_CONFIG` as `C:/Users/...` |
| **Never run `dicos.py setup` on a second pod** | It rebuilds the shared venv under a live trainer |
| **The 3090 has no `git`** | Both pods share `repo/`; pull from the 4090 side |
| `pytest` needs `PYTHONPATH=src` | Without it, zero tests collect and it looks like a pass |

### The one scientific rule that is easy to get wrong

**Compare a v3 screening row to M0-fresh (4.935508 on the common deposited-
energy-GeV response-density measure), never to B0 (4.483768) or raw M0
(4.513572).** Historical v2 totals receive the audited +0.421936354321
target-Jacobian offset before any cross-response-mode comparison. Raw values
remain provenance only.
Every screening row uses `initialize_from`, which transfers weights but not
optimizer state, and that fresh Adam costs a measured **0.021601**. Comparing to
B0 charges the feature for the optimizer restart.

**The frozen 0.65 diagnostic is `max_high_level_c2st_auc`.** B0's value for it is
**0.892897**. The hybrid figure 0.843222 is a different family answering to a
different gate. Never mix them.

---

## 1. Session start — do this before anything else

```bash
git fetch origin && git status --short && git log -5 --oneline && git rev-list --left-right --count origin/main...HEAD
```

`git fetch` **first**: without it `origin/main` is a cached ref, and on
2026-08-05 that made a pushed pod commit look like 19 unpushed commits.

```bash
python scripts/dicos.py exec "nvidia-smi --query-gpu=name,uuid,memory.total,memory.free,driver_version --format=csv,noheader"
```

```bash
MSYS_NO_PATHCONV=1 DICOS_CONFIG="C:/Users/Julia/.dicos/config_3090.json" python scripts/dicos.py exec "nvidia-smi --query-gpu=name,uuid,memory.total,memory.free --format=csv,noheader"
```

**Re-probe the fleet every session — it has changed three times.** As of
2026-08-15: training slot **RTX 4090** 24,564 MiB, diagnostics slot **RTX 3090**
24,576 MiB. The L40S is retired.

Then read the newest `logs.md` entries and `docs/WALKAWAY_RUNBOOK.md`.

---

## 2. What is running right now

```bash
python scripts/dicos.py jobs
```

```bash
python scripts/watch_v3_outputs.py --status
```

Prove there is no live writer before starting anything. Use `ps`, which reports
the process tree without inspecting a forbidden filesystem path. The search
token is assembled at runtime so the probe cannot match its own command line:

```bash
python scripts/dicos.py exec "command -v ps >/dev/null 2>&1 || { echo PROCESS_TREE_UNAVAILABLE; exit 2; }; ps -eo pid=,ppid=,args= | awk 'BEGIN { t=\"dicos_\" \"train\" } index(\$0,t) { print }'"
```

**A live trainer shows as MANY pids, not one.** `num_workers: 4` means one
trainer plus its dataloader workers, and workers are recycled between epochs, so
8–9 matching pids is normal for a single run. Check `ppid`: if they all share one
parent, that is **one writer**.

The first two columns are `pid` and `ppid`. Two distinct trainer parents means
two writers. Kill the **shell** first, then its child. If `ps` is unavailable,
the invariant cannot be proved within the read allowlist: do not launch another
writer.

---

## 3. Pipeline A — a v3 screening row, start to finish

This is the main scientific loop. Five steps, in order.

### A1. Build the template

```bash
python scripts/dicos.py exec "cd '<WORKDIR>' && PYTHONNOUSERSITE=1 PYTHONPATH=repo/src .venv/bin/python repo/scripts/build_v3_screening_configs.py --parent prep/configs/frozen_calibrated_lr3e4_dicos-f-02.yaml --envelope _v3/envelope_pilot_full.json --output-dir _v3/templates --only S3-first --horizon 24"
```

**Inheritance is opt-in.** Default carries nothing forward. Pass `--inherit` only
with rows that were **promoted**; it refuses standalone controls. The original
matrix lists S1..S5 as a cumulative chain on the assumption every row promotes —
S1 did not, so a blind chain would stack a rejected feature.

Good output: `inherited_from_promoted_rows: []` and `features` containing exactly
the one declared change.

### A2. Migrate the parent checkpoint, then freeze

```bash
python scripts/dicos.py exec "cd '<WORKDIR>' && LD_LIBRARY_PATH=/usr/lib64:\$LD_LIBRARY_PATH PYTHONNOUSERSITE=1 PYTHONPATH=repo/src .venv/bin/python repo/scripts/v3_prepare_screening_run.py --template _v3/templates/v3_S3_first.yaml --parent-checkpoint _runs/calibrated_lr3e4_dicos-f-02/checkpoints/best.pt --audit prep/train_data_audit_pilot.json --frozen-output prep/configs/frozen_v3_S3_first.yaml --checkpoint-output prep/checkpoints/v3_S3_first_init.pt --checkpoint-relative checkpoints/v3_S3_first_init.pt --report audit/v3_S3_first_preparation.json"
```

Migration happens **before** freezing, because the frozen config must carry
`initialize_from_sha256`, which cannot exist until the checkpoint does.

**Read the migration counts. They tell you what kind of row this is:**

| Counts | Meaning |
|---|---|
| `expanded 2, initialized 17` | axis columns added — migration is a behavioural no-op |
| `expanded 0, initialized 15` | a head was **replaced** (S2's spline) |
| `expanded 0, initialized 23` | a head was **replaced** (S3's hierarchical first layer) |
| `unexpected` anything but 0 | **stop.** An unclassified key is fatal |

### A3. Launch

```bash
python scripts/dicos.py start "cd '<WORKDIR>' && LD_LIBRARY_PATH=/usr/lib64:\$LD_LIBRARY_PATH PYTHONNOUSERSITE=1 PYTHONPATH=repo/src .venv/bin/python repo/scripts/dicos_train.py --config prep/configs/frozen_v3_S3_first.yaml --run-dir _runs/v3_S3_first --staged-root prep --postflight" --name v3s3
```

Or let the queue do it (§5).

**Check epoch 0 against the right expectation:**

- Migration was a **no-op** (axis rows) → epoch 0 near **4.66**. Near 5.2 means
  the `initialize_from` pointer is broken. That is what S1's first, discarded
  launch produced.
- A head was **replaced** (S2, S3) → epoch 0 is legitimately high. S2 began at
  **5.064650** with a correct pointer, because the response NLL starts untrained.

Verify the pointer before concluding anything:

```bash
python scripts/dicos.py exec "cd '<WORKDIR>' && PYTHONNOUSERSITE=1 .venv/bin/python -c \"
import yaml; t=yaml.safe_load(open('_runs/v3_S3_first/runtime_config.yaml'))['training']
print(t.get('initialize_from'), t.get('initialize_from_sha256'))\""
```

GPU at 0% with a live pid for several minutes is **normal** — preflight hashes
every shard before epoch 0.

### A4. Import the evidence

```bash
PYTHONPATH=src python scripts/import_v3_screening_run.py --row S3-first --report audit/v3_S3_import.json
```

Hash-verifies the frozen config (and checkpoints once declared) **on the pod**
rather than trusting the registry, re-derives each invariant report's `pass` from
its structural counts, and checks closure against the report's **effective**
tolerance — `max(absolute, relative × total_response)` — never the 2e-5 floor
alone. Comparing to the floor is what ended `dicos-p10` on a perfect epoch.

Safe to run mid-flight: the trainer writes the invariant report before the
history row, so a half-written epoch is never imported.

### A5. Rebuild and decide

```bash
PYTHONPATH=src python exhibition/build_v3_screening_figure.py
```

Then set `status: complete` and write a `disposition` in
`exhibition/data/v3_screening_rows.json`. A test enforces that only a completed
row may claim a disposition, and that an unpromoted one states its reason.

**The promotion rule: retain the simpler parent when an improvement is
statistically unresolved.** A negative result is a result. Compare against
**M0-fresh**, and against the run-to-run reference of **0.001259**.

---

## 4. Pipeline B — the validation battery

### B1. Freeze the bank (once; already done)

Bank `_v3/validation_bank_10k.json`, internal content sha256 `1bc3a6b2…`, byte-
file sha256 `ee77517b…`, 10,000 pairs = 20,000
evaluator examples, every bin 1,182–1,310 against a floor of 500.

Built from the **canonical** split. The pilot split holds only 6,656 validation
events — below the frozen 10,000 minimum. Cross-tabulation proved pilot train →
100% canonical train and pilot validation → 100% canonical validation, so B0 has
seen none of the 10,000.

### B2. Evaluate completed checkpoints automatically

```bash
PYTHONPATH=src python scripts/v3_battery_controller.py --status
PYTHONPATH=src python scripts/v3_battery_controller.py --advance
```

The workstation watcher calls `--advance` every 900 seconds; operators do not
need to issue it. B0 must have its passing terminal gate. A screening row must
have its full contiguous declared horizon and every invariant report. The
controller selects the lowest validation loss only, verifies `best.pt`'s
embedded epoch/metric and hashes, permits one RTX-3090 battery writer, imports
atomically, and never retries or overwrites a failed transaction.

Report schema v3 uses the `paired_response` family for the paired stochastic
detector-response residual. Its denominator is incident kinetic energy, not
truth deposited response, so exact and near-zero deposits are both stable. It
includes every validation pair and must not be described or compared as a
downstream incident-energy reconstruction metric. The controller rejects the
superseded top-level `reconstruction` family. Its data-usage block must account
separately for 10,000 validation truth events, 10,000 generated events, the
2,000-event training reference used only by memorization, and zero test events.

Fourteen inputs fail closed; nothing defaults. The evaluation split is a module
constant, not a flag — a test parses both source files and fails if the bare
split literal appears anywhere.

**Expect ~65 min per checkpoint.** Stage timings print as each family completes
and land in the report under `timing.stage_seconds`.

---

## 5. Pipeline C — unattended multi-row training

```bash
python scripts/dicos.py start "sh '<WORKDIR>/_v3/chain_queue.sh'" --name queue
```

Runs the prepared rows in sequence. It waits for the card to be free, then
**re-checks completeness after the wait** (checking only up front would restart a
row that finished while the queue was blocked), refuses to continue past a row
that stopped short of its horizon or never reached postflight, and skips
completed rows — so it is safe to re-issue after a pod restart.

**It will not decide a promotion.** Every queued row forks from B0 and measures
one declared change in isolation. Stacking a promoted feature is a separate
declared experiment and a judgment call on evidence, which a shell loop may not
make.

---

## 6. Pipeline D — keeping figures and metrics current

```bash
PYTHONPATH=src python scripts/watch_v3_outputs.py --interval-seconds 900
```

```bash
python scripts/watch_v3_outputs.py --status
python scripts/watch_v3_outputs.py --stop
```

Every pass imports new epochs, advances/imports fixed-bank batteries, rebuilds
the screening figures, summary and metrics catalog, and appends evidence to
`logs.md`. It keeps watching while any row
is **running or queued** — exiting in the gap between rows once stopped the
figures updating for a whole tranche.

**Runs on the workstation, not a pod** — the builders need matplotlib, and
writing into a pod's checkout would dirty the tree the pre-launch gate depends
on. It only updates while this machine is on.

Read-only against the pods, so it is safe beside a live trainer.

The v2.2 equivalent is `scripts/watch_campaign_outputs.py`.

---

## 7. Pipeline E — v2.2 continuation refresh

```bash
PYTHONPATH=src python scripts/refresh_continuation_outputs.py --family calibrated_lr3e4 --run-tag dicos-f-03 --run-dir _runs/calibrated_lr3e4_dicos-f-03 --expected-epoch 114 --lineage dicos-f-01 dicos-f-02 dicos-f-03
```

Add `--offline` to rebuild from local evidence without pod I/O.

**This is for v2.2 continuations only.** A v3 screening row must never go through
it: it appends to `continuation_history.csv` under a v2.2 family, which would
draw a different architecture on that family's continuous loss axis and let it
compete for that family's accepted best. A test makes the leak impossible.

---

## 8. Full QA — before claiming anything is done

```bash
$env:PYTHONPATH='src'; python -m compileall -q src vertex scripts tests exhibition; python -m pytest -q
```

**Expect 724 passed (2026-08-15).** Report the count you measure; it is not
hard-coded as a final expected value anywhere.

```bash
python exhibition/build_metrics_catalog.py
```

Expect `status PASS`, `131 graphics`, `declared_diagnostic_gap: null`.

```bash
python exhibition/build_exhibition.py
```

Public repo: `python -m unittest discover -s tests -v`, `npm ci`, `npm run
build`. Verify the Pages workflow **and** the live URL — a push is not a
deployment.

---

## 9. Measurement tools

```bash
python scripts/dicos.py exec "cd '<WORKDIR>' && LD_LIBRARY_PATH=/usr/lib64:\$LD_LIBRARY_PATH PYTHONNOUSERSITE=1 PYTHONPATH=repo/src .venv/bin/python repo/scripts/v3_d1_production_preflight.py --geometry prep/geometry_frozen --frozen-config prep/configs/frozen_calibrated_lr3e4_dicos-f-02.yaml --warmup 3 --measured 5 --repeats 1 --output audit/d1_preflight.json"
```

Escalates batch-1 smoke → critic batch 4 → generator batch 6, so an OOM names the
shape that failed. **Never reduces a declared value to obtain a pass.** Current
result: `RESOURCE_PREFLIGHT_FAIL`, 22.796 GiB against a 23.518 GiB card.

```bash
python scripts/dicos.py exec "... repo/scripts/v3_axis_performance_profile.py --geometry prep/geometry_frozen --frozen-config <cfg> --output audit/axis_profile.json"
```

---

## 10. Recording — do this as you go, not at the end

After every meaningful event: append to `logs.md`, write the `audit/NAME.{json,md}`
twin, refresh figures, and republish the dashboard and public site when a
family's lowest verified validation loss changes.

Record commands, source commit, dirty-state disposition, input/output SHA-256,
environment, GPU, job IDs, timings, costs, counterexamples, **failed attempts**,
and the decision the evidence supports. Never log private reasoning — log
evidence, alternatives, decisions and verification.

**A run whose evidence was never written down is a run that did not happen.**

Status vocabulary: `QA PASS`, `QA FINDING`, `ARTIFACT QUARANTINED`,
`FOLLOW-UP QA`, `RESOURCE PREFLIGHT FAIL`, `PHYSICS VALIDATION NOT ESTABLISHED`.
QA never grants permission to continue, change hardware, or launch.

---

## 11. What is deliberately not automated

- **Promotion decisions.** They need the battery, the guards and judgment.
- **Stacking a promoted feature.** A separate declared experiment.
- **Publication.** The owner's deliberate act.
- **Opening the test split.** Requires architecture, weights, metrics, stopping,
  seeds and checkpoint selection all frozen first.
- **Any paid cloud job.** Requires a fresh spending limit from the owner.
- **D1 training.** `resource_blocked` at 22.8 GiB on a 23.5 GiB card.

---

## 12. Where everything lives

| Path | What |
|---|---|
| `exhibition/data/v3_screening_rows.json` | declared row registry + comparator rule |
| `exhibition/data/v3_screening_history.csv` | measured per-epoch aggregate |
| `exhibition/current/v3_screening/` | figures + `screening_summary.json` |
| `exhibition/data/continuation_history.csv` | **v2.2 families only** |
| `_v3/validation_bank_10k.json` (pod) | the frozen evaluation bank |
| `_v3/battery/` (pod) | battery outputs |
| `audit/` | one JSON/MD twin per event |
| `logs.md` | the running record |
