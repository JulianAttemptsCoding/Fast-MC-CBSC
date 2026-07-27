# Compute extension r2 terminal analysis — 2026-07-27

The two authorized E2→E4 continuation jobs succeeded on separate on-demand
T4s. All four new immutable epoch snapshots passed independent checkpoint,
finite-tensor, paired-recovery, history, invariant, fixed 50-by-5 validation,
selection-hash, resource, and zero-test gates.

| Family | E2 parent | E3 | E4 | E4 vs E3 | E4 vs E2 |
|---|---:|---:|---:|---:|---:|
| Calibrated LR 3e-5 | 4.927671 | 4.939322 | 4.897327 | 0.850% better | 0.616% better |
| Calibrated LR 1e-4 | 4.878822 | 4.911421 | 4.827105 | 1.717% better | 1.060% better |

E3 regressed by 0.236% and 0.668%, respectively, before E4 recovered to a
new best for both families. Additional compute therefore improved the frozen
weighted validation objective over the requested two-epoch horizon, but the
trajectory was not monotonic.

Both E4 runs changed all 200 model tensors relative to their E2 parents,
reached optimizer step 5,550 and restarted-scheduler step 2,220, preserved
25.0186% T4 memory headroom, and passed fresh-model best-checkpoint reload.
Postflight 8/8 timing was 294.797 ms/event for LR 3e-5 and 278.449 ms/event
for LR 1e-4. No nonfinite, negative, count, support, or closure gate failed.

The fixed-sample diagnostics also improved in response bias and longitudinal
profile L1 from E3 to E4, while hit-count bias remained mixed. These 50
validation conditions and five stochastic draws per condition are descriptive
visual evidence, not a physics gate.

The latest two jobs consumed 5.199722 T4-hours. At the predeclared
conservative rate of $0.85/hour, they add $4.4198. The cumulative conservative
ledger is $53.1006/$100, leaving $46.8994.

The exhibition now contains complete E0–E4 train/validation curves for all
four calibrated families and regenerated fixed-condition figures. The public
site retains exactly one accepted E4 checkpoint per calibrated family.
Commit `784fe6bf572cb6285fb2e92a54858883da1c0e6e` deployed successfully in
workflow `30285942671`. The live manifest SHA-256 is
`3ab56be2af72b386fa2e553d48aea9e9dbb361e19621c35639e8e61b1f3c8bfe`;
all four gzip hashes and decompressed validation contracts were independently
verified. Interactive browser QA remains blocked by the existing local browser
kernel `os error 3`; HTTP, artifact, seven unit tests, TypeScript, and Vite
production-build checks pass.

The result supports taking the model to faster hardware for longer
optimization experiments if desired. It does not overturn the historical
frozen A100 screening result, establish Geant4 fidelity, authorize test
evaluation, or authorize another Vertex job.

Final disposition:

```text
structural_and_optimization_QA=PASS
more_compute_validation_hypothesis=SUPPORTED_FOR_ALL_4_CALIBRATED_FAMILIES
physics_validation=NOT_ESTABLISHED
historical_frozen_A100_screening=NO-GO_UNCHANGED
test_evaluation=BLOCKED_NOT_OPENED
further_Vertex_jobs_authorized=false
```
