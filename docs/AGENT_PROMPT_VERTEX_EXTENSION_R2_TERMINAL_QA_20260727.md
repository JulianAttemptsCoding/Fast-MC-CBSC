# Exact prompt for the independent E4 terminal-QA agent

Copy everything below the separator verbatim.

---

You are the independent terminal-QA agent for the completed CBSC-ZDC v2.2
calibrated LR 3e-5 and LR 1e-4 E2→E4 Vertex extension. Work only in:

```text
source=C:\Users\Julia\OneDrive\Desktop\coding\ASIoP\Fast MC CBSC
public=C:\Users\Julia\OneDrive\Desktop\coding\ASIoP\Fast-MC-Visual-Tests
project=asiop-zdc-1
region=us-central1
public_url=https://julianattemptscoding.github.io/Fast-MC-Visual-Tests/
```

Read these files completely before running any command:

```text
source\docs\IMPLEMENTATION_GUIDE.md
source\AGENTS.md
source\docs\COMPUTE_EXTENSION_PROTOCOL_20260727.md
source\logs.md
source\audit\compute_extension_20260727_r2_terminal_analysis.json
source\audit\compute_extension_20260727_r2_terminal_analysis.md
```

This experiment is terminal. Do not submit, resume, clone, cancel, or mutate a
Vertex job. Do not edit a frozen config. Never use `legacy/`, test data, Spot,
CPU fallback, AMP, or a mutable image tag. Never claim physics validation.

## 1. Verify the exact server-side jobs

```text
image=us-central1-docker.pkg.dev/asiop-zdc-1/cbsc-zdc/cbsc-zdc@sha256:8b4a94c0c748febdb059b1302503d280498ddd1360b595a90e0a6c9b0999048f

calibrated_lr3e5:
  pipeline=3939574635045060608
  custom_job=4234868273893605376
  input=gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/compute-extension-20260727-r2-calibrated-lr3e5-input
  output=gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/compute-extension-20260727-r2-calibrated-lr3e5-output
  parent_output=gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/compute-extension-20260727-r1-calibrated-lr3e5-output

calibrated_lr1e4:
  pipeline=8388568116933689344
  custom_job=3118380186584743936
  input=gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/compute-extension-20260727-r2-calibrated-lr1e4-input
  output=gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/compute-extension-20260727-r2-calibrated-lr1e4-output
  parent_output=gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/compute-extension-20260727-r1-calibrated-lr1e4-output
```

Run:

```powershell
gcloud ai custom-jobs describe 4234868273893605376 --project=asiop-zdc-1 --region=us-central1 --format=json
gcloud ai custom-jobs describe 3118380186584743936 --project=asiop-zdc-1 --region=us-central1 --format=json
```

Require `JOB_STATE_SUCCEEDED`, `ON_DEMAND`, one replica, `n1-standard-8`,
one `NVIDIA_TESLA_T4`, 100 GB `pd-ssd`, a 14,400-second timeout, exact image
digest and prefixes above, and `--postflight-training`. Expected execution:

```text
family    start UTC              end UTC                duration
lr3e5     2026-07-27T07:48:59Z  2026-07-27T10:27:27Z  9,508 s
lr1e4     2026-07-27T07:49:24Z  2026-07-27T10:22:55Z  9,211 s
```

Each output must contain exactly 183 objects, 13 objects in E3, 16 in E4,
and no `vertex_failure.json`.

## 2. Reproduce all four immutable epoch gates

Run from `source`. Add a unique `--output audit\independent_...json` to each
command if you want to preserve the reproduced reports.

```powershell
python scripts\verify_compute_extension_epoch_gcs.py --project asiop-zdc-1 --output-uri gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/compute-extension-20260727-r2-calibrated-lr3e5-output --input-uri gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/compute-extension-20260727-r2-calibrated-lr3e5-input --parent-output-uri gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/compute-extension-20260727-r1-calibrated-lr3e5-output --name calibrated_lr3e5 --expected-epoch 3 --history-start-epoch 3 --expected-training-epochs 5 --parent-epoch 2 --expected-parent-best-sha256 f40c883b9f202f5b0b5763dc171147485845ef7cff877637ca5a500d6ea9d8ad --expected-parent-last-sha256 f6ef8db0ba119c4415fa99ec257b71e3ee58762df347ce9408588266249047d3 --expected-batch-size 6 --expected-gradient-accumulation 4 --expected-selection-sha256 f70529198aa9575cd2ebc816fd0800ed5a1a3dcd918dab3845b5dc5d85dc59b6

python scripts\verify_compute_extension_epoch_gcs.py --project asiop-zdc-1 --output-uri gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/compute-extension-20260727-r2-calibrated-lr3e5-output --input-uri gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/compute-extension-20260727-r2-calibrated-lr3e5-input --parent-output-uri gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/compute-extension-20260727-r1-calibrated-lr3e5-output --name calibrated_lr3e5 --expected-epoch 4 --history-start-epoch 3 --expected-training-epochs 5 --parent-epoch 2 --expected-parent-best-sha256 f40c883b9f202f5b0b5763dc171147485845ef7cff877637ca5a500d6ea9d8ad --expected-parent-last-sha256 f6ef8db0ba119c4415fa99ec257b71e3ee58762df347ce9408588266249047d3 --expected-batch-size 6 --expected-gradient-accumulation 4 --expected-selection-sha256 f70529198aa9575cd2ebc816fd0800ed5a1a3dcd918dab3845b5dc5d85dc59b6

python scripts\verify_compute_extension_epoch_gcs.py --project asiop-zdc-1 --output-uri gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/compute-extension-20260727-r2-calibrated-lr1e4-output --input-uri gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/compute-extension-20260727-r2-calibrated-lr1e4-input --parent-output-uri gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/compute-extension-20260727-r1-calibrated-lr1e4-output --name calibrated_lr1e4 --expected-epoch 3 --history-start-epoch 3 --expected-training-epochs 5 --parent-epoch 2 --expected-parent-best-sha256 0f1866b6547e3bae37700fa2089c93d4c79a25d6e8ea7c345233adca737fa920 --expected-parent-last-sha256 3f9620b74341ee92ea7080c5b27eafb38eb3425bb545fd15169da2e805e28bce --expected-batch-size 6 --expected-gradient-accumulation 4 --expected-selection-sha256 f70529198aa9575cd2ebc816fd0800ed5a1a3dcd918dab3845b5dc5d85dc59b6

python scripts\verify_compute_extension_epoch_gcs.py --project asiop-zdc-1 --output-uri gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/compute-extension-20260727-r2-calibrated-lr1e4-output --input-uri gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/compute-extension-20260727-r2-calibrated-lr1e4-input --parent-output-uri gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/compute-extension-20260727-r1-calibrated-lr1e4-output --name calibrated_lr1e4 --expected-epoch 4 --history-start-epoch 3 --expected-training-epochs 5 --parent-epoch 2 --expected-parent-best-sha256 0f1866b6547e3bae37700fa2089c93d4c79a25d6e8ea7c345233adca737fa920 --expected-parent-last-sha256 3f9620b74341ee92ea7080c5b27eafb38eb3425bb545fd15169da2e805e28bce --expected-batch-size 6 --expected-gradient-accumulation 4 --expected-selection-sha256 f70529198aa9575cd2ebc816fd0800ed5a1a3dcd918dab3845b5dc5d85dc59b6
```

Every verifier must return `pass=true`, 200 changed model tensors, finite
parent/best/last/optimizer states, optimizer step 5,550 at E4, restarted
scheduler step 2,220, all invariants passing, 25.0186% T4 headroom, exact
50-by-5 validation selection, and `test_events_used=0`.

Reproduce:

```text
family  epoch  train       validation  best epoch  last SHA
lr3e5   E3     5.053009    4.939322    E2          d46e660cd803a65c0aafbd81f64ed7cb0375ee881d5c1d903053dafe7c506e87
lr3e5   E4     4.981933    4.897327    E4          83758012275d20a4a23c1495ccc30e240913c95a416f3fb31c0b5d472c10aaf8
lr1e4   E3     5.032178    4.911421    E2          08f05802c77f84e01854e1716207b20facbfa18ab09c3389b0edd8a2a1ec6fab
lr1e4   E4     4.920952    4.827105    E4          0a9a229495004681e2df9ebe5099889e40de5af2def05eb2cf48098f0ccb8915
```

E4 improves over E2 by 0.615795% and 1.060029%, respectively. Do not hide
that E3 regressed first. The narrow more-compute hypothesis is supported over
the two-epoch horizon, not monotonically at every epoch.

## 3. Verify postflight

Read, hash, and parse these four objects under each output:

```text
reports/training_postflight.json
reports/training_postflight_invariants.json
reports/training_postflight_resources.json
reports/training_postflight_timing.json
```

Require fresh best-checkpoint reload, `pass=true`, `Tesla T4`, 25.0186%
headroom, seven fixed kinetic conditions, 8 profile and 8 share steps, and:

```text
lr3e5  294.797365 ms/event  postflight SHA=2f7e1e2cd4659697d6db96c1b884a2c641956926a684b4deeb652adc80f38c31
lr1e4  278.449114 ms/event  postflight SHA=85ec565227e323c5fe7bedc84822c8c24e0e6fcedf517ca46725a728240ff355
```

## 4. Verify exhibition and public site

From `source`:

```powershell
python exhibition\build_exhibition.py
python -m compileall -q exhibition scripts src tests
```

Require five contiguous epochs for all four calibrated families, 23 generated
visual files, common selection position 21, common selection hash, validation
only, 50 conditions × five draws, zero test events, and no missing figure.

From `public`:

```powershell
python scripts\export_public_data.py --source '..\Fast MC CBSC\dashboard\public\data' --destination 'public\data' --selection 'config\public_snapshots.json'
npm ci
npm test
npm run build
```

Require exactly four public entries and these IDs:

```text
compute-extension-r2-calibrated-lr3e5:joint:0004
compute-extension-r2-calibrated-lr1e4:joint:0004
compute-extension-r1-calibrated-lr3e4:joint:0004
compute-extension-r1-calibrated-lr1e4-halfbatch:joint:0004
```

Verify public commit `784fe6bf572cb6285fb2e92a54858883da1c0e6e`,
successful workflow `30285942671`, and live manifest SHA-256
`3ab56be2af72b386fa2e553d48aea9e9dbb361e19621c35639e8e61b1f3c8bfe`.
Fetch each live gzip payload with cache bypass; verify compressed SHA before
decompression, exact epoch/checkpoint/stage, validation split, selection hash,
50 groups, five draws in every group, `qa.pass=true`, and zero test events.

If interactive browser setup fails with kernel-asset `os error 3`, record it as
an environment limitation. Do not substitute another automation driver.

## 5. Cost and output

Latest jobs used 5.199722 T4-hours × $0.85/hour = $4.4198. Cumulative
extension usage is 15.13 T4-hours. Conservative total is $53.1006/$100,
leaving $46.8994.

Write a new timestamped JSON and Markdown report under `source\audit`.
Record commands, hashes, mismatches, failed attempts, and live checks; never
record private hidden chain-of-thought. Do not alter accepted artifacts.
Finish with exactly:

```text
structural_and_optimization_QA=PASS
more_compute_validation_hypothesis=SUPPORTED_FOR_ALL_4_CALIBRATED_FAMILIES
physics_validation=NOT_ESTABLISHED
historical_frozen_A100_screening=NO-GO_UNCHANGED
test_evaluation=BLOCKED_NOT_OPENED
further_Vertex_jobs_authorized=false
```
