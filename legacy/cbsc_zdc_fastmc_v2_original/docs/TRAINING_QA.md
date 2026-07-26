# Recommended training QA and reporting

## Data preparation

Report branch names, units, jagged alignment, four-momentum mass-shell closure using a numerically stable energy residual plus a separately reported mass-squared residual, energy support, sentinel/unmapped energy, duplicate events, geometry validity, graph connectivity, threshold sensitivity, and split hashes.

## Frozen validation banks

Maintain separate immutable banks for:

- random in-domain p4 conditions;
- repeated identical p4 conditions with independent Geant4 seeds;
- supported interpolation conditions;
- out-of-domain stress conditions reported separately.

## During optimization

Report:

- total and component losses;
- gradient norms by stage;
- nonfinite steps;
- transform and logit extrema;
- flow-time coverage;
- truth-conditioned versus free-running results;
- truth, requested, and realized hit counts, including count calibration to detect support inflation;
- fraction of forbidden dust cells;
- memory and throughput.

## At each epoch

On a frozen p4 and model-seed bank, report:

- response mean, standard deviation, quantiles, and zero-response rate;
- ECAL/HCAL split and longitudinal profiles;
- active-layer and first/last-layer distributions;
- hit counts and positive-hit spectrum;
- subthreshold residual;
- centroids, widths, R50/R90, top-cell fractions, and neighbor correlations;
- high-level and geometry-aware classifier two-sample tests;
- conditional precision/recall and nearest-neighbor memorization;
- reconstruction closure when a frozen downstream model exists;
- decomposed inference timing.

## Improvement interpretation

A decreasing training loss is not sufficient. Classify checkpoint movement as:

- improving: free-running conditional physics improves beyond uncertainty without protected regressions;
- inconclusive: changes are within statistical uncertainty;
- plateau: optimization loss changes but detector metrics do not;
- overfitting: training improves while held-out metrics worsen;
- mode loss: conditional coverage or diversity decreases;
- exposure bias: truth-conditioned results improve while free-running results worsen;
- invalid: a software identity or data contract is violated.

These labels are reports, not user-imposed model-acceptance gates.
