# Research blueprint: CBSC-ZDC v2

## Research question

Can a hierarchical conditional generator reproduce the readout-level distribution of single-neutron Geant4 showers in a frozen ZDC geometry, conditioned only on incident four-momentum, while avoiding impossible energy support, dense low-energy dust, invalid layer correspondence, and serial exposure bias?

A faithful implementation of this blueprint should produce a scientifically interpretable experiment. It cannot guarantee that the learned distribution will meet physics-accuracy requirements; that remains an empirical result.

## Data and scientific domain

- Intended source: approximately 765k non-pencil-beam neutron Geant4 events over 0-300 GeV.
- Primary reported domain: 50-250 GeV.
- Raw event condition: `p4=[E,px,py,pz]` only.
- Deterministic derived variables are permitted.
- Static geometry, masks, channel coordinates, layer labels, ganging metadata, and edges are detector configuration.
- Train-support experiment: matched 0-300 and 50-250 runs. Broader training may reduce boundary artifacts, but may also consume capacity on qualitatively different low-energy response.

## Output contract

Primary output:

```text
Y in R_+^(6790)
```

with one value per valid readout channel, after the target mode is frozen as either raw deposit or thresholded readout.

Auxiliary generated quantities:

```text
V                 visible/no-response indicator
T                 modeled total response
A_l               active-layer indicator
D_l               layer energy budget
R_reserve         unallocated/leakage accounting channel
K_l               resolved hit count
S_l               exact active readout set
U_l               subthreshold residual when thresholded mode is used
```

## Probability factorization

For condition `c=f(p4)` and static geometry `G`:

```text
p(Y,V,T,A,D,K,S | c,G)
 = p(V|c)
   p(T|V,c)
   p(A|T,V,c)
   p(D,R_reserve|A,T,c)
   p(K|D,A,c)
   p(S|K,D,A,c,G)
   p(Y|S,K,D,c,G).
```

A shared stochastic event latent is provided to the stages so that total response, longitudinal development, occupancy, and spatial width can remain correlated.

## Longitudinal model

The original proposal's monotone per-layer deposit condition is rejected. The revised model generates exact active-layer support, then allocates total response across active layers and a reserve channel using a masked simplex.

If `w_l>=0`, `w_res>=0`, and

```text
sum_l w_l + w_res = 1,
```

then

```text
D_l = T*w_l,
R_reserve = T*w_res,
R_l = T - sum_{j<=l} D_j.
```

`R_l` is non-increasing, but `D_l` may rise, fall, or have multiple peaks. The reference code uses a logistic-normal sampler. The research model should compare it with a low-dimensional conditional flow-matching model over the same masked-simplex target.

## Spatial model

The main spatial field is parallel, not a 65-call rollout. At each flow integration step, every node is updated. Layer tokens use a causal attention mask, so a layer may depend on its own and previous-layer states without teacher-forced sequential sampling.

The primary state has two node channels:

```text
support/ranking state
positive-energy share state
```

The field is conditioned on:

```text
p4 embedding
shared event latent
flow time
layer budget
layer count
static node geometry
causal layer context.
```

## Exact anti-dust decoding

Use the decoder in `docs/ANTI_DUST_DESIGN.md`. Top-k is the primary exact-support method. Compare it against sparsemax/entmax, hard-concrete gates, and an optional point-cloud baseline.

## Training stages

1. data and target audit;
2. response hurdle and bounded response model;
3. active-layer and longitudinal profile model;
4. count model;
5. spatial field trained with truth global quantities;
6. generated-count/generated-support exposure;
7. full-cascade fine-tuning only after isolated-stage reporting;
8. matched baseline and ablation runs.

## Baselines

- competent conditional empirical/template baseline;
- direct `m-wojnar/faster_zdc` reproduction on its native data, then architecture adaptation where dimensionally sensible;
- original `m-wojnar/zdc` ZN models;
- ExpertSim mixture-of-generative-experts;
- supplied single-stage graph-flow baseline on identical data and geometry;
- non-graph parallel CFM with the same decoder;
- serial previous-layer model as a diagnostic ablation;
- optional sparse point-cloud generator.

## Recommended QA/report locations

No user-imposed physics gates are added. Report at:

- raw data conversion;
- target/threshold selection;
- split creation;
- each isolated stage;
- every epoch on frozen free-running banks;
- each baseline comparison;
- final in-domain, stress-domain, downstream, and timing evaluations.

Exact algebraic identities and tensor-validity checks remain software assertions rather than scientific performance gates.
