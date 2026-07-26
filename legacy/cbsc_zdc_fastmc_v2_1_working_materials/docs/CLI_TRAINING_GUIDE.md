# CLI training guide

This guide is the operator procedure for turning the production Geant4 ROOT corpus into frozen CBSC-ZDC runs. It assumes the environment is installed; all remaining model work is command-line execution and review of produced audit reports.

## 0. Environment and repository QA

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[root,dev]'
PYTHONPATH=src python -m compileall -q src tests
PYTHONPATH=src pytest -q
cbsc-zdc --help
```

Expected bundle result: 42 tests pass. Coverage is not a substitute for production ROOT or physics validation.

## 1. ROOT schema gate

```bash
cbsc-zdc inspect-root FILE.root --schema configs/schema_edm4hep_zdc.yaml
```

Run on every file family. Confirm the tree, resolved branch names, branch types, schema contract hash, units, neutron PDG/status rule, and sentinel IDs. A mismatch is a data-contract issue, not something to patch around in training.

## 2. Geometry gate

```bash
cbsc-zdc scan-geometry FILES... \
  --schema configs/schema_edm4hep_zdc.yaml \
  --output artifacts/geometry
```

Review `geometry_manifest.json` and `geometry_provenance.json`. Strict production expectations:

```text
nodes = 6790
layers = 65
layer counts = [400] + [100]*63 + [90]
```

Inspect edge counts, degree distribution, connected components, collection labels, z ordering, and any ganging metadata before accepting the hash.

## 3. Convert once

```bash
cbsc-zdc convert FILES... \
  --schema configs/schema_edm4hep_zdc.yaml \
  --geometry artifacts/geometry \
  --output artifacts/data \
  --target-mode raw_deposit \
  --min-kinetic-gev 0 \
  --max-kinetic-gev 300
```

Review `dataset_manifest.json`: accepted/filtered/rejected counts, source hashes, target, threshold, unit scales, primary selection, fixed vertex, geometry hash, and shards. Intentional range filtering is recorded separately from contract rejection.

## 4. Split once

```bash
cbsc-zdc split \
  --manifest artifacts/data/dataset_manifest.json \
  --output artifacts/splits.json \
  --group-by source_run \
  --seed 20260723
```

Use `event_hash` only when the Geant4 production lacks independent run/job grouping. Record that limitation.

## 5. Full train-split audit

```bash
cbsc-zdc audit-dataset \
  --manifest artifacts/data/dataset_manifest.json \
  --splits artifacts/splits.json \
  --split train \
  --min-kinetic-gev 0 \
  --max-kinetic-gev 300 \
  --output artifacts/train_data_audit.json
```

Do not pass `--max-events` for production freezing. Resolve every warning, especially duplicate IDs, variable vertex, positive response at zero kinetic energy, or response above an assumed cap.

## 6. Freeze every config

Example:

```bash
cbsc-zdc freeze-config \
  --template configs/templates/train_stage_response.yaml \
  --audit artifacts/train_data_audit.json \
  --geometry artifacts/geometry \
  --manifest artifacts/data/dataset_manifest.json \
  --splits artifacts/splits.json \
  --output configs/frozen_stage_response.yaml
```

Repeat for `profile`, `count`, `support`, `share`, `joint`, `full_0_300`, and `primary_50_250`. Do not hand-edit a frozen file afterward; regenerate it.

## 7. Stage sequence

```bash
cbsc-zdc train --config configs/frozen_stage_response.yaml
cbsc-zdc train --config configs/frozen_stage_profile.yaml
cbsc-zdc train --config configs/frozen_stage_count.yaml
cbsc-zdc train --config configs/frozen_stage_support.yaml
cbsc-zdc train --config configs/frozen_stage_share.yaml
cbsc-zdc train --config configs/frozen_stage_joint.yaml
```

Review each `history.json`, `resolved_config.json`, `environment.json`, and `trainable_parameters.json`. Diagnose isolated component failures before joint fine-tuning.

## 8. Pilot before full Vertex job

Set temporary `max_train_batches` and `max_val_batches` in a non-final pilot template, freeze it, and run on the target accelerator. Record peak memory, throughput, data-loader utilization, finite losses/gradients, and checkpoint reload. Do not modify the final frozen configuration based on final-test information.

## 9. Matched training support experiment

```bash
cbsc-zdc train --config configs/frozen_full_0_300.yaml
cbsc-zdc train --config configs/frozen_primary_50_250.yaml
```

The same split and primary validation/test bank are mandatory. Compare across the same three seeds.

## 10. QA and evaluation

```bash
cbsc-zdc qa --geometry artifacts/geometry --checkpoint RUN/best.pt --device cuda
cbsc-zdc evaluate \
  --checkpoint RUN/best.pt \
  --geometry artifacts/geometry \
  --manifest artifacts/data/dataset_manifest.json \
  --splits artifacts/splits.json \
  --split test \
  --gates configs/gates_primary.yaml \
  --output RUN/primary_test_report.json \
  --device cuda
```

A structural pass is necessary but not sufficient. Missing C2ST values or underpopulated energy bins fail the publication gate; increase the frozen evaluation sample, not the gate tolerance.

## 11. Sampling and timing

```bash
cbsc-zdc sample --checkpoint RUN/best.pt --geometry artifacts/geometry \
  --kinetic-gev 50 100 150 200 250 --direction 0 0 1 \
  --output RUN/fixed_conditions.npz --device cuda

cbsc-zdc benchmark --checkpoint RUN/best.pt --geometry artifacts/geometry \
  --batch-size 1 --repeats 100 --warmup 10 --device cuda
```

Repeat timing for throughput batches and report the decoder, solver steps, precision, hardware, serialization, and end-to-end path. Measure Geant4 separately.

## 12. Resume versus initialize

```yaml
training:
  initialize_from: ../runs/stage_response/best.pt  # new stage
  resume_from: null
```

```yaml
training:
  initialize_from: null
  resume_from: ../runs/stage_profile/last.pt       # same stage only
```

The CLI resolves these relative to the config file and rejects simultaneous use.

## Common hard failures

- `geometry hash mismatch`: wrong geometry/dataset/checkpoint combination.
- `audit did not scan complete train split`: rerun audit without sampling.
- `response cap below observed target`: regenerate cap from the full train audit.
- `empty split`: production grouping is inadequate; do not force a random row split silently.
- `active layer has no feasible count`: target/profile/threshold semantics are inconsistent.
- `nonfinite metric`: evaluation is invalid; do not serialize NaN as a pass.


## Wrapper scripts

The repository includes three audited shell wrappers:

```bash
bash scripts/verify_repository.sh
bash scripts/prepare_production_artifacts.sh /data/zdc/*.root
bash scripts/train_staged.sh configs
```

`prepare_production_artifacts.sh` performs inspection, geometry freezing, one-time 0-300 GeV conversion, splitting, full train audit, and freezing of every active template. It stops at the first failed contract and does not hide rejected events. `train_staged.sh` runs the staged chain and optionally the two matched final runs. Review the generated JSON/YAML artifacts before training; wrappers are not permission to bypass scientific gates.
