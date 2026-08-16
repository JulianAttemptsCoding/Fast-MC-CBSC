# V3 battery schema-v3 publication — 2026-08-15

Commit `dce4455` (`fix(eval): account battery data usage`) was pushed to
`origin/main` as `5083904..dce4455`; pre-push divergence was `0 1`.

The accepted B0 report now uses schema 3 and explicitly accounts for 10,000
validation truth events, 10,000 generated events, the 2,000-event training
reference used only for memorization, and zero test events. Report SHA-256 is
`0e7cc51d...`; provenance sidecar is `d6c9ae3f...`. Structural invariants pass.
Paired-response RMSE is 0.0459828; high-level C2ST remains 0.774766 against the
0.65 diagnostic target, so physics validation is not established.

Verification: 67 focused tests passed with one known warning; the full suite
passed 797 with 64 known warnings; compilation exited 0; remote compilation and
schema-version import passed; the 131-graphic catalog passed; and the refreshed
screening loss figure passed visual inspection through S2 epoch 13.

At publication, watcher PID 24260 held its live lock, schema-v3 M0 battery job
`v3bat3-v3-m0-fresh-e19` remained RUNNING under wrapper PID 30195, S2-response
was training, and S3-first remained queued. No manual controller advance was
used.

**PHYSICS VALIDATION NOT ESTABLISHED.**
