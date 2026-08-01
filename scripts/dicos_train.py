"""Run one training family on DiCOS, with the same checks the Vertex path used.

This is the DiCOS twin of `cbsc_zdc.cloud.vertex_stage`: same config
validation, same hash-verified resume, same per-epoch snapshots, same training
postflight. Only the transport differs -- artifacts are read from, and results
written to, the shared filesystem instead of GCS. Nothing scientific is
re-decided here.

Everything it touches lives under the one writable directory named in
AGENTS.md rule 17; the frozen config supplies the read-only dataset paths.

Usage (on the host, from the workdir):
    .venv/bin/python repo/scripts/dicos_train.py \
        --config prep/configs/frozen_calibrated_lr3e4_dicos-r1.yaml \
        --run-dir _runs/calibrated_lr3e4_dicos-r1
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path

REPO_SRC = Path(__file__).resolve().parents[1] / "src"
if str(REPO_SRC) not in sys.path:
    sys.path.insert(0, str(REPO_SRC))

from cbsc_zdc.cloud.vertex_stage import (  # noqa: E402
    _resolve_staged_checkpoints,
    run_training_postflight,
)
from cbsc_zdc.config import validate_config  # noqa: E402
from cbsc_zdc.training.trainer import train_from_config  # noqa: E402
from cbsc_zdc.utils import (  # noqa: E402
    dump_json,
    dump_yaml,
    environment_snapshot,
    load_yaml,
    sha256_file,
)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="frozen config for this family")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument(
        "--staged-root",
        default="prep",
        help="root the config's *_relative checkpoint paths resolve against",
    )
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--postflight", action="store_true")
    args = parser.parse_args(argv)

    config_path = Path(args.config)
    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    config = load_yaml(config_path)
    config["project"]["run_dir"] = str(run_dir.resolve())
    config["training"]["device"] = args.device

    # Same guarantee as the Vertex path: a resume checkpoint is located and
    # hash-verified before a single weight is loaded.
    _resolve_staged_checkpoints(config, Path(args.staged_root))
    validate_config(config)

    runtime_path = run_dir / "runtime_config.yaml"
    dump_yaml(config, runtime_path)
    dump_json(environment_snapshot(), run_dir / "environment.json")

    started = time.time()

    def on_epoch(epoch, run, row):
        """Per-epoch snapshot. Written to the shared filesystem, which outlives
        the pod, so an expired DiCOSApp costs at most the epoch in flight."""
        dump_json(
            {
                "epoch": int(epoch),
                "row": row,
                "elapsed_seconds": round(time.time() - started, 3),
                "best_checkpoint_sha256": sha256_file(run.checkpoints / "best.pt"),
                "last_checkpoint_sha256": sha256_file(run.checkpoints / "last.pt"),
            },
            run.reports / f"progress_epoch_{epoch:04d}.json",
        )

    def on_progress(progress, run, progress_path):
        dump_json(
            {
                "progress": progress,
                "progress_checkpoint_sha256": sha256_file(progress_path),
                "elapsed_seconds": round(time.time() - started, 3),
            },
            run.reports / "progress_inflight.json",
        )

    result_path = run_dir / "result.json"
    try:
        result = train_from_config(
            config, epoch_callback=on_epoch, progress_callback=on_progress
        )
        postflight = (
            run_training_postflight(config, result, run_dir) if args.postflight else None
        )
        dump_json(
            {
                "runtime_config": str(runtime_path),
                "config_sha256": sha256_file(runtime_path),
                "training": result,
                "training_postflight": postflight,
                "wall_seconds": round(time.time() - started, 3),
                "status": "ok",
            },
            result_path,
        )
    except Exception as exc:  # noqa: BLE001 -- recorded, then re-raised
        dump_json(
            {
                "status": "failed",
                "error": repr(exc),
                "traceback": traceback.format_exc(),
                "wall_seconds": round(time.time() - started, 3),
            },
            result_path,
        )
        raise

    print(json.dumps(json.loads(result_path.read_text())["training"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
