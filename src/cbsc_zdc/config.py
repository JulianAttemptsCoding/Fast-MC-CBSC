from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import re
from typing import Any

from .utils import load_yaml, sha256_file


REQUIRED_TOP_LEVEL = {"project", "data", "geometry", "model", "training", "loss_weights", "evaluation"}

# The v2.2 loss schema is frozen.  Every historical frozen configuration is
# validated against exactly this set; widening it would silently change what
# those configs mean.
EXPECTED_LOSS_WEIGHTS = {
    "visible", "response", "first_layer", "active", "profile_flow",
    "count", "support_bce", "support_rank", "share_flow",
}

ARCHITECTURE_V2_2 = "cbsc-zdc-v2.2"
ARCHITECTURE_V3 = "cbsc-zdc-v3"

# v3 keeps every v2.2 component and adds the hierarchical first-layer and
# span/gap activity heads.  ``first_layer`` and ``active`` remain because the
# autoregressive activity mode and the v2 first-layer categorical still use
# them; the added keys are inert when their mode is not selected.
V3_LOSS_WEIGHTS = EXPECTED_LOSS_WEIGHTS | {
    "ecal_start", "hcal_first", "active_last", "active_gap",
}

ARCHITECTURE_LOSS_WEIGHTS = {
    ARCHITECTURE_V2_2: EXPECTED_LOSS_WEIGHTS,
    ARCHITECTURE_V3: V3_LOSS_WEIGHTS,
}

ALLOWED_ACTIVITY_MODES = {"span_gaps", "autoregressive"}
ALLOWED_STAGES = {"response", "profile", "count", "support", "share", "joint"}
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def architecture_version(config: dict[str, Any]) -> str:
    """Return the declared architecture version.

    Absence of ``model.architecture_version`` means ``cbsc-zdc-v2.2``.  No
    existing frozen YAML is reinterpreted.
    """
    return str(config.get("model", {}).get("architecture_version", ARCHITECTURE_V2_2))


def expected_loss_weights(version: str, model: dict[str, Any] | None = None) -> set[str]:
    """Loss-weight keys required by this architecture and feature selection.

    Under v3 the added keys are required only when the head that produces them
    is actually selected.  A screening row that leaves a feature at ``v2`` keeps
    exactly the v2.2 schema, so its weights cannot silently carry a term that is
    never computed -- and the full v3 set is only demanded once every head is on.
    """
    try:
        base = ARCHITECTURE_LOSS_WEIGHTS[version]
    except KeyError:
        raise ValueError(
            f"model.architecture_version must be one of "
            f"{sorted(ARCHITECTURE_LOSS_WEIGHTS)}, got {version!r}"
        ) from None
    if version != ARCHITECTURE_V3 or model is None:
        return base
    required = set(EXPECTED_LOSS_WEIGHTS)
    if str(model.get("first_layer_mode", "v2")) == "hierarchical":
        required |= {"ecal_start", "hcal_first"}
    if str(model.get("activity_head_mode", "v2")) != "v2":
        required |= {"active_last", "active_gap"}
    return required


ALLOWED_FEATURE_MODES = {
    "response_mode": {"v2", "spline"},
    "first_layer_mode": {"v2", "hierarchical"},
    "count_mode": {"v2", "autoregressive"},
    "activity_head_mode": {"v2", "span_gaps", "autoregressive"},
}


def _validate_v3_model(model: dict[str, Any]) -> None:
    temperature = model.get("support_temperature", 1.0)
    try:
        temperature = float(temperature)
    except (TypeError, ValueError):
        raise ValueError("model.support_temperature must be a finite positive float") from None
    if not math.isfinite(temperature) or temperature <= 0:
        raise ValueError("model.support_temperature must be a finite positive float")
    mode = str(model.get("activity_mode", "span_gaps"))
    if mode not in ALLOWED_ACTIVITY_MODES:
        raise ValueError(
            f"model.activity_mode must be one of {sorted(ALLOWED_ACTIVITY_MODES)}, got {mode!r}"
        )
    for field, allowed in ALLOWED_FEATURE_MODES.items():
        value = str(model.get(field, "v2"))
        if value not in allowed:
            raise ValueError(f"model.{field} must be one of {sorted(allowed)}, got {value!r}")
    if str(model.get("response_mode", "v2")) == "spline":
        caps = model.get("response_envelope_caps_gev")
        if not caps:
            raise ValueError(
                "model.response_mode: spline requires model.response_envelope_caps_gev "
                "from the train-only envelope"
            )


def validate_config(config: dict[str, Any]) -> None:
    missing = REQUIRED_TOP_LEVEL - set(config)
    if missing:
        raise ValueError(f"configuration missing top-level sections: {sorted(missing)}")
    version = architecture_version(config)
    required_losses = expected_loss_weights(version, config.get("model"))
    if version == ARCHITECTURE_V3:
        _validate_v3_model(config["model"])
    else:
        stray = [f for f in ALLOWED_FEATURE_MODES
                 if str(config["model"].get(f, "v2")) != "v2"]
        if stray:
            raise ValueError(
                f"v3 feature modes {sorted(stray)} require "
                f"model.architecture_version: {ARCHITECTURE_V3}"
            )
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
    if loss_names != required_losses:
        missing = sorted(required_losses - loss_names)
        extra = sorted(loss_names - required_losses)
        raise ValueError(
            f"loss_weights keys mismatch for {version}: missing={missing}, extra={extra}"
        )
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
    restart_scheduler = training.get("restart_scheduler_on_resume", False)
    if not isinstance(restart_scheduler, bool):
        raise ValueError(
            "training.restart_scheduler_on_resume must be boolean"
        )
    if restart_scheduler and not has_resume:
        raise ValueError(
            "training.restart_scheduler_on_resume requires resume_from"
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
