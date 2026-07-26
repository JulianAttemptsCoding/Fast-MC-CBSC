#!/usr/bin/env bash
set -euo pipefail
if [[ $# -lt 2 ]]; then
  echo "Usage: $0 OUTPUT_DIR ROOT_FILE [ROOT_FILE ...]" >&2
  exit 64
fi
OUT="$1"; shift
ROOTS=("$@")
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"
mkdir -p "$OUT"
SCHEMA="configs/schema_sample_edm4hep.yaml"
PYTHONPATH=src python -m cbsc_zdc.cli inspect-root "${ROOTS[0]}" --schema "$SCHEMA" --output "$OUT/root_inspection.json"
PYTHONPATH=src python -m cbsc_zdc.cli scan-geometry "${ROOTS[@]}" --schema "$SCHEMA" --output "$OUT/geometry"
PYTHONPATH=src python -m cbsc_zdc.cli convert "${ROOTS[@]}" --schema "$SCHEMA" --geometry "$OUT/geometry" --output "$OUT/data" --target-mode raw_deposit --min-kinetic-gev 0 --max-kinetic-gev 300
PYTHONPATH=src python -m cbsc_zdc.cli split --manifest "$OUT/data/dataset_manifest.json" --output "$OUT/splits.json" --fractions 0.8 0.1 0.1 --group-by source_group --seed 20260723
PYTHONPATH=src python -m cbsc_zdc.cli audit-dataset --manifest "$OUT/data/dataset_manifest.json" --splits "$OUT/splits.json" --split train --kinetic-range 0 300 --output "$OUT/train_data_audit.json"
echo "Prepared artifacts in $OUT. STOP and review all JSON before freezing configs."
