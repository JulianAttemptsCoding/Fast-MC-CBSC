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

**The two closure invariants are bounded on an energy-scaled tolerance, changed
2026-08-05.** The bound is
`max(evaluation.closure_tolerance_gev, evaluation.closure_tolerance_relative *
total_response)`. The absolute floor is unchanged at 2e-5 GeV and still binds
below the 2 GeV crossover; the relative term is 1e-5 in configs frozen from
2026-08-05 onward and **defaults to 0.0**, so a config frozen earlier keeps the
original absolute-only rule and its runs stay reproducible.

The reason is that these invariants compare float32 reductions over thousands of
cells, so the residual is a few units in the last place of the magnitude being
summed and grows with it, while an absolute tolerance does not. At 300 GeV a
single float32 ULP is 3.05e-5 GeV and already exceeded the entire 2e-5
tolerance. This ended `dicos-p10` at epoch 40 on an otherwise perfect epoch.
Every term — absolute floor, relative term, scale, and the effective bound — is
written into each invariant report so any verdict can be recomputed from the
record. **Anything compared across this change is a new declared experiment.**

`RUN/reports/visualization/invariant_failure_epoch_NNNN.json` carries the
reduced invariants, the tolerance terms, the checkpoint SHA-256, and every
per-position row with its `selection_position`, `dataset_index`,
`generation_seed`, `kinetic_energy_gev` and `total_response_max_gev`. Note that
`RUN/reports/invariant_epoch_NNNN.json` is a **different, much smaller** check —
seven fixed conditions against the visualization's 50x5 — so `"pass": true`
there is not evidence that the visualization passed.

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
