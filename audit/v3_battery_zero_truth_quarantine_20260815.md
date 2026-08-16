# V3 battery zero-truth metric quarantine — 2026-08-15

Status: **AFFECTED ARTIFACT QUARANTINED; CORRECTED RERUN RUNNING**.

The first fixed-bank B0 report computed relative energy error for zero-truth
events by dividing through a `1e-9` floor. Those events have no defined relative
error; the result was an RMSE of **533,203,392** and mean bias fraction
31,026,830. The corrected definition evaluates positive-truth events only and
records both included and excluded counts, which must sum to all 10,000 pairs.

The B0 report is retained locally and on DiCOS as
`dicos-f-02_epoch90.zero-truth-relative-error.json`, SHA-256
`c0600cafcb571e4a6960b731d4b972d5bc62e8f4ac1423271422d90e51f0b214`,
under the respective `quarantine/` directories. It is evidence only and cannot
enter comparison, selection, promotion, or publication. The B0 checkpoint and
the separate 4,000-pair external-validation gate are unaffected.

The in-flight S1 `battery5` process had loaded the same old evaluator. Stopping
PID 10181 terminated its wrapper but not the evaluation child. That child
completed at 2026-08-16T00:26:43Z and wrote the obsolete-schema S1 report. The
autonomous importer rejected it before local acceptance. The report is now
quarantined locally and remotely as
`v3-s1-axis_epoch19.zero-truth-relative-error.json`, SHA-256
`619241c7b40048f785b5b7d28a615b83ae0f944fd3b07c52320e7eaa035e77f1`.
Generator training was untouched.

The staged evaluator now has SHA-256 `3312e3e3…`, the identity-checking battery
CLI `5f9c369f…`, and the checkpoint probe `c265abf9…`. Remote QA passed **57
tests** with one known PyTorch warning. A clean B0 rerun is active as
`v3bat-dicos-f-02-e90`; M0 and S1 follow automatically. Test events used: **0**.

Failed attempts remain in the JSON twin: the 3090 environment lacked pytest;
the corrected tests then deliberately failed 2/57 against the old module; and
the first controller advance refused a content-hash/file-hash mismatch before
creating a request or job.

**PHYSICS VALIDATION NOT ESTABLISHED.**
