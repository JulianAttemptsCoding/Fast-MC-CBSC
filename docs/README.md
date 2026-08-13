# Documentation map

## Start here

1. `HANDOFF.md` — current standings, known defects, the operations you need,
   and the traps that have already cost time. Read this first.
2. `../AGENTS.md` — operating contract.
3. `IMPLEMENTATION_GUIDE.md` — complete scientific and implementation guide.
4. `QA_POLICY.md` — QA is evidence, not progression permission.
5. `AGENT_PROMPT_CONTINUE_ANY_BACKEND_20260728.md` — self-contained new-chat
   and new-CLI handoff.

## Contracts

- `DATA_CONTRACT.md` — ROOT, prepared shard, split, target, and geometry
  semantics.
- `MODEL_WALKTHROUGH.md` — architecture and loss interpretation.
- `LOSS_WEIGHT_PROTOCOL.md` — nine-loss calibration procedure.
- `EVALUATION_PROTOCOL.md` — metrics and diagnostic thresholds.

## Execution

- `DICOS_BACKEND.md` — the ASGC pod backend and its filesystem contract.
- `TWO_GPU_PIPELINE.md` — training pod and diagnostics pod, and how they meet.
- `GPU_BENCHMARKS.md` — the single source of truth for throughput and cost;
  supersedes every figure in `../logs.md`.
- `FOCUSED_OPERATING_RULES.md` — the short form of the operating rules.
- `WORKSPACE_LAYOUT.md` — what lives where.
- `AUDIT_BUNDLE_README.md` — what the external audit bundle contains.
- `HARDWARE_PORTABILITY_QA.md` — backend-neutral accelerator QA.
- `VERTEX_AI_RUNBOOK.md` — Google Vertex transport and execution.
- `VERTEX_QA_CHECKLIST.md` — per-job and per-epoch Vertex checks.
- `VISUALIZATION_DASHBOARD.md` — local and public visual evidence.
- `EXHIBITION_ARCHIVE_AND_MIRROR.md` — immutable historical snapshots and
  safe synchronization of a dirty presentation checkout.
- `TROUBLESHOOTING.md` — failure diagnosis.

## Historical experiment specification

- `COMPUTE_EXTENSION_PROTOCOL_20260727.md` — the completed four-family
  two-epoch extension design.
- `AGENT_PROMPT_VERTEX_RUN_AND_ANALYZE.md` — compatibility pointer for old
  links.

Machine evidence is in `../audit/`; chronological evidence is in
`../logs.md`; presentation figures are in `../exhibition/`.

The `CBSC_ZDC_v2_2_*.md` files at repository root are release-bundle snapshots
retained for checksum provenance. Current operating instructions live under
`docs/`.
