# External accepted-best metrics pipeline — 2026-08-04

## Current disposition

Implementation, deterministic repeat evidence, local publication, and visual QA
are complete. No CBSC training was started. The accepted generator checkpoint
remains `calibrated_lr1e4`,
`dicos-p9`, epoch 38, validation loss `4.635219681489869`, checkpoint SHA-256
`4c967cfc325953afe789d11994d88a0dfc64808908c5617e430608826242e71e`.

## Frozen scientific boundary

- Every epoch: refresh all validation diagnostic fields and figures on the RTX
  3090; use zero CBSC test events.
- New accepted validation-loss best only: run four-momentum reconstruction and
  AUROC studies from a fixed validation bank. These metrics are downstream
  descriptions and cannot select checkpoints or influence CBSC training.
- Keep the historical 40,000-test-event C2ST isolated and labeled historical.
  Do not reuse it as an automatic per-best monitor.
- Fail closed on checkpoint, split, selection, geometry, external-repository,
  model, schema, or artifact-hash disagreement.

## Audited dependencies

- Four-momentum evaluator source:
  `C:\Users\Julia\Desktop\coding\ASIoP\ML ZDC all 1`, commit
  `34aeaa61622fba69341bebc3813ca20485b65ace`, with unrelated dirty work
  preserved. Frozen champion: `M1_xgb_focus_only`.
- AUROC evaluator source:
  `C:\Users\Julia\Desktop\coding\ASIoP\Fast-MC-tester`, commit
  `1e7abc593805c633d5e42a44ce073ca6287e8972`, local branch two commits ahead;
  no remote action has been taken.
- DiCOS accepted-best checkpoint and 4,000-event validation diagnostic remain
  present in the shared permitted workdir. Both GPU endpoints authenticated.

## Completed deliverables

- The hash-bound 4,000-pair validation bank and accepted-best evaluator
  transaction completed on the RTX 3090 with zero CBSC train/test source events.
- The deterministic candidate and independent AUROC-only repeat agree exactly
  after excluding wall-time fields; see
  `audit/external_metrics_determinism_20260804.{json,md}`.
- All 348 numeric scientific and QA leaves are complete for every lineage epoch
  16–40, with eight ordinary/best-loss-so-far figure families (PNG and SVG),
  loss-vs-epoch, and accepted running-best loss.
- The organized exhibition validates 117 scientific graphics, including seven
  accepted-best external-metric figures. Original-resolution visual QA passed.
- Invalid and nondeterministic predecessor figures are excluded from the live
  exhibition and preserved in `JulianAttemptsCoding/Fast-MC-CBSCs-archive`.
- All 190 canonical exhibition files were copied non-destructively to
  `C:\Users\Julia\Desktop\coding\ASIoP\Fast MC CBSC\exhibition`; a source-subset
  SHA-256 comparison found zero missing or mismatched files.
- Final source QA passed 255 tests with eight known Transformer warnings. Both
  DiCOS GPUs were idle after the completed transaction, and no training process
  was present.
- The RTX 4090 source checkout was safely fast-forwarded through feature commit
  `189312f5e6b63efcb7ad52861fc52c1fbd3b452c` and left clean. Its prior tracked
  overlay was content-equivalent apart from line endings and was preserved in a
  temporary stash through the fast-forward, verified redundant, then dropped.
  One explicitly resolved untracked `src/cbsc_zdc_fastmc.egg-info/` packaging
  directory was removed; no run data or evidence was touched.

## Execution record

- The first RTX 3090 bank-export attempt generated 4,000/4,000 paired
  validation events, then failed closed before artifact publication because
  `generate_paired_sample` did not return the required `p4_total_gev` array.
  No partial bank or manifest was accepted, the process exited, and the GPU
  returned idle. The exact four-vector is now part of the shared helper's
  explicit output contract and is covered by an end-to-end equality test.
- The initial controller-managed retry was interrupted during NumPy import
  (`EXIT=130`) because the launcher did not detach with `nohup`; it also exposed
  stale-exit ambiguity. The corrected controller archives prior PID/exit/log
  evidence into the transaction-local `attempts/` directory before launching a
  new detached attempt. No event bank was published by the failed retry.
- A later correctly detached batch-32 export was intentionally terminated
  (`EXIT=143`) before its first completed batch after live GPU profiling showed
  only about 2.6 GiB memory use. The fixed controller command now uses batch
  128, preserving the 4,000-event selection, seed, split, checkpoint, and
  automatic OOM backoff. Export PID 9642 and dependent evaluator-waiter PID
  9836 subsequently completed; they are retained only as execution evidence.
- The batch-128 bank then completed with `EXIT=0` and its validation-only QA
  manifest. The first evaluator failed closed at Matplotlib import because the
  pod inherited an unavailable inline backend; it published no result manifest.
  Evaluation is now launched with frozen `MPLBACKEND=Agg`, and retry archiving
  preserves the failed partial evidence.
- Two nominally seeded evaluator executions produced different AUROC ensemble
  means (0.848931 and 0.864693), so seeded CUDA was rejected as insufficiently
  reproducible. The accepted rerun required deterministic PyTorch/cuDNN and
  CUBLAS execution, and an independent duplicate reproduced its scientific
  outputs exactly before the result was accepted current.
- The deterministic candidate and an independent AUROC-only repeat then matched
  exactly after excluding wall-time fields: all model/report content, the three
  AUROCs (`0.867275`, `0.8646277777777778`, `0.8860638888888889`), and evaluator
  checkpoint SHA-256 were identical. The accepted ensemble is
  `0.8726555555555556 ± 0.011687150998288242`.

## Current accepted-best values

- Fast-MC macro RMS relative four-vector error: `0.3466445061663238`.
- Geant4 adapter/reference macro RMS: `0.20779912872768125`.
- Fast-MC energy relative RMSE: `0.24941970758526708`.
- Fast-MC median angular error: `15.559848215446166 mrad`.
- Low-level three-seed validation C2ST AUROC: `0.8726555555555556 ±
  0.011687150998288242`.
- High-level control AUROC: `0.9290972222222222`; condition-only control:
  `0.5`.

These values describe the fixed validation bank. They do not establish Geant4
fidelity and cannot select or tune a generator checkpoint.
