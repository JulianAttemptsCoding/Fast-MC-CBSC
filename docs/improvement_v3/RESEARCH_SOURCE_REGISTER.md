# Research and evidence source register

External technical decisions rely on primary papers/preprints and official
framework documentation. Numerical claims about CBSC-ZDC come from the audited
archive, not from transferring results across detectors.

## A. Internal primary evidence from the reviewed archive

| Source | Use in this plan |
|---|---|
| `AGENTS.md` | binding filesystem, data, test, logging, invariant, and experiment rules |
| `CLAUDE.md` | active L40S/3090 topology, resume behavior, environment, and current operational state |
| `docs/IMPLEMENTATION_GUIDE.md` | exact v2.2 data/model/training/evaluation contract |
| `docs/DATA_CONTRACT.md` | four-momentum, geometry, channel identity, target, and split semantics |
| `docs/QA_POLICY.md` | quarantine versus scientific-finding semantics |
| `docs/EVALUATION_PROTOCOL.md` | evidence hierarchy and test isolation |
| `docs/TWO_GPU_PIPELINE.md` | producer/diagnostic synchronization and evidence requirements |
| `configs/gates_primary.yaml` | actual provisional diagnostic thresholds in the archive |
| `src/cbsc_zdc/models/{system,response,profile,counts,support,node_fields}.py` | exact current sampler, double-zero path, independent longitudinal heads, hard top-k, and node inputs |
| `src/cbsc_zdc/training/{trainer,losses,flow_matching,truth}.py` | exact nine-part loss, gradient path, stages, scheduler, and derived truth |
| `src/cbsc_zdc/data/audit.py` | quantile-derived safety caps; basis for rejecting them as unverified hard spline support |
| `audit/campaign_20260810_lr3e4_terminal_analysis.{json,md}` | L40S transition and epoch-47 reference result |
| `logs.md`, 2026-08-12 entries | inherited scheduler `T_max`, declared corrective anneal, and in-flight state |
| `live_campaign_evidence/` | archive-time evidence that corrected anneal was still running |
| `external_models/` accepted C2ST/reconstruction evidence | current separability and downstream error measurements; evaluator remains external |
| `MANIFEST.sha256` and `verify_bundle.py` | valid archive integrity definition |

Companion analyses produced from that archive:

- `CBSC_ZDC_project_audit_and_research_review_20260812.md`;
- `CBSC_ZDC_full_file_ledger_20260812.csv`;
- `CBSC_ZDC_improvement_research_and_dynamic_critic_plan_20260812.md`.

## B. Generative modeling, flows, and discrete gradients

1. Durkan et al., **Neural Spline Flows** — monotone rational-quadratic
   splines with analytic invertibility and exact density evaluation.
   [arXiv:1906.04032](https://arxiv.org/abs/1906.04032)
2. Lipman et al., **Flow Matching for Generative Modeling** — simulation-free
   vector-field regression for continuous normalizing flows.
   [arXiv:2210.02747](https://arxiv.org/abs/2210.02747)
3. Tong et al., **Improving and Generalizing Flow-Based Generative Models with
   Minibatch Optimal Transport** — conditional flow matching and OT-CFM.
   [arXiv:2302.00482](https://arxiv.org/abs/2302.00482)
4. Kool, van Hoof, and Welling, **Stochastic Beams and Where to Find Them: The
   Gumbel-Top-k Trick for Sampling Sequences Without Replacement** — exact
   Gumbel top-k sampling ancestry.
   [PMLR v97](https://proceedings.mlr.press/v97/kool19a.html)
5. Jang, Gu, and Poole, **Categorical Reparameterization with Gumbel-Softmax**
   — relaxed categorical pathwise gradients; relevant only to deferred relaxed
   decisions.
   [arXiv:1611.01144](https://arxiv.org/abs/1611.01144)
6. Paulus et al., **Gradient Estimation with Stochastic Softmax Tricks** —
   structured combinatorial relaxations including subset selection.
   [arXiv:2006.08063](https://arxiv.org/abs/2006.08063)
7. Ahmed et al., **SIMPLE: A Gradient Estimator for k-Subset Sampling** — hard
   discrete forward samples with exact-marginal proxy gradients; D3 candidate.
   [arXiv:2210.01941](https://arxiv.org/abs/2210.01941)

## C. Dynamic critic design and stability

8. Goodfellow et al., **Generative Adversarial Nets** — original
   generator/discriminator objective.
   [arXiv:1406.2661](https://arxiv.org/abs/1406.2661)
9. Salimans et al., **Improved Techniques for Training GANs** — feature
   matching used as the matched control to direct critic-score optimization.
   [arXiv:1606.03498](https://arxiv.org/abs/1606.03498)
10. Shrivastava et al., **Learning from Simulated and Unsupervised Images
    through Adversarial Training** — discriminator history-buffer precedent.
    [arXiv:1612.07828](https://arxiv.org/abs/1612.07828)
11. Heusel et al., **GANs Trained by a Two Time-Scale Update Rule Converge to a
    Local Nash Equilibrium** — separate generator/critic learning rates.
    [arXiv:1706.08500](https://arxiv.org/abs/1706.08500)
12. Mescheder, Geiger, and Nowozin, **Which Training Methods for GANs Do
    Actually Converge?** — zero-centered gradient penalties and cautions about
    unregularized/finite-update GAN dynamics.
    [arXiv:1801.04406](https://arxiv.org/abs/1801.04406)
13. Miyato and Koyama, **cGANs with Projection Discriminator** — projection
    conditioning used for `p(shower|p4)` rather than marginal discrimination.
    [arXiv:1802.05637](https://arxiv.org/abs/1802.05637)
14. Miyato et al., **Spectral Normalization for Generative Adversarial
    Networks** — critic stabilization by controlling layer spectral norm.
    [arXiv:1802.05957](https://arxiv.org/abs/1802.05957)
15. Gulrajani et al., **Improved Training of Wasserstein GANs** — WGAN-GP
    alternative; retained as an ablation rather than assumed default.
    [arXiv:1704.00028](https://arxiv.org/abs/1704.00028)
16. Lin et al., **PacGAN: The Power of Two Samples in Generative Adversarial
    Networks** — contingency if repeated-condition diversity collapses.
    [arXiv:1712.04086](https://arxiv.org/abs/1712.04086)
17. Metz et al., **Unrolled Generative Adversarial Networks** — expensive
    contingency after simpler stability controls.
    [arXiv:1611.02163](https://arxiv.org/abs/1611.02163)

## D. Classifier tests and scientific generative-model evaluation

18. Lopez-Paz and Oquab, **Revisiting Classifier Two-Sample Tests** — held-out
    classifier testing and interpretation of separability.
    [arXiv:1610.06545](https://arxiv.org/abs/1610.06545)
19. Shekhar and Ramdas, **E-C2ST: Efficient and Anytime-Valid Classifier
    Two-Sample Tests** — additional C2ST methodology context.
    [arXiv:2210.13027](https://arxiv.org/abs/2210.13027)
20. Bischoff et al., **A Practical Guide to Statistical Distances for Evaluating
    Generative Models in Science** — complementary distances and
    scientific-evaluation cautions.
    [arXiv:2403.12636](https://arxiv.org/abs/2403.12636)
21. Krause et al., **CaloChallenge 2022: A Community Challenge for Fast
    Calorimeter Simulation** — broad metric suite including one-dimensional
    observables, KPD/FPD, classifiers, timing, and model size.
    [arXiv:2410.21611](https://arxiv.org/abs/2410.21611)
22. Ahmad et al., **Lantern: Conflict-Aware Gradient Blending for
    Physics-Guided Diffusion Models in Calorimeter Simulation** — provisional
    July 2026 preprint reporting that common symmetric multi-loss balancing can
    regress fidelity in one calorimeter setting; supports measuring conflicts
    rather than defaulting to automatic balancing.
    [arXiv:2607.25060](https://arxiv.org/abs/2607.25060)

## E. Calorimeter and ZDC generative simulation

23. Krause and Shih, **CaloFlow: Fast and Accurate Generation of Calorimeter
    Showers with Normalizing Flows** — flow-based calorimeter likelihoods and
    classifier evaluation.
    [arXiv:2106.05285](https://arxiv.org/abs/2106.05285)
24. Krause and Shih, **CaloFlow II: Even Faster and Still Accurate Generation
    of Calorimeter Showers with Normalizing Flows** — speed recovery and
    specialized training.
    [arXiv:2110.11377](https://arxiv.org/abs/2110.11377)
25. Diefenbacher et al., **L2LFlows: Generating High-Fidelity 3D Calorimeter
    Images** — explicit conditioning on preceding layers for longitudinal
    dependence.
    [arXiv:2302.11594](https://arxiv.org/abs/2302.11594)
26. Paganini et al., **CaloGAN: Simulating 3D High Energy Particle Showers in
    Multilayer Electromagnetic Calorimeters with Generative Adversarial
    Networks** — early adversarial calorimeter simulation.
    [arXiv:1712.10321](https://arxiv.org/abs/1712.10321)
27. **CaloShowerGAN** — conditional adversarial calorimeter simulation context.
    [arXiv:2309.06515](https://arxiv.org/abs/2309.06515)
28. Buhmann et al., **Hadrons, Better, Faster, Stronger** — hadronic
    calorimeter generative simulation and adversarial training.
    [arXiv:2112.09709](https://arxiv.org/abs/2112.09709)
29. Buhmann et al., **Getting High: High Fidelity Simulation of High
    Granularity Calorimeters with High Speed** — BIB-AE and postprocessing
    precedent; postprocessing remains a backup.
    [arXiv:2005.05334](https://arxiv.org/abs/2005.05334)
30. Hashemi et al., **GAN with an Auxiliary Regressor for the Fast Simulation
    of the Electromagnetic Calorimeter Response** — auxiliary-regressor
    precedent relevant to the optional frozen p4 model.
    [arXiv:2207.06329](https://arxiv.org/abs/2207.06329)
31. **IEA-GAN: Relational Reasoning and Self-Attention for Ultra-High
    Granularity Calorimeters** — learned relational objectives and diversity.
    [arXiv:2303.08046](https://arxiv.org/abs/2303.08046)
32. Kobylianskii et al., **CaloGraph: Graph-based Diffusion Model for Fast
    Shower Generation in Calorimeters with Irregular Geometry** — graph
    modeling for irregular detectors.
    [arXiv:2402.11575](https://arxiv.org/abs/2402.11575)
33. **Point-cloud and Image-based Models for Calorimeter Shower Fast
    Simulation** — sparse point-cloud representation and matched comparisons.
    [arXiv:2307.04780](https://arxiv.org/abs/2307.04780)
34. Kita et al., **Generative Diffusion Models for Fast Simulations of Particle
    Collisions at CERN** — directly adjacent ALICE ZDC diffusion work.
    [arXiv:2406.03233](https://arxiv.org/abs/2406.03233)
35. Wojnar, **Even Faster Simulations with Flow Matching: A Study of Zero
    Degree Calorimeter Responses** — directly adjacent ZDC flow matching and
    latent-flow timing/fidelity context.
    [arXiv:2507.18811](https://arxiv.org/abs/2507.18811)
36. Będkowski et al., **ExpertSim: Fast Particle Detector Simulation Using
    Mixture-of-Generative-Experts** — response-regime/expert-routing
    contingency.
    [arXiv:2508.20991](https://arxiv.org/abs/2508.20991)
37. Majerz et al., **Inverse Autoregressive Flows for Zero Degree Calorimeter
    Fast Simulation** — recent ZDC morphology/variability-scaling direction;
    not reconstructed from abstract alone.
    [arXiv:2512.20346](https://arxiv.org/abs/2512.20346)
38. Buss et al., **A First Full Physics Benchmark for Highly Granular
    Calorimeter Surrogates** — detector-integrated reconstruction and
    full-physics validation beyond single showers.
    [arXiv:2511.17293](https://arxiv.org/abs/2511.17293)

Reported numbers from sources 34–38 are not acceptance thresholds for this
project: detectors, preprocessing, conditioning, and metrics differ.

## F. Official implementation documentation

39. PyTorch, **Automatic Mixed Precision** — correct use of autocast and
    gradient scaling.
    [Official documentation](https://docs.pytorch.org/docs/stable/amp.html)
40. PyTorch, **Reproducibility** — RNG and deterministic-execution limits.
    [Official documentation](https://docs.pytorch.org/docs/stable/notes/randomness.html)
41. PyTorch, **CosineAnnealingLR** — scheduler definition/state behavior; the
    project-specific inherited-state defect is demonstrated by its own logs.
    [Official documentation](https://docs.pytorch.org/docs/stable/generated/torch.optim.lr_scheduler.CosineAnnealingLR.html)
42. PyTorch, **Spectral-normalization parametrization** — implementation API
    for critic linear layers.
    [Official documentation](https://docs.pytorch.org/docs/stable/generated/torch.nn.utils.parametrizations.spectral_norm.html)

## Source-use caveats

- A paper motivates an ablation; it does not prove that the ablation improves
  this 6,790-channel detector.
- R1, spectral normalization, replay proportions, gradient targets, critic
  capacity, and promotion margins are declared project hyperparameters. The
  cited papers do not uniquely derive those numbers.
- Very recent 2025–2026 ZDC/full-physics/conflict papers are treated as
  provisional or adjacent evidence and must not override matched local data.
- The exact data, operational, and test-isolation constraints come from the
  internal repository documents, which are authoritative for this project.

