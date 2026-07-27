# CBSC-ZDC calibrated compute-extension protocol

## Question

Does adding exactly two more joint-training epochs improve validation loss for
each of the four calibrated configurations already shown on the visual site?

This is a validation-only exploratory extension authorized after the frozen
A100 screen. It does not revise the historical A100 `NO-GO`, establish physics
fidelity, open the test split, or authorize final training.

## Fixed experiment

Run four jobs concurrently, each on one on-demand NVIDIA T4:

| Family | Parent epoch | New epochs | LR | Effective batch |
|---|---:|---:|---:|---:|
| calibrated LR 3e-5 | 0 | 1–2 | 3e-5 | 24 |
| calibrated LR 1e-4 | 0 | 1–2 | 1e-4 | 24 |
| calibrated LR 3e-4 | 2 | 3–4 | 3e-4 | 24 |
| calibrated LR 1e-4 half-batch | 2 | 3–4 | 1e-4 | 12 |

Every job must preserve its exact paired parent best/last checkpoints, model,
optimizer moments, scaler, RNG, data, split, fixed 50-by-5 validation bank,
loss weights, batch configuration, and FP32 execution. Because every parent
cosine horizon is exhausted, restart the scheduler over exactly the two new
epochs. Use new generation-zero input and output prefixes.

## Primary result

For each family, compare the minimum validation loss in its two new epochs to
the paired parent checkpoint's selected validation loss:

- `clear improvement`: relative decrease is at least 0.5%;
- `marginal improvement`: loss is strictly lower but decrease is below 0.5%;
- `no improvement`: neither new epoch is lower;
- `regression`: final loss is higher than the parent loss.

Report exact values and percentages even when the category is unfavorable.
The main aggregate question passes only if at least one family improves. Also
report whether all four, a majority, or only a minority improve.

## Mandatory QA

At every completed epoch require:

- immutable epoch snapshot and exact checkpoint hashes;
- finite train/validation losses, gradients, optimizer/model tensors;
- paired historical-best retention and checkpoint reload;
- correct cumulative optimizer and restarted-scheduler steps;
- zero nonfinite, negative-energy, support/count, or closure failures;
- at least 15% T4 memory headroom and FP32 8/8 timing;
- the exact same 50 validation conditions and Geant4 deposits, five
  non-identical FastMC draws per condition, and zero test events.

The fixed-sample response, hit-count, longitudinal-profile, and zero-response
metrics are secondary descriptive diagnostics. They cannot turn a validation
loss regression into improvement and are not physics validation.

## Website publication

After each epoch passes all mandatory QA, add it to the full local dashboard.
For the public site, retain exactly one accepted checkpoint per calibrated
family: publish the new epoch only when it becomes that family's lowest
verified validation-loss checkpoint. Never publish an in-flight, failed,
hash-mismatched, or partial epoch.

## Budget

The prior accounted total is `$35.24`. Four jobs have a conservative
four-hour cap each at `$0.85/hour`, totaling `$13.60`; add `$5.00` for
build/storage/management contingency. Worst-case accounted projection is
`$53.84`, leaving `$46.16` under the hard `$100` ceiling.
