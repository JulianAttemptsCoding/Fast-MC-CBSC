# Documentation map — what is current, and what is not

Every document in this repository has exactly one status below. If a file is not
listed here, it is not guidance.

Terminal status: **`PHYSICS VALIDATION NOT ESTABLISHED`**.

---

## Read in this order

| # | Document | What it gives you |
|---|---|---|
| 1 | **`HANDOFF.md`** | Where the project stands. **§0 first** — two corrections that change how every older number reads. |
| 2 | `../AGENTS.md` | The binding contract. Non-negotiable. |
| 3 | `../CLAUDE.md` | Session rules for this host. |
| 4 | **`V3_FULL_REPORT.md`** | The complete v3 record: every number, all defects, the honest status. |
| 5 | **`PIPELINES.md`** | Every operation with its exact command. |
| 6 | `WALKAWAY_RUNBOOK.md` | What is running right now, and what to do when you come back. |

`IMPLEMENTATION_GUIDE.md` is the full scientific and implementation reference;
read it when you need the model, not to start a session.

---

## Current — binding contracts

| Document | Scope |
|---|---|
| `QA_POLICY.md` | QA is evidence, never progression permission |
| `DATA_CONTRACT.md` | ROOT, shard, split, target and geometry semantics |
| `IMPLEMENTATION_GUIDE.md` | complete scientific and implementation guide |
| `MODEL_WALKTHROUGH.md` | architecture and loss interpretation |
| `LOSS_WEIGHT_PROTOCOL.md` | nine-loss calibration procedure |
| `EVALUATION_PROTOCOL.md` | metrics and diagnostic thresholds |
| `HARDWARE_PORTABILITY_QA.md` | backend-neutral accelerator QA |
| `VISUALIZATION_DASHBOARD.md` | local and public visual evidence |

## Current — operations

| Document | Scope |
|---|---|
| **`PIPELINES.md`** | every pipeline, end to end, with verified commands |
| `DICOS_BACKEND.md` | the ASGC pod backend and its filesystem contract |
| `TWO_GPU_PIPELINE.md` | training pod and diagnostics pod, and how they meet |
| `GPU_BENCHMARKS.md` | single source of truth for throughput and cost; supersedes every figure in `../logs.md` |
| `FOCUSED_OPERATING_RULES.md` | short form of the operating rules |
| `WORKSPACE_LAYOUT.md` | what lives where |
| `EXHIBITION_ARCHIVE_AND_MIRROR.md` | immutable snapshots and safe mirror sync |
| `AUDIT_BUNDLE_README.md` | what the external audit bundle contains |
| `TROUBLESHOOTING.md` | failure diagnosis |

## Current — state of the work

| Document | Scope |
|---|---|
| **`HANDOFF.md`** | current standings, defects, traps |
| **`V3_FULL_REPORT.md`** | the complete v3 programme record |
| **`WALKAWAY_RUNBOOK.md`** | live jobs and recovery |
| `improvement_v3/` | the v3 contract, experiment matrix and executable plan |

## Superseded backend, retained in place

| Document | Status |
|---|---|
| `VERTEX_AI_RUNBOOK.md` | **Vertex is not the current backend — DiCOS is.** Kept in `docs/` only because it is checksum-recorded in `../SHA256SUMS.txt`; moving it would break a recorded audit artifact. A backend move remains legitimate under `AGENTS.md`, so it is retained rather than deleted. |

## Archived — do not follow

Everything in **`archive/`**. Each file carries a supersession banner naming its
replacement. See `archive/README.md` for the full table.

Moved there 2026-08-15: the Vertex-era agent prompts, the completed
compute-extension protocol, the Vertex QA checklist, the pre-implementation v3
plan assessment, the v3 overlay delivery note, and the five
`CBSC_ZDC_v2_2_*.md` release-bundle snapshots that used to sit at repository
root looking authoritative.

---

## Where the evidence lives

| Path | What |
|---|---|
| `../logs.md` | chronological record, appended as work happens |
| `../audit/` | one JSON + Markdown twin per event |
| `../exhibition/current/` | the complete presently valid visual set |
| `../exhibition/archive/` | historical and superseded visuals |
| `../exhibition/data/v3_screening_rows.json` | the v3 row registry and comparator rule |

## Two facts that are easy to get wrong

**Compare a v3 screening row to M0-fresh (4.935508 on the common deposited-
energy-GeV response-density measure), never to B0 (4.483768) or raw M0
(4.513572).** The common value includes the audited, target-only historical-v2
Jacobian correction; it changes neither gradients nor the selected epoch.
Every screening row uses `initialize_from`, which transfers weights but not
optimizer state, and that fresh Adam costs a measured 0.021601.

**The frozen 0.65 diagnostic is `max_high_level_c2st_auc`.** B0's value for it is
**0.892897**. The hybrid figure 0.843222 answers to a different gate. Never mix
them.
