# Metrics and figures QA — 2026-08-04

## Disposition

The figure, graphic, metric-summary, internal-dashboard, and public-site
presentation layer is organized and QA-passing. No project training, checkpoint
generation, or diagnostic event-generation job was launched. No new test event
was used. Physics validation remains unestablished.

Accepted standings are now defined mechanically as the lowest validation loss
among non-quarantined observations. “Latest accepted” and “latest observed” are
separate fields, so `calibrated_lr1e4` epoch 40 remains visible as negative
evidence without becoming a parent, selection, or public snapshot.

| Family | Best accepted validation checkpoint |
|---|---:|
| `calibrated_lr3e5` | e8 / 4.843471 |
| `calibrated_lr1e4` | e38 / 4.635220 |
| `calibrated_lr3e4` | e22 / 4.597152 |
| `calibrated_lr1e4_halfbatch` | e21 / 4.673036 |

## Organization and presentation corrections

- Rewrote the stale family-choice builder against the current history/status
  contract; it now plots all observed epochs, marks quarantine, and excludes
  quarantine from accepted best and slope summaries.
- Split every family summary into best accepted, latest accepted, and latest
  observed fields.
- Made the diagnostic builder validate schema, split counts, fixed sample,
  checkpoint hash, seed/pool/range, and QA before plotting. Its default lineage
  is the current `dicos-p9 + dicos-p10`, not p9 alone.
- Updated the common gallery to say epochs 0–10 rather than “every epoch,” use
  each family’s actual current accepted visualization payload, and use the
  lowest accepted-loss visual family for distribution and 3D figures.
- Replaced false “test split untouched/sealed” wording with the exact governed
  boundary: zero new decision use, 40,000-event C2ST, 200-test-event paired
  draw, unresolved overlap, and 36,100–36,300 untouched.
- Separated the historical T4 ledger from the future 4090-trainer / 3090-
  diagnostic topology.
- Added `exhibition/METRICS_AND_FIGURES.md` and its machine-readable catalog,
  covering every PNG/SVG path, dimensions, bytes, hash, category, accepted
  standing, and test-use boundary.
- Made active PNG, SVG, JSON, gallery, and manifest writes atomic. SVG IDs and
  date metadata are normalized.
- The public site now defaults to LR 3×10⁻⁴ e22 explicitly rather than calling
  the last allowlist row “latest,” while preserving exactly one accepted
  snapshot per family.

## QA evidence

| Check | Result |
|---|---|
| graphic inventory | 87/87 PNG/SVG files decode or parse |
| exhibition hashes | all source, visual, gallery hashes match |
| historical C2ST hashes | 33/33 manifest figures match |
| complete build reproducibility | 60/60 outputs byte-identical |
| public data reproducibility | 6/6 files byte-identical |
| source suite | 241 passed; 8 known Transformer warnings |
| focused Ruff | all six changed/new Python files passed |
| internal dashboard | production build; 2/2 rendered tests |
| public site | 8/8 tests; production build |
| public data | 4 accepted snapshots; 0 test events |
| final live state | 4090 0 MiB/0%; 3090 1 MiB/0%; no pipeline processes |

Direct visual inspection caught two defects that render/build tests did not:
clipped continuation footers and a 3D log-colorbar collision. Both were fixed
and visually rechecked. A first dedicated-colorbar correction clipped the
figure title/footer under tight bounding; that attempt was rejected and the
final shortened, separated shared colorbar preserves all labels.

The in-app browser-control transport closed during setup and on two retries, so
no interactive browser inspection is claimed. Static frontend contract tests,
production builds, data-contract checks, and direct raster/vector inspection
all passed. GitHub Actions run `30892096628` completed successfully for public
commit `03627a6`; the live page returned HTTP 200 with the expected title/build
asset, and its live manifest reported four snapshots, LR 3×10⁻⁴ e22 as the
default, and zero test events.

A final broad Ruff command mistakenly included legacy source and reported 370
pre-existing, out-of-scope style findings. No lint rule was disabled and no
unrelated file was reformatted; the corrected focused lint scope covered every
changed or new Python file and passed.

## Reproducible entry point

```powershell
python exhibition/build_exhibition.py
python exhibition/build_continuation_loss_figures.py
python exhibition/build_family_choice_figure.py
python exhibition/build_diagnostic_trend_figure.py dicos-p9 dicos-p10
python exhibition/build_metrics_catalog.py
```

Machine-readable twin: `audit/metrics_and_figures_qa_20260804.json`.
