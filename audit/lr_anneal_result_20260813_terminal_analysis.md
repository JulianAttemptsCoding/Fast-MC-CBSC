# Terminal analysis: LR anneal result, staged-checkpoint defect, diagnostics gap

Date: 2026-08-13. Campaign `camp-20260812-lr3e4-anneal`.

## Result

`calibrated_lr3e4` improved from **4.512720740207991** (e47, `dicos-e-02`) to
**4.483767619419238** (e90, `dicos-f-02`), a gain of **0.028953**. Two
independent 24-epoch continuations from e90 both failed to beat it, so the
configuration has converged. Single seed.

## Nondeterminism

`dicos-f-04` re-ran `dicos-f-03`'s exact epoch range from the same checkpoint.
Restricted to epochs 91-92, where their learning rates still agree within 2%,
the validation losses differ by **0.000654 mean absolute** and **0.001259 max**.
The improvement is 20-40x that.

An estimate of 0.013275 taken over all 24 shared epochs is **withdrawn**: it was
confounded by the horizon defect below and is not a noise floor.

## Staged-checkpoint defect

`parent_last_epoch` came from the segment's own best history row while `best.pt`
was staged. A segment that never beats its inherited best leaves `best.pt`
untouched, so the two disagree. `dicos-f-03` reported best epoch 111 while its
`best.pt` was still `dicos-f-02`'s epoch 90 — hash
`491284c7423f365230d34b0443f95aa4888ec770bdc673c4c979897bad8acbce` identical
across both and the staged `dicosf04_best.pt`.

`dicos-f-04` therefore re-ran epochs 91-114, and because `epochs_absolute` was
computed from 111 the restarted cosine annealed over 46 epochs instead of the
declared 24. At epoch 114 its learning rate was 1.3487e-04 against
`dicos-f-03`'s 1.0000e-06, a factor of 135. Undeclared variant under AGENTS.md
28; excluded from the live lineage, retained as evidence. Cost 5.8 GPU-hours.

## Overfitting — established

Live lineage, epochs 48-114, n=67:

| series | r vs epoch | t | verdict |
|---|---|---|---|
| train loss | -0.805 | 10.93 | falling, p<0.001 |
| validation loss | -0.358 | 3.09 | falling, p<0.05 |
| train-to-validation gap | +0.560 | 5.46 | widening, p<0.001 |

Train improved 0.13436 against validation's 0.02324, a ratio of 5.8. The gap
drifted +0.04131 between halves, from -0.03729 mean (validation below train) to
+0.00402 (validation above). The total validation gain across all 67 epochs is
smaller than the one-off gain from correcting the learning-rate schedule.

## The fidelity claim is WITHDRAWN

An earlier version of this file stated that the loss improved while the physics
got worse, from `dicos-e-02` e54 against `dicos-f-02` e78. **Withdrawn**: two
points out of a series whose adjacent epochs swing 0.36-0.75 on the same metric.

Tested across epochs 48-86, n=39, where t>2.02 is p<0.05:

| metric | r vs epoch | t | significant | r vs validation loss |
|---|---|---|---|---|
| total response | -0.019 | 0.11 | no | +0.347 aligned |
| longitudinal L1 | +0.265 | 1.67 | no | +0.013 |
| ECAL fraction | +0.315 | 2.02 | borderline | -0.400 misaligned |
| radial RMS | +0.258 | 1.63 | no | -0.110 |
| hit count | -0.061 | 0.37 | no | +0.001 |

No significant trend, mixed correlation with the loss, per-epoch scatter 16-45%.
At 4,000 events per epoch these diagnostics cannot resolve a fidelity trend in
either direction. Misalignment is neither shown nor excluded.

## AUROC

Measured on two checkpoints only, both epoch <=38; nothing in the f-chain
(48-114) has been evaluated.

| checkpoint | validation loss | AUROC | high-level AUROC |
|---|---|---|---|
| `dicos-c-02` e34, lr3e4 | 4.550331 | 0.8624 +/- 0.0147 | 0.8947 |
| `dicos-p9` e38, lr1e4 | 4.635220 | 0.8727 +/- 0.0117 | 0.9291 |

Different families, two points. Whether the 4.550 -> 4.484 improvement moved
AUROC is unmeasured. Both sit far above the 0.65 target.

## Diagnostics gap

Epochs 79-114 have loss evidence and no distribution metrics, because the 3090
diagnostics pod ended between epochs 78 and 79 while training continued. Every
queued checkpoint survived, so the gap is recoverable; a replay is running.
`exhibition/data/diagnostic_gaps.json` and the `unmeasured` overrides in
`exhibition/data/continuation_status.json` carry the state and should be removed
once the replay lands.

## Verification

    compileall           exit 0
    pytest -q            350 passed
    metrics catalog      124 graphics, PASS, current_reaches_latest_observed_epoch 78
