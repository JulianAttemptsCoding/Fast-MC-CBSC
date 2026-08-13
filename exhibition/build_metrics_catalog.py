"""Validate and catalog every exhibition graphic and current metric summary."""

from __future__ import annotations

import hashlib
import html
import json
import zipfile
import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "exhibition"
CURRENT = HERE / "current"
ARCHIVE = HERE / "archive"
OUTPUT_JSON = HERE / "metrics_catalog.json"
OUTPUT_MD = HERE / "METRICS_AND_FIGURES.md"
OUTPUT_HTML = HERE / "index.html"
CURRENT_HTML = CURRENT / "index.html"
ARCHIVE_HTML = ARCHIVE / "index.html"
LAYOUT_CONTRACT = HERE / "visual_layout.json"


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
    if relative.startswith("current/model/"):
        return "current_model_and_contract"
    if relative.startswith("current/continuation/"):
        return "current_continuation_and_standings"
    if relative.startswith("current/diagnostics/"):
        return "current_validation_diagnostics"
    if relative.startswith("current/external_metrics/source_data/"):
        return "current_external_metric_source_evidence"
    if relative.startswith("current/external_metrics/"):
        return "current_accepted_best_external_metrics"
    if relative.startswith("current/presentations/"):
        return "current_presentations"
    if relative.startswith("archive/common_window_20260727/"):
        return "historical_common_window_snapshot"
    if relative.startswith("archive/c2st_20260728/"):
        return "historical_c2st_test_study"
    if relative.startswith("archive/paired_diagnostics_20260730/"):
        return "historical_paired_test_exception"
    if relative.startswith("archive/misc/"):
        return "historical_miscellaneous"
    raise ValueError(f"graphic is not classified by current/archive role: {relative}")


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
    directory = ARCHIVE / "c2st_20260728"
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
    # Slide decks are cataloged too. They were previously invisible here, so
    # the archived C2ST overview was the one exhibition artifact whose bytes
    # nothing verified -- a deck is exactly the artifact that leaves the group
    # and is therefore the one most worth hashing.
    for path in sorted([
        *HERE.rglob("*.png"), *HERE.rglob("*.svg"), *HERE.rglob("*.pptx")
    ]):
        # Word/PowerPoint write a `~$name` lock file beside an open document.
        # It is transient, unreadable while the app holds it, and not evidence.
        if path.name.startswith("~$"):
            continue
        relative = path.relative_to(HERE).as_posix()
        scope = relative.split("/", 1)[0]
        if scope not in {"current", "archive"}:
            raise ValueError(f"exhibition graphic escaped current/archive: {relative}")
        if path.stat().st_size <= 0:
            raise ValueError(f"empty graphic: {path}")
        record = {
            "path": relative,
            "scope": scope,
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
        elif path.suffix == ".svg":
            root = ET.parse(path).getroot()
            if not root.tag.endswith("svg"):
                raise ValueError(f"invalid SVG root: {relative}")
        else:
            # A .pptx is a ZIP of OOXML parts. Verify it actually opens and
            # carries a presentation part, so a truncated or half-written deck
            # cannot sit in the exhibition looking like evidence.
            with zipfile.ZipFile(path) as archive:
                broken = archive.testzip()
                if broken is not None:
                    raise ValueError(f"corrupt deck member in {relative}: {broken}")
                names = set(archive.namelist())
            required = {"[Content_Types].xml", "ppt/presentation.xml"}
            missing = sorted(required - names)
            if missing:
                raise ValueError(f"deck {relative} is missing {missing}")
            record["slides"] = sum(
                1 for name in names
                if name.startswith("ppt/slides/slide") and name.endswith(".xml")
            )
            if record["slides"] < 1:
                raise ValueError(f"deck {relative} contains no slides")
        records.append(record)
    return records


def _family_for_run_tags(run_tags: list[str]) -> str:
    try:
        from exhibition.build_diagnostic_trend_figure import family_for_run_tags
    except ModuleNotFoundError:
        from build_diagnostic_trend_figure import family_for_run_tags
    return family_for_run_tags(run_tags)


def declared_diagnostic_gap(family: str, diagnostics_latest: int,
                            observed_latest: int) -> dict | None:
    """The declaration covering epochs with loss evidence but no diagnostics.

    Training and diagnostics run on separate pods, so a diagnostics pod that
    ends mid-campaign leaves a permanent hole that no later refresh can fill.
    The check above still fails on an undeclared hole -- what a declaration
    buys is that the hole has a written reason, a stated consequence and a
    condition that closes it, carried into the catalog where a reader meets it.
    A declaration that does not cover the whole hole does not satisfy it.
    """
    path = ROOT / "exhibition" / "data" / "diagnostic_gaps.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("diagnostic gap declarations must use schema 1")
    for gap in payload.get("gaps", []):
        if gap.get("family") != family:
            continue
        if (int(gap["first_epoch_without_diagnostics"]) <= diagnostics_latest + 1
                and int(gap["last_epoch_without_diagnostics"]) >= observed_latest):
            return gap
    return None


def current_metrics() -> dict:
    loss = read_json(CURRENT / "continuation" / "loss_summary.json")
    choice = read_json(CURRENT / "continuation" / "family_choice.json")
    diagnostic = read_json(
        CURRENT / "diagnostics" / "diagnostic_summary.json"
    )
    all_metrics = read_json(
        CURRENT / "diagnostics" / "all_metric_trends.json"
    )
    external_path = (
        CURRENT / "external_metrics" / "external_metric_summary.json"
    )
    external = read_json(external_path) if external_path.is_file() else None
    if loss.get("schema_version") != 2 or choice.get("schema_version") != 2:
        raise ValueError("accepted-family metric summaries must use schema 2")
    if diagnostic.get("schema_version") != 2:
        raise ValueError("diagnostic summary must use schema 2")
    run_tags = diagnostic.get("run_tags")
    if not isinstance(run_tags, list) or not run_tags:
        raise ValueError("current diagnostic lineage must be nonempty")
    if any(not re.fullmatch(r"[a-z0-9][a-z0-9-]*", str(tag)) for tag in run_tags):
        raise ValueError("current diagnostic lineage contains an unsafe run tag")
    epochs = diagnostic.get("epochs")
    if not isinstance(epochs, list) or epochs != sorted(set(epochs)):
        raise ValueError("diagnostic epochs must be unique and increasing")
    if [row.get("epoch") for row in diagnostic.get("per_epoch", [])] != epochs:
        raise ValueError("diagnostic per-epoch provenance is incomplete")
    if diagnostic.get("test_events_used") != 0:
        raise ValueError("current diagnostic summary used test events")
    if (
        all_metrics.get("all_numeric_metric_leaves_complete_every_epoch") is not True
        or all_metrics.get("epochs") != epochs
        or all_metrics.get("test_events_used") != 0
    ):
        raise ValueError("comprehensive numeric metric trends are incomplete")
    if external is not None and (
        external.get("source_split") != "validation"
        or external.get("test_events_used") != 0
        or external.get("external_metrics_may_select_or_tune_cbsc") is not False
    ):
        raise ValueError("accepted-best external metric boundary failed")

    for family, row in loss["families"].items():
        other = choice["families"][family]
        for key in (
            "best_accepted_epoch",
            "best_accepted_run_tag",
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
    accepted = choice["families"]["calibrated_lr1e4"]
    if external is not None:
        current_external = external["current"]
        if (
            current_external["epoch"] != accepted["best_accepted_epoch"]
            or current_external["run_tag"] != accepted["best_accepted_run_tag"]
            or current_external["validation_loss"]
            != accepted["best_accepted_validation_loss"]
        ):
            raise ValueError("external metrics are not current with the accepted best")
    else:
        current_external = {
            "status": "pending",
            "run_tag": accepted["best_accepted_run_tag"],
            "epoch": accepted["best_accepted_epoch"],
            "validation_loss": accepted["best_accepted_validation_loss"],
            "source_split": "validation",
            "test_events_used": 0,
            "selection_role": "descriptive only; may not select or tune CBSC",
        }
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
        "all_numeric_diagnostic_metrics": {
            "leaf_count": all_metrics["numeric_metric_leaf_count"],
            "complete_every_epoch": all_metrics[
                "all_numeric_metric_leaves_complete_every_epoch"
            ],
            "epochs": all_metrics["epochs"],
        },
        "accepted_best_external_metrics": current_external,
    }


def write_atomic(path: Path, text: str) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def scoped_gallery(graphics: list[dict], scope: str, output: Path) -> Path:
    """Build the complete current or archive gallery."""
    grouped: dict[tuple[str, str], list[dict]] = {}
    for record in graphics:
        if record["scope"] != scope:
            continue
        stem = str(Path(record["path"]).with_suffix(""))
        grouped.setdefault((record["category"], stem), []).append(record)
    labels = {
        "current_model_and_contract": "Current model and scientific contract",
        "current_continuation_and_standings": (
            "Current loss vs epoch and accepted standings"
        ),
        "current_validation_diagnostics": (
            "Current 3090 validation metrics through the latest epoch"
        ),
        "current_accepted_best_external_metrics": (
            "Current accepted-best four-momentum and AUROC monitors"
        ),
        "current_external_metric_source_evidence": (
            "Current accepted-best evaluator source figures"
        ),
        "current_presentations": "Current status-update slide decks",
        "historical_common_window_snapshot": "Historical common-window snapshot",
        "historical_c2st_test_study": "Historical isolated C2ST test study",
        "historical_paired_test_exception": "Historical paired test exception",
        "historical_miscellaneous": "Historical miscellaneous visuals",
    }
    sections = []
    for category_name, label in labels.items():
        entries = sorted(
            (stem, records)
            for (category, stem), records in grouped.items()
            if category == category_name
        )
        if not entries:
            continue
        cards = []
        for stem, records in entries:
            by_format = {record["format"]: record for record in records}
            display = by_format.get("png") or by_format.get("svg")
            links = " · ".join(
                f'<a href="{html.escape(Path(record["path"]).relative_to(scope).as_posix())}">{fmt.upper()}</a>'
                for fmt, record in sorted(by_format.items())
            )
            title = Path(stem).name.replace("_", " ").title()
            if display is None:
                # A slide deck carries no raster to thumbnail. It is still
                # cataloged and hashed; it just renders as a download card.
                deck = next(iter(by_format.values()))
                slides = deck.get("slides")
                detail = f"{slides} slides" if slides else deck["format"].upper()
                cards.append(
                    '<figure class="document"><figcaption><strong>'
                    + html.escape(title)
                    + "</strong><span>"
                    + html.escape(detail)
                    + " · "
                    + links
                    + "</span></figcaption></figure>"
                )
                continue
            cards.append(
                '<figure><a class="image" href="'
                + html.escape(Path(display["path"]).relative_to(scope).as_posix())
                + '"><img loading="lazy" src="'
                + html.escape(Path(display["path"]).relative_to(scope).as_posix())
                + '" alt="'
                + html.escape(title)
                + '"></a><figcaption><strong>'
                + html.escape(title)
                + "</strong><span>"
                + links
                + "</span></figcaption></figure>"
            )
        boundary = ""
        if category_name.startswith("historical_"):
            boundary = (
                '<p class="warning">Archived evidence. It is not part of the '
                "current visual set and cannot silently steer current selection.</p>"
            )
        if category_name in {
            "historical_c2st_test_study",
            "historical_paired_test_exception",
        }:
            boundary = (
                '<p class="warning">Historical test-split evidence. It is '
                "isolated from training, checkpoint selection, and current "
                "visual selection.</p>"
            )
        sections.append(
            f'<section id="{html.escape(category_name)}"><h2>'
            f'{html.escape(label)}</h2>{boundary}'
            f'<div class="grid">{"".join(cards)}</div></section>'
        )
    nav = "".join(
        f'<a href="#{html.escape(name)}">{html.escape(label)}</a>'
        for name, label in labels.items()
        if any(category == name for category, _stem in grouped)
    )
    document = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>CBSC-ZDC {scope} exhibition</title><style>
:root{font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;color:#102a43;background:#f4f7fa}*{box-sizing:border-box}body{margin:0}main{max-width:1540px;margin:auto;padding:44px 28px 72px}h1{font-size:clamp(32px,4vw,54px);letter-spacing:-.04em;margin:0 0 10px}header p{color:#526b82;max-width:960px;line-height:1.55}nav{display:flex;flex-wrap:wrap;gap:8px;margin:24px 0 38px}nav a{background:#fff;border:1px solid #cbd6e2;padding:8px 11px;border-radius:6px}section{margin-top:52px}h2{font-size:25px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,470px),1fr));gap:22px}figure{margin:0;background:#fff;border:1px solid #d9e2ec;border-radius:7px;overflow:hidden}.image{display:block;background:#fff}img{display:block;width:100%;height:auto;max-height:520px;object-fit:contain}figcaption{display:flex;justify-content:space-between;gap:14px;padding:12px 14px;border-top:1px solid #d9e2ec;font-size:13px}figcaption span{white-space:nowrap}a{color:#145da0;text-decoration:none}a:hover{text-decoration:underline}.warning{padding:12px 14px;border-left:4px solid #b42318;background:#fff3f1;color:#7a271a}.boundary{padding:14px 16px;background:#eaf4ef;border-left:4px solid #16835b;margin-top:22px}
</style></head><body><main><header><h1>CBSC-ZDC {scope} exhibition</h1><p>Every {scope} scientific PNG/SVG, organized by evidence role.</p><p class="boundary">Optimization and descriptive validation evidence only; Geant4 fidelity is not established.</p><p><a href="../index.html">Exhibition home</a></p></header><nav>""".replace("{scope}", html.escape(scope))
    document += nav + "</nav>" + "".join(sections) + "</main></body></html>"
    write_atomic(output, document)
    return output


def landing_page(current_count: int, archive_count: int) -> Path:
    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>CBSC-ZDC exhibition</title><style>
:root{{font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;color:#102a43;background:#f4f7fa}}body{{margin:0}}main{{max-width:920px;margin:auto;padding:64px 28px}}h1{{font-size:48px;margin-bottom:12px}}p{{color:#526b82;line-height:1.55}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:20px;margin-top:34px}}a{{display:block;padding:28px;background:white;border:1px solid #cbd6e2;border-radius:8px;color:#145da0;text-decoration:none}}strong{{display:block;font-size:24px;margin-bottom:8px}}span{{color:#526b82}}
</style></head><body><main><h1>CBSC-ZDC exhibition</h1><p>All substantive exhibition visuals live in exactly one of two governed folders. Current means the complete latest valid set; archive means historical, superseded, or isolated evidence.</p><div class="cards"><a href="current/index.html"><strong>Current</strong><span>{current_count} PNG/SVG files, updated through the latest available epoch and accepted-best transaction.</span></a><a href="archive/index.html"><strong>Archive</strong><span>{archive_count} historical PNG/SVG files, explicitly excluded from current selection.</span></a></div><p>Optimization and descriptive validation evidence only. Physics validation is not established.</p></main></body></html>"""
    write_atomic(OUTPUT_HTML, document)
    return OUTPUT_HTML


def markdown(payload: dict) -> str:
    counts = payload["graphics"]["count_by_category"]
    scopes = payload["graphics"]["count_by_scope"]
    lines = [
        "# Metrics and figures catalog",
        "",
        "This is the deterministic QA index for every PNG/SVG under `exhibition/`.",
        "Every graphic is contained by exactly `current/` or `archive/`.",
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
        f"Current: **{scopes['current']}**. Archive: **{scopes['archive']}**.",
        "",
        "| Category | PNG/SVG files |",
        "|---|---:|",
    ])
    for name, count in sorted(counts.items()):
        lines.append(f"| `{name}` | {count} |")
    diagnostics = payload["metrics"]["large_validation_diagnostics"]
    external = payload["metrics"]["accepted_best_external_metrics"]
    external_pending = external.get("status") == "pending"
    if external_pending:
        external = {
            **external,
            "checkpoint_sha256": "pending",
            "auroc_mean": float("nan"),
            "auroc_std": float("nan"),
            "four_momentum_macro_rms": float("nan"),
        }
    all_metrics = payload["metrics"]["all_numeric_diagnostic_metrics"]
    lines.extend([
        "",
        "## Scientific boundary",
        "",
        f"Current large-sample diagnostics cover epochs {diagnostics['epochs'][0]}–"
        f"{diagnostics['epochs'][-1]} on {diagnostics['events_per_epoch']:,} fixed "
        "validation events per epoch. Quarantined epochs: "
        f"{diagnostics['quarantined_epochs'] or 'none'}. These are descriptive,",
        "not a fidelity gate or Geant4 validation.",
        f"All **{all_metrics['leaf_count']}** numeric diagnostic leaves are present "
        "at every epoch and are stored in `all_metric_trends.json`.",
        "",
        "## Current accepted-best external monitors",
        "",
        f"- Accepted checkpoint: `{external['run_tag']}` epoch "
        f"{external['epoch']} (`{external['checkpoint_sha256']}`).",
        f"- Low-level validation C2ST AUROC: {external['auroc_mean']:.6f} "
        f"± {external['auroc_std']:.6f} across evaluator seeds.",
        f"- Fast-MC macro RMS relative four-vector error: "
        f"{external['four_momentum_macro_rms']:.6f}.",
        "- These validation monitors cannot select or tune the generator.",
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
    if external_pending:
        section = lines.index("## Current accepted-best external monitors")
        lines[section + 2 : section + 7] = [
            f"- Accepted checkpoint: `{external['run_tag']}` epoch "
            f"{external['epoch']}.",
            "- Four-momentum and AUROC validation monitors are pending; no "
            "placeholder scientific value is reported.",
            "- These validation monitors cannot select or tune the generator.",
        ]
    return "\n".join(lines)


def verify_visual_layout(graphics: list[dict]) -> dict:
    contract = read_json(LAYOUT_CONTRACT)
    extensions = set(contract["visual_extensions"])
    ignored = set(contract["ignored_directory_names"])
    actual_outside = set()
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in extensions:
            continue
        relative = path.relative_to(ROOT)
        if any(part in ignored for part in relative.parts):
            continue
        if path == HERE or HERE in path.parents:
            continue
        actual_outside.add(relative.as_posix())
    expected_outside = set(contract["needed_outside_exhibition_exceptions"])
    if actual_outside != expected_outside:
        raise ValueError(
            "outside-exhibition visual exceptions changed; "
            f"missing={sorted(expected_outside - actual_outside)}, "
            f"unexpected={sorted(actual_outside - expected_outside)}"
        )
    html_paths = {
        path.relative_to(HERE).as_posix() for path in HERE.rglob("*.html")
    }
    if "index.html" not in html_paths:
        raise ValueError("required exhibition landing page is missing")
    escaped_html = sorted(
        path
        for path in html_paths
        if path != "index.html"
        and not path.startswith(("current/", "archive/"))
    )
    if escaped_html:
        raise ValueError(f"substantive HTML escaped current/archive: {escaped_html}")
    return {
        "all_graphics_under_current_or_archive": all(
            row["scope"] in {"current", "archive"} for row in graphics
        ),
        "root_html_is_router_only": True,
        "needed_outside_exhibition_exceptions": sorted(actual_outside),
    }


def build() -> dict:
    exhibition_manifest = verify_exhibition_manifest()
    c2st_manifest_count = verify_c2st_manifests()
    graphics = graphic_inventory()
    current_graphics = [row for row in graphics if row["scope"] == "current"]
    archive_graphics = [row for row in graphics if row["scope"] == "archive"]
    current_gallery = scoped_gallery(graphics, "current", CURRENT_HTML)
    archive_gallery = scoped_gallery(graphics, "archive", ARCHIVE_HTML)
    gallery = landing_page(len(current_graphics), len(archive_graphics))
    layout_qa = verify_visual_layout(graphics)
    metrics = current_metrics()
    counts = Counter(record["category"] for record in graphics)
    scope_counts = Counter(record["scope"] for record in graphics)
    latest_epoch = metrics["large_validation_diagnostics"]["epochs"][-1]
    # The shared diagnostic_summary.json/all_metric_trends.json slot holds
    # exactly one lineage at a time, and now that a campaign refreshes several
    # families in one pass, whichever ran last decides what that lineage is.
    # `calibrated_lr1e4` was correct back when it was the only family with
    # 3090 diagnostics; the family this check compares against must instead be
    # whichever family the shared slot's own run tags actually belong to.
    diagnostics_family = _family_for_run_tags(
        metrics["large_validation_diagnostics"]["run_tags"]
    )
    family = metrics["families"][diagnostics_family]
    declared_gap = None
    if latest_epoch != family["latest_observed_epoch"]:
        declared_gap = declared_diagnostic_gap(
            diagnostics_family, latest_epoch, family["latest_observed_epoch"]
        )
        if declared_gap is None:
            raise ValueError(
                "current diagnostics do not reach the latest observed epoch "
                f"for {diagnostics_family}"
            )
    payload = {
        "schema_version": 1,
        "graphics": {
            "total": len(graphics),
            "count_by_category": dict(sorted(counts.items())),
            "count_by_scope": dict(sorted(scope_counts.items())),
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
            "current_and_archive_galleries_contain_every_graphic": True,
            "current_reaches_latest_observed_epoch": latest_epoch,
            "declared_diagnostic_gap": declared_gap,
            **layout_qa,
        },
        "comprehensive_gallery": {
            "path": gallery.relative_to(HERE).as_posix(),
            "bytes": gallery.stat().st_size,
            "sha256": sha256(gallery),
        },
        "scoped_galleries": {
            "current": {
                "path": current_gallery.relative_to(HERE).as_posix(),
                "bytes": current_gallery.stat().st_size,
                "sha256": sha256(current_gallery),
            },
            "archive": {
                "path": archive_gallery.relative_to(HERE).as_posix(),
                "bytes": archive_gallery.stat().st_size,
                "sha256": sha256(archive_gallery),
            },
        },
    }
    write_atomic(OUTPUT_JSON, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    write_atomic(OUTPUT_MD, markdown(payload))
    return payload


if __name__ == "__main__":
    result = build()
    print(json.dumps({"graphics": result["graphics"]["total"], **result["qa"]}))
