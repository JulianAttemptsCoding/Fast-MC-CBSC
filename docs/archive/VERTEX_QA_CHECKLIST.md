> **ARCHIVED — SUPERSEDED. DO NOT FOLLOW THIS DOCUMENT.**
>
> Superseded 2026-08-15. Per-job Vertex checks. Vertex is not the current backend -- DiCOS is. See `docs/DICOS_BACKEND.md` and `docs/PIPELINES.md`. Retained because a backend move remains legitimate; `docs/VERTEX_AI_RUNBOOK.md` stays in `docs/` because it is checksum-recorded in `SHA256SUMS.txt`.
>
> Current entry point: `docs/HANDOFF.md` → `docs/PIPELINES.md`.
> Terminal status is unchanged: `PHYSICS VALIDATION NOT ESTABLISHED`.

---

# Vertex QA checklist

Use this checklist with `docs/VERTEX_AI_RUNBOOK.md` and
`docs/HARDWARE_PORTABILITY_QA.md`.

## Before submission

- record source commit and worktree state;
- confirm project, region, service account, quota, and current pricing;
- list recent custom jobs and pipelines to prevent duplicates;
- calculate conservative cost and duration;
- create unique, empty input/output prefixes;
- verify the container digest;
- verify frozen config, prepared-data manifest, split, geometry, and parent
  checkpoint hashes;
- record GPU, machine, scheduling, disk, replicas, precision, batch,
  accumulation, workers, seeds, and solver steps;
- confirm zero test events.

## During execution

- record pipeline/custom IDs immediately;
- inspect immutable progress objects rather than relying only on console logs;
- record every completed/failed epoch, loss component, finite check, checkpoint
  hash, resource result, invariant, visualization, and cost update in `logs.md`;
- preserve failures and never overwrite a prefix.

## After an epoch

- independently verify object inventory and hashes;
- reload paired best/last checkpoints and inspect embedded epoch/metric;
- verify model, optimizer, scaler, RNG, scheduler, and resume state as
  applicable;
- verify finite losses/gradients/tensors and all structural invariants;
- record T4/other-GPU headroom and full configured solver/decode timing;
- verify the fixed validation-only 50-by-5 sample and zero test use;
- synchronize the local dashboard;
- publish only the lowest independently verified validation-loss checkpoint for
  each calibrated family to the public site;
- report scientific metrics as findings and follow-up QA, never as hardware or
  training permission.

An integrity failure quarantines the affected artifact. A poor loss, visual,
throughput, or fidelity result is evidence to investigate; neither is a global
progression decision.
