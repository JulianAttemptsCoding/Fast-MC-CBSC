from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import yaml


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_frozen(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise ValueError("--frozen must be NAME=PATH")
    name, path = value.split("=", 1)
    return name, Path(path)


def verify(
    manifest_path: Path,
    frozen_specs: list[tuple[str, Path]],
) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["pass"] is True
    assert int(manifest["variant_count"]) > 0
    assert int(manifest["test_events_used"]) == 0
    variants = {row["name"]: row for row in manifest["variants"]}
    frozen = dict(frozen_specs)
    assert len(frozen) == len(frozen_specs) == int(manifest["variant_count"])
    assert set(frozen) == set(variants)

    rows = []
    common_provenance: dict[str, str] | None = None
    for name in sorted(variants):
        specification = variants[name]
        path = frozen[name]
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
        training = config["training"]
        visualization = config["evaluation"]["visualization"]
        parent_epoch = int(specification["parent_epoch"])

        assert config["data"]["manifest"] != "UNFROZEN"
        assert config["data"]["splits"] != "UNFROZEN"
        assert config["geometry"]["path"] != "UNFROZEN"
        assert training["stage"] == "joint"
        assert int(training["seed"]) == 20260723
        assert training["device"] == "cuda"
        assert training["amp"] is False
        assert int(training["epochs"]) == parent_epoch + 3
        assert int(training["early_stopping_patience"]) == 3
        assert int(training["checkpoint_interval_updates"]) == 50
        assert training["initialize_from"] is None
        assert training["initialize_from_relative"] is None
        assert training["initialize_from_sha256"] is None
        assert training["resume_from"] is None
        assert training["resume_from_sha256"] == specification[
            "last_checkpoint_sha256"
        ]
        assert training["resume_best_from"] is None
        assert training["resume_best_from_sha256"] == specification[
            "best_checkpoint_sha256"
        ]
        assert training["restart_scheduler_on_resume"] is True
        assert training["train_condition_encoder"] is True
        assert math.isclose(
            float(training["learning_rate"]),
            float(specification["learning_rate"]),
            rel_tol=0,
            abs_tol=0,
        )
        assert int(training["batch_size"]) == int(specification["batch_size"])
        assert int(training["gradient_accumulation"]) == int(
            specification["gradient_accumulation"]
        )
        assert config["data"]["train_kinetic_gev"] == [0.0, 300.0]
        assert config["data"]["evaluation_kinetic_gev"] == [50.0, 250.0]
        assert visualization == {
            "enabled": True,
            "split": "validation",
            "sample_count": 50,
            "draws_per_condition": 5,
            "selection_seed": 20260725,
            "generation_seed": 20260725,
            "required": True,
        }
        viability = config["viability"]
        assert viability["weight_source"] == "calibrated"
        assert viability["compute_extension_round"] == manifest["round_id"]
        assert int(viability["continuation_epochs"]) == 2
        assert int(viability["parent_epoch"]) == parent_epoch
        assert viability["parent_output_uri"] == specification[
            "parent_output_uri"
        ]
        assert viability["historical_hardware_screening_is_nonbinding"] is True
        assert int(viability["test_events_used"]) == 0

        template = manifest_path.parent / specification["template"]
        assert _sha256(template) == specification["template_sha256"]
        assert config["provenance"]["template_sha256"] == _sha256(template)
        comparable = dict(config["provenance"])
        comparable.pop("template_sha256")
        common_provenance = common_provenance or comparable
        assert comparable == common_provenance
        rows.append(
            {
                "name": name,
                "frozen_path": str(path),
                "frozen_sha256": _sha256(path),
                "template_sha256": _sha256(template),
                "parent_epoch": parent_epoch,
                "start_epoch": parent_epoch + 1,
                "expected_terminal_epoch": parent_epoch + 2,
                "best_checkpoint_sha256": specification[
                    "best_checkpoint_sha256"
                ],
                "last_checkpoint_sha256": specification[
                    "last_checkpoint_sha256"
                ],
                "learning_rate": float(training["learning_rate"]),
                "batch_size": int(training["batch_size"]),
                "gradient_accumulation": int(
                    training["gradient_accumulation"]
                ),
            }
        )

    return {
        "pass": True,
        "manifest_sha256": _sha256(manifest_path),
        "variant_count": len(rows),
        "common_provenance": common_provenance,
        "variants": rows,
        "test_events_used": 0,
        "scientific_status": (
            "frozen validation-only compute extension; no job submitted"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--frozen", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = verify(
        args.manifest,
        [_parse_frozen(value) for value in args.frozen],
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(args.output)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
