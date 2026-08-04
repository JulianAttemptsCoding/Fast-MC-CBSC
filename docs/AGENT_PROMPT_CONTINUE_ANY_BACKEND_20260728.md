# Exact prompt for continuing CBSC-ZDC in a new chat or CLI

Copy everything below the horizontal rule into the new agent. It is intentionally
self-contained and backend-neutral.

---

You are taking over the CBSC-ZDC v2.2 conditional Fast Monte Carlo project.
Treat this message as the controlling technical handoff. Do not assume access to
the previous chat. Work from repository and artifact evidence, and keep the user
informed with concise, evidence-backed updates.

The project owner's active-scope rule index is
`docs/FOCUSED_OPERATING_RULES.md`. Read it first; it collects the binding
DiCOS, credential/token, live-update, split-rigor, and accident-prevention rules
without replacing `AGENTS.md`.

The exact future 4090-trainer/3090-diagnostic state machine, startup order,
per-epoch refresh, internal-dashboard import, public-release boundary, and
failure recovery procedure is `docs/TWO_GPU_PIPELINE.md`. No future run should
be assembled from older command fragments without checking that file.

**Where the work happens now.** Training has moved from Vertex AI to **DiCOS**
at Academia Sinica. Read **section 10a** and `docs/DICOS_BACKEND.md` before
touching that host: they carry the access method, the environment, and a
filesystem contract that is binding (`AGENTS.md` 17-21). In one line: you may
write **only** inside
`/dicos_ui_home/julianjuan/sharedfs/work/IOP/julian/Fast MC CBSC`, and you may
read exactly **one** dataset,
`.../ZDC_ML_20260620/dataset/myTree_20251117_765k_0to300GeV_neutron_All.root`
— everything else in that directory, the `_transformed` variant included, is out
of scope for reading as well as writing.

To start a DiCOS session, ask the user for the DiCOSApp URL, then:

```bash
python scripts/dicos.py auth "<URL>"   # reuses the stored token if the URL has none
python scripts/dicos.py setup          # idempotent; provisions or repairs the pod
```

The Vertex sections below remain accurate as the historical record and as the
description of how the existing checkpoints were produced.

## 1. Find the repositories and establish state

The source repository is:

```text
https://github.com/JulianAttemptsCoding/Fast-MC-CBSC
```

The public visualization repository is:

```text
https://github.com/JulianAttemptsCoding/Fast-MC-Visual-Tests
```

The prior Windows locations were:

```text
C:\Users\Julia\OneDrive\Desktop\coding\ASIoP\Fast MC CBSC
C:\Users\Julia\OneDrive\Desktop\coding\ASIoP\Fast-MC-Visual-Tests
```

Do not hard-code those paths. On another CLI or host, clone both repositories,
set `SOURCE_REPO` and `PUBLIC_REPO` to their actual absolute paths, and resolve
all local paths from those roots.

Before any experiment or edit:

1. enter the source repository;
2. read `AGENTS.md` completely;
3. read `docs/IMPLEMENTATION_GUIDE.md` completely;
4. read `docs/QA_POLICY.md`, `docs/DATA_CONTRACT.md`,
   `docs/MODEL_WALKTHROUGH.md`, `docs/HARDWARE_PORTABILITY_QA.md`,
   `docs/VISUALIZATION_DASHBOARD.md`, **`docs/DICOS_BACKEND.md`** (the active
   training backend, with a binding filesystem contract),
   `docs/GPU_BENCHMARKS.md` (throughput and cost; supersedes `logs.md`), and
   this file;
5. read `CLAUDE.md` if present — it carries the host-specific operating rules
   (paths, `PYTHONPATH=src`, account identities) that this backend-neutral
   document deliberately does not hard-code;
6. inspect `git status --short`, `git log -5 --oneline`, remotes, and
   `git rev-list --left-right --count origin/main...HEAD` in both repositories;
7. read the newest entries in `logs.md` and the newest
   `audit/*_terminal_analysis.{json,md}`;
8. verify from the **process tree**, not from a log, that no unknown job is
   active before submitting work.

Never discard a dirty worktree. Existing changes belong to the user unless
proved otherwise.

## 2. Non-negotiable scientific and QA policy

- QA identifies trustworthy artifacts, failures, and follow-up investigations.
  It does not grant or deny permission to keep training, change hardware, or run
  a separately declared experiment.
- Quarantine an artifact with a schema, geometry, hash, invariant, nonfinite, or
  empty-bin failure. Do not publish, compare, resume from, or initialize from
  that artifact. Preserve the failure and produce a new corrected artifact.
  This does not block independent or corrected work.
- The old permission-style hardware-screening labels are superseded. Immutable
  historical configs and audit files may retain old fields because changing
  them would destroy provenance; they have no operational force.
- Never hand-edit a frozen config. Change a template or builder, generate a new
  unique config, freeze it through the repository tooling, and record both
  hashes.
- Never use `legacy/` as code or data.
- Never use test events for preprocessing, thresholds, architecture, loss
  weights, learning rate, stopping, checkpoint selection, or visualization.
- Structural correctness, decreasing loss, and visually plausible events are
  not Geant4 fidelity.
- Record commands, source commit, dirty-state disposition, input/output hashes,
  environment, GPU, correction, counterexample, costs, and failed attempts in
  `logs.md`. Record decisions and evidence, never private chain-of-thought.
- Ask the user to confirm the current spending limit before new paid compute.
  The last historical ledger was `$53.1006` against an earlier `$100` cap, but
  do not assume that limit or cloud credits are unchanged.

The filename `configs/gates_primary.yaml` and CLI option `--gates` are retained
for compatibility. They mean versioned diagnostic thresholds, not progression
permission.

## 3. Scientific question and current boundary

The model generates a sparse ZDC shower conditioned only on one incident
neutron four-vector. The active target is raw deposited readout energy. Training
uses 0–300 GeV incident kinetic energy; the primary eventual claim domain is
50–250 GeV.

Current evidence establishes:

- production ROOT conversion and content-addressed prepared data;
- detector geometry and graph;
- end-to-end FP32 GPU execution;
- checkpoint, paired-best/last, epoch, and mid-epoch recovery;
- zero structural-invariant failures in accepted runs;
- short-horizon optimization improvement for four calibrated joint families;
- fixed-condition validation-only visual QA and a public site.

It does not establish:

- Geant4 fidelity;
- final three-seed behavior;
- untouched-test performance;
- downstream reconstruction fidelity;
- diversity or memorization acceptance;
- publication-scale timing on a different target backend.

The test split has **never** informed preprocessing, thresholds, architecture,
loss weights, learning rate, stopping, or checkpoint selection. That part of the
seal is intact and must stay intact.

Two disclosed exceptions exist, both read-only and neither feeding any modelling
decision. State them accurately; do not repeat the older claim that the split is
wholly untouched.

1. **External C2ST study** (separate `Fast-MC-tester` repository): exercised
   40,000 of the 76,300 test events under a one-way isolation contract —
   read-only against the four accepted checkpoints, zero feedback into this
   generator. See that repository's `docs/ISOLATION.md`.
2. **In-repository diagnostic, 2026-07-30** — the first direct test-split use
   *inside this repository*. A 2,000-event random draw from the full corpus, at
   the project owner's explicit instruction after being warned twice, included
   **200 sealed-test events (10.0%)**; they appear in the six published figures
   under `exhibition/paired_diagnostics_20260730/`. It fed no preprocessing,
   threshold, architecture, loss-weight, learning-rate, stopping, or
   checkpoint-selection decision. `PHYSICS VALIDATION NOT ESTABLISHED`. See
   `logs.md` and that directory's `README.md`.

**How many test events remain untouched is no longer exactly established.** The
C2ST study consumed a specific 40,000; the 2026-07-30 draw took 200 more from
the full corpus without recording whether they overlap that set. The untouched
count is therefore between 36,100 and 36,300, and the earlier flat claim of
"36,300 untouched" should not be repeated. Computing the overlap from the two
recorded selections would settle it, and should be done before any publication
that depends on the figure.

Neither exception is licence to widen test-split use. Both were scoped, declared
in advance, and disclosed; anything further needs the same treatment. Note also
that `exhibition/build_paired_diagnostics_figures.py` does read test-derived
data, so the general statement elsewhere in this file that the exhibition
builder never touches the test split applies to `build_exhibition.py`, not to
that script.

## 4. Exact detector and geometry contract

The detector has 65 longitudinal layers and 6,790 readout channels:

```text
layer 0:       400 ECAL channels
layers 1–63:  100 HCAL channels each
layer 64:      90 HCAL channels
HCAL total: 6,390
total:      6,790
```

The frozen graph has:

```text
nodes: 6,790
directed edges: 107,920
geometry SHA-256:
e22d4cfb1e9293a33dd13151587910268ba64cd8efbcdb7a835a7442f2edcb4b
```

Canonical channel identity is:

```text
(subdetector, layer_id, cell_id)
```

Node features, in order:

```text
x_norm, y_norm, z_norm, layer_fraction, is_ecal, is_hcal
```

Edge features, in order:

```text
dx_norm, dy_norm, dz_norm, distance_norm, edge_type
```

Positions are in millimetres and energies are in GeV. The production generator
vertex is fixed at:

```text
[-917.4075317382812, -30.0, 35488.90625] mm
```

HCAL contains ganged readouts. A channel’s frozen position is the unweighted
centroid of its distinct stable physical positions, never a hit-frequency
weighted centroid. Exact multiplicity evidence:

```text
ganged channels: 2,400
maximum physical positions per channel: 4
multiplicity histogram:
  1 position: 4,390 channels
  2 positions: 1,950 channels
  3 positions:   444 channels
  4 positions:     6 channels
```

Do not reconstruct geometry from prose. Use the hashed geometry artifacts and
manifest.

## 5. Exact data locations, identity, and structure

### Raw production ROOT

The large local ROOT copy was deliberately deleted after cloud identity and
checksum verification. The canonical source is:

```text
gs://asiop-zdc-1-zdc-reco-us-central1/data/myTree_20251117_765k_0to300GeV_neutron_All.root
generation: 1783683550292251
size: 25,022,001,408 bytes
CRC32C: lCVUvQ==
SHA-256:
b7c666040e42352e158a9a3f78158d147cb2e056c6c88248d892c956f5c7b533
tree: myTree
entries: 764,940
```

Do not redownload it to the user’s old computer unless absolutely necessary.
Prefer cloud-side copies, streaming, or a backend-local durable filesystem.

### Canonical prepared production artifacts

```text
gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/prep-20260724-r5
```

Verified content:

```text
187 NPZ shards
764,940 events
shards 00000–00185: 4,096 events each
shard 00186: 3,084 events
dataset_manifest SHA-256:
5a6d963247091e91c0787dd763b46e3b1189f62785d9cab1d8fda4e76ca08096
```

Each shard contains:

```text
p4_total_gev       float32 [events, 4]
kinetic_energy_gev float32 [events]
event_id           int64   [events]
source_group       int64   [events]
event_ptr          int64   [events + 1]
cell_index         int32   [stored_hits]
cell_energy_gev    float32 [stored_hits]
```

For event `e`, sparse hits are
`event_ptr[e]:event_ptr[e+1]`. `cell_index` addresses the fixed 6,790-node
geometry.

Split counts:

```text
train:      612,482
validation:  76,158
test:        76,300
```

The short joint-training experiments used a fixed bounded bank:

```text
train:      26,624
validation:  6,656
test:            0
```

The fixed visual bank uses 50 validation conditions and five independent
Fast-MC draws per condition. Its selection SHA-256 is:

```text
f70529198aa9575cd2ebc816fd0800ed5a1a3dcd918dab3845b5dc5d85dc59b6
```

Target semantics are raw, non-sentinel readout deposits with threshold 0 GeV.
The stored Geant4 event-energy reference includes sentinel non-readout deposits,
so two closures are tracked separately. Sentinel evidence:

```text
events with excluded sentinel energy: 738,898
excluded sentinel energy total: 13,251.328791066537 GeV
maximum excluded sentinel energy/event: 1.647373832954901 GeV
maximum preparation closures: <= 1.3501e-13 GeV
conversion rejection counts: all zero
```

## 6. Condition and model architecture

The raw condition is:

```text
p4_total_gev = [E_total, p_x, p_y, p_z]
```

Use neutron mass:

```text
m_n = 0.93956542052 GeV
K_inc = E_total - m_n
u = p / |p|
```

The deterministic five-value network input is:

```text
[log(1 + K_inc/100 GeV), u_x, u_y, u_z, log(E_total/1 GeV)]
```

The current condition encoder maps this to 128 dimensions.

The stochastic hierarchy is:

1. Bernoulli visible/no-response hurdle;
2. mixture model for total detector response;
3. categorical first-positive-layer model;
4. Bernoulli active-layer model;
5. conditional flow matching for the layer-energy profile;
6. categorical per-layer hit counts;
7. geometry-aware graph support scores;
8. one Gumbel-Top-k draw per active layer, without replacement;
9. conditional share flow for energy fractions on selected cells;
10. exact softmax budget decoder.

The decoder enforces exact zeros outside selected support, exact requested hit
counts, nonnegative cell energies, exact layer budgets, and event-energy closure
within floating tolerance.

Current joint model dimensions:

```text
condition_dim: 128
hidden_dim: 96
response_hidden: 192
response_components: 4
profile_hidden: 128
count_hidden: 192
graph_blocks: 3
attention_heads: 4
attention_layers: 2
layer_context: bidirectional
dropout: 0
```

The calibrated nine-loss weights are:

```text
visible:      2.574416711989658
response:     0.16090104449935363
first_layer:  2.159450729859089
active:       0.5367704371463009
profile_flow: 0.16090104449935363
count:        0.16090104449935363
support_bce:  1.3241075363035668
support_rank: 1.4775912102536604
share_flow:   0.44496024094966563
```

Training stage order for staged experiments is:

```text
response -> profile -> count -> support -> share -> joint
```

Follow the shared-condition-encoder freezing/initialization rules in
`docs/IMPLEMENTATION_GUIDE.md`.

Loss interpretation is important:

- minimize the frozen weighted aggregate on the declared split;
- an NLL component can legitimately be negative; more negative is better;
- zero is not a universal optimum for NLL;
- do not add an absolute value or L2 wrapper merely to make a component
  nonnegative, because that changes the statistical objective;
- investigate a rising component through its raw definition, weight, gradients,
  validation trend, and downstream samples. Any changed loss is a new declared
  experiment.

Current accepted runs used FP32. A prior mixed-precision attempt produced
nonfinite gradients. That is historical evidence about that configuration, not
a permanent hardware rule. Any mixed-precision retry must be a separately named
bounded experiment with finite-gradient and checkpoint-reload QA.

## 7. Checkpoint lineage

**For the current state, read §7b. This section is the origin of the lineage,
not the present.** Everything the project now has descends from these epoch-4
Vertex artifacts; the accepted checkpoints today are many epochs further on and
were produced on DiCOS. The published set and the live run are in §7b.

All four calibrated families have verified epoch-4 artifacts. Exact validation
losses and checkpoint hashes at that point:

| Family | LR / effective batch | Epoch | Validation loss | Best checkpoint SHA-256 | Last checkpoint SHA-256 |
|---|---:|---:|---:|---|---|
| `calibrated_lr3e5` | `3e-5 / 24` | 4 | `4.89732698326055` | `949c8e0e199def5eba8cc6cc3f7be7d76aa9e110297fc4382b0e2f82c3b2e064` | `83758012275d20a4a23c1495ccc30e240913c95a416f3fb31c0b5d472c10aaf8` |
| `calibrated_lr1e4` | `1e-4 / 24` | 4 | `4.827105448151752` | `f4469a912275480507f758c9bdcd98bc58e94c459e50f5c73d9916446bebf945` | `0a9a229495004681e2df9ebe5099889e40de5af2def05eb2cf48098f0ccb8915` |
| `calibrated_lr3e4` | `3e-4 / 24` | 4 | `4.738041260930141` | `3f1022b87361b8a14d9f8432273dcd6c72f6a5e599c1be1575e7f37f4014803d` | `42782827de374dedcbba50a784460833ad16129c474f98553622b39d6467720a` |
| `calibrated_lr1e4_halfbatch` | `1e-4 / 12` | 4 | `4.8450291584386305` | `d14458bba3fcfbc35d5c3da0b106735fc8041ea2c191969ccb0b86eb484d91ca` | `999d4e3a49c18941a20eeb001a01f56d2d77a2e5e3147e940e0d8347f0d475d4` |

Cloud outputs:

```text
gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/compute-extension-20260727-r2-calibrated-lr3e5-output
gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/compute-extension-20260727-r2-calibrated-lr1e4-output
gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/compute-extension-20260727-r1-calibrated-lr3e4-output
gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/compute-extension-20260727-r1-calibrated-lr1e4-halfbatch-output
```

Latest two custom/pipeline jobs:

```text
calibrated_lr3e5:
  pipeline 3939574635045060608
  custom   4234868273893605376
calibrated_lr1e4:
  pipeline 8388568116933689344
  custom   3118380186584743936
```

The last training container identity was:

```text
us-central1-docker.pkg.dev/asiop-zdc-1/cbsc-zdc/cbsc-zdc@sha256:8b4a94c0c748febdb059b1302503d280498ddd1360b595a90e0a6c9b0999048f
```

Do not assume a `best.pt` filename means “epoch-4 last.” Verify the file’s
embedded selected metric, epoch, paired best/last semantics, and hash.

The T4 trajectories were non-monotonic: some epoch 3 losses regressed, then
epoch 4 recovered and improved. Over the full two-epoch extensions, all four
families improved their validation objective. This supports optimization
progress, not physics fidelity.

### 7a. HISTORICAL: the six-epoch continuation started 2026-08-01

**Completed long ago; kept for the reasoning, not the state.** This describes
`dicos-r3`. Its declared intent — "continue the winner alone with real early
stopping restored (patience 3)" — was **overturned by evidence** and must not
be carried forward: see the patience rule in §7b, which says the opposite and
says why.

All four families are being continued **six further epochs each** on the RTX
4090 pod — absolute epochs 5..10, resuming from the `last.pt` in the table
above, on the same 26,624/6,656 bank. Frozen configs live at
`prep/configs/frozen_<family>_dicos-r2.yaml`; the templates are generated by
`scripts/build_dicos_continuations.py` and are committed under
`configs/templates/dicos_continuation_20260801/`. The runner is
`scripts/dicos_train.py`, the DiCOS twin of `vertex_stage` (same validation,
hash-verified resume, per-epoch snapshots, postflight).

One declared deviation for this phase only: `early_stopping_patience` is
widened from 3 to 6 so that no family can stop early during a comparison whose
whole purpose is running all four over the *same* six epochs. The intent is
that the family with the largest start-to-end validation improvement is then
continued alone with **real early stopping restored (patience 3)**. An agent
picking this up must not carry the widened patience into that continuation.

Two things this phase does **not** establish, regardless of outcome: anything
about Geant4 fidelity, and anything about governed-test performance. The phase
used the pilot bank and zero test events; the separately disclosed historical
test exceptions and exact remaining-count uncertainty are in §3.

### 7b. STATE VERIFIED 2026-08-04T16:32:58+08:00 — read this before doing anything

**Nothing is training or generating. Both GPUs are idle, proved from their
process trees.** The RTX 4090 reported `0 MiB / 0%`; the RTX 3090 reported
`1 MiB / 0%`; self-match-safe `/proc` scans found no trainer, diagnostic
producer, or diagnostic consumer on either. The shared checkout is `07c1dda`;
the updated 4090 pipeline suite passed 21 tests and immutable artifact
verification passed 18/18. The project owner has explicitly requested
organization and QA only: do not start or resume training in this phase.

`dicos-p10` died at `2026-08-04T03:13:56Z` after completing epochs 39 and 40:

```text
epoch 39  validation 4.663274642140066  LR 7.631742512825513e-06
epoch 40  validation 4.702765165275920  LR 1e-06
EXIT=1    wall 1742.222 s
RuntimeError: epoch 40 visualization generation failed structural invariants
```

Neither epoch beat the inherited `4.635219681489869`, so no accepted standing
or public snapshot changed. `last.pt` was written before visualization and is
complete at epoch 40, SHA-256
`4a7583cce169a1cdac206aa1d03a50e41a05444a5172218dbbb89b3227ed1011`.
Mechanical resumability is not acceptance: the artifact remains quarantined
until the diagnostic contract is decided and the checkpoint is re-audited.

The replay found one failing validation condition of fifty: selection position
36, dataset index 894, `K=192.0687255859375 GeV`, generated response
`33.164573669433594 GeV`, layer closure
`2.6702880859375e-05 GeV` against the frozen absolute `2e-05 GeV`. Event
closure was `3.814697265625e-06 GeV`; every finite, nonnegative, support, and
count check was exact. The evidence is preserved in
`audit/p10_failure_20260804_viz_invariants.json`.

This exposes a diagnostic-design issue: an absolute closure tolerance does not
scale with float32 summation magnitude. **The threshold has not been changed.**
Changing it requires the owner's explicit decision and a new frozen diagnostic
contract. Making required visualization nonfatal is prohibited by `AGENTS.md`
23 and `docs/VISUALIZATION_DASHBOARD.md`.

```bash
PYTHONPATH=src python scripts/dicos.py exec \
  'nvidia-smi --query-gpu=name,memory.used,utilization.gpu --format=csv,noheader; \
   ps -eo pid,etime,args | grep "[d]icos_train" || echo NONE'
DICOS_CONFIG=$HOME/.dicos/config_3090.json PYTHONPATH=src \
  python scripts/dicos.py exec \
  'nvidia-smi --query-gpu=name,memory.used,utilization.gpu --format=csv,noheader; \
   grep -a -l dicos_$(echo train) /proc/[0-9]*/cmdline 2>/dev/null || echo NONE'
```

**Standings — lowest verified validation loss per calibrated family.**

    family                      best val    at epoch   run          published
    calibrated_lr3e4            4.597152    22         dicos-p7     yes  <- best
    calibrated_lr1e4            4.635220    38         dicos-p9     yes  (p10 continuing)
    calibrated_lr1e4_halfbatch  4.673036    21         dicos-p7     yes
    calibrated_lr3e5            4.843471     8         dicos-r3     yes

The lr3e4 lead over lr1e4 is **0.038068**. Run-to-run resolution is about
**0.02** (§7e), so the lead is real but no longer commanding — it was 0.105331
two phases ago. `calibrated_lr1e4` has closed most of the gap by being given
many more epochs (39 against 23), which is the open question p10 tests.

**Checkpoint identity for every currently accepted artifact.**

| family | run | best epoch | best.pt SHA-256 | last.pt SHA-256 |
|---|---|---:|---|---|
| `calibrated_lr3e4` | `dicos-p7` | 22 | `31802b9fcdde49a7369786b028b17ff1b09fd22c6587c118c9d41783b9a49bfb` | `eb533f18f08b1080ea367d75e77fb560d3957a2368a70d12e26e57191608460f` |
| `calibrated_lr1e4` | `dicos-p9` | 38 | `89cae275c092cecca5025159d766b920a412f96e83b4438b68bc1e6c4bd46b2a` | `98540e3dca3997ddaba34f5a1f964dd57a0a67ae9c3616fddaf4add7f06eb853` |
| `calibrated_lr1e4_halfbatch` | `dicos-p7` | 21 | `ffab832ac4798ca75bde5dd5e687ce3f634ab32b6c88f40169d3db59f0ead9b1` | `79bcdeac0d4550d230f2de5eb12e15be9ba73cf872802ac9f3862e2bf29aa2b9` |

`dicos-p10` frozen config `4e246713113ac979edcd60f32990930bdb355645bf3d2d5b3c28aa215ffb7e2c`,
template `657131348621642107544803dd19ed6a34ac688199e5c37bb74b666293857ef2`,
resuming from the p9 epoch-38 best on both the `resume_from` and
`resume_best_from` slots (one file, both slots, hash-verified).

**The public site is current.** All four families publish their lowest verified
checkpoint; the last published change was `calibrated_lr1e4` at epoch 38. When
p10 produces a better epoch, republishing that family is required by the stated
policy — see §14 for the exact procedure and the current snapshot IDs.

**Two findings from p8/p9 that change how continuations must be built.**

1. **Early-stopping patience must scale with the horizon; it cannot be a
   constant.** Run `dicos-p8` asked for 24 epochs and stopped after 6. Patience
   6 counted staleness against an *inherited* best that had been reached at the
   end of an anneal, at learning rate 1e-6. Restarting the scheduler to peak
   makes the model worse by construction for several epochs before it can be
   better, so the counter is already half spent before the run has a chance.
   Set patience to the full horizon of the run unless you are deliberately
   testing early stopping. `dicos-p9` and `dicos-p10` both use patience 24 for
   24 epochs.

2. **Continuing a spent cosine beats restarting it.** `CosineAnnealingLR` is
   periodic in `2*T_max`, so a scheduler resumed past its first anneal climbs
   smoothly back toward peak and re-anneals — SGDR without the extra machinery.
   `dicos-p9` set `restart_scheduler_on_resume: false` and resumed from the
   *best* checkpoint rather than a later, worse `last.pt`. It improved
   **0.067238** over 24 epochs, against p8's zero over the same nominal horizon.
   `--no-restart-scheduler` on `scripts/build_final_continuation.py` is what
   sets this.

**Resuming from best re-runs an epoch number.** p10 resumes from epoch 38, so
its first epoch is 39 — and p9 already wrote an epoch 39 on a different branch.
This is expected and has a required consequence: when p10's history is merged
into `exhibition/data/continuation_history.csv`, **p9's epoch 39 row must be
dropped**, because it is no longer on the live lineage. The same thing happened
between p6 and p9 at epoch 16 and was caught by the duplicate-epoch guard in
`exhibition/build_continuation_loss_figures.py`. Do not silence that guard;
resolve which branch is live and drop the other row.

**Current direction — what this phase is trying to do.**

The goal has not changed: take the strongest calibrated family and continue it
until validation stops improving, on the 26,624/6,656 pilot bank, so that a
single best generator exists to carry into the next stage.

The selection rule has been revised once, by evidence, and a new agent needs the
reasoning rather than the conclusion:

* The four families were first compared over identical absolute epochs 5..10
  (`dicos-r3`). The user's rule was **largest improvement from the start of the
  continuation to its end**, which chose `calibrated_lr1e4_halfbatch`
  (+0.134200).
* That family then failed to beat its own epoch-10 checkpoint in two solo
  continuations, and its later `dicos-p7` extension reached only 4.673036.
* `calibrated_lr3e4`, third on improvement but holding the lowest absolute
  loss, went on to the best result in the project.

The improvement criterion measured how far a family had climbed out of its own
restart, not how good it was. **Absolute validation loss has been the better
predictor.** Say this to the user rather than silently switching rules — the
original criterion was theirs.

The unresolved question behind p10 remains: can `calibrated_lr1e4`, which
improved 0.067238 across p9, eventually beat **4.597152**? P10 did not answer it:
the run died in the cosine trough before the learning rate climbed again. Do
not launch a successor until the closure-tolerance decision, re-audit, new
unique run tag, frozen config, and remaining-horizon patience are explicit.

Two boundaries that do not move whatever the outcome: this is optimization
evidence on the pilot bank, and it establishes nothing about Geant4 fidelity or
test performance. No new test events may be used; preserve the two previously
disclosed read-only exceptions and their unresolved overlap.

**GPU comparison — measured; `docs/GPU_BENCHMARKS.md` is the single source of
truth and this summary must not be re-derived from `logs.md`.** Identical work,
batch 6, six full epochs per card:

    RTX 4090                  649.83 s/epoch   10.83 min   5.540 epochs/h   no published rate
    RTX 3090                 1168.88 s/epoch   19.48 min   3.080 epochs/h   NTD$158/board-day
    80 GB datacentre GPU      990.17 s/epoch   16.50 min   3.636 epochs/h   NTD$346/board-day

Ratios: datacentre/4090 = **1.524**, 3090/4090 = **1.799**, 3090/datacentre =
**1.180**. The 3090 is **1.855x more cost-efficient per epoch** — 2.19x cheaper
per board-day against only 1.180x slower. A 24-epoch run costs roughly USD
$1.60 on the 3090. **Cost is not a real constraint at this scale; wall-clock and
GPU availability are.**

Two earlier figures in `logs.md` are withdrawn and must not be reused: "the 4090
is 3.2x the datacentre card" (that card had been sampled while two trainers
shared it; the true solo ratio is 1.524x), and the NT$395/NT$865 board-day
prices (from a stale, self-contradictory 2022 mirror; too high by 2.5x).

**As of 2026-08-04 the fleet is two cards: the RTX 4090 and the RTX 3090.** The
user has retired the 80 GB datacentre pod and it will not be used. Its numbers
above are kept because they were measured and because they are what withdrew the
3.2x claim, not because that hardware is available. Do not plan around it.

**Run history for this phase — read before interpreting any `_runs` directory.**

| tag | fate |
|---|---|
| `dicos-r1` | Aborted. Launched with `epochs: 6`, which is an **absolute** target, so it ran one epoch per family with the cosine annealed to `min_learning_rate` across it. Archived at `_runs/aborted_r1_epochs_misread/`. |
| `dicos-r2` (wave2) | Stopped after one epoch to free the GPU while a second pod was evaluated, then archived at `_runs/aborted_r2_slow_loader/` because it ran under the slow loader and an earlier commit. |
| `dicos-r3` | Complete, all four families, epochs 5..10, all QA PASS. The comparison the first winner was chosen from. |
| `dicos-final` | half-batch epochs 11..13, patience 3. Stopped by early stopping with **no improvement** on 4.710829. Patience 3 cannot survive a high-LR scheduler restart; not a statement about the model. |
| `dicos-final-r2` | half-batch epochs 11..16, patience 6. Completed, `EXIT=0`, QA PASS, ended 4.715659 — **did not beat** its own 4.710829. |
| `dicos-p6` (lr3e4) | Complete, QA PASS. 4.605498 at epoch 15. Superseded by `dicos-p7`. |
| `dicos-p6` (lr1e4) | Complete, QA PASS, on the datacentre card. 4.702458 at epoch 15, a real +0.063673. Its epoch 16 row is **off the live lineage** — p9 branched from the epoch-15 best — and was dropped from `continuation_history.csv`. Two earlier discarded attempts exist: one crashed at epoch 12 (`_runs/aborted_dcgpu_crash/`), one wiped by a stray writer. |
| `dicos-p7` (lr3e4) | Complete, QA PASS, 4090, epochs 17..22. **4.597152 at epoch 22 — the best result in the project.** Improvement +0.008346, which is *inside* the ~0.02 resolution, so this family has effectively plateaued. |
| `dicos-p7` (halfbatch) | Complete, QA PASS, 3090, epochs 17..22. 4.673036 at epoch 21, +0.037793 — real. |
| `dicos-p8` (lr1e4) | Complete but **stopped at 6 of 24 epochs**, no improvement. Scheduler restarted to peak, patience 6 against a best reached at LR 1e-6. The cause of the patience rule above. Not a statement about the model. |
| `dicos-p9` (lr1e4) | Complete, QA PASS, 4090, epochs 16..39, 24/24 invariants, postflight `pass: true`, wall 18,238.8 s, 26,640 updates. **4.635220 at epoch 38, +0.067238 — the largest single-run improvement of the phase.** |
| `dicos-p10` (lr1e4) | **Failed and quarantined after epoch 40.** Epochs 39 and 40 completed and neither improved on the p9 parent. Required epoch-40 visualization found one layer-closure residual `2.6702880859375e-05 GeV` against the frozen absolute `2e-05 GeV`; `last.pt` survived but may not be reused until the diagnostic decision and corrected re-audit. |
| quarantined | `_runs/quarantine_duplicate_writer/` — an lr3e4 attempt with two concurrent writers. Never resume, compare or publish from it. |

Do not compare a number from an aborted run against a completed one.

### 7c. Driving several pods at once

All pods mount the **same** CephFS workdir. Credentials live one file per pod
and are selected with `DICOS_CONFIG`; without it the client uses
`~/.dicos/config.json`, which is the 4090.

| pod | port | credentials file | venv | role |
|---|---|---|---|---|
| RTX 4090 (primary) | 32545 | `~/.dicos/config.json` | `.venv` | training |
| RTX 3090 | 32705 | `~/.dicos/config_3090.json` | `.venv_3090` | per-epoch diagnostics (§7d) |

**As of 2026-08-04 these two are the whole fleet.** The 80 GB datacentre pod
(port 31785, `~/.dicos/config_dcgpu.json`, `.venv_dcgpu`) has been retired by
the user and will not be used; its credentials file may still exist locally and
is dead. Do not plan work that needs a third card without asking.

```bash
DICOS_CONFIG=$HOME/.dicos/config_3090.json PYTHONPATH=src \
  python scripts/dicos.py exec 'nvidia-smi'
```

**Pod images differ.** The 3090 pod has no `ps`, no `pkill`, no `free`. Scan
`/proc` from the pod's own venv interpreter instead — and build the search
token at runtime, because a probe whose command line contains the string it is
searching for **matches itself**:

```python
needle = "dicos_" + "train"          # never write the literal
mine = {os.getpid(), os.getppid()}   # the heredoc's shell is a match too
```

That is not hypothetical: a self-matching probe once reported a phantom trainer,
and the `kill -9` that followed killed the probe's own process group.

**Access URLs.** Tokens are deliberately **not** written here: this file is
committed and pushed, and a token in the repository is pod access for anyone
who can read it.

    RTX 4090   http://scale-k8s-master01.twgrid.org:32545/
    RTX 3090   http://scale-k8s-master01.twgrid.org:32705/

> **Read `POD_ACCESS.local.md` in the repository root for the tokens.** It is
> untracked and git-ignored on purpose, so it exists only on the user's machine
> and will **not** arrive with a fresh clone. It carries the launch URLs with
> tokens, the `DICOS_CONFIG` mapping, and the procedure for refreshing a token
> when a pod moves. If it is absent — a different machine, a new clone — ask the
> user for the launch URL, or recover the token from the pod itself (§10a,
> "Recovering the token"). Never copy its contents into a tracked file, a commit
> message, or `logs.md`.

Keep the ports in the table above in step with that file whenever a pod moves;
this file carries ports, that file carries secrets.

**Keeping these current.** DiCOS has issued a *stable per-user* token, so when
a pod is relaunched usually only the **port** changes and the token still
works. To re-point at a moved pod:

```bash
DICOS_CONFIG=$HOME/.dicos/config_3090.json PYTHONPATH=src \
  python scripts/dicos.py auth "http://scale-k8s-master01.twgrid.org:<new-port>/"
```

`auth` accepts a URL with or without a token, reuses the stored one when the
URL carries none, verifies against the server before saving, and saves nothing
on failure. If the token really has changed, pass it explicitly as a second
argument, or recover it from a JupyterLab terminal with `jupyter server list`
(§10a has the notebook-cell variant). **Whenever a port or token changes here,
update the table above in the same commit** — a stale entry sends the next
agent to a dead pod or, worse, to the wrong one.

To add a pod, copy an existing credentials file and change `base_url` and
`token` only. Every other field encodes the filesystem contract — `workdir`,
`data_file`, `forbidden_paths` — and must not be widened.

**Never run `dicos.py setup` on a second pod.** It rebuilds the shared
`.venv`, which belongs to whatever is training. Build a per-pod venv instead —
`_setup/build_venv_dcgpu.sh` is the pattern: a fresh directory name, then
asserts that `sys.prefix` is the venv and `site.ENABLE_USER_SITE` is false
*before* any install, with `PIP_USER=0` and `PYTHONNOUSERSITE=1` exported. That
combination exists because without it a broken venv silently redirected 5 GB of
torch into `$HOME`, outside the one writable directory.

**Traps that cost real time today, all of them mine:**

* `dicos.py start` output is easy to swallow with a pipeline. **Never re-issue a
  start because the output looked empty** — check the process tree
  (`ps -eo pid,ppid,args | grep dicos_train`). Counting `START` lines in the log
  or looking at the pid file does **not** distinguish one wrapper from two; both
  write the same paths. `scripts/dicos_train.py` now takes a run-directory lock
  (`src/cbsc_zdc/training/run_lock.py`) so a second writer is refused outright,
  but the habit still matters.
* **Never move or delete a run directory while a process holds it.** Paths are
  resolved per write, not held open, so a moved directory makes the live process
  start writing to whatever now occupies that path — which is how the
  datacentre-GPU trainer ended up writing into the 3090's run directory.
* The datacentre-GPU and 3090 images have **no `ps`, `pkill`, or `free`**, and
  the datacentre pod's
  default `python3` predates 3.12 (no nested same-quote f-strings). Use each
  pod's venv interpreter and `_setup/kill_bench.py` or `_setup/kill_dcgpu.py`, which scan `/proc`.
* `pkill -f <pattern>` matches the probe shell's own command line and kills the
  probe; the resulting `__DICOS_EXIT__-15` is your own command dying.
* `dicos.py stop` kills the wrapper, not the trainer. Verify the GPU is actually
  released before assuming a run has ended.

**`CBSC_ZDC_SHARD_CACHE=0` is set for this wave.** It makes each loader worker
hold all 187 shards resident instead of 4. This is a transport property, not a
scientific one, and it was admitted only after proving byte-identity on the
production corpus: 400 samples read through both cache sizes give 0 tensor
mismatches and the same SHA-256 over all sample bytes,
`4ba4d7a713c9c1a574a5f27857a5fe46d8fe1e4a7fa8f456692ea4d367507c9b`
(`_setup/cache_equivalence.json`; contracts in `tests/test_shard_cache.py`).
Shard verification still happens on every load, so each shard is verified once
per worker rather than thousands of times — never zero times. The value is
recorded in each run's `environment.json`. `num_workers` was deliberately left
at 4, since the portability contract lists it as invariant.

### 7d. Per-epoch diagnostics — the producer/consumer pipeline

This did not exist when the rest of this document was written. It is how every
"metric vs epoch" figure and every distribution number after `dicos-p9` is
produced, and it runs **on the second GPU while the first one trains**.

Three pieces:

| piece | where it runs | what it does |
|---|---|---|
| `scripts/dicos_diag_producer.py` | same pod as the trainer | admits `checkpoints/last.pt` only after its copied epoch/hash match the post-visualization progress marker, then atomically queues it under `_diag/<run-tag>/queue`. Enforces one producer per tag and writes STOP/failure evidence from the launcher-owned `EXIT=` state. |
| `scripts/dicos_diagnostics.py --watch-dir` | the other pod's GPU | drains the queue, generates 4,000 validation events per checkpoint, atomically writes only QA-passing `_diag/<run-tag>/metrics_epoch_NNNN.json`, and quarantines conflicts/failures. |
| `scripts/refresh_continuation_outputs.py` | your workstation | hash-verifies metrics/history/visualizations, enforces validation-only contracts, updates the internal dashboard, rebuilds loss/metrics versus epoch and validation-loss-best-so-far counterparts, rebuilds both exhibitions, and writes epoch audit twins. It flags but does **not** silently publish a new public best. |

```bash
# producer, on the training pod
PYTHONPATH=src python scripts/dicos.py start \
  'cd "<WORKDIR>" && PYTHONNOUSERSITE=1 .venv/bin/python \
     repo/scripts/dicos_diag_producer.py \
     --run-dir "_runs/<family>_<tag>" --wrapper-log "_runs/<jobname>.log" \
     --run-tag "<tag>"' --name <tag>prod

# consumer, on the other pod
DICOS_CONFIG=$HOME/.dicos/config_3090.json PYTHONPATH=src python scripts/dicos.py start \
  'cd "<WORKDIR>" && PYTHONNOUSERSITE=1 PYTHONPATH=repo/src .venv_3090/bin/python \
     repo/scripts/dicos_diagnostics.py --n-events 4000 --selection-seed 20260803 \
     --watch-dir _diag/<tag>/queue --output-dir _diag/<tag> --device cuda' --name <tag>diag
```

Six rules this pipeline earned the hard way. Each corresponds to a fault that
actually occurred; none may be relaxed.

1. **Namespace by run tag, on the host as well as in the repo.** `_diag/` was
   flat, and p9 silently overwrote p8's `metrics_epoch_0017..0022.json`. p10
   would have overwritten p9's epoch 39 the same way. Both `_diag/<tag>/` on
   the host and `exhibition/data/diagnostics/<tag>/` in the repo are namespaced
   now. Do not collapse either back.
2. **Name the queued checkpoint by the epoch inside the file**, never by the
   report that triggered the copy. `last.pt` is overwritten every epoch, so a
   slow copy can otherwise label epoch N+1's weights as N.
3. **Drain the queue before honouring `STOP`.** The consumer's watch loop
   checks `STOP` *and* an empty pending list. An earlier version exited on
   `STOP` alone and would have dropped the last three epochs.
4. **Take the energy-bin edges from the checkpoint's own frozen config**, and
   assert they cover the sampled kinetic range. A hard-coded top edge of 225
   silently dropped every event in the 225–250 GeV bin. `dicos_diagnostics.py`
   now raises rather than dropping, and reports `events_outside_energy_bins`
   and `empty_energy_bins`.
5. **Cap the pooled cell spectrum at 200,000 values** (`POOLED_SPECTRUM_CAP`).
   `wasserstein_1d` on ~6.4M pooled values does not return in usable time — one
   attempt burned 700 s of CPU and was killed. Per-event metrics are uncapped
   and `src/cbsc_zdc/eval/metrics.py` is untouched; the cap is a deterministic
   subsample in the diagnostic driver only.
6. **A checkpoint is accepted only by the post-visualization marker.** The
   trainer writes `last.pt` before required visualization QA, so checkpoint
   existence alone can expose a failed epoch. The producer now requires the
   matching `progress_epoch_NNNN.json` epoch and checkpoint SHA-256 before it
   queues anything. Never weaken this to file-exists polling.

**The diagnostics never touch the test split.** The dataset is constructed with
`split="validation"`, which filters on the split code at construction, and an
independent assertion re-counts the drawn events and raises if any train or test
event is present. Every metrics file records `split_counts` so the claim is
checkable after the fact, not just asserted.

**What the diagnostics say, as of `dicos-p9` epoch 38.** These are honest
negative results and must travel with any favourable loss number:

* **C2ST AUROC sits at 0.77–0.92 for every epoch measured** and never
  approaches the 0.65 gate threshold. A classifier separates Fast-MC from
  Geant4 easily at every checkpoint the project has produced. The validation
  objective improving has not moved this.
* **Fast-MC produces about twice as many zero-response events** as Geant4 —
  0.015–0.023 against 0.0097.
* **The loss and the distribution metrics disagree about which epoch is best**
  (p8: 21 against 22; p9: 33 against 38). Checkpoint selection follows the
  validation loss, as declared. Do not switch selection rules to whichever
  metric flatters a run.
* **Share flow is 42.2% of the weighted objective** and the largest single
  source of improvement.
* **The pilot bank is 4.3% of the available training data** — the largest
  untested lever in the project, and untouched so far.

### 7e. Numbers you should not re-derive

**Run-to-run resolution is about 0.02** in validation loss, and hardware
nondeterminism is **not** its source. A controlled replicate — the 3090
benchmark run configured identically to the datacentre run, same seed, same
parent checkpoint — diverged by 0.0136 at epoch 11 and reconverged to
**5.8e-6** at the annealed endpoint. Two cards, same answer. Treat differences
below ~0.02 between separate runs as noise, and do not attribute them to
hardware.

## 8. Repository map and where to look

```text
AGENTS.md
  mandatory operating contract
logs.md
  chronological human-readable evidence and decisions
src/cbsc_zdc/
  active data, geometry, model, training, evaluation, CLI, and cloud code
configs/
  schema, loss, diagnostic-threshold, templates, and immutable frozen configs
scripts/
  builders, freezers, verification, analysis, visualization sync, and helpers
vertex/submit_custom_job.py
  Vertex custom-job launcher
docs/
  data/model/evaluation/runbook/QA contracts and this handoff
audit/
  machine-readable verification, terminal analyses, failures, and provenance
dashboard/
  full localhost Event Observatory and compact synchronized data
exhibition/
  presentation-ready figures, builder, hashes, and gallery
tests/
  executable source contracts
paper/ and references/
  specification and research source register
legacy/
  provenance only; never import or train from it
```

Start code tracing at:

```text
src/cbsc_zdc/models/system.py
src/cbsc_zdc/models/response.py
src/cbsc_zdc/models/profile.py
src/cbsc_zdc/models/counts.py
src/cbsc_zdc/models/support.py
src/cbsc_zdc/models/node_fields.py
src/cbsc_zdc/models/graph.py
src/cbsc_zdc/training/losses.py
src/cbsc_zdc/training/flow_matching.py
src/cbsc_zdc/training/trainer.py
src/cbsc_zdc/data/dataset.py
src/cbsc_zdc/data/geometry.py
src/cbsc_zdc/cloud/vertex_stage.py
```

If filenames differ on the checked-out commit, use `rg --files src/cbsc_zdc`
and `rg` for class/function names; do not guess.

**The scripts you will actually reach for on DiCOS**, none of which existed when
the rest of this document was written:

```text
scripts/dicos.py                          client: auth, setup, exec, start, jobs,
                                          logs, put, get, ls, verify, info.
                                          Enforces the filesystem contract
                                          client-side; do not weaken the guard.
scripts/dicos_train.py                    the trainer runner; DiCOS twin of
                                          vertex_stage. Takes a run-directory
                                          lock, so a second writer is refused.
scripts/dicos_diagnostics.py              per-epoch validation-only diagnostics,
                                          one-shot (--checkpoint) or watch
                                          (--watch-dir). See §7d.
scripts/build_final_continuation.py       builds a continuation template from an
                                          accepted parent; --parent-last-epoch,
                                          --no-restart-scheduler, --patience,
                                          --checkpoint-stem, --selected-by.
scripts/sync_dicos_visualizations.py      DiCOS -> dashboard, with the Vertex
                                          sync's validations.
scripts/refresh_continuation_outputs.py   one command: pull metrics + history,
                                          rewrite rows, rebuild figures.
scripts/dicos_diag_producer.py            tracked 4090-side producer. Atomically
                                          feeds the namespaced diagnostic queue,
                                          names by embedded epoch, refuses a
                                          second producer, and writes STOP only
                                          after final-checkpoint inspection.
_setup/inspect_ckpt.py                    on the host. Prints a checkpoint's
                                          embedded stage/epoch/metric and hash
                                          without loading a model.
```

`docs/GPU_BENCHMARKS.md` is the single source of truth for throughput and cost
and supersedes every such figure in `logs.md`.

## 9. Running on Vertex AI

Current Vertex identity:

```text
project: asiop-zdc-1
project number: 39719277374
region: us-central1
staging/data bucket: asiop-zdc-1-zdc-reco-us-central1
service account: 39719277374-compute@developer.gserviceaccount.com
```

Authenticate and inspect before submission:

```bash
gcloud auth list
gcloud config set project asiop-zdc-1
gcloud ai custom-jobs list --project asiop-zdc-1 --region us-central1 \
  --sort-by='~createTime' --limit=20
gcloud ai training-pipelines list --project asiop-zdc-1 \
  --region us-central1 --sort-by='~createTime' --limit=20
```

Describe a job:

```bash
gcloud ai custom-jobs describe JOB_ID \
  --project asiop-zdc-1 --region us-central1
```

Inspect an artifact prefix without downloading the prepared corpus:

```bash
gcloud storage ls -l -r 'gs://BUCKET/PREFIX/**'
gcloud storage cat gs://BUCKET/PREFIX/vertex_result.json
```

Vertex submission pattern:

```bash
python vertex/submit_custom_job.py \
  --project asiop-zdc-1 \
  --region us-central1 \
  --staging-bucket gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/staging \
  --container-uri IMAGE_BY_DIGEST \
  --display-name UNIQUE_DESCRIPTIVE_NAME \
  --input-prefix gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/UNIQUE_INPUT \
  --output-prefix gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/UNIQUE_OUTPUT \
  --config-relative configs/NEW_FROZEN_CONFIG.yaml \
  --machine-type MACHINE_TYPE \
  --accelerator-type ACCELERATOR_ENUM \
  --accelerator-count 1 \
  --service-account 39719277374-compute@developer.gserviceaccount.com
```

Before calling the launcher:

- calculate a conservative cost range;
- confirm the input and output prefixes are unique and empty;
- stage exact prepared artifacts, frozen config, and parent checkpoints;
- verify every staged hash;
- use the user’s requested scheduling strategy;
- record the resulting pipeline/custom IDs immediately in `logs.md`;
- never submit a duplicate because a CLI timed out—list and describe first.

The old runs used on-demand `n1-standard-8 + 1 NVIDIA_TESLA_T4`. That is a
record, not a requirement for future work.

## 10. Running on another CLI, cluster, or storage system

GCS and Vertex are transport/execution implementations, not part of the model’s
scientific definition. It is valid to use Slurm, Kubernetes, another managed
service, object storage other than GCS, a shared POSIX filesystem, or a local
GPU.

### 10a. DiCOS (ASGC) — the active training backend

Training is moving from Vertex to DiCOS at Academia Sinica. Full detail is in
`docs/DICOS_BACKEND.md`; read it before touching the host. The essentials:

**Access.** ASGC mandates Google-Authenticator OTP on its login services, so
there is no SSH path an agent can drive. The DiCOSApp JupyterLab is directly
reachable and its token authenticates the REST and kernel-websocket APIs.
`scripts/dicos.py` wraps this into a CLI usable by any agent or human:

```bash
python scripts/dicos.py auth "<launch or address-bar URL>"    # start of session
python scripts/dicos.py setup                                  # provision/repair
python scripts/dicos.py exec "nvidia-smi"                      # shell, synchronous
python scripts/dicos.py put local remote                       # upload
python scripts/dicos.py get remote local                       # download

python scripts/dicos.py start "<cmd>" --name job   # detached: hours-long work
python scripts/dicos.py jobs                       # running / finished
python scripts/dicos.py logs job --tail 40         # follow output
```

**Anything measured in hours must go through `start`, not `exec`.** `exec` is
synchronous and bounded by a timeout; `start` runs under `nohup` with its log on
the shared filesystem, so it survives the client disconnecting — though not the
pod's own end time, which kills every process inside it. Launch a long-lived app
before starting long work.

Apps are launched by the user from <https://dicos.grid.sinica.edu.tw/dockerapps/>.
If `~/.dicos/config.json` does not exist, the client prints how to create it
from `scripts/dicos_config.template.json`; the fields other than `token` and
`base_url` encode the filesystem contract and must not be widened.

Credentials live in `~/.dicos/config.json`, never in the repository.

**The one thing a human must supply.** DiCOSApp pods are ephemeral and the
portal mints a fresh Jupyter token into the pod’s environment at each launch
(`jupyter lab --NotebookApp.token="${DICOS_JUPYTER_TOKEN}"`), so no token can be
pinned in advance. An agent therefore cannot start a session unaided, and should
not: launching an app allocates shared GPU time on a multi-tenant academic
cluster behind mandatory 2FA. **Ask the user to launch the DiCOSApp, then run
`auth` followed by `setup`.** Do not attempt to bypass OTP or store 2FA
material.

In practice this is one paste, not a hunt. **The token has been observed to be
stable per user, not per pod** (the same value across two pods on two ports), so
normally only the port changes and `auth` reuses the stored token:

```bash
python scripts/dicos.py auth "<address-bar URL>"   # reuses the stored token
python scripts/dicos.py setup
```

If the stored token is still valid, even that is unnecessary -- just run
commands. Every command preflights the connection and prints precise recovery
steps instead of a bare 403.

Only if the token genuinely changed, have the user recover it. JupyterLab moves
it into a cookie seconds after login, so no clipboard race is needed. Easiest
first, a notebook cell:

```python
import json, glob, os, pathlib
# newest by mtime; sorting by name is lexicographic on PID and can hand back
# a dead pod's stale token
files = glob.glob(str(pathlib.Path.home() / ".local/share/jupyter/runtime/jpserver-*.json"))
print(json.load(open(max(files, key=os.path.getmtime)))["token"])
```

or a JupyterLab terminal running `jupyter server list`. Then:

```bash
python scripts/dicos.py auth "<address-bar URL>" "<token>"
```

`auth` accepts a URL containing the token, a URL plus token, a bare token, or a
URL alone. It ignores the pod-internal address `jupyter server list` prints,
verifies before saving, and saves nothing on failure.

**`setup` is idempotent and does everything else.** It clones or updates the
repo, builds or repairs the venv (validated by import, since a GPU app is a
different image and a venv built against another base env exists but is
broken), verifies the frozen geometry hash, and reports GPU presence. Run it
after every `auth`; it is cheap when nothing needs fixing.

**Filesystem contract — binding, see `AGENTS.md` 17-21.** The shared filesystem
is multi-tenant.

- Writable: **only** `/dicos_ui_home/julianjuan/sharedfs/work/IOP/julian/Fast MC CBSC`
  and below. Not `$HOME`, not `/ceph`, not any other `sharedfs/work/IOP/*`.
- **Exactly one readable data file**, immutable:
  `sharedfs/work/IOP/ZDC_ML_20260620/dataset/myTree_20251117_765k_0to300GeV_neutron_All.root`.
  Never write it, and never write into that directory.
- **Everything else in that directory is out of scope, reading included** — the
  `_transformed` variant and the older 15k/100k/135k files. Do not open, hash,
  or inspect them; the client refuses commands that name the transformed file.
- `scripts/dicos.py` enforces the above client-side and must not be weakened.
  Its guards are regression-tested offline in `tests/test_dicos_client.py`.

**Host facts that change how work is planned.**

- **No Slurm from inside a DiCOSApp pod** (`sbatch`/`squeue`/`sinfo` absent).
  Training runs *inside* a GPU app, so it must be checkpoint/resume-capable,
  because the pod’s session ends on a schedule and takes running processes with
  it. This is the main structural difference from Vertex, where a submitted job
  outlived the client.
- The CPU app has 128 cores and ~1.5 TB RAM — well suited to the CPU-bound
  conversion, and currently under-used by the single-threaded reader. The GPU
  app is a *different image*: 40 cores, ~1.5 TB RAM, RTX 4090 24 GB, no
  `/opt/miniconda3/envs/asgc`, and `/usr/bin/python3` is 3.9.21 — below this
  project's `requires-python >= 3.10`.
- `setup` therefore installs torch itself and pins `torch==2.6.0+cu124`, the
  version in `pytorch/pytorch:2.6.0-cuda12.4` that every accepted Vertex run
  used, so a backend move does not silently change numerics. Do not let it
  drift: an image shipping a different torch must still be overridden. numpy is
  2.5.1 here. Record both in the evidence of any run produced here.
- Egress works, so `pip install` and `git clone` succeed.

**Verified invariants (see `logs.md` and `docs/DICOS_BACKEND.md`).** The whole
data pipeline reproduces on DiCOS and is re-checkable at any time with
`python scripts/dicos.py verify`, which re-hashes from disk rather than trusting
recorded values:

- raw ROOT byte-identical to the canonical source
  (`b7c666040e42352e158a9a3f78158d147cb2e056c6c88248d892c956f5c7b533`,
  764,940 entries);
- frozen geometry present under `e22d4cfb…`, recomputed on the host;
- **all 187 prepared shards byte-identical** to the canonical manifest
  (764,940 events, 1,157,840,863 hits, zero rejections);
- **split reproduces the canonical assignment**, 612,482 / 76,158 / 76,300,
  `f71003e07eb16baf4029387fd8e54b2e22b98981bbd6ee519a6d363167b4c8c8`;
- `train_data_audit.json` reproduces the canonical audit exactly;
- `calibrated_lr3e4_best_epoch4.pt` staged and verified (`3f1022b8…`).

So existing epoch-4 checkpoints remain comparable to work done here.

**Resolved 2026-08-01 (was: "not present on the host").** All eight checkpoints
(best and last for all four families) are now staged under `prep/checkpoints/`
with host-verified hashes matching section 7, and the pilot partition exists
here, so the fixed 50x5 visual bank can be reconstructed. Two cautions survive:

- The training bank is `prep/training_pilot_splits.json` — **26,624 train /
  6,656 validation**, assignment
  `084f0dfd86e488c63bb41ea50d6783ad22eb57a322288c075a94b1ec12dd3714`. Do not
  confuse it with `pilot_splits.json` (338/104), a smaller bank that is *not*
  what the calibrated families trained on.
- That assignment was **transported, not regenerated**. numpy's
  `Generator.choice(replace=False)` switches algorithm with the sample
  fraction, so the 2048/512 draw is not reproducible across numpy versions
  (the smaller 26/8 draw does reproduce bit-exactly). Its split json records
  *this host's* manifest hash, with the Vertex hash kept alongside in its
  `provenance` block. That is not a weakened check: the loader compares the
  split's manifest hash against the manifest it is used with, and the two
  manifests describe byte-identical shards in identical order, differing only
  in `source_files[].path`.

Three independent confirmations that this is the same selection on the same
data: the pilot partition is a strict subset of the parent split (0 pilot-train
events outside parent-train, 0 outside parent-validation, 0 test events
touched); a fresh audit of the pilot train split reproduces the calibrated
response caps bit-exactly (`0.725470286351178`, `64.38813572617559`); and
preflight verifies all 187 shards with `"pass": true`.

Section 10 of this file (backend-neutral procedure) predates DiCOS: its step 1,
"copy or mount `prep-20260724-r5`", does not apply here — the corpus is produced
on-host from the one permitted ROOT file, and copying a second corpus in would
violate the data-source rule. See `docs/DICOS_BACKEND.md` sections 5-6.

**`training.epochs` is an ABSOLUTE epoch target, not a count of additional
epochs.** The trainer resumes at `checkpoint_epoch + 1` and iterates
`range(start_epoch, epochs)`. Every accepted parent ends at **epoch 4**, so a
continuation of N further epochs needs `epochs = 5 + N`, not `epochs = N`.
Setting it wrong does not error: with `restart_scheduler_on_resume` the cosine
horizon is `updates_per_epoch * (epochs - start_epoch)`, so the run silently
does too few epochs *and* anneals to `min_learning_rate` across them. This was
launched wrong once (`epochs: 6` → one epoch at LR 1e-6, validation 4.7723
against the parent best 4.7380) and caught from the first epoch report.
`scripts/build_dicos_continuations.py` derives it as
`PARENT_LAST_EPOCH + 1 + ADDITIONAL_EPOCHS`; two tests in
`tests/test_dicos_client.py` pin the algebra.

**Two traps already paid for.**

1. `_transformed.root` **must never be used**: it is a dense-grid rebinning with
   6,400 HCAL cells against the frozen 6,390 (it pads the 90-cell final layer to
   100), has four fewer events, and discards cell identity.
2. Derived float artifacts do **not** byte-reproduce across library versions.
   Regenerating the geometry on DiCOS changed only `edge_features[:,
   distance_norm]`, by exactly one float32 ULP, which was enough to change the
   hash. **Transport hash-pinned artifacts; do not regenerate them.** Expect the
   same for the prepared shard manifest and verify rather than assume.

Keep these invariant across a backend move:

- source commit;
- frozen config contents;
- dataset, split, geometry, and checkpoint hashes;
- data selection and zero-test-use contract;
- precision, seeds, optimizer, scheduler, batch, accumulation, workers, and
  solver steps;
- output layout and evidence fields.

Only rewrite runtime paths. Do not alter scientific values while adapting
transport.

Backend-neutral procedure:

1. copy or mount `prep-20260724-r5` and verify all 187 shard hashes against the
   manifest;
2. copy the exact parent best/last checkpoints and verify SHA-256;
3. build/pull the recorded container, or create an environment whose Python,
   PyTorch, CUDA, and package versions are captured;
4. generate a new template for the intended experiment and freeze it through
   the CLI; never edit a frozen YAML;
5. map manifest, split, geometry, checkpoint, and output paths into the
   backend’s local filesystem;
6. run:

```bash
cbsc-zdc doctor
cbsc-zdc train --config /absolute/path/to/new_frozen_config.yaml
```

7. synchronize immutable epoch/progress snapshots to durable storage during the
   job, not only at normal exit;
8. after every epoch, independently reload the checkpoint and verify finite
   tensors, selected metric, history, invariants, visualization, resources, and
   full solver/decode timing;
9. record scheduler/job ID, host, GPU, driver, CUDA, PyTorch, container/environment
   identity, commands, timings, hashes, and storage URI in `logs.md`.

If the backend cannot access GCS, make one verified server-side transfer into
its durable store. Record source generation/checksum, destination checksum, and
transfer command. Do not silently create a second “canonical” dataset.

## 11. Designing the next training experiment

Do not resume merely because files exist. First state the exact question. Good
examples:

- does the current lowest-validation-loss family continue improving for N
  additional epochs?
- does a larger-memory backend improve throughput at identical scientific
  settings?
- does a separately declared precision or DataLoader change preserve numerical
  behavior?
- do fixed-sample response/profile/count diagnostics improve with the objective?

For continuation training:

1. choose the exact accepted parent and verify both best and last hashes;
2. decide whether continuation resumes optimizer/scheduler/RNG or initializes
   model weights only; state the choice;
3. declare the scheduler horizon and checkpoint interval;
4. make a new unique template and freeze it;
5. preserve the 26,624/6,656/0 bank unless the new experiment explicitly
   declares a larger bank;
6. preserve the fixed 50-by-5 selection for cross-epoch visual comparison;
7. run one or several independent experiments only within the user’s requested
   scope and budget;
8. report every run, including regressions.

**`training.epochs` is an ABSOLUTE target, not a count of new epochs.** The
trainer resumes at `checkpoint_epoch + 1` and runs `range(start_epoch, epochs)`.
So `epochs = parent_last_epoch + 1 + additional`. Misreading this cost a whole
wave (`dicos-r1`), which ran one epoch per family with the cosine annealed to
`min_learning_rate` across it. `scripts/build_final_continuation.py` takes
`--parent-last-epoch` and computes it for you; use the builder.

**Two settings that are not free parameters any more**, both established by
`dicos-p8` against `dicos-p9` and explained in §7b:

* `early_stopping_patience` must equal the run's horizon, not a constant, when
  resuming from a best checkpoint reached at the end of an anneal;
* `restart_scheduler_on_resume: false` — continue the saved cosine. It is
  periodic in `2*T_max` and climbs back to peak on its own. Restarting to peak
  discards that and interacts badly with patience.

**Build it, do not hand-edit it.** Never edit a frozen config. Edit the template
or the builder, generate a new uniquely named config, freeze it through
`python -m cbsc_zdc.cli freeze-config`, and record both hashes. `--geometry`
wants the geometry **directory**, not the `.npz`. Then diff the new frozen
config against its parent and confirm only the intended fields moved — project
name, run dir, epochs, the resume pair, and provenance. Anything else appearing
in that diff is a defect. `freeze-config` also overrides `response_cap_ratio`
and `response_cap_absolute_gev` from the audit you pass, so passing the wrong
audit silently changes the physics caps.

More epochs are not guaranteed to improve monotonically. Do not cherry-pick a
single favorable epoch without showing the complete trajectory.

For eventual scientific validation, use three seeds for each frozen final
condition and report all seeds. The untouched test split may be evaluated only
after architecture, weights, optimizer, stopping, checkpoint selection,
diagnostic definitions, and seeds are frozen. Do not let a website or visual
sample select the final checkpoint.

## 12. Epoch-level QA and logging contract

At every completed or failed epoch, record:

- job/backend identity and state;
- start/end/duration and examples/second;
- epoch, optimizer steps, scheduler steps, LR, train loss, validation loss, and
  all nine component losses;
- gradient/model/optimizer finite-tensor checks;
- best/last checkpoint sizes, SHA-256, embedded epoch/metric, and reload result;
- immutable progress object/file inventory and hashes;
- nonfinite, negative, support, count, dust, layer-closure, and event-closure
  counts/maxima;
- GPU peak memory/headroom;
- full configured solver/decode timing, currently 8 profile and 8 share steps
  where that remains the experiment setting;
- fixed 50-by-5 selection hash and descriptive visual/statistical results;
- zero test events;
- cost used and revised projection;
- interpretation, counterexamples, follow-up QA, and website publication action.

Do not log private chain-of-thought. Log the evidence and why the declared
decision follows from it.

Every meaningful event gets a `logs.md` entry with its commands, source commit,
dirty-state disposition, input/output SHA-256, environment, GPU, job IDs,
timings, costs, counterexamples, **failed attempts**, and the decision the
evidence supports. Machine-readable twins go in `audit/NAME.{json,md}`.

The failed-attempts clause is load-bearing. Most of the rules in this document
exist because a specific mistake was written down: the absolute-`epochs`
misread, the two-writer quarantine, the self-matching process probe, the
manifest-filename clobbering, the flat `_diag/` overwrite, the 225–250 GeV bin
that vanished, the patience that stopped a 24-epoch run at 6. An agent that
logs only successes removes the mechanism that produced every one of those
guards.

## 13. Local Event Observatory

Source data live at:

```text
SOURCE_REPO/dashboard/public/data
```

The full local site shows all synchronized validation-only epochs and includes:

- one Geant4 reference plus five stochastic Fast-MC draws for the identical
  four-vector;
- synchronized 3D detector views;
- longitudinal profiles;
- total response, hit count, depth centroid, radial RMS, ECAL fraction, and late
  fraction;
- cross-epoch fixed-bank trends and provenance.

To synchronize a Vertex output and serve locally on Windows:

```powershell
.\scripts\start_visualization_dashboard.ps1 `
  -SourcePrefix "gs://BUCKET/RUN_OUTPUT_PREFIX" `
  -SyncIntervalSeconds 300 `
  -Port 3000
```

Open:

```text
http://localhost:3000/
```

On any host, the equivalent is:

```bash
python scripts/sync_vertex_visualizations.py \
  --source gs://BUCKET/RUN_OUTPUT_PREFIX \
  --destination dashboard/public/data
cd dashboard
npm ci
npm test
npm run dev -- --port 3000
```

If the source is not GCS, adapt the sync transport but feed the same verified
`geometry.json`, `manifest.json`, and epoch payload schema into
`dashboard/public/data`. Never bypass its hashes, validation split, 50-by-5,
unique-selection, draw-diversity, or zero-test checks.

## 14. Public visual site

Live URL:

```text
https://julianattemptscoding.github.io/Fast-MC-Visual-Tests/
```

Public-site contract:

- exactly four calibrated families unless the user explicitly changes scope;
- exactly one checkpoint per family: the lowest independently verified
  validation-loss checkpoint;
- exactly 50 fixed validation conditions;
- one Geant4 reference and five independent Fast-MC draws for the same
  four-vector;
- no uncalibrated variants and no duplicate best/last checkpoint displays;
- no test events;
- synchronized 3D cameras;
- compact, professional HEP-facing language;
- performance safeguards such as batched paths, lazy payload loading, and a
  capped device-pixel ratio;
- clear statement that visual QA is not Geant4 fidelity.

Current public snapshot IDs, as recorded in
`PUBLIC_REPO/config/public_snapshots.json`:

```text
dicos-r3-calibrated-lr3e5:joint:0008
dicos-p9-calibrated-lr1e4:joint:0038
dicos-p7-calibrated-lr3e4:joint:0022
dicos-p7-calibrated-lr1e4-halfbatch:joint:0021
```

Read that file rather than trusting this list; it is the authority and it moves
whenever a family produces a lower verified loss.

Publication procedure:

1. synchronize and verify the source dashboard epoch;
2. update `PUBLIC_REPO/config/public_snapshots.json` only if the new checkpoint
   is the selected lowest verified validation loss for that family;
3. export:

```bash
cd "$PUBLIC_REPO"
python scripts/export_public_data.py \
  --source "$SOURCE_REPO/dashboard/public/data" \
  --destination public/data \
  --selection config/public_snapshots.json
npm ci
npm test
npm run build
```

4. inspect manifest/checkpoint/selection hashes and payload size;
5. commit and push;
6. verify the GitHub Pages workflow and live URL rather than assuming push means
   deployment.

**Getting a DiCOS epoch into the dashboard.** The procedure above assumes a GCS
source. From DiCOS the transport is `scripts/sync_dicos_visualizations.py`,
which applies the same validations as the Vertex sync — epoch check, snapshot
id, SHA-256, atomic write, row normalization — but records `dicos_object`
rather than `gcs_object` for provenance. Pull the epoch payload from
`_runs/<family>_<tag>/reports/visualization/epoch_NNNN.json` and feed it to
that script; do not hand-assemble dashboard rows, which is how this was done
before the script existed and is not reproducible.

Note that `export_epoch_visualization` renders from **`last.pt` as of that
epoch**, not from `best.pt`. For the published checkpoint those coincide only
when the best epoch is also the final one. Check before claiming a figure shows
the published weights.

The last verified public source state was commit `03627a6`, manifest SHA-256
`cf14cff538f9e5c281b4fb4e0ea9d2c30e664063dd5eedfc48c3c84d53de57c3`,
24,837,900 bytes on disk across `public/data`, with four accepted family
snapshots and `dicos-p7-calibrated-lr3e4:joint:0022` as the explicit default.
Recheck workflow and live state rather than trusting this; it moves with every
publication.

The source-side figure/metric organization described below was committed and
pushed as `ad0e5b7`. It introduced no training or event generation and used no
new test events. Establish current repository state before relying on that
identity.

## 15. Exhibition figures

`SOURCE_REPO/exhibition` contains the presentation-ready gallery. The builder
uses compact verified audit/dashboard evidence and does not read the raw ROOT or
test split:

```bash
python exhibition/build_exhibition.py
```

The current catalog covers loss histories, objective components, fixed-sample
proxies, compute/cost, model architecture, data/geometry, claim boundaries,
same-condition longitudinal profiles, distributions, and 3D deposits. After any
new published epoch:

- update the compact history/evidence inputs;
- rebuild;
- verify every output hash and manifest assertion;
- **visually inspect the PNG/SVG outputs**;
- keep the distinction between optimization progress and physics fidelity.

That inspection step is not a formality. Three separate rendering faults were
caught only by looking at the rendered image, and none by a clean build: a
subtitle colliding with the title on short figures (fixed by positioning in
inches, `y = 1 - 0.36/height`, because fractional positions do not scale), a
best-epoch label sitting on top of the training curve (moved below the minimum
into opened headroom), and a silently missing energy bin.

**Two figure builders, two histories, and they must not be crossed.**

| builder | reads | covers |
|---|---|---|
| `exhibition/build_exhibition.py` | `exhibition/data/training_history.csv` | the original epochs 0..10; `build_exhibition.py` **asserts** that file is exactly epochs 0..10 |
| `exhibition/build_continuation_loss_figures.py` | `exhibition/data/continuation_history.csv` | every DiCOS continuation, per family and run tag |

Putting continuation rows into `training_history.csv` trips that assertion. It
is a guard, not an obstacle.

**Metric-vs-epoch trends** come from a third builder:

```bash
python exhibition/build_diagnostic_trend_figure.py dicos-p9 dicos-p10
```

It reads each `exhibition/data/diagnostics/<run-tag>/` in the supplied lineage
order (later tags win overlapping epochs) and writes four ordinary metric-vs-
epoch figures plus four matching `*_of_best_loss_so_far` figures. The latter
show 3090 metrics for the checkpoint selected only by accepted validation loss;
diagnostic metrics never select it. Missing bins are plotted as `NaN` so a gap breaks the
line visibly instead of being interpolated over. One command refreshes the whole
local picture from a live run:

```bash
python scripts/refresh_continuation_outputs.py \
  --family <family> --run-tag <tag> --run-dir _runs/<family>_<tag> \
  --lineage <oldest-tag> ... <tag> --expected-epoch <epoch>
```

It pulls diagnostics and history off the host, rewrites the continuation rows,
rebuilds all figure/metric/gallery/catalog outputs, and writes exact epoch audit
twins. Add `--offline` for a no-DiCOS-I/O rebuild test. Publication remains a
separate verified act (§14), but `public_release_required=true` is a mandatory
handoff whenever the accepted validation-loss best changes.

The deterministic cross-family index is:

```bash
python exhibition/build_metrics_catalog.py
```

It verifies every PNG/SVG, exhibition and historical C2ST manifest hash,
accepted/latest/quarantined metric agreement, active lineage, and conservative
test accounting before replacing `exhibition/metrics_catalog.json` and
`exhibition/METRICS_AND_FIGURES.md`, and builds `exhibition/index.html` as the
complete logically grouped exhibition. As of 2026-08-04 it covers 87 graphics;
the compact current-model gallery is `exhibition/current.html`.

## 16. Minimum verification before claiming work is done

`pytest` needs `PYTHONPATH=src`. Without it collection fails with
`ModuleNotFoundError: cbsc_zdc` and **runs zero tests, reporting success**.

Run from the source repository:

```bash
export PYTHONPATH=src                     # PowerShell: $env:PYTHONPATH='src'
python -m compileall -q src vertex scripts tests
PYTHONPATH=src python -m pytest -q         # expect 241 passed as of 2026-08-04
python exhibition/build_exhibition.py     # expect 23 visuals; verify the manifest hash
```

Run from the public repository:

```bash
python -m unittest discover -s tests -v   # expect 8 tests
npm ci
npm run build
```

Eight Transformer nested-tensor `UserWarning`s are known and nonfatal.

Use the environment’s exact Python executable if `python` is ambiguous. If a
test fails because a dependency is missing, record the environment and install
only the declared project dependencies. **Do not weaken the assertion.**

`tests/test_qa_policy.py` will fail if you write the 80 GB card's model name
into any active-guidance file. That is deliberate, not a bug: an earlier policy
revision used access to that card as a permission screen, and the token check is
what keeps it from coming back. Rename the card — "80 GB datacentre GPU" is the
descriptor the repo uses — rather than exempting your file from the test.

A push is not a deployment. Verify the GitHub Pages workflow and fetch the live
URL before saying the site is updated.

## 17. First response and first actions

Before you answer, establish state — do not report from this document, which
was written at a moment that has passed:

```bash
cd "$SOURCE_REPO" && git status --short && git log -5 --oneline \
  && git rev-list --left-right --count origin/main...HEAD
cd "$PUBLIC_REPO" && git status --short && git log -3 --oneline
PYTHONPATH=src python scripts/dicos.py exec \
  'nvidia-smi --query-gpu=name,memory.used,utilization.gpu --format=csv,noheader; \
   ps -eo pid,etime,args | grep "[d]icos_train" || echo NONE'
```

Then start your response with:

1. the source/public commit and dirty-state status;
2. the current standings and which run, if any, is training (§7b);
3. the scientific boundary — optimization evidence exists; Geant4 fidelity is
   **not** established, and C2ST AUROC 0.77–0.92 says a classifier still
   separates Fast-MC from Geant4 at every checkpoint;
4. whether any cluster job is currently active, proved from the process tree;
5. the current backend access you can actually verify;
6. the exact proposed next experiment and conservative cost/time range, if the
   user asked to launch one.

Then act within the user's request. Do not resurrect hardware permission gates.
Use QA findings to identify trusted artifacts and concrete follow-up checks.
Preserve provenance, keep the test split excluded from all development and
selection, retain the exact historical-use accounting instead of claiming it
was wholly untouched, and report negative results honestly.

**The standing operational duty, restated because it is the one most often
dropped:** at every meaningful event — launch, epoch, failure, correction, doc
change, repo change, verification run — append to `logs.md`, and keep the
graphs, the dashboard, the public site, the metrics, and the audit twins moving
with it. Not at the end of a session; as you go. A run whose evidence was never
written down is a run that did not happen.
