# Local and DiCOS workspace layout

## Workstation repository

- `scripts/refresh_continuation_outputs.py` is the sole per-epoch refresh entry
  point. It pulls hash-verified 3090 metrics and matching 4090 visualization
  evidence, refreshes loss-vs-epoch and best-so-far plots, rebuilds the current
  gallery and complete exhibition, and writes epoch audit twins.
- `exhibition/index.html` is the comprehensive catalog of every scientific
  PNG/SVG. `exhibition/current.html` is the compact current-model gallery.
- `exhibition/data/` contains compact immutable inputs, namespaced by run tag.
  Generated figures remain in provenance-preserving subdirectories and are
  organized logically by the comprehensive index rather than moved.
- `dashboard/` is the internal all-accepted-epoch viewer. The sibling
  `Fast-MC-Visual-Tests` repository contains exactly one accepted snapshot per
  family and changes only when validation loss establishes a new accepted best.

UI icons under `dashboard/public/` are application chrome, not scientific
figures, and are therefore not duplicated in the exhibition.

## DiCOS shared project workdir

The only active compute roles are:

| Path | Role |
|---|---|
| `.venv` | RTX 4090 sole training writer |
| `.venv_3090` | RTX 3090 per-epoch diagnostic consumer |
| `repo/` | synchronized source checkout |
| `prep/` | immutable prepared inputs and frozen configurations |
| `_runs/<family>_<tag>/` | namespaced training evidence |
| `_diag/<tag>/` | namespaced checkpoint/diagnostic handoff |
| `_external_metrics/deps/` | hash-pinned read-only evaluator source/model dependencies |
| `_external_metrics/runtime/` | frozen bank/evaluator entry points and configuration |
| `_external_metrics/runs/<tag>/epoch_NNNN/` | accepted-best bank, attempt logs, and downstream results |
| `_workspace/` | generated non-destructive workspace index |

External-metric stage retries preserve their prior PID/exit/log and partial
output under the transaction-local `attempts/` directory. The active
`validation_bank.manifest.json` and `results/manifest.json` are the only ready
sentinels; filenames, PIDs, or partial output alone never establish success.

The retired 80 GB datacentre environment, `.venv_dcgpu`, `_bench`, and `_setup`
are preserved historical material and are not current execution paths. Loose launcher logs/PID records
under `_runs/` stay in place because recovery evidence refers to their original
paths. `_tmp/` is transient QA material and must never become an input.

Generate or verify the index without moving evidence:

```bash
PYTHONDONTWRITEBYTECODE=1 python repo/scripts/dicos_workspace_inventory.py \
  --root . --output-dir _workspace
```

This organization is intentionally non-destructive. Cleanup requires a
separate evidence review and exact recovery plan.
