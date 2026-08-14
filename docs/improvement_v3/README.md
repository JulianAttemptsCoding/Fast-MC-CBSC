# CBSC-ZDC v3 improvement handoff

This directory is the repository-root handoff for the audited
`CBSC_ZDC_audit_bundle_20260812.zip` snapshot. It is a specification and
test-first implementation contract. It does not claim that any proposed model
change has improved Geant4 fidelity.

Read in this order:

1. `ORIGINAL_ARCHIVE_BASELINE.md` — exact input archive and evidence boundary.
2. `FINAL_IMPLEMENTATION_SPEC.md` — architecture, APIs, equations, file changes,
   checkpoint compatibility, and exact algorithms.
3. `LOSS_PHYSICS_AND_EQUATIONS.md` — every loss and its physical meaning.
4. `CONTINUATION_PLAN.md` — ordered experiments and promotion criteria.
5. `QA_QC_DECISION_LOG.md` — evidence, alternatives, decisions, and
   falsification checks; no hidden chain-of-thought.
6. `RESEARCH_SOURCE_REGISTER.md` — primary literature and official technical
   documentation.
7. `AGENT_ONE_SHOT_PROMPT.md` — exact prompt for the implementation agent.

Machine-readable companions are under `specs/improvement_v3/`. Run:

```bash
python scripts/verify_improvement_v3_handoff.py --repo-root .
```

The verifier checks the handoff manifest, validates YAML/CSV/JSON syntax, and
reports whether the repository still matches the audited base. A base mismatch
is not automatically an error: the live Git repository may legitimately be
newer than the August 12 archive. It is a mandatory reconciliation signal.

## Non-negotiable scope

- Preserve the v2.2 path for old frozen configs and checkpoints.
- Add v3 behind `model.architecture_version: cbsc-zdc-v3`.
- Preserve the 6,790-channel, 65-layer raw-deposit contract.
- Preserve exact zeros outside support, exact requested/realized counts,
  non-negativity, valid-cell support, layer closure, and event closure.
- Never train from `legacy/`.
- Never use test data for implementation, tuning, stopping, or checkpoint
  selection.
- Do not attach a classifier loss to the existing `CBSCZDC.sample()` and call
  it end-to-end differentiable.
- Keep the live critic, critic monitor, and external C2ST separate.
- Use L40S as the active training device and RTX 3090 as the external
  diagnostic device unless the live repository says otherwise. The older 4090
  plan is superseded.
- Do not use paid cloud compute without a new user-approved budget.

## What this handoff asks the next agent to implement

The required software scope is:

1. compatibility/versioning and exact resume state;
2. train-only diagnostics and critic partitions;
3. incident-axis-relative node features;
4. a strictly bounded positive-response spline whose hurdle is the only zero
   atom;
5. hierarchical ECAL-start/HCAL-first-layer prediction;
6. longitudinal span/gap and autoregressive activity/count options;
7. calibrated exact Gumbel-Top-k support sampling;
8. correlation/topology/diversity/memorization metrics;
9. staged D1 share and D2 profile conditional critics with replay and gradient
   isolation;
10. D3 support-estimator research code only after its trigger is met;
11. checkpoint, evidence, migration, CLI, and config support;
12. unit, gradient, resume, structural, and synthetic integration tests.

The experiment scope is intentionally sequential. Implementing all switches is
not permission to train all variants simultaneously or to open the test split.

