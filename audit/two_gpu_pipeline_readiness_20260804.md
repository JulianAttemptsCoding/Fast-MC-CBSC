# Two-GPU pipeline readiness — 2026-08-04

## Disposition

The organization-only pipeline is ready for a separately declared and frozen
future run. No training, diagnostic event generation, or publication was
started. The RTX 4090 remains the sole training writer; the RTX 3090 is the
4,000-event validation-only diagnostic generator.

The prior file-existence race is closed: `last.pt` cannot enter the 3090 queue
until its copied epoch and SHA-256 match the progress marker written after the
required inline 50×5 visualization succeeds. Failed visualization therefore
cannot create an accepted queue entry.

## End-to-end guards

- the detached launcher guarantees a terminal exit sentinel;
- producer admission is marker/epoch/hash bound and atomic;
- stale producer locks are reclaimed only for a provably dead same-host PID;
- producer, wrapper, consumer, QA, duplicate, and hash conflicts preserve
  namespaced negative evidence;
- the consumer drains before STOP, publishes normal metrics only after QA, and
  exits nonzero if any item was quarantined;
- refresh is hash-verified, atomic, validation-only, and imports dashboard
  payloads only when checkpoint identity agrees across 4090 and 3090 evidence;
- public release remains separate and occurs only when the independently
  verified family-best validation loss changes.

The exact commands and state machine are in `docs/TWO_GPU_PIPELINE.md`.

## Verification

| Check | Result |
|---|---|
| focused pipeline regression | 80 passed |
| full source suite | 230 passed; 8 known warnings |
| Ruff / compileall / diff whitespace | pass / pass / pass |
| shared DiCOS checkout | `07c1dda` |
| 4090 pipeline/visualization suite | 21 passed; 2 known warnings |
| DiCOS immutable artifact verification | 18/18 passed |
| 3090 environment import smoke | pass in `.venv_3090` |
| RTX 4090 live state | 0 MiB, 0%; no pipeline processes |
| RTX 3090 live state | 1 MiB, 0%; no pipeline processes |
| new train/test events used | 0 / 0 |
| public snapshot changed | no |

The first unqualified full-suite invocation omitted `PYTHONPATH=src` and failed
during collection on five package imports; the contract-correct rerun passed.
An optional remote Git query also found that the 3090 image has no Git; this did
not affect its repeated GPU/process proof.

The first updated on-pod test command collected from the workdir parent and
failed on three `scripts.*` imports. Its contract-correct rerun from `repo/`
passed. A first nested-quote 3090 smoke command was rejected locally; the
base64/stdin retry imported the updated consumer successfully. Neither failed
attempt started generation or touched scientific artifacts.

## Remaining launch gate

Readiness is not experiment authorization. A future launch still requires the
owner's scientific question, a unique builder-generated frozen config and tag,
an accepted hash-verified parent, same-session clean/idle probes, and proof of
one writer. `dicos-p10` epoch 40 remains quarantined and cannot be that parent.
