# Losses: equations and physical/experimental meaning

## 1. Truth variables derived from each Geant4 shower

Let `Y[b,i] >= 0` be raw deposited energy in channel `i`. In the primary raw
mode, support means strictly positive stored energy:

```text
S_i = 1[Y_i>0]
D_l = sum_{i:layer(i)=l} Y_i
k_l = sum_{i:layer(i)=l} S_i
A_l = 1[k_l>0]
V   = 1[sum_l k_l>0]
T   = sum_l D_l = sum_i Y_i
f   = min{l:A_l=1} if V=1, otherwise -1
q   = max{l:A_l=1} if V=1, otherwise -1
Z_E = 1[f=0]
```

Layer shares and centered log-profile targets are:

```text
p_l = D_l/max(T,1e-12)
z_l^P = A_l*(log(max(p_l,1e-8))
          - mean_{j:A_j=1} log(max(p_j,1e-8))).
```

Within-layer shares and centered log-share targets are:

```text
w_i = Y_i/max(D_layer(i),1e-12)
z_i^S = S_i*(log(max(w_i,1e-8))
          - mean_{j:S_j=1, layer(j)=layer(i)} log(max(w_j,1e-8))).
```

These variables are deterministic functions of training data. Generated
counterparts receive hats.

## 2. Event-scale losses

### 2.1 Visibility: `L_visible`

```text
L_visible = BCEWithLogits(o_V,V).
```

Physical question: does the neutron produce any stored detector response?

Experimental meaning: it controls zero-event frequency, detection efficiency,
and any trigger/selection that requires nonzero response. It must not be asked
to compensate for a positive-response distribution that can create its own
zeros.

### 2.2 Positive total response: `L_response`

For a visible event, `r_T=T/C(K)` and `u=S_theta^{-1}(r_T;c)`:

```text
L_response = -log |du/dr_T| + log C(K).
```

Physical question: conditional on being visible, how much energy does the
calorimeter record?

Experimental meaning: it controls response scale, stochastic resolution,
skew/tails, and energy/direction dependence. It is distributional likelihood,
not only mean-squared response error. The bounded spline makes the visibility
hurdle the only zero mechanism.

## 3. Shower-start and longitudinal-support losses

### 3.1 ECAL-start: `L_ecal_start`

```text
L_ecal_start = BCEWithLogits(o_E,Z_E), over visible events.
```

Physical question: does the first stored interaction occur in ECAL layer 0?

Experimental meaning: it controls the rare early-interaction prevalence and
the existence of ECAL energy. It is separated because a rare layer-0 class was
nearly ignored inside the old 65-way categorical problem.

### 3.2 First HCAL layer: `L_hcal_first`

```text
L_hcal_first = CE(o_H,f-1), over visible events with f>0.
```

Physical question: if the shower does not begin in ECAL, at what HCAL depth
does the first stored interaction occur?

Experimental meaning: it controls the interaction-depth distribution and the
remaining longitudinal space available for shower development.

### 3.3 Last active layer: `L_active_last`

```text
L_active_last = CE(o_q,q), over visible events.
```

Physical question: how far through the calorimeter does observable activity
extend?

Experimental meaning: it controls shower length, leakage-like late activity,
and premature termination.

### 3.4 Internal gaps: `L_active_gap`

```text
L_active_gap = BCEWithLogits(o_G,G), for f<l<q.
```

Physical question: which layers inside the shower span are empty?

Experimental meaning: it controls intermittent longitudinal gaps and prevents
the generator from making every shower perfectly contiguous or unrealistically
fragmented.

### 3.5 Autoregressive activity alternative: `L_active_ar`

```text
L_active_ar = sum_l -log P(A_l | A_<l,c,T,f).
```

Physical question: after the development observed so far, should the next
layer be active?

Experimental meaning: it learns layer-transition and longer-range dependence
when a compact span/gap law is insufficient. It replaces, rather than adds to,
the span/gap losses in the primary activity model.

## 4. Longitudinal energy and occupancy losses

### 4.1 Profile flow matching: `L_profile_flow`

For target `z_1=z^P`, masked source `z_0~N(0,I)`, and `t~Uniform(0,1)`:

```text
z_t = (1-t)z_0+t z_1
u*  = z_1-z_0
L_profile_flow = sum_l A_l*(v_theta(z_t,t,c,T,A)_l-u*_l)^2 / sum_l A_l.
```

Physical question: how is total response divided among active layers?

Experimental meaning: it controls ECAL/HCAL fraction, shower maximum, early/
late deposition, longitudinal width, and event-to-event profile fluctuations.
It learns a conditional distribution, not one average profile.

### 4.2 Autoregressive count: `L_count_ar`

```text
L_count_ar = weighted sum_l -log P(k_l | k_<l,D,A,c),
weight_l = 1 if A_l=1 else 0.2.
```

Physical question: how many cells are positive in each layer, given layer
energy and previous occupancy?

Experimental meaning: it controls exact sparsity, energy per hit, shower
spread, and cross-layer occupancy correlations. At fixed `D_l`, larger `k_l`
means more diffuse energy.

## 5. Cell-support and energy-texture losses

### 5.1 Support BCE: `L_support_bce`

For positive and negative valid-channel counts `n_+` and `n_-`:

```text
w_+ = clip(n_-/max(n_+,1),1,100)
L_support_bce = BCEWithLogits(a_i,S_i,pos_weight=w_+), valid cells only.
```

Physical question: which detector cells are plausible hit locations?

Experimental meaning: it controls geometry-conditioned occupancy, lateral
shape, boundary behavior, and local hit probability. The class weight keeps
the many zeros from dominating.

### 5.2 Support ranking: `L_support_rank`

For sampled positive/negative pairs `(i+,i-)`:

```text
L_support_rank = mean softplus(-(a_i+ - a_i-)).
```

Physical question: should a true hit be ranked above a true empty cell?

Experimental meaning: exact top-k depends on ordering, so ranking is more
directly aligned with support selection than independent probability
calibration alone. It complements, not replaces, support BCE.

### 5.3 Share flow matching: `L_share_flow`

Using the same linear flow construction on `z^S` and masking to truth support:

```text
L_share_flow = sum_i S_i*(v_theta(z_t,t,c,D,k,S)_i-u*_i)^2 / sum_i S_i.
```

Physical question: after support and layer budget are known, how is energy
divided among hit cells?

Experimental meaning: it controls leading-cell energy, core-versus-halo
structure, positive-cell spectrum, concentration, and irregular cell-level
texture. The exact decoder, not this loss, guarantees the shares sum to `D_l`.

## 6. Dynamic-critic losses

### 6.1 Critic classification loss: `L_D`

The conditional critic returns larger logits for Geant4-like inputs:

```text
L_D = E_real softplus(-D(real,P))
    + E_fake softplus( D(fake_detached,P))
    + L_R1.
```

Experimental question: can a learned low-level observer distinguish Geant4
from the current generator after conditioning on incident four-momentum?

Meaning: it can detect combinations omitted by hand-designed losses—wrong
correlations among depth, width, occupancy, energy, and topology. Its own score
is not an unbiased scientific evaluation because it is optimized during
training; that role belongs to the independent external C2ST.

### 6.2 R1 critic regularization: `L_R1`

```text
L_R1 = gamma/2 * E_real ||gradient_real D(real,P)||_2^2.
```

Meaning: it makes the live critic locally smoother around Geant4 samples and
stabilizes the generator signal. It is an optimization regularizer, not a
detector-physics objective.

### 6.3 Direct generator adversarial loss: `L_adv`

```text
L_adv = E_fake softplus(-D(fake,P)).
```

Physical/experimental meaning: penalize any differentiable generated feature
that the live conditional critic uses as evidence of “not Geant4.” During this
loss the critic weights are frozen but the critic forward pass retains the
gradient with respect to its input.

D1 applies it only to within-layer energy shares under truth discrete
structure. D2 applies it only to the 65-layer energy profile under truth
visibility/total/activity. It is not an end-to-end loss on the current exact
sampler.

### 6.4 Feature-matching control: `L_feature`

```text
L_feature = ||mean_batch h(real)-mean_batch h(fake)||_2^2.
```

Meaning: match the critic’s learned representation without directly maximizing
its final real/fake score. It is a separate stability ablation, not an extra
term automatically combined with `L_adv`.

## 7. Diagnostic-only objectives unless triggered

### 7.1 Edge co-occupancy

```text
L_edge = mean_(i,j in graph) BCEWithLogits(b_ij,S_i*S_j).
```

Meaning: neighboring cells should be co-hit with the correct probability. Add
only after an edge/distance-conditioned topology mismatch is established.

### 7.2 Layer-correlation distance

```text
L_corr = ||Corr(D_fake)-Corr(D_real)||_F^2 / 65^2.
```

Meaning: early, late, ECAL, and HCAL energy fluctuations should co-vary like
Geant4. Initially use it as a metric because minibatch correlation gradients
are noisy.

### 7.3 Graph-Laplacian morphology

```text
Q(Y) = sum_(i,j in graph) w_ij*(Y_i-Y_j)^2/(T^2+eps)
L_Lap = MMD^2({Q(real)},{Q(fake)}).
```

Meaning: distinguish overly smooth showers from fragmented or isolated energy
fields. Add only if this exact mismatch is measured.

### 7.4 Frozen four-momentum utility

```text
L_p4 = Huber((K_hat-K)/s_K) + alpha*(1-u_hat dot u).
```

Meaning: the generated shower should retain incident-energy/direction
information usable by a Geant4-trained reconstructor. It does not prove realism
and can be gamed, so it is optional, frozen, ensemble-checked, and weak.

## 8. Exact objectives by phase

### 8.1 Corrected supervised v3

For `span_gaps` activity:

```text
L_base = lambda_V L_visible
       + lambda_T L_response
       + lambda_E L_ecal_start
       + lambda_H L_hcal_first
       + lambda_q L_active_last
       + lambda_G L_active_gap
       + lambda_P L_profile_flow
       + lambda_k L_count_ar
       + lambda_B L_support_bce
       + lambda_R L_support_rank
       + lambda_S L_share_flow.
```

For autoregressive activity, replace the `q` and `G` terms with
`lambda_A L_active_ar`. Do not use both activity formulations in one primary
run.

Starting weights are 1 for every new normalized NLL/BCE/flow term, except
`support_rank=0.25`, `count_ar=0.75`, matching the existing priors where names
correspond. Calibrate only after isolated component tests; freeze all values
before the external validation comparison.

### 8.2 D1 or D2 direct critic

```text
L_G = L_base_active_module + lambda_adv L_adv,
```

where `lambda_adv` is set by the measured gradient-ratio controller and only
the stage module is trainable.

### 8.3 D1 or D2 feature-matching control

```text
L_G = L_base_active_module + lambda_feature L_feature,
```

with the same gradient-ratio controller. Do not combine direct and feature
losses in the first screen.

## 9. Why no single giant loss

Every extra loss changes optimization and can improve one statistic while
damaging another. Therefore edge, correlation, Laplacian, support-critic, and
four-momentum terms are dormant code paths or later ablations. A term becomes
active only when its matching validation diagnostic identifies a residual and
the continuation plan’s paired comparison is declared.

