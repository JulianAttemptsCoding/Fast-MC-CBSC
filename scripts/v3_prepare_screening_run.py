"""Freeze a v3 screening config and migrate its parent checkpoint in one step.

Produces, for one matrix row:

* a frozen config with recorded template and frozen hashes;
* a v3 initial checkpoint migrated from the parent, with the expanded axis
  columns zero-initialized so the migrated model reproduces its parent before
  fine-tuning;
* an audit twin recording every hash and the exact key classification.

It does not launch training.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import torch
import yaml

from cbsc_zdc.data.dataset import load_geometry
from cbsc_zdc.models.system import CBSCZDC
from cbsc_zdc.training.migration import (
    AXIS_FEATURE_COLUMNS,
    migrate_state_dict,
    sha256_file,
)
from cbsc_zdc.utils import sha256_json


def freeze(template: Path, config: dict, output: Path) -> None:
    cmd = [
        sys.executable, "-m", "cbsc_zdc.cli", "freeze-config",
        "--template", str(template),
        "--audit", str(config["provenance"]["train_data_audit"])
        if "train_data_audit" in config.get("provenance", {}) else str(config["data"]["audit"]),
        "--geometry", str(config["geometry"]["path"]),
        "--manifest", str(config["data"]["manifest"]),
        "--splits", str(config["data"]["splits"]),
        "--output", str(output),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"freeze-config failed:\n{result.stdout}\n{result.stderr}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--parent-checkpoint", type=Path, required=True)
    parser.add_argument("--frozen-output", type=Path, required=True)
    parser.add_argument("--checkpoint-output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--audit", type=Path, help="train data audit path override")
    parser.add_argument("--checkpoint-relative",
                        help="path recorded in the config, relative to the run root")
    args = parser.parse_args()

    template_config = yaml.safe_load(args.template.read_text(encoding="utf-8"))
    if args.audit:
        template_config.setdefault("data", {})["audit"] = str(args.audit)
        args.template.write_text(yaml.safe_dump(template_config, sort_keys=False), encoding="utf-8", newline="\n")

    # Migrate BEFORE freezing. The frozen config must carry
    # training.initialize_from_sha256, which cannot exist until the checkpoint
    # does; and the model shapes come from the template, since freezing only
    # adds provenance hashes.
    geometry = load_geometry(template_config["geometry"]["path"])
    target_model = CBSCZDC(geometry, template_config)
    target_model.preflight_v3_envelope()
    target_state = target_model.state_dict()

    payload = torch.load(args.parent_checkpoint, map_location="cpu", weights_only=False)
    # The axis block is inserted directly after the static node features, which
    # is where the field concatenates it. Appending instead would shift the
    # condition, layer-energy and count-fraction columns and silently destroy
    # the parent's behaviour.
    axis_offset = int(target_model.node_features.shape[1]) if target_model.axis_enabled else None
    # A v3 row that leaves axis features off adds no columns at all. Passing the
    # default 4 would make the migration demand an expansion the target does not
    # have, which is exactly how S2-response first failed.
    axis_columns = AXIS_FEATURE_COLUMNS if target_model.axis_enabled else 0
    migrated, report = migrate_state_dict(
        payload["model_state"], target_state,
        axis_columns=axis_columns, axis_offset=axis_offset,
    )
    report["axis_insertion_offset"] = axis_offset
    report["axis_columns_added"] = axis_columns

    # The migrated model must load cleanly and still satisfy every invariant.
    target_model.load_state_dict(migrated)

    out = {
        "format_version": 4,
        "model_state": migrated,
        "optimizer_state": None,
        "scheduler_state": None,
        "scaler_state": None,
        "epoch": 0,
        "best_metric": None,
        "config": template_config,
        "stage": payload.get("stage", "joint"),
        "provenance": {
            **(payload.get("provenance") or {}),
            "migrated_from": str(args.parent_checkpoint).replace("\\", "/"),
            "migration": "v2->v3",
            "v3_screening_row": template_config.get("provenance", {}).get("v3_screening_row"),
        },
        "architecture_version": "cbsc-zdc-v3",
        "experiment_contract_sha256": None,
        "critic_state": None,
        "critic_optimizer_state": None,
        "critic_scheduler_state": None,
        "gradient_ratio_controller_state": None,
        "replay_state_manifest": None,
        "critic_update_count": 0,
        "generator_update_count": 0,
        "role_partition_sha256": None,
        "response_envelope_sha256": template_config.get("model", {}).get("response_envelope_sha256"),
        "support_temperature": template_config.get("model", {}).get("support_temperature", 1.0),
    }
    args.checkpoint_output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(out, args.checkpoint_output)

    # Now the checkpoint exists, point the template at it and freeze. Without
    # this the row trains from random initialization and the migration is dead
    # work -- the run would answer "can 24 epochs from scratch beat a converged
    # model" instead of "does this feature help, starting from the parent".
    relative = args.checkpoint_relative or args.checkpoint_output.name
    template_config.setdefault("training", {})["initialize_from_relative"] = str(relative)
    template_config["training"]["initialize_from_sha256"] = sha256_file(args.checkpoint_output)
    args.template.write_text(
        yaml.safe_dump(template_config, sort_keys=False), encoding="utf-8", newline="\n"
    )
    freeze(args.template, template_config, args.frozen_output)
    frozen = yaml.safe_load(args.frozen_output.read_text(encoding="utf-8"))
    if not frozen.get("training", {}).get("initialize_from_relative"):
        raise SystemExit("the frozen config lost its initialize_from pointer")
    # The checkpoint is deliberately NOT rewritten here. Re-saving it would
    # change its bytes after its hash had already been stamped into the config,
    # so preflight would reject the very file the config points at.
    recorded = frozen["training"]["initialize_from_sha256"]
    actual = sha256_file(args.checkpoint_output)
    if recorded != actual:
        raise SystemExit(
            f"initialize_from_sha256 {recorded} does not match the checkpoint on disk {actual}"
        )

    report.update({
        "schema_version": 1,
        "kind": "cbsc-zdc-v3-screening-run-preparation",
        "row": template_config.get("provenance", {}).get("v3_screening_row"),
        "declared_change": template_config.get("provenance", {}).get("v3_declared_change"),
        "features_enabled": template_config.get("provenance", {}).get("v3_features_enabled"),
        "template": str(args.template).replace("\\", "/"),
        "template_sha256": sha256_file(args.template),
        "frozen_config": str(args.frozen_output).replace("\\", "/"),
        "frozen_sha256": sha256_file(args.frozen_output),
        "parent_checkpoint": str(args.parent_checkpoint).replace("\\", "/"),
        "parent_checkpoint_sha256": sha256_file(args.parent_checkpoint),
        "initial_checkpoint": str(args.checkpoint_output).replace("\\", "/"),
        "initial_checkpoint_sha256": sha256_file(args.checkpoint_output),
        "loss_weights": frozen.get("loss_weights"),
        "migrated_state_loads_cleanly": True,
        "initialize_from_relative": frozen["training"]["initialize_from_relative"],
        "initialize_from_sha256": frozen["training"]["initialize_from_sha256"],
    })
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: v for k, v in report.items() if k not in ("copied", "expanded", "initialized")}, indent=2))
    print(f"copied {report['counts']['copied']}, expanded {report['counts']['expanded']}, "
          f"initialized {report['counts']['initialized']}, unexpected {report['counts']['unexpected']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
