#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from types import SimpleNamespace

from cbsc_zdc.cli import command_freeze_config
from cbsc_zdc.data.audit import audit_dataset
from cbsc_zdc.data.split import create_split
from cbsc_zdc.data.synthetic import create_synthetic_dataset
from cbsc_zdc.preflight import validate_frozen_artifacts
from cbsc_zdc.utils import dump_json, dump_yaml, load_yaml, sha256_file


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create deterministic frozen synthetic inputs for a Vertex GPU smoke job"
    )
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", type=int, default=20260724)
    args = parser.parse_args()

    root = Path(args.output).resolve()
    artifacts = root / "artifacts"
    configs = root / "configs"
    artifacts.mkdir(parents=True, exist_ok=True)
    configs.mkdir(parents=True, exist_ok=True)

    created = create_synthetic_dataset(
        artifacts,
        n_events=192,
        n_layers=4,
        nodes_per_layer=4,
        shard_size=64,
        seed=args.seed,
    )
    split_path = artifacts / "splits.json"
    create_split(
        created["manifest"],
        split_path,
        fractions=(0.8, 0.1, 0.1),
        seed=args.seed,
        group_by="event_hash",
    )
    audit_path = artifacts / "train_data_audit.json"
    audit_dataset(
        created["manifest"],
        split_path,
        "train",
        audit_path,
        kinetic_range_gev=(0.0, 300.0),
    )

    template = load_yaml(
        Path(__file__).parents[1] / "configs/templates/train_full_0_300_raw.yaml"
    )
    template["project"]["name"] = "cbsc-zdc-v2-2-vertex-smoke"
    template["project"]["run_dir"] = "runs/vertex_smoke"
    template["model"].update(
        {
            "condition_dim": 16,
            "hidden_dim": 16,
            "response_hidden": 24,
            "response_components": 2,
            "profile_hidden": 16,
            "count_hidden": 24,
            "graph_blocks": 1,
            "attention_heads": 1,
            "attention_layers": 1,
        }
    )
    template["training"].update(
        {
            "seed": args.seed,
            "device": "cuda",
            "batch_size": 16,
            "gradient_accumulation": 1,
            "num_workers": 2,
            "epochs": 1,
            "amp": True,
            "early_stopping_patience": 2,
        }
    )
    template["evaluation"].update({"profile_steps": 1, "share_steps": 1})
    template_path = configs / "template_vertex_smoke.yaml"
    dump_yaml(template, template_path)

    frozen_path = configs / "frozen_vertex_smoke.yaml"
    command_freeze_config(
        SimpleNamespace(
            template=str(template_path),
            audit=str(audit_path),
            geometry=str(artifacts / "geometry"),
            manifest=str(created["manifest"]),
            splits=str(split_path),
            output=str(frozen_path),
        )
    )
    frozen = load_yaml(frozen_path)
    preflight = validate_frozen_artifacts(frozen, verify_shards=True)
    dump_json(preflight, artifacts / "local_preflight.json")

    files = sorted(path for path in root.rglob("*") if path.is_file())
    dump_json(
        {
            "purpose": "synthetic Vertex software/infrastructure smoke only",
            "physics_validation": False,
            "seed": args.seed,
            "config_relative": "configs/frozen_vertex_smoke.yaml",
            "files": [
                {
                    "path": path.relative_to(root).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
                for path in files
            ],
        },
        root / "smoke_input_manifest.json",
    )
    print(f"Prepared frozen Vertex smoke input: {root}")


if __name__ == "__main__":
    main()
