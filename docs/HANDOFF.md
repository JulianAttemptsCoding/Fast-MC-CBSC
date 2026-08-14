# Handoff — where this project actually stands

Written 2026-08-13, ahead of planned architecture and testing changes. This is
the "you are here" document. It states current results, the defects found so
far, the operations you will need, and the traps that have already cost this
project real time. It does not replace the binding contracts — `AGENTS.md`,
`docs/QA_POLICY.md`, `docs/DATA_CONTRACT.md`, `docs/IMPLEMENTATION_GUIDE.md`,
`CLAUDE.md` — it tells you which one to open and when.

---

## 1. The one-paragraph summary

Four calibrated families train a hierarchical stochastic generative model of
ZDC showers. The validation objective improves and structural invariants hold.
**Geant4 fidelity is not established.** A classifier separates Fast-MC from
Geant4 at AUROC 0.8624 and 0.8727 (seed-mean) on the only two checkpoints ever
evaluated — per-energy-bin values span the 0.77–0.92 quoted elsewhere — against
a 0.65 target never approached, and nothing in the current leading chain has
been evaluated at all. The model is **measurably overfitting** (§4), while
the per-epoch distribution metrics are too noisy at their current sample size
to say whether fidelity is improving or degrading. Treat every loss improvement
below as evidence about optimization, not about physics.

## 2. Current standings

Validation loss, lower is better. `calibrated_lr3e4` is the leading family.

| Family | Lowest observed | Epoch | Run tag | Evidence state |
|---|---|---|---|---|
| `calibrated_lr3e4` | **4.483768** | 90 | `dicos-f-02` | fully evidenced (diagnostics replayed 2026-08-13) |
| `calibrated_lr3e4` | 4.497629 | 70 | `dicos-f-01` | superseded by e90 |
| `calibrated_lr1e4_halfbatch` | 4.619967 | 33 | `dicos-c-03` | fully evidenced |
| `calibrated_lr1e4` | 4.635220 | 38 | `dicos-p9` | fully evidenced; this is what the public site serves |
| `calibrated_lr3e5` | 4.702203 | 36 | `dicos-c-05` | fully evidenced |

**A publication is owed.** The live public site still serves `dicos-p9`
(`calibrated_lr1e4`, 4.635220) while the internal best is far ahead. Publishing
is a deliberate act reserved to the owner; it has not been done and should not
be done automatically.

## 3. The learning-rate finding — the most important result so far

For its entire history this project annealed on a **12-epoch sawtooth instead
of a real schedule**, and nobody saw it because the config always declared the
horizon it intended.

`CosineAnnealingLR` is built with `T_max = updates_per_epoch * epochs`, but
`checkpoint.py` restores `scheduler_state` on every resume. `T_max` therefore
came from an ancestor — 6660 updates, a 6-epoch horizon at 1110 updates/epoch —
and every continuation inherited it. The learning rate swung 3e-4 ↔ 1e-6 on a
12-epoch period regardless of what any config said. Confirmed from the
trainer's own recorded `learning_rate` column: peaks at absolute epochs 28, 40,
52 and troughs at 34, 46 — spacing exactly 12, twice.

It also caused a **false campaign stop**: a best 7 epochs behind the latest
looked plateaued, when the run was mid-descent with the next trough due.

Corrected by declaring `restart_scheduler_on_resume: true` in
`configs/campaigns/campaign_20260812_lr3e4_anneal.json`, widening the
improvement window to 12 (≥ one full former LR period), and setting patience =
horizon. Evidence in `audit/lr_schedule_20260812_terminal_analysis.{json,md}`.

**Result: 4.512721 → 4.483768, an improvement of 0.028953.** Run-to-run
nondeterminism measured from two runs sharing a checkpoint and a matched LR is
~0.0007, so the improvement is 20–40× the noise floor. It is real, and it is
single-seed — three-seed behaviour remains unestablished.

**It then converged.** Two independent 24-epoch continuations from epoch 90
both failed to beat it. Do not expect more from this configuration; the next
gain has to come from elsewhere.

## 4. It is overfitting; whether fidelity degrades is NOT established

### The training set is being fitted ~6x faster than the model generalizes

Over the live lineage, epochs 48–114, n=67:

| Series | Pearson r vs epoch | t | Verdict |
|---|---|---|---|
| train loss | −0.805 | 10.93 | falling, p<0.001 |
| validation loss | −0.358 | 3.09 | falling, p<0.05 |
| **train↔val gap** | **+0.560** | **5.46** | **widening, p<0.001** |

Train loss improved **0.13436**, validation only **0.02324** — a **5.8x** ratio.
The gap drifted **+0.04131** between halves: early epochs sit at −0.037 mean
(validation below train), later at +0.004 (validation above). That is the
overfitting signature, and it is statistically strong.

For scale: the total validation gain across all 67 epochs (0.023) is *smaller*
than the one-off gain from fixing the learning-rate schedule (0.029).

### A retracted claim, kept here so it is not re-derived

An earlier version of this document, `logs.md`, and
`audit/lr_anneal_result_20260813_terminal_analysis.*` stated that "the loss
improved while the physics got worse", from `dicos-e-02` e54 against
`dicos-f-02` e78. **That is withdrawn.** It was two points out of a series whose
adjacent epochs swing 0.36–0.75 on the same metric. Tested across the complete
diagnosed lineage, epochs 48–90, n=43, where t>2.02 is uncorrected p<0.05:

| Metric | r vs epoch | t | significant? | r vs validation loss |
|---|---|---|---|---|
| total response | −0.003 | 0.02 | no | +0.262 (aligned) |
| longitudinal L1 | +0.213 | 1.40 | no | −0.003 |
| ECAL fraction | +0.316 | **2.13** | marginal | −0.376 (misaligned) |
| radial RMS | +0.253 | 1.68 | no | −0.125 |
| hit count | −0.041 | 0.26 | no | +0.018 |

One metric of five crosses the uncorrected threshold, barely. That is what five
simultaneous tests at p<0.05 produce by chance about a quarter of the time, and
a Bonferroni correction for five comparisons needs t≈2.70 — which nothing
reaches. Per-epoch scatter is 16–43%. At 4,000 events per epoch these
diagnostics **cannot resolve a fidelity trend in either direction.** Raising the
event count is the prerequisite for answering the question at all.

The accepted best is not a fidelity outlier in the bad direction: at epoch 90 it
beats the lineage median on four of the five metrics (total response 0.524 vs
0.545, longitudinal L1 0.196 vs 0.205, radial RMS 4.384 vs 4.496, hit count
61.3 vs 70.5) and loses only on ECAL fraction (0.054 vs 0.049).

### AUROC has never been measured on any of this

The classifier two-sample test exists for exactly two checkpoints, both epoch
≤38, and **nothing in the f-chain (48–114) has been evaluated**:

| Checkpoint | Validation loss | AUROC | high-level AUROC | energy rel. RMSE | angular median |
|---|---|---|---|---|---|
| `dicos-c-02` e34 (lr3e4) | 4.550331 | 0.8624 ± 0.0147 | 0.8947 | 0.2156 | 9.51 mrad |
| `dicos-p9` e38 (lr1e4) | 4.635220 | 0.8727 ± 0.0117 | 0.9291 | 0.2494 | 15.56 mrad |

Within that pair the better loss carried the better AUROC, but they are
different families and two points prove nothing. Whether the 4.550 → 4.484
improvement moved AUROC is **unmeasured**. Both sit far above the 0.65 target.

### What this means for loss-function work

The honest statement is *overfitting is established, misalignment is not*.
Do not start from "the loss is wrong" — start from measuring whether it is.
Two standing rules constrain the work: checkpoint selection follows the
validation loss **as declared** and does not switch to whichever metric
flatters a run, and any changed loss is a **new declared experiment**
(`AGENTS.md` 28). Never wrap an NLL component in `abs`/L2 to force
nonnegativity — a negative NLL is legitimate and more negative is better.

## 5. Defects found, and their status

| Defect | Status |
|---|---|
| LR sawtooth from restored `T_max` (§3) | fixed, declared, evidenced |
| `parent_last_epoch` taken from the segment's own best row while `best.pt` was an inherited checkpoint | fixed 2026-08-13 |
| `family_for_run_tags` returned the first family holding *any* tag, and `dicos-p6`/`dicos-p7` are shared across families | fixed 2026-08-13 |
| `advance_external_metrics` crashed with `FileNotFoundError` when the accepted best had no diagnostics | fixed 2026-08-13, now reports and declines |
| Diagnostics gap, epochs 79–114 | recoverable; replay in progress, see §6 |

### The `parent_last_epoch` defect, because it will bite again

A segment that never beats the best it inherited leaves `best.pt` untouched.
Its own lowest-loss row then names an epoch **no staged artifact corresponds
to**. `dicos-f-03` reported best epoch 111 while its `best.pt` was still
`dicos-f-02`'s epoch 90, so `dicos-f-04` resumed from epoch 90, re-ran epochs
91–114 that already existed, and — because `epochs_absolute` was computed from
111 — annealed over a **46-epoch horizon instead of the declared 24**. Cost:
5.8 GPU-hours and one undeclared LR schedule.

The epoch now comes from the checkpoint being staged, via `checkpoint_epoch()`.
`staged_best_is_inherited()` in `src/cbsc_zdc/training/campaign.py` detects the
condition and the supervisor journals `segment_kept_inherited_best` when it
happens. `dicos-f-04` is excluded from the live lineage as an undeclared
variant and retained as evidence.

## 6. Known evidence gap — mostly closed

Training and diagnostics run on **separate pods**. The RTX 3090 diagnostics pod
ended between epochs 78 and 79 on 2026-08-12 while the L40S kept training to
114, so epochs 79–114 had loss, LR and structural-invariant evidence but no
distribution metrics — including epoch 90, the accepted best.

Every queued checkpoint survived. On 2026-08-13 a replacement 3090 replayed
`_diag/dicos-f-02/queue`, which **closed epochs 79–90 and measured the accepted
best**. Diagnostics are now continuous from epoch 23 to 90.

**What remains:** epochs 91–114 (`dicos-f-03`). Its 24 checkpoints are still
queued in `_diag/dicos-f-03/queue`. The replay was stopped there because those
epochs did not improve on epoch 90 and the owner asked for compute to stop, so
the remaining gap does not touch checkpoint selection — it only prevents the
distribution-metric trend being extended past 90.

Two mechanisms carry that remainder, and both should be **removed once
`dicos-f-03`'s queue is drained**:

- `exhibition/data/diagnostic_gaps.json` — declares the range and its reason.
  `build_metrics_catalog.py` still fails on any *undeclared* gap; a declaration
  makes it visible, it does not excuse it.
- `exhibition/data/continuation_status.json` — marks epochs 91–114
  `unmeasured`, which keeps them out of accepted-best selection so the
  published payload can never point at an epoch with no diagnostics.
  `unmeasured` means exactly that; it is not `quarantined`, which means a
  failure.

**AUROC for epoch 90 is staged but not computed.** The external-metric state
records `dicos-f-02 e90 status=pending_offline`. Running it is the single
highest-value next measurement, because it is the only way to learn whether the
4.550 → 4.484 improvement moved the classifier at all.

## 7. Operations

Every command assumes `PYTHONPATH=src`. On PowerShell: `$env:PYTHONPATH='src'`.

### Verify the repository

```bash
python -m compileall -q src vertex scripts tests
python -m pytest -q
python exhibition/build_exhibition.py
python exhibition/build_metrics_catalog.py
python exhibition/build_all_metric_trends.py
```

### Bring up pods after they expire

Pods are compute only — the shared filesystem persists, so an expired pod loses
no evidence. Only the port changes; the token has been stable per user.

```bash
python scripts/dicos.py auth "<URL>"                                  # 4090, primary
DICOS_CONFIG=~/.dicos/config_3090.json python scripts/dicos.py auth "<URL>"
```

Never run `dicos.py setup` on a second pod — it rebuilds the shared `.venv` out
from under whatever is training. Per-pod venvs already exist: `.venv` (primary)
and `.venv_3090` (diagnostics).

### Run diagnostics

```bash
DICOS_CONFIG=~/.dicos/config_3090.json python scripts/dicos.py start \
  'cd "<WORKDIR>" && PYTHONNOUSERSITE=1 PYTHONPATH=repo/src .venv_3090/bin/python \
   repo/scripts/dicos_diagnostics.py --n-events 4000 --selection-seed 20260803 \
   --watch-root _diag --device cuda' --name campdiag
```

`--watch-root _diag` follows every run tag, including ones that appear later.
It skips epochs that already hold a valid metric, so it is safe to re-run.

### Refresh the local record

```bash
python scripts/refresh_campaign_outputs.py --plan configs/campaigns/<plan>.json
```

Per-segment, when the campaign's own derivation is not what you want:

```bash
python scripts/refresh_continuation_outputs.py \
  --family <family> --run-tag <tag> --run-dir _runs/<family>_<tag> \
  --expected-epoch <epoch with diagnostics> \
  --lineage <tag> <tag:MAX_EPOCH> ...
```

- `TAG:MAX_EPOCH` caps a superseded tag at its fork point. Required whenever a
  later segment forked from an epoch earlier than the parent's last.
- `--offline` rebuilds from local evidence with no pod I/O.
- `--no-diagnostics` imports loss evidence while the diagnostics pod is down.
  The 3090-only guard stays intact for pulls that do happen.

### Duplicate or non-contiguous epochs in the history

Both guards are correct and mean a fork was not accounted for. Resolve with the
campaign's own recorded fork points, never by hand-deleting rows:

```python
from refresh_campaign_outputs import fork_points, prune_superseded_rows
prune_superseded_rows(Path("exhibition/data/continuation_history.csv"),
                      fork_points(plan, events))
```

## 8. Traps that have already cost time

- **`origin/main` is a cached ref.** `git fetch` first, or a pushed pod commit
  looks like 19 unpushed commits. The pod is a full clone that commits and
  pushes; the workstation can legitimately be behind.
- **One writer per run directory.** A log's START count and the pid file cannot
  tell one wrapper from two. Check the process tree before any `start`.
- **A process probe must not match itself.** Build the search token at runtime
  and exclude your own pid *and* your parent shell. A literal token matches the
  probe's own `/proc` entry — that produced a phantom trainer, and the `kill -9`
  that followed killed the probe. The 3090 image has no `ps`; scan `/proc` from
  that pod's venv interpreter.
- **Never move or delete a run directory while a process holds it.** Paths
  resolve per write, so the live process starts writing wherever the path now
  points.
- **Never resume from a checkpoint quarantined by an invariant failure**, and
  never auto-resume a visualization-gate death: RNG is restored and the visual
  bank is fixed, so it re-runs the identical epochs and re-hits the identical
  failure forever.
- **`git checkout -- .` will revert your own uncommitted source fixes** along
  with generated output. Scope the pathspec explicitly.
- **Windows Git Bash mangles `/usr/lib64`** into `C:/Program Files/Git/usr/lib64`
  when passed inline to a remote exec.
- **CRLF corrupts JSON evidence.** `.gitattributes` forces `eol=lf` for
  evidence paths; an already-indexed file may need a direct
  `git cat-file -p HEAD:<path>` byte-write.

## 9. What is and is not established

**Established:** production conversion; frozen geometry and graph; FP32 GPU
execution; checkpoint/recovery; zero structural-invariant failures in accepted
runs; short-horizon optimization improvement for four calibrated families;
fixed-condition validation-only visual QA; a public site.

**Not established:** Geant4 fidelity; three-seed behaviour; untouched-test
performance; downstream reconstruction; diversity/memorization acceptance;
publication-scale timing on another backend.

Quantitatively, and this must travel with any favourable loss number: **C2ST
AUROC 0.77–0.92 at every checkpoint measured**, never approaching the 0.65
threshold, and unmoved by the improving objective. Fast-MC emits roughly
**twice** as many zero-response events as Geant4 (0.015–0.023 vs 0.0097).

**The test split is sealed.** It may not inform preprocessing, thresholds,
architecture, loss weights, LR, stopping, checkpoint selection, or
visualization.

## 10. Before changing architecture or testing

1. Read `AGENTS.md` — particularly rule 28, declared experiments.
2. Anything that changes the loss, the architecture, or a threshold is a new
   declared experiment with its own frozen config and recorded hashes. Never
   hand-edit a frozen config; edit a template or builder, regenerate, freeze
   through the CLI, record both hashes.
3. Never weaken a diagnostic threshold or an assertion to make a run pass. If a
   check has become wrong about the world, make it express the real invariant
   and declare the change with evidence — that is what `diagnostic_gaps.json`
   does, and it still fails on anything undeclared.
4. Keep `docs/GPU_BENCHMARKS.md` as the single source of truth for throughput
   and cost; it supersedes every figure in `logs.md`.
5. Append to `logs.md` as you go, with an `audit/NAME.{json,md}` twin. A run
   whose evidence was never written down is a run that did not happen.

## 11. CBSC-ZDC v3 — Stage A is implemented, no campaign is authorized

Added 2026-08-14. The v3 handoff (`docs/improvement_v3/`,
`specs/improvement_v3/`) is installed and verified: both archives matched their
declared SHA-256, the member scan was clean, nothing was overwritten, and
**all 11 audited base-file hashes match this repository exactly**.

### What exists now

Units 1–15 of the specification are implemented and unit-tested; the suite went
from 350 to 521 tests. `scripts/verify_v3_run.py --mode software` reports
`status: pass` — 16 modules importable, 17 test files present, 16 declared
constants at their contract values, the v2.2 loss schema unchanged, and the
exact sampler still carrying its `no_grad` decorator.

Two pieces carry most of the value:

- **The bounded response spline removes the second zero atom.** Visibility is
  now the only source of zeros; the positive branch is strictly inside
  `(0, C(K))` with no clamp, so it can never clear a visible event the way the
  v2.2 mixture-plus-clamp did.
- **The stage samplers avoid the discrete bottleneck rather than relaxing it.**
  `sample_exact` is untouched. D1 truth-forces `V,T,f,A,D,k,S` and trains only
  the share flow; D2 truth-forces `V,T,A` and trains only the profile flow.

### What is measured

On the live **RTX 4090 (23.52 GiB)** at production shape, declared critic batch
4, 20 warm-up plus 100 synchronized updates, three repeats:

| path | s/update | peak GiB |
|---|---:|---:|
| v3 supervised generator | 0.01772 | 0.07 |
| D1 critic update | 0.15237 | **14.85** |
| D1 generator through frozen critic | 0.21659 | 13.27 |
| D2 critic update | 0.01540 | 0.10 |
| D2 generator through frozen critic | 0.02145 | 0.09 |

**D1 fits at the declared batch size**, using 63% of the card. Nothing was
reduced to achieve that.

**Resume is bit-exact**: 32 updates, checkpointed at 16 and resumed, maximum
absolute generator-parameter difference **0.0** against a 1e-6 gate, with
critic, optimizer, controller and replay state and both hashes verified.

### What it would cost

Re-costed from measurement in
`specs/improvement_v3/executable_plan_20260814.csv`. The supplied
`experiment_matrix.csv` is unmodified.

| row family | each | note |
|---|---:|---|
| S1–S7 pilot | 5.2 h | all eleven for about 57 h — genuinely affordable |
| `V3-SUP`, `C0` | 107.6 h | `C0` is the required no-critic control |
| D2 arms | 141.5 h | |
| D1 arms | 446.6 h | 2.9× a D2 arm |
| **full matrix** | **6,038.6 h** | about 252 days on one card |

This **supersedes the 2,930.88 h figure** in `V3_PLAN_ASSESSMENT.md`, which was
arithmetically correct but extrapolated pilot supervised throughput to the
critic paths.

### The cheapest causally interpretable tranche

`C0` plus one D2 arm is **249 h (~10.4 days)** and yields a controlled result,
because `C0` is trained on the identical 551,234-event partition. The eleven
pilot S-rows at 57 h total are cheaper still and are the natural first spend.

### What is NOT done

1. The new heads are unit-tested but **not wired into `trainer.py`'s epoch
   loop**. That wiring is required before any S-row can run.
2. Units 16 (D3 estimator-QA harness) and 17 (optional p4 interface) are not
   implemented — both are triggered-only or disabled by default.
3. D1 was measured with critic batch 4 for the generator as well; a generator
   batch of 6 alongside a D1 critic is unmeasured.
4. `B0` is `B0_CANDIDATE_NOT_FROZEN` at 8 of 9 gate items. The only blocker is
   external validation metrics for `dicos-f-02` e90, which Stage B supplies.

No training campaign was launched, no paid compute was used, and the test split
was not opened. `PHYSICS VALIDATION NOT ESTABLISHED`.
