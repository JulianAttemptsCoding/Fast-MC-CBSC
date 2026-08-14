# Original archive baseline

## Exact input

| Field | Value |
|---|---|
| Reviewed filename | `CBSC_ZDC_audit_bundle_20260812.zip` |
| SHA-256 | `ec4f044695401d438d47019012b9d0a1bedda59da5d5d211a97f34e91b5a0432` |
| Compressed size | 110,349,073 bytes |
| Archive files | 1,513 |
| Manifested members | 1,512 plus self-excluded `MANIFEST.sha256` |
| Archive integrity | `unzip -t`: no errors |
| Bundle verification | 1,512 verified; 0 missing, changed, or unlisted |
| Primary code version | `cbsc-zdc-fastmc` 0.3.0 / CBSC-ZDC v2.2 |

The archive, not any legacy subdirectory, is the base used for every file-path
and code-path statement in this handoff. The live Git repository may contain
later commits. The agent must fetch and reconcile the live repository before
editing; it must never overwrite a newer implementation merely to reproduce
this snapshot.

## Audited critical-file hashes

| Relative path | SHA-256 |
|---|---|
| `AGENTS.md` | `4e39294b165a61161507a492cc8964c4c4e9250984bfd34b644afb800fdd55b8` |
| `src/cbsc_zdc/models/system.py` | `84e086357a1345bf8d27759d157c8a6a898a3a0059914c669771b0ae464d6822` |
| `src/cbsc_zdc/models/response.py` | `d02727c5ba2ad74431f0e45dab4a9e641bf6eee08b5332af762b0605c773c1cc` |
| `src/cbsc_zdc/models/profile.py` | `64bb03c5293347cdba5e546c33a313da10207c171f3d83aa3fc7bbc06162285e` |
| `src/cbsc_zdc/models/counts.py` | `3bca32a46ab5ebb02a1e517dc46a65b9e3fef3e148603d494e69846ea661f8dd` |
| `src/cbsc_zdc/models/support.py` | `514f2c3fbbaa12ac4f4a21931afd3086ab53407a93d16fcac9fce84a0f65f865` |
| `src/cbsc_zdc/models/node_fields.py` | `2bad8562e00e5836d91d182d133a07d1685fafb4b0208e54d78e96e954107cfd` |
| `src/cbsc_zdc/training/trainer.py` | `b542dd075d80bf32dcb739f50cee836f3bcd48c70c561371aefa9a13a4a5301f` |
| `src/cbsc_zdc/training/losses.py` | `f926dd69567c8023516ed3ecbfff40649dd5965f565723615cd28e2df7794b1f` |
| `src/cbsc_zdc/config.py` | `091197f456492a040162bda4d76acaa52b35c1b544d2779e5bf926874b7b7139` |
| `configs/templates/train_full_0_300_raw.yaml` | `9ffb04ca4947ebb7d225a20a2a1d0a7eed9bc49046350712f040d3089f508a91` |

## Scientific state at archive time

- Production conversion: 764,940 events in 187 shards.
- Canonical split: 612,482 train / 76,158 validation / 76,300 test.
- Pilot bank used for current training evidence: 26,624 train / 6,656
  validation, about 4.3% of the full training split.
- Primary claim domain: incident neutron kinetic energy 50–250 GeV.
- Training support: approximately 0–300 GeV.
- Detector: 65 layers and 6,790 valid channels: 400 ECAL + 6,390 HCAL.
- Best pre-correction pilot validation loss in the archive: 4.512721 at
  `dicos-e-02`, epoch 47.
- Corrected one-way 24-epoch learning-rate anneal `dicos-f-01` was still in
  flight in the archive.
- Current validation C2ST evidence: low-level/hybrid AUROC about 0.862–0.873;
  high-level AUROC about 0.895–0.929.
- Downstream four-momentum reconstruction errors/spreads were approximately
  1.4–2.5 times the Geant4 reference.
- Physics validation and production readiness were not established.

## Audited defects that the plan must address

1. The restored cosine scheduler inherited a six-epoch `T_max`, producing a
   12-epoch learning-rate sawtooth and confounding architecture conclusions.
2. The response positive branch could sample below zero, clamp to zero, and
   clear a nominally visible event, creating a second unintended zero atom.
3. Rare ECAL/layer-0 starts were underproduced by roughly two orders of
   magnitude in the cited diagnostics.
4. Layer activity and counts were sampled independently across depth,
   underrepresenting longitudinal dependence.
5. Support Gumbel noise could dominate learned support-logit separation.
6. Node fields lacked incident-axis-relative geometry features.
7. The exact full sampler is `@torch.no_grad()` and contains Bernoulli,
   categorical, sorting, and Boolean top-k operations. A classifier attached
   to it cannot provide ordinary end-to-end generator gradients.
8. Current metrics under-cover low-level topology, correlations, diversity,
   memorization, and full downstream physics.

## Current operational constraints

- Active fleet in the archive: L40S for training, RTX 3090 for diagnostics.
  The RTX 4090 was retired on 2026-08-10.
- DiCOS writes are restricted to
  `/dicos_ui_home/julianjuan/sharedfs/work/IOP/julian/Fast MC CBSC`.
- The only permitted data source is the immutable
  `myTree_20251117_765k_0to300GeV_neutron_All.root` at the path specified in
  `AGENTS.md`; every other neighboring data file is out of scope.
- The L40S requires `/usr/lib64` ahead of the zero-byte CUDA stub in
  `LD_LIBRARY_PATH`; use the repository launcher, not a new bypass.
- Test history is not colloquially untouched: an isolated older C2ST used
  40,000 test events and another draw had unresolved overlap. Do not create new
  test access during development.

