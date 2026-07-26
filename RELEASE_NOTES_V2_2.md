# CBSC-ZDC v2.2 release notes

## Purpose

This release turns the audited CBSC-ZDC design into a CLI-first research scaffold and an exact agent runbook for the production 765k-event neutron corpus.

## Active guarantees

- total-energy four-vector and kinetic-energy range semantics are separate;
- raw and thresholded targets are mutually exclusive;
- generated layer deposits are nonnegative but not forced to decrease with depth;
- support is sampled exactly once;
- requested counts are dynamically feasibility-masked;
- the decoder gives exact zero outside support and closes generated layer/event budgets within tolerance;
- data, geometry, split, config, and checkpoints carry provenance hashes;
- primary gates fail on missing energy-bin coverage rather than silently dropping bins.

## Release QA

- 18 regression tests pass;
- branch-aware suite coverage: 66% overall, approximately 70% statements and 48% branches;
- complete lightweight CPU smoke script passes;
- exact structural smoke invariants pass;
- loss-weight calibration and evaluator commands were executed;
- revised 13-page specification compiles and was visually rendered page by page.

## Remaining production work

No production Geant4 fidelity or speed claim exists. Agents must install ROOT extras, inspect production files, freeze the actual geometry and schema, convert the full corpus, create the immutable split, run the data audit, tune using validation only, train the matched multi-seed experiment, and complete the required fidelity/reconstruction/memorization/timing studies.
