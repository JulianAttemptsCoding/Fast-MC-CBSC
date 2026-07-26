# CBSC-ZDC Full Audit Report  
**Artifact audited:** `CBSC_ZDC_Auditor_Specification_LaTeX.pdf`  
**Audit date:** Thursday, July 23, 2026  
**Audit mode:** full specification-level textual audit of the provided knowledge-base content  
**Audit standard:** internal consistency, mathematical correctness, physics plausibility, implementability, QA sufficiency, research validity, falsifiability, and reproducibility-readiness  
**Important limitation:** this is **not** an execution audit of code, ROOT data, Vertex AI jobs, geometry files, or external repositories. No external citations were live-verified unless explicitly stated. The audit is based on the supplied document text and general domain knowledge.

---

## 0. Executive Audit Verdict

### Overall verdict
**PASS WITH REQUIRED CORRECTIONS as an auditor-ready research specification and implementation contract.**  
The document is unusually disciplined: it separates structural validity from empirical Geant4 fidelity, states what is not claimed, proves key decoder invariants, and defines a falsifiable comparison protocol.

### What is not verified
This audit **does not** verify that:

- CBSC-ZDC reproduces Geant4;
- the supplied scaffold is production-ready;
- the ROOT data satisfy the energy-support assumptions;
- the geometry graph is physically valid;
- external baselines are reproducible in this environment;
- speed or fidelity targets will be achieved.

The document itself says this clearly, and the audit agrees.

### Severity summary

| Severity | Count | Meaning |
|---|---:|---|
| Critical | 0 | No contradiction that invalidates the core mathematical contract, assuming stated preconditions are enforced. |
| Major | 8 | Ambiguities or missing enforcement steps that should be fixed before training or external audit sign-off. |
| Minor | 16 | Useful clarifications, QA additions, or reporting refinements. |
| Editorial | 6 | Notation, wording, or presentation cleanup. |

### Top major findings

1. **Notation collision:** `S` is used for both first-visible layer and selected cell-set support. The joint factorization therefore contains ambiguous duplicate `S` terms.
2. **Latent variable treatment:** the factorization conditions on shared `z` but does not explicitly show `p(z)` or whether the training objective marginalizes over `z` or uses sampled `z`.
3. **Threshold-mode semantics:** “visible response”, raw deposit, thresholded readout, subthreshold residual, and no-response events need stricter definitions. Subthreshold-only raw events can be ambiguous under the current wording.
4. **Energy convention:** whether `E` is total or kinetic energy must be frozen. The bounded support `ρ = T/E ∈ [0,1]` depends on this convention and on the Geant4 scoring contract.
5. **Count feasibility enforcement:** the categorical count model must explicitly mask infeasible counts `Kℓ > floor(Dℓ/τ)` and handle `τ = 0` separately. The theorem is correct only if these preconditions are enforced.
6. **Pseudocode gaps:** sampling pseudocode lacks explicit branches for `V = 0`, infeasible `K`, `Dℓ < τ`, solver direction, and separate random seeds for flow noise and Gumbel sampling.
7. **No quantitative acceptance thresholds:** the protocol correctly says fidelity must be measured, but “computationally useful” and “fidelity” need predeclared primary metrics, statistical tests, and speed targets.
8. **External verification gap:** data, geometry, ROOT schema, external repositories, and cited references are not independently verified in this audit environment.

### Bottom line
The specification is **structurally sound and worth implementing**. The central physics correction — monotone **remaining budget**, not monotone **layer deposit** — is correct. The anti-dust decoder theorem is correct under its assumptions. The largest risks are not algebraic; they are **data-contract ambiguity, threshold semantics, implementation enforcement, and empirical evaluation discipline**.

---

# 1. Audit Scope, Method, and Assurance

## 1.1 Audit objective
Determine whether the CBSC-ZDC specification is:

1. internally consistent;
2. mathematically sound under its stated assumptions;
3. physically reasonable for neutron-induced hadronic ZDC showers;
4. implementable as a reproducible experiment;
5. protected against the previously identified failure modes: dense dust, invalid graph structure, exposure bias, unbounded response, and loss-only validation;
6. falsifiable as a research claim.

## 1.2 Audit method
The audit followed an iterative loop:

```text
Read specification section
→ QA check against logic/math/physics
→ Research question: what external or domain knowledge is needed?
→ QA re-check after clarification
→ Iterate finding status until stable
```

The audit was organized into cycles:

1. intake and scope;
2. claims and assurance;
3. physics basis;
4. data contract;
5. statistical factorization;
6. longitudinal cascade;
7. count model and exact decoder;
8. conditional flow matching;
9. training and exposure bias;
10. evaluation, baselines, and literature;
11. implementation contract and scaffold status;
12. consolidated findings.

## 1.3 Assurance statement
This audit confirms that the **mathematical invariants appear correct as written**, especially:

- monotone remaining budget;
- exact support count;
- exact threshold consistency;
- exact layer and event accounting.

It does **not** confirm Geant4 fidelity, speed, or production readiness.

---

# 2. Chronological Source Log

The following sources were used in the order they entered the audit. “Verification” means verification within this environment.

| Source ID | Audit time index | Source | Use in audit | Verification status |
|---|---:|---|---|---|
| SRC-01 | T0 | User request: “fully audit. QA, research, QA, and iterate…” | Defined audit mandate and logging requirement. | Direct instruction. |
| SRC-02 | T1 | Provided knowledge-base text of `CBSC_ZDC_Auditor_Specification_LaTeX.pdf` | Primary audited artifact. | Full text available in prompt; no binary hash or file system access. |
| SRC-03 | T2 | Title, abstract, assurance statement | Determined document status: research design, not fidelity claim. | Verified from text. |
| SRC-04 | T3 | Section 1: Scope, status, precise claim | Extracted research question and claims C1–C4. | Verified from text. |
| SRC-05 | T4 | Section 1.3: Relationship to previous project models | Identified negative evidence from legacy HurdleGraph and HGF-ZDC. | Internal project claims; not externally verified. |
| SRC-06 | T5 | Section 2: Physics basis | Audited neutron/hadronic shower rationale. | Consistent with general HEP calorimetry knowledge. |
| SRC-07 | T6 | Section 2 references to Geant4 hadronic physics | Supported stochastic interaction claim. | Citations present; external live verification not performed. |
| SRC-08 | T7 | Section 3: Data contract and condition manifold | Audited sole raw condition, static geometry, entry position, target mode, energy support. | Text verified; data not verified. |
| SRC-09 | T8 | Section 4: Statistical factorization | Audited joint decomposition and latent variable role. | Found notation and latent-prior ambiguity. |
| SRC-10 | T9 | Section 5: Longitudinal cascade model | Audited hurdle, response, first-visible layer, active layers, masked simplex. | Mathematically mostly sound; semantic clarifications needed. |
| SRC-11 | T10 | Section 6: Finite-support count model | Audited categorical count and threshold feasibility. | Requires explicit feasibility masking. |
| SRC-12 | T11 | Section 7: Parallel conditional flow-matching spatial model | Audited CFM state, objective, velocity network, sampling. | Sound; needs t-dependence and causal-edge QA. |
| SRC-13 | T12 | Section 8: Exact sparsity and anti-dust decoder | Audited theorem, proof, corollary, Top-k limitations. | Theorem correct under preconditions. |
| SRC-14 | T13 | Section 9: Training objectives | Audited modular loss and exposure-bias mitigation. | Sound; needs loss-weight protocol and support-training clarity. |
| SRC-15 | T14 | Section 10: Data pipeline and provenance | Audited ROOT audit plan, canonical tensors, splitting, range experiment. | Strong; requires actual execution. |
| SRC-16 | T15 | Section 11: Staged implementation and Vertex AI plan | Audited stage sequence, job layout, precision plan. | Strong; stages are reporting locations, not pass/fail gates. |
| SRC-17 | T16 | Section 12: Baselines and controlled comparisons | Audited internal and external baseline ladder. | Strong; external reproduction depends on license/data/code availability. |
| SRC-18 | T17 | Section 13: QA and reporting | Audited algebraic QA, monitoring, distributional evaluation, downstream studies. | Comprehensive; needs quantitative thresholds. |
| SRC-19 | T18 | Section 14: Failure modes | Audited failure-mode table and required diagnoses. | Useful and largely complete. |
| SRC-20 | T19 | Section 15: Implementation contract | Audited tensor interface, hyperparameters, pseudocode. | Pseudocode needs branching and feasibility corrections. |
| SRC-21 | T20 | Section 16: Software QA status of scaffold | Audited claim of 30 passed tests and 100% synthetic coverage. | Accepted as stated; not independently executed. |
| SRC-22 | T21 | Section 17: Research literature audit and evidence depth | Audited distinction between 600-work catalogue and core bibliography. | Honest evidence-depth disclosure. |
| SRC-23 | T22 | Sections 18–19: Explanations for judge and HEP physicist | Checked consistency of public-facing claims. | Consistent with technical content. |
| SRC-24 | T23 | Section 20: Conclusions | Checked claim boundaries. | Appropriately restrained. |
| SRC-25 | T24 | Appendix A: Claim-to-evidence map | Audited claim mapping. | Mostly sound; internal evidence not externally verifiable. |
| SRC-26 | T25 | Appendix B: Chronological design corrections | Audited design evolution. | Useful; supports corrective validity. |
| SRC-27 | T26 | Appendix C: Recommended auditor checklist | Used as final checklist basis. | Strong; expanded in this audit. |
| SRC-28 | T27 | References [1]–[45] in the document | Used as cited support for Geant4, calorimeter flows, CFM, sparse models, ZDC baselines. | Bibliographic metadata inspected from text; no live external verification. |
| SRC-29 | T28 | General domain knowledge of ML/HEP calorimeter simulation | Sanity checks for flow matching, Gumbel-Top-k, sparsemax, CaloFlow, Geant4 concepts. | Internal model knowledge; not live citation verification. |

---

# 3. Chronological Thought Log

This is a distilled audit trail, not a private stream-of-consciousness dump. Each entry records an audit-relevant thought and the action it triggered.

| Thought ID | Time | Audit thought | QA / research / iteration triggered |
|---|---:|---|---|
| TH-01 | T0 | The user asks for a full audit with separate chronological logs. The output must be structured, not just a summary. | Created source, thought, idea, QA, research, and iteration logs. |
| TH-02 | T1 | The only concrete evidence is the provided PDF text. I must not claim code execution or data inspection. | Added explicit audit limitation. |
| TH-03 | T2 | The document repeatedly says it is not a fidelity claim. The audit should respect that boundary. | Separated structural validity from empirical fidelity. |
| TH-04 | T3 | Claim C1 rejects monotone layer deposits. This is physically plausible for neutrons. | Checked against hadronic shower physics; accepted. |
| TH-05 | T4 | The research question is conditional density estimation: `pθ(Y | pµ, G) ≈ pG4(Y | pµ, G)`. This is well posed if data support is known. | Added data-contract audit as high priority. |
| TH-06 | T5 | Prior project models are internal negative evidence. They motivate design choices but are not externally verifiable. | Marked internal audits as evidence-limited. |
| TH-07 | T6 | Neutrons do not ionize continuously before interaction; late starts are real. Therefore `D_{ℓ+1} ≤ D_ℓ` is wrong. | Validated central design correction. |
| TH-08 | T7 | Geant4 hadronic physics is model- and cross-section-dependent. The surrogate should emulate scored readout, not microscopic truth. | Accepted “scored target” framing. |
| TH-09 | T8 | The sole raw condition is four-momentum. Entry position is deterministic if vertex and plane are fixed. This does not create new coverage. | Added condition-manifold warning. |
| TH-10 | T9 | The mass-shell relation needs a numeric tolerance. “Source precision” is too vague for an implementation contract. | Raised minor finding: specify tolerance. |
| TH-11 | T10 | `E` in the mass-shell relation is total energy. But calorimeter response is often related to kinetic energy. `ρ = T/E` needs convention. | Raised major finding: freeze energy convention. |
| TH-12 | T11 | Raw-deposit mode and thresholded-readout mode are scientifically distinct. The threshold must be frozen for reproducibility. | Accepted; added threshold-provenance requirement. |
| TH-13 | T12 | The factorization uses shared latent `z` but does not show `p(z)` or marginalization. This is a probabilistic specification gap. | Raised major finding: add latent prior/objective. |
| TH-14 | T13 | `S` appears as first-visible layer and selected cell set. This creates ambiguity in Eq. (12). | Raised major notation finding. |
| TH-15 | T14 | The visible hurdle sets all budgets and counts to zero when `V=0`. But in thresholded mode, subthreshold-only raw events may have zero resolved hits but positive raw residual. | Raised major threshold-semantics finding. |
| TH-16 | T15 | Beta mixture on `(0,1)` cannot represent endpoint mass at 0 or 1. Hurdle handles zero, but endpoint `ρ=1` needs explicit component. | Raised minor finding. |
| TH-17 | T16 | First-visible-layer survival normalizes over detector layers. If there is probability of starting after the detector, normalization hides a physical leakage/outside state. | Raised minor survival-model finding. |
| TH-18 | T17 | Masked-simplex allocation gives inactive layers exact zero by `-∞` logits. Active layers remain strictly positive. This is acceptable if “active” means nonzero raw layer. | Noted implementation detail. |
| TH-19 | T18 | Proposition 5.1 proves monotone remaining budget, not monotone deposits. The proof is trivial and correct. | QA passed. |
| TH-20 | T19 | Count model categorical support `0..Nℓ` is flexible, but feasibility depends on `Dℓ`, `τ`, and geometry. Must mask before sampling. | Raised major count-feasibility finding. |
| TH-21 | T20 | For thresholded mode, if `Dℓ < τ`, `Kℓ=0` and budget becomes residual. This is a good anti-dust rule. | QA passed; needs implementation assertion. |
| TH-22 | T21 | The flow state has support-ranking and positive-share channels. This is a reasonable continuous relaxation for later exact Top-k. | Accepted design. |
| TH-23 | T22 | The target share encoding uses mean-centered log excess. Softmax is shift-invariant, so it approximately recovers normalized excess if `ε` is small. | Raised minor numerical-transform finding. |
| TH-24 | T23 | CFM velocity must depend on time `t`. The document explicitly warns against ignoring `t`. This should be a unit test. | Added QA test requirement. |
| TH-25 | T24 | Graph edges must be physical, not array-slot. Prior models had invalid graph correspondence. Edge provenance is critical. | Added graph-audit requirement. |
| TH-26 | T25 | Causal layer attention is good, but graph message passing could leak future information if longitudinal edges are not strictly directed. | Raised major graph-causality finding. |
| TH-27 | T26 | Gumbel-Top-k gives exact support size. It does not guarantee correct occupancy if the count model is wrong. The document acknowledges this. | Accepted; reinforced count calibration reporting. |
| TH-28 | T27 | The anti-dust theorem is correct if `B ≥ Kτ`, `1 ≤ K ≤ Nℓ`, and weights are positive and normalized. | QA passed; precondition enforcement required. |
| TH-29 | T28 | Corollary 8.2 gives event accounting. It requires consistent definition of `Uℓ` and `Rres` across modes. | Added accounting-mode clarification. |
| TH-30 | T29 | Hard Top-k is non-differentiable. The specification correctly says support training needs supervised or relaxed objectives. | Accepted. |
| TH-31 | T30 | The loss is modular. But loss weights can hide physics errors if tuned against test metrics. The document says weights should be frozen on validation. | Accepted; added weight-reporting requirement. |
| TH-32 | T31 | ROOT audit list is strong. But the attached ROOT file is only a schema fixture; no numerical audit was possible here. | Marked data audit as future required execution. |
| TH-33 | T32 | Splitting by Geant4 job/run/seed is correct. Row-hash splitting is a fallback with leakage risk. | Accepted. |
| TH-34 | T33 | Training-range experiment R1/R2 is a good controlled comparison. It should not be interpreted as pileup learning. | Accepted. |
| TH-35 | T34 | Staged implementation separates truth-conditioned and free-running evaluation. This is essential for exposure bias. | Accepted. |
| TH-36 | T35 | Baseline ladder is strong: empirical, no-graph, mixture, full graph, single-stage, serial, point-cloud. This makes the experiment falsifiable. | Accepted. |
| TH-37 | T36 | External ALICE ZDC baselines are methodologically relevant but not directly transferable to 6,790 channels. The document says this. | Accepted. |
| TH-38 | T37 | QA section is comprehensive but lacks predeclared numeric acceptance thresholds. | Raised major evaluation-criteria finding. |
| TH-39 | T38 | Pseudocode does not branch on `V=0` or infeasible counts. It could sample nonsense if implemented literally. | Raised major implementation-contract finding. |
| TH-40 | T39 | Scaffold claims 30 passed tests and 100% synthetic coverage. This is useful but not fidelity evidence. | Accepted with caveat. |
| TH-41 | T40 | Literature audit honestly distinguishes core checked references from a 600-work discovery map. This is responsible. | Accepted. |
| TH-42 | T41 | The document’s own chronological corrections show the design converged by eliminating false constraints. This supports audit confidence. | Accepted. |
| TH-43 | T42 | Final synthesis: no critical mathematical flaw; major issues are specification clarification and enforcement. | Produced final verdict: pass with corrections. |

---

# 4. Chronological Idea Log

These ideas emerged during the audit and are ordered by when they became relevant.

| Idea ID | Time | Idea | Rationale | Priority |
|---|---:|---|---|---|
| IDEA-01 | T3 | Add an explicit “audit status” banner to every section: structural, empirical, or implementation. | Prevents readers from confusing design validity with Geant4 fidelity. | P2 |
| IDEA-02 | T9 | Rename first-visible layer from `S` to `F` and selected hit set from `Sℓ` to `Hℓ`. | Removes notation collision. | P0 |
| IDEA-03 | T11 | Define `E` as total energy or kinetic energy in the data contract. | Needed for `ρ = T/E` support. | P0 |
| IDEA-04 | T12 | Add explicit numeric mass-shell tolerance, e.g. `|E² - |p|² - m_n²| / m_n² < δ`. | Makes preprocessing auditable. | P1 |
| IDEA-05 | T13 | Add `p(z) = N(0,I)` to the joint factorization and state whether training marginalizes or samples `z`. | Makes probabilistic model complete. | P0 |
| IDEA-06 | T14 | Introduce separate variables: `V_raw`, `V_readout`, `T_raw`, `T_readout`, `U_total`. | Resolves threshold-mode ambiguity. | P0 |
| IDEA-07 | T15 | Use zero-one-inflated beta or beta mixture plus endpoint mass for `ρ`. | Handles `ρ=1` and possible endpoint behavior. | P1 |
| IDEA-08 | T16 | Add an explicit “first visible outside detector” or “no visible inside” state to survival model. | Avoids silent renormalization. | P1 |
| IDEA-09 | T18 | Log reserve fraction `Rres/T` as a primary diagnostic. | Reserve can hide profile misspecification. | P1 |
| IDEA-10 | T19 | Enforce count feasibility by masking logits before categorical sampling. | Prevents decoder precondition violations. | P0 |
| IDEA-11 | T20 | Add a deterministic fallback: if generated `K` is infeasible, project to `min(K, floor(D/τ), Nℓ)` and log the event. | Defensive implementation. | P1 |
| IDEA-12 | T22 | Version the flow target transform `(s*, r*)` together with the decoder. | Prevents train/sample mismatch. | P1 |
| IDEA-13 | T23 | Add a unit test: permute `t` and assert velocity changes. | Detects ignored time conditioning. | P0 |
| IDEA-14 | T25 | Add edge-direction causality test: assert no path from deeper to shallower layers in longitudinal edges. | Prevents future leakage. | P0 |
| IDEA-15 | T26 | Add graph connectivity report: isolated valid nodes, degree histogram, component sizes. | Detects invalid geometry graph. | P1 |
| IDEA-16 | T27 | Report requested-count calibration and realized-count calibration separately. | Top-k exactness does not fix bad counts. | P1 |
| IDEA-17 | T28 | Add property-based decoder fuzzing over random `B, K, τ, Nℓ`. | Strengthens algebraic QA. | P1 |
| IDEA-18 | T30 | Compare hard Top-k with sparsemax/entmax/hard-concrete as ablations, not defaults. | Document already suggests this; keep as optional. | P2 |
| IDEA-19 | T31 | Publish loss-weight selection protocol and freeze weights before test evaluation. | Prevents test-set tuning. | P1 |
| IDEA-20 | T33 | Add leakage audit: nearest-neighbor event similarity across train/validation/test. | Detects duplicated Geant4 events. | P1 |
| IDEA-21 | T35 | Add exposure-bias matrix: truth vs generated profile/count/support combinations. | Isolates error sources. | P1 |
| IDEA-22 | T37 | Predeclare primary metrics and pass/fail or target ranges. | Makes “useful” falsifiable. | P0 |
| IDEA-23 | T38 | Expand pseudocode into a state machine with explicit zero-response and residual paths. | Prevents implementation ambiguity. | P0 |
| IDEA-24 | T39 | Add timing targets: model-only and end-to-end, batch size, hardware, precision, solver NFE. | Needed for speed claims. | P1 |
| IDEA-25 | T41 | Keep the 600-reference catalogue as supplementary discovery map, not evidence for specific claims. | Preserves evidence depth honesty. | P2 |

---

# 5. Iterative QA / Research / QA Cycles

Each cycle below shows how the audit was iterated.

## Cycle 1: Intake and scope

| Item | Content |
|---|---|
| QA question | Is the request actionable? What is the artifact? |
| Research need | None beyond supplied text. |
| QA result | The artifact is a specification, not trained model. Audit must be specification-level. |
| Iteration | Restricted claims to textual/mathematical audit; added limitation statement. |

## Cycle 2: Claims and assurance

| Item | Content |
|---|---|
| QA question | Are claims C1–C4 consistent with the rest of the document? |
| Research need | Hadronic shower physics; Geant4 stochasticity. |
| QA result | C1 is physically sound. C2 is true: components are known. C3 is conditionally true. C4 is methodologically sound. |
| Iteration | Elevated “no fidelity guarantee” to executive summary. |

## Cycle 3: Physics basis

| Item | Content |
|---|---|
| QA question | Is rejecting monotone layer deposits correct? |
| Research need | Neutron interactions, longitudinal shower profiles. |
| QA result | Correct. Neutron showers can start late and grow. Monotone remaining budget is the right conservation structure. |
| Iteration | Accepted Proposition 5.1 as central invariant. |

## Cycle 4: Data and condition manifold

| Item | Content |
|---|---|
| QA question | Is `pµ` truly the sole raw condition? Is entry position independent? |
| Research need | Fixed-gun vertex geometry. |
| QA result | Entry position is deterministic from `pµ` if vertex/plane fixed. No new coverage. |
| Iteration | Added condition-manifold warning and `pz` division guard. |

## Cycle 5: Statistical factorization

| Item | Content |
|---|---|
| QA question | Is the joint factorization complete? |
| Research need | Latent-variable generative model conventions. |
| QA result | Missing explicit `p(z)`; notation collision on `S`. |
| Iteration | Created major findings F-02 and F-03. |

## Cycle 6: Longitudinal cascade

| Item | Content |
|---|---|
| QA question | Are hurdle, response, start, active layers, and profile coherent? |
| Research need | Zero-inflated continuous distributions; survival models. |
| QA result | Mostly coherent; threshold semantics and endpoint mass need clarification. |
| Iteration | Added findings on `V` semantics and beta endpoint handling. |

## Cycle 7: Count model and decoder

| Item | Content |
|---|---|
| QA question | Does the exact decoder prove what it claims? |
| Research need | Gumbel-Top-k, thresholded sparse decoding. |
| QA result | Theorem and corollary are correct under preconditions. Feasibility must be enforced. |
| Iteration | Added mandatory count-feasibility masking and decoder assertions. |

## Cycle 8: Flow model

| Item | Content |
|---|---|
| QA question | Is parallel CFM with graph and causal attention well specified? |
| Research need | Conditional flow matching, graph neural networks, causal masking. |
| QA result | Sound, but requires t-dependence tests, edge-direction audit, and target-transform versioning. |
| Iteration | Added QA tests for `t` dependence and graph causality. |

## Cycle 9: Training and exposure bias

| Item | Content |
|---|---|
| QA question | Will truth-conditioned training hide free-running errors? |
| Research need | Exposure bias in sequential/hierarchical generative models. |
| QA result | The staged generated-condition exposure is appropriate. |
| Iteration | Recommended cross-combination matrix and joint fine-tuning as optional. |

## Cycle 10: Evaluation and baselines

| Item | Content |
|---|---|
| QA question | Is the comparison protocol falsifiable? |
| Research need | Calorimeter generative evaluation practices. |
| QA result | Strong diagnostics, but no quantitative acceptance thresholds. |
| Iteration | Added major finding: predeclare primary metrics and speed targets. |

## Cycle 11: Implementation contract

| Item | Content |
|---|---|
| QA question | Can the pseudocode be implemented without ambiguity? |
| Research need | Defensive sampling, feasibility constraints. |
| QA result | Pseudocode lacks branches for zero response, infeasible counts, residual routing, and solver details. |
| Iteration | Added corrected pseudocode requirements. |

## Cycle 12: Literature and evidence depth

| Item | Content |
|---|---|
| QA question | Are claims supported at the right evidence depth? |
| Research need | Known calorimeter ML literature. |
| QA result | Core claims are plausible; external references not live-verified. Internal audits are not public. |
| Iteration | Added evidence-depth caveats. |

---

# 6. Detailed Findings

Finding IDs:

- `F-xx`: finding;
- severity: Critical / Major / Minor / Editorial;
- status: Open unless noted.

---

## 6.1 Scope, status, and claim findings

### F-01 — Document status is clear and appropriate
**Severity:** Informational  
**Status:** Pass

The document clearly states that it is:

- an auditor-ready design specification;
- not a report of validated physics performance;
- not a claim that CBSC-ZDC has been trained;
- not a guarantee of Geant4 agreement.

This is one of the strongest aspects of the specification.

---

### F-02 — Claims C1–C4 are mostly well bounded
**Severity:** Informational  
**Status:** Pass with minor clarification

C1, rejecting monotone per-layer deposits, is physically correct.  
C2, using known components, is accurate.  
C3, decoder invariants, is conditionally correct.  
C4, separating implementation validity from empirical fidelity, is methodologically correct.

**Recommendation:** keep this framing in all future papers and reports.

---

## 6.2 Physics findings

### F-03 — Monotone remaining budget is the correct conservation structure
**Severity:** Informational  
**Status:** Pass

Proposition 5.1 is correct:

\[
R_\ell = T - \sum_{j=0}^{\ell} D_j
\]

implies

\[
R_{\ell+1} \le R_\ell
\]

without requiring

\[
D_{\ell+1} \le D_\ell.
\]

This correctly permits late-starting, growing, fluctuating hadronic showers.

---

### F-04 — “Visible” must be defined as raw-visible or readout-visible
**Severity:** Major  
**Status:** Open

The specification uses “visible-response indicator” `V`. In raw-deposit mode this can mean `T_raw > 0`. In thresholded-readout mode it could mean “at least one cell ≥ τ”.

Problem:

- If `V = 0` forces all budgets, counts, and residuals to zero, then a raw event with only subthreshold deposits cannot be represented with positive residual `U`.
- If `V = 1` means raw-visible, then an event can have `V = 1` but zero resolved thresholded hits.

**Required correction:** define explicitly:

```text
V_raw      = 1 iff raw total response T_raw > 0
V_readout  = 1 iff at least one readout cell ≥ τ
T_raw      = total raw deposited energy used in accounting
T_readout  = sum of thresholded cell energies
U_total    = sum of subthreshold residuals
Rres       = profile/accounting reserve
```

Then state which variables the hurdle models. For the current accounting identity, `V_raw` is the appropriate hurdle for raw total response.

---

### F-05 — Energy convention for `E` must be frozen
**Severity:** Major  
**Status:** Open

The mass-shell relation implies `E` is total energy:

\[
E^2 - p_x^2 - p_y^2 - p_z^2 = m_n^2.
\]

But calorimeter response is often compared to kinetic energy:

\[
K = E - m_n.
\]

The support assumption `ρ = T/E ∈ [0,1]` depends on this convention.

**Required correction:** state one of:

1. `E` is total energy, and `T/E` is audited accordingly; or  
2. `E_kin` is used for response fraction, with mass-shell validation still using total energy.

Also specify tolerance and overflow handling.

---

### F-06 — First-visible layer is not microscopic first interaction
**Severity:** Minor  
**Status:** Pass with note

The document correctly warns that `S` is first visible layer, not necessarily first nuclear interaction. This should remain prominent because it prevents overinterpretation.

---

### F-07 — Survival model should handle probability of no start inside detector
**Severity:** Minor  
**Status:** Open

The hazard model defines unnormalized probabilities:

\[
\tilde p_\ell = h_\ell \prod_{j<\ell}(1-h_j)
\]

and normalizes across detector layers. If the unnormalized sum is less than one, normalization silently conditions on starting inside the detector.

**Recommendation:** add either:

- an explicit terminal state `S = L` meaning first visible response outside scored detector; or
- a statement that normalization is conditional on `V = 1` and `S < L`.

---

## 6.3 Data-contract findings

### F-08 — ROOT audit plan is strong but unexecuted
**Severity:** Major in practice, Minor in specification  
**Status:** Open

The required ROOT audit items are appropriate:

- file hashes;
- branch names and units;
- mass-shell residuals;
- channel-ID decoding;
- duplicate/invalid IDs;
- ECAL/HCAL total reconciliation;
- zero-response frequency;
- threshold sensitivity;
- provenance for splitting.

However, this audit could not execute those checks.

**Required action:** produce a data-contract report before training.

---

### F-09 — Threshold choice must be physically justified
**Severity:** Major  
**Status:** Pass with requirement

The document correctly says threshold must not be chosen merely to make optimization easier.

**Required action:** freeze `τ` with provenance:

- detector/electronics threshold;
- analysis threshold;
- or raw mode `τ = 0`.

Record the choice in the resolved config and geometry hash.

---

### F-10 — Subthreshold residual requires raw truth
**Severity:** Major  
**Status:** Open

The residual

\[
U_\ell = \sum_{i:\ell_i=\ell} Y_i 1\{0 < Y_i < \tau\}
\]

can only be computed if raw deposits are available.

If only thresholded readout is available, `Uℓ` is unknown. Then event accounting must either:

1. define `T` as thresholded sum and drop `U`; or  
2. require raw Geant4 deposits.

**Required correction:** state which data fields are mandatory for thresholded mode.

---

### F-11 — Entry-position formula needs guard against `pz = 0`
**Severity:** Minor  
**Status:** Open

The intercept formulas divide by `pz`:

\[
x_{\text{entry}} = x_0 + (z_{\text{det}} - z_0)\frac{p_x}{p_z}
\]

For a ZDC, `pz` should be large and positive, but implementation should guard:

- reject non-forward events;
- or clamp/flag small `|pz|`.

---

### F-12 — Condition manifold must match Geant4 gun
**Severity:** Minor  
**Status:** Pass with note

The document correctly says arbitrary edge-entry claims require new Geant4 data. This is important. Any extrapolation in angle or entry position should be labeled OOD/stress.

---

## 6.4 Statistical factorization findings

### F-13 — Notation collision on `S`
**Severity:** Major / Editorial  
**Status:** Open

`S` is used for:

1. first-visible layer;
2. selected cell set `Sℓ`.

Equation (12) contains `S` twice in the joint variable list, which is ambiguous.

**Required correction:** rename:

```text
F     = first visible layer
Hℓ    = selected hit/support set in layer ℓ
```

Then update factorization:

\[
p(Y,V,F,A,T,D,R_{\text{res}},K,H \mid c,G)
\]

---

### F-14 — Missing explicit latent prior
**Severity:** Major  
**Status:** Open

The factorization conditions on shared latent `z`, but the joint does not show:

\[
p(z) = \mathcal N(0,I).
\]

Also unclear whether the training objective:

1. approximates a marginalized likelihood;
2. uses sampled `z` as a stochastic conditioning variable;
3. uses an encoder/inference network.

**Required correction:** add either:

\[
p_\theta(\cdot \mid c,G) = \int p(z) p_\theta(\cdot \mid c,z,G) dz
\]

or state that training and sampling use `z ∼ N(0,I)` without marginal likelihood interpretation.

---

### F-15 — Factorization order is generative, not necessarily causal
**Severity:** Minor  
**Status:** Pass with note

The order samples total response before first-visible layer, but physically first interaction depth influences total response. This is acceptable for a generative factorization if the joint distribution is correct.

**Recommendation:** avoid causal language unless supervised by microscopic truth.

---

## 6.5 Longitudinal cascade findings

### F-16 — Hurdle is appropriate
**Severity:** Informational  
**Status:** Pass

A Bernoulli hurdle is appropriate for the point mass at zero response. It is better than forcing a continuous density to approximate a delta function.

---

### F-17 — Beta mixture should allow endpoint masses
**Severity:** Minor  
**Status:** Open

The beta mixture is defined on `(0,1)`. If data have mass at `ρ = 1`, clipping is not enough.

**Recommendation:** use one of:

- beta mixture plus explicit `ρ = 1` atom;
- zero-one-inflated beta;
- target-correct unbounded/overflow component if `T > E` occurs.

---

### F-18 — Active-layer model should not force contiguous layers
**Severity:** Minor  
**Status:** Pass

The specification correctly allows gaps after the first visible layer. This is appropriate for sparse readout and fluctuating showers.

---

### F-19 — Masked-simplex reserve needs interpretation control
**Severity:** Minor  
**Status:** Pass with requirement

The reserve `Rres` is an accounting variable. The document correctly says its interpretation must be frozen.

**Required reporting:**

- `Rres/T` distribution;
- correlation of reserve with late energy, leakage, and profile error;
- warning if reserve absorbs too much budget.

---

## 6.6 Count model findings

### F-20 — Count feasibility must be enforced
**Severity:** Major  
**Status:** Open

For thresholded mode, feasible counts satisfy:

\[
1 \le K_\ell \le \min(N_\ell, \lfloor D_\ell/\tau \rfloor)
\]

when `Dℓ ≥ τ`. For raw mode `τ = 0`, feasible counts satisfy:

\[
K_\ell = 0 \iff D_\ell = 0,
\quad
1 \le K_\ell \le N_\ell \iff D_\ell > 0.
\]

The categorical count model must mask infeasible values before sampling and before loss computation where appropriate.

**Required implementation:**

```python
feasible = (K <= N_layer)
if tau > 0:
    feasible &= (K == 0) | ((K >= 1) & (K <= floor(D / tau)))
else:
    feasible &= (D > 0) == (K >= 1)
```

---

### F-21 — Count calibration is a primary physics object
**Severity:** Informational  
**Status:** Pass

The document correctly says exact support decoding transfers occupancy fidelity into the count model. Therefore count calibration must be reported separately from total loss.

---

## 6.7 Anti-dust decoder findings

### F-22 — Theorem 8.1 is correct under preconditions
**Severity:** Informational  
**Status:** Pass

Given:

- `B > 0`;
- integer `K` with `1 ≤ K ≤ Nℓ`;
- `B ≥ Kτ`;
- selected set size `K`;
- positive normalized weights on selected set;

the decoder satisfies:

1. exact zeros outside selected set;
2. selected cells ≥ τ;
3. layer sum equals `B`;
4. exactly `K` positive cells;
5. no forbidden dust `0 < Ŷi < τ`.

The proof is correct.

---

### F-23 — Decoder preconditions must be runtime assertions
**Severity:** Major  
**Status:** Open

The theorem does not protect against an invalid generated count. The implementation must assert:

```text
Kℓ integer
0 ≤ Kℓ ≤ Nℓ
if τ > 0 and Kℓ > 0: Dℓ ≥ Kℓ τ
if τ = 0: Kℓ = 0 iff Dℓ = 0
```

If assertions fail, the sample should be rejected, repaired, or logged as invalid.

---

### F-24 — Degenerate case `B = Kτ` needs stable handling
**Severity:** Minor  
**Status:** Open

If `B = Kτ`, then:

\[
Ŷ_i = τ
\]

for all selected cells. The share weights become irrelevant. Implementation should avoid numerical issues from softmax over share logits when `B - Kτ = 0`.

**Recommendation:** if `B - Kτ` is below tolerance, assign equal shares or skip share normalization.

---

### F-25 — Event accounting corollary is correct if modes are consistent
**Severity:** Informational  
**Status:** Pass

The identity

\[
\sum_i \hat Y_i + \sum_\ell U_\ell + R_{\text{res}} = T
\]

is correct if:

- `Uℓ` is defined for thresholded mode;
- `Uℓ = 0` for raw mode;
- each layer decoder is exact.

---

## 6.8 Conditional flow-matching findings

### F-26 — Parallel CFM is well motivated
**Severity:** Informational  
**Status:** Pass

Parallel node updates avoid:

- invalid layer-slot correspondence from serial rollouts;
- accumulated free-running error;
- serial latency.

Causal layer attention and directed longitudinal edges preserve depth ordering.

---

### F-27 — Velocity field must provably depend on `t`
**Severity:** Major QA  
**Status:** Pass with required test

The document correctly warns that a network accepting but ignoring `t` is not the specified field.

**Required QA test:**

- sample same `X`, condition, geometry;
- evaluate velocity at different `t`;
- assert output differs beyond numerical tolerance.

---

### F-28 — Graph causality must be tested
**Severity:** Major  
**Status:** Open

Causal transformer masking is not enough if graph edges allow deeper-to-shallower message passing.

**Required edge contract:**

- lateral edges: within same layer or explicitly non-causal;
- longitudinal edges: directed shallow → deep only;
- no path from layer `j` to layer `i` when `j > i`.

**Required QA:**

- graph reachability test;
- edge-direction unit test;
- invalid-edge rejection test.

---

### F-29 — Flow target transform must be versioned
**Severity:** Minor  
**Status:** Open

The support and share encodings:

\[
s_i^* = \operatorname{logit}(\epsilon + (1-2\epsilon)M_i)
\]

\[
r_i^* = M_i \left[
\log(Y_i - \tau + \epsilon)
- \frac{1}{K_{\ell_i}}
\sum_{j \in S_{\ell_i}} \log(Y_j - \tau + \epsilon)
\right]
\]

are reasonable but not unique. The decoder and target transform must be versioned together.

**Recommendation:** store transform name, `ε`, and threshold in config hash.

---

### F-30 — Share encoding recovers normalized excess only approximately
**Severity:** Minor  
**Status:** Open

Because softmax is shift-invariant, if:

\[
r_i = \log(Y_i - τ + ε) - \text{constant}
\]

then:

\[
\operatorname{softmax}(r_i) \propto Y_i - τ + ε.
\]

If `ε` is small relative to excess energy, this is fine. If many selected cells are near threshold, `ε` can bias shares.

**Recommendation:** use small `ε`, report sensitivity, or use exact excess normalization for training targets.

---

## 6.9 Training-objective findings

### F-31 — Modular loss is appropriate
**Severity:** Informational  
**Status:** Pass

The loss decomposition:

\[
L = \lambda_V L_V + \lambda_\rho L_\rho + \lambda_S L_S + \lambda_A L_A + \lambda_D L_D + \lambda_K L_K + \lambda_{FM} L_{FM} + \lambda_{sup} L_{sup} + \lambda_{aux} L_{aux}
\]

is appropriate for a hierarchical model.

---

### F-32 — Loss weights must be frozen before test evaluation
**Severity:** Minor  
**Status:** Pass with requirement

The document says weights should be selected on frozen validation. This should be enforced by:

- saving `loss_weights.yaml`;
- hashing it into the experiment ID;
- reporting all unweighted losses.

---

### F-33 — Support training cannot rely only on hard Top-k
**Severity:** Major QA  
**Status:** Pass with requirement

Hard Top-k is non-differentiable. The specification correctly recommends:

- supervised support logits;
- ranking loss;
- continuous relaxation;
- straight-through estimator;
- generated-support exposure.

This must be implemented, not optional, for trainable support.

---

### F-34 — Exposure-bias plan is strong
**Severity:** Informational  
**Status:** Pass

Stages 4–6 are appropriate:

1. truth profile/count/support;
2. generated profile/count/support;
3. optional joint fine-tuning.

Recommended additional report:

| Profile source | Count source | Support source | Metric delta |
|---|---|---|---|
| truth | truth | truth | baseline |
| generated | truth | truth | profile error |
| truth | generated | truth | count error |
| truth | truth | generated | support error |
| generated | generated | generated | full cascade |

---

## 6.10 Evaluation and baseline findings

### F-35 — Evaluation diagnostics are comprehensive
**Severity:** Informational  
**Status:** Pass

The recommended diagnostics are strong:

- conditional 1-D histograms;
- classifier two-sample tests;
- geometry-aware classifiers;
- Fréchet/kernel distances;
- precision/recall;
- memorization checks;
- truth-half floors;
- repeated-condition ensembles;
- downstream reconstruction.

---

### F-36 — No quantitative acceptance criteria
**Severity:** Major  
**Status:** Open

The specification says fidelity must be measured but does not define numeric targets for:

- total response KS or Wasserstein distance;
- layer-profile error;
- occupancy error;
- C2ST accuracy;
- reconstruction resolution closure;
- speedup versus Geant4;
- memory budget;
- inference latency.

**Required correction:** predeclare primary and secondary metrics, with statistical uncertainty and decision labels:

```text
improvement / plateau / regression / inconclusive
```

Optionally define target ranges for production usefulness.

---

### F-37 — Baseline ladder is strong
**Severity:** Informational  
**Status:** Pass

The internal ladder is appropriate:

- B0 empirical/template;
- B1 non-graph CFM;
- M1 mixture-of-experts;
- G1 full CBSC-ZDC;
- S1 single-stage graph flow;
- A1 serial layer model;
- P1 sparse point-cloud model.

This makes the scientific question falsifiable.

---

### F-38 — External ZDC baselines need license and representation audit
**Severity:** Minor  
**Status:** Open

ALICE ZDC repositories are relevant but not directly transferable to 6,790 irregular channels.

**Required action:** for each external baseline, record:

- license;
- commit hash;
- native representation;
- adaptation changes;
- whether comparison is direct or adapted.

---

## 6.11 Implementation-contract findings

### F-39 — Tensor interface is mostly clear
**Severity:** Informational  
**Status:** Pass

The reference tensor interface is useful:

- `pµ [B,4]`;
- condition embedding `[B,C]`;
- node features `[6790,Fn]`;
- edge index `[2,Ne]`;
- profile budgets `[B,65]`;
- counts `[B,65]`;
- flow state `[B,6790,2]`;
- final cell energy `[B,6790]`.

---

### F-40 — Pseudocode needs explicit branches
**Severity:** Major  
**Status:** Open

Current pseudocode does not explicitly handle:

1. `V = 0`;
2. `Dℓ < τ`;
3. infeasible `Kℓ`;
4. empty selected sets;
5. solver direction and step grid;
6. separate seeds for flow noise and Gumbel sampling;
7. deterministic Top-k diagnostic mode.

**Recommended corrected structure:**

```python
function SAMPLE(p4, geometry, seed):
    validate_units_shape_mass_shell(p4)
    c = condition_encoder(minimal_features(p4))
    z = Normal(0, I).sample(seed.z)

    V = sample_visible(c, z)
    if V == 0:
        return zeros(geometry.N), zero_residuals(), zero_reserve(), diagnostics

    rho = sample_response(c, z)
    T = response_to_total(p4, rho)

    F = sample_first_visible_layer(c, z, T)
    A = sample_active_layers(c, z, T, F)
    D, reserve = sample_masked_simplex_profile(c, z, T, A)

    K = sample_layer_counts(c, z, D, A)
    K = enforce_feasibility(K, D, A, geometry, tau)

    X = Normal(0, I).sample(seed.flow)
    for t in solver_grid(0, 1):
        v = spatial_graph_field(X, t, c, geometry, D, K)
        X = solver_step(X, v, t)

    H = gumbel_topk(X.support_scores, K, geometry.valid, seed.gumbel)
    Y, U = exact_threshold_safe_decode(H, X.share_scores, D, K, tau)

    assert_structural_invariants(Y, U, reserve, T)
    return Y, diagnostics
```

---

### F-41 — Hyperparameters are starting values, not validated optima
**Severity:** Informational  
**Status:** Pass

The document correctly labels hyperparameters as pilot starting values. This avoids overclaiming.

---

## 6.12 Software QA status findings

### F-42 — Scaffold test status is honestly bounded
**Severity:** Informational  
**Status:** Pass with caveat

The scaffold claims:

- 30 passed tests;
- 100% statement/branch coverage under synthetic suite;
- no fidelity claim.

This is useful but limited.

**Required next QA:**

- integration tests with real ROOT schema;
- geometry builder tests;
- distributed dataloader tests;
- full loss orchestration tests;
- Vertex launcher dry-run;
- large-sample invariant tests.

---

### F-43 — Nested-tensor transformer warning should be profiled
**Severity:** Minor  
**Status:** Open

The warning from `norm_first=True` is not necessarily numerical failure, but timing and correctness should be profiled.

---

## 6.13 Literature and evidence findings

### F-44 — Core bibliography is appropriate
**Severity:** Informational  
**Status:** Pass with caveat

The cited works cover:

- Geant4;
- hadronic shower parameterization;
- ZDC detector context;
- CaloFlow/iCaloFlow/L2LFlows/CaloDREAM;
- flow matching;
- sparse and point-cloud calorimeter models;
- Gumbel-Top-k;
- sparsemax/entmax/hard-concrete;
- ALICE ZDC ML;
- ExpertSim;
- AtlFast3.

No live external verification was performed in this audit.

---

### F-45 — 600-work catalogue is not full-text evidence
**Severity:** Informational  
**Status:** Pass

The document correctly says the large catalogue is a discovery/contribution map, not 600 full-text replications. This is responsible and should be preserved.

---

### F-46 — Internal audits are persuasive but not externally verifiable
**Severity:** Minor  
**Status:** Open

References [5], [6], [7] are internal project evidence. They motivate design corrections but cannot be independently verified by an external auditor unless the evidence packages are provided.

---

# 7. Algebraic QA Summary

| Check | Result | Notes |
|---|---|---|
| Mass-shell condition is well defined | Pass with action | Need numeric tolerance and energy convention. |
| Proposition 5.1: monotone remaining budget | Pass | Correct and central. |
| Masked-simplex exact zero inactive layers | Pass | Active layers remain positive. |
| Count feasibility conditions | Conditional | Must mask before sampling. |
| Theorem 8.1: no-dust decoder | Pass | Requires `B ≥ Kτ`, valid `K`, positive normalized weights. |
| Corollary 8.2: event accounting | Pass | Requires consistent `Uℓ`, `Rres`, and `T`. |
| Gumbel-Top-k exact support size | Pass | Does not guarantee correct `K`. |
| CFM objective well posed | Pass | Must consume `t`. |
| Causal layer attention | Pass | Must be matched by directed graph edges. |
| Hard Top-k differentiability | Conditional | Requires supervised/relaxed support training. |

---

# 8. Research Audit

## 8.1 Research questions supported by the specification

| Research question | Is it well posed? | What evidence is needed? |
|---|---|---|
| Can CBSC-ZDC approximate `pG4(Y | pµ, G)` on 50–250 GeV? | Yes | Held-out Geant4, distributional metrics, downstream reconstruction. |
| Does monotone remaining budget fix the unphysical monotone-deposit constraint? | Yes | Shower profiles with late maxima; algebraic invariant tests. |
| Does exact Top-k remove dense dust? | Yes, structurally | Zero forbidden cells, occupancy metrics, positive-hit spectra. |
| Does graph message passing improve geometry-sensitive fidelity? | Yes, if compared to no-graph baseline | Matched B1 vs G1, geometry-aware C2ST, width/centroid metrics. |
| Does hierarchy earn its cost versus single-stage flow? | Yes | Matched S1 vs G1 with timing and fidelity. |
| Does wider 0–300 GeV training help 50–250 GeV? | Yes | R1 vs R2 experiment. |
| Is the model computationally useful? | Partially | Needs predeclared speed/memory targets. |

## 8.2 Research risks

| Risk | Severity | Mitigation |
|---|---|---|
| Data support mismatch | High | Full ROOT audit, energy-support report. |
| Threshold misdefinition | High | Freeze `τ`, define raw vs readout visibility. |
| Count model bottleneck | High | Count calibration, generated-count spatial tests. |
| Exposure bias | Medium | Generated-condition stages, cross-combination matrix. |
| Graph leakage or invalid edges | High | Edge provenance, causality tests, no-graph baseline. |
| Loss-only overfitting | Medium | Frozen validation, distributional metrics, downstream tests. |
| External baseline incompatibility | Medium | Native reproduction first, adaptation disclosed. |
| Overinterpretation of latent `z` | Low | State `z` is statistical, not physical. |

---

# 9. Auditor Checklist with Verdicts

This expands Appendix C.

| # | Checklist item | Verdict | Required action |
|---:|---|---|---|
| 1 | ROOT branch map, units, channel codec, sentinel meaning, event counts | Not verified | Execute ROOT audit. |
| 2 | Target is raw deposit or thresholded readout, not mixed | Conditional | Freeze target mode and visibility definitions. |
| 3 | Energy-support assumption before `T/E ≤ 1` | Conditional | Audit `T > E` frequency; define `E` convention. |
| 4 | Geometry hashes and valid-node adjacency | Not verified | Build geometry audit report. |
| 5 | Sole raw condition is `pµ`; entry coordinate deterministic | Pass | Add `pz` guard. |
| 6 | Static compilation, unit tests, deterministic replay | Accepted as stated | Re-run in implementation environment. |
| 7 | Every generated tensor maps to a mathematical variable | Conditional | Rename `S` collision; add `p(z)`. |
| 8 | Flow field consumes `t`; solver documented | Conditional | Add t-dependence test. |
| 9 | Hard support is not the only gradient path | Pass in spec | Implement supervised/relaxed support loss. |
| 10 | Zero dust, exact count, accounting on large sample | Conditional | Add large-sample property tests. |
| 11 | Primary-domain and stress-domain reports separate | Pass | Keep separated. |
| 12 | Baselines matched or mismatches disclosed | Pass in spec | Execute matched comparisons. |
| 13 | Final test set not used for preprocessing or checkpoint selection | Pass in spec | Enforce manifest control. |
| 14 | Speed comparisons report hardware, batch, precision, steps | Pass in spec | Add numeric speed targets. |
| 15 | Conclusions do not exceed supported manifold | Pass | Keep OOD labels. |

---

# 10. Corrective Action Plan

## P0 — Required before training sign-off

1. **Rename ambiguous variables**
   - `S` → `F` for first-visible layer.
   - `Sℓ` → `Hℓ` for selected hit set.
   - Update Eq. (12), figures, pseudocode.

2. **Add explicit latent prior**
   - State `z ∼ N(0,I)`.
   - State whether training marginalizes or samples `z`.

3. **Define threshold semantics**
   - Define `V_raw`, `V_readout`, `T_raw`, `T_readout`, `Uℓ`.
   - State which hurdle is modeled.
   - Handle subthreshold-only raw events.

4. **Freeze energy convention**
   - State whether `E` is total or kinetic for `ρ`.
   - Define mass-shell tolerance.
   - Define overflow handling if `T > E`.

5. **Enforce count feasibility**
   - Mask categorical counts by geometry and budget.
   - Assert decoder preconditions.
   - Log infeasible sample attempts.

6. **Fix pseudocode**
   - Add zero-response branch.
   - Add residual branch for `Dℓ < τ`.
   - Add feasibility enforcement.
   - Specify solver grid and seed separation.

7. **Predeclare evaluation criteria**
   - Primary physics metrics.
   - Primary speed metrics.
   - Statistical uncertainty protocol.
   - Decision labels: improvement / regression / inconclusive.

8. **Add graph causality tests**
   - Directed longitudinal edges only.
   - No deeper-to-shallower paths.
   - Edge provenance report.

## P1 — Required before final publication or production claim

1. Execute full ROOT data audit.
2. Produce geometry graph audit.
3. Report reserve fraction diagnostics.
4. Report count calibration separately.
5. Add exposure-bias combination matrix.
6. Add large-sample invariant tests.
7. Add external baseline license/commit/representation table.
8. Add timing targets and memory budget.
9. Add threshold sensitivity study.
10. Add leakage/neares-neighbor train-test audit.

## P2 — Recommended but optional

1. Endpoint-mass response model.
2. Sparsemax/entmax/hard-concrete ablations.
3. Latent or distilled flow after fidelity teacher exists.
4. Mixture-of-experts routing.
5. Point-cloud sparse comparison.
6. Public evidence package for internal audits.

---

# 11. Updated Claim-to-Evidence Audit

| Claim in specification | Auditor verdict | Evidence status |
|---|---|---|
| Original monotone-per-layer-deposit constraint is physically inappropriate | Strongly supported | Hadronic shower physics; document argument. |
| Monotone remaining budget is correct conservation structure | Proven | Proposition 5.1. |
| Model uses known published components | Supported | References to CFM, graph models, flows, Top-k, sparse models. |
| Decoder guarantees nonnegative outputs, exact zeros, threshold consistency, accounting | Proven conditionally | Theorem 8.1 and Corollary 8.2; requires implementation enforcement. |
| Training/reporting protocol separates validity from fidelity | Supported | Document structure and assurance statement. |
| CBSC-ZDC reproduces Geant4 | Not claimed; not verified | Requires training and held-out evaluation. |
| Prior project models failed structurally | Internally supported | Internal audits; not externally verified. |
| Graph/attention hierarchy will improve fidelity | Not claimed as guaranteed | Must be tested against baselines. |
| Wider training range helps | Not claimed as guaranteed | R1/R2 experiment required. |
| Model is computationally useful | Not yet verifiable | Needs timing targets and benchmarks. |

---

# 12. Final Audit Opinion

The CBSC-ZDC specification is **well conceived, mathematically careful, and unusually honest about its limits**. Its central design choices are defensible:

1. **Reject monotone layer deposits.**  
   Correct for neutron-induced hadronic showers.

2. **Enforce monotone remaining budget.**  
   Mathematically sound and physically appropriate.

3. **Use exact count and exact support decoding.**  
   Prevents dense low-energy dust and makes accounting auditable.

4. **Use parallel CFM with graph and causal layer attention.**  
   A reasonable alternative to serial layer autoregression.

5. **Separate structural correctness from Geant4 fidelity.**  
   This is the correct scientific posture.

The specification should be approved for implementation **after the P0 corrections**. The most important corrections are not about the core model; they are about **notation, threshold semantics, energy convention, feasibility enforcement, pseudocode completeness, graph causality testing, and predeclared evaluation criteria**.

If those corrections are made, the resulting experiment should be:

- structurally valid;
- reproducible;
- falsifiable;
- protected against the earlier project failure modes;
- ready for controlled comparison with baselines.

But the final scientific result — whether CBSC-ZDC actually approximates Geant4 with useful fidelity and speed — remains **empirical and unproven**.