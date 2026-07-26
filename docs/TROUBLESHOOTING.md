# Troubleshooting: Fastest Tests First

## ROOT inspection fails

1. `cbsc-zdc doctor` and confirm `uproot`/`awkward` available.
2. Run `inspect-root` without schema to list keys.
3. Compare exact branch names and tree name.
4. Inspect one file from every production family.
5. Do not rename branches in code merely to force a pass; update the frozen schema and tests.

## Geometry count is not 6,790

1. inspect sentinel IDs;
2. check ECAL/HCAL collection naming;
3. verify duplicate cell IDs and position tolerance;
4. check whether some valid cells never receive hits in the sample;
5. use the detector geometry source if zero-hit channels cannot be inferred from event data;
6. do not train on a silently incomplete graph.

## Conversion rejects many events

Ranked hypotheses:

1. unit mismatch;
2. wrong primary-selection status;
3. variable vertex;
4. cell IDs absent from geometry;
5. negative/sentinel hit conventions;
6. range interpreted as total instead of kinetic energy.

Plot rejection rate versus kinetic energy and source file.

## Split is empty or badly imbalanced

1. count unique source groups;
2. confirm file boundaries are independent jobs;
3. inspect largest group sizes;
4. use `event_hash` only when no valid group metadata exists;
5. do not repeatedly change seed until proportions look attractive.

## Training loss is NaN/Inf

1. rerun CPU with `amp: false`;
2. inspect the named component loss;
3. check target masks for empty/all-invalid batches;
4. reduce learning rate by 3x;
5. inspect response transform and scale;
6. verify no corrupt input shard;
7. confirm gradients are finite before optimizer step.

## Structural QA fails

- support mismatch: support may have been sampled twice or selected zero-budget cells;
- count mismatch: feasibility mask or decoder selection is wrong;
- closure failure: masked softmax or scatter mapping is wrong;
- dust: threshold decoder or target mode is inconsistent;
- outside-valid energy: geometry mask was bypassed.

Treat all as code blockers.

## Response is severely biased

1. train/evaluate response head alone;
2. compare visible rate and total response distribution;
3. verify kinetic versus total energy;
4. inspect response scale and numerical caps;
5. stratify by energy/direction;
6. check whether target is raw deposit or calibrated readout.

## Good total response, bad occupancy

1. count calibration by layer;
2. support BCE and ranking curves;
3. requested versus realized counts;
4. positive-cell energy spectrum;
5. graph edge audit;
6. support family weight sensitivity.

## Good teacher-forced losses, bad free-running showers

This is cascade exposure error. Evaluate generated total/profile/count inputs separately. Do not infer that more joint epochs will necessarily fix it. Consider controlled generated-condition exposure only after identifying the failing transition.

## GPU is slow

1. benchmark batch 1 and larger batches;
2. confirm CUDA and AMP are active;
3. inspect DataLoader wait time;
4. increase workers cautiously;
5. profile graph message passing and solver steps;
6. compare profile/share steps 4, 8, 16 for fidelity-speed tradeoff;
7. investigate the pre-norm Transformer nested-tensor warning only after correctness.
