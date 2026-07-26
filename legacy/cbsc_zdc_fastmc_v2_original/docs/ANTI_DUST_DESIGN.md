# Exact sparsity and anti-dust design

## Problem

A dense generator followed by a global or layerwise energy rescaling can reduce an energy loss by placing a small positive value in many nominally empty cells. This changes occupancy, the hit-energy spectrum, shower width, connectedness, and downstream reconstruction even if the total energy is correct. Convolutional L2LFlows and iCaloFlow explicitly report that rescaling zero voxels upward can create an excess of low-energy hits.

## Target contract first

There are two scientifically different outputs.

### Raw-deposit mode

The target is the raw Geant4 deposit in every readout channel. Exact zeros are modeled as a point mass; positive values are modeled conditionally. The threshold parameter is `tau=0`. Sparsity must still be modeled explicitly because an ordinary softmax is strictly positive everywhere.

### Thresholded-readout mode

A detector/noise/analysis threshold `tau>0` is frozen from the detector contract. The target is

```text
Y_i^(tau) = Y_i * 1[Y_i >= tau].
```

Subthreshold raw energy may be recorded separately as a layer-level residual if total raw accounting is needed. The model must not invent an arbitrary threshold from optimization convenience.

## Recommended primary decoder

For layer `l`:

- `B_l >= 0`: generated layer budget;
- `K_l`: generated number of resolved hits;
- `S_l`: a subset of valid channels with `|S_l|=K_l`;
- `r_li`: positive-energy share logits;
- `tau`: frozen threshold.

The count contract is:

```text
K_l = 0                                      if B_l = 0,
K_l = 0 and U_l = B_l                       if 0 < B_l < tau and tau > 0,
1 <= K_l <= min(N_l, floor(B_l/tau))        if B_l >= tau and tau > 0,
1 <= K_l <= N_l                             if B_l > 0 and tau = 0.
```

Thus any resolved positive layer has at least one selected cell. A thresholded layer whose entire budget is below threshold is represented by the layer residual `U_l`, not by a fake above-threshold hit.

Support is sampled with Gumbel-Top-k from geometry-aware scores. For `i in S_l`,

```text
w_li = exp(r_li) / sum_{j in S_l} exp(r_lj),
E_li = tau + (B_l - K_l*tau) * w_li.
```

For `i not in S_l`, `E_li=0` exactly.

### Decoder properties

When `B_l >= K_l*tau`:

```text
E_li = 0                    for i not in S_l,
E_li >= tau                 for i in S_l,
sum_i E_li = B_l,
number of nonzero cells = K_l.
```

Therefore the decoder cannot assign `0.001 GeV` to every channel while claiming a small support. It does **not**, by itself, prevent the count network from inflating `K_l`. Count inflation is prevented empirically by training `K_l` against the frozen truth count with categorical negative log-likelihood, training support scores against the truth support/ranking, exposing the spatial model to generated counts during later training, and reporting count calibration separately from the aggregate loss. A model that predicts `K_l=N_l` everywhere is visibly wrong even though the decoder remains algebraically valid.

If `B_l<tau`, no above-threshold hit is possible. The implementation outputs zero cell energy and records `B_l` as `subthreshold_residual_l`; it does not smear the amount across cells.

## Why not ordinary softmax over every cell?

Softmax has strictly positive support. Even if many values are numerically small, every cell receives energy after budget normalization. This is exactly the failure mode to avoid.

## Why top-k is primary but not assumed optimal

Advantages:

- exact hit count;
- exact zeros;
- exact budget identity;
- simple auditing;
- direct control of the tiny-energy failure.

Risks:

- count prediction becomes a hard bottleneck;
- deterministic top-k can reduce diversity;
- the operator is discontinuous;
- truth-mask training and generated-mask inference can diverge.

Mitigations:

- stochastic Gumbel-Top-k at inference;
- a finite-support categorical count distribution instead of Poisson;
- a differentiable sparse top-k or straight-through relaxed top-k during end-to-end training;
- generated-count and generated-support exposure during training, not truth support only;
- explicit count, support, positive-hit spectrum, and geometry-aware distribution diagnostics.

## Required alternatives to compare

1. **Sparsemax/entmax shares:** differentiable exact zeros, but support size is not directly calibrated.
2. **Hard-concrete gates:** exact-zero stochastic gates with an expected L0 penalty, but independent or weakly correlated gates can miss set structure.
3. **Bernoulli hurdle plus normalization:** simple but does not enforce an exact count and can produce train/sample support mismatch.
4. **Sparse point-cloud generation:** avoids dense empty cells entirely, but count, duplicate-hit, mapping-to-readout, and speed become separate problems.

## Recommended reports

- exact-zero fraction;
- hit count by layer and condition;
- fraction of cells in `(0,tau)`;
- subthreshold residual by layer;
- positive-hit energy spectrum in log scale;
- fraction of layer energy in the smallest 10%, 25%, and 50% of active hits;
- top-1/top-5 energy fractions;
- connected components and nearest-neighbor occupancy;
- stability under threshold sensitivity scans.
