# Walk-away runbook — what is running, and what to do when you come back

Written 2026-08-14. This is the "I ignored this for a few days, what now" page.
It assumes nothing except that you can run `python scripts/dicos.py`.

---

## 1. What is running right now

Two independent jobs, one per GPU. Neither needs you.

| Job | Pod | What it is | Expected duration |
|---|---|---|---|
| `v3s1` | RTX 4090 (training) | **S1-axis**: the first v3 screening row, 24 epochs on the pilot bank | **~11.5 h** |
| `campdiag` | RTX 3090 (diagnostics) | Draining `_diag/dicos-f-03/queue`, 24 checkpoints, closing the declared 91–114 gap | ~3 h |

Both write only under the permitted project directory. Neither touches the test
split. No paid cloud compute is involved.

## 2. The single command to check on things

```bash
python scripts/v3_status.py
```

It prints, for both pods: GPU utilization, live writer PIDs, the newest epoch and
loss for every active run, the diagnostics queue depth, and whether anything has
died. If that script is unavailable, the manual equivalents are in §6.

## 3. What "good" looks like

**S1-axis.** Epoch 0 came in at **4.665888**, which is the right shape: the run
starts from B0's weights (4.483768) through a migration verified as a
behavioural no-op, then trains one epoch at the fresh cosine's peak learning
rate of 2.99e-4, which moves a converged model away from its optimum before the
anneal brings it back. For comparison `dicos-f-01`'s equivalent re-heat epoch
was 4.6115.

This number is the initialization check. The first launch of S1 read **5.204838**
because `initialize_from` was unset and it trained from random weights; that run
was discarded. If a future row starts anywhere near 5.2, suspect the
initialization pointer before believing anything about the feature.

**Measured cost: 1735.8 s/epoch**, so 24 epochs was about 12.3 h, against the
v2.2 rate of 779.6 s/epoch (34.15 vs 15.4 examples/s).

**The causal attribution once written here is WITHDRAWN.** It said the axis
features cause that factor, because they add four columns across 6,790 nodes on
a 107,920-edge graph. Profiled on the production graph 2026-08-15
(`audit/v3_axis_performance_profile_20260815.json`), that is false:

    support field forward   with axis / without axis   1.0015
    share field forward                                1.0099
    full sample                                        1.0055
    axis construction                                  0.00023 s per batch

Roughly **1%**, not 2.23x. `axis_for()` is also already hoisted — computed once
per batch before the share-flow loop and reused across every solver step — so
there is no caching win available either.

The 2.23x epoch-rate difference is **real but unattributed**. It is not the axis
feature's forward cost. Until a full training-step comparison including backward
is run, do not cost any row from S1's rate. The consequent **115 GPU-hour**
projection for the eleven pilot rows is withdrawn with it; the rows in
`audit/v3_prepared_tranche_20260815.json` are projected from the v2.2 rate and
carry a first-epoch cost checkpoint.

The question S1 answers: *do incident-axis node coordinates lower the validation
loss?* Anything better than 4.483768 at the end is a candidate improvement;
anything worse is a real negative result and must be reported as one.

**Diagnostics.** `_diag/dicos-f-03/queue` should shrink toward zero and
`metrics_epoch_*.json` should grow toward 24.

## 4. What to do when S1 finishes

```bash
# 1. pull the evidence and rebuild everything
PYTHONPATH=src python scripts/refresh_continuation_outputs.py --offline \
  --family calibrated_lr3e4 --run-tag v3-S1-axis \
  --run-dir "_runs/v3_S1_axis" --expected-epoch <last epoch>

# 2. full QA
PYTHONPATH=src python -m pytest -q                 # expect 555 passed
python exhibition/build_metrics_catalog.py         # expect status PASS
```

Then decide the row: keep S1 if it beat 4.483768, otherwise retain the simpler
parent. Either way, record the result — **a negative result is a result**, and
the promotion rule is "retain the simpler parent when an improvement is
statistically unresolved."

To start the next row (S2 adds the bounded response spline):

```bash
python scripts/dicos.py exec "cd '<workdir>' && LD_LIBRARY_PATH=/usr/lib64:\$LD_LIBRARY_PATH \
  PYTHONNOUSERSITE=1 PYTHONPATH=repo/src .venv/bin/python \
  repo/scripts/build_v3_screening_configs.py \
  --parent prep/configs/frozen_calibrated_lr3e4_dicos-f-02.yaml \
  --envelope _v3/envelope_pilot_full.json --output-dir _v3/templates \
  --only S2-response --horizon 24"
```

then `v3_prepare_screening_run.py` with `--parent-checkpoint` set to S1's best,
then launch exactly as S1 was launched.

## 5. If something has gone wrong

**A job died.** Both are checkpoint/resume capable. Re-issue the same `start`
command; the trainer picks up from its last checkpoint. **Before re-issuing,
prove there is no live writer** (§6) — a log that looks empty is not proof, and
starting a second writer on one run directory has cost this project real time.

**The pod expired.** Re-auth with the new URL, then `setup` is *not* needed on
the diagnostics pod — it would rebuild the shared venv out from under the
trainer. Only re-auth.

**The GPU shows 0% but a PID is alive.** Preflight hashes every shard before the
first epoch and can take several minutes with no output at all. That is normal.

**`dicos.py stop` returned but the GPU is still busy.** Known: `stop` kills the
wrapper and leaves its children. Scan `/proc` and SIGTERM them explicitly (§6).

**Git Bash mangles `/usr/lib64`.** It rewrites POSIX paths before they reach the
pod. Prefix the command with `MSYS_NO_PATHCONV=1`, and note that this also
disables `~` expansion, so pass `DICOS_CONFIG` as an explicit
`C:/Users/...` path.

## 6. Manual checks, if the status script is unavailable

```bash
# training pod
python scripts/dicos.py exec "nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader"
python scripts/dicos.py exec "tail -5 _runs/v3_S1_axis/logs/history.csv"

# diagnostics pod
MSYS_NO_PATHCONV=1 DICOS_CONFIG="C:/Users/Julia/.dicos/config_3090.json" \
  python scripts/dicos.py exec "ls _diag/dicos-f-03/queue/*.pt | wc -l"
```

One-writer proof — the probe must not match itself, so the token is built at
runtime and the probe excludes its own PID and its parent:

```bash
python scripts/dicos.py exec "PYTHONNOUSERSITE=1 .venv/bin/python -c \"
import glob,os
tok='dicos_'+'train'
print([int(c.split('/')[2]) for c in glob.glob('/proc/[0-9]*/cmdline')
       if tok in open(c,'rb').read().decode('utf8','ignore')
       and int(c.split('/')[2]) not in (os.getpid(),os.getppid())])\""
```

## 7. What is deliberately NOT running

- **D1 and D2 critic arms.** Measured at 446.6 h and 141.5 h each. They need
  their own budget decision, and D1's memory must be re-measured first: the
  preflight used a synthetic graph with 40,740 edges while the production
  geometry has **107,920**, so the 14.85 GiB figure is an underestimate.
- **Any full-data or FINAL row.** Not authorized, and the test split stays sealed.
- **Publication.** Still owed, still the owner's deliberate act.

## 8. Status vocabulary

`QA PASS` on the software. `FOLLOW-UP QA` on S1 until it completes.
**`PHYSICS VALIDATION NOT ESTABLISHED`** — unchanged. A classifier still
separates Fast-MC from Geant4 at AUROC 0.843 against a 0.65 target, and nothing
currently running changes that.
