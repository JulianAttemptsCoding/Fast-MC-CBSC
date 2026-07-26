# CBSC-ZDC v2.2 Vertex QA gate plan

Date: 2026-07-24  
Project: `asiop-zdc-1`  
Region: `us-central1`  
Primary claim domain: 50–250 GeV kinetic energy  
Production training support: 0–300 GeV kinetic energy  
Production target: raw deposited energy, threshold 0 GeV

This plan follows `docs/IMPLEMENTATION_GUIDE.md`. A failed mandatory gate stops the
workflow. The failed artifact must be corrected upstream, dependent artifacts must
be regenerated and rehashed, and the gate must be rerun. Synthetic or pilot passes
are infrastructure/software evidence, not physics validation.

## Immutable inputs

- ROOT URI:
  `gs://asiop-zdc-1-zdc-reco-us-central1/data/myTree_20251117_765k_0to300GeV_neutron_All.root`
- ROOT generation: `1783683550292251`
- ROOT size: `25022001408` bytes
- ROOT CRC32C: `lCVUvQ==`
- Expected tree and entries: latest `myTree`, `764940`
- Schema: `configs/schema_production_myTree.yaml`
- GPU image:
  `us-central1-docker.pkg.dev/asiop-zdc-1/cbsc-zdc/cbsc-zdc@sha256:45ff337d8c4b1b34e936a24926a8fa495aebfb06187e75965fab9624d1f402f1`
- FP32 frozen config SHA-256:
  `e75f1bda7140a00b9caf04bf9ee574c034879e7a935dfe32a42a983680511f31`
- GPU: exactly one on-demand `NVIDIA_TESLA_T4`; Spot/low-cost scheduling is forbidden.

## Ordered gates

| ID | Gate and evidence | Pass condition | Failure action |
|---|---|---|---|
| G00 | Repository contract | Guide read first; `legacy/` excluded; no frozen config edited | Stop and restart from active files |
| G01 | Bundle integrity | Original 169 checksums match before changes; all subsequent changes are in the evidence log | Stop on missing/mismatched input |
| G02 | Unit/contract regression | `PYTHONPATH=src python -m pytest -q` passes; compileall passes | Fix code and rerun |
| G03 | Cloud identity | Project, region, service account, APIs, bucket, image digest, and source generation are recorded | Stop on any mismatch |
| G04 | ROOT schema | Tree exists; required branches exist; 764940 entries; vector lengths and neutron primary contract hold | Fix schema/adapter, never skip rows silently |
| G05 | Full geometry freeze | Full ROOT scan proves stable distinct physical centers, freezes each ganged readout at the unweighted centroid of its centers, and passes strict counts: 6790 nodes, 65 layers, expected per-layer counts | Stop on unknown, duplicate, drifting, hit-frequency-weighted, or empty geometry |
| G06 | Full conversion | Every event is accounted for; no nonfinite/negative hit; no primary failure; all stored hits (including sentinel non-readout deposits) agree with `energySum_ZDC`; mapped nodes separately agree with non-sentinel raw readout deposits; excluded sentinel energy and all hashes are recorded | Stop on rejection or either residual failure |
| G07 | Leakage-safe split | Deterministic event-hash split has nonempty train/validation/test and all energy bins; assignment hash/length/codes pass | Stop; disclose one-file grouping limitation |
| G08 | Train-only audit | 0–300 GeV train audit has no nonfinite/negative targets and no empty energy bin | Stop; never inspect test to repair this gate |
| G09 | Pilot derivation | Pilot copies only parent train/validation assignments; test count is exactly zero; 26 train and 8 validation events per full energy bin before evaluation-range filtering | Stop on any test selection or parent-hash mismatch |
| G10 | Freeze/preflight | Frozen config has no `UNFROZEN`; geometry, data, split, assignment, audit, and all shard hashes cross-check | Regenerate; never hand-edit frozen YAML |
| G11 | Vertex scheduling | Job spec says one `NVIDIA_TESLA_T4`, accelerator count 1, strategy `ON_DEMAND`, one replica, immutable image digest | Cancel on Spot/unspecified accelerator/wrong image |
| G12 | Target-hardware startup | CUDA is available; environment records exactly one device named T4; runtime config preserves scientific values | Stop on CPU fallback or config drift |
| G13 | Per-batch training | Loss, gradients, and parameters remain finite; no loader/schema/hash failure | Stop immediately and retain failure artifact |
| G14 | Per-epoch candidate | Structural invariant report passes before candidate checkpoint acceptance; best and last checkpoints save | Stop on count/support/nonnegative/closure failure |
| G15 | Reload/sample | Best checkpoint reloads; fixed conditions 0, 50, 150, 250, 300 GeV sample successfully; invariant report passes | Stop; diagnose serialization/model contract |
| G16 | Pilot resource gate | Peak T4 memory leaves at least 15% device-memory headroom; throughput and complete solver/decode timing are recorded | Reduce batch/accumulation only through a new template/freeze |
| G17 | Validation-only pilot | Validation report completes with no structural failure; results are explicitly not test/physics validation | Use validation only for permitted pilot choices |
| G18 | Component stages | Exact response → profile → count → support → share → joint order; expected checkpoint and shared-encoder rules enforced | Stop on stage/init mismatch |
| G19 | Loss/LR and gate freeze | Validation-only loss calibration, LR pilot, and truth-half statistical-floor study complete; final weights/LR/gates frozen | Do not start final runs |
| G20 | Final run matrix | Three frozen seeds each for matched 0–300 and 50–250 conditions: 20260723, 20260724, 20260725 | Report every seed and failed gate |
| G21 | Frozen test | Test is opened exactly once after protocol freeze; same 50–250 bank for both conditions; stress domains separate | A test-informed change invalidates final claim |
| G22 | Scientific acceptance | Per-bin fidelity, diversity, memorization, reconstruction, competent baselines/ablations, and end-to-end timing pass for all seeds | Report a negative result; never weaken baseline/gate |

## Current status

- G00-G17: pass for the FP32 structural smoke, with the failed AMP attempt
  retained as mandatory negative evidence.
- G04-G10: full-corpus preparation job
  `projects/39719277374/locations/us-central1/customJobs/1981826012068970496`
  succeeded. Independent verification covered all 764,940 events and all 187
  shard hashes. Full split counts are 612,482 train, 76,158 validation, and
  76,300 test. The pilot selected 338 train, 64 validation, and zero test
  events.
- G05 geometry hash
  `e22d4cfb1e9293a33dd13151587910268ba64cd8efbcdb7a835a7442f2edcb4b`
  proves 6,790 nodes, 65 layers, 2,400 ganged channels, and the unweighted
  distinct-center centroid contract.
- The first on-demand T4 smoke, custom job `5080522458025426944`, correctly
  failed G13 at epoch 0 step 0 because AMP produced a nonfinite gradient norm.
  It accepted no optimizer update and no checkpoint.
- A new unfrozen template changed only `training.amp` to `false`; it was frozen
  normally and submitted under a new prefix. FP32 custom job
  `projects/39719277374/locations/us-central1/customJobs/4964365651620659200`
  succeeded on one on-demand T4. It completed one finite epoch, saved/reloaded
  checkpoints, passed epoch/postflight/validation structural invariants, and
  retained `49.868352168789687%` measured memory headroom.
- The output is
  `gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/smoke-20260724-r2-fp32`.
  Independent reports are `audit/agent_vertex_smoke_analysis_20260724.json`
  and `audit/agent_vertex_smoke_analysis_20260724.md`.
- G18-G22 remain blocked. The observed one-epoch validation diagnostics are
  poor (high-level C2ST AUC `1.0`) and are not physics validation. Final
  training remains blocked until validation-only calibration, gate freezing,
  and the remaining publication-level evaluation work are complete.

## Known scientific limitations and engineering risks

- The single monolithic ROOT file exposes no run/seed family identifier. The
  supported fallback is deterministic `event_hash`; this does not prove
  simulation-family independence.
- The provided acceptance gates and loss weights are provisional. They may be
  studied using validation, but not test.
- A one-epoch full-architecture pilot proves execution, memory, checkpoint, and
  structural contracts only.
- The smoke timing used one profile step and one share step for two short
  iterations. It includes solver and decode, but is not the final 8/8-step
  production performance benchmark.
- Production HCAL `hcal_pos*` values are discrete physical centers, and a single
  `(layerID, cellID)` may represent multiple centers. Static readout positions
  are frozen as the unweighted centroid of the distinct centers; weighting by
  observed hit frequency would leak response-distribution information.
- Low-level C2ST, neighborhood correlations, connected components,
  repeated-condition diversity, memorization, reconstruction, and all required
  baselines are not yet complete in the CLI.
- The evaluator no longer retains full model outputs on the GPU, but its final
  dense CPU truth/generated arrays can still require several GB on the complete
  test bank. Full-evaluation memory/streaming behavior must be piloted before G21.
- The container dependencies use lower bounds rather than a lockfile. The immutable
  image digest and emitted environment are therefore mandatory provenance.
- On-demand scheduling avoids Spot preemption, and Python exceptions upload failure
  artifacts. A hard worker loss between epoch uploads can still lose the current
  local epoch; long production runs should add and verify periodic GCS checkpoint
  synchronization.
