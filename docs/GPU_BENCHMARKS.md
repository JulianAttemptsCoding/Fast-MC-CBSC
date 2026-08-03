# GPU throughput and cost — measured

Single source of truth for GPU performance and cost on this workload. It
supersedes the throughput and cost numbers scattered through `logs.md`, several
of which were wrong. Where this file disagrees with an older `logs.md` entry,
this file wins.

Hardware choice is transport, not science (`docs/QA_POLICY.md`). Nothing here
grants or denies permission to run anything.

**Everything below is now measured over six full epochs per card.** The
estimated 3090 figures that appeared in the first version of this document have
been replaced by a real benchmark, and the earlier estimate is retained at the
bottom only to record that it was accurate.

## Method

All comparisons use identical work: same architecture, same frozen pilot bank
(26,624 train / 6,656 validation), `batch_size: 6`, `gradient_accumulation: 4`,
`amp: false`, `num_workers: 4`, `CBSC_ZDC_SHARD_CACHE=0`, torch `2.6.0+cu124`,
numpy `2.5.1`, `cudnn.allow_tf32=True`, `cuda.matmul.allow_tf32=False`. Families
differ only in learning rate, which does not change the compute.

Epoch wall time comes from each run's own `logs/history.csv` `seconds` column,
which covers training *and* validation for one full epoch. One trainer per GPU,
always.

## Measured, 2026-08-03

| GPU | run | condition | n | mean s/epoch | min | max |
|---|---|---|---:|---:|---:|---:|
| RTX 4090 | `lr3e4 dicos-p7` | batch 6, 3 trainers on the cluster | 6 | **649.83** | 645.36 | 659.18 |
| A100-SXM4-80GB | `lr1e4 dicos-p6` | batch 6, 3 trainers on the cluster | 6 | **990.17** | 985.31 | 997.18 |
| RTX 3090 | `bench lr1e4` | batch 6, **solo** | 6 | **1168.88** | 1165.94 | 1171.16 |
| RTX 3090 | `halfbatch dicos-p7` | batch **3**, 3 trainers | 6 | 1333.18 | 1325.94 | 1338.34 |

Ratios on equal work: **A100 / 4090 = 1.524**, **3090 / 4090 = 1.799**,
**3090 / A100 = 1.180**.

The batch-3 row is real but is **different work** — 8,874 batches per epoch
instead of 4,437 on the same 26,624 samples — and must not be compared against
the batch-6 rows. It is recorded because it is what the half-batch family
actually costs to run.

### Two conditions that differ, and by how much

The 4090 and A100 epochs were measured while all three pods were training. The
pods have separate GPUs but mount the same CephFS workdir, so shard loading and
checkpoint writes contend even though the cards do not. The 3090 benchmark ran
**solo**, after training had vacated that card.

The size of the effect is bounded by the 4090's own spread under contention:
645.36 s to 659.18 s, **2.1%**. So the 3090's solo figure flatters it by at most
about 2%, which does not approach the 1.18x and 1.52x gaps it sits between. No
ranking here turns on it.

### The A100's memory and tensor cores are idle

Peak CUDA memory is **11.74 GB on both the 4090 and the A100** — identical, as
it should be for the same architecture at the same batch size. The A100 finishes
with 86.2% of its 80 GB unused; the 4090 uses less than half of its 24 GB.
Half-batch peaks at 5.91 GB.

This explains the ranking. The A100's advantages are capacity, bandwidth and
tensor-core throughput. This workload runs `amp: false`, so it never touches a
tensor core, and it fits in a third of a 4090. What is left is FP32
non-tensor-core throughput, where the 4090 is simply the faster part. The A100
would only become interesting under a **separately declared** experiment that
used its strengths — mixed precision, a much larger batch, or a larger model.

## Pricing

From ASGC's live accounting page, <https://dicos.grid.sinica.edu.tw/static/docs/accounting.html>:

> SRU is a weighted unit of computing-device usage, scaled by system
> performance.
>
> `Computing Usage (SRU) = (CPUCore-Day or GPUBoard-Day) x NPIndex`
>
> `1 SRU = NTD$2`

NPIndex per GPU board-day: **RTX3090 = 79.0**, **A100 = 173.0**, V100 = 70.0,
P100 = 47.0, GTX-1080Ti = 1.0.

So a whole board for a whole day costs:

| GPU | NPIndex | NTD / board-day | USD / board-day |
|---|---:|---:|---:|
| RTX 3090 | 79.0 | **158.00** | 4.89 |
| A100 80 GB | 173.0 | **346.00** | 10.71 |
| RTX 4090 | **not listed** | — | — |

USD at 32.31 TWD/USD (2 August 2026).

### The RTX 4090 has no published rate

It appears in neither the accounting page's NPIndex table nor the resource list,
both checked directly. The card is demonstrably present and usable, but ASGC
publishes no price for it. **No cost figure is given for the fastest card here,
and none should be invented by analogy.**

### Correcting the NT$395 / NT$865 figures

`logs.md` previously used NTD$395/board-day for the 3090 and NTD$865 for the
A100. Those come from a `readthedocs` mirror marked *Last Updated: Feb. 2022*,
which is both **stale and self-contradictory**: its text says `1 SRU = NTD$3`
while its own table lists 395 and 865, which are `79 x 5` and `173 x 5`.

The live ASGC page is internally consistent at `NTD$2` with an explicit NPIndex
table, and is the source used here. **The old figures were too high by 2.5x.**

## The three requested metrics

### epoch / time

| GPU | s/epoch | min/epoch | epochs/hour |
|---|---:|---:|---:|
| **RTX 4090** | 649.83 | **10.83** | 5.540 |
| **A100 80 GB** | 990.17 | **16.50** | 3.636 |
| **RTX 3090** | 1168.88 | **19.48** | 3.080 |

### cost / time

| GPU | SRU/hour | NTD/hour | USD/hour | NTD/board-day |
|---|---:|---:|---:|---:|
| RTX 4090 | — | — | — | no published rate |
| A100 80 GB | 7.208 | 14.42 | 0.446 | 346.00 |
| RTX 3090 | 3.292 | 6.58 | 0.204 | 158.00 |

### epoch / cost

| GPU | SRU/epoch | epochs/SRU | NTD/epoch | USD/epoch | NTD per 6-epoch run |
|---|---:|---:|---:|---:|---:|
| RTX 4090 | — | — | — | — | unpriced |
| A100 80 GB | 1.983 | 0.504 | **3.97** | 0.123 | 23.79 |
| RTX 3090 | 1.069 | 0.936 | **2.14** | 0.066 | 12.83 |

**The 3090 is 1.855x more cost-efficient per epoch than the A100** — 2.19x
cheaper per board-day against only 1.18x slower. That ranking is independent of
the SRU price, which cancels in the ratio.

**The absolute cost is negligible.** A full six-epoch continuation costs about
**NTD$13 (USD$0.40)** on the 3090 or **NTD$24 (USD$0.74)** on the A100. Cost is
not a meaningful constraint on experiment design at this scale; wall-clock time
and GPU availability are.

## Corrections to the prior record

1. **"The 4090 is 3.2x faster than the A100" was wrong.** That rested on an
   A100 rate of 2.30 batch/s sampled while two trainers shared the card. Measured
   solo over six epochs, the true ratio on equal work is **1.524x**. The original
   caveat predicted the contaminated figure understated the card "by up to 2x";
   it was right, and the headline it qualified is withdrawn.

2. **"3090 ahead of the datacentre card is likely but not established" points
   the wrong way.** Measured, the **A100 is 1.180x faster than the 3090**. The
   3090's advantage is cost per epoch, not speed.

3. **The NT$ price figures were 2.5x too high** — see above.

4. **"Running two families in parallel across the 4090 and the A100 is slower
   end to end than queueing both on the 4090" no longer holds.** At 1.524x
   rather than 3.2x, parallel finishes in about 16.5 min/epoch against 21.7
   min/epoch for two sequential 4090 epochs.

## An accuracy note on the superseded estimate

Before the 3090 could be benchmarked it was estimated at ~1,165 s/epoch, by two
independent routes (a cited 4.04 batch/s plus scaled validation overhead, and
scaling the measured batch-3 epoch by relative sample throughput). The measured
value is **1,168.88 s**, so the estimate was accurate to **0.3%**. Recorded
because it means the estimation method is usable when a card cannot be freed,
not because an estimate should be preferred to a measurement.

## What is still unmeasured

- Any RTX 4090 cost figure, for want of a published rate.
- Anything about `amp`, larger batches, or larger models — every figure here is
  FP32, batch 6 (or 3), this model. Those are exactly the regimes where the
  A100 would be expected to close or reverse the gap.
- Solo epoch times for the 4090 and A100; theirs were measured under ~2%
  cluster contention.
