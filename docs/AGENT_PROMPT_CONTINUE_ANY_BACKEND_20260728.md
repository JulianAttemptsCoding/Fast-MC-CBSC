# Exact prompt for continuing CBSC-ZDC in a new chat or CLI

Copy everything below the horizontal rule into the new agent. It is intentionally
self-contained and backend-neutral.

---

You are taking over the CBSC-ZDC v2.2 conditional Fast Monte Carlo project.
Treat this message as the controlling technical handoff. Do not assume access to
the previous chat. Work from repository and artifact evidence, and keep the user
informed with concise, evidence-backed updates.

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
   training backend, with a binding filesystem contract), and this file;
5. inspect `git status --short`, `git log -5 --oneline`, and remotes in both
   repositories;
6. read the newest entries in `logs.md`;
7. read `audit/compute_extension_20260727_r2_terminal_analysis.json` and
   `audit/compute_extension_20260727_r2_terminal_analysis.md`;
8. verify that no unknown job is active before submitting work.

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
   generator, the remaining 36,300 untouched. See that repository's
   `docs/ISOLATION.md`.
2. **In-repository diagnostic, 2026-07-30** — the first direct test-split use
   *inside this repository*. A 2,000-event random draw from the full corpus, at
   the project owner's explicit instruction after being warned twice, included
   **200 sealed-test events (10.0%)**; they appear in the six published figures
   under `exhibition/paired_diagnostics_20260730/`. It fed no preprocessing,
   threshold, architecture, loss-weight, learning-rate, stopping, or
   checkpoint-selection decision. `PHYSICS VALIDATION NOT ESTABLISHED`. See
   `logs.md` and that directory's `README.md`.

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

## 7. Current accepted epoch-4 checkpoints

All four calibrated families have verified epoch-4 artifacts. One checkpoint
per family is published. Exact validation losses and checkpoint hashes:

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
import json, glob, pathlib
print(json.load(open(sorted(glob.glob(str(
    pathlib.Path.home() / ".local/share/jupyter/runtime/jpserver-*.json")))[-1]))["token"])
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
  conversion, and currently under-used by the single-threaded reader.
- `torch 2.8.0+cu128` and `numpy 2.1.3` here, versus `2.6.0+cu124` on Vertex.
  Record this in the evidence of any run produced here; it also makes bit-exact
  reproduction of existing checkpoints unlikely.
- Egress works, so `pip install` and `git clone` succeed.

**Verified invariants (see `logs.md` and `docs/DICOS_BACKEND.md`).** The raw
ROOT file on DiCOS is byte-identical to the canonical source
(`b7c666040e42352e158a9a3f78158d147cb2e056c6c88248d892c956f5c7b533`,
764,940 entries), and the frozen geometry is present under hash
`e22d4cfb…`, re-verified on the host.

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

Current public snapshot IDs are:

```text
compute-extension-r2-calibrated-lr3e5:joint:0004
compute-extension-r2-calibrated-lr1e4:joint:0004
compute-extension-r1-calibrated-lr3e4:joint:0004
compute-extension-r1-calibrated-lr1e4-halfbatch:joint:0004
```

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

The last verified public state before this handoff was commit
`784fe6bf572cb6285fb2e92a54858883da1c0e6e`, workflow `30285942671`,
manifest SHA-256
`3ab56be2af72b386fa2e553d48aea9e9dbb361e19621c35639e8e61b1f3c8bfe`,
and 24,582,747 compressed bytes. Recheck because this can change.

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
- visually inspect the PNG/SVG outputs;
- keep the distinction between optimization progress and physics fidelity.

## 16. Minimum verification before making changes

Run from the source repository:

```bash
python -m compileall -q src vertex scripts tests
python -m pytest -q
python exhibition/build_exhibition.py
```

Run from the public repository:

```bash
python -m unittest discover -s tests -v
npm ci
npm run build
```

Use the environment’s exact Python executable if `python` is ambiguous. If a
test fails because a dependency is missing, record the environment and install
only the declared project dependencies. Do not weaken the assertion.

## 17. First response and first actions

Start your response to the user with:

1. the source/public commit and dirty-state status;
2. the latest accepted model state (four calibrated epoch-4 families);
3. the scientific boundary (optimization evidence exists; Geant4 fidelity is
   not established);
4. whether any cloud/cluster job is currently active;
5. the current backend/storage access you can actually verify;
6. the exact proposed next experiment and conservative cost/time range, if the
   user asked to launch one.

Then act within the user’s request. Do not resurrect hardware permission gates.
Use QA findings to identify trusted artifacts and concrete follow-up checks.
Preserve provenance, keep the test split sealed during development, update
`logs.md` at every meaningful event, and report negative results honestly.
