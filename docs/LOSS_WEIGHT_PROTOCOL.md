# Loss-Weight Research and Freezing Protocol

## 1. Why no single paper provides the answer

CBSC-ZDC combines binary classification, categorical classification, mixture-density likelihoods, pairwise ranking, and flow-matching regression. Their raw numerical scales differ. The best weights depend on batch composition, target sparsity, architecture, normalization, and detector response. Therefore published methods guide the procedure, not the final constants.

## 2. Research basis

- GradNorm balances tasks using gradient magnitudes and relative training rates.
- Uncertainty weighting learns task scales from homoscedastic uncertainty.
- Dynamic task prioritization emphasizes tasks that learn slowly.

For an auditable physics study, the active default is **fixed weights after training-only calibration**, not continuously adaptive weights. Fixed weights make two runs exactly comparable and reduce the risk that an adaptive mechanism hides a persistently weak physical component.

## 3. Starting values

```yaml
visible: 1.0
response: 1.0
first_layer: 0.5
active: 0.5
profile_flow: 1.0
count: 0.75
support_bce: 1.0
support_rank: 0.25
share_flow: 1.0
```

Rationale:

- main proper-scoring and flow losses begin near 1;
- first/active are auxiliary structure losses and begin at 0.5;
- count begins at 0.75 because inactive classes are already downweighted;
- support ranking supplements BCE and begins at 0.25 to avoid dominating support classification.

## 4. Exact calibration procedure

### Gate 1: isolated stages

Train response, profile, count, support, and share stages. Confirm every component can improve on validation independently. Do not calibrate a loss that is numerically broken.

### Gate 2: default joint pilot

Use the final architecture, one seed, and a training-only pilot. Save the best validation checkpoint.

### Gate 3: gradient-norm measurement

```bash
cbsc-zdc calibrate-loss-weights \
  --config configs/frozen_joint_pilot.yaml \
  --checkpoint runs/joint_pilot/checkpoints/best.pt \
  --max-batches 64 \
  --clip-min 0.25 \
  --clip-max 4.0 \
  --output artifacts/loss_weight_calibration.json \
  --device cuda
```

For component `j`, the code measures the median gradient norm `g_j` with respect to the shared condition encoder. It computes the geometric mean

```text
g_bar = exp(mean_j log g_j)
```

and an inverse-norm proposal

```text
lambda_j_raw = clip(g_bar/g_j, 0.25, 4.0).
```

Weights are normalized so their arithmetic mean is one.

This equalizes initial gradient scale only. It does not certify task importance.

### Gate 4: family sensitivity matrix

Group losses into five scientific families:

```text
response: visible + response
longitudinal: first_layer + active + profile_flow
multiplicity: count
support: support_bce + support_rank
energy sharing: share_flow
```

Run a minimum sensitivity matrix on validation:

```text
calibrated baseline
response family ×0.5 and ×2
longitudinal family ×0.5 and ×2
multiplicity family ×0.5 and ×2
support family ×0.5 and ×2
share family ×0.5 and ×2
```

Use one seed for screening. Reject settings that improve weighted validation loss while damaging the corresponding physical metrics.

### Gate 5: select by validation Pareto criteria

Primary selection order:

1. structural pass;
2. no catastrophic failure in any module-specific metric;
3. total-response scale and resolution;
4. layer profile and counts;
5. spatial support and positive-cell spectra;
6. C2ST and reconstruction closure;
7. weighted validation loss only as a tie-breaker.

### Gate 6: freeze and repeat three seeds

Write selected weights into an unfrozen template. Freeze it. Run three independent seeds. Do not change weights after examining test output.

## 5. Alternatives not used as default

### Learned uncertainty weights

Useful when tasks have different observation noise, but learned scale parameters can suppress a difficult component. Use only as an ablation with its own predeclared interpretation.

### Fully dynamic GradNorm

Can improve multitask optimization, but changes weights during every run and adds another tuned hyperparameter. Use as an ablation after the fixed protocol is complete.

### Grid search over all nine losses

Computationally intractable and statistically dangerous. Search scientifically grouped families instead.

## 6. Failure diagnoses

- proposed weight at clip maximum: the loss has unusually small shared gradients; verify masking and normalization before increasing it;
- proposed weight at clip minimum: verify the loss is not numerically over-scaled or dominated by class imbalance;
- zero gradient norm: component may not depend on shared encoder, target mask may be empty, or graph is detached;
- calibrated model worsens a component: gradient equalization is not physical importance; restore or increase that family using validation-only evidence;
- large seed variation: weights are not yet robust; do not report a single best seed.
