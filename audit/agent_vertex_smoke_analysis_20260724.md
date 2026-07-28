# Vertex FP32 smoke analysis

Date: 2026-07-24

## QA interpretation

The production-data-derived, full-architecture FP32 smoke reproduced its
**structural and infrastructure QA**. Train/validation-only component,
loss-calibration, and learning-rate work are identified as follow-up QA.

It is **not physics validation** and does not open the test split. Whether to run
new training is a user decision under a newly specified experiment. The
one-epoch validation
diagnostics are poor, as expected for a connectivity smoke: high-level C2ST AUC
is `1.0`, generated zero fraction is `0.296875` versus truth `0.015625`, and
normalized hit-count Wasserstein is `1.0333642292132128`.

## Exact successful execution

- Training pipeline:
  `projects/39719277374/locations/us-central1/trainingPipelines/5105571531929419776`
- Custom job:
  `projects/39719277374/locations/us-central1/customJobs/4964365651620659200`
- Terminal state: `JOB_STATE_SUCCEEDED`
- Runtime: `2026-07-24T16:24:13Z` to `2026-07-24T16:40:48Z`
- Scheduling: `ON_DEMAND`
- Worker: one `n1-standard-8`, one `NVIDIA_TESLA_T4`, one replica
- Image:
  `us-central1-docker.pkg.dev/asiop-zdc-1/cbsc-zdc/cbsc-zdc@sha256:45ff337d8c4b1b34e936a24926a8fa495aebfb06187e75965fab9624d1f402f1`
- Input:
  `gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/prep-20260724-r5-fp32-r2`
- Output:
  `gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/smoke-20260724-r2-fp32`
- Frozen config SHA-256:
  `e75f1bda7140a00b9caf04bf9ee574c034879e7a935dfe32a42a983680511f31`
- Template SHA-256:
  `bb09dff2040906d98d5df5e116a344c12d7212836090d66ee33cbcd6f7fc9633`

The GCS config object's MD5 and CRC32C match the local frozen config. A
field-by-field comparison found only the permitted Vertex path/run-directory
rewrites plus staging provenance; all scientific fields remained frozen.

## Data and geometry evidence

- Source: the full 25,022,001,408-byte production ROOT object, generation
  `1783683550292251`, SHA-256
  `b7c666040e42352e158a9a3f78158d147cb2e056c6c88248d892c956f5c7b533`
- Events: 764,940
- Preparation: 187/187 shards independently verified
- Geometry: 6,790 nodes, 65 layers, hash
  `e22d4cfb1e9293a33dd13151587910268ba64cd8efbcdb7a835a7442f2edcb4b`
- Ganging: 2,400 readouts, maximum four stable physical centers per readout,
  frozen at the unweighted centroid
- Full split: 612,482 train / 76,158 validation / 76,300 test
- Pilot assignments: 338 train / 104 validation / 0 test / 764,498 excluded
- Actual selected smoke events: 338 train / 64 validation / 0 test
- Event-total closure maximum: `1.3500311979441904e-13` GeV
- Modeled non-sentinel readout closure maximum:
  `1.1368683772161603e-13` GeV

The staged input manifest contains 207 objects and 5,944,363,214 bytes, including
all 187 production shards. It contains no `legacy/` path and no test-named
artifact.

## Training, reload, invariants, and resources

- FP32 (`amp: false`), joint stage, one epoch, seed `20260723`
- Train loss: `24.04530804497855`
- Validation loss: `20.07763433456421`
- Updates: `84`
- Epoch time: `57.4816040180001` seconds
- Throughput: `5.880142104144429` examples/s
- Best and last checkpoints exist; postflight reloaded the best checkpoint
- Checkpoint is format 2, epoch 0, joint stage, with model, optimizer, scheduler,
  scaler, RNG, config, environment, and provenance state
- CUDA: PyTorch `2.6.0+cu124`, CUDA `12.4`, cuDNN `90100`
- T4 total memory: 15,655,829,504 bytes
- Peak allocated: 7,848,525,312 bytes
- Headroom: `49.868352168789687%`, above the required 15%

Epoch-candidate and postflight invariants both passed with zero nonfinite,
negative, invalid-support, support-mask, count, requested/realized, and dust
failures. Maximum closures were:

- Epoch candidate: layer `4.76837158203125e-07` GeV; event
  `9.5367431640625e-07` GeV
- Fixed-condition postflight: layer `4.76837158203125e-07` GeV; event
  `2.384185791015625e-07` GeV
- Validation: layer `9.5367431640625e-07` GeV; event
  `3.814697265625e-06` GeV

An independent array-level recheck of the five fixed conditions
`[0, 50, 150, 250, 300]` GeV found zero nonfinite, negative, support, or count
failures and reproduced layer closure to `4.76837158203125e-07` GeV.

The smoke benchmark exercised sampler solver plus decode on the T4 at batch 2,
one profile step, one share step, one warmup, and two iterations:
`99.04152249998788` ms/event. This is a short structural timing check, not a
production speed claim and not the frozen 8/8-step benchmark required later.

## Preserved failures

The evidence retains every material failed gate:

1. Preparation r1 exposed legitimate ganged HCAL geometry.
2. Preparation r2/r3 hit a native structured-NumPy mapping crash.
3. Preparation r4 exposed incorrect sentinel-versus-modeled event accounting.
4. Coordinator r1 rejected the legitimate `excluded` pilot count.
5. The first T4 smoke failed at AMP step 0 with a nonfinite gradient norm;
   no update or checkpoint was accepted.
6. The first FP32 wildcard copy flattened the directory hierarchy and is
   permanently excluded.
7. Two local test invocations omitted `PYTHONPATH=src`; corrected runs passed.
8. Two unsupported coordinator resource specifications were rejected before
   resource creation.

No gate was weakened. The successful retry changed only the unfrozen template's
precision setting to FP32, then generated a new frozen config, image-pinned job,
and GCS prefix.

## Next permitted work

The next agent may independently verify these artifacts and then plan or run
validation-only work in the exact guide order:

`response -> profile -> count -> support -> share -> joint`

Before any final training, it must complete train-only gradient calibration
(maximum 64 batches), validation-only sensitivity and optimizer pilots,
truth-half gate-floor work, full-evaluation memory piloting, and final
gate/config freezes. It must not open test data or launch the six-run final
matrix.

The complete machine-readable record, including every output SHA-256, is
`audit/agent_vertex_smoke_analysis_20260724.json`.
