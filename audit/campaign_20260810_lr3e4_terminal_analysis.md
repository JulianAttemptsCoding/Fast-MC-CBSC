# Campaign `camp-20260810-lr3e4` — declared, launched, training

## Disposition

`QA PASS` for everything checked this session. `dicos-e-02` is training on an
L40S (the 4090 was retired by the owner mid-session), confirmed at 93–96% GPU
utilization with its first epoch in flight. No scientific conclusion is
available and none is claimed. `PHYSICS VALIDATION NOT ESTABLISHED`.

## Declaration

**Question.** Does `calibrated_lr3e4` — the project's overall champion at the
end of camp-20260805 — keep improving when given further 20-epoch segments
from its own best checkpoint?

**Owner's instruction, 2026-08-10.** Continue training `calibrated_lr3e4` (the
name only; use whatever hyperparameters the family's own frozen template
already carries), and ensure the pipeline stays smooth around it.

**Rule, unchanged from camp-20260805.** Resume from the parent's best
checkpoint on both resume slots, hash-verified. 20-epoch segments,
`early_stopping_patience` equal to the segment horizon,
`restart_scheduler_on_resume: false`. Continue while
`latest_epoch - best_epoch <= 6`; this chain has no next family, so the rule
otherwise stops rather than advances.

**Boundary.** Optimization evidence on the pilot bank only. Nothing about
Geant4 fidelity, three-seed behaviour, or untouched-test performance. The
76,300-event test split stays sealed.

## Parent, verified on the host

| family | run | best epoch | validation loss | best.pt SHA-256 |
|---|---|---:|---:|---|
| `calibrated_lr3e4` | `dicos-c-02` | 34 | 4.5503306071196254 | `5995c86a…c2089` |

`parent_last_epoch = 34` is the BEST epoch, not dicos-c-02's own last-written
epoch (~42–43) — the resume continues from the best checkpoint, as every prior
segment in this project has.

Verified directly on the pod via the 3090 (the shared filesystem makes this a
read, no 4090 needed): `sha256sum` on both checkpoint files, not taken from
memory or an old note.

## Provenance reconstructed while declaring this

`dicos-c-01` — the family's first camp-20260805 segment — is confirmed
**aborted** (`_runs/aborted_c01_producer_path_and_shard_cache/`ed on the pod),
on exactly the producer-`ModuleNotFoundError` and shard-cache-starvation bugs
fixed during that session. `dicos-c-02` was the clean restart from the same
parent (`dicos-p7` best, epoch 22): its own frozen config's
`resume_from_sha256` matches `dicos-p7`'s best hash exactly, confirming it
never resumed from `dicos-c-01` — which produced no checkpoint to resume from.

## New segment plan

`configs/campaigns/campaign_20260810_lr3e4.json`, `run_tag_prefix: "dicos-e"`
— a fresh prefix, checked against the pod's own `_runs/` listing to confirm no
`dicos-e-*` tag exists yet, so it cannot collide with any of the five
`dicos-c-*` directories camp-20260805 already wrote.

`parent_frozen` points at `dicos-c-02`'s own frozen config
(`prep/configs/frozen_calibrated_lr3e4_dicos-c-02.yaml`), not the family's
original `dicos-p7` baseline — per the project rule to diff every new frozen
config against its immediate parent. `parent_template` is unchanged (it
carries architecture/loss/schedule, not per-segment provenance). If launched
as declared, the absolute epoch target is 55.

**Launched, as `dicos-e-02`.** The owner retired the 4090 entirely mid-session
and provided a new L40S pod (port 30568) on the same credentials slot. The
existing `.venv` (pinned `torch==2.6.0+cu124`, unchanged) failed to
initialize CUDA there — `cudaErrorSystemDriverMismatch` (803) — traced to a
0-byte `libcuda.so.1` stub on the pod's default loader path; the real,
driver-matched library only exists under `/usr/lib64`. Fixed in `launch()`
by prepending `/usr/lib64` to `LD_LIBRARY_PATH`, verified live
(`torch.cuda.is_available()` False → True, same pinned build).

The fix was written and locally tested but **not committed before the first
real launch attempt** (`dicos-e-01`), which therefore ran the pod's stale
pre-fix code and failed identically — a clean `RuntimeError`, exit 1, 0
epochs, 0 checkpoints, 0 evidence lost. Archived rather than deleted
(`_runs/aborted_e01_cuda_stub_before_fix`, `_diag/aborted-e01`), matching the
`aborted_c01_producer_path_and_shard_cache` precedent from 2026-08-05.
Committed (`2eddba1`), pushed, re-pulled on the pod, re-verified, relaunched.
The supervisor's own persisted state advanced the run tag to `dicos-e-02`
without any collision or manual bookkeeping.

## Bug fixed this session: no timeout on the pod-call subprocess

`scripts/refresh_campaign_outputs.py:_dicos()` wrapped every call to
`scripts/dicos.py` — used by `refresh()` and, through it,
`watch_campaign_outputs.py`'s poll loop — in a bare `subprocess.run` with no
timeout. `dicos.py`'s own HTTP calls are individually bounded (30–300s), but
nothing bounded the child process itself: a kernel-websocket exec that accepts
a connection and never replies has no per-receive timeout on that path. This
is offered as a *plausible* mechanism for the still-unexplained 6h50m gap in
the 2026-08-05 watcher run — not a confirmed root cause.

Fixed with a 360s outer timeout, above `dicos.py`'s largest internal
single-request budget (300s). `subprocess.TimeoutExpired` is converted into
the same `SystemExit` contract `_dicos()` already raised on a nonzero return
code, so `latest_epoch()`'s existing fallback-to-local and
`watch_campaign_outputs.run_loop()`'s existing catch-and-retry both cover it
with no further changes. Two new tests pin the timeout value and its
conversion, with `subprocess.run` monkeypatched — no pod required.

Still open: the root cause inside `dicos.py`'s kernel-websocket receive loop
is not found, only defended against from the outside. A per-receive timeout
there would close the gap properly instead of only bounding the blast radius.

## Repo sync

`Fast MC CBSC`: clean, 0/0 against `origin/main` at session start.
`Fast-MC-Visual-Tests`: 1 commit behind `origin/main`
(`03627a6 fix(site): clarify snapshot and test status`, the owner's own
2026-08-04 commit, unrelated to this session) — fast-forwarded; public suite
now 8/8 (was 7/7).

## Verification

    PYTHONPATH=src python -m compileall -q src vertex scripts tests exhibition   exit 0
    PYTHONPATH=src python -m pytest -q                                           332 passed (330 -> 332)
    python -m unittest discover -s tests -v  (Fast-MC-Visual-Tests)              8 passed (7 -> 8)

## Cost

ASGC SRUs; no paid cloud compute. The 649.83 s/epoch figure is a 4090
measurement and does not carry over to the L40S, which has no measured rate
yet — record one from `dicos-e-02`'s own `history.csv` once epochs land.
