#!/usr/bin/env bash
set -euo pipefail
if [[ $# -ne 6 ]]; then
  echo "Usage: $0 CHECKPOINT GEOMETRY MANIFEST SPLITS OUTPUT_JSON DEVICE" >&2
  exit 64
fi
REPO="$(cd "$(dirname "$0")/.." && pwd)"; cd "$REPO"
PYTHONPATH=src python -m cbsc_zdc.cli qa --checkpoint "$1" --geometry "$2" --output "${5%.json}_invariants.json" --device "$6"
PYTHONPATH=src python -m cbsc_zdc.cli evaluate --checkpoint "$1" --geometry "$2" --manifest "$3" --splits "$4" --split test --gates configs/gates_primary.yaml --output "$5" --device "$6" --require-pass
