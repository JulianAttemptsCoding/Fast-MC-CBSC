# CBSC-ZDC v2.2 Implementation QA Report

## Scope

This report covers the active v2.2 code, CLI, implementation guide, synthetic execution path, and packaging preparation. It does not claim production ROOT fidelity or Geant4 agreement.

## Inputs reviewed

- four supplied independent audits, preserved verbatim under `audit/SUPPLIED_AUDIT_*`;
- original v2 repository and v2.1 working materials;
- sample ROOT schema fixture;
- active v2.2 source and configs;
- primary methodology and official framework documentation listed in `references/PRIMARY_SOURCE_REGISTER_V2_2.md`.

Findings were accepted only when supported by algebra, code, an executable counterexample/test, production contract logic, or a primary source. Conflicting audit verdicts were resolved finding by finding.

## Major implementation corrections completed during this round

1. Fixed the longitudinal flow total-feature tensor shape from `[B,1]` to `[B,1,1]` before layer expansion.
2. Fixed in-place broadcast failure in count-feasibility masks by expanding and cloning the geometry mask to batch shape.
3. Replaced all-`-inf` softmax behavior for zero-count layers with an explicitly zero masked normalization.
4. Reclassified sampled continuous response values clamped to exactly zero as no-response events.
5. Removed a second support selection during decoding by passing the already sampled support mask into the exact decoder.
6. Added a float32 serialization tolerance around the neutron rest-energy boundary while retaining strict mass-shell checks.
7. Prevented shared-condition-encoder catastrophic forgetting in isolated stages: only response and joint stages train it by default; later isolated stages require a previous checkpoint.
8. Corrected gradient accumulation for a final incomplete accumulation window.
9. Added nonfinite total-loss and gradient-norm hard failures.
10. Added documented DataLoader worker seeding.
11. Removed the misleading `cascade` training stage, which had been an alias for teacher-forced joint training rather than true generated-condition exposure.
12. Made underpopulated/missing primary energy bins fail evaluation instead of disappearing from `all(...)` gate logic.
13. Added truth-half distributional floors and a broader high-level metric report.
14. Added a cloud staging/training/upload entry point and Vertex submission helper.
15. Added an agent-facing exact implementation manual, loss-weight protocol, data contract, evaluation protocol, Vertex runbook, troubleshooting guide, wrappers, and container definition.
16. Strengthened configuration validation so stage, ranges, positive training controls, and the exact nine loss-weight keys fail early.
17. Made loss-weight calibration DataLoader order deterministic from the frozen seed.
18. Replaced non-standard JSON `NaN` for empty positive-cell comparisons with explicit `null`, with strict-JSON regression coverage.

## Executed QA

### Repository tests

```text
18 passed
2 warnings
```

Warnings: PyTorch Transformer nested-tensor performance notice caused by pre-norm encoder configuration. No numerical or assertion failure.

Branch-aware coverage from the release suite is 66% overall across source and tests (1,592 statements and 300 branches). Statement coverage is approximately 70% and branch coverage approximately 48%. Low-coverage areas remain production ROOT I/O, full training/evaluator orchestration, and cloud paths; coverage is not represented as physics evidence. The machine-readable report is `coverage.json`.

Covered contracts include:

- kinetic versus total energy;
- neutron mass shell and float32 rest-energy serialization;
- exact support counts, zeros, threshold floor, and closure;
- zero-count decoding;
- one-time preselected support use;
- group split integrity;
- sparse shard materialization;
- untrained structural invariants;
- fixed loss-weight calibration;
- configuration rejection paths;
- explicit flow-time dependence.

### Synthetic CLI path

Successfully executed on a synthetic dataset:

- data/geometry generation;
- deterministic split;
- full selected-split audit;
- config freeze and hash capture;
- one-epoch joint training;
- checkpoint save and reload;
- fixed-condition sampling;
- structural invariant QA;
- timing benchmark;
- gradient-norm loss calibration;
- validation evaluation that correctly failed physics gates for a tiny untrained/undertrained model.

Example structural result from the final release smoke artifact:

```text
nonfinite = 0
negative = 0
outside_valid_support = 0
support_mask_mismatch = 0
count mismatch = 0
layer closure max = 0
pass = true
```

A synthetic fidelity failure is expected and is not converted into a pass.

## Sample ROOT fixture evidence

- file type: ROOT version 63002;
- SHA-256: `3d6a78f5fb586eb611c30f0bf902e63f09290eac7791fe84f9396aa05a590e1d`;
- string-level branch evidence matches the sample schema for event tree, MC particle four-momentum, and ECAL/HCAL cell ID and energy branches.

Numeric ROOT inspection was not executed in this environment because Uproot/Awkward were unavailable. Therefore branch types, event counts, numerical units, vertex constancy, exact channel count, and real distributions remain production gates.

## Remaining non-code blockers

1. Confirm production ROOT branches and units with Uproot/Awkward.
2. Confirm primary-neutron selection semantics.
3. Establish whether ROOT files correspond to independent Geant4 run/seed groups.
4. Freeze the complete 6,790-node geometry, including zero-hit valid cells.
5. Convert and audit the full 765k-event corpus.
6. Run target-GPU memory/throughput pilot.
7. Determine final loss weights and learning rate using validation only.
8. Train all six matched final runs.
9. Implement or connect experiment-specific low-level C2ST, reconstruction, and memorization analyses.
10. Reproduce required baselines.
11. Measure Geant4 and FastMC end-to-end speed on disclosed hardware.

## Final software verdict

The package is a substantially complete CLI-first implementation scaffold and agent runbook. It is ready for production schema/geometry setup and controlled training. It is not yet a validated ZDC FastMC.
