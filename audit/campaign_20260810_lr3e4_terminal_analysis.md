# Campaign `camp-20260810-lr3e4` — complete

## Disposition

`QA PASS`. `dicos-e-02` ran its full 20-epoch segment on an L40S to `exit 0`
and the campaign ended itself under the declared improvement rule, unattended.
`calibrated_lr3e4` has a new lowest verified validation loss. That is
optimization evidence on the pilot bank and nothing more —
`PHYSICS VALIDATION NOT ESTABLISHED`.

## Outcome

| field | value |
|---|---|
| run tag | `dicos-e-02` |
| exit | 0, `2026-08-11T04:03:34Z`, wall 17209.014 s |
| epochs | 20 (absolute 35–54, target 55) |
| best | **epoch 47, validation 4.512720740207991** |
| previous family best | epoch 34, 4.5503306071196254 (`dicos-c-02`) |
| improvement | 0.037610 |

The campaign's own decision, with no operator present:

    outcome: campaign_complete
    reason:  best epoch 47 (4.512721) is 7 epochs behind the latest epoch 54
             and no family remains in the chain

7 > the declared 6-epoch window, and this is a single-family chain, so the rule
stops rather than advancing — exactly as specified on 2026-08-10.

### Standings after

| family | validation loss | epoch | run |
|---|---:|---:|---|
| `calibrated_lr3e4` | **4.512721** | 47 | `dicos-e-02` |
| `calibrated_lr1e4_halfbatch` | 4.619967 | 33 | `dicos-c-03` |
| `calibrated_lr1e4` | 4.635220 | 38 | `dicos-p9` |
| `calibrated_lr3e5` | 4.702203 | 36 | `dicos-c-05` |

### L40S throughput

17209.014 s / 20 epochs = **860.5 s/epoch** at batch 6, against the 4090's
measured 649.83 s/epoch. A single-run observation recorded here only;
`docs/GPU_BENCHMARKS.md` remains the source of truth and wants its own
measurement before this figure is used for planning.

## The connectivity outage was a client bug, not ASGC

Both pods were unreachable from this workstation 2026-08-11 → 2026-08-12 with
`could not open a kernel channel: [WinError 10060]`, while `git fetch`
succeeded throughout. ASGC and the pods were ruled out directly: the owner's
own JupyterLab tab worked, and `python3 -c "print(1+1)"` returned `2`
instantly in a pod terminal.

Measured, not guessed. A bare `socket.create_connection()` to the pod
connected in **21.2 s, five times running, with no variance** — Windows'
SYN-retransmit ladder (3 + 6 + 12 s). The first two SYNs to the Taiwan host
are dropped on the US→TW path; the third lands. `requests` hides this behind
keep-alive so only its first call pays. A kernel channel opens a *fresh*
socket every time and always pays it.

The `timeout` parameter was never what bound: `websocket-client`'s own connect
gave up at **21.0 s with `timeout=30` and again at 21.0 s with `timeout=90`**,
in the same script where a plain socket to the same host:port succeeded at
21.2 s.

**Fix.** `Dicos._preconnect()` establishes the socket where a 90 s budget is
honoured and hands it to `websocket.create_connection(socket=…)` already open.
Verified live immediately afterward. Two details that are not cosmetic:

- `_preconnect()` returns `None` for a non-`http` scheme **deliberately** —
  `websocket-client` skips its own TLS wrapping when handed a socket, so
  pre-connecting a `wss://` channel would send plaintext to a TLS port.
- The retry loop closes a socket it opened for a failed attempt; the handover
  only happens on success, so otherwise three attempts leak three sockets.

Training was never affected — the trainer is a detached pod process and
completed normally mid-outage, confirmed from its own log rather than assumed.

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
    PYTHONPATH=src python -m pytest -q                                           335 passed
    python -m unittest discover -s tests -v  (Fast-MC-Visual-Tests)              8 passed (7 -> 8)
    refresh catalog          124 graphics, PASS, all_manifest_hashes_match true,
                               current_reaches_latest_observed_epoch 54
    diagnostic_summary.json  epochs 23..54, 32 rows, 32 unique
    family_choice.json       calibrated_lr3e4 best e47, 4.512720740207991, dicos-e-02

The fork overlap between `dicos-c-02` (diagnostics 23–42) and `dicos-e-02`
(35–54) resolves correctly: `build_diagnostic_trend_figure.load()` keys by
epoch with later-tag-wins, so `dicos-e-02` supersedes the overlap and the
merged view has no duplicates. This closes the fork-awareness item left open
on 2026-08-11 — that failure was transient, seen only while `dicos-e-02` had
reached epoch 36 and `dicos-c-02` still supplied 37–42.

## Open

1. **A publication is owed and has not been made.** `calibrated_lr3e4`'s
   lowest verified loss changed (4.550331 → 4.512721); the live public
   selection is still `dicos-p9-calibrated-lr1e4:joint:0038`. Publication is a
   deliberate, separate act and is the owner's call.
2. `refresh()` runs each per-family subprocess *before*
   `prune_superseded_rows()`, so a fork transition makes that subprocess's
   trailing figure step raise on the un-pruned duplicate. The post-prune block
   (`refresh_campaign_outputs.py:420`) re-runs those builders by design, so the
   final state is correct — but the failed return code still poisons
   `result["exit_code"]`, making a *successful* refresh exit 1 with a
   traceback. The watcher is unaffected (`run_once` reads the result dict).
3. No campaign is running; the declared chain is complete. Whether to declare
   another `calibrated_lr3e4` segment is the owner's call — epochs 48–54 all
   sat above the epoch-47 best, which is what stopped it.

## Cost

ASGC SRUs; no paid cloud compute. The 649.83 s/epoch figure is a 4090
measurement and does not carry over to the L40S, which has no measured rate
yet — record one from `dicos-e-02`'s own `history.csv` once epochs land.
