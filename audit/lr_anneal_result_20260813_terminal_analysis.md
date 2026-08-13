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

## The loss does not track fidelity

`dicos-e-02` e54 versus `dicos-f-02` e78, validation loss improving:

| metric | e54 | e78 |
|---|---|---|
| total response GeV (Wasserstein) | 0.50974 | 0.70446 |
| longitudinal profile (relative L1) | 0.17992 | 0.23088 |
| ECAL fraction (Wasserstein) | 0.02624 | 0.06300 |
| radial RMS mm (Wasserstein) | 1.50709 | 1.99955 |
| hit count (Wasserstein) | 52.35871 | 59.13216 |

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
