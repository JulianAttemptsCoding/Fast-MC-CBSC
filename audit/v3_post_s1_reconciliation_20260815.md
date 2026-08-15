# Post-S1 reconciliation — 2026-08-15

Phase A of the post-2026-08-14 continuation. No training was launched, no paid
compute was used, and the test split was not opened. Starting commit
`7bb5c7d`, clean worktree, in sync with `origin/main`.

`PHYSICS VALIDATION NOT ESTABLISHED`.

## S1-axis is a negative result, and it is now in the record

| | Validation loss | Δ vs B0 |
|---|---|---|
| **B0** `dicos-f-02` e90 | **4.483768** | — |
| `dicos-f-03` e111 — matched 24-epoch re-heat, **no** axis | 4.491971 | +0.008203 |
| **S1-axis** e19 — same re-heat, **with** axis | **4.514053** | **+0.030286** |

S1 falls short of its matched control by **0.022082**. The run itself is clean:
24/24 invariant reports pass, every structural count zero, both closure
residuals inside the report's own effective tolerance, 24 fixed-condition
visualization payloads with zero test events.

**Disposition `S1_CONFIGURATION_NOT_PROMOTED`.** Under the frozen promotion rule
the simpler parent is retained and axis features stay off downstream.

**Causal status `S1_AXIS_CAUSAL_EFFECT_UNRESOLVED`.** `initialize_from`
transfers weights only, so S1 began with a fresh Adam while its control resumed
one; and S1 was judged on validation loss alone where the frozen v3 plan
required off-axis/topology targets, paired bootstrap, guard metrics and C2ST.
The executed configuration is a valid negative. The feature's causal question is
not closed by this run.

The shortfall is **17.5× the mean-absolute run-to-run reference** of 0.001259.
That is a magnitude statement about reproducibility. It is not a standard error,
a confidence interval, a p-value, or a sigma, and it licenses no significance
claim.

## The declared diagnostics gap is closed

`dicos-f-03` epochs 91–114 were replayed on the 3090 and imported: 24 metrics
files, each passing the validation-only split contract (train 0 / validation
4000 / test 0) and the full diagnostic QA gate. The pod-side queue is drained to
`done/`.

Diagnostic coverage is now contiguous over **epochs 48–114** with
`declared_diagnostic_gap: null`. Both stale carriers were removed — the gap
declaration and the 24 `unmeasured` overrides — and both are retained as visible
history in `closed_gaps[]` and `removed_overrides[]` rather than erased.

**Selection is unchanged.** B0 remains `dicos-f-02` e90 at 4.483767619419238;
f-03's own best of 4.491971 does not improve on it. What changed is that epoch
114 moved from `unmeasured` to `accepted`, and the family's latest accepted
epoch is now 114 at 4.588262.

The overrides could only be removed *after* the import. They were still accurate
before it: the metrics existed on the pod but had never been pulled locally.

## The prompt's Phase A step 2 was not followed literally

It directed importing S1 through `refresh_continuation_outputs.py`. That is the
right vehicle for `dicos-f-03` and was used for it. It is the wrong vehicle for a
v3 screening row, for four independent reasons:

1. it appends to `continuation_history.csv` under a **v2.2 family**, and a
   screening row changes the architecture and is *initialized from* rather than
   *resumed from* its parent — the family's loss figure would show a jump from
   4.4838 at epoch 90 to S1's re-heat epoch 0 at 4.6659 as though one model had
   regressed;
2. imported rows compete for that family's accepted best;
3. the exhibition builders hold a **closed four-family registry**
   (`build_exhibition.VARIANTS` and the `ORDER`/`LABELS`/`COLORS` maps), so the
   row would have raised or been silently dropped;
4. the script keys its epoch record off per-epoch distribution diagnostics, and
   S1 has none.

Implemented instead: a separate, reusable v3 screening record — declared row
registry, hash-verifying importer, aggregate history, figure/summary builder, and
a new exhibition scope. S2, S3, M0-fresh and R1-data4x drop into it with no
further structural work. A test now asserts that no screening variant or run tag
can ever appear in `continuation_history.csv` or in `build_exhibition.VARIANTS`.

## Two defects found and fixed

**The importer's invariant validator required an `epoch` field the reports do
not carry.** Caught on the first real import. The fix does more than remove the
check: `pass` is now re-derived from the structural counts rather than trusted,
and both closure residuals are checked against the report's own **effective**
tolerance — `max(absolute, relative × total_response)` — never against the 2e-5
absolute floor alone. Comparing against the floor is precisely the misreading
that ended `dicos-p10` on a structurally perfect epoch, and a test now pins that
a residual above the floor but below the effective bound is accepted.

**The exhibition gallery silently dropped graphics whose category had no section
label.** `category()` has always failed closed on an unclassified path, but the
gallery's label map failed **open**: an unlabelled category was still counted in
the inventory while never being rendered, so
`current_and_archive_galleries_contain_every_graphic` could report a complete set
over an incomplete page. Adding the new scope surfaced it. `scoped_gallery` now
raises on any cataloged category missing a label, with two regression tests.

## Verification

```
python -m compileall -q src vertex scripts tests exhibition     exit 0
PYTHONPATH=src python -m pytest -q                              598 passed  (558 -> 598, +40)
python exhibition/build_metrics_catalog.py                      131 graphics, status PASS
                                                                declared_diagnostic_gap null
                                                                current_reaches_latest_observed_epoch 114
```

The exact graphic-count guard moved `current` 76 → 78 for the two new screening
figures, with the reason recorded beside the earlier increases. The count stays
exact, so an unnoticed addition still fails. This is a declared increase, not a
relaxation.

## Still open after this phase

- **S1's checkpoint is format 3 with a null `architecture_version`** — the
  trainer saves a v3 run through the v2.2 path. The result stands; the file is
  not a valid adversarial-resume source and must never be rewritten. Phase B.
- **S1 has no distribution diagnostics.** It was launched through
  `dicos_train.py` rather than the campaign supervisor, so nothing was staged
  into `_diag/`. Recoverable only by evaluating the retained best checkpoint
  through the validation metric battery. Phase C.
- **The AUROC 0.843222 battery used 8,000 examples against a frozen 10,000-event
  minimum.** Directional evidence only; relabelled in Phase F.
