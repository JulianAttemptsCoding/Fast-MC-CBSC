# CBSC-ZDC exhibition

Presentation-ready figures generated from verified CBSC-ZDC v2.2 evidence.

Open [index.html](index.html) for the landing page. Every substantive visual is
in exactly one governed folder:

- [current/](current/README.md) contains every presently valid, up-to-date
  visual and its complete `index.html` gallery;
- [archive/](archive/README.md) contains historical, superseded, isolated-test,
  or otherwise non-current visuals and its complete `index.html` gallery.

PNG files are slide-ready; SVG counterparts are included for editable vector
use where practical. `visual_layout.json` is the machine-enforced placement and
outside-exhibition exception contract.

## Model/contract figure catalog

Figures 1–6 are an explicitly historical common-window snapshot in
`archive/common_window_20260727/`. Figures 7–12 remain current in
`current/model/`; epoch-dependent current plots live in `current/continuation/`
and `current/diagnostics/`.

1. `01_train_validation_loss_each_model` — train and validation loss over the
   common comparison window (epochs 0–10) for all four calibrated families.
2. `02_validation_loss_comparison` — cross-family validation trajectories and
   percent reduction.
3. `03_objective_component_evolution` — nine objective components across the
   common comparison window.
4. `04_fixed_sample_proxy_trajectories` — response, hit-count, and longitudinal
   fixed-sample diagnostics.
5. `05_loss_vs_visual_proxy_boundary` — why objective progress and physics
   proxies are not interchangeable.
6. `06_vertex_compute_and_budget` — historical parallel T4 execution and
   conservative budget position.
7. `07_model_architecture_and_exact_decoder` — the stochastic cascade and exact
   energy/count constraints.
8. `08_data_geometry_and_split_contract` — production data flow, detector
   geometry, and governed test boundary.
9. `09_evidence_and_claim_boundary` — established vs unestablished claims.
10. `10_same_condition_longitudinal_profiles` — one Geant4 event compared with
    five Fast-MC draws for each current best checkpoint.
11. `11_best_model_sample_distributions` — four distribution-level visual
    checks for the lowest accepted-loss family with a verified payload.
12. `12_same_condition_3d_energy_deposits` — one Geant4 3D deposit and five
    conditional Fast-MC draws.

## Companion material built from test events

[`archive/c2st_20260728/`](archive/c2st_20260728/README.md) holds the classifier two-sample test
comparison figures and the overview presentation deck. **Those artifacts use
40,000 test-split events** and are therefore kept out of this gallery, which is
built under `test_events_used = 0`. The builder passes an explicit file list to
its compact current-model gallery step and labels the study archive-only.

## Rebuild

```powershell
python exhibition/build_exhibition.py
python exhibition/build_continuation_loss_figures.py
python exhibition/build_family_choice_figure.py
python exhibition/build_diagnostic_trend_figure.py dicos-p9 dicos-p10
python exhibition/build_all_metric_trends.py dicos-p9 dicos-p10
python exhibition/build_external_metric_figures.py
python exhibition/build_metrics_catalog.py
```

The builders read compact audit evidence plus existing validation visualization
payloads. It does not read `legacy/`, the original ROOT tree, or test events.
`manifest.json` records compact current-gallery hashes and QA assertions;
`metrics_catalog.json` validates and hashes the complete exhibition. SVG
identifiers and metadata are normalized so two builds from identical inputs are
byte-for-byte reproducible.

## Scientific boundary

These figures establish structural execution and bounded optimization progress.
They do not establish Geant4 fidelity, and the gallery build uses zero test
events. The full-history loss and diagnostic companions are under
`current/continuation/` and `current/diagnostics/`. Every epoch refresh updates
ordinary loss/metric trajectories and their accepted validation-loss
best-so-far counterparts. Quarantined checkpoints remain visible but are
excluded from accepted standings and running-best traces.

Test-split accounting, repository-wide: 40,000 of the 76,300 test events were
consumed on 2026-07-28 by the isolated classifier two-sample test recorded in
`logs.md` and published under `archive/c2st_20260728/`. A separate 2,000-event paired
diagnostic draw included 200 test events; its overlap with the C2ST sample is
unresolved, so the untouched remainder is exactly bounded at 36,100–36,300.
Those studies measured separability or descriptive agreement, not fidelity, and
no result from them may influence CBSC-ZDC preprocessing, thresholds,
architecture, loss weights, learning rate, stopping, checkpoint selection, or
new visualization selection.

Hardware-screening measurements are nonbinding QA observations and do not
control future training.
