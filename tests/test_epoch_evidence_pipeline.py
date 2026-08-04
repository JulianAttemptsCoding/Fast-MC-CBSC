from __future__ import annotations

import json
from pathlib import Path

import pytest

from exhibition import build_diagnostic_trend_figure as diagnostic
from exhibition import build_exhibition
from exhibition import build_metrics_catalog
from exhibition.build_continuation_loss_figures import _running_best
from scripts import dicos_workspace_inventory
from scripts import prepare_public_best_release
from scripts import refresh_continuation_outputs as refresh

ROOT = Path(__file__).resolve().parents[1]


def test_running_best_never_advances_on_quarantine() -> None:
    rows = [
        {"validation_loss": 5.0, "status": "accepted"},
        {"validation_loss": 4.0, "status": "accepted"},
        {"validation_loss": 3.0, "status": "quarantined"},
        {"validation_loss": 3.5, "status": "accepted"},
    ]
    assert _running_best(rows) == [5.0, 4.0, 4.0, 3.5]


def test_best_metric_trace_uses_validation_loss_only() -> None:
    rows = []
    for tag in ("dicos-p9", "dicos-p10"):
        for path in sorted(
            (ROOT / "exhibition/data/diagnostics" / tag).glob(
                "metrics_epoch_*.json"
            )
        ):
            row = json.loads(path.read_text(encoding="utf-8"))
            row["run_tag"] = tag
            rows.append(row)
    rows.sort(key=lambda row: int(row["epoch"]))
    selected, epochs, trace, unavailable = diagnostic.best_loss_so_far_rows(
        rows, "calibrated_lr1e4"
    )
    assert unavailable == list(range(16, 24))
    assert epochs[0] == 24
    assert len(selected) == len(epochs)
    assert trace[-1]["best_checkpoint_epoch"] == 38
    assert trace[-1]["best_validation_loss"] == pytest.approx(4.635219681489869)
    assert trace[-1]["metric_available_from_3090"] is True


def test_current_best_visualizations_are_resolved_not_hardcoded() -> None:
    resolved = build_exhibition.resolve_best_files()
    assert set(resolved) == set(build_exhibition.VARIANTS)
    standings = json.loads(
        (ROOT / "exhibition/current/continuation/family_choice.json").read_text(
            encoding="utf-8"
        )
    )["families"]
    for family, path in resolved.items():
        payload = json.loads(
            (ROOT / "dashboard/public/data" / path).read_text(encoding="utf-8")
        )
        assert payload["epoch"] == standings[family]["best_accepted_epoch"]
        assert payload["split"] == "validation"
        assert payload["qa"]["test_events_used"] == 0


def test_public_selection_is_derived_from_current_accepted_bests() -> None:
    selection = prepare_public_best_release.derive_selection()
    assert len(selection["snapshots"]) == 4
    assert len({row["family"] for row in selection["snapshots"]}) == 4
    assert selection["default_snapshot_id"] == (
        "dicos-p7-calibrated-lr3e4:joint:0022"
    )
    assert all("lowest verified validation-loss" in row["basis"] for row in selection["snapshots"])


def test_complete_gallery_references_every_graphic() -> None:
    payload = build_metrics_catalog.build()
    pages = {
        scope: (ROOT / "exhibition" / scope / "index.html").read_text(
            encoding="utf-8"
        )
        for scope in ("current", "archive")
    }
    for record in payload["graphics"]["files"]:
        relative = Path(record["path"]).relative_to(record["scope"]).as_posix()
        assert relative in pages[record["scope"]]
    landing = (ROOT / "exhibition/index.html").read_text(encoding="utf-8")
    assert 'href="current/index.html"' in landing
    assert 'href="archive/index.html"' in landing


def test_workspace_inventory_is_non_destructive_and_path_bounded(
    tmp_path: Path,
) -> None:
    (tmp_path / "repo").mkdir()
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv_3090").mkdir()
    (tmp_path / "_runs/run-a").mkdir(parents=True)
    (tmp_path / "_runs/run.log").write_text("evidence", encoding="utf-8")
    (tmp_path / "_diag/tag-a").mkdir(parents=True)
    payload = dicos_workspace_inventory.build(tmp_path, Path("_workspace"))
    assert payload["runs"]["namespaced_directories"] == ["run-a"]
    assert payload["runs"]["immutable_launcher_records"] == ["run.log"]
    assert payload["diagnostic_namespaces"] == ["tag-a"]
    assert (tmp_path / "_workspace/inventory.json").is_file()
    assert (tmp_path / "_runs/run.log").read_text(encoding="utf-8") == "evidence"
    with pytest.raises(ValueError, match="inside"):
        dicos_workspace_inventory.build(tmp_path, Path("../outside"))


def test_quarantined_metric_is_not_treated_as_visualization_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    status = tmp_path / "status.json"
    status.write_text(
        json.dumps(
            {
                "default_status": "accepted",
                "overrides": [
                    {
                        "variant": "family",
                        "run_tag": "tag",
                        "epoch": 7,
                        "status": "quarantined",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(refresh, "CONTINUATION_STATUS", status)
    assert refresh.checkpoint_status("family", "tag", 6) == "accepted"
    assert refresh.checkpoint_status("family", "tag", 7) == "quarantined"


def test_epoch_record_rejects_wrong_expected_epoch() -> None:
    with pytest.raises(RuntimeError, match="expected epoch 999"):
        refresh.write_epoch_record(
            family="calibrated_lr1e4",
            run_tag="dicos-p10",
            lineage=["dicos-p9", "dicos-p10"],
            expected_epoch=999,
            offline=True,
            previous_best=None,
        )
