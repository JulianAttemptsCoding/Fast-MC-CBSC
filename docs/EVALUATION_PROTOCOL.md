# Evaluation and Decision Protocol

## 1. Hierarchy of evidence

1. algebraic invariants;
2. one-dimensional conditional distributions;
3. longitudinal and spatial correlations;
4. classifier two-sample tests;
5. diversity and memorization;
6. downstream reconstruction;
7. timing.

Passing an earlier level does not imply passing a later level.

## 2. Primary domain

Report 50–250 GeV in fixed bins:

```text
[50,75), [75,100), [100,125), [125,150),
[150,175), [175,200), [200,225), [225,250].
```

The executable gate requires sufficient events in every bin. Missing bins fail rather than disappearing from the average.

## 3. Current executable metrics

- mean and width of total response per energy bin;
- zero-response rate;
- response Wasserstein distance normalized by truth standard deviation;
- hit-count Wasserstein distance;
- high-level C2ST AUC;
- total response, hit count, depth centroid, x/y centroid, radial RMS;
- top-cell fraction, ECAL fraction, late-energy fraction;
- positive-cell energy spectrum;
- mean longitudinal profile;
- truth-half Wasserstein floors;
- exact structural invariants.

## 4. Provisional gates

`configs/gates_primary.yaml` supplies starting thresholds. They must be judged against validation truth-half floors and frozen before final test. They are not universal detector specifications.

## 5. Additional required publication studies

- low-level geometry-aware C2ST on sparse/dense representations;
- longitudinal covariance and neighbor correlations;
- connected-component distributions;
- repeated identical-p4 ensembles;
- nearest-neighbor memorization and train/test proximity;
- conditional precision/recall or coverage;
- downstream four-momentum reconstruction closure;
- stress regions 0–50 and 250–300 GeV;
- native and adapted external baselines;
- end-to-end speed.

These may require analysis code specific to the experiment’s reconstruction package.

## 6. Multi-seed decision

A model family passes only when the predeclared aggregate rule passes. Recommended:

- all three seeds pass structural gates;
- median seed passes every fidelity gate;
- no seed has a catastrophic outlier exceeding twice a gate threshold;
- report median and full range, not only the best seed.

## 7. Test isolation

The test split is opened only after:

- target and threshold frozen;
- geometry frozen;
- architecture frozen;
- optimizer and loss weights frozen;
- gates frozen;
- checkpoint-selection rule frozen;
- number of seeds frozen.
