# CBSC-ZDC v2.2: Complete Implementation, Training, QA, and Results Guide

**Audience:** an implementation agent who knows basic Python and introductory machine learning but is not expected to redesign the model.

**Goal:** turn the repository ZIP plus the production Geant4 corpus into a frozen, auditable experiment for single-neutron ZDC shower generation, then train, evaluate, benchmark, and report it without silently changing the scientific contract.

**Project target:** approximately 765,000 Geant4 single-neutron events generated over 0–300 GeV incident **kinetic** energy, with the primary reported domain fixed to 50–250 GeV.

**Detector contract:** 65 longitudinal layers and 6,790 valid readout channels: 400 ECAL channels plus 6,390 HCAL channels. The active geometry must be established from the production files and frozen by hash before training.

---

## 0. Read this first: current assurance boundary

This repository is an executable research scaffold. Its synthetic tests establish software and algebraic properties. They do not establish that the model reproduces Geant4.

The following are independent QA areas needed before claiming a validated
FastMC:

1. the production ROOT schema and units pass inspection;
2. the 6,790-channel geometry and graph are frozen and independently reviewed;
3. the complete training selection is audited;
4. the split manifest is frozen before model development;
5. all final metrics are computed on untouched test events;
6. structural invariants pass;
7. fidelity metrics are reported across all primary energy bins and all seeds;
8. diversity, memorization, downstream reconstruction, and speed studies pass;
9. the result is compared against competent internal and external baselines.

The code intentionally separates **structural validity** from **physics fidelity**. An untrained model can satisfy exact nonnegativity and energy closure while being a very poor Geant4 surrogate.

---

## 1. Repository map

```text
cbsc_zdc_fastmc_v2_2/
├── README.md                         start here
├── AGENTS.md                         agent operating contract
├── Dockerfile                        Vertex/custom-container image
├── pyproject.toml                    package and CLI definition
├── configs/
│   ├── schema_sample_edm4hep.yaml    sample ROOT branch contract
│   ├── gates_primary.yaml            versioned diagnostic thresholds
│   ├── loss_weights_default.yaml     starting joint-loss weights
│   └── templates/                    stage and range experiment templates
├── docs/
│   ├── IMPLEMENTATION_GUIDE.md       this document
│   ├── MODEL_WALKTHROUGH.md          beginner-facing model explanation
│   ├── DATA_CONTRACT.md              exact data and geometry semantics
│   ├── LOSS_WEIGHT_PROTOCOL.md       loss-weight selection procedure
│   ├── EVALUATION_PROTOCOL.md        metrics, QA thresholds, and interpretation
│   ├── VERTEX_AI_RUNBOOK.md          cloud execution procedure
│   └── TROUBLESHOOTING.md            ranked failure diagnosis
├── scripts/
│   ├── verify_repository.sh
│   ├── smoke_test.sh
│   ├── prepare_production_artifacts.sh
│   └── run_primary_evaluation.sh
├── src/cbsc_zdc/                     active implementation
├── tests/                             fast executable contract tests
├── vertex/submit_custom_job.py       Vertex submission helper
├── fixtures/                          schema-only ROOT fixture
├── audit/                             supplied audits and dispositions
├── paper/                             revised specification
├── references/                        primary-source register
└── legacy/                            previous materials; not active code
```

Never train from `legacy/`. It exists only for provenance.

---

## 2. End-to-end evidence map

The production workflow has ordered dependencies and QA checkpoints. The order
protects provenance: downstream artifacts must cite trustworthy upstream
artifacts. A finding does not grant or deny permission to run a new or corrected
experiment.

```text
ZIP integrity
  ↓
Environment install
  ↓
Repository tests and synthetic smoke run
  ↓
ROOT schema inspection
  ↓
Geometry scan and hash freeze
  ↓
One-time ROOT conversion
  ↓
One-time split creation
  ↓
Complete train-split data audit
  ↓
Config freeze
  ↓
Small target-hardware pilot
  ↓
Component stage diagnostics
  ↓
Loss-weight calibration and validation-only sensitivity study
  ↓
Matched 0–300 vs 50–250 final training runs, three seeds each
  ↓
Validation selection
  ↓
Frozen test evaluation
  ↓
Baselines, ablations, reconstruction, memorization, timing
  ↓
Scientific result or documented negative result
```

An integrity failure quarantines the affected artifact: diagnose it, correct the
upstream artifact, regenerate dependent hashes, and rerun before trusting or
reusing it. A poor scientific metric or performance result is preserved as a QA
finding and a place for further investigation. Neither category is a global
progression decision. Never weaken a diagnostic threshold merely because
training already consumed compute.

---

## 3. From ZIP to a verified local installation

### 3.1 Extract and enter the repository

```bash
unzip CBSC_ZDC_FASTMC_v2_2_REVISED_REPOSITORY.zip
cd cbsc_zdc_fastmc_v2_2
```

Verify the bundle checksum if a manifest accompanies the ZIP:

```bash
sha256sum -c SHA256SUMS.txt
```

Expected: every line prints `OK`.

### 3.2 Create an isolated environment

Recommended production baseline: Python 3.10–3.12 with a CUDA-enabled PyTorch build supported by the target Vertex image.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
```

Install the full local toolchain:

```bash
python -m pip install --no-build-isolation -e '.[root,eval,dev]'
```

For Vertex submission from the same machine:

```bash
python -m pip install --no-build-isolation -e '.[root,eval,dev,cloud]'
```

Why `--no-build-isolation` is shown: it prevents a restricted/offline environment from attempting to download a second build environment. It is not required when normal package access is available.

### 3.3 Verify the repository

```bash
bash scripts/verify_repository.sh
```

Current expected test result in the bundled QA environment:

```text
18 passed
2 PyTorch Transformer nested-tensor performance warnings
```

The warnings arise from `norm_first=True` in `TransformerEncoderLayer`. They are performance notices, not failed numerical checks.

### 3.4 Run the complete synthetic smoke path

```bash
bash scripts/smoke_test.sh /tmp/cbsc_zdc_smoke
```

This executes synthetic data creation, group splitting, data audit, config freezing, one-epoch CPU training, checkpoint load, sampling, invariant QA, and timing.

Success criterion: the script exits with status 0 and prints `Smoke test passed`.

Interpretation: this proves that the CLI chain is connected. It does not prove detector fidelity. The final release smoke run produced zero nonfinite/negative/dust/count failures and layer/event closure within the declared tolerance; its CPU timing is only a software smoke measurement and must not be cited as FastMC performance.

---

## 4. Exact data semantics

### 4.1 Raw event condition

The only raw event condition is the incident neutron four-vector:

```text
p4_total_gev = [E_total, p_x, p_y, p_z]
```

All entries are in GeV. `E_total` is relativistic total energy, not Geant4 gun kinetic energy.

The neutron mass-shell relation is

```text
E_total² - p_x² - p_y² - p_z² = m_n²,
```

with

```text
m_n = 0.93956542052 GeV.
```

The incident kinetic energy used for range cuts and plots is

```text
K_inc = E_total - m_n.
```

The momentum magnitude is

```text
|p| = sqrt(E_total² - m_n²).
```

The normalized direction is

```text
u = (p_x, p_y, p_z) / |p|.
```

The deterministic condition vector passed to the neural network is

```text
c_raw = [log(1 + K_inc / 100 GeV), u_x, u_y, u_z, log(E_total / 1 GeV)].
```

A learned condition encoder maps these five numbers to a 128-dimensional representation by default.

### 4.2 Raw Geant4 detector target

The primary target mode is `raw_deposit`:

```text
Y = [Y_1, ..., Y_6790],  Y_i ≥ 0,
```

where `Y_i` is the event’s total stored deposited energy for readout channel `i`, in GeV, after summing duplicate hits to the same channel.

The total modeled detector response is

```text
T = sum_i Y_i.
```

No unobserved reserve variable is used. In raw mode, the generated event must satisfy

```text
sum_i Ŷ_i = T_hat
```

within the configured floating-point tolerance.

### 4.3 Optional thresholded mode

`thresholded_readout` is a separate experiment, not a training trick. A cell is retained only when its stored energy meets a frozen detector/analysis threshold `tau`:

```text
Y_i^(tau) = Y_i * 1[Y_i ≥ tau].
```

The target total is then the sum of retained readout, not the raw total. Do not mix raw energy with a hidden subthreshold residual in this mode.

### 4.4 Geometry metadata

Static geometry includes:

- cell ID and subdetector;
- world position `(x,y,z)` in mm;
- longitudinal layer index;
- valid-channel mask;
- graph edges and edge features.

Geometry is not an additional random event condition. It is fixed detector metadata and must be hashed.

Project-history detector context, to be verified against the production geometry artifact:

- ECAL: a 20 x 20 LYSO + SiPM cell plane, nominal cell size 3 x 3 x 7 cm, approximately 60 x 60 cm face, and approximately 6.5 radiation lengths of depth;
- HCAL: 64 steel/scintillator + SiPM sampling layers, nominal envelope approximately 65 x 60 x 163 cm;
- active readout contract: 400 ECAL plus 6,390 HCAL channels.

These prose dimensions explain the intended detector, but they do not override the production channel map. The executable experiment is defined by the frozen cell IDs, positions, layer map, ganging, valid mask, edges, and geometry hash. If the production files contradict the historical dimensions or the strict 6,790-channel contract, stop and resolve the detector definition before conversion.

---

## 5. Inspect the supplied schema fixture

The included ROOT file is a structure fixture, not production data. Its detected branch family includes:

```text
MCParticles.PDG
MCParticles.generatorStatus
MCParticles.mass
MCParticles.momentum.x/y/z
MCParticles.vertex.x/y/z
EcalFarForwardZDCHits.cellID
EcalFarForwardZDCHits.energy
EcalFarForwardZDCHits.position.x/y/z
HcalFarForwardZDCHits.cellID
HcalFarForwardZDCHits.energy
HcalFarForwardZDCHits.position.x/y/z
```

Once Uproot and Awkward are installed:

```bash
cbsc-zdc inspect-root \
  fixtures/outfile_neutron1_schema_fixture.root \
  --schema configs/schema_sample_edm4hep.yaml \
  --output artifacts/fixture_root_inspection.json
```

Review:

1. tree name;
2. exact branch spellings;
3. scalar versus jagged branch types;
4. energy and position units;
5. neutron PDG and generator-status selection;
6. sentinel cell IDs;
7. number of primary candidates per event.

Do not infer production units merely because the sample branch names match. Confirm them from the production software contract and numerical distributions.

---

## 6. Freeze the production ROOT contract

Copy the sample schema before modifying it:

```bash
cp configs/schema_sample_edm4hep.yaml configs/schema_production_zdc.yaml
```

For every ROOT file family, run:

```bash
cbsc-zdc inspect-root /data/zdc/file_000.root \
  --schema configs/schema_production_zdc.yaml \
  --output artifacts/root_file_000_inspection.json
```

Required decisions:

- Is generator energy kinetic? The repository assumes yes for Geant4 particle-gun style data, then constructs total four-vector energy from momentum and mass.
- Are hit energies already in GeV?
- Are positions in mm?
- Does `generatorStatus == 1` uniquely select the incident neutron?
- Is PDG 2112 sufficient to distinguish it from secondaries?
- Does `cellID == -100` or another sentinel occur?
- Is the generator vertex fixed across all events?
- Does each event contain exactly one valid incident neutron?

If any answer differs, update the schema or converter contract and add a regression test before conversion.

---

## 7. Freeze geometry

### 7.1 Scan all production files

```bash
cbsc-zdc scan-geometry /data/zdc/*.root \
  --schema configs/schema_production_zdc.yaml \
  --output artifacts/geometry \
  --position-tolerance-mm 0.001 \
  --z-tolerance-mm 0.01 \
  --step-size 2048
```

Production strict mode expects:

```text
n_nodes = 6790
n_layers = 65
layer_counts = [400] + [100] * 63 + [90]
```

Use `--no-strict-counts` only during diagnosis. A final production geometry must return to strict mode or have a formally revised detector contract.

### 7.2 Review geometry outputs

Required files include:

```text
artifacts/geometry/geometry.npz
artifacts/geometry/geometry_manifest.json
artifacts/geometry/cell_map.json
```

Review at minimum:

- exact node and layer counts;
- ECAL/HCAL assignment;
- unique cell IDs within each subdetector;
- position consistency for repeated cell IDs;
- z-ordering and layer grouping;
- edge count and edge-type distribution;
- zero-degree and isolated-node checks;
- geometry hash.

The graph is an implementation hypothesis. It must be retained only if it improves held-out fidelity enough to justify its latency and memory.

---

## 8. Convert ROOT once

Primary raw-deposit conversion:

```bash
cbsc-zdc convert /data/zdc/*.root \
  --schema configs/schema_production_zdc.yaml \
  --geometry artifacts/geometry \
  --output artifacts/data \
  --target-mode raw_deposit \
  --threshold-gev 0 \
  --min-kinetic-gev 0 \
  --max-kinetic-gev 300 \
  --shard-size 4096 \
  --step-size 2048 \
  --fixed-vertex-tolerance-mm 0.001
```

The converter:

1. selects the primary neutron;
2. constructs total-energy four-momentum;
3. computes kinetic energy;
4. rejects events outside 0–300 GeV;
5. enforces fixed-vertex tolerance;
6. rejects negative/nonfinite hit energy;
7. maps `(subdetector, cellID)` to the frozen channel index;
8. sums duplicate hits in a channel;
9. writes sparse compressed shards;
10. writes source and artifact hashes.

Review `artifacts/data/dataset_manifest.json` before splitting. Any nonzero rejection category must be explained. Do not silently discard a large or energy-dependent event class.

### 8.1 Source groups

The active converter assigns `source_group` by ROOT file. This is leakage-safe only when ROOT files correspond to independent Geant4 job/run/seed families.

If one ROOT file combines unrelated jobs but exposes no run/seed metadata, use `event_hash` splitting and disclose the limitation. Do not invent groups from contiguous row ranges unless the production process proves those ranges correspond to independent simulations.

---

## 9. Create the split once

Preferred split:

```bash
cbsc-zdc split \
  --manifest artifacts/data/dataset_manifest.json \
  --output artifacts/splits.json \
  --fractions 0.8 0.1 0.1 \
  --group-by source_group \
  --seed 20260723
```

Fallback when independent source groups do not exist:

```bash
cbsc-zdc split \
  --manifest artifacts/data/dataset_manifest.json \
  --output artifacts/splits_event_hash.json \
  --fractions 0.8 0.1 0.1 \
  --group-by event_hash \
  --seed 20260723
```

Why 80/10/10:

- approximately 80% gives the generator maximum exposure to rare shower modes;
- approximately 10% validation is large enough for stable energy-bin and distributional model selection;
- approximately 10% test leaves a large untouched bank for final conditional distributions, classifier tests, and reconstruction studies.

Group integrity takes priority over exact percentages. With large job groups, realized fractions may differ slightly from 80/10/10.

The same split manifest must be used for both training-support experiments:

- model A trains on 0–300 GeV;
- model B trains on 50–250 GeV;
- both validate and test on the same 50–250 GeV event bank;
- stress metrics for 0–50 and 250–300 GeV are reported separately.

This isolates the effect of broader training support from architecture and test-sample variation.

---

## 10. Audit the entire training split

```bash
cbsc-zdc audit-dataset \
  --manifest artifacts/data/dataset_manifest.json \
  --splits artifacts/splits.json \
  --split train \
  --kinetic-range 0 300 \
  --output artifacts/train_data_audit.json
```

Review:

- selected event count;
- kinetic-energy range;
- zero-response frequency;
- negative-response count;
- total-response and hit-count quantiles;
- response-to-kinetic ratio quantiles;
- mass-shell residual;
- normalization values;
- conservative sampling caps.

The finite response cap is a numerical safety rail derived only from the complete training selection. It is not a physical assertion that the detector can never exceed a particular fraction.

Stop if:

- mass-shell residuals are inconsistent with serialization precision;
- negative energies exist;
- positive detector response appears at exactly zero kinetic energy without a documented source;
- tails appear to be unit mistakes;
- train/validation/test assignments overlap;
- energy coverage is unexpectedly missing.

---

## 11. Freeze configurations

Never train directly from an unfrozen template.

Example full-range config:

```bash
cbsc-zdc freeze-config \
  --template configs/templates/train_full_0_300_raw.yaml \
  --audit artifacts/train_data_audit.json \
  --geometry artifacts/geometry \
  --manifest artifacts/data/dataset_manifest.json \
  --splits artifacts/splits.json \
  --output configs/frozen_full_0_300_seed20260723.yaml
```

Primary-only comparison config:

```bash
cbsc-zdc freeze-config \
  --template configs/templates/train_primary_50_250_raw.yaml \
  --audit artifacts/train_data_audit.json \
  --geometry artifacts/geometry \
  --manifest artifacts/data/dataset_manifest.json \
  --splits artifacts/splits.json \
  --output configs/frozen_primary_50_250_seed20260723.yaml
```

A frozen config records hashes of the template, audit, geometry manifest, dataset manifest, split manifest, and assignment file. Do not hand-edit it. Change the template and freeze again.

---

## 12. Model architecture in operational order

The generator is hierarchical because a 6,790-dimensional sparse shower is easier to learn when physically meaningful global variables are generated first.

### 12.1 Condition encoder

Input: five deterministic features derived from the neutron four-vector.

Output:

```text
c in R^128
```

Default network: linear layer, SiLU activation, two residual MLP blocks, and layer normalization.

### 12.2 Visible-response hurdle

```text
V ~ Bernoulli(sigmoid(f_V(c))).
```

`V=0` means the modeled readout is exactly zero.

Loss: binary cross-entropy.

### 12.3 Total-response mixture density

For visible events, transform response:

```text
y_T = log(1 + T / s_T),   s_T = 10 GeV by default.
```

The response head predicts a finite mixture of Normal distributions for `y_T`:

```text
p(y_T | c, V=1) = sum_m pi_m(c) Normal(y_T; mu_m(c), sigma_m(c)).
```

Loss: negative log-likelihood.

At sampling, `T` is transformed back with `expm1` and clipped only by the train-audit numerical safety cap.

### 12.4 First positive layer

```text
L0 ~ Categorical(softmax(f_L(c,T))).
```

Loss: categorical cross-entropy on visible events.

### 12.5 Active-layer mask

For each layer:

```text
A_l ~ Bernoulli(sigmoid(f_A(c,T,L0,l))).
```

Hard constraints:

```text
A_l = 0 for l < L0,
A_L0 = 1,
A_l = 0 for all l when V = 0.
```

Loss: binary cross-entropy.

### 12.6 Longitudinal energy profile by conditional flow matching

Truth layer shares are

```text
q_l = D_l / T,
```

where `D_l` is the observed energy in layer `l` and

```text
sum_l D_l = T.
```

The continuous target is centered log share on active layers. Flow matching constructs

```text
x_0 ~ Normal(0,I),
t ~ Uniform(0,1),
x_t = (1-t)x_0 + t x_1,
u_t = x_1 - x_0.
```

The model learns

```text
v_theta(x_t,t,c,T,A) approximately u_t
```

using masked mean-squared error. At generation, an ODE is integrated from noise to the learned profile state. A masked softmax then guarantees nonnegative layer budgets summing exactly to `T`.

### 12.7 Layer hit counts

For every layer with `N_l` valid channels:

```text
K_l ~ Categorical({0,1,...,N_l}).
```

Dynamic masks enforce:

- inactive layer: `K_l=0`;
- active raw-deposit layer: `K_l>=1`;
- thresholded layer: `K_l*tau <= D_l`;
- count cannot exceed geometry.

Loss: categorical cross-entropy, with inactive zero-count examples downweighted to avoid domination.

### 12.8 Geometry-aware support scorer

For every node, a score is predicted using:

- node geometry features;
- event condition;
- generated/truth layer energy;
- count fraction;
- edge-conditioned message passing;
- layer-level Transformer context.

The primary layer Transformer is bidirectional. Causal depth-only attention is an ablation, not an assumed physical requirement.

Losses:

- class-balanced support BCE;
- pairwise ranking loss between positive and negative cells.

### 12.9 One Gumbel-Top-k support draw

For layer `l`, add Gumbel noise to support scores and choose exactly `K_l` valid channels. This is the only support-sampling stochasticity.

It produces a support set `H_l` with

```text
|H_l| = K_l.
```

### 12.10 Share flow and exact decoder

A second conditional flow predicts continuous energy-share logits only on selected cells.

Raw mode decoder:

```text
Ŷ_i = D_l * exp(r_i) / sum_{j in H_l} exp(r_j),  i in H_l,
Ŷ_i = 0,                                          i not in H_l.
```

Thresholded mode decoder:

```text
Ŷ_i = tau + (D_l - K_l tau) * softmax(r)_i,       i in H_l,
Ŷ_i = 0,                                          i not in H_l.
```

Consequences:

- exactly `K_l` selected channels;
- exact zero outside support;
- no positive subthreshold dust in thresholded mode;
- nonnegative energy;
- exact layer budget closure in real arithmetic;
- event total closes to generated `T` within floating tolerance.

---

## 13. Loss function and exact starting weights

The joint objective is

```text
L_total = sum_j lambda_j L_j.
```

Bundled starting values:

| Component | Symbol | Default weight |
|---|---:|---:|
| Visible BCE | `L_visible` | 1.00 |
| Response mixture NLL | `L_response` | 1.00 |
| First-layer CE | `L_first` | 0.50 |
| Active-layer BCE | `L_active` | 0.50 |
| Profile flow MSE | `L_profile` | 1.00 |
| Count CE | `L_count` | 0.75 |
| Support BCE | `L_support_bce` | 1.00 |
| Support ranking | `L_support_rank` | 0.25 |
| Share flow MSE | `L_share` | 1.00 |

These are **starting priors**, not universal optimal constants. No paper can determine the correct weights for this detector before observing this implementation’s gradient scales and validation tradeoffs.

The repository uses a controlled fixed-weight protocol inspired by gradient-normalization research:

1. normalize each component internally by event/active-element counts;
2. debug each component in isolation;
3. run a short joint pilot with default weights;
4. measure median gradient norms on the shared condition encoder over training batches;
5. calculate inverse-norm weights, clip each to `[0.25,4.0]`, normalize their mean to 1;
6. freeze the proposed weights;
7. run validation-only sensitivity tests around major loss families;
8. select using physics metrics, not aggregate loss alone;
9. freeze final weights before test.

Command:

```bash
cbsc-zdc calibrate-loss-weights \
  --config configs/frozen_joint_pilot.yaml \
  --checkpoint runs/joint_pilot/checkpoints/best.pt \
  --max-batches 64 \
  --clip-min 0.25 \
  --clip-max 4.0 \
  --output artifacts/loss_weight_calibration.json \
  --device cuda
```

Then copy the proposed values into a new **unfrozen** template, freeze it, and rerun. Do not automatically overwrite a frozen config.

Detailed rationale and the validation matrix are in `docs/LOSS_WEIGHT_PROTOCOL.md`.

---

## 14. Component-stage diagnostics

The staged chain is for debugging and initialization, not proof that the free-running cascade works.

Order:

```text
response → profile → count → support → share → joint
```

Freeze each stage template against the same artifacts. The bundled stage templates contain the expected previous checkpoint path.

Example:

```bash
cbsc-zdc freeze-config \
  --template configs/templates/stage_response.yaml \
  --audit artifacts/train_data_audit.json \
  --geometry artifacts/geometry \
  --manifest artifacts/data/dataset_manifest.json \
  --splits artifacts/splits.json \
  --output configs/frozen_stage_response.yaml

cbsc-zdc train --config configs/frozen_stage_response.yaml
```

Repeat for the remaining stages.

Important shared-encoder rule:

- response stage trains the condition encoder;
- profile/count/support/share stages require `initialize_from` and keep the condition encoder frozen by default;
- joint stage unfreezes the entire model.

This prevents later isolated tasks from changing the shared condition representation and silently breaking previously frozen heads.

After each stage, review:

```text
RUN/environment.json
RUN/resolved_config.json
RUN/logs/history.csv
RUN/reports/training_summary.json
RUN/checkpoints/best.pt
RUN/checkpoints/last.pt
```

A stage loss decreasing is only a local software diagnostic. Evaluate the generated cascade after joint training.

---

## 15. Target-hardware pilot

Before a full 765k-event run, create a pilot template with:

- 1–2 epochs;
- small but representative train/validation subsets only through a copied pilot manifest, never by modifying final splits;
- final model dimensions;
- final mixed-precision setting;
- target GPU;
- final shard format and DataLoader worker count.

Pilot QA observations:

1. no NaN/Inf loss;
2. no NaN/Inf gradient norm;
3. checkpoint save and reload pass;
4. structural QA passes after sampling;
5. GPU memory has at least 15% headroom;
6. DataLoader does not starve the accelerator;
7. throughput is recorded;
8. no unexpected CPU fallback dominates time.

Do not use a tiny model to estimate final memory. Use the real architecture with fewer batches.

---

## 16. Full training plan

### 16.1 Seeds

Use at least three independent seeds for each final condition:

```text
20260723
20260724
20260725
```

Every seed receives a separately frozen config and run directory.

### 16.2 Matched support experiment

Train six primary models:

```text
3 seeds × train on 0–300 GeV
3 seeds × train on 50–250 GeV
```

Architecture, optimizer, loss weights, batch size, number of epochs, early-stopping rule, split, and test bank must otherwise match.

### 16.3 Default optimizer setup

Bundled starting protocol:

```text
optimizer: AdamW
learning rate: 1e-4
minimum cosine learning rate: 1e-6
betas: (0.9, 0.999)
epsilon: 1e-8
weight decay: 0.01
gradient clipping: 1.0
AMP: enabled on CUDA
effective batch: batch_size × gradient_accumulation
early stopping patience: 8 epochs
```

These are credible pilot values, not detector-specific optima. Tune learning rate before architecture size. Recommended validation-only pilot grid:

```text
learning rate: {3e-5, 1e-4, 3e-4}
weight decay: {0, 1e-3, 1e-2}
effective batch: largest stable value, plus one half-size control
```

Use a minimum-credible subset and one seed for this pilot. After choosing, freeze and use three seeds. Never tune on final test metrics.

### 16.4 Launch locally or on a configured GPU machine

```bash
cbsc-zdc train \
  --config configs/frozen_full_0_300_seed20260723.yaml \
  --device cuda
```

Resume the same stage after interruption:

```bash
cbsc-zdc train \
  --config configs/frozen_full_0_300_seed20260723.yaml \
  --resume runs/full_0_300_seed20260723/checkpoints/last.pt \
  --device cuda
```

`resume` restores optimizer, scheduler, scaler, epoch, and model state and checks the stage identity. `initialize_from` starts a new stage with model weights only.

---

## 17. Vertex AI execution

See `docs/VERTEX_AI_RUNBOOK.md` for exact build, upload, submit, monitoring, and recovery commands.

Minimal conceptual flow:

```text
freeze artifacts locally
→ upload frozen config + manifests + shards + geometry to GCS
→ build and push Docker image
→ submit one-GPU CustomContainerTrainingJob
→ container stages inputs locally
→ train with cbsc-zdc
→ upload complete run directory to GCS
```

The image entry point is `cbsc_zdc.cloud.vertex_stage`. It rewrites only machine-local paths while preserving the frozen scientific values and source hashes.

---

## 18. Structural QA after every checkpoint candidate

```bash
cbsc-zdc qa \
  --checkpoint runs/full_0_300_seed20260723/checkpoints/best.pt \
  --geometry artifacts/geometry \
  --profile-steps 8 \
  --share-steps 8 \
  --tolerance 0.00002 \
  --output runs/full_0_300_seed20260723/reports/invariant_qa.json \
  --device cuda
```

The report must show:

```text
nonfinite = 0
negative = 0
outside_valid_support = 0
support_mask_mismatch = 0
count_mismatch_max = 0
requested_realized_mismatch_max = 0
layer_closure_max_gev <= tolerance
event_closure_max_gev <= tolerance
dust_cells = 0 in thresholded mode
pass = true
```

A structural failure is a code or contract failure. Do not average it away over events.

---

## 19. Validation and test evaluation

Validation during development:

```bash
cbsc-zdc evaluate \
  --checkpoint RUN/checkpoints/best.pt \
  --geometry artifacts/geometry \
  --manifest artifacts/data/dataset_manifest.json \
  --splits artifacts/splits.json \
  --split validation \
  --gates configs/gates_primary.yaml \
  --output RUN/reports/validation_report.json \
  --device cuda \
  --batch-size 16
```

Final test, exactly once after model/protocol freeze:

```bash
cbsc-zdc evaluate \
  --checkpoint RUN/checkpoints/best.pt \
  --geometry artifacts/geometry \
  --manifest artifacts/data/dataset_manifest.json \
  --splits artifacts/splits.json \
  --split test \
  --gates configs/gates_primary.yaml \
  --output RUN/reports/primary_test_report.json \
  --device cuda \
  --batch-size 16 \
  --require-pass
```

`--require-pass` exits nonzero when any configured diagnostic threshold is
missed. This is useful for reproducible report generation and artifact
quarantine; it does not decide whether future training is allowed.

The bundled threshold file is explicitly provisional. It requires at least
10,000 evaluation events and 500 events per primary energy bin, then reports
response scale, resolution, zero rate, normalized Wasserstein distances, C2ST,
and structural invariants. Validate the thresholds’ reasonableness using
truth-half statistical floors on validation, then freeze the diagnostic
definition before test.

Current executable report also includes:

- hit counts;
- depth centroid;
- x/y centroid;
- radial RMS;
- top-cell fraction;
- ECAL fraction;
- late-energy fraction;
- positive-cell energy spectrum;
- mean longitudinal profile;
- truth-half distributional floors.

Publication-level work must add low-level geometry-aware C2ST, neighborhood correlations, connected components, repeated-condition ensembles, downstream reconstruction, and memorization tests if they are not yet implemented in the CLI.

---

## 20. Sampling fixed conditions

```bash
cbsc-zdc sample \
  --checkpoint RUN/checkpoints/best.pt \
  --geometry artifacts/geometry \
  --kinetic-gev 50 75 100 125 150 175 200 225 250 \
  --direction 0 0 1 \
  --profile-steps 8 \
  --share-steps 8 \
  --seed 20260723 \
  --output RUN/reports/fixed_condition_samples.npz \
  --device cuda
```

Outputs:

```text
p4_total_gev
kinetic_energy_gev
cell_energy_gev
 total_response_gev
layer_energy_gev
counts
support_mask
```

For diversity studies, repeat the same exact four-vector with many different seeds. Do not compare showers at only similar energy and call that conditional diversity.

---

## 21. Speed benchmarking

```bash
cbsc-zdc benchmark \
  --checkpoint RUN/checkpoints/best.pt \
  --geometry artifacts/geometry \
  --kinetic-gev 150 \
  --direction 0 0 1 \
  --batch-size 1 \
  --warmup 20 \
  --iterations 200 \
  --profile-steps 8 \
  --share-steps 8 \
  --device cuda \
  --output RUN/reports/timing_batch1.json
```

Repeat for throughput batches such as 16, 64, and the largest stable batch.

Every speed claim must state:

- CPU/GPU model;
- PyTorch/CUDA versions;
- precision;
- batch size;
- profile and share solver steps;
- warmup and repetitions;
- model-only latency;
- decode and serialization inclusion;
- end-to-end input/output latency;
- Geant4 benchmark method and hardware.

Do not compare a batched GPU model time with a single-threaded end-to-end Geant4 number without explaining the mismatch.

---

## 22. Required baselines and ablations

At minimum:

1. **B0 empirical/template baseline:** conditional resampling or interpolation by energy/direction.
2. **B1 non-graph model:** same hierarchy and exact decoder, MLP/CNN node field.
3. **G1 full graph model:** active CBSC-ZDC.
4. **S1 single-stage graph-flow baseline:** removes explicit profile/count hierarchy while preserving output contract.
5. **A1 causal versus bidirectional layer context.**
6. **P1 sparse point-cloud baseline.**
7. **External native ZDC reproduction:** begin with `faster_zdc` on its original representation before adaptation.

Fairness rules:

- identical train/validation/test events where representation allows;
- same target semantics;
- same primary energy domain;
- matched hyperparameter-search budget;
- matched seeds;
- timing on the same hardware and precision;
- no baseline is weakened by an intentionally poor decoder.

---

## 23. Result interpretation

### 23.1 A valid positive result

A defensible success statement is:

> Across three seeds, the frozen CBSC-ZDC configuration satisfied structural
> invariants and its predeclared 50–250 GeV diagnostic thresholds on the
> untouched test bank, showed the reported truth-relative diversity and
> reconstruction closure, did not exhibit detected memorization, and achieved
> the reported end-to-end speed under the disclosed hardware and solver
> settings.

### 23.2 A valid negative result

A scientifically useful negative result is:

> The hierarchy satisfied exact accounting but missed specific distributional
> thresholds, identifying whether response, profile, count, support, or
> morphology caused the mismatch. The controlled baselines showed which
> complexity did or did not help.

### 23.3 Invalid claims

Do not claim success because:

- training loss decreased;
- one event looks plausible;
- total energy closes exactly;
- a high-level classifier AUC alone is near 0.5;
- one seed passed;
- test metrics were used to choose weights;
- generated showers are merely different from each other;
- the surrogate is faster without including solver and decode costs.

---

## 24. Agent completion checklist

Before declaring the implementation run complete, an agent must attach:

### Data and geometry

- [ ] ROOT inspection JSON for every file family
- [ ] production schema YAML and SHA-256
- [ ] geometry NPZ, manifest, cell map, and hash
- [ ] conversion manifest and source hashes
- [ ] explained rejection counts
- [ ] split manifest and assignment hash
- [ ] complete train audit

### Training

- [ ] frozen config for every run
- [ ] three seeds per final support condition
- [ ] environment snapshot
- [ ] complete history CSV
- [ ] best and last checkpoints
- [ ] loss calibration report
- [ ] validation-only hyperparameter decision log

### Evaluation

- [ ] invariant report
- [ ] validation report
- [ ] untouched primary test report
- [ ] stress-domain report
- [ ] fixed-condition diversity bank
- [ ] memorization/nearest-neighbor report
- [ ] downstream reconstruction report
- [ ] baseline/ablation table
- [ ] timing report

### Scientific statement

- [ ] all claims trace to artifacts
- [ ] failures are reported, not hidden
- [ ] no structural property is described as Geant4 fidelity
- [ ] no test-informed tuning occurred

---

## 25. What still requires production-specific judgment

The repository eliminates most generic implementation work, but it cannot infer the following from a schema-only sample:

1. exact production units and primary-selection semantics;
2. whether each ROOT file is an independent job/seed family;
3. whether the generator vertex is fixed;
4. whether the observed 6,790-channel geometry exactly matches the stored project specification;
5. whether raw deposited energy or a detector threshold is the intended target;
6. the final scientifically appropriate acceptance thresholds;
7. the final loss weights and learning rate after validation pilots;
8. whether graph edges improve fidelity enough to justify cost.

These are experiment decisions, not routine coding omissions. Record each decision in the run’s evidence log.

---

## 26. Primary methodological references used by the implementation design

- Lipman et al., **Flow Matching for Generative Modeling**, arXiv:2210.02747.
- Kool, van Hoof, and Welling, **The Gumbel-Top-k Trick**, ICML 2019.
- Chen et al., **GradNorm**, ICML 2018.
- Kendall, Gal, and Cipolla, **Uncertainty-weighted multi-task learning**, CVPR 2018.
- Diefenbacher et al., **L2LFlows**, JINST 2023.
- Kobylianskii et al., **CaloGraph**, irregular-geometry graph diffusion.
- PyTorch official reproducibility and AMP documentation.
- Google Cloud official Vertex AI Custom Job documentation.

The reference register and bibliography audit provide exact metadata and relevance notes.
