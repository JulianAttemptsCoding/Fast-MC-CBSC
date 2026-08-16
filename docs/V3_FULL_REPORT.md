# CBSC-ZDC v3 — everything that happened, 2026-08-13 to 2026-08-15

The complete record of the v3 architecture programme: what was built, what was
measured, what was wrong, and what it means. Written to be read cold by someone
who was not here.

Terminal scientific status: **`PHYSICS VALIDATION NOT ESTABLISHED`**.

---

## 1. The one-paragraph version

v3 is a set of architectural changes to the CBSC-ZDC generative model, screened
one change at a time against a frozen baseline. The software is implemented,
wired and tested. Two rows have completed and **neither improved anything**: the
incident-axis feature is measurably neutral, and the apparent shortfall that
made it look harmful turned out to be an optimizer artifact that is now
quantified. Two more rows are queued and running unattended. Separately, the
adversarial critic D1 — the only part of the programme that attacks the actual
failure mode — **does not fit on the available hardware**. The project's core
problem is unchanged and now better evidenced: the training objective improves
while the classifier that measures fidelity does not move.

---

## 2. What v3 is

v3 keeps the exact decoder and every structural invariant of v2.2 and changes
how five stages are modelled. Each is selected by its own config flag, and every
flag **defaults to the v2.2 behaviour even under a v3 declaration**, so a bare
v3 config behaves exactly like v2.2 and emits exactly the v2.2 loss keys.

| Flag | v2.2 default | v3 option | Screening row |
|---|---|---|---|
| `axis_features` | `false` | incident-axis node coordinates | S1 |
| `response_mode` | `v2` | bounded conditional spline | S2 |
| `first_layer_mode` | `v2` | hierarchical ECAL/HCAL | S3 |
| `activity_head_mode` | `v2` | span+gaps, or autoregressive | S4 |
| `count_mode` | `v2` | autoregressive | S5 |

Plus two adversarial arms that are not feature flags: **D1** (share critic) and
**D2** (profile critic).

The per-feature toggles exist because the first wiring turned on every v3 head
whenever the version was `cbsc-zdc-v3`, which would have made S3's result
silently contain S2's and S4's changes.

---

## 3. Results

### 3.1 The numbers

| Run | What it is | Historical raw val | Common-measure val | Epoch |
|---|---|---:|---:|---:|
| **B0** `dicos-f-02` | v2.2 baseline, frozen | **4.483768** | **4.905704** | 90 |
| `dicos-f-03` | v2.2, 24-ep re-heat, **resumed** optimizer | 4.491971 | 4.913907 | 111 |
| **M0-fresh** | v3, zero axis, **fresh** optimizer | **4.513572** | **4.935508** | 19 |
| **S1-axis** | v3, real axis, **fresh** optimizer | **4.514053** | **4.935990** | 19 |
| S2-response | bounded spline; already GeV-density | 4.931398 | 4.931398 | 11 so far |
| S3-first | hierarchical first layer | *queued* | *queued* | — |

The historical v2-family values were logged in `y=log1p(T/s)` density units.
The audit in `audit/response_loss_measure_M0_20260815.json` reproduces the
trainer's validation batching and establishes a **+0.421936354321** total-loss
offset to express them in deposited-energy-GeV density units. It is target-only:
gradients and within-run selected epochs are unchanged. Raw values remain
immutable provenance; all cross-response-mode comparisons use the common
column.

### 3.2 The axis feature is neutral

M0-fresh is identical to S1 in architecture, parameter count, input width, seed,
data order, bank, batch, accumulation, schedule, solver steps, update count and
stopping rule. The **only** difference is that S1 feeds computed incident-axis
coordinates where M0 feeds zeros.

```
S1  4.514053
M0  4.513572
    ---------
     0.000481   against a run-to-run reference of 0.001259
```

Below the reproducibility band. **The axis feature changed nothing measurable.**

This works because with identically zero axis input the axis weight block
receives zero gradient and stays zero for the whole run, so M0 is mathematically
a v2.2 model trained with a fresh optimizer while keeping S1's exact parameter
count.

### 3.3 The shortfall was the optimizer, and it is now measured

```
S1 vs dicos-f-03, total          0.022082
  from the fresh optimizer       0.021601      (M0 vs dicos-f-03)
  from the axis feature          0.000481      (S1 vs M0, below reference)
```

`initialize_from` transfers weights but **not** optimizer state. Every screening
row therefore starts a fresh Adam, and that costs **0.021601** on this bank and
horizon.

### 3.4 The comparator rule — the most reusable result here

> **The correct comparator for any screening row is M0-fresh at 4.935508 on the
> common GeV-density measure, not raw M0 at 4.513572 or B0 at 4.483768.**

Every screening row pays the same measured optimizer restart. Comparing a row
directly against B0 charges its feature for that restart; comparing raw v2-head
loss against the spline additionally mixes two density measures. Screening
rows are compared only after the audited measure normalization.

Read against the right yardstick, S1 is not "0.030 worse than B0" — it is
**0.0005 from its true control**, which is nothing. This is recorded as
`comparator_rule` in the screening registry and pinned by tests.

---

## 4. Fidelity: the problem v3 has not solved

Three checkpoints have ever had an external classifier run against them.

| Checkpoint | Val loss | Hybrid C2ST | **High-level GBM** | Condition-only |
|---|---|---|---|---|
| `dicos-p9` e38 | 4.635220 | 0.872656 | **0.929097** | 0.500000 |
| `dicos-c-02` e34 | 4.550331 | 0.862415 | **0.894731** | 0.500000 |
| `dicos-f-02` e90 | 4.483768 | 0.843222 | **0.892897** | 0.500000 |

**The frozen 0.65 diagnostic is named `max_high_level_c2st_auc`**, so B0's gate
value is **0.892897**. The target is 0.65. Nothing is close. The condition-only
control sits at exactly 0.5, so the evaluator is not leaking labels.

Across the campaign the loss improved **0.067** while that gated number moved
**0.0018**. That decoupling is the central open problem, and no v3 row has
addressed it yet.

Reconstruction, same three checkpoints:

| | Energy rel. RMSE | Energy bias | Angular median | Angular 68% |
|---|---|---|---|---|
| `dicos-p9` | 0.249420 | −0.051010 | 15.560 mrad | 20.687 |
| `dicos-c-02` | 0.215650 | −0.043570 | 9.511 mrad | 12.662 |
| `dicos-f-02` | **0.210445** | **−0.039760** | **9.442 mrad** | **12.402** |
| *Geant4* | — | — | — | *10.704* |

B0 is best on every one. Angular 68% is 16% wider than Geant4; energy is biased
low by ~4%.

**Caveat on all of it:** that battery used 8,000 examples against a frozen
10,000 minimum, so it is labelled `FOLLOW-UP QA — BELOW FROZEN EVENT MINIMUM`.
Directional evidence only; it may not pass or fail the gate or select a row.

---

## 5. Overfitting

Established on the measured lineage, epochs 48–114, n=67:

| | r | t | p |
|---|---|---|---|
| train loss vs epoch | −0.805 | 10.93 | <0.001 |
| validation loss vs epoch | −0.358 | 3.09 | <0.05 |
| **gap (val − train) vs epoch** | **+0.560** | **5.46** | **<0.001** |

Train improved **0.13436**, validation **0.02324** — a ratio of **5.8×**. The
total validation gain across 67 epochs is smaller than the one-off gain from
correcting the learning-rate schedule.

**Not** established: nearest-neighbour memorization. That metric has never run.

---

## 6. D1 does not fit the hardware

The 2026-08-14 preflight measured D1 at 14.85 GiB and concluded it fits. That
used a **synthetic 40,740-edge graph**. Against the real frozen production
geometry — 6,790 nodes, **107,920 edges**, 65 layers — it reverses:

| Stage | Status | Peak |
|---|---|---|
| forward smoke, batch 1 | ok | 0.072 GiB |
| D1 critic update, batch 4 | **RESOURCE_PREFLIGHT_FAIL** | 22.796 GiB |
| D1 generator, batch 6 | **RESOURCE_PREFLIGHT_FAIL** | 22.857 GiB |

Card is 23.518 GiB; both are genuine OOM with 4.69 MiB and 42.69 MiB free.
Nothing was reduced to force a pass.

**D1 is `resource_blocked` on the RTX 4090.** D2 remains eligible — its measured
path is 0.098 GiB and does not touch the edge set.

### The hardware question

| | RTX 4090 | L40S |
|---|---|---|
| FP32 peak | 82.6 TFLOPS | 91.6 (+11%) |
| Memory bandwidth | **1008 GB/s** | 864 (−14%) |
| VRAM | 24 GB | **48 GB** |

This workload is message-passing over 107,920 edges and is **bandwidth-bound**,
so the 4090 is likely equal or faster for throughput. The L40S never received a
measured epoch rate on this project.

**The L40S's only advantage here is capacity — but that advantage is decisive
for D1**, which needs more than 23.5 GiB and would fit comfortably in 48 GB.

> **Keep-or-drop recommendation.** If you intend to run D1, keep an L40S or
> another ≥32 GB card; D1 cannot run otherwise, and D1 is the arm aimed
> squarely at the AUROC problem. If you are content to run D2 only, or to defer
> the adversarial programme, the L40S is not needed and the 4090 + 3090 pair is
> sufficient for every remaining screening row.

---

## 7. What was built

### Source modules
`axis_features`, `splines`, `response_v3`, `response_envelope`, `first_layer`,
`activity`, `counts_ar`, `critics`, `adversarial`, `replay`, `role_partition`,
`stage_sampling`, `migration`, `eval/topology`, `eval/correlations`,
`eval/diversity`, `eval/v3_battery`, `v3_preflight_shapes`.

### Pipeline
| Script | Role |
|---|---|
| `build_v3_screening_configs.py` | one template per row, inheritance opt-in |
| `v3_prepare_screening_run.py` | migrate from parent, then freeze |
| `import_v3_screening_run.py` | hash-verified evidence import |
| `build_v3_screening_figure.py` | figures + summary |
| `watch_v3_outputs.py` | keeps figures/metrics current while rows train |
| `chain_queue.sh` | runs remaining rows in sequence, unattended |
| `run_v3_validation_battery.py` | fixed-bank metric battery |
| `v3_d1_production_preflight.py` | D1 memory on the real graph |
| `v3_axis_performance_profile.py` | axis cost attribution |

### The fixed evaluation bank
10,000 validation conditions → **20,000 evaluator examples**, every energy bin
between 1,182 and 1,310 against a floor of 500, sha256 `1bc3a6b2…`.

Built from the **canonical** split, because the pilot split holds only 6,656
validation events — below the frozen 10,000 minimum. Cross-tabulation proved no
contamination first:

| pilot | → canonical |
|---|---|
| train 26,624 | **100% canonical train** |
| validation 6,656 | **100% canonical validation** |

So B0 has seen none of the 10,000.

Tests: **350 → 724**.

---

## 8. Every defect found, and how

Ordered by how much damage each would have done.

1. **Migration appended the axis block at the end** instead of inserting it at
   `offset = node_dim`, shifting every later column. The condition encoder
   matched at exactly 0.0 while **support logits differed by 14.37**. S1 would
   have trained from a scrambled checkpoint and the result attributed to axis
   features. Only surfaced against the real 6-column production geometry.
2. **The generator vertex silently defaulted to the origin.** True value is
   `[-917.41, -30.0, 35488.91]` mm — ~35.5 m downstream. The features would have
   been physically meaningless while looking perfectly valid.
3. **`initialize_from` was never set**, so S1's first launch trained from random
   weights (epoch 0 val **5.204838** against an expected ~4.48). Run discarded.
4. **The trainer never wrote format 4.** `save_checkpoint` supported it; nothing
   passed `architecture_version`. A helper test cannot observe an argument its
   caller never passes. S1's checkpoints are format 3 and cannot carry critic
   state — the blast radius was every adversarial row.
5. **S2 was built carrying unpromoted S1's axis features.** The row list is
   cumulative, which assumes every row promotes. Inheritance is now opt-in and
   must name promoted rows.
6. **`wasserstein_1d` was quadratic** — 0.10 s at n=10,000, 7.29 s at 100,000,
   **114.41 s at 400,000**. On the several-million-entry positive-cell array
   that is hours per call. Replaced with an exact O(n log n) sum over merged
   breakpoints, with equivalence to the old formulation pinned by test.
7. **The battery died on a CPU/CUDA `edge_index`** after an hour of completed
   work per checkpoint, three times.
8. **Migration refused S2** — `classify` routes input projections by key name,
   so a v3 row with axis *off* was asked for four columns it correctly lacks.
9. **The exhibition gallery silently dropped graphics** whose category had no
   section label: `category()` failed closed, the label map failed **open**.
10. **`dicos.py stop` leaves a chained script's shell alive**, which restarts the
    next item. Left two evaluations racing for one output path — twice.
11. **My own queue re-checked completeness before waiting**, which would have
    started a second S2 over a completed run.

### Wrong diagnoses I made and corrected

- Blamed the battery stall on **topology's Python union-find** and subsampled
  it. Measured: 5.1 s per 1,000 events. Wrong; reverted, and the module now
  records that so it is not repeated.
- Blamed it on **`high_level_features` memory**. Pod has ~1 TB RAM. Wrong.
- Claimed the axis features cost **2.23×**. Profiled: ~1% (support 1.0015, share
  1.0099, full sample 1.0055). M0 later confirmed it independently by running at
  1733.7 s/epoch with zero axis information.
- Claimed the LR correction "nearly cleared" D1's 0.02 gate. That delta was
  **hybrid** C2ST; D1's rule names **low-level**. Withdrawn.
- Called a ratio "34σ-equivalent". It is 33.8× a reproducibility reference, not
  a sigma. Withdrawn.

---

## 9. What is running, and what needs nothing

| Job | Card | State |
|---|---|---|
| `queue2` | 4090 | S2 running, S3 queued behind it |
| `v3bat2-dicos-f-02-e90` | 3090 | schema-v2 B0 rerun; autonomous M0/S1/S2/S3 queue follows |
| `watch_v3_outputs` | workstation | imports epochs/batteries and rebuilds figures/catalog every 15 min |

The queue refuses to start a row until the card is free, refuses to continue
past a row that stopped short of its horizon or never reached postflight, and
skips completed rows so it is safe to re-issue after a pod restart.

The watcher only runs while the workstation is on.

The f-03 battery leg exposed a provenance failure, not a physics result.
`dicos-f-03/checkpoints/best.pt` is the inherited B0 epoch-90 checkpoint (same
SHA-256 `491284c7…`), because no f-03 epoch beat B0. The launcher labeled that
evaluation epoch 111. Its report is quarantined and excluded from comparison;
the intended epoch-111 checkpoint was not retained. The battery now fails
before generation when the requested and embedded checkpoint epochs differ.

Two B0 fixed-bank reports are quarantined as a whole. The original
reconstruction metric divided relative error by a numerical floor for
zero-truth events and reported RMSE 5.332e8. Excluding exact zeros did not cure
the definition: arbitrarily small positive deposited truth produced RMSE
123,548.67. The separate B0 external-validation gate is unaffected, and its
downstream incident-energy reconstruction value is not comparable to this
paired detector-response residual. Report schema v2 normalizes the paired
generated-minus-truth deposited response by incident kinetic energy, includes
all pairs, and labels the quantity as not downstream reconstruction. It passed
57 synchronized remote tests and is rerunning B0 under a distinct transaction.
A watcher-driven controller then queues M0, S1, and every completed row with
checkpoint and contract provenance.
The attempted stop of the old S1 wrapper did not kill its child; that child
completed at 00:26:43Z with the obsolete evaluator. The controller rejected its
report before acceptance, and it is quarantined locally and remotely.

---

## 10. Honest status

**Established:** production conversion, frozen geometry, FP32 execution,
checkpoint/recovery, zero structural-invariant failures in accepted runs,
short-horizon optimization improvement, a growing train-validation gap
consistent with overfitting, the axis feature being neutral, the fresh-optimizer
cost, and D1 not fitting the current card.

**Not established:** Geant4 fidelity, three-seed behaviour, untouched-test
performance, downstream reconstruction, diversity/memorization acceptance,
publication-scale timing on another backend.

**Not yet validly measured:** the schema-v2 full metric battery on any
checkpoint (the B0 rerun is active); the D3
trigger; any adversarial training.

The gap between the objective and the fidelity metric remains the project's
central unsolved problem, and nothing in v3 has moved it yet.

`PHYSICS VALIDATION NOT ESTABLISHED`.
