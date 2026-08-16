# V3 battery schema-v2 publication — 2026-08-15

Commit `9bcc2fd` (`fix(eval): normalize paired response`) was pushed to
`origin/main` as `f7a3f31..9bcc2fd`. Pre-push divergence was `0 1`.

Report schema v2 replaces the unstable deposited-truth relative-error
denominator with `paired_response`, normalized by incident kinetic energy. The
quantity is a paired stochastic detector-response residual, not downstream
incident-energy reconstruction. The evaluator SHA-256 is `3e561d50...`, the
controller is `d86c1e03...`, and the presentation guard is `f6d18624...`.

Verification: JSON validation passed; compilation exited 0; the full local
suite passed 795 tests with 64 known warnings; synchronized remote QA passed 57
tests with one known warning; the 131-graphic catalog passed; and the refreshed
screening loss figure passed visual inspection through S2 epoch 10. Test events
used: **0**.

At publication, autonomous B0 job `v3bat2-dicos-f-02-e90` remained RUNNING on
the RTX 3090 under wrapper PID 23257. Workstation watcher PID 24260 held its
live lock, S2-response was training, and S3-first remained queued. No manual
controller advance was used.

Failed attempts are retained in the JSON twin: stale remote test deployment,
one local pytest invocation without `PYTHONPATH=src`, one wrong-pod health
query, and unavailable narrow process-tree tools.

**PHYSICS VALIDATION NOT ESTABLISHED.**
