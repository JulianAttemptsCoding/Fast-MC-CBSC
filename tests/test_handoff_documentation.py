"""The handoff set must stay true, not just exist.

A manual whose commands have drifted is worse than no manual: it makes a wrong
action look sanctioned. These tests pin the facts a returning agent will act on
and the existence of every script the docs tell them to run.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
PIPELINES = DOCS / "PIPELINES.md"
RUNBOOK = DOCS / "WALKAWAY_RUNBOOK.md"
HANDOFF = DOCS / "HANDOFF.md"
REPORT = DOCS / "V3_FULL_REPORT.md"
REGISTRY = ROOT / "exhibition" / "data" / "v3_screening_rows.json"


@pytest.mark.parametrize("path", [PIPELINES, RUNBOOK, HANDOFF, REPORT])
def test_the_handoff_set_exists(path):
    assert path.is_file(), f"{path.name} is missing"
    assert len(path.read_text(encoding="utf-8")) > 2000


@pytest.mark.parametrize("path", [PIPELINES, RUNBOOK, HANDOFF, REPORT])
def test_every_doc_carries_the_terminal_status(path):
    """No handoff document may read as though fidelity were established."""
    assert "PHYSICS VALIDATION NOT ESTABLISHED" in path.read_text(encoding="utf-8")


def test_every_script_the_pipelines_doc_names_actually_exists():
    """A manual pointing at a script that is not there is worse than none."""
    text = PIPELINES.read_text(encoding="utf-8")
    referenced = set(re.findall(r"(?:scripts|exhibition)/[A-Za-z0-9_]+\.py", text))
    assert referenced, "the pipelines doc names no scripts at all"
    missing = [name for name in referenced if not (ROOT / name).is_file()]
    assert not missing, f"pipelines doc names scripts that do not exist: {sorted(missing)}"


def test_the_comparator_rule_is_stated_consistently():
    """The single easiest scientific mistake must read the same everywhere."""
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    rule = registry["comparator_rule"]
    m0 = f"{rule['statement']}"
    assert "M0-fresh" in m0 and "NOT B0" in m0

    m0_loss = "4.513572"
    b0_loss = "4.483768"
    for path in (PIPELINES, RUNBOOK, REPORT):
        text = path.read_text(encoding="utf-8")
        assert m0_loss in text, f"{path.name} omits the M0 comparator value"
        assert b0_loss in text, f"{path.name} omits B0 for contrast"


def test_the_two_c2st_families_are_never_conflated_in_the_docs():
    """0.65 gates high-level (0.892897), not the hybrid 0.843222."""
    for path in (PIPELINES, REPORT):
        text = path.read_text(encoding="utf-8")
        assert "max_high_level_c2st_auc" in text
        assert "0.892897" in text


def test_the_pipelines_doc_covers_every_operational_pipeline():
    text = PIPELINES.read_text(encoding="utf-8")
    for topic in (
        "Session start",
        "screening row",
        "validation battery",
        "unattended",
        "figures and metrics current",
        "continuation refresh",
        "Full QA",
    ):
        assert topic.lower() in text.lower(), f"pipelines doc omits {topic!r}"


def test_the_pipelines_doc_states_what_is_not_automated():
    """An agent must not infer that a judgment call can be scripted."""
    text = PIPELINES.read_text(encoding="utf-8")
    assert "not automated" in text.lower()
    for item in ("Promotion decisions", "Publication", "test split"):
        assert item.lower() in text.lower()


def test_the_pipelines_doc_warns_that_a_trainer_is_many_pids():
    """Seeing 9 pids and killing them is how a good run gets destroyed."""
    text = PIPELINES.read_text(encoding="utf-8")
    assert "dataloader workers" in text
    assert "ppid" in text


def test_the_runbook_names_only_live_jobs():
    """A runbook naming a stopped job sends the operator to an empty log."""
    text = RUNBOOK.read_text(encoding="utf-8")
    for retired in ("battery2", "battery3", "battery4", "`v3m0`"):
        assert retired not in text, f"runbook still names the retired job {retired}"


def test_the_registry_records_a_comparator_for_every_unfinished_row():
    """A row must know what it will be judged against before it finishes."""
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    assert registry["comparator_rule"]["measured_fresh_optimizer_cost"] > 0
    for row in registry["rows"]:
        assert row["parent"]["validation_loss"] > 0, row["row_id"]


# --------------------------------------------------------------------------
# the archive must stay unfollowable
# --------------------------------------------------------------------------

ARCHIVE = DOCS / "archive"

#: Bytes are deliberately preserved for these: they are a delivered artifact,
#: and prepending a banner would destroy the provenance they exist to carry.
UNBANNERED = {"README.md"}


def test_the_archive_exists_and_explains_itself():
    assert (ARCHIVE / "README.md").is_file()
    text = (ARCHIVE / "README.md").read_text(encoding="utf-8")
    assert "Do not follow any of it" in text
    assert "PHYSICS VALIDATION NOT ESTABLISHED" in text


def test_every_archived_guidance_document_carries_a_supersession_banner():
    """An archived doc without a banner reads as current guidance."""
    missing = []
    for path in ARCHIVE.glob("*.md"):
        if path.name in UNBANNERED:
            continue
        head = path.read_text(encoding="utf-8")[:400]
        if "ARCHIVED — SUPERSEDED" not in head:
            missing.append(path.name)
    assert not missing, f"archived docs without a supersession banner: {missing}"


def test_every_banner_names_a_replacement_that_exists():
    for path in ARCHIVE.glob("*.md"):
        if path.name in UNBANNERED:
            continue
        head = path.read_text(encoding="utf-8")[:1600]
        assert "HANDOFF.md" in head or "PIPELINES.md" in head or "V3_FULL_REPORT.md" in head, (
            f"{path.name} does not name a current replacement"
        )


def test_the_release_bundle_snapshots_are_byte_preserved():
    """Never banner a delivered artifact: it destroys its provenance."""
    bundle = ARCHIVE / "release_bundle_v2_2"
    assert bundle.is_dir()
    for path in bundle.glob("*.md"):
        assert "ARCHIVED — SUPERSEDED" not in path.read_text(encoding="utf-8")[:400], (
            f"{path.name} was modified; release-bundle snapshots must keep their bytes"
        )


def test_no_current_document_sends_a_reader_to_the_archive_as_guidance():
    """A live doc may cite the archive as history, never as instruction."""
    live = [
        p for p in DOCS.glob("*.md")
    ] + [ROOT / "AGENTS.md", ROOT / "CLAUDE.md", ROOT / "README.md"]
    offenders = []
    for path in live:
        text = path.read_text(encoding="utf-8")
        for name in ("AGENT_PROMPT_CONTINUE_ANY_BACKEND_20260728",
                     "AGENT_PROMPT_VERTEX_RUN_AND_ANALYZE"):
            if name not in text:
                continue
            # Citing it is fine only alongside a word marking it as retired.
            window = text[max(0, text.index(name) - 400): text.index(name) + 400]
            if not any(w in window.lower() for w in
                       ("archiv", "supersed", "retired", "must not be followed")):
                offenders.append(f"{path.name} -> {name}")
    assert not offenders, f"current docs cite archived guidance without marking it: {offenders}"


def test_the_moved_files_are_gone_from_their_old_locations():
    """Two copies of one document is the confusion this cleanup removed."""
    for stale in (
        DOCS / "AGENT_PROMPT_CONTINUE_ANY_BACKEND_20260728.md",
        DOCS / "AGENT_PROMPT_VERTEX_RUN_AND_ANALYZE.md",
        DOCS / "VERTEX_QA_CHECKLIST.md",
        DOCS / "COMPUTE_EXTENSION_PROTOCOL_20260727.md",
        ROOT / "V3_PLAN_ASSESSMENT.md",
        ROOT / "CBSC_ZDC_v3_DELIVERY_README.md",
    ):
        assert not stale.exists(), f"{stale.name} still exists at its old path"
    for name in (
        "CBSC_ZDC_v2_2_COMPLETE_IMPLEMENTATION_GUIDE.md",
        "CBSC_ZDC_v2_2_DATA_CONTRACT.md",
        "CBSC_ZDC_v2_2_MODEL_WALKTHROUGH.md",
    ):
        assert not (ROOT / name).exists(), f"{name} still sits at repository root"


def test_the_documentation_index_lists_every_live_doc():
    """A doc absent from the index has no declared status, which is the defect."""
    index = (DOCS / "README.md").read_text(encoding="utf-8")
    for path in DOCS.glob("*.md"):
        if path.name == "README.md":
            continue
        assert path.name in index, f"{path.name} is not listed in docs/README.md"


def test_checksummed_documents_were_not_moved():
    """Moving a checksum-recorded file breaks a recorded audit artifact."""
    sums = (ROOT / "SHA256SUMS.txt").read_text(encoding="utf-8")
    for line in sums.splitlines():
        parts = line.split("  ", 1)
        if len(parts) != 2:
            continue
        recorded = parts[1].strip()
        if recorded.startswith("docs/") or "/" not in recorded:
            assert (ROOT / recorded).is_file(), (
                f"{recorded} is checksummed in SHA256SUMS.txt but no longer at that path"
            )
