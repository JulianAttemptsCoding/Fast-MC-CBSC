# Compute extension terminal analysis — 2026-07-27

All four user-authorized, on-demand T4 compute-extension jobs succeeded. Every
second added epoch passed the streamed checkpoint, finite-tensor, paired
recovery, history, invariant, T4 resource, fixed 50-by-5 validation sample,
selection-hash, and zero-test gates.

| Family | Parent loss | First added | Final | Final vs first | Final vs parent |
|---|---:|---:|---:|---:|---:|
| LR 3e-5 | 4.988944 | 4.974206 (E1) | 4.927671 (E2) | 0.936% better | 1.228% better |
| LR 1e-4 | 4.973253 | 4.952879 (E1) | 4.878822 (E2) | 1.495% better | 1.899% better |
| LR 3e-4 | 4.800034 | 4.828354 (E3) | 4.738041 (E4) | 1.870% better | 1.292% better |
| LR 1e-4, half batch | 4.903753 | 4.882708 (E3) | 4.845029 (E4) | 0.772% better | 1.198% better |

The exact requested question has a positive answer: two additional epochs
improved validation loss in all four calibrated families. LR 3e-4 first
regressed, then recovered to the best loss in its family. This supports
continued optimization on faster hardware, but does not establish Geant4
fidelity. Fixed-sample response, hit-count, and longitudinal-profile proxies
remain mixed and sometimes move opposite to the full validation objective.

The four jobs consumed 9.930278 T4-hours. At the predeclared conservative
$0.85/hour rate, the extension projects to $8.4408. Adding the prior $35.24
ledger and $5 build/storage/management contingency gives $48.6808, leaving
$51.3192 under the hard $100 ceiling.

The public site now contains only the new best checkpoint for each calibrated
family. Commit `a3816fbd590fde159d3a0c02ea0a67caa22673dc` deployed successfully
in workflow `30243408128`. Live manifest SHA-256 is
`2e504c7a094fe90ae050adbb06765834ea2472f4b7c7fa83beffbfcf17ba1f00`;
all four live gzip hashes, decompressions, exact IDs/checkpoints, 50-by-5
groups, validation split, QA flags, and zero-test claims were independently
verified. Interactive browser QA was blocked by the Codex kernel-asset
`os error 3`; HTTP, artifact, seven tests, TypeScript build, and static
frontend contracts pass.

Storage remediation is also terminal. The 25,022,001,408-byte local ROOT copy
was removed only after matching the durable GCS generation, byte size, CRC32C,
and frozen source SHA-256. The 4,105,726,074-byte audit tree was archived at
`gs://asiop-zdc-1-zdc-reco-us-central1/cbsc-v2-2/local-evidence-offload-20260727-r1/audit`;
local and remote inventories match at 1,018 objects and the checksum-only
rsync passed before ignored local mirrors were removed.

Final disposition:

```text
structural_and_optimization_QA=PASS
more_compute_validation_hypothesis=SUPPORTED_FOR_ALL_4_CALIBRATED_FAMILIES
physics_validation=NOT_ESTABLISHED
historical_frozen_A100_screening=NO-GO_UNCHANGED
test_evaluation=BLOCKED_NOT_OPENED
further_Vertex_jobs_authorized=false
```
