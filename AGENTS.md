# Agent Operating Contract

The project owner's active-scope index is `docs/FOCUSED_OPERATING_RULES.md`.
It summarizes the DiCOS/token/updating/split-rigor/accident-prevention subset;
the numbered rules below remain binding.

1. Read `docs/IMPLEMENTATION_GUIDE.md` before executing commands, and
   `docs/PIPELINES.md` for how each operation is actually run on this host.
2. Treat `legacy/` as evidence only; never import or train from it.
3. Never hand-edit a frozen configuration.
4. Never use test data for preprocessing, thresholds, loss weights, architecture, stopping, or checkpoint selection.
5. Quarantine any artifact affected by a schema, geometry, hash, invariant,
   nonfinite, or empty-bin failure. Diagnose it before trusting or reusing that
   artifact; the failure does not prohibit independent or corrected experiments.
6. Do not describe a synthetic test pass as physics validation.
7. Record every command, input hash, output hash, environment, correction, and failed attempt in an evidence log.
8. Do not log private hidden chain-of-thought. Log evidence, alternatives, decisions, counterexamples, and verification steps.
9. Use the exact stage order and shared-encoder rules in the guide.
10. Use three seeds for each frozen final condition.
11. Report all seeds and all failed QA checks.
12. Do not weaken a baseline, change output semantics, or omit solver/decode time.
13. Production target remains raw deposited energy unless a separately justified thresholded experiment is frozen.
14. Primary claim domain remains 50–250 GeV even when training uses 0–300 GeV.
15. The final result may be negative; scientific integrity takes priority over a pass.
16. QA findings identify trustworthy artifacts and follow-up work. They never
    grant or deny permission to continue training, change hardware, or launch a
    separately specified experiment.

## DiCOS (ASGC) filesystem contract — binding, no exceptions

The DiCOS shared filesystem is multi-tenant: other groups' data and other
people's work live beside this project's. These limits were set by the data
owner and are not negotiable by an agent.

**Complete DiCOS read allowlist — exactly two locations.** This project may
read, list, inspect, search, stat, or hash only:

- `/dicos_ui_home/julianjuan/sharedfs/work/IOP/julian/Fast MC CBSC/**`;
- the single immutable source file
  `/dicos_ui_home/julianjuan/sharedfs/work/IOP/ZDC_ML_20260620/dataset/myTree_20251117_765k_0to300GeV_neutron_All.root`.

Everything else on the DiCOS filesystem is out of scope, reading included. Do
not inspect directory listings, metadata, contents, hashes, symlink targets, or
filenames anywhere else. In particular, `$HOME`, `/ceph`, `/volumes`, `/tmp`,
every other directory under `sharedfs/work/IOP/`, and the parent directory of
the permitted ROOT file are unreadable to this project. Invoking installed
runtime software is not permission to enumerate or inspect its containing
directory or any other system file.

17. **One writable location.** Create, edit, move, or delete files *only* under
    `/dicos_ui_home/<account>/sharedfs/work/IOP/julian/Fast MC CBSC`
    (account `julianjuan`; the same directory appears in JupyterLab as
    `sharedfs/work/IOP/julian/Fast MC CBSC`). Everything else on that host —
    including `$HOME` itself, `/ceph`, `/volumes`, and every other directory
    under `sharedfs/work/IOP/` — is unreadable and unwritable to this project.
18. **Exactly one permitted external data source, and it is immutable.** The
    only external data file this project may read is
    `/dicos_ui_home/<account>/sharedfs/work/IOP/ZDC_ML_20260620/dataset/myTree_20251117_765k_0to300GeV_neutron_All.root`.
    Read it and nothing else. Never write, move, rename, truncate,
    re-permission, or delete it, and never write any output into that
    directory. It is not this project's to modify.
19. **Everything else in that dataset directory is out of scope**, reading
    included — most importantly
    `myTree_20251117_765k_0to300GeV_neutron_All_transformed.root`, and the
    older 15k/100k/135k files beside it. Do not open, hash, inspect, or import
    them. `scripts/dicos.py` refuses any command that so much as names the
    transformed file.
20. `scripts/dicos.py` enforces the read and write allowlists client-side and
    must not be weakened or bypassed. If a task appears to require any read or
    write outside the two readable locations, stop; do not inspect the path to
    diagnose it and do not work around the guard.
21. `_transformed.root` is a dense-grid rebinning with a different geometry
    (6,400 vs 6,390 HCAL channels) and four fewer events. It is incompatible
    with the frozen geometry and must not be used for training, conversion, or
    evaluation. See `docs/DICOS_BACKEND.md`.

## Evidence and guards

22. **Keep the record in step with the work, as you go.** After every
    meaningful event — launch, epoch, failure, correction, doc or repo change,
    verification run — append to `logs.md`, write the `audit/NAME.{json,md}`
    twin, refresh the diagnostics and figures, and republish the dashboard and
    public site whenever a family's lowest verified validation loss changes.
    Evidence written only at the end of a session is evidence that gets lost.
23. **Never weaken an assertion, guard, threshold, or test to make something
    pass.** That includes exempting a file from a policy test, silencing a
    duplicate-epoch or empty-bin check, and relaxing the filesystem guard in
    `scripts/dicos.py`. Fix the thing the guard caught. Every such guard in this
    repository exists because a specific failure occurred, and the failure is
    recorded next to it.
24. **One writer per run directory, proved from the process tree.** A log's
    contents and a pid file cannot distinguish one wrapper from two. A probe
    whose command line contains the string it searches for matches itself;
    build the token at runtime and exclude your own process and its parent.
25. **Namespace per-run artifacts by run tag.** Runs of one family share
    absolute epoch numbers whenever one resumes from another's best checkpoint,
    so a flat metrics directory silently overwrites the older run.
26. **Make the current state self-contained.** Whenever reasonably possible and
    useful, organize and label every active artifact, metric, figure, decision,
    command, failure, and next action with its purpose, provenance, split,
    checkpoint/run identity, scientific status, and current/superseded/
    quarantined state. Keep the binding rules, current-state audit, handoff,
    catalogs, and operator commands synchronized so a future operator can
    continue safely without reconstructing chat or repository history. Missing
    context is a fail-closed documentation defect: add it before relying on the
    artifact or procedure.
27. **Keep the exhibition in exactly two visual scopes.** Every exhibition
    image, graphic, video, PDF, slide deck, and substantive visual page belongs
    under `exhibition/current/` or `exhibition/archive/`. `current/` must be the
    complete presently valid set and must be regenerated through the latest
    available epoch; accepted-best plots must identify the current accepted
    validation-loss best. `archive/` is historical/superseded evidence and may
    not select or tune a checkpoint. `exhibition/index.html` is only a router.
    Any needed visual outside `exhibition/` must be explicitly labeled in
    `exhibition/visual_layout.json`, finite, and rejected by QA if the exact
    allowlist changes.

28. **A threshold is not a free parameter in either direction, and a threshold
    must be able to express the quantity it bounds.** Rule 23 forbids relaxing
    one to make a run pass. This is the other half: do not silently tighten or
    re-derive one either, and when evidence shows a threshold is *mis-specified*
    -- bounding a quantity whose scale it cannot represent -- record the
    evidence, state the options with their costs, and get the owner's decision.
    Changing it is a declared change: record both config hashes, say plainly
    that anything compared across it is a new declared experiment, and pin the
    new behaviour with tests that also prove the old behaviour still holds for
    configs frozen before the change.

    The worked example is `closure_tolerance_gev`. It was absolute, the residual
    it bounds is float32 rounding that scales with event energy, and at 300 GeV
    a single ULP already exceeded the entire tolerance. It ended `dicos-p10` on
    a structurally perfect epoch. Corrected 2026-08-05 to
    `max(absolute, closure_tolerance_relative * total_response)` with the
    absolute floor unchanged; see `logs.md` and
    `audit/closure_tolerance_20260805_terminal_analysis.{json,md}`.
