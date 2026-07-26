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
    if not name or not path:
        raise ValueError("--frozen must be NAME=PATH")
    return name, Path(path)


def verify(manifest_path: Path, frozen_specs: list[tuple[str, Path]]) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["pass"] is True
    assert int(manifest["variant_count"]) == 5
    assert int(manifest["parallel_wave_limit"]) == 5
    assert int(manifest["test_events_used"]) == 0
    variants = {row["name"]: row for row in manifest["variants"]}
    frozen = dict(frozen_specs)
    assert len(frozen) == len(frozen_specs) == 5
    assert set(frozen) == set(variants)

    rows = []
    common_provenance: dict[str, str] | None = None
    for name in sorted(variants):
        specification = variants[name]
        path = frozen[name]
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
        training = config["training"]
        visualization = config["evaluation"]["visualization"]
        assert config["data"]["manifest"] != "UNFROZEN"
        assert config["data"]["splits"] != "UNFROZEN"
        assert config["geometry"]["path"] != "UNFROZEN"
        assert training["stage"] == "joint"
        assert int(training["seed"]) == 20260723
        assert training["device"] == "cuda"
        assert training["amp"] is False
        assert int(training["epochs"]) == 1
        assert int(training["checkpoint_interval_updates"]) == 50
        assert int(training["early_stopping_patience"]) == 1
        assert training["initialize_from"] is None
        assert training["initialize_from_relative"] == "checkpoints/joint_best.pt"
        assert (
            training["initialize_from_sha256"] == manifest["checkpoint_sha256"]
        )
        assert training["resume_from"] is None
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
        assert int(training["batch_size"]) * int(
            training["gradient_accumulation"]
        ) == int(specification["effective_batch"])
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
        assert set(config["loss_weights"]) == set(specification["loss_weights"])
        for component, expected in specification["loss_weights"].items():
            assert math.isclose(
                float(config["loss_weights"][component]),
                float(expected),
                rel_tol=0,
                abs_tol=0,
            )

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
                "learning_rate": float(training["learning_rate"]),
                "batch_size": int(training["batch_size"]),
                "gradient_accumulation": int(
                    training["gradient_accumulation"]
                ),
                "effective_batch": int(training["batch_size"])
                * int(training["gradient_accumulation"]),
                "weight_source": config["viability"]["weight_source"],
            }
        )

    return {
        "pass": True,
        "matrix_manifest_sha256": _sha256(manifest_path),
        "checkpoint_sha256": manifest["checkpoint_sha256"],
        "variant_count": len(rows),
        "common_provenance": common_provenance,
        "variants": rows,
        "test_events_used": 0,
        "scientific_status": "frozen A100 viability wave; no job submitted",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--frozen", action="append", default=[], required=True)
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
