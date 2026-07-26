# CBSC-ZDC FastMC v2.1

**Audited, CLI-first experimental repository for conditional generation of 6,790-channel ZDC neutron showers.**

CBSC-ZDC means **Constrained Budgeted Stochastic Cascade for Zero Degree Calorimeters**. The intended production study is:

- fixed detector: 65 longitudinal layers, 400 ECAL channels, 6,390 HCAL channels;
- corpus: approximately 765,000 non-pencil-beam single-neutron Geant4 events;
- available incident kinetic-energy support: 0-300 GeV;
- primary reporting domain: 50-250 GeV;
- sole raw event condition: `p4_total_gev = [E_total, px, py, pz]`;
- primary target: raw positive hit energy in the frozen 6,790-channel readout order.

## Current scientific status

The repository is ready for **production data-contract inspection, geometry freezing, conversion, staged training, sampling, evaluation, and timing through the CLI**. It is not yet a trained or Geant4-validated FastMC. The included software evidence proves execution and algebraic invariants on synthetic data only. It does not prove fidelity, diversity, reconstruction closure, or speed on the production corpus.

## Audit-driven architecture corrections

v2.1 removes the six blocking defects found in the previous specification:

1. Raw-deposit and thresholded-readout targets are mutually exclusive.
2. The unidentified shared latent was removed; cross-stage dependence is explicit and ancestral.
3. Binary support is no longer a continuous-flow target; one supervised support scorer and one Gumbel-Top-k draw determine support.
4. Numerical decision gates are frozen before final-test exposure.
5. `p4[0]` is total energy, while selection, training ranges, and reports use incident kinetic energy `K_inc = E_total - m_n`.
6. The unobserved reserve/slack channel was removed; modeled response closes directly through layers to cells.

The model never imposes decreasing deposited energy with depth. It permits late starts, gaps, fluctuations, and multiple maxima. Only the remaining accounting budget is non-increasing.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e '.[root,dev]'
cbsc-zdc --help
```

ROOT conversion requires Uproot and Awkward Array. The core model/tests require Python 3.10+, PyTorch, NumPy, and PyYAML.

## Production CLI sequence

Do not skip, reorder, or silently bypass the audit/freeze steps.

### 1. Inspect each production ROOT family

```bash
cbsc-zdc inspect-root /data/zdc/run000.root \
  --schema configs/schema_edm4hep_zdc.yaml \
  > artifacts/root_inspection_run000.json
```

Repeat for every distinct file family. Resolve branch types, units, generator status, sentinels, and tree names before conversion.

### 2. Freeze geometry

```bash
cbsc-zdc scan-geometry /data/zdc/*.root \
  --schema configs/schema_edm4hep_zdc.yaml \
  --output artifacts/geometry
```

Strict mode requires 6,790 nodes with layer counts `(400, 100 x 63, 90)`. It writes immutable arrays, graph edges, provenance, and a geometry hash. Any per-cell position inconsistency above tolerance aborts.

### 3. Convert the complete 0-300 GeV corpus once

```bash
cbsc-zdc convert /data/zdc/*.root \
  --schema configs/schema_edm4hep_zdc.yaml \
  --geometry artifacts/geometry \
  --output artifacts/data \
  --target-mode raw_deposit \
  --min-kinetic-gev 0 \
  --max-kinetic-gev 300
```

Both matched training-range experiments use this same converted manifest and the same split manifest. Do **not** create a separate 50-250 dataset or split.

### 4. Create the leakage-aware split

```bash
cbsc-zdc split \
  --manifest artifacts/data/dataset_manifest.json \
  --output artifacts/splits.json \
  --group-by source_run \
  --seed 20260723
```

`source_run` is preferred. Event hashing is a disclosed fallback only when independent run/job groups are unavailable.

### 5. Audit the entire training split

```bash
cbsc-zdc audit-dataset \
  --manifest artifacts/data/dataset_manifest.json \
  --splits artifacts/splits.json \
  --split train \
  --min-kinetic-gev 0 \
  --max-kinetic-gev 300 \
  --output artifacts/train_data_audit.json
```

Production freezing refuses a sampled audit by default. The response-ratio cap is derived only from this fully scanned training split.

### 6. Freeze configurations by hash

```bash
cbsc-zdc freeze-config \
  --template configs/templates/train_full_0_300_raw.yaml \
  --audit artifacts/train_data_audit.json \
  --geometry artifacts/geometry \
  --manifest artifacts/data/dataset_manifest.json \
  --splits artifacts/splits.json \
  --output configs/frozen_full_0_300.yaml

cbsc-zdc freeze-config \
  --template configs/templates/train_primary_50_250_raw.yaml \
  --audit artifacts/train_data_audit.json \
  --geometry artifacts/geometry \
  --manifest artifacts/data/dataset_manifest.json \
  --splits artifacts/splits.json \
  --output configs/frozen_primary_50_250.yaml
```

The only difference between the matched range runs is `data.train_kinetic_gev`. Validation and test remain 50-250 GeV.

### 7. Staged diagnostic training

Freeze each stage template exactly as above, then run:

```bash
cbsc-zdc train --config configs/frozen_stage_response.yaml
cbsc-zdc train --config configs/frozen_stage_profile.yaml
cbsc-zdc train --config configs/frozen_stage_count.yaml
cbsc-zdc train --config configs/frozen_stage_support.yaml
cbsc-zdc train --config configs/frozen_stage_share.yaml
cbsc-zdc train --config configs/frozen_stage_joint.yaml
```

Each downstream template uses `initialize_from` to load the preceding best checkpoint while freezing upstream modules. `resume_from` is reserved for resuming the same stage and validates stage, model, geometry, optimizer, scheduler, trainable-parameter list, and RNG state.

### 8. Matched final runs

```bash
cbsc-zdc train --config configs/frozen_full_0_300.yaml
cbsc-zdc train --config configs/frozen_primary_50_250.yaml
```

Use identical architecture, optimizer, solver steps, seeds, compute budget, and validation/test bank.

### 9. Structural QA, sampling, evaluation, and timing

```bash
cbsc-zdc qa \
  --geometry artifacts/geometry \
  --checkpoint runs/full_0_300_joint/best.pt \
  --device cuda

cbsc-zdc sample \
  --checkpoint runs/full_0_300_joint/best.pt \
  --geometry artifacts/geometry \
  --kinetic-gev 50 100 150 200 250 \
  --direction 0 0 1 \
  --profile-steps 8 \
  --share-steps 8 \
  --output runs/samples.npz \
  --device cuda

cbsc-zdc evaluate \
  --checkpoint runs/full_0_300_joint/best.pt \
  --geometry artifacts/geometry \
  --manifest artifacts/data/dataset_manifest.json \
  --splits artifacts/splits.json \
  --split test \
  --gates configs/gates_primary.yaml \
  --output runs/primary_test_report.json \
  --device cuda

cbsc-zdc benchmark \
  --checkpoint runs/full_0_300_joint/best.pt \
  --geometry artifacts/geometry \
  --batch-size 1 \
  --device cuda
```

Repeat timing at throughput batch sizes and measure the Geant4 denominator separately under a declared setup.

## Architecture summary

A p4 conditioner feeds: a visible-response hurdle; a train-audited finite total-response model; a direct first-positive-layer head; active-layer support; a masked-simplex longitudinal share flow; categorical hit counts with dynamic feasibility; a geometry-aware support scorer; one exact Gumbel-Top-k sample; and a graph conditional flow for continuous positive-energy shares. The final decoder gives exact zeros outside selected support and closes each layer and event within the frozen floating-point tolerance.

## Evaluation contract

The CLI reports global and energy-binned response bias/resolution, response and hit-count Wasserstein distances, zero-response rates, high-level C2ST, geometry-aware morphology C2ST, structural invariants, and synchronized model sampling time. Publication evaluation additionally requires repeated-condition diversity, memorization/coverage, longitudinal covariance, occupancy/positive-hit spectra, spatial topology, reconstruction closure, three seeds, and matched baselines.

## Software verification included in this bundle

```bash
PYTHONPATH=src python -m compileall -q src tests
PYTHONPATH=src pytest -q
PYTHONPATH=src coverage run --branch --source=src/cbsc_zdc -m pytest -q
coverage report -m
```

Current result: **42 tests passed**. Measured branch-aware coverage is **51% overall**; low coverage is concentrated in production ROOT I/O, CLI orchestration, evaluator orchestration, and long-running trainer paths. A separate synthetic CLI evidence run completes creation, split, audit, provenance freeze, one-epoch joint training, checkpoint reload, invariant QA, sampling, evaluation, and benchmark. Neither test count nor coverage is a physics claim.

## Repository map

- `AGENTS.md` - mandatory operating rules for coding/training agents.
- `configs/` - ROOT schema, frozen-template inputs, gates, Vertex settings, and baseline contracts.
- `docs/CLI_TRAINING_GUIDE.md` - detailed operator runbook and failure handling.
- `docs/DATA_CONTRACT.md` - event, energy, target, geometry, and split semantics.
- `docs/ARCHITECTURE_V2_1.md` - mathematical architecture and decoder.
- `docs/EVALUATION_PROTOCOL.md` - frozen metrics and decision gates.
- `audit/` - audit reconciliation, evidence, QA, residual risks, and traceability.
- `scripts/` - repository verification, production conversion/freezing, and staged-training wrappers.
- `references/` - primary-source register and citation-verification notes.
- `paper/` - revised auditor specification source, bibliography, and PDF.
- `legacy_v2/` - superseded material preserved only for provenance.
