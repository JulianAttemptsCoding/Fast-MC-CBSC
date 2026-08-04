# Exhibition archive and Desktop synchronization — 2026-08-04

## Disposition

Pass. This task was limited to deterministic figure/metric rebuilding,
historical exhibition archiving, exact Desktop exhibition synchronization, and
QA. It starts no training or event generation, performs no DiCOS I/O, and uses
no new test event.

The clean source checkout began at `bfae6c0b96e97cc9fdf364e884b1ee7f04131f04`.
The requested Desktop destination is a separate older checkout at
`ca69349bdb6e10f24a050eda874536eb135642f5` with pre-existing user changes.
Those unrelated changes are preserved. Both complete pre-sync exhibition trees
must be archived with SHA-256 manifests and pushed before only the Desktop
`exhibition/` tree is replaced.

Initial inventory:

| Snapshot | Files | Bytes | PNG/SVG graphics |
|---|---:|---:|---:|
| clean source | 151 | 19,004,353 | 87 |
| dirty Desktop destination | 134 | 16,723,787 | 77 |

Scientific boundary: the figures are optimization and descriptive validation
evidence. They do not establish Geant4 fidelity.

The first archive-helper test run failed 2/3 because verifier paths were
relative to `exhibition/` while manifest paths included that prefix. The path
namespace was corrected; the exact-inventory and SHA-256 assertions remain
unchanged. The overwrite-refusal test already passed, and the failed tests
operated only on temporary fixtures.

The archive clone itself succeeded. The initial combined command nevertheless
exited nonzero because its follow-up Git probes still ran from the parent
directory. Repeating them from the resolved clone verified a valid empty
unborn `main` checkout with the requested GitHub origin.

Both snapshots then passed exact verification. The clean source snapshot has
145 files / 18,844,757 bytes and 147 covered hashes; the dirty Desktop snapshot
has 134 files / 16,723,787 bytes and 136 covered hashes. The first staged-diff
check flagged trailing spaces embedded in historical Matplotlib SVG output.
Those bytes must not be rewritten, so the archive marks `archives/**` as
`-diff -text`. This prevents line-ending normalization and text-diff lint while
retaining the complete SHA-256 verification contract.

Archive commit `041ce150eedb226ccb9a69eddd82dea6067dfd17` is pushed on
`main`. A fresh-clone check proposed with bundled recursive temp cleanup was
rejected before execution. The non-destructive verification fetched the remote,
passed `git fsck --full`, matched local HEAD, `origin/main`, and `ls-remote`, and
rechecked every snapshot hash. The archive is verified before Desktop
replacement.

The exact offline epoch transaction then rebuilt the current figures and
metrics from local immutable evidence. It passed the 87-graphic catalog,
PNG/SVG decode/parse, manifest hashes, accepted-summary agreement, and complete
gallery coverage. Epoch 40 remains quarantined; the accepted best remains epoch
38 at `4.635219681489869`, and no public release is required. The refresh made
no Git-visible exhibition change, demonstrating that the archived source state
was already the deterministic current render.

A consecutive complete refresh changed 0/145 tracked exhibition hashes. The
Desktop overlay copied those 145 files, matched all 145 hashes, and preserved
all 73 non-exhibition dirty-state lines. A broad cleanup command was rejected
before execution; the safe correction moved only four exact, already-archived
Python cache files to a validated temporary backup. The resulting Desktop
`exhibition/` inventory is exact.

The catalog builder cannot be rerun from the Desktop checkout without merging
unrelated repository evidence: it failed closed before writes because the
current manifest pins a clean-source audit hash and the older Desktop checkout
retains its pre-existing dirty version of that audit. That guard was not
weakened and the audit was not overwritten. Generation/catalog QA remains in
the clean canonical source; the Desktop is verified as its byte-identical
presentation mirror.

Static mirror QA passed `index.html`, `current.html`, and all 87 linked graphics
over HTTP. Direct original/high-resolution inspection passed representative
loss, running-best, ordinary metric, best-so-far metric, split-contract, and 3D
deposit figures. The in-app browser connection closed during setup and retry,
so no interactive pass is claimed. A bounded local preview provided the HTTP
checks; after its wrapper ended, the exact child listener was identified and
stopped, and port 8765 was confirmed closed.

Final QA passed focused Ruff, compileall, JSON parsing, diff whitespace, the
complete 244-test source suite, the internal production build and 2/2 rendered
tests, and the unchanged public repository's production build and 8/8 tests.
The Desktop contains 145 files and 87 PNG/SVG graphics with 145/145 canonical
source hashes. No accepted checkpoint changed, so no public release is needed.

Two final wrapper errors were rejected: PowerShell `ConvertFrom-Json` does not
set `$LASTEXITCODE`, and three guessed historical test filenames did not exist,
so pytest ran zero tests. The JSON check uses `try/catch`; the actual test
modules were enumerated with `rg`. No guard or test configuration changed.
The corrected archive/exhibition/offline-refresh selection passed 12/12.
