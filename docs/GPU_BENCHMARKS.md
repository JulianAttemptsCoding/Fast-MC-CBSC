# GPU throughput and cost — measured, cited, and unmeasured

Single source of truth for GPU performance on this workload. It supersedes the
throughput and cost numbers scattered through `logs.md`, two of which were
wrong. Every row below is labelled **measured**, **cited**, or **estimated**;
do not promote a label without new evidence.

Hardware choice is transport, not science (`docs/QA_POLICY.md`). Nothing here
grants or denies permission to run anything.

## Method

All comparisons use identical work: the same architecture, the same frozen
pilot bank (26,624 train / 6,656 validation), `gradient_accumulation: 4`,
`amp: false`, `num_workers: 4`, `CBSC_ZDC_SHARD_CACHE=0`, torch `2.6.0+cu124`,
numpy `2.5.1`, `cudnn.allow_tf32=True`, `cuda.matmul.allow_tf32=False`.
Families differ only in learning rate, which does not change the compute.

Two rates are reported and they are not interchangeable:

- **epoch wall time** — from the run's own `history.csv` `seconds` column,
  covering training *and* validation for one full epoch. This is the practical
  number and the basis for the cost figures below.
- **mid-epoch training-only batch/s** — from `progress_inflight.json` deltas.
  Useful for a quick comparison, but excludes validation.

**Batch size must match or the comparison is void.** `calibrated_lr1e4_halfbatch`
runs `batch_size: 3` against the other families' `6`, giving 8,874 batches per
epoch instead of 4,437 on the same 26,624 samples. Its batch/s is therefore not
comparable to a batch-6 figure, and smaller batches are independently less
efficient per sample. Only `examples_per_second` compares across batch shapes,
and even that confounds card speed with batch-shape efficiency.

**One trainer per GPU, always.** The single worst measurement error in this
project's history came from sampling a GPU while two trainers shared it.

**Caveat that applies to every 2026-08-03 figure: the GPUs are separate, the
filesystem is not.** All three measurements were taken with three trainers
running concurrently on three pods that mount the same CephFS workdir. The
cards do not contend, but shard loading and checkpoint writes do.
`CBSC_ZDC_SHARD_CACHE=0` keeps all 187 shards resident per worker, so steady-
state reads come from memory rather than the filesystem, which should make the
effect small — but it is not zero, and it is visible: the 4090's first two
epochs took 645.36 s and 659.18 s, a 2.1% spread on identical work.

The practical consequence is that **the ratios are more trustworthy than the
absolute epoch times**, because contention depresses all three roughly
together. Absolute epoch times measured under a solo run would likely be
slightly faster than the numbers here. Where a decision turns on the ratio —
which card, which is cheaper per epoch — this caveat does not change the
answer. Where it turns on absolute wall-clock, treat these as a mild
upper bound.

## Measured — 2026-08-03, solo, batch 6, identical work

| GPU | epoch wall time | epochs/hour | examples/s | source |
|---|---:|---:|---:|---|
| RTX 4090 | **645.36 s** (10.76 min) | 5.578 | 41.25 | `calibrated_lr3e4_dicos-p7` epoch 17 |
| A100-SXM4-80GB | **997.18 s** (16.62 min) | 3.610 | 26.70 | `calibrated_lr1e4_dicos-p6` epoch 11 |

**The RTX 4090 is 1.545x the A100 on this workload.** Both measurements are
solo, first-epoch-of-run, and cover identical batch counts, so warmup enters
both symmetrically.

Mid-epoch training-only rates sampled the same way on the same day:

| GPU | batch/s | batch size |
|---|---:|---:|
| RTX 4090 | 7.29 | 6 |
| A100-SXM4-80GB | 4.65 | 6 |
| RTX 3090 | 7.06 | **3 — not comparable to the rows above** |

The 4090's 7.29 batch/s reproduces the 7.31 recorded on 2026-08-02, which is a
useful independent check that the sampling method is stable.

### The A100's memory buys nothing here

Peak CUDA memory is **11.74 GB on both cards** — identical, as it should be for
the same architecture at the same batch size. The A100's 80 GB leaves ~68 GB
idle, and the 4090's 24 GB is less than half used.

This matters for the choice of card. The A100's headline advantages are memory
capacity, memory bandwidth, and tensor-core throughput. This workload runs
`amp: false`, so it never touches a tensor core, and it fits in a third of a
4090. What remains is FP32 non-tensor-core throughput, where the 4090 is simply
the faster part. Nothing about that is a defect in the A100; the workload just
does not ask for anything the A100 is good at.

The corollary is that the A100 would only become interesting under a *separately
declared* experiment that used its strengths — mixed precision, a substantially
larger batch, or a larger model. Any of those is a new declared experiment with
its own QA, not a transport change.

## Cited — not re-verifiable from artifacts

| GPU | batch/s | batch size | status |
|---|---:|---:|---|
| RTX 3090 | 4.04 | 6 | recorded 2026-08-02 from a solo `_bench/` run under the same frozen config. **`_bench/` no longer exists on the filesystem**, so this is a citation, not a measurement that can be re-checked. |

Against today's solo A100 figure this puts the **A100 at about 1.15x the
3090** on batch-6 throughput. That ordering is new, and it reverses an earlier
guess — see corrections.

## Estimated — pending a live measurement

| GPU | epoch wall time | epochs/hour | basis |
|---|---:|---:|---|
| RTX 3090 | ~1,158 s (~19.3 min) | ~3.11 | 4,437 batches at the cited 4.04 batch/s, plus ~60 s validation scaled from the measured 4090 and A100 validation overheads (36.8 s and 43.0 s respectively) |

**This is an estimate and is labelled as such in every table that uses it.** A
clean batch-6 benchmark on the 3090 is scheduled for after
`calibrated_lr1e4_halfbatch_dicos-p7` finishes on that card. It must not be run
concurrently with that training — that is exactly how the bad A100 number was
produced.

## Pricing, and why the NT$ figures are soft

From ASGC's published resource table, **dated February 2022**:

| GPU | SRU / board-day |
|---|---:|
| RTX 3090 | 79 |
| A100 (80 GB) | 173 |
| RTX 4090 | **not listed** |

There is **no published rate for the RTX 4090** in either the price list or the
resource list, so no cost figure can be given for the fastest card here. That
is a gap in the vendor's published data, not something to fill by analogy.

ASGC's own documents disagree on the value of one SRU: one states **NT$2**,
another **NT$3**, and the price table implies **NT$5**. Absolute NT$ figures
are therefore uncertain by up to 2.5x and are always quoted as a range. **The
SRU ratios are unaffected** and are the trustworthy quantity: the A100 costs
`173/79 = 2.19x` the 3090 per board-day.

Whether this account is billed at all, or draws on a project allocation, is not
visible from the client.

## The three requested metrics

### epoch / time

| GPU | min/epoch | epochs/hour | status |
|---|---:|---:|---|
| RTX 4090 | 10.76 | 5.578 | measured |
| A100 80 GB | 16.62 | 3.610 | measured |
| RTX 3090 | ~19.3 | ~3.11 | estimated |

### cost / time

| GPU | SRU/hour | NT$/hour (SRU = 2 … 5) | status |
|---|---:|---:|---|
| RTX 4090 | — | — | **no published rate** |
| A100 80 GB | 7.208 | 14.42 … 36.04 | table |
| RTX 3090 | 3.292 | 6.58 … 16.46 | table |

### epoch / cost

| GPU | SRU/epoch | epochs/SRU | NT$/epoch (SRU = 2 … 5) | status |
|---|---:|---:|---:|---|
| RTX 4090 | — | — | — | unpriced |
| A100 80 GB | 1.997 | 0.501 | 3.99 … 9.98 | measured epoch, table price |
| RTX 3090 | ~1.059 | ~0.944 | ~2.12 … ~5.29 | estimated epoch, table price |

**The 3090 is roughly 1.9x more cost-efficient per epoch than the A100**,
despite being the slower card, because it is 2.19x cheaper per board-day and
only about 1.15x slower. If throughput is the goal the 4090 wins outright; if
cost per epoch is the goal the 3090 leads among the two priced cards.

This conclusion rests on an estimated 3090 epoch time and on a disputed SRU
price. The ranking between the two priced cards is robust to the SRU price,
because that price cancels in the ratio.

## Corrections to the prior record

1. **"The 4090 is 3.2x faster than the A100" is wrong.** That came from an
   A100 rate of 2.30 batch/s sampled while two trainers shared the card. The
   solo rate measured on 2026-08-03 is 4.65 batch/s, and the true ratio on
   equal work is **1.545x** by epoch wall time. The earlier figure overstated
   the 4090's advantage by very close to the 2x contamination factor that the
   original caveat predicted.

2. **"3090 ahead of the datacentre card is likely but not established" was a
   guess, and it points the wrong way.** With the A100 measured solo, the A100
   is about 1.15x *faster* than the 3090, not slower. The 3090's advantage is
   in cost per epoch, not throughput.

3. The practical consequence recorded on 2026-08-02 — that running two
   families across the 4090 and the A100 is slower end-to-end than queueing
   both on the 4090 — **no longer holds**. At 1.545x rather than 3.2x, two
   families in parallel across those two cards finish in about the time the
   A100 alone takes for one, which beats sequential on the 4090.

## What is still unmeasured

- Any RTX 4090 cost figure, for want of a published rate.
- A live 3090 batch-6 epoch time.
- Anything about `amp`, larger batches, or configurations that would engage the
  A100's tensor cores or its memory-bandwidth advantage. Every figure here is
  FP32, batch 6 or 3, this model.
