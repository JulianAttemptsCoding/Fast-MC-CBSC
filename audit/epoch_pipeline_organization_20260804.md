# Per-epoch evidence pipeline organization QA — 2026-08-04

## Disposition

The local per-epoch evidence transaction is organized and QA-passing. No
training or event generation was started and no new test event was used.
Remote checkout synchronization and its no-training smoke checks remain before
the final disposition.

Every epoch refresh now performs one ordered, fail-closed transaction:

1. hash-validate the namespaced 3090 4,000-event validation metric;
2. validate and merge the matching 4090 history/visualization evidence;
3. rebuild train/validation loss vs epoch and accepted running-best loss;
4. rebuild every 3090 metric vs epoch and the same metric for the accepted
   validation-loss best-so-far checkpoint;
5. resolve current-best graphics mechanically from standings and dashboard
   hashes, never from hardcoded epoch filenames;
6. rebuild the compact current gallery and the complete exhibition;
7. validate/hash all graphics and write exact epoch/current audit twins;
8. when and only when an accepted epoch lowers validation loss, derive and QA
   the one-best-snapshot-per-family public release candidate. Commit, deploy,
   workflow, and live verification remain explicit gates.

Epoch 40 remains visible and quarantined. It cannot advance a running-best
trace or become a visualization/public selection. Current accepted best for
`calibrated_lr1e4` remains epoch 38 at `4.635219681489869`.

## Exhibition

- Complete index: `exhibition/index.html`.
- Compact current-model gallery: `exhibition/current.html`.
- Validated scientific graphics: 87.
- Loss/standings graphics: 6, including ordinary loss vs epoch and accepted
  running-best validation loss.
- 3090 large-validation graphics: 18, including four raw metric families and
  four validation-loss-best-so-far counterparts in PNG/SVG.
- Historical C2ST and paired-test graphics remain in separately labeled
  sections and cannot steer current model decisions.
- All 87 linked graphics returned HTTP 200 and decode/parse successfully.
- Consecutive complete offline epoch transactions were byte-identical for all
  60 generated outputs.

## QA

| Check | Result |
|---|---|
| focused Ruff / JSON / compile / whitespace | pass |
| full source suite | 241 passed; 8 known Transformer warnings |
| internal dashboard | production build; 2/2 rendered tests |
| public site | 8/8 tests; production build |
| public selection | four current accepted family bests; unchanged |
| direct figure inspection | pass after two layout corrections |
| interactive browser | unavailable; connection closed during setup/retry |

The browser limitation is not hidden: no interactive pass is claimed. Direct
raster inspection, complete link HTTP checks, static gallery contracts,
production builds, and data/hash contracts passed.

Scientific boundary: optimization and descriptive validation evidence only;
Geant4 fidelity is not established.
