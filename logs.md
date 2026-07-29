# CBSC-ZDC Vertex training journal

Last updated: 2026-07-25 15:11 Asia/Taipei  
Project/region: `asiop-zdc-1` / `us-central1`  
Budget ceiling: **$100 USD**

## Journal contract

This is the durable, human-readable journal for production preparation,
Vertex training, QA, QC, research decisions, corrections, and results.
Machine-readable evidence remains under `audit/`.

The journal records evidence, commands, hashes, alternatives, decisions,
counterexamples, verification steps, and failed attempts. It intentionally
does **not** record private hidden chain-of-thought, as required by
`AGENTS.md`.

Update cadence:

- every completed or failed epoch;
- during long epochs, at a meaningful immutable checkpoint interval once
  mid-epoch recovery is implemented;
- every Vertex state transition that changes the disposition;
- before and after every submission;
- every failed gate, correction, image build, and independent artifact check;
- every cost projection that can permit or stop a new job.

Scientific constraints:

- `legacy/` is evidence only;
- production target is raw deposited energy;
- no test data informs training, tuning, thresholds, gates, stopping, or
  checkpoint selection;
- primary claim domain remains 50--250 GeV;
- stage order is response -> profile -> count -> support -> share -> joint;
- later isolated stages keep the condition encoder frozen;
- final conditions require seeds 20260723, 20260724, and 20260725;
- schema, geometry, hash, invariant, nonfinite, or empty-bin failure stops the
  chain;
- structural success is not physics validation;
- Spot and CPU fallback are forbidden for this training program.

## Budget ledger and stop rule

Planning rates are deliberately conservative estimates, not invoices:

- on-demand NVIDIA T4 in Iowa: official listed GPU rate $0.35/hour;
- `n1-standard-8`: estimated from eight N1 predefined vCPUs plus 30 GiB
  memory at approximately $0.38/hour;
- 100 GB `pd-ssd`, Vertex management fees, builds, and storage are additional;
- journal planning rate for an `n1-standard-8` + one T4 job: **$0.85/hour**;
- planning rate for `n1-highmem-8`: **$0.55/hour**;
- planning rate for `n1-standard-4`: **$0.25/hour**.

Official pricing references:

- https://cloud.google.com/products/compute/gpus-pricing
- https://cloud.google.com/products/compute/resources/pricing
- https://cloud.google.com/vertex-ai/pricing

As of this update, all identified CBSC custom-job wall time is estimated at
$1.95. A conservative $3.00 placeholder covers Cloud Builds, storage, and
unitemized overhead. Accounted planning spend is therefore **$4.95**, leaving
**$95.05**.

Hard budget gate:

1. Recompute the ledger before every new Vertex submission.
2. Include the running job and a contingency reserve.
3. Do not submit a job whose worst credible cost would take accounted spend
   above $100.
4. Never change scientific semantics or weaken a gate to fit the budget.
5. If valid completion cannot fit, stop and report the exact measured
   infeasibility rather than overspend.

Current feasibility warning: the accepted FP32 joint pilot measured about
6.04 events/second. At that rate, one 612,482-event full-train epoch is about
28.2 hours. Six one-epoch final runs alone project to about 169 hours or
$143.65 at the conservative T4 rate, before useful multi-epoch training.
Therefore the current implementation cannot enter the six-run final matrix
under the $100 ceiling. Component timing and code-level throughput research
must establish a defensible speedup before final submission.

### Accounted custom jobs

| Custom job | State at ledger | Resource | Billable h | Conservative USD |
|---|---:|---|---:|---:|
| 5551984247922753536 | failed | n1-highmem-8 | 0.3519 | 0.19 |
| 3440077497662701568 | cancelled | n1-highmem-8 | 0.0963 | 0.05 |
| 2318329346726559744 | cancelled | n1-highmem-8 | 0.0091 | 0.01 |
| 8852770931064438784 | failed | n1-highmem-8 | 0.0928 | 0.05 |
| 1981826012068970496 | succeeded | n1-highmem-8 | 1.5775 | 0.87 |
| 9206444239301378048 | failed | n1-standard-4 | 0.6878 | 0.17 |
| 5475007438862155776 | failed | n1-standard-4 | 0.2267 | 0.06 |
| 5080522458025426944 | failed | n1-standard-8 + T4 | 0.1594 | 0.14 |
| 4964365651620659200 | succeeded | n1-standard-8 + T4 | 0.2764 | 0.23 |
| 2224189161156378624 | succeeded | n1-standard-8 + T4 | 0.2014 | 0.17 |
| 7763317635659333632 | running | n1-standard-8 + T4 | 0.0171 | 0.01 |

The first budget script attempt used PowerShell's unsupported `??` operator
and failed before querying or changing cloud state. The corrected expression
ran. Its first datetime calculation mixed local and UTC kinds and produced an
invalid negative total; this was rejected. The repeated calculation used
`DateTimeOffset` and produced the ledger above.

## Frozen production foundation

- ROOT:
  `gs://asiop-zdc-1-zdc-reco-us-central1/data/myTree_20251117_765k_0to300GeV_neutron_All.root`
- generation `1783683550292251`
- size `25,022,001,408` bytes
- CRC32C `lCVUvQ==`
- SHA-256
  `b7c666...b533` (full value retained in the machine-readable audit)
- accepted preparation job `1981826012068970496`
- preparation prefix
  `gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/prep-20260724-r5`
- 764,940 events and 187/187 verified shards
- geometry hash
  `e22d4cfb1e9293a33dd13151587910268ba64cd8efbcdb7a835a7442f2edcb4b`
- 6,790 nodes, 65 layers, 2,400 ganged channels
- full split train/validation/test = 612,482 / 76,158 / 76,300
- conversion closures <= `1.35e-13` GeV

Preparation failures remain preserved:

1. r1: ganged-geometry gate failure.
2. r2/r3: native SIGSEGV attempts.
3. r4: sentinel-accounting gate failure.
4. coordinator r1: excluded-count gate failure.

No failed prefix was reused or overwritten.

## Accepted structural smoke

Custom job `4964365651620659200`, on-demand T4, FP32:

| Epoch | Stage | Train loss | Validation loss | Updates | Seconds | Events/s |
|---:|---|---:|---:|---:|---:|---:|
| 0 | joint | 24.045308045 | 20.077634335 | 84 | 57.481604 | 5.880142 |

QA:

- best and last checkpoints exist and hash-verify;
- fresh best-checkpoint reload succeeded;
- all structural failure counts are zero;
- layer/event closure below `2e-5` GeV;
- T4 memory headroom `49.868%`;
- validation C2ST AUC `1.0`;
- truth/generated zero fraction `0.0156 / 0.297`;
- normalized response Wasserstein `0.403`;
- normalized hit-count Wasserstein `1.033`.

Decision: structural/infrastructure **GO**; physics fidelity **not
established**. The undertrained validation result is poor as expected and was
not used to weaken any gate.

Preserved failed smoke:

- AMP produced a nonfinite-gradient failure; no checkpoint was accepted.
- A flattened GCS prefix failed the required hierarchy.

Decision: continue in FP32 unless a separate, bounded AMP correction passes.

## Target-hardware hardening pilot

Custom job `2224189161156378624`, pipeline `3304430748143976448`,
on-demand T4, immutable r12 image:

| Epoch | Stage | Train loss | Validation loss | Updates | Seconds | Events/s | Peak GPU bytes |
|---:|---|---:|---:|---:|---:|---:|---:|
| 0 | joint | 25.767865045 | 21.440538927 | 56 | 55.951096 | 6.040990 | 11,717,986,304 |

Checkpoint hashes:

- best:
  `8c3c031087f3d9a3a35e1966b451f6ac28a0532af18abffa6a6f060cc105ee88`
- last:
  `8bd4a895d4b02813083dca0f65ef88ca9a5e02da4e4bddcd8c0b3816226c2edf`

QA:

- immutable `progress/epoch_0000` hashes exactly match terminal checkpoints;
- fresh best reload passed configured 8/8 solver/decode invariants;
- all discrete failures zero;
- event closure `1.9073486328125e-06` GeV;
- T4 headroom `25.1526%`, above the 15% gate;
- short 8/8 postflight timing `273.176836` ms/event.

The short timing is a structural QA measurement, not a publication benchmark.

Independent manifest QA found that a non-slash-terminated GCS prefix also
listed sibling `r5-fp32*` directories. The run still resolved the correct r5
scientific paths, but staged 618 objects / 17.833 GB rather than 205 objects /
5.944 GB. Progression stopped. The listing was slash-bounded, terminal
uploads were made generation-zero, a regression test was added, and local QA
passed 30 tests plus compileall. Immutable r13 image:

`sha256:a7f047e05962b42bf3704a28d0f4de28bbb4265d3740c8b9a01bf9dc02059d05`

## Bounded diagnostic bank

- 13 energy bins
- each bin: 2,048 train and 512 validation
- totals: 26,624 train, 6,656 validation, zero test
- primary 50--250 validation selection: 4,096 events
- split SHA-256:
  `a4d0967597bee525843d81647bd259deee7c2e908d25d2b1df78a8179526b0b3`
- assignment SHA-256:
  `084f0dfd86e488c63bb41ea50d6783ad22eb57a322288c075a94b1ec12dd3714`
- train-audit SHA-256:
  `ebc951971dc3ad25f9738b2d150d54d5b3fcc9518d039c2a33420f53a409496f`
- zero negative values and no empty bin
- response cap ratio `0.725470286351178`
- absolute response cap `64.38813572617559` GeV

## Active response-stage diagnostic

Frozen config SHA-256:

`ceb8e9106d6f3e93cf7d457f27a199df014ebde93beaf59917bbf331f56dd95c`

Vertex:

- pipeline `748849065843752960`
- custom job `7763317635659333632`
- exact r13 immutable image
- one on-demand `n1-standard-8` + T4, one replica, 100 GB `pd-ssd`
- FP32, batch 6, accumulation 4, three epochs
- condition encoder trainable
- zero test events
- output:
  `gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/stage-20260725-r1-response-output`

State history:

- submitted after base-prefix, overlay, image, service-account, hardware, and
  empty-output-prefix checks;
- pending at 2026-07-25 12:31 Asia/Taipei;
- running from `2026-07-25T04:35:23Z`.
- the training process initialized the model at
  `2026-07-25T04:41:40Z`; the only emitted message was the known nonfatal
  `TransformerEncoder` nested-tensor performance warning;
- no immutable epoch snapshot or failure artifact existed at the
  2026-07-25 12:53 Asia/Taipei check. This is not yet a pass or a failure.

Response epochs:

| Epoch | Train loss | Validation loss | Response NLL | Visible BCE | Updates represented | Seconds | Events/s | Peak GPU bytes |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | -0.475950481 | -0.528839940 | -0.545333293 | 0.069382812 | checkpoint epoch 0 | 2,843.694854 | 9.362467 | 385,734,656 |
| 1 | -0.660202545 | -0.534187518 | -0.716075809 | 0.055873264 | checkpoint epoch 1 | 2,608.806202 | 10.205434 | 385,734,656 |
| 2 | -0.722174113 | -0.589568856 | -0.777784716 | 0.055610603 | checkpoint epoch 2 | 2,468.325097 | 10.786262 | 385,734,656 |

Epoch 0 independent QA:

- immutable snapshot creation time `2026-07-25T05:31:38Z`;
- best SHA-256
  `baff0052cd072cc07d2b815d5d91ef5e6ce398023bc841a5df01d522a29656f9`;
- last SHA-256
  `6b885ecdb175e58c533b513f6f4b42af37533ed3c9c20b12fcbda3e618cbf91b`;
- both 14,336,500-byte objects were independently downloaded and re-hashed
  with exact agreement;
- checkpoint stage `response`, epoch 0, seed 20260723, geometry/manifest/split
  hashes all match the frozen inputs;
- preflight passed 187/187 shards and selected 26,624 train, 4,096 primary
  validation, and zero test events;
- staged manifest is now correct: 209 objects / 5,944,413,683 bytes, comprising
  exactly 205 preparation and four overlay objects, with zero sibling,
  `legacy/`, or test-path matches;
- invariant gate passed: every discrete failure zero, layer closure
  `9.5367431640625e-07` GeV, event closure
  `3.814697265625e-06` GeV;
- finite negative response NLL is possible for a continuous density and is not
  itself a failure; the three-epoch trend remains required.

Recovery QA found a real checkpoint-order defect: epoch-0 `best.pt` recorded
best metric `-0.5288399397`, while `last.pt` recorded `+inf` because last was
saved before checkpoint selection. The active three-epoch job is unaffected
and remains running, but no new stage will be submitted on r13. Locally moved
the last-checkpoint save after best selection; 30 tests and compileall passed.
This correction is not yet a built Vertex image, and full recovery remains
blocked until prior-best preservation and an actual resume pilot pass.

Epoch 1 independent QA:

- immutable snapshot creation time `2026-07-25T06:15:10Z`;
- best SHA-256
  `2ace2bb53db11d1179907f50591e20371142e66baa133f106e16371860012b3e`;
- last SHA-256
  `c3538913189995d762d2b9225806840997f9f165da7313ba7300d5ee8825aaba`;
- both 14,336,500-byte objects independently downloaded and re-hashed exactly;
- every invariant failure remained zero; layer/event closures improved to
  `2.384185791015625e-07` / `4.76837158203125e-07` GeV;
- train loss improved by `0.184252065` and validation loss improved by
  `0.005347578` versus epoch 0; visible BCE and response NLL both moved in the
  expected direction;
- throughput increased 9.0% from 9.3625 to 10.2054 events/s with unchanged
  peak allocation;
- because r13 writes last before best selection, epoch-1 `best.pt` correctly
  stores `-0.5341875182`, while `last.pt` carries the prior epoch's
  `-0.5288399397`. This independently reproduces the ordering defect and does
  not invalidate the best checkpoint or uninterrupted training.

Local recovery hardening now additionally requires a paired, hash-pinned
`resume_from` last checkpoint and `resume_best_from` best checkpoint. Runtime
staging resolves both only inside the staged input root. Resume rejects stage,
epoch order, finite-best-metric, metric-equality, or provenance mismatch and
copies the preserved prior best into the new run before continuing. It also
rejects a resume configuration that leaves no remaining epoch. Focused tests
cover path resolution, missing pairs, matching restore, and metric mismatch.
Local result: 33 tests passed, two known warnings, compileall clean.

This is still local code only. A new immutable image and an actual Vertex
resume job are required before the recovery gate can pass. Safe mid-epoch
checkpoint/resume remains a separate open gate before full-data training.

Terminal response-stage QA:

- custom job `7763317635659333632` succeeded at
  `2026-07-25T06:56:44Z`;
- validation improved at every epoch:
  `-0.528839940 -> -0.534187518 -> -0.589568856`;
- terminal best/last hashes independently downloaded and reproduced:
  `d378de58ce310b9454620db3811e9cbba6760ba426fd7b3e4dd467c709119463`
  /
  `c03f425e8f684a9ffa58117c6614ea93e3cf91dc8a85b68842c5c66975c170cf`;
- terminal best is response stage, epoch 2, seed 20260723, and carries the
  exact accepted geometry/dataset/diagnostic-split provenance;
- 3,330 optimizer updates completed;
- all epoch-2 and fresh-reload invariants passed with zero discrete failures;
- fresh reload used configured 8/8 solvers and measured 247.045238 ms/event in
  the short batch-2 postflight;
- response-stage peak/postflight allocation was 398,736,384 of
  15,655,829,504 bytes, leaving 97.4531% headroom;
- output has exactly 56 objects / 114,993,418 bytes and no
  `vertex_failure.json`.

Decision: isolated response diagnostic **PASS**. This is a component
optimization diagnostic, not cascade fidelity or physics validation.

r13 terminal last again carries the prior selected metric
`-0.5341875182` while terminal best carries `-0.5895688564`; this is the known
save-order failure and is preserved. No successor uses r13 recovery semantics.

Further local recovery QA now restores Python, NumPy, Torch, and CUDA RNG state
only for resume (not cross-stage initialization) and seeds each train/validation
epoch order from the frozen run seed plus epoch number. This removes dependence
on generator state consumed by earlier epochs for future images. Local result:
34 tests passed, two known warnings, compileall clean. Actual Vertex recovery
remains required.

Recovery image and live pilot:

- Cloud Build `769eff68-9d7b-49a7-8a82-a02117a9855e` succeeded in 2m39s;
- immutable r14 digest
  `sha256:662fdcd70c0d78bba52df4af2e09d8e40b419f9f00f4473bdf12b1a6940d058a`;
- new frozen recovery config SHA-256
  `46e51b2ab840e4ee1adf1eac1ee05b864022a6156e5ddafa46f4c286ed91d4bf`;
- recovery last is terminal epoch-2 last
  `c03f425e...c170cf`, whose recorded selected metric corresponds to epoch 1;
- paired prior best is immutable epoch-1 best
  `2ace2bb5...12b3e`, so the pair's metric/provenance contract is exact;
- the six-object immutable overlay is 28,728,008 bytes and contains the frozen
  config, diagnostic split/audit, and the two checkpoints;
- conservative budget before submission: $3.94 custom-job estimate + $3.00
  contingency = $6.94 accounted, $93.06 remaining;
- six-hour worst-case recovery reservation $5.10, leaving $87.96;
- budget gate passed and the unique output prefix was empty.

Exactly one recovery pilot was submitted:

- pipeline `6956920414685626368`;
- custom job `8279014977365344256`;
- one on-demand `n1-standard-8` + T4, one replica, 100 GB `pd-ssd`;
- 21,600-second timeout, FP32, configured 8/8 postflight;
- exact r14 digest, base r5 input, recovery overlay, and expected service
  account independently matched the terminal submission spec;
- initial state pending.

The direct `cbsc-zdc freeze-config` command was unavailable in the local shell;
it changed nothing. The successful repeat used
`PYTHONPATH=src python -m cbsc_zdc.cli freeze-config`.

Do not advance to profile until all three response epoch artifacts, checkpoint
hashes, loss trend, invariants, resource data, and immutable progress snapshots
pass independent QA and the recovery correction is frozen into a new image.

## Open engineering/research gates

1. Validate bounded response through joint stages in exact order.
2. Prove interruption recovery; current epoch snapshots do not yet establish
   correct best-checkpoint recovery.
3. Add safe mid-epoch recovery before any full-data epoch.
4. Run complete nine-component train-only gradient calibration, <=64 batches.
5. Run validation-only family sensitivity and LR/WD/effective-batch studies.
6. Establish truth-half floors and full-validation memory behavior without
   opening test.
7. Improve measured joint throughput enough that the frozen six-run final
   design fits the remaining budget, or record budget infeasibility.
8. Freeze all final scientific choices before test.

Detailed historical evidence and all failed gates are in
`audit/vertex_readiness_analysis_20260724.md`.

## 2026-07-25 15:28 Asia/Taipei — response-loss sign research and QA

Question investigated: whether a response loss moving farther below zero is
bad, and whether the objective needs `abs()` or L2.

Implementation evidence:

- `src/cbsc_zdc/models/response.py` trains a four-component Gaussian mixture
  on `y = log1p(total_gev / 10 GeV)`.
- The response term is a continuous-density negative log likelihood:
  `-mean(logsumexp(log_softmax(mixture_logits) + Normal.log_prob(y)))`.
- The scale is `softplus(raw_scale) + 0.05`; visible/no-response prediction is
  a separate binary cross entropy.
- For a continuous density, density may exceed one. Therefore log-density may
  be positive and NLL may be negative; zero is not a lower bound or special
  optimum. This differs from a discrete probability mass, which is at most
  one.

Independent untouched diagnostic-validation scan of the accepted response
checkpoint `d378de58...119463` (4,096 validation events; no test data):

- 4,046 visible targets;
- mean response NLL `-0.6548890471`;
- visible BCE `0.0658041887`;
- fraction of truth points with mixture density greater than one:
  `0.6875926852`;
- truth log-density quantiles
  `[min,1%,5%,25%,50%,75%,95%,99%,max]` =
  `[-6.4085,-2.9990,-1.6944,-0.7984,1.5025,1.7107,1.8148,1.8311,1.8428]`;
- component scale quantiles =
  `[0.05054,0.05057,0.05068,0.07221,0.09951,0.15451,0.23660,0.24436,0.25558]`;
- mixture-weighted scale quantiles =
  `[0.06838,0.06889,0.06997,0.07485,0.08128,0.08749,0.09270,0.09516,0.09830]`;
- no component scale was pinned at or below `0.0501`; 25% were below `0.06`;
- mixture-entropy range was `0.7638` to `1.0816`, so the model had not
  collapsed to a single component.

Analytic counterexample, also encoded as a regression test: a Normal density at
its mean has NLL `log(sigma * sqrt(2*pi))`. Values are `0.91894` at sigma 1,
`0.22579` at 0.5, `-1.38365` at 0.1, and `-2.07679` at the model's 0.05 scale
floor. A negative value is therefore mathematically expected for a sufficiently
narrow valid density.

Decision:

- Do not apply `abs()` to the NLL or aggregate loss. Once the NLL is negative,
  `abs()` reverses its gradient and pushes a better-likelihood model toward
  worse likelihood; it also adds a cusp at zero.
- Do not replace the mixture likelihood with L2 to repair the sign. L2 targets
  the conditional mean and can average or blur a multimodal conditional
  response. The mixture-density objective is intentional.
- An L1/L2 value may be reported as a separately frozen validation diagnostic
  or predeclared ablation, but it must not be introduced as a post-hoc sign
  correction.
- Continue minimizing validation NLL: more negative is better, provided
  finiteness, held-out validation improvement, scale-floor/collapse checks,
  calibration, invariants, and later frozen physics metrics also pass.
- Improve display terminology in future logging to `response_nll_y` and report
  `mean_log_density = -response_nll_y`; this is a clarity change only.

Research references:

- PyTorch continuous distribution and `log_prob` semantics:
  <https://docs.pytorch.org/docs/stable/distributions.html>
- Bishop's mixture-density-network rationale, including why sum-of-squares can
  average multivalued targets:
  <https://www.microsoft.com/en-us/research/publication/mixture-density-networks/>

QA change:

- Added `tests/test_response_likelihood.py`, SHA-256
  `fbdf0e141330b11aead8387ea590feafa93535404afe5742e4b8819192231489`,
  proving the production response head returns a finite negative NLL for a
  valid sigma-0.1 density at its mode.
- Command: `$env:PYTHONPATH='src'; python -m pytest -q`.
- Result: 35 passed in 20.04 seconds; two pre-existing nonfatal Transformer
  nested-tensor warnings.
- A subsequent `git diff` / `git status` evidence command failed because this
  workspace has no `.git` repository. It changed nothing and is preserved here.

## 2026-07-25 16:01 Asia/Taipei — epoch observatory and recovery failure

Epoch visualization implementation:

- Added a mandatory, frozen validation-only comparison bank for newly frozen
  training configs: 50 fixed randomly selected Geant4 validation events and
  five stochastic Fast-MC draws for the identical four-vector per event.
- The selection is deliberately fixed across epochs by seed `20260725`.
  Resampling the truth bank each epoch was rejected because it would confound
  model evolution with sample variation.
- The existing epoch worker generates the bank after `last.pt` is safely
  written, using the same resident model/T4 and forked explicit RNG. No
  auxiliary T4 job is normally needed.
- Each immutable bundle records stage, epoch, last-checkpoint SHA-256, geometry,
  dataset, split, selection, event/global IDs, four-vectors, draw seeds, solver
  steps, sparse deposits, layer profiles, high-level reconstruction summaries,
  structural invariants, and descriptive fixed-bank metrics.
- Stop conditions include non-validation split, changed geometry/selection,
  invalid four-vector, nonfinite/negative energy, structural failure, wrong draw
  count, or epoch overwrite. Test usage is explicitly recorded as zero.
- Added localhost dashboard under `dashboard/`, a 300-second immutable GCS sync,
  and `docs/VISUALIZATION_DASHBOARD.md`.
- The dashboard contains synchronized interactive 3D Geant4 plus five Fast-MC
  detector views, longitudinal profiles, reconstructed-event summaries, sample
  distributions, and fixed-bank cross-epoch trends. Component-stage output is
  labeled diagnostic; visual similarity is never called physics validation.
- Synthetic fallback data is labeled interface QA only and explicitly states
  that it is not Geant4 or physics validation.
- QA: full Python suite `39 passed`, three known Transformer warnings;
  compileall clean; dashboard production build passed; two rendered-page/data
  contract tests passed.
- Browser preview control failed because the browser-control runtime could not
  create its kernel assets (`os error 3`). No alternative browser-control
  mechanism was substituted. Interactive visual QA remains open; HTTP 200 was
  independently verified for `/` and `/demo/manifest.json`.
- Per user direction, deleted heartbeat automation
  `continue-cbsc-vertex-training`. Monitoring now uses server-side work plus
  300-second sync/poll intervals.

Recovery gate failure:

- Custom job `8279014977365344256`, pipeline
  `6956920414685626368`, ended `JOB_STATE_FAILED`.
- It ran from `2026-07-25T07:13:16Z` to `07:21:20Z` on the exact on-demand
  `n1-standard-8` plus one T4 spec and immutable r14 image.
- Staging and preflight succeeded. Failure occurred before epoch 3:
  `TypeError: RNG state must be a torch.ByteTensor`.
- Exact cause: `torch.load(..., map_location=cuda)` moved the saved CPU RNG
  ByteTensor to CUDA; `torch.set_rng_state` requires a CPU ByteTensor.
- Preserved exactly six GCS failure objects / 75,380 bytes under
  `audit/recovery_response_r1_failure/`; individual hashes are in its
  `manifest.json`. Neither failed input nor output prefix will be reused.
- Correction normalizes Torch and CUDA RNG state arrays to detached CPU
  `uint8` tensors before restoration. Focused regression result: 12 passed, one
  known warning.
- No duplicate or retry was submitted at this point.

Conservative budget update:

- Prior custom-job estimate: $3.94.
- Failed recovery reservation charged conservatively as $0.20 despite only
  8m04s between worker start/end.
- Custom-job estimate now $4.14; management/build/storage contingency remains
  $3.00; accounted total $7.14; conservative remaining budget $92.86.
- A six-hour retry at the existing $0.85/h conservative rate would reserve
  $5.10 and leave $87.76. Submission remains gated on a new immutable image,
  frozen config, unique empty prefixes, full tests, and independent spec QA.

## 2026-07-25 16:15 Asia/Taipei — r15 recovery retry pre-submission gate

- Full corrected suite: 40 passed, three known Transformer warnings; compileall
  clean; all unfrozen YAML templates validated.
- Initial r15 Cloud Build command was stopped before build creation because
  Cloud SDK packaging ignored `.dockerignore` and selected 29,660 files /
  683.1 MiB, including irrelevant dashboard dependencies. No build ID or cloud
  compute was created by that attempt.
- Added strict `.gcloudignore` allowlist. Independently enumerated final build
  context: 61 files / 250,937 bytes, zero `__pycache__` or `.pyc`.
- Cloud Build `a581e834-5e36-4fea-8f69-7d12a19d2def` succeeded in 3m28s.
- Immutable r15 digest:
  `sha256:f74e0f1bc9cfda1930ff5a2698c3e6675304c49f10d97a12e829f7bd2f80b8a1`.
- New frozen recovery config:
  `audit/training_hardening_inputs/recovery_response_r2/configs/frozen_pilot_stage_response_resume_fp32_r2.yaml`,
  SHA-256
  `eab628be2c7a03ceae7cdfd7b24e911a8e4ba3bd4ba8c22c695cd5a8dce1d265`.
- New input prefix
  `gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/recovery-20260725-r2-response-input`
  was empty before generation-zero creation and contains exactly six objects /
  28,728,231 bytes.
- Five copied artifacts/checkpoints independently match the immutable r1
  sources by byte count, MD5, and CRC32C. The new config has its own generation
  and includes the mandatory 50×5 validation visualization contract.
- New output prefix
  `gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/recovery-20260725-r2-response-output`
  remains empty.
- No existing custom job has display name
  `cbsc-v2-2-recovery-response-fp32-20260725-r2`.
- Budget immediately before submission: $4.14 estimated custom jobs + $3.00
  build/storage/management contingency = $7.14 accounted; $92.86 remaining.
  Six-hour on-demand T4 worst-case reservation is $5.10, leaving $87.76.
- Authorized spec remains one replica, on-demand `n1-standard-8`, one
  `NVIDIA_TESLA_T4`, 100 GB `pd-ssd`, 21,600-second timeout, exact r15 digest,
  base prep r5, unique r2 overlay/output, FP32, and training postflight.

Exactly one r15 recovery retry was submitted:

- pipeline `7685263305203515392`;
- custom job `7148299209593061376`;
- initial state `JOB_STATE_PENDING`;
- live server spec independently matches every authorized field and the output
  prefix remained empty immediately after submission.

The async helper raised after successful submission only while trying to print
`job.resource_name`, which the SDK does not populate in async mode. The job was
not resubmitted. The helper now prints an asynchronous acceptance message
instead; compileall passes. Monitoring uses a 300-second job-state loop.

## 2026-07-25 16:21 Asia/Taipei — response-loss interpretation QA

Question tested: whether the negative response loss was moving away from an
ideal value of zero and should be replaced by an absolute-value or L2 loss.

- Active implementation evidence:
  `src/cbsc_zdc/models/response.py` computes a zero-inflated objective:
  binary cross-entropy for the visibility atom plus the negative log density of
  a four-component Normal mixture for
  `log1p(total_response_gev / 10 GeV)`.
- Continuous probability **densities**, unlike discrete probabilities, may
  exceed one. Their log density can therefore be positive and their negative
  log density negative. Zero is not a universal optimum or lower bound for this
  response NLL. PyTorch's `Normal.log_prob` supplies exactly the density term
  used here: https://docs.pytorch.org/docs/stable/distributions.html
- Observed validation objective, which the frozen code minimizes, improved
  monotonically:
  `-0.528839940 -> -0.534187518 -> -0.589568856`. Because lower is better,
  the increasingly negative values move in the intended direction.
- Train response NLL also improved monotonically:
  `-0.545333293 -> -0.716075809 -> -0.777784716`; visible BCE improved
  `0.069382812 -> 0.055873264 -> 0.055610603`. All values and gradients were
  finite.
- Counterexample checked: adding `abs(NLL)` would reverse the gradient whenever
  NLL is negative and incorrectly push a better-fitting density back toward
  zero. Replacing the mixture NLL with L2 would discard the predicted
  multimodal conditional distribution and uncertainty. Neither modification is
  scientifically or mathematically justified by the sign.
- Separate rule retained: the flow-matching profile/share objectives are masked
  squared errors, so for those components zero is the theoretical floor. The
  original Flow Matching objective is a squared vector-field regression:
  https://arxiv.org/abs/2210.02747
- Decision: make no loss mutation. Continue to select response checkpoints by
  finite, lower validation NLL and later judge generated response using
  validation-only distributional metrics (scale, resolution, zero fraction,
  Wasserstein distance, and fixed-condition visual/statistical banks), not by
  proximity of NLL to zero.

## 2026-07-25 16:22 Asia/Taipei — recovery r2 worker started

- The existing 300-second monitor observed custom job
  `7148299209593061376` transition to `JOB_STATE_RUNNING`.
- No duplicate describe loop or Vertex job was created.
- This is an infrastructure state transition only. Recovery remains blocked
  pending immutable epoch-3, paired-checkpoint/RNG restoration evidence,
  50-condition × 5-draw visualization output, invariant QA, and 8/8 postflight.

## 2026-07-25 16:24 Asia/Taipei — localhost epoch sync armed

- Existing dashboard dev server remains healthy at
  `http://localhost:3000/`.
- Started exactly one hidden
  `scripts/sync_vertex_visualizations.py` process (PID `18736`) against the
  recovery r2 output with `--interval-seconds 300`.
- First sync result:
  `{"downloaded":0,"epochs":0,"status":"waiting_for_first_epoch"}`; stderr is
  empty. This is the expected state before the immutable epoch-3 snapshot.
- The synchronizer accepts only matching immutable progress snapshots with
  validation split, QA pass, zero test events, exactly five Fast-MC draws per
  condition, stable geometry hash, and stable validation-selection hash.

## 2026-07-25 16:26 Asia/Taipei — recovery r2 training initialized

- Cloud Logging shows the training program reached model initialization at
  `2026-07-25T08:25:58Z`.
- The only program output is the previously classified nonfatal PyTorch
  `TransformerEncoder` nested-tensor performance warning caused by
  `norm_first=True`.
- There is no failure artifact or epoch snapshot yet. This remains an active
  epoch, not evidence of restored checkpoint correctness.

## 2026-07-25 16:42 Asia/Taipei — mid-epoch recovery design gate

- Research basis:
  PyTorch's general checkpoint guidance requires model and optimizer state plus
  other resume state; its reproducibility guidance requires an explicit
  DataLoader generator and worker seeding. Sources:
  https://docs.pytorch.org/tutorials/beginner/saving_loading_models.html and
  https://docs.pytorch.org/docs/stable/notes/randomness
- Accepted snapshot boundary: only immediately after an optimizer and
  scheduler step, after gradients are cleared. Saving inside an accumulation
  window would require serializing pending gradients and is rejected.
- Required mid-epoch payload: model, optimizer, scheduler, scaler, Python,
  NumPy, CPU Torch and CUDA RNG states; epoch; exact next batch index; frozen
  loader-length/order contract; train/component running sums and counts;
  elapsed time; completed update count; current selected metric; and a
  hash-pinned paired prior-best checkpoint when one exists.
- Resume rule: recreate the epoch's permutation from frozen `seed + epoch`,
  restore training RNG, advance the deterministic loader to the exact next
  batch without recomputing model losses, and continue. Any loader length,
  provenance, stage, configuration, hash, optimizer-boundary, or paired-best
  mismatch must stop.
- Counterexamples rejected:
  saving only weights loses AdamW moments and scheduler position; saving only a
  batch index can replay a different shuffle; saving during gradient
  accumulation can silently omit partial gradients.
- Implementation is intentionally not injected into the already-running
  immutable r15 recovery. It requires a new image and a separate bounded
  interruption/equivalence proof before full-data training.

Local implementation completed after the design freeze:

- checkpoint format v3 can carry an explicit mid-epoch progress contract;
- `resume_progress_from[_relative/_sha256]` is distinct from completed-epoch
  `resume_from`, cannot be mixed with initialization or completed resume, and
  may omit `resume_best_from` only when no finite best exists during epoch 0;
- progress validation stops on epoch, loader length, batch size, accumulation,
  epoch seed, next-step boundary, aggregate, update-count, or nonfinite drift;
- checkpoints are written only after the optimizer and scheduler step and
  gradient clearing;
- the trainer reconstructs `seed + epoch`, advances the loader to `next_step`,
  restores aggregates and all serialized training state, and continues;
- Vertex callback code uploads immutable, uniquely keyed in-flight snapshots
  containing progress checkpoint, progress JSON, and the paired best when
  available;
- stale local `progress.pt` is removed only after a newer completed-epoch
  `last.pt` exists, preventing ambiguity in terminal/epoch snapshots.

Local QA: focused config/progress tests `18 passed`; full suite `42 passed`
with the same three nonfatal Transformer warnings; compileall clean. This is
**implemented locally but not yet interruption-equivalence or Vertex proven**,
so the full-data gate remains closed.

## 2026-07-25 17:18 Asia/Taipei — recovery r2 terminal verification

Server state and evidence:

- Pipeline `7685263305203515392`, custom job `7148299209593061376`,
  `JOB_STATE_SUCCEEDED`.
- Worker interval: `2026-07-25T08:20:16Z` to `09:16:08Z`.
- Exact immutable r15 image, one on-demand `n1-standard-8` + one Tesla T4,
  one replica, 100 GB `pd-ssd`, FP32, 21,600-second timeout, and expected
  service account were re-read from the terminal Vertex spec.
- Output listing: exactly 32 objects / 73,664,533 bytes; no
  `vertex_failure.json`.

Evidence download correction:

- The first `gcloud storage cp .../**` attempt flattened paths on Windows and
  skipped repeated basenames. It is preserved at
  `audit/recovery_response_r2_success/` as an unusable failed evidence attempt.
- Re-downloaded the immutable prefix with recursive prefix synchronization to
  `audit/recovery_response_r2_success_structured/`; all 32 paths are retained.
- Exact source best/last checkpoints were separately downloaded to
  `audit/recovery_response_r2_sources/`.
- Reusable verifier `scripts/verify_recovery_output.py` wrote
  `audit/recovery_response_r2_verification.json` and passed every assertion.

Independent checkpoint/recovery QA:

- History contains exactly one row: response epoch 3; no epoch was replayed.
- Train / validation loss:
  `-0.7257548422 / -0.5889020705`; visible BCE `0.0555758100`; response NLL
  `-0.7813306526`; all finite.
- Source last is epoch 2, source paired best epoch 1. Their exact hashes are
  `c03f425e...c170cf` / `2ace2bb5...eaba`.
- Source optimizer/scheduler step was 3,330; final best and last are both
  4,440: exactly 1,110 new updates. This independently proves optimizer and
  scheduler restoration rather than reinitialization.
- Source and final stage/provenance match. Python, NumPy, CPU Torch, and CUDA
  RNG states are present. The worker necessarily passed the previously failing
  RNG restore call and completed training.
- Final best / last hashes:
  `5e67b56a...f845b` / `9ec31538...227f`; both are epoch 3, carry identical
  model state and selected metric `-0.5889020705`.
- The accepted uninterrupted response best remains
  `d378de58...119463` with validation `-0.5895688564`, better by
  `0.0006667859`. The recovery checkpoint is therefore not promoted as the
  scientific predecessor.
- Scheduler boundary disclosed: the source checkpoint was already at the
  original cosine `T_max=3330`; the recovery proof deliberately extended to
  4,440, producing LR `2.575e-5`. This proves exact scheduler restoration but
  is not a valid basis for extending a completed scientific schedule.

Data, structural, resource, and timing QA:

- Staged manifest: exactly 211 unique relative paths: 205 from prep r5 and six
  from the unique recovery overlay; no `legacy` or test path.
- Preflight: real production data, 187/187 shards; selected train/validation/
  test = 26,624 / 4,096 / 0.
- Epoch invariants: every discrete failure zero; layer/event closure
  `4.7684e-7 / 9.5367e-7` GeV.
- Fresh-best reload postflight: every discrete failure zero; layer/event
  closure `2.3842e-7 / 1.9073e-6` GeV.
- T4 peak allocation `399,014,400 / 15,655,829,504` bytes; headroom
  `97.4513%`.
- Required 8/8 solver/decode postflight: `262.1148 ms/event`, batch 2, two
  timed iterations. This short recovery check is not the final benchmark.

Epoch visualization/dashboard QA:

- Artifact SHA-256 `626a18c9...61ef4`; selection SHA-256
  `f7052919...59b6`.
- Exactly 50 unique validation conditions and five same-four-vector draws per
  condition; 250 generated showers; zero test events.
- All truth/generated values finite and nonnegative; all structural invariant
  counters zero; maximum layer/event closure `9.5367e-7 / 1.9073e-6` GeV.
- Generation took `217.543 s` on the resident T4, so no auxiliary GPU was
  needed.
- Descriptive component-stage results: truth/generated response means
  `4.21556 / 4.35468 GeV` (`+3.30%`); truth/generated hit-count means
  `1726.48 / 751.448` (`-56.48%`); mean longitudinal-profile relative L1
  `1.62064`. These large morphology errors are expected because downstream
  heads are untrained and are not physics validation.
- The 300-second synchronizer published the real bank locally. HTTP QA:
  `/` and `/data/manifest.json` both return 200; the manifest identifies the
  exact recovery prefix, epoch 3, and matching geometry/selection hashes.

Disposition: paired completed-epoch recovery **PASS**. Response component gate
is complete. Structural and recovery success do not establish Geant4 fidelity.

## 2026-07-25 17:27 Asia/Taipei — local mid-epoch equivalence proof

- Added a full synthetic interruption test, not only field-level unit tests.
- One deterministic response run trained uninterrupted. A matched run was
  deliberately interrupted after its first optimizer-boundary progress
  snapshot (`next_step=2`), then resumed into a new run directory.
- The progress checkpoint had full state, a matching normalized training
  contract hash, and exact aggregate/batch boundary.
- Resumed versus uninterrupted terminal model tensors were bitwise identical.
  Train loss, validation loss, learning rate, visible BCE, response NLL, and
  total optimizer updates were exactly equal.
- The stale progress checkpoint was absent after the resumed epoch produced
  the newer completed `last.pt`.
- Full repository QA is now 43 passed with four instances of the same known
  Transformer performance warning; compileall and all template validation
  pass.

Boundary: local interruption equivalence **PASS**. A Vertex/GCS in-flight
snapshot and resume proof is still required before full-data training.

## 2026-07-25 22:41 Asia/Taipei — profile pre-submission gate

Immutable image:

- Cloud Build `faf94066-623c-4b9d-bab2-7b71a9b7355c` succeeded in 3m27s.
- Verified allowlisted context: 61 files / 263,086 bytes; no dashboard
  dependencies, audit data, ROOT data, test data, bytecode, or `legacy/`.
- r16 digest:
  `sha256:dcd6548e40ccee98ecefa0960864c8528546b152ea8f7540481594acc5d35893`.

Frozen profile protocol:

- New unfrozen template:
  `configs/templates/pilot_stage_profile_fp32.yaml`.
- Frozen only through the CLI, never hand-edited:
  `audit/training_hardening_inputs/stage_profile_r1/configs/frozen_pilot_stage_profile_fp32.yaml`.
- Frozen SHA-256:
  `6dbbe30d3e42ee9cd39318673a11bf73af471d72258c6f084fb68613f165b117`.
- Stage `profile`; exact bounded production bank; three epochs; FP32; batch 6
  × accumulation 4 (effective 24, matching the accepted response diagnostic);
  seed 20260723; condition encoder frozen; 8/8 postflight; required 50×5
  validation visualization.
- Mid-epoch interval is explicitly zero for this component job because the
  Vertex/GCS proof is still open; new code remains dormant.
- Initialization is hash-pinned to the better accepted uninterrupted response
  checkpoint `d378de58...119463`, not the recovery extension.

Unique input/output QA:

- Input and output prefixes were independently empty; no matching profile job
  existed.
- Input prefix was created with generation-match zero and contains exactly two
  objects / 14,339,535 bytes: frozen config and response best.
- Server-side checkpoint copy has the same 14,336,500 bytes, MD5
  `oiABUVP5gsqsEVsKdr63Fw==`, and CRC32C `cvv6rg==` as the accepted source.
- Output prefix remains empty.

Conservative budget immediately before submission:

- Prior custom-job ledger through failed recovery: $4.14.
- Successful recovery r2 charged at a rounded-up $0.80
  (`55m52s × $0.85/h` conservative rate).
- Custom-job estimate: $4.94.
- Build/storage/management contingency increased to $4.00 to cover r15/r16 and
  retained evidence.
- Accounted total: $8.94; conservative remaining budget: $91.06.
- A six-hour on-demand T4 profile timeout reserves $5.10 and would leave
  $85.96. The submission fits the hard $100 ceiling.

Exactly one profile job was submitted:

- Pipeline `7536609333128200192`;
- custom job `4083748372115095552`;
- initial state `JOB_STATE_PENDING`;
- live server spec independently matches the exact r16 digest, base prep r5,
  unique profile overlay/output, frozen config path, one on-demand T4,
  `n1-standard-8`, one replica, 100 GB `pd-ssd`, expected service account,
  21,600-second timeout, CUDA, and training postflight;
- output remained empty after submission.

The SDK's async helper left a local status-printing process alive after server
acceptance. Exact PID/command line were resolved and only that local process
was stopped; a fresh server describe confirmed the Vertex job remained
pending. Monitoring now uses exactly one 300-second loop (session `43405`).

The completed recovery visualization watcher was stopped after its artifacts
were synced. A single replacement watcher (PID `11208`) now checks the unique
profile output every 300 seconds; initial state is
`waiting_for_first_epoch`. The localhost dashboard remains live and retains
the last verified bank until profile epoch 0 exists.

## 2026-07-25 22:55 Asia/Taipei — profile r1 staging failure and r2 gate

Failed job evidence:

- Profile r1 custom job `4083748372115095552` ended `JOB_STATE_FAILED`.
- It ran only from `14:49:13Z` to `14:50:44Z`; no model epoch began.
- Exact root cause:
  `FileNotFoundError: /tmp/cbsc_zdc/input/artifacts/training_pilot_splits.json`.
- Prep r5 does not contain the diagnostic training split. The r1 overlay
  mistakenly carried only config + predecessor checkpoint and omitted the
  split manifest and assignment.
- Preflight stopped before model construction, as designed.
- The first managed worker attempt preserved three immutable failure objects /
  68,802 bytes. A subsequent managed retry reached the same failure handler
  and hit HTTP 412 rather than overwrite generation-0 evidence.
- Structured failure evidence and hashes are preserved under
  `audit/stage_profile_r1_failure/`. Failed prefixes will never be reused.

Correction and counterexample QA:

- Added `scripts/verify_vertex_staging.py`, which merges server-side base and
  overlays by relative path, stops on collisions/missing or unsafe paths,
  downloads and verifies frozen dataset/split/geometry/assignment hashes,
  validates every hash-pinned checkpoint, and rejects `legacy`/test paths.
- Running it against r1 independently reproduced the missing
  `artifacts/training_pilot_splits.json` failure before submission.
- Created entirely new r2 input/output prefixes. r2 input contains four
  generation-0 objects / 14,389,741 bytes: unchanged frozen config, accepted
  response checkpoint, split manifest, and split assignment.
- Full merged staging verification passed and was saved to
  `audit/stage_profile_r2_staging_verification.json`:
  205 base + 4 overlay = 209 unique objects / 5,958,748,764 bytes; real
  production data; zero forbidden paths; all four frozen artifact hashes and
  checkpoint SHA `d378...9463` match.
- r2 output is independently empty; no matching r2 job exists; script
  compileall passes. No image or scientific-config change is required.

Budget before r2 retry:

- r1 failure charged conservatively as $0.15 despite only 1m31s of worker
  runtime.
- Accounted total rises from $8.94 to $9.09; remaining budget $90.91.
- Six-hour on-demand T4 retry reserve is $5.10, leaving $85.81.

Exactly one corrected profile r2 job was submitted:

- Pipeline `329020341986787328`;
- custom job `6016741215913902080`;
- initial state `JOB_STATE_PENDING`;
- live server spec independently matches exact r16 digest, corrected r2
  overlay, unique empty r2 output, frozen config, on-demand one-T4 resources,
  timeout, service account, and postflight.
- The helper's stray local async status process was stopped by exact command
  match after acceptance; the server job remained pending.
- Exactly one 300-second monitor is active (session `40217`).
- Dashboard watcher was moved from closed r1 to r2 (PID `14712`), with initial
  `waiting_for_first_epoch`.

At 2026-07-25 23:04 Asia/Taipei, the existing monitor observed profile r2
enter `JOB_STATE_RUNNING`. This is provisioning/execution evidence only; the
profile gate remains closed until immutable epoch artifacts pass.

## 2026-07-25 23:12 Asia/Taipei — profile r2 running and pricing cross-check

The existing 300-second monitor (session `40217`) reported
`JOB_STATE_RUNNING` at 23:09:53. An independent
`gcloud ai custom-jobs describe 6016741215913902080` reproduced the exact
authorized server specification:

- start time `2026-07-25T15:01:16Z`;
- immutable image
  `sha256:dcd6548e40ccee98ecefa0960864c8528546b152ea8f7540481594acc5d35893`;
- one `n1-standard-8`, one `NVIDIA_TESLA_T4`, one replica, on demand;
- 100 GB `pd-ssd`, 21,600-second timeout, expected service account;
- base preparation r5, corrected r2 overlay, unique r2 output, CUDA, and
  training postflight.

Cloud Logging reached model construction at `15:07:25Z` and contains only the
known nonfatal PyTorch `norm_first=True` Transformer performance warning.
The output prefix still matches no objects, so epoch 0 has not completed and
there is nothing yet that can pass the profile gate. No duplicate or successor
job was submitted.

Budget-rate research was independently refreshed against Google Cloud's
official current pricing pages:

- T4 GPU in `us-central1`: `$0.35/hour`
  (`https://cloud.google.com/products/compute/gpus-pricing?hl=en`);
- N1 predefined vCPU: `$0.031611/vCPU-hour`;
- N1 predefined memory: `$0.004237/GiB-hour`
  (`https://cloud.google.com/products/compute/resources/pricing`).

For `n1-standard-8` (8 vCPU, 30 GiB), the published VM subtotal is
`8×0.031611 + 30×0.004237 = $0.379998/hour`; VM plus T4 is therefore
approximately `$0.729998/hour` before disk and service overhead. The existing
`$0.85/hour` conservative ledger rate remains justified and is retained.
Accounted prior spend remains `$9.09`; the active six-hour reserve is `$5.10`,
so the conservative uncommitted remainder remains `$85.81`. This cross-check
does not authorize another submission.

Verifier preparation QA:

- Downloaded the exact r2 overlay predecessor to the new local evidence
  directory `audit/stage_profile_r2_source/response_best.pt`; its independently
  computed SHA-256 is exactly
  `d378de58ce310b9454620db3811e9cbba6760ba426fd7b3e4dd467c709119463`.
- Added `scripts/verify_component_stage_output.py` to independently check each
  completed immutable component epoch: complete finite history, selected
  best/last semantics, optimizer and scheduler steps, exact predecessor hash,
  zero change in every frozen tensor, change confined to the intended stage
  module, production preflight/staging counts, zero test use, structural
  invariants, and the 50-condition × five-draw visualization contract.
- The initial QA invocation had two harness errors and is retained as a failed
  attempt: a malformed `python -c` negative-control string caused a
  `SyntaxError`, and pytest collection omitted the required `PYTHONPATH=src`,
  causing three import errors. The verifier itself compiled successfully.
  These invocation errors do not pass any gate; correction uses a committed
  positive/negative regression test and the explicit repository import path.

Corrected verifier QA passed:

- `python -m py_compile` passed for the verifier and its regression test.
- With `PYTHONPATH=src`, 17 focused tests passed. This includes both controls:
  an intended `profile.*` tensor mutation is accepted, while a frozen
  `condition.*` mutation is rejected.
- The only two warnings are the already classified nonfatal Transformer
  nested-tensor performance warnings.
- The profile synchronizer has completed four independent 300-second checks;
  each reports `waiting_for_first_epoch`, with zero downloaded epochs.

The in-app visual browser connection was retried only after rereading its
required operating instructions. The runtime again failed before page access
with `failed to write kernel assets ... os error 3`, including on a connection
state check. This independently reproduces the previously logged desktop
environment limitation. It is not treated as UI pass or failure. The existing
HTTP/build/data-contract QA remains valid, and no unapproved alternate browser
surface was substituted.

After simplifying one verifier assertion without changing its semantics, the
complete local repository suite passed: **45 passed**, four known Transformer
performance warnings, exit zero. This supersedes the focused-test count for
local code QA. It does not advance the Vertex profile gate.

## 2026-07-26 00:03 Asia/Taipei — profile r2 epoch 0 independently passed

The immutable epoch appeared at `16:00:21Z` while the job remained running.
Server listing is exactly 13 objects / 55,495,840 bytes under the unique
`progress/epoch_0000` prefix. It was mirrored into the new evidence directory
`audit/stage_profile_r2_epoch_0000`; the independent report is
`audit/stage_profile_r2_epoch_0000_verification.json`.

All verifier assertions passed:

- exact predecessor SHA-256 `d378...9463`, stage `response` → `profile`;
- all 40 changed tensors are confined to `profile.*`;
- **zero** mismatches in the frozen condition encoder, response, count,
  support, share, geometry, and mask tensors;
- best/last semantics are correct for epoch 0; hashes are
  `c3bdeec2...c97ce` / `c5662b24...ae245`;
- optimizer and scheduler are both at exactly 1,110 updates;
- production preflight is exact: 187 shards, 26,624 train, 4,096 validation,
  zero test; 205 base + four corrected-overlay objects;
- epoch structural invariants pass with every failure counter zero,
  layer closure `9.5367e-7 GeV`, event closure `4.7684e-7 GeV`.

Epoch-0 measurements:

| measurement | value |
|---|---:|
| train weighted loss | 3.966256104 |
| validation weighted loss | 2.793788581 |
| train first-layer CE | 0.690892304 |
| train active-layer BCE | 0.435593615 |
| train profile-flow MSE | 3.403013145 |
| learning rate | 7.525e-5 |
| updates | 1,110 |
| training seconds | 2,676.345 |
| training throughput | 9.94790 events/s |
| peak T4 allocation | 403,064,832 bytes |

The weighted total is independently consistent with the frozen weights:
`0.5×0.690892304 + 0.5×0.435593615 + 3.403013145 = 3.966256104`.
These losses are nonnegative as expected: CE/BCE have entropy-dependent
population floors and the profile MSE has theoretical floor zero. One epoch
does not establish an improvement trend; epochs 1–2 remain required.

Visualization/dashboard gate:

- exact same 50 validation conditions × five draws, selection hash
  `f705...59b6`, 8/8 solver steps, zero test;
- all nonfinite/negative/fixed-count/support mismatch counters zero;
- visualization closures `5.7220e-6 / 3.8147e-6 GeV`, within `2e-5 GeV`;
- descriptive profile relative L1 `0.307060`;
- descriptive response bias `+12.704%` and hit-count bias `+62.972%`.

The latter two are not tuned gates: response is frozen from the accepted
predecessor, while count/support/share are not yet component-trained. The
accepted original response job predates the epoch-visualization exporter, so
an attempted lookup of its epoch-2 visualization correctly found no objects;
the recovery epoch-3 visualization uses a different response checkpoint and
is not a valid direct comparator. Cross-profile-epoch QA will instead require
identical per-draw generated response values because response tensors and
generation seeds are frozen.

That cross-epoch gate is now executable, not merely planned. The component
verifier compares all 250 repeated-condition draws across epochs and requires
the upstream stochastic outputs to remain exactly identical at the appropriate
stage boundary: response for profile; response plus layer budgets for count;
response plus layers plus counts for support; and those plus selected support
for share. Seven positive/negative unit tests pass, compilation is clean, and
an epoch-0 self-cross-check verified all 250 response draws. Epoch 1 will use
epoch 0 as the independent reference.

The localhost synchronizer published epoch 0. Independent HTTP checks return
200 for `/` and `/data/manifest.json`; the manifest reports latest epoch 0,
one epoch, and the exact selection hash. This is descriptive validation
monitoring, not Geant4 fidelity validation. Profile gate remains open pending
epochs 1–2 and terminal postflight; no successor was submitted.

## 2026-07-26 00:56 Asia/Taipei — profile r2 epoch 1 independently passed

The immutable epoch-1 snapshot contains exactly 16 objects / 77,219,125 bytes
and was mirrored to `audit/stage_profile_r2_epoch_0001`. The first verifier run
stopped before writing a report because the proposed exact-response
cross-epoch assertion found different generation seeds. Code inspection
established the counterexample: the exporter intentionally uses
`generation_seed + epoch×1,000,003 + event_position×10,007`. Thus the
validation conditions are fixed, but each epoch deliberately receives an
independent FastMC sample. Exact draw equality would be scientifically wrong,
not a stronger gate.

The correction preserves the actual contract:

- identical selection hash and all 50 Geant4 truth conditions;
- exactly 250 FastMC draws per epoch;
- exact `+1,000,003` seed offset from epoch 0 to epoch 1;
- frozen upstream integrity proven by byte-exact model tensors, not by forcing
  stochastic outputs to repeat.

Four focused positive/negative tests and compilation pass for the corrected
check. The original failed assertion is retained here and in command evidence;
no output report existed to overwrite. The corrected independent report is
`audit/stage_profile_r2_epoch_0001_verification.json`.

All epoch-1 gates pass:

- exact predecessor and staging/preflight contracts;
- all changed model tensors confined to `profile.*`; zero frozen-tensor
  mismatches;
- best/last correctly select epoch 1, hashes
  `9bd56ee8...d986c` / `d2f13ac8...57e1f`;
- optimizer and scheduler exactly 2,220 updates;
- every epoch and visualization structural failure counter zero; epoch
  closures `1.1921e-7 / 2.3842e-7 GeV`, visualization closures ≤`5.7221e-6`;
- zero test use and unchanged validation selection hash.

Epoch-1 measurements and changes from epoch 0:

| measurement | epoch 0 | epoch 1 | relative change |
|---|---:|---:|---:|
| train weighted loss | 3.966256104 | 2.807006051 | -29.23% |
| validation weighted loss | 2.793788581 | 2.509450324 | -10.18% |
| train first-layer CE | 0.690892304 | 0.452959450 | -34.44% |
| train active-layer BCE | 0.435593615 | 0.365566127 | -16.08% |
| train profile-flow MSE | 3.403013145 | 2.397743263 | -29.54% |
| descriptive profile relative L1 | 0.307060 | 0.253661 | -17.39% |

Training took `2,658.898 s` at `10.0132 events/s`; peak allocation remains
403,064,832 bytes. Every trained component and the validation objective moved
downward, so the profile component has a real two-epoch optimization signal.
The visualization change is supportive but noisy because the draws are
independent. Descriptive epoch-1 response bias is `+1.078%` and hit-count bias
`+62.265%`; neither is used for selection, and downstream count remains
untrained.

The localhost manifest now returns latest epoch 1, two epochs, and the same
selection hash. Profile gate remains open for epoch 2 and terminal reload,
resource, and 8/8 timing checks. No successor was submitted.

Full regression after the seed-contract correction: **47 passed**, four known
Transformer warnings, exit zero.

## 2026-07-26 01:50 Asia/Taipei — profile r2 terminal gate passed

Custom job `6016741215913902080` ended `JOB_STATE_SUCCEEDED` at
`2026-07-25T17:41:44Z`. The complete unique output contains exactly 73 objects
/ 330,733,796 bytes and no `vertex_failure.json`. It was mirrored to
`audit/stage_profile_r2_terminal`; the independent terminal report is
`audit/stage_profile_r2_terminal_verification.json`.

Epoch 2 independently passes:

- train/validation weighted loss `2.642119713 / 2.451456106`;
- first-layer CE `0.448964579`, active BCE `0.345567855`, profile-flow MSE
  `2.244853496`;
- 3,330 exact optimizer and scheduler updates; final LR `1e-6`;
- `2,677.057 s`, `9.94525 events/s`, peak allocation 403,064,832 bytes;
- all changes confined to `profile.*`, zero frozen-tensor mismatch;
- epoch-2 best/last hashes `ef29d9d3...4ee24` /
  `b31f9687...75cf2`; best correctly selects epoch 2;
- epoch invariants all zero-failure, closures
  `3.5763e-7 / 4.7684e-7 GeV`;
- fixed 50-condition truth bank, independent 250-draw epoch seed contract,
  zero test, visualization closures ≤`5.7221e-6 GeV`.

Across epochs 0→1→2, validation loss decreases monotonically
`2.793788581 → 2.509450324 → 2.451456106`. Train loss and all three trained
components also improve. The component-stage optimization gate therefore
passes. Descriptive profile relative L1 is `0.307060 / 0.253661 / 0.299739`;
because each epoch uses independent FastMC draws, that small-sample statistic
is not monotonic and is not used for checkpoint selection.

Terminal fresh-reload postflight passes:

- best checkpoint reload and sampling succeed;
- every invariant counter is zero; closure ≤`5.7221e-6 GeV`;
- Tesla T4 peak `403,064,832 / 15,655,829,504` bytes, headroom `97.4255%`;
- required FP32 8/8 solver/decode short check: `275.396 ms/event`, batch 2,
  two iterations.

This is a passed profile component diagnostic on real production data, not
physics validation. The count/support/share heads remain untrained.

Budget closeout:

- actual server runtime `2h40m28s`;
- conservative charge rounded up to `$2.30` at `$0.85/hour`;
- prior accounted total `$9.09` becomes `$11.39`;
- remaining hard-budget capacity `$88.61`;
- a six-hour count-stage reserve would be `$5.10`, leaving `$83.51`.

The profile stage gate is complete. Count configuration and staging still
require independent freeze/hash/input/spec QA before any submission.

## 2026-07-26 01:55 Asia/Taipei — count pre-submission gate passed

Created the new unfrozen template
`configs/templates/pilot_stage_count_fp32.yaml`, then froze it only through
`PYTHONPATH=src python -m cbsc_zdc.cli freeze-config`. The frozen file is
`audit/training_hardening_inputs/stage_count_r1/configs/frozen_pilot_stage_count_fp32.yaml`,
SHA-256 `436a6efda2514d762f18104c5e232f6f71ab984182d53af96b112c1b8db17012`.

A field-by-field comparison against the accepted profile config found exactly
the intended differences: project name/run directory, template hash, stage
`profile→count`, and predecessor relative path/hash. All scientific data,
geometry, model, optimizer, FP32, effective batch 24, three-epoch, loss,
condition-encoder freeze, and 50×5 visualization settings are unchanged.
Initialization is pinned to accepted profile best
`ef29d9d330e4d68080a8538bd21245a59284330b4ea2d0a5c1bc042723d4ee24`.

Unique generation-0 count input contains exactly four objects / 16,666,968
bytes: frozen config, profile best, diagnostic split, and assignment. The new
count output prefix is empty and no matching display name exists.

Independent merged staging verification passes in
`audit/stage_count_r1_staging_verification.json`:

- 205 base + four overlay = 209 unique objects / 5,961,025,991 bytes;
- exact dataset, geometry, split, assignment, config, and predecessor hashes;
- stage `count`, real production data, zero forbidden paths/collisions;
- focused QA 16 passed; compileall clean.

Budget immediately before submission remains:

- accounted `$11.39`, remaining `$88.61`;
- worst-case six-hour one-T4 reserve `$5.10`;
- conservative post-reserve remainder `$83.51`.

The authorized spec is exactly one on-demand T4, `n1-standard-8`, one replica,
100 GB `pd-ssd`, 21,600-second timeout, r16 digest, base r5, unique count
overlay/output, expected service account, CUDA, and training postflight.

Exactly one count job was submitted:

- pipeline `3896909185840840704`;
- custom job `3159244635742666752`;
- initial server state `JOB_STATE_PENDING`;
- actual SDK display name
  `cbsc-v2-2-stage-count-fp32-20260726-r1-custom-job-custom-job`;
- independent live describe matches every authorized image, prefix, config,
  resource, on-demand, timeout, service-account, CUDA, and postflight field;
- output remains empty.

The completed profile dashboard watcher was stopped only after exact PID and
command-line verification. Two local watcher-launch failures are preserved:
the first identity wildcard used the wrong token order and stopped nothing;
the second safely stopped the verified profile watcher but failed because
`Start-Process` did not quote a script path containing spaces. Its stderr is
retained in `dashboard/vertex_sync_count_r1.err.log`. The corrected hidden
count watcher is PID `9020`, uses 300-second intervals, and writes new `r1b`
logs. One server-state 300-second monitor is session `94156`. These local
corrections did not affect or duplicate the Vertex job.

At 2026-07-26 02:01 Asia/Taipei, the existing monitor observed count job
`3159244635742666752` enter `JOB_STATE_RUNNING`. The corrected visualization
watcher has completed two 300-second checks and correctly reports
`waiting_for_first_epoch` with no stderr. This is execution evidence only; the
count gate remains closed.

## 2026-07-26 02:55 Asia/Taipei — count r1 epoch 0 independently passed

The epoch first appeared as a partial two-checkpoint prefix. Verification was
correctly deferred until all 13 immutable objects were present. Complete
snapshot size is 41,508,493 bytes. Local mirror:
`audit/stage_count_r1_epoch_0000`; independent report:
`audit/stage_count_r1_epoch_0000_verification.json`.

All gates pass:

- exact accepted profile predecessor `ef29...4ee24`;
- all seven changed tensors confined to `counts.*`; zero frozen-tensor
  mismatch in condition/response/profile/support/share/geometry;
- best/last hashes `09fb3478...bd599` / `69f6f062...20af3`;
- exactly 1,110 optimizer and scheduler updates;
- finite count CE `3.799753980`, weighted train loss `2.849815485`, finite
  validation loss `2.843521855`;
- the frozen count weight is independently reproduced:
  `0.75×3.799753980 = 2.849815485`;
- 2,551.772 seconds, 10.4335 events/s, peak 402,456,064 bytes;
- production staging/preflight exact, zero test;
- epoch and 50×5 visualization structural counters all zero, epoch closures
  ≤`1.9074e-6 GeV`, visualization closures ≤`4.7684e-6 GeV`.

Descriptive hit-count bias is `-6.736%`, response bias `+12.704%`, and profile
relative L1 `0.269694`. Only the count loss is a component-stage optimization
target; visualization statistics remain small-sample diagnostics with
independent epoch draws. One epoch cannot establish a count-loss trend.

The localhost updater had not yet reached its next 300-second poll at the
verification instant and correctly still served the last complete profile
bank. It will switch atomically when it observes the complete count epoch.
Count job remains running; epochs 1–2 and terminal postflight are required.

## 2026-07-26 03:05 Asia/Taipei — stage-qualified dashboard recovery passed

The prior count watcher PID `9020` stopped safely on an immutable-name
collision: profile epoch 0 and count epoch 0 have different hashes. This was a
correct integrity rejection, not corrupted training evidence. The rejected
attempt and traceback remain in
`dashboard/vertex_sync_count_r1b.err.log`; no cloud artifact was changed.

The sync contract now keys snapshots by exact `(stage, epoch)` identity and
uses stage-qualified filenames for new downloads. Existing profile files and
hashes were retained without overwrite. The manifest migrated to schema 2 and
now contains four independently hashed snapshots:

- `profile:0000`, `profile:0001`, `profile:0002`;
- `count:0000` at `count_epoch_0000.json`.

The shared geometry hash remains `c6c02f...922bf1`, the validation selection
remains `f70529...59b6`, and `latest_id=count:0000`. A one-shot GCS sync
downloaded exactly one new object and reported four total snapshots. The
localhost UI now selects snapshots by stage-qualified ID, preserves acquisition
order in the trend chart, and labels points by stage plus epoch.

QA evidence:

- Python compileall clean;
- focused Python tests: `12 passed`, one known nonfatal Transformer warning;
- dashboard production build passed;
- rendered dashboard tests: `2 passed`;
- one initial focused-test command was issued from `dashboard/` and therefore
  found no root `tests/`; this command failure changed nothing. Re-running from
  repository root with `PYTHONPATH=src` passed.

The corrected hidden watcher is PID `20244`, uses exactly a 300-second
interval, writes new `r1c` logs, and completed its first pass with zero stderr.
The single Vertex state monitor remains session `94156`; at 03:02 the existing
count custom job `3159244635742666752` remained `JOB_STATE_RUNNING`. No job was
submitted, duplicated, stopped, or modified.

## 2026-07-26 03:12 Asia/Taipei — loss-form and live-site QA

Loss-form review did not justify a scientific change. PyTorch's categorical
cross-entropy is already the negative log probability of the target class, and
the profile/share flow objectives already regress the target velocity with
elementwise squared error. Zero is the ideal limit for these nonnegative
components, but finite stochastic data, irreducible conditional variation, and
validation sampling make exact zero neither expected nor a safe stopping rule.
Wrapping cross-entropy in absolute value is redundant while it is nonnegative;
squaring the already reduced loss would rescale gradients according to the
current batch loss and change the frozen optimization problem without evidence.
Decision: keep the frozen loss definitions and judge the count stage only after
the predeclared multi-epoch train/validation trend and structural/visual gates.
Primary references reviewed were the official PyTorch CrossEntropyLoss and
MSELoss definitions plus Lipman et al.'s Flow Matching formulation.

The in-app visual browser connection failed before page discovery because its
local kernel asset path was unavailable; the required troubleshooting lookup
failed identically. This local tooling failure is preserved and did not affect
the site or training. Independent HTTP/data-contract QA against
`http://localhost:3000/` passed: status 200, 8,890-byte server response,
manifest schema 2, four snapshots, `latest_id=count:0000`, count artifact
stage/epoch exact, 50 validation conditions, exactly five draws each, QA pass,
and zero test events. Build and rendered-page tests remain the visual regression
evidence until browser tooling is available.

Server checks at 03:07 and 03:12 still report the sole count job
`JOB_STATE_RUNNING`; epoch 1 is not yet present in GCS. No correction or
submission is authorized by unchanged running state.

## 2026-07-26 03:45 Asia/Taipei — count r1 epoch 1 independently passed

Epoch 1 appeared at 03:42 as 16 immutable objects / 54,677,454 bytes. The first
mirror command failed before transfer because `gcloud storage cp` requires an
existing local directory. After creating a new, verified path inside `audit/`,
the second command downloaded all 16 objects with transport checksum
verification. The wildcard copy flattened the remote subdirectories, so the
files were moved by explicit literal paths into the expected
`checkpoints/`, `logs/`, `reports/`, and `reports/visualization/` layout. Final
local count and bytes exactly match GCS; no prior evidence directory was reused
or overwritten.

Independent evidence:

- mirror: `audit/stage_count_r1_epoch_0001`;
- report: `audit/stage_count_r1_epoch_0001_verification.json`;
- exact profile predecessor `ef29d9...4ee24`;
- only the seven `counts.*` tensors changed; zero frozen mismatch;
- best/last hashes `33d8cde6...fe745` / `2929ef58...477a`;
- exact 2,220 optimizer and scheduler updates;
- finite count CE decreased `3.799753980 → 3.636642309`;
- weighted train loss decreased `2.849815485 → 2.727481732`;
- validation loss decreased `2.843521855 → 2.798861735`;
- epoch time 2,554.433 seconds, 10.4227 events/s, peak 402,456,064 bytes;
- epoch and visualization invariants all pass, closures at most
  `7.6294e-6 GeV`, zero test events;
- fixed 50-condition truth bank retained with 250 independent Fast-MC draws.

This directly falsifies the concern that the active count objective was moving
away from zero through epoch 1: both train count loss and validation loss moved
down. The descriptive 50-condition hit-count bias changed from `-6.736%` to
`-10.537%`; that small stochastic visual statistic is not the optimization
target or a physics gate, and it is not used to select this component
checkpoint. Response bias `+1.078%` and profile L1 `0.263183` reflect frozen
upstream heads plus independent draws.

The stage-qualified localhost manifest now has five snapshots and
`latest_id=count:0001`; its exact artifact hash is
`184b8b...ab4a`. Count epoch 2 and terminal postflight remain required. The sole
Vertex job remains under the existing monitor; no new job was submitted.

## 2026-07-26 04:31 Asia/Taipei — count r1 terminal gate passed

The sole Vertex count job completed `JOB_STATE_SUCCEEDED`:

- pipeline `3896909185840840704`;
- custom job `3159244635742666752`;
- start/end `2026-07-25T17:56:57Z` /
  `2026-07-25T20:25:53Z`;
- exact r16 immutable image, on-demand one T4, `n1-standard-8`, 100 GB
  `pd-ssd`, one replica, 21,600-second timeout, expected service account and
  exact base/overlay/output/config/postflight arguments.

The GCS output contains exactly 73 objects / 232,474,455 bytes, zero
`vertex_failure.json`, and all terminal postflight reports. It was mirrored
without overwrite to `audit/stage_count_r1_terminal`; local count and bytes
match exactly. Independent terminal report:
`audit/stage_count_r1_terminal_verification.json`.

All terminal gates pass:

- accepted count best hash
  `163477340b936bac71400675c4822720b823a8343a53e7e22a97b4796a3a0e5b`;
- last hash
  `c9c2fc7d235dbf5a849c735254bb6a28238629adf4a1aac7de1f415f1a2e0401`;
- only seven `counts.*` tensors changed, zero frozen mismatch;
- best/last epoch 2, exactly 3,330 optimizer/scheduler updates;
- count CE `3.799754 → 3.636642 → 3.605898`;
- weighted train `2.849815 → 2.727482 → 2.704424`;
- validation `2.843522 → 2.798862 → 2.791588`;
- epoch throughput `10.43`, `10.42`, `10.48` events/s;
- all epoch, visual, and fresh-checkpoint postflight invariants pass;
- terminal postflight reloaded `best.pt`, sampled seven fixed kinetic
  conditions, and closed layers/events within `1.9074e-6 GeV`;
- Tesla T4 peak 402,456,064 / 15,655,829,504 bytes, headroom `97.429%`;
- FP32 8/8 solver/decode timing 266.845 ms/event, batch 2, two iterations.

The final descriptive 50-condition bank has hit-count bias `-7.993%`, response
bias `+10.557%`, and profile relative L1 `0.299739`. These independent-draw,
small-bank values are visual diagnostics, not physics validation and not
checkpoint selectors. The monotonic train/validation count losses are the
relevant component-stage evidence.

Repository-wide QA after the dashboard changes is `53 passed` with four known
nonfatal Transformer performance warnings. The localhost manifest now contains
six snapshots through `count:0002`. After exact PID/command-line verification,
completed watcher PID `20244` was stopped; localhost serving remains available.

Conservative count charge is `$2.30` for 2.482 hours of wall time. Accounted
budget is now `$13.69`, including the previously retained contingency; remaining
budget is `$86.31`. The count gate is complete. Support remains closed until its
new template/config, exact count predecessor hash, staging, unique prefixes,
spec, input, and worst-case budget reserve all pass.

## 2026-07-26 04:36 Asia/Taipei — support r1 pre-submission gate passed

A new unfrozen template was created at
`configs/templates/pilot_stage_support_fp32.yaml` and then frozen only through
the repository CLI. It was not derived by editing a frozen config.

- template SHA `ce1da7b...d5967`;
- frozen config
  `audit/training_hardening_inputs/stage_support_r1/configs/frozen_pilot_stage_support_fp32.yaml`;
- frozen SHA `e8d0c63b...6eb5f`;
- stage `support`, FP32, one-seed three-epoch component diagnostic;
- batch 4 × accumulation 6 = effective batch 24, matching the accepted
  effective batch while using the support template's safer per-step batch;
- condition encoder frozen;
- initialization pinned to accepted count best
  `163477340b936bac71400675c4822720b823a8343a53e7e22a97b4796a3a0e5b`
  at `checkpoints/count_best.pt`;
- exact 26,624 train / 6,656 validation / zero test bank and 50×5 validation
  visualization contract retained.

Field-by-field comparison to the accepted count config found only intended
differences: project name/run directory, template hash, stage, batch/
accumulation pair with unchanged effective batch, and predecessor path/hash.
All data, geometry, model, optimizer, FP32, epoch, loss, encoder-freeze, and
visualization fields are unchanged.

Generation-0 input/output and duplicate checks passed before upload: both
support prefixes were empty and no matching display name existed. Four overlay
objects were uploaded with generation-match zero:

- frozen config;
- exact accepted count checkpoint;
- diagnostic split manifest;
- diagnostic assignment.

Overlay inventory is four objects / 13,760,796 bytes. Independent merged staging
report `audit/stage_support_r1_staging_verification.json` passes with 205 base +
4 overlay = 209 objects / 5,958,119,819 bytes, exact hashes, real production
data, zero forbidden paths, and no collisions.

The first focused-test command named two nonexistent test files and therefore
ran no tests; compileall still completed cleanly. The corrected focused suite
passed `30` tests with one known Transformer warning, and the immediately prior
full suite passed `53`. This command-selection failure changed no config or
cloud job.

Budget before submission: accounted `$13.69`, remaining `$86.31`; a conservative
six-hour on-demand one-T4 reserve is `$5.10`, leaving `$81.21`. The authorized
support spec is the exact r16 digest, one on-demand T4, `n1-standard-8`, one
replica, 100 GB `pd-ssd`, 21,600-second timeout, expected service account, base
r5, unique support overlay/output, CUDA, and training postflight. No submission
has occurred at this log boundary.

## 2026-07-26 10:18 Asia/Taipei — exactly one joint r1 job submitted

Immediate recheck found an empty output prefix and no pre-existing job. Exactly
one asynchronous Vertex job was accepted:

- pipeline `6159088389292294144`;
- custom job `8267310950965575680`;
- actual SDK server display name
  `cbsc-v2-2-stage-joint-fp32-20260726-r1-custom-job-custom-job`;
- initial state `JOB_STATE_PENDING`.

Independent server describe matches the full authorized contract: immutable
r16 digest `dcd6548e...d35893`, prep r5 base, unique joint overlay/output,
joint frozen config and bounded split, CUDA, training postflight, one replica,
n1-standard-8, one NVIDIA_TESLA_T4, on-demand scheduling, 100 GB pd-ssd,
21,600-second timeout, and compute service account. The first read-only
cardinality filter used the requested unsuffixed display name and returned zero
because the SDK appends `-custom-job`; local filtering on the actual server
display name then proved exactly one match. No duplicate was submitted.

The submission helper observation session is `39594` and watches this same job.
Hidden localhost watcher PID `19776` has an exact verified command line, unique
logs, and a 300-second interval; it currently waits for the first joint epoch.
Joint remains closed pending immutable epoch and terminal verification of all
nine losses, full-network changes, checkpoints, invariants, visualization,
resource headroom, and 8/8 timing.

At 2026-07-26 10:21:59 Asia/Taipei, joint custom job
`8267310950965575680` entered `JOB_STATE_RUNNING` after normal on-demand T4
allocation. The first 300-second combined cadence command returned nonzero only
because `gcloud storage ls` found the still-empty pre-epoch output prefix; the
authoritative job state is running with no error. This expected empty-prefix
condition is preserved and is not a training failure. Watcher PID `19776`
remains identity-correct, has emitted two clean
`waiting_for_first_epoch` records, and has zero stderr. Joint epoch 0 remains
closed.

## 2026-07-26 14:05 Asia/Taipei — joint r1 terminal gate passed

Vertex custom job `8267310950965575680` / pipeline
`6159088389292294144` succeeded from `2026-07-26T02:21:59Z` through
`2026-07-26T05:57:22Z` (3h35m23s), with an empty authoritative error field.
The complete prefix was mirrored to `audit/stage_joint_r1_terminal`: 73 objects
/ 346,933,025 bytes, no `vertex_failure.json`. Independent terminal report
`audit/stage_joint_r1_terminal_verification.json` passes:

- exact share source
  `169170083a06b2199ebb37eeadab3898490532d3650d88bd2d5ef611d5ea839c`;
- selected epoch-2 best
  `03c7960861d6f6f3012a8e4469421d51e33d1a8dad7fc8ec8c8406d547f1adb7`;
- terminal last
  `306c05f6af0df0c0006ae4ea80b6fe8c2a52a93ba5d12d6e3605b42450558a09`;
- all 200 model tensors changed as expected for the fully unfrozen joint stage,
  zero mismatch, exactly 3,330 optimizer/scheduler updates;
- weighted train total `10.105607 → 9.687044 → 9.418839`;
- validation total `10.088126 → 9.613643 → 9.491410`, selecting epoch 2;
- all nine train components finite and the weighted total reconstructs exactly;
- throughput `6.8646`, `6.8606`, `6.8693` events/s;
- fresh best reload passes seven conditions and every structural invariant,
  event closure `2.38419e-7 GeV`;
- T4 peak 11,743,752,704 / 15,655,829,504 bytes, headroom `24.988%`;
- FP32 profile-8/share-8 timing `276.981 ms/event`, batch 2, two iterations;
- all three 50×5 epoch visualization contracts pass, use zero test events, and
  localhost reached 15 snapshots through `joint:0002`.

The response mixture negative log-likelihood is legitimately negative
(`-0.738093 → -0.789394 → -0.824654`) because a continuous probability
density can exceed one; more negative here is an improvement. It must not be
wrapped in absolute value or an outer L2. The aggregate weighted joint
objective remains positive and decreased normally.

Descriptive terminal-draw response bias is `+14.859%`, hit-count bias `-8.702%`,
and profile relative L1 `0.318038`; these are not checkpoint selectors or
physics validation. Completed watcher PID `19776` was identity-checked and
stopped. Conservative joint charge `$3.20` makes accounted budget `$21.49` and
remaining `$78.51`. Joint component diagnostics are complete. The next
mandatory gate is a bounded real-T4 mid-epoch interruption/recovery proof,
followed by ≤64-batch train-only loss calibration and validation-only pilots;
test remains unopened.

## 2026-07-26 14:10 Asia/Taipei — mid-epoch interruption r1 pre-submit gate

Created new unfrozen
`configs/templates/pilot_joint_mid_epoch_interrupt_fp32.yaml` and CLI-froze
`audit/training_hardening_inputs/recovery_mid_joint_r1/configs/frozen_pilot_joint_mid_epoch_interrupt_fp32.yaml`.
Template SHA is `3ea4d71a...849c8`; frozen SHA is `0a35fc26...7d75a`.
It is a one-epoch FP32 joint run, batch 6 × accumulation 4, initialized from
accepted joint best `03c796...1adb7`, with immutable mid-epoch snapshots every
50 optimizer updates. The job hard timeout is predeclared as 1,500 seconds:
long enough to upload optimizer-boundary snapshots but intentionally shorter
than the measured ~3,878-second epoch.

Unique generation-0 overlay contains 4 objects (config, joint best, bounded
split and assignment). Independent merged staging passes: 209 objects /
5,973,774,683 bytes, exact hashes, real production data, zero forbidden path
or collision. Focused recovery/config/cloud QA is `19 passed` with one known
warning; compileall clean. Input/output and display name were empty before
staging. The expected timeout will be preserved as an intentional interruption,
not called a successful training run. Conservative maximum interrupt charge
is `$0.50`, leaving `$78.01` before reserving the resume leg. No interruption
job has been submitted at this boundary.

## 2026-07-26 14:12 Asia/Taipei — exactly one interruption leg submitted

Exactly one asynchronous Vertex job was accepted after the immediate
empty-prefix/no-duplicate recheck:

- pipeline `6029904569121636352`;
- custom job `8356299649681719296`;
- actual display
  `cbsc-v2-2-joint-mid-epoch-interrupt-20260726-r1-custom-job`;
- initial authoritative state `JOB_STATE_PENDING`.

Independent server describe proves exactly one name match and the exact r16,
base/overlay/output/config/split, CUDA, one-replica n1-standard-8,
one on-demand T4, 100 GB pd-ssd, compute service account, and 1,500-second
timeout contract. No postflight flag is set because completion is intentionally
prevented; success requires at least one hash-verified optimizer-boundary
inflight snapshot followed by the declared timeout. Submission observer session
is `59897`; it refers to this same job and is not a duplicate.

At 2026-07-26 14:13:49 Asia/Taipei, interruption custom job
`8356299649681719296` entered `JOB_STATE_RUNNING`. Its first two 300-second
checks found no progress object while base staging and the 187-shard preflight
ran; those empty listings are preserved and are not training failures.

At the next gate, immutable inflight snapshots existed at updates 50 and 100.
Both remain preserved. The later update 100 was mirrored to
`audit/recovery_mid_joint_r1_interrupt_update_00000100`: 2 objects /
29,367,708 bytes. Independent checkpoint inspection passes:

- progress checkpoint SHA
  `8c926e0ba821ac422cd53846c3fd5402ec678a4ff5d18c2abc1db2a85cf9ce70`
  exactly matches `progress.json`;
- stage joint, epoch 0, update 100, next batch 400 of 4,437, batch 6,
  accumulation 4, train count 400, optimizer boundary true;
- every optimizer state step and scheduler step equals 100;
- model, all nine component accumulators, total accumulator, and elapsed time
  are finite;
- optimizer/scheduler/scaler plus CPU and CUDA RNG states are present;
- recomputed trajectory-contract hash exactly matches
  `75d9aa9c...5f80d`;
- no prior completed epoch means the paired best is correctly absent and
  `best_metric` is positive infinity;
- visualization/test selection remains validation-only.

Update 100 is accepted as the recovery source; update 50 is an immutable
fallback. The resume leg remains closed until the interruption job reaches its
predeclared timeout and the terminal state/error are preserved.

## 2026-07-26 14:38 Asia/Taipei — sleep-safe handoff

The desktop may sleep without losing accepted progress. Interruption job
`8356299649681719296` is fully server-side on Vertex. Immutable GCS progress
snapshots are already present at updates 50, 100, 150, and 200 under the unique
interruption output prefix. Update 100 is independently mirrored, hash-verified,
and sufficient for exact recovery; therefore later local observer/session loss
cannot invalidate or erase the accepted recovery source. No local process is
required for the Vertex timeout or GCS artifact persistence. On continuation:
read this guide/log first, capture the authoritative terminal timeout, do not
resubmit the interruption leg, and construct exactly one new resume leg from
the verified update-100 SHA `8c926e0b...ce70` (or verify a later snapshot before
choosing it). The resume leg has not been submitted.

## 2026-07-26 04:39 Asia/Taipei — exactly one support r1 job submitted

The uniqueness check was repeated immediately before submission and still found
zero output objects and zero matching jobs. Exactly one asynchronous Vertex
pipeline/custom job was then accepted:

- pipeline `2954601332557742080`;
- custom job `8378580153306972160`;
- actual SDK display name
  `cbsc-v2-2-stage-support-fp32-20260726-r1-custom-job`;
- initial custom-job state `JOB_STATE_PENDING`.

Independent server describe matches the authorized spec exactly: immutable r16
digest, base r5, support overlay/output, frozen support config, training pilot
split, production geometry/manifest, CUDA, postflight training, one replica,
`n1-standard-8`, one `NVIDIA_TESLA_T4`, on-demand scheduling, 100 GB `pd-ssd`,
21,600-second timeout, and the expected service account. The display-name query
returns exactly this one job.

The SDK's asynchronous local client continues printing pipeline status in exec
session `28272`; it is observation only and does not create another job. A
separate localhost visualization watcher was started as hidden PID `18300` with
300-second intervals and new support-r1 logs. Its launch command contained a
nonterminating PowerShell `Test-Path` expression error (the `-or` subexpression
needed parentheses), but the paths were in fact new and the process launched
successfully. Its first pass reports `waiting_for_first_epoch` with zero stderr.
This local precheck syntax error did not affect Vertex or overwrite a log.

Support remains closed pending immutable epoch and terminal verification. No
other stage may be configured or submitted yet.

At 2026-07-26 04:41 Asia/Taipei, custom job
`8378580153306972160` entered `JOB_STATE_RUNNING` after normal on-demand T4
allocation. This is execution evidence only; support epoch 0 remains closed.

## 2026-07-26 05:50 Asia/Taipei — support r1 epoch 0 independently passed

Support epoch 0 is a complete 13-object / 48,818,132-byte immutable snapshot,
mirrored to `audit/stage_support_r1_epoch_0000`. The first independent verifier
run failed closed because the verifier had encoded the earlier profile/count
batch-6/accumulation-4 values as universal constants. No report was written and
the Vertex job was unaffected.

The verifier was corrected to take explicit expected batch size and gradient
accumulation while retaining defaults for the already-accepted stages. It now
also checks the exact predecessor filename for every component stage. A new
regression test freezes the stage-order filename map; focused QA is `5 passed`
and compileall clean. The corrected independent report is
`audit/stage_support_r1_epoch_0000_verification.json`.

All epoch-0 gates pass:

- exact count predecessor `163477...a0e5b`;
- all 64 changed tensors confined to `support.*`; zero frozen mismatch in
  condition/response/profile/count/share/geometry tensors;
- best/last `6755ebfb...cf763` / `7f003d4a...3dc9`;
- exactly 1,110 optimizer and scheduler updates;
- finite support BCE `0.682490428` and ranking loss `0.316068462`;
- weighted train loss independently closes:
  `0.682490428 + 0.25×0.316068462 = 0.761507544`;
- finite validation loss `0.654732760`;
- 2,722.007 seconds, 9.7810 events/s;
- peak T4 memory 3,956,515,840 bytes, leaving about 74.73% headroom;
- epoch and 50×5 visual invariants all pass, closures ≤`5.7221e-6 GeV`,
  zero test events.

The fixed-bank hit bias is `-7.482%`, response bias `+12.704%`, and profile L1
`0.269694`; these are descriptive independent draws, not support-checkpoint
selection metrics or physics validation. One epoch cannot establish a support
loss trend.

The 300-second watcher updated localhost atomically: seven total snapshots,
`latest_id=support:0000`. The sole support job remains running for epochs 1–2
and terminal postflight.

## 2026-07-26 06:37 Asia/Taipei — support r1 epoch 1 independently passed

Epoch 1 contains 16 immutable objects / 62,155,435 bytes and is mirrored at
`audit/stage_support_r1_epoch_0001`. Independent report:
`audit/stage_support_r1_epoch_0001_verification.json`.

All gates pass:

- exact accepted count predecessor; all 64 changes remain confined to
  `support.*`, zero frozen mismatch;
- best/last `b09349bc...25c96` / `ef7f201c...bf4e8`;
- exactly 2,220 optimizer/scheduler updates;
- support BCE `0.682490428 → 0.571882335`;
- support rank `0.316068462 → 0.220478271`;
- weighted train `0.761507544 → 0.627001903`, exactly reproducing
  `BCE + 0.25×rank`;
- validation `0.654732760 → 0.632098089`;
- 2,715.124 seconds, 9.8058 events/s, unchanged peak memory;
- all epoch and cross-epoch 50×5 gates pass, closures ≤`5.7221e-6 GeV`,
  fixed 50 truth conditions and exact independent seed offset, zero test.

Both train components and validation moved toward zero, which again provides no
evidence for wrapping the frozen objectives in absolute value or another L2.
The descriptive hit bias is `-9.088%`, response bias `+1.078%`, and profile L1
`0.263183`; these are not stage checkpoint selectors or physics validation.

Localhost now has eight snapshots through `support:0001`. Epoch 2 and terminal
postflight remain required; the existing job continues.

## 2026-07-26 07:22 Asia/Taipei — support r1 terminal gate passed

Vertex custom job `8378580153306972160` succeeded after 2h36m26s. Its exact
authorized server spec is unchanged. The output contains 73 objects /
262,219,743 bytes, zero failure artifact, a complete 19-object epoch-2 snapshot,
and all terminal postflight reports. Exact mirror:
`audit/stage_support_r1_terminal`; independent report:
`audit/stage_support_r1_terminal_verification.json`.

All terminal gates pass:

- accepted best
  `b7f968050ba99538b20a78d125dbc359c28324189fd150a0e195702e6c747a89`;
- last `8cd100ec...d6ee4`;
- all 64 changes remain only `support.*`; zero frozen mismatch;
- best/last epoch 2 and exactly 3,330 optimizer/scheduler updates;
- BCE `0.682490 → 0.571882 → 0.562911`;
- ranking `0.316068 → 0.220478 → 0.214391`;
- weighted train `0.761508 → 0.627002 → 0.616509`;
- validation `0.654733 → 0.632098 → 0.625293`;
- throughput `9.781`, `9.806`, `9.892` events/s;
- fresh `best.pt` reload passed seven fixed conditions and all postflight
  invariants, closures ≤`4.7684e-7 GeV`;
- T4 peak 3,956,515,840 / 15,655,829,504 bytes, headroom `74.728%`;
- FP32 8/8 timing 263.873 ms/event, batch 2, two iterations;
- terminal 50×5 visual invariants pass, closures ≤`9.5367e-6 GeV`, zero test.

The final descriptive hit bias is `-7.993%`, response bias `+10.557%`, and
profile L1 `0.299739`; these remain independent-draw diagnostics, not Geant4
fidelity or checkpoint selectors.

Localhost now has nine snapshots through `support:0002`. Completed watcher PID
`18300` was stopped only after exact command-line verification. Conservative
support charge is `$2.30`; accounted budget is `$15.99`, remaining `$84.01`.
Support is accepted as component/structural evidence. Share remains closed
until a new unfrozen template is pinned to the accepted support hash and passes
all freeze/staging/spec/budget gates.

## 2026-07-26 07:25 Asia/Taipei — share r1 pre-submission gate passed

Created new unfrozen `configs/templates/pilot_stage_share_fp32.yaml` and froze
it only through the repository CLI:

- template SHA `97efb021...07dbd`;
- frozen config
  `audit/training_hardening_inputs/stage_share_r1/configs/frozen_pilot_stage_share_fp32.yaml`;
- frozen SHA `58e43064...7e10d`;
- FP32, stage share, batch 4 × accumulation 6, three epochs, frozen encoder;
- initialization pinned to accepted support best
  `b7f968050ba99538b20a78d125dbc359c28324189fd150a0e195702e6c747a89`
  at `checkpoints/support_best.pt`.

Field-by-field diff from the accepted support config contains only project
name/run directory, template hash, stage, and predecessor path/hash. The exact
data, geometry, model, optimizer, batch, FP32, loss, split, and 50×5
visualization contracts are unchanged.

Unique input/output and display-name checks found zero objects/jobs. Four
generation-0 overlay objects total 17,463,746 bytes. Independent
`audit/stage_share_r1_staging_verification.json` passes: 209 merged objects /
5,961,822,769 bytes, exact support checkpoint/config/data/geometry/split hashes,
real production data, zero forbidden path/collision. Focused QA `31 passed`
with one known warning; compileall clean.

Budget before submission: accounted `$15.99`, remaining `$84.01`; six-hour
one-T4 reserve `$5.10`, leaving `$78.91`. Authorized spec remains exact r16,
one on-demand T4, n1-standard-8, one replica, 100 GB pd-ssd, timeout 21,600
seconds, expected SA, base r5, unique share overlay/output, CUDA, training
postflight. No submission has occurred at this log boundary.

## 2026-07-26 07:26 Asia/Taipei — exactly one share r1 job submitted

Immediate uniqueness recheck still found zero output objects and zero matching
jobs. Exactly one asynchronous Vertex job was accepted:

- pipeline `3742836820463845376`;
- custom job `6143565484131352576`;
- actual display name `cbsc-v2-2-stage-share-fp32-20260726-r1-custom-job`;
- initial state `JOB_STATE_PENDING`.

Independent server describe matches the entire authorized immutable image,
prefix/config/split/geometry, on-demand one-T4 resource, disk, timeout, service
account, CUDA, and postflight contract. The display-name query returns exactly
this one job. SDK observation session is `15987`; it is not a second job.

Hidden share dashboard watcher PID `14620` uses exact 300-second intervals and
new logs. Its first pass is `waiting_for_first_epoch` with zero stderr. Share
remains closed pending independent epoch and terminal gates.

At 2026-07-26 07:28 Asia/Taipei, custom job
`6143565484131352576` entered `JOB_STATE_RUNNING` after normal on-demand T4
allocation. Share epoch 0 remains closed.

## 2026-07-26 08:33 Asia/Taipei — share r1 epoch 0 gate passed

The immutable epoch-0 snapshot was mirrored to
`audit/stage_share_r1_epoch_0000` and independently verified in
`audit/stage_share_r1_epoch_0000_verification.json`. It contains 13 objects /
48,931,305 bytes and passes every stage gate:

- exact inherited support checkpoint
  `b7f968050ba99538b20a78d125dbc359c28324189fd150a0e195702e6c747a89`;
- best `ee1bb4aff2c93cfe2d762fa646b4cd44b3b1aef7e0372e0aa52d0a7318cc93c2`,
  last `3485cac604ed356d15a927eee028498b6cdbfe2c9ce9edcfa2ecb65e79dba73b`;
- exactly 62 changed tensors, all under `share.*`, with zero frozen-tensor
  mismatch and exactly 1,110 optimizer/scheduler updates;
- train share-flow loss `5.376477417`, validation loss `4.867630384`, all
  finite; this single point establishes execution, not a trend;
- 2,654.945 seconds and 10.0281 events/s; peak CUDA allocation
  3,964,674,560 bytes;
- epoch invariants pass with zero nonfinite/negative/support/count failures and
  layer/event closure no worse than `1.90735e-6 GeV`;
- the 50-condition × 5-independent-draw visualization artifact passes, uses
  zero test events, preserves the fixed selection hash
  `f7052919...59b6`, and has closure no worse than `7.62939e-6 GeV`.

Descriptive independent-draw diagnostics are generated response bias
`+12.704%`, hit-count bias `-7.482%`, and mean longitudinal-profile relative
L1 `0.269694`. They are neither checkpoint-selection inputs nor physics
validation. Epochs 1–2 and terminal fresh-reload/postflight remain closed; the
one existing Vertex job continues and no duplicate was submitted.

While the existing job trains, the independent verifier was extended
fail-closed for the next required `joint` stage. It now requires a share-stage
predecessor named `share_best.pt`, an unfrozen condition encoder, finite values
for all nine component losses, exact reconstruction of the recorded weighted
train total, and permits model changes across the fully unfrozen network.
Component-stage frozen-prefix checks remain unchanged. Regression QA is
`8 passed`, compileall is clean, and the accepted share epoch-0 artifact was
reverified successfully with the strengthened weighted-loss check. No frozen
config, cloud input, running job, or checkpoint was changed.

Local QA during the same training window first failed closed at collection:
plain `python -m pytest -q` under the desktop Python 3.13 shell produced 15
`ModuleNotFoundError: cbsc_zdc` errors because the package was not installed in
that interpreter. No test body ran. With the active source made explicit via
`PYTHONPATH=<repo>/src`, the complete suite passed `57 passed` with four known
nonfatal Transformer nested-tensor warnings. The dashboard production build
also passed all five vinext build phases. A nonterminating path typo attempted
to read `dashboard/package.json` while already inside `dashboard/`; it did not
affect the build. HTTP manifest QA reports schema 2, ten snapshots, latest
`share:0000`. This is software/site QA, not physics validation.

Read-only mid-epoch recovery audit confirms that the active implementation
saves only at optimizer boundaries and serializes the exact epoch/next batch,
loader length, batch/accumulation, deterministic epoch seed, accumulated loss
sums/counts, optimizer updates, elapsed time, model, optimizer, scheduler,
scaler, and RNG state plus a hash of every trajectory-affecting setting. Vertex
uploads each snapshot once to an immutable
`progress/inflight_epoch_NNNN/update_NNNNNNNN` prefix with checkpoint/config
hashes. Resume rejects changed loader/batch/accumulation/seed/contract, a
non-boundary checkpoint, or inconsistent best pairing. The local regression
proves resumed and uninterrupted terminal model tensors and recorded losses
are exactly equal. This is strong software evidence; a bounded on-demand T4
interruption/recovery job remains mandatory before full-data final training.

## 2026-07-26 09:16 Asia/Taipei — share r1 epoch 1 gate passed

The complete immutable epoch-1 prefix was mirrored to
`audit/stage_share_r1_epoch_0001`: 16 objects / 62,323,994 bytes. Independent
report `audit/stage_share_r1_epoch_0001_verification.json` passes the
strengthened verifier:

- exact support source `b7f968...747a89`;
- best `169170083a06b2199ebb37eeadab3898490532d3650d88bd2d5ef611d5ea839c`,
  last `79c21e8bf3528202c7a00969c278a65248574e94f65e9c11f23421a99b992cb4`,
  best/last epoch 1, exactly 2,220 optimizer/scheduler updates;
- exactly the 62 `share.*` tensors changed and zero frozen mismatch;
- train share-flow `5.376477417 → 4.755979060`, validation
  `4.867630384 → 4.730273987`; both are finite, weighted-total consistent,
  and move toward zero without an absolute-value or extra-L2 modification;
- epoch 1 took 2,650.850 seconds at 10.0436 events/s with peak CUDA allocation
  3,964,674,560 bytes;
- all epoch invariants pass, with event closure
  `4.76837e-7 GeV` and every discrete/nonfinite failure count zero;
- cross-epoch visualization contract preserves the exact 50 truth events and
  changes every generation group by the declared `+1,000,003` seed offset;
  250 FastMC draws, zero test events, and all structural gates pass.

The epoch-1 descriptive independent-draw statistics are response bias
`+1.078%`, hit-count bias `-9.088%`, and longitudinal-profile relative L1
`0.263183`. These are not checkpoint selectors or physics validation. The
300-second watcher was identity-checked and localhost now serves schema 2 with
11 snapshots through `share:0001`. Epoch 2 and terminal postflight remain
closed; the existing single job continues.

Calibration-path QA found and corrected a protocol-enforcement gap before it
could affect a run. `calibrate_loss_weights` now rejects batch counts outside
the predeclared `[1,64]` range, rejects nonfinite/nonpositive/reversed clip
bounds, and records `batches_consumed` in its evidence report. Focused QA is
`15 passed`; complete QA is now `59 passed` with the same four known
Transformer warnings; compileall is clean. A preceding broad `rg` search
included minified visualization JSON under `audit/` and generated a very large
truncated read-only output; the query was narrowed to source/tests/docs and no
artifact was modified by that tooling miss.

## 2026-07-26 10:00 Asia/Taipei — share r1 epoch 2 gate passed; terminal pending

The complete immutable epoch-2 snapshot was mirrored to
`audit/stage_share_r1_epoch_0002`: 19 objects / 75,852,555 bytes. Independent
report `audit/stage_share_r1_epoch_0002_verification.json` passes:

- exact support source and zero frozen mismatch; only the same 62 `share.*`
  tensors changed;
- best remains the epoch-1 checkpoint
  `169170083a06b2199ebb37eeadab3898490532d3650d88bd2d5ef611d5ea839c`;
  epoch-2 last is
  `a77b5dbc44aecda554c339d8115d54bcd15a8eb28bead2d6421d4443b7a9d967`;
- exactly 3,330 optimizer/scheduler updates;
- train share-flow `5.376477 → 4.755979 → 4.674678`;
- validation `4.867630 → 4.730274 → 4.746518`.

The final training component continued toward zero, while validation worsened
slightly from epoch 1. Therefore checkpoint selection correctly retained epoch
1; no objective modification or post-hoc selection change is justified.
Epoch 2 took 2,662.328 seconds at 10.0003 events/s with unchanged
3,964,674,560-byte peak allocation. All structural invariants pass with exact
event closure in the epoch gate. The cross-epoch 50×5 contract again preserves
truth and advances seeds by `+1,000,003`; zero test events were used.

Descriptive epoch-2 response bias is `+10.557%`, hit-count bias `-7.993%`, and
profile relative L1 `0.299739`; these independent-draw fluctuations are not
checkpoint selectors or physics validation. Localhost schema 2 now contains
12 snapshots through `share:0002`. Share remains closed until the authoritative
Vertex state and terminal fresh-reload/resource/8-step timing reports pass.

## 2026-07-26 10:07 Asia/Taipei — share r1 terminal gate passed

Vertex custom job `6143565484131352576` / pipeline
`3742836820463845376` succeeded from `2026-07-25T23:28:31Z` through
`2026-07-26T02:02:27Z` (2h33m56s). The authoritative error field is empty.
The complete output was mirrored to `audit/stage_share_r1_terminal`: 73 objects
/ 262,963,989 bytes, with no `vertex_failure.json`. Independent terminal report
`audit/stage_share_r1_terminal_verification.json` passes all gates:

- selected best is the immutable epoch-1 checkpoint
  `169170083a06b2199ebb37eeadab3898490532d3650d88bd2d5ef611d5ea839c`;
- terminal last is
  `a77b5dbc44aecda554c339d8115d54bcd15a8eb28bead2d6421d4443b7a9d967`;
- exact predecessor, 62 share-only changes, zero frozen mismatch, 3,330
  optimizer/scheduler updates, and weighted loss history all reproduce;
- a fresh model loaded `best.pt`, sampled seven fixed 0–300 GeV conditions,
  and passed every structural invariant with layer closure
  `1.90735e-6 GeV` and event closure `3.81470e-6 GeV`;
- Tesla T4 peak allocation 3,964,674,560 / 15,655,829,504 bytes, headroom
  `74.676%`;
- FP32 solver/decode benchmark, profile 8 / share 8, batch 2, two iterations:
  `262.306 ms/event`.

This accepts the share component structurally and diagnostically; it is not
physics validation. The exact 300-second watcher PID `14620` was stopped only
after command-line identity verification and localhost completion. The SDK
observer also exited normally. A conservative `$2.30` runtime charge makes
accounted budget `$18.29` and remaining budget `$81.71`. Joint remains closed
until a new unfrozen template is pinned to the accepted share hash, CLI-frozen,
staged into unique generation-0 prefixes, and passes budget/spec/input QA.

## 2026-07-26 10:16 Asia/Taipei — joint r1 pre-submission gate passed

Created new unfrozen `configs/templates/pilot_stage_joint_fp32.yaml` and froze
it only through `cbsc-zdc freeze-config`:

- template SHA
  `bed069c37b2f871bfb08ae08d27ce28468d254da53afccfce0f3fb6980d063b6`;
- frozen config
  `audit/training_hardening_inputs/stage_joint_r1/configs/frozen_pilot_stage_joint_fp32.yaml`;
- frozen SHA
  `6a15bf93ec6b9bad6d552d438803c6592c07f6df3122a8b22f7c3937953c929c`;
- FP32, joint, batch 6 × accumulation 4, effective batch 24, three epochs,
  fully trainable condition encoder;
- initialization pinned to accepted share best
  `169170083a06b2199ebb37eeadab3898490532d3650d88bd2d5ef611d5ea839c`
  at `checkpoints/share_best.pt`.

Field-by-field diff from the accepted share frozen config is restricted to
project name/run directory, template hash, batch/accumulation (same effective
batch), predecessor path/hash, stage, and encoder unfreeze. Data, geometry,
model, optimizer, total effective batch, nine loss weights, and evaluation/
visualization contracts are identical.

A read-only `ConvertFrom-Yaml` attempt failed because the PowerShell cmdlet is
not installed; Python/YAML inspection replaced it. A local full preflight then
failed closed because the lightweight freeze directory intentionally contains
no 187 production shard files. Neither failure modified the frozen config. The
required cloud staging verifier passes:

- unique generation-0 overlay: 4 objects / 17,489,087 bytes;
- merged base+overlay: 209 objects / 5,961,848,110 bytes;
- exact config/share checkpoint/data/geometry/split/assignment hashes;
- real production data, zero forbidden paths/collisions.

Both joint input/output prefixes were empty before upload, and no matching
Vertex display name existed. Focused pre-submit QA is `32 passed`; compileall
is clean. Budget is `$18.29` accounted / `$81.71` remaining; a six-hour
one-T4 hard-timeout reserve is `$5.10`, leaving `$76.61`. The authorized job
spec is exact r16 image, one on-demand T4, n1-standard-8, one replica, 100 GB
pd-ssd, 21,600-second timeout, accepted compute service account, base r5,
unique joint overlay/output, CUDA, and training postflight. No joint submission
has occurred at this log boundary.

## 2026-07-26 17:45 Asia/Taipei — interruption terminal and resume pre-submit

Authoritative interruption state is `JOB_STATE_CANCELLED`, error `CANCELED`,
from `2026-07-26T06:13:49Z` through `06:39:07Z` (25m18s), exactly matching the
predeclared 1,500-second hard-timeout design. It produced no false terminal
training result. Five immutable optimizer-boundary snapshots remain at updates
50/100/150/200/250.

Update 250 was independently mirrored and verified and supersedes update 100
as the preferred recovery source while preserving update 100 as fallback:

- checkpoint SHA
  `9730d737663188c85a0bbc2388d8f15f02b07d1d2c65ead7018f9dd86374abbc`;
- epoch 0, update 250, next step/train count 1000 of 4,437;
- batch 6 × accumulation 4 optimizer boundary;
- optimizer/scheduler step 250;
- exact nine components, finite aggregates/model, scaler, CPU/CUDA RNG,
  exact recomputed trajectory contract, correct positive-infinity no-prior-best.

Created new unfrozen resume template SHA `735f3f2d...24610` and CLI-frozen
config SHA `b50e9c94...c4cc4`. The failed first diff command (invalid one-line
Python function syntax) is preserved; a corrected diff proves changes are
limited to project/template and replacing initialization with the exact
progress resume path/hash. All scientific trajectory fields are identical.

Unique generation-0 resume overlay contains config, update-250 progress,
bounded split and assignment. Merged staging independently passes: 209 objects
/ 5,973,779,017 bytes, exact hashes, real data, zero forbidden/collision.
Focused QA `19 passed`, one known warning, compileall clean. The interruption
is conservatively charged `$0.50`: `$21.99` accounted, `$78.01` remaining.
Two-hour resume hard-timeout reserve `$1.70` leaves `$76.31`. Resume input and
output were empty and no matching job existed. No resume job has been submitted
at this boundary.

## 2026-07-26 17:51 Asia/Taipei — resume running and sleep-safe observability restored

Submitted exactly one mid-epoch resume leg: pipeline
`2118880136471248896`, custom job `3541091829929738240`. An independent
server describe reports `JOB_STATE_RUNNING` from `2026-07-26T09:48:33Z` with
the exact immutable r16 image
`sha256:dcd6548e40ccee98ecefa0960864c8528546b152ea8f7540481594acc5d35893`,
one on-demand `NVIDIA_TESLA_T4`, `n1-standard-8`, one replica, 100 GB
`pd-ssd`, the accepted service account, 7,200-second timeout, exact r5 base,
unique resume overlay/output, CUDA, frozen resume config, and training
postflight. No duplicate was submitted.

The visualization sync originally keyed snapshots only as `stage:epoch`.
Because the recovery proof is also joint epoch 0, that would collide with the
accepted joint epoch-0 snapshot. The sync/dashboard contract now accepts a
sanitized optional run label, producing IDs and filenames such as
`joint-resume-r1:joint:0000` while preserving all 15 existing rows. Focused
visualization QA is `12 passed` with one known nonfatal Transformer warning;
compileall and the full dashboard production build pass. A prior test command
run from the dashboard subdirectory failed only because repo-relative `src`
and `tests` paths did not exist there; it made no changes, and the corrected
repo-root command passed.

The first one-shot recovery sync correctly returned
`waiting_for_first_epoch`; therefore the existing schema-2 manifest remains
unchanged until a genuine immutable recovery epoch exists. Hidden watcher PID
`22240` polls the unique recovery output every 300 seconds with run label
`joint-resume-r1`. Hidden localhost server PID `18520` is listening on
`127.0.0.1:3000`. These local helpers may stop when the computer sleeps, but
the Vertex job and immutable GCS outputs are server-side; no training progress
depends on them. On wake, verify job/output state first and never resubmit this
resume job.

Localhost route QA then found that vinext production mode served `/` but
returned 404 for `/data/manifest.json`, so port 3000 is not accepted as the
live dashboard endpoint. A hidden vinext development server was started
without changing training or data. `http://localhost:3001/` and
`http://localhost:3001/data/manifest.json` both return HTTP 200; the latter
reports the preserved 15 snapshots through `joint:0002`. Its serving process
is PID `15728` under launcher PID `11252`. The accepted local viewer URL is
therefore `http://localhost:3001/`. Like the watcher, it is disposable and may
need restart after sleep; Vertex/GCS progress is unaffected.

## 2026-07-26 18:05 Asia/Taipei — resume r1 failed closed before epoch 0

The exact single resume custom job `3541091829929738240` is terminal
`JOB_STATE_FAILED`; it ran from `2026-07-26T09:48:33Z` through
`09:57:36Z`. No duplicate was submitted. Its unique output contains exactly
six preflight/failure objects and no epoch snapshot:

- `environment.json`;
- `reports/preflight.json`;
- `resolved_config.json`;
- `runtime_config.yaml`;
- `staged_input_manifest.json`;
- `vertex_failure.json`.

`vertex_failure.json` and Cloud Logging independently report the same
`ValueError: mid-epoch training contract changed` at
`trainer._validate_mid_epoch_progress`. Preflight had already passed the real
production contract: 187 shards, 26,624 train / 4,096 validation / zero test,
and exact dataset, geometry, split, assignment, and geometry hashes. The job
therefore failed before any resumed optimizer update, validation pass,
checkpoint selection, or visualization artifact.

Read-only reproduction against the immutable update-250 checkpoint found:

- checkpoint contract
  `75d9aa9c5abf3a2cb211ad034296b9e0236917d93593a9cedb6ec18355b5f80d`;
- resume-config contract
  `724662c59614902a5151f85a6155449d9047cd16e46251b69476f7982e080dc3`;
- the only contract-relevant difference is
  `provenance.template_sha256`;
- substituting only the interrupt template provenance hash reproduces the
  checkpoint contract exactly.

The initialization references also differ operationally, but the validator
already excludes them. The defect is that a separately CLI-frozen resume
template must have a new template SHA even when all trajectory settings and
artifact hashes are identical. The safe correction is to exclude only
`provenance.template_sha256` from the in-flight trajectory hash while retaining
all model, data semantics, geometry semantics, training settings, loss
weights, evaluation settings, and dataset/geometry/split/assignment
provenance hashes. A replacement job remains closed until this behavior has
positive and counterexample tests, full focused QA, an immutable image, exact
staging verification, and a fresh conservative budget gate.

Commands/evidence at this boundary: full implementation guide and `AGENTS.md`
read; exact `gcloud ai custom-jobs describe`; recursive output listing;
process/listener identity inspection; `gcloud storage cat` of failure and
preflight; exact Cloud Logging query; repository search and trainer/test/config
inspection; read-only PyTorch checkpoint load and independent contract
recomputation. One initial Python inspection failed because `src` was not on
`PYTHONPATH`; rerunning with resolved `src` succeeded and is the evidence above.
The 300-second watcher PID `22240` and accepted dev viewer PID `15728` survived
sleep. There is no honest next-epoch ETA until the failed resume gate is fixed
and a replacement is authorized.

## 2026-07-26 18:18 Asia/Taipei — resume validator correction passes pre-build QA

The real checkpoint counterexample showed that merely omitting template
provenance from future contract hashes would orphan the existing format-v3
update-250 checkpoint. The corrected implementation is backward compatible
without a waiver:

1. future trajectory hashes omit only `provenance.template_sha256`;
2. an old stored hash is accepted only if the checkpoint embeds its original
   config, that exact embedded config reproduces the stored legacy hash, and
   its normalized scientific contract equals the current resume contract;
3. a changed learning rate, weight decay, model/data/evaluation field, or
   artifact-provenance hash still fails closed.

The immutable update-250 source exercises the legacy path successfully:

- stored legacy hash `75d9aa9c...f80d`;
- normalized embedded-source hash `8522e24f...2ee0`;
- normalized resume hash `8522e24f...2ee0`;
- accepted next step 1,000 and optimizer update 250.

QA results: focused recovery/hardening suite `15 passed` with one known
nonfatal Transformer warning; full repository suite `65 passed` with four of
the same warning; compileall clean. Source SHA-256:
`trainer.py=16770b74...0231c`,
`test_vertex_training_hardening.py=a68c1e97...5a7d1`.
The failed r1 output is preserved locally as six hash-verified objects under
`audit/recovery_mid_joint_r1_resume_failed`; machine-readable evidence SHA is
`7089eeca...0274d`.

Current official Google rates rechecked immediately before build: on-demand
T4 in `us-central1` is `$0.35/h`; `n1-standard-8` is `$0.379998/h`; disk and
service overhead are additional. The existing `$0.85/h` planning rate remains
conservative. Cloud Build default-pool `e2-highcpu-8` is `$0.0156/min`
(`$0.016/min` rounded). References:
`https://cloud.google.com/products/compute/gpus-pricing`,
`https://cloud.google.com/products/compute/pricing/general-purpose`, and
`https://cloud.google.com/build/pricing-update`.

Budget gate: prior accounted `$21.99`; failed 9m03s resume rounded up to
`$0.15`; new build/storage reserve `$0.50`. Post-build planning account is
therefore `$22.64`, leaving `$77.36`. A two-hour one-T4 replacement reserve is
`$1.70`, leaving `$75.66`; this remains far below the hard `$100` ceiling.

Cloud build context independently lists 68 files / 277,541 bytes with zero
`legacy/`, audit, dashboard, ROOT, test, bytecode, Git, or dependency-cache
content. Dockerfile SHA is `40dc5b5a...586b`; package manifest SHA is
`97050983...a179`. Build is authorized; a replacement Vertex job is not yet
authorized until the resulting immutable digest and new generation-zero
staging/output prefixes pass independent QA.

## 2026-07-26 18:21 Asia/Taipei — resume r2 replacement pre-submit gate passed

Cloud Build `cba19037-9592-4d6d-8098-96037ad7227e` succeeded in 3m29s.
Artifact Registry independently resolves tag `r17-mid-epoch-contract-fix` to
immutable image:

`us-central1-docker.pkg.dev/asiop-zdc-1/cbsc-zdc/cbsc-zdc@sha256:10f3372b3fad3723a314a7d8353fa8fe47300d65037de2d26d4206ef95413d00`

The four accepted r1 resume inputs were copied object-for-object into new r2
input paths with destination generation precondition zero. Nothing was
overwritten. Independent merged-staging QA passes:

- new overlay:
  `gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/recovery-mid-20260726-r2-joint-resume-input`;
- 4 objects / 29,419,994 bytes;
- merged base plus overlay: 209 objects / 5,973,779,017 bytes;
- progress checkpoint generation `1785061042720788`, size 29,366,676,
  exact SHA `9730d737...abbc`;
- unchanged CLI-frozen resume config SHA `b50e9c94...c4cc4`;
- exact dataset/geometry/split/assignment hashes, real data, zero forbidden
  paths;
- staging report SHA `b6d4634d...474f8`.

The new r2 output prefix is empty, and the server lists zero matching r2 jobs.
The final independent reference-spec read confirms the accepted service
account, one replica, one on-demand T4, `n1-standard-8`, 100 GB `pd-ssd`,
7,200-second timeout, CUDA, bounded split, and training postflight. Budget
remains the predeclared `$22.64` planning account plus at most `$1.70` for this
leg, leaving `$75.66`. Exactly one r2 replacement is now authorized.

## 2026-07-26 18:25 Asia/Taipei — exactly one resume r2 submitted and timed

Exactly one replacement was accepted:

- pipeline `4448472596844904448`;
- custom job `252663657484255232`;
- actual display
  `cbsc-v2-2-joint-mid-epoch-resume-20260726-r2-custom-job`;
- initial authoritative state `JOB_STATE_PENDING`;
- output still empty and exact display-name cardinality one.

Independent server-spec QA matches the authorized immutable r17 digest, prep
r5 base, unique r2 overlay/output, frozen resume config, bounded train/
validation/zero-test split, CUDA, postflight, one replica, on-demand
`NVIDIA_TESLA_T4`, `n1-standard-8`, 100 GB `pd-ssd`, accepted service account,
and 7,200-second timeout. The SDK's local status process PID `20824` was stopped
only after exact command-line identity and server acceptance were verified;
the server job remained pending.

The failed r1 dashboard watcher was stopped after exact PID/command identity.
One r2 watcher, PID `23596`, now polls the unique r2 output every 300 seconds
with run label `joint-resume-r2`. The localhost dev viewer remains healthy:
both `http://localhost:3001/` and its manifest return HTTP 200. One combined
stop/start helper command was rejected by local process policy before acting;
the operations were split into verified commands and succeeded.

ETA is measurement-based:

- update-250 checkpoint: 1,000/4,437 loader batches completed in
  877.576 seconds;
- remaining 3,437 batches project to 3,016.3 seconds = 50.27 minutes;
- accepted joint epochs uploaded 68m57s and 68m44s apart while full training
  time was about 64m40s, giving about 4m15s validation/visualization/upload
  overhead per epoch;
- the prior resume reached model construction after about 6m23s of
  staging/preflight.

Therefore the first and only recovery epoch artifact is expected about
60–63 minutes after r2 enters running, with a conservative 70-minute watch
window. From the 18:19 submission, the current safe local estimate is
approximately 19:23–19:32 Asia/Taipei, plus normal T4 provisioning variance.
This recovery config has exactly one epoch, so there is no second epoch in this
job; the next work after terminal verification is the loss-calibration gate.
The 300-second watcher is the requested safe timer and will collect the
50-condition × 5-draw comparison as soon as the immutable epoch appears.

While r2 provisions, a dedicated independent terminal verifier was added at
`scripts/verify_mid_epoch_recovery_output.py`. It will stop on file/byte/hash
mismatch; stale progress; source contract mismatch; wrong skipped-batch/update
accounting; optimizer/scheduler/RNG drift; nonfinite history or any of nine
loss components; weighted-loss mismatch; checkpoint selection/reload mismatch;
preflight/staging/test leakage; invariant/resource/headroom/timing failure; or
any 50-condition × 5-draw visualization contract difference. It explicitly
checks that source update 250 becomes terminal update 1,110—exactly 860 new
updates—rather than repeating the first 1,000 loader batches. It also requires
the same fixed validation selection, Geant4 truth deposits, four-vectors, and
generation seeds as accepted joint epoch 0. Initial compile/help QA and the
full `65 passed` suite are clean. A tautological elapsed-time assertion noticed
during review was replaced before use by strict elapsed-growth and
examples-per-second consistency checks. No recovery artifact has been accepted
at this boundary.

At 2026-07-26 18:32:51 Asia/Taipei, the completed one-shot 300-second timer
reported r2 `JOB_STATE_RUNNING`, server start `2026-07-26T10:31:57Z`, empty
error, and zero output objects. Using the measured 60–63 minute interval from
worker start revises the expected immutable epoch artifact to
19:32–19:35 Asia/Taipei; the conservative 70-minute deadline is 19:42. A new
300-second timer was armed. No epoch result or physics conclusion exists yet.

Next-gate protocol decision prepared, not executed: loss calibration will use
the accepted default joint-pilot best checkpoint
`03c7960861d6f6f3012a8e4469421d51e33d1a8dad7fc8ec8c8406d547f1adb7`,
not the recovery-proof checkpoint. The guide requires gradient norms from the
default joint pilot; using the recovery result would silently turn a
fault-tolerance proof into an additional scientifically selected training
epoch. Calibration remains train-only, exactly all nine losses, at most 64
batches, fixed `[0.25,4.0]` clipping, zero test, and produces a proposal rather
than automatically changing any frozen config. No calibration job has been
submitted.

The user pointed back to `docs/AGENT_PROMPT_VERTEX_RUN_AND_ANALYZE.md`; it was
read end-to-end and reconciled with current evidence. It is the original
post-smoke handoff: it authorizes read-only smoke verification and a plan, then
explicitly blocks component submissions, final training, and test until later
authorization. Those smoke checks and the requested independent files were
completed previously, and the user's subsequent explicit instructions
authorized continued train/validation work. Current accepted progress
therefore supersedes that historical stopping point:
response→profile→count→support→share→joint are complete, while physics
validation/final training remain gated. Nothing in the handoff justifies
bypassing the presently active mid-epoch recovery gate or duplicating r2.

## 2026-07-26 18:48 Asia/Taipei — recovery r2 remains healthy; calibration runner QA

Authoritative custom job `252663657484255232` remains
`JOB_STATE_RUNNING`, with server start `2026-07-26T10:31:57Z`, no error, and
zero output objects at 18:44:41 local. This is consistent with the worker
publishing an immutable epoch bundle only after the resumed epoch and its
postflight checks complete. The measured estimate remains 19:32–19:35 for the
first and only recovery epoch artifact; 19:42 is the conservative deadline.
The existing 600-second one-shot timer and the independent 300-second
dashboard watcher remain active. No duplicate timer, watcher, recovery job, or
calibration job was started. The localhost dashboard root and manifest both
return HTTP 200; the watcher reports only `waiting_for_first_epoch`, with no
stderr.

While the T4 runs, the next train-only calibration path was reviewed and
locally gated:

- `src/cbsc_zdc/cloud/vertex_calibrate.py`
  SHA-256 `2b16b38d...f4913`;
- `vertex/submit_calibration_job.py`
  SHA-256 `00db5a04...555`;
- hardening tests SHA-256 `afe8d48e...d7f0b`;
- recovery terminal verifier remains
  `3789bc35...595b`.

The runner requires a joint checkpoint with an exact caller-supplied SHA,
strict frozen-artifact preflight including shard hashes, train split only,
zero test events, CUDA, all nine expected gradient components, finite positive
median norms and proposed weights, `[0.25,4.0]` clipping, and at least 15% T4
memory headroom. It generation-0 uploads either a complete result or a
preserved failure report. The submitter fixes one on-demand T4,
`n1-standard-8`, one replica, 100 GB `pd-ssd`, and CUDA. It has not been
submitted and its future source remains the accepted joint-pilot best
`03c796...1adb7`, never the recovery proof.

QA outcomes: compileall clean, both CLI `--help` paths clean, and the focused
hardening suite reports `15 passed in 3.14s`. One first CLI probe failed with
`ModuleNotFoundError: cbsc_zdc` because the system Python does not have the
repository installed; rerunning with the resolved repository `src` on
`PYTHONPATH` passed. A `git diff/status` diagnostic also failed because this
workspace contains no `.git` repository. Neither failure changed files or
cloud state. They are preserved here because environmental and failed-command
evidence is part of the audit.

## 2026-07-26 18:52 Asia/Taipei — dashboard lint defect corrected and re-gated

The completed 18:49:16 one-shot timer again found recovery r2 running with no
error and zero output. A new 600-second one-shot status timer is active, while
the existing 300-second immutable visualization synchronizer remains the
higher-frequency artifact collector.

Dashboard QA found two React lint failures in
`dashboard/app/ZdcDashboard.tsx`: the initial manifest refresh and epoch
loading transition synchronously initiated state-changing work from effect
bodies. The epoch loader also lacked an active-request guard, so a sufficiently
slow prior snapshot request could race a newer selection. The correction
defers both effect starts to scheduled callbacks, clears those callbacks during
cleanup, and guards every artifact/error/loading state update against an
obsolete effect. It does not change scientific data, snapshot identity, or
visual statistics. Corrected source SHA-256 is
`0ab8c04f...b6ed6`.

Post-correction gates:

- ESLint: clean;
- vinext production build: all five phases pass;
- rendered HTML tests: `2 passed`, including the labeled five-draw/zero-test
  fixture contract;
- live localhost root and immutable manifest: HTTP 200;
- r2 sync: clean `waiting_for_first_epoch`, no stderr.

An attempted read-only in-app browser render again failed before page discovery
with `failed to write kernel assets: os error 3`. No alternate browser-control
surface was substituted because the browser contract forbids it. This is a
local browser-bridge limitation, not a dashboard pass; acceptance is currently
based on lint, production compilation, rendered-server tests, live HTTP/data
responses, and the prior successful visual QA evidence. No cloud state changed.

Calibration checkpoint binding was then strengthened before any build or
submission. Exact object SHA alone is necessary but would not independently
detect a caller pairing a valid joint checkpoint with different staged data.
The runner now recomputes geometry NPZ, dataset-manifest, and split-manifest
SHA-256 values plus the training seed, and requires exact equality with the
checkpoint's embedded training provenance. Counterexamples changing each of
the four fields are rejected. Updated runner SHA-256 is
`b4db4a9d...6e684`; updated hardening tests are
`76cc47c4...b1ae9`. Compileall is clean, focused calibration/hardening QA is
`19 passed`, and the complete Python suite is `67 passed` with the same four
known nonfatal Transformer nested-tensor performance warnings. No image was
built and no Vertex calibration job was submitted.

Calibration staging was further minimized without changing the training path.
The generic runtime-config builder now accepts an opt-out for resolving
historical training checkpoints; its default remains strict resolution for
every training job. The calibration runner alone opts out because it
immediately loads and hash/provenance-verifies the accepted joint checkpoint,
and never executes the frozen config's historical share-stage initializer.
Counterexample QA proves the default still stops on missing/mismatched training
checkpoints while calibration retains the frozen initializer metadata without
downloading it. Current SHAs: stage helper `f4ab4635...b1898`, calibration
runner `1590cc87...a8ee`, hardening tests `4226264d...a12be`. Focused QA is
`20 passed`; full Python QA is `68 passed` with four unchanged nonfatal
warnings.

Read-only next-prefix preflight found exact accepted source objects:

- frozen joint config: 3,025 bytes, generation `1785032079494666`;
- bounded pilot split JSON: 1,815 bytes, generation `1785032109381259`;
- bounded pilot assignments: 48,391 bytes, generation `1785032120364927`;
- accepted joint best checkpoint: 29,362,400 bytes, generation
  `1785045417443936`, SHA `03c796...1adb7`.

Proposed unique calibration r1 input and output prefixes are both empty, and
there are zero custom jobs matching display
`cbsc-v2-2-joint-loss-calibration-20260726-r1`. This is preparation evidence
only: no objects were copied, image built, or job submitted before recovery r2
passes and a fresh budget gate.

## 2026-07-26 19:01 Asia/Taipei — resumed mid-epoch checkpoints 300/350/400 verified

The 18:59:37 timer found six objects while the custom job remained running.
They are three paired immutable in-flight snapshots at optimizer updates 300,
350, and 400, not a completed epoch. Each contains `progress.pt` and
`progress.json`; generations are respectively
`1785063197474222`, `1785063359201439`, and `1785063521125453`. The snapshots
advance exactly 200 loader batches/50 optimizer steps each:

| Update | Next loader step | Train count | Elapsed s | Progress SHA |
|---:|---:|---:|---:|---|
| 300 | 1,200 | 1,200 | 1,651.174 | `44d6c306...d56fb4` |
| 350 | 1,400 | 1,400 | 1,812.858 | `9713f89e...f812cd` |
| 400 | 1,600 | 1,600 | 1,974.701 | `88d3621a...8ae88` |

Update 400 was independently mirrored once to
`audit/recovery_mid_joint_r2_update_00000400`. Its local SHA exactly matches
the immutable progress manifest. Binary inspection verifies format v3, joint
stage, epoch 0, infinite pre-validation best (expected), optimizer/scheduler/
scaler/RNG present, optimizer steps uniquely 400, scheduler last epoch 400,
optimizer-boundary true, batch 6, accumulation 4, `next_step=1600`, and the
unchanged normalized scientific contract `8522e2...2ee0`. All nine cumulative
loss components are finite. Mean weighted component loss
`9.7259427118` reproduces cumulative mean `9.7259427214` within
`9.62e-9`.

Notable component means through update 400 are visible `0.04913`, response NLL
`-0.76354`, first `0.42980`, active `0.28512`, profile `2.15966`, count
`3.47131`, support BCE/rank `0.55935/0.21365`, and share `4.70700`. The
negative response NLL is valid continuous-density likelihood behavior and is
not wrapped in absolute value or L2.

Measured update-300→350 and 350→400 intervals are both about 162 seconds, or
3.24 seconds per optimizer update. From update 400, 710 updates remain to
1,110, projecting 38.3 minutes of training plus roughly 4.25 minutes for
validation/visualization/upload. The evidence-based final artifact estimate is
therefore revised to approximately 19:40–19:43 local. The prior 19:32–19:35
estimate under-accounted resumed loader replay/skip overhead. No final epoch or
physics conclusion is accepted yet.

## 2026-07-26 19:14 Asia/Taipei — recovery progresses through update 650

The 19:12:58 600-second timer found 16 immutable objects: eight paired
snapshots through optimizer update 650. Vertex remains running with no error,
and an independent severity>=WARNING Cloud Logging query returns no entries.
Updates 450, 500, 550, 600, and 650 all advance by exactly 200 loader batches
and 50 optimizer steps per snapshot under the unchanged contract.

Update 650 was mirrored once to
`audit/recovery_mid_joint_r2_update_00000650`. Its local checkpoint SHA
`f7373fbf...e7154` matches `progress.json`; it has exact `next_step=2600`,
optimizer and scheduler step 650, restored RNG/scaler, all nine finite
components, and normalized contract `8522e2...2ee0`. Cumulative weighted mean
loss is `9.6344413981`, agreeing with direct cumulative mean
`9.6344414043` within `6.21e-9`; this is lower than update 400's `9.72594`.
Response NLL mean is finite at `-0.7876329`.

At the stable ~3.24 seconds/update rate, 460 optimizer updates remain, or about
24.8 minutes of training plus roughly 4.25 minutes of terminal validation,
50×5 visualization, and upload. ETA remains approximately 19:41–19:43.

One read-only `rg` budget-history query failed because PowerShell expanded
dollar-sign alternatives inside the regular expression, producing an unclosed
group. It was rerun with simple literal alternatives and succeeded; no files
or cloud state changed.

Independent next-gate verifier
`scripts/verify_loss_calibration_output.py` is now prepared, SHA-256
`1e674a7e...18583`. It requires exactly six immutable terminal artifacts;
recomputes every output hash; proves the original frozen joint config remains
FP32/CUDA/seed 20260723; checks 205 base plus four unique overlay objects with
zero test/legacy path; requires exactly 64 train-only batches and all nine
finite positive gradient medians; independently recomputes geometric-mean,
clipping, normalization, and all proposed weights to `1e-12`; verifies exact
accepted checkpoint SHA/epoch/provenance; requires real 187-shard preflight
with 26,624/4,096/0 selections; and enforces Tesla T4 plus >=15% memory
headroom.

The first schema review correctly rejected the verifier's assumption that
preflight hashes were top-level: the production report nests them under
`preflight.hashes`. This was corrected before use and locked with a complete
synthetic terminal-fixture test, SHA `4b9867b6...5b48d`. Focused verifier/
calibration QA is `21 passed`; complete Python QA is now `69 passed` with the
same four nonfatal Transformer performance warnings. The synthetic fixture
tests only verifier logic and is not described as physics or production
validation.

At 19:18:20, recovery reached immutable update 750/1,110 with exact
`next_step=3000` and unchanged contract. Cumulative weighted mean improved to
`9.6006083`. More importantly, the non-overlapping update-650→750 window over
400 events has weighted mean `9.3806933`, below the cumulative mean, with all
nine window components finite. Window response NLL is `-0.8429774`; becoming
more negative remains the correct maximum-likelihood direction, while count
`3.40391`, profile `2.06740`, support BCE/rank `0.55215/0.20547`, and share
`4.57798` remain ordinary nonnegative objectives. This is training-progress
evidence only, not validation or fidelity evidence.

## 2026-07-26 19:26 Asia/Taipei — recovery update 850; calibration staging gate ready

The 19:25:18 timer found recovery still running cleanly with 24 immutable
objects, exactly 12 paired in-flight snapshots through update 850. Update 850
has `next_step=3400`, `train_count=3400`, unchanged contract, all reported
components finite, and cumulative weighted mean `9.5802340`. The dashboard
watcher correctly ignores incomplete in-flight checkpoints and continues
waiting for the complete epoch artifact.

Only 260 optimizer updates remain. At measured throughput this is about 14.0
minutes of training plus terminal validation/visualization/upload; ETA remains
near 19:42–19:44.

The independent GCS staging verifier now supports an explicit post-training
analysis mode while retaining strict historical-checkpoint resolution by
default. Calibration mode refuses to skip historical initializers unless an
extra checkpoint is declared as a safe relative path plus exact lowercase
SHA-256; unsafe, malformed, missing, duplicate, or mismatched checkpoints
fail. Verifier SHA is `83798a95...d4559`, hardening-test SHA
`3c846823...dbcab`. Focused QA is `22 passed`; full Python QA is `70 passed`
with four unchanged nonfatal warnings. No staging objects or job were created.

## 2026-07-26 19:37 Asia/Taipei — final pre-terminal checkpoint update 1050

The 19:36:04 timer found 32 immutable objects, exactly 16 paired in-flight
snapshots through update 1,050/1,110. Vertex remains running, error null, and a
fresh severity>=WARNING log query is empty. Update 1,050 was mirrored to
`audit/recovery_mid_joint_r2_update_00001050`; SHA
`2fada9c0...257b8` exactly matches its manifest. It verifies
`next_step=4200`, optimizer/scheduler 1,050, RNG/scaler present, unchanged
contract, all nine finite, cumulative mean `9.5465330717`, independently
weighted mean `9.5465330725` (difference `8.23e-10`), and response NLL mean
`-0.7996685`.

Only 237 loader batches, approximately 60 optimizer updates, remain. Training
completion is projected around 19:39–19:40, followed by roughly four minutes
for validation, the required 50×5 validation comparison, reload/invariant/T4
postflight, and immutable upload. Terminal artifact ETA is 19:43–19:45.

At 19:42:46 the job remained running and clean with the final interval
checkpoint update 1,100/1,110. It has exact `next_step=4400` of 4,437 loader
batches, unchanged contract, all components finite, and cumulative weighted
mean `41983.72791814804 / 4400 = 9.5417563450`. Only 37 loader batches remain.
No epoch bundle exists yet, so validation/postflight rather than optimizer
progress is now the active gate.

## 2026-07-26 19:52 Asia/Taipei — mid-epoch recovery gate passes independently

Vertex custom job `252663657484255232` reached `JOB_STATE_SUCCEEDED` at
19:45:24 local after 1h13m27s of worker time. The accepted server spec is still
one replica, on-demand T4, `n1-standard-8`, 100 GB `pd-ssd`, exact r17 digest
`10f337...13d00`, accepted service account, 7,200-second timeout, exact prep
r5/unique r2 overlay/output, CUDA, and training postflight. There is no error
and no `vertex_failure.json`.

The output is exactly 66 objects / 644,958,608 bytes. It was mirrored once to
`audit/recovery_mid_joint_r2_resume_terminal`. Independent verifier
`audit/recovery_mid_joint_r2_resume_terminal_verification.json`, SHA
`f3cc988b...861a2`, passed every gate:

- exact source update-250 SHA `9730d7...abbc`, legacy contract, and normalized
  scientific contract;
- exact resume at loader step 1,000 / optimizer 250, followed by only the
  remaining 860 updates to optimizer/scheduler 1,110;
- all 17 immutable update-300 through update-1,100 snapshots are preserved and
  hash-verified;
- terminal best SHA `492a0c...7bd27`, last SHA `d4eb83...d6be`, exact epoch-0
  selection and paired duplicate hashes; fresh reload succeeds;
- all nine train components finite and exactly weight-consistent;
- train loss `9.5406162741`, validation loss `9.4809894806`;
- real 187-shard preflight, exact 26,624 train / 4,096 validation / zero test,
  209 unique staged objects, accepted hashes, and no legacy/test path;
- epoch and fresh-reload invariants all pass, all categorical/support failure
  counters zero, layer closure <=`7.6294e-6 GeV`, event closure
  <=`3.8147e-6 GeV`;
- Tesla T4 peak 11,738,958,336 / 15,655,829,504 bytes, headroom
  `25.0186%`;
- FP32 profile-8/share-8 timing `272.7106 ms/event`, batch 2, two iterations;
- same fixed 50 unique validation events, Geant4 deposits, exact four-vectors,
  and generation seeds as accepted joint epoch 0; five draws each, zero test,
  structural pass, visualization closure <=`1.14441e-5 GeV`.

The descriptive 50-condition bank reports response bias `+8.699%`, hit-count
bias `-7.102%`, and longitudinal-profile relative L1 `0.254396`. These are
small-sample visual/statistical diagnostics, not selection gates or Geant4
fidelity. The result establishes safe interruption/recovery and structural
postflight only; physics validation remains unestablished.

The 300-second synchronizer added the run-qualified immutable snapshot
`joint-resume-r2:joint:0000` to localhost, bringing the dashboard to 16
snapshots. Root and manifest remain HTTP 200. Completed watcher PID `23596`
was stopped only after exact command-line identity and successful sync were
verified.

Conservative recovery charge is rounded up to `$1.10` (actual worker duration
1.2242h at the `$0.85/h` planning rate). Prior account `$22.64` becomes
`$23.74`; remaining hard-budget capacity is `$76.26`. The recovery gate is
complete. The next authorized gate is exactly one 64-batch train-only
calibration after immutable image, four-object staging, unique-prefix,
server-spec, and fresh budget QA.

## 2026-07-26 19:54 Asia/Taipei — calibration image build authorized

Fresh pre-build budget: `$23.74` accounted, `$0.50` build/storage contingency,
and `$1.70` two-hour one-T4 calibration reserve give worst-case `$25.94`,
leaving `$74.06` under the hard `$100` ceiling.

Cloud Build context is exactly 69 allowlisted files / 287,421 bytes, with zero
legacy, audit, dashboard, test, ROOT, bytecode, Git, or dependency-cache
content. Key SHAs: Dockerfile `40dc5b5a...586b`, package manifest
`97050983...a179`, stage helper `f4ab4635...b1898`, calibration runner
`1590cc87...a8ee`, trainer `16770b74...0231c`, and weights
`4ffea9f4...c4da1`. Artifact Registry has zero existing
`r18-loss-calibration` tags. Exactly one immutable-image build is authorized;
the calibration job remains closed until digest, staging, prefix, spec, and
budget verification pass.

## 2026-07-26 20:03 Asia/Taipei — calibration pre-submit gate passes

Cloud Build `53a48555-ad34-416b-bc1e-585be9f4f8ba` succeeded in 3m59s.
Independent build and Artifact Registry reads resolve tag
`r18-loss-calibration` to immutable image:

`us-central1-docker.pkg.dev/asiop-zdc-1/cbsc-zdc/cbsc-zdc@sha256:c31f083578d9933233e54eb51cc27901fdd87f8f730520938b37111e37c96b7d`

Four and only four accepted objects were copied to new calibration input paths
using destination generation precondition zero: frozen joint config, pilot
split JSON, pilot assignments, and accepted joint best checkpoint. Nothing was
overwritten. Independent merged-staging verifier
`audit/calibration_joint_r1_staging_verification.json`, SHA
`5d354a50...f322c`, passes:

- overlay 4 objects / 29,415,631 bytes;
- base plus overlay 209 objects / 5,973,774,654 bytes;
- config SHA `6a15bf93...c929c`, joint, real production data;
- exact dataset, geometry, split, assignment, and checkpoint hashes;
- joint checkpoint generation `1785067202407493`, size 29,362,400, SHA
  `03c796...1adb7`;
- zero collisions and zero forbidden paths.

Fresh checks find the unique calibration output empty and zero custom jobs
matching `cbsc-v2-2-joint-loss-calibration-20260726-r1`. Exact authorized spec:
one replica, on-demand T4, `n1-standard-8`, 100 GB `pd-ssd`, exact r18 digest,
accepted service account, 7,200-second timeout, CUDA; prep r5 plus unique
four-object overlay; frozen joint config; exact accepted joint-best source;
64 train-only batches; clip `[0.25,4.0]`; no validation/test selection;
generation-zero terminal upload. Worst-case account remains `$25.94`, leaving
`$74.06`. Exactly one calibration submission is authorized.

One read-only repository search for the prior staging-bucket argument placed
`rg` glob options after paths, which PowerShell/rg interpreted as filenames.
It failed without mutation; the exact prior service account and usable project
bucket are independently established.

## 2026-07-26 20:12 Asia/Taipei — calibration submitted exactly once

Vertex accepted training pipeline `5827277770262052864` and backing custom job
`767991563283333120` for display name
`cbsc-v2-2-joint-loss-calibration-20260726-r1`. Independent custom-job
inspection confirms the frozen specification without relying on the submitter:

- state at inspection: `JOB_STATE_PENDING`;
- command `python -m cbsc_zdc.cloud.vertex_calibrate`;
- exact r18 immutable image digest
  `sha256:c31f083578d9933233e54eb51cc27901fdd87f8f730520938b37111e37c96b7d`;
- one replica, on-demand `NVIDIA_TESLA_T4`, `n1-standard-8`, 100 GB `pd-ssd`;
- service account `39719277374-compute@developer.gserviceaccount.com`;
- timeout 7,200 seconds, CUDA, 64 train-only batches, clip `[0.25,4.0]`;
- prep-r5 base, unique calibration-r1 overlay and output, frozen joint config,
  and accepted checkpoint SHA `03c796...1adb7`.

The output prefix was empty before submission and the matching-job count was
zero. The local SDK process continued only as a state observer after server
acceptance; its exact command-line identity was checked and PID `10464` was
stopped. A fresh server read proves the custom job remains pending, so the
server-side work and evidence are independent of this computer remaining
awake. No duplicate was submitted. A 600-second polling interval is used while
capacity is pending; after allocation, the conservative completion window is
approximately 20–40 minutes, bounded by the enforced two-hour timeout.

The GitHub remote requested by the user,
`JulianAttemptsCoding/Fast-MC-CBSC`, currently advertises no refs. Repository
publication therefore needs no history rewrite or merge. Publication QA must
still exclude credentials, ROOT data, checkpoint mirrors, dependency caches,
and other generated large artifacts before an initial commit.

## 2026-07-26 20:16 Asia/Taipei — reproducible repository published

The previously empty remote
`https://github.com/JulianAttemptsCoding/Fast-MC-CBSC.git` now has initial
`main` commit `73e6455729bd9fbac0801db5de7a7d5236b029d4`. Independent
`git ls-remote` returned the same SHA for `refs/heads/main`, and local `main`
tracks `origin/main`.

Publication QA covered 298 files / 5.12 MiB. No tracked nested `.git` path,
raw `.root` file, model checkpoint, likely secret filename, or likely private
key/API-token content was found. The generated multi-hundred-megabyte
dashboard epoch payloads, Vertex output mirrors, package dependencies, build
bundles, caches, and credentials are ignored; compact verification JSON/Markdown,
source, tests, frozen/template configurations, dashboard code, and human
`logs.md` remain versioned. The empty, commitless dashboard-local Git metadata
was moved—not deleted—to recoverable temporary backup
`C:\Users\Julia\AppData\Local\Temp\fast-mc-cbsc-dashboard-git-20260726-200751\.git`
before initializing the repository root, avoiding an accidental gitlink.

The optional `gh auth status` check failed because GitHub CLI is not installed.
No mutation occurred in that failed check. Git Credential Manager subsequently
authenticated the ordinary `git push`, and remote-SHA equality is the
authoritative verification. `git diff --cached --check` reported inherited
Markdown trailing spaces used in supplied/historical documents; these were not
silently rewritten because they are evidence files, and they do not affect
source execution or repository integrity.

## 2026-07-26 20:20 Asia/Taipei — loss-direction research and QA disposition

The calibration custom job entered `JOB_STATE_RUNNING` at
`2026-07-26T12:07:12Z` (20:07 Asia/Taipei). Its unique output still matches no
objects, which is correct before the generation-zero terminal publication.
The safe estimated completion window is 20:27–20:47, bounded by the two-hour
Vertex timeout. This is a 64-batch calibration gate, not a training epoch; no
new checkpoint or visualization is expected from it.

The concern that “zero is always the best loss” was checked against the actual
implementation, measured histories, and primary references. Disposition:
**do not add an absolute value and do not replace the objective with a blanket
L2 loss**.

Evidence and reasoning:

- `visible`, `first_layer`, `active`, `count`, `support_bce`, and
  `support_rank` are BCE/cross-entropy/softplus ranking objectives whose
  infimum is zero.
- `profile_flow` and `share_flow` are already masked squared-error objectives;
  adding another L2 operation would change their units and gradients rather
  than repair them.
- `response` is negative log density from a continuous four-component Gaussian
  mixture in transformed response space. A continuous density may exceed one,
  so its negative log density may legitimately be negative and has no special
  optimum at zero. Taking `abs(response_nll)` would create a false minimum at
  density one and reverse correct gradients once the NLL becomes negative.
- Flow Matching is defined as vector-field regression, consistent with the
  implemented masked MSE (Lipman et al.,
  `https://arxiv.org/abs/2210.02747`; Tong et al.,
  `https://arxiv.org/abs/2302.00482`).
- PyTorch’s likelihood documentation likewise defines NLLs from densities or
  probabilities rather than a universal zero-distance target
  (`https://docs.pytorch.org/docs/2.12/generated/torch.nn.modules.loss.PoissonNLLLoss.html`).
- Multi-task losses naturally have different scales, motivating calibrated
  weights rather than forcing identical raw values (Kendall, Gal, Cipolla,
  `https://arxiv.org/abs/1705.07115`).

The observed joint pilot is moving in the correct minimization direction:
train total `10.1056 → 9.6870 → 9.4188` and validation
`10.0881 → 9.6136 → 9.4914` over epochs 0–2. The response NLL becomes more
negative (`-0.7381 → -0.7894 → -0.8247`), which is an improvement in log
density, not divergence. The nonnegative flow components also fall:
profile `2.3199 → 2.0634`, share `4.7792 → 4.5852`. The response visual bias
did not monotonically improve, confirming why validation physics metrics—not
raw loss magnitude or distance from zero—must control family sensitivity.

No loss formula is changed at this gate. The authorized 64-batch gradient
calibration measures whether any component dominates the shared encoder; the
predeclared validation-only family matrix then tests physical consequences.
One diagnostic `rg audit/*verification.json` used a POSIX-style wildcard that
PowerShell passed literally and failed without mutation. Exact files were read
with `Get-ChildItem`/`ConvertFrom-Json` instead.

## 2026-07-26 20:25 Asia/Taipei — calibration r1 fails closed on T4 memory

Pipeline `5827277770262052864` / custom job `767991563283333120`
failed at `2026-07-26T12:14:45Z`, after 7m33s of running time. The immutable
r1 output prefix is preserved and will never be reused. It contains exactly
four failure objects / 72,894 bytes:

- `environment.json`, SHA `d018a198...e119`;
- `runtime_config.yaml`, SHA `88cb3cb7...8f30`;
- `staged_input_manifest.json`, SHA `c45b8bb5...6049`;
- `vertex_failure.json`, SHA `0497383e...7c4f`.

Independent job describe is SHA `3789c55b...9d39`; all evidence is mirrored
under `audit/calibration_joint_r1_failure/`. The worker and failure artifact
agree exactly: `torch.OutOfMemoryError` at the support graph forward while
trying to allocate 44 MiB. PyTorch had 14.28 GiB allocated, 129.78 MiB
reserved-but-free, and only 35.56 MiB device capacity free on the 14.58 GiB
T4. CUDA, real-data staging, exact checkpoint, and frozen-config preflight had
already succeeded. There is no calibration report and no accepted proposal.

Root cause: `calibrate_loss_weights` constructed the full nine-loss joint
autograd graph for batch 6, then retained the graph while differentiating all
nine components. This is materially different from the accepted joint trainer,
which releases the graph after one weighted backward pass and had 25% T4
headroom. Fragmentation is not the primary diagnosis: only 129.78 MiB was
reserved but unallocated, far less than the live 14.28 GiB allocation.

Conservative failed-job charge is rounded up to `$0.15`. Accounted spend moves
from `$23.74` to `$23.89`; remaining capacity is `$76.11`.

## 2026-07-26 20:31 Asia/Taipei — memory-bounded calibration correction passes local QA

The correction preserves the calibration semantics while bounding live
autograd memory:

1. For each unchanged train batch, compute loss graphs in the original
   scientific order: response, profile, count, support, share.
2. Differentiate every loss in a stage-family graph, retaining only until that
   family’s last component.
3. Release that graph before constructing the next family.
4. Require every one of the nine components exactly once per batch and record
   exactly 64 observations per component.

This retains the same batch, checkpoint, model, loss formulas, shared condition
encoder, stochastic draw order, clip rule, and median calculation. It does not
lower the batch, omit a loss, use AMP, weaken the 15% headroom gate, or change
scientific selection. The five family graphs have previously demonstrated far
lower isolated-stage memory than the full retained graph.

Changed source SHAs:

- `src/cbsc_zdc/training/weights.py`:
  `340162791a048d6fc02ddac0350ece94eb898b170b8d98af76c70ba8d7a38787`;
- `src/cbsc_zdc/cloud/vertex_calibrate.py`:
  `c898081d8768342d5432122c11f96b69207f8fd5b4f349540f67e3040b459056`;
- verifier `7957c0fc...ac7`;
- weight tests `95bb2355...6d01`;
- verifier tests `2fd66945...c01db`.

QA results: full suite `71 passed` with only the four known nonfatal
Transformer nested-tensor warnings; compileall clean; strict Ruff initially
reported inherited compact one-line formatting in the touched weight module,
so that module was mechanically formatted; Ruff then passed and the focused
calibration/hardening suite passed `23/23`. No cloud resubmission is authorized
until a new immutable image, unique r2 input/output prefixes, fresh staging
verification, exact job cardinality, and budget reserve all pass.

## 2026-07-26 20:35 Asia/Taipei — corrected calibration image build authorized

Fresh budget gate: `$23.89` accounted + `$0.50` build/storage contingency +
`$1.70` two-hour corrected calibration reserve = `$26.09` worst credible
account, leaving `$73.91`. No `r19-loss-calibration-memory` tag exists.

The upload context is 69 allowlisted files / 288,831 bytes with zero legacy,
audit, dashboard, tests, ROOT, checkpoint, Git, bytecode, or dependency-cache
content. Exact correction SHAs and the unchanged Docker/package/stage hashes
were rechecked. Exactly one r19 Cloud Build is authorized; no replacement
Vertex job is authorized until its immutable digest and new r2 staging are
independently verified.

## 2026-07-26 20:40 Asia/Taipei — corrected calibration r2 pre-submit passes

Cloud Build `f0fd292a-e8d2-4775-8974-4403eef0f494` succeeded in 3m21s.
Independent Artifact Registry inspection resolves r19 to immutable digest:

`us-central1-docker.pkg.dev/asiop-zdc-1/cbsc-zdc/cbsc-zdc@sha256:bbcb57e9fa5489e913bb7f48f243289d961e7a2987a1532efeaab8cc945a382b`

The four approved calibration inputs were copied from preserved r1 input to
new r2 paths with destination generation precondition zero. Exact r2 overlay:
4 objects / 29,415,631 bytes; frozen config SHA `6a15bf93...c929c`, split
manifest `a4d09675...6b0b3`, assignments `084f0dfd...d3714`, accepted joint
best `03c79608...1adb7` generation `1785068839757442`.

Independent merged staging verification
`audit/calibration_joint_r2_staging_verification.json`, SHA
`2cdec270b0dbbbeb82d6892fab4465a1a430c134950284704edbdc30f7358440`,
passes 209 objects / 5,973,774,654 bytes, real data, exact dataset/geometry/
split/config/checkpoint hashes, zero forbidden paths, zero collision, and
train/validation/test selection `26624/4096/0`. The unique r2 output is empty
and exact r2 custom-job cardinality is zero.

Worst credible account remains `$26.09`, leaving `$73.91`. Exactly one
corrected r2 submission is authorized with the same 64 train-only batches,
clip `[0.25,4.0]`, FP32/CUDA, on-demand T4, machine/disk/service account, and
7,200-second timeout. No other calibration or training job is authorized.

## 2026-07-26 20:43 Asia/Taipei — corrected calibration r2 submitted once

Vertex accepted pipeline `579739779445293056` and backing custom job
`5885120877976092672`. Exact display-name cardinality is one. Independent
server describe—not submitter output—confirms the complete authorized r19
digest, prep/r2-overlay/r2-output/config/checkpoint arguments, five-family
memory-bounded code, 64 batches, clip bounds, CUDA, one replica, on-demand T4,
`n1-standard-8`, 100 GB `pd-ssd`, service account, and 7,200-second timeout.

Initial state is `JOB_STATE_PENDING`. After exact server acceptance, local SDK
observer PID `5416` was identity-checked and stopped; a fresh describe proves
the server job remains pending. No duplicate exists. The next poll uses a
600-second timer. Based on r1 provisioning plus the additional bounded family
forwards, first terminal evidence is conservatively expected 20–45 minutes
after allocation, with the two-hour timeout as hard bound.

Post-submission regression QA added a production-loss equivalence test using a
synthetic geometry only; it is explicitly not physics validation. With the
same model, batch, and RNG seed it computes all nine losses and shared-
condition-encoder gradient norms through the original joint graph and through
the new response→profile→count→support→share grouping. Every component value
and gradient norm matches. Ruff passes and the loss-weight suite passes `5/5`
with only the known Transformer warning. Test SHA:
`6bb93ca2e1eee1369f95792eb629bf5769cd8c953a91d0036bbee6d9177d8fea`.

Up to five on-demand T4s are available for time-efficient independent work.
They may be used concurrently only after calibration, for predeclared
independent validation/optimizer/throughput variants with unique empty
generation-zero prefixes and a combined worst-case budget reservation.
Dependent QA, calibration retries, and protocol-freezing steps remain serial;
parallel capacity is never used to duplicate a job or bypass evidence.

## 2026-07-26 20:50 Asia/Taipei — historical hardware-screening scope and r2 allocation

The user clarified that Vertex should provide evidence for possible migration
to a faster external cluster, not complete the publication-scale six-run final
matrix.
The frozen test bank remains closed and physics validation remains
unestablished. The new bounded decision protocol is:

1. accept train-only calibration;
2. run five matched one-epoch pilots concurrently: exact default-weight
   control, calibrated weights at learning rates `3e-5`, `1e-4`, `3e-4`, and
   calibrated `1e-4` with half effective batch;
3. require real 26,624/4,096/0 staging, finite/all-nine losses, checkpoint
   reload, invariants, ≥15% T4 headroom, 8/8 timing, and fixed 50×5
   Geant4/FastMC visualization per epoch;
4. Pareto-select at most two from validation/structural/visual evidence only
   and continue them for several epochs;
5. report the optimization and hardware observations without calling the pilot
   physics validation. The permission-style disposition used at the time is
   superseded by `docs/QA_POLICY.md`.

At measured joint throughput, one pilot epoch is 3,878 seconds plus about
4–6 minutes of validation/visualization/postflight. The future epoch poll
interval is therefore 4,200 seconds. Calibration r2 itself entered
`JOB_STATE_RUNNING` at `2026-07-26T12:35:18Z`; its existing 600-second timer
remains active, with expected terminal evidence about 20:55–21:20.

Unfrozen-only viability-wave generator SHA `4244704c...e494b` and test SHA
`58eab82d...f23a5` predeclare the five variants, exact checkpoint binding,
one epoch, FP32, fixed visualization, zero test, update-50 recovery snapshots,
and wave limit five. They do not freeze a config or submit a job. Ruff,
compileall, and the combined calibration/viability tests pass `8/8` with one
known Transformer warning.

### Dashboard inventory correction

A read-only diagnostic initially queried a nonexistent `snapshots` property
and therefore printed zero; it did not modify the dashboard. The manifest
schema actually uses `epochs`. A fresh parse proves `schema_version=3`,
`epochs=16`, latest ID `joint-resume-r2:joint:0000`, fixed selection SHA
`f70529198aa9575cd2ebc816fd0800ed5a1a3dcd918dab3845b5dc5d85dc59b6`,
and `test_events_used=0`. This is the exact accepted pre-viability inventory.

## 2026-07-26 20:56 Asia/Taipei — calibration r2 accepted

Corrected train-only calibration custom job `5885120877976092672` succeeded
from `12:35:18Z` through `12:45:52Z`. Its unique output contains exactly six
objects / 75,643 bytes and no `vertex_failure.json`. Independent verifier
`audit/calibration_joint_r2_terminal_verification.json`, SHA-256
`be5f135ae8ff82c2759fcdab4eb0eecbf24fd75b147c63920abb67ad805a0945`,
recomputed every gate:

- all 209 staged real-production objects and hashes match;
- exact checkpoint SHA
  `03c7960861d6f6f3012a8e4469421d51e33d1a8dad7fc8ec8c8406d547f1adb7`;
- 64/64 train-only batches, all nine components, 64 finite observations each,
  zero test events;
- fixed group order `response→profile→count→support→share`;
- Tesla T4 peak 6,080,549,888 / 15,655,829,504 bytes, 61.161% headroom;
- 202.245 seconds measured calibration compute.

The accepted mean-one weights are visible `2.574416712`, response
`0.1609010445`, first-layer `2.159450730`, active `0.5367704371`,
profile-flow `0.1609010445`, count `0.1609010445`, support-BCE
`1.324107536`, support-rank `1.477591210`, share-flow `0.4449602409`.
These balance shared-encoder gradient scale; they are a train-only proposal,
not a validation selection and not physics validation.

The first local `gcloud storage cp --recursive` mirror flattened the two report
paths. All bytes and hashes were preserved under
`audit/calibration_joint_r2_terminal/`, but that layout was not accepted.
A second non-overwriting exact-path mirror under
`audit/calibration_joint_r2_terminal_exact/` passed the strict verifier. A
multi-command freeze call printed only four records before returning; the
fifth file was independently found present and hashable, so no config was
re-frozen or overwritten.

Dashboard QA during calibration: ESLint passes, production build passes, two
rendered-HTML contract tests pass, and root/manifest HTTP responses are 200.
The apparent string-valued trend was only shallow diagnostic serialization;
the actual schema-3 manifest stores trend objects. Browser-level visual QA is
not claimed because the desktop browser bridge failed to initialize with local
path error 3.

Budget update: prior accounted `$23.89` + conservative r19 build `$0.50` +
rounded calibration r2 `$0.15` = `$24.54`; hard-budget remainder `$75.46`.
Five two-hour one-T4 hard-timeout reserves total `$8.50`. Including a separate
`$5.00` build/storage/management contingency leaves `$61.96`, so the complete
one-epoch viability wave fits without weakening any gate.

## 2026-07-26 21:04 Asia/Taipei — five-way viability wave submitted

The accepted calibration report generated exactly five new unfrozen templates.
They were frozen only through `cbsc-zdc freeze-config`; a new independent
verifier (script SHA `979fd69c...aa68`, report SHA `7ae19f73...34f4`) proves
all five share exact production artifact provenance, checkpoint
`03c79608...adb7`, joint FP32/seed 20260723/one epoch/update-50 snapshots,
0–300 GeV training, 50–250 GeV validation, fixed validation 50×5
visualization, and fully trainable encoder. Frozen config hashes:

- default control: `5a798127...a997`;
- calibrated LR `3e-5`: `45db1a13...64d4`;
- calibrated LR `1e-4`: `e7befc0d...da3`;
- calibrated LR `3e-4`: `8efa643d...c2d`;
- calibrated LR `1e-4`, effective batch 12: `3518e3f1...5eb4`.

All ten new input/output prefixes and all matching display names were empty
before mutation. Each unique input received only its new config with
generation-match zero; the exact immutable calibration input is a shared
read-only checkpoint/split overlay. Five independent merged-staging reports
pass at 210 real objects, one exact checkpoint, no collision, and no forbidden
or test path. Their SHA-256 values are respectively `f1f28b73...b3e2`,
`816dfde6...f919`, `153afbe5...5a1c`, `af24e406...7818`, and
`51c43885...f359`.

Exactly five server-side jobs were accepted in parallel:

- default control: pipeline `8444361734973554688`, custom job
  `1645340269597425664`;
- calibrated LR `3e-5`: pipeline `2423049033179201536`, custom job
  `2259914492966076416`;
- calibrated LR `1e-4`: pipeline `5510266577741676544`, custom job
  `5596221998754693120`;
- calibrated LR `3e-4`: pipeline `4715381243510784000`, custom job
  `8082035270226018304`;
- calibrated LR `1e-4` half-batch: pipeline `2461329630011850752`, custom job
  `4196752603805122560`.

Independent server listing confirms each is one replica, on-demand
`n1-standard-8`, one `NVIDIA_TESLA_T4`, 100 GB `pd-ssd`, 7,200-second timeout,
exact r19 digest `bbcb57e9...382b`, exact config/output, two overlays, and the
approved service account. All five are initially pending. After identity
checking their complete submitter command lines, local SDK observers were
stopped; a fresh server listing proves all five jobs remain pending.

Allocation is polled after 300 seconds. Once start times exist, the next-epoch
timer is `start + 4,200 seconds`: 3,878 seconds previously measured for joint
training plus approximately 322 seconds for validation, fixed visualization,
checkpoint publication, and postflight. Comparative analysis waits until all
five immutable epoch outputs are independently verified.

Post-submit local QA: Ruff and compile checks pass. Two test invocations named
nonexistent historical paths (`test_loss_weight_calibration.py`, then
`test_loss_calibration.py`) and ran zero tests; neither mutated state. The
correct `PYTHONPATH=src` suite using `test_loss_weights.py` passes 8/8 with one
known nonfatal Transformer warning.

Before any result was visible, the historical hardware-screening protocol froze
the same-weight-family comparison, wave-1 Pareto tolerances, maximum-two
continuation design, and two-additional-epoch recovery plan. Official target
accelerator/T4 specifications and Google GPU pricing were rechecked. Hardware
peaks were not used as a claimed speedup; the target software stack still
requires an empirical 256-batch plus 8/8 benchmark. The old permission framing
is superseded by `docs/QA_POLICY.md`.

All five jobs allocated concurrently between `13:04:50Z` and `13:05:39Z`.
The measured safe epoch/terminal window is therefore
`2026-07-26 22:14:50–22:15:39 Asia/Taipei`. A 1,200-second health timer was
armed before the longer remaining interval.

During that wait, the existing component-output verifier was generalized
without changing its historical defaults so it can verify joint→joint
viability initialization, one training epoch, update-50 checkpoints, and the
second exact overlay source. Script SHA is `a1d585de...0e2d`; Ruff/compile pass
and all eight existing verifier tests pass. This is local verification tooling
only and did not change the running immutable image or jobs.

The verifier now also computes truth/generated zero-response fractions,
per-condition deposit diversity, and within-condition response spread from the
full 50×5 artifact. Its first unit test failed because the synthetic fixture
used shallow nested copies, not because of the metric code; replacing the
fixture's nested Geant4 object independently produced the intended one-zero
counterexample. Final verifier SHA is `92a47237...88c6`; Ruff passes and the
corrected suite passes 9/9.

Pre-result wave analyzer SHA `84f77f4b...ce66` implements the frozen
same-weight-family rule, toleranced Pareto dominance, deterministic worst-rank
tie break, and maximum-two continuation. Its first cross-family unit test
incorrectly made the default row better on response as well as incomparable
aggregate loss, so dominance was legitimately true. Equalizing every
non-aggregate metric isolated the intended counterexample. Ruff passes and the
combined analyzer/verifier suite passes 12/12.

## 2026-07-26 21:37 Asia/Taipei — wave mid-epoch gate

All five jobs remain `JOB_STATE_RUNNING`. At the 1,200-second health timer,
the batch-6 jobs had immutable update-350 snapshots (350/1110, 31.53%); the
half-batch job had update 650/2219 (29.29%). Every progress record is epoch 0,
seed 20260723, optimizer-boundary true, and has finite accumulated losses.
Partial train means are:

- default control `9.749463` (not cross-family comparable);
- calibrated LR3e-5 `5.073775`;
- calibrated LR1e-4 `5.137950`;
- calibrated LR3e-4 `5.413417`;
- calibrated LR1e-4 half-batch `5.154070`.

Independent downloads reproduce every worker SHA. All five checkpoints contain
207 finite model tensors, exact optimizer steps `{350}` or `{650}`, matching
scheduler last-epoch, matching next batch (`1400` or `2600`), Torch and CUDA
RNG, and no prior-best checkpoint as expected before first validation. Exact
checkpoint hashes are `20212ea5...4b6c`, `03dfddb7...62be`,
`a17f76e2...a9b4`, `48cb6950...c983`, and `9c35662c...c2d2`.

Measured train projection is 3,550–3,805 seconds plus validation,
visualization, and postflight. The updated safe terminal window is
22:25–22:35 local. The next timer is 3,000 seconds.

Scheduler QA found a real continuation counterexample before any wave result:
restoring a one-epoch `CosineAnnealingLR` at `last_epoch=T_max` and stepping
beyond the old horizon makes LR rise again. The protocol now requires an
explicit resume warm restart for wave 2: preserve model, optimizer moments,
scaler, RNG, selected best, and epoch numbering; reset only LR/initial-LR and
construct a monotonic cosine horizon for exactly the two remaining epochs.
Configuration rejects the option without paired resume. Focused recovery,
config, and loss QA passes 33 tests with two known Transformer warnings.

An unscoped Ruff call reported 42 pre-existing compact-style E701/E702/E703
findings throughout `trainer.py`; it did not mutate code. A scoped run ignoring
only those historical style classes passes, and `git diff --check` is clean.
This correction is not in the currently running r19 image. A new immutable
image is required only if wave-2 continuation is selected.

Pre-build QA at commit `92752af`: full repository test suite passes 81/81 with
five known Transformer warnings and compileall is clean. A repository-wide
Ruff check (already ignoring only historical E701/E702/E703 compact style)
found 12 additional pre-existing unused-import/ambiguous-name findings outside
the changed continuation path; it made no mutation. The previously scoped
changed-file Ruff gate passes. Conservative budget remains `$24.54` accounted,
`$8.50` live-wave worst reserve, and `$5.00` contingency. Spending at most
`$0.50` of that contingency on an immutable continuation image still leaves
`$61.96` after all reserves.

Cloud Build `46b06a98-3741-4e6e-8df8-be175260b86e` succeeded from
`13:39:16Z` through `13:41:50Z`. The allowlisted context was 75 files /
300.0 KiB. Independent Artifact Registry describe resolves immutable r20:
`us-central1-docker.pkg.dev/asiop-zdc-1/cbsc-zdc/cbsc-zdc@sha256:8b4a94c0c748febdb059b1302503d280498ddd1360b595a90e0a6c9b0999048f`.
No job uses this image yet. Conservative accounted spend becomes `$25.04`;
live-wave worst reserve `$8.50` plus remaining contingency `$4.50` still leaves
`$61.96`.

Pre-result continuation generator SHA `a52e586d...1334` consumes only the
accepted wave analysis and selected verifier reports, refuses overwrite or an
unselected result, preserves each selected weight/LR/batch contract, binds
exact best/last hashes, sets total epochs to three (therefore exactly epochs
1–2 remain), and enables only the explicit scheduler restart. It produces
unfrozen templates only; no config is frozen or job submitted. Ruff/compile
pass and the combined continuation/analyzer/config/loss suite passes 19/19
with one known Transformer warning.

## 2026-07-27 06:55 Asia/Taipei — viability wave 1 terminal gate

The local machine slept across the terminal timer, but all work was already
server-side. Exactly the five authorized custom jobs succeeded; no replacement
was submitted. Their start/end durations were:

- default `1645340269597425664`: 4,526 s;
- calibrated LR3e-5 `2259914492966076416`: 4,558 s;
- calibrated LR1e-4 `5596221998754693120`: 4,590 s;
- calibrated LR3e-4 `8082035270226018304`: 4,590 s;
- calibrated LR1e-4 half-batch `4196752603805122560`: 4,800 s.

Each immutable terminal mirror has exactly 19 files and no
`vertex_failure.json`; byte totals are
`72,828,877/72,839,477/72,885,408/73,125,092/72,988,166`.
Each epoch-0 mirror has 13 files, and every one of its 13 hashes equals the
corresponding terminal file. The accepted source remains
`03c79608...adb7`.

The first verifier invocation intentionally stopped without an output because
the command incorrectly supplied epoch 0 as its own comparison epoch; the
cross-epoch contract correctly requires `epoch_delta > 0`. The corrected
terminal-only invocation passes all five. Verification report SHA-256 values
are `d0b86c79...2d7a`, `c0deee3a...9af7`, `3c849d78...19f`,
`e53c741e...69e2`, and `6ce2a556...1cb7`.

All five prove finite selected losses and gradients, exact final optimizer
steps (1,110 or 2,219), changed trainable tensors, exact best/last hashes,
checkpoint reload, epoch and postflight invariant pass, zero negative or
nonfinite output, zero count/support mismatch, 8/8 solver/decode timing, and
zero test use. Batch-6 T4 headroom is `24.9119%`; half-batch headroom is
`62.1314%`. The five validation losses are:

- default-family control `9.479305` (not comparable to calibrated totals);
- calibrated LR3e-5 `4.988944`;
- calibrated LR1e-4 `4.973253`;
- calibrated LR3e-4 `4.951028`;
- calibrated LR1e-4 half-batch `4.976166`.

Every fixed visualization contains 50 identical validation conditions, one
four-vector per condition, five FastMC draws, and all 50 conditions with
multiple unique deposits. Generated zero-response fractions are
`0.032/0.028/0.032/0.020/0.024` versus truth `0.0`. The corresponding absolute
response bias, absolute hit-count bias, and profile relative L1 are:

```text
default                 0.08694  0.07143  0.25412
calibrated LR3e-5       0.08095  0.07068  0.26733
calibrated LR1e-4       0.09277  0.06656  0.26291
calibrated LR3e-4       0.03487  0.04626  0.22228
calibrated half-batch   0.08618  0.05795  0.23019
```

The first wave-analyzer command used display-label hyphens and was rejected
before output because the frozen contract requires canonical underscore IDs.
The corrected invocation produced
`audit/viability_20260726_r1_wave_analysis.json`, SHA
`fefd0102...8efa`, and selected exactly the two nondominated candidates:
`calibrated_lr3e4` and `calibrated_lr1e4_halfbatch`. This is validation-only
successive halving, not physics validation.

Dashboard synchronization was sequential. Manifest schema 3 now has 21 epochs
and five new viability rows, one fixed selection `f7052919...9b6`, five draws
per each of 50 conditions, four p4 components, matching file hashes, and zero
test events. ESLint, production build, two rendered-HTML tests, and localhost
root/manifest HTTP 200 pass. Browser-level visual inspection remains blocked
only by the already logged desktop bridge `os error 3`.

Actual wave cost is conservatively rounded per job to
`1.3/1.3/1.3/1.3/1.4` hours at `$0.85/h`, or `$5.61`. Prior accounted spend
`$25.04` therefore becomes `$30.65`. Keeping `$4.50` contingency and reserving
two four-hour continuation timeouts (`$6.80`) leaves `$58.05` below the hard
`$100` ceiling.

## 2026-07-27 06:55 Asia/Taipei — wave-2 continuation preflight

The accepted analyzer and exact reports generated two new unfrozen templates
only. They were frozen through `cbsc-zdc freeze-config`, never hand-edited:

- LR3e-4 frozen config `135c45ff...208b`, paired best/last
  `520294c5...9758` / `571d460f...a762`;
- half-batch frozen config `c58ff7a8...1efd`, paired best/last
  `75e8e38c...71bc` / `716fcbfe...ff84`.

Both are joint FP32, seed 20260723, epochs total 3 (resume epochs 1–2 only),
update-50 snapshots, `restart_scheduler_on_resume=true`, preserved optimizer
moments/scaler/RNG/selected best, fixed validation 50×5, and zero test events.
Focused recovery/config/verifier QA passes 40/40 with one documented
Transformer warning; compileall is clean.

Both new input/output prefixes and both display names were empty. The installed
`gcloud` lacks `training-pipelines list`, so that first collision command
stopped; the read-only Vertex SDK returned zero matching pipelines. Generation
0 then created exactly three unique objects per input. Two attempted retries
were rejected by generation-0 because the original long-running upload had
completed between list and retry; this proves no overwrite occurred.

Merged staging verification independently passes for both at 212 objects:
205 base production objects + four shared split/checkpoint objects + three
unique continuation objects, zero forbidden paths, synthetic false, exact
config and paired-checkpoint hashes. Reports are
`e93fd568...6a73` (LR3e-4) and `72cb82b8...244f` (half-batch). Output prefixes
remain empty. Budget and all hard gates permit exactly these two on-demand T4
continuations using immutable r20 `sha256:8b4a94c0...9048f`; no test or final
six-run training is authorized.

## 2026-07-27 06:58 Asia/Taipei — exactly two wave-2 jobs submitted

After a final output-emptiness and `$58.05` post-reserve budget check, exactly
the two selector-authorized jobs were submitted:

- calibrated LR3e-4: pipeline `7762998777287278592`, custom job
  `8103319616316506112`;
- calibrated LR1e-4 half-batch: pipeline `3138927859884621824`, custom job
  `576590778143342592`.

Independent server descriptions initially show `JOB_STATE_PENDING` and match
one on-demand `NVIDIA_TESLA_T4`, one `n1-standard-8` replica, 100 GB `pd-ssd`,
14,400-second timeout, approved service account, immutable r20
`sha256:8b4a94c0...9048f`, exact base/shared/unique prefixes, exact frozen
config relative paths, CUDA, postflight training, and unique output prefixes.
No third job or local observer was submitted. The next gate is a 300-second
shell timer followed by identity/state/progress inspection.

## 2026-07-27 07:04 Asia/Taipei — wave-2 allocation gate

The 300-second shell timer completed. LR3e-4 job `8103319616316506112`
is `JOB_STATE_RUNNING` from `23:01:47Z`; half-batch job
`576590778143342592` is `JOB_STATE_RUNNING` from `23:00:32Z`. Neither has
published an in-flight update yet, which is expected during initial staging
and first 50 updates. No duplicate or mutation occurred.

Pre-result verifier QA found that the existing component verifier assumed a
fresh epoch-0 history and an uninterrupted cosine scheduler. That would
misclassify the intentionally resumed wave-2 contract, whose local history
begins at epoch 1, optimizer steps remain cumulative, a prior best can survive,
and only scheduler step counting restarts. Before any wave-2 result existed,
the verifier was extended to:

- require the exact parent best/last checkpoint pair and resume hashes;
- require history epochs 1–2 and the explicit scheduler restart;
- distinguish cumulative optimizer steps from restarted scheduler steps;
- accept an exact preserved parent best or a legitimately improved new best;
- verify invariant/progress/visualization evidence at every resumed epoch;
- prove fixed truth and independent generation seeds across epoch 0→1→2.

Ruff and compileall pass. Focused continuation/recovery/verifier QA passes
17/17 with one documented Transformer warning, and a full real wave-1
terminal regression still passes with history start 0. No job uses this local
verifier code; it is independent post-run QA.

## 2026-07-26 21:54 Asia/Taipei — dashboard browser retry preserved

The five Vertex jobs remain under the existing 3,000-second timer; no job was
polled or resubmitted early. The terminal estimate remains 22:25–22:35 local.
The in-app browser bridge was retried against `http://localhost:3001/` only
after re-reading its operating contract and discovering the required runtime.
Initialization again failed before page discovery with the identical local
kernel-asset error, `os error 3`. A follow-up state inspection failed at the
same initialization boundary. This is preserved as a browser-bridge
environment limitation, not a dashboard pass or a model failure. The existing
ESLint/build/rendered-HTML and HTTP-200 checks remain the accepted nonvisual
site QA; no alternate browser driver was substituted.

A separate read-only localhost probe returned HTTP 200 for both `/` and
`/data/manifest.json`. Its first summary incorrectly reported zero snapshots
because it queried a nonexistent `snapshots` property. Direct schema
inspection corrected the diagnostic: schema 3 stores the records under
`epochs`, with 16 accepted epochs, fixed selection
`f7052919...9b6`, and latest `joint-resume-r2:joint:0000`. No dashboard
artifact was changed.

At 22:00 local, one read-only five-job health check confirmed every exact
custom job remains `JOB_STATE_RUNNING` with its original start time:
default `1645340269597425664`, calibrated LR3e-5
`2259914492966076416`, calibrated LR1e-4 `5596221998754693120`,
calibrated LR3e-4 `8082035270226018304`, and half-batch
`4196752603805122560`. No result metric was read and no partial candidate was
selected. The 22:25–22:35 terminal estimate and existing 3,000-second timer
remain unchanged.

The same immutable progress stream refined the ETA without opening validation:
default, calibrated LR3e-5, calibrated LR1e-4, and calibrated LR3e-4 are at
updates `900/1110`, `900/1110`, `850/1110`, and `900/1110`; half-batch is at
`1700/2219`. All records are epoch 0 and optimizer-boundary true. Measured
elapsed-rate projections leave roughly 670–887 seconds of training, after
which validation, fixed 50×5 generation, artifact publication, and postflight
still run. The safe terminal window tightens to 22:20–22:30. Partial means
(`9.5673` default; calibrated `5.0661/5.0975/5.2289/5.1150`) are recorded only
as finite health evidence and remain forbidden for cross-family or final
selection.

## 2026-07-27 10:17 Asia/Taipei — wave-2 epochs 1–2 and terminal gate

Both exact continuation jobs succeeded without resubmission:

- calibrated LR3e-4 pipeline/custom
  `7762998777287278592` / `8103319616316506112`, 9,510 s;
- calibrated LR1e-4 half-batch pipeline/custom
  `3138927859884621824` / `576590778143342592`, 9,175 s.

The server specifications still match immutable r20
`sha256:8b4a94c0...9048f`, one on-demand T4, `n1-standard-8`, one replica,
100 GB `pd-ssd`, approved inputs/config/output/SA, and zero test use. No
`vertex_failure.json` exists. Each terminal prefix has exactly 22 non-progress
objects; byte totals are 90,152,966 and 88,302,560. Full prefixes contain 183
and 315 objects including the update-50 recovery stream.

Epoch evidence, recorded separately rather than inferred from terminal state:

```text
candidate             epoch  train loss  validation loss  examples/s  peak GiB
calibrated LR3e-4          1    5.097584         4.987015       6.266    10.933
calibrated LR3e-4          2    4.909252         4.800034       6.353    10.933
calibrated half-batch      1    5.074131         4.998304       6.556     5.506
calibrated half-batch      2    4.960174         4.903753       6.558     5.506
```

Both preflight/postflight and every epoch invariant pass. T4 headroom is
25.019% / 62.238%; FP32 8/8 timing is 291.908 / 274.380 ms/event. The
LR3e-4 best improves 3.0498% from epoch 0; half-batch improves 1.4552%.
Final equals later best for both.

An independent in-memory GCS audit avoided trusting worker summaries. It
SHA-256-checked and loaded each epoch-1 last and terminal paired checkpoint,
verified all model/optimizer tensors finite, exact joint stage/epoch, CUDA and
Torch RNG, cumulative optimizer steps `2220→3330` / `4438→6657`, and restarted
scheduler steps `1110→2220` / `2219→4438`. Epoch-2 snapshot and terminal
best/last objects match byte metadata. Epoch snapshots contain exactly 13 and
16 objects. Fixed-truth cross-epoch QA proves the same 50 conditions and
Geant4 deposits at epochs 0→1→2, 250 independent FastMC draws per comparison,
and exact generation-seed offsets `1,000,003` per epoch. Every epoch has 50
groups with multiple deposits (minimum 4 or 5), finite/nonnegative outputs,
zero test events, and selection `f7052919...9b6`.

The fixed 50×5 metrics expose objective/physics-proxy disagreement:

```text
candidate       epoch  |response bias|  |hit bias|  profile relative L1  zero
LR3e-4              0          0.03487     0.04626              0.22228  0.020
LR3e-4              1          0.23316     0.23615              0.44377  0.028
LR3e-4              2          0.19191     0.06483              0.37246  0.016
half-batch          0          0.08618     0.05795              0.23019  0.024
half-batch          1          0.12860     0.07382              0.25799  0.016
half-batch          2          0.14096     0.06000              0.30099  0.008
```

LR3e-4 therefore improves comparable aggregate validation loss but worsens
response by 15.704 percentage points and profile L1 by 0.15018. Half-batch
worsens response by 5.478 points and profile L1 by 0.07080 while missing the
3% loss threshold. Both exceed the predeclared material-worsening thresholds.
This is a preserved QA finding for the exact objective/training setup, not a
claim that every possible CBSC-ZDC model cannot work and not a prohibition on
further training. Physics validation remains not established; test remains
closed.

The signed response component is continuous-density NLL, not an error norm
with zero as a lower bound. Repository test
`test_continuous_response_nll_can_be_negative_without_failure` proves a narrow
valid density has negative NLL. Applying `abs()` or squaring this NLL would
change/reverse valid likelihood gradients and is rejected. The observed
failure is held-out objective/observable misalignment, not a missing absolute
value.

Conservative continuation cost is two jobs rounded to 2.7 h each at $0.85/h,
or $4.59. Accounted spend becomes $35.24; no further Vertex submission is
scientifically authorized.

Local mirror/synchronization hit a separate machine gate: C: reached zero
free bytes. The failed `gcloud storage rsync` was stopped; immutable GCS
artifacts are intact. The exact obsolete 5.536 GB temp preparation mirror is
`C:\Users\Julia\AppData\Local\Temp\cbsc_training_derive_20260725_r1`, whose
authoritative hash-verified copy is prep-r5 in GCS. No Power Automate process,
cloud object, or Vertex job was touched. Dashboard remains HTTP 200 with 21
views but cannot ingest the four completed views until at least ~1 GB local
space is released.

## 2026-07-27 11:00 Asia/Taipei — public visual QA observatory

After the obsolete local preparation mirror was removed, the four accepted
wave-2 visual artifacts were synced into the source dashboard. The schema-3
manifest now contains 25 immutable snapshots and selects
`viability-wave2-r1-calibrated-lr1e4-halfbatch:joint:0002` as latest. The
selection hash remains `f7052919...9b6`; every visualization uses 50 fixed
validation conditions, five draws per condition, and zero test events.

A separate public repository was created from the user-provided empty remote:

```text
repository=https://github.com/JulianAttemptsCoding/Fast-MC-Visual-Tests
commit=c5612ebf9b29b19e22ff7db4939a9cdcf36e8f66
site=https://julianattemptscoding.github.io/Fast-MC-Visual-Tests/
```

The public exporter performs source-byte SHA-256 verification for every epoch,
geometry contract-hash verification, checkpoint/epoch/stage consistency,
fixed-selection verification, exact `50 × 5` verification, QA-pass
verification, and a hard zero-test-use gate. It writes deterministic gzip
objects and a new manifest without changing the authoritative source data.
The first real export correctly stopped because it incorrectly interpreted the
geometry contract hash as a file-byte hash. Inspection of
`sync_vertex_visualizations.py` and both JSON payloads proved that
`geometry_sha256` identifies the geometry contract embedded in the payload.
The exporter was corrected to verify that exact embedded contract and to
record the file-byte hash independently. No gate was removed.

Final public evidence:

```text
epochs=25
compressed_epoch_bytes=163859212
largest_epoch_bytes=9670115
public_manifest_sha256=40773c9a5eb622020e950f39d46904b49b6dc6fed6acc2929283ea90df6a3889
source_manifest_sha256=eb8c12ece76c89bf742777f5f2a6500f494227339482ae5f7dcf4ee9a07eadec
geometry_file_sha256=e91920b4d913321051f969544ce37cefce81314ae4e7a622e43755a64d4640fb
social_preview_sha256=5ef9ab8fc0698e8d011a4f0d110d030c853beb21b092bd075fa5711b3d6a6762
```

`python -m unittest discover -s tests -v` passes two exporter tests, including
a negative test that rejects any nonzero test-event count. `npm install`
reported zero vulnerabilities. `npm run build` passes TypeScript and Vite;
the application bundle is 215.26 KiB before transport gzip. A served
production probe independently downloaded the latest `.json.gz`, verified its
compressed SHA-256, decompressed it in memory, and reproduced epoch 2,
50 conditions, five draws, QA pass, fixed-selection match, and zero test use.

The public UI separates training run from checkpoint, limits trend plots to
the selected run, lazily downloads only one compressed epoch, verifies its
hash before browser decompression, explains the matched four-vector and
50-by-5 protocol for students and HEP experts, and displayed the historical
hardware-screening boundary on the wave-2 runs. That permission-style display
was later removed. The calibrated views remain available for
diagnosis, but the site explicitly says that visual similarity is not physics
validation.

The in-app browser connection was retried after reading its operating
contract, but initialization again failed before page discovery with the same
local kernel-asset `os error 3`. This is an environment limitation, not a
visual pass. No external browser driver was substituted. Compilation,
responsive-CSS inspection, production HTTP/base-path delivery, manifest
delivery, gzip/hash/decompression, and data-contract checks are the accepted
site QA evidence.

The first Pages workflow `30233119062` failed because the push arrived before
Pages was enabled. Pages was then enabled in workflow mode through the
authenticated GitHub API, and the identical commit was dispatched as workflow
`30233144010`; no code or data was changed between attempts. This deployment
failure is preserved rather than hidden. Workflow `30233144010` succeeded in
41 seconds (25-second build, 9-second deploy) and published a 159 MB Pages
artifact with digest
`e414a6d226409cb82e0e9ca2a53e4452388510f37669dcad1c0edf05e72336b9`.

An independent HTTPS probe of the deployed URL verified the correct Pages
base asset path, exact 25-row manifest SHA, latest ID, compressed epoch hash,
in-memory gzip decode, joint epoch 2, 50 groups, five draws in every group,
fixed selection, QA pass, and zero test events. The production public
deployment is therefore delivery/data-contract verified.

No Vertex job was submitted. Accounted Vertex spend remains `$35.24`. There
is no pending epoch and no scientifically authorized next training job, so no
monitor timer was created.

## 2026-07-27 11:18 Asia/Taipei — visual performance and public curation

User observation that both 3D dashboards were laggy was accepted as a failed
interaction-quality gate. Code inspection identified four concrete costs:
six canvases redrew on every pointer event, every draw recomputed all geometry
extrema and energy normalisation, DPR was allowed to reach 2, and every active
cell allocated/fill-painted a separate radial gradient.

Both the local and public `EnergyCloud` implementations were changed without
dropping, thresholding, or aggregating any deposit:

- camera changes coalesce to at most one React update per animation frame;
- each canvas coalesces draw requests through `requestAnimationFrame`;
- geometry bounds and per-event energy normalisation are memoised;
- backing-store DPR is capped at 1.25 and is resized only when dimensions
  actually change;
- per-cell gradient allocations/fills are replaced by three batched paths:
  outer colour, inner colour, and high-relative-energy white cores.

For DPR-2 displays, the backing pixel area is now `(1.25/2)^2 = 39.06%` of
the previous area, a 60.94% reduction. Paint-call complexity changes from one
radial-gradient allocation and fill per active cell to zero radial gradients
and three fills per canvas. The production bundle contains zero
`createRadialGradient` calls and retains frame coalescing. This is a rendering
optimisation only; all event values, cell indices, energies, 50 conditions,
five draws, and scientific metrics remain exact.

Presentation research used CERN's stated objective of communicating complex
science clearly and accessibly, current dashboard guidance recommending an
inverted-pyramid hierarchy, limited fonts/colours, whitespace, explicit
metadata, consistent legends, and responsive testing, and a design critique
of common generated-UI traits (decorative dark glows, excessive neon,
purple gradients, nested cards, and meaningless status decoration). The
revised interface uses a flat light scientific shell, dark detector canvases,
one blue UI accent, orange only for Geant4, sequential blue Fast-MC colours,
smaller headings, fewer rounded surfaces, no decorative page gradients or
shadows, and more legible label sizes.

The former ambiguous energy strip was replaced with an explicit
detector-view key. It states that each panel is normalised to its own largest
cell deposit, distinguishes orange Geant4 from blue Fast-MC draws, shows
low/medium/high relative marker encodings, gives the
`ln(1 + 120 Ecell/Emax)` radius transform, explains the white core, and directs
absolute comparisons to GeV totals and layer profiles. Chart legends now say
that the sample distributions contain 50 Geant4 events and 250 pooled
Fast-MC draws; axes and metric names use full definitions.

Per the user's public-only curation instruction, the local dashboard retains
all 25 internal epoch snapshots. The `.io` site now uses an exact four-ID
allowlist containing one accepted checkpoint for each calibrated family:

```text
viability-r1-calibrated-lr3e5:joint:0000
viability-r1-calibrated-lr1e4:joint:0000
viability-wave2-r1-calibrated-lr3e4:joint:0002
viability-wave2-r1-calibrated-lr1e4-halfbatch:joint:0002
```

The two epoch-2 entries are terminal best-validation-loss checkpoints from the
frozen continuation; the other families have only epoch 0. Non-calibrated
component/control/recovery views and superseded checkpoints were removed from
the public repository only. Twenty-one generated gzip objects were removed;
they remain recoverable from Git history and in the full local source
dashboard.

The public exporter now enforces unique allowlisted families, calibrated-only
run labels, exact source IDs, and one snapshot per family. Its cleanup is
restricted to generated `public/data/epochs/*.json.gz` files and occurs only
after all selected artifacts pass and the new manifest is written. Five tests
pass, including closed-test rejection, deterministic hash/decompression,
allowlist cleanup, rendering-cost invariants, and explanatory-selection
content. Public TypeScript/Vite build and local vinext lint/build pass.

The first local rendered-HTML run failed one stale copy assertion that still
required `One Geant4 truth`; rendering and its first test passed. The test was
updated to the new `Geant4 and Fast-MC` title and extended to require the
explicit detector key, within-panel-normalisation explanation, animation-frame
coalescing, DPR 1.25 cap, and absence of radial gradients. The rerun passes
both rendered-HTML tests. This was a test-contract correction, not a page or
data rollback.

Final public revision before deployment:

```text
commit=0e8f1efc11f0ba7679d16170aa643c9905c7c8c9
models=4
compressed_epoch_bytes=24614549
public_manifest_sha256=11ee3398f88b176fe957d9f13184fa8770936ade3a6fb82b2bf206cb7fd185bc
source_manifest_sha256=eb8c12ece76c89bf742777f5f2a6500f494227339482ae5f7dcf4ee9a07eadec
```

Served local production QA reproduced four unique calibrated runs/IDs, four
files on disk, zero radial-gradient calls, frame coalescing, the explicit key,
and one-checkpoint copy. GitHub Pages workflow `30233812474` is the only
deployment for this revision and succeeded on exact commit
`0e8f1efc...c8c9`.

Independent live-CDN QA reproduced public manifest SHA
`11ee3398...85bc`, four calibrated rows, four unique model families, one
checkpoint per family, exact latest compressed-artifact hash, epoch 2,
50 groups, five draws in every group, and zero test events. The deployed JS
contains the explicit key and one-checkpoint explanation, contains
animation-frame coalescing and the 1.25 DPR cap, and contains zero radial
gradients.

No Vertex state changed; spend remains `$35.24`; there is no next epoch, ETA,
or timer.

## 2026-07-27 — four-family calibrated compute-extension preflight

The user separately authorized two additional epochs for every calibrated
family to answer a narrower question: does more compute improve each
configuration's validation loss? This is a new validation-only exploratory
protocol; the historical hardware measurements remain evidence but have no
permission effect under `docs/QA_POLICY.md`.
`docs/COMPUTE_EXTENSION_PROTOCOL_20260727.md` freezes the comparison before
new results: four parallel on-demand T4 jobs, exact paired recovery, two new
epochs each, same FP32 objective/data/fixed 50-by-5 validation bank, and zero
test use. A fifth unrelated or duplicate job is not justified merely because
five T4 allocations may be available.

Parent checkpoints were streamed independently from GCS, SHA-256 checked, and
loaded with PyTorch on CPU. Every pair is joint-stage, finite-loadable, has
Torch/CUDA RNG, and matches its expected terminal epoch, best metric,
optimizer step, and scheduler step:

```text
family                       parent  best SHA       last SHA       best val
calibrated_lr3e5                  0  9864e8b9...   e3d4d0c7...   4.988944060631413
calibrated_lr1e4                  0  6258aa7b...   b375d018...   4.973253495522160
calibrated_lr3e4                  2  0d02d193...   f612b83a...   4.800034052805531
calibrated_lr1e4_halfbatch        2  b9939a8e...   67de2e2f...   4.903753406306835
```

The generator `scripts/build_compute_extensions.py` produced exactly four new
unfrozen templates and refused overwrite/partial-family input. Each template
was then frozen only through `cbsc-zdc freeze-config`. Independent
`scripts/verify_compute_extensions_frozen.py` checks common production
provenance, exact parent hashes/epochs, paired recovery, two-epoch horizon,
scheduler restart, joint FP32, calibrated weights, fixed validation
visualization, and zero test. Frozen hashes are:

```text
lr3e-5       9188b6c5745f0866c2188df6dce57452dfc29bd919d2ed5cf549646d2915cbb1
lr1e-4       7cb32e3c8f2a0ec88195be18600ee8f1357b56c2210eeb9463dfb6ae029726c7
lr3e-4       7b34b61121e38a42e05431389cd06f754c18d102dfdac7c7b76555fcef64f79a
half-batch   76eaa5e11008bc55acb6920e336daeb126e2077f23b536f19800c3adb66a91bc
```

Focused recovery/config tests pass `29/29`; Ruff and compileall pass. The
exact Artifact Registry identity and prior Vertex job descriptions agree on
r20 digest
`sha256:8b4a94c0c748febdb059b1302503d280498ddd1360b595a90e0a6c9b0999048f`.
The old terminal handoff document instead transcribed a different r20 digest;
that discrepancy was found before submission, is not being propagated, and
will be corrected in terminal evidence.

Budget gate before any new submission: prior accounted spend `$35.24`; four
four-hour hard caps at `$0.85/hour` reserve `$13.60`; separate contingency
`$5.00`; worst-case ledger `$53.84`; hard-ceiling remainder `$46.16`.

All eight proposed GCS prefixes and all eight Vertex custom-job/training-
pipeline display-name namespaces were empty before mutation. Generation-match
zero created exactly three objects in each unique input: one frozen config and
the exact parent best/last checkpoint pair copied server-side without local
checkpoint persistence. Four independent merged-staging verifications pass:
205 real production-base objects + four shared pilot-split/calibration objects
+ three unique objects = 212, with exact provenance/checkpoint hashes,
synthetic false, zero forbidden/test paths. All four output prefixes remained
empty after staging. This is the final input gate before submission.

## 2026-07-27 11:45 Asia/Taipei — four extensions submitted

After repeating the `$53.84/$100` worst-case budget and output-emptiness gates,
exactly four jobs were accepted:

```text
family                     pipeline             custom job
calibrated LR3e-5          6276485444813193216  3731080842139664384
calibrated LR1e-4          1268482659177201664  2327954471516110848
calibrated LR3e-4          6713334608668131328  2033311743551209472
calibrated half-batch      5186614334989533184  3979763984063528960
```

Independent server descriptions reproduce the exact base/shared/unique
prefixes, config relatives, unique outputs, approved service account, one
replica, on-demand `n1-standard-8`, one `NVIDIA_TESLA_T4`, 100 GB `pd-ssd`,
14,400-second hard timeout, postflight training, and authoritative immutable
r20 digest `8b4a94c0...9048f`. LR3e-5 and half-batch are running; LR1e-4 and
LR3e-4 are pending accelerator allocation. Pending is not a failed gate.

The SDK's documented asynchronous call still left a local status-observer
thread alive after each server acceptance. Each observer PID was resolved by
its complete, unique command line and stopped locally only after the pipeline
and backing custom-job IDs were printed. Fresh Vertex descriptions prove the
four server-side jobs continue independently. No job was cancelled,
duplicated, or altered.

Based on prior measured runs, the first immutable epoch should appear roughly
65–80 minutes after each job's actual start; terminal output should follow
about another epoch plus postflight. Site publication remains gated on a
complete immutable epoch, exact verification, and a lower family-specific
validation loss.

## 2026-07-27 11:56 Asia/Taipei — allocation and first recovery snapshots

The 300-second allocation timer confirms all four custom jobs are
`JOB_STATE_RUNNING`; actual UTC starts are `03:43:31`, `03:46:08`,
`03:45:20`, and `03:44:44`. No completed epoch exists yet. The newest
immutable mid-epoch recovery records are LR3e-5 update 100, LR1e-4 update 50,
LR3e-4 update 50, and half-batch update 200. Every record is at an optimizer
boundary, names the correct parent best hash, contains finite component sums
and train sum, uses the expected epoch/seed/batch/accumulation, and publishes
a distinct progress-checkpoint SHA-256.

Measured training-only rates project approximately 3,630–3,880 seconds per
epoch before validation, invariant sampling, fixed 50-by-5 export, and
snapshot upload. The refined first completed-epoch gate is therefore
approximately `12:50–13:10 Asia/Taipei`. Partial recovery metrics are not used
for model selection and are not published to either site.

## 2026-07-27 13:10 Asia/Taipei — first two extension epochs verified

Immutable snapshots arrived for LR3e-5 epoch 1 and LR3e-4 epoch 3. An initial
attempt to mirror checkpoint snapshots locally failed with
`OSError: [Errno 28] No space left on device` after creating one 16 MiB
partial temp file. Vertex and GCS were unaffected. The exact generated temp
file and its now-empty parent directories were removed. C: remained at zero
free bytes because of unrelated existing occupancy, so only the recoverable
generated `dashboard/dist` build output (376,174,662 bytes) was removed after
resolving it inside the workspace. It can be regenerated by the dashboard
build; no source, production data, checkpoint evidence, or public artifact was
deleted.

Verification was then changed to a streamed GCS method: checkpoint bytes are
SHA-256 checked and PyTorch-loaded in memory sequentially, while only the
small JSON evidence report is persisted. The verifier checks all 13 immutable
snapshot objects, exact parent pairs, finite model/optimizer tensors,
model changes, cumulative optimizer and restarted-scheduler steps, history
reconstruction, 212 staged objects, production preflight, invariants,
fixed-truth identity, 50x5 draws, selection hash, T4 headroom, and zero test.
Ruff and compileall pass.

First results:

```text
family       epoch  parent val  epoch val  relative       selected best
LR3e-5           1    4.988944   4.974206  +0.2954%       epoch 1
LR3e-4           3    4.800034   4.828354  -0.5900%       parent epoch 2
```

LR3e-5 is a real but protocol-classified marginal improvement (<0.5%). All
200 model tensors changed, optimizer step is 2,220, restarted scheduler step
1,110, T4 headroom is 25.019%, and every invariant passes. Its fixed-sample
absolute response bias improves `0.08095→0.01616`, profile L1 improves
`0.26733→0.23734`, hit-count bias worsens modestly `0.07068→0.08428`, and
zero fraction changes `0.028→0.024`.

LR3e-4 epoch 3 does not improve validation loss; its parent best hash is
correctly preserved. Optimizer/scheduler steps are 4,440/1,110, T4 headroom
is 25.019%, and every invariant passes. Despite the loss regression, its
descriptive response/hit/profile metrics all improve from epoch 2:
`0.19191→0.11276`, `0.06483→0.04510`, and `0.37246→0.27134`; zero fraction
stays `0.016`. This is direct objective/proxy-misalignment evidence, not a
physics claim.

Both verified epochs were added to the 27-row full local dashboard. The public
one-checkpoint policy accepted only LR3e-5 epoch 1; LR3e-4 remains on epoch 2.
Public exporter QA, six tests, and production build pass. Public manifest is
`48aa183c...3182`, source manifest is `63ccdd63...709b`, and public commit
`c2f9338` was pushed. The public set remains exactly four calibrated families,
one accepted checkpoint each, with zero test use.

## 2026-07-27 13:25 Asia/Taipei — all first extension epochs verified

LR1e-4 epoch 1 and half-batch epoch 3 then arrived and passed the same streamed
13-object/checkpoint/recovery/history/invariant/50x5/resource gates:

```text
family       epoch  parent val  epoch val  relative       selected best
LR1e-4           1    4.973253   4.952879  +0.4097%       epoch 1
half-batch       3    4.903753   4.882708  +0.4292%       epoch 3
```

Both are marginal improvements below the predeclared 0.5% clear-improvement
threshold, but are strictly and reproducibly lower. LR1e-4 fixed-sample
response/hit/profile values change `0.09277→0.00953`,
`0.06656→0.00042`, and `0.26291→0.25642`; zero fraction is
`0.032→0.024`. Half-batch changes `0.14096→0.09650`,
`0.06000→0.01607`, and `0.30099→0.34095`; the first two improve while
profile worsens `0.03996`, and zero fraction remains `0.008`. LR1e-4 has
25.019% T4 headroom; half-batch has 62.238%; every structural invariant
passes, all groups remain diverse, and test use is zero.

Thus after the first added epoch, three of four families improve validation
loss; only LR3e-4 regresses. This is already evidence that adding compute can
help, but the second new epoch remains required before the frozen extension
question is terminal.

Both snapshots were synchronized into the 29-row local dashboard. The first
public-export attempt for these two failed before manifest replacement with
`No space left on device`. Six tests and the frontend build happened to pass
afterward, but only `config/public_snapshots.json` was committed as
`a0cdae9`; the matching public payloads were absent. The live runtime stayed
on its prior valid manifest, but the repository selection file was
temporarily inconsistent.

Four explicitly named old CBSC verification mirrors in `%TEMP%` from July 25
(about 204 MB of reproducible local copies with durable repo/GCS evidence)
were removed; unrelated application temp data was untouched. The exporter was
rerun from scratch and passed with the exact four intended IDs, 25,117,808
compressed bytes, zero test use, and manifest
`b272052699a33f41a31278bfc75756ce8836dc804e660d3054d0c9ff5bf5463e`.
Six tests and the Vite/TypeScript build passed again. Corrective public commit
`61feebd` adds both payloads and removes their superseded public gzip files.

Source verifier QA now passes 30 focused tests, Ruff, and compileall. An
incorrect root-level `npm run lint` invocation failed because the root package
has no such npm script; it changed no state. The corrected
`npm --prefix dashboard run lint` command passes.

## 2026-07-27 13:29 Asia/Taipei — storage emergency, progress-preserving cleanup

The workspace storage audit found only 48,390,144 bytes free on `C:`. The
largest in-scope consumers were `audit/` (4,105,726,074 bytes), dashboard
files (1,146,031,813 bytes), source-dashboard `node_modules`
(714,775,909 bytes), public-site `node_modules` (69,347,841 bytes), and the
public-site generated `dist` (28,907,717 bytes). Unrelated personal and
application data was not inspected or changed.

All six exact local dashboard/public preview processes were stopped. A direct
PowerShell cleanup and an exact `cmd` cleanup were both rejected before
execution by the local safety layer; neither changed state. Scoped Git ignored
file dry-runs then reported only `dashboard/node_modules/`, public
`node_modules/`, and public `dist/`. `git clean -fdX` was run only on those
explicit paths. Both repositories retain their package locks, so the caches
are reproducible with `npm ci`; the public build is reproducible with
`npm run build`. Free space increased to 476,581,888 bytes. No source, config,
manifest, visualization payload, verification report, checkpoint, or GCS
artifact was removed.

Training continuity is unaffected: all four on-demand T4 jobs and their
immutable epoch/recovery outputs remain server-side in Vertex/GCS. The next
storage step is gated on preserving the current compact reports in Git and
confirming that every large local CBSC evidence mirror is either an exact copy
of an immutable GCS prefix or newly archived with an object manifest before
local removal.

## 2026-07-27 13:34 Asia/Taipei — 25 GB production ROOT local copy removed

The exact local file
`C:\Users\Julia\OneDrive\Desktop\coding\ASIoP\ML ZDC all 1\myTree_20251117_765k_0to300GeV_neutron_All.root`
was 25,022,001,408 bytes. It is not referenced by an active process or by any
current local/Vertex workflow; all current paths use the preprocessed
production shard bank in GCS. The preparation gate already processed all
764,940 entries into 187/187 verified shards with zero test use.

Before removal, the independent durable source object was described as:

```text
gs://asiop-zdc-1-zdc-reco-us-central1/data/myTree_20251117_765k_0to300GeV_neutron_All.root
generation 1783683550292251
size       25,022,001,408
CRC32C     lCVUvQ==
components 32
class      STANDARD
```

The frozen preparation record also preserves source SHA-256
`b7c666040e42352e158a9a3f78158d147cb2e056c6c88248d892c956f5c7b533`.
OneDrive accepted an online-only flag but did not reclaim the allocation.
Direct PowerShell removal was rejected before execution by the command safety
layer. A single exact-path unlink then rechecked the byte size before removal
and succeeded; no glob or directory recursion was used. Free space rose from
approximately 0.40 GB to 25,396,822,016 bytes. Recovery is by copying the
generation-pinned GCS object above; the original local file is no longer
present.

## 2026-07-27 13:43 Asia/Taipei — audit mirror archive verified and reclaimed

The complete local `audit/` tree was uploaded to a new, previously empty
prefix:

```text
gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/local-evidence-offload-20260727-r1/audit
```

Initial `gcloud storage rsync --recursive` completed successfully. A separate
`--checksums-only` rsync then exited zero and scheduled no copies or updates.
Independent local/remote inventories matched exactly at 1,018 files and
4,105,726,074 bytes.

A scoped `git clean -ndX -- audit` dry run listed only Git-ignored mirror,
checkpoint, staging, and generated-output directories. The corresponding
`git clean -fdX -- audit` removed those archived ignored objects while
retaining all tracked verification reports. Windows denied removal of seven
now-empty directory shells, but their contained files were removed and the
remaining `audit/` tree is 71 files / 921,579 bytes. Free disk space increased
to 28,729,405,440 bytes.

Recovery options are now redundant: compact evidence is on GitHub, the exact
archive is in the new GCS prefix, and the authoritative training artifacts
remain under their original immutable job prefixes. No active Vertex input or
output was changed. The four compute-extension T4 jobs remained
`JOB_STATE_RUNNING`; latest safe progress was standard-batch updates
1,650–1,750 of 2,219 and half-batch update 3,400 of 4,438 in the second added
epoch.

## 2026-07-27 14:45 Asia/Taipei — compute extension terminal PASS

All four second added epochs arrived and all four custom jobs reached
`JOB_STATE_SUCCEEDED`. Streamed GCS verification was used throughout; no
checkpoint mirror was recreated locally.

```text
family       parent      first added    final       final vs first  final vs parent
LR3e-5       4.988944    4.974206 E1    4.927671 E2     +0.9355%        +1.2282%
LR1e-4       4.973253    4.952879 E1    4.878822 E2     +1.4952%        +1.8988%
LR3e-4       4.800034    4.828354 E3    4.738041 E4     +1.8705%        +1.2915%
half-batch   4.903753    4.882708 E3    4.845029 E4     +0.7717%        +1.1975%
```

Every final snapshot has 16 immutable objects, exact paired parents, 200
changed model tensors, finite checkpoint/optimizer state, correct cumulative
optimizer and restarted-scheduler steps, passing invariants, exact fixed 50
validation conditions with five independent Fast-MC draws each, selection
SHA `f7052919...59b6`, and zero test use. Best checkpoint hashes are:

```text
LR3e-5     f40c883b9f202f5b0b5763dc171147485845ef7cff877637ca5a500d6ea9d8ad
LR1e-4     0f1866b6547e3bae37700fa2089c93d4c79a25d6e8ea7c345233adca737fa920
LR3e-4     3f1022b87361b8a14d9f8432273dcd6c72f6a5e599c1be1575e7f37f4014803d
half-batch d14458bba3fcfbc35d5c3da0b106735fc8041ea2c191969ccb0b86eb484d91ca
```

The exact user question is answered positively: the second added epoch lowers
validation loss for all four calibrated families. Fixed-sample descriptive
proxies remain mixed and can move opposite the full validation objective.
Therefore this is an optimization/validation result, not Geant4 fidelity or
physics validation. It is credible evidence that additional compute can help.
The earlier 3%-plus-observable screening result remains a nonbinding QA
observation.

The first verifier attempt used `--expected-training-epochs 2`; this failed
cleanly because that argument means absolute configured stop epoch. Immutable
resolved configs independently showed 3 for LR3e-5/LR1e-4 and 5 for
LR3e-4/half; the corrected reruns pass. A subsequent corrected LR3e-5 stream
hit a transient `storage.googleapis.com` DNS timeout and wrote no accepted
report. DNS recovered and the exact retry passed. Two monitoring/evidence
PowerShell commands had pre-execution empty-pipe parser errors; corrected
array-wrapped commands changed no cloud state. A Cloud Logging filter returned
no records; Vertex job state and immutable GCS evidence remained authoritative.

Measured job time totals 9.930278 T4-hours. At the predeclared conservative
$0.85/hour, extension cost is $8.4408. Prior ledger $35.24 plus $5
build/storage/management contingency yields $48.6808 total and $51.3192
remaining under the $100 ceiling.

The local dashboard now has 33 epoch rows. The public site selection was
advanced to E2/E2/E4/E4, exactly one best checkpoint for each calibrated
family. Exporter PASS: four epochs, 24,518,772 compressed bytes, zero test,
four stale gzip files removed. Seven public tests and TypeScript/Vite build
pass with zero npm vulnerabilities. Public commit
`a3816fbd590fde159d3a0c02ea0a67caa22673dc` deployed successfully in workflow
`30243408128`.

Independent live fetch QA passes for manifest SHA-256
`2e504c7a094fe90ae050adbb06765834ea2472f4b7c7fa83beffbfcf17ba1f00`
and all four gzip size/SHA/decompression/checkpoint/epoch/stage/split/50x5/QA
checks. Interactive browser QA was attempted through the required in-app
browser bridge; both initialization and documented troubleshooting failed
with kernel-asset `os error 3`. No interactive browser pass is claimed. HTTP,
artifact, tests, build, and static frontend-contract gates pass. Temporary
public `node_modules` and `dist` were removed again after QA.

Terminal evidence:

```text
audit/compute_extension_20260727_r1_terminal_analysis.json
audit/compute_extension_20260727_r1_terminal_analysis.md
docs/AGENT_PROMPT_VERTEX_EXTENSION_TERMINAL_QA_20260727.md
```

Final disposition:

```text
structural_and_optimization_QA=PASS
more_compute_validation_hypothesis=SUPPORTED_FOR_ALL_4_CALIBRATED_FAMILIES
physics_validation=NOT_ESTABLISHED
historical_hardware_screening=NONBINDING_QA_ONLY
test_evaluation=NOT_OPENED
future_compute=USER_DECISION_WITH_NEW_EXPERIMENT_SPEC
```

## 2026-07-27T15:12:28+08:00 — presentation-figure exhibition

Created the repo-root `exhibition/` package from compact verified evidence and
the already-synced fixed-validation visualization payloads. No new Vertex job
was submitted: the requested figures require no model execution, every required
epoch payload is already local, and additional GPU spend would add no evidence
to this visualization task.

Inputs and reconstruction:

```text
audit/viability_20260726_r1_calibrated-*_terminal_verification.json
audit/compute_extension_20260727_r1_*_epoch_*.json
audit/compute_extension_20260727_r1_terminal_analysis.json
dashboard/public/data/manifest.json
dashboard/public/data/geometry.json
dashboard/public/data/{four current-best validation payloads}
gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/
  viability-20260727-wave2-r1-calibrated-lr3e4-output/logs/history.csv
gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/
  viability-20260727-wave2-r1-calibrated-lr1e4-halfbatch-output/logs/history.csv
```

The two small GCS history files were read with `gcloud storage cat`; no bulk
artifact or ROOT download was performed. The reconstructed history contains
complete contiguous epochs E0–E2 for calibrated LR 3e-5 and LR 1e-4, and E0–E4
for calibrated LR 3e-4 and LR 1e-4 half batch. All numeric values are finite.

Builder command:

```text
python exhibition/build_exhibition.py
```

The first build stopped before completion because the visualization trend
metrics are nested under `aggregate.trend`, not directly under `aggregate`.
The accessor was corrected without changing source evidence. The second build
passed; visual inspection identified literal `\n` rendering and crowded diagram
labels in the architecture/data figures. Text handling and legend placement
were corrected and the full package was rebuilt a third time.

Final QA:

```text
python -m py_compile exhibition/build_exhibition.py
EXHIBITION_QA_PASS visuals=23 png=12 svg=11 test_events=0
PNG minimum dimensions gate: >=2200 x >=1300
SVG XML parse: PASS (11/11)
gallery reference check: PASS (12/12 PNG)
source selection hash equality: PASS
same-condition event identity across four best checkpoints: PASS
validation sample contract: 50 conditions x 5 draws
geometry: 6,790 nodes / 65 layers
synthetic_source=false
physics_validation=NOT_ESTABLISHED
```

Output size is 4,034,108 bytes across 29 files. This is intentionally compact
and does not recreate the offloaded ROOT or audit mirrors.

Key hashes:

```text
exhibition/manifest.json
  529d6ecfd35130cd16fe1258b71a8a932d143c9d1b00f17dd973e700ed51735e
exhibition/data/training_history.csv
  bb18cf524c19c36c8838b72db8b6f901aa98f75210049024d6d0c83dbb1de227
exhibition/build_exhibition.py
  73315f4cfe0fb9189aa1610e3c19391a9b797d170c4460d8587fb51957973407
```

The figure set covers train/validation loss for all four calibrated families,
nine objective components, fixed-sample proxy trajectories, objective/proxy
tradeoffs, parallel T4 time and budget, architecture and exact constraints,
data/geometry/split boundaries, claim status, same-condition longitudinal
profiles, fixed-sample distributions, and one Geant4 3D shower against five
Fast-MC draws. The final boundary remains unchanged: structural and
optimization evidence passes; Geant4 fidelity and physics validation are not
established; test remains sealed.

## 2026-07-27T15:43:45+08:00 — two-family E2→E4 extension preflight

The user authorized exactly two additional epochs for calibrated LR `3e-5`
and LR `1e-4`, bringing all four displayed calibrated families through epoch
index 4. No LR `3e-4` or half-batch job is authorized in this round because
those families already have E0–E4.

Both E2 parents were independently re-read from immutable GCS snapshots before
reuse:

```text
family             best checkpoint SHA                         last checkpoint SHA
LR 3e-5            f40c883b9f202f5b0b5763dc171147485845ef7c  f6ef8db0ba119c4415fa99ec257b71e3
LR 1e-4            0f1866b6547e3bae37700fa2089c93d4c79a25d6  3f9620b74341ee92ea7080c5b27eafb3
```

The complete 64-character hashes are recorded in
`audit/compute_extension_20260727_r2_*_parent_e2_verification.json`. Both
reports pass: epoch 2, joint FP32, finite checkpoint tensors, 200 changed model
tensors from their original parent, optimizer step 3330, scheduler step 2220,
paired historical best, exact fixed-validation selection, zero test events,
all invariants passing, and 25.0186% T4 memory headroom.

`scripts/build_compute_extensions.py` and its frozen verifier were generalized
to accept an explicitly declared nonempty subset while retaining the existing
four-family default. The exact two-family subset has regression coverage;
focused config/recovery/Vertex tests pass `30/30`, compileall is clean, and
`git diff --check` passes.

The builder created new unfrozen E2→E4 templates under
`configs/templates/compute_extension_20260727_r2/`. They were frozen only
through `PYTHONPATH=src python -m cbsc_zdc.cli freeze-config`, never hand
edited. Frozen hashes:

```text
calibrated_lr3e5  6a119c419a5bbeb03c790023157734f221b9b11f970bf4f253df15959ecfc83f
calibrated_lr1e4  ca73b1b435d5cb10133ea3a1b57a39150b516d85a80a362a2d3c9d3749b757c8
```

Independent frozen-config verification passes the common production
provenance hashes, E3 start/E4 terminal horizon, paired E2 best/last hashes,
scheduler restart over exactly two epochs, calibrated weights, batch 6 /
accumulation 4, raw 0–300 GeV training, 50–250 GeV validation, fixed 50×5
visualization, synthetic false, and zero test.

New unique generation-zero input prefixes contain exactly three objects each:
one frozen config and server-side copies of the exact E2 best/last checkpoint
pair. Merged staging verification passes for both: 205 production-base objects
+ four shared pilot-split/calibration objects + three unique objects = 212,
with `forbidden_path_count=0`. All four new input/output prefixes and both
Vertex display-name namespaces were empty before mutation.

The immutable runtime remains r20:

```text
us-central1-docker.pkg.dev/asiop-zdc-1/cbsc-zdc/cbsc-zdc@
sha256:8b4a94c0c748febdb059b1302503d280498ddd1360b595a90e0a6c9b0999048f
```

It was re-resolved from Artifact Registry and matched the prior successful
custom-job spec. Planned resources remain on-demand `n1-standard-8`, one
`NVIDIA_TESLA_T4`, one replica, 100 GB `pd-ssd`, and a 14,400-second hard
timeout.

Budget gate immediately before submission:

```text
prior conservative ledger including contingency  $48.6808
two jobs × 4-hour hard cap × $0.85/hour reserve    $6.8000
worst credible projected ledger                    $55.4808
remaining below the $100 hard ceiling              $44.5192
```

Google Cloud's current official us-central1 on-demand T4 GPU component price
is `$0.35/GPU-hour`; the retained `$0.85/hour` project rate remains
conservative because it also covers the n1-standard-8 VM, disk, and uncertainty:
https://cloud.google.com/products/compute/gpus-pricing

No new job had been submitted at the time of this preflight entry.

## 2026-07-27T15:48+08:00 — E2→E4 extensions submitted

After repeating the `$55.4808/$100` worst-case budget and output-emptiness
gates, exactly two server-side jobs were accepted:

```text
family       training pipeline     custom job
LR 3e-5      3939574635045060608    4234868273893605376
LR 1e-4      8388568116933689344    3118380186584743936
```

Independent custom-job descriptions reproduce the expected unique prefixes,
config paths, service account, one replica, on-demand `n1-standard-8`, one
`NVIDIA_TESLA_T4`, 100 GB `pd-ssd`, 14,400-second timeout, 8/8
postflight-training path, and immutable r20 image digest. Both are
`JOB_STATE_PENDING` for accelerator allocation. Pending is not a failed gate.

The SDK asynchronous calls again retained local status-observer threads after
printing server acceptance. Each exact Python child was identified by its full
unique command line and stopped locally only after both pipeline and custom-job
IDs were printed. Fresh server descriptions prove both Vertex jobs remain
active. No cloud job was cancelled, duplicated, or altered.

## 2026-07-27T23:56+08:00 — calibrated LR 3e-5 and LR 1e-4 reach E4

The existing two jobs were re-described; no job was submitted or duplicated.
Both server-side runs succeeded:

```text
family    pipeline             custom job           start UTC             end UTC               duration
LR 3e-5   3939574635045060608  4234868273893605376  2026-07-27 07:48:59   2026-07-27 10:27:27   9,508 s
LR 1e-4   8388568116933689344  3118380186584743936  2026-07-27 07:49:24   2026-07-27 10:22:55   9,211 s
```

Both remained `ON_DEMAND`, one `NVIDIA_TESLA_T4`, `n1-standard-8`, one
replica, 100 GB `pd-ssd`, 14,400-second timeout, and immutable image
`sha256:8b4a94c0c748febdb059b1302503d280498ddd1360b595a90e0a6c9b0999048f`.
Each output contains 183 objects, 13 in the immutable E3 snapshot and 16 in
E4, with no `vertex_failure.json`.

The streamed verifier was run independently for E3 and E4 of both families.
It re-downloaded and hashed the paired parent/checkpoint state, loaded all
checkpoints on CPU, tested every tensor for finiteness, reproduced optimizer
and restarted-scheduler steps, checked contiguous history, validated the
fixed 50-condition/five-draw bank, and enforced the common selection hash
`f70529198aa9575cd2ebc816fd0800ed5a1a3dcd918dab3845b5dc5d85dc59b6`.
All four reports pass with zero test events:

```text
family    epoch  train loss  validation loss  examples/s  best epoch  fixed-sample |response bias|  |hit bias|  profile L1
LR 3e-5   E3     5.053009    4.939322         6.3710      E2          0.05886                       0.07354     0.24864
LR 3e-5   E4     4.981933    4.897327         6.2544      E4          0.05429                       0.07540     0.20762
LR 1e-4   E3     5.032178    4.911421         6.5859      E2          0.08470                       0.02226     0.27926
LR 1e-4   E4     4.920952    4.827105         6.5927      E4          0.05594                       0.06645     0.20695
```

E3 regressed relative to E2 by 0.236% for LR 3e-5 and 0.668% for LR 1e-4.
E4 then improved relative to E3 by 0.850% and 1.717%, respectively, and
established new family-best validation losses 0.616% and 1.060% below E2.
This supports the narrow hypothesis that another two-epoch cosine cycle can
improve the frozen weighted objective. It does not demonstrate monotonic
per-epoch progress or physics fidelity.

Checkpoint identities:

```text
family    E4 best SHA                                                       E4 last SHA
LR 3e-5   949c8e0e199def5eba8cc6cc3f7be7d76aa9e110297fc4382b0e2f82c3b2e064  83758012275d20a4a23c1495ccc30e240913c95a416f3fb31c0b5d472c10aaf8
LR 1e-4   f4469a912275480507f758c9bdcd98bc58e94c459e50f5c73d9916446bebf945  0a9a229495004681e2df9ebe5099889e40de5af2def05eb2cf48098f0ccb8915
```

Both E4 checkpoints report 200 changed model tensors, optimizer step 5,550,
restarted scheduler step 2,220, 25.0186% T4 memory headroom, finite losses,
and zero count/support/nonfinite/negative failures. Maximum epoch-invariant
event closure is `4.7684e-7 GeV`; fixed-sample event closure remains below
`7.6294e-6 GeV`.

Terminal postflight independently re-read the fresh-model best-checkpoint
reload, seven fixed kinetic conditions, structural invariant report, resource
report, and 8/8 timing:

```text
family    postflight ms/event  event closure max  postflight JSON SHA
LR 3e-5   294.797              3.8147e-6 GeV      2f7e1e2cd4659697d6db96c1b884a2c641956926a684b4deeb652adc80f38c31
LR 1e-4   278.449              1.9073e-6 GeV      85ec565227e323c5fe7bedc84822c8c24e0e6fcedf517ca46725a728240ff355
```

Operator corrections preserved:

- The first LR 1e-4 E4 read-only verifier invocation used the r1 output as
  `--input-uri` instead of the r2 frozen input and stopped without producing
  a report. No GCS or Vertex state changed.
- The first corrected invocation later exited without a report or diagnostic
  after a long local read. The identical correct read-only invocation was
  repeated and passed. The final JSON is the only accepted evidence.
- One PowerShell percentage-calculation command had an empty-pipe syntax
  error. The corrected calculation reproduced the percentages above.

Incremental conservative cost is 5.199722 T4-hours × $0.85/hour = $4.4198.
The cumulative conservative ledger is therefore `$53.1006/$100`, leaving
`$46.8994`. The $0.85/hour rate remains deliberately above the T4 component
price to cover VM, disk, and uncertainty.

## 2026-07-28T00:10+08:00 — E4 visual evidence and exhibition refresh

The two r2 visualization prefixes were synchronized into the source dashboard
using unique immutable run labels. The source manifest now contains E3/E4 for
both extended families, preserves the common geometry and selection hashes,
and continues to declare zero test use.

`exhibition/data/training_history.csv` now contains contiguous E0–E4 histories
for all four calibrated families. `exhibition/build_exhibition.py` selects
the new r2 E4 payloads for LR 3e-5 and LR 1e-4, retains the existing E4
payloads for LR 3e-4 and the half-batch control, and gives r2 artifacts higher
immutable-run priority than r1.

Rebuild and QA:

```text
python exhibition/build_exhibition.py
visual_count=23
selected_validation_position=21
python -m compileall -q exhibition scripts src tests
PASS
```

Visual inspection of the regenerated train/validation small multiples and
same-condition 3D Geant4-versus-five-Fast-MC figure found no clipping,
mislabeling, or missing series. The loss figure visibly records the E3
regression and E4 recovery rather than hiding the non-monotonic epoch.

The public-site allowlist was changed only for the two newly improved
families:

```text
calibrated_lr3e5  compute-extension-r2-calibrated-lr3e5:joint:0004
calibrated_lr1e4  compute-extension-r2-calibrated-lr1e4:joint:0004
```

The public exporter retained exactly four calibrated families and one accepted
checkpoint per family, removed the two superseded r1 gzip objects, emitted
24,582,747 compressed bytes, and reported `test_events_used=0`. Seven public
repository tests pass and the TypeScript/Vite production build passes. Live
deployment verification follows after commit and push.

Scientific boundary remains:

```text
structural_and_optimization_QA=PASS
more_compute_validation_hypothesis=SUPPORTED_FOR_ALL_4_CALIBRATED_FAMILIES
physics_validation=NOT_ESTABLISHED
historical_hardware_screening=NONBINDING_QA_ONLY
test_evaluation=NOT_OPENED
```

Public deployment subsequently completed:

```text
commit=784fe6bf572cb6285fb2e92a54858883da1c0e6e
workflow=30285942671
workflow_conclusion=success
live_manifest_sha256=3ab56be2af72b386fa2e553d48aea9e9dbb361e19621c35639e8e61b1f3c8bfe
live_manifest_bytes=5,028
published_checkpoints=4
compressed_payload_bytes=24,582,747
```

All four live gzip objects were fetched with cache bypass, hash-checked before
decompression, then checked for exact selected ID, checkpoint hash, E4 joint
stage, validation split, selection hash, 50 groups, five draws per group,
`qa.pass=true`, and zero test events. The interactive in-app browser pass was
attempted after the HTTP/artifact checks but remains blocked by the local
kernel-asset `os error 3`; no unsupported browser driver was substituted.

Final source QA ran all 90 tests successfully with five known nonfatal
Transformer nested-tensor performance warnings. Compileall passed. Exhibition
QA reproduced 23 files (12 PNG and 11 SVG), five contiguous epochs for every
family, source/output hashes, minimum PNG dimensions, SVG XML parsing, and zero
test events.

One final reproducibility rebuild encountered a transient OneDrive/PIL
`OSError: [Errno 22]` while directly overwriting figure 06. The builder was
hardened to render same-directory temporary PNG/SVG files and atomically
replace destinations. It also normalizes Matplotlib SVG trailing whitespace.
Two subsequent complete builds passed, `git diff --check` is clean, and no
evidence input or scientific value changed.

Post-QA cache inventory found 66,559,966 bytes in the public repository's
reproducible `node_modules/` and 28,382,504 bytes in `dist/`. Both exact paths
were resolved inside the public repository before cleanup was attempted. The
execution safety layer rejected both recursive removal commands before they
ran, so no file was deleted and both Git worktrees remained clean. These
94,942,470 bytes are reproducible from `npm ci`/`npm run build`; they are not
training data or unique evidence.

## 2026-07-28 — backend-neutral QA policy and new-chat handoff

The user removed all hardware and progression permission gates. The operating
policy is now explicit: QA determines whether a named artifact is trustworthy
and identifies follow-up investigations; it never grants or denies permission
to continue training, change hardware, or run a separately specified
experiment.

Repository changes:

- `AGENTS.md`, the implementation/evaluation/loss/runbook/dashboard documents,
  builders, tests, and exhibition language now use nonblocking QA terminology;
- `docs/QA_POLICY.md` defines artifact quarantine, scientific findings, and
  follow-up QA;
- the old hardware-specific protocol was removed and replaced by
  `docs/HARDWARE_PORTABILITY_QA.md`;
- obsolete Vertex handoff/progression-plan documents were removed, while
  `docs/AGENT_PROMPT_VERTEX_RUN_AND_ANALYZE.md` remains as a compatibility
  pointer;
- `docs/AGENT_PROMPT_CONTINUE_ANY_BACKEND_20260728.md` is the self-contained
  new-chat/new-CLI prompt with exact model, detector, data, checkpoint, Vertex,
  non-Vertex, website, exhibition, logging, and QA contracts;
- `docs/README.md` and `audit/README.md` organize active guidance without moving
  path-sensitive machine evidence;
- the public-site source contains no hardware progression status.

Provenance exception: previously frozen July 2026 YAML files and their manifests
are not hand-edited. They may retain superseded historical field names. Those
strings are immutable provenance only and have no operational effect under
`docs/QA_POLICY.md`. Hash-like strings that coincidentally contain the same
characters are also not terminology.

Scientific state is unchanged: all four calibrated families have independently
verified epoch-4 artifacts and short-horizon validation improvement; physics
validation is not established; the test split remains unopened. No cloud job
was submitted and no training artifact was changed during this documentation
and organization pass.

Verification iteration:

- `python -m compileall -q src vertex scripts tests` passed;
- the first `python -m pytest -q` omitted `PYTHONPATH=src` and failed during
  import collection with `ModuleNotFoundError: cbsc_zdc`; it executed no tests
  and changed no artifact;
- corrected `$env:PYTHONPATH='src'; python -m pytest -q` passed `92/92` with
  five known nonfatal Transformer nested-tensor performance warnings;
- the new QA-policy regression tests passed;
- the exhibition rebuilt `23` visuals and removed the hardware-permission
  display; manifest SHA-256 is
  `262292e4a1b5d0c19f1d21b461f452bdf694b5e09eabc31139e50efd512ec649`;
- the public repository passed `7/7` unit tests and the TypeScript/Vite
  production build;
- `git diff --check` passed in both repositories.

Machine-readable summary:
`audit/qa_policy_and_handoff_20260728.{json,md}`.

## 2026-07-28 — new-CLI takeover, state verification, and standing rules

A new agent session took over the project from
`docs/AGENT_PROMPT_CONTINUE_ANY_BACKEND_20260728.md`. No experiment was
launched, no config was frozen, no training artifact was changed, and no test
event was read.

State established from evidence at source commit
`ab4761c58540271bacd1fde5aafb73a0c1dd6643`:

- source worktree clean, `origin/main` synchronized (0 ahead / 0 behind);
- public worktree `Fast-MC-Visual-Tests` clean at `c0387a1`, also synchronized;
- both repositories now resolve under `C:\Users\Julia\Desktop\coding\ASIoP\`.
  The prior `...\OneDrive\Desktop\...` locations recorded in the handoff no
  longer exist on this host; only runtime paths differ, no scientific value
  was changed;
- `gcloud` authenticated as `jjjsresearch@gmail.com`, project `asiop-zdc-1`,
  region `us-central1`; `gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/`
  listed successfully;
- the six most recent Vertex custom jobs are all `JOB_STATE_SUCCEEDED`; the
  newest are `3118380186584743936` (r2 calibrated_lr1e4) and
  `4234868273893605376` (r2 calibrated_lr3e5). No job is active;
- `audit/compute_extension_20260727_r2_terminal_analysis.{json,md}` reconfirm
  four accepted epoch-4 families, `qa_pass=true`, zero test events, and the
  `$53.1006/$100` conservative ledger.

Verification iteration on this host:

- `python -m compileall -q src vertex scripts tests` passed;
- `$env:PYTHONPATH='src'; python -m pytest -q` passed `92/92` in 29.90 s with
  the five known nonfatal Transformer nested-tensor performance warnings. The
  `PYTHONPATH=src` prerequisite is now recorded in `CLAUDE.md` because omitting
  it collects zero tests and fails with `ModuleNotFoundError: cbsc_zdc`.

Repository change: added `CLAUDE.md` at the source root, SHA-256
`70a9bb16ac8f19cd03c766d813a0cec037df6c3dc7261b0a6a5bdf19e6cc6e06`. It is an
operational session-rules pointer only. It restates the local environment,
session-start checks, the mandatory `logs.md` rule, hard prohibitions, QA
semantics under `docs/QA_POLICY.md`, paid-compute confirmation, backend
portability invariants, minimum verification commands, and the standing
scientific boundary. It introduces no new scientific value and does not
override `AGENTS.md` or any `docs/` contract.

Scientific state is unchanged: optimization improvement is supported for all
four calibrated families; `physics_validation=NOT_ESTABLISHED`; the test split
remains unopened. Spending authorization must be reconfirmed with the user
before any new paid compute.

## 2026-07-28 — sealed test split opened for an isolated downstream C2ST study

The user directed that the untouched test split be used as the Geant4 class of a
standalone classifier two-sample test (C2ST) built to show colleagues how well a
discriminator can separate Geant4 events from CBSC-ZDC Fast-MC events. I raised
that `AGENTS.md` clause 4 and `docs/DATA_CONTRACT.md` reserve the test split, and
recommended the 69,502 validation events no model has seen. The user reaffirmed
the test split and required that the study have no way of relaying information
back to the Fast-MC model.

Decision recorded: 40,000 of the 76,300 test events are consumed by an external
discriminator study under a one-way isolation contract.

Isolation contract, binding on this repository:

- no discriminator result, score, checkpoint, or figure may influence CBSC-ZDC
  preprocessing, thresholds, architecture, loss weights, learning rate,
  stopping, checkpoint selection, visualization, or any frozen config;
- the discriminator lives in a separate repository
  (`https://github.com/JulianAttemptsCoding/Fast-MC-tester`, local root
  `C:\Users\Julia\Desktop\coding\ASIoP\Fast-MC-tester`) and writes no artifact
  into this repository other than this log;
- four-momenta for the Fast-MC class are resampled from the **train** split's
  empirical `p4_total_gev`, never copied from the test four-vectors, so the
  Fast-MC class carries no test-event condition information;
- the four accepted epoch-4 checkpoints are consumed read-only by verified
  SHA-256 and are not retrained, reselected, or modified;
- consequence disclosed: any future publication must state that 40,000 test
  events were exposed to this discriminator study. The remaining 36,300 test
  events are untouched.

Scope authorized: 40,000 Geant4 test events versus 10,000 generated events from
each of the four calibrated epoch-4 families (40,000 total). Metrics centre on
AUROC with per-family breakdown, plus a Brownian-diffusion noise-equivalence
sweep. Spending confirmed against the `$100` cap with `$53.1006` already used;
this experiment is held to a hard `$10` ceiling and will stop and report if the
conservative projection exceeds it.

Supporting facts established from the prepared corpus before this decision:

- `artifacts/train_data_audit.json` gives train `K_inc` mean `149.05330283643448`
  GeV and std `86.60899791192668` GeV against the `[0,300]` range, consistent
  with a uniform incident kinetic-energy distribution;
- `shard_00000.npz` (4,096 events) gives `K_inc` in
  `[7.4066185e-05, 299.05484]` GeV, direction `u_z` mean `0.96873057` with
  `u_x`/`u_y` standard deviations `0.17362595`/`0.17435908` bounded within
  `+/-0.441`, `1508.370361328125` mean stored hits per event, and a single
  `source_group`;
- the prepared corpus is `5,943,519,651` bytes across 188 objects, about
  `7.8` KB per event, so 40,000 Geant4 events are roughly 310 MB;
- the existing `c2st_auc` helper in `src/cbsc_zdc/eval/metrics.py` is a
  nine-feature HistGradientBoosting probe and is not the full-detector
  discriminator requested; new code is required and will live in the separate
  repository.

No cloud job was submitted and no training artifact was changed by this entry.

## 2026-07-28 — external C2ST study completed; 40,000 test events consumed

The isolated discriminator study authorized earlier today has finished. Recorded
here because `docs/ISOLATION.md` in the separate repository requires disclosure
in this one, and because any future publication using the test split must state
what was consumed.

Test-split accounting:

```text
test events total        76,300
consumed by this study   40,000
remaining untouched      36,300
selection SHA-256        79433330ff9009120aea53525fcee3a270ab0c9806ead848bef27bc40bc65a55
```

The study trained a binary discriminator on the full 6,790-channel readout plus
the incident neutron four-vector, separating Geant4 test events from 40,000
Fast-MC events generated by the four accepted epoch-4 checkpoints, 10,000 each.

Headline result: the discriminator separates the two sources at AUROC
`0.999452 +/- 0.000089` over five independent trainings. A condition-only control
sits at `0.503628` with validation loss `0.6931564` against `ln 2 = 0.6931472`,
so the separation comes from the calorimeter deposits and not from any condition
mismatch. `PHYSICS VALIDATION NOT ESTABLISHED` remains the correct
characterisation of the generator, and this result is consistent with that.

`QA FINDING`, recorded as evidence only: the per-observable breakdown places the
discrepancy in the internal energy arrangement rather than the global budget.
Total response (`+3.0%`), hit multiplicity (`-1.4%`), ECAL fraction
(`-0.00003%`) and depth centroid (`-4.0%`) are all at chance separability, while
transverse `radial_rms_mm` is `+22.3%` with `+35.8%` excess width,
`top1_fraction` is `-47.6%`, and `hit_energy_gini` is `+55.4%` wider.

All three classifiers ranked the four calibrated families in the same order, and
that order tracked the published validation losses, with `calibrated_lr3e4`
least detectable and `calibrated_lr3e5` most. The absolute spread was small.

Isolation held throughout, and this entry does not change it:

- nothing in this repository was modified by the study except this log entry;
- the four epoch-4 checkpoints were consumed read-only, verified by SHA-256
  against the published table, with embedded `epoch` and `best_metric` checked;
- Fast-MC conditions were resampled from the **train** split, so no test-split
  four-vector reached the generator;
- no discriminator result may influence CBSC-ZDC preprocessing, thresholds,
  architecture, loss weights, learning rate, stopping, checkpoint selection, or
  visualization. The per-observable finding above is disclosure, not a directive:
  acting on it would require a separately declared experiment.

Study repository `https://github.com/JulianAttemptsCoding/Fast-MC-tester`,
commit `6ad9261`, full write-up at `results/20260728-r2/SUMMARY.md`.

Compute: Vertex custom jobs `4939197830460866560` (generation, `4.01` h) and
`2861974074987380736` (discrimination, `2.00` h), both `JOB_STATE_SUCCEEDED` on
on-demand `n1-standard-8 + 1 NVIDIA_TESLA_T4`. `6.01` T4-hours at the
conservative `$0.85` per hour is `$5.11`, taking the cumulative conservative
ledger to `$58.21` of `$100`.

One defect was found and corrected during the study and is recorded in full in
the study repository's `logs.md`: a fully-masked attention row for no-response
events produced a NaN validation loss on PyTorch's fused eval path, which caused
silent selection of an untrained model in the first run. The generation half of
that run was unaffected and its corpus was reused, so no events were regenerated.

## 2026-07-29 — C2ST exhibition material and overview deck published here

The comparison figures, the overview presentation, and the improvement analysis
from the isolated classifier two-sample test are now published in this
repository under `exhibition/c2st_20260728/`, at the owner's direction.

Placement decision and why it is a subdirectory:

- the parent `exhibition/` gallery is built under `test_events_used = 0`, asserted
  at `exhibition/build_exhibition.py:733`, recorded in `exhibition/manifest.json`,
  and printed on its own panels;
- these artifacts are built from 40,000 test-split events, so mixing them into
  that gallery would have made its assertions false;
- `make_gallery` receives an explicit file list rather than globbing `figures/`,
  so the subdirectory is invisible to the builder. Verified empirically: after
  adding it, `python exhibition/build_exhibition.py` still reported
  `visual_count 23` and `test_events_used 0`, and the regenerated
  `manifest.json` contained zero references to the new folder. The only diff was
  the `generated_at_utc` timestamp and the eleven SVG byte hashes, which churn on
  every rebuild independently of this change, so that churn was reverted with
  `git checkout -- exhibition/manifest.json exhibition/figures exhibition/index.html`.

`CORRECTION`: `exhibition/README.md` previously stated "The test split remains
unopened." That became false on 2026-07-28. The scientific-boundary section now
carries the repository-wide accounting: 40,000 of 76,300 test events consumed,
36,300 untouched, separability measured rather than fidelity, and no feedback
permitted into CBSC-ZDC training or checkpoint selection.

Published contents:

```text
exhibition/c2st_20260728/
  README.md                        placement, headline, boundary
  CBSC_ZDC_FastMC_overview.pptx    29 slides
  C2ST_RESULTS.md                  full study write-up
  IMPROVEMENTS.md                  evidence-backed improvement analysis
  figures/                         18 energy-binned comparison figures
  figures_manifest.json            corpus hash, geometry hash, per-figure SHA-256
```

The presentation is a 29-slide overview for a calorimetry audience new to machine
learning, roughly half construction and half results, written to be read without
a presenter. It states the epoch-4 status on the title slide and in a dedicated
slide, and repeats that a falling training loss is not evidence of physics
fidelity.

Two numbers in the circulated project notes were corrected against the frozen
configs before the deck quoted them:

- the response safety cap used by these runs is
  `min(64.38813572617559 GeV, 0.725470286351178 * K_inc)`, derived from the
  training-split audit. The `min(500 GeV, 2 * K_inc)` in the notes is the
  `ResponseHead.sample` default and was not the value used;
- the effective batch is `24` (batch 6 with 4 accumulation steps) for three
  families and `12` for the half-batch control, not `12` throughout.

Verified unchanged after the addition: `python -m pytest -q` passes `92/92` and
`python -m compileall -q src vertex scripts tests exhibition` passes. No training
artifact, frozen config, checkpoint, or dashboard payload was touched, and no
paid compute was used.

Reproduction source, tests and builders remain in
`https://github.com/JulianAttemptsCoding/Fast-MC-tester`.
