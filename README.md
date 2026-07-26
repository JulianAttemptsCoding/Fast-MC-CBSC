# CBSC-ZDC v2.2

CLI-first, auditable Fast Monte Carlo research scaffold for 65-layer, 6,790-channel single-neutron ZDC showers.

## Status

- active target: raw deposited readout energy;
- condition: neutron four-momentum only;
- training support comparison: 0–300 GeV versus 50–250 GeV;
- primary result domain: 50–250 GeV;
- software QA: 18 tests pass in the bundled environment;
- synthetic CLI chain: training, sampling, structural QA, evaluation, timing, and loss calibration exercised;
- physics status: **not yet trained or validated on the production 765k-event corpus**.

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
- [Complete implementation/training/QA/results guide](docs/IMPLEMENTATION_GUIDE.md)
- [Beginner model walkthrough](docs/MODEL_WALKTHROUGH.md)
- [Loss-weight research and freezing protocol](docs/LOSS_WEIGHT_PROTOCOL.md)
- [Evaluation and decision protocol](docs/EVALUATION_PROTOCOL.md)
- [Active implementation QA report](audit/IMPLEMENTATION_QA_V2_2.md)
- [Revised auditor specification PDF](paper/CBSC_ZDC_Auditor_Specification_v2_2.pdf)
