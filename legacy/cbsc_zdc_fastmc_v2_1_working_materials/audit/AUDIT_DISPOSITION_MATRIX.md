# Audit disposition matrix

## Evidence reviewed

All four supplied audit files were read in full rather than accepted by verdict:

| Audit | Lines | SHA-256 | Treatment |
|---|---:|---|---|
| `Pasted text(179).txt` | 1,557 | `12a963303fe3ce1d60b9f9e63859dbc12ef86b2b050212ab5357756075c77183` | independent audit; every finding reconciled |
| `CBSC_ZDC_audit_log.txt` | 933 | `b1357908e09255c7e41c2eb7d04a4b0def5c6a399133d0114c84648ff891e6cf` | citation/physics/architecture audit; claims rechecked |
| `CBSC_ZDC_full_audit_chronological(1).txt` | 2,130 | `99b9a6df93cfb8984679d608bd0f46742d74c3dacb8b20ec2c21a555830fb7b0` | strongest blocker/major-finding audit; used as issue spine |
| `Pasted markdown (2)(32).md` | 1,379 | `e825a7f2ebfe3d788694e3719426dc2237ad26a2c57a0713feeb5906916622d1` | specification-level audit; strengths and enforcement gaps reconciled |

A finding was accepted only when supported by mathematics, source code, the data contract, primary documentation, or an executable test. Contradictory audit verdicts were resolved at the individual-finding level.

## Blockers

| ID | Audit claim | Independent disposition | v2.1 correction | Verification |
|---|---|---|---|---|
| B1 | thresholded-readout accounting mixes raw budget and subthreshold residual | **Correct**; counterexample is decisive | mutually exclusive `raw_deposit` and `thresholded_readout_only`; no residual in core target | decoder and truth-hierarchy tests for both modes |
| B2 | shared latent `z` lacks marginal/inference objective and may be ignored | **Correct** under the written stagewise losses | removed `z`; dependence is explicit ancestral conditioning | source search, model signature tests, architecture docs |
| B3 | continuous support flow plus independent Gumbel noise creates double stochasticity | **Correct**; support coupling was unidentified | support scorer + one Gumbel-Top-k draw; flow is share-only | support exactness, seed reproducibility, share-mask tests |
| B4 | no predeclared numerical success/failure rule | **Correct** | `configs/gates_primary.yaml` and evaluation protocol | executable gate loader/application tests and documentation |
| B5 | kinetic and total incident energy conflated | **Correct**; Geant4 gun energy is kinetic while p4 uses total | `p4[0]=E_total`; all ranges use `K_inc=E_total-m_n`; float64 shell check | contract unit tests and dataset audit |
| B6 | reserve is positive, unobserved, and non-identifiable | **Correct** | reserve removed; `sum D_l=T` and `sum Y_i=T` | profile and event closure tests |

## Major findings

| ID | Finding | Disposition and correction |
|---|---|---|
| M1 | duplicate `S` notation | accepted; renamed to `first_positive_layer` and `support_mask` throughout active materials |
| M2 | singular binary support target in continuous CFM | accepted; binary support removed from flow target |
| M3 | dimensionful logarithms | accepted; code uses dimensionless normalized shares and declared GeV scales in `log1p` transforms |
| M4 | zero residual share is unidentified at threshold floor | accepted; share-flow mask excludes zero-residual entries |
| M5 | floating-point “exactness” overstated | accepted; paper distinguishes real-arithmetic identity from numerical tolerance |
| M6 | incomplete geometry artifact | accepted; deterministic scan/freeze/hash CLI and strict project counts added |
| M7 | incomplete fixed-condition validation bank | accepted; required in evaluation protocol; cannot be produced before production data are available |
| M8 | no independent training-seed protocol | accepted; three-seed rule and deterministic component seed streams added |
| M9 | profile/support objectives not frozen | accepted; configuration and loss weights are explicit and hashed |
| M10 | optimization protocol not frozen | accepted; optimizer, scheduler, precision, accumulation, clipping, stopping, and resume are in config/checkpoint |
| M11 | RNG contract incomplete | accepted; master seed splits into profile/count/support/share streams; training seed archived |
| M12 | scaffold claims unverifiable | partly correct; current package was executed locally and reports commands/results, while physics claims remain withheld |
| M13 | baseline fairness underspecified | accepted; matched-data/compute/solver/seed rules and required baseline configs added |
| M14 | bibliography metadata errors | accepted; active bibliography rebuilt from corrected primary metadata; old bibliography moved to legacy |
| M15 | threshold-dependent visible/active semantics | accepted; separate target modes with consistent hierarchy; raw mode is primary |
| M16 | `p_z`/detector intercept domain incomplete | accepted; entry intercept is not used as an event feature in v2.1; a variable vertex would require a new contract |
| M17 | test-set and metric implementation immutability | accepted; freeze-before-test rule and hashed protocol added |
| M18 | “truth” versus Geant4 reference terminology | accepted; active materials use “held-out Geant4 reference events” for scored targets |

## Additional architecture findings from the citation/line audits

| Finding | Disposition |
|---|---|
| Causal layer attention was treated as primary without adequate physics justification | accepted; joint bidirectional layer mixing is primary, causal is an ablation |
| Independent Gumbel perturbation after a stochastic support flow should be removed | accepted through B3 redesign |
| Count feasibility must be masked before sampling | accepted and implemented in `LayerCountHead` |
| `-inf` masking may be numerically awkward in mixed precision | accepted; implementation uses large finite negative logits plus explicit masks and renormalization |
| Profile reserve can hide errors | accepted through reserve removal |
| Threshold must be detector-motivated rather than optimization-motivated | accepted; thresholded mode requires a separate frozen experiment |
| A point-cloud baseline should be required, not optional | accepted; P1 is required |
| Public ALICE ZDC latency is not directly comparable to this detector | accepted; timing is contextual only and native reproduction is separated from adaptation |

## Findings not accepted as stated

| Audit statement | Reason for rejection/qualification |
|---|---|
| “Critical count = 0; pass with corrections” | rejected as an overall verdict because B1-B6 materially prevented a unique trainable contract |
| “Causal generation is required by detector depth” | rejected; depth order does not imply that a joint readout generator must forbid deep-to-shallow contextual computation |
| “Use deterministic Top-k” as the only correction | qualified; deterministic Top-k removes support diversity. v2.1 retains one principled stochastic Gumbel-Top-k draw and removes the second stochastic mechanism |
| “Bound total response by incident energy” | rejected as a default. The exact scored target and kinetic/total convention must be audited; v2.1 uses a training-derived finite cap |
| “100% synthetic coverage proves implementation readiness” | rejected. Coverage is software evidence only and does not cover production ROOT/geometry, scale, or fidelity |

## Final disposition

The active v2.1 material is a **CLI-ready experimental implementation contract**, not a validated FastMC. All identified mathematical contradictions in the active architecture were removed. Remaining blockers are empirical/provenance tasks that require the real 765k-event corpus and production environment rather than additional repository coding.
