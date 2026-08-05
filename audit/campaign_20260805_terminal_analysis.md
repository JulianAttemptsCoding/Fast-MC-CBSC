# Campaign `camp-20260805` — declaration, launch, and one aborted segment

## Disposition

`QA PASS` for the campaign machinery. Training is in flight. No scientific
conclusion is available yet and none is claimed.

## Declaration

**Question.** Does the strongest calibrated family continue improving on the
26,624/6,656 pilot bank when given further 20-epoch segments, and does the
ordering between families survive being given comparable numbers of epochs?

**Chain and rule, as the owner stated it.** `calibrated_lr3e4` for 20 further
epochs; if the best loss is within 6 epochs of the most current epoch, continue
the same family, otherwise advance to `calibrated_lr1e4_halfbatch` on the same
rule, then `calibrated_lr3e5`. The owner named a third family "lr1e5" which does
not exist; asked which of the four was meant, they answered `lr3e5`.

`calibrated_lr1e4` is excluded by the owner's instruction. It has had 39 epochs,
the most of any family, and its `dicos-p10` epoch-40 checkpoint is
`ARTIFACT QUARANTINED` and is not a valid parent.

**Boundary.** Optimization evidence on the pilot bank. Nothing about Geant4
fidelity, three-seed behaviour, or untouched-test performance. The
76,300-event test split is not read by training, diagnostics, or visualization.
`PHYSICS VALIDATION NOT ESTABLISHED`.

**Comparability.** Every segment uses the energy-scaled closure tolerance
declared 2026-08-05, so these segments are a new declared experiment relative to
any run frozen before it.

## Parents, verified on the host

| family | run | best epoch | validation loss | best.pt SHA-256 |
|---|---|---:|---:|---|
| `calibrated_lr3e4` | `dicos-p7` | 22 | 4.597151546143159 | `31802b9f…9bfb` |
| `calibrated_lr1e4_halfbatch` | `dicos-p7` | 21 | 4.673036068110655 | `ffab832a…ad9b1` |
| `calibrated_lr3e5` | `dicos-r3` | 8 | 4.843470557018744 | `3641c1a6…14a79` |

`parent_last_epoch` is the **best** epoch, not the last, because the resume
continues from the best checkpoint. For the half-batch family those differ — 21
against 22 — and using the last would have shifted its horizon by one.

## What makes unattended freezing safe

The supervisor generates a template, freezes it through the CLI, and then reads
its own diff against the parent frozen config, refusing to launch if anything
outside an explicit allowlist moved. `tests/test_campaign.py` pins that the
allowlist contains no scientific value: learning rate, batch size, seed,
accumulation, workers, solver steps and the absolute closure tolerance are all
refused.

It also refuses to launch when the run directory exists or another trainer is in
the process tree, using a search token assembled at runtime so the probe cannot
match itself.

## Segment `dicos-c-01` — aborted after 6 minutes, two defects

Neither was visible without launching, and both would have run for hours looking
healthy.

**The diagnostic producer died instantly and silently.**

```text
ValueError: run directory must be a safe workdir-relative path
  dicos_diag_producer.py:50 resolve_under <- :309 main
```

The producer resolves its path arguments under the workdir and refuses anything
that escapes it; the supervisor passed absolute paths. `producer_started` had
already been logged with its pid, and since nothing waits on the producer until
the trainer exits, it sat as `[python] <defunct>`. **The campaign would have
trained for hours with nothing reaching the 3090.** Caught only by reading the
process tree rather than the log.

Fixed by passing workdir-relative paths and by verifying producer liveness five
seconds after launch. A dead producer now terminates the trainer and aborts the
segment, because training blind is worse than not training.

**`CBSC_ZDC_SHARD_CACHE` was unset**, so the run recorded `shard_cache_size: 4`
— the slow-loader configuration that got `dicos-r2` archived. The symptom was
the GPU at 487 MiB and **0% utilization** with four loader workers at ~85% CPU:
starving, not stalled. Every accepted run since uses `0`; the supervisor now
sets it.

**Disposition.** No epoch completed, so no evidence was produced or lost.
Stopped supervisor-first so it could not observe the exit and start a second
segment, then the trainer. GPU confirmed released at `0 MiB` and a
self-match-safe `/proc` scan confirmed `holders: NONE` **before** anything moved,
because a live process resolves paths per write and would follow the directory.

```text
_runs/calibrated_lr3e4_dicos-c-01 -> _runs/aborted_c01_producer_path_and_shard_cache/
_diag/dicos-c-01                  -> _diag/aborted-c01
```

`dicos-c-01` produced no epochs and must not be compared against anything.

## Segment `dicos-c-02` — in flight

```text
frozen   29fc4fe0f79276e4919c58554f544707e016a7dcb99912726b284caa15c450d7
template e2612a223286842a7148c36bdb394750b1a3e7d124b6e0796de3b49cc4a230ba
parent   4051591355f22fa07f8a8aaea80a86a05cac85f92430fc13bfb52dc034ab609a
resume   31802b9fcdde49a7369786b028b17ff1b09fd22c6587c118c9d41783b9a49bfb
         the p7 epoch-22 best, on BOTH resume slots
absolute epochs 23..42, patience 20, cosine continued not restarted
```

The frozen config regenerated byte-identically, so the idempotent path reused it
rather than overwriting a frozen config. Both fixes verified in the live run:
producer pid present and not defunct, `environment.json` records
`shard_cache_size: 0`.

## What is autonomous and what is not

Autonomous on DiCOS: training across segments and families, per-epoch structural
gates, per-epoch 3090 diagnostics namespaced by run tag, and campaign state and
event journalling.

**Not autonomous, and not a matter of effort:**

- **the public website** — the pods have no Node, so it cannot be built there;
- **any push or publication from a pod** — the only writable directory on DiCOS
  is the multi-tenant project workdir and `$HOME` is not writable, so a
  credential file would have to live where other tenants can read it;
- **exhibition figures** — the builders write into `exhibition/current/`, so
  running them inside the pod's `repo/` checkout would dirty the clean tree that
  the pre-launch gate and every `git pull` depend on.

Figures are a deterministic rendering of the metrics, which do accumulate on the
pod. `scripts/refresh_campaign_outputs.py` rebuilds the whole local picture from
the campaign's own recorded state with no arguments, so the arguments that
change every segment cannot be got wrong.

## Cost

DiCOS is accounted in ASGC SRUs. At the measured 649.83 s/epoch on the 4090 a
20-epoch segment is roughly 3.6 hours. No paid cloud compute was used.
