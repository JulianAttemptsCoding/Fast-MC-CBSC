# Walk-away runbook — what is running, and what to do when you come back

Rewritten 2026-08-15. This is the "I ignored this for a few days, what now" page.
It assumes nothing except that you can run `python scripts/dicos.py`.

---

## 1. What is running right now

Three jobs across two cards. None of them needs you.

| Job | Pod | What it is | Expected |
|---|---|---|---|
| `queue2` | RTX 4090 | **S2-response** running, **S3-first** queued behind it | ~12 h each |
| `battery5` | RTX 3090 | Validation battery on B0, `dicos-f-03` e111 and S1 e19 | ~3–4 h |
| `watch_v3_outputs` | workstation | Imports epochs and rebuilds figures every 15 min | continuous |

**M0-fresh is complete.** Best 4.513572 at epoch 19. It resolved the S1 causal
question: the axis feature is neutral, and S1's shortfall was the fresh
optimizer. See `docs/V3_FULL_REPORT.md`.

Everything writes only under the permitted project directory. Nothing touches
the test split. No paid cloud compute is involved.

**The queue refuses to continue past a row that stopped short of its horizon or
never reached postflight.** A tranche that silently continues past a failed row
produces results nobody can attribute. It also skips rows already complete, so
it is safe to re-issue after a pod restart.

**Read every screening row against M0-fresh at 4.513572, not against B0 at
4.483768.** Every row uses `initialize_from`, which transfers weights but not
optimizer state, and that fresh Adam costs a measured **0.021601**. Comparing a
row to B0 charges its feature for the optimizer restart.

## 2. The single command to check on things

```bash
python scripts/v3_status.py
```

Figures and metrics update themselves while the watcher runs:

```bash
python scripts/watch_v3_outputs.py --status
```

Manual equivalents, if that script is unavailable:

```bash
python scripts/dicos.py jobs
python scripts/dicos.py exec "tail -3 '_runs/v3_M0_fresh/logs/history.csv'"
python scripts/dicos.py logs queue2
```

```bash
MSYS_NO_PATHCONV=1 DICOS_CONFIG="C:/Users/Julia/.dicos/config_3090.json" python scripts/dicos.py logs battery5
```

## 3. What "good" looks like

**M0-fresh.** Epoch 0 measured **4.660598**, against S1's 4.665888 — the
expected re-heat signature, because both start from B0's weights through a
migration verified as a behavioural no-op and then train one epoch at the fresh
cosine's 2.99e-4 peak. The pointer is confirmed good.

Its rate is **1733.7 s/epoch**, essentially identical to S1's 1735.8 despite
carrying **zero** axis information — an independent confirmation that the 2.23x
gap against `dicos-f-02`'s 779.6 is not the axis feature. Note the 3090 battery
was reading the same shared filesystem throughout, so this run's *timing*
carries that confound; its loss does not.

**If a row that migrates as a behavioural no-op starts anywhere near 5.2,
suspect the `initialize_from` pointer.** That number is what S1's first,
discarded launch produced when it trained from random weights.

**But this heuristic does NOT apply to a row that replaces a head.** S2-response
legitimately began at **5.064650**: the bounded spline replaces the response head
outright, so 15 of its tensors are freshly initialized and the response NLL --
one of the largest weighted terms -- starts untrained. A high epoch 0 is expected
there. Check `initialize_from`, its sha256 and the preflight before concluding
anything: S2's were all correct.

The rule that always holds: read the migration report. `expanded 0, unexpected 0`
with a nonzero `initialized` count means a head was replaced on purpose.

**S2-response.** Same initialization signature. Its migration report should read
`copied 193, expanded 0, initialized 15, unexpected 0` — `expanded 0` is correct
and expected, because S2 adds no axis columns.

**The battery.** Three JSON files under `_v3/battery/`. Each records
`test_events_used: 0`, all twelve metric families, and 1,000 bootstrap
replicates at 95%.

## 4. What each result means

### M0-fresh — read it against two numbers

| M0 lands near | Reading |
|---|---|
| **4.491971** (`dicos-f-03`) | the fresh optimizer explains most of S1's shortfall; the axis feature is close to neutral |
| **4.514053** (S1) | the optimizer is the dominant term and the axis feature is not the story |
| **4.483768** (B0) | both the optimizer and the axis feature cost something |

M0 holds architecture, parameter count, input width, seed, data order, bank,
batch, accumulation, schedule, solver steps, update count and stopping rule
identical to S1. The only difference is that S1 feeds computed incident-axis
values where M0 feeds zeros. Because the axis input is identically zero, its
weight block receives zero gradient and stays zero all run, so M0 is
mathematically a v2.2 model with a fresh optimizer while keeping S1's exact
parameter count.

**Whatever it says, record it.** A negative result is a result, and the
promotion rule retains the simpler parent when an improvement is unresolved.

### S2-response

Its declared targets are the **zero-cause decomposition** and the
**positive-response distribution**. The battery reports the zero rate split into
the visibility hurdle and the positive branch, which is exactly the second zero
atom the bounded spline exists to remove.

S2 is justified as a **structural repair, not an AUROC fix**: the zero-only
AUROC bound is `0.5 + |p_fast − p_truth|/2` = at most **0.507**, against a
measured 0.843. Do not expect it to move the classifier much.

## 5. When a row finishes

```bash
# 1. import the evidence (hash-verified against the pod)
PYTHONPATH=src python scripts/import_v3_screening_run.py --row M0-fresh \
  --report audit/v3_M0_import_20260815.json

# 2. rebuild the screening figures and summary
PYTHONPATH=src python exhibition/build_v3_screening_figure.py

# 3. full QA
PYTHONPATH=src python -m pytest -q
python exhibition/build_metrics_catalog.py     # expect status PASS
```

Then set the row's `status` to `complete` and write its `disposition` in
`exhibition/data/v3_screening_rows.json`. A test enforces that only a completed
row may claim a disposition, and that an unpromoted one states its reason.

**Screening rows never enter `exhibition/data/continuation_history.csv`.** That
file is the four v2.2 learning-rate families on one continuous loss axis; a
screening row changes the architecture and is *initialized from* rather than
*resumed from* its parent. A test makes the leak impossible.

## 6. If something has gone wrong

**A job died.** Every row is checkpoint/resume capable. Re-issue the same start
command; the trainer resumes from its last checkpoint. **Before re-issuing,
prove there is no live writer** — a log that looks empty is not proof, and
starting a second writer on one run directory has cost this project real time:

```bash
python scripts/dicos.py exec "PYTHONNOUSERSITE=1 .venv/bin/python -c \"
import glob,os
tok='dicos_'+'train'
print([int(c.split('/')[2]) for c in glob.glob('/proc/[0-9]*/cmdline')
       if tok in open(c,'rb').read().decode('utf8','ignore')
       and int(c.split('/')[2]) not in (os.getpid(),os.getppid())])\""
```

**The pod expired.** Re-auth with the new URL. Do **not** run `setup` on the
diagnostics pod — it rebuilds the shared venv out from under whatever is
training.

**GPU shows 0% but a PID is alive.** Preflight hashes every shard before the
first epoch and can take several minutes with no output at all. Normal.

**`dicos.py stop` returned but the GPU is still busy.** Known: `stop` kills the
wrapper and leaves its children. Scan `/proc` and SIGTERM them explicitly.

**Stopping a chained script needs the shell killed FIRST.** `battery5` and
`queue2` run several steps in sequence. Killing only the current child lets the
shell start the next one, which on 2026-08-15 left two evaluations running that
would have collided on one output path. Kill the parent shell, then its current
child, then confirm nothing matching remains.

**Git Bash mangles `/usr/lib64`.** Prefix with `MSYS_NO_PATHCONV=1`, and note
that this also disables `~` expansion, so pass `DICOS_CONFIG` as an explicit
`C:/Users/...` path. The `/usr/lib64` prefix is required on the training pod or
every CUDA call fails with `cudaErrorSystemDriverMismatch` (803).

**The 3090 has no `git`.** Both pods mount the same `repo/`, so pull from the
4090 side.

## 7. What is deliberately NOT running

- **D1.** `RESOURCE_PREFLIGHT_FAIL`, measured 2026-08-15 on the real
  107,920-edge production graph: the critic update at batch 4 peaks at
  **22.796 GiB** and OOMs with 4.69 MiB free on a 23.518 GiB card. **D1 is
  `resource_blocked`; do not plan D1 training on this card.** The earlier
  14.85 GiB figure came from a synthetic 40,740-edge graph and is superseded.
  The one remaining implementation-equivalent lever is activation checkpointing,
  which must prove 1e-6 forward equivalence and float32-tolerance gradient
  equivalence.
- **D2.** Independently eligible — its memory path is distinct and does not
  touch the edge set — but it is a separate multi-day budget decision and only
  becomes *preferred* once the battery shows profile or correlation
  discrepancies are leading.
- **S3-first, R1-data4x.** Prepared and costed in
  `audit/v3_prepared_tranche_20260815.json`, not launched. S3's parent rule: if
  S2 promotes, S3 forks from S2; if not, S3 is an isolated B0/M0 row. A failed
  feature is never stacked just because the matrix listed a chain.
- **Any full-data or FINAL row, the three-seed protocol, opening the test
  split, publication.**

## 8. Standing corrections worth remembering

- **The axis features do not cost 2.23×.** Profiled at production shape they
  cost ~1% (support 1.0015, share 1.0099, full sample 1.0055). S1's
  1735.8 s/epoch is real but **unattributed**; do not cost any row from it.
- **The 0.65 gate names high-level C2ST**, where B0 reads **0.892897** — not the
  hybrid 0.843222. The claim that the learning-rate correction nearly cleared
  D1's 0.02 gate is **withdrawn**; that delta was hybrid and D1's rule names
  low-level.
- **The 8,000-example external battery is below the frozen 10,000 minimum.**
  Directional evidence only; it may not pass or fail the 0.65 diagnostic or
  select a row. The new fixed bank is 10,000 pairs = 20,000 examples.

## 9. Status vocabulary

`QA PASS` on the software. `FOLLOW-UP QA` on M0, S2 and the battery until they
complete. `RESOURCE PREFLIGHT FAIL` on D1. `D3_TRIGGER_NOT_MET`.
`S1_CONFIGURATION_NOT_PROMOTED` and `S1_AXIS_CAUSAL_EFFECT_UNRESOLVED`.

**`PHYSICS VALIDATION NOT ESTABLISHED`** — unchanged. A classifier separates
Fast-MC from Geant4 at high-level AUROC 0.892897 against a 0.65 target, and
nothing currently running changes that.
