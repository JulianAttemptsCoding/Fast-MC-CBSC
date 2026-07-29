# Geant4 vs Fast-MC comparison and overview deck — 2026-07-28

Presentation-ready material from the classifier two-sample test (C2ST) study.

> **These artifacts use 40,000 events from the test split.** They are kept in
> this subdirectory, separate from the parent `exhibition/` gallery, because that
> gallery is built under `test_events_used = 0` and states so on its own panels.
> Nothing here is included in `exhibition/manifest.json` or `exhibition/index.html`;
> `exhibition/build_exhibition.py` passes an explicit file list to its gallery
> builder and does not scan this directory.

## Contents

| Item | What it is |
|---|---|
| `CBSC_ZDC_FastMC_overview.pptx` | 29-slide overview of the model and its current results, written for a calorimetry audience new to machine learning. Reads without a presenter. |
| `figures/` | 18 Geant4 vs Fast-MC comparison figures binned in incident kinetic energy. |
| `figures_manifest.json` | Corpus hash, geometry hash, event counts, and a SHA-256 for every figure. |
| `C2ST_RESULTS.md` | Full write-up of the discrimination study. |
| `IMPROVEMENTS.md` | Evidence-backed analysis of what to change and why. |

## Headline

A classifier given the full 6,790-channel readout plus the incident four-vector
separates Geant4 from Fast-MC at **AUROC 0.99945 +/- 0.00009**. A control seeing
only the four-momentum scores 0.50363, so the separation is genuinely in the
calorimeter deposits.

The model reproduces the global budget well — total response `+3.0%`, hit
multiplicity `-1.4%`, ECAL fraction `-0.00003%`, depth centroid `-4.0%` — and
misplaces the energy inside each layer: transverse width `+22%` to `+27%`,
hottest-cell share `-41%` to `-56%`.

Measured root cause: the Gumbel-Top-k support draw runs at temperature 1, where
the noise standard deviation of 1.2825 sits against a median within-layer logit
spread of 1.4127 and a median selection-boundary gap of 0.0235. Selection
sharpness is 0.466 against a uniform-random baseline, so roughly half the support
scorer's learned preference is discarded by its own sampling step.

## Status and boundary

All four families are **epoch-4** checkpoints trained on about 4.3% of the
available training split. This is an early snapshot, not a verdict on the
architecture.

These are descriptive comparisons and a separability measurement. They are not
Geant4 fidelity, and physics validation remains not established. Per the
isolation contract recorded in `logs.md`, no result here may influence CBSC-ZDC
preprocessing, thresholds, architecture, loss weights, learning rate, stopping,
checkpoint selection, or visualization; acting on the diagnosis would require a
separately declared experiment.

## Reproduction

Source, tests, and builders live in the study repository:
<https://github.com/JulianAttemptsCoding/Fast-MC-tester>

```bash
python exhibition/build_exhibition.py --corpus corpus.npz --geometry-dir artifacts/geometry
PYTHONPATH=src:presentation python presentation/build_presentation.py
```
