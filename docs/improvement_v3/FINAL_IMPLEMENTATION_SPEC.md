# CBSC-ZDC v3 exact implementation specification

## 1. Outcome and boundary

Implement a backward-compatible `cbsc-zdc-v3` experiment family that improves
the probability laws feeding the existing exact decoder. The final production
output remains one nonnegative raw-deposit shower
`cell_energy_gev[B,6790]` conditioned on incident neutron total four-momentum
`p4_total_gev[B,4]` and frozen detector geometry.

The v3 generator remains:

```text
p4 + geometry
  -> condition and incident-axis coordinates
  -> visibility V and positive total response T
  -> ECAL-start flag and first HCAL layer f
  -> active layers A
  -> longitudinal layer budgets D
  -> feasible layer counts k
  -> exact stochastic support S
  -> positive within-layer shares w
  -> exact decoder Y_hat
```

This is a replacement of weak heads plus later optional auxiliary training; it
is not a dense end-to-end generator and it does not remove the event/layer/cell
factorization.

### Required unchanged invariants

For event `b`, layer `l`, and valid channel `i`:

- `Y_hat[b,i] >= 0` and finite;
- invalid channels are exactly zero;
- channels outside `S_hat` are exactly zero;
- `sum_{i in layer l} S_hat[b,i] = k_hat[b,l]`;
- `sum_{i in layer l} Y_hat[b,i] = D_hat[b,l]` within the existing
  float32-aware absolute/relative closure rule;
- `sum_i Y_hat[b,i] = T_hat[b]` within the same rule;
- raw-deposit mode retains `threshold_gev = 0`;
- old v2.2 frozen configs and checkpoints retain their prior interpretation.

## 2. Exact symbols and shapes

| Symbol/code name | Shape | Definition |
|---|---:|---|
| `B` | scalar | batch size |
| `N` | scalar | 6,790 detector channels |
| `L` | scalar | 65 layers |
| `P` / `p4_total_gev` | `[B,4]` | `[E_total,p_x,p_y,p_z]` in GeV |
| `m_n` | scalar | neutron mass, 0.93956542052 GeV |
| `K` | `[B]` | incident kinetic energy, `E_total-m_n` |
| `p` | `[B]` | momentum norm `sqrt(px^2+py^2+pz^2)` |
| `u` | `[B,3]` | incident unit direction `(px,py,pz)/max(p,1e-12)` |
| `X` | `[N,d_g]` | existing frozen static node features |
| `r_i` | `[N,3]` | cell center in mm |
| `r_0` | `[3]` | frozen generator vertex / incident origin in mm |
| `c_raw` | `[B,5]` | existing deterministic four-momentum features |
| `c` | `[B,d_c]` | condition encoder output; default `d_c=128` |
| `x_axis` | `[B,N,4]` | new incident-axis-relative node features |
| `V` | `[B]` Boolean | visible-response indicator |
| `T` | `[B]` | total raw deposited response in GeV |
| `Z_E` | `[B]` Boolean | visible shower begins in ECAL layer 0 |
| `f` | `[B]` integer | first active layer; `-1` if invisible |
| `q` | `[B]` integer | last active layer; `-1` if invisible |
| `A` | `[B,65]` Boolean | active-layer mask |
| `D` | `[B,65]` | exact nonnegative layer budgets summing to `T` |
| `k` | `[B,65]` integer | requested positive-cell counts |
| `a` | `[B,6790]` | support logits |
| `S` | `[B,6790]` Boolean | exact selected support |
| `r` | `[B,6790]` | share-flow terminal state |
| `Y_hat` | `[B,6790]` | generated cell-energy vector in GeV |

The existing condition features remain:

```text
c_raw = [log(1 + K/100), u_x, u_y, u_z, log(E_total/1 GeV)].
```

No entry point is added as a new random event input in v3. The production
contract says the generator vertex is fixed. The converter/audit must expose
that frozen `r_0`; if it is not uniquely fixed within tolerance, implementation
must fail closed and the data contract must be expanded before training.

## 3. Architecture versioning and compatibility

### 3.1 Config switch

Add:

```yaml
model:
  architecture_version: cbsc-zdc-v3
```

Absence of this key means `cbsc-zdc-v2.2`. Do not reinterpret any existing
frozen YAML. `validate_config()` must select the exact expected loss/config
schema by architecture version.

### 3.2 Sampling APIs

Keep:

```python
CBSCZDC.sample(...)
```

as the v2-compatible exact inference API. For v3 expose:

```python
sample_exact(p4_total_gev, profile_steps=8, share_steps=8,
             seed=None, stochastic=True) -> CBSCOutput

sample_share_for_loss(p4_total_gev, truth_structure, share_noise,
                      share_steps=8) -> DifferentiableShareOutput

sample_profile_for_loss(p4_total_gev, truth_total, truth_active,
                        profile_noise, profile_steps=8)
                      -> DifferentiableProfileOutput
```

`sample_exact()` may be decorated with `@torch.no_grad()`. The two loss APIs
must not be. They accept continuous source noise explicitly so resume and
gradient tests control randomness. They may truth-force only the variables
named in their signature. Never silently call `sample_exact()` inside an
adversarial generator loss.

### 3.3 v2-to-v3 initialization

Add a one-time audited migration command:

```bash
cbsc-zdc migrate-v2-checkpoint \
  --source V2_BEST.pt \
  --v3-template V3_UNFROZEN.yaml \
  --output V3_INITIAL.pt \
  --report audit/v2_to_v3_migration.json
```

Migration rules:

| Module | Rule |
|---|---|
| condition encoder | exact copy |
| visibility subhead | exact copy when shapes match |
| positive-response spline | new initialization |
| profile flow | exact copy when shapes match |
| ECAL/HCAL first heads | new initialization |
| activity span/gap or AR head | new initialization |
| AR count head | new initialization |
| support/share graph blocks, layer context, output | exact copy |
| expanded support/share input projection | copy old columns exactly; initialize the four new axis-feature columns to zero |
| critic(s) | new initialization |

The report must list every copied, expanded, initialized, missing, and
unexpected key with tensor shapes and SHA-256 hashes of source/output
checkpoints. Any unclassified key is fatal. Zero initialization of the new
axis columns makes migrated node fields reproduce the old input projection
before fine-tuning.

## 4. Incident-axis-relative geometry

For each event choose a stable orthonormal basis around `u`.

```text
reference a = (0,0,1) if abs(u_z) < 0.9 else (0,1,0)
e1 = normalize(a - (a dot u) u)
e2 = u cross e1
delta_i = r_i - r_0
s_i = delta_i dot u
x_i = delta_i dot e1
y_i = delta_i dot e2
rho_i = sqrt(x_i^2+y_i^2)
```

Normalize only with frozen geometry-derived scales:

```text
x_axis_i = [s_i/s_scale, x_i/r_scale, y_i/r_scale, rho_i/r_scale]
s_scale = max_i abs((r_i-r_0) dot z_hat), at least 1 mm
r_scale = max_i ||(r_i-r_0)_xy||, at least 1 mm
```

Record `r_0`, `s_scale`, and `r_scale` in the geometry manifest and hash them.
Concatenate `x_axis` after existing static node features in both support and
share fields. Static edge features remain unchanged.

Required numerical tests:

- `u,e1,e2` are unit and mutually orthogonal within `1e-6` in float32;
- no discontinuity/NaN at directions parallel to global `z` or `y`;
- rigidly rotating `u`, `r_i`, and `r_0` together leaves `(s,x,y,rho)` equal
  up to the deterministic basis sign convention;
- with the new projection columns at zero, migrated v3 node logits match v2
  logits within `1e-6` for the same batch.

## 5. Response head: one and only one zero atom

### 5.1 Hurdle

Keep:

```text
V ~ Bernoulli(sigmoid(o_V(c))).
```

If `V=0`, set `T=0` exactly. If `V=1`, `T` must be strictly positive without a
clamp and must never clear `V` after sampling.

### 5.2 Train-only cap envelope

The bounded spline requires support known from training data only. Add
`cbsc-zdc audit-response-envelope`. Use 25-GeV bins from 0 through 300 GeV.
For bin `j`:

```text
m_j = max positive training response in bin j
c_j = max(1e-6 GeV, 1.10*m_j + 1e-6 GeV)
C_j = max_{h<=j} c_h
```

`C(K)=C_j` for `K` in bin `j`; `K=300` belongs to the last bin. Empty bins are
fatal for a production envelope. Store bin edges, raw maxima, monotone caps,
event counts, source/split hashes, and algorithm version. The command must
re-scan every selected training event and assert `0<T<C(K)` for every visible
event. Validation/test data never influence `C`.

This envelope is a numerical/model support contract, not a claim that larger
physical responses are impossible. Validation truth outside it is reported as
an out-of-support finding; it is never clipped or hidden.

### 5.3 Conditional rational-quadratic spline

For visible truth define:

```text
r_T = T/C(K), with 0 < r_T < 1.
u_0 ~ Uniform(eps,1-eps), eps=1e-6.
r_T = S_theta(u_0; c).
```

`S_theta` is a monotone rational-quadratic spline on `[0,1]` with:

- 16 bins;
- minimum bin width `1e-3`;
- minimum bin height `1e-3`;
- minimum derivative `1e-3`;
- network `Linear(d_c,192) -> SiLU -> Linear(192,192) -> SiLU -> params`;
- positive widths/heights produced by softmax with minimum-bin adjustment;
- positive derivatives produced by softplus plus the minimum derivative;
- float64 forward/inverse/finite-difference tests and float32 training.

The positive-response NLL for visible event `b` is:

```text
L_response,b = -log p(T_b | V_b=1,c_b)
             = -log |d S_theta^{-1}(r_T)/d r_T| + log C(K_b).
```

The uniform-base log density is zero. Do not clamp `r_T` during training; an
out-of-support target is a fatal train-contract error. Sampling uses
`u_0 in [eps,1-eps]`, so `0<T<C(K)` by construction.

The visibility BCE and positive-response NLL remain distinct logged losses.

## 6. Hierarchical first layer

For visible events define `Z_E = 1[f=0]`.

```text
p_E = sigmoid(g_E([c,log1p(T)]))
Z_E ~ Bernoulli(p_E)

if Z_E=1: f=0
if Z_E=0: f ~ Categorical(softmax(g_H([c,log1p(T)]))) over {1,...,64}
if V=0: f=-1 and neither first-layer sample is allowed to activate a layer
```

Use separate two-layer MLPs of hidden width 128. Start with unweighted
likelihoods:

```text
L_ecal_start = BCEWithLogits(o_E, Z_E) over visible events
L_hcal_first = CE(o_H, f-1) over visible non-ECAL events
```

Do not add focal/class weighting in the first experiment. Report ECAL-start
prevalence, Brier score, reliability bins, precision/recall, and HCAL first
layer distributions by 25-GeV energy bin. The prevalence and calibration are
the physical targets; recall alone is not.

## 7. Longitudinal activity

Implement both options behind `model.activity_mode` and select using the
predeclared train-only diagnostic below.

### 7.1 Selection statistic

For each visible truth shower, let `f=min active`, `q=max active`, let an
internal gap be an inactive layer in `[f,q]`, and record gap count and maximum
consecutive gap length. Compute:

```text
compact_fraction = fraction with gap_count <= 2 and max_gap_length <= 2.
```

If `compact_fraction >= 0.99`, the primary compact candidate is
`span_gaps`. Otherwise the primary candidate is `autoregressive`. Implement
both so the other remains a matched ablation; do not choose using test data.

### 7.2 Span-plus-gaps

Predict last active layer over feasible `{f,...,64}`:

```text
q ~ Categorical(p(q | c,T,f)).
```

For `f<l<q`, predict gap logits conditioned on `c,T,f,q,l`. Derive:

```text
A_l = 1[f<=l<=q] * (1-G_l),
G_f=G_q=0.
```

Losses:

```text
L_active_last = CE(q_logits,q_truth)
L_active_gap  = BCE(gap_logits,G_truth) over internal span positions only.
```

### 7.3 Autoregressive activity

Use a one-layer GRU, hidden width 128, over 65 layer tokens. At layer `l`, the
input is `[c,log1p(T),embed(f),embed(l),A_{l-1}]`; teacher-force truth during
NLL training and feed sampled previous activity during exact generation.
Hard-mask `A_l=0` for `l<f`, `A_f=1`, and all layers inactive when `V=0`.

```text
L_active_ar = sum_l BCEWithLogits(o_l,A_l) over feasible l.
```

Record teacher-forced and free-running transition matrices separately.

## 8. Longitudinal counts

Replace the v3 independent count head with a one-layer GRU of hidden width 192.
At layer `l`, input:

```text
[c, log1p(D_l), A_l, embed(l), k_{l-1}/M_{l-1}].
```

Teacher-force `k_{l-1}` in NLL training; use the sampled previous count in
`sample_exact()`. Output logits for classes `0..M_global` and retain every
existing feasibility mask:

- inactive -> `k_l=0` only;
- active raw mode -> `1<=k_l<=M_l`;
- thresholded mode -> additionally `k_l*tau<=D_l`.

Loss:

```text
L_count_ar = weighted CE over all layers,
weight=1 for active layers and 0.2 for inactive layers.
```

The inactive weight stays unchanged for the first matched comparison.

## 9. Profile and share flows

Keep the existing continuous flow fields and exact masked-softmax decoders in
the first v3 comparison. Add source-noise arguments to the loss samplers and
refactor ODE integration into differentiable helper functions shared by exact
and training-only APIs.

OT-CFM is an ablation, not the default. If implemented, apply it only to the
65-dimensional profile target. Transport candidates may be paired only inside
the same visibility class and active-mask signature; within that group use
cost:

```text
cost(a,b) = ||z0_a-z1_b||_2^2
          + 10*||c_a-c_b||_2^2
          + 2*|log1p(T_a)-log1p(T_b)|^2.
```

Use the Hungarian assignment for pilot batches no larger than 64. If no group
contains at least two compatible members, fall back to identity coupling and
log the fallback count. Do not apply OT-CFM to share targets with different
hard supports.

## 10. Exact support with calibrated stochasticity

Keep the exact forward support:

```text
score_i = a_i/tau_support + g_i,
g_i = -log(-log(U_i)),
S_l = indicators of the k_l largest scores in layer l.
```

`tau_support>0` is a frozen sampling temperature. Lower values make learned
logits dominate; higher values make Gumbel noise dominate. `tau_support` does
not change deterministic top-k ordering.

Add validation-only screen `{0.25,0.5,1.0,2.0}` after incident-axis features
are trained. For each value report:

- truth-support recall at truth `k`;
- repeated-draw Jaccard distribution;
- graph-edge/distance-binned co-occupancy;
- connected components and component sizes;
- nearest-neighbor distances and radial eccentricity;
- independent low-level C2ST;
- support entropy/diversity at repeated identical `p4`.

Select by the multi-metric rule in `CONTINUATION_PLAN.md`; never select only
the lowest C2ST or the most deterministic support. The default in config is
`1.0` until the screen is frozen.

## 11. Staged dynamic conditional critics

### 11.1 Separation of roles

Implement three distinct systems:

1. `LiveCritic`: train-only, updated continually, supplies generator gradients.
2. `CriticMonitor`: same architecture but never supplies gradients; evaluated
   on a disjoint train-only holdout to detect critic overfit/staleness.
3. Existing external C2ST ensemble: validation-only during development and
   remaining test holdout once after protocol freeze; never imported by
   training code.

### 11.2 Deterministic train-only role partition

From the canonical 612,482 training event IDs, compute
`SHA256("cbsc-v3-critic-20260813:" + decimal_event_id)`, sort by digest then
event ID, and assign exact ranks:

```text
generator_train       551,234 events
critic_real_train      30,624 events
critic_monitor_holdout 30,624 events
```

Write a manifest containing every event ID, source split, role, algorithm,
seed string, input split hash, counts, and assignment SHA-256. Assert that all
IDs were already in `train`, roles are disjoint/exhaustive, and zero validation
or test IDs occur.

Because generator training data is reduced by 10%, every critic experiment
must have a no-critic control trained on the same 551,234-event generator
partition.

### 11.3 Critic conditioning

All critics use a projection logit:

```text
d(Y,P) = u(h_Y) + dot(h_Y,h_P),
h_P = Linear(128,H)(c),
```

where larger `d` means more Geant4-like. Apply spectral parametrization to all
critic linear output projections. Critic parameters are never shared with the
generator.

### 11.4 D1 share critic

Truth-force `V,T,f,A,D,k,S`. Generate only the share-flow state and decode
energies on the fixed truth support. Inputs per node:

```text
[log1p(Y_i/1 GeV), Y_i/max(D_layer,1e-12), support_i,
 static node features, incident-axis features].
```

Architecture: hidden width 96; two edge-message blocks; one bidirectional
two-layer, four-head layer-context Transformer; masked layer mean/max pooling;
global mean/max pooling; 128-dimensional shower embedding; projection
conditioning. Trainable generator module: share flow only.

### 11.5 D2 profile critic

Truth-force `V,T,A`. Generate only continuous layer budgets. Layer-token input:

```text
[D_l/max(T,1e-12), log1p(D_l/1 GeV), A_l, layer_embedding_l].
```

Architecture: token width 128; two-layer four-head Transformer; masked mean
and max pooling; 128-dimensional embedding; projection conditioning. Trainable
generator module: profile flow only.

### 11.6 Critic objective and update order

For normalized real `Y` and detached fake `Y_hat`:

```text
L_D = mean softplus(-D(real,P_real))
    + mean softplus( D(fake_detached,P_fake))
    + L_R1.

L_R1 = gamma/2 * mean ||gradient_real D(real,P_real)||_2^2.
```

Defaults:

```yaml
critic:
  optimizer: Adam
  learning_rate: 1.0e-4
  betas: [0.0, 0.99]
  updates_per_generator_update: 1
  r1_gamma: 1.0
  r1_interval: 16
  batch_size: 4
  gradient_clip_norm: 5.0
```

Use lazy R1 every 16 critic updates and multiply the computed R1 term by 16 so
its expected coefficient remains `gamma`. Critic update occurs first. Fake
inputs are detached. Then freeze critic parameter `requires_grad` flags without
using `torch.no_grad()`, recompute a fresh fake, and calculate the generator
loss so gradients flow through the critic input into only the intended
generator module.

Two separate ablations are required:

```text
direct:  L_adv = mean softplus(-D(fake,P))
feature: L_fm  = ||mean h(real) - mean h(fake)||_2^2
```

Do not switch objectives mid-run. The direct classifier loss is the literal
test of the proposed idea; feature matching is its matched stability control.

### 11.7 Adversarial gradient-ratio controller

Every 16 generator updates, before the combined backward pass, compute
unscaled float32 gradients over the active generator module:

```text
g_base = grad(L_base)
g_adv0 = grad(L_adv_without_weight)
lambda_raw = rho_target * ||g_base||_2/(||g_adv0||_2+1e-12)
lambda_new = clamp(lambda_raw,1e-5,10)
lambda = 0.9*lambda_previous + 0.1*lambda_new
rho_observed = lambda*||g_adv0||_2/(||g_base||_2+1e-12).
```

Hold `lambda` constant between measurements. Default `rho_target=0.10`; run
separate screens at `0.05`, `0.10`, and `0.20`. An observed ratio above 0.25,
nonfinite gradient, or gradient outside the intended module is a failed
training artifact to diagnose, not a reason to weaken a test.

For every base component `j`, log cosine similarity
`dot(g_adv,g_j)/(||g_adv|| ||g_j|| + 1e-12)` at the same interval.

### 11.8 Replay

The pilot in-process buffer stores stage-specific fake tensors on CPU plus:

```text
event_id, p4, stage, stratum, generator_step, generator_epoch,
generator_checkpoint_sha256, sampler_version, seed.
```

Pilot capacity is 8,192 events. Final configured capacity is 65,536 events;
if dense D1 storage would exceed 1 GiB, use sparse CSR storage without changing
the event capacity or sampling law. Never silently shrink the final buffer.

Each critic fake minibatch has exact largest-remainder composition:

```text
50% fresh current-generator fakes
25% recent FIFO fakes
25% anchor fakes
```

For batch size 4 this is 2 fresh, 1 recent, 1 anchor. Anchor fakes are generated
once from the corrected supervised baseline and are versioned by checkpoint
hash. Recent FIFO excludes anchors. Until both historical pools contain enough
samples, replace missing history with fresh samples and log the warm-up
composition. Stratify sampling by 25-GeV energy bin, visible/zero,
ECAL/HCAL-start, and count/activity quartile where the stage representation
contains those variables.

Never store validation/test real events, conditions, or generated showers in
live replay. Replay state, RNG, metadata, and content manifest must be
checkpointed for exact resume.

### 11.9 Hardware topology

First prove D1/D2 correctness in one L40S process. A live generator gradient
requires the frozen critic forward pass on the same autograd device; a
filesystem queue to the 3090 cannot transmit autograd.

After single-process validation, the 3090 may train a versioned asynchronous
critic copy and produce external diagnostics. The L40S may import critic weights
only at an epoch boundary after hash and monitor verification, and must log
critic age in generator updates. This is a separate staleness ablation, not the
default implementation.

## 12. D3 support critic trigger and estimator QA

D3 is not part of the first critic campaign. Implement its research harness
only if, after response/first/activity/count/axis/temperature changes, the
validation support-topology distance remains significantly above the
truth-half floor and is a leading C2ST feature family.

Forward output must remain exact hard top-k. Compare SIMPLE and one structured
soft-top-k estimator on tiny layers where the expected loss gradient can be
enumerated. For each estimator report 100-noise-draw gradient mean/variance,
cosine with enumerated or central finite-difference gradient, and relative
bias. Promotion requires positive median gradient cosine and lower bias and
variance than the straight-through Gumbel control. Do not default to a manual
straight-through estimator.

## 13. Optional four-momentum predictor

Do not include it in D1/D2. Later, train a separate three-model neural ensemble
on Geant4 training events only. Input is the shower plus geometry; output is
positive kinetic energy and an unnormalized direction vector. Normalize the
direction and derive total four-momentum on the neutron mass shell.

```text
L_p4 = Huber((K_hat-K)/s_K) + alpha*(1-u_hat dot u).
```

If the train direction covariance has fewer than two eigenvalues above `1e-4`,
direction support is insufficient: omit the angular training term and state
that arbitrary-angle utility is not tested. Freeze the predictors before any
generator use. A generator-side p4 term, if later screened, has gradient target
at most 0.05 and must pass adversarial-gaming checks against the other two
ensemble members and the external XGBoost evaluator.

## 14. Metrics added before architecture selection

Implement train/validation metrics with truth-half floors and 1,000 stratified
bootstrap replicates:

- 65x65 layer-energy covariance and correlation Frobenius distance;
- adjacent-layer activity/count transition matrices;
- gap count and length;
- graph-edge and distance-binned support co-occupancy;
- connected-component count and sizes;
- pairwise/nearest-neighbor hit distance;
- radial eccentricity and local density;
- repeated-identical-p4 diversity and support Jaccard;
- KPD/FPD or an explicitly documented detector-specific embedding distance;
- MMD and sliced Wasserstein on normalized high-level vectors;
- train nearest-neighbor memorization versus truth-truth floor;
- external high- and low-level C2ST with three evaluator seeds;
- downstream reconstruction and complete end-to-end timing.

Every metric report includes split, event IDs or selection manifest hash,
energy bins, checkpoint/config/geometry hashes, RNG seeds, sample count,
solver steps, software environment, and whether it is diagnostic, selection,
or final-test evidence.

## 15. Checkpoint and evidence schema

Format v3 checkpoints add:

```text
format_version = 4
architecture_version
experiment_contract_sha256
critic_state (nullable)
critic_optimizer_state (nullable)
critic_scheduler_state (nullable)
gradient_ratio_controller_state (nullable)
replay_state_manifest (nullable)
critic_update_count
generator_update_count
role_partition_sha256
response_envelope_sha256
support_temperature
```

Resume must restore all non-null states and produce a deterministic
next-update equivalence test. A critic checkpoint cannot be paired with a
generator or replay state bearing different contract/checkpoint hashes.

Each meaningful run event appends `logs.md` and writes an
`audit/NAME.{json,md}` twin. Required per-update/epoch fields include base and
component losses, critic real/fake loss and logits, R1, monitor AUC/loss,
fresh/recent/anchor counts, replay age distribution, gradient norms/ratio/
cosines, parameter-update isolation result, GPU memory, throughput, and all
artifact hashes.

## 16. Exact active file plan

The agent may adjust names to match a newer live repository only after recording
the mapping. On the audited base, implement:

### New modules

```text
src/cbsc_zdc/models/axis_features.py
src/cbsc_zdc/models/splines.py
src/cbsc_zdc/models/critics.py
src/cbsc_zdc/training/adversarial.py
src/cbsc_zdc/training/replay.py
src/cbsc_zdc/training/role_partition.py
src/cbsc_zdc/eval/topology.py
src/cbsc_zdc/eval/correlations.py
src/cbsc_zdc/eval/diversity.py
src/cbsc_zdc/eval/memorization.py
scripts/build_v3_experiment_matrix.py
scripts/verify_v3_run.py
```

### Modified modules

```text
src/cbsc_zdc/models/system.py
src/cbsc_zdc/models/response.py
src/cbsc_zdc/models/profile.py
src/cbsc_zdc/models/counts.py
src/cbsc_zdc/models/support.py
src/cbsc_zdc/models/node_fields.py
src/cbsc_zdc/training/trainer.py
src/cbsc_zdc/training/losses.py
src/cbsc_zdc/training/checkpoint.py
src/cbsc_zdc/config.py
src/cbsc_zdc/cli.py
src/cbsc_zdc/data/audit.py
src/cbsc_zdc/eval/evaluator.py
src/cbsc_zdc/eval/metrics.py
src/cbsc_zdc/preflight.py
```

### Required test files

```text
tests/test_v3_compatibility.py
tests/test_axis_features.py
tests/test_response_spline.py
tests/test_response_envelope.py
tests/test_hierarchical_first_layer.py
tests/test_longitudinal_activity.py
tests/test_autoregressive_counts.py
tests/test_support_temperature.py
tests/test_differentiable_stage_sampling.py
tests/test_conditional_critics.py
tests/test_adversarial_gradient_isolation.py
tests/test_replay_buffer.py
tests/test_critic_role_partition.py
tests/test_v3_checkpoint_resume.py
tests/test_topology_metrics.py
tests/test_correlation_metrics.py
tests/test_v3_end_to_end_smoke.py
```

The full assertion catalog is machine-readable under
`specs/improvement_v3/test_catalog.yaml`.

## 17. Explicitly rejected defaults

- Do not remove the exact decoder.
- Do not train a full-shower critic through current `sample()`.
- Do not merely remove `@torch.no_grad()`.
- Do not reset the critic every 20 epochs.
- Do not freeze one critic forever.
- Do not retain every historical fake or let history dominate.
- Do not train the p4 predictor on generated events.
- Do not make the classifier loss dominant.
- Do not use the external C2ST model as the training critic.
- Do not select on aggregate validation loss or C2ST alone.
- Do not add automatic GradNorm/PCGrad/ConFIG by default.
- Do not change model width/depth until full-data underfitting is shown.
- Do not apply OT coupling across incompatible hard share supports.
- Do not open the test split during these phases.

