# Archive — superseded documents, retained as history

Nothing in this directory is current guidance. **Do not follow any of it.**
Every file carries a supersession banner naming what replaced it and why.

Current entry point: **`docs/HANDOFF.md`** → **`docs/PIPELINES.md`**.

These files are kept rather than deleted because they record what was believed
when a decision was taken, which is the point of an evidence log. A future
reader needs to be able to see that a claim was made, and why it was withdrawn.

Terminal status is unchanged everywhere: `PHYSICS VALIDATION NOT ESTABLISHED`.

---

## What moved here on 2026-08-15, and what replaced it

| Archived | Superseded by | Why |
|---|---|---|
| `AGENT_PROMPT_CONTINUE_ANY_BACKEND_20260728.md` | `HANDOFF.md`, `PIPELINES.md`, `V3_FULL_REPORT.md` | The Vertex-era self-contained handoff. Its backend instructions are wrong now — training runs on DiCOS. Several numbers predate the corrections in `HANDOFF.md` §0. It was 90 KB and read as authoritative. |
| `AGENT_PROMPT_VERTEX_RUN_AND_ANALYZE.md` | `HANDOFF.md` | Compatibility pointer for old links to the above. |
| `COMPUTE_EXTENSION_PROTOCOL_20260727.md` | `logs.md`, `audit/` twins | Design for a four-family two-epoch extension that has since completed. |
| `VERTEX_QA_CHECKLIST.md` | `DICOS_BACKEND.md`, `PIPELINES.md` | Per-job Vertex checks. Vertex is not the current backend. |
| `V3_PLAN_ASSESSMENT.md` | `V3_FULL_REPORT.md` | The pre-implementation concerns document, written before any v3 row ran. Every question in it is now answered or explicitly still open in the full report, which also carries the measured results. |
| `CBSC_ZDC_v3_DELIVERY_README.md` | `audit/v3_reconciliation_20260814.json`, `V3_FULL_REPORT.md` | Delivery note for the v3 overlay archive. The overlay is installed and long since superseded by the working tree. |
| `release_bundle_v2_2/CBSC_ZDC_v2_2_*.md` (5 files) | `docs/` equivalents | Release-bundle snapshots that sat at repository root looking authoritative. Their `docs/` counterparts are the live documents and have since diverged. |

## The release-bundle snapshots

`release_bundle_v2_2/` holds the five `CBSC_ZDC_v2_2_*.md` files that used to sit
at repository root. **Their bytes are untouched** — no banner was prepended —
because they are a delivered artifact and rewriting them would destroy exactly
the provenance they exist to carry.

They are not listed in `SHA256SUMS.txt` (verified 2026-08-15), so moving them
broke no recorded checksum. Their live counterparts are:

| Snapshot | Live document |
|---|---|
| `CBSC_ZDC_v2_2_COMPLETE_IMPLEMENTATION_GUIDE.md` | `docs/IMPLEMENTATION_GUIDE.md` |
| `CBSC_ZDC_v2_2_DATA_CONTRACT.md` | `docs/DATA_CONTRACT.md` |
| `CBSC_ZDC_v2_2_LOSS_WEIGHT_PROTOCOL.md` | `docs/LOSS_WEIGHT_PROTOCOL.md` |
| `CBSC_ZDC_v2_2_MODEL_WALKTHROUGH.md` | `docs/MODEL_WALKTHROUGH.md` |
| `CBSC_ZDC_v2_2_IMPLEMENTATION_QA.md` | `docs/QA_POLICY.md` + the test suite |

The live documents have diverged from these snapshots. Where they disagree, the
`docs/` version is current.

## What deliberately did NOT move

`docs/VERTEX_AI_RUNBOOK.md` describes a backend that is not current, but it is
**checksum-recorded in `SHA256SUMS.txt`**, so moving it would break a recorded
audit artifact for a cosmetic gain. It stays in `docs/` and is marked
`superseded backend` in the documentation index instead.

A backend move remains legitimate under `AGENTS.md` — GCS and Vertex are
transport, not science — so the Vertex material is retained rather than deleted.
