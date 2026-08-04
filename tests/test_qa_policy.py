from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_active_guidance_has_no_hardware_permission_screen() -> None:
    active_files = [
        ROOT / "AGENTS.md",
        ROOT / "README.md",
        *sorted((ROOT / "docs").glob("*.md")),
        ROOT / "exhibition" / "README.md",
        ROOT / "exhibition" / "build_exhibition.py",
        ROOT / "scripts" / "build_compute_extensions.py",
        ROOT / "scripts" / "build_viability_matrix.py",
        ROOT / "scripts" / "verify_compute_extensions_frozen.py",
        ROOT / "scripts" / "verify_viability_frozen.py",
    ]
    forbidden = (
        "a" + "100",
        "scale-up " + "gate",
        "progression " + "gate",
        "progression-" + "gate",
        "frozen_a" + "100",
    )
    failures: list[str] = []
    for path in active_files:
        text = path.read_text(encoding="utf-8").lower()
        for phrase in forbidden:
            if phrase in text:
                failures.append(f"{path.relative_to(ROOT)}: {phrase}")
    assert failures == []


def test_current_policy_is_explicitly_nonblocking() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    policy = (ROOT / "docs" / "QA_POLICY.md").read_text(encoding="utf-8")
    handoff = (
        ROOT / "docs" / "AGENT_PROMPT_CONTINUE_ANY_BACKEND_20260728.md"
    ).read_text(encoding="utf-8")
    required = "never grant or deny permission"
    normalized_agents = " ".join(agents.lower().split())
    normalized_policy = " ".join(policy.lower().split())
    normalized_handoff = " ".join(handoff.lower().split())
    assert required in normalized_agents
    assert "does not grant or deny permission" in normalized_policy
    assert "does not grant or deny permission" in normalized_handoff


def test_self_contained_continuity_rule_is_binding_and_indexed() -> None:
    agents = " ".join((ROOT / "AGENTS.md").read_text("utf-8").lower().split())
    focused = " ".join(
        (ROOT / "docs" / "FOCUSED_OPERATING_RULES.md")
        .read_text("utf-8")
        .lower()
        .split()
    )
    for phrase in (
        "make the current state self-contained",
        "without reconstructing chat or repository history",
        "missing context is a fail-closed documentation defect",
    ):
        assert phrase in agents
    for phrase in (
        "self-contained continuity",
        "one current-state audit",
        "superseded and quarantined material explicitly",
    ):
        assert phrase in focused
