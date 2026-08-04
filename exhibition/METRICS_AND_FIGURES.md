# Metrics and figures catalog

This is the deterministic QA index for every PNG/SVG under `exhibition/`.
Every graphic is contained by exactly `current/` or `archive/`.
Current standings exclude quarantined checkpoints; quarantined observations
remain visible as negative evidence.

## Current accepted family standings

| Family | Best accepted | Latest accepted | Latest observed | Status |
|---|---:|---:|---:|---|
| `calibrated_lr1e4` | e38 / 4.635220 | e39 / 4.663275 | e40 / 4.702765 | quarantined |
| `calibrated_lr1e4_halfbatch` | e21 / 4.673036 | e22 / 4.678376 | e22 / 4.678376 | accepted |
| `calibrated_lr3e4` | e22 / 4.597152 | e22 / 4.597152 | e22 / 4.597152 | accepted |
| `calibrated_lr3e5` | e8 / 4.843471 | e10 / 4.874426 | e10 / 4.874426 | accepted |

## Graphics inventory

Validated graphics: **117**.
Current: **65**. Archive: **52**.

| Category | PNG/SVG files |
|---|---:|
| `current_accepted_best_external_metrics` | 9 |
| `current_continuation_and_standings` | 6 |
| `current_external_metric_source_evidence` | 5 |
| `current_model_and_contract` | 11 |
| `current_validation_diagnostics` | 34 |
| `historical_c2st_test_study` | 33 |
| `historical_common_window_snapshot` | 12 |
| `historical_miscellaneous` | 1 |
| `historical_paired_test_exception` | 6 |

## Scientific boundary

Current large-sample diagnostics cover epochs 16–40 on 4,000 fixed validation events per epoch. Quarantined epochs: [40]. These are descriptive,
not a fidelity gate or Geant4 validation.
All **348** numeric diagnostic leaves are present at every epoch and are stored in `all_metric_trends.json`.

## Current accepted-best external monitors

- Accepted checkpoint: `dicos-p9` epoch 38 (`4c967cfc325953afe789d11994d88a0dfc64808908c5617e430608826242e71e`).
- Low-level validation C2ST AUROC: 0.872656 ± 0.011687 across evaluator seeds.
- Fast-MC macro RMS relative four-vector error: 0.346645.
- These validation monitors cannot select or tune the generator.

The current gallery, training decisions, and validation diagnostics use zero
test events. Historical isolated evidence remains separated:

- C2ST study: 40,000 test events.
- Paired diagnostic draw: 200 test events among 2,000 sampled events.
- Overlap is unresolved; untouched test remainder is 36,100–36,300.
- Neither historical study may steer model or checkpoint decisions.

Full per-file paths, dimensions, byte sizes, and hashes are in
`metrics_catalog.json`.
