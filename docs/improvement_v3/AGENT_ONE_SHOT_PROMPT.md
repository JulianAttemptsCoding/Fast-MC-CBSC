# Exact one-shot implementation prompt

Copy everything below the divider into the coding agent after extracting
`CBSC_ZDC_v3_REPO_ROOT_OVERLAY.zip` at the repository root.

---

You are the implementation and experiment-continuation agent for CBSC-ZDC.
Work in the current repository root and complete the software implementation,
tests, audit evidence, and safely available validation-only experiment
continuation in one sustained task. Do not ask me to restate context already in
the repository or this handoff.

## Authoritative starting point

The implementation specification is the extracted handoff:

1. `docs/improvement_v3/ORIGINAL_ARCHIVE_BASELINE.md`
2. `docs/improvement_v3/FINAL_IMPLEMENTATION_SPEC.md`
3. `docs/improvement_v3/LOSS_PHYSICS_AND_EQUATIONS.md`
4. `docs/improvement_v3/CONTINUATION_PLAN.md`
5. `docs/improvement_v3/QA_QC_DECISION_LOG.md`
6. `docs/improvement_v3/RESEARCH_SOURCE_REGISTER.md`
7. `specs/improvement_v3/contract.yaml`
8. `specs/improvement_v3/acceptance_gates.yaml`
9. `specs/improvement_v3/experiment_matrix.csv`
10. `specs/improvement_v3/file_change_map.csv`
11. `specs/improvement_v3/test_catalog.yaml`

The original reviewed input was
`CBSC_ZDC_audit_bundle_20260812.zip`, SHA-256
`ec4f044695401d438d47019012b9d0a1bedda59da5d5d211a97f34e91b5a0432`.
The handoff maps every change to that snapshot. The live Git repository may be
newer. Reconcile; never overwrite or revert newer work merely to match the
archive.

## Binding constraints

Read `AGENTS.md`, `docs/IMPLEMENTATION_GUIDE.md`,
`docs/FOCUSED_OPERATING_RULES.md`, `docs/QA_POLICY.md`,
`docs/DATA_CONTRACT.md`, `docs/HARDWARE_PORTABILITY_QA.md`, and
`docs/TWO_GPU_PIPELINE.md` in full before editing or launching anything. More
recent repository rules supersede stale state notes, but record every conflict
and resolution.

Non-negotiable rules:

- Never import, train from, or treat `legacy/` as active code.
- Never hand-edit a frozen config. Modify an unfrozen template/builder, create a
  unique config, freeze it with repository tooling, and record/diff hashes.
- Never use test events for code decisions, preprocessing, response envelopes,
  role partitions, architecture, loss weights, optimizer, stopping,
  checkpoint selection, diagnostic definitions, replay, or visual selection.
- Preserve the disclosed historical test contamination; create no new test
  access until the final protocol is frozen.
- On DiCOS, write only under
  `/dicos_ui_home/julianjuan/sharedfs/work/IOP/julian/Fast MC CBSC`.
- The only permitted data source is the immutable
  `myTree_20251117_765k_0to300GeV_neutron_All.root` path named in `AGENTS.md`.
  Do not read or name neighboring transformed/old data files.
- Never weaken `scripts/dicos.py`, an assertion, an invariant, a filesystem
  guard, a threshold, or a test to obtain a pass.
- Preserve every dirty user change. If a change overlaps this task, integrate
  it deliberately and document the resolution; do not reset or discard it.
- Do not print, log, copy, or commit credentials or tokens.
- Before any paid Vertex/cloud job, stop and request a new explicit spending
  limit. This prompt does not authorize paid cloud compute.
- The active archive-time hardware was L40S training plus RTX 3090 diagnostics;
  the RTX 4090 was retired. Re-probe live state before relying on it.
- A structural/software pass is not Geant4 fidelity. Use the repository’s QA
  terminology exactly and state `PHYSICS VALIDATION NOT ESTABLISHED` unless the
  final frozen multi-seed test protocol has actually completed.
- Log evidence, alternatives, decisions, counterexamples, commands, hashes,
  environment, failures, and corrections. Never log private chain-of-thought.

## Step 1 — live reconciliation before edits

Run, capture, and audit:

```bash
pwd
python scripts/verify_improvement_v3_handoff.py --repo-root .
git fetch origin
git status --short
git log -5 --oneline
git remote -v
git rev-list --left-right --count origin/main...HEAD
tail -n 300 logs.md
find audit -maxdepth 1 -type f -name '*terminal_analysis*' -printf '%T@ %p\n' | sort -n | tail -n 20
```

Do the equivalent fetch/status/divergence inspection in the public visual repo
and compare against the DiCOS checkout using existing safe tooling. List and
describe active jobs/processes before any launch; prove one writer per run
directory from the process tree using the repository’s self-match-safe probe.

Determine whether `camp-20260812-lr3e4-anneal` / `dicos-f-01` completed after
the archive. If a valid terminal artifact exists, use it; do not rerun it. If it
is live, monitor it. If it failed, diagnose and quarantine only the affected
artifact; resume only through the existing hash-verified exact-resume contract
and only from a non-quarantined checkpoint.

Append the reconciliation event to `logs.md` and create
`audit/v3_reconciliation_YYYYMMDD.{json,md}` before implementation. Include the
audited-base hash comparison and a file-by-file mapping for any live path that
differs from `specs/improvement_v3/file_change_map.csv`.

## Step 2 — create the implementation branch and freeze the contract

If the worktree is clean, create a non-colliding branch named
`feat/cbsc-zdc-v3-improvements`. If it is dirty, do not branch-switch until you
have proved switching preserves the user’s changes; work safely in place or
make a non-destructive checkpoint commit only when repository policy and change
ownership allow it.

Copy `specs/improvement_v3/contract.yaml` into the run-evidence area through a
builder, calculate its SHA-256, and use that hash as
`experiment_contract_sha256`. Do not mutate the supplied handoff contract.
Project-specific values in it are frozen starting hypotheses; any justified
change creates a new versioned contract and an audit twin with old/new hashes.

## Step 3 — implement all required software, test-first

Implement the exact file plan and APIs in
`docs/improvement_v3/FINAL_IMPLEMENTATION_SPEC.md`. Treat
`specs/improvement_v3/test_catalog.yaml` as the minimum assertion set, not a
suggestion. Add the listed tests before or alongside implementation.

Required implementation order:

1. architecture-version-aware config validation that preserves v2.2 defaults;
2. checkpoint format v4, exact resume fields, and v2 loader compatibility;
3. deterministic train-only critic role partition;
4. train-only response-envelope audit;
5. incident-axis feature computation and geometry-manifest provenance;
6. conditional bounded rational-quadratic response spline;
7. hierarchical ECAL-start/HCAL-first-layer heads;
8. span/gap and autoregressive activity modes plus train diagnostic selector;
9. autoregressive feasible count head;
10. frozen support-temperature sampling with exact hard top-k;
11. differentiable share/profile stage samplers with explicit source noise;
12. topology, correlation, diversity, memorization, bootstrap, and provenance
    metrics;
13. D1/D2 projection critics, logistic/R1 losses, feature-matching control,
    update isolation, gradient-ratio controller, and bounded replay;
14. v2-to-v3 migration command with explicit tensor-key classification;
15. CLI, preflight, config-freezing, evidence, and run-verification support;
16. D3 tiny-geometry estimator-QA harness, but no default D3 training;
17. optional Geant4-only p4 ensemble interface, disabled in D1/D2 configs.

Implementation details are exact in the spec. Do not substitute an unbounded
lognormal, reuse the old quantile safety cap as hard spline support, attach the
critic to current `sample()`, use a straight-through top-k by default, reset the
critic every 20 epochs, combine direct and feature critic objectives in one
first-screen run, or run the live critic on the separate 3090 before the L40S
single-process implementation is proven.

Preserve v2 checkpoint semantics. The migration command must copy/reinitialize
only the modules declared in the specification and must reject any
unclassified state key. The four expanded axis-feature columns begin at zero so
the migrated node projection reproduces v2 before fine-tuning.

Format code with the repository’s existing tools. Keep changes minimal within
each module; do not rewrite unrelated systems.

## Step 4 — local verification gates

Use the repository’s supported environment. On this project,
`PYTHONPATH=src` is mandatory for pytest. Do not rebuild a shared DiCOS virtual
environment from the diagnostic pod.

Run at minimum:

```bash
PYTHONPATH=src python -m compileall -q src scripts tests
PYTHONPATH=src python -m pytest -q
python scripts/verify_improvement_v3_handoff.py --repo-root .
python scripts/verify_v3_run.py --mode software --repo-root .
```

Then run the existing synthetic smoke path and a new v3 synthetic smoke with:

- one supervised forward/backward update;
- one exact sample;
- every invariant;
- one D1 critic update and D1 generator update;
- one D2 critic update and D2 generator update;
- checkpoint save/reload;
- uninterrupted versus resumed next-update comparison;
- zero test-loader construction.

Run response-spline forward/inverse/Jacobian checks in float64 and ordinary
training in float32. Run adversarial-gradient tests with AMP disabled so the
unscaled reference is exact; separately smoke AMP on CUDA.

Do not proceed past a failing schema/hash/invariant/nonfinite/empty-bin test.
Diagnose and fix the cause. Do not weaken the test.

Append implementation and verification events as they occur. Create
`audit/v3_software_implementation_terminal.{json,md}` containing changed-file
hashes, original/new test counts, exact commands/exits, known warnings,
coverage for new modules, and the statement that software QA is not physics
validation.

## Step 5 — build production-derived train-only artifacts

Using only the frozen training assignment:

1. build the exact 551,234/30,624/30,624 role manifest using the SHA-256 sort
   algorithm in the contract;
2. build the 25-GeV train-only maximum response envelope;
3. build the longitudinal compact-fraction/gap/transition/count-correlation
   audit;
4. verify geometry origin and incident-axis normalization;
5. hash every output and run its preflight verifier.

Fail if a role ID is not train, roles overlap, counts differ, a production
response-envelope bin is empty, any visible train response is outside its cap,
the vertex is not fixed within the frozen tolerance, or hashes do not match the
declared split/geometry/data artifacts.

Do not inspect validation/test to construct these artifacts.

## Step 6 — run the ordered validation-only experiment matrix

Follow `docs/improvement_v3/CONTINUATION_PLAN.md` and
`specs/improvement_v3/experiment_matrix.csv` exactly. Generate unique unfrozen
templates with a builder, freeze them with repository tooling, diff each frozen
config against its parent, and verify that only declared fields differ.

Run Phase 2 on the pilot bank first: `B0`, S1, S2, S3, both S4 variants, S5,
the four S6 temperatures, and S7 only if its prerequisites exist. Use identical
validation event IDs and generation seeds for paired bootstrap comparisons.
Apply the frozen promotion rule; retain the simpler parent when an improvement
is statistically unresolved. Report every candidate, including negative ones.

Build `V3-SUP`, then `C0` on the exact 551,234-event generator partition. `C0`
is the required control for every critic run.

Run D1 and D2 separately. For each critic update, detach fakes; for each
generator update, freeze critic parameter flags but retain input autograd.
Measure gradients every 16 generator updates and log the exact ratio/cosines.
Use 2 fresh + 1 recent + 1 anchor fake for critic batch size 4 after warm-up.
Replay may contain train events only. Run direct and feature objectives as
separate experiments. Do not stack D1 and D2 until each independently meets its
predeclared validation criteria and repeats across three generator seeds.

The first live critic is synchronous and single-process on the L40S. Keep the
3090 on external per-epoch diagnostics. Do not infer that an asynchronous
critic is equivalent; declare it separately only after the synchronous result.

Do not run D3 unless its topology/feature trigger is met and the tiny-geometry
SIMPLE/soft estimator QA is complete. Do not activate the p4 generator loss in
D1/D2.

After every epoch: checkpoint, invariant check, external validation diagnostics,
critic monitor, replay/gradient evidence, figures/catalog, `logs.md`, and audit
state. Keep per-run namespaces and do not overwrite repeated absolute epochs.

## Step 7 — final full-data protocol

Only after validation selects one protocol, freeze architecture, response
envelope, support temperature, base/adversarial weights, replay, seeds,
checkpoint selection, metric definitions, and the remaining test-event
manifest. Train the final supervised and retained critic conditions on full
data with generator seeds 20260723, 20260724, and 20260725. Report every seed.

Do not open the remaining test holdout until this freeze is complete. Open it
once, disclose the earlier 40,000-event historical C2ST and unresolved 200-event
overlap, and report all predeclared metrics and failures. A low one-classifier
AUC alone is not success.

If runtime ends before full training completes, leave a self-contained,
hash-verified campaign and handoff with exact next command, one-writer state,
checkpoint/replay/critic hashes, and no unsupported final claim. Do not call an
in-flight or pilot result final.

## Completion deliverables

Before finishing, provide:

- implemented source/config/builders/tests;
- updated docs and source register where live paths differed;
- all commands and exact exits;
- original and final repository commit hashes and dirty-state disposition;
- `audit/v3_*` JSON/Markdown twins for reconciliation, implementation,
  artifacts, every experiment family, and terminal state;
- role/envelope/experiment/checkpoint/replay manifests and hashes;
- validation comparison table with bootstrap intervals, every seed, timing,
  C2ST, reconstruction, topology/correlation/diversity/memorization, and
  structural results;
- remaining-test freeze and final report only if legitimately completed;
- a concise current-state handoff with the next exact command if anything is
  still running;
- explicit separation of `QA PASS`, `QA FINDING`, `ARTIFACT QUARANTINED`,
  `FOLLOW-UP QA`, and `PHYSICS VALIDATION NOT ESTABLISHED`.

Do not claim that an idea worked unless its recorded experiment demonstrates
it. Preserve all negative evidence. Commit logically separated, verified
changes and do not push/deploy external/public changes unless repository policy
and the user’s request authorize that action.

---

