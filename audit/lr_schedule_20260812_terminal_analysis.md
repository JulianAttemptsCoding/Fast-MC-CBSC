# Learning-rate schedule: annealing over 6 epochs, not the declared horizon

## Disposition

`QA FINDING`. A declared experiment (`camp-20260812-lr3e4-anneal`) is training
to test the correction. No result yet and none claimed.
`PHYSICS VALIDATION NOT ESTABLISHED`.

## The finding

`_runs/calibrated_lr3e4_dicos-e-02/checkpoints/best.pt` carries

    scheduler_state:  T_max=6660,  eta_min=1e-06,  base_lrs=[0.0003]
    config beside it: training.epochs=55

At the measured **1110 updates/epoch**, `T_max=6660` is exactly **6.000
epochs** — while the config it sits beside declares a 55-epoch horizon.
`CosineAnnealingLR` is periodic in `2·T_max`, so the realised schedule is a
**12-epoch sawtooth**, not the single long anneal the horizon implies.

The mechanism is `checkpoint.py:75`, which restores `scheduler_state`
unconditionally on resume. `T_max` is part of that state dict, so an
ancestor's 6-epoch horizon has been inherited by every continuation of this
family regardless of what each new config asked for. Nothing was hand-edited;
the value simply propagated.

**This is read off the record, not inferred from the loss.** The trainer logs
the realised per-epoch learning rate:

| | absolute epochs | spacing |
|---|---|---|
| peaks (3.0e-4) | 28, 40, 52 | 12, 12 |
| troughs (1.0e-6) | 34, 46 | 12 |

### Loss tracks LR phase, not progress

| phase | epoch | validation loss |
|---|---:|---:|
| trough | 34 | 4.550331 |
| trough | 45 | 4.519305 |
| trough | 47 | **4.512721** |
| peak | 40 | 4.642563 |
| peak | 51 | 4.654804 |
| peak | 52 | 4.633719 |

Within-cycle swing ≈ **0.14**. Real trough-to-trough gain ≈ **0.04**
(e22 4.597152 → e34 4.550331 → e47 4.512721). The model is genuinely learning
about 0.04 per cycle, but each cycle re-heats to the full peak and gives most
of it back. **Every "best" this family has recorded is whichever trough
happened to be deepest.**

## It caused a false stop

`camp-20260810-lr3e4` ended `campaign_complete` because `dicos-e-02`'s best
(e47) was 7 epochs behind its last (e54) — outside the 6-epoch improvement
window. But **epoch 54 sat mid-descent at lr 2.25e-4**, with the next trough
due near epoch 58. A window shorter than the learning-rate period measures
where in the cycle a segment stopped, not whether the family converged.

`dicos-p8` is the same class of failure from the patience side: stopped at 6
of 24 epochs, before reaching the low-LR end of its own anneal.

This re-frames a standing note. `CLAUDE.md` records that a scheduler restart
"produced nothing" where continuing produced p9's 0.067. That comparison is
**confounded** — the restart run was ended early by patience and never reached
the part of the anneal under test. It is not evidence against restarting with
patience equal to the horizon.

## The change, declared

`configs/campaigns/campaign_20260812_lr3e4_anneal.json`, prefix `dicos-f`:

- **`restart_scheduler_on_resume: true`** → `trainer._restart_cosine_scheduler`
  rebuilds the scheduler with `T_max = updates_per_epoch × (epochs −
  start_epoch)`, i.e. *this segment's own horizon*. One 24-epoch anneal
  instead of four 6-epoch sawteeth.
- **`improvement_window: 12`** (was 6) — at least one full former LR period,
  so the stopping rule cannot fire on phase.
- **`segment_epochs: 24`, patience 24** — the anneal's low-LR end is the part
  under test; patience must not end the run before it.

Learning rate (3e-4), batch, seed, optimizer, accumulation, loss weights,
geometry, splits and both closure tolerances are **unchanged**. The schedule's
*shape* is the only moving part. `DECLARED EXPERIMENT` — not directly
comparable to anything frozen before it.

**No guard was weakened.** `training.restart_scheduler_on_resume` was already
in `ALLOWED_CONFIG_DELTA`; `dicos_campaign.py` merely hardcoded `False`. It is
now `campaign.get("restart_scheduler_on_resume", False)`, so `camp-20260805`
and `camp-20260810-lr3e4` mean exactly what they meant. Three tests pin it,
including that the schedule's *shape* is allowlisted while its *peak*
(`training.learning_rate`) is not.

## Launch

Dry-run first. Its `config_delta` moved only allowed fields, and
`training.learning_rate` **does not appear in it**:

    training.restart_scheduler_on_resume   False -> True
    training.epochs                        55 -> 72
    training.early_stopping_patience       20 -> 24
    training.resume_{,best_}from_sha256    -> 43fcf86c…  (dicos-e-02 best, e47)

    frozen        e0978e724d13e8e2a7141dec36852d89ba86d61a9ea153923b300ff9ff419658
    template      89590dae37925b12bed0f3518268a54730a2ba6ef204dd755fad169d61d5a00b
    parent frozen 82d00f25a1d3e4ca4a3f751f5ed9278e423263dd54a98000bba36aa9f2449e0e

Target 72 = 47 + 1 + 24, resuming from `dicos-e-02`'s **best** on both slots.

Launched `camp0812-anneal` (pid 3526), run tag `dicos-f-01`. Verified rather
than assumed: GPU **96% / 12057 MiB**, `environment.json` records
`shard_cache_size: 0`, and a `/proc` scan shows exactly **one** producer
(pid 3658, ppid 3528 = the supervisor). A second pid in an earlier scan was a
transient child, gone on re-check — rule 24 holds. Watcher restarted on the
new plan, pid 34656, 600 s.

## What this will and will not show

It tests exactly one thing: whether annealing once over the declared horizon
beats the sawtooth's 4.512721.

**Expect the early epochs to be worse than 4.512721** — the restart re-heats
to 3e-4 from a checkpoint annealed to 2.1e-5. That is the same jump the
sawtooth already performed every 12 epochs; the difference is that the descent
now has 24 epochs rather than 6. A negative result is a real result and will
be reported with the complete trajectory.

## Operational note

`dicos.py exec "LD_LIBRARY_PATH=/usr/lib64 …"` **fails from Git Bash on this
workstation and never reaches the pod** — MSYS rewrites `/usr/lib64` to
`C:/Program Files/Git/usr/lib64`, the space splits the argument, and the local
shell reports `Files/Git/usr/lib64: No such file or directory`. The prefix is
unnecessary for the supervisor: `launch()` sets it for the trainer subprocess
and the supervisor is CPU-only. Keep it only for a one-off
`.venv/bin/python -c` that genuinely needs CUDA.

## Verification

    PYTHONPATH=src python -m compileall -q src scripts tests   exit 0
    PYTHONPATH=src python -m pytest -q                         338 passed (335 -> 338)
    dry-run config_delta                                       allowed fields only,
                                                                 learning_rate absent

## Still open

- **A publication is owed.** `calibrated_lr3e4`'s lowest verified loss changed
  to 4.512721 while the live selection is still
  `dicos-p9-calibrated-lr1e4:joint:0038`. Deliberately not made here —
  `dicos-f-01` may move the number again within a day.
- If annealing over the real horizon helps, ask the same question of
  `calibrated_lr1e4_halfbatch` and `calibrated_lr3e5` as a separate declared
  campaign rather than folding it into this one.
