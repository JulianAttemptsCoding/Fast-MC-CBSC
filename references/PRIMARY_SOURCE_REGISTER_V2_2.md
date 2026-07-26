# Primary Source Register v2.2

| Topic | Primary source | Use |
|---|---|---|
| Flow matching | Lipman et al., `https://arxiv.org/abs/2210.02747` | simulation-free vector-field regression and ODE sampling |
| Flow matching guide | Lipman et al., `https://arxiv.org/abs/2412.06264` | implementation/design review |
| Gumbel-Top-k | Kool, van Hoof, Welling, `https://proceedings.mlr.press/v97/kool19a.html` | exact sampling without replacement |
| GradNorm | Chen et al., `https://proceedings.mlr.press/v80/chen18a.html` | gradient-scale loss balancing inspiration |
| Uncertainty weighting | Kendall, Gal, Cipolla, `https://openaccess.thecvf.com/content_cvpr_2018/html/Kendall_Multi-Task_Learning_Using_CVPR_2018_paper.html` | alternative multitask weighting |
| PyTorch reproducibility | `https://docs.pytorch.org/docs/stable/notes/randomness` | seeds, deterministic algorithms, DataLoader workers |
| PyTorch AMP | `https://docs.pytorch.org/docs/stable/amp.html` | autocast and gradient scaling |
| PyTorch AdamW | `https://docs.pytorch.org/docs/main/generated/torch.optim.AdamW.html` | optimizer contract |
| Vertex Custom Jobs | `https://cloud.google.com/vertex-ai/docs/training/create-custom-job` | custom container training workflow |
| EDM4hep hit semantics | official/generated EDM4hep `SimCalorimeterHit` API | cell ID, hit energy in GeV, position in mm |
| Geant4 | official documentation and particle-gun interface | kinetic-energy convention and simulation context |

Detector-specific and calorimeter-generator references remain in the original register and revised specification. Bibliographic metadata must be rechecked before publication.
