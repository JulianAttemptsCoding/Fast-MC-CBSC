# Line-by-line revision index

The four source audits were reviewed from first to last line. This index maps every substantive topic encountered to the active correction; repeated audit entries are consolidated rather than duplicated.

| Source-audit topic | Active files revised |
|---|---|
| claim boundary / not fidelity | `README.md`, paper Sections 1 and 16, `CLAIM_TRACEABILITY.md` |
| monotone deposit rejection | `models/profile.py`, `ARCHITECTURE_V2_1.md`, paper Section 5 |
| energy kinetic vs total | `contracts.py`, `features.py`, `root_adapter.py`, `DATA_CONTRACT.md`, paper Section 3 |
| p4 mass-shell numerical stability | `contracts.py`, tests, paper Section 3 |
| fixed vertex and entry-condition ambiguity | `root_adapter.py`, `DATA_CONTRACT.md` |
| geometry counts, ganging, edges, isolated nodes | `geometry.py`, `scan-geometry`, geometry docs and tests |
| raw/threshold target ambiguity | `contracts.py`, `root_adapter.py`, `objectives.py`, decoder tests, paper Sections 3 and 8 |
| duplicate `S` notation | all active code/paper/docs use descriptive names |
| shared latent semantics | removed from `models/system.py`; paper factorization revised |
| visible hurdle definition | `truth_hierarchy`, `LongitudinalCascade`, target docs |
| total-response support/endpoint | training-derived cap, mixture caveat, audit CLI |
| first-layer hazard normalization | replaced with direct categorical first-positive layer |
| active-layer semantics | raw-positive layer definition; thresholded-only separate |
| reserve/slack | removed from model, loss, decoder, and paper |
| count feasibility | `models/counts.py`, decoder, tests |
| singular support flow | support scorer separated from share flow |
| dimensionful epsilon/log transforms | dimensionless share target; declared GeV scales |
| CFM time dependence | explicit `TimeEmbedding`, tests |
| graph causality | bidirectional primary, causal ablation |
| Gumbel-Top-k double randomness | one support sample only |
| decoder proof and fp tolerance | decoder tests, paper theorem and numerical qualification |
| support/count training | BCE, ranking, categorical CE, calibration protocol |
| exposure bias | staged/free-running protocol and evaluation requirements |
| split leakage | `splits.py`, CLI refusal of empty groups |
| predeclared acceptance gates | `gates_primary.yaml`, evaluator, paper Section 12 |
| seed/RNG contract | `randomness.py`, checkpoint metadata, docs |
| optimizer/precision/resume | `trainer.py`, templates, Vertex runbook |
| fixed-condition/diversity/memorization | `EVALUATION_PROTOCOL.md` |
| baseline fairness and point-cloud baseline | baseline configs and `BASELINES.md` |
| timing completeness | CLI benchmark and protocol |
| bibliography conflations/errors | new `paper/references_v2_1.bib`; original moved to legacy |
| software QA overclaim | active text separates synthetic execution from physics validation |
| visual PDF QA | revised PDF rendered and preflighted; report in `QA_REPORT.md` |
