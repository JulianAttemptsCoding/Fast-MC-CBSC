> **ARCHIVED — SUPERSEDED. DO NOT FOLLOW THIS DOCUMENT.**
>
> Superseded 2026-08-15 by `docs/V3_FULL_REPORT.md`. This was the pre-implementation concerns document written before any v3 row ran. Every question it raises is either answered or explicitly still open in the full report, which also carries the measured results it could only speculate about.
>
> Current entry point: `docs/HANDOFF.md` → `docs/PIPELINES.md`.
> Terminal status is unchanged: `PHYSICS VALIDATION NOT ESTABLISHED`.

---

# Assessment of the CBSC-ZDC v3 handoff

Written 2026-08-13 against `CBSC_ZDC_v3_REPO_ROOT_OVERLAY.zip` and
`CBSC_ZDC_v3_COMPLETE_HANDOFF.zip`, before extracting either into the
repository. Nothing has been extracted into the repo and no code has been
written. The archives are still sitting untracked at repo root.

**Verdict: the software specification is excellent and I recommend building it.
The experiment matrix is not executable — it needs roughly 120–160 days of
continuous single-GPU compute, against a two-pod fleet whose pods expire.** The
correct action is to implement and re-scope, not to start a matrix that cannot
finish. Details and a concrete counter-proposal below.

---

## 1. What I verified, and what came back clean

I checked the handoff's factual claims against live state rather than trusting
them. It holds up unusually well.

| Claim in the handoff | Verified? | Evidence |
|---|---|---|
| 11 audited base file hashes | **all 11 match live exactly** | recomputed SHA-256 of each |
| Canonical split 612,482 / 76,158 / 76,300 | **exact** | `audit/next_agent_verified_prepare_r5.json` |
| Role partition 551,234 + 30,624 + 30,624 | **sums to 612,482 exactly** | arithmetic |
| 764,940 events, 187 shards | **exact** | same audit file |
| Detector 6,790 = 400 ECAL + 6,390 HCAL | **exact** | `CLAUDE.md`, data contract |
| Low-level/hybrid AUROC ≈ 0.862–0.873 | **exact** | `external_metric_summary.json`: 0.8624, 0.8727 |
| High-level AUROC ≈ 0.895–0.929 | **exact** | same: 0.8947, 0.9291 |
| LR sawtooth from restored `T_max` | **correct** | independently found and fixed 2026-08-12 |
| Response branch can sample ≤0 and clear a visible event | **plausible, matches code** | `models/response.py` |

The base-hash result is the important one. **Whoever produced this read this
exact codebase**, not a generic description of it. That earns the plan real
credibility.

`scripts/verify_improvement_v3_handoff.py` is safe — read-only hashing, YAML/CSV
validation, prints JSON, no writes, no network, no execution of archive content.

### It is also well aligned with findings made after the archive was cut

Two things I established *today*, which the plan could not have known, both
point the same way it does:

- **The model measurably overfits** (train↔val gap widening, r=+0.560, t=5.46,
  p<0.001; train improving 5.8× faster than validation). The plan moves training
  from the 26,624-event pilot bank to the 551,234-event generator partition — a
  **20.7× data increase**, which is the single most direct answer to overfitting.
  It does this for unrelated reasons, but it is the right move.
- **The per-epoch fidelity diagnostics cannot resolve a trend** at 4,000
  events/epoch (scatter 16–43%, nothing survives multiple-comparison
  correction). `acceptance_gates.yaml` sets
  `min_total_evaluation_events: 10000` and `min_events_per_energy_bin: 500`
  with 1,000 stratified bootstrap replicates. That is exactly the fix.

### The technical design avoids the traps I would have checked for

- It does **not** naively strip `@torch.no_grad()` from the exact sampler; it
  adds separate differentiable loss APIs (`sample_share_for_loss`,
  `sample_profile_for_loss`) and forbids calling `sample_exact()` inside an
  adversarial loss.
- D1 and D2 truth-force the discrete variables and generate only continuous
  state (shares, layer budgets), so gradients never cross the top-k. The genuinely
  hard discrete case (D3, support) is deferred behind an explicit trigger and an
  estimator-QA harness. This is the right ordering.
- It requires a **no-critic control (`C0`) on the identical 551,234-event
  partition**, because critic runs lose 10% of training data. Without this,
  every critic result would be confounded. Many plans miss this.
- R1 applied lazily every 16 updates with the ×16 coefficient correction — correct.
- The response NLL is dimensionally right: with `r_T = S(u₀)`, `u₀ ~ U(0,1)`,
  `T = C(K)·r_T`, then `−log p(T) = −log|dS⁻¹/dr_T| + log C(K)`. ✓
- §17 "explicitly rejected defaults" reads like it was written by someone who
  has actually watched GANs fail.

---

## 2. The blocker: the experiment matrix needs ~120–160 days of GPU

This is the only issue I consider disqualifying as written.

**Measured throughput on the live training pod**, from `dicos-f-02`'s own
history: **34.15 examples/sec**, 779.6 s/epoch, on the 26,624-event pilot bank,
peak 10.94 GiB.

Extrapolating to the banks the matrix actually specifies:

| Bank | Events | Hours/epoch at 34.15 ex/s |
|---|---:|---:|
| pilot | 26,624 | 0.22 |
| `critic_generator_partition` | 551,234 | **4.48** |
| `full_train` | 612,482 | **4.98** |

Costing `experiment_matrix.csv` at 24 epochs per run:

| Matrix rows | Runs | Bank | GPU-hours |
|---|---:|---|---:|
| 0–11 (`B0`…`S7`) | 12 | pilot | 62 |
| 12–21 (`V3-SUP`, `C0`, D1×4, D2×4) | 10 | 551,234 | 1,076 |
| 22–23 (D1/D2 selected, 3 seeds) | 6 | 551,234 | 646 |
| 24 (`D12`, 3 seeds) | 3 | 551,234 | 323 |
| 25 (`D3-triggered`) | 1 | 551,234 | 108 |
| 26–27 (FINAL, 3 seeds each) | 6 | 612,482 | 717 |
| **Total** | **38** | | **≈ 2,932 h ≈ 122 days** |

That is **continuous, single-card, with zero failures, at only 24 epochs per
run** — and 24 epochs is very likely too few, since the current pilot needed 90+
epochs to converge. At 50 epochs for the full-data rows the total passes **150
days**. Critic runs add a critic forward/backward and replay sampling on top,
plausibly another 20–40% on rows 14–25.

Against that: the fleet is **two pods that expire**, and a single 24-epoch run
on the 551,234-event bank is **4.5 days of wall-clock that must survive pod
expiry**. The longest run this project has completed is ~5.8 hours.

**This is not a reason to abandon the plan. It is a reason to re-scope it before
starting, so we do not begin a matrix that structurally cannot finish.**

---

## 3. Other concerns, in descending order

### 3.1 The hardware assumption is wrong — 4090/24 GB, not L40S/48 GB

The spec (§11.9, "Current operational constraints") and `CLAUDE.md` both state
the training pod is an **NVIDIA L40S** and that the 4090 was retired
2026-08-10. Live, right now:

```
training pod    : NVIDIA GeForce RTX 4090, 24564 MiB, driver 595.58.03
diagnostics pod : NVIDIA GeForce RTX 3090, 24576 MiB, driver 610.43.02
```

The fleet changed again after those documents were written. Consequences:

- **48 GB → 24 GB.** Current training peaks at 10.94 GiB. The D1 share critic
  adds a GNN plus a bidirectional 2-layer 4-head Transformer over 6,790 nodes,
  *alongside* the generator, plus a CPU replay buffer. Whether that fits in the
  remaining ~13 GiB is **unmeasured and must be measured before D1 is planned**,
  not assumed.
- The L40S `libcuda.so.1` / `/usr/lib64` workaround in `CLAUDE.md` may not apply
  to this pod. Re-probe rather than inherit.
- `docs/GPU_BENCHMARKS.md` and `CLAUDE.md` both need correcting regardless of
  what we decide about v3.

### 3.2 The archive's own baseline is now stale in one place

`ORIGINAL_ARCHIVE_BASELINE.md` says the corrected anneal `dicos-f-01` "was still
in flight". It completed. Current state:

- accepted best is **4.483768 at epoch 90, `dicos-f-02`**, fully evidenced,
  not 4.512721 at `dicos-e-02` e47;
- the campaign ran four segments and self-terminated `campaign_complete`;
- `dicos-f-04` is an undeclared variant, excluded from the live lineage and
  retained as evidence.

This does not invalidate anything — `B0` is defined as "corrected_scheduler_only"
and that is exactly what we now have — but the v3 branch point should be
`dicos-f-02` e90, and `B0` may be **already done** rather than needing a rerun.
That alone removes one pilot run.

### 3.3 The audit-bundle hash does not match, though the content does

`ORIGINAL_ARCHIVE_BASELINE.md` claims the reviewed input was
`CBSC_ZDC_audit_bundle_20260812.zip`, SHA-256
`ec4f044695401d438d47019012b9d0a1bedda59da5d5d211a97f34e91b5a0432`, 110,349,073
bytes, 1,513 files.

I built and reported
`ad28d284cbddfec41e0495f5d35e14b4511f775334c371e76eb2e1faa90a253c`, ~105.2 MB,
1,512 manifest entries. The file is no longer on disk, so I cannot re-hash it.

**I consider this a low-severity discrepancy**, because all 11 audited *file*
hashes match live exactly — the content that was reviewed is verifiably correct
regardless of the container hash. The likely explanation is that I rebuilt the
bundle several times that day and the reviewed copy was a different build.
Worth confirming, not worth blocking on.

### 3.4 D1 and D2 may well produce null results, by construction

D1 truth-forces `S` (the support) and trains only the share flow. D2
truth-forces `A` and trains only the profile flow. But the plan's own §12 says
support topology is a leading suspect for the C2ST gap, and defers it to D3.

So the two critics that get run first are the two that **cannot touch the
variable most likely responsible for the AUROC gap**. That is a defensible,
risk-ordered choice — continuous-only gradients are far safer to get right —
but we should expect D1/D2 to plausibly move the classifier very little, and we
should not read a null there as "adversarial training does not work here."
The acceptance gate demands `external_c2st_auc_min_absolute_reduction: 0.02`,
which may be a high bar for a share-only critic.

### 3.5 Critic batch size 4 is very small

`critic.batch_size: 4`, composed 2 fresh / 1 recent / 1 anchor. Discriminators
are usually unstable at that scale, and R1 gradient-penalty estimates are noisy
with 4 samples. It is a declared, screenable hyperparameter and the gradient
controller bounds the damage — but I would expect this to need raising, and it
interacts with the memory question in §3.1.

### 3.6 Pod expiry versus 4.5-day runs

No Slurm from a DiCOSApp pod; pods expire; training must be
checkpoint/resume-capable. That already works. But the longest completed run
here is ~5.8 h, and rows 12–27 each need **4.5+ days**. The resume path will be
exercised far harder than it ever has been, including now resuming *critic
state, optimizer state, replay buffer contents and RNG* (spec §15). That
machinery is new and unproven, and a resume bug on day 3 of a 4.5-day run is
expensive. It needs a deliberate soak test before the matrix, not during it.

---

## 4. What I recommend instead

Keep the specification. Change the sequencing so each stage produces a decision
on evidence we can actually afford.

### Stage A — software only, no new training (~feasible now)

Implement §§3–10 and §§14–16 of the spec: architecture versioning, checkpoint
v4, role partition, response envelope, axis features, response spline,
hierarchical first-layer, activity modes, AR counts, the differentiable stage
samplers, and **all of §14's metrics**. Full test catalog. No critics yet.

This is the bulk of the value and costs **zero training GPU**. It is also
strictly reusable no matter what we decide about the critics.

### Stage B — fix the measurement problem first (~cheap, highest value)

Run §14's metrics with `min_total_evaluation_events: 10000` and 1,000 bootstrap
replicates **against checkpoints that already exist** (`dicos-f-02` e90 and its
lineage). This directly answers the question I could not answer today — whether
fidelity tracks the loss — and it needs only inference, not training.

It also gives every later comparison a truth-half floor and a confidence
interval, without which the pilot screens in rows 1–11 cannot be read anyway.

### Stage C — the pilot screens, honestly costed (~62 GPU-hours)

Rows 0–11 on the pilot bank are genuinely affordable: about **2.6 days total**,
and `B0` may already be satisfied by `dicos-f-02`. Run these, apply the frozen
promotion rule, and report negatives.

### Stage D — decide on critics with real numbers in hand

Before committing to rows 12–27, measure:

1. peak memory of a D1 critic step on the 24 GB card (one step, not a run);
2. actual s/epoch on the 551,234-event bank (one epoch, not a run);
3. a deliberate resume soak: kill and resume a critic run mid-epoch, verify the
   `next_update_parameter_max_abs_difference: 1.0e-6` gate.

Then re-cost rows 12–27 with measured numbers and choose a subset. My guess is
that a defensible critic result needs `C0` + one D1 arm + one D2 arm at one seed
— about 4 runs, ~430 GPU-hours, ~18 days — with the 3-seed replication and the
full-data finals deferred to an explicit, separately-budgeted decision.

### What I would not do

Start at row 12 and hope. The prompt's own instruction — *"Do not call an
in-flight or pilot result final"* — means an unfinished matrix produces nothing
citable. Better to complete Stages A–C and hold a real decision point than to be
40% through a 122-day matrix with no reportable result.

---

## 5. Questions I need answered before implementing

1. **Compute budget.** Is there any path to more than one training GPU, or to a
   pod that survives multi-day runs? This single answer decides whether rows
   12–27 are re-scoped or dropped.
2. **Do you want Stage A started now?** It is the majority of the specification,
   costs no training compute, and is useful regardless of the critic decision. I
   can begin immediately on your word.
3. **The 4090/L40S change** — was this a deliberate swap, or did the pod get
   reprovisioned? It affects whether I correct `CLAUDE.md` as a fleet change or
   investigate it as a surprise.
4. **The bundle hash** — do you still have the zip you uploaded for review? If
   so, hashing it closes §3.3 completely.
5. **`B0`** — accept `dicos-f-02` e90 as the corrected-scheduler baseline, or
   insist on a fresh `B0` run under the v3 config schema?

---

## 6. Status

`QA FINDING` — the handoff is verified genuine and technically sound; the
experiment matrix is not executable under available compute.

`PHYSICS VALIDATION NOT ESTABLISHED` — unchanged, and nothing in this assessment
changes it.

Nothing extracted, nothing implemented, no compute spent, repository untouched
apart from this file. Both zips remain untracked at repo root.
