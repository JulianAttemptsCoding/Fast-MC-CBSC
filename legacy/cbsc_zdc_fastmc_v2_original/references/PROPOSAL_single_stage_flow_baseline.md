# Proposal: Single-Stage Graph Flow Baseline, Trained on the Same Real Data

## 1. What this is

A concrete plan to implement and train the **fourth, still-missing required baseline**
from this project's original scope: a single-stage generative flow, as a controlled
comparison against the current hierarchical (start-depth -> profile -> cell) model,
trained and evaluated on the *exact same real dataset, splits, and geometry* already
used throughout this project. Motivated by, and citing, a directly relevant recent paper
on flow-matching for zero-degree-calorimeter fast simulation (§2).

This is a plan and cost/design analysis, not an implementation -- nothing described here
has been built yet.

## 2. Related work (researched and cited for this proposal)

1. **Wojnar, M. "Even Faster Simulations with Flow Matching: A Study of Zero Degree
   Calorimeter Responses."** arXiv:2507.18811 (2025). Code:
   [github.com/m-wojnar/faster_zdc](https://github.com/m-wojnar/faster_zdc). Author
   affiliated with AGH University of Krakow (per search indexing; not independently
   confirmed from the paper's own metadata).

   Verbatim abstract: *"Recent advances in generative neural networks, particularly flow
   matching (FM), have enabled the generation of high-fidelity samples while
   significantly reducing computational costs. ... we leverage FM to develop surrogate
   models for fast simulations of zero degree calorimeters in the ALICE experiment. We
   present an effective training strategy that enables the training of fast generative
   models with an exceptionally low number of parameters. This approach achieves
   state-of-the-art simulation fidelity for both neutron (ZN) and proton (ZP) detectors,
   while offering substantial reductions in computational costs compared to existing
   methods. Our FM model achieves a Wasserstein distance of 1.27 for the ZN simulation
   with an inference time of 0.46 ms per sample, compared to the current best of 1.20
   with an inference time of approximately 109 ms. The latent FM model further improves
   the inference speed, reducing the sampling time to 0.026 ms per sample, with a
   minimal trade-off in accuracy. Similarly, our approach achieves a Wasserstein distance
   of 1.30 for the ZP simulation, outperforming the current best of 2.08."*

   Relevant facts for this proposal: **single-stage** flow matching (no hierarchy), no
   graph structure mentioned in the abstract (see §3 for what could and couldn't be
   confirmed about ALICE's ZN/ZP representation), and a **"latent FM" variant** that
   compresses the target into a
   smaller latent space before running the flow, trading a small accuracy loss for a
   further ~18x speedup (0.46ms -> 0.026ms). The identity of the "current best" baseline
   (WD 1.20 ZN / 2.08 ZP) is not stated in the abstract and was not independently
   resolved for this proposal -- flagged rather than guessed.

2. **Majerz, E., Dzwinel, W., Kitowski, J. "Inverse Autoregressive Flows for Zero Degree
   Calorimeter fast simulation."** arXiv:2512.20346.

   Verbatim abstract: *"...We leverage this paradigm to accelerate simulations of the
   Zero Degree Calorimeter (ZDC) of the ALICE experiment at CERN. Our method introduces a
   novel loss function and an output variability-based scaling mechanism, which enhance
   the model's capability to accurately represent the spatial distribution and morphology
   of particle showers in detector outputs while mitigating the influence of rare
   artefacts on the training. Leveraging Normalizing Flows (NFs) in a teacher-student
   generative framework, we demonstrate that our approach not only outperforms classic
   data-driven model assimilation but also yields models that are 421 times faster than
   existing NF implementations in ZDC simulation literature."*

   Relevant fact: confirms an active, current (2025) research line specifically on
   flow-based ZDC fast-simulation, and that "rare artefacts" / output-variability
   handling is a live concern in this exact problem class -- directly relevant to this
   project's own documented sentinel-hit tail (§`LIMITATIONS.md` item 3: 1.9% of events
   lose >10% of HCAL energy to sentinel removal).

3. Prior citations already used in this project's evaluation-methodology grounding
   (`analysis.md` §7), repeated here for a complete reference list: **CaloChallenge 2022**
   (arXiv:2410.21611); **CaloFlow** (Krause & Shih, arXiv:2106.05285) and **CaloFlow II**
   (arXiv:2110.11377); **CaloGAN** (Paganini, Oliveira et al.); **L2LFlows**
   (arXiv:2302.11594).

4. This project's own prior identification of the gap this proposal fills:
   `FINAL_QA_REPORT.md` gate table: *"Baselines: single-stage graph flow | NOT IMPLEMENTED
   | requires a new model variant."*

## 3. Why "single-stage *graph*" flow, not a direct port of Wojnar's model

Wojnar's model cannot be trained on our data as-is. Neither the paper's abstract nor its
repository README, as fetched for this research pass, state the exact ZN/ZP response
dimensionality -- this was **not independently confirmed** and should not be taken as a
cited fact. What *is* confirmed: the repo's own README describes CNN/UNet/Transformer
encoder-decoder backbones, which is only consistent with a fixed, regular (image-like or
short-vector) input -- ALICE's ZN/ZP are widely known in the fast-calorimeter-simulation
literature to be low-channel-count devices (a handful of towers each), which would fit
that description, but this proposal treats that as a reasonable inference, not a verified
number. Our detector is 400 ECAL + 6,390 HCAL = 6,790 irregularly-tiled nodes across 65 layers,
with a real k-NN graph (lateral + longitudinal edges) already built and verified
(`data/geometry.csv`, `src/zdcfast/geometry.py`). Forcing our data into a fixed
image-like shape to reuse their exact architecture would either discard real geometric
information or require an arbitrary, unjustified re-gridding.

The right adaptation, and the one this project's own gate table already names
(`FINAL_QA_REPORT.md`: *"Baselines: single-stage graph flow | NOT IMPLEMENTED"*, quoted
in full in §2 point 4), is a **single-stage flow that keeps the graph** -- i.e., take the existing
`GraphCellVectorField` message-passing architecture (`src/zdcfast/models/cell_flow.py`)
and the same rectified-flow / flow-matching training recipe already used for the
`profile_flow` and `cell_flow` stages, but collapse the current 3-stage hierarchy
(`StartDepthNet` -> `ProfileVectorField` -> `GraphCellVectorField`) into **one** flow that
predicts, per node, both channels (occupancy logit, conditional energy score) directly
from noise, conditioned only on the 11-dimensional condition vector
(`build_condition_features`, `transforms.py:35-68`) -- no separately-generated global
profile, no separate start-depth classification.

**A useful framing, worth stating explicitly**: Wojnar's own "latent FM" variant
(compress to a small latent space, flow there, then decode) is conceptually close to
what this project's *existing* hierarchical model already does -- the profile flow *is*
a form of flow-in-a-compressed-representation (130 dimensions) before a second stage
fills in per-cell detail. The single-stage baseline proposed here tests the *other* end
of that same spectrum: no compression stage at all, one flow directly in the full
6,790-node space. This makes the comparison a genuine, well-motivated ablation of the
hierarchy itself, not an arbitrary alternative architecture.

## 4. Data plan

**Identical to the existing model, deliberately, to make the comparison valid**:

- Same source file: `gs://asiop-zdc-1-zdc-reco-us-central1/data/myTree_20251117_765k_
  0to300GeV_neutron_All.root`, same canonicalized shards (`data/processed/`), same
  70/10/20 hash split (train/validation/test).
- Same geometry (`data/geometry.csv`, 6,790 nodes, same k-NN graph settings:
  `lateral_k_ecal=8`, `lateral_k_hcal=6`, `longitudinal_k=3`, bidirectional).
- Same condition vector construction (`build_condition_features`): four-momentum +
  entry point -> 11 derived features.
- Same statistics/standardization pipeline (`statistics.pt`).

No new data engineering is required -- this is the direct benefit of proposing a
baseline that reuses this project's already-verified data contract rather than adopting
a different dataset's representation.

## 5. Proposed architecture (concrete)

- Reuse `StaticMessagePassingBlock` / `LongitudinalLayerMixer` (the same message-passing
  primitives already in `graph_blocks.py`, already float32-accumulation-safe per this
  project's own earlier bugfix) as the flow's velocity-prediction network.
- State: 2 channels per node (occupancy score, conditional energy score) -- identical to
  the existing `CellFieldTransform` target encoding, so the existing decoder
  (exact top-k/softmax) can be reused unchanged.
- Conditioning: the raw 11-dim condition vector directly (via FiLM-style modulation or
  concatenation into the first message-passing block's node features -- exact mechanism
  to be decided during implementation, not fixed by this proposal).
- Longitudinal structure (which the current model gets explicitly from the start-depth
  classifier + profile flow's per-layer fractions) must be learned **implicitly** through
  the graph's longitudinal edges and message passing alone. This is the central open
  question this baseline is designed to answer (§8).
- Training: straight-line rectified-flow interpolation + velocity matching, matching the
  existing `cell_flow_loss` recipe, including the existing auxiliary losses
  (`lambda_hit_bce`, `lambda_count`, `lambda_moment` -- all already implemented and
  tuned in `losses.py`, reusable without modification).
- Sampling: same 8-step integration as the existing cell flow, for a fair
  throughput comparison.

## 6. Training plan (phased, budget-aware)

Remaining budget in this project's $90 GPU-spend cap: **~$11.80** (see
`outputs/cost_ledger.md` -- $78.2 spent as of the last full-scale evaluate run). This
project's own measured full-width cell-stage cost is $9.50-9.83/epoch (11.2-11.3h/epoch
on a single T4); a single-stage flow over the same 6,790-node graph is unlikely to be
meaningfully cheaper per epoch (same graph, same data volume, same message-passing cost
per forward pass, only removing the separate profile-flow forward pass), so the
remaining budget realistically funds **one, at most two**, full-scale epochs -- not
enough for a real comparison at full scale.

Proposed phasing, mirroring the pilot-then-full-scale discipline already used for the
main model:

- **Phase A -- pilot-scale, fits in remaining budget.** Train on the existing 100k-event
  pilot split (`data-pilot`, already in GCS), reduced width matching the pilot's own cell
  flow (`cell_hidden_dim=64`, `message_passing_blocks=3` -- no separate profile-net width
  applies here since there is no separate profile stage in this design), for a small
  number of epochs (5-8). Cost estimate grounded in this project's own measured pilot
  cell-stage rate ($8.10 / 10 epochs = $0.81/epoch, `outputs/cost_ledger.md`): **~$4-6.5
  total** for 5-8 epochs, comfortably inside the ~$11.80 remaining budget, leaving margin
  for the evaluate run afterward (historically $0.20-1). Evaluate with the *unmodified*
  `zdcfast.evaluate` module against: (a) the
  existing hierarchical model's pilot-scale checkpoint, (b) the conditional-template
  baseline -- all three on the identical pilot test split, for a clean 3-way comparison
  at matched scale.
- **Phase B -- full-scale, needs new/additional budget.** Only after Phase A's result is
  reviewed. Train on the full 764,940-event dataset at full width, matching the effort
  already spent on the hierarchical model, for a true final comparison. Explicitly
  **not** committed to by this proposal -- requires a separate budget decision.

## 7. Evaluation plan

No new evaluation code needed. Reuse `zdcfast.evaluate` unchanged -- same gates,
same metrics (cell-level and response-level Wasserstein distance with truth-floor
normalization, low/high-level classifier AUC, longitudinal-profile total variation,
throughput), same `configs/*.yaml` gate thresholds. This guarantees the comparison is
apples-to-apples with every number already reported in `analysis.md` for the
hierarchical model and the conditional-template baseline.

Additionally, once Phase A completes, the existing fixed-condition grid harness
(`scripts/fixed_condition_compare.py`, `outputs/fixed_condition_geant4/conditions.csv`)
can be re-run with a third `--checkpoint` argument for the new baseline, at no extra
engineering cost, extending the existing extrapolation-stress-test comparison
(`outputs/fixed_condition_compare_combined/`) to three models instead of two.

## 8. Open design questions / risks (deliberately not resolved here)

- **Can a single flow learn the longitudinal shower profile implicitly**, without an
  explicit start-depth signal or separate global-profile conditioning? This is the
  actual scientific question this baseline exists to answer -- if it clearly
  underperforms the hierarchical model on `start_depth_total_variation` specifically,
  that is direct evidence the explicit hierarchy earns its complexity. If it performs
  comparably, that is evidence the hierarchy is not necessary in its current form.
- The exact conditioning-injection mechanism (concatenation vs. FiLM vs. cross-attention)
  is not fixed by this proposal and should be decided empirically during a short probe,
  consistent with this project's established discipline (measure before committing --
  the same discipline that caught the cell-stage OOM and the 4-day unbounded-pilot
  miscalculation earlier in this project).
- This project's own persistent, unresolved response-mean-bias issue (~23%, unchanged
  across three training runs at increasing scale -- `analysis.md` §5/§10) may or may not
  also appear in a single-stage model; if it does, that would be evidence the bias is a
  property of the loss/data (e.g. the `lambda_share_ce` rescaling, or the response-target
  encoding itself), not of the specific hierarchical architecture -- a genuinely useful
  diagnostic either way.

## 9. Success criteria

This baseline is informative regardless of outcome:
- If it matches or beats the hierarchical model on the same gates at the same scale: the
  extra architectural complexity (start-depth classifier + separate profile flow) is not
  earning its cost, and future work should simplify.
- If it clearly underperforms, especially on `start_depth_total_variation` and the
  response-bias/resolution gates: positive evidence the explicit hierarchy is doing real
  work, strengthening confidence in the current design.
- Either way, it is a real, cited, externally-motivated data point currently missing
  from this project's own gate table (`FINAL_QA_REPORT.md`).

## 10. Full citation list

- Wojnar, M. *Even Faster Simulations with Flow Matching: A Study of Zero Degree
  Calorimeter Responses.* arXiv:2507.18811, 2025. https://arxiv.org/abs/2507.18811 --
  code: https://github.com/m-wojnar/faster_zdc
- Majerz, E., Dzwinel, W., Kitowski, J. *Inverse Autoregressive Flows for Zero Degree
  Calorimeter fast simulation.* arXiv:2512.20346. https://arxiv.org/abs/2512.20346
- Krause, C., Shih, D. *CaloFlow: Fast and Accurate Generation of Calorimeter Showers
  with Normalizing Flows.* arXiv:2106.05285. https://arxiv.org/abs/2106.05285
- Krause, C., Shih, D. *CaloFlow II: Even Faster and Still Accurate Generation of
  Calorimeter Showers with Normalizing Flows.* arXiv:2110.11377.
  https://arxiv.org/abs/2110.11377
- *L2LFlows: Generating High-Fidelity 3D Calorimeter Images.* arXiv:2302.11594.
  https://arxiv.org/abs/2302.11594
- Paganini, M., de Oliveira, L., Nachman, B. *CaloGAN: Simulating 3D High Energy
  Particle Showers in Multi-Layer Electromagnetic Calorimeters with Generative
  Adversarial Networks.*
- *CaloChallenge 2022: A Community Challenge for Fast Calorimeter Simulation.*
  arXiv:2410.21611. https://arxiv.org/abs/2410.21611
- This project's own prior documentation, cited throughout: `analysis.md`,
  `FINAL_QA_REPORT.md`, `LIMITATIONS.md`, `outputs/cost_ledger.md`.
