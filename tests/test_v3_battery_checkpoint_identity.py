from __future__ import annotations

import pytest
import torch

from scripts.v3_battery_checkpoint_identity import identity


def test_identity_hashes_and_checks_the_embedded_epoch(tmp_path) -> None:
    checkpoint = tmp_path / "best.pt"
    config = tmp_path / "frozen.yaml"
    torch.save({"epoch": 7, "best_metric": 4.2}, checkpoint)
    config.write_text("schema_version: 1\n", encoding="utf-8")
    observed = identity(checkpoint, config, 7)
    assert observed["checkpoint_embedded_epoch"] == 7
    assert observed["checkpoint_best_metric"] == pytest.approx(4.2)
    assert len(observed["checkpoint_sha256"]) == 64
    assert len(observed["frozen_config_sha256"]) == 64
    with pytest.raises(ValueError, match="expected 8, embedded 7"):
        identity(checkpoint, config, 8)
