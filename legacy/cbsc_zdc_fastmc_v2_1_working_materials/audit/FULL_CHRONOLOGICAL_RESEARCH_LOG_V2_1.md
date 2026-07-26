# CBSC-ZDC v2.1 full chronological research and revision log

This document records evidence, decisions, rejected alternatives, edits, and verification outcomes. It is intentionally not a verbatim private chain-of-thought transcript.

1. Preserved the original v2 repository, TeX, and PDF as immutable legacy artifacts.
2. Copied the four supplied audits unchanged and recorded line counts and SHA-256 hashes.
3. Reconciled 5,999 audit lines at issue level rather than adopting any overall verdict.
4. Re-derived the remaining-budget identity and exact sparse decoder. Retained them with explicit feasibility and floating-point qualifications.
5. Accepted the mixed threshold/raw accounting counterexample; made raw deposit primary and thresholded-readout-only a separate target.
6. Researched kinetic versus total neutron energy; fixed `p4[0]=E_total` and all range/normalization semantics to `K_inc=E_total-m_n`.
7. Removed the unidentified shared latent because the old losses supplied no posterior, marginalization, or identifiable coupling.
8. Removed the unobserved reserve/slack and enforced direct total-to-layer-to-cell closure.
9. Removed binary support from the continuous flow target. Retained a supervised geometry-aware support scorer and exactly one Gumbel-Top-k draw.
10. Restricted conditional flow matching to continuous layer and positive-share states.
11. Replaced the renormalized first-interaction hazard with a direct first-positive-layer categorical head.
12. Chose joint bidirectional layer context as primary; retained causal context as an ablation.
13. Added dynamic geometry/budget count-feasibility masks and exact support/count checks.
14. Added explicit seed substreams for visible, response, start, activity, profile, count, support, and share randomness.
15. Implemented ROOT schema contracts, signed/uint64 sentinel handling, primary-neutron selection, unit scales, fixed-vertex checks, conversion rejection accounting, and immutable manifests.
16. Implemented deterministic geometry freezing, physical adjacency graphs, exact project counts, provenance, and hashing.
17. Implemented sparse immutable shards, bounds checks, kinetic-range filters, group-aware splits, and split/manifest binding.
18. Added full train-only data audit and training-derived finite response cap with freeze refusal on incomplete scans.
19. Implemented staged training, module freezing, initialization versus resume semantics, optimizer/scheduler/scaler/RNG checkpointing, and provenance validation.
20. During execution QA, found a Python namespace collision: a response method named `parameters` shadowed `nn.Module.parameters`. Renamed it to `distribution_parameters`; added staged trainability tests.
21. Added exact zero-kinetic response handling after identifying a boundary inconsistency in stochastic sampling.
22. Implemented global/binned metrics, tie-aware AUC, high/low-level C2ST, structural diagnostics, synchronized timing, and nonfinite-safe JSON.
23. During full CLI gate execution, found that unavailable C2ST values caused `float(None)` instead of a clean failed decision. Repaired the gate to fail safely on missing/nonfinite values and added a regression test.
24. Rebuilt the active bibliography after verifying misattributed/conflated entries; preserved the old bibliography only in legacy provenance.
25. Added CLI/operator/agent guides, stage templates, matched range templates, baseline contracts, Vertex runbook, failure rules, and wrapper scripts.
26. Ran compilation and 42 unit tests; all passed.
27. Measured branch-aware coverage honestly at 51% over 2,585 statements and 768 branches; did not treat coverage as physics evidence.
28. Ran a synthetic CLI pipeline through data creation, split, audit, freeze, one-epoch training, reload, QA, sampling, evaluation, and benchmark. Structural invariants passed; physics gates failed as expected for the tiny model.
29. Confirmed the fixture ROOT signature and required branch strings. Numeric ROOT inspection remained unresolved because optional ROOT packages were unavailable offline.
30. Recompiled and visually QAed the revised auditor PDF.
31. Generated repository/master archives only after final tests, document checks, inventory, and checksums.

## Frozen conclusion

The repository is a complete CLI-ready experimental scaffold. It is not a trained or validated FastMC. Remaining work is production environment/dependency setup, data-contract acceptance through the CLI, actual training, and frozen empirical evaluation.
