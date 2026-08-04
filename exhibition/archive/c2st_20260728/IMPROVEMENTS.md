# How the CBSC-ZDC Fast-MC could be improved

Evidence-backed analysis based on the classifier two-sample test in
`results/20260728-r2/`, the per-observable diagnosis, the energy-binned
comparisons in `exhibition/`, and direct measurement of the generator's own
internals.

Nothing here may be applied to CBSC-ZDC without a separately declared experiment.
`docs/ISOLATION.md` rule 1 forbids this study from steering training or
checkpoint selection; this document is analysis, not authorisation.

---

## 1. What the evidence actually says

The discriminator reaches AUROC `0.99945`, so the two sources are trivially
separable. The per-observable breakdown says *where*:

| Reproduced correctly (separability at chance) | Reproduced badly |
|---|---|
| total response `+3.0%` | transverse radial RMS **`+22%` to `+27%`** |
| hit multiplicity `-1.4%` | top-1 cell fraction **`-41%` to `-56%`** |
| ECAL fraction `-0.00003%` | top-5 cell fraction `-27%` to `-39%` |
| shower depth centroid `-4.0%` | late-shower fraction `-35%` to `-59%` |
| active layer count `-2%` | |

**The generator solves the budgeting problem and fails the placement problem.**
It puts the right total energy into the right number of cells spread over the
right layers, and then arranges that energy too diffusely inside each layer.

The radial energy density (`figures/13_radial_energy_density.png`)
shows this directly. At every energy the Fast-MC core is roughly **2.5-3x too
low** while the tail beyond about 50 mm is **1.5-2x too high**, with a crossover
near one HCAL channel width. Energy is being moved out of the core into the
periphery.

Two further patterns matter for diagnosis:

- the radial bias is **flat in energy** (`+0.22` to `+0.27` across 0-300 GeV),
  which points at a mechanism that does not scale with shower size;
- the top-1 deficit **worsens monotonically with energy** (`-0.45` at 12 GeV to
  `-0.56` at 288 GeV), which points at a mechanism whose absolute damage grows
  with the number of cells selected.

Both signatures are explained by the same cause.

---

## 2. Root cause 1: the Gumbel-Top-k support draw is noise-dominated

**This is the primary finding and it is measured, not inferred.**

`src/cbsc_zdc/models/support.py:21` implements the support draw as

```python
scores = logits - torch.log(-torch.log(u))
```

which is Gumbel-Top-k at temperature exactly 1. Gumbel noise has a fixed
standard deviation of `pi/sqrt(6) = 1.2825`. Whether that noise is negligible or
dominant depends entirely on the spread of the support logits it is added to,
and that spread is a property the model was never constrained to control.

Measured on the `calibrated_lr3e4` epoch-4 checkpoint over 616 populated layers
spanning 25-275 GeV (`exhibition/evidence/gumbel_selection_sharpness.json`):

```text
Gumbel noise standard deviation             1.2825
median within-layer support logit std       1.4127
effective noise / signal                    0.908
median logit gap at the selection boundary  0.0235
```

The gap between the last selected and the first rejected cell is `0.0235`, while
the noise added to each is `1.28`. The noise is roughly **fifty times larger than
the decision it is perturbing.**

Define selection sharpness as the overlap between the stochastic draw and the
model's own deterministic top-k, rescaled against the uniform-random baseline
`k/N`:

```text
sharpness = (overlap - k/N) / (1 - k/N)
0 = indistinguishable from picking k cells at random within the layer
1 = the learned ranking is followed exactly
```

Measured sharpness at the current setting: **`0.466`**.

**More than half of the geometry-aware support scorer's output is discarded by
its own sampling step.** Roughly one selected cell in two is placed by noise
rather than by the learned preference. Those cells land away from the core, and
because the decoder enforces exact layer budgets, energy must be taken from the
core to fill them. That is precisely the observed core deficit, tail excess,
inflated radial RMS, and suppressed top-cell fraction.

It also explains both energy trends: the *fraction* of misplaced cells is
constant, so the radial bias is flat, while the *number* of misplaced cells grows
with `k`, so the concentration deficit worsens with energy.

### The fix and its measured size

Introduce a temperature on the support logits:

```python
scores = logits / tau + gumbel
```

Measured sharpness against `tau`:

| `tau` | mean overlap | sharpness | effective noise/signal |
|---:|---:|---:|---:|
| 1.00 (current) | 0.6215 | **0.4658** | 0.908 |
| 0.70 | 0.6825 | 0.5608 | 0.636 |
| 0.50 | 0.7407 | 0.6473 | 0.454 |
| 0.35 | 0.7978 | 0.7293 | 0.318 |
| 0.25 | 0.8441 | 0.7937 | 0.227 |
| 0.15 | 0.8983 | 0.8668 | 0.136 |
| 0.10 | 0.9295 | 0.9078 | 0.091 |
| 0.05 | 0.9634 | 0.9518 | 0.045 |

A temperature near `0.25-0.35` roughly doubles the effective sharpness.

Two important caveats. First, `tau` is a genuine physical knob, not a free win:
real showers *are* stochastic in which cells fire, so driving `tau` to zero would
produce showers that are too deterministic and would show up as too-narrow
distributions and suppressed diversity. It should be **calibrated against the
radial RMS and top-1 fraction**, not minimised. Second, temperature is not the
only route — the same effect is obtained by letting the support head learn a
scale, or by training the support loss on the *sampled* support rather than only
on the ranking. The temperature is simply the cheapest thing to test.

Recommended first experiment: freeze everything else, sweep
`tau` in `{1.0, 0.5, 0.35, 0.25, 0.15}` at inference only on an existing
checkpoint, and measure radial RMS and top-1 fraction against Geant4. This costs
no training at all and would either confirm or kill the hypothesis in under an
hour of GPU time.

---

## 3. Root cause 2: no incident-axis-relative node features

The node features are fixed detector metadata
(`docs/DATA_CONTRACT.md`): `[x_norm, y_norm, z_norm, layer_fraction, is_ecal,
is_hcal]`. They are identical for every event. The only per-event information the
support and share fields receive is the 128-dimensional condition vector,
broadcast identically to all 6,790 nodes, plus the layer energy and count
fraction.

So the network must construct an event-specific transverse profile, centred on an
event-specific shower axis, out of a global vector plus three message-passing
blocks over a fixed graph. It has no coordinate telling it "how far is this cell
from where the shower actually is".

The geometry makes this concrete. The production vertex is fixed at
`[-917.41, -30.0, 35488.91]` mm and the detector spans `z = 35718.6` to
`37387.3` mm. Incident directions have `u_x`, `u_y` standard deviations of about
`0.174`, bounded within `+/-0.441`. The extrapolated shower axis therefore moves

```text
at the front face  (230 mm from vertex):   ~40 mm at 1 sigma  ~ 1.3 ECAL cells
at the back        (1899 mm from vertex):  ~330 mm at 1 sigma ~ 5.8 HCAL cells
```

The axis wanders by several channel widths across the detector depth, differently
in every event, and nothing in the node features encodes it.

**Recommendation.** Add per-event node features computed from the incident
four-vector and the frozen geometry:

- `r_perp`: perpendicular distance from the cell to the extrapolated incident
  line, normalised by a characteristic Moliere-like scale;
- `log1p(r_perp)`, since transverse profiles are approximately exponential;
- `s_along`: distance along the axis from the vertex, normalised;
- optionally `cos(phi)`, `sin(phi)` about the axis.

These are cheap deterministic functions of data the model already has, they add
no parameters beyond a slightly wider input layer, and they hand the network the
coordinate the transverse profile is actually a function of. This is the standard
representation choice in the calorimeter-surrogate literature, where models are
usually given cylindrical coordinates about the incident axis rather than
absolute detector coordinates.

Because the node features are part of the frozen geometry artifact, this change
requires a new geometry build and a new frozen config, so it is a larger
experiment than the temperature sweep. It is the highest-value *architectural*
change on this list.

---

## 4. Root cause 3: the loss weights under-weight exactly what is broken

The calibrated nine-loss weights are:

```text
visible       2.574417     support_rank   1.477591
first_layer   2.159451     support_bce    1.324108
active        0.536770     share_flow     0.444960
response      0.160901     profile_flow   0.160901     count  0.160901
```

The components governing the observables that are wrong carry the lowest weights:
`share_flow` at `0.445` controls within-layer energy sharing, which is exactly the
top-1 and Gini defect, and `profile_flow` at `0.161` controls the longitudinal
shape, which is exactly the `-35%` to `-59%` late-fraction defect. Meanwhile
`visible` at `2.574` governs a hurdle whose zero-response rate is already
essentially correct, and `first_layer` at `2.159` governs a quantity the diagnosis
finds at chance separability.

This is not a mistake in the calibration procedure; it is a consequence of what
that procedure optimises. `docs/LOSS_WEIGHT_PROTOCOL.md` derives the weights from
**inverse median gradient norms on the shared condition encoder**, which equalises
how loudly each head speaks to the encoder. It says nothing about which head
matters for physics. The protocol anticipates this: step 8 is *"select using
physics metrics, not aggregate loss alone"*, and step 7 is a validation-only
sensitivity study around major loss families. The four calibrated families differ
only in learning rate and batch size, so that step appears not to have been
exercised.

**Recommendation.** Run the protocol's own step 7/8: a validation-only sensitivity
scan multiplying `share_flow` and `profile_flow` by `{2, 4, 8}` while holding the
rest fixed, selecting on the radial RMS, top-1 fraction and late fraction rather
than on the aggregate objective. Note that the aggregate validation loss will
almost certainly get *worse* under a reweighting that improves physics, because
it is a different objective. That is expected and is not a regression.

---

## 5. Root cause 4: the models are barely trained

All four families are epoch-4 checkpoints from a bounded 26,624-event training
bank, out of 612,482 available train events. They have seen roughly **4.3% of the
training corpus once**. The E3 regression followed by E4 recovery recorded in
`audit/compute_extension_20260727_r2_terminal_analysis.md` is the signature of a
model still early in optimisation.

Some of the observed discrepancy is simply undertraining, and any architectural
conclusion drawn at epoch 4 is provisional. **Before attributing a defect to the
architecture, the cheapest control is to train the existing architecture on the
full train split for a realistic number of epochs and re-measure.** The C2ST is
the natural progress metric: AUROC should fall, and the per-observable table says
which observable is improving.

---

## 6. What will not work, and why

**Post-hoc classifier reweighting (DCTR, arXiv:2009.03796) is not viable at the
current fidelity.** DCTR corrects a generator by weighting samples with
`w = p/(1-p)` from a Geant4-vs-generated classifier. That works when the classifier
is weak, because the weights stay near 1. Here the classifier reaches AUROC
`0.99945`, meaning `p` is near 0 or 1 for almost every event, so `w` is wildly
dispersed and the effective sample size collapses to a tiny fraction of the
generated statistics. Reweighting is a finishing tool for a generator that is
already close, and it becomes worth revisiting only once the AUROC is down around
`0.6` or below.

The same caveat applies more weakly to regression-based refinement such as Fast
Perfekt: learning a deterministic morphing from Fast-MC to Geant4 is far harder
when the two distributions barely overlap in the observables that matter.

**Do not tune against this study's discriminator.** Beyond the isolation contract,
optimising a generator against a fixed classifier is adversarial training with a
frozen critic, and it reliably produces a generator that defeats that specific
critic without becoming more faithful. If a classifier is ever used in the training
loop it must be retrained continuously and the reported evaluation classifier must
be a separate, freshly trained one.

---

## 7. Ranked recommendations

| # | Change | Expected impact | Cost | How to verify |
|---|---|---|---|---|
| 1 | Support temperature `tau` about `0.25-0.35`, calibrated not minimised | High. Directly targets the measured `0.466` sharpness, the core deficit, radial RMS and top-1 fraction | Very low: inference-only sweep on an existing checkpoint, then one short retrain | Radial RMS bias, top-1 fraction, radial density core-to-tail ratio |
| 2 | Train on the full 612,482-event split for a realistic horizon | High but unknown split between "undertrained" and "architectural" | High: this is the real training run | C2ST AUROC trend and the per-observable table |
| 3 | Incident-axis node features `r_perp`, `log1p(r_perp)`, `s_along` | High. Removes a genuine representational bottleneck for the transverse profile | Medium: new geometry build, new frozen config | Radial density shape, radial RMS energy dependence |
| 4 | Loss-weight sensitivity on `share_flow` and `profile_flow`, selected on physics metrics | Medium to high. Targets top-1, Gini and late fraction | Medium: validation-only scan, the protocol's own step 7/8 | Late fraction, top-1 fraction, Gini |
| 5 | Energy-weighted support loss so hot cells dominate the BCE and ranking terms | Medium. Currently every cell counts equally, so the core is not privileged | Low: loss change only, a new declared experiment | Top-1 and top-5 fraction |
| 6 | More share-flow solver steps, or a more expressive share field | Low to medium. 8 steps may under-resolve the sharing distribution | Low: inference-only step sweep first | Top-1 fraction, cell energy spectrum |
| 7 | Post-hoc reweighting or regression refinement | None yet; revisit below AUROC about 0.6 | Low | Effective sample size of the weights |

Recommendation 1 is the obvious first move: it is nearly free, it is directly
predicted by a measurement rather than a hunch, and it is falsifiable in an hour.

---

## 8. A note on what "better" means here

The four families differ in detectability in a way that tracks validation loss:
`calibrated_lr3e4` has both the best validation loss and the lowest AUROC on all
three classifiers, `calibrated_lr3e5` the worst and highest. So the training
objective is not measuring the wrong thing.

But the effect is tiny. Every family sits between AUROC `0.977` and `0.9998`. A
`3.4%` improvement in validation loss moved the GBM AUROC by about `0.014`. On
that slope, closing the gap to indistinguishability by optimising this objective
alone is not a realistic path. The defects identified above are structural, and
they need structural changes, not more of the same objective.

---

## References

- Krause, C. et al., *CaloChallenge 2022: A Community Challenge for Fast
  Calorimeter Simulation*, arXiv:2410.21611. Normalising flows and diffusion
  models dominated fidelity; representation and conditioning choices mattered more
  than raw capacity. <https://arxiv.org/abs/2410.21611>
- Diefenbacher, S. et al., *DCTRGAN: Improving the Precision of Generative Models
  with Reweighting*, JINST 15 P11004, arXiv:2009.03796.
  <https://arxiv.org/abs/2009.03796>
- Favaro, L. et al., *CaloDREAM: Detector Response Emulation via Attentive flow
  Matching*, arXiv:2405.09629. Conditional flow matching with attention on
  calorimeter showers. <https://arxiv.org/pdf/2405.09629>
- *A Comprehensive Evaluation of Generative Models in Calorimeter Shower
  Simulation*, arXiv:2406.12898. <https://arxiv.org/pdf/2406.12898>
- Kool, W., van Hoof, H. and Welling, M., *Stochastic Beams and Where to Find
  Them: The Gumbel-Top-k Trick*, ICML 2019. The sampling step whose temperature is
  the subject of section 2.
- Chen, Z. et al., *GradNorm*, ICML 2018. The gradient-balancing idea behind the
  loss-weight calibration discussed in section 4.
