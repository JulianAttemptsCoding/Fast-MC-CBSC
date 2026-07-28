# CBSC-ZDC QA policy

## Purpose

QA exists to say what evidence is trustworthy, what failed, and what should be
investigated next. It does not grant or deny permission to train, continue for
more epochs, change hardware, or run a separately specified experiment.

## Interpretation

- A schema, geometry, hash, invariant, nonfinite, or empty-bin failure
  quarantines the affected artifact. Do not publish, compare, resume from, or
  initialize from it until the defect is understood and a corrected artifact is
  produced.
- A poor loss trend, fidelity metric, throughput result, or visual comparison is
  a scientific observation and a place for further QA. Preserve it and diagnose
  it. It is not a global stop condition.
- A successful software, structural, or optimization check establishes only the
  property measured by that check. It is not physics validation.
- Hardware measurements are backend-specific. A result on a T4, any datacenter
  GPU, or a local accelerator does not control whether another backend may be
  tried.
- Budget remains a user constraint. Before paid work, report the conservative
  projection and obtain or follow the user’s current authorization; never turn a
  historical hardware result into a spending decision.

## Terminology

Use:

- `QA PASS`: the stated property was reproduced;
- `QA FINDING`: a notable measurement or counterexample;
- `ARTIFACT QUARANTINED`: the named output is not trustworthy;
- `FOLLOW-UP QA`: a concrete next check;
- `PHYSICS VALIDATION NOT ESTABLISHED`: test-domain scientific claims remain
  unsupported.

Do not describe a hardware or scientific QA result as permission to continue or
as a prohibition on a separately specified experiment.

The CLI still accepts `--gates configs/gates_primary.yaml` for compatibility.
Treat that file as a versioned set of diagnostic thresholds. Its result is an
evaluation report, not permission to proceed.
