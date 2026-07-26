# CBSC-ZDC FastMC v2

Research specification and executable scaffold for a **Constrained Budgeted Stochastic Cascade** surrogate of single-neutron showers in a fixed Zero Degree Calorimeter.

## Status

This repository is designed to make the proposed experiment implementable and auditable. It is **not** a trained or validated simulator. A faithful implementation should avoid the structural invalidities found in the prior recurrent and HGF-ZDC models, but physics fidelity remains an empirical question.

## Raw input and target domain

- Sole raw event condition: `p4 = [E, px, py, pz]`.
- Allowed event features: deterministic functions of `p4` only.
- Static detector geometry is configuration, not event input.
- Available Geant4 support: intended 0-300 GeV non-pencil-beam neutrons.
- Primary reporting domain: 50-250 GeV.
- Required training comparison: 0-300 GeV versus 50-250 GeV using matched architecture and optimization.

## Correct physics constraint

The model does **not** force per-layer deposited energy to decrease with depth. Neutron-induced hadronic showers can start late, rise, fluctuate, and leak. Instead, the model generates a nonnegative total response and allocates it over an explicitly generated active-layer support plus a reserve channel. The remaining accounting budget

```text
R_l = T - sum_{j<=l} D_j
```

is automatically non-increasing, while individual deposits `D_l` are unconstrained in ordering.

## Anti-dust decoder

The primary decoder prevents the model from spreading tiny positive values over every cell:

1. generate a finite hit count `K_l` for each layer;
2. sample exactly `K_l` cells using stochastic Gumbel-Top-k;
3. set every unselected cell exactly to zero;
4. if a readout threshold `tau>0` is scientifically defined, decode selected energies as

```text
E_i = tau + (B_l - K_l*tau) * softmax(r)_i,
```

with `K_l <= floor(B_l/tau)`;
5. if `B_l < tau`, keep it as a layer-level subthreshold residual rather than distributing it as artificial cell dust.

Top-k is the primary implementation because it gives exact support size and exact zeros. Sparsemax/entmax, hard-concrete gates, and sparse point-cloud generation are documented comparison options rather than assumed improvements.

## Architecture

1. strict neutron four-momentum validation;
2. minimal `p4` condition encoder;
3. shared event latent;
4. visible/no-response hurdle;
5. bounded mixture model for total response, enabled only after target-support audit;
6. stochastic active-layer support;
7. masked-simplex longitudinal allocation with reserve;
8. finite-support categorical hit-count model;
9. parallel conditional flow-matching field with causal longitudinal attention;
10. stochastic exact support selection and threshold-safe energy allocation.

The architecture is a combination of established methods. No individual component is claimed as novel.

## Software QA performed in this package

```bash
PYTHONPATH=src python -m compileall -q src tests
PYTHONPATH=src pytest -q
```

Current result: `30 passed`; measured source-and-test statement/branch coverage is 100% under the local synthetic suite. PyTorch emits a repeated nested-tensor optimization warning because the causal transformer uses `norm_first=True`; this is not a numerical failure and remains documented for production profiling. Coverage proves code-path execution only, not Geant4 fidelity.

## Main documents

- `paper/CBSC_ZDC_Auditor_Specification.tex`
- `docs/RESEARCH_BLUEPRINT.md`
- `docs/ANTI_DUST_DESIGN.md`
- `docs/TRAINING_QA.md`
- `docs/EXTERNAL_BASELINES.md`
- `FULL_CHRONOLOGICAL_RESEARCH_LOG.md` (merged original research catalogue and v2 QA chronology)
- `audit/FULL_CHRONOLOGICAL_RESEARCH_LOG_V2.md`
- `audit/LINE_BY_LINE_AUDIT.md`
- `audit/CLAIM_TRACEABILITY.md`
- `audit/QA_REPORT.md`
