# Terminal analysis — `dicos-p8`, `dicos-p9`, `dicos-p10`

Machine-readable twin: `audit/continuation_20260804_terminal_analysis.json`.
Supersedes `audit/continuation_20260803_terminal_analysis.{json,md}` for this
family; the p7 runs are analysed there and are not restated here.

Date 2026-08-04. Backend DiCOS (ASGC). Source commit at launch `1fe95eb`.
Bank: 26,624 train / 6,656 validation / **0 test**, assignment
`084f0dfd…`, geometry `e22d4cfb…`.

## What this phase established

Two settings that had been treated as free parameters are not.

**Early-stopping patience must scale with the horizon.** `dicos-p8` asked for
24 epochs and stopped after 6. Its patience of 6 counted staleness against an
*inherited* best — 4.702458, reached at the end of the parent's anneal at
learning rate 1e-6. Restarting the scheduler to peak makes the model worse by
construction for several epochs before it can be better, so the counter was
already spent before the run had a chance to beat anything. The trajectory was
still descending monotonically when it stopped:

    epoch   17        18        19        20        21        22
    val     4.818539  4.836366  4.769665  4.742476  4.740615  4.735947

This is a statement about the stopping rule, not about the model. A constant
patience is wrong whenever the resumed best came from an annealed endpoint.

**Continuing a spent cosine beats restarting it.** `CosineAnnealingLR` is
periodic in `2*T_max`, so a scheduler resumed past its first anneal climbs
smoothly back toward peak and re-anneals — SGDR without the extra machinery.
`dicos-p9` differed from `dicos-p8` in exactly two declared settings,
`restart_scheduler_on_resume: false` and patience widened to the full horizon,
and improved **0.067238** over 24 epochs where p8 improved nothing over the
same nominal request. It is the largest single-run improvement of the phase.

    dicos-p9   epochs 16..39   EXIT=0   24/24 invariants   postflight pass
    best 4.635219681489869 at epoch 38
    best.pt  89cae275c092cecca5025159d766b920a412f96e83b4438b68bc1e6c4bd46b2a
    last.pt  98540e3dca3997ddaba34f5a1f964dd57a0a67ae9c3616fddaf4add7f06eb853
    wall 18,241 s wrapper / 15,550.6 s summed over epochs / 26,640 updates

The 2,690 s difference between wrapper wall and summed epoch time is dataset
construction plus 24 per-epoch visualization exports, not unaccounted compute.

## Standings

    family                      best val    at epoch   run
    calibrated_lr3e4            4.597152    22         dicos-p7   <- best
    calibrated_lr1e4            4.635220    38         dicos-p9
    calibrated_lr1e4_halfbatch  4.673036    21         dicos-p7
    calibrated_lr3e5            4.843471     8         dicos-r3

The lr3e4 lead is **0.038068** against a run-to-run resolution of about 0.02.
Real, but narrowing: it was 0.105331 two phases ago, and it closed because
`calibrated_lr1e4` was given more epochs (39 against 23), not because any
setting changed in its favour. That is the question `dicos-p10` tests.

## In flight

`dicos-p10`, `calibrated_lr1e4` on the RTX 4090, absolute epochs 39..62,
started 2026-08-04T02:44:11Z, resuming from the p9 epoch-38 best with the cosine
continued and patience 24. Frozen config
`4e246713113ac979edcd60f32990930bdb355645bf3d2d5b3c28aa215ffb7e2c`.

The frozen config was diffed field by field against its parent. Exactly thirteen
fields moved — project name, run dir, `epochs`, the four resume fields, and six
provenance fields. Every backend-portability invariant is unchanged: learning
rate, batch, accumulation, workers, precision, seed, solver steps, response
caps, geometry, splits, audit.

Epoch 39 completed at 4.663275 with learning rate 7.63e-6 — the cosine's
minimum, identical to the value p9 reached at its own epoch 39, which confirms
the scheduler state was restored rather than reset. From here the periodic
cosine should climb back toward peak.

**Note for whoever merges p10's history.** Resuming from epoch 38 re-runs epoch
39, and p9 already wrote an epoch 39 on a different branch. p9's epoch-39 row
must be dropped from `exhibition/data/continuation_history.csv` when p10's rows
land. The same thing happened between p6 and p9 at epoch 16. The duplicate-epoch
guard in `exhibition/build_continuation_loss_figures.py` will catch it; resolve
which branch is live rather than silencing the guard.

## Negative results, in full

These are not incidental and must travel with any favourable loss number.

- **C2ST AUROC sits at 0.77–0.92** at every checkpoint measured, against a
  threshold of 0.65. A classifier separates Fast-MC from Geant4 easily at every
  epoch this project has produced, and 24 epochs of improving validation
  objective did not move it.
- **Fast-MC emits roughly twice as many zero-response events as Geant4** —
  0.015–0.023 against 0.0097.
- **The loss and the distribution metrics disagree about which epoch is best**
  (p8: 22 against 21; p9: 38 against 33). Checkpoint selection follows the
  validation loss, as declared. The rule is not switched to whichever metric
  flatters a run.
- **Share flow is 42.2% of the weighted objective** — the largest component and
  the largest source of improvement.
- **The pilot bank is 4.3% of available training data.** A full-split run would
  likely dominate any family choice, and it remains untested.

`PHYSICS VALIDATION NOT ESTABLISHED.` Optimisation evidence on a validation
split only, zero test events.

## Faults found and fixed this phase

Recorded because the guards that now exist are the only reason these do not
recur.

| fault | damage | fix |
|---|---|---|
| flat `_diag/` overwrote metrics when two runs of one family shared an absolute epoch | p8's epochs 17–22 lost | namespace `_diag/<run-tag>/`; the run tag is now a required argument to `diag_producer.py`. p9's 24 files were moved before p10 could overwrite epoch 39 |
| the watch loop honoured `STOP` before draining the queue | would have dropped the last three epochs | exit only when `STOP` exists **and** pending is empty |
| energy-bin edges hard-coded with a top edge of 225 GeV | every 225–250 GeV event silently dropped from the figures | read edges from the checkpoint's own frozen config; raise if they do not cover the sampled range; report `events_outside_energy_bins` and `empty_energy_bins` |
| `wasserstein_1d` on the ~6.4M-value pooled spectrum never returned | 700 s CPU burned, process killed | `POOLED_SPECTRUM_CAP = 200_000`, deterministic, in the driver only — per-event metrics uncapped, `eval/metrics.py` untouched |
| a process probe matched itself | phantom trainer reported; the `kill -9` that followed killed the probe's own process group | build the search token at runtime, exclude own pid and parent pid |
| the continuation builder wrote its manifest under a fixed filename | a second family overwrote the first family's provenance | manifest named per family and run tag; the damaged historical directory left as-is, being an immutable record |

## A QA finding against this project's own documentation

`tests/test_qa_policy.py::test_active_guidance_has_no_hardware_permission_screen`
failed on `docs/GPU_BENCHMARKS.md`, a file added earlier in this phase. The
document wrote the 80 GB card's model name into active guidance. That token is
forbidden there because an earlier revision of the policy used access to that
card as a permission screen, and the token check is what keeps the screen from
returning.

The card was renamed to its capacity descriptor throughout, and the document now
records why the check exists. **The test was not exempted and not weakened**,
which is the only acceptable resolution: the guard caught exactly what it was
built to catch.

## Fleet

As of 2026-08-04 the fleet is the RTX 4090 and the RTX 3090. The user has
retired the 80 GB datacentre pod. Its measured figures remain valid history —
they are what withdrew the erroneous "4090 is 3.2× that card" claim, the true
solo ratio being 1.524× — but that hardware is not available and no plan should
assume it. `docs/GPU_BENCHMARKS.md` is the single source of truth for
throughput and cost.
