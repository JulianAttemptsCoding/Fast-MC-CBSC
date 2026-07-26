from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

from .utils import load_yaml, sha256_file


REQUIRED_TOP_LEVEL = {"project", "data", "geometry", "model", "training", "loss_weights", "evaluation"}
EXPECTED_LOSS_WEIGHTS = {
    "visible", "response", "first_layer", "active", "profile_flow",
    "count", "support_bce", "support_rank", "share_flow",
}
ALLOWED_STAGES = {"response", "profile", "count", "support", "share", "joint"}
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def validate_config(config: dict[str, Any]) -> None:
    missing = REQUIRED_TOP_LEVEL - set(config)
    if missing:
        raise ValueError(f"configuration missing top-level sections: {sorted(missing)}")
    target_mode = config["data"].get("target_mode")
    if target_mode not in {"raw_deposit", "thresholded_readout"}:
        raise ValueError("data.target_mode must be raw_deposit or thresholded_readout")
    if target_mode == "raw_deposit" and float(config["data"].get("threshold_gev", 0.0)) != 0:
        raise ValueError("raw_deposit mode requires threshold_gev=0")
    split = config["data"].get("split_fraction", [0.8, 0.1, 0.1])
    if len(split) != 3 or abs(sum(float(x) for x in split) - 1.0) > 1e-8:
        raise ValueError("data.split_fraction must contain train/validation/test fractions summing to 1")
    if int(config["geometry"].get("n_nodes", 6790)) <= 0:
        raise ValueError("geometry.n_nodes must be positive")
    if int(config["geometry"].get("n_layers", 65)) <= 0:
        raise ValueError("geometry.n_layers must be positive")
    stage = str(config["training"].get("stage", "joint"))
    if stage not in ALLOWED_STAGES:
        raise ValueError(f"training.stage must be one of {sorted(ALLOWED_STAGES)}")
    for field in ("batch_size", "gradient_accumulation", "epochs"):
        if int(config["training"].get(field, 0)) <= 0:
            raise ValueError(f"training.{field} must be positive")
    train_range = config["data"].get("train_kinetic_gev")
    eval_range = config["data"].get("evaluation_kinetic_gev")
    for name, value in (("train_kinetic_gev", train_range), ("evaluation_kinetic_gev", eval_range)):
        if not isinstance(value, list) or len(value) != 2 or float(value[0]) > float(value[1]):
            raise ValueError(f"data.{name} must be [low, high] with low <= high")
    loss_names = set(config["loss_weights"])
    if loss_names != EXPECTED_LOSS_WEIGHTS:
        missing = sorted(EXPECTED_LOSS_WEIGHTS - loss_names)
        extra = sorted(loss_names - EXPECTED_LOSS_WEIGHTS)
        raise ValueError(f"loss_weights keys mismatch: missing={missing}, extra={extra}")
    for name, value in config["loss_weights"].items():
        if float(value) < 0:
            raise ValueError(f"loss weight {name} must be nonnegative")
    training = config["training"]
    for checkpoint_field in (
        "initialize_from",
        "resume_from",
        "resume_progress_from",
        "resume_best_from",
    ):
        relative_field = f"{checkpoint_field}_relative"
        hash_field = f"{checkpoint_field}_sha256"
        relative = training.get(relative_field)
        expected_hash = training.get(hash_field)
        if relative is not None:
            relative_path = Path(str(relative))
            if relative_path.is_absolute() or ".." in relative_path.parts:
                raise ValueError(
                    f"training.{relative_field} must be a safe relative path"
                )
            if not isinstance(expected_hash, str) or not SHA256_PATTERN.fullmatch(
                expected_hash
            ):
                raise ValueError(
                    f"training.{hash_field} must be a lowercase SHA-256 when "
                    f"training.{relative_field} is set"
                )
        elif expected_hash is not None:
            raise ValueError(
                f"training.{hash_field} requires training.{relative_field}"
            )
    has_initialize = any(
        training.get(field) is not None
        for field in ("initialize_from", "initialize_from_relative")
    )
    has_resume = any(
        training.get(field) is not None
        for field in ("resume_from", "resume_from_relative")
    )
    has_resume_progress = any(
        training.get(field) is not None
        for field in ("resume_progress_from", "resume_progress_from_relative")
    )
    has_resume_best = any(
        training.get(field) is not None
        for field in ("resume_best_from", "resume_best_from_relative")
    )
    if has_resume and has_resume_progress:
        raise ValueError(
            "training cannot use resume_from and resume_progress_from together"
        )
    if has_initialize and (has_resume or has_resume_progress):
        raise ValueError(
            "training cannot initialize_from and a resume checkpoint together"
        )
    if has_resume and not has_resume_best:
        raise ValueError(
            "training.resume_from and training.resume_best_from must be paired"
        )
    if has_resume_best and not (has_resume or has_resume_progress):
        raise ValueError(
            "training.resume_best_from requires a resume checkpoint"
        )
    checkpoint_interval = int(training.get("checkpoint_interval_updates", 0))
    if checkpoint_interval < 0:
        raise ValueError(
            "training.checkpoint_interval_updates must be nonnegative"
        )
    visualization = config.get("evaluation", {}).get("visualization")
    if visualization is not None:
        if not isinstance(visualization, dict):
            raise ValueError("evaluation.visualization must be a mapping")
        if visualization.get("split", "validation") != "validation":
            raise ValueError(
                "evaluation.visualization.split must be validation; test is forbidden"
            )
        sample_count = int(visualization.get("sample_count", 50))
        draws = int(visualization.get("draws_per_condition", 5))
        if not 1 <= sample_count <= 200:
            raise ValueError(
                "evaluation.visualization.sample_count must be between 1 and 200"
            )
        if not 1 <= draws <= 10:
            raise ValueError(
                "evaluation.visualization.draws_per_condition must be between 1 and 10"
            )


def load_config(path: str | Path) -> dict[str, Any]:
    config = load_yaml(path)
    validate_config(config)
    config.setdefault("provenance", {})
    config["provenance"]["config_path"] = str(Path(path).resolve())
    config["provenance"]["config_sha256"] = sha256_file(path)
    return config


@dataclass(frozen=True)
class RunPaths:
    root: Path

    @property
    def checkpoints(self) -> Path:
        return self.root / "checkpoints"

    @property
    def logs(self) -> Path:
        return self.root / "logs"

    @property
    def reports(self) -> Path:
        return self.root / "reports"

    def create(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.checkpoints.mkdir(exist_ok=True)
        self.logs.mkdir(exist_ok=True)
        self.reports.mkdir(exist_ok=True)
