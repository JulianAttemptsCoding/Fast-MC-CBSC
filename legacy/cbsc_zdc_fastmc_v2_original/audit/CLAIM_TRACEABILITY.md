# Claim traceability ledger

This ledger maps substantive claims in the LaTeX auditor paper to one of five evidence types:

- **Primary source:** paper, official manual, or official repository.
- **Project evidence:** uploaded audits, executable source, tests, or measured local tooling output.
- **Mathematical derivation:** follows from the explicitly stated equations and assumptions.
- **Design hypothesis:** proposed for matched empirical testing and not represented as established fact.
- **Limitation statement:** records what has not been established.

| ID | Claim | Evidence type | Support / qualification |
|---|---|---|---|
| C001 | Neutron-induced hadronic shower deposits need not decrease monotonically with depth. | Primary source + physics reasoning | Geant4 hadronic manual; hadronic longitudinal-profile and calorimetry literature. |
| C002 | A nonnegative layer allocation implies a non-increasing cumulative remaining accounting budget. | Mathematical derivation | Proposition in the paper: `R_l=T-sum_{j<=l}D_j`. |
| C003 | A dense ordinary softmax assigns strictly positive mass to every finite unmasked logit. | Mathematical derivation | Definition of softmax. |
| C004 | Rescaling dense calorimeter outputs can lift nominal zeros and create excess low-energy hits. | Primary source | iCaloFlow and Convolutional L2LFlows discussions. |
| C005 | Explicit point-mass/sparse models are appropriate comparisons for sparse detector outputs. | Primary source | SARM, CaloPointFlow II, CaloClouds. |
| C006 | Gumbel-Top-k samples a fixed number of elements without replacement. | Primary source | Kool, van Hoof, and Welling (2019). |
| C007 | Sparsemax/entmax can return exact zeros; hard-concrete provides stochastic exact-zero gates. | Primary source | Martins & Astudillo; Peters et al.; Louizos et al. |
| C008 | The threshold-safe decoder gives exact zeros outside support, exact count, threshold consistency, and exact resolved-layer accounting under its hypotheses. | Mathematical derivation + project tests | Theorem in the paper; `tests/test_support_decoder.py`. |
| C009 | Top-k alone cannot prevent count inflation. | Mathematical/design analysis | Decoder is conditional on `K`; paper explicitly requires categorical truth-count training and count calibration reports. |
| C010 | The finite categorical count head can mask geometrically and energetically impossible counts. | Project code + tests | `models/counts.py`; `tests/test_counts.py`. |
| C011 | The revised flow field explicitly depends on flow time. | Project code + tests | `models/spatial.py`; `tests/test_spatial_time.py`. |
| C012 | The revised profile allows exact inactive-layer zeros and arbitrary non-monotone positive layer shapes. | Mathematical derivation + tests | Masked simplex; `tests/test_budget.py`. |
| C013 | The bounded response support is valid only if the stored target audit supports `T<=E_inc`. | Limitation/data-contract statement | Paper Section on energy support; no unconditional physical claim. |
| C014 | Direct `E^2-|p|^2` subtraction is numerically ill-conditioned for high-energy float32 four-vectors. | Numerical analysis + tests | Stable energy-closure implementation; 50/100/250/300 GeV tests in `tests/test_contracts.py`. |
| C015 | Flow matching trains a time-dependent vector field by regression on a chosen conditional probability path. | Primary source | Lipman et al.; Tong et al. |
| C016 | Hierarchical layer/global-to-local decompositions recur in successful calorimeter models. | Primary source | CaloFlow, iCaloFlow, L2LFlows, CaloDREAM. |
| C017 | There is no universal FastMC winner across all CaloChallenge datasets and quality/speed metrics. | Primary source | CaloChallenge results paper and official benchmark. |
| C018 | `faster_zdc` provides public ZDC flow-matching code and reports 0.46 ms/sample full FM and 0.026 ms/sample latent FM in its stated setup. | Primary paper + official repository | arXiv:2507.18811; `m-wojnar/faster_zdc`; cross-hardware transfer is explicitly disclaimed. |
| C019 | ExpertSim uses a mixture-of-generative-experts architecture for heterogeneous ALICE ZDC responses. | Primary paper + official repository | arXiv:2508.20991 and linked repository. |
| C020 | A p4-only model cannot learn independent entry-position effects when entry is deterministic from p4 under a fixed vertex. | Mathematical/data-contract reasoning | Straight-line intercept relationship; prior HGF audit. |
| C021 | Training on 0-300 GeV may help boundaries or dilute capacity relative to 50-250 GeV-only training. | Design hypothesis | Requires a matched training-range experiment; no direction of effect is asserted. |
| C022 | Wider single-particle energy support is not pileup training. | Definition/limitation | Pileup requires multiple-particle/event conditions or a validated composition method. |
| C023 | The legacy recurrent model and HGF-ZDC checkpoint contain the documented structural/fidelity failures. | Project evidence | Uploaded project analyses `analysis.md` and `analysis(1).md`. |
| C024 | The supplied single-stage graph-flow design is an unimplemented controlled baseline proposal. | Project evidence | Uploaded `PROPOSAL_single_stage_flow_baseline.md`. |
| C025 | The revised source passes 30 synthetic tests with 100% measured source-and-test statement/branch coverage. | Measured project evidence | Local `pytest` and `coverage` outputs recorded 2026-07-23. |
| C026 | The PyTorch nested-tensor message is a performance-path warning, not a numerical exception. | Project/tool evidence | Warning text observed during tests; production profiling remains recommended. |
| C027 | The current repository is not a complete Vertex training/evaluation system and is not a trained simulator. | Limitation statement | README, paper, and missing production components list. |
| C028 | The attached ROOT fixture was not freshly decoded numerically in this environment. | Limitation statement | ROOT/Uproot/Awkward unavailable in the active environment; no fabricated event statistics. |
| C029 | The 600-entry catalogue is not equivalent to 600 line-by-line full-text peer reviews. | Evidence-depth limitation | Paper Section 17 and chronological log. |
| C030 | Exact implementation should yield a structurally valid, auditable experiment but cannot guarantee Geant4 fidelity. | Mathematical/software assurance + epistemic limitation | Abstract, assurance statement, and held-out empirical requirement. |
