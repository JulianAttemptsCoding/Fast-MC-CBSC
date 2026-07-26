#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python -m compileall -q src tests
PYTHONPATH=src pytest -q
PYTHONPATH=src python -m cbsc_zdc.cli doctor
PYTHONPATH=src python -m cbsc_zdc.cli --help >/dev/null
echo "Repository verification passed."
