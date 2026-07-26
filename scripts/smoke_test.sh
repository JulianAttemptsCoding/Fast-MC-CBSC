#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
WORK="${1:-/tmp/cbsc_zdc_smoke}"
rm -rf "$WORK"
PYTHONPATH=src python -m cbsc_zdc.cli make-synthetic --output "$WORK" --events 24 --layers 2 --nodes-per-layer 3 --shard-size 12 --seed 123
PYTHONPATH=src python -m cbsc_zdc.cli split --manifest "$WORK/data/dataset_manifest.json" --output "$WORK/splits.json" --group-by event_hash --seed 123
PYTHONPATH=src python -m cbsc_zdc.cli audit-dataset --manifest "$WORK/data/dataset_manifest.json" --splits "$WORK/splits.json" --split train --kinetic-range 0 300 --output "$WORK/train_audit.json"
cp configs/templates/train_full_0_300_raw.yaml "$WORK/template.yaml"
python - "$WORK/template.yaml" "$WORK" <<'PY'
from pathlib import Path
import sys, yaml
p=Path(sys.argv[1]); root=Path(sys.argv[2]); cfg=yaml.safe_load(p.read_text())
cfg['project']['run_dir']=str(root/'run')
cfg['model'].update({'condition_dim':8,'hidden_dim':8,'response_hidden':12,'response_components':2,'profile_hidden':8,'count_hidden':12,'graph_blocks':1,'attention_layers':1,'attention_heads':1})
cfg['training'].update({'device':'cpu','batch_size':6,'gradient_accumulation':1,'num_workers':0,'epochs':1,'amp':False,'early_stopping_patience':2})
cfg['evaluation'].update({'profile_steps':1,'share_steps':1})
p.write_text(yaml.safe_dump(cfg,sort_keys=False))
PY
PYTHONPATH=src python -m cbsc_zdc.cli freeze-config --template "$WORK/template.yaml" --audit "$WORK/train_audit.json" --geometry "$WORK/geometry" --manifest "$WORK/data/dataset_manifest.json" --splits "$WORK/splits.json" --output "$WORK/frozen.yaml"
PYTHONPATH=src python -m cbsc_zdc.cli train --config "$WORK/frozen.yaml" --device cpu
PYTHONPATH=src python -m cbsc_zdc.cli qa --checkpoint "$WORK/run/checkpoints/best.pt" --geometry "$WORK/geometry" --profile-steps 1 --share-steps 1 --output "$WORK/qa.json" --device cpu
PYTHONPATH=src python -m cbsc_zdc.cli sample --checkpoint "$WORK/run/checkpoints/best.pt" --geometry "$WORK/geometry" --kinetic-gev 50 150 250 --profile-steps 1 --share-steps 1 --output "$WORK/samples.npz" --device cpu
PYTHONPATH=src python -m cbsc_zdc.cli benchmark --checkpoint "$WORK/run/checkpoints/best.pt" --geometry "$WORK/geometry" --batch-size 2 --warmup 1 --iterations 2 --profile-steps 1 --share-steps 1 --device cpu --output "$WORK/benchmark.json"
echo "Smoke test passed: $WORK"
