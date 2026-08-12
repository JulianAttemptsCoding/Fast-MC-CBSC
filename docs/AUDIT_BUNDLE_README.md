# CBSC-ZDC Fast Monte Carlo — audit bundle

Prepared 2026-08-12 for external review. Please read this file first; it is
written to tell you where the weak points are, not to sell the work.

---

## 1. What this is in one paragraph

A conditional generative model that produces a sparse Zero Degree Calorimeter
shower — 6,790 readout channels across 65 layers — from a single incident
neutron four-vector. The generator is a hierarchical stochastic cascade
(visibility → total response → longitudinal profile → per-layer hit counts →
geometry-aware support selection → energy shares) with an exact decoder that
enforces exact zeros outside the selected support, exact requested hit counts,
nonnegative cell energies, exact per-layer budgets, and event-energy closure to
floating-point tolerance. Training is on 0–300 GeV incident kinetic energy; the
eventual claim domain is 50–250 GeV.

## 2. The two things to take away

**Geant4 fidelity is not established, and the evidence says so clearly.** A
classifier separates Fast-MC from Geant4 at AUROC **0.85–0.93** at every
checkpoint the project has produced, ensemble or single-model. The
predeclared acceptance gate is **≤ 0.65**. Nothing has come close, and the
steadily improving training objective has not moved it.

**The learning-rate schedule was silently broken for the entire project,
found 2026-08-12.** `CosineAnnealingLR`'s `T_max` is restored from the parent
checkpoint on every resume (`checkpoint.py:75`), and an ancestor's 6-epoch
horizon has propagated into every continuation regardless of the horizon each
config declared. The realised learning rate — read from the trainer's own
per-epoch log, not inferred — has sawtoothed 3e-4 ↔ 1e-6 on a **12-epoch
period** the whole time. Validation loss tracks that phase: within-cycle
swing ≈0.14 against a real trough-to-trough gain of ≈0.04. Every "best"
checkpoint this project has ever selected is whichever trough of that
sawtooth happened to be deepest, not a converged optimum. A corrected run
(`camp-20260812-lr3e4-anneal`, one true anneal over the full segment horizon)
is in flight; see §7 item 1 and `audit/lr_schedule_20260812_terminal_analysis.md`.
**If you read one thing in this bundle before forming an opinion on the loss
landscape or the optimizer, read that file.**

Everything else in this bundle should be read against both of these.

## 3. Current standings

Lowest verified validation loss per calibrated family, on the frozen weighted
joint objective, pilot validation split, as of this bundle:

| Family | Validation loss | Epoch | Run |
|---|---:|---:|---|
| `calibrated_lr3e4` | **4.512721** | 47 | `dicos-e-02` |
| `calibrated_lr1e4_halfbatch` | 4.619967 | 33 | `dicos-c-03` |
| `calibrated_lr1e4` | 4.635220 | 38 | `dicos-p9` |
| `calibrated_lr3e5` | 4.702203 | 36 | `dicos-c-05` |

Run-to-run resolution is about **0.02**, established by a controlled replicate
on two different GPUs. Treat smaller differences as noise.

`calibrated_lr3e4`'s 4.512721 was itself a sawtooth trough (§2) reached under
the un-corrected schedule; `dicos-f-01` is currently testing whether a real
anneal over the same or a longer horizon beats it. Treat this number as
provisional. `dicos-p10` epoch 40 is `ARTIFACT QUARANTINED` and is not a valid
parent for anything. See §7.

## 4. Where to look

| Path | What it holds |
|---|---|
| `AUDIT_README.md` | this file |
| `logs.md` | **the primary evidence record.** Chronological, includes every failed attempt |
| `audit/*.{json,md}` | machine-readable and human twins of each terminal analysis |
| `audit/lr_schedule_20260812_terminal_analysis.md` | **start here** — the LR finding in full, with the exact checkpoint state and the recorded per-epoch schedule that proves it |
| `AGENTS.md` | the binding operating contract, 28 numbered rules |
| `docs/` | data, model, evaluation, QA, backend and portability contracts |
| `docs/AGENT_PROMPT_CONTINUE_ANY_BACKEND_20260728.md` | the full self-contained handoff |
| `src/cbsc_zdc/` | all active model, data, training and evaluation code |
| `src/cbsc_zdc/training/trainer.py` | training loop, optimizer, and the `CosineAnnealingLR` / `_restart_cosine_scheduler` code at the centre of §2's finding |
| `src/cbsc_zdc/training/checkpoint.py` | checkpoint save/load, including the unconditional `scheduler_state` restore at line 75 |
| `configs/templates/` | every training config ever used, including frozen ones |
| `configs/campaigns/` | declared multi-segment campaign plans, each a self-contained scientific question with its own evidence and stop rule |
| `tests/` | executable contracts (338 passing at bundle time) |
| `exhibition/current/` | the current figure set |
| `exhibition/current/presentations/` | a slide deck summarising results |
| `external_models/classifier_c2st__Fast-MC-tester/` | the C2ST classifier study, full repo at its recorded commit |
| `external_models/four_momentum__ASIoP-ZDC-2/` | the four-momentum reconstruction model, full repo at its recorded commit |
| `live_campaign_evidence/` | the in-flight LR-correction campaign's own state, event log and per-epoch history, pulled from the training host at the instant this bundle was built |
| `MANIFEST.sha256` | SHA-256 and size of every file here |
| `GIT_PROVENANCE.md` | commit identity and recent history |

Suggested reading order: this file → `audit/lr_schedule_20260812_terminal_analysis.md`
→ `AGENTS.md` → the last ~800 lines of `logs.md` →
`src/cbsc_zdc/training/trainer.py` and `src/cbsc_zdc/models/system.py`.

## 5. What is and is not established

**Established.** Production ROOT conversion and content-addressed prepared data;
frozen detector geometry and graph; end-to-end FP32 GPU execution; checkpoint,
paired best/last, epoch and mid-epoch recovery; zero structural-invariant
failures in accepted runs; short-horizon optimization improvement for four
calibrated families; fixed-condition validation-only visual QA; a fully
unattended multi-segment campaign supervisor that has now run to completion
twice with no operator present, correctly enforcing its own declared stopping
rules both times.

**Not established.** Geant4 fidelity. Three-seed behaviour — never run.
Untouched-test performance — the split is sealed. Downstream reconstruction
fidelity — numbers exist and are 1.4–2.5× worse than a Geant4 control run
through the identical readout adapter. Diversity and memorization acceptance.
Publication-scale timing on another backend. **Whether the true learning-rate
anneal (§2) changes any of the above** — it is a declared experiment in
flight, not yet a result.

**Known concrete defects.**

- The learning-rate schedule anneal horizon has been wrong since the project's
  early continuations (§2). This is the single most actionable item in this
  bundle and is why it leads the reading order.
- Fast-MC emits roughly **twice** as many zero-response events as Geant4
  (0.015–0.023 against 0.0097).
- The ECAL layer-0 deposit is undershot by about two orders of magnitude; see
  `exhibition/current/model/10_same_condition_longitudinal_profiles.png`.
- Mean response bias in the 100–125 GeV bin sat near **+0.40** for 25
  consecutive epochs in an earlier run, far outside the ±0.05 predeclared
  band, and did not improve as the loss fell. Whether this recurs under the
  corrected schedule is untested.
- Several shower observables have the correct mean and a visibly wrong spread —
  total response is over-dispersed, hit count under-dispersed.
- The loss and the distribution metrics **disagree** about which epoch is best.
  Checkpoint selection follows the validation loss, as declared, and is not
  switched to whichever metric flatters a run.

## 6. The two evaluator model families

Neither is part of the generator. Both are **downstream, descriptive** and
neither may select or tune a checkpoint. Both are included in full under
`external_models/`, each pinned to the exact commit that produced the numbers —
the bundle build verifies that match rather than assuming it.

### Classifier two-sample tests (C2ST) — `external_models/classifier_c2st__Fast-MC-tester`

Answers "can a trained discriminator tell Geant4 from Fast-MC?". Four
architectures, of which two are controls.

**`calibrated_lr3e4`, `dicos-c-02` epoch 34** (the family's champion before the
sawtooth-trough successors `dicos-e-02`/`dicos-f-01`; no external re-evaluation
has run against those newer checkpoints yet), validation split, 1,200 events:

| Model | Input | AUROC |
|---|---|---:|
| hybrid low-level, 3-seed ensemble | hits + profile + condition | **0.8624 ± 0.0147** (0.8463–0.8751) |
| high-level GBM control | 15 shower observables | 0.894731 |
| condition-only control | four-vector alone | 0.500000 (p = 1.0) |

**`calibrated_lr1e4`, `dicos-p9` epoch 38**, validation split, 4,000 events/class:

| Model | Input | AUROC |
|---|---|---:|
| hybrid low-level, 3-seed ensemble | hits + profile + condition | 0.872656 ± 0.011687 |
| high-level GBM control | 15 shower observables | 0.929097 |
| condition-only control | four-vector alone | 0.500000 (p = 1.0) |

**Two things worth your attention.** The condition-only control sitting exactly
at chance is the sanity check that separation comes from the calorimeter
deposits and not from mismatched incident conditions. And the *high-level GBM
beats the low-level hybrid* in both evaluations, which suggests the residual
discrepancy lives in summary shower observables rather than fine per-cell
structure — the opposite of what an earlier July study found (below).

Earlier study, 2026-07-28, **test** split, 40,000 events per class, epoch-4
checkpoints: hybrid 0.99945 ± 0.00009, dense 0.99616, high-level GBM 0.98518,
condition-only 0.50363. Full write-up in
`exhibition/archive/c2st_20260728/C2ST_RESULTS.md`.

**These studies are not comparable as a single tracked quantity** — different
checkpoint, split, sample size and (for the 07-28 study) evaluator. They agree
qualitatively: a classifier separates the two generators easily, far above the
0.65 gate, at every checkpoint tested so far.

### Four-momentum reconstruction — `external_models/four_momentum__ASIoP-ZDC-2`

A reconstruction model is run over both generators through the **identical**
frozen 6,790-channel readout adapter, so the Geant4 column is the reference
floor rather than truth.

**`calibrated_lr3e4`, `dicos-c-02` epoch 34**, validation split, 4,000 events:

| Metric | Fast-MC | Geant4 control | Ratio |
|---|---:|---:|---:|
| Energy relative RMSE | 0.2156 | 0.1541 | 1.40× |
| Energy relative 68% width | 0.1535 | 0.0733 | 2.09× |
| Energy MAE (GeV) | 21.14 | 12.25 | 1.73× |
| Mean energy response | 0.9564 | 0.9941 | — |
| Relative energy bias | −4.36% | −0.59% | 7.34× |
| Angular median (mrad) | 9.51 | 8.11 | 1.17× |
| Macro RMS relative 4-vector error | 0.2942 | 0.2078 | 1.42× |

`mass_shell_residual_abs_max_gev2` is 2.5e-11 for both, so the reconstruction
is self-consistent and the degradation is a property of the generated
showers, not of the adapter.

For comparison, the same evaluation against `calibrated_lr1e4`, `dicos-p9`
epoch 38 (see `exhibition/current/external_metrics/source_data/dicos-p9/epoch_0038/four_momentum/metrics.json`
for the full record): energy relative RMSE ratio 1.62×, width68 ratio 2.52×,
MAE ratio 2.10×. **`lr3e4` at `dicos-c-02` reconstructs measurably closer to
Geant4 than `lr1e4` does** on every one of these metrics despite `lr1e4`
having had far more epochs — worth investigating whether that tracks the
learning-rate lead this family already had, or something architectural.

**Question for you:** is a factor 1.4–2.5 on reconstruction resolution the
right figure of merit for a fast simulator, and what would an acceptable
value be for this detector?

## 7. Open questions where review is most valuable

1. **Is the corrected learning-rate schedule (§2) actually the fix, and is a
   single 24-epoch anneal the right horizon, or would a shorter or longer one
   do better?** `dicos-f-01` is running now
   (`configs/campaigns/campaign_20260812_lr3e4_anneal.json`); its own
   early epochs are *expected* to be worse than 4.512721 as the schedule
   re-heats from an annealed 2.1e-5 back to 3e-4 — that is not itself
   evidence against the correction. A negative result at the end of the
   anneal would be.
2. **Is the closure tolerance correction sound?** `closure_tolerance_gev` was
   absolute while the residual it bounds is float32 rounding that scales with
   energy; at 300 GeV one ULP already exceeded the whole tolerance, and it
   killed a run on a structurally perfect epoch. It is now
   `max(2e-5, 1e-5 × total_response)`. The measurement, the reasoning and the
   replay are in `audit/closure_tolerance_20260805_terminal_analysis.md`.
   **Anything compared across that change is a new declared experiment.**
3. **Is the loss the right selection quantity** when it demonstrably disagrees
   with every distribution metric about which epoch is best, and — as of §2 —
   was itself being read at essentially random phase of a hidden 12-epoch
   cycle for most of the project's history?
4. **Would the pilot bank explain the fidelity gap?** 4.3% of the corpus is a
   large confound and nobody has tested it.
5. **Is the AUROC gate of 0.65 the right target**, and is the low-level hybrid
   the right evaluator? Note the high-level GBM control currently *beats* the
   low-level classifier in every evaluation run so far, which suggests the
   residual discrepancy lives in summary shower observables rather than fine
   per-cell structure.
6. **Is the exact decoder buying anything** that a softer constraint would not?

## 8. What is deliberately not in this bundle

- **Model checkpoints** — they live on the training host; each is ~29 MB and
  they are not needed to review the method. Hashes for every accepted checkpoint
  are recorded in `logs.md` and the handoff.
- **`exhibition/data/visualizations/`** — the raw 50-condition, 5-draws-per-condition
  sample dumps behind the structural-invariant QA gate (~13.5 MB per epoch,
  ~1.25 GB in total). This is what a checkpoint is checked *against*, not
  evidence about the loss function or architecture. The figures it produces
  (`exhibition/current/model/*.png` and similar) are derived from it and are
  included; the raw draws are not. Clone the repository if you need them.
- **The prepared corpus and the raw 25 GB ROOT file** — identity, hashes and
  entry counts are recorded; the data is not redistributable here.
- **`.git`** — clone the repository for full history. `GIT_PROVENANCE.md` has the
  commit identity and recent log.
- **Any credential.** The bundle builder refuses to produce an archive if a live
  token value appears in any staged file, and it builds from `git ls-files`
  rather than a directory walk so an untracked local secret cannot be swept in.

## 9. Verifying this bundle

```bash
python verify_bundle.py            # re-hash every file against MANIFEST.sha256
```

Standard library only, so it runs before you install anything. It should report
every file verified and nothing missing, changed, or unmanifested.

To run the code you need Python ≥ 3.10, PyTorch, NumPy and PyYAML:

```bash
pip install -e .
PYTHONPATH=src python -m pytest -q                          # expect 338 passed
PYTHONPATH=src python exhibition/build_metrics_catalog.py   # PASS
```

**This was checked by extracting the shipped archive into a clean directory and
running the suite there**, not only in the source tree — the first attempt at
the first bundle (2026-08-05) failed on arrival and that is how this practice
started.

Eight `UserWarning`s (five Transformer nested-tensor, three deprecation) are
known and harmless. `tests/test_root_fixture.py` needs `fixtures/`, which is
included.

**On the dashboard payloads.** `dashboard/public/data/*.json` holds one ~13 MB
JSON per synchronised epoch and is gitignored. Tests resolve the *accepted-best*
payload for each family per the currently **published** selection, so exactly
those four are included:

```text
dicos-p7-calibrated-lr3e4_joint_epoch_0022.json
dicos-p9-calibrated-lr1e4_joint_epoch_0038.json
dicos-p7-calibrated-lr1e4-halfbatch_joint_epoch_0021.json
dicos-r3-calibrated-lr3e5_joint_epoch_0008.json
```

**Note the mismatch with §3**: the published selection above is `dicos-p7`
for `lr3e4` (validation loss 4.597152), while §3's internal standings show
`dicos-e-02` at 4.512721. **A publication is owed and has not yet been made**
— publishing a moving number while a correction experiment is in flight is a
deliberate choice, not an oversight; see `logs.md` for the reasoning. The
figures under `exhibition/current/` already reflect the true current
standings even though the public dashboard payloads do not yet.

## 10. Status at the moment this bundle was built

The declared learning-rate correction (§2, §7.1) is training now:
`camp-20260812-lr3e4-anneal`, run tag `dicos-f-01`, resuming
`calibrated_lr3e4` from its `dicos-e-02` epoch-47 best (4.512721) with the
cosine scheduler genuinely restarted over the segment's real 24-epoch
horizon, target absolute epoch 72. Confirmed running at 96% GPU utilization
and correctly single-producer at the moment this bundle was assembled. Its
first several epochs are expected to read worse than 4.512721 before the
anneal's low-LR end is reached — see §7.1 for why that is not itself a
finding.

`GIT_PROVENANCE.md` has the exact commit this bundle was built from and the
recent commit log, including the full sequence of fixes that led to this
finding (a two-day cross-Pacific connectivity outage traced to a Windows
TCP SYN-retransmit ladder, the pod-fleet swap from 4090 to L40S mid-project,
and the campaign-supervisor race condition that first surfaced the evidence
gap this section closes).

---

*Report negative results and regressions in full. Structural correctness, a
decreasing loss, and a plausible-looking event are not Geant4 fidelity.*
