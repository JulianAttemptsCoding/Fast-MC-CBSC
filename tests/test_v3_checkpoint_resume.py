"""Checkpoint format v4: new required fields, and v2/v3 loader compatibility.

Format 4 carries the critic, replay and controller state that a v3 adversarial
run needs for exact resume.  Every field is nullable so a supervised v3 run and
a migrated v2 run both round-trip, but a *present* critic state may never be
paired with a generator or replay state bearing a different contract hash.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import torch
from torch import nn

from cbsc_zdc.training.checkpoint import (
    CHECKPOINT_FORMAT_V3,
    CHECKPOINT_FORMAT_V4,
    V4_REQUIRED_FIELDS,
    load_checkpoint,
    save_checkpoint,
)


class Tiny(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.linear = nn.Linear(3, 2)

    def forward(self, x: torch.Tensor) -> torch.Tensor:  # pragma: no cover - unused
        return self.linear(x)


def save(tmp_path: Path, **kwargs) -> Path:
    model = Tiny()
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    path = tmp_path / "ckpt.pt"
    save_checkpoint(
        path, model, optimizer, None, None,
        epoch=1, best_metric=0.5, config={"model": {}}, stage="joint",
        provenance={"seed": 1}, **kwargs,
    )
    return path


def test_format4_contains_every_required_field(tmp_path: Path) -> None:
    path = save(tmp_path, architecture_version="cbsc-zdc-v3", experiment_contract_sha256="a" * 64)
    payload = torch.load(path, map_location="cpu", weights_only=False)
    assert payload["format_version"] == CHECKPOINT_FORMAT_V4
    for field in V4_REQUIRED_FIELDS:
        assert field in payload, field


def test_a_supervised_v3_checkpoint_leaves_critic_fields_null(tmp_path: Path) -> None:
    path = save(tmp_path, architecture_version="cbsc-zdc-v3", experiment_contract_sha256="b" * 64)
    payload = torch.load(path, map_location="cpu", weights_only=False)
    for field in (
        "critic_state", "critic_optimizer_state", "critic_scheduler_state",
        "gradient_ratio_controller_state", "replay_state_manifest",
    ):
        assert payload[field] is None
    assert payload["critic_update_count"] == 0
    assert payload["generator_update_count"] == 0


def test_omitting_architecture_version_writes_a_v2_compatible_format3(tmp_path: Path) -> None:
    # A v2.2 run must keep producing exactly what it produced before.
    path = save(tmp_path)
    payload = torch.load(path, map_location="cpu", weights_only=False)
    assert payload["format_version"] == CHECKPOINT_FORMAT_V3
    assert "critic_state" not in payload


def test_old_format_checkpoint_still_loads_on_v2_path(tmp_path: Path) -> None:
    path = save(tmp_path)
    model = Tiny()
    payload = load_checkpoint(path, model)
    assert payload["format_version"] == CHECKPOINT_FORMAT_V3
    assert payload["epoch"] == 1


def test_a_format4_checkpoint_loads_through_the_same_loader(tmp_path: Path) -> None:
    path = save(tmp_path, architecture_version="cbsc-zdc-v3", experiment_contract_sha256="c" * 64)
    model = Tiny()
    payload = load_checkpoint(path, model)
    assert payload["format_version"] == CHECKPOINT_FORMAT_V4
    assert payload["architecture_version"] == "cbsc-zdc-v3"


def test_mismatched_generator_critic_contract_hash_is_fatal(tmp_path: Path) -> None:
    path = save(
        tmp_path,
        architecture_version="cbsc-zdc-v3",
        experiment_contract_sha256="d" * 64,
        critic_state={"w": torch.zeros(1)},
    )
    model = Tiny()
    with pytest.raises(ValueError, match="experiment_contract_sha256"):
        load_checkpoint(path, model, expected_contract_sha256="e" * 64)


def test_a_matching_contract_hash_loads(tmp_path: Path) -> None:
    path = save(
        tmp_path,
        architecture_version="cbsc-zdc-v3",
        experiment_contract_sha256="d" * 64,
        critic_state={"w": torch.zeros(1)},
    )
    model = Tiny()
    payload = load_checkpoint(path, model, expected_contract_sha256="d" * 64)
    assert payload["critic_state"] is not None


def test_mismatched_replay_manifest_is_fatal(tmp_path: Path) -> None:
    path = save(
        tmp_path,
        architecture_version="cbsc-zdc-v3",
        experiment_contract_sha256="f" * 64,
        critic_state={"w": torch.zeros(1)},
        replay_state_manifest={"content_sha256": "1" * 64, "events": 8},
    )
    model = Tiny()
    with pytest.raises(ValueError, match="replay"):
        load_checkpoint(path, model, expected_replay_sha256="2" * 64)


def test_a_critic_state_without_a_contract_hash_is_rejected_at_save(tmp_path: Path) -> None:
    model = Tiny()
    with pytest.raises(ValueError, match="experiment_contract_sha256"):
        save_checkpoint(
            tmp_path / "bad.pt", model, None, None, None,
            epoch=0, best_metric=None, config={}, stage="joint", provenance={},
            architecture_version="cbsc-zdc-v3",
            critic_state={"w": torch.zeros(1)},
        )
