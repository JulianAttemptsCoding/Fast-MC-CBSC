# CBSC-ZDC Fast Monte Carlo — audit bundle

Prepared 2026-08-05 for external review. Please read this file first; it is
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

## 2. The one thing to take away

**Geant4 fidelity is not established, and the evidence says so clearly.**

A classifier separates Fast-MC from Geant4 at AUROC **0.77–0.92** at every
checkpoint the project has ever produced. The predeclared acceptance gate is
**≤ 0.65**. Nothing has come close, and the steadily improving training
objective has not moved it. The honest summary is: the optimization works, and
it has not yet bought fidelity.

Everything else in this bundle should be read against that.

## 3. Current standings

Lowest verified validation loss per calibrated family, on the frozen weighted
joint objective, pilot validation split:

| Family | Validation loss | Epoch | Run |
|---|---:|---:|---|
| `calibrated_lr3e4` | 4.597152 | 22 | `dicos-p7` |
| `calibrated_lr1e4` | 4.635220 | 38 | `dicos-p9` |
| `calibrated_lr1e4_halfbatch` | 4.673036 | 21 | `dicos-p7` |
| `calibrated_lr3e5` | 4.843471 | 8 | `dicos-r3` |

Run-to-run resolution is about **0.02**, established by a controlled replicate
on two different GPUs. Treat smaller differences as noise. The `lr3e4` lead over
`lr1e4` is 0.038 — real, but not commanding, and `lr1e4` has had 39 epochs
against `lr3e4`'s 23.

`dicos-p10` epoch 40 is `ARTIFACT QUARANTINED` and is not a valid parent for
anything. See §7.

## 4. Where to look

| Path | What it holds |
|---|---|
| `AUDIT_README.md` | this file |
| `logs.md` | **the primary evidence record.** Chronological, ~7,900 lines, includes every failed attempt |
| `audit/*.{json,md}` | machine-readable and human twins of each terminal analysis |
| `AGENTS.md` | the binding operating contract, 28 numbered rules |
| `docs/` | data, model, evaluation, QA, backend and portability contracts |
| `docs/AGENT_PROMPT_CONTINUE_ANY_BACKEND_20260728.md` | the full self-contained handoff; §7b0 is current state |
| `src/cbsc_zdc/` | all active model, data, training and evaluation code |
| `configs/templates/` | every training config ever used, including frozen ones |
| `tests/` | 294 executable contracts |
| `exhibition/current/` | the current figure set, 66 graphics |
| `exhibition/current/presentations/` | a 17-slide status deck summarising results |
| `external_models/classifier_c2st__Fast-MC-tester/` | the C2ST classifier study, full repo at its recorded commit |
| `external_models/four_momentum__ASIoP-ZDC-2/` | the four-momentum reconstruction model, full repo at its recorded commit |
| `live_campaign_evidence/` | state of the run that was in flight when this was built |
| `MANIFEST.sha256` | SHA-256 and size of every file here |
| `GIT_PROVENANCE.md` | commit identity and recent history |

Suggested reading order: this file → `AGENTS.md` → the last ~600 lines of
`logs.md` → `audit/closure_tolerance_20260805_terminal_analysis.md` →
`src/cbsc_zdc/training/trainer.py` and `src/cbsc_zdc/models/system.py`.

## 5. What is and is not established

**Established.** Production ROOT conversion and content-addressed prepared data;
frozen detector geometry and graph; end-to-end FP32 GPU execution; checkpoint,
paired best/last, epoch and mid-epoch recovery; zero structural-invariant
failures in accepted runs; short-horizon optimization improvement for four
calibrated families; fixed-condition validation-only visual QA.

**Not established.** Geant4 fidelity. Three-seed behaviour — never run.
Untouched-test performance — the split is sealed. Downstream reconstruction
fidelity — first numbers exist and are 1.6–2.5× worse than a Geant4 control run
through the identical readout adapter. Diversity and memorization acceptance.
Publication-scale timing on another backend.

**Known concrete defects.**

- Fast-MC emits roughly **twice** as many zero-response events as Geant4
  (0.015–0.023 against 0.0097).
- The ECAL layer-0 deposit is undershot by about two orders of magnitude; see
  `exhibition/current/model/10_same_condition_longitudinal_profiles.png`.
- Mean response bias in the 100–125 GeV bin sits near **+0.40** for 25
  consecutive epochs, far outside the ±0.05 predeclared band, and does not
  improve as the loss falls.
- Several shower observables have the correct mean and a visibly wrong spread —
  total response is over-dispersed, hit count under-dispersed.
- The loss and the distribution metrics **disagree** about which epoch is best.
  Checkpoint selection follows the validation loss, as declared, and is not
  switched to whichever metric flatters a run.

## 5b. The two evaluator model families

Neither is part of the generator. Both are **downstream, descriptive** and
neither may select or tune a checkpoint. Both are included in full under
`external_models/`, each pinned to the exact commit that produced the numbers —
the bundle build verifies that match rather than assuming it.

### Classifier two-sample tests (C2ST) — `external_models/classifier_c2st__Fast-MC-tester`

Answers "can a trained discriminator tell Geant4 from Fast-MC?". Four
architectures, of which two are controls.

Current monitor, validation split, `dicos-p9` epoch 38, 4,000 events per class:

| Model | Input | AUROC |
|---|---|---:|
| hybrid low-level, 3-seed ensemble | hits + profile + condition | **0.872656 ± 0.011687** |
| high-level GBM control | 15 shower observables | 0.929097 |
| condition-only control | four-vector alone | 0.500000 (p = 1.0) |

Per-seed values 0.867275, 0.864628, 0.886064; ensemble accuracy 0.7525 ± 0.0055.

**Two things worth your attention.** The condition-only control sitting exactly
at chance is the sanity check that separation comes from the calorimeter
deposits and not from mismatched incident conditions. And the *high-level GBM
beats the low-level hybrid* here, which suggests the residual discrepancy lives
in summary shower observables rather than fine per-cell structure — the opposite
of what the July study found.

Earlier study, 2026-07-28, **test** split, 40,000 events per class, epoch-4
checkpoints: hybrid 0.99945 ± 0.00009, dense 0.99616, high-level GBM 0.98518,
condition-only 0.50363. Full write-up in
`exhibition/archive/c2st_20260728/C2ST_RESULTS.md`.

**These two studies are not comparable as a single tracked quantity** — different
split, sample size, evaluator and checkpoint. They agree qualitatively: a
classifier separates the two generators easily, far above the 0.65 gate.

### Four-momentum reconstruction — `external_models/four_momentum__ASIoP-ZDC-2`

A reconstruction model is run over both generators through the **identical**
frozen 6,790-channel readout adapter, so the Geant4 column is the reference
floor rather than truth. This is the first downstream fidelity evidence the
project has.

| Metric | Fast-MC | Geant4 control | Ratio |
|---|---:|---:|---:|
| Energy relative RMSE | 0.2494 | 0.1541 | 1.62× |
| Energy relative 68% width | 0.1849 | 0.0733 | 2.52× |
| Energy MAE (GeV) | 25.70 | 12.25 | 2.10× |
| Mean energy response | 0.9490 | 0.9941 | — |
| Relative energy bias | −5.10% | −0.59% | 8.58× |
| Angular median (mrad) | 15.56 | 8.11 | 1.92× |
| Macro RMS relative 4-vector error | 0.3466 | 0.2078 | 1.67× |

Per energy bin, Fast-MC energy RMSE runs 0.399 at 50–75 GeV down to 0.195 at
225–250 GeV; the control runs 0.280 down to 0.137. Both improve with energy, as
expected for a sampling calorimeter, and the gap never closes.

`mass_shell_residual_abs_max_gev2` is 2.5e-11, so the reconstruction is
self-consistent and the degradation is a property of the generated showers, not
of the adapter.

**Question for you:** is a factor 1.6–2.5 on reconstruction resolution the right
figure of merit for a fast simulator, and what would an acceptable value be for
this detector?

## 6. Data provenance and the test split

The corpus is 764,940 events, split 612,482 train / 76,158 validation /
76,300 test. All training here used a bounded pilot bank of **26,624 train /
6,656 validation**, which is **4.3%** of available training data and is the
largest untested lever in the project.

**The test split has never informed preprocessing, thresholds, architecture,
loss weights, learning rate, stopping, checkpoint selection, or visualization.**

Two disclosed read-only exceptions exist, neither feeding any modelling
decision:

1. An external C2ST study exercised 40,000 test events under a one-way isolation
   contract (separate repository).
2. On 2026-07-30, a 2,000-event draw from the full corpus included **200 sealed
   test events (10.0%)**, at the project owner's explicit instruction after being
   warned twice. They appear in six archived figures under
   `exhibition/archive/paired_diagnostics_20260730/`.

**The untouched remainder is therefore between 36,100 and 36,300, not exactly
known**, because the overlap between those two selections was never computed.
Any publication depending on that number should compute it first.

## 7. Open questions where review is most valuable

1. **Is the closure tolerance correction sound?** `closure_tolerance_gev` was
   absolute while the residual it bounds is float32 rounding that scales with
   energy; at 300 GeV one ULP already exceeded the whole tolerance, and it killed
   a run on a structurally perfect epoch. It is now
   `max(2e-5, 1e-5 × total_response)`. The measurement, the reasoning and the
   replay are in `audit/closure_tolerance_20260805_terminal_analysis.md`. The
   relative term was chosen as 12× the measured float32 noise ceiling and ~150×
   below a single mis-decoded cell. **Anything compared across that change is a
   new declared experiment.**
2. **Is the loss the right selection quantity** when it demonstrably disagrees
   with every distribution metric about which epoch is best?
3. **Would the pilot bank explain the fidelity gap?** 4.3% of the corpus is a
   large confound and nobody has tested it.
4. **Is the AUROC gate of 0.65 the right target**, and is the low-level hybrid
   the right evaluator? Note the high-level GBM control currently *beats* the
   low-level classifier (0.929 against 0.873), which suggests the residual
   discrepancy lives in summary shower observables rather than fine per-cell
   structure.
5. **Is the exact decoder buying anything** that a softer constraint would not?

## 8. What is deliberately not in this bundle

- **Model checkpoints** — they live on the training host; each is ~29 MB and
  they are not needed to review the method. Hashes for every accepted checkpoint
  are recorded in `logs.md` and the handoff.
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
PYTHONPATH=src python -m pytest -q                          # expect 294 passed
PYTHONPATH=src python exhibition/build_metrics_catalog.py   # 119 graphics, PASS
```

**This was checked by extracting the shipped archive into a clean directory and
running the suite there**, not only in the source tree — the first two attempts
failed on arrival and that is how it was caught.

Eight `UserWarning`s (five Transformer nested-tensor, three deprecation) are
known and harmless. `tests/test_root_fixture.py` needs `fixtures/`, which is
included.

**On the dashboard payloads.** `dashboard/public/data/*.json` holds one ~13 MB
JSON per synchronised epoch, about 870 MB in total, and is gitignored. Four
tests resolve the *accepted-best* payload for each family, so exactly those four
are included:

```text
dicos-p7-calibrated-lr3e4_joint_epoch_0022.json
dicos-p9-calibrated-lr1e4_joint_epoch_0038.json
dicos-p7-calibrated-lr1e4-halfbatch_joint_epoch_0021.json
dicos-r3-calibrated-lr3e5_joint_epoch_0008.json
```

The other 46 epochs the dashboard manifest references are not here. That means
`dashboard/` will not serve its full cross-epoch history from this bundle; the
figures under `exhibition/current/` already summarise what those payloads show.

## 10. Status at the moment this bundle was built

A campaign was training. `calibrated_lr3e4` was being continued over absolute
epochs 23–42, resuming from its own epoch-22 best with the cosine continued
rather than restarted. Epochs 23, 24 and 25 came in at 4.600282, 4.641767 and
4.652393 — all *above* the 4.597152 parent best, which is the expected shape
while the resumed cosine climbs back from an annealed 1e-6 toward peak before it
can improve. It is not yet evidence in either direction.

See `live_campaign_evidence/` for the campaign's own state file and event log.

---

*Report negative results and regressions in full. Structural correctness, a
decreasing loss, and a plausible-looking event are not Geant4 fidelity.*
