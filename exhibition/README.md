# CBSC-ZDC exhibition

Presentation-ready figures generated from verified CBSC-ZDC v2.2 evidence.

Open [index.html](index.html) for the gallery. PNG files are slide-ready; SVG
counterparts are included for editable vector use where practical.

## Figure catalog

1. `01_train_validation_loss_each_model` — train and validation loss over every
   completed epoch for each of the four calibrated families.
2. `02_validation_loss_comparison` — cross-family validation trajectories and
   percent reduction.
3. `03_objective_component_evolution` — nine objective components across
   epochs.
4. `04_fixed_sample_proxy_trajectories` — response, hit-count, and longitudinal
   fixed-sample diagnostics.
5. `05_loss_vs_visual_proxy_boundary` — why objective progress and physics
   proxies are not interchangeable.
6. `06_vertex_compute_and_budget` — parallel T4 execution and conservative
   budget position.
7. `07_model_architecture_and_exact_decoder` — the stochastic cascade and exact
   energy/count constraints.
8. `08_data_geometry_and_split_contract` — production data flow, detector
   geometry, and sealed test boundary.
9. `09_evidence_and_claim_boundary` — established vs unestablished claims.
10. `10_same_condition_longitudinal_profiles` — one Geant4 event compared with
    five Fast-MC draws for each current best checkpoint.
11. `11_best_model_sample_distributions` — four distribution-level visual
    checks for the current best visual family.
12. `12_same_condition_3d_energy_deposits` — one Geant4 3D deposit and five
    conditional Fast-MC draws.

## Companion material built from test events

[`c2st_20260728/`](c2st_20260728/README.md) holds the classifier two-sample test
comparison figures and the overview presentation deck. **Those artifacts use
40,000 test-split events** and are therefore kept out of this gallery, which is
built under `test_events_used = 0`. The builder passes an explicit file list to
its gallery step and does not scan that subdirectory, so `manifest.json` and
`index.html` are unaffected by it.

## Rebuild

```powershell
python exhibition/build_exhibition.py
```

The builder reads compact audit evidence plus existing validation visualization
payloads. It does not read `legacy/`, the original ROOT tree, or test events.
`manifest.json` records source/output hashes and QA assertions.

## Scientific boundary

These figures establish structural execution and short-horizon optimization
progress. They do not establish Geant4 fidelity, and they use zero test events.

Test-split accounting, repository-wide: 40,000 of the 76,300 test events were
consumed on 2026-07-28 by the isolated classifier two-sample test recorded in
`logs.md` and published under `c2st_20260728/`. The remaining 36,300 are
untouched. That study measured separability, not fidelity, and no result from it
may influence CBSC-ZDC preprocessing, thresholds, architecture, loss weights,
learning rate, stopping, checkpoint selection, or visualization.

Hardware-screening measurements are nonbinding QA observations and do not
control future training.
