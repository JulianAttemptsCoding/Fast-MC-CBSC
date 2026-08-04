# Per-epoch evidence pipeline organization QA — 2026-08-04

## Disposition

The per-epoch evidence transaction is organized and QA-passing locally and on
the role-appropriate DiCOS runtime surfaces. No training or event generation
was started and no new test event was used.

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

- Landing router: `exhibition/index.html`.
- Complete current index: `exhibition/current/index.html`.
- Complete archive index: `exhibition/archive/index.html`.
- Compact current-model gallery: `exhibition/current/model/index.html`.
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
| DiCOS 4090 runtime suite | 20 passed; trainer/producer help entry points pass |
| DiCOS 3090 entry point | diagnostic help/import pass; no generation |
| DiCOS workspace | 12 classified entries; 17 run directories; 2 diagnostic namespaces |
| final live state | 4090 0 MiB/0%; 3090 1 MiB/0%; no pipeline process |

The browser limitation is not hidden: no interactive pass is claimed. Direct
raster inspection, complete link HTTP checks, static gallery contracts,
production builds, and data/hash contracts passed.

The shared checkout was fast-forwarded to implementation commit `a3f40bf`, and
the generated `_workspace` index classifies active, historical-preserve,
transient-review, and unclassified paths without moving or deleting evidence.
The first remote suite mistakenly included workstation-only plotting and HTTP
client modules; their optional dependencies are intentionally absent on the
training pod. The corrected pod-runtime suite passed without altering either
GPU environment. The 3090 image also lacks `ps`, so final process proof used a
direct `/proc` scan.

Scientific boundary: optimization and descriptive validation evidence only;
Geant4 fidelity is not established.
