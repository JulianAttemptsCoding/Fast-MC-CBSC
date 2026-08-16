# V3 battery response-denominator quarantine - 2026-08-15

Status: **SECOND B0 REPORT QUARANTINED; SCHEMA-V2 CORRECTION DEPLOYED**.

Excluding exact zero-truth deposits did not make eventwise deposited-response
relative error valid. Positive truth deposits can be arbitrarily close to zero.
The corrected B0 run therefore still produced an RMSE of 123,548.671875 and a
mean bias fraction of 3,344.763916 despite correctly counting 9,907 positive and
93 zero-truth events. The report and its provenance sidecar are quarantined;
the remote/local report SHA-256 is `cfa0b6d0...`.

The previously cited 0.210445 external metric is downstream incident-energy
reconstruction and is not comparable to a paired deposited-response residual.
Report schema v2 removes that ambiguity. Its `paired_response` family divides
the generated-minus-truth deposited response by the predeclared positive
incident kinetic energy and labels the result as a paired stochastic response
diagnostic, not reconstruction accuracy. The evaluator SHA-256 is
`3e561d50...`; the previous `3312e3e3...` source is archived on DiCOS.

The automatically launched M0 evaluation was stopped before report creation.
Because stopping wrapper PID 21912 left GPU child PID 21914 alive, that exact
child was terminated and its disappearance from `nvidia-smi` was verified.
Generator training was untouched.

At 2026-08-16T02:00:56Z the unchanged 900-second workstation watcher
autonomously launched the distinct schema-v2 transaction
`v3bat2-dicos-f-02-e90`. Its local and remote request SHA-256 both equal
`72fdf4fb...`; RTX-3090 wrapper PID 23257 and evaluator GPU PID 23259 are
running. An initial health query accidentally selected the 4090 because the
3090 config was omitted; it changed nothing and was corrected immediately.
The 3090 image has neither `pgrep` nor `pstree`, so the narrowly targeted probes
failed and the job-wrapper state plus exact GPU PID were recorded without a
broad process listing.

QA: 117 focused local tests passed; the full local suite passed 795 tests with
64 known warnings; synchronized remote QA passed 57 tests with one known
warning; compilation exited 0; and the 131-graphic catalog passed. Test events
used: **0**. The refreshed validation-loss figure passed visual inspection
through S2 epoch 10. One final local pytest invocation omitted the required
`PYTHONPATH=src` and stopped during collection with 13 import errors before any
test ran; the documented-environment rerun passed all 795 tests.

**PHYSICS VALIDATION NOT ESTABLISHED.**
