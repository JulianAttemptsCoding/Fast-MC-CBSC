from __future__ import annotations

from pathlib import Path

import pytest
import torch
import yaml

from scripts.build_compute_extensions import EXPECTED_VARIANTS, Variant, build
from scripts.verify_compute_extension_epoch_gcs import _finite_tensors


def _template(path: Path, *, parent_epoch: int, name: str) -> None:
    path.write_text(
        yaml.safe_dump(
            {
                "project": {"name": name, "run_dir": f"runs/{name}"},
                "training": {
                    "stage": "joint",
                    "epochs": parent_epoch + 1,
                    "amp": False,
                    "learning_rate": 1e-4,
                    "batch_size": 6,
                    "gradient_accumulation": 4,
                    "checkpoint_interval_updates": 50,
                    "initialize_from": None,
                    "initialize_from_relative": "checkpoints/source.pt",
                    "initialize_from_sha256": "c" * 64,
                    "resume_from": None,
                },
                "viability": {
                    "weight_source": "calibrated",
                    "test_events_used": 0,
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def _variants(tmp_path: Path) -> list[Variant]:
    variants = []
    for index, name in enumerate(sorted(EXPECTED_VARIANTS)):
        parent_epoch = 0 if index < 2 else 2
        template = tmp_path / f"{name}.yaml"
        _template(template, parent_epoch=parent_epoch, name=name)
        variants.append(
            Variant(
                name=name,
                template=template,
                parent_epoch=parent_epoch,
                best_sha256="a" * 64,
                last_sha256="b" * 64,
                parent_output_uri=f"gs://bucket/{name}",
            )
        )
    return variants


def test_builds_four_paired_two_epoch_extensions(tmp_path: Path) -> None:
    output = tmp_path / "output"
    manifest = build(_variants(tmp_path), output, "compute-extension-r1")

    assert manifest["pass"] is True
    assert manifest["variant_count"] == 4
    assert manifest["test_events_used"] == 0
    for row in manifest["variants"]:
        config = yaml.safe_load((output / row["template"]).read_text())
        training = config["training"]
        assert training["epochs"] == row["parent_epoch"] + 3
        assert training["resume_from_sha256"] == "b" * 64
        assert training["resume_best_from_sha256"] == "a" * 64
        assert training["restart_scheduler_on_resume"] is True
        assert training["initialize_from_relative"] is None
        assert config["viability"]["frozen_a100_decision_unchanged"] is True


def test_requires_all_four_calibrated_variants(tmp_path: Path) -> None:
    variants = _variants(tmp_path)
    with pytest.raises(ValueError, match="declared calibrated subset"):
        build(variants[:-1], tmp_path / "output", "compute-extension-r1")


def test_accepts_declared_calibrated_subset(tmp_path: Path) -> None:
    variants = [
        variant
        for variant in _variants(tmp_path)
        if variant.name in {"calibrated_lr3e5", "calibrated_lr1e4"}
    ]
    manifest = build(
        variants,
        tmp_path / "output",
        "compute-extension-r2",
        {"calibrated_lr3e5", "calibrated_lr1e4"},
    )
    assert manifest["variant_count"] == 2
    assert {row["name"] for row in manifest["variants"]} == {
        "calibrated_lr3e5",
        "calibrated_lr1e4",
    }


def test_rejects_mismatched_declared_subset(tmp_path: Path) -> None:
    variants = _variants(tmp_path)
    with pytest.raises(ValueError, match="declared calibrated subset"):
        build(
            variants[:2],
            tmp_path / "output",
            "compute-extension-r2",
            {"calibrated_lr3e5"},
        )


def test_stream_verifier_finds_nested_nonfinite_tensor() -> None:
    count, failures = _finite_tensors(
        {
            "model": {"finite": torch.tensor([1.0])},
            "optimizer": [{"bad": torch.tensor([float("nan")])}],
        }
    )
    assert count == 2
    assert failures == ["checkpoint.optimizer[0].bad"]
