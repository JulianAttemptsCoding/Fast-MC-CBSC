# Full continuation plan

## Governing rule

Software implementation may be completed in one coding pass. Scientific
experiments remain ordered so each result has a causal interpretation. A poor
metric is preserved as a finding; a schema/hash/invariant/nonfinite failure
quarantines only the affected artifact. Test data stay sealed until the final
protocol is frozen.

## Phase 0 — reconcile the live repository and corrected baseline

1. Fetch the live source and public repos, inspect clean/dirty state, recent
   commits, remote divergence, newest `logs.md`, newest terminal analyses, and
   both DiCOS process trees.
2. Run the handoff verifier. Compare critical hashes against the August 12
   archive. Record every live difference; do not revert newer code.
3. Determine the terminal status of `camp-20260812-lr3e4-anneal` /
   `dicos-f-01`. Do not rerun it if a valid terminal artifact exists.
4. If still live, monitor it through the existing campaign tools. If halted,
   diagnose and resume only from a non-quarantined, hash-matched checkpoint
   under the existing exact-resume contract.
5. Freeze one corrected-v2 reference checkpoint, its complete external
   validation report, exact config, environment, and hashes. This is `B0`.

Phase-0 evidence required:

- one-way schedule trace or exact terminal explanation;
- no unknown writer;
- invariant report;
- validation high/low-level C2ST, reconstruction, response/profile/count/
  support metrics, and timing on the corrected checkpoint;
- explicit statement `PHYSICS VALIDATION NOT ESTABLISHED` unless the entire
  final protocol was independently completed.

## Phase 1 — implement compatibility, diagnostics, and test infrastructure

Implement architecture versioning, v2-to-v3 migration, train-only role
partition, response envelope audit, new metric modules, v3 checkpoint schema,
CLI/config validation, and every unit/gradient/resume/synthetic test before a
new training run.

Acceptance evidence:

- old v2.2 config loads with unchanged meaning;
- old checkpoint exact sample is bitwise equal for fixed CPU seed when code
  path is unchanged, or numerically equal with a documented deterministic
  backend limitation;
- v3 migration has zero unclassified keys;
- role manifest contains exactly 551,234/30,624/30,624 train IDs, no validation
  or test IDs;
- response envelope contains all positive generator-train responses;
- all original and new tests pass;
- synthetic smoke passes exact invariants;
- compile/static checks pass.

No physics inference is made from Phase 1.

## Phase 2 — minimum-credible supervised head ablations

Use the existing 26,624/6,656 pilot bank first, one declared seed, same
optimizer/batch/schedule/epochs/solver steps, and no test access. Each row starts
from the same audited initialization wherever tensor compatibility permits.

| ID | Change from previous row | Purpose |
|---|---|---|
| `B0` | corrected v2 reference | scheduler-clean reference |
| `S1-axis` | incident-axis features only; new input columns initially zero then trained | test missing directional geometry |
| `S2-response` | S1 + bounded positive-response spline | remove second zero atom and improve response |
| `S3-first` | S2 + hierarchical ECAL/HCAL start | repair rare ECAL starts |
| `S4-activity-span` | S3 + span/gap activity | compact longitudinal dependence |
| `S4-activity-ar` | S3 + AR activity | complex longitudinal dependence control |
| `S5-count-ar` | selected S4 + AR counts | cross-layer occupancy dependence |
| `S6-temp-*` | selected S5 + each support temperature | calibrate support stochasticity |
| `S7-ot-profile` | selected S6 + OT-CFM profile coupling | optional flow-coupling screen |

Implement both S4 variants. The predeclared compact-fraction rule names the
primary candidate before validation; validation still reports the matched
alternative.

### General paired promotion rule

For a candidate `C` and its immediate control `R`, calculate 1,000
energy-stratified bootstrap replicates using identical validation event IDs and
generation seeds.

Retain the change for the next composite candidate only when all hold:

1. every structural invariant passes for every generated event;
2. the targeted discrepancy `d_target(C)-d_target(R)` has a 95% bootstrap
   upper bound below zero;
3. no guard discrepancy worsens by more than
   `max(0.10*d_guard(R), truth_half_floor_guard)` with a 95% lower bound above
   that margin;
4. mean external high- or low-level C2ST AUROC does not increase by more than
   0.01;
5. end-to-end sampling time does not increase by more than 20% unless the
   fidelity gain is explicitly reported as a Pareto trade-off.

If the targeted difference is statistically unresolved, preserve the simpler
control. These are proposed validation-selection rules and must be frozen in
the experiment contract before runs begin.

### Target and guard metrics by row

| Row | Target discrepancy | Guard metrics |
|---|---|---|
| S1 | off-axis centroid/topology and condition-aware C2ST; if direction support is degenerate, only feature correctness is claimed | response, profile, counts, speed |
| S2 | zero-fraction error and positive-response conditional distance/NLL | binned mean/resolution, tails, cap support |
| S3 | ECAL-start prevalence/calibration and layer-0 energy distance | non-ECAL first layer, total/profile closure |
| S4 | activity transition/gap/last-layer distances and layer correlation | marginal activity/profile, speed |
| S5 | adjacent/long-range count correlation and count transition distance | count marginals, energy-per-hit, speed |
| S6 | support topology and repeated-condition diversity | support recall, memorization, speed |
| S7 | profile distribution/correlation and solver-step saturation | response, support, wall time |

## Phase 3 — corrected supervised composite

Combine only retained changes into `V3-SUP`. Train:

1. pilot bank, three short software seeds for failure detection;
2. the exact critic generator partition (551,234 events), one seed, no critic;
3. full canonical train split only after the partition-matched result confirms
   that the 10% role reservation itself is understood.

Recalibrate base loss weights on generator-train only using the existing
protocol, inspect gradient conflicts, freeze the chosen values in a new
template, then freeze configs through the repository CLI. Do not hand-edit
frozen configs.

The partition-matched no-critic run is `C0` and is the only valid control for
critic experiments.

## Phase 4 — D1 share critic

Run on the same 551,234-event generator partition:

| ID | Critic/generator auxiliary | Gradient target |
|---|---|---:|
| `D1-control` | none (`C0`) | 0 |
| `D1-feature-r05` | feature matching | 0.05 |
| `D1-direct-r05` | direct classifier | 0.05 |
| `D1-direct-r10` | direct classifier | 0.10 |
| `D1-direct-r20` | direct classifier | 0.20 |

Use one implementation seed for the screen, then repeat the selected direct or
feature objective with three generator seeds before calling it reproducible.

### D1 acceptance

In addition to the general rule:

- intended nonzero generator gradients occur only in share-flow parameters;
- critic parameters receive no generator-update gradients;
- direct-critic validation low-level C2ST mean AUROC improves by at least 0.02
  absolute versus `D1-control`, with 95% bootstrap upper bound on delta below
  zero;
- positive-cell spectrum, top-cell fraction, local topology, and
  reconstruction do not cross guard margins;
- repeated-condition diversity is not below the truth 95% interval and
  nearest-neighbor memorization is not above the truth-truth floor;
- replay contains zero non-train IDs and exact logged composition;
- all resume-equivalence tests pass.

Do not keep a classifier variant merely because the live critic is confused.

## Phase 5 — D2 profile critic

Start again from `C0` or the selected supervised checkpoint; do not stack D1
automatically. Screen:

| ID | Auxiliary | Gradient target |
|---|---|---:|
| `D2-control` | none | 0 |
| `D2-feature-r05` | profile feature matching | 0.05 |
| `D2-direct-r05` | profile classifier | 0.05 |
| `D2-direct-r10` | profile classifier | 0.10 |
| `D2-direct-r20` | profile classifier | 0.20 |

Acceptance mirrors D1, but the target metrics are the 65-layer profile,
covariance/correlation, ECAL fraction, late-energy fraction, shower maximum,
and profile-aware C2ST. Gradients must be isolated to the profile flow.

Only after independent D1 and D2 benefits replicate may a combined `D12` run
be declared. Combined weights are independently ratio-controlled per module;
they are not summed under one global classifier weight.

## Phase 6 — conditional support work

Run D3 only if its trigger in the implementation specification is satisfied.
First complete enumerated/finite-difference estimator QA on tiny geometries.
Then screen a support critic under truth counts/budgets. The exact forward
top-k and exact decoder remain unchanged.

If topology is already within truth-half floors after S6, skip D3 and record
that the trigger was not met.

## Phase 7 — optional downstream utility

Train and freeze the Geant4-only neural p4 ensemble. Use it primarily as a
metric. A generator-side p4 loss is tested only if reconstruction remains a
leading discrepancy after D1/D2 and the direction-support audit allows it.
Maximum gradient target is 0.05. It receives its own matched ablation and is
never combined for the first test with a newly introduced critic.

## Phase 8 — final full-data, three-seed study

Freeze one final architecture/protocol from validation only. Train the
following on full data with seeds 20260723, 20260724, and 20260725:

- corrected v2 reference if compute permits;
- final v3 supervised control;
- final v3 critic variant, if a critic survived prior phases;
- required graph-free/hierarchy-free and external same-data baselines as
  resources permit.

All conditions use matched data, solver steps, checkpoint selection,
evaluation event bank, and disclosed hyperparameter budgets.

Before final test, freeze:

- target and threshold semantics;
- geometry and split hashes;
- architecture and every loss weight;
- response envelope and support temperature;
- critic/replay protocol;
- number of seeds;
- checkpoint selection;
- metric definitions and diagnostic thresholds;
- remaining test event manifest.

Then open the remaining declared test holdout once. Report every seed, every
failed threshold, historical test contamination, truth-half floors,
downstream reconstruction, memorization/diversity, and end-to-end speed.

## Final existing diagnostic thresholds

Do not silently replace `configs/gates_primary.yaml`. In the audited archive it
requires at least 10,000 total events and 500 per primary bin, with:

```text
max_abs_mean_bias_fraction              0.05
max_abs_resolution_difference_fraction 0.10
max_zero_fraction_absolute_difference  0.01
max_response_wasserstein_normalized     0.15
max_hit_count_wasserstein_normalized    0.15
max_high_level_c2st_auc                 0.65
```

These are provisional project diagnostics, not universal physical laws. Judge
them against validation truth-half floors and explicitly freeze any revised
version before final test. Never tighten or relax them simply to change a pass.

## Timing and resource rule

- First implementation and smoke tests: local/CPU where possible.
- Training: active DiCOS L40S; 3090 remains external diagnostics unless the
  asynchronous critic ablation is separately declared.
- No paid Vertex/cloud job without a new user-confirmed budget.
- Every speed report includes solver and exact-decoder time, synchronization,
  batch size, precision, hardware, warmup, repetitions, and I/O boundary.

## Handoff after interruption

At every interruption, the next agent must be able to reconstruct:

1. current Git commit and dirty-state owner;
2. active experiment contract and hashes;
3. one-writer/process-tree proof;
4. last complete and in-flight checkpoint/replay/critic state;
5. latest validation and independent metric state;
6. every failure/quarantine;
7. exact next command and why that command is within the declared experiment.

Update `logs.md`, the audit JSON/Markdown twin, diagnostics, and current-state
handoff at each meaningful event, not only at the end.

