from __future__ import annotations

import json
from pathlib import Path

from exhibition import build_metrics_catalog as catalog


ROOT = Path(__file__).resolve().parents[1]


def test_every_exhibition_graphic_decodes_or_parses() -> None:
    graphics = catalog.graphic_inventory()
    assert len(graphics) == 87
    assert all(row["bytes"] > 0 for row in graphics)


def test_manifests_and_accepted_metric_summaries_agree() -> None:
    manifest = catalog.verify_exhibition_manifest()
    metrics = catalog.current_metrics()
    assert len(manifest["visuals"]) == 23
    assert metrics["large_validation_diagnostics"]["run_tags"] == [
        "dicos-p9",
        "dicos-p10",
    ]
    assert metrics["large_validation_diagnostics"]["quarantined_epochs"] == [40]
    lr1e4 = metrics["families"]["calibrated_lr1e4"]
    assert lr1e4["latest_accepted_epoch"] == 39
    assert lr1e4["latest_observed_epoch"] == 40
    assert lr1e4["latest_observed_status"] == "quarantined"


def test_catalog_records_conservative_test_accounting() -> None:
    payload = json.loads(
        (ROOT / "exhibition" / "metrics_catalog.json").read_text(encoding="utf-8")
    )
    accounting = payload["test_split_accounting"]
    assert accounting["current_training_selection_and_gallery_used"] == 0
    assert accounting["untouched_remainder_min"] == 36100
    assert accounting["untouched_remainder_max"] == 36300
