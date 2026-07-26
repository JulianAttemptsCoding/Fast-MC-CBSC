# CBSC-ZDC v2.1 final QA report

## Verdict

**Repository/software gate: PASS for a CLI-ready experimental scaffold.**  
**Production-data/physics gate: NOT RUN and therefore NOT PASSED.**

The four supplied audits were treated as hypotheses, not authority. Their 5,999 lines were reviewed and reconciled finding-by-finding. Six genuine blockers were accepted and removed; several global “pass” verdicts were rejected because they understated contradictions in the old specification. The active design now has a unique target contract, trainable factorization, one support-randomness mechanism, frozen incident-energy semantics, no unobserved reserve, and predeclared decision gates.

## Executed software evidence

```text
python -m compileall -q src tests                         PASS
pytest -q                                                  42 passed
coverage run --branch --source=src/cbsc_zdc -m pytest -q  PASS
coverage report -m                                        51% overall
cbsc-zdc --help                                            PASS
synthetic CLI pipeline                                    PASS
```

Measured coverage spans 2,585 statements and 768 branches. It is not represented as 100%; low-coverage areas are the production ROOT adapter, CLI orchestration, full trainer/evaluator paths, and split/data-audit orchestration.

## Synthetic end-to-end evidence

The included non-physics evidence run completed synthetic data/geometry creation, splitting, complete train audit, configuration freezing, one-epoch joint training, checkpoint reload, invariant QA, sampling, evaluation, and benchmark. Structural findings:

- nonfinite cells: 0;
- negative cells: 0;
- energy outside selected support: 0;
- requested/realized count mismatches: 0;
- response-cap violations: 0;
- maximum layer/event closure residual: `3.815e-6 GeV`;
- invariant verdict: pass.

The tiny trained model failed the fidelity gates (including large mean-response bias), as it should. This confirms only that the evaluation path can expose failure; it does not establish metric validity on production statistics.

## ROOT fixture evidence

The supplied fixture SHA-256 is `3d6a78f5fb586eb611c30f0bf902e63f09290eac7791fe84f9396aa05a590e1d`. ROOT signature/version and the required MCParticle/EventHeader/ECAL/HCAL branch strings were confirmed by binary inspection. Uproot/Awkward were unavailable in the offline build environment, so branch types, event arrays, units, generator multiplicity, vertices, hit values, sentinel frequency, and exact geometry were not numerically inspected. Production acceptance explicitly requires `inspect-root`, `scan-geometry`, and `convert`.

## PDF QA

The revised specification was compiled with `latexmk`/Biber and rendered page-by-page. Final acceptance requires:

- zero undefined references/citations;
- zero overfull boxes;
- embedded fonts;
- no clipped/overlapping/missing content;
- source/bibliography/PDF hashes recorded in the bundle manifest.

## Production blockers

1. Numerically inspect every production ROOT family.
2. Recover and approve the exact 6,790-channel geometry and graph.
3. Convert the complete 0-300 GeV corpus once.
4. Freeze a leakage-safe split and full train-only audit.
5. Run staged pilots on target hardware.
6. Train the matched 0-300 and 50-250 support experiments across three seeds.
7. Run frozen held-out fidelity, diversity, memorization, reconstruction, baseline, and timing gates.

No production FastMC claim is allowed before those gates pass.
