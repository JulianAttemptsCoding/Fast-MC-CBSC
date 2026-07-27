# Exact prompt for an independent terminal QA agent

Copy everything below the separator verbatim.

---

You are the independent terminal QA agent for the completed CBSC-ZDC v2.2
Vertex compute extension. Work in:

```text
source=C:\Users\Julia\OneDrive\Desktop\coding\ASIoP\Fast MC CBSC
public=C:\Users\Julia\OneDrive\Desktop\coding\ASIoP\Fast-MC-Visual-Tests
project=asiop-zdc-1
region=us-central1
public_url=https://julianattemptscoding.github.io/Fast-MC-Visual-Tests/
```

First read `source\docs\IMPLEMENTATION_GUIDE.md`, `source\AGENTS.md`,
`source\docs\COMPUTE_EXTENSION_PROTOCOL_20260727.md`, `source\logs.md`, and
`source\audit\compute_extension_20260727_r1_terminal_analysis.{json,md}`.
Never use `legacy/`, test data, Spot, CPU fallback, AMP, a mutable image tag,
or a frozen-config edit. Do not submit, resume, clone, cancel, or mutate any
Vertex job. The experiment is terminal. Never claim physics validation.

Independently describe and verify these exact existing jobs:

```text
image=us-central1-docker.pkg.dev/asiop-zdc-1/cbsc-zdc/cbsc-zdc@sha256:8b4a94c0c748febdb059b1302503d280498ddd1360b595a90e0a6c9b0999048f

calibrated_lr3e5:
  pipeline=6276485444813193216
  custom_job=3731080842139664384
  output=gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/compute-extension-20260727-r1-calibrated-lr3e5-output
  expected_epochs=1,2

calibrated_lr1e4:
  pipeline=1268482659177201664
  custom_job=2327954471516110848
  output=gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/compute-extension-20260727-r1-calibrated-lr1e4-output
  expected_epochs=1,2

calibrated_lr3e4:
  pipeline=6713334608668131328
  custom_job=2033311743551209472
  output=gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/compute-extension-20260727-r1-calibrated-lr3e4-output
  expected_epochs=3,4

calibrated_lr1e4_halfbatch:
  pipeline=5186614334989533184
  custom_job=3979763984063528960
  output=gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/compute-extension-20260727-r1-calibrated-lr1e4-halfbatch-output
  expected_epochs=3,4
```

For each custom job, require `JOB_STATE_SUCCEEDED`, on-demand provisioning,
one `NVIDIA_TESLA_T4`, one replica, `n1-standard-8`, 100 GB `pd-ssd`, the
exact image digest above, exact input/output/config arguments, and zero test
use. Stop and report any mismatch.

From `source`, rerun the streamed verifier without creating checkpoint
mirrors. These are the exact four commands:

```powershell
python scripts\verify_compute_extension_epoch_gcs.py --project asiop-zdc-1 --output-uri gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/compute-extension-20260727-r1-calibrated-lr3e5-output --input-uri gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/compute-extension-20260727-r1-calibrated-lr3e5-input --parent-output-uri gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/viability-20260726-r1-calibrated-lr3e5-output --name calibrated_lr3e5 --expected-epoch 2 --history-start-epoch 1 --expected-training-epochs 3 --parent-epoch 0 --expected-parent-best-sha256 9864e8b9f77238caa68abe50eb8c460cbc498847a8f9194a5aaf9e5bdfe91707 --expected-parent-last-sha256 e3d4d0c7519340b546f07d9282a9c67c24600fa74198bebde6f45a192ef42185 --expected-batch-size 6 --expected-gradient-accumulation 4 --expected-selection-sha256 f70529198aa9575cd2ebc816fd0800ed5a1a3dcd918dab3845b5dc5d85dc59b6

python scripts\verify_compute_extension_epoch_gcs.py --project asiop-zdc-1 --output-uri gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/compute-extension-20260727-r1-calibrated-lr1e4-output --input-uri gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/compute-extension-20260727-r1-calibrated-lr1e4-input --parent-output-uri gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/viability-20260726-r1-calibrated-lr1e4-output --name calibrated_lr1e4 --expected-epoch 2 --history-start-epoch 1 --expected-training-epochs 3 --parent-epoch 0 --expected-parent-best-sha256 6258aa7b42d462ab7f5a9383811f8e8845f8f2356304c5a12bd39fbe0ae06221 --expected-parent-last-sha256 b375d0188708c9c0c99ace85d763c3390de384d86bd4929f8be4d965a4d40724 --expected-batch-size 6 --expected-gradient-accumulation 4 --expected-selection-sha256 f70529198aa9575cd2ebc816fd0800ed5a1a3dcd918dab3845b5dc5d85dc59b6

python scripts\verify_compute_extension_epoch_gcs.py --project asiop-zdc-1 --output-uri gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/compute-extension-20260727-r1-calibrated-lr3e4-output --input-uri gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/compute-extension-20260727-r1-calibrated-lr3e4-input --parent-output-uri gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/viability-20260727-wave2-r1-calibrated-lr3e4-output --name calibrated_lr3e4 --expected-epoch 4 --history-start-epoch 3 --expected-training-epochs 5 --parent-epoch 2 --expected-parent-best-sha256 0d02d193fcf2b97a1a3c89fa89ab88ebe6f708c83a1e52d36a609cec002d57a4 --expected-parent-last-sha256 f612b83a3f0025583b052413de6497bdeaf54713d146bfa07d1a1e1e8479c125 --expected-batch-size 6 --expected-gradient-accumulation 4 --expected-selection-sha256 f70529198aa9575cd2ebc816fd0800ed5a1a3dcd918dab3845b5dc5d85dc59b6

python scripts\verify_compute_extension_epoch_gcs.py --project asiop-zdc-1 --output-uri gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/compute-extension-20260727-r1-calibrated-lr1e4-halfbatch-output --input-uri gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/compute-extension-20260727-r1-calibrated-lr1e4-halfbatch-input --parent-output-uri gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/viability-20260727-wave2-r1-calibrated-lr1e4-halfbatch-output --name calibrated_lr1e4_halfbatch --expected-epoch 4 --history-start-epoch 3 --expected-training-epochs 5 --parent-epoch 2 --expected-parent-best-sha256 b9939a8eb157a33097c9dcf3af82e4bffd6d474888b129c65442ea006beca1e4 --expected-parent-last-sha256 67de2e2f26c947c163b6566ae8343e05cd3297e5facbd6b4431f27e02858ff1b --expected-batch-size 3 --expected-gradient-accumulation 4 --expected-selection-sha256 f70529198aa9575cd2ebc816fd0800ed5a1a3dcd918dab3845b5dc5d85dc59b6
```

Every verifier must report `pass=true`, exact paired parents, 200 changed
model tensors, finite checkpoints, correct optimizer/scheduler state, all
invariants passing, exact fixed 50 conditions × five independent draws,
selection SHA above, and `test_events_used=0`.

Reproduce this validation table within floating-point serialization:

```text
family                         parent      first added    final       vs first   vs parent
calibrated_lr3e5               4.988944    4.974206 E1    4.927671 E2   0.935517%  1.228171%
calibrated_lr1e4               4.973253    4.952879 E1    4.878822 E2   1.495222%  1.898779%
calibrated_lr3e4               4.800034    4.828354 E3    4.738041 E4   1.870461%  1.291507%
calibrated_lr1e4_halfbatch     4.903753    4.882708 E3    4.845029 E4   0.771684%  1.197537%
```

Verify public commit `a3816fbd590fde159d3a0c02ea0a67caa22673dc`,
successful workflow `30243408128`, and live manifest SHA-256
`2e504c7a094fe90ae050adbb06765834ea2472f4b7c7fa83beffbfcf17ba1f00`.
Require exactly these four IDs:

```text
compute-extension-r1-calibrated-lr3e5:joint:0002
compute-extension-r1-calibrated-lr1e4:joint:0002
compute-extension-r1-calibrated-lr3e4:joint:0004
compute-extension-r1-calibrated-lr1e4-halfbatch:joint:0004
```

Fetch the live manifest and all gzip payloads with cache bypass. Verify
compressed size/SHA-256 before decompression, exact checkpoint/epoch/stage,
validation split, selection hash, 50 groups, five draws per group, QA pass,
and zero test use. Run `npm ci`, `npm test`, and `npm run build` only if space
permits; remove reproducible `node_modules` and `dist` afterward.

Verify storage evidence without downloading bulk data:

```text
ROOT=gs://asiop-zdc-1-zdc-reco-us-central1/data/myTree_20251117_765k_0to300GeV_neutron_All.root#1783683550292251
ROOT_size=25022001408
ROOT_crc32c=lCVUvQ==
ROOT_sha256=b7c666040e42352e158a9a3f78158d147cb2e056c6c88248d892c956f5c7b533
archive=gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/local-evidence-offload-20260727-r1/audit
archive_objects=1018
archive_bytes=4105726074
```

Cost reconciliation is 9.930278 extension T4-hours × $0.85/hour = $8.4408.
Prior ledger is $35.24 and contingency $5, so conservative total is $48.6808
and remaining budget is $51.3192.

Write a new independent JSON and Markdown report. Do not modify training or
public artifacts unless a reproduced mismatch requires diagnostic evidence.
End with exactly:

```text
structural_and_optimization_QA=PASS
more_compute_validation_hypothesis=SUPPORTED_FOR_ALL_4_CALIBRATED_FAMILIES
physics_validation=NOT_ESTABLISHED
historical_frozen_A100_screening=NO-GO_UNCHANGED
test_evaluation=BLOCKED_NOT_OPENED
further_Vertex_jobs_authorized=false
```
