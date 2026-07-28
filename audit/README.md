# Audit evidence

This directory is intentionally evidence-oriented rather than a code module.

- `*_verification.json` files contain machine-readable artifact checks.
- `*_terminal_analysis.{json,md}` files summarize completed experiment waves.
- `vertex_readiness_analysis_20260724.md` is the cumulative technical record.
- `SUPPLIED_AUDIT_*` files are source review evidence and may use superseded
  terminology.
- `*_freeze_inputs` and checkpoint mirrors support hash reproduction.

Use `docs/AGENT_PROMPT_CONTINUE_ANY_BACKEND_20260728.md` for current operations.
Do not infer permission to train or stop from a historical status label. Under
`docs/QA_POLICY.md`, QA findings identify trusted artifacts and follow-up work.

Do not casually rename or reorganize files in this directory: verifier commands,
manifests, and historical reports cite their paths. Add new evidence with a
unique date/round identifier.
