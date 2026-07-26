# Exact copy/paste prompt for the next Vertex agent

Copy everything below the separator verbatim into the new agent.

---

You are the next execution and independent QA agent for CBSC-ZDC v2.2. Work
only in:

`C:\Users\Julia\OneDrive\Desktop\coding\ASIoP\Fast MC CBSC`

The production-data-derived FP32 Vertex structural smoke has already completed
successfully. Your first objective is to independently reproduce its read-only
verification and analyze its artifacts. Your second objective is to make an
evidence-backed plan for the next train/validation-only Vertex phase. Do not
submit another preparation, coordinator, or smoke job. Do not launch final
training and do not open test data.

Follow this sequence exactly.

1. Before any command, read these files completely, in this order:

```text
docs/IMPLEMENTATION_GUIDE.md
AGENTS.md
docs/VERTEX_QA_GATE_PLAN_20260724.md
docs/VERTEX_EXECUTION_HANDOFF_20260724.md
audit/vertex_readiness_analysis_20260724.md
audit/agent_vertex_smoke_analysis_20260724.json
audit/agent_vertex_smoke_analysis_20260724.md
```

2. Apply these non-negotiable rules:

- Treat `legacy/` as evidence only. Never import or train from it.
- Never hand-edit a frozen config.
- Never use test events or test metrics for preprocessing, thresholds, loss
  weights, architecture, stopping, checkpoint selection, or corrections.
- Stop on schema, geometry, hash, invariant, nonfinite, negative-energy,
  empty-bin, split-leakage, CUDA-fallback, checkpoint, memory-headroom, or
  artifact failure.
- Preserve every failure and every prefix. Never weaken a gate and never
  overwrite a GCS prefix.
- Use one on-demand `NVIDIA_TESLA_T4` for any later authorized pilot. Spot,
  low-cost, preemptible, another accelerator, multiple GPUs, and CPU fallback
  are forbidden.
- Log commands, timestamps, hashes, environment, alternatives, decisions,
  counterexamples, and failed attempts. Do not log hidden chain-of-thought.
- A structural smoke pass is not physics validation.

3. Use these exact immutable identities:

```text
project=asiop-zdc-1
project_number=39719277374
region=us-central1
service_account=39719277374-compute@developer.gserviceaccount.com

root_uri=gs://asiop-zdc-1-zdc-reco-us-central1/data/myTree_20251117_765k_0to300GeV_neutron_All.root
root_generation=1783683550292251
root_size=25022001408
root_crc32c=lCVUvQ==
root_sha256=b7c666040e42352e158a9a3f78158d147cb2e056c6c88248d892c956f5c7b533
root_tree=myTree
root_entries=764940

prepare_job=projects/39719277374/locations/us-central1/customJobs/1981826012068970496
prepare_prefix=gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/prep-20260724-r5

smoke_pipeline=projects/39719277374/locations/us-central1/trainingPipelines/5105571531929419776
smoke_job=projects/39719277374/locations/us-central1/customJobs/4964365651620659200
smoke_input=gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/prep-20260724-r5-fp32-r2
smoke_output=gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/smoke-20260724-r2-fp32
smoke_image=us-central1-docker.pkg.dev/asiop-zdc-1/cbsc-zdc/cbsc-zdc@sha256:45ff337d8c4b1b34e936a24926a8fa495aebfb06187e75965fab9624d1f402f1
smoke_frozen_config_sha256=e75f1bda7140a00b9caf04bf9ee574c034879e7a935dfe32a42a983680511f31
smoke_template_sha256=bb09dff2040906d98d5df5e116a344c12d7212836090d66ee33cbcd6f7fc9633
geometry_hash=e22d4cfb1e9293a33dd13151587910268ba64cd8efbcdb7a835a7442f2edcb4b
```

4. Verify local code without changing it:

```powershell
$env:PYTHONPATH = (Resolve-Path -LiteralPath 'src').Path
python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw 'pytest failed' }
python -m compileall -q src vertex tests
if ($LASTEXITCODE -ne 0) { throw 'compileall failed' }
```

Require exactly 25 passing tests. The two documented Transformer
nested-tensor warnings are nonfatal; any other failure is fatal.

5. Re-verify preparation from the full production ROOT artifact:

```powershell
gcloud ai custom-jobs describe 1981826012068970496 `
  --project asiop-zdc-1 `
  --region us-central1 `
  --format=json
if ($LASTEXITCODE -ne 0) { throw 'preparation describe failed' }

python vertex/verify_prepare_output.py `
  --prefix gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/prep-20260724-r5 `
  --expected-generation 1783683550292251 `
  --expected-size 25022001408 `
  --expected-crc32c lCVUvQ== `
  --expected-entries 764940 `
  --output audit/next_agent_verified_prepare_r5.json
if ($LASTEXITCODE -ne 0) { throw 'preparation verification failed' }
```

Require `JOB_STATE_SUCCEEDED` and `pass=true`. Require:

```text
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

Do not use any failed preparation prefix.

6. Describe the existing smoke job. Do not submit a job:

```powershell
$smoke = gcloud ai custom-jobs describe 4964365651620659200 `
  --project asiop-zdc-1 `
  --region us-central1 `
  --format=json | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) { throw 'smoke describe failed' }
if ($smoke.state -ne 'JOB_STATE_SUCCEEDED') {
  throw "unexpected smoke state: $($smoke.state)"
}
$pool = $smoke.jobSpec.workerPoolSpecs[0]
if ($smoke.jobSpec.scheduling.strategy -ne 'ON_DEMAND') {
  throw 'smoke was not ON_DEMAND'
}
if ($pool.machineSpec.machineType -ne 'n1-standard-8') {
  throw 'wrong machine type'
}
if ($pool.machineSpec.acceleratorType -ne 'NVIDIA_TESLA_T4' -or
    [int]$pool.machineSpec.acceleratorCount -ne 1) {
  throw 'wrong accelerator'
}
if ([int]$pool.replicaCount -ne 1) {
  throw 'wrong replica count'
}
$expectedImage = 'us-central1-docker.pkg.dev/asiop-zdc-1/cbsc-zdc/' +
  'cbsc-zdc@sha256:45ff337d8c4b1b34e936a24926a8fa495aebfb06187e75965fab9624d1f402f1'
if ($pool.containerSpec.imageUri -ne $expectedImage) {
  throw 'wrong immutable image'
}
```

Also confirm the exact input prefix, output prefix, FP32 config relative path,
one CUDA device request, 100 GB `pd-ssd`, and the service account from the job
JSON.

7. Verify and obtain the existing artifacts:

```powershell
gcloud storage ls -l -r `
  'gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/smoke-20260724-r2-fp32/**'
if ($LASTEXITCODE -ne 0) { throw 'smoke listing failed' }

$target = Join-Path (Get-Location) 'audit\vertex_smoke_fp32_r2'
if (-not (Test-Path -LiteralPath $target)) {
  New-Item -ItemType Directory -Path $target | Out-Null
  gcloud storage cp --recursive `
    gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/smoke-20260724-r2-fp32/* `
    $target
  if ($LASTEXITCODE -ne 0) { throw 'smoke download failed' }
}
```

Require exactly these 16 files and no `vertex_failure.json`:

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

Hash every file:

```powershell
$root = Resolve-Path -LiteralPath 'audit\vertex_smoke_fp32_r2'
$hashes = Get-ChildItem -LiteralPath $root -Recurse -File |
  Sort-Object FullName |
  ForEach-Object {
    $hash = Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256
    [pscustomobject]@{
      path = $_.FullName.Substring($root.Path.Length + 1).Replace('\','/')
      size = $_.Length
      sha256 = $hash.Hash.ToLowerInvariant()
    }
  }
$hashes | Format-Table -AutoSize
```

Compare every value to the `output_artifacts.sha256` object in
`audit/agent_vertex_smoke_analysis_20260724.json`. A mismatch is fatal.

8. Independently analyze the reports and require these exact accepted values:

```text
cuda_available=true
cuda_device_count=1
cuda_device_name=Tesla T4
total_memory_bytes=15655829504
peak_memory_bytes=7848525312
headroom_fraction=0.49868352168789687
resource pass=true

preflight pass=true
verified_shards=187
selected train/validation/test=338/64/0

training stage=joint
epoch=0
updates=84
train_loss=24.04530804497855
validation_loss=20.07763433456421
seconds=57.4816040180001
examples_per_second=5.880142104144429

epoch invariant pass=true
epoch layer_closure_max_gev=4.76837158203125e-07
epoch event_closure_max_gev=9.5367431640625e-07

postflight invariant pass=true
postflight layer_closure_max_gev=4.76837158203125e-07
postflight event_closure_max_gev=2.384185791015625e-07

all nonfinite, negative, invalid-support, support-mask, count,
requested/realized, and dust failure values=0

timing device=cuda:0
timing batch_size=2
timing profile_steps=1
timing share_steps=1
timing iterations=2
timing milliseconds_per_event=99.04152249998788
```

The postflight created a fresh model and loaded `best.pt` before sampling, so
successful `vertex_result.json.smoke_postflight.pass=true` plus the fixed
condition artifacts proves checkpoint reload. Confirm `best.pt` and `last.pt`
exist and have the expected hashes.

9. Check the scientific boundary. Record, do not hide:

```text
validation events=64
high_level_c2st_auc=1.0
truth_zero_fraction=0.015625
generated_zero_fraction=0.296875
response_wasserstein_normalized=0.4034199118614197
hit_count_wasserstein_normalized=1.0333642292132128
```

These are poor one-epoch diagnostics. State explicitly that this smoke passed
software, target-hardware, checkpoint, resource, and structural gates only. It
did not validate Geant4 fidelity. Do not tune an acceptance gate from these
values. The timing is a one-step solver/decode smoke, not the required final
8/8-step performance benchmark.

10. Preserve and report all earlier failures:

- preparation r1 job `5551984247922753536`: ganged-position counterexample;
- preparation r2/r3 jobs `3440077497662701568` and
  `2318329346726559744`: native structured-NumPy mapping crash;
- preparation r4 job `8852770931064438784`: sentinel accounting mismatch;
- coordinator r1 job `9206444239301378048`: legitimate `excluded` count
  rejected before smoke submission;
- first T4 pipeline `7972253432239095808` and custom job
  `5080522458025426944`: finite forward loss but nonfinite AMP gradient norm at
  epoch 0 step 0, with no accepted update or checkpoint;
- staging prefix `prep-20260724-r5-fp32`: flattened hierarchy and excluded.

Do not delete or reuse any failed prefix.

11. Write your independent outputs to new files:

```text
audit/next_agent_vertex_smoke_verification_20260724.json
audit/next_agent_vertex_smoke_verification_20260724.md
```

Include job spec, state, every input/output hash, event/split counts, geometry
and ganging evidence, training measurements, all invariant values, checkpoint
reload evidence, timing scope, resource measurements, poor validation
diagnostics, and every failed gate. End with exactly these four dispositions:

```text
structural_smoke=GO
validation_only_component_loss_lr_work=GO
physics_validation=NOT_ESTABLISHED
final_training=BLOCKED
```

If and only if every read-only verification above passes, make a concrete plan
for the next permitted Vertex phase. The plan must:

- use train and validation only;
- use exact stage order
  `response -> profile -> count -> support -> share -> joint`;
- enforce the guide's predecessor checkpoint and shared-encoder rules;
- perform train-only gradient-norm loss calibration on at most 64 batches;
- perform validation-only loss sensitivity and
  learning-rate/weight-decay/effective-batch studies;
- include truth-half statistical-floor and full-validation memory pilots;
- use new unfrozen templates, normal config freezing, immutable image digests,
  empty generation-0-locked GCS prefixes, one on-demand T4, and no CPU fallback;
- stop on every mandatory gate;
- not submit the six final runs;
- not open test.

Do not launch that next phase merely because this prompt asks for a plan. First
return the verification and proposed exact job matrix, commands, new prefix
names, and QA gates for review. A later explicit authorization is required to
submit those new validation-only jobs.

Your final response must link both new verification files, state the four
dispositions verbatim, summarize the measured evidence, list every failed gate,
and clearly separate structural smoke success from physics validation.

---
