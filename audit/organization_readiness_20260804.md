# Organization readiness — 2026-08-04

## Disposition

The repository is organized for the intended two-GPU topology: the RTX 4090 is
the sole future training writer/producer, and the RTX 3090 drains namespaced
per-epoch checkpoints for event generation and validation-only diagnostics.
This work launched no trainer or diagnostic job.

`dicos-p10` remains quarantined. Its epoch-40 checkpoint is mechanically
readable but is not an accepted parent. The open scientific decision is whether
to freeze a corrected scale-aware diagnostic contract and re-audit it or keep
the current absolute tolerance and its recovery cost. Required visualization
QA was not made nonfatal.

## Guards and reproducibility added

- focused owner-requested rule index covering DiCOS, tokens, continuous
  updates, split rigor, and accident prevention;
- tracked, one-producer-per-tag 4090 checkpoint producer and namespaced 3090
  consumer state;
- atomic invariant-failure evidence before the visualization exception;
- hash-pinned restoration for the 65 ignored dashboard evidence payloads;
- tracked 64,794-byte synthetic ROOT schema fixture with a byte-reproducible
  generator and no production events;
- safe Windows process-liveness check that cannot terminate the probed runner;
- explicit quarantine status in continuation metrics/figures, visible as
  negative evidence but excluded from best-checkpoint selection.

## QA evidence

| check | result |
|---|---|
| source suite | 218 passed; 8 known warnings |
| Ruff / compileall / diff whitespace | pass / pass / pass |
| dashboard evidence | 65/65 hashes and QA contracts verified |
| exhibition | 23 artifacts built; changed figures visually inspected |
| deterministic SVGs | 7/7 identical across consecutive builds |
| internal dashboard | clean install, build, lint, 2/2 rendered tests |
| internal production dependency audit | 0 vulnerabilities |
| public site | 7/7 tests, production build pass, live HTTP 200 |
| 4090 checkout | `cfa1556`; 30/30 relevant tests |
| DiCOS artifact verification | 18/18 checks passed |

The internal dashboard development toolchain retains 12 audit advisories (8
high, 4 moderate) whose reported automatic fixes require breaking/out-of-range
Cloudflare, Vite, React-server, or Drizzle changes. Nonbreaking fixes were
applied; no unreviewed `--force` upgrade was used. The production-only audit is
zero.

## Academic boundary

No new test events were used. The p10 epoch-40 diagnostic used 4,000 validation
events and remains negative evidence; it neither selects a checkpoint nor
establishes Geant4 fidelity. Accepted standings and the public snapshot did not
change, so no new public payload was published.

## Launch status

This audit does not authorize or start training. Before a future launch, declare
the experiment, build/freeze a unique config, verify both process trees and the
one-writer lock, and use only an accepted hash-verified parent. Do not use p10
unless a corrected re-audit accepts it.
