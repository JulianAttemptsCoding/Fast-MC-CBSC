# CBSC-ZDC v2 chronological research, QA, and iteration log

This is a chronological record of externally reportable research actions, evidence checks, design changes, code changes, and validation results. It is not a reproduction of private hidden reasoning.

## 2026-07-23 - Stage 1: artifact reconstruction

1. Reopened the previously delivered repository, research blueprint, training-QA note, external-baseline note, source modules, tests, and ReportLab PDF-generation script.
2. Confirmed that the prior auditor PDF was generated with ReportLab, not LaTeX, so it did not meet the revised deliverable requirement.
3. Counted the previous repository and reference material: more than 11,000 concatenated lines, including a 600-entry bibliography catalogue.
4. Re-ran the prior source inspection line by line for the executable modules.

### Findings requiring correction

- `ParallelSpatialField.forward()` accepted flow time `t` but never used it. The claimed flow/flow-matching vector field was therefore time independent in the executable scaffold.
- The former `BudgetCascade` was a feed-forward stochastic generator, not a conditional flow. Calling the overall implementation a trained flow-capable reference needed qualification.
- Sequential sigmoid stick breaking over 65 layers introduced an avoidable ordering bias: unless spend fractions remain very small, the residual budget contracts multiplicatively toward late layers.
- The count model used a Poisson distribution, imposing equality of conditional mean and variance and providing a weak model for broad/overdispersed hadronic hit counts.
- The decoder used deterministic top-k and ordinary softmax. It produced exact zeros outside top-k but had no detector-threshold contract, no subthreshold residual, and no explicit protection against low-energy values among selected hits.
- The old code did not test whether the vector field changed with time.
- The old PDF stated the architecture more strongly than the executable code justified.

Decision: replace the executable scaffold and rewrite the paper rather than patching only prose.

## Stage 2: literature check focused on exact sparsity and low-energy dust

### Calorimeter evidence

- Convolutional L2LFlows reports that per-layer rescaling can shift nominally zero voxels above threshold, creating an excess of low-energy hits. The authors avoid that rescaling for CaloChallenge and use explicit empty-voxel handling elsewhere.
- iCaloFlow reports the same effect: forcing layer outputs to re-normalize can enhance low-energy voxels above the cut and distort the voxel-energy spectrum.
- SARM shows that explicitly modeling sparse particle-physics images can outperform non-sparse autoregressive and GAN baselines on sparse observables.
- CaloPointFlow II and CaloClouds motivate generating active deposits as point clouds rather than dense arrays when occupancy is low.

### General sparse-generation methods

- Sparsemax and alpha-entmax produce exact zeros while remaining differentiable almost everywhere, but do not directly calibrate a fixed hit count.
- Hard-concrete gates provide stochastic exact zeros and a differentiable expected L0 objective, but do not automatically model correlated fixed-cardinality support.
- Gumbel-Top-k gives stochastic sampling without replacement; differentiable sparse top-k methods offer trainable relaxations.

Decision: use a finite count plus stochastic exact top-k as the primary auditable decoder; retain sparsemax/entmax, hard-concrete, and point-cloud models as comparisons.

## Stage 3: target-contract correction

The previous design conflated two targets:

1. raw Geant4 energy deposits, which may contain genuine tiny positive values;
2. thresholded detector/readout output, where values below a frozen threshold are zero.

The revised specification requires selecting the target before training.

- Raw mode uses `tau=0` and an exact count/support model. This prevents positive values in all cells while retaining genuine small positive hits when the count model requests them.
- Thresholded mode uses `tau>0`, chosen from detector/noise/analysis semantics rather than optimization convenience. Selected hits are at least `tau`; budget below `tau` becomes a layer-level subthreshold residual instead of artificial cell dust.

Decision: add target mode and threshold to the immutable data contract.

## Stage 4: longitudinal-model correction

The original scientific insight remains valid only in corrected form: conservation constrains cumulative accounting, not a monotonically decreasing sequence of layer deposits.

The revised implementation no longer uses 65 sequential sigmoid spend fractions. It generates:

- a visible/no-response hurdle;
- a bounded total-response fraction, conditional on target-support audit;
- exact active-layer support;
- a positive masked-simplex allocation over active layers plus reserve.

The cumulative remaining budget is monotone by identity:

```text
R_l = T - sum_{j<=l} D_j,
```

while individual `D_l` may be non-monotonic.

Decision: retain the physical budget interpretation but remove the unnecessary depth-order bias of direct stick breaking.

## Stage 5: spatial-model correction

The user's previous-layer concept is retained through causal longitudinal attention, but all layers are integrated in parallel at every flow step.

Reasons:

- avoids a 65-call free-running rollout;
- avoids false same-slot correspondence between staggered/ganged layers;
- reduces teacher-forcing exposure bias;
- retains directional dependence from earlier layer tokens;
- permits static geometry or graph features.

The revised field now explicitly embeds flow time and conditions on layer budgets and counts.

Decision: parallel causal layer attention is the main candidate; serial previous-layer generation remains an ablation.

## Stage 6: code rewrite

Implemented:

- `VisibleResponseHead`;
- bounded `MixtureBetaResponse`;
- stochastic `LayerActivityHead`;
- `MaskedSimplexProfile` with reserve;
- finite-support categorical `LayerCountHead` with geometry and threshold feasibility masks;
- stochastic `gumbel_topk_mask`;
- `threshold_safe_layer_decoder`;
- `ParallelCausalSpatialField` with flow-time embedding;
- flow-matching tuple/loss utilities;
- dust and support/count diagnostic losses;
- expanded invariant reporting.

Removed from the primary code path:

- direct 65-stage sigmoid stick-breaking;
- Poisson count sampling;
- time-independent spatial field;
- deterministic-only support selection;
- silent spreading of subthreshold budget.

## Stage 7: code QA

Executed:

```text
PYTHONPATH=src python -m compileall -q src tests
PYTHONPATH=src pytest -q
```

Initial rewrite result at that stage:

```text
5 passed
```

This was an intermediate result. Subsequent QA expanded the suite to 30 tests and 100% measured source-and-test statement/branch coverage; see Stages 11--17 below.

Tests now verify:

- bounded response under the explicitly audited mode;
- exact profile accounting;
- exact inactive-layer zeros;
- no forbidden cell energy in `(0,tau)`;
- exact selected support count;
- exact layer budget when resolvable;
- subthreshold residual behavior when `B<tau`;
- time dependence of the vector field;
- full event accounting across resolved cells, subthreshold residual, and reserve.

Two PyTorch nested-tensor warnings were observed because `norm_first=True` disables one nested-tensor optimization. They are performance notices, not correctness failures; they should be revisited during real performance profiling.

## Stage 8: external baseline verification

Verified current public repositories and their documented scope:

- `m-wojnar/faster_zdc`: 59 commits at the time of the web snapshot; FM, latent FM, VQ-GAN, classical baselines, standalone models/weights, and reported ZN/ZP metrics.
- `patrick-bedkowski/expertsim-mix-of-generative-experts`: public repository, one commit in the snapshot, native nine-variable condition including coordinates, and separate neutron/proton ZDC images.
- `luigifvr/vit4hep`: public CFM/NF codebase extending CaloDREAM with separate energy and shape networks.

Decision: reproduce `faster_zdc` natively first; do not treat it as a drop-in architecture for a 6,790-channel irregular detector.

## Stage 9: document rewrite plan

The revised auditor document is authored in LaTeX and structured as an academic methods/specification paper. It includes:

- falsifiable research hypothesis;
- exact input/output and target contract;
- neutron/ZDC/Geant4 motivation;
- full probability factorization;
- mathematical support and accounting identities;
- conditional flow-matching equations;
- exact anti-dust theorem and proof;
- tensor and hyperparameter specification;
- data, training, baseline, QA, evaluation, and Vertex plans;
- limitations and non-guarantee statement;
- claim traceability and software-QA appendices.

The paper deliberately states that exact implementation should produce a valid empirical test, not guaranteed detector fidelity.

## Stage 10: remaining honesty constraints

- The attached ROOT sample could not be decoded numerically in this environment because ROOT/Uproot/Awkward were unavailable and package installation was blocked. No new numerical claims about its branch values are made.
- The 600-entry catalogue was not converted into a false claim of 600 fresh line-by-line full-text reviews. The revised paper relies on a smaller core bibliography reviewed deeply enough to support each substantive claim. The 600 catalogue remains supplementary metadata/abstract screening and is labeled accordingly.
- No trained-model performance claim is made for CBSC-ZDC v2.


## Stage 11: mathematical audit of the count and anti-dust theorem

1. Re-read the count feasibility equation, exact-support theorem, decoder code, and thresholded-residual case together.
2. Found an edge-case ambiguity: the theorem previously allowed a positive budget with `K=0` in its wording even though a normalized selected-cell share cannot exist on an empty support.
3. Corrected the contract:
   - `B=0` implies `K=0`;
   - in thresholded mode, `0<B<tau` implies `K=0` and `U=B`;
   - any resolved positive layer has `K>=1` and `B>=K*tau`;
   - in raw mode, `B>0` implies `K>=1`.
4. Corrected the positive-share target equation so it is evaluated only on layers with `K>0`; zero-count layers set the share target to zero and are excluded from that loss.
5. Added an explicit section explaining that exact Top-k does not prevent count inflation by itself. The count is independently supervised and reported, otherwise a model could legally request every channel.

Decision: retain exact Top-k as the auditable sampling decoder, but never describe it as a complete solution without the count/support objectives.

## Stage 12: numerical audit of the four-momentum validator

1. Tested the original direct mass-squared subtraction on valid neutron four-vectors at 50, 100, 250, and 300 GeV stored as float32.
2. Observed false relative mass-squared residuals increasing with energy because `E^2` and `|p|^2` are large nearly equal numbers.
3. Replaced rejection logic with the stable float64 energy closure

```text
abs(E - sqrt(|p|^2 + m_n^2)) / E.
```

4. Retained the signed mass-squared residual as a diagnostic rather than the sole rejection statistic.
5. Added high-energy float32 regression tests and malformed-four-vector tests.

Decision: report both residuals; validate using the numerically stable one.

## Stage 13: sampler and loss-semantics audit

1. Found that `stochastic=False` still sampled a Gaussian event latent, beta response, and flow base state, so the API name was misleading.
2. Defined deterministic diagnostic semantics:
   - zero event latent;
   - argmax mixture component;
   - beta mean;
   - argmax discrete choices;
   - zero flow base state;
   - deterministic Top-k.
3. Added a no-seed deterministic-repeat test.
4. Found that the positive-hit diagnostic loss truncated sorted arrays when generated and truth hit counts differed, biasing the comparison toward the lower tail.
5. Replaced truncation with quantiles evaluated on one common probability grid and added a regression test.
6. Aligned the reference sampler with forward Euler time points `t=step/steps`; the paper continues to recommend a solver comparison for production.

Decision: preserve deterministic mode only as a diagnostic central sample, not as the stochastic FastMC output.

## Stage 14: geometry and validation-path audit

1. Added constructor validation for node-feature rank, geometry-vector lengths, nonnegative layer IDs, nonempty valid-node support, paired edge inputs, and at least one valid node in every modeled layer.
2. Added validation tests for graph index shape, edge feature shape, invalid node IDs, spatial-state dimensions, geometry mismatch, valid-mask mismatch, and partial edge arguments.
3. Added decoder validation tests for negative thresholds, incompatible shapes, invalid Top-k requests, zero-support selection, stochastic selection, and layers with no valid cells.
4. Added count-head tests for threshold feasibility, inactive-layer zero counts, geometry limits, stochastic sampling, deterministic sampling, and invalid layer dimensions.
5. Added loss-helper tests for dust fraction, support BCE, count cross entropy, empty positive spectra, and unequal-count quantile comparison.

Decision: treat software identity violations as implementation errors, while keeping physics performance as recommended QA/reporting rather than hard user-imposed gates.

## Stage 15: expanded executable QA

Executed:

```text
PYTHONPATH=src python -m compileall -q src tests scripts
PYTHONPATH=src pytest -q
PYTHONPATH=src coverage run --branch -m pytest -q
coverage json -o coverage.json
coverage report -m
```

Final local result:

```text
30 passed
100% aggregate source-and-test statement/branch coverage
```

Seven repeated PyTorch warnings state that nested-tensor optimization is disabled because the transformer layer uses `norm_first=True`. No NaN, exception, failed assertion, or numerical mismatch accompanies the warning. The pre-norm choice is retained for the reference scaffold, and the production timing study is instructed to profile alternatives rather than suppress the warning.

Coverage is not treated as proof of physics fidelity. It establishes that all currently measured source and test statement/branch paths were executed under the synthetic suite. The ROOT adapter and complete production training pipeline remain intentionally incomplete.

## Stage 16: primary-source revalidation

Rechecked the core external claims against primary or official sources:

- Wojnar, *Even Faster Simulations with Flow Matching*, arXiv:2507.18811: confirms ALICE ZDC full flow matching, ZN Wasserstein 1.27, 0.46 ms/sample, latent 0.026 ms/sample, and links `https://github.com/m-wojnar/faster_zdc`.
- Official `m-wojnar/faster_zdc` README: confirms the repository implements the ALICE ZDC flow-matching framework.
- CaloDREAM, arXiv:2405.09629: confirms the combination of conditional flow matching, an autoregressive layer-energy transformer, and a vision transformer for voxel distributions.
- ExpertSim, arXiv:2508.20991: confirms a mixture-of-generative-experts approach tailored to heterogeneous ALICE ZDC responses and links its code repository.
- Kool et al., arXiv:1903.06059: confirms the Gumbel-Top-k extension for sampling `k` elements without replacement.

Decision: keep all cross-paper speed numbers explicitly hardware/batch/representation qualified; do not transfer compact ALICE timing to the 6,790-node detector as an expected result.

## Stage 17: LaTeX auditor-paper construction and PDF QA

1. Replaced the old ReportLab report with a LaTeX academic methods/specification paper.
2. Added full mathematical definitions, factorization, propositions, proofs, tensor contracts, pseudocode, training stages, comparison designs, QA/reporting locations, limitations, and both five-minute pitches.
3. Fixed bibliography compilation by escaping an underscore in an internal filename and switched to `biblatex`/`biber`.
4. Fixed a PDF-bookmark warning by using `\texorpdfstring` around the Top-k subsection title.
5. Compiled the paper with `latexmk`; no undefined citations, undefined references, overfull boxes, or fatal LaTeX errors remained. The remaining underfull-box notices occur in narrow table cells and do not clip content.
6. Rendered every page to PNG and inspected a full contact sheet plus the title, architecture figure, anti-dust theorem, Vertex plan, tensor/hyperparameter tables, software-QA section, and bibliography pages.
7. Re-ran PDF preflight and structural inspection after the final compile; results are recorded in `audit/QA_REPORT.md`.

Final assurance language was tightened: implementing the specification should produce a structurally valid and falsifiable experiment under the declared assumptions; it cannot guarantee trained fidelity to Geant4.

## Final evidence-depth statement

The line-by-line audit now inventories all nonblank Python source/test/script lines and attaches coverage-derived execution status or manual/static status. The prose paper is checked through claim traceability rather than falsely describing every sentence as an independent experiment. The 600-entry literature catalogue remains a discovery/contribution map with evidence-depth labels, not 600 new full-text replications.

## Stage 18: coverage-scope correction, packaging QA, and final rerun

1. Re-examined the earlier 99% coverage statement and found an important tooling limitation: the original report counted only modules imported by the tests. The compatibility module, flow-matching utility, and ROOT-adapter package paths were not all represented in that denominator.
2. Added explicit package initializers and synthetic tests for:
   - ROOT-adapter optional-dependency failure and a controlled fake-ROOT inspection path;
   - the compatibility export module;
   - masked and unmasked flow-matching loss;
   - explicit event-latent sampling;
   - batched Top-k validation;
   - diagnostics with and without per-layer reconstruction;
   - explicit empty-graph construction.
3. Replaced manual try/except assertions in graph tests with `pytest.raises` and corrected the expected error message.
4. Re-ran coverage over the complete importable source tree and tests. Final result:

```text
30 passed
100% measured statement/branch coverage
980 measured statements
132 measured branches
```

5. Refactored the smoke utility from compressed one-line statements into typed, auditable Python, added controlled `--nodes` and `--steps` arguments, and ran a 65-node/one-step synthetic sample. All reported algebraic invariants were zero-error.
6. Added PDF metadata, recompiled the LaTeX source, checked for undefined references/citations and overfull boxes, and repeated PDF structural inspection.
7. Regenerated the line-by-line source ledger from the final files and coverage JSON.

Decision: replace the earlier 21-test/99% statement everywhere with the corrected 30-test/100% measured source-and-test result. Retain the warning that complete synthetic coverage is not evidence of Geant4 fidelity or production readiness.
