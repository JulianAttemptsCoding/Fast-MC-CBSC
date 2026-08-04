# Focused operating rules

This is the operator index for the five rule families the project owner wants
kept in active context: DiCOS, credentials/tokens, live evidence updates,
data-split/academic rigor, and accident prevention. `AGENTS.md` remains the
binding authority; detailed procedures remain in `docs/DICOS_BACKEND.md` and
the continuing-agent handoff.

## 1. DiCOS scope and GPU roles

1. Write, edit, move, and delete only under
   `/dicos_ui_home/julianjuan/sharedfs/work/IOP/julian/Fast MC CBSC`.
   Everything else on the DiCOS host is read-only to this project.
2. The only readable dataset file is the immutable
   `/dicos_ui_home/julianjuan/sharedfs/work/IOP/ZDC_ML_20260620/dataset/myTree_20251117_765k_0to300GeV_neutron_All.root`.
   Do not modify it or write into its directory.
3. Do not read anything else in that dataset directory. In particular, never
   name, inspect, hash, convert, train on, or evaluate with `_transformed.root`
   or the older 15k/100k/135k files.
4. Never weaken or bypass `scripts/dicos.py`. If its guard blocks an operation,
   stop and inspect the request.
5. The 4090 is the sole training writer. The 3090 is the per-epoch diagnostic
   consumer/event generator. Both mount the same workdir.
6. Use `.venv` only from the 4090 and `.venv_3090` only from the 3090. Never run
   `setup` through the 3090 config; it could rebuild the primary shared venv.
7. No third/retired pod is in scope without the owner's instruction.

## 2. Credentials and tokens

1. Credentials stay outside Git: 4090 in `~/.dicos/config.json`, 3090 in
   `~/.dicos/config_3090.json`. Never duplicate tokens into documentation.
2. Never print, log, commit, echo, screenshot, summarize, or expose token
   values. Report only presence and authentication success.
3. Set `DICOS_CONFIG` explicitly for every 3090 command. Unset selects 4090.
4. Prefer `python scripts/dicos.py auth "<external address-bar URL>"`; it reuses
   the stored token. If it changed, recover the newest Jupyter runtime token in
   the Lab UI and pass it directly to `auth`. `auth` verifies before saving and
   saves nothing on failure.
5. The token carries real account permissions. The client guard prevents
   plausible mistakes but is not a sandbox; the operator upholds the contract.

## 3. Update evidence while work happens

1. After every meaningful launch, epoch, failure, correction, repo/doc change,
   or verification, append to `logs.md` immediately. Include failed attempts,
   commit/dirty state, environment/GPU, commands, input/output hashes, timing,
   and the evidence-backed decision. Never log hidden chain-of-thought.
2. For scientific/run conclusions, refresh the machine-readable and human
   `audit/NAME.json` + `audit/NAME.md` twins.
3. Keep current metrics, continuation history/status, diagnostics, and figures
   synchronized. Visually inspect figures; rendering success is not layout QA.
   Every epoch must refresh loss vs epoch, accepted running-best loss, every
   3090 diagnostic metric vs epoch, the same metrics for the validation-loss
   best-so-far checkpoint, and the complete exhibition catalog.
4. Republish the dashboard/public site only when a family's lowest independently
   verified validation-loss checkpoint changes. Verify tests, build, workflow,
   and live URL; a push is not deployment.
5. Preserve negative evidence. Never omit a failed run, QA check, or unfavorable
   epoch from the trajectory.

## 4. Data split and academic rigor

1. Canonical split: 612,482 train / 76,158 validation / 76,300 test. Pilot bank:
   26,624 train / 6,656 validation / 0 test. Fixed visual bank: 50 validation
   conditions × five draws, selection SHA-256
   `f70529198aa9575cd2ebc816fd0800ed5a1a3dcd918dab3845b5dc5d85dc59b6`.
2. Test data must not inform preprocessing, thresholds, architecture, loss
   weights, learning rate, stopping, checkpoint selection, diagnostic
   definitions, or website/visual selection.
3. Do not claim the test split is wholly untouched. Disclose the isolated
   external 40,000-event C2ST and the 2026-07-30 draw containing 200 test
   events. Neither fed model decisions. Exactly 36,100–36,300 test events
   remain untouched because overlap is unresolved. No new test use is implied.
4. Loss, invariants, synthetic fixtures, visual plausibility, and website
   success are not Geant4 fidelity. Physics validation is not established.
5. Production target is raw non-sentinel deposited readout energy at threshold
   0 GeV. Training is 0–300 GeV; primary claim range is 50–250 GeV. A changed
   target is a new frozen experiment.
6. Final scientific conditions require three seeds; report every seed and
   result. Negative results are valid results.

## 5. Accident-prevention rules

1. Never hand-edit a frozen config. Change a template/builder, generate a unique
   config, freeze through repository tooling, record hashes, and diff it.
2. Never weaken an assertion, threshold, invariant, filesystem guard, or test
   to obtain a pass. Fix the caught defect.
3. Quarantine artifacts with schema, geometry, hash, invariant, nonfinite, or
   empty-bin failure. Preserve evidence. Do not publish, compare, resume,
   initialize, or select from them until a corrected re-audit passes.
4. Prove one writer per run directory from process tree and atomic run lock. A
   probe builds its search token at runtime and excludes its PID/parent.
5. Namespace queue, metrics, failed checkpoints, and STOP marker by run tag;
   absolute epochs repeat across resumed run tags.
6. `training.epochs` is absolute:
   `parent_last_epoch + 1 + additional_epochs`. Use a builder.
7. The 4090 producer admits a checkpoint only when its embedded epoch and SHA-256
   match the post-visualization `progress_epoch_NNNN.json` marker. It copies
   atomically, deduplicates all handled states, and emits STOP only after wrapper
   exit plus final acceptance inspection. The 3090 drains pending work even if
   STOP exists and preserves failures/evidence.
8. Before launch, verify both GPU/process trees, repository state, frozen
   hashes, run tag/path, and absence of another writer. Logs/PID files alone do
   not prove liveness.
9. `legacy/` is evidence only; never import or train from it.

## 6. Self-contained continuity

1. Organize and label active artifacts so their purpose, provenance, data split,
   run tag, epoch, checkpoint hash, selection role, scientific interpretation,
   and status are visible without reconstructing project history.
2. Keep one current-state audit and one executable handoff synchronized with the
   binding rules, logs, metrics catalogs, figures, and exact operator commands.
3. Mark superseded and quarantined material explicitly; do not leave ambiguous
   duplicates or require filenames alone to carry scientific meaning.
4. Treat missing operational context as a fail-closed documentation defect.
   Repair the label, catalog, README, audit twin, or handoff before relying on
   the artifact or asking a future operator to continue from it.
5. Keep every exhibition visual in exactly one of `exhibition/current/` or
   `exhibition/archive/`. Current is the complete presently valid set through
   the latest available epoch; archive is historical/superseded evidence and
   must not affect checkpoint selection. The root exhibition page is a router,
   and every needed repository visual outside exhibition must match the exact,
   documented allowlist in `exhibition/visual_layout.json`.

## Current stop state

- Organization/QA only: do not start or resume training yet.
- Both GPUs were verified idle at 2026-08-04 08:32:58 UTC: RTX 4090 0 MiB/0%,
  RTX 3090 1 MiB/0%, and no pipeline process on either. Re-probe because state
  can change.
- `dicos-p10` epoch 40 is quarantined: visualization layer-closure residual
  `2.6702880859375e-05 GeV` exceeded the frozen `2e-05 GeV` tolerance. Its
  checkpoint is not an accepted parent.
- Future topology: 4090 training plus 3090 per-epoch generation/metrics/figures,
  with evidence refreshed every epoch. Launch requires a separately declared,
  frozen experiment.
- The exact state machine, start order, refresh, dashboard, publication, and
  recovery procedure is `docs/TWO_GPU_PIPELINE.md`.
