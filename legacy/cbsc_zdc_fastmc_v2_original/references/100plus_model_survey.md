# HEP Fast Monte Carlo / Detector-Surrogate Research Log

**Date:** 2026-07-22  
**Primary project:** single-neutron ZDC FastMC  
**Raw per-event condition contract:** incident four-momentum only, `p4 = [E, px, py, pz]`  
**Catalogue size:** **160 separately named or separately trained/evaluated model instances**, spanning **87 family labels** and more than 80 primary/official sources.

> **Counting rule.** “Model instance” means either (a) a separately named published system, (b) a materially different published architecture/sampling variant such as teacher versus distilled student or full-space versus latent diffusion, or (c) a separately trained and officially evaluated CaloChallenge submission for a different dataset/particle. It does **not** mean that HEP contains 160 fundamentally unrelated architecture ideas. The CaloChallenge alone received 50 submitted sample sets from 31 submissions, so dataset-specific instances are scientifically real but share families. [S001–S003]

---

## 1. Executive conclusions

1. **There is no universal best FastMC architecture.** The largest common benchmark found rankings that change by dataset, physical observable, learned classifier, speed and model size. No submitted model was indistinguishable from Geant4 under every test. [S001–S005]

2. **The most reliable pattern is hierarchical generation**, not a specific neural family:
   - zero/no-response or interaction class;
   - total response;
   - detector/layer energy budgets;
   - occupancy or point count;
   - local spatial allocation.

   CaloFlow, iCaloFlow, L2LFlows, CaloDREAM, CaloClouds3, CaloHadronic, AllShowers and production systems repeatedly use some version of this decomposition. [S024–S028, S036, S044, S050–S051]

3. **Diffusion and score models are often among the most faithful**, but raw iterative sampling is expensive. Distillation, consistency models, latent generation, fewer integration steps and smaller backbones recover speed, usually with measurable quality loss. [S005, S035, S037–S039, S053–S054, S064]

4. **Normalizing flows offer stable objectives and strong fidelity**, but direct high-dimensional flows can be memory-intensive or serial. Layer factorization, convolutional coupling, latent compression and teacher–student distillation are the successful scaling techniques. [S024–S030]

5. **GANs remain exceptionally fast**, but the literature repeatedly encounters mode collapse, weak conditioning, missing high-response tails and classifier-visible artifacts. Auxiliary regressors, diversity losses, postprocessing and mixture routing help, but they do not make adversarial loss a sufficient validation metric. [S008–S013, S022–S023, S063, S065]

6. **Graphs are useful only when the graph is correct and demonstrably helpful.** CaloGraph and geometry-aware models support graph/geometry conditioning, but a no-graph or geometry-token baseline is mandatory. The user project's 952 isolated ganged nodes are an example of graph inductive bias making a model worse, not better. [S040, S056–S057, P001]

7. **Sparse point clouds and token models are serious alternatives** for high-granularity detectors. They avoid wasting computation on empty cells but introduce point-count, ordering/tokenization, duplicate-hit and variable-length validation problems. [S033–S036, S041, S052, S058–S060]

8. **Mixtures of experts are particularly relevant to ZDC response heterogeneity.** ExpertSim explicitly routes heterogeneous ZDC cases to specialized generators. This directly addresses the user's observed combination of zero/low response, normal showers, late showers and rare pathological tails. [S061]

9. **Production systems are hybrid and conservative.** AtlFast3, Lamarr, Delphes, point libraries and classical parameterizations show that a useful system may route among calibrated approximations rather than use one end-to-end neural generator everywhere. [S020–S021, S067, S081–S082]

10. **Training loss is not the decision variable.** A FastMC model is improving only when **free-running conditional distributions** improve beyond statistical uncertainty without violating protected physics metrics. The user's HGF run is a direct counterexample: cell validation loss improved while ECAL/late-HCAL closure did not. [P002]

---

## 2. Exact input contract for the user model

### 2.1 Sole raw condition

The only event-level raw condition is:

```text
p4_raw = [E, px, py, pz]
```

Everything else must be either:

- a deterministic feature derived from `p4_raw`; or
- static detector metadata/configuration shared by all events.

Static geometry arrays, channel masks, cell centers, areas, layers, subdetector labels and graph edges are **not additional event raw data**. They are part of the frozen detector definition.

### 2.2 Allowed deterministic features

For neutron mass `m_n`, the preprocessing version may deterministically calculate:

```text
p        = sqrt(px^2 + py^2 + pz^2)
kinetic  = E - m_n
ux,uy,uz = (px,py,pz) / p
theta    = atan2(sqrt(px^2 + py^2), pz)
phi      = atan2(py, px)
slope_x  = px / pz
slope_y  = py / pz
beta     = p / E
gamma    = E / m_n
mass_shell_residual = E^2 - p^2 - m_n^2
logE     = log(E / E0)
```

For a single fixed-mass particle, several of these are algebraically redundant. The recommended initial encoder input is:

```text
[logE, ux, uy, uz]
```

or

```text
[logE, px/pz, py/pz]
```

with raw `p4` retained as the public API and mass-shell quantities retained for QA. Add redundant derived features only through an ablation proving that they improve held-out conditional physics.

### 2.3 Entry point and the fixed-vertex condition

If the production vertex `(x0,y0,z0)` and detector plane `z=z_det` are fixed, the straight-line intercept is deterministic:

```text
x_entry = x0 + (z_det - z0) * px/pz
y_entry = y0 + (z_det - z0) * py/pz
```

This is allowed as derived data. It does **not** create independent entry-position support. In the current dataset, the fixed gun and angular range only cover a central region; a model conditioned solely on p4 cannot truthfully claim arbitrary edge entry unless new Geant4 events vary the vertex or otherwise create independent entry positions. [P002]

### 2.4 Consequence for literature comparison

A paper is marked “p4-compatible” when its event condition can be reconstructed from energy and direction for one fixed particle species and detector geometry. Models that vary particle type, detector geometry, material, impact point independently, track path or event multiplicity need additional raw conditions and are not direct templates for the current contract.

---

## 3. What the 100+ model study says works

### 3.1 Strong recurring design choices

| Design choice | Why it works | Main risk |
|---|---|---|
| Explicit zero/no-response component | Prevents a dense model from smearing probability into physically empty events/layers. | A miscalibrated hurdle classifier corrupts all downstream stages. |
| Bounded or contract-correct total-response codec | Removes impossible output support before training. | The bound must match raw deposition versus calibrated/digitized target semantics. |
| Separate total/layer profile from cell texture | Makes global calibration and local morphology independently diagnosable. | Independently sampled stages can destroy correlations unless they share a latent/event state. |
| Exact energy-budget normalization | Guarantees nonnegative energy closure. | Can hide a biased upstream budget; exact sums are necessary, not sufficient. |
| Geometry-aware representation | Helps irregular cells, ganging and cross-layer overlap. | Incorrect edges or mappings inject systematic bias. |
| Sparse point/token output | Efficient for high-dimensional mostly-zero showers. | Count, token order and low-energy tail modeling become bottlenecks. |
| Teacher–student/distillation | Converts a slow high-fidelity model into a faster sampler. | Student can lose modes/tails while matching teacher loss. |
| Latent generation | Major speed/memory gain. | Decoder bottleneck can erase information permanently. |
| Mixture/router | Handles response regimes that one smooth density averages together. | Router mistakes and expert undertraining add new failure modes. |
| Physics/postprocessing calibration | Can correct known global response defects cheaply. | May overfit a marginal while joint morphology remains wrong. |
| Downstream reconstruction validation | Tests whether the surrogate is useful for physics, not just visually plausible. | Reconstruction model must be frozen before comparing simulators. |
| Hybrid production routing | Uses the cheapest adequate model in each regime. | Integration and calibration complexity. |

### 3.2 Recurring failure modes

- Unbounded transformations producing rare catastrophic energies.
- Dense softmax profiles that cannot represent exactly inactive layers.
- Training on truth masks but sampling on generated masks.
- Teacher-forced improvement with free-running degradation.
- Excellent pooled medians hiding wrong means, resolutions or tails.
- GAN diversity collapse.
- VAE latent-prior mismatch.
- Diffusion/flow matching step count selected by loss rather than physics.
- Graph edges based on readout index instead of physical adjacency.
- Per-cell marginal distances dominated by zeros.
- Random projections or weak classifiers falsely suggesting closure.
- Fixed-condition evaluation that matches Geant4 only by energy.
- Speed numbers compared across different hardware, batch size, precision and preprocessing.
- “More generated events” reducing Monte Carlo noise but not surrogate bias. [S001, S004–S007, S085, P001–P002]

---

## 4. Catalogue of 160 FastMC / detector-surrogate model instances

The result/lesson column reports the paper or benchmark claim conservatively. Speed numbers are **not directly comparable** unless hardware, precision, batch size, preprocessing and output format match.

### Catalogue entries 1–35

| # | Model instance | Family | Detector/task | How it works | Reported result / lesson | p4-only relevance | Sources |
|---:|---|---|---|---|---|---|---|
| 1 | GFLASH parameterised shower model | Classical parameterisation | EM calorimeter showers | Analytic/parameterized longitudinal and lateral shower profiles inside Geant4. | Very fast classical reference; fidelity depends on tuning and represented shower class. | Compatible when detector/material configuration is fixed; typically needs particle type, energy and direction. | [S081], [S049] |
| 2 | FastCaloSim | Classical/parametric | ATLAS calorimeter | Parameterized shower shapes and response derived from detailed simulation. | Production precedent: direct physics parameterisation remains competitive where calibrated and well segmented. | Energy/direction from p4 are usable; production implementations also need particle type and detector-region information. | [S020] |
| 3 | FastCaloSim V2 | Classical/parametric | ATLAS calorimeter | Modernized parameterized calorimeter response used inside AtlFast3. | Chosen as one branch of a production hybrid rather than forcing one model over the full phase space. | p4-compatible only within a fixed particle species/geometry or with extra categorical conditions. | [S020] |
| 4 | FastCaloGAN | GAN/production component | ATLAS calorimeter | GAN shower generator with ATLAS-specific conditioning and calibration. | Deployed as a component selected in regions where it offers a useful speed–fidelity compromise. | Incident p4 supplies energy/direction; impact position/particle class must be fixed or encoded. | [S020], [S019] |
| 5 | AtlFast-II | Production fast simulation | ATLAS detector | Fast tracking plus parameterized calorimeter response. | Demonstrates system-level integration is as important as the shower generator. | Not a p4-only single-shower model; full event context and detector navigation are used. | [S020] |
| 6 | AtlFast3 hybrid | Hybrid production system | ATLAS detector | Chooses among FastCaloSim V2, FastCaloGAN and other approximations by particle/region. | Strong lesson: production systems may route between models instead of seeking one universal generator. | Would require a router; p4 alone is sufficient only if particle type and detector region are otherwise fixed. | [S020] |
| 7 | Delphes 3 | Parameterized full detector | Generic collider detector | Object-level efficiencies, resolutions and reconstructed-object parameterizations. | Extremely fast and widely used, but intentionally less detailed than cell-level Geant4 surrogates. | Not a cell-level p4-to-shower generator. | [S021] |
| 8 | Lamarr integrated pipeline | Modular DGM/GBDT production system | LHCb detector and reconstruction | Pipeline of learned detector-response and reconstruction parameterizations. | Reported good agreement on key reconstructed quantities and ~100x simulation-phase speedup. | Not p4-only: uses track/event/reconstruction context. | [S067] |
| 9 | CaloML VAE | VAE | LHCb calorimeter | Conditional latent calorimeter generator. | Review reports large acceleration; must be judged on reconstructed-energy and shower-shape closure. | Generally p4-compatible for fixed species/geometry. | [S068] |
| 10 | CaloML VAEWithProfiles | Hierarchical VAE | LHCb calorimeter | Adds explicit shower-profile information/constraints to a VAE. | Illustrates the recurring benefit of separating global profiles from local texture. | Generally p4-compatible for fixed species/geometry. | [S068] |
| 11 | LHCb calorimeter point library | Lookup/library | LHCb calorimeter | Reuses pre-simulated shower points/templates with transformations. | Non-neural example showing that strong indexing/interpolation baselines must be included. | Uses p4-derived energy/direction but may require impact/local geometry coordinates. | [S082] |
| 12 | SQuIRELS | Schrödinger bridge/refinement | Calorimeter | Learns a stochastic bridge from fast GFLASH-like samples to Geant4-like samples. | Promising when an existing fast simulator captures coarse physics and ML only learns the correction. | Not strictly p4-only because the coarse simulator output is also an input. | [S049] |
| 13 | CALPAGAN | Conditional GAN/refinement | Calorimeter | pix2pix-style transformation of one shower representation into a higher-fidelity one. | Refinement can be easier than unconditional generation, but requires a base simulation input. | Not p4-only; consumes a coarse shower/image. | [S023] |
| 14 | SuperCalo pipeline | Flow super-resolution | High-granularity calorimeter | Generates fine cells conditioned on coarse calorimeter cells. | Useful decomposition: solve coarse/global response first, then stochastic super-resolution. | Not p4-only unless the coarse shower is generated internally. | [S032] |
| 15 | ParaFlow | Conditional normalizing flow | Variable-material calorimeter | Conditions on detector/material parameters and incident particle variables. | Shows extra detector-configuration conditions are required when geometry/material is not fixed. | p4-only is sufficient only for one frozen detector/material configuration. | [S048] |
| 16 | CaloDiffusion — CaloChallenge D1 photon | Diffusion | CaloChallenge D1 photon | Official separately submitted and evaluated sample/model instance for the named CaloChallenge dataset. | The benchmark found no universal winner: rankings change by observable, classifier, dataset, speed and model size; every submitted sample remained identifiable in at least some tests. | The public challenge conditions primarily on incident energy. For a fixed neutron detector, p4 contains this and direction; independent position effects require support in the data. | [S001], [S002], [S003], [S039] |
| 17 | CaloINN — CaloChallenge D1 photon | Normalizing flow | CaloChallenge D1 photon | Official separately submitted and evaluated sample/model instance for the named CaloChallenge dataset. | The benchmark found no universal winner: rankings change by observable, classifier, dataset, speed and model size; every submitted sample remained identifiable in at least some tests. | The public challenge conditions primarily on incident energy. For a fixed neutron detector, p4 contains this and direction; independent position effects require support in the data. | [S001], [S002], [S003], [S030] |
| 18 | Calo-VQ — CaloChallenge D1 photon | VQ/token model | CaloChallenge D1 photon | Official separately submitted and evaluated sample/model instance for the named CaloChallenge dataset. | The benchmark found no universal winner: rankings change by observable, classifier, dataset, speed and model size; every submitted sample remained identifiable in at least some tests. | The public challenge conditions primarily on incident energy. For a fixed neutron detector, p4 contains this and direction; independent position effects require support in the data. | [S001], [S002], [S003], [S041] |
| 19 | CaloScore — CaloChallenge D1 photon | Score diffusion | CaloChallenge D1 photon | Official separately submitted and evaluated sample/model instance for the named CaloChallenge dataset. | The benchmark found no universal winner: rankings change by observable, classifier, dataset, speed and model size; every submitted sample remained identifiable in at least some tests. | The public challenge conditions primarily on incident energy. For a fixed neutron detector, p4 contains this and direction; independent position effects require support in the data. | [S001], [S002], [S003], [S037] |
| 20 | CaloScore distilled — CaloChallenge D1 photon | Distilled score model | CaloChallenge D1 photon | Official separately submitted and evaluated sample/model instance for the named CaloChallenge dataset. | The benchmark found no universal winner: rankings change by observable, classifier, dataset, speed and model size; every submitted sample remained identifiable in at least some tests. | The public challenge conditions primarily on incident energy. For a fixed neutron detector, p4 contains this and direction; independent position effects require support in the data. | [S001], [S002], [S003], [S038] |
| 21 | CaloScore single-shot — CaloChallenge D1 photon | Single-shot score model | CaloChallenge D1 photon | Official separately submitted and evaluated sample/model instance for the named CaloChallenge dataset. | The benchmark found no universal winner: rankings change by observable, classifier, dataset, speed and model size; every submitted sample remained identifiable in at least some tests. | The public challenge conditions primarily on incident energy. For a fixed neutron detector, p4 contains this and direction; independent position effects require support in the data. | [S001], [S002], [S003], [S038] |
| 22 | CaloFlow teacher — CaloChallenge D1 photon | Normalizing-flow teacher | CaloChallenge D1 photon | Official separately submitted and evaluated sample/model instance for the named CaloChallenge dataset. | The benchmark found no universal winner: rankings change by observable, classifier, dataset, speed and model size; every submitted sample remained identifiable in at least some tests. | The public challenge conditions primarily on incident energy. For a fixed neutron detector, p4 contains this and direction; independent position effects require support in the data. | [S001], [S002], [S003], [S025], [S026] |
| 23 | CaloFlow student — CaloChallenge D1 photon | Distilled flow student | CaloChallenge D1 photon | Official separately submitted and evaluated sample/model instance for the named CaloChallenge dataset. | The benchmark found no universal winner: rankings change by observable, classifier, dataset, speed and model size; every submitted sample remained identifiable in at least some tests. | The public challenge conditions primarily on incident energy. For a fixed neutron detector, p4 contains this and direction; independent position effects require support in the data. | [S001], [S002], [S003], [S025], [S026] |
| 24 | CaloMan — CaloChallenge D1 photon | Manifold+density | CaloChallenge D1 photon | Official separately submitted and evaluated sample/model instance for the named CaloChallenge dataset. | The benchmark found no universal winner: rankings change by observable, classifier, dataset, speed and model size; every submitted sample remained identifiable in at least some tests. | The public challenge conditions primarily on incident energy. For a fixed neutron detector, p4 contains this and direction; independent position effects require support in the data. | [S001], [S002], [S003], [S031] |
| 25 | BoloGAN — CaloChallenge D1 photon | GAN | CaloChallenge D1 photon | Official separately submitted and evaluated sample/model instance for the named CaloChallenge dataset. | The benchmark found no universal winner: rankings change by observable, classifier, dataset, speed and model size; every submitted sample remained identifiable in at least some tests. | The public challenge conditions primarily on incident energy. For a fixed neutron detector, p4 contains this and direction; independent position effects require support in the data. | [S001], [S002], [S003] |
| 26 | CaloShower2GAN — CaloChallenge D1 photon | GAN | CaloChallenge D1 photon | Official separately submitted and evaluated sample/model instance for the named CaloChallenge dataset. | The benchmark found no universal winner: rankings change by observable, classifier, dataset, speed and model size; every submitted sample remained identifiable in at least some tests. | The public challenge conditions primarily on incident energy. For a fixed neutron detector, p4 contains this and direction; independent position effects require support in the data. | [S001], [S002], [S003] |
| 27 | CaloShower3GAN — CaloChallenge D1 photon | GAN | CaloChallenge D1 photon | Official separately submitted and evaluated sample/model instance for the named CaloChallenge dataset. | The benchmark found no universal winner: rankings change by observable, classifier, dataset, speed and model size; every submitted sample remained identifiable in at least some tests. | The public challenge conditions primarily on incident energy. For a fixed neutron detector, p4 contains this and direction; independent position effects require support in the data. | [S001], [S002], [S003] |
| 28 | CaloVAE+INN — CaloChallenge D1 photon | VAE-latent flow | CaloChallenge D1 photon | Official separately submitted and evaluated sample/model instance for the named CaloChallenge dataset. | The benchmark found no universal winner: rankings change by observable, classifier, dataset, speed and model size; every submitted sample remained identifiable in at least some tests. | The public challenge conditions primarily on incident energy. For a fixed neutron detector, p4 contains this and direction; independent position effects require support in the data. | [S001], [S002], [S003], [S030] |
| 29 | CaloDiffusion — CaloChallenge D1 pion | Diffusion | CaloChallenge D1 pion | Official separately submitted and evaluated sample/model instance for the named CaloChallenge dataset. | The benchmark found no universal winner: rankings change by observable, classifier, dataset, speed and model size; every submitted sample remained identifiable in at least some tests. | The public challenge conditions primarily on incident energy. For a fixed neutron detector, p4 contains this and direction; independent position effects require support in the data. | [S001], [S002], [S003], [S039] |
| 30 | CaloINN — CaloChallenge D1 pion | Normalizing flow | CaloChallenge D1 pion | Official separately submitted and evaluated sample/model instance for the named CaloChallenge dataset. | The benchmark found no universal winner: rankings change by observable, classifier, dataset, speed and model size; every submitted sample remained identifiable in at least some tests. | The public challenge conditions primarily on incident energy. For a fixed neutron detector, p4 contains this and direction; independent position effects require support in the data. | [S001], [S002], [S003], [S030] |
| 31 | Calo-VQ — CaloChallenge D1 pion | VQ/token model | CaloChallenge D1 pion | Official separately submitted and evaluated sample/model instance for the named CaloChallenge dataset. | The benchmark found no universal winner: rankings change by observable, classifier, dataset, speed and model size; every submitted sample remained identifiable in at least some tests. | The public challenge conditions primarily on incident energy. For a fixed neutron detector, p4 contains this and direction; independent position effects require support in the data. | [S001], [S002], [S003], [S041] |
| 32 | CaloFlow teacher — CaloChallenge D1 pion | Normalizing-flow teacher | CaloChallenge D1 pion | Official separately submitted and evaluated sample/model instance for the named CaloChallenge dataset. | The benchmark found no universal winner: rankings change by observable, classifier, dataset, speed and model size; every submitted sample remained identifiable in at least some tests. | The public challenge conditions primarily on incident energy. For a fixed neutron detector, p4 contains this and direction; independent position effects require support in the data. | [S001], [S002], [S003], [S025], [S026] |
| 33 | CaloFlow student — CaloChallenge D1 pion | Distilled flow student | CaloChallenge D1 pion | Official separately submitted and evaluated sample/model instance for the named CaloChallenge dataset. | The benchmark found no universal winner: rankings change by observable, classifier, dataset, speed and model size; every submitted sample remained identifiable in at least some tests. | The public challenge conditions primarily on incident energy. For a fixed neutron detector, p4 contains this and direction; independent position effects require support in the data. | [S001], [S002], [S003], [S025], [S026] |
| 34 | CaloMan — CaloChallenge D1 pion | Manifold+density | CaloChallenge D1 pion | Official separately submitted and evaluated sample/model instance for the named CaloChallenge dataset. | The benchmark found no universal winner: rankings change by observable, classifier, dataset, speed and model size; every submitted sample remained identifiable in at least some tests. | The public challenge conditions primarily on incident energy. For a fixed neutron detector, p4 contains this and direction; independent position effects require support in the data. | [S001], [S002], [S003], [S031] |
| 35 | BoloGAN — CaloChallenge D1 pion | GAN | CaloChallenge D1 pion | Official separately submitted and evaluated sample/model instance for the named CaloChallenge dataset. | The benchmark found no universal winner: rankings change by observable, classifier, dataset, speed and model size; every submitted sample remained identifiable in at least some tests. | The public challenge conditions primarily on incident energy. For a fixed neutron detector, p4 contains this and direction; independent position effects require support in the data. | [S001], [S002], [S003] |

### Catalogue entries 36–70

| # | Model instance | Family | Detector/task | How it works | Reported result / lesson | p4-only relevance | Sources |
|---:|---|---|---|---|---|---|---|
| 36 | DNN CaloSim — CaloChallenge D1 pion | Dense neural generator | CaloChallenge D1 pion | Official separately submitted and evaluated sample/model instance for the named CaloChallenge dataset. | The benchmark found no universal winner: rankings change by observable, classifier, dataset, speed and model size; every submitted sample remained identifiable in at least some tests. | The public challenge conditions primarily on incident energy. For a fixed neutron detector, p4 contains this and direction; independent position effects require support in the data. | [S001], [S002], [S003] |
| 37 | CaloShowerGAN — CaloChallenge D1 pion | GAN | CaloChallenge D1 pion | Official separately submitted and evaluated sample/model instance for the named CaloChallenge dataset. | The benchmark found no universal winner: rankings change by observable, classifier, dataset, speed and model size; every submitted sample remained identifiable in at least some tests. | The public challenge conditions primarily on incident energy. For a fixed neutron detector, p4 contains this and direction; independent position effects require support in the data. | [S001], [S002], [S003], [S022] |
| 38 | CaloVAE+INN — CaloChallenge D1 pion | VAE-latent flow | CaloChallenge D1 pion | Official separately submitted and evaluated sample/model instance for the named CaloChallenge dataset. | The benchmark found no universal winner: rankings change by observable, classifier, dataset, speed and model size; every submitted sample remained identifiable in at least some tests. | The public challenge conditions primarily on incident energy. For a fixed neutron detector, p4 contains this and direction; independent position effects require support in the data. | [S001], [S002], [S003], [S030] |
| 39 | CaloDiffusion — CaloChallenge D2 electron | Diffusion | CaloChallenge D2 electron | Official separately submitted and evaluated sample/model instance for the named CaloChallenge dataset. | The benchmark found no universal winner: rankings change by observable, classifier, dataset, speed and model size; every submitted sample remained identifiable in at least some tests. | The public challenge conditions primarily on incident energy. For a fixed neutron detector, p4 contains this and direction; independent position effects require support in the data. | [S001], [S002], [S039] |
| 40 | Convolutional L2LFlows — CaloChallenge D2 electron | Convolutional flow | CaloChallenge D2 electron | Official separately submitted and evaluated sample/model instance for the named CaloChallenge dataset. | The benchmark found no universal winner: rankings change by observable, classifier, dataset, speed and model size; every submitted sample remained identifiable in at least some tests. | The public challenge conditions primarily on incident energy. For a fixed neutron detector, p4 contains this and direction; independent position effects require support in the data. | [S001], [S002], [S029] |
| 41 | CaloINN — CaloChallenge D2 electron | Normalizing flow | CaloChallenge D2 electron | Official separately submitted and evaluated sample/model instance for the named CaloChallenge dataset. | The benchmark found no universal winner: rankings change by observable, classifier, dataset, speed and model size; every submitted sample remained identifiable in at least some tests. | The public challenge conditions primarily on incident energy. For a fixed neutron detector, p4 contains this and direction; independent position effects require support in the data. | [S001], [S002], [S030] |
| 42 | MDMA — CaloChallenge D2 electron | Attentive point-cloud GAN | CaloChallenge D2 electron | Official separately submitted and evaluated sample/model instance for the named CaloChallenge dataset. | The benchmark found no universal winner: rankings change by observable, classifier, dataset, speed and model size; every submitted sample remained identifiable in at least some tests. | The public challenge conditions primarily on incident energy. For a fixed neutron detector, p4 contains this and direction; independent position effects require support in the data. | [S001], [S002], [S058] |
| 43 | Calo-VQ — CaloChallenge D2 electron | VQ/token model | CaloChallenge D2 electron | Official separately submitted and evaluated sample/model instance for the named CaloChallenge dataset. | The benchmark found no universal winner: rankings change by observable, classifier, dataset, speed and model size; every submitted sample remained identifiable in at least some tests. | The public challenge conditions primarily on incident energy. For a fixed neutron detector, p4 contains this and direction; independent position effects require support in the data. | [S001], [S002], [S041] |
| 44 | CaloScore — CaloChallenge D2 electron | Score diffusion | CaloChallenge D2 electron | Official separately submitted and evaluated sample/model instance for the named CaloChallenge dataset. | The benchmark found no universal winner: rankings change by observable, classifier, dataset, speed and model size; every submitted sample remained identifiable in at least some tests. | The public challenge conditions primarily on incident energy. For a fixed neutron detector, p4 contains this and direction; independent position effects require support in the data. | [S001], [S002], [S037] |
| 45 | CaloScore distilled — CaloChallenge D2 electron | Distilled score model | CaloChallenge D2 electron | Official separately submitted and evaluated sample/model instance for the named CaloChallenge dataset. | The benchmark found no universal winner: rankings change by observable, classifier, dataset, speed and model size; every submitted sample remained identifiable in at least some tests. | The public challenge conditions primarily on incident energy. For a fixed neutron detector, p4 contains this and direction; independent position effects require support in the data. | [S001], [S002], [S038] |
| 46 | CaloScore single-shot — CaloChallenge D2 electron | Single-shot score model | CaloChallenge D2 electron | Official separately submitted and evaluated sample/model instance for the named CaloChallenge dataset. | The benchmark found no universal winner: rankings change by observable, classifier, dataset, speed and model size; every submitted sample remained identifiable in at least some tests. | The public challenge conditions primarily on incident energy. For a fixed neutron detector, p4 contains this and direction; independent position effects require support in the data. | [S001], [S002], [S038] |
| 47 | iCaloFlow teacher — CaloChallenge D2 electron | Layer-inductive flow teacher | CaloChallenge D2 electron | Official separately submitted and evaluated sample/model instance for the named CaloChallenge dataset. | The benchmark found no universal winner: rankings change by observable, classifier, dataset, speed and model size; every submitted sample remained identifiable in at least some tests. | The public challenge conditions primarily on incident energy. For a fixed neutron detector, p4 contains this and direction; independent position effects require support in the data. | [S001], [S002], [S027] |
| 48 | iCaloFlow student — CaloChallenge D2 electron | Distilled layer-inductive flow | CaloChallenge D2 electron | Official separately submitted and evaluated sample/model instance for the named CaloChallenge dataset. | The benchmark found no universal winner: rankings change by observable, classifier, dataset, speed and model size; every submitted sample remained identifiable in at least some tests. | The public challenge conditions primarily on incident energy. For a fixed neutron detector, p4 contains this and direction; independent position effects require support in the data. | [S001], [S002], [S027] |
| 49 | SuperCalo — CaloChallenge D2 electron | Flow super-resolution | CaloChallenge D2 electron | Official separately submitted and evaluated sample/model instance for the named CaloChallenge dataset. | The benchmark found no universal winner: rankings change by observable, classifier, dataset, speed and model size; every submitted sample remained identifiable in at least some tests. | The public challenge conditions primarily on incident energy. For a fixed neutron detector, p4 contains this and direction; independent position effects require support in the data. | [S001], [S002], [S032] |
| 50 | DeepTree — CaloChallenge D2 electron | Tree point-cloud GAN | CaloChallenge D2 electron | Official separately submitted and evaluated sample/model instance for the named CaloChallenge dataset. | The benchmark found no universal winner: rankings change by observable, classifier, dataset, speed and model size; every submitted sample remained identifiable in at least some tests. | The public challenge conditions primarily on incident energy. For a fixed neutron detector, p4 contains this and direction; independent position effects require support in the data. | [S001], [S002], [S059] |
| 51 | CaloPointFlow — CaloChallenge D2 electron | Point-cloud flow | CaloChallenge D2 electron | Official separately submitted and evaluated sample/model instance for the named CaloChallenge dataset. | The benchmark found no universal winner: rankings change by observable, classifier, dataset, speed and model size; every submitted sample remained identifiable in at least some tests. | The public challenge conditions primarily on incident energy. For a fixed neutron detector, p4 contains this and direction; independent position effects require support in the data. | [S001], [S002], [S033] |
| 52 | CaloVAE+INN — CaloChallenge D2 electron | VAE-latent flow | CaloChallenge D2 electron | Official separately submitted and evaluated sample/model instance for the named CaloChallenge dataset. | The benchmark found no universal winner: rankings change by observable, classifier, dataset, speed and model size; every submitted sample remained identifiable in at least some tests. | The public challenge conditions primarily on incident energy. For a fixed neutron detector, p4 contains this and direction; independent position effects require support in the data. | [S001], [S002], [S030] |
| 53 | CaloDiffusion — CaloChallenge D3 electron | Diffusion | CaloChallenge D3 electron | Official separately submitted and evaluated sample/model instance for the named CaloChallenge dataset. | The benchmark found no universal winner: rankings change by observable, classifier, dataset, speed and model size; every submitted sample remained identifiable in at least some tests. | The public challenge conditions primarily on incident energy. For a fixed neutron detector, p4 contains this and direction; independent position effects require support in the data. | [S001], [S002], [S039] |
| 54 | L2LFlows MAF — CaloChallenge D3 electron | Layerwise autoregressive flow | CaloChallenge D3 electron | Official separately submitted and evaluated sample/model instance for the named CaloChallenge dataset. | The benchmark found no universal winner: rankings change by observable, classifier, dataset, speed and model size; every submitted sample remained identifiable in at least some tests. | The public challenge conditions primarily on incident energy. For a fixed neutron detector, p4 contains this and direction; independent position effects require support in the data. | [S001], [S002], [S028] |
| 55 | Convolutional L2LFlows — CaloChallenge D3 electron | Convolutional flow | CaloChallenge D3 electron | Official separately submitted and evaluated sample/model instance for the named CaloChallenge dataset. | The benchmark found no universal winner: rankings change by observable, classifier, dataset, speed and model size; every submitted sample remained identifiable in at least some tests. | The public challenge conditions primarily on incident energy. For a fixed neutron detector, p4 contains this and direction; independent position effects require support in the data. | [S001], [S002], [S029] |
| 56 | MDMA — CaloChallenge D3 electron | Attentive point-cloud GAN | CaloChallenge D3 electron | Official separately submitted and evaluated sample/model instance for the named CaloChallenge dataset. | The benchmark found no universal winner: rankings change by observable, classifier, dataset, speed and model size; every submitted sample remained identifiable in at least some tests. | The public challenge conditions primarily on incident energy. For a fixed neutron detector, p4 contains this and direction; independent position effects require support in the data. | [S001], [S002], [S058] |
| 57 | CaloClouds — CaloChallenge D3 electron | Point-cloud diffusion | CaloChallenge D3 electron | Official separately submitted and evaluated sample/model instance for the named CaloChallenge dataset. | The benchmark found no universal winner: rankings change by observable, classifier, dataset, speed and model size; every submitted sample remained identifiable in at least some tests. | The public challenge conditions primarily on incident energy. For a fixed neutron detector, p4 contains this and direction; independent position effects require support in the data. | [S001], [S002], [S034] |
| 58 | Calo-VQ — CaloChallenge D3 electron | VQ/token model | CaloChallenge D3 electron | Official separately submitted and evaluated sample/model instance for the named CaloChallenge dataset. | The benchmark found no universal winner: rankings change by observable, classifier, dataset, speed and model size; every submitted sample remained identifiable in at least some tests. | The public challenge conditions primarily on incident energy. For a fixed neutron detector, p4 contains this and direction; independent position effects require support in the data. | [S001], [S002], [S041] |
| 59 | CaloScore distilled — CaloChallenge D3 electron | Distilled score model | CaloChallenge D3 electron | Official separately submitted and evaluated sample/model instance for the named CaloChallenge dataset. | The benchmark found no universal winner: rankings change by observable, classifier, dataset, speed and model size; every submitted sample remained identifiable in at least some tests. | The public challenge conditions primarily on incident energy. For a fixed neutron detector, p4 contains this and direction; independent position effects require support in the data. | [S001], [S002], [S038] |
| 60 | CaloScore single-shot — CaloChallenge D3 electron | Single-shot score model | CaloChallenge D3 electron | Official separately submitted and evaluated sample/model instance for the named CaloChallenge dataset. | The benchmark found no universal winner: rankings change by observable, classifier, dataset, speed and model size; every submitted sample remained identifiable in at least some tests. | The public challenge conditions primarily on incident energy. For a fixed neutron detector, p4 contains this and direction; independent position effects require support in the data. | [S001], [S002], [S038] |
| 61 | iCaloFlow teacher — CaloChallenge D3 electron | Layer-inductive flow teacher | CaloChallenge D3 electron | Official separately submitted and evaluated sample/model instance for the named CaloChallenge dataset. | The benchmark found no universal winner: rankings change by observable, classifier, dataset, speed and model size; every submitted sample remained identifiable in at least some tests. | The public challenge conditions primarily on incident energy. For a fixed neutron detector, p4 contains this and direction; independent position effects require support in the data. | [S001], [S002], [S027] |
| 62 | iCaloFlow student — CaloChallenge D3 electron | Distilled layer-inductive flow | CaloChallenge D3 electron | Official separately submitted and evaluated sample/model instance for the named CaloChallenge dataset. | The benchmark found no universal winner: rankings change by observable, classifier, dataset, speed and model size; every submitted sample remained identifiable in at least some tests. | The public challenge conditions primarily on incident energy. For a fixed neutron detector, p4 contains this and direction; independent position effects require support in the data. | [S001], [S002], [S027] |
| 63 | GEANT4 Transformer — CaloChallenge D3 electron | Transformer generator | CaloChallenge D3 electron | Official separately submitted and evaluated sample/model instance for the named CaloChallenge dataset. | The benchmark found no universal winner: rankings change by observable, classifier, dataset, speed and model size; every submitted sample remained identifiable in at least some tests. | The public challenge conditions primarily on incident energy. For a fixed neutron detector, p4 contains this and direction; independent position effects require support in the data. | [S001], [S002] |
| 64 | CaloPointFlow — CaloChallenge D3 electron | Point-cloud flow | CaloChallenge D3 electron | Official separately submitted and evaluated sample/model instance for the named CaloChallenge dataset. | The benchmark found no universal winner: rankings change by observable, classifier, dataset, speed and model size; every submitted sample remained identifiable in at least some tests. | The public challenge conditions primarily on incident energy. For a fixed neutron detector, p4 contains this and direction; independent position effects require support in the data. | [S001], [S002], [S033] |
| 65 | CaloVAE+INN — CaloChallenge D3 electron | VAE-latent flow | CaloChallenge D3 electron | Official separately submitted and evaluated sample/model instance for the named CaloChallenge dataset. | The benchmark found no universal winner: rankings change by observable, classifier, dataset, speed and model size; every submitted sample remained identifiable in at least some tests. | The public challenge conditions primarily on incident energy. For a fixed neutron detector, p4 contains this and direction; independent position effects require support in the data. | [S001], [S002], [S030] |
| 66 | Early PRL calorimeter GAN | GAN | Multilayer EM calorimeter | Energy-conditioned 3D shower GAN. | Demonstrated feasibility of large speedups; later work exposed classifier-visible artifacts and mode/shape limitations. | p4-compatible for fixed particle species and geometry. | [S009] |
| 67 | CaloGAN positron instance | GAN | Multilayer calorimeter | Particle/energy-conditioned 3-stream GAN. | Fast but later classifier tests showed GAN samples can be easily distinguishable. | p4-compatible; particle species is fixed in this instance. | [S008], [S024] |
| 68 | CaloGAN photon instance | GAN | Multilayer calorimeter | Photon-conditioned 3-stream GAN. | Large speedup; fidelity depends strongly on shower observable and tails. | p4-compatible for fixed photon species. | [S008] |
| 69 | CaloGAN charged-pion instance | GAN | Multilayer calorimeter | Hadron-conditioned 3-stream GAN. | Harder multimodal shower distribution than EM case; requires explicit coverage checks. | p4-compatible for fixed pion species. | [S008] |
| 70 | Attribute-conditioned CaloGAN | GAN | Calorimeter | Auxiliary objectives enforce continuous physical attributes. | Shows that passing a condition is not enough: the generator needs condition-sensitive losses/evaluation. | Directly relevant to p4 conditioning. | [S010] |

### Catalogue entries 71–105

| # | Model instance | Family | Detector/task | How it works | Reported result / lesson | p4-only relevance | Sources |
|---:|---|---|---|---|---|---|---|
| 71 | Early detector WGAN | WGAN | Detector response | Wasserstein adversarial training. | More stable adversarial objective, but critic loss still does not certify detector fidelity. | Usually p4-compatible for a fixed detector. | [S011] |
| 72 | Precise EM WGAN | WGAN | Electromagnetic calorimeter | WGAN with physics-aware conditioning/evaluation. | Improved EM fidelity; still requires tail, sparsity and joint-distribution validation. | p4-compatible for fixed species/geometry. | [S012] |
| 73 | Fast accurate detector GAN | GAN | Detector response | Conditional GAN surrogate. | Reported speed and feature-level agreement; cross-hardware speed numbers are not directly portable. | Depends on the detector task; often p4 plus local geometry. | [S013] |
| 74 | 3DGAN electron model | 3D GAN | High-granularity calorimeter | 3D convolutional generator. | Reported approximately per-observable 10% agreement and ~10^3 speed scale; deployment quality remains observable-dependent. | p4-compatible for fixed electron species. | [S014] |
| 75 | 3DGAN photon transfer model | Transfer-learning GAN | High-granularity calorimeter | Fine-tunes an existing generator to photons. | Transfer learning can reduce new-particle cost but must be checked for inherited biases. | p4 plus a fixed/known particle class. | [S014] |
| 76 | 3DGAN pi0 transfer model | Transfer-learning GAN | High-granularity calorimeter | Fine-tuned neutral-pion shower generator. | Demonstrates cross-particle transfer; multi-shower topology makes fidelity harder. | p4 alone does not encode decay topology unless the input is the post-decay particle. | [S014] |
| 77 | BIB-AE photon model | Bounded-information autoencoder | Highly granular ECAL | Autoencoder plus latent generator and auxiliary regularizers. | Captured detailed structure including low-energy effects better than simpler VAEs; latent generation remained a major issue. | p4-compatible for fixed photon geometry. | [S015] |
| 78 | BIB-AE improved latent sampler | AE + latent density | Highly granular ECAL | Improved model of the learned latent distribution. | Key lesson: reconstruction quality does not imply sample quality; prior/latent mismatch must be measured. | p4-compatible. | [S016] |
| 79 | WGAN hadron model | WGAN | Hadronic calorimeter | Adversarial hadronic-shower generator. | Hadronic response broadness makes mode coverage and late-shower tails critical. | p4-compatible for fixed hadron species. | [S017] |
| 80 | BIB-AE hadron model | Autoencoder | Hadronic calorimeter | Bounded-information AE adapted to hadronic showers. | Competitive spatial modeling but generative latent calibration remains central. | p4-compatible. | [S017] |
| 81 | Angle-conditioned BIB-AE | Conditional AE | Calorimeter with varying angle | Adds angle and other incident variables; evaluated with reconstruction. | Strong precedent for deriving direction from p4 and validating downstream quantities. | Directly p4-compatible. | [S018] |
| 82 | ATLAS photon GAN | GAN | ATLAS EM calorimeter | ATLAS detector-specific conditional generator. | Demonstrated realistic experiment-specific modeling; calibration/production integration remain separate steps. | p4-compatible within the trained detector region. | [S019] |
| 83 | Standalone CaloShowerGAN | GAN | CaloChallenge D1 | GAN with challenge-specific preprocessing and physics losses. | Fast, but benchmark rankings depend on observable and classifier. | p4 energy/direction compatible. | [S022], [S001] |
| 84 | DeepTreeGAN | Tree point-cloud GAN | Calorimeter | Hierarchical tree expansion produces sparse hits. | Natural variable-size representation; needs explicit count and duplicate/coverage checks. | p4-compatible for fixed geometry. | [S059] |
| 85 | DeepTreeGANv2 | Tree point-cloud GAN | Calorimeter | Improved tree generator and training strategy. | Refinements improve stability/fidelity but do not remove need for conditional tail tests. | p4-compatible. | [S060] |
| 86 | Geometry-aware autoregressive model | Autoregressive | Multiple calorimeter geometries | Autoregressive deposits conditioned on cell size/position. | Can adapt response to geometry; serial generation may be slow. | Needs static/per-event geometry in addition to p4 when geometry varies. | [S056] |
| 87 | GAAM unseen-geometry model | Geometry-aware autoregressive | Unseen calorimeter geometries | Explicit geometry conditioning and cross-geometry evaluation. | Reported >50% improvement over geometry-unaware baseline on several metrics. | Not p4-only if geometry is variable; compatible for a frozen geometry. | [S057] |
| 88 | Original CaloFlow | Normalizing flow | Calorimeter | Separate flow for layer energies and voxel allocation. | High fidelity and stable likelihood training; original autoregressive sampling was costly. | p4-compatible for fixed species/geometry. | [S024] |
| 89 | CaloFlow II teacher | Autoregressive flow teacher | Calorimeter | High-fidelity slow flow used as a density teacher. | Teacher quality useful, but teacher speed is not production speed. | p4-compatible. | [S025] |
| 90 | CaloFlow II student | Distilled flow | Calorimeter | IAF/student distillation from teacher density. | Reported roughly 500x faster sampling than original while preserving much fidelity. | p4-compatible. | [S025] |
| 91 | CaloFlow Challenge photon | Normalizing flow | CaloChallenge D1 photon | Challenge-specific photon flow. | Several orders faster than Geant4 with high fidelity, but still identifiable by strong tests. | p4 energy compatible. | [S026], [S001] |
| 92 | CaloFlow Challenge pion | Normalizing flow | CaloChallenge D1 pion | Challenge-specific charged-pion flow. | Shows flows can handle hadrons, though fidelity is harder than EM showers. | p4 energy compatible. | [S026], [S001] |
| 93 | iCaloFlow teacher | Layer-inductive flow | High-dimensional calorimeter | Three-flow hierarchy with layer-pair inductive structure. | Improves scaling and parameter reuse; remains sequential across layers. | p4-compatible. | [S027] |
| 94 | iCaloFlow student | Distilled layer-inductive flow | High-dimensional calorimeter | Distilled faster sampler. | Useful speed–fidelity compromise; must compare free-running accumulation across layers. | p4-compatible. | [S027] |
| 95 | L2LFlows ILD model | Layerwise normalizing flow | ILD ECAL | 30 separate flows conditioned on previous five layers. | Reported significantly improved fidelity over BIB-AE; serial layer generation is a latency cost. | p4-compatible. | [S028] |
| 96 | Convolutional L2LFlows ILD model | Convolutional flow | ILD ECAL | Coupling flows with convolution/U-Net links. | Scales to larger lateral grids; high-dimensional flow support/tails still require invariants. | p4-compatible. | [S029] |
| 97 | CaloINN direct model | Invertible flow | Lower-dimensional calorimeter | Direct invertible network in voxel space. | Strong challenge performance at manageable dimension; direct flows scale poorly with dimension. | p4-compatible. | [S030] |
| 98 | CaloVAE+INN latent model | VAE + flow | High-dimensional calorimeter | Compresses showers then learns latent density with an INN. | Faster/scalable, but decoder/latent losses can hide cell-level and sparsity defects. | p4-compatible. | [S030] |
| 99 | Standalone CaloMan | Manifold + density | Calorimeter | Learns lower-dimensional shower manifold then its probability density. | Elegant dimension reduction; poor manifold coverage can permanently remove modes. | p4-compatible. | [S031] |
| 100 | CaloPointFlow II | Point-cloud flow | Sparse calorimeter hits | Flow over unordered active deposits with count/dequantization treatment. | Avoids dense empty voxels; variable count and energy closure are central diagnostics. | p4-compatible for fixed geometry or with coordinates as outputs. | [S033] |
| 101 | CaloClouds base | Point-cloud diffusion | Highly granular ECAL | Generates Geant4-step-like point clouds independently of voxel geometry. | Geometry-independent output can be revoxelized; point count and duplicate hits require validation. | p4-compatible. | [S034] |
| 102 | CaloClouds II continuous-time | Point-cloud diffusion | Highly granular ECAL | Reduced-step continuous-time sampler. | Reported around 6x Geant4 CPU speed in the paper's setup; still iterative. | p4-compatible. | [S035] |
| 103 | CaloClouds II consistency | Consistency point-cloud model | Highly granular ECAL | One/few-step distillation of diffusion behavior. | Reported around 46x Geant4 CPU speed with quality trade-off. | p4-compatible. | [S035] |
| 104 | CaloClouds3 hybrid | Flow + diffusion point cloud | Highly granular ECAL | Combines count/global flow and point-cloud diffusion. | Reflects trend toward separate count/global and spatial models. | p4-compatible. | [S036] |
| 105 | CaloScore VP-SDE | Score diffusion | Calorimeter | Variance-preserving score model. | High fidelity but many denoising evaluations unless distilled. | p4-compatible. | [S037] |

### Catalogue entries 106–140

| # | Model instance | Family | Detector/task | How it works | Reported result / lesson | p4-only relevance | Sources |
|---:|---|---|---|---|---|---|---|
| 106 | CaloScore VE-SDE | Score diffusion | Calorimeter | Variance-exploding score model. | Different noise geometry changes optimization and tails; select through physics metrics, not loss alone. | p4-compatible. | [S037] |
| 107 | CaloScore third SDE configuration | Score diffusion | Calorimeter | Alternative score/noise configuration studied in the paper. | Architecture/noise schedule is a model-level experimental variable. | p4-compatible. | [S037] |
| 108 | CaloScore v2 full | Score diffusion | Calorimeter | Improved full-step score generator. | Independent evaluation found CaloScore among the strongest tested, while still imperfect. | p4-compatible. | [S038], [S005] |
| 109 | CaloScore v2 progressively distilled | Distilled diffusion | Calorimeter | Progressive reduction in score evaluations. | A concrete way to recover speed only after a high-fidelity teacher exists. | p4-compatible. | [S038] |
| 110 | CaloScore v2 single-shot | Single-shot score model | Calorimeter | One network evaluation after distillation. | Very fast but benchmark shows a quality loss relative to the full model on some metrics. | p4-compatible. | [S038], [S001] |
| 111 | CaloDiffusion regular-grid model | Diffusion | CaloChallenge calorimeters | 3D cylindrical convolutions exploit detector symmetries. | Among strongest evaluated models in independent studies; inference is comparatively slow. | p4-compatible. | [S039], [S005] |
| 112 | CaloDiffusion GLaM model | Diffusion + geometry latent map | Irregular calorimeter | Maps irregular geometry into a latent grid for convolutional diffusion. | Useful alternative to a graph; mapping quality and invertibility must be checked. | p4-compatible with static geometry metadata. | [S039] |
| 113 | CaloGraph | Graph diffusion | Irregular low-granularity calorimeter | Diffusion directly on graph nodes/edges. | Graph is justified only if edges are correct and it beats no-graph baselines. | p4-compatible with static detector graph. | [S040] |
| 114 | Calo-VQ end-to-end | VQ-VAE + sequence model | Calorimeter | Discrete tokenization followed by generative token model. | Fast generation; quantization can erase low-energy/tail detail. | p4-compatible. | [S041] |
| 115 | CaloQVAE | Quantum-assisted VAE | Calorimeter | VAE with quantum/RBM latent sampler. | Research proof of concept; hardware novelty does not substitute for physics closure. | p4-compatible. | [S042] |
| 116 | Calo4pQVAE | Quantum-assisted multi-particle VAE | Calorimeter | Extends quantum-assisted generation across particle classes. | Uses FPD/KPD to monitor model quality; still experimental. | p4 plus particle identity unless a neutron-only instance is trained. | [S043] |
| 117 | CaloDREAM full-space | Conditional flow matching | Calorimeter | Autoregressive layer energies plus transformer-like voxel flow. | Strong hierarchy and solver optimization; global and local stages must be jointly validated. | p4-compatible. | [S044] |
| 118 | CaloDREAM latent | Latent conditional flow matching | Calorimeter | Runs flow matching in compressed shower space. | Improves speed, risking decoder-induced bias and lost sparsity. | p4-compatible. | [S044] |
| 119 | Universal ViT regular-geometry instance | ViT generative model | Regular calorimeter | One transformer framework applied to regular layouts. | Supports cross-detector reuse; data/conditioning normalization becomes critical. | p4-compatible with geometry token/config. | [S045] |
| 120 | Universal ViT irregular/multi-detector instance | ViT generative model | Irregular/multiple calorimeters | Geometry-aware tokens enable multiple detectors. | Not p4-only if detector identity/geometry varies; fixed geometry is compatible. | Needs detector/geometry condition when multiple layouts are included. | [S045] |
| 121 | CaloDiT-2 multi-detector model | Diffusion transformer | Multiple calorimeters | Transformer diffusion with detector-aware conditioning. | Generalization is a first-class metric rather than assumed interpolation. | Needs detector identity/geometry in multi-detector mode. | [S046] |
| 122 | ViT conditional-flow-matching model | CFM transformer | High-granularity calorimeter | Shared ViT backbone trained with conditional flow matching. | Good fidelity–speed compromise; iterative step count must be tuned on physics metrics. | p4-compatible. | [S047] |
| 123 | ViT coupling-normalizing-flow model | Coupling NF transformer | High-granularity calorimeter | Same broad backbone with invertible coupling objective. | Allows controlled comparison of generative objective; likelihood does not guarantee better samples. | p4-compatible. | [S047] |
| 124 | OmniJet-alpha_C | Token transformer | Variable-length calorimeter point clouds | Tokenizes active deposits and autoregressively generates sequences. | Handles sparsity and variable length; serial token generation can dominate latency. | p4-compatible. | [S052] |
| 125 | CaloHadronic | Count flow + diffusion transformers | Hadronic ECAL/HCAL | PointCountFM plus separate ECAL/HCAL EDM-style generators. | Directly relevant decomposition for heterogeneous hadronic showers. | p4-compatible for fixed neutron species/geometry. | [S050] |
| 126 | AllShowers | Unified multi-particle flow | Multiple calorimeters/particles | One model across particles using count/global and continuous-flow components. | Tests whether a universal model can share statistics without erasing particle-specific modes. | Needs particle identity unless neutron-only; p4 alone does not determine species in general. | [S051] |
| 127 | CaloTrilogy one/few-step model | Conditional flow matching | High-granularity calorimeter | Unified global/local end-to-end one/few-step generation. | Targets removal of auxiliary networks and repeated function calls; very recent and requires independent reproduction. | p4-compatible. | [S053] |
| 128 | CaloArt CCD2 model | Diffusion transformer | CaloChallenge D2 | Large-patch x/v-prediction transformer. | Reports strong FPD/classifier metrics and ~9.71 ms single-GPU generation in its setup. | Incident-energy compatible; p4 supplies more direction information if data support it. | [S054] |
| 129 | CaloArt CCD3 model | Diffusion transformer | CaloChallenge D3 | Large patches make 40,500-voxel generation tractable. | Reports Pareto-frontier placement and ~11.14 ms single-GPU generation in its setup. | Incident-energy compatible. | [S054] |
| 130 | FPGA VAE floating-point reference | VAE | Calorimeter hardware inference | Uncompressed/float reference used before deployment compression. | Separates model-quality loss from hardware quantization loss. | p4-compatible. | [S055] |
| 131 | FPGA VAE quantized model | Quantized VAE | Calorimeter hardware inference | Quantization-aware training and FPGA deployment. | Potential sub-ms deployment; physics metrics must be repeated after quantization. | p4-compatible. | [S055] |
| 132 | MDMA standalone | Mean-field attentive GAN | Sparse calorimeter point cloud | Attention-based point-cloud adversarial generation. | Avoids fixed voxel assumptions; GAN coverage and count distributions remain vulnerable. | p4-compatible. | [S058] |
| 133 | ALICE ZDC conditional VAE | VAE | ALICE neutron ZDC | Classifier for zero response followed by conditional VAE. | VAE Wasserstein 6.45 in the paper's five-channel metric; smoother but blurrier responses. | Original study uses multiple particle attributes; p4-only is possible only if omitted variables are fixed/derived. | [S063] |
| 134 | ALICE ZDC conditional DC-GAN | GAN | ALICE neutron ZDC | Conditional DC-GAN after zero-response classifier. | Raw GAN failed to cover high responses well; paper reports Wasserstein 8.25. | Same p4 caveat as above. | [S063] |
| 135 | ALICE ZDC GAN + auxiliary regressor | GAN + physics regressor | ALICE neutron ZDC | Adds shower-center regressor loss. | Improved spatial placement but did not fully fix distribution coverage; Wasserstein 7.20. | p4-compatible only under fixed non-p4 attributes. | [S063] |
| 136 | ALICE ZDC GAN + postprocessing | GAN + calibration | ALICE neutron ZDC | Physics-motivated response postprocessing. | Large metric gain; reported Wasserstein 5.71, showing post-hoc calibration can dominate architecture differences. | p4-compatible; postprocessing must be frozen and validated. | [S063] |
| 137 | ALICE ZDC GAN + regressor + postprocessing | GAN + calibration | ALICE neutron ZDC | Combines auxiliary spatial loss and response correction. | Best of that study at Wasserstein 5.16 and ~100x speedup. | p4-compatible only on supported condition manifold. | [S063] |
| 138 | ALICE ZDC pixel diffusion | Diffusion | ALICE neutron ZDC | Diffusion directly in detector-image space. | Reported best fidelity among that study's baselines but ~109 ms/sample in later comparison. | Original condition vector contains more than p4; neutron-only fixed setup can be adapted. | [S062], [S064] |
| 139 | ALICE ZDC latent diffusion | Latent diffusion | ALICE neutron ZDC | Autoencoder plus diffusion in latent space. | Faster than pixel diffusion with a quality trade-off. | p4-compatible under fixed omitted variables. | [S062] |
| 140 | ALICE ZDC full flow matching | Flow matching | ALICE neutron/proton ZDC | Small CFM model sampled with ~11 Euler steps. | For ZN: Wasserstein 1.27, MAE 16.99, 0.46 ms/sample at batch 256 in the paper's setup. | Original setup uses a particle attribute vector; p4-only requires fixed/derived other attributes. | [S064] |

### Catalogue entries 141–160

| # | Model instance | Family | Detector/task | How it works | Reported result / lesson | p4-only relevance | Sources |
|---:|---|---|---|---|---|---|---|
| 141 | ALICE ZDC latent flow matching | Latent flow matching | ALICE neutron/proton ZDC | CFM in compressed detector-response space. | For ZN: 0.026 ms/sample but worse Wasserstein 2.11; explicit speed–fidelity trade-off. | p4-compatible under same caveat. | [S064] |
| 142 | ExpertSim ZDC mixture model | Mixture of experts | ALICE ZDC | Physics-guided router selects specialized generative experts. | Direct response to heterogeneity/multimodality; routing errors become a new failure mode. | p4 can drive the router only if all response-regime determinants are encoded or stochastic. | [S061] |
| 143 | ALICE proton SDI-GAN | Diversity-regularized GAN | ALICE proton ZDC | Selective-diversity loss and auxiliary spatial regressor. | Targets GAN mode collapse and broad response intensity; reports significant speedup. | p4-compatible for proton-only fixed geometry. | [S065] |
| 144 | ALICE ZDC IAF teacher | Normalizing-flow teacher | ALICE ZDC | Physics-weighted loss and output-variability scaling. | Designed to reduce rare-artifact dominance and improve morphology. | p4-compatible under fixed other attributes. | [S066] |
| 145 | ALICE ZDC IAF student | Distilled inverse autoregressive flow | ALICE ZDC | Teacher-student density distillation. | Paper reports 421x faster than previous ZDC NF implementations; compare only under matched hardware. | p4-compatible under fixed other attributes. | [S066] |
| 146 | MPD TPC direct GAN | GAN | Time projection chamber | Direct generation of detector response images/signals. | Reported >10x speed and no noticeable degradation in selected high-level observables. | Not p4-only: TPC response depends on track/path and detector conditions. | [S071] |
| 147 | MPD TPC indirect-metric GAN variant | GAN | Time projection chamber | Alternative representation/evaluation of TPC response. | Shows fast simulation outside calorimetry needs detector-specific sufficient conditions. | Not p4-only for full tracks. | [S071], [S072] |
| 148 | LHCb Cherenkov WGAN | WGAN | RICH/Cherenkov detector | Generates high-dimensional Cherenkov response conditioned on track parameters. | Demonstrates adversarial detector surrogates beyond calorimeters. | Generally requires track position/direction and detector conditions, not just p4. | [S070] |
| 149 | LHCb calorimeter GAN | GAN | LHCb calorimeter | Experiment-specific conditional calorimeter generator. | Emphasizes continuous conditioning and reconstruction-level validation. | p4-compatible only with fixed impact/local region. | [S069] |
| 150 | LArTPC score-diffusion model | Diffusion | Liquid-argon TPC images | Score model generates detector-image patches. | Useful fidelity proof; not yet equivalent to full track+electronics fast simulation. | Not p4-only; topology and detector conditions are required. | [S073] |
| 151 | LArTPC unpaired-translation model | Cycle/domain translation | Liquid-argon TPC | Translates simulation images toward detector-like domain without paired events. | Corrects domain mismatch rather than replacing the full simulator. | Consumes a simulated image, not p4 only. | [S074] |
| 152 | LAr optical-photon probability network | Supervised neural surrogate | LAr photon transport | Predicts photon-detection probabilities instead of propagating every optical photon. | Strong example where deterministic/sampling surrogates replace a specific costly physics substep. | Requires emission position and detector geometry, not p4 alone. | [S075] |
| 153 | FARICH conditional GAN | Conditional GAN | Focusing aerogel RICH | Generates ring/hit response from particle/track conditions. | Very recent; validates that p4 alone is insufficient when entry geometry varies independently. | Usually needs entry point and track path in addition to p4. | [S076] |
| 154 | Graph diffusion reconstructed-particle model | Graph diffusion | Reconstructed detector objects | Generates variable reconstructed-object graphs. | Moves validation to object/event level; topology and conservation are essential. | Needs event-level particle set, not one p4. | [S077] |
| 155 | PIPPIN full-event generator | Variable-length generative model | Full collider events | Generates reconstructed particles from hard-process information. | Full-event surrogate; useful downstream benchmark but not comparable to a single-shower model. | Needs full parton/event condition, not one p4. | [S078] |
| 156 | Graph generative detector-response model | Graph GAN | Detector-level particle clouds | Message-passing generator for variable particle sets. | Graph structure can encode detector/object relations, but must be physically audited. | Needs event particle set/geometry. | [S079] |
| 157 | CLAS12 GPT hit generator | Autoregressive transformer | CLAS12 detector hits | Sequence model generates detector-hit tokens. | Shows token generation as an alternative to images/graphs; autoregressive latency must be measured. | Requires trajectory/event context beyond one p4. | [S080] |
| 158 | Legacy ZDC HurdleGraph model | Hurdle VAE/recurrent graph | User ZDC ECAL+HCAL | Profile generator plus ECAL and 64-step HCAL recurrent allocation. | Rejected: unbounded total-energy support, forced positive layers, invalid recurrence, isolated ganged nodes, AUC ~0.99 and catastrophic tails. | Raw API used p4; derived kinematics were allowed. Entry was not an independent raw input. | [P001] |
| 159 | HGF-ZDC graph rectified-flow model | Hierarchical graph flow | User ZDC ECAL+HCAL | Start-depth model, profile rectified flow and 6,790-node cell flow. | Rejected checkpoint: ~23% response bias, late-HCAL suppression, high-level AUC ~0.67, ~4.6–5 events/s and invalid fixed-condition reference construction. | Implementation used p4 plus derived entry; for the fixed gun, entry is deterministic from p4, but arbitrary entry cannot be claimed. | [P002] |
| 160 | GraphFlow v0.3 candidate | Bounded hierarchical graph flow | User ZDC ECAL+HCAL | Bounded response ratio, explicit inactive layers/counts, exact top-k/softmax budgets and parallel graph generation. | Structurally defensible but unvalidated; should receive only a matched 50k–100k pilot against non-graph and mixture baselines. | Must accept only raw p4; geometry is static metadata and all event features must be deterministic functions of p4. | [P001], [P002] |

---

## 5. How to know whether the model is improving while training

### 5.1 Non-negotiable rule

**Do not select checkpoints using training loss, teacher-forced validation loss or one scalar score.**

A checkpoint is improving only if its **free-running generated distribution** becomes closer to held-out Geant4 across predeclared conditional physics metrics, with uncertainty small enough to distinguish the checkpoints, and without regressions in protected metrics.

### 5.2 Four immutable validation banks

#### Bank A — random held-out p4 bank

- Fixed p4 rows from the validation split.
- Representative of the declared 50–250 GeV domain.
- Stratified by energy and direction.
- Never used for optimizer steps or threshold tuning.

Purpose: overall in-domain monitoring.

#### Bank B — repeated-condition stochastic bank

- Exact same p4 repeated under many independent Geant4 seeds.
- The model generates the same number of independent samples for that exact p4.
- Required for conditional variance, tails, mode coverage and diversity.

Purpose: test `q(Y|p4)` rather than a pooled marginal.

#### Bank C — supported interpolation grid

- p4 values inside the observed training support but between common training points.
- Entry position, if derived from p4 and a fixed vertex, must remain on the actual condition manifold.

Purpose: interpolation smoothness and conditional calibration.

#### Bank D — explicit stress/OOD bank

- Below 50 GeV, above 250 GeV, extreme angles or unsupported intercepts.
- Report separately.
- Never include in the primary-domain headline score.

Purpose: failure characterization, not validation.

### 5.3 Checkpoint evaluation cadence

| Cadence | Generation/evaluation |
|---|---|
| Every optimizer step | Loss components, finite check, gradient norm, learning rate, transform-domain ranges. |
| Every 500–2,000 steps | 256–512 fixed validation p4 values × 4 model seeds; fast response/profile/count diagnostics. |
| Every epoch | ≥2,000 random held-out p4 plus ≥64 anchor p4 × 32 generated samples each. |
| Every 3–5 epochs | ≥20,000 generated events, bootstrap confidence intervals, C2ST, FPD/KPD, conditional coverage. |
| Promotion candidate | ≥50,000–100,000 generated events, deep tail tests, downstream reconstruction and matched timing. |
| Final candidate | Million-event invariant test plus sufficiently large repeated-condition Geant4 anchors for the claimed tolerances. |

Small early banks identify direction. They cannot certify a 1% response claim when Geant4 sampling uncertainty is much larger.

### 5.4 Gate 0: invariants

Any failure rejects the checkpoint regardless of loss:

```text
NaN/Inf rate                    = 0
negative cell energy rate       = 0
invalid/padded channel energy   = 0
sum(cell energies)-total budget = 0 within numeric tolerance
unsupported p4 accepted         = 0
energy-bound violation rate     = 0, if the audited target is raw deposited energy
```

For the legacy model, a 2.42% energy violation rate would imply roughly 24.2 million invalid events per billion generated events. A good median cannot compensate for this. [P001]

### 5.5 Gate 1: total response and zero response

For each conditional bin or anchor `k`, define:

```text
R = E_dep / E_inc
bias_k = |mean(R_gen,k) - mean(R_G4,k)| / mean(R_G4,k)
resolution_error_k =
    |std(R_gen,k) - std(R_G4,k)| / std(R_G4,k)
```

Track:

- zero-response probability;
- mean, median and standard deviation;
- 1%, 5%, 25%, 50%, 75%, 95%, 99% quantiles;
- tail probabilities at predeclared thresholds;
- worst-bin and percentile-bin error, not only an average.

**Improvement criterion:** bootstrap confidence interval for the new checkpoint's error is lower than the previous checkpoint's, or the paired bootstrap difference excludes zero, with no major tail regression.

### 5.6 Gate 2: longitudinal and detector-sharing closure

Track conditionally:

- ECAL, HCAL and total energy;
- ECAL/HCAL fraction;
- per-layer mean, variance and zero probability;
- first and last active layer;
- cumulative longitudinal profile;
- late-energy fractions such as layers 50–64;
- layer-energy covariance and layer-count covariance.

This gate would have caught HGF-ZDC's persistent ~23% response bias and severe late-HCAL underproduction even while cell loss improved. [P002]

### 5.7 Gate 3: occupancy and spatial morphology

Track:

- total and per-layer hit count;
- centroid `(x,y)` and radial centroid;
- RMS widths;
- `R50` and `R90`;
- maximum-cell and top-k energy fractions;
- nearest-neighbor energy correlations;
- connected-component sizes;
- ordinary versus ganged channel behavior;
- boundary-distance behavior only where the training/reference data actually contain it.

Do not average a per-cell metric over thousands of mostly empty channels and call that spatial closure.

### 5.8 Gate 4: joint-distribution tests

Use several complementary tests:

1. **High-level classifier two-sample test (C2ST).**
   - Inputs: named physics observables and conditions.
   - AUC near 0.5 is necessary but classifier capacity must be adequate.

2. **Geometry-aware low-level C2ST.**
   - Graph, sparse transformer or point-cloud classifier using cell energy, coordinates, layer, area, subdetector and ganging.
   - Do not randomly project away geometry.

3. **FPD and KPD.**
   - Use a frozen, disclosed physics feature extractor.
   - Report uncertainty and truth-vs-truth floors. [S004]

4. **Conditional energy distance or MMD.**
   - Evaluate at repeated p4 anchors, not only pooled samples.

5. **Correlation and copula diagnostics.**
   - Total energy versus start depth, width, hit count, ECAL fraction and late energy.

No one metric is sufficient. [S001,S004,S005]

### 5.9 Gate 5: diversity, coverage and memorization

At each repeated p4 anchor:

- compare generated conditional variance to Geant4;
- compare pairwise shower distances;
- evaluate precision and recall/coverage separately;
- inspect nearest-neighbor distance to train and test showers;
- verify output changes with random seed;
- verify output changes appropriately with p4;
- test whether rare Geant4 regimes receive generated probability.

Failure signatures:

| Pattern | Likely interpretation |
|---|---|
| High precision, low recall | Mode collapse / missing regimes. |
| Low precision, high recall | Overdispersed/unphysical generation. |
| Correct mean, low variance | Underdispersion; common in regression-like or overregularized models. |
| Correct pooled distribution, wrong anchors | Model ignores part of p4. |
| Generated samples much closer to training than test | Memorization. |
| Teacher-forced good, free-running bad | Exposure bias. |
| Loss down, C2ST/physics flat | Objective–physics misalignment or plateau. |

Precision/recall-style metrics are specifically useful because a single distance can confound fidelity and coverage. [S006,S007]

### 5.10 Gate 6: downstream physics closure

Freeze the existing reconstruction model before testing FastMC.

Compare Geant4 and FastMC on:

- reconstructed incident energy scale and resolution;
- position and angular resolution;
- selection efficiency;
- threshold turn-on;
- tail migration;
- reconstruction trained on Geant4 and evaluated on FastMC;
- reconstruction trained on FastMC and evaluated on locked Geant4.

Full-physics benchmarking shows that post-reconstruction behavior can expose errors hidden by shower-level metrics. [S084]

### 5.11 Gate 7: speed and deployment

Report separately:

```text
CPU batch-1 p50/p95 latency
GPU batch-1 p50/p95 latency
GPU throughput at batches 32, 128, 512, 1024
preprocessing time
ODE/flow network time
decoding/postprocessing time
serialization/data-transfer time
peak memory
model size and precision
```

Never compare the user's 4.6–5 events/s result directly with a paper's batch-256 mixed-precision number without disclosing the mismatch. The ALICE FM paper is instructive because it decomposes the speed gains: fewer steps, smaller model, mixed precision and latent generation reduce 11.8 ms to 0.026 ms/sample in that specific benchmark. [S064]

### 5.12 Checkpoint promotion rule

Use a lexicographic/Pareto decision, not a weighted sum that lets one easy metric hide a fatal failure.

```text
1. Invariants must all pass.
2. Primary-domain response and resolution must pass pilot gates.
3. Conditional coverage/diversity must not regress.
4. Longitudinal and geometry-sensitive metrics must improve.
5. Downstream closure must improve or remain equivalent.
6. Among physics-equivalent candidates, choose the faster/smaller model.
```

A checkpoint is labeled **IMPROVING** only when:

- at least two consecutive evaluations show improvement beyond bootstrap uncertainty on predeclared primary metrics;
- no protected metric regresses beyond tolerance;
- free-running, not teacher-forced, evaluation improves;
- the change is reproduced with a second training seed before major scaling.

Labels:

| Label | Meaning |
|---|---|
| `IMPROVING` | Statistically supported free-running physics improvement without protected regressions. |
| `NOISY/INCONCLUSIVE` | Differences are within validation uncertainty. |
| `PLATEAU` | Training loss improves but physics metrics do not over multiple checkpoints. |
| `OVERFITTING` | Train objective improves while held-out distribution metrics worsen. |
| `MODE_COLLAPSE` | Conditional diversity/recall falls. |
| `EXPOSURE_BIAS` | Teacher-forced metrics improve while free-running rollout worsens. |
| `INVALID` | Any invariant or data-contract failure. |

---

## 6. Recommended live training dashboard for the p4-only ZDC model

### 6.1 Step-level logging

```text
step
epoch
learning_rate
loss_total
loss_response
loss_profile
loss_count
loss_cell
gradient_norm_total
gradient_norm_by_stage
nonfinite_steps
response_transform_min/max
predicted_count_min/max
GPU memory
events_per_second_train
```

### 6.2 Free-running checkpoint table

```text
checkpoint_id
training_seed
generated_seed_bank_hash
validation_p4_manifest_hash
invariant_failures
max_response_bias_50_250
max_resolution_error_50_250
zero_response_Brier/ECE
ECAL_fraction_error
late_HCAL_fraction_error
start_depth_TV
hit_count_W1
R50_W1
R90_W1
high_level_C2ST_AUC
geometry_C2ST_AUC
FPD
KPD
conditional_precision
conditional_recall
nearest_train_test_ratio
downstream_energy_bias
downstream_resolution_error
batch1_latency_ms
batch256_events_per_second
peak_memory_MB
decision
```

### 6.3 Pilot gates for this project

These are engineering pilot gates, not universal final-publication thresholds:

```text
invariant failures                         = 0
max conditional response mean bias         < 5%
max conditional resolution discrepancy     < 15%
high-level C2ST AUC                         materially below prior ~0.67/0.99 failures
geometry-aware C2ST                        improves over no-graph baseline
late-HCAL and ECAL response                 no major systematic suppression
graph model                                beats matched non-graph model on >=2
                                           predeclared geometry-sensitive metrics
latency                                    has a plausible route to production
```

Final gates can be tighter only after the repeated-condition Geant4 reference has enough events to resolve them.

---

## 7. Architecture recommendation derived from the survey

For the next 50k–100k pilot, compare on identical data, steps and hardware:

1. **B0: competent conditional empirical/template model**
   - zero-response mixture;
   - bounded/empirical total response;
   - layer profile;
   - entry-centered spatial template;
   - stochastic residuals.

2. **B1: compact non-graph conditional flow/CFM**
   - p4 encoder;
   - shared event latent;
   - parallel layer/count/spatial decoder;
   - exact budgets.

3. **M1: response-regime mixture**
   - router from p4 plus stochastic latent;
   - experts for zero/low, early, late/leakage-like and broad-response modes;
   - routing/coverage diagnostics.

4. **G1: GraphFlow v0.3**
   - same raw p4 and same global/profile codec as B1;
   - audited physical graph;
   - no isolated valid nodes;
   - graph must earn its complexity.

5. **Optional P1: sparse point-cloud model**
   - only after the active-hit target and threshold are frozen.

### Stop conditions

Stop the graph branch if:

- a no-graph model matches or beats it on geometry-sensitive metrics;
- latency remains orders of magnitude off the useful frontier;
- count/top-k errors dominate;
- the available p4 support cannot identify the claimed spatial behavior.

Stop all training if the target semantics, sentinel-energy meaning or supported condition manifold remain unresolved.

---

## 8. Research and QA log

1. **Scope search.** Began from the CaloChallenge primary paper, official homepage, submitted-sample archives and workshop presentation; this supplied 50 officially evaluated model instances and prevented reliance on review articles alone. [S001–S003]
2. **Architecture expansion.** Traced primary papers for GAN, VAE, flow, diffusion, CFM, graph, point-cloud, transformer, mixture, classical and production-hybrid systems. [S008–S083]
3. **Non-calorimeter check.** Included TPC, LArTPC, RICH, reconstructed-object and full-event surrogates to identify which lessons generalize and which conditions exceed p4. [S067–S080]
4. **Metric cross-check.** Used the dedicated HEP generative-metrics paper, precision/recall literature, CaloChallenge and an independent calorimeter comparison. [S001,S004–S007]
5. **Current-literature check.** Included papers available through 2026-07-22, clearly marking very recent systems whose results still need independent reproduction.
6. **Deduplication.** Kept architecture families distinct from dataset/particle-specific model instances. Official challenge submissions are counted as instances because each is a separately generated/evaluated sample set.
7. **Numerical caution.** Quoted exact speed/metric numbers only where the primary source explicitly reported them. All speed claims are labeled as source-specific and not directly comparable.
8. **Project comparison.** Checked literature lessons against both uploaded project analyses. The legacy model is kept as a negative model instance; HGF-ZDC is separated from the newer unvalidated GraphFlow v0.3 candidate. [P001,P002]
9. **Input-contract QA.** Every catalogue row states whether p4-only conditioning is plausible. Models needing independent position, geometry, material, track or event data are explicitly marked.
10. **No false validation.** “Stable training,” “loss decreases,” “finite outputs” and “beats a weak baseline” are not treated as model validation.

---

## 9. Source ledger

- **[S001] CaloChallenge 2022: A Community Challenge for Fast Calorimeter Simulation.** Primary community benchmark: 31 submissions, 50 submitted sample sets, four datasets, quality/speed/model-size evaluation.  
  Source: https://arxiv.org/abs/2410.21611
- **[S002] CaloChallenge official homepage and submitted samples.** Official dataset, model-code and submitted-sample index; used to distinguish architecture families from separately evaluated model instances.  
  Source: https://calochallenge.github.io/homepage/
- **[S003] CaloChallenge 2023 results presentation.** Primary workshop presentation listing the submitted models by dataset and showing metric-specific rankings.  
  Source: https://indico.cern.ch/event/1253794/contributions/5588599/attachments/2749348/4784940/CaloChallenge.C.Krause.pdf
- **[S004] Evaluating generative models in high energy physics.** Primary metrics paper proposing FPD/KPD and recommending them with feature-level Wasserstein distances.  
  Source: https://arxiv.org/abs/2211.10295
- **[S005] A Comprehensive Evaluation of Generative Models in Calorimeter Simulation.** Independent multi-metric comparison; found CaloDiffusion and CaloScore strongest among the evaluated set but still imperfect.  
  Source: https://arxiv.org/abs/2406.12898
- **[S006] Precision and Recall for Distributions.** Separates sample fidelity/precision from distribution coverage/recall; useful for detecting mode collapse.  
  Source: https://arxiv.org/abs/1806.00035
- **[S007] Improved Precision and Recall Metric for Assessing Generative Models.** Refined manifold-based precision/recall method for generative evaluation.  
  Source: https://arxiv.org/abs/1904.06991
- **[S008] CaloGAN.** Foundational 3D calorimeter GAN; reports large CPU/GPU speedups and establishes energy-conditioned shower generation.  
  Source: https://arxiv.org/abs/1712.10321
- **[S009] Accelerating Science with GANs: 3D Particle Showers.** Early PRL demonstration of GAN-generated multilayer calorimeter showers.  
  Source: https://arxiv.org/abs/1705.02355
- **[S010] Controlling Physical Attributes in GAN-Accelerated Simulations.** Studies continuous physical conditioning and auxiliary constraints.  
  Source: https://arxiv.org/abs/1711.08813
- **[S011] Wasserstein GAN for Fast Detector Simulation.** Early WGAN-based detector-response surrogate.  
  Source: https://arxiv.org/abs/1802.03325
- **[S012] Precise Simulation of Electromagnetic Calorimeter Showers Using a WGAN.** High-fidelity electromagnetic calorimeter WGAN study.  
  Source: https://arxiv.org/abs/1807.01954
- **[S013] Fast and Accurate Simulation of Particle Detectors Using GANs.** Early GAN detector-simulation work emphasizing fidelity and speed.  
  Source: https://arxiv.org/abs/1805.00850
- **[S014] 3DGAN high-granularity calorimeter simulation.** 3D convolutional GAN with transfer-learning studies across particle species.  
  Source: https://arxiv.org/abs/2109.07388
- **[S015] Getting High: BIB-AE for High-Granularity Calorimeters.** Bounded-information-bottleneck autoencoder for ~27k-channel calorimeter showers, including low-energy/MIP structure.  
  Source: https://arxiv.org/abs/2005.05334
- **[S016] BIB-AE latent-space generation study.** Investigates latent sampling and density estimation for the BIB-AE.  
  Source: https://arxiv.org/abs/2102.12491
- **[S017] Hadronic shower generation with BIB-AE and WGAN.** Extends deep generative calorimeter simulation to hadronic showers.  
  Source: https://arxiv.org/abs/2112.09709
- **[S018] New Angles on Fast Calorimeter Shower Simulation.** Adds incident-angle/multi-parameter conditioning and evaluates downstream reconstruction.  
  Source: https://arxiv.org/abs/2303.18150
- **[S019] ATLAS photon shower generation with GANs.** ATLAS-oriented GAN study for electromagnetic calorimeter simulation.  
  Source: https://arxiv.org/abs/2210.06204
- **[S020] AtlFast3.** Production ATLAS fast simulation combining parametric FastCaloSim V2 and FastCaloGAN components.  
  Source: https://arxiv.org/abs/2109.02551
- **[S021] Delphes 3.** Widely used parameterized detector simulation; important non-generative production baseline.  
  Source: https://arxiv.org/abs/1307.6346
- **[S022] CaloShowerGAN.** GAN architecture submitted to CaloChallenge and evaluated on photon/pion shower data.  
  Source: https://arxiv.org/abs/2309.06515
- **[S023] CALPAGAN.** Conditional image-to-image refinement of calorimeter simulations using a pix2pix-style GAN.  
  Source: https://arxiv.org/abs/2401.02248
- **[S024] CaloFlow.** Normalizing-flow calorimeter generator; introduced classifier two-sample evaluation and stable likelihood-based training.  
  Source: https://arxiv.org/abs/2106.05285
- **[S025] CaloFlow II.** Teacher-student probability-density distillation for much faster flow sampling.  
  Source: https://arxiv.org/abs/2110.11377
- **[S026] CaloFlow for CaloChallenge Dataset 1.** Photon and charged-pion CaloFlow models on the public challenge data.  
  Source: https://arxiv.org/abs/2210.14245
- **[S027] iCaloFlow.** Layer-inductive CaloFlow extension with teacher/student variants.  
  Source: https://arxiv.org/abs/2305.11934
- **[S028] L2LFlows.** One normalizing flow per layer, conditioned on previous layers; reported higher fidelity than BIB-AE on ILD ECAL.  
  Source: https://arxiv.org/abs/2302.11594
- **[S029] Convolutional L2LFlows.** Coupling-flow/U-Net extension scaling L2LFlows to much higher-dimensional calorimeters.  
  Source: https://arxiv.org/abs/2405.20407
- **[S030] Normalizing Flows for High-Dimensional Detector Simulations.** CaloINN and CaloVAE+INN; direct INN at lower dimension and VAE-latent INN at higher dimension.  
  Source: https://arxiv.org/abs/2312.09290
- **[S031] CaloMan.** Manifold-learning plus density-estimation approach for calorimeter showers.  
  Source: https://arxiv.org/abs/2211.15380
- **[S032] SuperCalo.** Conditional flow super-resolution from coarse to fine calorimeter cells.  
  Source: https://arxiv.org/abs/2308.11700
- **[S033] CaloPointFlow II.** Sparse point-cloud normalizing flow with CDF dequantization and DeepSetFlow.  
  Source: https://arxiv.org/abs/2403.15782
- **[S034] CaloClouds.** Geometry-independent point-cloud diffusion for highly granular calorimeters.  
  Source: https://arxiv.org/abs/2305.04847
- **[S035] CaloClouds II.** Accelerated continuous-time and consistency variants of CaloClouds.  
  Source: https://arxiv.org/abs/2309.05704
- **[S036] CaloClouds3.** Hybrid normalizing-flow/diffusion point-cloud calorimeter generator.  
  Source: https://arxiv.org/abs/2511.01460
- **[S037] CaloScore.** Score-based calorimeter generators using multiple SDE/noise formulations.  
  Source: https://arxiv.org/abs/2206.11898
- **[S038] CaloScore v2.** Progressive distillation and single-shot score-model variants.  
  Source: https://arxiv.org/abs/2308.03847
- **[S039] CaloDiffusion.** Diffusion model with cylindrical convolutions and geometry-latent mapping for irregular layouts.  
  Source: https://arxiv.org/abs/2308.03876
- **[S040] CaloGraph.** Graph diffusion for irregular calorimeter geometry.  
  Source: https://arxiv.org/abs/2402.11575
- **[S041] Calo-VQ.** VQ-VAE/token model for calorimeter showers with fast sequence generation.  
  Source: https://arxiv.org/abs/2405.06605
- **[S042] CaloQVAE.** Quantum-assisted VAE/RBM calorimeter generation study.  
  Source: https://arxiv.org/abs/2312.03179
- **[S043] Calo4pQVAE.** Four-particle quantum-assisted VAE study with FPD/KPD monitoring.  
  Source: https://arxiv.org/abs/2412.04677
- **[S044] CaloDREAM.** Conditional flow matching with separate layer-energy and voxel-shape models, including latent variants.  
  Source: https://arxiv.org/abs/2405.09629
- **[S045] Universal Vision Transformer for Fast Calorimeter Simulation.** Single ViT-style framework spanning regular, irregular and multiple detector geometries.  
  Source: https://arxiv.org/abs/2601.05289
- **[S046] CaloDiT-2: Generalisable Multi-Detector Calorimeter Simulation.** Transformer diffusion model designed to generalize across detector geometries.  
  Source: https://arxiv.org/abs/2509.07700
- **[S047] Fast, Accurate and Precise ViT Calorimeter Simulation.** Controlled comparison of conditional flow matching and coupling normalizing flows with a shared ViT backbone.  
  Source: https://arxiv.org/abs/2509.25169
- **[S048] ParaFlow.** Parameter-conditioned flow for material/upstream-detector variation.  
  Source: https://arxiv.org/abs/2503.21461
- **[S049] SQuIRELS.** Schrödinger-bridge refinement from fast GFLASH-like simulation toward Geant4.  
  Source: https://arxiv.org/abs/2308.12339
- **[S050] CaloHadronic.** Point-count flow plus diffusion-transformer components for hadronic ECAL/HCAL shower generation.  
  Source: https://arxiv.org/abs/2506.21720
- **[S051] AllShowers.** Unified multi-particle generative calorimeter model.  
  Source: https://arxiv.org/abs/2601.11716
- **[S052] OmniJet-alpha_C.** Tokenized variable-length point-cloud transformer for calorimeter simulation.  
  Source: https://arxiv.org/abs/2501.05534
- **[S053] CaloTrilogy.** Unified one/few-step end-to-end calorimeter flow-matching framework.  
  Source: https://arxiv.org/abs/2606.04165
- **[S054] CaloArt.** Large-patch x-prediction diffusion transformer; reports strong CCD2/CCD3 quality-time trade-offs.  
  Source: https://arxiv.org/abs/2605.12011
- **[S055] FPGA-deployable VAE calorimeter simulation.** Quantization-aware/compressed VAE deployment study targeting sub-millisecond hardware inference.  
  Source: https://arxiv.org/abs/2603.13490
- **[S056] Geometry-aware Autoregressive Models.** Cell-geometry-conditioned autoregressive calorimeter generator.  
  Source: https://arxiv.org/abs/2212.08233
- **[S057] GAAM geometry generalization.** Geometry-aware model evaluated on unseen layouts; reports >50% improvement over geometry-unaware baselines on several metrics.  
  Source: https://arxiv.org/abs/2305.11531
- **[S058] MDMA.** Mean-field attentive point-cloud GAN used in CaloChallenge.  
  Source: https://arxiv.org/abs/2305.15254
- **[S059] DeepTreeGAN.** Tree-structured point-cloud GAN for calorimeter showers.  
  Source: https://arxiv.org/abs/2311.12616
- **[S060] DeepTreeGANv2.** Refined tree-structured point-cloud GAN.  
  Source: https://arxiv.org/abs/2312.00042
- **[S061] ExpertSim.** Mixture-of-generative-experts model for heterogeneous ALICE ZDC responses.  
  Source: https://arxiv.org/abs/2508.20991
- **[S062] Generative Diffusion Models for ALICE ZDC.** Pixel and latent diffusion models for ZDC, including quality-versus-sampling-time analysis.  
  Source: https://arxiv.org/abs/2406.03233
- **[S063] Machine Learning Methods for ALICE neutron ZDC.** Conditional VAE and GAN variants, zero-response classifier, auxiliary regressor and postprocessing; reports ~100x speedup.  
  Source: https://arxiv.org/abs/2306.13606
- **[S064] Even Faster ZDC Simulation with Flow Matching.** Full and latent flow matching for ALICE ZN/ZP; reports 0.46 ms and 0.026 ms/sample at batch 256 with fidelity trade-off.  
  Source: https://arxiv.org/abs/2507.18811
- **[S065] Deep Generative Models for ALICE proton ZDC.** SDI-GAN with diversity and spatial regularization for proton ZDC.  
  Source: https://arxiv.org/abs/2406.03263
- **[S066] Inverse Autoregressive Flows for ZDC.** Physics-scaled loss and teacher-student IAF; reports 421x speed relative to prior ZDC NF implementations.  
  Source: https://arxiv.org/abs/2512.20346
- **[S067] Lamarr: LHCb ultra-fast simulation.** Production-oriented modular fast detector/reconstruction simulation with deep generative models and GBDTs; ~100x simulation-phase speedup.  
  Source: https://arxiv.org/abs/2309.13213
- **[S068] LHCb machine-learning fast/flash simulation review.** Summarizes CaloML, fast/flash modules and validation criteria used at LHCb.  
  Source: https://arxiv.org/abs/2511.02020
- **[S069] Generative Models for Fast Calorimeter Simulation: LHCb.** LHCb calorimeter GAN fast-simulation study.  
  Source: https://arxiv.org/abs/2003.09762
- **[S070] Cherenkov detector simulation with a WGAN.** WGAN surrogate for Cherenkov/RICH-like detector response.  
  Source: https://arxiv.org/abs/1903.11788
- **[S071] GAN-Based TPC Fast Simulation for MPD.** TPC response GAN; reports >10x speed and no noticeable degradation in selected high-level observables.  
  Source: https://arxiv.org/abs/2203.16355
- **[S072] TPC detector-response surrogate follow-up.** Additional TPC surrogate modeling and validation.  
  Source: https://arxiv.org/abs/2207.04340
- **[S073] Score-based diffusion for LArTPC images.** Diffusion generation of LArTPC detector images; proof of generative fidelity rather than a mature production speed replacement.  
  Source: https://arxiv.org/abs/2307.13687
- **[S074] Unpaired image translation for LArTPC simulation.** Domain translation between simulated and detector-like LArTPC images.  
  Source: https://arxiv.org/abs/2304.12858
- **[S075] Photon-detection probability ML for LAr detectors.** Neural surrogate for optical-photon detection probability, replacing expensive photon propagation.  
  Source: https://arxiv.org/abs/2109.07277
- **[S076] FARICH conditional GAN simulation.** Conditional generative surrogate for focusing aerogel RICH response.  
  Source: https://arxiv.org/abs/2605.17635
- **[S077] Graph diffusion for reconstructed-particle detector simulation.** Graph diffusion model generating reconstructed detector objects.  
  Source: https://arxiv.org/abs/2405.10106
- **[S078] PIPPIN: full-event generation.** Variable-length full-event generative model from hard process to reconstructed particles.  
  Source: https://arxiv.org/abs/2406.13074
- **[S079] Graph generative detector response.** Graph-based generative model for detector-level particle clouds.  
  Source: https://arxiv.org/abs/2104.01725
- **[S080] CLAS12 GPT detector-hit generation.** Autoregressive transformer for detector-hit generation in a non-calorimeter HEP detector.  
  Source: https://arxiv.org/abs/2606.16035
- **[S081] GFLASH parameterised shower model in Geant4.** Official classical parameterized-shower documentation; non-neural reference.  
  Source: https://geant4.web.cern.ch/documentation/dev/bfad_html/ForApplicationDevelopers/TrackingAndPhysics/parameterized.html
- **[S082] LHCb calorimeter point-library simulation.** Point-library based calorimeter acceleration; non-generative reference for sparse lookup/reuse.  
  Source: https://cds.cern.ch/record/2950495
- **[S083] Deep Generative Models for Detector Signature Simulation: Taxonomy.** Review/taxonomy used to cross-check architecture families and scope.  
  Source: https://arxiv.org/abs/2312.09597
- **[S084] First Full Physics Benchmark for Highly Granular Calorimeter Surrogates.** Post-reconstruction/full-physics validation showing why shower-image metrics alone are insufficient.  
  Source: https://arxiv.org/abs/2511.17293
- **[S085] Calomplification.** Studies when generated samples can have more statistical utility than the finite training sample, with observable-dependent limits.  
  Source: https://arxiv.org/abs/2202.07352
- **[P001] Project analysis: legacy recurrent ZDC model.** Project evidence for the recurrent HurdleGraph architecture, bugs, training history and independent evaluation.  
  Source: analysis.md (uploaded in this conversation)
- **[P002] Project analysis: HGF-ZDC graph rectified-flow model.** Project evidence for HGF-ZDC data contract, architecture, training, evaluation and unresolved response bias.  
  Source: analysis(1).md (uploaded in this conversation)

---

## 10. Final project decision

The literature does **not** support another long run of the prior recurrent model or the unchanged HGF recipe.

It supports:

- retaining a hierarchical global-to-local design;
- enforcing target-correct support and exact invariants;
- using p4 as the only raw event condition;
- deriving direction and fixed-vertex intercept deterministically;
- testing a compact non-graph flow and a mixture model before committing to a graph;
- monitoring free-running conditional distributions throughout training;
- selecting checkpoints through physics gates and a Pareto frontier;
- generating new repeated-condition Geant4 anchors if strict conditional or edge claims are required.

The most important operational change is simple:

> **A lower loss is not progress. Progress is a statistically supported improvement in free-running conditional Geant4 closure, with zero invariant failures and no protected-metric regression.**
