"""Validate and catalog every exhibition graphic and current metric summary."""

from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "exhibition"
OUTPUT_JSON = HERE / "metrics_catalog.json"
OUTPUT_MD = HERE / "METRICS_AND_FIGURES.md"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def category(path: Path) -> str:
    relative = path.relative_to(HERE).as_posix()
    if relative.startswith("figures/"):
        return "common_window_gallery"
    if relative.startswith("continuation_20260802/"):
        return "continuation_and_standings"
    if relative.startswith("diagnostics_20260803/"):
        return "large_validation_diagnostics"
    if relative.startswith("c2st_20260728/"):
        return "historical_c2st_test_study"
    if relative.startswith("paired_diagnostics_20260730/"):
        return "historical_paired_test_exception"
    return "other"


def verify_exhibition_manifest() -> dict:
    manifest = read_json(HERE / "manifest.json")
    if manifest.get("schema_version") != 2:
        raise ValueError("exhibition manifest schema must be 2")
    for entry in manifest["source_files"]:
        path = ROOT / entry["path"]
        if path.stat().st_size != entry["bytes"] or sha256(path) != entry["sha256"]:
            raise ValueError(f"exhibition source hash mismatch: {path}")
    for entry in manifest["visuals"]:
        path = HERE / entry["path"]
        if path.stat().st_size != entry["bytes"] or sha256(path) != entry["sha256"]:
            raise ValueError(f"exhibition visual hash mismatch: {path}")
    gallery = HERE / manifest["gallery"]["path"]
    if sha256(gallery) != manifest["gallery"]["sha256"]:
        raise ValueError("exhibition gallery hash mismatch")
    return manifest


def verify_c2st_manifests() -> int:
    directory = HERE / "c2st_20260728"
    count = 0
    for manifest_name in ("figures_manifest.json", "method_manifest.json"):
        manifest = read_json(directory / manifest_name)
        if manifest.get("schema_version") != 1:
            raise ValueError(f"unsupported {manifest_name} schema")
        for entry in manifest["figures"]:
            path = directory / "figures" / entry["file"]
            if not path.is_file() or sha256(path) != entry["sha256"]:
                raise ValueError(f"C2ST figure hash mismatch: {path}")
            count += 1
    return count


def graphic_inventory() -> list[dict]:
    records = []
    for path in sorted([*HERE.rglob("*.png"), *HERE.rglob("*.svg")]):
        relative = path.relative_to(HERE).as_posix()
        if path.stat().st_size <= 0:
            raise ValueError(f"empty graphic: {path}")
        record = {
            "path": relative,
            "category": category(path),
            "format": path.suffix[1:],
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        if path.suffix == ".png":
            with Image.open(path) as image:
                image.verify()
            with Image.open(path) as image:
                width, height = image.size
            if width < 600 or height < 350:
                raise ValueError(f"undersized graphic {relative}: {width}x{height}")
            record["width"] = width
            record["height"] = height
        else:
            root = ET.parse(path).getroot()
            if not root.tag.endswith("svg"):
                raise ValueError(f"invalid SVG root: {relative}")
        records.append(record)
    return records


def current_metrics() -> dict:
    loss = read_json(HERE / "continuation_20260802" / "loss_summary.json")
    choice = read_json(HERE / "continuation_20260802" / "family_choice.json")
    diagnostic = read_json(
        HERE / "diagnostics_20260803" / "diagnostic_summary.json"
    )
    if loss.get("schema_version") != 2 or choice.get("schema_version") != 2:
        raise ValueError("accepted-family metric summaries must use schema 2")
    if diagnostic.get("schema_version") != 2:
        raise ValueError("diagnostic summary must use schema 2")
    if diagnostic.get("run_tags") != ["dicos-p9", "dicos-p10"]:
        raise ValueError("current diagnostic lineage must be dicos-p9 + dicos-p10")
    if diagnostic.get("quarantined_epochs") != [40]:
        raise ValueError("current diagnostic summary must expose quarantined epoch 40")
    if diagnostic.get("test_events_used") != 0:
        raise ValueError("current diagnostic summary used test events")

    for family, row in loss["families"].items():
        other = choice["families"][family]
        for key in (
            "best_accepted_epoch",
            "best_accepted_validation_loss",
            "latest_accepted_epoch",
            "latest_accepted_validation_loss",
            "latest_observed_epoch",
            "latest_observed_validation_loss",
            "latest_observed_status",
            "quarantined_epochs",
        ):
            if row[key] != other[key]:
                raise ValueError(f"family summaries disagree: {family}/{key}")
    return {
        "families": choice["families"],
        "noise_resolution": choice["noise_resolution"],
        "large_validation_diagnostics": {
            "run_tags": diagnostic["run_tags"],
            "epochs": diagnostic["epochs"],
            "events_per_epoch": diagnostic["n_events_per_epoch"],
            "split": "validation",
            "test_events_used": diagnostic["test_events_used"],
            "quarantined_epochs": diagnostic["quarantined_epochs"],
            "scientific_status": diagnostic["scientific_status"],
        },
    }


def write_atomic(path: Path, text: str) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def markdown(payload: dict) -> str:
    counts = payload["graphics"]["count_by_category"]
    lines = [
        "# Metrics and figures catalog",
        "",
        "This is the deterministic QA index for every PNG/SVG under `exhibition/`.",
        "Current standings exclude quarantined checkpoints; quarantined observations",
        "remain visible as negative evidence.",
        "",
        "## Current accepted family standings",
        "",
        "| Family | Best accepted | Latest accepted | Latest observed | Status |",
        "|---|---:|---:|---:|---|",
    ]
    for family, row in payload["metrics"]["families"].items():
        lines.append(
            f"| `{family}` | e{row['best_accepted_epoch']} / "
            f"{row['best_accepted_validation_loss']:.6f} | "
            f"e{row['latest_accepted_epoch']} / "
            f"{row['latest_accepted_validation_loss']:.6f} | "
            f"e{row['latest_observed_epoch']} / "
            f"{row['latest_observed_validation_loss']:.6f} | "
            f"{row['latest_observed_status']} |"
        )
    lines.extend([
        "",
        "## Graphics inventory",
        "",
        f"Validated graphics: **{payload['graphics']['total']}**.",
        "",
        "| Category | PNG/SVG files |",
        "|---|---:|",
    ])
    for name, count in sorted(counts.items()):
        lines.append(f"| `{name}` | {count} |")
    diagnostics = payload["metrics"]["large_validation_diagnostics"]
    lines.extend([
        "",
        "## Scientific boundary",
        "",
        f"Current large-sample diagnostics cover epochs {diagnostics['epochs'][0]}–"
        f"{diagnostics['epochs'][-1]} on {diagnostics['events_per_epoch']:,} fixed "
        "validation events per epoch. Epoch 40 is quarantined. These are descriptive,",
        "not a fidelity gate or Geant4 validation.",
        "",
        "The current gallery, training decisions, and validation diagnostics use zero",
        "test events. Historical isolated evidence remains separated:",
        "",
        "- C2ST study: 40,000 test events.",
        "- Paired diagnostic draw: 200 test events among 2,000 sampled events.",
        "- Overlap is unresolved; untouched test remainder is 36,100–36,300.",
        "- Neither historical study may steer model or checkpoint decisions.",
        "",
        "Full per-file paths, dimensions, byte sizes, and hashes are in",
        "`metrics_catalog.json`.",
        "",
    ])
    return "\n".join(lines)


def build() -> dict:
    exhibition_manifest = verify_exhibition_manifest()
    c2st_manifest_count = verify_c2st_manifests()
    graphics = graphic_inventory()
    metrics = current_metrics()
    counts = Counter(record["category"] for record in graphics)
    payload = {
        "schema_version": 1,
        "graphics": {
            "total": len(graphics),
            "count_by_category": dict(sorted(counts.items())),
            "files": graphics,
        },
        "metrics": metrics,
        "test_split_accounting": {
            "total": 76300,
            "historical_c2st_used": 40000,
            "historical_paired_draw_used": 200,
            "historical_overlap": "unresolved",
            "untouched_remainder_min": 36100,
            "untouched_remainder_max": 36300,
            "current_training_selection_and_gallery_used": 0,
        },
        "qa": {
            "status": "PASS",
            "exhibition_manifest_visuals": len(exhibition_manifest["visuals"]),
            "c2st_manifest_figures": c2st_manifest_count,
            "all_png_decoded": True,
            "all_svg_parsed": True,
            "all_manifest_hashes_match": True,
            "accepted_metric_summaries_agree": True,
        },
    }
    write_atomic(OUTPUT_JSON, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    write_atomic(OUTPUT_MD, markdown(payload))
    return payload


if __name__ == "__main__":
    result = build()
    print(json.dumps({"graphics": result["graphics"]["total"], **result["qa"]}))
