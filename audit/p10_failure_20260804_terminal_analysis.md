# dicos-p10 terminal analysis — 2026-08-04

## Disposition

`ARTIFACT QUARANTINED`. `calibrated_lr1e4_dicos-p10` completed epochs 39 and
40, then exited during required epoch-40 visualization QA. Neither epoch beat
the inherited p9 best, so accepted standings and the public site remain
unchanged. Nothing is training.

The epoch-40 checkpoint survived and is mechanically readable, but it is not
accepted for reuse until a corrected diagnostic contract is explicitly chosen,
frozen, and used to re-audit it.

## Exact failure

| field | value |
|---|---:|
| configured absolute tolerance | `2e-05 GeV` |
| failing validation conditions | `1 / 50` |
| selection position | `36` |
| dataset index | `894` |
| incident kinetic energy | `192.0687255859375 GeV` |
| maximum generated response | `33.164573669433594 GeV` |
| maximum layer closure residual | `2.6702880859375e-05 GeV` |
| maximum event closure residual | `3.814697265625e-06 GeV` |

Nonfinite, negative, invalid-support, support-mask, count, requested/realized,
and dust counts were all zero.

The evidence supports a diagnostic-design failure rather than a demonstrated
model failure: one absolute tolerance is being applied to float32 reductions
whose numerical error floor changes with energy scale. The threshold itself has
not been changed.

## Preserved checkpoint

```text
_runs/calibrated_lr1e4_dicos-p10/checkpoints/last.pt
epoch 40
SHA-256 4a7583cce169a1cdac206aa1d03a50e41a05444a5172218dbbb89b3227ed1011
inherited best 4.635219681489869
```

“Mechanically resumable” is not “accepted.” The quarantine rule remains in
force.

## Validation-only epoch-40 diagnostic

The RTX 3090 consumer completed its independently namespaced 4,000-event
validation diagnostic:

| metric | value |
|---|---:|
| train / validation / test | `0 / 4000 / 0` |
| diagnostic QA | `pass` |
| high-level C2ST AUROC | `0.7692010416666666` |
| truth zero fraction | `0.00975` |
| generated zero fraction | `0.013` |
| response bias fraction | `0.13064812617194038` |
| hit-count bias fraction | `-0.005861783289965877` |
| longitudinal-profile relative L1 | `0.1958909338178803` |

This is negative validation evidence and is retained as such. It does not
override quarantine, select a checkpoint, or establish Geant4 fidelity.

## Organization fix

`src/cbsc_zdc/eval/visualization.py` now writes a compact atomic
`invariant_failure_epoch_NNNN.json` before preserving the existing fatal
exception. The record includes the checkpoint hash, unchanged tolerance,
reduced invariants, and every validation selection row. A synthetic regression
test proves the failure evidence is written and the normal epoch artifact is
not.

No threshold, random seed, selection, model behavior, or training control flow
changed.

## Open owner decision

Recommended: freeze a scale-aware `max(abs_tol, rel_tol * declared_energy_scale)`
diagnostic in a new experiment, then re-audit the epoch-40 checkpoint. Raising
the absolute threshold or keeping the current threshold with recovery cost are
possible but must also be declared. Making visualization nonfatal is rejected
because it weakens a required guard.

`PHYSICS VALIDATION NOT ESTABLISHED`. Zero test events were used by p10 or its
epoch-40 diagnostic.
