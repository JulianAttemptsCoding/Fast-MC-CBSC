# Workstation reconciliation — 2026-08-05

## Disposition

`QA PASS` for the repository toolchain. No training, no event generation, no
paid compute, zero test events. Standings and the public site are unchanged.

## What was actually wrong

The workstation checkout was 19 commits behind `origin/main` and additionally
carried a partial, degraded copy of some of those same commits as uncommitted
worktree edits. It had also lost two directories the pod commits do not touch:
all 65 tracked files under `legacy/`, and the untracked `fixtures/`, whose
absence made `pytest` report `1 failed, 203 passed`.

## One corrected intermediate conclusion

An early comparison reported the pod as 19 commits ahead of `origin/main`. That
was wrong. `git rev-list --left-right --count origin/main...HEAD` had been run
before any `git fetch`, so `origin/main` was a cached ref still pinned at
`ca69349`. The prior session's push had succeeded and the remote was already at
`e56aa14`. The durable fix is that the session-start checklist must `git fetch`
before comparing against `origin/main`.

## Disposition of the dirty worktree

Committed whole, before anything else, to `backup/local-worktree-20260805`
(`7a9e39e`). `main` was then fast-forwarded, which restored `legacy/` and
`fixtures/` from their tracked blobs.

Transport was a `git bundle` of `ca69349..HEAD` built inside the permitted pod
workdir, hash-verified on both ends:

```text
_transfer_pod_commits.bundle
17,440,712 bytes
sha256 4bbfd83fbcbcbb4c98496a92249b23d68b063043fdf48779a0b2caafd6f9012b
```

Nothing was lost. Zero files exist in the backup that are absent from `main`.
Of 27 differing files, 17 were byte-identical to their `ca69349` versions. The
10 genuinely locally-edited files were each verified to have their substance
already in `main` — the `invariant_failure_epoch_NNNN` visualization fix, its
test, `AGENTS.md` rules 26 and 27, and a `logs.md` that is 495 lines longer on
`main`.

One exception: `audit/p10_failure_20260804_terminal_analysis.json` was rewritten
by the pod under a different schema. `main`'s version carries the failure
numbers and the epoch-40 diagnostic; the backup carries provenance fields the
rewrite dropped (`source_commit`, `worktree_at_start`, `backend`, `qa_labels`,
`supersedes`). `main`'s version is kept and the dropped provenance stays
recoverable at `7a9e39e`. **Do not delete that branch without deciding what to
do with those fields.**

## Two repaired QA failures

**Stale manifest source hashes.** `exhibition/manifest.json` recorded
`fd24d699…` for `audit/compute_extension_20260727_r2_terminal_analysis.json`
whose content hashes to `2e64cbca…`, plus two more. CRLF was ruled out before
anything changed — the file has 0 CRLF and 132 bare LF, and its as-is and
LF-normalized digests are identical. `build_exhibition.py` regenerated the
manifest to `069476089bc003d2437a7098af6a819596a101017ab1813cfd799c5a84c18bec`.
No threshold or assertion moved.

**A QA contract that required gitignored build output to exist.**
`verify_visual_layout` demanded four files under `dashboard/dist/` that
`.gitignore` line 47 deliberately excludes, because that path is Next.js build
output. The contract failed on this checkout and would fail on any fresh clone,
on both pods, and in CI. The four files are stock Next.js scaffold icons copied
at build time from `dashboard/public/`, whose tracked originals stay in the
exception list.

Fixed by removing the four `dist` entries and adding `dist`, `out`, `.next` and
`.wrangler` to `ignored_directory_names`, beside the `node_modules`, `.venv` and
`.vinext` entries already there, with a written rationale. The guard's purpose —
catching a graphic that escapes `exhibition/current` or `exhibition/archive`
into tracked source — is unchanged; what was removed is a dependency on
untracked generated output. `AGENTS.md` 27 governs declared diagnostic
thresholds; this is a build-artifact inventory and no scientific value moved.

## Verification

```text
compileall src vertex scripts tests exhibition       exit 0
pytest -q                                            257 passed
build_exhibition.py                                  23 visuals
  manifest 069476089bc003d2437a7098af6a819596a101017ab1813cfd799c5a84c18bec
build_metrics_catalog.py                             117 graphics, PASS
  65 current / 52 archive, PNG decoded, SVG parsed, hashes match
build_continuation_loss_figures.py                   exit 0
build_all_metric_trends.py       epochs 16..40, 348 leaves, 8 figures
public repo unittest                                 7 tests OK
public repo npm ci / npm run build                   clean, 1.37 s
live URL                                             HTTP 200
  sha256 7693d96826286da5f5b461796e79e6c5235f1f8c4d07a00c7db9cf5df859b307
```

**Expected test count moves 204 → 257.** 204 was the workstation's stale figure.
The pod session added nine test modules and extended four.

## Standings and boundary — unchanged

```text
calibrated_lr3e4            4.597152  epoch 22  dicos-p7   best
calibrated_lr1e4            4.635220  epoch 38  dicos-p9
calibrated_lr1e4_halfbatch  4.673036  epoch 21  dicos-p7
calibrated_lr3e5            4.843471  epoch  8  dicos-r3
```

`dicos-p10` epoch 40 remains `ARTIFACT QUARANTINED` and is not a valid parent.
No publication was owed and none was made. `PHYSICS VALIDATION NOT ESTABLISHED`;
C2ST AUROC remains 0.77–0.92 at every epoch measured.

## Standing hazard recorded

A `ps -eo pid,ppid,etime,args` probe on the 4090 printed the JupyterLab command
line, which contains `--NotebookApp.token=<value>`. The value was not copied
into any file, commit, log or message. Future process-tree probes on a pod must
filter that command out rather than print it verbatim.
