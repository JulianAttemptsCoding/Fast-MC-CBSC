# V3 validation-battery autonomy — 2026-08-15

Status: **PASS; AUTONOMOUS QUEUE ACTIVE**.

The workstation watcher now advances the fixed-bank validation queue every 15
minutes. A row becomes eligible only after its full contiguous declared horizon
and all invariant reports; B0 enters through its separate passing terminal
gate. Checkpoint selection is validation loss only. Before launch, `best.pt`
must embed the selected epoch and metric, and its checkpoint/config hashes are
recorded. The config hash must also equal the frozen row registry, and all three
checkpoint/config provenance fields are mandatory in imported reports; the
evaluator repeats the epoch check.

The frozen controller contract has SHA-256 `2b5dad5e…`. It fixes 10,000
validation pairs, three evaluator seeds, 1,000 paired bootstrap replicates,
full structural/topology and memorization settings, and zero test events. It
records the validation bank's distinct internal content and byte-file hashes.

Only one `battery5`/`v3bat*` writer may run on the RTX 3090. Reports import
atomically only after remote/local hash agreement, schema-v3 incident-normalized
paired-response accounting, structural pass, all four separate C2ST families,
checkpoint provenance, and `test_events_used: 0`. The superseded
`reconstruction` family is rejected. A failed transaction is never retried or
overwritten automatically.

The provenance sidecar is mandatory, conflict checked, and recreated after an
interrupted report/sidecar handoff. The figure builder independently requires
that sidecar and the loss-selected epoch.

At initial activation, controller SHA-256 was `55544d93...` and the
presentation guard was `082f66fe...`.
Focused QA passed 153 tests, including 10 controller/identity tests; full
repository QA passed 795 tests with 64 known warnings, `compileall` exited 0,
and the 131-graphic catalog passed. Both S2 epoch-7 screening figures passed
visual inspection.

Watcher PID 24260 (parent 20384) is the sole matching Python refresher. It also
follows queued S3 automatically and rebuilds the screening summary, figures,
and metrics catalog after a report import. The first clean transaction,
`v3bat-dicos-f-02-e90`, is running; its local and remote request SHA-256 both
equal `72fdf4fb…`. Queue order is B0, M0, S1, then S2/S3 as their horizons
finish. The controller never starts generator training.

This record's first transaction was later quarantined after its exact-zero fix
proved insufficient for arbitrarily small positive truth deposits. The active
correction is report schema v2: `paired_response` is normalized by incident
kinetic energy and is explicitly not downstream reconstruction. Controller
SHA-256 is now `d86c1e03...`; evaluator SHA-256 is `3e561d50...`; presentation
guard SHA-256 is `f6d18624...`. At 2026-08-16T02:00:56Z the unchanged watcher
autonomously launched `v3bat2-dicos-f-02-e90`; local and remote request SHA-256
both equal `72fdf4fb...`, wrapper PID 23257 is running on the RTX 3090, and its
evaluator GPU PID is 23259. Test events used remain zero.

The subsequent schema-v2 container was quarantined because it declared zero
training events despite using a 2,000-event memorization reference. Schema v3
accounts for that reference explicitly. At 03:35:11Z the watcher accepted B0
report SHA-256 `0e7cc51d...`, recreated sidecar `d6c9ae3f...`, and launched
`v3bat3-v3-m0-fresh-e19` under wrapper PID 30195 / evaluator PID 30197.
Controller SHA-256 is `cae0523d...`; presentation guard is `d7f1bfeb...`.

End-to-end fail-closed proof occurred while B0 was running: the old `battery5`
wrapper's S1 child had survived the earlier wrapper stop and completed with the
obsolete evaluator. The controller rejected that report before acceptance
because corrected zero-truth accounting was absent. It is quarantined locally
and remotely with SHA-256 `619241c7...`; the corrected B0 job was unaffected.

**PHYSICS VALIDATION NOT ESTABLISHED.**
