# Evidence and decision log

This is a reproducible record of audit-relevant reasoning, evidence, alternatives, decisions, and tests. It is intentionally not a verbatim transcript of private hidden reasoning.

## Chronology

1. **Artifact identification.** Verified the current repository/specification and preserved the original v2 package under `legacy_v2` and the master bundle's `legacy/` directory.
2. **Audit ingestion.** Read 5,999 total lines across four supplied audits. Extracted every blocker, major finding, citation defect, implementation ambiguity, and claimed strength.
3. **Mathematical re-derivation.** Rechecked remaining-budget monotonicity and exact-support decoder identities. Accepted the algebra only under explicit feasibility and floating-point-tolerance conditions.
4. **Energy convention research.** Reconciled Geant4 kinetic-energy gun conventions with four-vector total energy. Split the concepts in code and documentation.
5. **Target-contract counterexample.** Confirmed that a layer with one above-threshold and one subthreshold raw hit cannot satisfy the old mixed decoder/accounting equations. Selected raw deposit as primary and made thresholded-only a separate target.
6. **Latent trainability check.** Confirmed no posterior, marginal likelihood, or joint transport identified the old shared latent. Removed it rather than adding unnecessary variational machinery.
7. **Support-generation check.** Confirmed the old support CFM had discrete atoms and was followed by independent Gumbel noise. Replaced it with supervised support logits plus one exact support sample; retained CFM only for continuous shares.
8. **Reserve identifiability check.** Confirmed a softmax reserve is strictly positive and unobserved. Removed it; total response closes directly to layers and cells.
9. **Layer-context decision.** Rejected the assumption that detector depth requires causal internal attention. Chose joint bidirectional context as primary and retained causal edges/mixing as a controlled ablation.
10. **Data/geometry implementation.** Added explicit PODIO/EDM4hep branch map, primary-neutron selection, uint64 sentinel handling, fixed-vertex gate, geometry scan, channel mapping, physical graph construction, sparse shards, and manifest hashes.
11. **Leakage control.** Added run-group split and refusal of empty partitions; retained event hash only as a disclosed fallback.
12. **Training-cap freeze.** Added a training-split-only data audit and `freeze-config` command that binds data, split, geometry, audit, and response cap by hash.
13. **Training implementation.** Added CLI training, stage selection, AdamW, cosine/constant schedule, mixed precision, gradient accumulation, gradient clipping, early stopping, resume validation, environment capture, and checkpoints.
14. **Evaluation falsifiability.** Added structural invariants, executable minimum metrics, predeclared gates, required binned/low-level/downstream analyses, and timing rules.
15. **Software QA.** Ran compilation, unit tests, synthetic dataset creation, split audit, config freeze, joint training, checkpoint reload, sampling, and structural QA.
16. **Fixture QA.** Computed the ROOT fixture hash and confirmed required branch strings. Full numeric reading remains a production gate because Uproot/Awkward could not be installed from the offline build index.
17. **Documentation revision.** Replaced stale active README/configs/docs/audits/paper; preserved all original material as legacy provenance.
18. **Namespace collision discovery.** During executable review, found that the previous response-mixture method named `parameters` shadowed `torch.nn.Module.parameters`, which prevented stage-freezing/training logic from enumerating parameters. Renamed it to `distribution_parameters` and added staged-training coverage.
19. **Zero-kinetic boundary discovery.** Forced exact zero response, inactive layers, and `first_positive_layer=-1` when `K_inc=0`, rather than relying on a learned visible hurdle. Added a regression test.
20. **Gate missing-value discovery.** A real synthetic evaluation with too few events produced unavailable C2ST values. The original gate function attempted `float(None)` and crashed instead of returning a scientific failure. Added a finite/missing-safe C2ST gate and regression test; the same run now returns `pass: false` with explicit failed checks.
21. **Packaging.** Final archives, manifests, and checksums are generated only after all source, documentation, PDF, and test gates complete.

## Alternatives considered and rejected

- **Keep mixed raw/threshold contract:** rejected by explicit counterexample.
- **Add a VAE posterior for shared z:** possible but unnecessary complexity before proving the hierarchy works; explicit ancestral dependence is simpler and auditable.
- **Deterministic Top-k only:** rejected as primary because it suppresses support diversity; used only when `stochastic=False` for deterministic QA.
- **Flow over binary support with dequantization:** possible research ablation, but not justified as the primary implementation.
- **Monotone layer deposits:** rejected as physically invalid for event-level neutron showers.
- **Unit response cap:** rejected until the scored target is audited.
- **Silently discard unknown geometry or variable vertices:** rejected because it can bias the dataset.
- **Random row split by default:** rejected in favor of independent run/job grouping.
- **Treat public ALICE timing as the speed denominator:** rejected; this detector and representation differ.

## Source hierarchy

1. executable repository tests and frozen data contracts;
2. official Geant4 and EDM4hep documentation;
3. primary research papers;
4. uploaded audit arguments after independent verification;
5. internal historical project logs as motivation, not external proof.
