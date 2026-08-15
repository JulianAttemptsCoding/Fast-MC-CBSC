# CBSC-ZDC v2.2

CLI-first, auditable Fast Monte Carlo research scaffold for 65-layer, 6,790-channel single-neutron ZDC showers.

## Status

New here, or picking this up after a break? Read
**[docs/HANDOFF.md](docs/HANDOFF.md)** first — current standings, the defects
found so far, the operations you will need, and the traps that have already
cost time.

- active target: raw deposited readout energy;
- condition: neutron four-momentum only;
- training support comparison: 0–300 GeV versus 50–250 GeV;
- primary result domain: 50–250 GeV;
- software QA: 740 source tests pass in the current environment (2026-08-15);
- production preparation: 764,940 real Geant4 events converted into 187
  content-addressed shards;
- current optimization evidence: four calibrated joint-training families train
  on production-derived train/validation data; the leading family
  (`calibrated_lr3e4`) reaches validation loss 4.483768 at epoch 90;
- visual QA: fixed-condition Geant4-versus-Fast-MC comparisons are available
  locally and on the public site;
- physics status: **optimization and structural execution are established;
  Geant4 fidelity is not yet established**. A classifier separates Fast-MC from
  Geant4 at AUROC 0.77–0.92 at every epoch measured, and the improving loss has
  not moved it.

## Start

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install --no-build-isolation -e '.[root,eval,dev]'
bash scripts/verify_repository.sh
bash scripts/smoke_test.sh /tmp/cbsc_zdc_smoke
```

Then follow [the complete implementation guide](docs/IMPLEMENTATION_GUIDE.md).

## CLI

```bash
cbsc-zdc doctor
cbsc-zdc inspect-root --help
cbsc-zdc scan-geometry --help
cbsc-zdc convert --help
cbsc-zdc split --help
cbsc-zdc audit-dataset --help
cbsc-zdc freeze-config --help
cbsc-zdc train --help
cbsc-zdc calibrate-loss-weights --help
cbsc-zdc qa --help
cbsc-zdc evaluate --help
cbsc-zdc sample --help
cbsc-zdc benchmark --help
```

## Core design

```text
p4 → condition encoder → visible hurdle → total response mixture
   → first/active layers → profile flow → hit counts
   → geometry-aware support scores → one Gumbel-Top-k draw
   → selected-cell share flow → exact budget decoder → 6,790 channels
```

The decoder guarantees exact zeros outside selected support and exact generated energy accounting within floating tolerance. These guarantees do not imply Geant4 fidelity.

## Active documents

- [Agent operating contract](AGENTS.md)
- [Documentation map](docs/README.md)
- [Complete implementation/training/QA/results guide](docs/IMPLEMENTATION_GUIDE.md)
- [Pipelines — every operation with its exact command](docs/PIPELINES.md)
- [The complete v3 record](docs/V3_FULL_REPORT.md)
- [QA policy: checks are evidence, not progression permission](docs/QA_POLICY.md)
- [Hardware portability QA](docs/HARDWARE_PORTABILITY_QA.md)
- [Beginner model walkthrough](docs/MODEL_WALKTHROUGH.md)
- [Loss-weight research and freezing protocol](docs/LOSS_WEIGHT_PROTOCOL.md)
- [Evaluation and decision protocol](docs/EVALUATION_PROTOCOL.md)
- [Active implementation QA report](audit/IMPLEMENTATION_QA_V2_2.md)
- [Revised auditor specification PDF](paper/CBSC_ZDC_Auditor_Specification_v2_2.pdf)
