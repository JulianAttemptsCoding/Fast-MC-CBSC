"""One-time audited v2 -> v3 checkpoint migration.

Every tensor key in the source checkpoint must be explicitly classified.  An
unclassified key is fatal: silently dropping one would produce a v3 model that
quietly lost a trained component, and silently copying one would tie v3 to a
v2 module whose meaning has changed.

Classification rules follow the specification:

============================================ =========================
module                                       rule
============================================ =========================
condition encoder                            exact copy
visibility subhead                           exact copy when shapes match
positive-response spline                     new initialization
profile flow                                 exact copy when shapes match
ECAL/HCAL first heads                        new initialization
activity span/gap or AR head                 new initialization
AR count head                                new initialization
support/share graph blocks, context, output  exact copy
expanded support/share input projection      copy old columns, zero the new
critic(s)                                    new initialization
============================================ =========================

The four new axis-feature columns are initialized to **zero** so a migrated
model reproduces its v2 parent's node logits exactly before any fine-tuning.
That makes the migration itself a no-op on behaviour, which is what lets a
later change be attributed to training rather than to the migration.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import torch

EXACT_COPY_PREFIXES = (
    "condition.",
    "response.visible.",
    "profile.flow.",
    "profile.first",
    "profile.active",
    "profile.layer_embedding",
    "support.blocks.",
    "support.context.",
    "support.output.",
    "share.blocks.",
    "share.context.",
    "share.output.",
    "share.time.",
    "support.time.",
)

# Replaced by a differently-parametrized v3 module; the v2 weights have no
# meaning under the new parametrization.
NEW_INIT_PREFIXES = (
    "response.mixture.",  # superseded by the bounded spline
    "counts.",            # superseded by the autoregressive count head
)

# Modules that exist only in v3.  They have no v2 counterpart, so they are
# always freshly initialized -- but they must still be *classified*, otherwise
# a target-only key would be silently skipped rather than reported.
V3_ONLY_PREFIXES = (
    "response.spline.",
    "first_layer.",
    "activity.",
    "counts_ar.",
    "critic.",
)

EXPANDED_PREFIXES = ("support.input.", "share.input.")

# Registered buffers holding the frozen detector geometry. They are not learned
# parameters, but they are in the state dict and must be classified rather than
# silently skipped. They are copied exactly, and a shape mismatch means the two
# checkpoints describe different detectors -- which is fatal, not reshapeable.
GEOMETRY_BUFFERS = (
    "node_features",
    "layer_index",
    "valid_mask",
    "edge_index",
    "edge_features",
    "max_counts",
    "cell_positions_mm",
    "generator_vertex_mm",
    "response_envelope_caps_gev",
)

AXIS_FEATURE_COLUMNS = 4


class MigrationError(ValueError):
    """Raised when a source key cannot be classified, or a rule cannot apply."""


def classify(key: str) -> str:
    if key in GEOMETRY_BUFFERS:
        return "geometry_buffer"
    if key.startswith(EXPANDED_PREFIXES) and key.endswith("weight") and ".0." in key:
        return "expanded"
    if key.startswith(EXACT_COPY_PREFIXES):
        return "exact_copy"
    if key.startswith(NEW_INIT_PREFIXES):
        return "new_init"
    if key.startswith(V3_ONLY_PREFIXES):
        return "new_init"
    if key.startswith(EXPANDED_PREFIXES):
        return "exact_copy"
    return "unclassified"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def migrate_state_dict(
    source: dict[str, torch.Tensor],
    target: dict[str, torch.Tensor],
    *,
    axis_columns: int = AXIS_FEATURE_COLUMNS,
) -> tuple[dict[str, torch.Tensor], dict[str, Any]]:
    """Return ``(migrated_state, report)``.

    ``target`` supplies the v3 shapes and the fresh initialization for modules
    that are not copied.
    """
    migrated = {k: v.clone() for k, v in target.items()}
    copied: list[dict[str, Any]] = []
    expanded: list[dict[str, Any]] = []
    initialized: list[str] = []
    missing: list[str] = []
    unexpected: list[str] = []

    for key, tensor in source.items():
        kind = classify(key)
        if kind == "unclassified":
            unexpected.append(key)
            continue
        if key not in target:
            missing.append(key)
            continue
        if kind == "new_init":
            initialized.append(key)
            continue
        destination = target[key]
        if kind == "geometry_buffer":
            if destination.shape != tensor.shape:
                raise MigrationError(
                    f"{key}: geometry buffer shape differs {tuple(tensor.shape)} -> "
                    f"{tuple(destination.shape)}; the checkpoints describe different detectors"
                )
            # Keep the target's own value: it was built from the frozen geometry
            # this run will actually use, and it is asserted identical in shape.
            copied.append({"key": key, "shape": list(tensor.shape), "kind": "geometry_buffer"})
            continue
        if kind == "exact_copy":
            if destination.shape != tensor.shape:
                # A shape change under an exact-copy rule means the module
                # changed meaning; refuse rather than reshape.
                raise MigrationError(
                    f"{key}: exact-copy rule but shapes differ "
                    f"{tuple(tensor.shape)} -> {tuple(destination.shape)}"
                )
            migrated[key] = tensor.clone()
            copied.append({"key": key, "shape": list(tensor.shape)})
            continue
        # expanded input projection: copy the old columns, zero the new ones
        if destination.shape[0] != tensor.shape[0]:
            raise MigrationError(
                f"{key}: expanded rule expects an unchanged output width, got "
                f"{destination.shape[0]} vs {tensor.shape[0]}"
            )
        old_columns = tensor.shape[1]
        if destination.shape[1] != old_columns + axis_columns:
            raise MigrationError(
                f"{key}: expected {old_columns + axis_columns} input columns, "
                f"target has {destination.shape[1]}"
            )
        block = torch.zeros_like(destination)
        block[:, :old_columns] = tensor
        migrated[key] = block
        expanded.append(
            {
                "key": key,
                "old_columns": old_columns,
                "new_columns": destination.shape[1],
                "zero_initialized_columns": axis_columns,
            }
        )

    for key in target:
        if key not in source and classify(key) != "unclassified":
            initialized.append(key)

    if unexpected:
        raise MigrationError(
            f"{len(unexpected)} source key(s) could not be classified: {unexpected[:5]}. "
            "Every key must be explicitly classified; extend the rules rather than "
            "dropping it."
        )

    report = {
        "copied": copied,
        "expanded": expanded,
        "initialized": sorted(set(initialized)),
        "missing_in_target": missing,
        "unexpected_in_source": unexpected,
        "axis_feature_columns": axis_columns,
        "counts": {
            "copied": len(copied),
            "expanded": len(expanded),
            "initialized": len(set(initialized)),
            "missing": len(missing),
            "unexpected": len(unexpected),
        },
    }
    return migrated, report


def migrate_checkpoint(
    source_path: Path, target_state: dict[str, torch.Tensor], output_path: Path, report_path: Path,
    *, architecture_version: str = "cbsc-zdc-v3", experiment_contract_sha256: str | None = None,
) -> dict[str, Any]:
    payload = torch.load(Path(source_path), map_location="cpu", weights_only=False)
    migrated, report = migrate_state_dict(payload["model_state"], target_state)
    out = {
        "format_version": 4,
        "model_state": migrated,
        "optimizer_state": None,
        "scheduler_state": None,
        "scaler_state": None,
        "epoch": 0,
        "best_metric": None,
        "config": payload.get("config"),
        "stage": payload.get("stage"),
        "provenance": {
            **(payload.get("provenance") or {}),
            "migrated_from": str(source_path),
            "migration": "v2->v3",
        },
        "architecture_version": architecture_version,
        "experiment_contract_sha256": experiment_contract_sha256,
        "critic_state": None,
        "critic_optimizer_state": None,
        "critic_scheduler_state": None,
        "gradient_ratio_controller_state": None,
        "replay_state_manifest": None,
        "critic_update_count": 0,
        "generator_update_count": 0,
        "role_partition_sha256": None,
        "response_envelope_sha256": None,
        "support_temperature": 1.0,
    }
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    torch.save(out, output_path)
    report.update(
        {
            "schema_version": 1,
            "kind": "cbsc-zdc-v2-to-v3-migration",
            "source_path": str(source_path),
            "source_sha256": sha256_file(source_path),
            "output_path": str(output_path),
            "output_sha256": sha256_file(output_path),
            "architecture_version": architecture_version,
        }
    )
    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    Path(report_path).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    return report
