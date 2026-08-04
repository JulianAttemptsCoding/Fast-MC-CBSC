# Can a classifier tell Geant4 from CBSC-ZDC Fast-MC?

**Yes, essentially perfectly.** Given the full 6,790-channel ZDC readout plus the
incident neutron four-vector, a trained discriminator identifies which generator
produced an event with **AUROC 0.99945 ± 0.00009** over five independent
trainings.

Study run 2026-07-28, Vertex custom jobs `4939197830460866560` (generation) and
`2861974074987380736` (discrimination), Tesla T4, PyTorch 2.6.0+cu124.

## Setup

| | |
|---|---|
| Geant4 class | 40,000 events from the CBSC-ZDC **test** split |
| Fast-MC class | 40,000 events, 10,000 from each calibrated epoch-4 family |
| Conditions | resampled from the **train** split; no test four-vector reaches the generator |
| Partitions | 56,000 train / 12,000 validation / 12,000 test, stratified by class and family |
| Selection hash | `79433330ff9009120aea53525fcee3a270ab0c9806ead848bef27bc40bc65a55` |
| Geometry | `e22d4cfb1e9293a33dd13151587910268ba64cd8efbcdb7a835a7442f2edcb4b`, 6,790 channels, 65 layers |

## Headline

| Model | Input | AUROC |
|---|---|---:|
| **hybrid (primary)** | hits + profile + condition | **0.99945 ± 0.00009** |
| dense | flat 6,790 channels, geometry-blind | 0.99616 |
| high-level GBM | 15 shower observables | 0.98518 |
| **condition only (control)** | four-vector alone | **0.50363** |

The condition-only control sits at chance — validation loss 0.69316, which is
`ln 2` to five decimals, permutation p = 0.51. The separation therefore comes
entirely from the calorimeter deposits and is not an artefact of mismatched
incident conditions.

Best single training: AUROC 0.999607, DeLong 95% CI [0.999503, 0.999710],
accuracy 0.988417 against a null sigma of 0.004564 (z = 107.0), permutation
p < 0.001, ECE 0.0027, Jensen-Shannon distance 0.9817, 516,993 parameters.

## Do the four families differ? Yes, and it tracks validation loss

Three independent classifiers, one consistent ordering:

| Family | Published val loss | Hybrid AUROC | Dense AUROC | GBM AUROC |
|---|---:|---:|---:|---:|
| `calibrated_lr3e4` | **4.738041** (best) | **0.99945** | **0.99488** | **0.97739** |
| `calibrated_lr1e4_halfbatch` | 4.845029 | 0.99956 | 0.99583 | 0.98315 |
| `calibrated_lr1e4` | 4.827105 | 0.99976 | 0.99683 | 0.98861 |
| `calibrated_lr3e5` | 4.897327 (worst) | **0.99983** | **0.99747** | **0.99149** |

The best-loss family is the least detectable and the worst-loss family the most,
on all three classifiers independently. The extremes have non-overlapping 95%
bootstrap intervals, so the ordering is real. Only the middle two swap.

**The effect is real but small.** All four sit at AUROC 0.977-0.9998. A better
validation loss buys a marginally less detectable generator, not a meaningfully
more faithful one.

## Separability does not depend on incident energy

| Domain | AUROC (GBM) |
|---|---|
| 0-50 GeV, below the claim domain | 0.9846 |
| 50-250 GeV, primary claim domain | 0.9795 - 0.9883 |
| 250-300 GeV, above | 0.9887 |

Flat across 0-300 GeV. The discrepancy is a systematic modelling difference, not
an edge or extrapolation effect.

## Which observable gives it away

Each shower observable scored on its own. Separability is folded above chance, so
0.5 means the observable carries no class information.

**Correct, at chance:**

| Observable | Separability | Relative bias |
|---|---:|---:|
| `hit_count` | 0.5024 | -1.4% |
| `depth_centroid_layer` | 0.5043 | -4.0% |
| `ecal_fraction` | 0.5063 | -0.00003% |
| `total_response_gev` | 0.5104 | +3.0% |

**Wrong:**

| Observable | Separability | Mean bias | Width bias |
|---|---:|---:|---:|
| `radial_rms_mm` | **0.7558** | **+22.3%** (87.5 -> 107.0 mm) | +35.8% |
| `top5_fraction` | 0.6856 | -33.3% (0.346 -> 0.231) | -33.7% |
| `top1_fraction` | 0.6422 | -47.6% (0.157 -> 0.082) | -48.4% |
| `hit_energy_gini` | 0.6392 | -3.8% | +55.4% |
| `late_fraction` | 0.5486 | -44.5% | -47.7% |

**The generator gets the global budget right and the internal energy
distribution wrong.** Total response, hit multiplicity, ECAL fraction and shower
depth are all essentially correct. What is wrong is how the energy is arranged
inside the shower: about 22% too broad transversally, with the hottest cell
holding barely half the energy fraction it should.

That localises to the second half of the generative hierarchy — support scoring,
the Gumbel-Top-k draw, and the share flow — rather than the response or
longitudinal profile stages.

No single observable exceeds 0.76 while the pooled classifiers reach 0.985 and
0.9995, so the separation is genuinely multivariate: it lives in the joint
structure, which is why a full-detector classifier was worth building.

## How much noise erases the difference

Each cell's deposited energy is treated as a population of particles undergoing
3D Brownian motion for time `t`; the noise level is the diffusion length
`lambda = sqrt(2 D t)` in millimetres. The median channel spacing is 36.809 mm.

| lambda (channel widths) | lambda (mm) | Fixed classifier | Retrained control |
|---:|---:|---:|---:|
| 0.00 | 0.0 | 0.9996 | 0.9852 |
| 0.35 | 12.9 | 0.9962 | |
| 0.50 | 18.4 | 0.9141 | |
| 0.75 | 27.6 | 0.6197 | 0.9818 |
| **1.00** | **36.8** | **0.5040** | **0.9842** |
| 1.50 | 55.2 | 0.4575 | 0.9790 |
| 3.00 | 110.4 | 0.4910 | |
| 12.00 | 441.7 | 0.4889 | |

Read this carefully, because the two columns disagree completely.

**A frozen classifier is blinded by one channel width of diffusion** — 36.8 mm.
The transition is a cliff, not a slope: near-perfect separability collapses to
chance between 0.35 and 1.0 channel widths.

**A classifier allowed to retrain on the diffused data is barely affected.** At
the same 36.8 mm it still scores 0.9842, against an undiffused baseline of
0.9852. The difference is not erased at all; the frozen model is simply looking
for features that the noise disturbed.

There is a clean reason. Diffusion adds the *same* variance to both classes, so a
*ratio* difference in transverse width survives almost untouched:

```text
undiffused    87.5 vs 107.0 mm                       ratio 1.222
plus 1 cell   sqrt(87.5^2+36.8^2) = 94.9  vs
              sqrt(107^2+36.8^2)  = 113.2            ratio 1.193
```

And because the diffusion kernel is row-stochastic it conserves every event total
exactly, so no amount of spatial smearing can touch an energy-scale difference
either. Out to 12 channel widths — 441.7 mm, wider than the detector face — the
retrained classifier still separates the two sources.

A particle-counting variant (`E -> q * Poisson(E / q)` with `q = 1e-4` GeV, about
27 pseudo particles in a typical cell) was run alongside and tracks the spatial
sweep closely: 0.9955 undiffused, 0.5235 at one channel width. It confirms rather
than changes the picture.

**Answer: 36.8 mm of Brownian diffusion blinds a fixed classifier, but no tested
amount makes the two sources genuinely equivalent. Spatial diffusion is the wrong
axis for this particular discrepancy.**

## Boundary

- This measures separability, not Geant4 fidelity. A high AUROC is a genuine
  falsification; nothing here validates the Fast-MC as a physics surrogate.
- The four families are epoch-4 checkpoints from short pilot training. This is
  not a statement about the architecture's ceiling.
- No result here may influence CBSC-ZDC training, configuration, or checkpoint
  selection. See `docs/ISOLATION.md`.
- 40,000 of the 76,300 CBSC-ZDC test events were consumed by this study and must
  be disclosed in any future publication using that split. The remaining 36,300
  are untouched.

## Figures

See `figures/`. `REPORT.md` in this directory is the full machine-generated
report; `results.json` carries every number with its provenance.
