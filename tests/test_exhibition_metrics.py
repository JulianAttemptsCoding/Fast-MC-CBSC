from __future__ import annotations

import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

from exhibition import build_metrics_catalog as catalog


ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "exhibition"


class _LocalReferences(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.values: list[str] = []

    def handle_starttag(self, _tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if name in {"href", "src"} and value:
                self.values.append(value)


def test_every_exhibition_graphic_decodes_or_parses() -> None:
    graphics = catalog.graphic_inventory()
    assert len(graphics) >= 103
    assert all(row["bytes"] > 0 for row in graphics)
    paths = {row["path"] for row in graphics}
    assert len(paths) == len(graphics)
    required = {
        f"current/diagnostics/{stem}.{suffix}"
        for stem in (
            "feature_moments_vs_epoch",
            "feature_moments_of_best_loss_so_far",
            "feature_resolutions_vs_epoch",
            "feature_resolutions_of_best_loss_so_far",
            "energy_bin_moments_vs_epoch",
            "energy_bin_moments_of_best_loss_so_far",
            "profiles_and_qa_vs_epoch",
            "profiles_and_qa_of_best_loss_so_far",
        )
        for suffix in ("png", "svg")
    }
    assert required <= paths
    assert {row["scope"] for row in graphics} == {"current", "archive"}
    assert catalog.verify_visual_layout(graphics)[
        "all_graphics_under_current_or_archive"
    ] is True


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


def test_current_gallery_is_complete_and_reaches_latest_evidence() -> None:
    payload = json.loads(
        (ROOT / "exhibition" / "metrics_catalog.json").read_text(encoding="utf-8")
    )
    assert payload["graphics"]["count_by_scope"] == {
        "archive": 52,
        "current": 65,
    }
    assert payload["qa"]["current_reaches_latest_observed_epoch"] == 40
    assert payload["qa"]["all_graphics_under_current_or_archive"] is True
    current_paths = {
        row["path"]
        for row in payload["graphics"]["files"]
        if row["scope"] == "current"
    }
    required_prefixes = {
        "current/model/",
        "current/continuation/",
        "current/diagnostics/",
        "current/external_metrics/",
        "current/external_metrics/source_data/",
    }
    assert all(
        any(path.startswith(prefix) for path in current_paths)
        for prefix in required_prefixes
    )


def test_every_local_gallery_link_and_image_target_exists() -> None:
    for page in HERE.rglob("*.html"):
        parser = _LocalReferences()
        parser.feed(page.read_text(encoding="utf-8"))
        for value in parser.values:
            parsed = urlsplit(value)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            target = (page.parent / parsed.path).resolve()
            assert target.is_file(), f"{page.relative_to(HERE)} -> {value}"
