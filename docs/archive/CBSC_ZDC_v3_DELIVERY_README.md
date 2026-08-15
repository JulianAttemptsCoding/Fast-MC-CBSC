> **ARCHIVED — SUPERSEDED. DO NOT FOLLOW THIS DOCUMENT.**
>
> Superseded 2026-08-15. The delivery note for the v3 overlay archive. The overlay is installed, reconciled and long since superseded by the working tree; see `audit/v3_reconciliation_20260814.json` and `docs/V3_FULL_REPORT.md`.
>
> Current entry point: `docs/HANDOFF.md` → `docs/PIPELINES.md`.
> Terminal status is unchanged: `PHYSICS VALIDATION NOT ESTABLISHED`.

---

# CBSC-ZDC v3 delivery

This overlay adds only new handoff/specification files. It does not overwrite
the active model implementation. Extract it at the CBSC-ZDC repository root,
verify it, then give the coding agent the exact text in
`docs/improvement_v3/AGENT_ONE_SHOT_PROMPT.md`.

```bash
unzip CBSC_ZDC_v3_REPO_ROOT_OVERLAY.zip -d .
python scripts/verify_improvement_v3_handoff.py --repo-root .
```

The verifier may report `live_diff` for audited-base files. That means the live
repository differs from the August 12 archive and must be reconciled. It is not
permission to overwrite or revert the live file.

The package contains a complete implementation specification, equations and
physical meaning of every loss, experiment order, exact train-only critic
partition, response-envelope algorithm, critic/replay/gradient settings,
acceptance gates, file-change map, test catalog, source register, decision log,
and one-shot prompt.

