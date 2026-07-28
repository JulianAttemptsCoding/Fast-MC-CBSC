# CBSC-ZDC hardware portability QA

## Scope

This protocol measures whether a frozen CBSC-ZDC experiment runs correctly and
efficiently on a chosen accelerator and software stack. It is backend-neutral:
Vertex AI, Slurm, Kubernetes, a managed training service, and a directly
attached GPU are all valid execution environments.

Hardware QA never grants or denies permission to continue training. It records
compatibility, numerical behavior, memory headroom, throughput, recovery, and
cost evidence for the exact environment measured.

## Freeze before comparison

Record:

1. source commit and dirty-worktree disposition;
2. container digest or fully captured environment lock;
3. frozen configuration hash;
4. prepared-data manifest, split, geometry, and checkpoint hashes;
5. command line and runtime path mappings;
6. GPU model/count, host CPUs/RAM, driver, CUDA, Python, and PyTorch versions;
7. precision mode, batch size, accumulation, workers, seeds, and solver steps.

Changing these creates a new experiment. It is allowed, but must be labeled and
compared explicitly.

## Bounded portability run

Use production-derived training and validation artifacts with zero test events.
Run long enough to include:

- startup and data staging;
- at least one complete optimizer interval;
- an immutable checkpoint snapshot;
- validation on the declared bank;
- checkpoint reload and deterministic resume evidence;
- generation plus the full solver/decode timing path.

## Required observations

- finite model, optimizer, gradients, and selected losses;
- exact artifact hashes and object/file inventory;
- nonnegativity, energy closure, hit-count, support, and layer invariants;
- peak allocated/reserved memory and headroom;
- examples/second, seconds/epoch, data-wait fraction, and 8/8
  solver/decode milliseconds per event;
- checkpoint and mid-epoch recovery behavior;
- train/validation loss and all component losses;
- fixed validation-only visual sample: 50 conditions and five Fast-MC draws per
  condition when that payload is enabled;
- projected cost with assumptions and uncertainty.

## Interpreting results

Classify each result as:

- compatible and reproduced;
- compatible with follow-up QA;
- incompatible for the exact environment/configuration measured;
- inconclusive because evidence is missing.

An incompatibility applies only to the named artifact and environment. Preserve
the failure, fix or vary one declared factor, and run a new labeled experiment.
Do not turn the observation into a global hardware or training decision.

## Historical note

The repository contains immutable July 2026 screening configurations and audit
records created under an older permission-style protocol. Their bytes and
hashes remain provenance evidence. That policy is superseded by
`docs/QA_POLICY.md`; their labels have no current operational effect.
