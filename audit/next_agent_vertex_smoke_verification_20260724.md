# Independent re-verification of the FP32 Vertex structural smoke, and next-phase proposal

Verification run date: 2026-07-25
Working directory: `C:\Users\Julia\OneDrive\Desktop\coding\ASIoP\Fast MC CBSC`
Scope: read-only reproduction of the existing successful smoke's verification, plus
a proposed (not submitted) plan for the next train/validation-only Vertex phase.
No preparation, coordinator, smoke, or final-training job was submitted. Test data
was not opened. `legacy/` was not read or trained from. No frozen config was
hand-edited.

Companion machine-readable file: `audit/next_agent_vertex_smoke_verification_20260724.json`
Independent preparation re-verification artifact: `audit/next_agent_verified_prepare_r5.json`

## QA summary

```text
structural_smoke=QA_PASS
validation_only_component_loss_lr_work=FOLLOW_UP_QA
physics_validation=NOT_ESTABLISHED
final_training=NOT_RUN_USER_DECISION
```

## 1. Local code verification (step 4)

```text
PYTHONPATH=src python -m pytest -q  -> 25 passed, 2 warnings (documented Transformer
                                        nested-tensor performance warnings, nonfatal)
python -m compileall -q src vertex tests -> exit 0
```

Matches the required historical "exactly 25 passing tests" QA check.

## 2. Independent preparation re-verification (step 5)

`gcloud ai custom-jobs describe 1981826012068970496` confirms `JOB_STATE_SUCCEEDED`,
display name `cbsc-v2-2-full-root-prep-20260724-r5`, exact root URI/generation/size/
CRC32C arguments, output prefix `prep-20260724-r5`, and the correct service account.

`python vertex/verify_prepare_output.py` was re-run against
`gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/prep-20260724-r5` with the pinned
identity values and reproduced, byte-for-byte against the prompt's required values:

```text
pass=true
entries=764940
n_nodes=6790
n_layers=65
n_shards=187
verified_shards=187
geometry_hash=e22d4cfb1e9293a33dd13151587910268ba64cd8efbcdb7a835a7442f2edcb4b
ganged_channel_count=2400
max_physical_positions_per_channel=4
event_total_residual_max_gev=1.3500311979441904e-13
modeled_readout_residual_max_gev=1.1368683772161603e-13
full split=612482 train / 76158 validation / 76300 test
pilot assignments=338 train / 104 validation / 0 test / 764498 excluded
pilot selected=338 train / 64 validation / 0 test
```

Output written to `audit/next_agent_verified_prepare_r5.json`.

## 3. Smoke job description (step 6, read-only)

`gcloud ai custom-jobs describe 4964365651620659200` confirms, independently:

```text
state=JOB_STATE_SUCCEEDED
scheduling.strategy=ON_DEMAND
machineType=n1-standard-8
acceleratorType=NVIDIA_TESLA_T4, acceleratorCount=1
replicaCount=1
bootDiskType=pd-ssd, bootDiskSizeGb=100
imageUri=...cbsc-zdc@sha256:45ff337d8c4b1b34e936a24926a8fa495aebfb06187e75965fab9624d1f402f1
input-prefix=gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/prep-20260724-r5-fp32-r2
output-prefix=gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/smoke-20260724-r2-fp32
config-relative=configs/frozen_production_full_architecture_smoke_fp32.yaml
device=cuda (one CUDA device request)
serviceAccount=39719277374-compute@developer.gserviceaccount.com
```

The exact PowerShell assertion block from the handoff prompt was executed
programmatically against the live job spec and printed `ALL ASSERTIONS PASSED`.
No job was submitted; this was a `describe` call only.

## 4. Artifact listing, download, and hashing (step 7)

`gcloud storage ls -l -r` on the smoke output prefix returned exactly 16 objects,
58,800,504 bytes total, and no `vertex_failure.json`. A local copy already existed
at `audit/vertex_smoke_fp32_r2` (from the prior agent's session) containing exactly
the same 16 required files. Every file was independently re-hashed with SHA-256;
**all 16 hashes and sizes matched** `output_artifacts.sha256` in
`audit/agent_vertex_smoke_analysis_20260724.json` exactly. Zero mismatches.

## 5. Independent report analysis (step 8)

Every field below was read directly from the downloaded, hash-verified report
files (not copied from the prior agent's summary) and matches the prompt's
required accepted values exactly:

```text
environment.json:      cuda_available=true, cuda_device_count=1,
                        cuda_device_name=Tesla T4,
                        total_memory_bytes=15655829504
reports/smoke_resources.json:
                        pass=true, peak_memory_bytes=7848525312,
                        headroom_fraction=0.49868352168789687
reports/preflight.json:
                        pass=true, verified_shards=187,
                        selected 338/64/0
logs/history.csv (epoch 0):
                        stage=joint, updates=84 (training_summary.json),
                        train_loss=24.04530804497855,
                        validation_loss=20.07763433456421,
                        seconds=57.4816040180001,
                        examples_per_second=5.880142104144429
reports/invariant_epoch_0000.json (epoch candidate):
                        pass=true, layer_closure_max_gev=4.76837158203125e-07,
                        event_closure_max_gev=9.5367431640625e-07
reports/smoke_invariants.json (postflight fixed conditions):
                        pass=true, layer_closure_max_gev=4.76837158203125e-07,
                        event_closure_max_gev=2.384185791015625e-07
reports/smoke_timing.json:
                        device=cuda:0, batch_size=2, profile_steps=1,
                        share_steps=1, iterations=2,
                        milliseconds_per_event=99.04152249998788
```

All nonfinite/negative/invalid-support/support-mask/count/requested-realized/dust
failure counts are 0 in every one of the three invariant reports (epoch candidate,
postflight fixed-condition, and validation).

**Checkpoint reload evidence:** `vertex_result.json.smoke_postflight.pass=true`.
The postflight path in the training container constructs a *fresh* model instance,
loads `checkpoints/best.pt` from disk, then samples five fixed conditions
`[0, 50, 150, 250, 300]` GeV, runs the invariant QA, benchmarks solver+decode
timing, and evaluates the validation split — all of which passed. A corrupted or
non-round-trippable checkpoint would have failed this path. Combined with the
independent SHA-256 match on `checkpoints/best.pt` and `checkpoints/last.pt`
against the frozen record, this proves the checkpoint save/reload contract.

## 6. Scientific boundary — recorded, not hidden (step 9)

From `reports/smoke_validation.json`, independently read:

```text
validation events=64
high_level_c2st_auc=1.0
truth_zero_fraction=0.015625
generated_zero_fraction=0.296875
response_wasserstein_normalized=0.4034199118614197
hit_count_wasserstein_normalized=1.0333642292132128
```

Additional distributional evidence in the same report (not required by the
prompt, but independently observed and included for completeness): the
generated depth centroid, ECAL fraction, radial RMS, and late-energy fraction
are all far from truth after one epoch on 338 training events — e.g. truth ECAL
fraction 0.245 vs. generated 0.00003, truth depth centroid layer 12.4 vs.
generated 31.6.

**This smoke passed software, target-hardware, checkpoint, resource, and
structural gates only. It did not validate Geant4 fidelity.** These values are
one-epoch, 338-train-event diagnostics and must not be used to tune, weaken, or
otherwise inform any acceptance gate. The timing measurement
(99.04152249998788 ms/event, 1 profile step, 1 share step, batch 2, 2
iterations) is a one-step solver/decode connectivity smoke, not the required
final 8-profile-step/8-share-step production performance benchmark.

## 7. Every preserved failed gate (step 10)

| id | resource | gate that failed | outcome / correction |
|---|---|---|---|
| prep-r1 | customJobs/5551984247922753536 | geometry position consistency | cell (1,1,2) varied 46.9354 mm peak-to-peak; exposed legitimate ganged HCAL readouts; corrected by freezing the unweighted centroid of distinct stable physical centers, never hit-frequency-weighted |
| prep-r2/r3 | customJobs/3440077497662701568, 2318329346726559744 | conversion execution | native SIGSEGV localized to structured-NumPy HCAL mapping; corrected with plain `uint64` grouped search |
| prep-r4 | customJobs/8852770931064438784 | event accounting | entry-0 residual 0.0194756 GeV from omitted sentinel deposits; corrected to two separate strict closures (all-hits vs. `energySum_ZDC`, mapped-nodes vs. non-sentinel readout) |
| coordinator-r1 | customJobs/9206444239301378048 | pilot count verification | verifier incorrectly rejected the legitimate `excluded=764498` count before smoke submission; corrected to require all four exact counts; no T4 was submitted |
| t4-smoke-amp | pipeline 7972253432239095808 / customJobs/5080522458025426944 | finite gradient, epoch 0 step 0 | finite forward loss, nonfinite AMP gradient norm; no update/checkpoint accepted; corrected via a new unfrozen template (`training.amp: false` only), refrozen under a new hash and prefix — no frozen YAML was hand-edited |
| fp32-staging-flatten | prefix `prep-20260724-r5-fp32` | directory hierarchy | wildcard `gcloud storage cp` flattened shard hierarchy; corrected with `gcloud storage rsync --recursive` into `prep-20260724-r5-fp32-r2` |

All six failed prefixes/jobs remain preserved and were not deleted, reused, or
overwritten by this verification run.

## 8. Structural smoke vs. physics validation — explicit separation

- **Structural smoke (GO):** software chain, target-hardware CUDA execution,
  checkpoint save/reload, resource headroom, and every structural invariant
  (nonnegativity, exact support, exact count, exact layer/event closure) passed
  on the full production-derived geometry and preparation artifacts.
- **Physics validation (NOT_ESTABLISHED):** one epoch on 338 pilot training
  events with default loss weights and an untuned learning rate is not a trained
  model. C2ST AUC of 1.0 and the large truth/generated distributional gaps are
  the expected signature of an undertrained pilot, not evidence about the
  architecture's eventual fidelity ceiling. No claim of Geant4 fidelity is made
  or implied by this smoke.

---

# Proposed next phase (plan only — NOT submitted, requires explicit authorization)

This section is a concrete proposal for review. **No job below has been
submitted.** It follows `docs/IMPLEMENTATION_GUIDE.md` §§13–16, `AGENTS.md`, and
`docs/VERTEX_QA_GATE_PLAN_20260724.md` gates G18–G19. It uses train and
validation splits only; test remains closed.

## Ground rules carried into every job in this matrix

- One on-demand `NVIDIA_TESLA_T4`, `n1-standard-8`, one replica, `ON_DEMAND`
  scheduling, `pd-ssd` boot disk. No Spot, no CPU fallback, no multi-GPU.
- Reuse the existing immutable image digest
  `sha256:45ff337d8c4b1b34e936a24926a8fa495aebfb06187e75965fab9624d1f402f1`
  unless a code change is required, in which case a new Cloud Build image is
  produced and its new digest is recorded before submission — the digest is
  never mutated in place.
- Every job starts from a **new unfrozen template** (never edit
  `configs/frozen_production_full_architecture_smoke_fp32.yaml` or any other
  already-frozen config), frozen normally with `cbsc-zdc freeze-config`, and
  submitted under a **new, empty, generation-0-locked GCS prefix**
  (checked with `gcloud storage ls` returning nothing before submission).
- Input data prefix for all stage/calibration/LR jobs is the verified full
  preparation prefix `gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/prep-20260724-r5`
  (764,940 events, 187 shards, geometry hash
  `e22d4cfb1e9293a33dd13151587910268ba64cd8efbcdb7a835a7442f2edcb4b`), using
  `splits.json` (train/validation only — test indices are never read into any
  container argument or manifest for this phase).
- Every job stops immediately on schema/geometry/hash/invariant/nonfinite/
  negative-energy/empty-bin/split-leakage/CUDA-fallback/checkpoint/memory-
  headroom/artifact failure, per `AGENTS.md` rule 5. A stopped job's prefix is
  preserved, never deleted or reused.
- Three final seeds and the six final matched runs are explicitly **out of
  scope** for this phase; nothing here freezes final gates or launches final
  training.

## Proposed job matrix

| # | Purpose | Stage order gate | Template (new, unfrozen) | Data | Predecessor checkpoint | New GCS prefix | Epochs/batches | QA gate before advancing |
|---|---|---|---|---|---|---|---|---|
| 1 | Component diagnostic: response | 1/6 | `configs/templates/stage_response.yaml` → frozen as `configs/frozen_stage_response_seed20260723.yaml` | train (full 612,482) + validation (76,158) | none; `train_condition_encoder: true` | `gs://.../cbsc-v2-2/stage-20260725-r1-response` | per template (30 epochs, early stop patience 8) | G14 per-epoch invariant pass; encoder trained |
| 2 | Component diagnostic: profile | 2/6 | `stage_profile.yaml` | same | `stage-20260725-r1-response/checkpoints/best.pt`; encoder frozen | `gs://.../cbsc-v2-2/stage-20260725-r1-profile` | per template | G14 pass; predecessor-checkpoint contract enforced |
| 3 | Component diagnostic: count | 3/6 | `stage_count.yaml` | same | `stage-20260725-r1-profile/checkpoints/best.pt`; encoder frozen | `gs://.../cbsc-v2-2/stage-20260725-r1-count` | per template | G14 pass |
| 4 | Component diagnostic: support | 4/6 | `stage_support.yaml` | same | `stage-20260725-r1-count/checkpoints/best.pt`; encoder frozen | `gs://.../cbsc-v2-2/stage-20260725-r1-support` | per template | G14 pass |
| 5 | Component diagnostic: share | 5/6 | `stage_share.yaml` | same | `stage-20260725-r1-support/checkpoints/best.pt`; encoder frozen | `gs://.../cbsc-v2-2/stage-20260725-r1-share` | per template | G14 pass |
| 6 | Component diagnostic: joint | 6/6 | `stage_joint.yaml` | same | `stage-20260725-r1-share/checkpoints/best.pt`; full model unfrozen | `gs://.../cbsc-v2-2/stage-20260725-r1-joint` | per template | G14 pass; this checkpoint feeds calibration |
| 7 | Train-only gradient-norm loss calibration | after §14 | `cbsc-zdc calibrate-loss-weights --config <frozen joint-pilot config> --checkpoint stage-20260725-r1-joint/checkpoints/best.pt --max-batches 64 --clip-min 0.25 --clip-max 4.0 --device cuda` | **train only**, ≤64 batches | joint-stage checkpoint from #6 | `gs://.../cbsc-v2-2/calib-20260725-r1-loss-weights` | ≤64 batches, no epoch | median gradient norms recorded; proposed weights clipped to [0.25,4.0], mean-normalized to 1; not yet frozen |
| 8 | Copy calibrated weights into a new unfrozen template, freeze, short confirmation run | — | new template with only `loss_weights.*` changed from calibration output | train + validation | joint checkpoint from #6 | `gs://.../cbsc-v2-2/calib-20260725-r1-confirm` | short (e.g. 2–3 epochs) | G14 pass; confirms calibrated weights do not break finite-loss/finite-gradient gate |
| 9 | Validation-only LR / weight-decay / effective-batch sensitivity | guide §16.3 | grid over `{3e-5, 1e-4, 3e-4} × {0, 1e-3, 1e-2}` LR/WD, plus one effective-batch control, one seed, minimum-credible epoch count | train (fit) / **validation (select)** | joint checkpoint from #6 (or #8 if calibration confirmed) | `gs://.../cbsc-v2-2/pilot-20260725-r1-lr-wd-batch` | short pilot runs, one seed each | selection uses validation loss/physics metrics only; test never opened; decisions logged with rationale |
| 10 | Truth-half statistical-floor study at full validation scale | guide §19 | evaluation-only pass using `cbsc-zdc evaluate --split validation` over the **full 76,158-event validation split** (not the 64-event pilot subset) | **validation only** | best available checkpoint (post-LR-pilot) | `gs://.../cbsc-v2-2/pilot-20260725-r1-truth-half-floor` | evaluation only, no training | establishes a credible truth-vs-truth Wasserstein/C2ST floor per the `truth_half_floor` block already present in `smoke_validation.json`, at full statistical scale instead of the 64-event pilot |
| 11 | Full-validation evaluation memory/streaming pilot | required by `audit/vertex_readiness_analysis_20260724.md` and `VERTEX_QA_GATE_PLAN` open item | same evaluation command as #10, run with GPU memory instrumentation (`smoke_resources.json`-style headroom capture) over all 76,158 validation events | **validation only** | same checkpoint as #10 | `gs://.../cbsc-v2-2/pilot-20260725-r1-full-validation-memory` | ≥15% headroom maintained across the full evaluation pass, no CPU fallback, no OOM; if it fails, batch/streaming must change via a new template — never by weakening the 15% gate |

## What this phase explicitly does NOT do

- Does not submit any of the six final matched-seed runs (3× 0–300 GeV, 3×
  50–250 GeV).
- Does not open the test split (76,300 events) for any purpose.
- Does not freeze final acceptance gates, final loss weights, or final
  optimizer settings — items 7–11 above only produce evidence and proposed
  values for a human/agent decision, per guide §13 step 6 ("freeze the
  proposed weights") and §16.3 ("use a minimum-credible subset ... after
  choosing, freeze").
- Does not hand-edit any existing frozen config.
- Does not reuse or overwrite any prior GCS prefix, including the six failed
  ones in the table above or the successful `prep-20260724-r5` /
  `smoke-20260724-r2-fp32` prefixes.

## Authorization required

Per the operating instructions, this plan is presented for review only. Explicit
authorization is required before submitting jobs #1–11 above.
