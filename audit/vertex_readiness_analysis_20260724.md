# Vertex readiness analysis evidence log

- Analysis date: 2026-07-24
- Working directory: `C:\Users\Julia\OneDrive\Desktop\coding\ASIoP\Fast MC CBSC`
- Time zone: Asia/Taipei
- Scope: read-only readiness analysis of the active repository, Vertex training path, and QA gate placement. No training, cloud submission, configuration mutation, or use of `legacy/`.
- Scientific boundary: synthetic tests may establish software/algebraic properties only; they are not physics validation.

## Commands and actions

1. `Get-Content -LiteralPath 'docs/IMPLEMENTATION_GUIDE.md' -Raw`
   - Purpose: bootstrap the repository operating contract before any other shell command.
   - Result: succeeded; guide version identifies CBSC-ZDC v2.2 and mandates the production state-machine order, three final seeds per support condition, frozen artifacts, untouched test evaluation, and stop-on-failure gates.
2. Created this evidence log with the workspace patch mechanism.
   - Purpose: satisfy the repository requirement to record commands, evidence, decisions, failures, and verification without recording private chain-of-thought.
3. `git status --short`
   - Purpose: detect pre-existing workspace edits before any implementation.
   - Result: failed because this extracted repository has no `.git` metadata. No version-control baseline is available; use `SHA256SUMS.txt`, `MANIFEST.txt`, and explicit hashes instead.
4. `rg --files -g '!legacy/**'`
   - Purpose: enumerate the active repository without treating `legacy/` as implementation input.
   - Result: active code, tests, docs, configs, scripts, fixture, audits, paper, and Vertex helper found; no production `artifacts/`, frozen production configs, or run directories found.
5. `Get-ChildItem -Force | Select-Object Mode,Length,LastWriteTime,Name`
   - Purpose: inspect top-level contents and hidden files.
   - Result: repository is an extracted bundle, not a Git worktree; `legacy/` exists but remains excluded.
6. Read the active operational documents and packaging files in one PowerShell loop:
   - `README.md`, `RELEASE_NOTES_V2_2.md`, `pyproject.toml`, `Dockerfile`, `.dockerignore`, `docs/DATA_CONTRACT.md`, `docs/EVALUATION_PROTOCOL.md`, `docs/LOSS_WEIGHT_PROTOCOL.md`, `docs/VERTEX_AI_RUNBOOK.md`, `docs/TROUBLESHOOTING.md`.
   - Result: the scaffold is explicitly not production-trained or physics-validated. Vertex documentation exists but assumes production artifacts and cloud prerequisites that are absent from this bundle.
7. Read all active YAML templates/configs, shell workflow scripts, the Vertex submission helper, and the cloud staging entry point in one PowerShell loop.
   - Result: templates are unfrozen; final defaults use one CUDA GPU, batch 4, accumulation 8, 30 epochs, and end-of-job upload only. Stage order and shared-encoder settings match the guide.
8. Counted lines and bytes for every active Python source and test file.
   - Result: 31 active source modules and 8 test modules; the lowest-covered orchestration areas are ROOT I/O, training, evaluation, and cloud staging.
9. Read every active source module in `src/cbsc_zdc/`, every test, all active configs/scripts, and the active audit summaries.
   - Result: documented contracts are stronger than the currently enforced runtime checks; detailed findings appear below.
10. `python --version`, `python -m pip --version`, `gcloud --version`, `docker --version`, `bash --version`, and manifest line counts.
    - Result: Python 3.13.1; gcloud 573.0.0; GNU bash available through WSL; Docker is not installed; `SHA256SUMS.txt` has 169 entries and `MANIFEST.txt` has 168.
11. Verified every entry in `SHA256SUMS.txt` with PowerShell `Get-FileHash`.
    - Result: 169 listed, 0 missing, 0 mismatched before implementation changes.
12. `bash scripts/verify_repository.sh`
    - Result: failed because WSL has no `python` command. This is an environment-path failure, not a code-test failure.
13. Ran the Windows-equivalent repository verification: compileall, pytest, CLI doctor, and CLI help with `PYTHONPATH=src`.
    - Result: 18 tests passed with the two documented Transformer warnings. Doctor found Uproot, Awkward, scikit-learn, and Vertex SDK; local PyTorch is CPU-only 2.12.0.
14. `cbsc-zdc inspect-root fixtures/outfile_neutron1_schema_fixture.root --schema configs/schema_sample_edm4hep.yaml`
    - Result: the command exited successfully but reported all 19 required branches missing. This is a hard schema failure that the CLI did not convert into a nonzero exit.
15. Inspected actual fixture branch keys with Uproot.
    - Result: fixture keys include collection prefixes, e.g. `MCParticles/MCParticles.PDG`; the sample YAML incorrectly uses `MCParticles.PDG`.
16. Parsed `coverage.json` and searched active code for integrity/gate paths.
    - Result: 66.44% combined coverage, 69.85% statements, 48.33% branches. Coverage is only 13.89% for ROOT I/O, 16.23% for the trainer, and 22.95% for the evaluator.
17. `gcloud config list --format=json` and active-auth inspection.
    - Result: project `asiop-zdc-1`, region default `us-central1`, and one active authenticated account. Account identity is intentionally omitted from this log.
18. Inspected enabled APIs, Artifact Registry repositories, buckets, and service accounts.
    - Result: Vertex AI, Artifact Registry, Cloud Build, and Storage APIs are enabled; two Docker repositories and a regional bucket exist; the default compute service account is enabled.
19. Inspected GCS prefixes and summarized sizes.
    - Result: production data prefix is 25,022,001,408 bytes; prior model prefix is about 6.86 GB; prior runs are about 11.71 GB. Prior model artifacts are not treated as active v2.2 inputs.
20. Located current-style frozen artifacts in GCS by name.
    - Result: no v2.2 `dataset_manifest.json`, `geometry_manifest.json`, split assignment, train audit, or frozen config exists.
21. Described the production ROOT object.
    - Result: `gs://asiop-zdc-1-zdc-reco-us-central1/data/myTree_20251117_765k_0to300GeV_neutron_All.root`, generation `1783683550292251`, size 25,022,001,408 bytes, composite object with CRC32C `lCVUvQ==`.
22. Checked local disk.
    - Result: only 11.03 GiB free, so the 25.02 GB ROOT object cannot be downloaded and converted locally.
23. Checked T4 zone listings and project Compute Engine quota.
    - Result: T4 is listed in four `us-central1` zones. Compute Engine global GPU quota reports zero, but prior Vertex GPU jobs succeeded; Vertex-specific quota must be tested by the pilot.
24. Listed recent Vertex custom jobs.
    - Result: multiple prior jobs succeeded, failed, and were cancelled. They are provenance evidence only and are not reused as active training inputs.
25. Inspected IAM roles for the default compute service account.
    - Result: it has broad `roles/editor`; execution should work, but least-privilege service-account hardening remains recommended.
26. Opened the production ROOT object directly through authenticated GCS range reads with Uproot.
    - First attempt against tree `events` failed. Available keys include `myTree;865`.
    - Latest `myTree` has 764,940 events and 40 vector branches.
27. Inspected production branch types and bounded samples.
    - Primary fields are one-element vectors: `mcPar_PDG`, mass, momentum, stored total energy, and vertex.
    - Hit branches are jagged vectors. HCAL has explicit `hcal_LayerID`.
    - In the first 100 events, the sole PDG is 2112, stored total energy exactly matches `sqrt(p^2+m^2)`, the vertex is fixed, direction varies, and kinetic energy spans approximately 0.118–296.298 GeV.
    - ECAL cell IDs cover 0–399. HCAL cell IDs cover 0–99 plus sentinel `-100`, while `hcal_LayerID` covers 1–64.
    - The first-100 hit-energy sample has no negative or nonfinite energies, and `sum(ecal_energy)+sum(hcal_energy)` agrees with `energySum_ZDC` to `1.78e-14` GeV.
28. A requested 10,000-event remote sample read was too slow; the exact Python process was identified and terminated after repeated nonproductive waits. This failed attempt did not create or modify data.
29. Compared top-level duplicate documents with their active `docs/` or `audit/` copies.
    - Result: all five compared pairs are byte-identical.
30. `python -m ruff check src tests vertex`
    - Result: failed with 408 style/lint findings, dominated by deliberate multi-statement one-line formatting plus a few unused imports. Ruff is installed but is not part of the repository verification script.
31. Attempted Vertex quota inspection with a beta gcloud command.
    - Result: failed because the beta component is not installed in the current noninteractive gcloud environment. No component was installed.

## Early readiness findings

- The repository is code-ready as a scaffold, but not production-run-ready: no production ROOT corpus, production schema, geometry freeze, converted shards, split assignment, train audit, frozen gates, frozen final configs, pilot measurements, or cloud coordinates/credentials are present.
- `vertex_stage.py` uploads the run directory only after normal training completion. A VM loss/preemption before that upload can lose all intermediate checkpoints; this is explicitly acknowledged by the runbook and is a release-blocking risk for long/preemptible jobs unless periodic checkpoint synchronization is added and tested or non-preemptible resources are mandated.
- The Docker base image is tag-pinned but not digest-pinned, and Python dependencies use open lower bounds. Reproducibility requires recording the built image digest and installed environment; a rebuild is not guaranteed identical.
- The final prompt requested by the user must include exact execution commands, artifact layout, stop gates, monitoring, recovery, and required output analysis.

## Production compatibility findings

### Blocking

1. The bundled sample schema fails against its own fixture because branch keys omit collection prefixes.
2. The production ROOT file is not EDM4hep-tree-shaped: it uses `myTree` and flat vector branches, with no generator-status field.
3. HCAL channel identity is `(layerID, cellID)`, not `cellID` alone. The current converter would collapse different longitudinal cells or fail position consistency.
4. There is one monolithic ROOT file and no run/seed branch in the 40-branch tree. `source_group` splitting would produce one group and fail; deterministic `event_hash` is the only supported current fallback, with the leakage limitation disclosed.
5. The local disk cannot hold the production ROOT object. Production inspection/conversion must run in a cloud job with adequate boot disk.
6. Vertex training currently validates only YAML shape. It does not enforce the frozen config’s recorded manifest, split-assignment, geometry, or geometry-hash relationships after staging.
7. The cloud stage uploads only after normal completion. A preemption or crash can lose every checkpoint produced during the job.
8. The evaluator retains every full model output on the accelerator, including logits and flow states, and can exhaust GPU memory on the full test bank.

### Major QA gaps

- `inspect-root` returns zero even when required branches are missing.
- `collection_hits` removes negative/nonfinite rows before the converter can reject or count them; the advertised invalid-hit rejection is therefore ineffective.
- Freeze-config records hashes but does not compare geometry hashes, split hashes, or audit linkage before writing.
- Dataset loading checks shard hashes lazily but does not validate split-manifest or assignment-file hashes/length/codes.
- Training does not check nonfinite validation loss and selects `best.pt` by aggregate teacher-forced validation loss only.
- Stage loss computation builds all component graphs and filters only at the end, wasting stage memory/compute.
- Stage initialization does not enforce the expected preceding stage.
- No checkpoint structural QA is run inside training; only post-training CLI QA exists.
- Publication-required low-level C2ST, correlations/components, repeated-condition diversity, memorization, reconstruction, and baselines remain unimplemented.

## Cloud readiness

- Ready: authenticated project, region, APIs, bucket, Artifact Registry, Cloud Build, Vertex history, production ROOT object.
- Not ready: Docker locally, v2.2 image, corrected production schema/converter, production converted/frozen artifacts, gates frozen from validation floors, checkpoint synchronization, final evaluation memory safety, or multi-seed submission matrix.
- Safe immediate cloud action: build the corrected image with Cloud Build and run a synthetic one-epoch T4 smoke test. This is infrastructure/software QA only.

## Decisions and constraints

- `legacy/` is evidence-only and will not be read for active implementation claims unless a provenance question specifically requires it.
- Frozen configurations will not be edited.
- Test data will not be used to choose preprocessing, thresholds, weights, architecture, stopping, or checkpoints.
- Any schema, geometry, hash, invariant, nonfinite, or empty-bin failure is a hard stop.

## Implementation and verification actions

The initial scope statement above described the audit phase. The user then
explicitly authorized setup and smoke execution. The following actions therefore
include local mutations, Cloud Build, and Vertex submissions.

32. Corrected `configs/schema_sample_edm4hep.yaml` and added
    `configs/schema_production_myTree.yaml`.
    - The fixture schema now includes collection prefixes.
    - The production schema uses `myTree`, optional generator status,
      `energySum_ZDC`, and explicit HCAL `layer_id`.
33. Updated the schema, ROOT I/O, geometry, conversion, dataset, audit, config
    freezing, CLI, trainer, evaluator, and preflight paths.
    - Optional generator status is supported without weakening primary validation.
    - HCAL channel identity is `(layer_id, cell_id)`.
    - Invalid non-sentinel hits fail before filtering.
    - Geometry scanning is streaming rather than retaining all hit positions.
    - Conversion checks finite primaries and stored event-total closure.
    - Split assignment length, codes, and hashes are verified.
    - Frozen artifact relationships and every shard hash are verified before
      training/evaluation.
    - Stage predecessor and shared-encoder contracts are enforced.
    - Nonfinite loss/gradient and per-epoch structural failures stop training.
    - The evaluator no longer accumulates complete accelerator outputs.
34. Added ROOT-fixture, sentinel, and preflight regression tests.
35. Added `.gcloudignore`, full-ROOT preparation/staging entry points, and Vertex
    submission helpers.
36. First full fixture geometry attempt failed with `OverflowError` when comparing
    sentinel `-100` against a `uint64` cell ID. The comparison was corrected to
    avoid unsafe signed-to-unsigned coercion and a regression test was added.
37. One intermediate sentinel regression test failed because the test constructed
    a signed sentinel through an Awkward `uint64` list. The fixture construction
    was corrected; the production logic was not weakened.
38. Corrected fixture verification:
    - strict schema inspection passed for 1,000 events;
    - a non-project-count fixture geometry freeze passed with 65 layers and 9,472
      observed fixture channels;
    - full fixture conversion created four shards and rejected zero events;
    - event-hash split and train audit completed.
    These are fixture/software checks, not detector or physics validation.
39. Created a local synthetic frozen-input smoke bundle at
    `C:\Users\Julia\AppData\Local\Temp\cbsc_vertex_smoke_20260724`.
    - Preflight passed.
    - A one-epoch CPU joint run completed with nine updates.
    - Checkpoint reload, invariants, validation evaluation, and timing completed.
    - Structural checks had zero nonfinite, negative, support/count, and closure
      failures. The poor synthetic fidelity and CPU timing are not physics or
      production-speed claims.
40. Final local regression command:
    `$env:PYTHONPATH=(Resolve-Path src).Path; python -m pytest -q`.
    - Result: 22 passed, with two known Transformer nested-tensor warnings.
41. One later `python -m pytest -q` invocation omitted `PYTHONPATH=src` and failed
    collection with `ModuleNotFoundError: cbsc_zdc`. It was rerun with the required
    environment and all 22 tests passed. This was an invocation/environment error,
    not a test failure.
42. Added CUDA device count/name to the emitted environment and made Vertex
    `ON_DEMAND` scheduling explicit in both submission helpers.
43. Added immutable production-object generation, size, and CRC32C arguments to the
    reusable full-ROOT preparation helper. The already-running r1 prep job predates
    this enforcement, so its emitted `source_identity.json` must be compared
    manually to all three expected values before acceptance.
44. Built Cloud Build image r1:
    - build `f63572e9-813b-4cc6-baa1-dbc56364fca4`, status `SUCCESS`;
    - image digest
      `sha256:84b7c4c17cb5e55cc4809a769121a27c2f8b653f7b78b05f6e38095bf3fc30fa`;
    - base digest
      `sha256:77f17f843507062875ce8be2a6f76aa6aa3df7f9ef1e31d9d7432f4b0f563dee`;
    - Python 3.11, PyTorch 2.6.0+cu124, NumPy 2.2.2, Uproot 5.7.5,
      Awkward 2.11.0, scikit-learn 1.9.0, Vertex SDK 1.162.0, and Storage
      SDK 3.13.0 were observed in the build log.
45. Submitted full production ROOT preparation:
    - resource
      `projects/39719277374/locations/us-central1/customJobs/5551984247922753536`;
    - display name `cbsc-v2-2-full-root-prep-20260724-r1`;
    - input is the exact 25,022,001,408-byte production ROOT URI;
    - output is
      `gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/prep-20260724-r1`;
    - machine `n1-highmem-8`, 200 GB `pd-ssd`, one replica, 24-hour timeout;
    - the image is r1 by immutable digest.
46. Built the environment-evidence image r2:
    - build `ea3e24cf-2811-4095-b2f0-0fa598c8f04e`, status `SUCCESS`,
      duration 2m33s;
    - immutable digest
      `sha256:87b5e13f5c33aaac10a2d37780c50a9aaa2b159523503ea52225e3ec4aa59202`.
47. Created `docs/VERTEX_QA_GATE_PLAN_20260724.md` with the ordered hard-stop
    gate matrix. The target-hardware job is fixed to exactly one on-demand
    `NVIDIA_TESLA_T4`; Spot/low-cost scheduling is forbidden.
48. Built the final source-complete r3 image after adding immutable GCS generation
    enforcement:
    - build `984c79d6-1bfb-4085-b835-6b487a4ba66f`, status `SUCCESS`,
      duration 2m38s;
    - immutable digest
      `sha256:3f5e68721c37fc6c6409d971a0d1967e0d776bac04f627ce4a9a6de185472ebd`.
    This is the only image authorized for the on-demand T4 smoke.
49. Full preparation r1 failed the mandatory geometry gate after reading the full
    ROOT corpus:
    - exact failure: `cell (1, 1, 2) position varies by 46.9354 mm peak-to-peak`;
    - failure artifact uploaded under the r1 preparation prefix;
    - conversion, splitting, freezing, and T4 submission did not run.
50. Ran a bounded 2,000-event production diagnostic over ECAL/HCAL ID, layer, and
    position branches.
    - ECAL repeated IDs have one fixed physical center.
    - HCAL `(layerID, cellID)` readouts can map to multiple discrete, stable
      physical centers. For example layer 1/cell 2 maps to centers separated by
      approximately 46.94 mm in x, 27.11 mm in y, and 1.17 mm in z.
    - This is ganged readout geometry, not continuously varying hit coordinates.
51. Corrected geometry freezing to retain distinct stable physical centers per
    readout and use their unweighted centroid.
    - Hit-frequency weighting is explicitly forbidden because it would introduce
      shower-distribution information into static geometry.
    - The geometry archive and manifest now record physical-position multiplicity,
      ganged-channel count, maximum multiplicity, histogram, and contract.
52. Added the full-data counterexample as a regression contract.
    - `PYTHONPATH=src python -m pytest -q`: 23 passed.
    - targeted Ruff on the changed geometry/test modules: pass.
53. Built corrected r4 image:
    - build `758e7136-86e4-471d-b135-762c52727416`, status `SUCCESS`,
      duration 3m26s;
    - immutable digest
      `sha256:07ad7bb3a39e75c429c28549192438d239da3eec4b8a7b599fcc5961e2ded50d`.
54. Submitted corrected full-ROOT preparation r2:
    - resource
      `projects/39719277374/locations/us-central1/customJobs/3440077497662701568`;
    - output
      `gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/prep-20260724-r2`;
    - source generation, size, and CRC32C are mandatory command arguments;
    - scheduling strategy is explicitly `ON_DEMAND`.
55. Added CUDA device total-memory bytes to the environment evidence so the T4
    headroom gate is computed from the worker, not a nominal product value.
56. Built r5, the image authorized for GPU smoke:
    - build `6230db2a-a596-4eb2-b7f6-124ef51f8623`, status `SUCCESS`,
      duration 3m7s;
    - immutable digest
      `sha256:62ba7632c85e40df73f3844944a4492dd124365cd31ba3fb7fc7f7134c370d4d`.
57. Added a postflight resource gate after reload, sample, benchmark, and
    validation. It records actual device name, total memory, peak allocated
    memory, and headroom and fails below 15% or on CPU fallback.
58. Built r6, superseding r5 for GPU smoke:
    - build `aa76fcc9-1d6c-4a45-b9a4-291093c24dbf`, status `SUCCESS`,
      duration 3m24s;
    - immutable digest
      `sha256:ba479da20db59fb750719de109a12d622581b00c54901745a1cbe6acfc15f13c`.
59. Corrected preparation r2 passed the full ganged-geometry scan and emitted
    the first conversion marker, then native code exited with `SIGSEGV` (status
    139) on the 2,048-event first chunk. No GPU work was submitted.
60. Vertex automatically reprovisioned the identical failed r2 job. It was
    explicitly cancelled after the retry began to prevent an unnecessary second
    full scan and identical crash.
61. Split geometry and conversion chunk controls:
    - geometry remains 2,048 events/chunk;
    - conversion is reduced to 128 events/chunk;
    - `faulthandler` is enabled;
    - first-chunk substage markers identify primary, hit validation, ECAL mapping,
      and HCAL mapping;
    - a passed geometry gate is uploaded before native conversion begins.
62. The 128-event path completed a fresh 1,000-event fixture geometry/conversion:
    four shards, 1,000 accepted events, and zero rejections.
63. Built r7:
    - build `f466750a-8b8d-49ae-894a-888f299eb660`, status `SUCCESS`,
      duration 3m39s;
    - immutable digest
      `sha256:83f25fef006f566c6d2e8bc537716f02a5fdc27c1d360b133c2fda603aebd3a6`.
64. Submitted full-ROOT preparation r3:
    - resource
      `projects/39719277374/locations/us-central1/customJobs/2318329346726559744`;
    - output
      `gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/prep-20260724-r3`;
    - one on-demand CPU worker; immutable source identity mandatory.
65. r3 reproduced and uploaded the full geometry gate:
    - geometry hash
      `e22d4cfb1e9293a33dd13151587910268ba64cd8efbcdb7a835a7442f2edcb4b`;
    - 6,790 nodes, 65 layers, exact project counts;
    - 2,400 ganged channels, maximum multiplicity 4;
    - histogram: 4,390×1, 1,950×2, 444×3, 6×4 physical centers;
    - geometry archive size 564,653 bytes.
66. `faulthandler` localized the r3 native crash to the HCAL
    `map_collection` structured-array allocation immediately after ECAL
    structured search. Normal geometry size/multiplicity rules out geometry
    memory pressure; the structured NumPy lookup path is the evidence-backed
    cause.
67. Replaced structured-key mapping with plain `uint64` searches grouped by
    `(subdetector, layer_id)`. This retains full-width cell-ID support and
    explicit unknown-group/unknown-ID failures. The revised mapping passed the
    1,000-event fixture with identical shard hashes and zero rejections.
68. Added optional hash-verified reuse of a passed geometry prefix. Reuse checks
    URI, generation, size, CRC32C, source SHA-256, schema hash, strict counts,
    source hash in the geometry manifest, and recomputed geometry content hash.
69. Built r8:
    - build `7fe33344-06e4-46d3-a482-7fd3f9b25e20`, status `SUCCESS`,
      duration 3m30s;
    - immutable digest
      `sha256:1da943cab83184da11233d2d9b2b1d43b0411a206f848ac4a93153d70859e736`.
70. Submitted preparation r4 using the preserved r3 geometry:
    - resource
      `projects/39719277374/locations/us-central1/customJobs/8852770931064438784`;
    - output
      `gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/prep-20260724-r4`;
    - reused geometry input remains the non-training r3 prefix and must pass all
      reuse checks before conversion.
71. Preparation r4 completed both plain-`uint64` first-chunk mapping stages,
    then stopped at the event-accounting gate:
    - exact entry-0 residual: `0.0194756` GeV;
    - no native crash occurred;
    - the failed prefix remains diagnostic-only.
72. Ran a read-only authenticated 128-event production diagnostic against the
    pinned ROOT object:
    - `sum(ecal_energy)+sum(hcal_energy)` agrees with `energySum_ZDC` to
      `1.7763568394002505e-14` GeV;
    - 123/128 events contain positive energy on sentinel cell ID `-100`;
    - entry 0 has `0.019475594743166624` GeV sentinel energy, exactly explaining
      the failed residual;
    - maximum sentinel energy in the sample is `0.23446324308687538` GeV.
73. Corrected the accounting contract without weakening a tolerance:
    - all stored hits, including sentinel non-readout deposits, must close to
      `energySum_ZDC` within `1e-6` GeV;
    - mapped detector nodes separately must close to raw non-sentinel readout
      hits within `1e-6` GeV;
    - excluded sentinel event count, total energy, and maximum event energy are
      recorded in the dataset manifest;
    - any negative/nonfinite energy now fails even when its ID is a sentinel.
74. Local verification after the accounting correction:
    - the first test attempt omitted `PYTHONPATH=src` and failed import
      collection; no code or data changed;
    - the contract-correct invocation passed: 24 tests, with only the two known
      PyTorch Transformer warnings;
    - `python -m compileall -q src vertex tests` passed.
75. Built r9:
    - build `05eed7df-ad02-440c-9706-0f1895e10e05`, status `SUCCESS`,
      duration 2m43s;
    - immutable digest
      `sha256:5f3af141fd0d79140daa874c00eb091984a6316b3aedb69d7ffcc38a1257301a`.
76. Submitted preparation r5:
    - resource
      `projects/39719277374/locations/us-central1/customJobs/1981826012068970496`;
    - output
      `gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/prep-20260724-r5`;
    - source generation/size/CRC and reused geometry are pinned;
    - scheduling is on-demand on one CPU worker.
77. Added a server-side, fail-closed automatic continuation path before the
    desktop sleep deadline:
    - preparation is polled through the Vertex API;
    - the same production identity, geometry, conversion, split, audit, pilot,
      and shard-verification gates are rechecked;
    - a GCS generation-zero lock prevents duplicate smoke submission;
    - only one on-demand `NVIDIA_TESLA_T4` is permitted;
    - orchestration result/failure artifacts are written to a separate prefix.
78. Local verification after adding the coordinator:
    - 24 tests passed with only the two known Transformer warnings;
    - package and launcher compilation passed.
79. Built r10:
    - build `89f1d531-b090-4244-91a4-fac6098267cb`, status `SUCCESS`,
      duration 3m40s;
    - immutable digest
      `sha256:4ada18f7e352a418f817ca4df95631357642004201091c3cd2d6360a97301f07`.
80. Coordinator submission corrections:
    - the first asynchronous SDK call returned before resource creation; a
      display-name lookup proved no job existed before retry;
    - Vertex rejected a 50 GB disk, then rejected unsupported
      `e2-standard-2`; neither rejection created a resource or GCS object;
    - the launcher now uses supported `n1-standard-4`, 100 GB `pd-standard`,
      and synchronous API submission without waiting for job completion.
81. Submitted automatic coordinator:
    - resource
      `projects/39719277374/locations/us-central1/customJobs/9206444239301378048`;
    - state at spec verification: pending;
    - strategy `ON_DEMAND`, one CPU replica, r10 immutable digest;
    - status prefix
      `gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/orchestration-20260724-r1`.
82. Created and then updated a 10-minute Codex heartbeat
    `resume-vertex-smoke-qa`. It resumes this thread after wake, monitors the
    existing coordinator, forbids duplicate submission, and performs the final
    independent artifact analysis.
83. The coordinator reached `JOB_STATE_RUNNING` and emitted repeated
    `prepare state=JOB_STATE_RUNNING` polls. At the same checkpoint,
    preparation r5 had converted 524,800/764,940 events with accepted equal to
    processed. The desktop is no longer on the execution critical path.
84. Preparation r5 reached `JOB_STATE_SUCCEEDED`.
    - Independent `vertex/verify_prepare_output.py` passed all 764,940 events
      and all 187 shard hashes.
    - Split counts: 612,482 train, 76,158 validation, 76,300 test.
    - Pilot assignment counts: 338 train, 104 validation, 0 test, 764,498
      excluded; evaluation-range selection is 338 train, 64 validation, 0 test.
    - Maximum all-hit/event-total residual:
      `1.3500311979441904e-13` GeV.
    - Maximum mapped-readout/non-sentinel residual:
      `1.1368683772161603e-13` GeV.
    - Sentinel non-readout evidence: 738,898 events,
      13,251.328791066537 GeV total, 1.647373832954901 GeV maximum/event.
    - Verification report: `audit/verified_prepare_r5.json`.
85. Automatic coordinator r1
    `projects/39719277374/locations/us-central1/customJobs/9206444239301378048`
    failed before claiming the smoke prefix.
    - Its verifier incorrectly required the pilot count dictionary to omit the
      legitimate `excluded` count.
    - Preserved failure:
      `gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/orchestration-20260724-r1/orchestration_failure.json`.
    - The smoke prefix remained empty; no T4 was submitted.
86. Corrected the pilot-count verifier to require all four exact counts,
    including `excluded=total_entries-442`.
    - Added a regression test for correct, wrong-excluded, and nonzero-test
      cases.
    - Local verification: 25 tests passed; only the two known Transformer
      warnings; compileall passed.
87. Built r11:
    - build `df8e4320-f6f1-4979-9f92-7f85e0ff27b4`, status `SUCCESS`,
      duration 2m35s;
    - immutable digest
      `sha256:45ff337d8c4b1b34e936a24926a8fa495aebfb06187e75965fab9624d1f402f1`.
88. Corrected coordinator r2
    `projects/39719277374/locations/us-central1/customJobs/5475007438862155776`
    passed preparation verification, atomically claimed the smoke prefix, and
    submitted one on-demand T4 job:
    - training pipeline `7972253432239095808`;
    - custom job `5080522458025426944`;
    - exact resources: one `NVIDIA_TESLA_T4`, `n1-standard-8`, one replica,
      `ON_DEMAND`, r11 immutable digest.
89. The first T4 full-architecture smoke failed the mandatory gradient gate.
    - CUDA was available on exactly one Tesla T4 with 15,655,829,504 bytes,
      CUDA 12.4, cuDNN 90100, and PyTorch 2.6.0+cu124.
    - Full preflight passed and verified all 187 shards.
    - Forward loss was finite, but the first AMP backward pass produced a
      nonfinite gradient norm at epoch 0, step 0.
    - No optimizer update or checkpoint was accepted.
    - Preserved output:
      `gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/smoke-20260724-r1`.
90. Froze a full-precision retry without editing a frozen YAML.
    - New unfrozen template:
      `configs/templates/pilot_full_architecture_smoke_fp32.yaml`, SHA-256
      `bb09dff2040906d98d5df5e116a344c12d7212836090d66ee33cbcd6f7fc9633`.
    - The only scientific change is `training.amp: false`; data, architecture,
      seed, optimizer, losses, batch, and epoch count are unchanged.
    - New frozen config SHA-256:
      `e75f1bda7140a00b9caf04bf9ee574c034879e7a935dfe32a42a983680511f31`.
91. The first GCS wildcard copy flattened the directory hierarchy into
    `prep-20260724-r5-fp32`; this unusable prefix is preserved and excluded.
    A corrected `gcloud storage rsync --recursive` created
    `prep-20260724-r5-fp32-r2` with the original hierarchy, 205 copied source
    objects plus the two newly frozen FP32 config/template objects.
92. Submitted FP32 on-demand T4 smoke:
    - training pipeline `5105571531929419776`;
    - custom job `4964365651620659200`;
    - input
      `gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/prep-20260724-r5-fp32-r2`;
    - output
      `gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/smoke-20260724-r2-fp32`;
    - state at submission/spec check: pending, then running;
    - exact resources remain one on-demand T4 and one replica.
93. FP32 custom job `4964365651620659200` reached
    `JOB_STATE_SUCCEEDED`.
    - Vertex start/end: `2026-07-24T16:24:13Z` /
      `2026-07-24T16:40:48Z`.
    - The terminal job spec independently confirmed `ON_DEMAND`, one
      `n1-standard-8`, one `NVIDIA_TESLA_T4`, one replica, 100 GB `pd-ssd`,
      the r11 immutable image, the FP32 input/output prefixes, and the expected
      service account.
    - GCS contained exactly 16 required output objects, 58,800,504 bytes, with
      both checkpoints and no `vertex_failure.json`.
94. Downloaded and hashed the complete smoke output.
    - The first `gcloud storage cp --recursive ... audit/vertex_smoke_fp32_r2`
      command failed because this gcloud version requires the destination
      directory to exist.
    - Created that exact directory and repeated the copy successfully. No GCS
      object was modified.
    - Local output:
      `audit/vertex_smoke_fp32_r2`.
95. Independently verified the successful result.
    - The staged input manifest contains 207 objects, 5,944,363,214 bytes,
      187 shards, no `legacy/` path, and no test-named path.
    - GCS and local FP32 config hashes matched. A field-by-field frozen/runtime
      comparison found only permitted machine-local paths, run directory, and
      staging provenance changes.
    - Preflight verified 187/187 shards and selected 338 train, 64 validation,
      and zero test events.
    - One FP32 joint epoch completed with finite train loss
      `24.04530804497855`, validation loss `20.07763433456421`, 84 updates,
      57.4816040180001 seconds, and 5.880142104144429 examples/s.
    - Best and last checkpoints exist. The postflight built a new model,
      reloaded best, sampled five fixed conditions, benchmarked, and evaluated
      validation only.
    - Peak T4 allocation was 7,848,525,312 of 15,655,829,504 bytes, leaving
      `0.49868352168789687` headroom.
    - Epoch, fixed-condition, and validation invariant reports all passed with
      every discrete failure count zero and all closure residuals below
      `2e-5` GeV.
96. The first independent raw-array sample recheck could not run because the
    local FP32 freeze-input folder contained the geometry manifest but not
    `geometry.npz`.
    - Downloaded the pinned 564,653-byte geometry object from the accepted FP32
      input prefix; its SHA-256 is
      `c6c02f3c84f5e02e70d2ca3fb894dd8cae899e1afc9100e34334d8ee5c922bf1`.
    - The repeated check found zero nonfinite, negative, support, or count
      failures and independently reproduced layer closure to
      `4.76837158203125e-07` GeV.
97. Final local verification and reporting:
    - `PYTHONPATH=src python -m pytest -q`: 25 passed, with only the two known
      Transformer warnings.
    - `python -m compileall -q src vertex tests`: passed.
    - Machine-readable report:
      `audit/agent_vertex_smoke_analysis_20260724.json`.
    - Human report:
      `audit/agent_vertex_smoke_analysis_20260724.md`.
    - QA plan, execution handoff, and exact copy/paste next-agent prompt were
      updated with terminal job IDs, hashes, measurements, failed gates, and
      the structural-versus-physics boundary.
98. Final workspace consistency checks:
    - `git status --short` could not run because the supplied workspace has no
      `.git` directory; no Git-state claim is made.
    - The first Windows `rg` check used a wildcard filename argument that is not
      expanded by this invocation and returned an invalid-filename error.
    - Repeated `rg` with all four explicit filenames; terminal job ID, state,
      config hash, and final dispositions are consistent across the handoff,
      prompt, and both analysis reports.
99. Confirmed all five final handoff/report files exist and the downloaded
    smoke folder has no `vertex_failure.json`. Deleted the now-obsolete
    `resume-vertex-smoke-qa` heartbeat after completion so it cannot submit or
    monitor redundant work.
100. Reviewed the independent verification artifacts written on 2026-07-25:
     - `audit/next_agent_vertex_smoke_verification_20260724.json`;
     - `audit/next_agent_vertex_smoke_verification_20260724.md`;
     - `audit/next_agent_verified_prepare_r5.json`.
     Their identities, counts, hashes, resource measurements, invariants, and
     four dispositions match the prior accepted evidence.
101. Rejected the proposed training matrix as executable without correction.
     - It assigned the full 612,482-event train split and up to 30 epochs to
       every diagnostic stage. At the measured 5.8801 examples/s, one joint
       epoch projects to approximately 28.9 hours before any tuning.
     - All stock stage/final templates still enabled AMP, despite the preserved
       nonfinite AMP gradient failure.
     - Vertex runtime staging did not rewrite or hash predecessor/resume
       checkpoints, so stages 2-6 could not safely consume the previous job.
     - The container uploaded only at terminal job exit, so a long worker loss
       could discard all completed epochs.
     - Loss calibration did not fail when one or more expected components
       produced no finite positive shared-encoder gradient.
102. Hardened the active training path before authorizing another GPU job:
     - Vertex accepts collision-checked overlay prefixes for per-job configs
       and checkpoints without duplicating the 187-shard base prefix.
     - `initialize_from_relative` and `resume_from_relative` require a pinned
       lowercase SHA-256 and resolve only inside the staged input root.
     - Every completed epoch uploads an immutable generation-zero snapshot
       under `OUTPUT/progress/epoch_NNNN`.
     - A generic training postflight reloads best, samples the configured 8/8
       solver path, runs invariants, records solver/decode timing, and enforces
       at least 15% actual T4 memory headroom.
     - Calibration now stops unless every expected component has a finite,
       positive gradient-norm median.
103. Added regression tests for checkpoint path containment, checkpoint hash
     mismatch, successful staged checkpoint resolution, and incomplete
     calibration.
     - `PYTHONPATH=src python -m pytest -q`: 29 passed with only the two
       documented Transformer warnings.
     - `python -m compileall -q src vertex tests`: passed.
104. Built the first long-run-hardening image:
     - Cloud Build `910231cd-75e5-41a0-8824-3ff14dc0a6f0`;
     - status `SUCCESS`, duration 2m31s;
     - immutable digest
       `sha256:0051cee228b6b4502a7bd5ce68fea09bde97a4a401b80ee03098fa4809e703d3`.
105. Froze a new FP32 target-hardware pilot without editing any prior frozen
     config.
     - Template:
       `configs/templates/pilot_training_hardening_batch6_fp32.yaml`.
     - Frozen config:
       `audit/training_hardening_inputs/configs/frozen_pilot_training_hardening_batch6_fp32.yaml`.
     - Frozen SHA-256:
       `84f3bf52f1dad1d5a334294c95cdfe2dcbb473e42bba75b12ca298d29eb4badb`.
     - The pilot retains the full architecture and verified production-derived
       338/64/0 pilot selection, uses FP32, batch 6, one epoch, and configured
       8/8 postflight solver/decode QA.
106. Confirmed both the overlay-input and output prefixes were empty, uploaded
     the frozen config with generation-match zero, and submitted exactly one
     on-demand T4 pilot:
     - training pipeline `3304430748143976448`;
     - custom job `2224189161156378624`;
     - image is the r12 immutable digest;
     - one `n1-standard-8`, one `NVIDIA_TESLA_T4`, one replica, 100 GB
       `pd-ssd`, `ON_DEMAND`;
     - output
       `gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/training-pilot-20260725-r1-output`.
107. Derived a bounded diagnostic split from the accepted full preparation
     artifacts, using only train and validation assignments.
     - Split manifest:
       `audit/training_hardening_inputs/artifacts/training_pilot_splits.json`,
       SHA-256
       `a4d0967597bee525843d81647bd259deee7c2e908d25d2b1df78a8179526b0b3`.
     - Assignment:
       `audit/training_hardening_inputs/artifacts/training_pilot_splits_assignments.npz`,
       SHA-256
       `084f0dfd86e488c63bb41ea50d6783ad22eb57a322288c075a94b1ec12dd3714`.
     - It contains exactly 2,048 train and 512 validation events in each of
       13 energy bins: 26,624 train, 6,656 validation, zero test, and 731,660
       excluded.
     - The 50--250 GeV validation selection contains 4,096 events.
     - Complete selected-train audit:
       `audit/training_hardening_inputs/artifacts/training_pilot_train_audit.json`,
       SHA-256
       `ebc951971dc3ad25f9738b2d150d54d5b3fcc9518d039c2a33420f53a409496f`;
       zero negatives, no empty energy bin, response cap ratio
       `0.725470286351178`, and absolute cap
       `64.38813572617559` GeV.
108. Froze the first bounded component-stage configuration and uploaded its
     four exact overlay objects with generation-match zero.
     - Stage is `response`; the condition encoder is trainable; FP32, batch 6,
       accumulation 4, three epochs, and no test selection.
     - Frozen config:
       `audit/training_hardening_inputs/stage_response_r1/configs/frozen_pilot_stage_response_fp32.yaml`.
     - Frozen SHA-256:
       `ceb8e9106d6f3e93cf7d457f27a199df014ebde93beaf59917bbf331f56dd95c`.
     - Input:
       `gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/stage-20260725-r1-response-input`.
     - No component-stage job was submitted before the target-hardware gate.
109. Target-hardware hardening custom job `2224189161156378624` reached
     `JOB_STATE_SUCCEEDED`.
     - Vertex start/end: `2026-07-25T04:11:10Z` /
       `2026-07-25T04:23:15Z`.
     - Terminal spec independently confirmed `ON_DEMAND`, one
       `n1-standard-8`, one `NVIDIA_TESLA_T4`, one replica, 100 GB `pd-ssd`,
       the r12 immutable digest, expected service account, and exact prefixes.
     - The immutable `progress/epoch_0000` checkpoint hashes exactly match the
       terminal best and last checkpoint hashes:
       best `8c3c031087f3d9a3a35e1966b451f6ac28a0532af18abffa6a6f060cc105ee88`;
       last `8bd4a895d4b02813083dca0f65ef88ca9a5e02da4e4bddcd8c0b3816226c2edf`.
     - The full-architecture FP32 epoch completed 56 updates in
       55.951096146 seconds, 6.040989780 events/s, with finite train/validation
       losses `25.767865045` / `21.440538927`.
     - Fresh best-checkpoint reload and configured 8/8 sampling passed every
       invariant. Peak allocation was 11,717,986,304 of 15,655,829,504 bytes,
       leaving `0.2515256824` headroom, above the 15% gate.
     - Measured 8/8 solver/decode timing was 273.17683575 ms/event for the
       short batch-2, two-iteration postflight; it is a QA measurement, not a
       publication benchmark.
110. Independent staged-manifest inspection exposed a prefix-boundary defect
     before the component chain.
     - Listing base prefix `prep-20260724-r5` also matched sibling prefixes
       `prep-20260724-r5-fp32` and `prep-20260724-r5-fp32-r2`.
     - The scientifically resolved r5 files were correct, and no overlay
       collision or test/legacy path occurred, so job 2224189161156378624
       remains a valid target-hardware pass.
     - However, 618 objects and 17,833,083,901 bytes were staged instead of
       the intended r5 directory, wasting approximately 11.9 GB and startup
       time. Progression stopped before response submission.
111. Corrected GCS input listing to use a slash-terminated directory boundary
     and changed both success and failure terminal uploads to generation-zero
     writes so a run can never overwrite an output object.
     - Added a regression proving `prep-...-r5` cannot match
       `prep-...-r5-fp32`.
     - `PYTHONPATH=src python -m pytest -q`: 30 passed with only the two known
       Transformer warnings.
     - `python -m compileall -q src vertex tests`: passed.
     - A first `rg` evidence search used a Windows wildcard argument and
       returned the recorded invalid-filename error; the explicit-path repeat
       succeeded.
112. Built and pinned the corrected training image.
     - Cloud Build `cd55cf5a-5487-4bc3-94c0-9303ed8d5d58`;
     - status `SUCCESS`, duration 3m28s;
     - immutable digest
       `sha256:a7f047e05962b42bf3704a28d0f4de28bbb4265d3740c8b9a01bf9dc02059d05`.
     - A slash-bounded, read-only GCS listing independently returned exactly
       205 r5 objects and 5,944,359,023 bytes with zero sibling matches.
113. Reconfirmed the response overlay contains exactly four objects and 54,660
     bytes and that its output prefix was empty, then submitted exactly one
     response-stage job:
     - training pipeline `748849065843752960`;
     - custom job `7763317635659333632`;
     - one `n1-standard-8`, one on-demand `NVIDIA_TESLA_T4`, one replica,
       100 GB `pd-ssd`, 43,200-second timeout;
     - r13 immutable image and expected service account;
     - base input `prep-20260724-r5`, collision-checked response overlay, and
       output `stage-20260725-r1-response-output`;
     - terminal spec inspection at submission matched every requested field.
114. Added the user-specified hard budget ceiling of $100 USD.
     - Official current references list an on-demand T4 in Iowa at $0.35/hour
       and N1 compute as separately billed vCPU and memory.
     - Adopted a conservative planning rate of $0.85/hour for one
       `n1-standard-8` + T4 + disk/management uncertainty, $0.55/hour for
       `n1-highmem-8`, and $0.25/hour for `n1-standard-4`.
     - Enumerated all 11 matching CBSC custom jobs. Their conservative
       estimated compute total was $1.95 at the measurement time; added a
       $3.00 build/storage/unitemized contingency, leaving $95.05.
     - The first PowerShell ledger expression used unsupported `??` syntax and
       failed before cloud access. The first corrected expression mixed local
       and UTC `DateTime` kinds, yielding an invalid negative total; it was
       rejected. The final calculation used `DateTimeOffset`.
115. Added the required repo-root human journal `logs.md`, initial SHA-256
     `6ba357dade27c21b4d4a76cd1b2479157a84250f2fa2689bf09e646ef6301197`.
     - It records every known epoch, failed gate, correction, active job,
       artifact identity, budget estimate, open QA gate, alternative, and
       scientific boundary.
     - Per AGENTS.md, it records evidence and decisions, not private hidden
       chain-of-thought.
     - Required cadence is every completed/failed epoch or efficient notable
       mid-epoch checkpoint, plus every gate, submission, correction, and cost
       disposition.
116. Recorded a budget-feasibility stop before final training.
     - At 6.04099 events/s, one 612,482-event epoch projects to about 28.2
       hours.
     - Six one-epoch final runs project to about 169 hours / $143.65 at the
       conservative rate, before scientifically meaningful multi-epoch
       training.
     - The six-run matrix is therefore blocked until measured code/hardware
       throughput improvements make the frozen protocol fit the remaining
       budget. Gates or scientific semantics will not be weakened to fit cost.
     - Updated heartbeat `continue-cbsc-vertex-training` to enforce `logs.md`,
       the $100 pre-submission gate, current response job IDs, exact stage
       order, and the throughput-feasibility decision.
117. Response job `7763317635659333632` completed immutable epoch 0.
     - Train/validation losses `-0.4759504806` / `-0.5288399397`;
       response NLL `-0.5453332930`, visible BCE `0.0693828124`.
     - 26,624 train events completed in 2,843.694854282 seconds at
       9.362467270 events/s; peak CUDA allocation 385,734,656 bytes.
     - Best/last SHA-256:
       `baff0052cd072cc07d2b815d5d91ef5e6ce398023bc841a5df01d522a29656f9`
       /
       `6b885ecdb175e58c533b513f6f4b42af37533ed3c9c20b12fcbda3e618cbf91b`.
     - Independent downloads re-hashed exactly. Stage, epoch, seed, geometry,
       dataset, and diagnostic-split provenance all match.
     - Preflight passed 187/187 shards and 26,624/4,096/0 selected
       train/primary-validation/test events.
     - Staging boundary correction passed in production: exactly 205 base plus
       four overlay objects, 5,944,413,683 bytes, with no sibling, legacy, or
       test-path match.
     - Every invariant failure count was zero; layer/event closures
       `9.5367431640625e-07` / `3.814697265625e-06` GeV.
118. Epoch-0 recovery inspection found `best.pt` correctly stored
     `best_metric=-0.5288399397`, but `last.pt` stored `best_metric=inf`.
     - Cause: last was written before the epoch's best-selection branch.
     - The active non-resumed response job is unaffected; no r13 successor
       stage is authorized.
     - Moved last-save after selection locally. Regression suite remains
       30 passed with two known warnings; compileall passed.
     - This fixes the metric ordering but does not by itself prove preservation
       of a prior best checkpoint across a resumed worker, so the recovery gate
       remains open and a new immutable image plus resume pilot are required.
119. Response epoch 1 passed independent QA.
     - Train/validation `-0.6602025454` / `-0.5341875182`; response NLL
       `-0.7160758093`, visible BCE `0.0558732644`.
     - 2,608.806202019 seconds, 10.205434186 events/s, unchanged
       385,734,656-byte peak allocation.
     - Best/last hashes independently reproduced:
       `2ace2bb53db11d1179907f50591e20371142e66baa133f106e16371860012b3e`
       /
       `c3538913189995d762d2b9225806840997f9f165da7313ba7300d5ee8825aaba`.
     - All structural failure counts zero; layer/event closure
       `2.384185791015625e-07` / `4.76837158203125e-07` GeV.
     - Validation improved by `0.00534757845`; train, response, and visible
       losses moved in the expected direction.
     - Best stored epoch-1 metric, while last stored epoch-0 metric,
       independently reproducing the already diagnosed r13 save-order defect.
120. Hardened paired-checkpoint recovery locally.
     - Config validation now requires `resume_from` and
       `resume_best_from` together, forbids simultaneous initialize/resume, and
       applies safe-relative-path plus lowercase SHA-256 rules to both.
     - Vertex resolves and hash-checks both staged paths inside the input root.
     - Trainer verifies same stage, best epoch not newer than last, finite and
       exactly matching best metric, and identical provenance; it preserves the
       prior best in the new run and rejects a resume with no remaining epoch.
     - Tests cover staged pair resolution, missing-pair rejection, successful
       preservation, and metric mismatch. Suite: 33 passed, two known warnings;
       compileall passed.
     - No image has yet been built from this change and no recovery job
       submitted. Full recovery remains blocked pending a Vertex resume pilot;
       mid-epoch recovery is still separately open before full training.
121. Response epoch 2 and terminal job passed.
     - Epoch-2 train/validation `-0.7221741132` / `-0.5895688564`,
       response NLL `-0.7777847158`, visible BCE `0.0556106029`;
       2,468.32509685 seconds at 10.786261516 events/s.
     - Validation improved at every epoch. Total optimizer updates: 3,330.
     - Terminal best/last hashes independently reproduced:
       `d378de58ce310b9454620db3811e9cbba6760ba426fd7b3e4dd467c709119463`
       /
       `c03f425e8f684a9ffa58117c6614ea93e3cf91dc8a85b68842c5c66975c170cf`.
     - Terminal best is stage response, epoch 2, seed 20260723, with matching
       geometry/dataset/split provenance.
     - Epoch and fresh-reload invariants all passed. Configured 8/8 short
       timing was 247.0452375 ms/event. Postflight peak 398,736,384 of
       15,655,829,504 bytes left 97.4531% headroom.
     - Exactly 56 output objects / 114,993,418 bytes, no failure artifact.
     - Disposition: isolated response diagnostic pass; no physics claim.
122. The r13 terminal last checkpoint retained epoch-1 best metric while the
     terminal best improved at epoch 2, as predicted by the diagnosed ordering
     defect. It is preserved and not authorized as a recovery source paired
     with terminal best.
123. Added resume-only Python/NumPy/Torch/CUDA RNG restoration and
     epoch-indexed deterministic DataLoader seeds for future images.
     - Cross-stage initialization does not restore predecessor RNG.
     - Local suite: 34 passed, two known warnings; compileall passed.
     - Vertex recovery and mid-epoch recovery remain open.
124. Built recovery image r14.
     - Cloud Build `769eff68-9d7b-49a7-8a82-a02117a9855e`, `SUCCESS`, 2m39s.
     - Immutable digest
       `sha256:662fdcd70c0d78bba52df4af2e09d8e40b419f9f00f4473bdf12b1a6940d058a`.
125. Froze recovery config
     `audit/training_hardening_inputs/recovery_response_r1/configs/frozen_pilot_stage_response_resume_fp32.yaml`,
     SHA-256
     `46e51b2ab840e4ee1adf1eac1ee05b864022a6156e5ddafa46f4c286ed91d4bf`.
     - The first direct `cbsc-zdc` invocation failed because that executable is
       not installed in the local shell. The module invocation with
       `PYTHONPATH=src` succeeded.
     - Pair is terminal epoch-2 last
       `c03f425e...c170cf` with epoch-1 best
       `2ace2bb5...12b3e`; their stored selected metric and provenance match.
126. Uploaded a six-object, 28,728,008-byte recovery overlay with
     generation-match zero. Input and output prefixes were independently empty
     before creation; the output remained empty before submission.
127. Recomputed budget immediately before recovery submission:
     - custom jobs $3.94 estimated; $3.00 contingency; $6.94 accounted;
       $93.06 remaining.
     - six-hour worst case $5.10; projected reserve $87.96; gate passed.
128. Submitted exactly one r14 recovery pilot:
     - pipeline `6956920414685626368`;
     - custom job `8279014977365344256`;
     - one on-demand T4, `n1-standard-8`, one replica, 100 GB `pd-ssd`,
       21,600-second timeout, expected service account and exact prefixes.
     - Immediate spec inspection matched all fields; initial state pending.
129. Investigated the negative response-loss sign against the implementation,
     independent diagnostic validation, an analytic counterexample, and primary
     documentation.
     - The optimized response term is continuous Gaussian-mixture NLL in
       `y=log1p(total_gev/10 GeV)`, not a nonnegative error norm.
     - 68.7593% of 4,046 visible validation truth points had fitted density
       greater than one, which necessarily gives negative per-target NLL.
     - Validation mean response NLL was `-0.6548890471`; all values and
       gradients were finite.
     - Learned component scales ranged `0.0505365` to `0.255575`; none was
       pinned at or below `0.0501`. Mixture entropy ranged `0.7638` to
       `1.0816`, with no single-component collapse.
     - An explicit sigma-0.1 Normal-at-its-mode example has valid NLL
       `-1.3836466`; this is now protected by
       `tests/test_response_likelihood.py`, SHA-256
       `fbdf0e141330b11aead8387ea590feafa93535404afe5742e4b8819192231489`.
     - Full local result: 35 passed, two known warnings.
     - `abs(NLL)` is rejected because it reverses the maximum-likelihood
       gradient below zero. Replacing the MDN likelihood with L2 is rejected
       as a sign fix because it changes the learned conditional distribution
       to a conditional-mean objective and can blur multimodal responses.
     - L1/L2 may only be used as a separately frozen validation diagnostic or
       predeclared ablation. Negative likelihood alone is not a pass: finite
       gradients, held-out NLL, scale/collapse, calibration, invariant, and
       physics gates remain required.
     - Sources:
       <https://docs.pytorch.org/docs/stable/distributions.html> and
       <https://www.microsoft.com/en-us/research/publication/mixture-density-networks/>.
     - A `git diff`/`git status` evidence command failed because this workspace
       is not a Git repository; no state changed.
130. Added a frozen per-epoch validation visualization contract for subsequent
     jobs.
     - Fixed 50-event validation bank, selection seed `20260725`, five
       independent Fast-MC draws per exact Geant4 four-vector.
     - Test use is forbidden and recorded as zero.
     - Export happens after safe `last.pt` creation on the resident epoch T4;
       explicit forked RNG prevents perturbing subsequent training.
     - Immutable artifacts contain checkpoint/geometry/data/split/selection
       hashes, event IDs, p4, seeds, 3D sparse deposits, profiles, event
       summaries, descriptive metrics, and structural QA.
     - Localhost observatory and 300-second immutable GCS sync implemented.
       Full Python suite: 39 passed; compileall clean; dashboard build and two
       rendered/data-contract tests passed.
     - Browser-control setup failed with kernel-asset `os error 3`, so visual
       interaction QA is preserved as open. HTTP endpoints returned 200.
     - Synthetic UI fixture is explicitly labeled not Geant4/not physics.
131. Recovery job `8279014977365344256` / pipeline
     `6956920414685626368` failed before epoch 3.
     - Exact on-demand T4/r14 spec and staging/preflight passed.
     - Failure: `TypeError: RNG state must be a torch.ByteTensor`.
     - Cause: CUDA map-location moved the serialized CPU RNG ByteTensor onto
       CUDA before `torch.set_rng_state`.
     - Six objects / 75,380 bytes preserved under
       `audit/recovery_response_r1_failure/`; manifest records every hash.
     - Correction converts Torch and CUDA RNG arrays to detached CPU uint8
       tensors before restoration. Focused QA: 12 passed.
     - Failed prefixes remain immutable; no retry yet submitted.
132. Budget after failed recovery:
     - prior custom jobs $3.94; conservative failed-job charge $0.20;
       contingency $3.00; accounted $7.14; remaining $92.86.
     - six-hour retry reserve $5.10 would leave $87.76.
133. Deleted heartbeat automation `continue-cbsc-vertex-training` per user
     request. Monitoring and localhost synchronization use 300-second
     server-side timers/poll intervals instead of scheduled prompts.
134. r15 recovery correction passed 40 local tests, template validation, and
     compileall.
     - First packaging attempt was stopped pre-build at 29,660 files / 683.1
       MiB; Cloud SDK had ignored `.dockerignore`. No build was created.
     - Strict `.gcloudignore` reduced the verified source to 61 files /
       250,937 bytes and excluded bytecode/dashboard/audit data.
     - Cloud Build `a581e834-5e36-4fea-8f69-7d12a19d2def` succeeded in 3m28s.
     - Immutable digest
       `sha256:f74e0f1bc9cfda1930ff5a2698c3e6675304c49f10d97a12e829f7bd2f80b8a1`.
135. Froze recovery r2 config, SHA-256
     `eab628be2c7a03ceae7cdfd7b24e911a8e4ba3bd4ba8c22c695cd5a8dce1d265`.
     It includes validation-only 50×5 epoch visualization.
136. Created unique r2 input prefix with generation-match zero:
     - exactly six objects / 28,728,231 bytes;
     - copied artifact/checkpoint byte, MD5, and CRC32C values all match r1;
     - unique r2 output prefix independently empty.
137. Pre-submission budget/spec gate:
     - $7.14 accounted, $92.86 remaining;
     - six-hour reserve $5.10, leaving $87.76;
     - no duplicate display name;
     - authorized exact spec is one on-demand T4, one replica,
       `n1-standard-8`, 100 GB `pd-ssd`, 21,600 seconds, r15 digest, base r5,
       unique r2 input/output, FP32, and training postflight.
138. Submitted exactly one r15 recovery retry:
     - pipeline `7685263305203515392`;
     - custom job `7148299209593061376`;
     - initial state pending;
     - independent live spec matched every field and output was empty.
     - Async wrapper raised only when printing an unavailable resource property
       after successful submission. It was corrected without resubmission.
     - Monitoring is a 300-second server-state loop, not a scheduled prompt.
139. Response-loss sign QA:
     - implementation is visibility BCE plus continuous Normal-mixture NLL on
       transformed response;
     - continuous density NLL is not lower-bounded by zero;
     - validation improved monotonically
       `-0.528839940 -> -0.534187518 -> -0.589568856`;
     - `abs(NLL)` would reverse valid gradients below zero, while L2 would
       remove multimodal likelihood semantics;
     - no loss change accepted. Flow MSE components retain zero as their
       theoretical floor, and response quality remains gated by independent
       validation distributions rather than NLL sign.
140. At 2026-07-25 16:22 Asia/Taipei, the existing 300-second monitor observed
     recovery r2 custom job `7148299209593061376` enter
     `JOB_STATE_RUNNING`. This is not a gate pass; no successor was submitted.
141. Armed one hidden localhost visualization synchronizer (PID `18736`) at a
     300-second interval for the unique recovery r2 output. Initial result was
     correctly `waiting_for_first_epoch`, with no stderr and no downloaded
     artifacts. Dashboard remains live on localhost port 3000.
142. Recovery r2 model initialization reached Cloud Logging at
     `2026-07-25T08:25:58Z`. Only the known nonfatal `norm_first=True`
     Transformer performance warning was emitted; no epoch artifact or failure
     existed at this gate.
143. Mid-epoch recovery design was frozen at the decision level:
     - snapshot only after optimizer/scheduler step and gradient clearing;
     - include full training/RNG state, next batch, epoch aggregates, update
       count, loader-order contract, provenance, and paired prior best;
     - reconstruct `seed + epoch` ordering and skip consumed loader batches
       without recomputing stochastic losses;
     - reject all state/order/hash/provenance mismatches.
144. Mid-epoch recovery was then implemented locally:
     - checkpoint format v3 progress payload;
     - separate hash-pinned progress-resume configuration;
     - optimizer-boundary-only saves with full aggregates/order contract;
     - deterministic skip-to-next-batch resume;
     - immutable Vertex in-flight snapshot callback with paired best;
     - stale progress removal only after completed `last.pt`.
     Focused tests: 18 passed. Full suite: 42 passed, three known warnings;
     compileall clean. Vertex interruption/equivalence proof is still required,
     so this cannot yet authorize full-data runs.
145. Recovery r2 terminal gate independently passed:
     - job `7148299209593061376` succeeded on exact on-demand T4/r15 spec;
     - 32 objects / 73,664,533 bytes, no failure object;
     - structured local mirror and source checkpoints re-hashed;
     - exactly epoch 3 and 1,110 updates; optimizer/scheduler 3330→4440;
     - stage/provenance/RNG state valid; best/last model states identical;
     - epoch and fresh-reload invariants all zero-failure, closures ≤1.91e-6;
     - T4 headroom 97.4513%; 8/8 short timing 262.115 ms/event;
     - visualization: 50 validation conditions × five draws, zero test,
       artifact/selection hashes fixed, all invariant/nonfinite/negative gates
       pass; localhost manifest returns the real epoch-3 bank.
146. Scientific predecessor decision:
     - recovery validation `-0.5889020705` is worse than accepted uninterrupted
       response best `-0.5895688564` by `0.0006667859`;
     - profile must initialize from original hash
       `d378de58ce310b9454620db3811e9cbba6760ba426fd7b3e4dd467c709119463`;
     - recovery scheduler was intentionally advanced beyond original
       `T_max=3330`, proving restoration but not authorizing schedule extension.
147. Local mid-epoch interruption equivalence passed:
     - interrupted at first optimizer-boundary snapshot (`next_step=2`);
     - resumed in a new run with exact contract-hash validation;
     - terminal model tensors bitwise equal to uninterrupted control;
     - train/validation/component losses, LR, and update count exactly equal;
     - stale progress removed only after completed last checkpoint.
     Full suite: 43 passed, four known warnings; compileall/templates clean.
     Vertex/GCS proof remains open before full data.
148. Profile pre-submission gate:
     - r16 build `faf94066-623c-4b9d-bab2-7b71a9b7355c`, digest
       `sha256:dcd6548e40ccee98ecefa0960864c8528546b152ea8f7540481594acc5d35893`;
     - frozen profile config SHA
       `6dbbe30d3e42ee9cd39318673a11bf73af471d72258c6f084fb68613f165b117`;
     - profile/FP32/3 epochs/effective batch 24/encoder frozen/50×5 bank;
     - initialization pinned to accepted response `d378...9463`;
     - unique input has two objects / 14,339,535 bytes with source-matching
       MD5/CRC; output empty; no duplicate job;
     - $8.94 accounted, $91.06 remaining; six-hour reserve $5.10 leaves
       $85.96.
149. Submitted exactly one profile job:
     - pipeline `7536609333128200192`;
     - custom job `4083748372115095552`;
     - initial pending state and independently exact r16/on-demand T4/spec;
     - output empty.
     The stray local SDK status process was stopped without affecting the
     server job. One 300-second server monitor is active.
150. Replaced the completed recovery dashboard watcher with one 300-second
     profile watcher (PID `11208`). Initial result is
     `waiting_for_first_epoch`; localhost remains live.
151. Profile r1 failed preflight before model construction:
     - missing `artifacts/training_pilot_splits.json` because r1 overlay omitted
       diagnostic split manifest/assignment;
     - first attempt preserved three objects / 68,802 bytes; managed retry
       received generation-0 HTTP 412 rather than overwrite;
     - evidence preserved in `audit/stage_profile_r1_failure/`; prefixes closed.
152. Added merged staging verifier and reproduced r1 failure locally. New r2
     staging passes:
     - 205 base + 4 overlay = 209 unique objects / 5,958,748,764 bytes;
     - config/dataset/split/assignment/geometry/predecessor hashes exact;
     - real data, zero forbidden paths;
     - output empty, no duplicate job.
     Budget: $9.09 accounted, $90.91 remaining; retry reserve leaves $85.81.
153. Submitted exactly one corrected profile r2:
     - pipeline `329020341986787328`;
     - custom job `6016741215913902080`;
     - pending, exact r16/on-demand T4/corrected staging/output/spec;
     - one 300-second monitor and one r2 dashboard watcher (PID `14712`).
154. Profile r2 entered `JOB_STATE_RUNNING` at 23:04 Asia/Taipei. No epoch
     artifact was yet available; no successor was submitted.
155. At 23:12, an independent server describe reconfirmed the exact r16
     on-demand T4 profile-r2 specification and start time
     `2026-07-25T15:01:16Z`. Cloud Logging had reached model construction with
     only the known Transformer performance warning; the unique output prefix
     remained empty. Official Google pricing was refreshed: T4 `$0.35/h`,
     N1 vCPU `$0.031611/vCPU-h`, N1 memory `$0.004237/GiB-h`; an
     `n1-standard-8` plus T4 is about `$0.729998/h` before disk/service
     overhead. The ledger continues to use the more conservative `$0.85/h`.
     Prior accounted spend is `$9.09`; the active six-hour reserve leaves
     `$85.81`. No new job was submitted.
156. Prepared independent per-epoch component verification while profile r2
     runs. The predecessor was downloaded from the immutable r2 overlay and
     re-hashed exactly to `d378...9463`. The new verifier checks frozen versus
     trainable tensor deltas, best/last selection, optimizer/scheduler steps,
     staging/preflight, invariants, visualization, and zero test use. Its
     first test harness attempt preserved two invocation failures: malformed
     inline-Python syntax and missing `PYTHONPATH=src`; verifier compilation
     itself passed. A proper regression test was added before rerun.
157. Corrected verifier QA passed: 17 focused tests and compilation clean,
     with only two known Transformer warnings. Positive/negative controls prove
     intended profile-only change acceptance and frozen-condition mutation
     rejection. Four 300-second dashboard polls still found no completed
     profile epoch. Browser-control reconnection again failed at the desktop
     kernel-asset layer (`os error 3`) before navigation; it is recorded as an
     environment limitation, not a UI result.
158. Full local regression after the component verifier addition: 45 passed,
     four known Transformer performance warnings, exit zero. This is software
     QA only; the running profile Vertex gate remains closed.
159. Profile r2 immutable epoch 0 independently passed:
     - 13 objects / 55,495,840 bytes, locally re-hashed;
     - exact `d378...9463` response predecessor;
     - all 40 changed tensors are `profile.*`; zero frozen-tensor mismatch;
     - best/last `c3bd...c97ce` / `c566...ae245`, exactly 1,110 optimizer and
       scheduler updates;
     - finite train/validation `3.966256104 / 2.793788581`;
     - train first/active/profile-flow
       `0.690892304 / 0.435593615 / 3.403013145`, exactly consistent with
       frozen weights;
     - 2,676.345 seconds, 9.94790 events/s, 403,064,832-byte peak allocation;
     - epoch and 50×5 visualization invariants all pass; closures ≤5.73e-6;
       zero test, exact selection hash; localhost latest epoch 0 and HTTP 200.
     Descriptive profile relative L1 is `0.307060`; downstream morphology is
     not physics validation. A lookup for an original-response epoch-2 visual
     correctly found no object because that run predates the exporter.
     Cross-epoch response outputs will be checked for identity. No successor
     was submitted; epochs 1–2 and terminal postflight remain mandatory.

160. Added a hierarchical cross-epoch frozen-upstream gate. It requires exact
     identity across all 250 draws for response at profile stage; response and
     layers at count; plus counts at support; plus selected support at share.
     Seven unit controls and compilation passed; an epoch-0 self-check found
     250/250 response draws identical. Epoch 1 will compare against epoch 0.

161. Epoch 1 exposed and corrected an over-strong QA assumption in item 160.
     The exporter intentionally offsets generation seeds by
     `epoch×1,000,003`, so fixed truth conditions receive independent FastMC
     samples each epoch. The first verifier stopped on this counterexample and
     wrote no pass report. The corrected gate checks identical 50-condition
     truth/selection, 250 draws, and the exact seed offset; frozen upstream
     integrity remains proven by byte-exact tensors. Four focused controls and
     compilation pass.
162. Profile r2 immutable epoch 1 independently passed:
     - 16 objects / 77,219,125 bytes, locally mirrored and re-hashed;
     - all changes confined to `profile.*`, zero frozen mismatch;
     - best/last select epoch 1, hashes `9bd5...d986c` /
       `d2f1...57e1f`, with exactly 2,220 optimizer/scheduler updates;
     - train/validation `2.807006051 / 2.509450324`, improvements of
       `29.23% / 10.18%` from epoch 0;
     - first/active/profile-flow improve
       `34.44% / 16.08% / 29.54%`;
     - 2,658.898 seconds, 10.0132 events/s, 403,064,832-byte peak;
     - all epoch/visualization invariants pass, closures ≤5.73e-6, zero test;
       descriptive profile relative L1 improved 17.39% to `0.253661`.
     Localhost latest epoch is 1 with unchanged selection. Epoch 2 and terminal
     postflight remain required; no successor was submitted.
163. Full regression after correcting the cross-epoch seed contract:
     47 passed, four known Transformer warnings, exit zero.
164. Profile r2 terminal gate passed:
     - job `6016741215913902080` succeeded after `2h40m28s`;
     - complete output 73 objects / 330,733,796 bytes, no failure object;
     - epoch-2 train/validation `2.642119713 / 2.451456106`, with monotonic
       validation `2.793788581→2.509450324→2.451456106`;
     - all trained components improved; changes confined to `profile.*`;
     - best/last `ef29...4ee24` / `b31f...75cf2`, exactly 3,330 updates;
     - all epoch/visual/postflight invariants pass, closures ≤5.73e-6;
     - T4 headroom `97.4255%`; FP32 8/8 short timing
       `275.396 ms/event`, batch 2.
     This is component optimization/structural evidence, not physics
     validation.
165. Budget closeout charged profile r2 conservatively at `$2.30`. Accounted
     total is `$11.39`, remaining `$88.61`; a six-hour count reserve would
     leave `$83.51`. Count is not yet submitted pending freeze/staging/spec QA.
166. Count pre-submission gate passed:
     - new template frozen only through CLI, frozen SHA
       `436a6efd...17012`;
     - only intended profile→count/project/predecessor/template-hash fields
       differ; FP32/effective-batch-24/3-epoch/frozen-encoder protocol exact;
     - predecessor pinned to accepted profile best `ef29...4ee24`;
     - unique generation-0 input four objects / 16,666,968 bytes;
     - merged staging 205+4=209 objects / 5,961,025,991 bytes, all hashes
       exact, real data, no forbidden path/collision;
     - unique output empty, no duplicate display name;
     - focused QA 16 passed and compileall clean;
     - `$11.39` accounted, `$88.61` remaining, six-hour reserve leaves
       `$83.51`.
167. Submitted exactly one count job: pipeline `3896909185840840704`, custom
     job `3159244635742666752`, initial pending. Independent server describe
     matches exact r16 digest, corrected overlay/output, frozen config,
     on-demand one-T4 resources, timeout, service account, and postflight;
     output remains empty.
168. Replaced the completed profile visualization watcher. Two safe local
     launch failures are preserved: an identity wildcard mismatch stopped
     nothing, then an unquoted spaced script path exited before watching.
     Corrected count watcher PID `9020` uses new r1b logs and 300-second
     intervals. Exactly one state monitor is session `94156`. No Vertex job
     was affected or duplicated.
169. Count job `3159244635742666752` entered `JOB_STATE_RUNNING` at 02:01.
     The corrected 300-second visualization watcher is healthy and waiting for
     epoch 0 with no stderr. Count gate remains closed.
170. Count r1 immutable epoch 0 independently passed:
     - verification waited through a partial two-object upload until all
       13 objects / 41,508,493 bytes existed;
     - exact profile predecessor `ef29...4ee24`;
     - all seven changes confined to `counts.*`, zero frozen mismatch;
     - best/last `09fb...bd599` / `69f6...20af3`, exactly 1,110 updates;
     - count CE `3.799753980`, weighted train `2.849815485`, validation
       `2.843521855`, finite and weight-consistent;
     - 2,551.772 seconds, 10.4335 events/s, peak 402,456,064 bytes;
     - all epoch/visual invariants pass, closures ≤4.77e-6, zero test.
     Descriptive hit-count bias is `-6.736%`; not physics validation. Epochs
     1–2 and terminal postflight remain required.
171. Dashboard stage-identity correction passed:
     - old watcher PID `9020` failed closed because profile epoch 0 and count
       epoch 0 have different immutable hashes; traceback preserved;
     - sync keys are now `(stage, epoch)`, existing profile objects were not
       overwritten, and count epoch 0 was stored separately;
     - manifest schema 2 contains profile epochs 0/1/2 plus count epoch 0,
       with exact shared geometry/selection hashes and `latest_id=count:0000`;
     - focused Python QA `12 passed` (one known warning), dashboard build
       passed, rendered UI tests `2 passed`;
     - corrected watcher PID `20244` completed a first 300-second-mode pass
       with zero stderr; monitor session `94156` still reports the sole count
       job running. No cloud job or artifact was mutated.
172. Loss-form QA found no basis to alter the frozen objective:
     - count already uses categorical cross-entropy; profile/share flow already
       use squared error;
     - absolute value is redundant for the nonnegative losses and an outer L2
       would distort gradient scaling;
     - official PyTorch definitions and the Flow Matching source support the
       existing forms; trend/generation gates, not distance-to-zero alone,
       remain authoritative.
173. Live localhost data-contract QA passed over HTTP: status 200, manifest
     schema 2, four snapshots, latest count epoch 0, exact 50×5 validation
     contract, QA pass, zero test. The in-app visual-browser connection and its
     troubleshooting lookup both failed on a missing local kernel-asset path;
     this tooling failure is preserved and did not affect training. Count
     remained running at 03:07 and 03:12 with no epoch 1 prefix yet.
174. Count r1 immutable epoch 1 independently passed:
     - complete 16 objects / 54,677,454 bytes mirrored to a new path; the first
       copy failed before transfer because the directory did not exist, and the
       successful wildcard copy's flattened layout was corrected with explicit
       in-audit literal moves; final count/bytes exact;
     - exact profile source `ef29...4ee24`, only seven `counts.*` tensors
       changed, zero frozen mismatch;
     - best/last `33d8...fe745` / `2929...477a`, 2,220 exact updates;
     - count CE `3.799754→3.636642`, weighted train
       `2.849815→2.727482`, validation `2.843522→2.798862`;
     - 2,554.433 seconds, 10.4227 events/s, peak 402,456,064 bytes;
     - all invariant/50×5 visual gates pass, closures ≤7.63e-6, zero test;
     - localhost schema-2 timeline now has five snapshots and
       `latest_id=count:0001`.
     The hit-bias visual changed to `-10.537%` but is descriptive, stochastic,
     and not a checkpoint-selection gate. Epoch 2 and terminal remain closed.
175. Count r1 terminal gate passed:
     - job `3159244635742666752` succeeded with exact authorized immutable
       on-demand T4 spec and 2.482-hour wall time;
     - output 73 objects / 232,474,455 bytes, zero failure artifact, exact local
       mirror and independent terminal report;
     - best `163477...a0e5b`, last `c9c2fc...e0401`, only `counts.*` changed,
       zero frozen mismatch, 3,330 exact updates;
     - count CE `3.799754→3.636642→3.605898`, validation
       `2.843522→2.798862→2.791588`;
     - all epoch/visual/fresh-reload postflight invariants pass, closure
       ≤1.91e-6, T4 headroom `97.429%`, FP32 8/8 timing
       `266.845 ms/event`;
     - full local suite `53 passed`, four known warnings;
     - dashboard contains six snapshots through `count:0002`; completed watcher
       stopped only after exact identity verification.
     Count is accepted as structural/component evidence, not physics
     validation. Conservative `$2.30` charge makes accounted `$13.69`,
     remaining `$86.31`.
176. Support r1 pre-submission gate passed:
     - new unfrozen template `ce1da7...d5967`, CLI-frozen config
       `e8d0c6...6eb5f`, stage support, FP32, three epochs, effective batch 24,
       frozen encoder;
     - predecessor exact count best `163477...a0e5b`;
     - field diff limited to intended project/template/stage,
       batch-4×accumulation-6, and predecessor fields;
     - exact 26,624/6,656/0 bank and 50×5 validation visuals retained;
     - generation-0 overlay 4 objects / 13,760,796 bytes;
     - merged staging 209 objects / 5,958,119,819 bytes, exact hashes, real,
       zero forbidden/collision;
     - corrected focused suite `30 passed` (one known warning), compileall
       clean; prior full suite `53 passed`;
     - no duplicate job, empty unique output;
     - accounted `$13.69`, remaining `$86.31`; six-hour reserve leaves
       `$81.21`.
     Authorized spec is exact r16, one on-demand T4, n1-standard-8, 100 GB
     pd-ssd, timeout 21,600 seconds, exact prefixes/config/SA/CUDA/postflight.
177. Submitted exactly one support job: pipeline `2954601332557742080`,
     custom `8378580153306972160`, initial pending. Independent server describe
     matches the exact r16 image, base/overlay/output/config/split,
     on-demand one-T4 resources, timeout, service account, CUDA, and postflight.
     Display-name query returns exactly one job. SDK observation session is
     `28272`. Support dashboard watcher PID `18300` uses 300-second intervals
     and is waiting for epoch 0 with zero stderr. A nonterminating PowerShell
     log-path precheck syntax error is preserved; the paths were new, process
     started, and no cloud state or existing log was affected.
178. Support custom job `8378580153306972160` entered `JOB_STATE_RUNNING` at
     04:41 after on-demand T4 allocation. Epoch 0 remains closed.
179. Support r1 immutable epoch 0 independently passed:
     - 13 objects / 48,818,132 bytes, exact new local mirror;
     - initial verifier failed closed because batch-6/accumulation-4 was
       hardcoded from earlier stages; no report/job mutation;
     - verifier now accepts explicit expected batch/accumulation and checks
       every stage predecessor filename; regression QA `5 passed`, compileall;
     - exact count source `163477...a0e5b`, all 64 changes only `support.*`,
       zero frozen mismatch;
     - best/last `6755eb...cf763` / `7f003d...3dc9`, 1,110 updates;
     - BCE `0.682490428`, rank `0.316068462`, weighted train `0.761507544`,
       validation `0.654732760`, all finite and weight-consistent;
     - 2,722.007 seconds, 9.7810 events/s, peak 3,956,515,840 bytes
       (~74.73% headroom);
     - all epoch/50×5 visual gates pass, closure ≤5.73e-6, zero test;
     - localhost has seven snapshots through `support:0000`.
     Epochs 1–2 and terminal remain closed; not physics validation.
180. Support r1 immutable epoch 1 independently passed:
     - 16 objects / 62,155,435 bytes, exact mirror/report;
     - all 64 changes only `support.*`, zero frozen mismatch;
     - best/last `b09349...25c96` / `ef7f20...bf4e8`, 2,220 updates;
     - BCE `0.682490→0.571882`, rank `0.316068→0.220478`, weighted train
       `0.761508→0.627002`, validation `0.654733→0.632098`;
     - 2,715.124 seconds, 9.8058 events/s, unchanged peak memory;
     - all epoch/cross-epoch 50×5 gates pass, closure ≤5.73e-6, zero test;
     - localhost has eight snapshots through `support:0001`.
     Epoch 2 and terminal remain closed; not physics validation.
181. Support r1 terminal gate passed:
     - job `8378580153306972160` succeeded in 2h36m26s, exact authorized spec;
     - 73 objects / 262,219,743 bytes, zero failure, exact mirror/report;
     - best `b7f968...747a89`, last `8cd100...9d6ee4`, only 64
       `support.*` tensors changed, 3,330 updates;
     - BCE `0.682490→0.571882→0.562911`, rank
       `0.316068→0.220478→0.214391`, validation
       `0.654733→0.632098→0.625293`;
     - fresh reload/postflight pass, closure ≤4.77e-7, headroom `74.728%`,
       FP32 8/8 timing `263.873 ms/event`;
     - terminal 50×5 gate pass, zero test; localhost nine snapshots through
       `support:0002`, watcher stopped after identity verification;
     - conservative `$2.30` charge makes accounted `$15.99`, remaining
       `$84.01`.
     Support is structural/component evidence, not physics validation.
182. Share r1 pre-submission gate passed:
     - new unfrozen template `97efb0...07dbd`, CLI-frozen config
       `58e430...7e10d`, FP32 share, effective batch 24, three epochs, frozen
       encoder;
     - predecessor exact support best `b7f968...747a89`;
     - diff limited to project/template/stage/predecessor fields;
     - unique generation-0 overlay 4 objects / 17,463,746 bytes;
     - merged staging 209 objects / 5,961,822,769 bytes, exact hashes, real,
       zero forbidden/collision;
     - focused QA `31 passed`, one known warning, compileall clean;
     - empty output/no duplicate; `$15.99` accounted, `$84.01` remaining,
       six-hour reserve leaves `$78.91`.
183. Submitted exactly one share job: pipeline `3742836820463845376`, custom
     `6143565484131352576`, initial pending. Independent describe matches exact
     r16/base/overlay/output/config/split/on-demand T4/disk/timeout/SA/CUDA/
     postflight; exactly one display-name match. SDK session `15987`; dashboard
     watcher PID `14620` uses 300-second intervals and waits with zero stderr.
184. Share custom job `6143565484131352576` entered `JOB_STATE_RUNNING` at
     07:28 after T4 allocation. Epoch 0 remains closed.
185. Share r1 immutable epoch 0 independently passed:
     - 13 objects / 48,931,305 bytes, exact mirror/report;
     - exact support source `b7f968...747a89`;
     - best/last `ee1bb4...c93c2` / `3485ca...a73b`, exactly 62 changes only
       under `share.*`, zero frozen mismatch, 1,110 updates;
     - train share-flow `5.376477417`, validation `4.867630384`, all finite;
     - 2,654.945 seconds, 10.0281 events/s, peak 3,964,674,560 bytes;
     - all epoch and 50×5 visual gates pass, closure ≤7.63e-6 GeV, zero test;
     - descriptive response bias `+12.704%`, hit bias `-7.482%`, profile L1
       `0.269694`, not selection inputs or physics validation.
     Epochs 1–2 and terminal remain closed; exactly one existing job continues.
186. The independent stage verifier was extended fail-closed for the upcoming
     joint stage: exact share predecessor filename/stage, trainable encoder,
     all nine finite component losses, weighted-total reconstruction, and
     all-network change permission. Existing component frozen-prefix checks are
     preserved. Regression QA `8 passed`, compileall clean, and share epoch 0
     still passes under the strengthened weighted-loss assertion. No frozen or
     cloud artifact changed.
187. Local full-suite/site QA during share training:
     - first plain pytest invocation failed collection with 15 import errors
       because desktop Python 3.13 lacked the editable `cbsc_zdc` path;
     - explicit `PYTHONPATH=<repo>/src` rerun passed `57 passed`, four known
       Transformer warnings;
     - dashboard production build passed all five vinext phases;
     - HTTP manifest schema 2 has ten snapshots, latest `share:0000`;
     - a nonterminating doubled `dashboard/` read-path typo is preserved.
     No frozen/cloud artifact changed; this is not physics validation.
188. Read-only mid-epoch contract audit:
     - snapshots only at optimizer boundaries and preserve exact data-order,
       accumulated-loss, update, model/optimizer/scheduler/scaler/RNG state;
     - a trajectory-contract hash detects changed scientific/runtime settings;
     - Vertex uses immutable epoch/update-qualified prefixes with hashes;
     - resume rejects loader/batch/accumulation/seed/contract/best mismatch;
     - local regression proves byte-equal terminal tensors and exact recorded
       losses versus uninterrupted training.
     A bounded real-T4 interruption/recovery proof remains required before
     full-data final runs; local equivalence is not that cloud proof.
189. Share r1 immutable epoch 1 independently passed:
     - 16 objects / 62,323,994 bytes, exact mirror/report;
     - source `b7f968...747a89`, best/last `169170...a839c` /
       `79c21e...92cb4`, only 62 `share.*` changes, zero frozen mismatch,
       exactly 2,220 updates;
     - train `5.376477→4.755979`, validation `4.867630→4.730274`, all finite
       and weighted-total consistent;
     - 2,650.850 seconds, 10.0436 events/s, peak 3,964,674,560 bytes;
     - all epoch/cross-epoch 50×5 gates pass, seed offset `+1,000,003`,
       closure ≤7.63e-6 GeV, zero test;
     - localhost schema 2 has 11 snapshots through `share:0001`.
     Epoch 2 and terminal remain closed; not physics validation.
190. Calibration protocol was hardened before use:
     - `max_batches` now fails outside `[1,64]`;
     - clip bounds must be finite, positive, and ordered;
     - the report records actual `batches_consumed`;
     - focused `15 passed`, full `59 passed` with four known warnings,
       compileall clean.
     One overly broad read-only `rg` included minified audit JSON and produced
     truncated noise; it was narrowed and changed no artifact.
191. Share r1 immutable epoch 2 independently passed:
     - 19 objects / 75,852,555 bytes, exact mirror/report;
     - source exact, only 62 `share.*` changes, zero frozen mismatch;
     - best retained from epoch 1 `169170...a839c`; epoch-2 last
       `a77b5d...9d967`; exactly 3,330 updates;
     - train `5.376477→4.755979→4.674678`; validation
       `4.867630→4.730274→4.746518`, correctly selecting epoch 1;
     - 2,662.328 seconds, 10.0003 events/s, peak 3,964,674,560 bytes;
     - all epoch/cross-epoch visual gates pass, closure ≤7.63e-6, zero test;
     - localhost schema 2 has 12 snapshots through `share:0002`.
     Terminal authoritative state/reload/resource/timing remain closed.
192. Share r1 terminal gate passed:
     - custom `6143565484131352576` / pipeline `3742836820463845376`
       succeeded in 2h33m56s with empty error;
     - 73 objects / 262,963,989 bytes, no failure, exact terminal mirror/report;
     - best epoch 1 `169170...a839c`, last `a77b5d...9d967`, 62 share-only
       changes, zero frozen mismatch, 3,330 updates;
     - fresh best reload and seven-condition postflight invariants pass,
       closure ≤3.815e-6 GeV;
     - T4 headroom `74.676%`; FP32 8/8 timing `262.306 ms/event`;
     - watcher PID `14620` identity-checked/stopped; SDK observer exited;
     - conservative `$2.30` charge: `$18.29` accounted, `$81.71` remaining.
     Share is component/structural evidence, not physics validation. Joint
     remains closed pending new freeze/staging/spec/budget gates.
193. Joint r1 pre-submission gate passed:
     - new unfrozen template `bed069...63b6`, CLI-frozen config
       `6a15bf...929c`, FP32 joint, batch 6×accum 4, three epochs, encoder
       trainable;
     - exact accepted share best `169170...a839c`;
     - diff limited to project/template, batch/accum with same effective 24,
       predecessor, joint stage, and encoder unfreeze;
     - local preflight failed closed only because freeze inputs omit production
       shards; cloud staging independently passes;
     - generation-0 overlay 4 objects / 17,489,087 bytes; merged 209 objects /
       5,961,848,110 bytes, exact real hashes, zero forbidden/collision;
     - focused QA `32 passed`, compileall clean;
     - `$18.29` accounted, `$81.71` remaining; six-hour reserve leaves
       `$76.61`; empty output/no duplicate.
     No joint submission at this boundary.
194. Submitted exactly one joint job: pipeline `6159088389292294144`, custom
     `8267310950965575680`, initial pending, actual SDK display name ends in
     `-custom-job-custom-job`. Independent describe matches exact r16/base/
     overlay/output/config/split/CUDA/postflight/on-demand one-T4/disk/timeout/
     SA contract. An initial unsuffixed-name filter returned zero; local filter
     on the actual SDK name proves exactly one match. Observer session `39594`;
     localhost watcher PID `19776` uses exact 300-second intervals and unique
     logs. Joint epochs/terminal remain closed.
195. Joint custom job `8267310950965575680` entered `JOB_STATE_RUNNING` at
     10:21:59 after T4 allocation. The first combined cadence command was
     nonzero solely because the pre-epoch output prefix is empty; authoritative
     state is running with no error. Watcher PID `19776` remains exact, has two
     clean waiting records and zero stderr. Epoch 0 remains closed.
196. Joint r1 terminal gate passed:
     - custom `8267310950965575680` / pipeline `6159088389292294144`
       succeeded in 3h35m23s with empty error;
     - 73 objects / 346,933,025 bytes, no failure, exact mirror/report;
     - exact share source; best epoch 2 `03c796...1adb7`, last
       `306c05...58a09`; all 200 tensors changed, zero mismatch, 3,330 updates;
     - train `10.105607→9.687044→9.418839`, validation
       `10.088126→9.613643→9.491410`; all nine finite and weight-consistent;
     - response continuous-density NLL legitimately decreases below zero;
       absolute value/outer L2 remains rejected;
     - fresh reload/invariants pass, closure ≤2.385e-7 GeV, T4 headroom
       `24.988%`, FP32 8/8 timing `276.981 ms/event`;
     - all 50×5 contracts pass, zero test; localhost 15 snapshots;
     - watcher stopped; conservative `$3.20` charge gives `$21.49` accounted,
       `$78.51` remaining.
     Joint diagnostics are complete, not physics validation. Next gate is the
     real-T4 mid-epoch interruption/recovery proof.
197. Mid-epoch interruption r1 pre-submit passed:
     - new template `3ea4d7...849c8`, CLI-frozen `0a35fc...7d75a`;
     - one-epoch FP32 joint, batch 6×accum 4, exact joint best
       `03c796...1adb7`, snapshot every 50 updates;
     - 1,500-second timeout is intentionally shorter than measured epoch;
     - generation-0 overlay 4 objects; merged 209 objects /
       5,973,774,683 bytes, exact real hashes, zero forbidden/collision;
     - focused `19 passed`, compileall clean;
     - worst interrupt reserve `$0.50`, leaving `$78.01`.
     No interruption job at this boundary.
198. Submitted exactly one interruption leg: pipeline
     `6029904569121636352`, custom `8356299649681719296`, initial pending.
     Independent server describe proves one match and exact r16/base/overlay/
     output/config/split/CUDA/on-demand one-T4/disk/SA/1,500-second timeout.
     No postflight is requested because the timeout is intentional. Observer
     session `59897`; inflight snapshot and expected-timeout gates remain
     closed.
199. Interruption job entered running at 14:13:49. After two expected empty
     preflight-era checks, immutable inflight snapshots appeared at updates 50
     and 100. Update 100 mirror (2 objects / 29,367,708 bytes) independently
     passes: checkpoint SHA `8c926e...ce70`, joint epoch 0, update 100,
     next batch/train count 400 of 4,437, batch 6×accum 4 boundary, optimizer/
     scheduler step 100, finite model and all nine aggregates, scaler and
     CPU/CUDA RNG present, recomputed contract exact, correct no-prior-best
     +infinity, validation-only visualization. Update 50 remains preserved.
     Resume stays closed pending the declared timeout.
200. Sleep-safe handoff: server-side interruption job continues independently
     of the desktop; immutable GCS snapshots exist at updates 50/100/150/200.
     Update 100 is locally mirrored and fully verified, so no accepted progress
     depends on a local observer. After wake, capture the authoritative timeout,
     do not duplicate the interrupt leg, and submit at most one new resume leg
     from verified SHA `8c926e...ce70` (or independently verify a later source).
201. Interruption ended `CANCELLED/CANCELED` after 25m18s, exactly the
     predeclared timeout, with no false terminal result and five immutable
     snapshots through update 250.
202. Update 250 independently passes: SHA `9730d7...abbc`, joint epoch 0,
     update 250, next step/train count 1000/4437, batch 6×accum 4 boundary,
     optimizer/scheduler 250, finite model/nine aggregates, scaler/RNG/contract,
     correct no-prior-best. Update 100 remains fallback.
203. Resume pre-submit passed: template `735f3f...24610`, CLI-frozen
     `b50e9c...c4cc4`; corrected diff only project/template and init→exact
     resume source. Merged staging 209 objects / 5,973,779,017 bytes, exact
     real hashes, zero forbidden/collision; `19 passed`, compileall clean.
     `$21.99` accounted, `$78.01` remaining; two-hour reserve leaves `$76.31`.
     No resume job at this boundary.
204. Submitted exactly one mid-epoch resume leg: pipeline
     `2118880136471248896`, custom `3541091829929738240`. Independent server
     describe proves running and exact r16 image, unique base/overlay/output,
     frozen config, CUDA, one on-demand T4, n1-standard-8, one replica,
     100 GB pd-ssd, accepted service account, 7,200-second timeout, and
     training postflight. No duplicate was submitted.
205. Recovery visualization collision gate fixed before the first recovery
     artifact: optional sanitized run labels now make IDs/files
     run-qualified while preserving the existing 15 stage rows. Focused
     `12 passed`, compileall and dashboard production build pass. The initial
     no-artifact sync correctly waited without mutating the schema-2 manifest.
     Hidden watcher PID `22240` polls every 300 seconds with run label
     `joint-resume-r1`; localhost PID `18520` listens on port 3000. Vertex/GCS
     remain server-side if the desktop sleeps.
206. Localhost asset-route QA rejected vinext production mode: `/` returned
     200 but `/data/manifest.json` returned 404. A hidden dev server was
     started at `http://localhost:3001/`; both root and manifest return 200,
     with the preserved 15 snapshots through `joint:0002`. Serving PID
     `15728` (launcher `11252`). This local correction does not affect
     server-side Vertex/GCS progress.
207. Mid-epoch resume r1 failed closed before epoch 0:
     - custom `3541091829929738240` is `JOB_STATE_FAILED` after 9m03s;
     - exactly six preflight/failure objects, no epoch or checkpoint artifact;
     - preflight independently passed 187 real shards, 26,624/4,096/0
       train/validation/test, and every frozen artifact hash;
     - `vertex_failure.json` and Cloud Logging agree on
       `ValueError: mid-epoch training contract changed`;
     - checkpoint contract `75d9aa...f80d` versus resume contract
       `724662...0dc3`;
     - the sole contract-relevant difference is the necessarily new
       `provenance.template_sha256`; replacing only that metadata value
       reproduces the checkpoint contract exactly.
     The validator must exclude only template provenance metadata while
     retaining all trajectory fields and artifact hashes. No duplicate or
     replacement is authorized until positive/counterexample tests, immutable
     image/staging verification, and budget QA pass.
208. Resume validator correction passes pre-build QA:
     - new normalized contract omits only template provenance metadata;
     - legacy acceptance requires the checkpoint's embedded original config
       to reproduce both its stored old hash and the current normalized
       scientific contract;
     - actual update-250 old hash `75d9aa...f80d` maps to identical embedded
       and resume normalized hash `8522e2...2ee0`;
     - scientific-drift counterexamples remain rejected;
     - focused `15 passed`, full `65 passed`, compileall clean;
     - failed r1 six-object mirror/evidence preserved;
     - official current compute rates support retaining conservative `$0.85/h`;
       `$22.64` post-build planning account plus `$1.70` two-hour replacement
       reserve leaves `$75.66`.
     Build context is 68 files / 277,541 bytes with zero forbidden content.
209. Resume r2 replacement pre-submit passed:
     - Cloud Build `cba19037-9592-4d6d-8098-96037ad7227e` succeeded in 3m29s;
     - immutable r17 digest `10f337...13d00`;
     - new generation-0 r2 overlay has the exact four accepted artifacts;
     - merged staging passes 209 objects / 5,973,779,017 bytes, exact checkpoint
       `9730d7...abbc`, config `b50e9c...c4cc4`, all artifact hashes, real data,
       zero forbidden paths;
     - new output empty, zero matching r2 jobs;
     - exact one-T4 on-demand reference spec and `$75.66` post-reserve budget.
     Exactly one r2 replacement is authorized.
210. Exactly one resume r2 submitted:
     - pipeline `4448472596844904448`, custom `252663657484255232`;
     - independent pending spec matches immutable r17, exact unique inputs/
       output/config, bounded zero-test bank, CUDA/postflight, on-demand
       one-T4 n1-standard-8, 100 GB pd-ssd, SA, and 7,200s timeout;
     - exact name cardinality one, output empty, no duplicate;
     - local SDK observer stopped after identity/server verification;
     - r2 dashboard watcher PID `23596`, 300-second interval, run-qualified
       label; localhost root/manifest HTTP 200.
     Measured remaining training is 50.27m plus about 4.25m epoch overhead and
     about 6.4m staging/preflight. Safe first/only epoch estimate is 60–63m
     after running (70m watch window); this one-epoch proof has no next epoch.
211. Independent mid-epoch terminal verifier prepared while r2 provisions. It
     enforces exact source/normalized legacy contract, update 250→1110 with
     exactly 860 new updates, scheduler/RNG/aggregate continuity, nine finite
     and weight-consistent losses, best/last selection, immutable staging,
     zero test, epoch+reload invariants, T4 headroom, 8/8 timing, and the same
     50×5 validation/Geant4/four-vector selection. Compile/help and full
     `65 passed` QA succeed. No artifact is accepted yet.
212. Resume r2 entered `JOB_STATE_RUNNING` at 18:31:57 Asia/Taipei. The
     18:32:51 300-second timer found empty error and zero output objects.
     Measured epoch artifact ETA is 19:32–19:35; conservative deadline 19:42.
213. Next-gate source is predeclared as accepted default joint-pilot best
     `03c796...1adb7`, not the recovery-proof result. Calibration will be
     train-only, all nine losses, ≤64 batches, clip `[0.25,4.0]`, zero test,
     and proposal-only. No calibration job exists.
214. Re-read `docs/AGENT_PROMPT_VERTEX_RUN_AND_ANALYZE.md` at user request. It
     is the historical post-smoke handoff and explicitly stops after planning
     absent later authorization. Subsequent user authorization and accepted
     response→profile→count→support→share→joint evidence supersede that stop;
     it does not permit bypassing or duplicating active recovery r2.

215. At 18:44:41 local, recovery r2 remains running with no error and zero
     output objects; measured artifact ETA remains 19:32–19:35, conservative
     deadline 19:42. Existing 600s timer and 300s visualization watcher remain
     the only monitors; localhost root/manifest are HTTP 200.
216. Prepared calibration runner passes compile, both CLI-help paths, and
     focused hardening (`15 passed`). It strictly requires accepted joint
     checkpoint hash, frozen-artifact/shard preflight, train-only zero-test
     input, CUDA, all nine finite positive gradient medians/weights,
     `[0.25,4.0]`, >=15% T4 headroom, and one on-demand T4. No calibration was
     submitted. Initial system-Python module lookup and git diagnostics failed
     because the repo is not installed and has no `.git`; corrected
     `PYTHONPATH` QA passed and neither diagnostic mutated state.
217. Dashboard QA found and corrected two React effect lint failures plus a
     stale epoch-request race. Corrected SHA `0ab8c04f...b6ed6`; ESLint clean,
     all five production-build phases pass, rendered contracts `2 passed`, and
     live root/manifest HTTP 200. Browser bridge setup still fails before page
     discovery with kernel-assets `os error 3`; no unsupported substitute was
     used. Recovery timer at 18:49:16 remains clean/running/zero-output, and
     one new 600s timer plus the existing 300s watcher are active.
218. Calibration now independently binds the exact checkpoint to geometry,
     dataset manifest, split manifest, and seed provenance. Counterexamples for
     every field fail. Updated runner `b4db4a9d...6e684`; focused QA `19
     passed`, full Python `67 passed` with four known nonfatal warnings,
     compileall clean. No image or calibration job exists.
219. Calibration no longer downloads the irrelevant historical share
     initializer; training retains strict resolution by default. Updated stage
     helper `f4ab4635...b1898`, runner `1590cc87...a8ee`, tests
     `4226264d...a12be`; focused `20 passed`, full `68 passed`, compile clean.
     Accepted config/splits/assignment/joint-best generations and sizes were
     read independently. Proposed calibration r1 input/output are empty and
     matching job count is zero; nothing submitted before recovery gate.
220. Recovery r2 immutable mid-epoch updates 300/350/400 verified. Update 400
     mirror SHA `88d3621a...8ae88`, exact contract `8522e2...2ee0`,
     next-step/train-count 1600, optimizer/scheduler 400, RNG/scaler present,
     all nine finite, weighted mean agreement `9.62e-9`. Two measured 50-update
     intervals are ~162s; revised terminal estimate 19:40–19:43 after 710
     remaining updates plus validation/viz/upload. Job remains running; no
     terminal or physics result accepted.

221. Recovery progressed through update 650 with zero warning/error logs.
     Update-650 mirror SHA `f7373fbf...e7154`, next-step 2600,
     optimizer/scheduler 650, RNG/scaler present, all nine finite, mean loss
     `9.6344414`, response NLL `-0.7876329`, weighted agreement `6.21e-9`.
     Remaining 460 updates plus terminal overhead keep ETA 19:41–19:43.
222. Independent calibration terminal verifier `1e674a7e...18583` now checks
     six-file immutability, all hashes/staging, 64 train-only batches, all nine
     medians and recomputed weights, accepted checkpoint provenance, real
     187-shard 26,624/4,096/0 preflight, and T4 headroom. Initial nested-hash
     schema assumption was corrected before use and fixture-tested
     (`4b9867b6...5b48d`). Focused `21 passed`, full `69 passed`, four known
     warnings.

223. Recovery update 750/1110: next-step 3000, unchanged contract, cumulative
     mean `9.6006083`; update-650→750 window mean `9.3806933`, all nine finite,
     response NLL `-0.8429774`. Progress only; validation/fidelity not inferred.
224. Recovery update 850/1110: next-step 3400, cumulative mean `9.5802340`,
     unchanged finite contract; 260 updates plus terminal overhead project
     19:42–19:44. Calibration staging verifier `83798a95...d4559` adds a strict
     extra joint-checkpoint path/SHA mode without weakening training defaults;
     focused `22 passed`, full `70 passed`.
225. Final pre-terminal update 1050 mirror SHA `2fada9c0...257b8`: next-step
     4200, optimizer/scheduler 1050, RNG/scaler present, all nine finite,
     cumulative/weighted means agree within `8.23e-10`, response NLL
     `-0.7996685`, zero warning logs. About 60 updates remain; terminal ETA
     19:43–19:45.
226. At 19:42:46, update 1100/1110 has next-step 4400/4437, unchanged finite
     contract, cumulative mean `9.5417563450`; only 37 loader batches remain.
     Job is running with no terminal artifact, so validation/postflight remains
     open.
227. Recovery r2 custom `252663657484255232` succeeded after 1h13m27s.
     Independent 66-object / 644,958,608-byte mirror verifier
     `f3cc988b...861a2` passes source update250→terminal1110 with exactly 860
     new updates, best `492a0c...7bd27`, last `d4eb83...d6be`, train/validation
     `9.540616/9.480989`, all nine finite, exact staged 26,624/4,096/0 real
     bank, zero invariant failures, closures <=7.63e-6 GeV, T4 headroom
     25.019%, and 8/8 `272.711 ms/event`.
228. Fixed 50×5 validation/Geant4/four-vector/seed contract passes; descriptive
     response/hit/profile values +8.699%/-7.102%/0.254396 are not physics
     validation. Localhost now has 16 snapshots including
     `joint-resume-r2:joint:0000`; exact watcher PID 23596 stopped after sync.
     Conservative r2 charge $1.10 makes accounted $23.74, remaining $76.26.
     Recovery gate complete; calibration is next.

229. Calibration build pre-gate: worst-case account $25.94 leaves $74.06;
     context 69 files / 287,421 bytes, zero forbidden, exact key hashes, zero
     existing r18 tag. One image build authorized; job still closed.
230. Build `53a48555-ad34-416b-bc1e-585be9f4f8ba` succeeded; immutable r18
     digest `c31f0835...96b7d`. Generation-zero four-object calibration overlay
     plus prep passes 209 objects / 5,973,774,654 bytes, exact config/data/
     geometry/split/assignment/joint-best hashes, zero forbidden; verifier
     `5d354a50...f322c`. Output empty, matching job count zero, exact one-T4
     64-batch train-only spec and $74.06 post-reserve capacity. One submission
     authorized.
231. Calibration pipeline `5827277770262052864` / custom
     `767991563283333120` was submitted exactly once. Independent describe
     confirmed r18, prep/overlay/output/config/checkpoint, CUDA, one on-demand
     T4, n1-standard-8, 100GB pd-ssd, service account, and 7200s timeout. It
     entered running at 20:07:12 Asia/Taipei and failed closed at 20:14:45.
232. Immutable r1 failure output has 4 objects / 72,894 bytes and is preserved
     under `audit/calibration_joint_r1_failure/`. Failure SHA
     `0497383e...7c4f` and worker logs independently prove T4 OOM at the
     support graph: 14.28GiB live PyTorch allocation, 129.78MiB reserved but
     free, 35.56MiB device free, failed 44MiB request. No proposal exists and
     neither r1 prefix may be reused. Conservative charge $0.15 gives $23.89
     accounted / $76.11 remaining.
233. Root cause is full nine-loss graph retention across nine gradient-norm
     calls, not training, input, checkpoint, schema, or fragmentation. A
     memory-bounded correction computes response/profile/count/support/share
     family graphs in identical stochastic order, differentiates every family
     component, and releases each graph before the next. It requires every
     component exactly once per batch and records 64 observations each; no
     loss, batch, precision, headroom gate, or selection rule is weakened.
234. Corrected weight/calibrator/verifier source SHAs are
     `34016279...a38787`, `c898081d...459056`, and
     `7957c0fc...ac7`. Full QA passes 71 tests with four known nonfatal
     Transformer warnings and clean compileall; strict Ruff found inherited
     compact syntax in the touched weight file, which was formatted, after
     which Ruff and focused 23-test QA passed. A replacement remains closed
     pending a new image, unique r2 prefixes, fresh staging/spec/cardinality,
     and budget gates.
235. Corrected Cloud Build `f0fd292a-e8d2-4775-8974-4403eef0f494`
     succeeded in 3m21s; independent registry digest is
     `sha256:bbcb57e9...a382b`. Build context 69 files / 288,831 bytes had zero
     forbidden content. Fresh budget reserve gives $26.09 worst case /
     $73.91 remaining.
236. Generation-zero r2 overlay has 4 objects / 29,415,631 bytes. Independent
     verifier `2cdec270...58440` passes merged 209 objects /
     5,973,774,654 bytes, real exact config/data/geometry/split/assignment/
     checkpoint hashes, zero forbidden/collision, and 26,624/4,096/0
     train/validation/test. R2 output is empty and matching-job cardinality
     zero; exactly one corrected calibration submission is authorized.
237. Corrected calibration pipeline `579739779445293056` / custom
     `5885120877976092672` was accepted exactly once. Independent server spec
     matches the entire authorized r19/on-demand-one-T4/input/output/config/
     checkpoint/64-batch/clip/CUDA/disk/SA/timeout contract. Exact local SDK
     observer PID 5416 was stopped after acceptance; fresh server state remains
     pending. One 600-second timer is the only poller.
238. Post-submit synthetic regression (not physics validation) proves identical
     all-nine loss values and shared-encoder gradient norms between the
     original joint graph and memory-bounded grouped graphs under the same
     model/batch/RNG; test SHA `6bb93ca2...d8fea`, Ruff pass, 5 tests pass.
     Up to five on-demand T4s may later run independent, predeclared validation
     variants concurrently, but calibration/dependent gates remain serial and
     every parallel wave needs a combined worst-case budget reservation and
     unique generation-zero prefixes.
239. User narrowed the outcome to an A100 viability decision, not final
     publication training. Predeclared five-way one-epoch wave is default
     control; calibrated LR 3e-5/1e-4/3e-4; calibrated LR1e-4 effective-batch
     half-control. Exact real bank/checkpoint/FP32/fixed-50x5/zero-test gates
     remain. At most two continue several epochs; result is GO/CONDITIONAL
     GO/NO-GO, never physics validation.
240. Unfrozen viability generator `4244704c...e494b` and tests
     `58eab82d...f23a5` pass Ruff/compile and combined 8 tests. R2 allocated at
     20:35:18 local. Existing 600s calibration timer remains; later measured
     epoch timer is 4200s from 3878s training plus terminal overhead.
241. Dashboard inventory correction: an initial read-only query used the
     nonexistent `snapshots` field and printed zero. The schema-3 field is
     `epochs`; independent parsing proves 16 accepted snapshots, latest
     `joint-resume-r2:joint:0000`, fixed selection hash
     `f7052919...59b6`, and zero test events. No dashboard mutation occurred.
242. Calibration r2 job `5885120877976092672` succeeded in 10m34s. Strict
     independent verification of six objects / 75,643 bytes passes: exact
     209-object real staging, checkpoint `03c79608...adb7`, 64/64 train-only
     batches, all nine finite gradients with 64 observations, zero test, and
     T4 peak 6.081 GB / 15.656 GB (61.161% headroom). Verification SHA is
     `be5f135a...0945`; scientific status remains train-only proposal.
243. Accepted mean-one calibration weights range from `0.1609010445` for
     response/profile/count to `2.574416712` for visible. They compensate
     measured shared-encoder gradient scales and must be validation-screened;
     no single aggregate weighted loss is a fidelity claim.
244. Evidence-copy QA preserved a flattened first mirror and then created an
     exact-path non-overwriting mirror that passed. Dashboard lint/build/two
     HTML tests and HTTP 200 pass; interactive visual QA is unclaimed because
     the browser bridge failed with local path error 3. The manifest trend
     object itself is correct.
245. Conservative accounted budget is `$24.54`; five two-hour T4 reserves are
     `$8.50`, plus `$5.00` contingency, leaving `$61.96`. The predeclared
     five-way one-epoch A100-viability wave therefore fits the `$100` ceiling.
246. Five frozen configs passed exact matrix QA (report `7ae19f73...34f4`):
     default; calibrated LR `3e-5/1e-4/3e-4`; calibrated LR `1e-4` effective
     batch 12. All bind checkpoint `03c79608...adb7`, identical production
     provenance, FP32, seed 20260723, one epoch, fixed 50x5 validation, and
     zero test.
247. Ten new GCS prefixes and five display names were empty. Generation-zero
     config overlays plus the immutable calibration checkpoint/split overlay
     each pass 210-object real-staging verification; report hashes are
     `f1f28b73...b3e2`, `816dfde6...f919`, `153afbe5...5a1c`,
     `af24e406...7818`, and `51c43885...f359`.
248. Exactly five on-demand T4 jobs accepted: default `1645340269597425664`,
     calibrated LR3e-5 `2259914492966076416`, calibrated LR1e-4
     `5596221998754693120`, calibrated LR3e-4 `8082035270226018304`, and
     half-batch `4196752603805122560`. Server specs independently match r19,
     one T4/n1-standard-8/one replica/100GB pd-ssd/7200s/exact overlays,
     configs, outputs, and SA. Initial state is pending; no duplicate exists.
249. Exact submitter processes were identity-checked and stopped after server
     acceptance; jobs remained pending. Poll allocation after 300s, then use
     `start + 4200s` as conservative first-epoch/terminal timer.
250. Post-submit Ruff/compile pass. Two zero-test invocations used nonexistent
     historical test filenames and are preserved as command errors; corrected
     `PYTHONPATH=src` calibration/viability suite passes 8 tests with one known
     nonfatal Transformer warning.
251. Before results, `docs/A100_VIABILITY_PROTOCOL.md` froze hard gates,
     same-weight-family comparisons, Pareto tolerances, maximum-two
     continuation, two additional epochs, and exact GO/CONDITIONAL-GO/NO-GO
     rules. Official NVIDIA and Google sources were rechecked; no A100 speedup
     is claimed without a target-stack 256-batch plus 8/8 benchmark.
252. All five jobs allocated concurrently from `13:04:50Z` to `13:05:39Z`;
     conservative epoch/terminal ETA is 22:14:50–22:15:39 local. A 1200s
     health timer precedes the remaining interval.
253. Output verifier `a1d585de...0e2d` now supports joint→joint source,
     one-epoch/update-50 contracts, and an additional exact overlay while
     retaining historical defaults. Ruff/compile and eight existing tests pass;
     this local tool change does not alter running image/jobs.
254. Full 50x5 output analysis now reports truth/generated zero-response,
     deposit diversity, and response spread. The first test exposed shallow
     copying in its synthetic fixture; replacing the nested fixture object
     supplied the intended counterexample. Final verifier `92a47237...88c6`;
     Ruff and corrected 9-test suite pass.
255. Pre-result analyzer `84f77f4b...ce66` implements weight-family-safe
     comparisons, toleranced Pareto dominance, deterministic tie breaking, and
     maximum-two continuation. Its first cross-family test accidentally
     improved response too; equalizing non-aggregate metrics isolated loss
     incomparability. Ruff and combined 12 tests pass.
256. At 1200s all five jobs run. Batch-6 snapshots are update 350/1110;
     half-batch is 650/2219. Independent local SHA/load QA proves five worker
     hashes, 207 finite tensors, optimizer/scheduler steps, next batches,
     Torch/CUDA RNG, and expected no-prior-best state. Partial calibrated train
     means are `5.0738/5.1380/5.4134/5.1541`; default `9.7495` is not
     cross-family comparable.
257. Measured train projections are 3550–3805s; revised terminal ETA is
     22:25–22:35 local and next timer is 3000s.
258. Pre-result scheduler QA proved restoring a one-epoch cosine state beyond
     `T_max` would make LR rise. Wave 2 now explicitly preserves optimizer
     moments/RNG/best/epoch but restarts only LR and a two-epoch monotonic
     cosine horizon. Config requires paired resume; focused 33 tests pass.
     Unscoped Ruff exposed 42 historical compact-style findings; scoped lint
     ignoring only E701/E702/E703 passes. Running r19 jobs are unchanged.
259. Continuation pre-build at `92752af`: full 81 tests and compileall pass.
     Repo-wide Ruff additionally exposes 12 historical unused/ambiguous-name
     findings outside the changed path; scoped changed-file lint passes. A
     `$0.50` image build remains inside the already reserved `$5` contingency
     and leaves `$61.96` after all worst-case reserves.
260. Cloud Build `46b06a98-3741-4e6e-8df8-be175260b86e` succeeded in 2m35s
     from the 75-file/300 KiB allowlist. Independent registry digest is r20
     `sha256:8b4a94c0...9048f`. No job uses it yet. Accounted spend is `$25.04`;
     remaining after live-wave worst reserve and contingency is `$61.96`.

## Implementation QA disposition

- Local software/contract state: pass.
- Full production data preparation r5: pass.
- On-demand T4 full-architecture FP32 smoke: structural/infrastructure pass.
- Validation-only component, loss-calibration, and optimizer pilot work: GO.
- Physics validation: not established. The one-epoch high-level C2ST AUC is
  `1.0`, which explicitly demonstrates that structural success is not fidelity.
- Final training and test evaluation: blocked. Loss weights, learning rate,
  statistical-floor-informed acceptance gates, component diagnostics,
  full-evaluation memory behavior, and the required six-run final matrix remain
  unfinished.
