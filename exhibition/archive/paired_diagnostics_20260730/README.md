# Paired Geant4/Fast-MC HCAL diagnostics — 2026-07-30

**⚠ Uses the sealed test split, by deliberate one-off exception.** Of the
2000 randomly-sampled events behind these figures, **200 (10%) are from the
sealed test split**, 219 from validation, 1,581 from train. This was an
explicit instruction from the project owner after being warned twice that the
full 764,940-event corpus includes the test split — see `logs.md` for the
full disclosure. This sample feeds no preprocessing, threshold, architecture,
loss-weight, learning-rate, stopping, or checkpoint-selection decision; it is
a one-off visual diagnostic only. It does not establish Geant4 fidelity.

## What this is

2000 real Geant4 events, randomly drawn from the full prepared corpus
(seed `20260730`), each paired with exactly one Fast-MC event generated from
the *same* incident four-momentum by the `calibrated_lr3e4` family's accepted
epoch-4 checkpoint (lowest validation loss of the four calibrated families,
`3f1022b87361b8a14d9f8432273dcd6c72f6a5e599c1be1575e7f37f4014803d`). All six
figures compare HCAL-only quantities (channels 400–6789 of the 6,790-channel
detector).

| Figure | What it shows |
|---|---|
| `01_hcal_cell_energy_spectrum.png` | Pooled nonzero HCAL cell energies across all 2000 events — how many cells carry a given amount of energy, with a Gen/Truth ratio panel. |
| `02_hcal_total_energy_response.png` | Total HCAL energy per event. |
| `03_hcal_energy_fraction.png` | HCAL energy / beam (incident kinetic) energy per event. |
| `04_hcal_hit_multiplicity.png` | Number of HCAL cells with nonzero energy per event. |
| `05_hcal_fraction_vs_energy.png` | Mean HCAL/beam-energy fraction, binned by beam energy. |
| `06_hcal_hits_vs_energy.png` | Mean HCAL hit count, binned by beam energy. |

Built by `exhibition/build_paired_diagnostics_figures.py` from the raw
per-event arrays in `results.npz` (produced on Vertex AI by
`src/cbsc_zdc/cloud/paired_diagnostics.py`, not stored in this repo — see
`vertex_result.json` here for its provenance hashes and the GCS output prefix
it was downloaded from).

## Reproduction

```bash
python -m cbsc_zdc.cloud.paired_diagnostics \
  --data-prefix gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/prep-20260724-r5/artifacts \
  --checkpoint-uri gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/compute-extension-20260727-r1-calibrated-lr3e4-output/progress/epoch_0004/checkpoints/best.pt \
  --checkpoint-sha256 3f1022b87361b8a14d9f8432273dcd6c72f6a5e599c1be1575e7f37f4014803d \
  --output-prefix gs://BUCKET/NEW-UNIQUE-OUTPUT-PREFIX \
  --n-events 2000 --selection-seed 20260730

python exhibition/build_paired_diagnostics_figures.py \
  --results path/to/downloaded/results.npz --out-dir exhibition/archive/paired_diagnostics_20260730
```
