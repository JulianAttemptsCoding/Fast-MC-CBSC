# CBSC-ZDC v2.2 Research and Decision Log

This is an auditable record of evidence, alternatives, decisions, corrections, commands, and outcomes. It is intentionally not a transcript of private hidden chain-of-thought.

## D001 — Energy convention

Evidence: Geant4 particle-gun energy convention is kinetic, while a four-vector time component is total energy.

Decision: store `[E_total,px,py,pz]`; define all project ranges using `K_inc=E_total-m_n`; validate mass shell in float64.

Rejected: using one symbol `E` for both values.

Verification: contract unit tests.

## D002 — Target mode

Evidence: supplied audits gave a concrete counterexample showing that mixing raw layer energy and thresholded resolved energy breaks accounting.

Decision: raw-deposit mode is primary. Thresholded readout is a mutually separate target whose total is only retained readout.

Rejected: hidden subthreshold residual in the core model.

Verification: decoder tests for both modes.

## D003 — Shared latent

Evidence: a sampled latent without inference or a joint objective can be ignored under independent proper losses.

Decision: remove the unidentified shared latent. Dependence is carried by explicit ancestral conditioning and shared network representations.

## D004 — Support generation

Evidence: a continuous support flow plus independent Gumbel selection creates two unidentified stochastic support mechanisms.

Decision: support is a supervised geometry-aware score field followed by one Gumbel-Top-k draw. Flow matching is used only for continuous profile/share variables.

Verification: preselected-support regression test and structural QA.

## D005 — Exact decoder

Decision: final raw-mode energy is a softmax share over exactly selected cells, multiplied by the exact generated layer budget. Threshold mode adds a fixed floor before allocating the residual budget.

Verification: exact count, zero, floor, and closure tests.

## D006 — Longitudinal structure

Decision: do not impose decreasing deposited energy. Generate nonnegative layer shares summing to total response. Bidirectional layer context is primary; causal context is an ablation.

## D007 — Response support

Decision: use a zero hurdle plus a mixture density in dimensionless `log1p(T/s_T)` space. Apply only a finite cap learned from the complete train audit as a sampling safety rail.

Rejected: universal `T<=K_inc` or `T<=E_total` assertion before auditing the stored scoring target.

## D008 — Loss weights

Research: GradNorm motivates gradient-scale balancing; uncertainty weighting is a relevant alternative.

Decision: start with declared weights, run isolated stages, calibrate fixed inverse-gradient-norm weights on training batches, perform validation-only family sensitivity, then freeze. Dynamic weighting is an ablation.

Reason: fixed weights are easier to audit and compare across seeds/support experiments.

## D009 — Stage training and the condition encoder

Discovered implementation risk: sequential isolated stages originally retrained the shared condition encoder while freezing prior heads, invalidating earlier heads.

Decision: response stage trains condition encoder; profile/count/support/share freeze it and require initialization; joint stage unfreezes all.

## D010 — Gradient accumulation

Discovered implementation risk: a final partial accumulation window was divided by the full accumulation factor.

Decision: divide by the actual final-window size and hard-fail on nonfinite loss/gradient norm.

## D011 — Data split

Decision: 80/10/10, stratified by energy while preserving independent source groups. Same manifest for 0–300 and 50–250 comparison. Event-hash fallback only when valid run groups are absent.

## D012 — Evaluation bin coverage

Discovered implementation risk: bins with fewer than two events were omitted, and `all([])` could pass.

Decision: every primary bin is represented; insufficient bins fail explicit coverage gates.

## D013 — Reproducibility

Decision: archive seed, full environment, config, data/geometry/split hashes, optimizer/scheduler/scaler states, and use documented DataLoader seeding. Do not claim exact reproducibility across different PyTorch/hardware versions.

## D014 — Vertex execution

Decision: custom container downloads a frozen GCS prefix to local disk, rewrites only local paths, trains, and uploads the entire run directory. One T4 is an initial pilot example, not a fixed hardware claim.

## D015 — Assurance statement

Decision: repository is implementation-ready for production schema/geometry setup and training, not physics-validated. Exact invariants are necessary but insufficient.
