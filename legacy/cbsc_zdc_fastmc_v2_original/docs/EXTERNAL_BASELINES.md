# External implementation baselines

## Highest-priority ZDC code

### m-wojnar/faster_zdc

- Repository: https://github.com/m-wojnar/faster_zdc
- Paper: https://arxiv.org/abs/2507.18811
- Implements full-space and latent flow matching for ALICE neutron and proton ZDC response, with pretrained/standalone inference material in the repository.
- The repository reports approximately 70k-parameter FM models, ZN Wasserstein 1.27, approximately 0.46 ms/sample for full FM, and approximately 0.026 ms/sample for latent FM in its stated setup.
- It is not a drop-in model for a 6,790-channel ECAL+HCAL output. First reproduce the repository natively; then adapt the training recipe, not its assumed image dimensionality.

### m-wojnar/zdc

- Repository: https://github.com/m-wojnar/zdc
- Earlier ALICE neutron-ZDC model collection including VAE, GAN, vector-quantized, and diffusion approaches.
- Useful for reproducing the historical quality/speed progression and zero-response handling.

### ExpertSim

- Repository: https://github.com/patrick-bedkowski/expertsim-mix-of-generative-experts
- Paper: https://arxiv.org/abs/2508.20991
- Mixture-of-generative-experts model for heterogeneous ZDC responses.
- Its documented native data use nine conditional variables, including coordinates, so it is not compliant with a p4-only raw-input contract without a controlled adaptation.

## General calorimeter code

### VisionTransformers4HEP / CaloDREAM extension

- Repository: https://github.com/luigifvr/vit4hep
- Supports conditional flow matching and normalizing flows, with separate energy and shape networks and configurable preprocessing.
- Useful as a non-graph transformer/CFM baseline.

### CaloHadronic

- Repository: https://github.com/FLC-QU-hep/CaloHadronic
- Transformer-based point-cloud diffusion across ECAL and HCAL for hadronic showers.
- Useful as a sparse representation baseline and for holistic ECAL+HCAL conditioning.

### CaloDiffusion

- Repository: https://github.com/OzAmram/CaloDiffusion
- Diffusion model with geometry adaptation for irregular calorimeters.

## Supplied project baseline

The supplied `PROPOSAL_single_stage_flow_baseline.md` remains a useful controlled ablation: one full detector flow, identical data/splits/geometry, no separate start/profile stages. The revised version must use the p4-only input contract and the same anti-dust decoder as the hierarchical candidate so that only hierarchy is being tested.
