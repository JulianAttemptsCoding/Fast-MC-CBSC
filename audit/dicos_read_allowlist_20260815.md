# DiCOS two-entry read-allowlist audit — 2026-08-15

Status: **verified** at source commit
`9d2d8d12c1e762713ce5860a823dd460d43e1ab7` plus the working-tree changes
hashed in the JSON twin.

## Binding scope

On DiCOS, the project may read only:

1. `/dicos_ui_home/julianjuan/sharedfs/work/IOP/julian/Fast MC CBSC/**`;
2. `/dicos_ui_home/julianjuan/sharedfs/work/IOP/ZDC_ML_20260620/dataset/myTree_20251117_765k_0to300GeV_neutron_All.root`.

The first location is the only writable location. The second is an exact,
immutable source file. Every other DiCOS filesystem location is unreadable and
unwritable to the project, including the source file's parent directory, other
dataset files, home, system, temporary, process, and other groups' paths.

## Enforcement completed

- The exact scope is explicit in `AGENTS.md`, the focused rules, backend guide,
  handoff, pipeline guide, and walkaway runbook.
- `scripts/dicos.py` enforces the read scope for content API reads and remote
  command entry points. It rejects out-of-scope absolute paths, parent
  traversal, home expansion, and forbidden dataset names.
- Active process checks no longer inspect the process filesystem. They consume
  `ps` output and fail closed if a one-writer process tree cannot be proved.
- Setup resolves an interpreter through `PATH`; that runtime invocation does
  not authorize inspection of its installation directory.

## Failure and correction retained

The first focused run produced **8 failed, 67 passed**. The new token parser
mistook the slash in relative paths such as `prep/data` for an absolute path;
two old test expectations also permitted behavior the new rule forbids. The
parser now requires an absolute-path boundary, while parent traversal and
system-file reads remain rejected. No assertion, threshold, or guard was
weakened.

## Verification

- Corrected focused guard suite: **74 passed**.
- Final guard plus external-controller suite: **83 passed**.
- Final guard, external-controller, and policy suite: **87 passed**.
- `compileall` over `scripts` and `src`: exit 0.
- Full repository suite: **768 passed**, 64 known PyTorch warnings.
- `git diff --check`: exit 0; Git emitted only workstation line-ending notices.
- Metrics catalog: **131 graphics, PASS**; all image/manifest/accepted-summary
  checks passed and the current exhibition reached latest observed epoch 114.
- No DiCOS path outside the two-entry allowlist was accessed while applying or
  verifying this change. Test strings name prohibited paths only to prove the
  client refuses them; the tests run locally without DiCOS network access.

At verification, watcher PID 17320 held the live lock. S2-response epoch 4 had
been imported with best validation loss 4.988013; S3-first remained queued.
The existing watcher and queues were not duplicated or interrupted.

**PHYSICS VALIDATION NOT ESTABLISHED.**
