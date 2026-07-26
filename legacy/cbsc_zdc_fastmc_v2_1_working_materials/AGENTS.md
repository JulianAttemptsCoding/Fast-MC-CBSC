# AGENTS.md - CBSC-ZDC v2.1 operating contract

This file is authoritative for automated coding, conversion, training, and evaluation agents.

## Scientific invariants

1. Never claim trained, validated, faster-than-Geant4, or physics-ready status before frozen held-out gates pass.
2. `p4_total_gev[:,0]` is relativistic total energy. All ranges and response normalization use `K_inc = E_total - m_n`.
3. The sole raw event condition is `[E_total, px, py, pz]`. Geometry is static metadata. Never condition on target hits, event IDs, truth shower summaries, or downstream reconstruction.
4. `raw_deposit` is the primary target. Never mix raw energy with thresholded readout or invent subthreshold residual accounting.
5. Never impose `D[l+1] <= D[l]`; hadronic event deposits may rise, fluctuate, gap, and start late.
6. Do not reintroduce a reserve/slack variable or unidentified shared latent.
7. Support is produced by the support scorer plus exactly one Gumbel-Top-k draw. Binary support is not a continuous-flow target.
8. Unselected cells must be exactly zero. Count, support, and positive-energy distributions are separate validation objects.
9. Never alter geometry, target mode, split, metrics, gates, or final-test bank after final-test exposure.
10. `legacy_v2/` is provenance only and must not guide active implementation.

## Mandatory command order

```text
inspect-root -> scan-geometry -> convert -> split -> audit-dataset -> freeze-config
-> response -> profile -> count -> support -> share -> joint
-> qa -> sample -> evaluate -> benchmark
```

Stop at the first contract failure. Never silently discard malformed events or unknown channels.

## Agent preflight

```bash
python -m pip install -e '.[root,dev]'
PYTHONPATH=src python -m compileall -q src tests
PYTHONPATH=src pytest -q
cbsc-zdc --help
```

Verify the production schema and units before scanning geometry. The sample ROOT fixture establishes branch-name structure only; it does not establish production distributions or complete geometry.

## Matched range experiment

Use one converted 0-300 GeV dataset and one split manifest. The two runs differ only in the training-index energy filter:

- full-support run: `data.train_kinetic_gev: [0,300]`;
- primary-support run: `data.train_kinetic_gev: [50,250]`.

Both validate and test on 50-250 GeV. Do not create separate splits or preprocessors.

## Stage initialization contract

- `initialize_from`: load model weights from the preceding stage, then start a new optimizer/scheduler for a new stage.
- `resume_from`: continue the same stage with full optimizer/scheduler/scaler/RNG state.
- response trains condition + visible/response modules;
- profile trains only first-layer/activity/profile-flow modules;
- count, support, and share train only their own modules;
- joint trains all modules.

A new stage must not use `resume_from`.

## Required production artifacts

Before training, archive and hash:

- source ROOT files and schema contract;
- geometry arrays, graph, provenance, and hash;
- converted shard manifest;
- split manifest and grouping rule;
- full train-split audit;
- frozen configuration and gates;
- source archive/commit and environment/container digest.

## Failure rules

Abort on:

- schema/type/unit mismatch;
- multiple or missing generator neutron;
- nonfinite/negative non-sentinel hit energy;
- variable primary vertex when fixed-vertex mode is required;
- unknown channel or geometry-count mismatch;
- split-hash mismatch or empty split;
- incomplete production train audit;
- response cap below any audited training target;
- NaN/Inf loss, gradient, generated value, or metric;
- any support/count/closure/cap invariant failure.

Do not weaken a gate to make a run pass. Record a failure and diagnose it.

## Final-test discipline

The final test bank is one-way. Hyperparameters, checkpoints, thresholds, gate values, metric code, and model selection use training/validation only. Changes after test exposure are post-test exploratory work unless a new untouched test bank is created.

## Required reporting

Every production result must include:

- exact commands and configuration hashes;
- hardware/software/precision/batch/solver-step details;
- three training seeds;
- global and energy-binned metrics;
- high- and low-level C2ST with uncertainties;
- occupancy/count/positive-hit and spatial diagnostics;
- repeated-condition diversity and memorization checks;
- reconstruction closure;
- model-only and end-to-end timing;
- measured Geant4 denominator;
- absolute gates and matched baseline comparisons.
