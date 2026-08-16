#!/usr/bin/env python
"""Read-only checkpoint identity probe for the autonomous v3 battery queue."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch

from cbsc_zdc.utils import sha256_file


def identity(checkpoint: Path, frozen_config: Path, expected_epoch: int) -> dict:
    payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
    embedded_epoch = int(payload["epoch"])
    if embedded_epoch != int(expected_epoch):
        raise ValueError(
            f"checkpoint epoch mismatch: expected {expected_epoch}, "
            f"embedded {embedded_epoch}"
        )
    best_metric = float(payload["best_metric"])
    return {
        "checkpoint": checkpoint.as_posix(),
        "checkpoint_sha256": sha256_file(checkpoint),
        "checkpoint_embedded_epoch": embedded_epoch,
        "checkpoint_best_metric": best_metric,
        "frozen_config": frozen_config.as_posix(),
        "frozen_config_sha256": sha256_file(frozen_config),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--frozen-config", type=Path, required=True)
    parser.add_argument("--expected-epoch", type=int, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(identity(
        args.checkpoint, args.frozen_config, args.expected_epoch
    ), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
