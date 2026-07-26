# CBSC-ZDC v2.2 A100 viability protocol

## Scope

This protocol decides whether the current model is worth moving from Vertex T4
screening to an external A100 cluster. It does not establish Geant4 fidelity,
open the test split, or authorize the six final-seed runs.

All screening uses the same accepted joint checkpoint, production ROOT-derived
26,624-train/4,096-validation/zero-test bank, fixed 50 validation events, and
five Fast-MC draws per four-momentum condition.

## Wave 1: five matched one-epoch screens

Run concurrently on one on-demand T4 each:

1. default weights, learning rate `1e-4`, effective batch 24;
2. calibrated weights, learning rate `3e-5`, effective batch 24;
3. calibrated weights, learning rate `1e-4`, effective batch 24;
4. calibrated weights, learning rate `3e-4`, effective batch 24;
5. calibrated weights, learning rate `1e-4`, effective batch 12.

The four calibrated jobs have directly comparable aggregate validation loss.
The default-weight aggregate is not numerically comparable to calibrated
aggregates because its component weights differ; it is a control for raw
component behavior, structural behavior, and fixed-sample observables.

## Hard gates

Exclude a candidate on any of:

- failed/cancelled Vertex state, missing or non-immutable output;
- wrong image, resource, prefix, config, checkpoint, split, or hash;
- synthetic, legacy, test, overlap, collision, schema, geometry, or empty-bin
  evidence;
- nonfinite loss/gradient, negative energy, invariant failure, or closure above
  the frozen tolerance;
- checkpoint best/last mismatch, reload failure, optimizer/scheduler/RNG
  inconsistency, or missing update snapshots;
- T4 headroom below 15%;
- missing FP32 8/8 solver/decode timing;
- anything other than 50 fixed validation conditions × five generated draws.

Do not rescue a hard failure by changing a threshold or comparing a partial
artifact.

## Wave-1 Pareto comparison

For every structural pass, report:

- train and validation aggregate loss, interpreted only within the same weight
  family;
- every available unweighted component loss;
- absolute response bias, absolute hit-count bias, and longitudinal-profile
  relative L1 from the fixed 50×5 sample;
- generated zero-response fraction, truth zero-response fraction, stochastic
  draw diversity, examples/s, T4 peak memory, and FP32 8/8 ms/event.

Candidate A is considered no worse than B only when all applicable differences
are within these screening tolerances:

- calibrated-family validation loss: 1% relative;
- response and hit-count absolute bias: one percentage point;
- profile relative L1: `0.01`;
- throughput: 5% relative;
- memory headroom: five percentage points.

A dominates B when it is no worse on every applicable metric and improves at
least one beyond its tolerance. Continue at most two nondominated candidates.
If more than two remain, choose the two with the smallest worst normalized
rank across calibrated validation loss, the three visual metrics, throughput,
and memory. Default control can continue only if it is nondominated without
using its differently weighted aggregate as a cross-family advantage.

## Wave 2: continuation

Resume each selected candidate for two more epochs from its exact accepted
best/last checkpoint pair. Preserve model, optimizer moments, scaler, RNG,
fixed truth selection, epoch numbering, and independent epoch generation
seeds. Use new generation-0 prefixes and the proven mid-epoch recovery path.

Do not restore the one-epoch cosine horizon unchanged. Wave 1 necessarily ends
at `T_max`; stepping that state beyond its horizon makes cosine annealing rise
again. Wave 2 therefore uses the explicit frozen
`training.restart_scheduler_on_resume=true` contract: reset every optimizer
parameter group's LR/initial-LR to the candidate's declared learning rate and
create one fresh monotonic cosine horizon covering exactly the two remaining
epochs. Optimizer moments and every other recovery state stay intact. This is
a pre-result protocol correction based on scheduler-state QA, not a
result-driven hyperparameter change.

## Decision

Issue **A100 GO** only if at least one three-epoch trajectory:

- passes every hard gate;
- improves its comparable validation loss by at least 3% from wave-1 epoch 0
  to its later best, with final loss no more than 5% above that best;
- improves at least two of the three fixed-sample metrics from epoch 0 by at
  least two percentage points for response/hit bias or `0.02` for profile L1;
- worsens none of those metrics by more than five percentage points or `0.05`;
- shows finite, non-identical Fast-MC draws without increased zero-response
  collapse; and
- retains at least 15% T4 memory headroom.

Issue **A100 CONDITIONAL GO** when training is structurally stable, comparable
validation loss improves, and generated draws remain non-collapsed, but the
three-epoch visual statistics are mixed or below the GO improvement threshold.
The condition is a bounded A100 throughput/memory benchmark before longer
training.

Issue **A100 NO-GO** when every continuation hard-fails, diverges, becomes
nonfinite, collapses, fails to improve comparable validation loss, or shows
materially worsening fixed-sample observables.

An A100 has substantially more memory bandwidth and capacity than a T4, but
peak hardware specifications do not predict this sparse graph/flow workload's
speedup. Even after GO, first run 256 train-only batches plus 8/8 decode timing
on the target A100 software stack. Do not extrapolate a full-run cost until
that measurement passes the same invariants.

Hardware and price checks use primary sources:

- NVIDIA A100 specifications:
  <https://www.nvidia.com/en-us/data-center/a100/>
- NVIDIA T4 datasheet:
  <https://www.nvidia.com/content/dam/en-zz/Solutions/Data-Center/tesla-t4/t4-tensor-core-datasheet.pdf>
- Google Cloud GPU pricing:
  <https://cloud.google.com/products/compute/gpus-pricing>

## Scientific boundary

`GO` means “the implementation learns stably enough to justify an A100
experiment.” It never means “physics validated.” Test data and final claims
remain closed until the frozen multi-seed protocol is completed.
