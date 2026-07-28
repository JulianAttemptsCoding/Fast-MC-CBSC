from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
EXPECTED_VARIANTS = {
    "calibrated_lr3e5",
    "calibrated_lr1e4",
    "calibrated_lr3e4",
    "calibrated_lr1e4_halfbatch",
}


@dataclass(frozen=True)
class Variant:
    name: str
    template: Path
    parent_epoch: int
    best_sha256: str
    last_sha256: str
    parent_output_uri: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_variant(value: str) -> Variant:
    fields = value.split("|")
    if len(fields) != 6:
        raise ValueError(
            "--variant must be "
            "NAME|TEMPLATE|PARENT_EPOCH|BEST_SHA256|LAST_SHA256|PARENT_GS_URI"
        )
    name, template, parent_epoch, best_sha, last_sha, parent_uri = fields
    return Variant(
        name=name,
        template=Path(template),
        parent_epoch=int(parent_epoch),
        best_sha256=best_sha,
        last_sha256=last_sha,
        parent_output_uri=parent_uri.rstrip("/"),
    )


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


def build(
    variants: list[Variant],
    output_dir: Path,
    round_id: str,
    expected_variants: set[str] | None = None,
) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(
            f"refusing to overwrite compute-extension directory: {output_dir}"
        )
    expected = expected_variants or EXPECTED_VARIANTS
    if not expected or not expected.issubset(EXPECTED_VARIANTS):
        raise ValueError("expected variants must be a nonempty calibrated subset")
    if {variant.name for variant in variants} != expected:
        raise ValueError(
            "compute extension variants do not match the declared calibrated subset"
        )
    if len(variants) != len(expected):
        raise ValueError("duplicate compute-extension variant")
    if not round_id or not re.fullmatch(r"[a-z0-9-]+", round_id):
        raise ValueError("round ID must contain only lowercase letters, digits, hyphens")

    output_dir.mkdir(parents=True)
    rows = []
    for variant in sorted(variants, key=lambda item: item.name):
        if variant.parent_epoch < 0:
            raise ValueError("parent epoch must be nonnegative")
        if not SHA256_PATTERN.fullmatch(variant.best_sha256):
            raise ValueError(f"invalid best SHA-256 for {variant.name}")
        if not SHA256_PATTERN.fullmatch(variant.last_sha256):
            raise ValueError(f"invalid last SHA-256 for {variant.name}")
        if not variant.parent_output_uri.startswith("gs://"):
            raise ValueError(f"parent output must be a gs:// URI for {variant.name}")

        config = yaml.safe_load(variant.template.read_text(encoding="utf-8"))
        training = config["training"]
        viability = config["viability"]
        if training["stage"] != "joint":
            raise ValueError(f"{variant.name} is not a joint-stage template")
        if training["amp"] is not False:
            raise ValueError(f"{variant.name} is not FP32")
        if int(training["epochs"]) != variant.parent_epoch + 1:
            raise ValueError(
                f"{variant.name} template epochs do not match parent epoch"
            )
        if viability["weight_source"] != "calibrated":
            raise ValueError(f"{variant.name} is not calibrated")
        if int(viability["test_events_used"]) != 0:
            raise ValueError(f"{variant.name} used test data")

        extension = copy.deepcopy(config)
        extension["project"]["name"] += f"-{round_id}"
        extension["project"]["run_dir"] += f"_{round_id.replace('-', '_')}"
        training = extension["training"]
        training["epochs"] = variant.parent_epoch + 3
        training["early_stopping_patience"] = 3
        training["checkpoint_interval_updates"] = 50
        for field in (
            "initialize_from",
            "initialize_from_relative",
            "initialize_from_sha256",
            "resume_from",
            "resume_from_relative",
            "resume_from_sha256",
            "resume_progress_from",
            "resume_progress_from_relative",
            "resume_progress_from_sha256",
            "resume_best_from",
            "resume_best_from_relative",
            "resume_best_from_sha256",
        ):
            training[field] = None
        training["resume_from_relative"] = (
            f"checkpoints/{variant.name}_last_epoch{variant.parent_epoch}.pt"
        )
        training["resume_from_sha256"] = variant.last_sha256
        training["resume_best_from_relative"] = (
            f"checkpoints/{variant.name}_best_epoch{variant.parent_epoch}.pt"
        )
        training["resume_best_from_sha256"] = variant.best_sha256
        training["restart_scheduler_on_resume"] = True

        extension["viability"].update(
            {
                "compute_extension_round": round_id,
                "continuation_epochs": 2,
                "parent_epoch": variant.parent_epoch,
                "parent_output_uri": variant.parent_output_uri,
                "parent_template_sha256": _sha256(variant.template),
                "historical_hardware_screening_is_nonbinding": True,
                "selection_split": "validation",
                "test_events_used": 0,
                "scheduler_contract": (
                    "preserve model/optimizer/scaler/RNG and paired historical "
                    "best; restart exhausted cosine over exactly two new epochs"
                ),
            }
        )

        output_path = output_dir / f"{variant.name}_{round_id}.yaml"
        _write_yaml(output_path, extension)
        rows.append(
            {
                "name": variant.name,
                "template": output_path.name,
                "template_sha256": _sha256(output_path),
                "source_template": str(variant.template),
                "source_template_sha256": _sha256(variant.template),
                "parent_epoch": variant.parent_epoch,
                "start_epoch": variant.parent_epoch + 1,
                "stop_before_epoch": variant.parent_epoch + 3,
                "best_checkpoint_sha256": variant.best_sha256,
                "last_checkpoint_sha256": variant.last_sha256,
                "parent_output_uri": variant.parent_output_uri,
                "learning_rate": float(training["learning_rate"]),
                "batch_size": int(training["batch_size"]),
                "gradient_accumulation": int(
                    training["gradient_accumulation"]
                ),
                "test_events_used": 0,
            }
        )

    manifest = {
        "pass": True,
        "round_id": round_id,
        "scientific_status": (
            "user-authorized validation-only compute extension; "
            "hardware screening is nonbinding QA evidence"
        ),
        "variant_count": len(rows),
        "variants": rows,
        "test_events_used": 0,
    }
    _write_json(output_dir / "extension_manifest.json", manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--round-id", required=True)
    parser.add_argument(
        "--expected-variant",
        action="append",
        choices=sorted(EXPECTED_VARIANTS),
        help=(
            "declare the exact calibrated subset for this round; omit to "
            "retain the four-family protocol"
        ),
    )
    args = parser.parse_args()
    report = build(
        [_parse_variant(value) for value in args.variant],
        args.output_dir,
        args.round_id,
        set(args.expected_variant) if args.expected_variant else None,
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
