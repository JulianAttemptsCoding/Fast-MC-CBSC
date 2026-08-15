# Response-loss measure correction — 2026-08-15

Status: **PASS**.

The legacy response head parameterizes a mixture in
`y=log1p(T/response_scale_gev)` but historically returned `-log p(y)`. The v3
bounded spline returns `-log p(T)` in deposited-energy GeV. Their raw totals
were therefore not comparable. The required identity is:

```text
NLL_T = NLL_y + log(response_scale_gev + T).
```

The correction is target-only, so it changes neither parameter gradients nor
the best epoch within a fixed run. The validation-only audit reproduced the
trainer's exact mean-of-batches reduction over 4,096 validation events (4,046
visible, 683 batches, zero empty-visible batches) and found a response-component
offset of 2.622334464228 and a weighted total-loss offset of
**0.421936354321**. Test events used: **0**.

Historical raw → common-measure values are B0 4.483768 → 4.905704,
M0-fresh 4.513572 → 4.935508, and S1-axis 4.514053 → 4.935990. S2 already uses
the GeV-density measure; through epoch 6 its best is 4.978104, or +0.042596
against corrected M0. The earlier raw cross-mode gap was invalid.

The legacy head now includes the Jacobian in code. The tested source SHA-256 is
`0bee892ca06dc7789a146dca202721e0dd90a98d9651f361830b8ff1ce7f3a79`.
It was deployed to the staged DiCOS `repo/src/` tree before S3 launched; the
actual pre-change file is retained under `_v3/code_archive/` with SHA-256
`d02727c5ba2ad74431f0e45dab4a9e641bf6eee08b5332af762b0605c773c1cc`.
The live S2 spline process remained untouched. Remote focused QA passed all
three response-likelihood tests.

Import, summary, watcher, figures, registry, and active documentation now
preserve raw provenance beside common-measure values and forbid raw cross-mode
comparison. The corrected figures were visually inspected and are legible.
The read-only workstation watcher was restarted once so its long-lived process
loaded the corrected logic. Process-tree proof found exactly one matching Python
writer: PID 28344 (parent 29192); its status reports raw and common values and
the fair M0 delta.

The audit also retains the duplicate-reader orchestration correction, the
initial unused-path deployment and exact cleanup, the initial missing
`PYTHONPATH`, the first overbroad gradient test, the unsupported PowerShell
timestamp flag, and the failed mojibake-sensitive patch attempt.

Final QA: focused tests **90 passed**; full suite **782 passed** with 64 known
PyTorch warnings; remote response tests **3 passed**; compilation exit 0;
metrics catalog **131 graphics, PASS**; `git diff --check` exit 0 with
line-ending notices only.

**PHYSICS VALIDATION NOT ESTABLISHED.**
