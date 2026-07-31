# Agent Operating Contract

1. Read `docs/IMPLEMENTATION_GUIDE.md` before executing commands.
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

17. **One writable location.** Create, edit, move, or delete files *only* under
    `/dicos_ui_home/<account>/sharedfs/work/IOP/julian/Fast MC CBSC`
    (account `julianjuan`; the same directory appears in JupyterLab as
    `sharedfs/work/IOP/julian/Fast MC CBSC`). Everything else on that host —
    including `$HOME` itself, `/ceph`, `/volumes`, and every other directory
    under `sharedfs/work/IOP/` — is read-only to this project.
18. **The source datasets are immutable.** The two files under
    `/dicos_ui_home/<account>/sharedfs/work/IOP/ZDC_ML_20260620/dataset/`
    (`myTree_20251117_765k_0to300GeV_neutron_All.root` and its `_transformed`
    variant) may be **read only**. Never write, move, rename, truncate,
    re-permission, or delete them, and never write any output into that
    directory. They are not this project's to modify.
19. **No other dataset.** Data may come only from those two files. Do not read
    or import any other dataset from the shared filesystem into this project.
20. `scripts/dicos.py` enforces 17 and 18 client-side and must not be weakened
    to work around them. If a task appears to require writing outside the
    permitted directory, that is a signal to stop and ask, not to bypass the
    guard.
21. `_transformed.root` is a dense-grid rebinning with a different geometry
    (6,400 vs 6,390 HCAL channels) and four fewer events. It is incompatible
    with the frozen geometry and must not be used for training, conversion, or
    evaluation. See `docs/DICOS_BACKEND.md`.
