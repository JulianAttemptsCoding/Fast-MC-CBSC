# V3 battery data-usage accounting quarantine — 2026-08-15

Status: **SCHEMA-V2 ACCOUNTING QUARANTINED; SCHEMA-V3 MIGRATION VERIFIED**.

The schema-v2 B0 metric payload is finite and valid, but its top-level
`train_events_used: 0` contradicts the 2,000 training events explicitly used as
the memorization nearest-neighbour reference. This is not test leakage and did
not affect training, selection, or any metric value, but it is inaccurate data
provenance and therefore a schema failure.

The original report (SHA-256 `96f53a74...`) and sidecar (`f3862775...`) are
quarantined. A hash-pinned migration produced schema-v3 report SHA-256
`0e7cc51d...`, explicitly accounting for 10,000 validation truth events,
10,000 generated events, 2,000 training-reference events used only for
memorization, and zero test events. Removing the added accounting metadata and
restoring the two source schema fields reproduces the quarantined report
exactly: metric-payload equivalence **PASS**.

The evaluator now emits schema 3 directly (`1f8b95ac...`); the controller and
presentation guard require the exact usage block. Focused local QA passed 67
tests with one known warning. Remote compilation and schema-version import
passed in `.venv_3090`; remote pytest was unavailable and the 4090 `.venv` was
not used from the 3090.

The automatically launched schema-v2 M0 wrapper PID 28495 was stopped before
report creation. Its surviving child PID 28497 was terminated exactly.
Generator training was untouched.

At 2026-08-16T03:35:11Z the unchanged workstation watcher accepted schema-v3
B0, recreated provenance sidecar SHA-256 `d6c9ae3f...`, and autonomously
launched `v3bat3-v3-m0-fresh-e19`. Local and remote request SHA-256 both equal
`06b67520...`; wrapper PID 30195 and evaluator GPU PID 30197 are running. Full
local QA passed 797 tests with 64 known warnings; compilation exited 0.

**PHYSICS VALIDATION NOT ESTABLISHED.**
