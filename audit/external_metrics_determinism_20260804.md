# External evaluator determinism proof — 2026-08-04

Two independent RTX 3090 executions used the same fixed validation bank,
partition, three evaluator seeds, deterministic PyTorch/cuDNN configuration,
and `CUBLAS_WORKSPACE_CONFIG=:4096:8`.

- Scientific model/report content after removing wall-time fields: exact match.
- AUROC values: `0.867275`, `0.8646277777777778`,
  `0.8860638888888889` in both executions.
- Ensemble AUROC: `0.8726555555555556 ± 0.011687150998288242`.
- Evaluator checkpoint SHA-256: exact match,
  `ed2dda9c4b6d35a027ae2ecd4ce0739788baa6b78087f04d4e7c9477a906dacf`.
- CBSC test events used: `0`.

Only elapsed-second fields differ and are explicitly excluded from scientific
equality. The JSON twin records both source hashes and the complete verdict.
