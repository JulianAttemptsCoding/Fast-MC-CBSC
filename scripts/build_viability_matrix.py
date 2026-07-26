from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import yaml


COMPONENTS = {
    "visible",
    "response",
    "first_layer",
    "active",
    "profile_flow",
    "count",
    "support_bce",
    "support_rank",
    "share_flow",
}
EXPECTED_STAGES = ("response", "profile", "count", "support", "share")
VARIANTS = (
    {
        "name": "default_control",
        "weights": "default",
        "learning_rate": 1e-4,
        "batch_size": 6,
        "gradient_accumulation": 4,
    },
    {
        "name": "calibrated_lr3e5",
        "weights": "calibrated",
        "learning_rate": 3e-5,
        "batch_size": 6,
        "gradient_accumulation": 4,
    },
    {
        "name": "calibrated_lr1e4",
        "weights": "calibrated",
        "learning_rate": 1e-4,
        "batch_size": 6,
        "gradient_accumulation": 4,
    },
    {
        "name": "calibrated_lr3e4",
        "weights": "calibrated",
        "learning_rate": 3e-4,
        "batch_size": 6,
        "gradient_accumulation": 4,
    },
    {
        "name": "calibrated_lr1e4_halfbatch",
        "weights": "calibrated",
        "learning_rate": 1e-4,
        "batch_size": 3,
        "gradient_accumulation": 4,
    },
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_yaml(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        yaml.safe_dump(value, sort_keys=False),
        encoding="utf-8",
    )
    temporary.replace(path)


def _write_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _accepted_weights(report: dict[str, Any]) -> dict[str, float]:
    if report.get("pass") is not True:
        raise ValueError("calibration report did not pass")
    if report.get("scientific_status") != (
        "train-only proposal; not validation selection"
    ):
        raise ValueError("unexpected calibration scientific status")
    if report.get("split") != "train" or int(report.get("test_events_used", -1)) != 0:
        raise ValueError("calibration must be train-only with zero test events")
    if (
        int(report.get("batches_consumed", -1)) != 64
        or int(report.get("max_batches", -1)) != 64
    ):
        raise ValueError("calibration must contain exactly 64 accepted batches")
    if report.get("memory_bounded_loss_groups") != list(EXPECTED_STAGES):
        raise ValueError("calibration loss-group order mismatch")
    if set(report.get("measured_components", [])) != COMPONENTS:
        raise ValueError("calibration component set mismatch")
    if report.get("gradient_norm_observations") != {
        name: 64 for name in COMPONENTS
    }:
        raise ValueError("calibration observation-count mismatch")
    weights = {
        name: float(value) for name, value in report.get("weights", {}).items()
    }
    if set(weights) != COMPONENTS:
        raise ValueError("calibration weight set mismatch")
    if not all(math.isfinite(value) and value > 0 for value in weights.values()):
        raise ValueError("calibration contains invalid weights")
    if not math.isclose(
        sum(weights.values()) / len(weights),
        1.0,
        rel_tol=0,
        abs_tol=1e-12,
    ):
        raise ValueError("calibration weights are not normalized to mean one")
    return weights


def generate_matrix(
    base_template: Path,
    calibration_report: Path,
    checkpoint_sha256: str,
    output_dir: Path,
) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite matrix directory: {output_dir}")
    if (
        len(checkpoint_sha256) != 64
        or any(character not in "0123456789abcdef" for character in checkpoint_sha256)
    ):
        raise ValueError("checkpoint SHA-256 must be lowercase hexadecimal")
    base = yaml.safe_load(base_template.read_text(encoding="utf-8"))
    report = json.loads(calibration_report.read_text(encoding="utf-8"))
    calibrated = _accepted_weights(report)
    default_weights = {
        name: float(value) for name, value in base["loss_weights"].items()
    }
    if set(default_weights) != COMPONENTS:
        raise ValueError("base-template loss set mismatch")
    training = base["training"]
    if training.get("stage") != "joint":
        raise ValueError("viability base template must be joint stage")
    if bool(training.get("amp", True)):
        raise ValueError("viability base template must use FP32")
    if int(training.get("seed", -1)) != 20260723:
        raise ValueError("viability screening seed must be 20260723")
    if base["data"].get("train_kinetic_gev") != [0.0, 300.0]:
        raise ValueError("viability training domain must be 0-300 GeV")
    if base["data"].get("evaluation_kinetic_gev") != [50.0, 250.0]:
        raise ValueError("viability validation domain must be 50-250 GeV")
    visualization = base["evaluation"].get("visualization", {})
    if (
        visualization.get("split") != "validation"
        or int(visualization.get("sample_count", -1)) != 50
        or int(visualization.get("draws_per_condition", -1)) != 5
        or visualization.get("required") is not True
    ):
        raise ValueError("viability visualization contract mismatch")

    output_dir.mkdir(parents=True)
    manifest_variants = []
    for specification in VARIANTS:
        variant = copy.deepcopy(base)
        name = str(specification["name"])
        selected_weights = (
            calibrated
            if specification["weights"] == "calibrated"
            else default_weights
        )
        variant["project"]["name"] = f"cbsc-zdc-v2-2-viability-{name}"
        variant["project"]["run_dir"] = f"runs/viability_{name}"
        variant["training"]["epochs"] = 1
        variant["training"]["early_stopping_patience"] = 1
        variant["training"]["checkpoint_interval_updates"] = 50
        variant["training"]["initialize_from"] = None
        variant["training"]["initialize_from_relative"] = (
            "checkpoints/joint_best.pt"
        )
        variant["training"]["initialize_from_sha256"] = checkpoint_sha256
        variant["training"]["resume_from"] = None
        variant["training"]["train_condition_encoder"] = True
        variant["training"]["learning_rate"] = float(
            specification["learning_rate"]
        )
        variant["training"]["batch_size"] = int(specification["batch_size"])
        variant["training"]["gradient_accumulation"] = int(
            specification["gradient_accumulation"]
        )
        variant["loss_weights"] = dict(selected_weights)
        variant["viability"] = {
            "screening_only": True,
            "selection_split": "validation",
            "test_events_used": 0,
            "weight_source": specification["weights"],
            "baseline_calibration_report_sha256": _sha256(calibration_report),
            "baseline_checkpoint_sha256": checkpoint_sha256,
            "successive_halving_wave": 1,
            "max_parallel_jobs": 5,
        }
        path = output_dir / f"{name}.yaml"
        _write_yaml(path, variant)
        manifest_variants.append(
            {
                **specification,
                "effective_batch": int(specification["batch_size"])
                * int(specification["gradient_accumulation"]),
                "template": path.name,
                "template_sha256": _sha256(path),
                "loss_weights": dict(selected_weights),
            }
        )

    manifest = {
        "pass": True,
        "scientific_status": (
            "unfrozen A100 viability wave; no job submitted"
        ),
        "base_template": str(base_template),
        "base_template_sha256": _sha256(base_template),
        "calibration_report": str(calibration_report),
        "calibration_report_sha256": _sha256(calibration_report),
        "checkpoint_sha256": checkpoint_sha256,
        "variant_count": len(manifest_variants),
        "parallel_wave_limit": 5,
        "estimated_epoch_poll_seconds": 4200,
        "test_events_used": 0,
        "variants": manifest_variants,
    }
    _write_json(output_dir / "matrix_manifest.json", manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-template", type=Path, required=True)
    parser.add_argument("--calibration-report", type=Path, required=True)
    parser.add_argument("--checkpoint-sha256", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = generate_matrix(
        args.base_template,
        args.calibration_report,
        args.checkpoint_sha256,
        args.output_dir,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
