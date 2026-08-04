# Exhibition archive and Desktop mirror

This document defines the safe organization boundary for presentation metrics,
figures, and graphics. The canonical builders run only in a clean, current
source checkout. A second checkout may hold a byte-identical presentation
mirror without becoming the build authority.

## Locations

- Canonical source: resolve the current `Fast-MC-CBSC` checkout; do not hard-code
  a workstation path in automation.
- Presentation tree: `SOURCE_REPO/exhibition/`.
- Historical archive:
  `https://github.com/JulianAttemptsCoding/Fast-MC-CBSCs-archive`.
- Current workstation mirror requested on 2026-08-04:
  `C:\Users\Julia\Desktop\coding\ASIoP\Fast MC CBSC\exhibition`.

The Desktop checkout may contain unrelated dirty work. Never reset or replace
that repository to update its presentation mirror.

## Ordered transaction

1. Establish source and mirror commit/dirty state. Read `AGENTS.md`, the focused
   rules, and the implementation guide.
2. Create immutable pre-sync snapshots with
   `scripts/archive_exhibition_snapshot.py create`. Snapshot both the canonical
   exhibition and the exact mirror exhibition; never overwrite a snapshot ID.
3. Verify every snapshot hash, commit and push the archive, fetch it, run
   `git fsck`, and prove local/remote commit equality. Do not replace mirror
   bytes before this passes.
4. Run `scripts/refresh_continuation_outputs.py --offline` in the canonical
   source. This updates loss vs epoch, accepted running-best loss, every 3090
   metric vs epoch, best-loss-so-far metric companions, galleries, and catalog
   without DiCOS I/O or event generation.
5. Repeat the full offline transaction and require identical hashes.
6. Copy exactly the files returned by `git ls-files exhibition` into the mirror.
   Remove or move only extra mirror files that are already covered by the
   verified archive. Preserve every non-exhibition dirty-state line.
7. Require identical relative file inventories and SHA-256 values. Serve the
   mirror and verify every gallery link plus representative rendered layout.
8. Update `logs.md`, the audit twin, and the continuing-agent handoff.

## Build authority and mirror QA

`exhibition/manifest.json` intentionally hashes canonical evidence outside the
presentation tree, including audit and dashboard inputs. Therefore a mirror in
an older or dirty repository may correctly fail a catalog rebuild against its
adjacent stale inputs. Do not weaken that guard and do not overwrite unrelated
mirror evidence merely to make the builder pass.

Generation and catalog validation happen in the canonical source. Mirror
validation is exact inventory/hash equality plus static HTTP and rendered-page
QA. A full repository merge is a separately scoped operation.

## Scientific boundary

The current gallery and per-epoch diagnostics use validation evidence and zero
new test events. Historical C2ST and paired-test artifacts stay explicitly
isolated and retain their disclosed test-event accounting. Presentation or
rendering success is not Geant4 fidelity.
