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
python scripts/dicos.py info                 # probe the remote environment
python scripts/dicos.py exec "nvidia-smi"    # run a shell command
python scripts/dicos.py ls .                 # list the workdir
python scripts/dicos.py put local remote     # upload
python scripts/dicos.py get remote local     # download
```

Steps 1 and 2 are the whole session start-up. `setup` clones or updates the
repo, builds or repairs the venv, verifies the frozen geometry hash, and reports
the GPU — so a brand-new pod, including a GPU image different from the CPU one,
is ready without any further manual work.

### Starting a session (do this first, every time)

The DiCOSApp token changes whenever the pod restarts, so a stored token is
usually stale.

**If you catch the launch URL while it still has `?token=…`** (it appears for a
moment right after the app opens), one argument is enough:

```bash
python scripts/dicos.py auth "http://scale-k8s-master01.twgrid.org:32065/?token=abc123…"
```

**Usually you will not catch it.** JupyterLab moves the token into a cookie and
rewrites the address bar to `.../lab/tree/...`, so a URL copied even seconds
later contains no token. Recover it from inside the pod — in JupyterLab open
*File ▸ New ▸ Terminal* and run:

```bash
jupyter server list
# Currently running servers:
# http://<pod-name>:8888/?token=57115a0b…  ::  /dicos_ui_home/<account>
```

Then pass the address-bar URL and that token as two arguments:

```bash
python scripts/dicos.py auth "http://scale-k8s-master01.twgrid.org:32065/lab/tree/..." "57115a0b…"
```

The token is also in `~/.local/share/jupyter/runtime/jpserver-<pid>.json`, which
persists in `HOME`, if reading a file is easier than running a command.

`auth` accepts any of: a URL containing the token, a URL plus a separate token,
or a bare token on its own. It verifies against the server before saving, and
saves nothing if authentication fails.

> The address `jupyter server list` prints is the **pod-internal** one
> (`http://<pod-name>:8888`), which is not reachable from outside the cluster.
> `auth` detects this and keeps the working external URL rather than storing the
> internal one, so pasting that line verbatim is safe.

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
  "base_url": "http://scale-k8s-master01.twgrid.org:32065",
  "token": "<DiCOSApp JupyterLab token>",
  "jupyter_root": "/dicos_ui_home/julianjuan",
  "workdir": "/dicos_ui_home/julianjuan/sharedfs/work/IOP/julian/Fast MC CBSC",
  "readonly_data": ["<the two ROOT files>"]
}
```

### Two address spaces

A recurring source of confusion, handled by the client: the contents API is
rooted at the server's `root_dir` (the user's `HOME`), while shell commands use
absolute paths. The Jupyter URL path `sharedfs/work/IOP/julian/Fast MC CBSC`
and the filesystem path
`/dicos_ui_home/julianjuan/sharedfs/work/IOP/julian/Fast MC CBSC` are the same
directory. `jupyter_root` in the config is what lets the client translate.

### Write scope

Enforced client-side, matching the constraint agreed with the data owner:
`put`/`mkdir` refuse any destination outside `workdir`, and `exec` refuses
commands that redirect into or mutate a declared `readonly_data` path. This is
a guard against honest mistakes, not a security boundary — the token carries
whatever permissions the account has.

### Operational constraint: pods are ephemeral

DiCOSApp sessions have an end time (the CPU pod observed here ran a 2-hour
session). **When the pod expires the token changes and any running process
dies.** Consequences:

- long work must be checkpoint/resume-capable (this project already is) or fit
  inside one session;
- after a restart, run `auth` with the new launch URL, then `setup`;
  everything on the shared filesystem (`.venv/`, `repo/`, `prep/`) persists,
  so nothing else needs redoing.

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
| Raw ROOT dataset identical to the canonical GCS source | **VERIFIED** — SHA-256 `b7c666040e42352e158a9a3f78158d147cb2e056c6c88248d892c956f5c7b533`, byte-for-byte match with the recorded canonical hash; 764,940 entries |
| Test suite passes on DiCOS | **67 passed, 1 failed** — the failure is `test_root_fixture.py`, which needs a 24 MB fixture excluded from git by `.gitignore` (`*.root`), not a science failure |
| Frozen geometry present on DiCOS with hash `e22d4cfb…` | **VERIFIED** — transported, then recomputed *on the host* and matched |
| Geometry *regenerated* from the DiCOS ROOT is physically identical | **VERIFIED with one caveat** — see below |
| Dataset manifest hash `5a6d9632…` reproduces | not yet attempted |

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

## 4. The two ROOT files

Both live in a directory this project must treat as read-only.

**`myTree_20251117_765k_0to300GeV_neutron_All.root`** — 25,022,001,408 bytes,
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

Using it would silently produce a different detector. It should be ignored for
this project.

## 5. Migration plan and status

1. ~~Establish programmatic access~~ — **done**, `scripts/dicos.py`, guards
   regression-tested in `tests/test_dicos_client.py` (17 tests, offline)
2. ~~Verify the raw dataset is the canonical one~~ — **done**, hash matches
3. ~~Stand up the environment and prove the code runs~~ — **done**, 67 tests pass
4. ~~Establish the frozen geometry on DiCOS under hash `e22d4cfb…`~~ — **done**,
   transported and verified on-host
5. Produce the prepared shards from the raw ROOT and record their manifest hash
6. Produce the split, then train inside a GPU DiCOSApp

### Current remote layout

```
sharedfs/work/IOP/julian/Fast MC CBSC/
  .venv/                     asgc-derived venv (torch 2.8.0+cu128, uproot 5.7.5)
  repo/                      git clone, pip install -e
  prep/geometry_frozen/      canonical geometry, hash e22d4cfb… verified on-host
  _setup/                    scan logs and dataset hashes
```

### Open questions for step 5-6

- **Conversion cost.** The geometry scan alone read the 25 GB file in ~20 min at
  ~465 entries/s single-threaded. Full conversion writes 187 shards and will be
  materially longer; the pod's session limit means it should be run resumably or
  on a longer-lived app. The CPU pod's 128 cores are unused by the current
  single-threaded reader — worth revisiting before committing to a long run.
- **Manifest reproducibility.** Given the float32 finding above, the shard
  manifest hash `5a6d9632…` may or may not byte-reproduce. Either outcome is
  informative and must be recorded, not worked around: if it does, provenance is
  end-to-end; if it does not, the prepared artifacts should be transported from
  GCS instead, and the reason documented.
- **Torch version.** 2.8.0+cu128 here vs 2.6.0+cu124 on Vertex. Fine for new
  runs, but it is an environment difference that belongs in the evidence of any
  result produced here, and it makes bit-exact reproduction of existing
  checkpoints unlikely.
