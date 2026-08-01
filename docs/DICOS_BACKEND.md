# DiCOS (ASGC) backend — access, environment, and migration state

Per `CLAUDE.md`'s backend-portability rule, GCS and Vertex are transport, not
science. This document records the DiCOS equivalent: how the host is reached,
what it provides, and which invariants have been verified across the move.

## 1. Access model

ASGC mandates Google-Authenticator OTP on its login services, so there is no
SSH path an agent can drive unattended. The DiCOSApp **JupyterLab is directly
reachable** and its token authenticates both the REST contents API and the
kernel websocket, which together are sufficient for file transfer and shell
execution.

`scripts/dicos.py` wraps this into a CLI any agent or shell can call — Claude
Code, Codex/ChatGPT, or a human — since it is a plain command-line program with
no agent-specific coupling:

```bash
python scripts/dicos.py auth "<launch URL>"  # 1. every new session
python scripts/dicos.py setup                # 2. provision/repair, idempotent
python scripts/dicos.py verify               # re-hash every artifact from disk
python scripts/dicos.py info                 # probe the remote environment
python scripts/dicos.py exec "nvidia-smi"    # run a shell command (synchronous)
python scripts/dicos.py ls .                 # list the workdir
python scripts/dicos.py put local remote     # upload
python scripts/dicos.py get remote local     # download

# long work -- conversion, training -- must not run through `exec`
python scripts/dicos.py start "<cmd>" --name convert   # detached, survives disconnect
python scripts/dicos.py jobs                           # what is running / finished
python scripts/dicos.py logs convert --tail 40         # follow its output
```

Launch a DiCOSApp from <https://dicos.grid.sinica.edu.tw/dockerapps/>.

`verify` re-hashes the geometry, all 187 shards, the split assignment, and any
staged checkpoint **from disk**, rather than trusting the values recorded in the
manifests, so a truncated or corrupted file cannot pass. Run it after any pod
change and before relying on the corpus for a training run. It also reports
leftover upload parts and any job still running.

### Running work that outlives a command

`exec` is synchronous and bounded by a timeout, so anything measured in hours
(the ROOT conversion, training) must go through `start`. It runs the command
under `nohup` with its log on the shared filesystem, so the job survives the
client disconnecting and its output remains readable from a later session —
though **not** past the pod's own end time, which kills every process inside it.
`jobs` reports each job as RUNNING or finished by checking the recorded pid.

Steps 1 and 2 are the whole session start-up. `setup` clones or updates the
repo, builds or repairs the venv, verifies the frozen geometry hash, and reports
the GPU — so a brand-new pod, including a GPU image different from the CPU one,
is ready without any further manual work.

### Starting a session (do this first, every time)

**The token appears to be stable per user, not per pod.** The same value was
observed across two different pods on two different ports. So in the normal case
you never need to hunt for it — hand over whatever URL the address bar shows and
`auth` reuses the stored token:

```bash
python scripts/dicos.py auth "http://scale-k8s-master01.twgrid.org:30122/lab/tree/..."
# authenticated against http://scale-k8s-master01.twgrid.org:30122 (reused the stored token)
```

If the stored token still works, even that is unnecessary — just run commands.
Every command preflights the connection and, if it fails, prints exactly what to
do rather than a bare 403.

#### Recovering the token, when it really has changed

JupyterLab moves the token into a cookie and rewrites the address bar within
seconds of login, so a URL copied later contains none. There is no need to race
the clipboard; the token is retrievable at leisure, in decreasing order of
convenience:

1. **A notebook cell** — no terminal needed, works purely in the Lab UI:

   ```python
   import json, glob, os, pathlib
   # newest by mtime -- sorting by name is lexicographic on PID and can return
   # a dead pod's stale token, which then fails authentication confusingly
   files = glob.glob(str(pathlib.Path.home() / ".local/share/jupyter/runtime/jpserver-*.json"))
   print(json.load(open(max(files, key=os.path.getmtime)))["token"])
   ```

2. **A JupyterLab terminal** (*File ▸ New ▸ Terminal*):

   ```bash
   jupyter server list
   # http://<pod-name>:8888/?token=57115a0b…  ::  /dicos_ui_home/<account>
   ```

3. **The runtime file itself**, `~/.local/share/jupyter/runtime/jpserver-<pid>.json`,
   which persists in `HOME` across pods. There is also a clickable
   `jpserver-<pid>-open.html` beside it containing the same token.

Then pass URL and token together:

```bash
python scripts/dicos.py auth "<address-bar URL>" "<token>"
```

`auth` accepts any of: a URL containing the token, a URL plus a separate token,
a bare token, or a URL alone (reusing the stored token). It verifies against the
server before saving and saves nothing on failure.

> The address `jupyter server list` prints is the **pod-internal** one
> (`http://<pod-name>:8888`), unreachable from outside the cluster. `auth`
> detects this and keeps the working external URL, so pasting that line
> verbatim is safe.

### A Git Bash trap worth knowing

On Windows, Git Bash rewrites POSIX-looking absolute arguments into Windows
paths, so `put file /dicos_ui_home/...` silently becomes
`C:/Program Files/Git/dicos_ui_home/...`. The client detects a drive letter and
refuses with an explanatory message rather than doing something surprising.
Either use workdir-relative paths (recommended) or prefix the command with
`MSYS_NO_PATHCONV=1`.

Credentials live in `~/.dicos/config.json`, **outside this repository**:

```json
{
  "base_url": "http://scale-k8s-master01.twgrid.org:30122",
  "token": "<DiCOSApp JupyterLab token>",
  "jupyter_root": "/dicos_ui_home/julianjuan",
  "workdir": "/dicos_ui_home/julianjuan/sharedfs/work/IOP/julian/Fast MC CBSC",
  "data_file": ".../ZDC_ML_20260620/dataset/myTree_20251117_765k_0to300GeV_neutron_All.root",
  "forbidden_paths": [".../myTree_20251117_765k_0to300GeV_neutron_All_transformed.root"]
}
```

`data_file` is the one dataset this project may read; `forbidden_paths` are
refused outright, reads included. Only `base_url` normally changes between
sessions.

### Two address spaces

A recurring source of confusion, handled by the client: the contents API is
rooted at the server's `root_dir` (the user's `HOME`), while shell commands use
absolute paths. The Jupyter URL path `sharedfs/work/IOP/julian/Fast MC CBSC`
and the filesystem path
`/dicos_ui_home/julianjuan/sharedfs/work/IOP/julian/Fast MC CBSC` are the same
directory. `jupyter_root` in the config is what lets the client translate.

### Write scope

Enforced client-side, matching the contract agreed with the data owner
(`AGENTS.md` 17-21):

- `put`/`mkdir` refuse any destination outside `workdir`, normalising `..`
  first so traversal cannot slip past;
- **`exec` and `start` refuse commands that appear to write outside `workdir`**
  — redirections and file-mutating verbs (`rm`, `mv`, `cp`, `mkdir`, `tee`,
  `dd`, …) naming an absolute path elsewhere. `/dev/null` and friends are
  exempt, since discarding output is not a write anyone can be harmed by;
- `exec` refuses commands that mutate `data_file`, the single permitted
  dataset;
- `exec` refuses any command that so much as *names* a `forbidden_paths`
  entry, because the scope was narrowed to one file and the rest of that
  directory is out of bounds for reading too.

Reads outside `workdir` remain allowed — `setup` has to inspect `/opt`
interpreters, and the permitted dataset lives elsewhere by definition.

**Know what this is and is not.** The command guard is a best-effort textual
check, not a sandbox: a shell cannot be fully parsed, so a glob, a here-doc, or
a Python one-liner could still write outside scope. It exists to stop the
plausible mistake. The contract itself is upheld by `AGENTS.md` and by whoever
is driving; the token carries whatever permissions the account has.

Two subtleties worth knowing, both found by testing rather than reasoning:

- the workdir contains a space (`Fast MC CBSC`), so a token-based path regex
  truncates at `.../julian/Fast` and would flag legitimate in-workdir writes.
  The guard compares against the full workdir at the match offset instead;
- `2>/dev/null` is so common that treating it as an escape made ordinary
  commands fail, which is the fastest way to get a guard disabled.

### Operational constraint: pods are ephemeral

DiCOSApp sessions have an end time chosen at launch — the first pod observed
here ran 2 hours, a later one 3 days. **When a pod ends, every process inside it
dies**, so:

- long work must be checkpoint/resume-capable (this project already is) or fit
  inside one session. Prefer launching an app with a generous end time before
  starting anything lengthy;
- the shared filesystem persists across pods, so `.venv/`, `repo/`, and `prep/`
  survive. After a relaunch, `auth` with the new URL and `setup` restores a
  working session, and `setup` is a no-op when nothing needs repair;
- the port usually changes; the **token has so far not**, appearing to be
  per-user rather than per-pod, which is why `auth` accepts a bare URL.

## 2. What the host provides

Probed on `jupyterlabcpu-julianjuan` (the CPU DiCOSApp):

| | |
|---|---|
| CPU / RAM | **128 cores, 1,511 GB** — excellent for the CPU-bound conversion |
| GPU | none on the CPU pod; several GPU tiers exist as separate DiCOSApps (L40s, RTX 4090, RTX 3090, P100, and data-centre accelerators) |
| Shared FS | 13 PB total, 2.9 PB free, mounted at `~/sharedfs` |
| Batch system | **none reachable** — `sbatch`/`squeue`/`sinfo`/`condor_submit` all absent |
| Egress | works (pypi and github reachable), so `pip install` and `git clone` both work |
| git | 2.51.0 |

**There is no Slurm from inside a DiCOSApp pod.** Training therefore runs
*inside* a GPU DiCOSApp (see "Choosing a DiCOSApp" below), not as a batch
submission. This is the single biggest structural difference from the Vertex
backend, where jobs were submitted and outlived the client.

Which GPU tier is used is a transport decision. This project retired
hardware-permission screening and nothing here reinstates it: hardware is never
a precondition for running a separately declared experiment. Record what was
actually used in a run's evidence.

### Choosing a DiCOSApp

The portal lists many apps. Two constraints narrow it sharply:

1. **It must be a `Jupyter Lab GPU …` app.** The access method in this document
   is JupyterLab's token + REST + kernel websocket. Apps listed outside the
   Jupyter group (`PyTorch`, `Transformer`, `Code Server`, …) may expose a
   different interface, and `scripts/dicos.py` cannot drive them.
2. **Avoid the `with Tensorflow` variants.** This project is PyTorch; those
   images are built around TensorFlow and are the most likely to lack `torch`
   in the base environment.

So: prefer a plain `Jupyter Lab GPU <tier>` app on the highest data-centre
accelerator tier that shows as unused, falling back down the tiers (L40s, then
RTX 4090, then RTX 3090) if the top tier is busy. Treat a `CUDA 13` variant as a
second choice — a newer CUDA runtime may not match the base image's `torch`
build. `setup` validates the environment by import and rebuilds the venv if the
image differs, so a wrong guess is recoverable rather than fatal.

For the **conversion** step no GPU is needed at all; the CPU app (128 cores,
~1.5 TB RAM) is the better tool and leaves GPU allocation free for training.

### Numerics warning when moving off the T4

Accepted runs so far are FP32 on a T4, and a previous mixed-precision attempt
produced nonfinite gradients. Newer data-centre GPUs enable **TF32** for cuDNN
by default, which silently reduces mantissa precision relative to those runs.
Before training here, decide explicitly and record the decision:

```python
torch.backends.cuda.matmul.allow_tf32   # False by default in recent torch
torch.backends.cudnn.allow_tf32         # True by default -- the one to check
```

Leaving TF32 on is defensible for a *new* declared experiment, but it is a
numerics change, not a free speedup, and must not be introduced silently into a
run being compared against the existing epoch-4 checkpoints.

### Python environment

The pod's default kernel (`/opt/miniconda3`, Python 3.13) has no scientific
stack. The `asgc` conda env does:

```
/opt/miniconda3/envs/asgc/bin/python   3.11.13
  torch 2.8.0+cu128   numpy 2.1.3   scipy 1.15.3   sklearn 1.6.1
  matplotlib 3.10.0   pyyaml 6.0.2
  uproot / awkward:  ABSENT
```

Since `/opt` is not writable, the project uses a venv layered on that env, which
inherits torch/numpy and adds what is missing:

```bash
/opt/miniconda3/envs/asgc/bin/python -m venv --system-site-packages .venv
./.venv/bin/pip install uproot awkward
./.venv/bin/pip install -e repo
```

Note `torch 2.8.0+cu128` here vs `2.6.0+cu124` on Vertex. That is a genuine
environment difference to record in any run's evidence, not something to paper
over.

## 3. Verified invariants

| Invariant | Status |
|---|---|
| Permitted ROOT dataset identical to the canonical GCS source | **VERIFIED** — SHA-256 `b7c666040e42352e158a9a3f78158d147cb2e056c6c88248d892c956f5c7b533`, byte-for-byte match with the recorded canonical hash; 764,940 entries |
| Test suite passes on DiCOS | **67 passed, 1 failed** — the failure is `test_root_fixture.py`, which needs a 24 MB fixture excluded from git by `.gitignore` (`*.root`), not a science failure |
| Frozen geometry present on DiCOS with hash `e22d4cfb…` | **VERIFIED** — transported, then recomputed *on the host* and matched |
| Geometry *regenerated* from the DiCOS ROOT is physically identical | **VERIFIED with one caveat** — see below |
| Prepared corpus reproduces the canonical shards | **VERIFIED — all 187 shards byte-identical.** 764,940 events, 1,157,840,863 hits, every `shards[].sha256` and `n_hits` equal to the canonical manifest's, all five rejection counters zero, and the sentinel accounting exact (738,898 events, 13,251.328791066537 GeV total, 1.647373832954901 GeV max) |
| Split reproduces the canonical assignment | **VERIFIED** — 612,482 / 76,158 / 76,300 and `assignment_sha256 = f71003e07eb16baf4029387fd8e54b2e22b98981bbd6ee519a6d363167b4c8c8`, matching the parent recorded in the pilot split |

**The data pipeline reproduces bit-exactly on DiCOS.** Raw ROOT, prepared
shards, and split assignment are all byte-identical to the artifacts the
existing checkpoints were trained against, so those checkpoints remain
comparable and nothing here is a new declared dataset. Only the geometry needed
transporting rather than regenerating, for the float32 reason below.

### Geometry: regenerate vs. transport

Rescanning the DiCOS ROOT reproduced the structure exactly — 6,790 nodes,
65 layers, 107,920 edges — and every array came back bit-identical
(`positions_mm`, `cell_id`, `layer_index`, `subdetector`, `node_features`,
`valid_mask`, and the graph topology `edge_index`) **except one column**:

```
edge_features[:, distance_norm]   4,092 of 107,920 values differ
                                  max abs 1.192e-07,  max rel 1.173e-07
float32 eps                       1.1920929e-07
```

Only the single `sqrt`-derived column differs, by exactly one float32 ULP.
That is a library-version rounding difference (numpy 2.1.3 here), not a
different detector — the physical geometry is identical, which independently
confirms the DiCOS ROOT file really is the canonical dataset.

The geometry hash is nevertheless a strict byte hash, so it changed
(`a417d29d…`). **The resolution is to transport the frozen artifact, not
regenerate it**, exactly as the portability rule requires: geometry is a frozen,
hash-addressed input, so it moves across backends unchanged. The regenerated
copy was discarded; `prep/geometry_frozen/` holds the canonical one and its
hash was re-verified on the host after upload.

The general lesson for the remaining steps: **derived float artifacts will not
byte-reproduce across library versions.** Anything hash-pinned must be
transported. Only genuinely deterministic outputs should be regenerated, and
each one's hash must be checked, not assumed.

The three Vertex-specific test modules (`test_auto_smoke`,
`test_compute_extensions`, `test_vertex_training_hardening`) fail to import for
lack of `google.cloud`, which is expected and correct on this backend.

## 4. The dataset directory: one file in scope, the rest not

`sharedfs/work/IOP/ZDC_ML_20260620/dataset/` belongs to the group, not to this
project. It holds ten files: four dataset pairs (15k, 100k, 135k, 765k), each a
raw tree plus a `_transformed` variant, and two small helpers. **Exactly one is
in scope.** The findings below are recorded so no future agent needs to re-open
anything to re-derive them.

**`myTree_20251117_765k_0to300GeV_neutron_All.root`** — the only permitted
input — 25,022,001,408 bytes,
tree `myTree`, **764,940 entries**, 40 branches. Raw Geant4 output: per-hit
vectors (`ecal_cellID`, `ecal_energy`, `hcal_cellID`, `hcal_LayerID`,
`hcal_energy`, positions), MC truth (`mcPar_*`), and energy sums. **This is the
authoritative input** — it is the file the entire existing result set derives
from, and the one `configs/schema_production_myTree.yaml` describes.

**`myTree_20251117_765k_0to300GeV_neutron_All_transformed.root`** —
5,811,755,027 bytes, tree `tree`, **764,936 entries**, 3 branches:

```
cell    float[20][20]        mcPar   float[1][6]        hcal    float[64][10][10]
```

This is somebody's **dense-grid rebinning** for a CNN-style model, and it is
**not usable here**, for three independent reasons:

1. **Different geometry.** It flattens the detector onto regular grids —
   20×20 = 400 (matching the ECAL count) and 64×10×10 = **6,400** HCAL cells.
   This project's frozen geometry has **6,390** HCAL channels (63 layers × 100
   plus a final layer of **90**), so the transform pads that last layer from 90
   to 100 and invents 10 channels that do not exist.
2. **Different event count.** 764,936 vs 764,940 — **4 events are missing**, so
   event indices do not correspond and no split or selection hash could carry
   over.
3. **Discards cell identity.** The raw `cellID` and per-hit positions are gone,
   but the frozen geometry (hash `e22d4cfb…`, including the ganged-readout
   centroid rule) is derived from exactly those.

Using it would silently produce a different detector. **It is now out of scope
entirely — reading included** — and `scripts/dicos.py` refuses any command that
names it. The record above exists so that decision never needs re-litigating by
reopening the file.

## 5. Migration plan and status

1. ~~Establish programmatic access~~ — **done**, `scripts/dicos.py`, guards
   regression-tested in `tests/test_dicos_client.py` (17 tests, offline)
2. ~~Verify the raw dataset is the canonical one~~ — **done**, hash matches
3. ~~Stand up the environment and prove the code runs~~ — **done**, 67 tests pass
4. ~~Establish the frozen geometry on DiCOS under hash `e22d4cfb…`~~ — **done**,
   transported and verified on-host
5. ~~Produce the prepared shards and verify them~~ — **done**, all 187
   byte-identical to canonical
6. ~~Produce the split~~ — **done**, reproduces the canonical assignment
7. Train inside a GPU DiCOSApp — the only step remaining; see section 6

### Current remote layout

```
sharedfs/work/IOP/julian/Fast MC CBSC/
  .venv/                     asgc-derived venv (torch 2.8.0+cu128, uproot 5.7.5)
  repo/                      git clone, pip install -e
  prep/geometry_frozen/      canonical geometry, hash e22d4cfb… verified on-host
  _setup/                    scan logs and dataset hashes
```

### Regenerate or transport the prepared shards? — settled

Earlier drafts left this open. It is decided, on two grounds.

**Transport is not available.** The prepared shards live on GCS; the contract
for this host permits exactly one data source, the raw ROOT file. Copying a
second corpus in would also risk the "two canonical datasets" failure the
handoff forbids. So the shards are **produced on DiCOS from the permitted
file**, with the conversion parameters pinned to the canonical ones.

**The manifest hash cannot reproduce, for a reason unrelated to floats.**
`dataset_manifest.json` records `source_files[].path`, and the canonical run
read from `/tmp/cbsc_zdc_prepare/source/production.root` while DiCOS reads from
the shared filesystem. Two different paths, therefore two different manifests,
therefore `5a6d9632…` can never match no matter how deterministic the pipeline
is. Comparing it would be a category error.

**What to compare instead**, in decreasing strength:

1. **Per-shard SHA-256** against the canonical manifest's `shards[].sha256`.
   These cover event content only, so they are the real test of whether the
   corpus is identical.
2. Event count (`764,940`), shard count (`187`), the 4,096/3,084 split, and
   the recorded rejection counters (all zero).
3. The sentinel-energy accounting: `738,898` events carrying excluded sentinel
   energy totalling `13,251.328791066537` GeV, maximum `1.647373832954901` GeV.

Record the outcome either way. If the shard hashes match, provenance is
end-to-end and existing checkpoints stay comparable. If they do not, the DiCOS
corpus is a **new declared artifact** with its own hashes, and anything trained
on it is a new experiment rather than a continuation — which must be said
plainly rather than glossed.

### Splitting: use `event_hash`, not `source_group`

`cbsc-zdc split --group-by source_group` **fails** on this corpus with "split
creation produced an unassigned or empty partition". The corpus is converted
from a single ROOT file, so every event carries `source_group == 0`; with one
group the greedy stratified allocation cannot seed three partitions. The
canonical production split used `--group-by event_hash`, which assigns per event
from a stable hash and reproduces the recorded counts and assignment hash
exactly. Use:

```bash
cbsc-zdc split --manifest prep/data/dataset_manifest.json   --output prep/splits.json --seed 20260723 --group-by event_hash   --fractions 0.8 0.1 0.1
```

## 6. Training on a GPU — the verified path

Everything up to training is done and checked. This section is the procedure,
and every step below was executed successfully on the host (the training step
as a CPU smoke run that was stopped once it was confirmed stepping).

### What is already on the host

```
prep/geometry_frozen/   canonical geometry, hash e22d4cfb… verified on-host
prep/data/              187 shards + manifest, byte-identical to canonical
prep/splits.json        612,482 / 76,158 / 76,300, assignment f71003e0…
prep/train_data_audit.json   reproduces the canonical audit exactly
prep/checkpoints/       calibrated_lr3e4_best_epoch4.pt, sha 3f1022b8…
```

`cbsc-zdc` preflight passes against these with `verified_shards: 187`.

### Session start

```bash
python scripts/dicos.py auth "<address-bar URL>"   # token is reused
python scripts/dicos.py setup                      # expect all nine checks green
python scripts/dicos.py exec "nvidia-smi"          # confirm the GPU is present
```

`setup` rebuilds the venv automatically if the GPU image's base environment
differs from the CPU pod's — it validates by import, not by existence.

### Freezing a config, then training

Never hand-edit a frozen config. Write a template, freeze it, record both
hashes:

```bash
# 1. template (a copy of a repo template with device/paths adjusted) --
#    keep it in prep/, not in repo/, so the clone stays clean
# 2. freeze it against the on-host artifacts
cbsc-zdc freeze-config   --template ../prep/<your_template>.yaml   --audit    ../prep/train_data_audit.json   --geometry ../prep/geometry_frozen   --manifest ../prep/data/dataset_manifest.json   --splits   ../prep/splits.json   --output   ../prep/<your_frozen>.yaml

# 3. train, detached -- never through `exec`
python scripts/dicos.py start   "cd repo && PYTHONPATH=src ../.venv/bin/python -m cbsc_zdc.cli train      --config ../prep/<your_frozen>.yaml" --name train_r1
python scripts/dicos.py jobs
python scripts/dicos.py logs train_r1 --tail 40
python scripts/dicos.py stop train_r1        # if it must be ended early
```

Preflight hashes all 187 shards before the first step, which takes a few
minutes and produces no output; that is expected, not a hang. Progress after
that goes to the run directory rather than stdout, so `jobs` showing RUNNING
with a small log is normal — confirm real work with
`exec "ps -eo pid,%cpu,rss,cmd | grep [c]bsc_zdc"`.

### Choosing the experiment: two different things

**A fresh run on the full split** is ready now. The existing families trained on
a 26,624-event bank, 4.3% of what is available, and "trained on only a fraction"
is one of the recorded limitations — so a full-split run is the more valuable
experiment and needs nothing further.

**Continuing an existing family** is possible but has a wrinkle worth
understanding before committing. The accepted epoch-4 runs used the *pilot*
bank, and `training_pilot_splits.json` pins `manifest_sha256 = 5a6d9632…`, the
canonical manifest. The DiCOS manifest hashes to `688b440c…` — not because the
data differs (all 187 shard hashes match) but because a manifest records its
source **path**. `ShardedSparseDataset` compares that hash and would refuse the
transported pilot split. Regenerating the pilot bank on DiCOS, via the logic in
`cloud/vertex_prepare.py`, is the way to continue those exact families. Do not
"fix" this by relaxing the hash check.

### Getting checkpoints onto the host

DiCOS has no `gcloud`, `gsutil`, `rclone`, or `google-cloud-storage`, so it
cannot pull from GCS itself. Transfer via this machine instead — download with
`gcloud` locally, then `put`, which chunks and verifies by SHA-256:

```bash
python scripts/dicos.py put local_checkpoint.pt prep/checkpoints/<name>.pt
```

`calibrated_lr3e4_best_epoch4.pt` was moved this way and verified on-host
(hash `3f1022b8…`, `epoch=4`, `best_metric=4.7380412609301406`).

### Two things that are NOT on the host, and matter

**The fixed 50x5 visual bank is absent.** Epoch visualisation (handoff section
12, `docs/VISUALIZATION_DASHBOARD.md`) expects a frozen selection of 50
validation conditions, recorded under selection hash
`f70529198aa9575cd2ebc816fd0800ed5a1a3dcd918dab3845b5dc5d85dc59b6`. That
selection was drawn from the **pilot** validation partition, which does not
exist here — this host has the production split. A run configured with
`evaluation.visualization.enabled` will therefore draw its own bank, with a
different selection hash, and its epochs will not be visually comparable to the
existing published epochs. Decide deliberately: either accept a new bank for a
new declared experiment and record its hash, or reconstruct the pilot partition
first. Do not silently publish a differently-banked epoch alongside the old ones.

**Only the `best` checkpoint is staged.** `prep/checkpoints/` holds
`calibrated_lr3e4_best_epoch4.pt` (`3f1022b8…`). Handoff section 11 asks for
both `best` and `last` hashes to be verified before a continuation, and `last`
(`42782827de374dedcbba50a784460833ad16129c474f98553622b39d6467720a`) is not
here. Transfer it the same way if a continuation is intended; the other three
families are absent entirely.

### Decide TF32 before the first real run

Accepted runs are FP32 on a T4. Newer accelerators enable **TF32 for cuDNN by
default**, which silently lowers precision:

```python
torch.backends.cuda.matmul.allow_tf32   # False by default
torch.backends.cudnn.allow_tf32         # True by default -- this is the one
```

Leaving it on is defensible for a newly declared experiment and is a real
speed-up, but it is a numerics change. It must not enter a run being compared
against the existing epoch-4 checkpoints without being declared and recorded.

### Resolved during step 5-6

- **Conversion cost — measured.** ~100 minutes single-threaded on the CPU pod
  for the full 25 GB. The 128 cores go unused by the reader; if the corpus is
  ever rebuilt, parallelising by entry range is the obvious win.
- **Manifest reproducibility — answered.** Every shard reproduced byte-
  identically; only the manifest's own hash differs, because it records the
  source path. Provenance is end-to-end. Transport from GCS was never needed
  and is not available under the one-data-source rule.
- **Torch version.** 2.8.0+cu128 here vs 2.6.0+cu124 on Vertex. Fine for new
  runs, but it is an environment difference that belongs in the evidence of any
  result produced here, and it makes bit-exact reproduction of existing
  checkpoints unlikely.
