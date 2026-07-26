# Vertex execution handoff

This is operational evidence, not a physics-validation claim. Read
`docs/IMPLEMENTATION_GUIDE.md`, `AGENTS.md`, and
`docs/VERTEX_QA_GATE_PLAN_20260724.md` before running a command.

## Current terminal state

The full production preparation and FP32 target-hardware smoke are complete.
Do not submit another preparation, coordinator, or smoke job.

```text
project: asiop-zdc-1
project number: 39719277374
region: us-central1
service account: 39719277374-compute@developer.gserviceaccount.com

preparation job:
  projects/39719277374/locations/us-central1/customJobs/1981826012068970496
preparation state:
  JOB_STATE_SUCCEEDED
verified preparation prefix:
  gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/prep-20260724-r5

FP32 training pipeline:
  projects/39719277374/locations/us-central1/trainingPipelines/5105571531929419776
FP32 custom job:
  projects/39719277374/locations/us-central1/customJobs/4964365651620659200
FP32 state:
  JOB_STATE_SUCCEEDED
FP32 input:
  gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/prep-20260724-r5-fp32-r2
FP32 output:
  gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/smoke-20260724-r2-fp32
FP32 image:
  us-central1-docker.pkg.dev/asiop-zdc-1/cbsc-zdc/cbsc-zdc@sha256:45ff337d8c4b1b34e936a24926a8fa495aebfb06187e75965fab9624d1f402f1
FP32 frozen config SHA-256:
  e75f1bda7140a00b9caf04bf9ee574c034879e7a935dfe32a42a983680511f31
```

The exact resource specification is one `n1-standard-8` worker, one
`NVIDIA_TESLA_T4`, one replica, `ON_DEMAND`, 100 GB `pd-ssd`, and a six-hour
timeout. Spot, low-cost, another accelerator, multiple GPUs, and CPU fallback
remain forbidden.

## Immutable source

```text
URI:
  gs://asiop-zdc-1-zdc-reco-us-central1/data/myTree_20251117_765k_0to300GeV_neutron_All.root
generation:
  1783683550292251
size:
  25022001408
CRC32C:
  lCVUvQ==
SHA-256:
  b7c666040e42352e158a9a3f78158d147cb2e056c6c88248d892c956f5c7b533
tree / entries:
  myTree / 764940
```

Independent preparation verification is in `audit/verified_prepare_r5.json`.
It passed all 764,940 events, all 187 shards, strict 6,790-node/65-layer
geometry, both event-energy closure contracts, deterministic splits, train-only
audits, and the zero-test pilot selection.

## Reproduce the independent read-only verification

Run from the repository root in PowerShell:

```powershell
$env:PYTHONPATH = (Resolve-Path -LiteralPath 'src').Path
python -m pytest -q
python -m compileall -q src vertex tests

gcloud ai custom-jobs describe 4964365651620659200 `
  --project asiop-zdc-1 `
  --region us-central1 `
  --format=json

gcloud storage ls -l -r `
  'gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/smoke-20260724-r2-fp32/**'
```

Require 25 passing tests, only the two documented Transformer warnings,
successful compilation, `JOB_STATE_SUCCEEDED`, and the exact job specification
above.

The smoke output has already been downloaded to:

```text
audit/vertex_smoke_fp32_r2
```

If it is missing, create the destination and copy the existing output. Do not
submit a job:

```powershell
$target = Join-Path (Get-Location) 'audit\vertex_smoke_fp32_r2'
if (-not (Test-Path -LiteralPath $target)) {
  New-Item -ItemType Directory -Path $target | Out-Null
  gcloud storage cp --recursive `
    gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/smoke-20260724-r2-fp32/* `
    $target
}
```

Require exactly these 16 output objects and no `vertex_failure.json`:

```text
checkpoints/best.pt
checkpoints/last.pt
environment.json
logs/history.csv
reports/invariant_epoch_0000.json
reports/preflight.json
reports/smoke_invariants.json
reports/smoke_resources.json
reports/smoke_samples.npz
reports/smoke_timing.json
reports/smoke_validation.json
reports/training_summary.json
resolved_config.json
runtime_config.yaml
staged_input_manifest.json
vertex_result.json
```

Compare their SHA-256 values to
`audit/agent_vertex_smoke_analysis_20260724.json`. Stop on any mismatch.

## Accepted measured result

```text
CUDA devices:
  1
device:
  Tesla T4
PyTorch / CUDA / cuDNN:
  2.6.0+cu124 / 12.4 / 90100
T4 total memory:
  15655829504 bytes
peak allocated:
  7848525312 bytes
headroom:
  0.49868352168789687

train / validation / test selected:
  338 / 64 / 0
epoch:
  0 (one completed epoch)
updates:
  84
train loss:
  24.04530804497855
validation loss:
  20.07763433456421
epoch seconds:
  57.4816040180001
examples/second:
  5.880142104144429

epoch invariant maximum layer / event closure:
  4.76837158203125e-07 / 9.5367431640625e-07 GeV
postflight maximum layer / event closure:
  4.76837158203125e-07 / 2.384185791015625e-07 GeV
all structural failure counts:
  0

short postflight timing:
  batch 2, profile steps 1, share steps 1, 2 iterations
  99.04152249998788 ms/event
```

The postflight path constructed a fresh model, loaded `best.pt`, sampled fixed
conditions `[0, 50, 150, 250, 300]` GeV, ran invariants, benchmarked solver plus
decode, and evaluated validation only. This proves checkpoint reload.

The timing is a short connectivity check. It is not the required final
8-profile-step/8-share-step performance benchmark.

## Scientific boundary

The structural smoke passed, but one epoch is visibly not physics-valid:

```text
high-level C2ST AUC:
  1.0
truth / generated zero fraction:
  0.015625 / 0.296875
normalized response Wasserstein:
  0.4034199118614197
normalized hit-count Wasserstein:
  1.0333642292132128
```

Do not use those values to weaken or tune an acceptance gate. They document why
structural success must not be confused with Geant4 fidelity.

## Preserved failed gates

All failed prefixes and jobs remain evidence:

1. Preparation r1 (`5551984247922753536`) exposed ganged HCAL positions.
2. Preparation r2/r3 (`3440077497662701568`,
   `2318329346726559744`) exposed the structured-NumPy native crash.
3. Preparation r4 (`8852770931064438784`) exposed the sentinel accounting
   mismatch.
4. Coordinator r1 (`9206444239301378048`) rejected the legitimate pilot
   `excluded` count before submitting a smoke.
5. First T4 custom job (`5080522458025426944`, pipeline
   `7972253432239095808`) failed the finite-gradient gate under AMP at step 0.
6. `prep-20260724-r5-fp32` is an unusable flattened staging prefix.

The AMP failure was corrected without editing a frozen config: only
`training.amp` changed in a new unfrozen template, which was frozen under a new
hash and run under new prefixes.

## Next permitted phase

The next agent may independently verify this handoff, then work only with train
and validation data:

1. Run component diagnostics in exact order
   `response -> profile -> count -> support -> share -> joint`.
2. Obey the shared-encoder rules: response trains it; intermediate components
   initialize from the required predecessor and keep it frozen; joint unfreezes.
3. Run train-only gradient-norm calibration for at most 64 batches.
4. Run validation-only loss sensitivity and LR/weight-decay/effective-batch
   studies.
5. Run truth-half gate-floor and full-validation memory pilots.
6. Freeze gates, loss weights, optimizer choices, and three final seeds only
   after those studies.

Do not open test, submit a final run, omit a failed gate, change raw-deposit
semantics, weaken a baseline, or call this smoke physics validation.

The exact copy/paste next-agent instructions are in
`docs/AGENT_PROMPT_VERTEX_RUN_AND_ANALYZE.md`.
