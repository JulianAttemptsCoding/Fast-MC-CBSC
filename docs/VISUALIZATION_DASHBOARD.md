# Epoch visualization dashboard

## Purpose and scientific boundary

The localhost Event Observatory compares a fixed bank of validation Geant4
events with stochastic Fast-MC reconstructions after each enabled training
epoch.

Each comparison group contains:

- one validation Geant4 detector deposit;
- the exact incident neutron four-vector `[E_total, p_x, p_y, p_z]`;
- five independent Fast-MC draws conditioned on that same four-vector;
- per-event summaries and layer profiles;
- immutable checkpoint, geometry, dataset, split, selection, and seed
  provenance.

The default bank contains 50 randomly selected validation conditions. The
selection seed is frozen, so the same 50 conditions are used at every epoch.
Changing truth events every epoch is forbidden because it would confound model
evolution with sample variation.

These plots and their 50-condition statistics are descriptive QA. They are not
checkpoint-selection metrics, acceptance decisions, or physics validation. Test
events are forbidden. The untouched test split remains closed until the full
protocol is frozen.

## Epoch-worker behavior

Newly frozen configs enable:

```yaml
evaluation:
  profile_steps: 8
  share_steps: 8
  visualization:
    enabled: true
    split: validation
    sample_count: 50
    draws_per_condition: 5
    selection_seed: 20260725
    generation_seed: 20260725
    required: true
```

After `last.pt` is safely written for an epoch, the same resident model and T4
generate the visualization bank. No auxiliary Vertex job or additional T4 is
normally needed. The exporter uses explicit forked RNG state, so visualization
does not alter the subsequent training RNG stream.

The exporter stops on:

- any attempt to use a non-validation split;
- empty or non-unique selection;
- invalid neutron four-vector;
- nonfinite or negative truth/generated energy;
- geometry change within a run;
- validation-selection change across epochs;
- structural invariant failure;
- epoch artifact overwrite.

Artifacts are written under:

```text
RUN/reports/visualization/
  geometry.json
  manifest.json
  epoch_0000.json
  epoch_0001.json
  ...
```

The existing immutable Vertex progress upload publishes them beneath the exact
epoch snapshot:

```text
GCS_OUTPUT/progress/epoch_NNNN/reports/visualization/
```

## Start localhost with 300-second sync

From PowerShell at repository root:

```powershell
.\scripts\start_visualization_dashboard.ps1 `
  -SourcePrefix "gs://BUCKET/RUN_OUTPUT_PREFIX" `
  -SyncIntervalSeconds 300
```

Then open:

```text
http://localhost:3000/
```

The hidden sync process checks GCS every 300 seconds. It downloads only the
artifact created in its matching immutable epoch snapshot, verifies the
validation/test-data/QA/draw-count/hash contracts, and refuses to overwrite a
different local epoch or geometry. If the computer sleeps, Vertex continues;
the sync catches up after wake.

To inspect the interface without production artifacts:

```powershell
$env:PYTHONPATH="src"
python scripts/build_dashboard_fixture.py --output dashboard/public/demo
.\scripts\start_visualization_dashboard.ps1
```

The fallback fixture is conspicuously labeled synthetic interface QA and must
never be described as Geant4 or physics validation.

## Dashboard views

- synchronized interactive 3D energy-deposit views for Geant4 plus five
  Fast-MC draws;
- exact four-vector, validation event ID, epoch, stage, checkpoint, and solver
  provenance;
- longitudinal energy profiles across detector layers;
- reconstructed total response, hit count, depth centroid, radial RMS, ECAL
  fraction, and late fraction;
- sample response and hit-count distributions;
- fixed-bank response bias, hit-count bias, and longitudinal-profile distance
  across epochs.

Visual similarity never overrides the full validation report. A visually
plausible event can coexist with failed distributional, diversity,
reconstruction, memorization, or timing studies.
