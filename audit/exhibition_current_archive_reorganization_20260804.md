# Exhibition current/archive reorganization — 2026-08-04

## Status

Complete in the canonical repository; final Desktop mirror verification is
recorded in the JSON twin and `logs.md`. No training, event generation, or new
test-event evaluation was performed.

## Contract

- Every exhibition PNG, SVG, raster image, PDF, and substantive HTML visual must
  live under `exhibition/current/` or `exhibition/archive/`.
- `current/` is the complete presently valid visual set. Epoch-dependent plots
  must cover the latest available epoch; accepted-best-only plots must identify
  the current validation-loss best instead of pretending the latest observation
  is accepted.
- `archive/` contains historical, superseded, isolated-test, or otherwise
  non-current visuals. It may not silently feed current checkpoint selection.
- `exhibition/index.html` may remain only as the required landing/router page.
- Dashboard UI icons and active/legacy specification PDFs are explicit needed
  repository-source exceptions outside `exhibition/`; a QA allowlist will make
  those exceptions finite and reviewable.

## Starting inventory

The clean canonical repository contained 117 PNG/SVG graphics and two HTML
gallery pages under `exhibition/`. The current lineage covers observed epochs
16–40; epoch 40 is quarantined, epoch 39 is the latest accepted observation, and
epoch 38 is the current accepted validation-loss best for the external monitor
transaction.

## Final organization

- `exhibition/current/` contains all 65 presently valid graphics: complete
  continuation loss history, all diagnostic trends through epoch 40, the
  accepted-best epoch-38 external metrics and their source figures, and the
  current model/contract graphics.
- `exhibition/archive/` contains all 52 historical graphics plus the historical
  slide deck: the epoch-0–10 common-window comparison, isolated C2ST exhibit,
  paired diagnostics, and the previously unmanifested example graphic.
- `exhibition/index.html` is only a current/archive router. Each scope has its
  own complete generated gallery.
- `exhibition/visual_layout.json` is the exact machine-readable contract for
  visual extensions, scopes, and the finite set of needed outside-exhibition
  exceptions.

## QA evidence

- Offline epoch refresh passed with no generator training, event generation, or
  test-event use. It rebuilt every epoch-dependent plot through epoch 40 while
  preserving epoch 40 as quarantined and epoch 38 as the accepted best.
- Catalog QA passed 117/117 graphics: PNG decode, SVG parse, manifest hashes,
  accepted-summary agreement, scoped-gallery inclusion, two-scope placement,
  current epoch coverage, and router-only root HTML.
- Deterministic local HTML link/image resolution passed. The in-app browser
  transport closed twice before page open, so no browser rendering claim is
  made; original-resolution inspection of representative current loss,
  diagnostic, external-metric, and archived comparison figures passed.
- Full source QA passed: 257 tests with eight known Transformer warnings, Ruff,
  compileall, JSON parsing, and `git diff --check`.
- The internal dashboard production build and both rendered-HTML tests passed;
  all eight public-site tests and its TypeScript/Vite production build passed.
  No publication was triggered because the accepted best did not change.
- The exact Desktop exhibition mirror now has the same 195-file set and 195/195
  matching SHA-256 hashes. Mirroring removed 134 stale pre-layout duplicate
  files from the mirror; each remains recoverable from the canonical current or
  archive scope and Git history. Generated `__pycache__` directories are ignored
  nonvisual build residue; two policy-blocked cleanup attempts removed nothing.
