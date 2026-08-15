# V3 battery f-03 artifact quarantine — 2026-08-15

Status: **ARTIFACT QUARANTINED**.

The battery report labeled `dicos-f-03` epoch 111 actually evaluated the
inherited B0 epoch-90 checkpoint. Both `best.pt` files have SHA-256
`491284c7423f365230d34b0443f95aa4888ec770bdc673c4c979897bad8acbce`.
The report's near-identical metrics were therefore a provenance signal, not an
independent checkpoint result.

The affected JSON is retained under the local and DiCOS battery `quarantine/`
directories with SHA-256
`ff2ecca405593101c775d63271ede5cc53b7fd9b289a1416a0f7421af0b2ef59`.
It may not be compared, selected, promoted, or published as a valid evaluation.

`dicos-f-03` retained only inherited `best.pt` (epoch 90) and `last.pt` (epoch
114). Its within-segment lowest row was epoch 111, but that exact checkpoint no
longer exists. Epoch 114 will not be substituted under the old label.

The battery now checks the checkpoint's embedded epoch against the requested
report epoch before generation and records checkpoint and frozen-config hashes.
Focused QA passed **166 tests**; the full suite passed **772 tests** with 64
known PyTorch warnings; compilation passed; the metrics catalog passed all 131
graphics. The directory-listing bug
found during diagnosis also now fails closed on the backend's ambiguous empty
response instead of treating it as proof of an empty directory.

B0 is unaffected and valid. S1 `best.pt` independently reports embedded epoch
19 and SHA-256 `2235774417fcb916ab3becbfe3eef985bbd90e0ee24a090174736de5afd9ae31`;
its battery was still running and was not accepted at audit time. Test events
used: **0**.

**PHYSICS VALIDATION NOT ESTABLISHED.**
