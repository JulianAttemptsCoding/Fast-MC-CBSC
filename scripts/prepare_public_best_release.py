"""Prepare and QA the public one-best-snapshot-per-family release candidate.

This command never commits or pushes. It derives the allowlist mechanically
from accepted validation-loss standings, exports deterministic public data, and
runs the public tests/build. Deployment remains an explicit verified boundary.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DATA = ROOT / "dashboard/public/data"


def run(command: list[str], cwd: Path) -> str:
    result = subprocess.run(
        command, cwd=cwd, capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"{' '.join(command)} failed: {result.stderr.strip() or result.stdout.strip()}"
        )
    return result.stdout.strip()


def derive_selection() -> dict:
    from exhibition import build_exhibition

    standings = json.loads(
        (ROOT / "exhibition/current/continuation/family_choice.json").read_text(
            encoding="utf-8"
        )
    )["families"]
    best_files = build_exhibition.resolve_best_files()
    dashboard = json.loads(
        (SOURCE_DATA / "manifest.json").read_text(encoding="utf-8")
    )
    by_path = {row["path"]: row for row in dashboard["epochs"]}
    snapshots = []
    run_labels = []
    for family in build_exhibition.VARIANTS:
        entry = by_path[best_files[family]]
        run_labels.append(entry["run_label"])
        snapshots.append(
            {
                "family": family,
                "id": entry["id"],
                "basis": (
                    "lowest verified validation-loss checkpoint for this "
                    "calibrated family"
                ),
            }
        )
    default_family = min(
        standings,
        key=lambda family: standings[family]["best_accepted_validation_loss"],
    )
    default_id = next(
        row["id"] for row in snapshots if row["family"] == default_family
    )
    return {
        "schema_version": 1,
        "policy": "one accepted checkpoint per calibrated model family",
        "default_snapshot_id": default_id,
        "source_run": ", ".join(run_labels),
        "snapshots": snapshots,
    }


def prepare(public_repo: Path) -> dict:
    public_repo = public_repo.resolve()
    required = [
        public_repo / ".git",
        public_repo / "scripts/export_public_data.py",
        public_repo / "config/public_snapshots.json",
        public_repo / "package.json",
    ]
    if any(not path.exists() for path in required):
        raise ValueError(f"not a public Fast-MC repository: {public_repo}")
    if run(["git", "status", "--short"], public_repo):
        raise RuntimeError("public repository must be clean before preparing release")

    selection = derive_selection()
    selection_path = public_repo / "config/public_snapshots.json"
    temporary = selection_path.with_name(f".{selection_path.name}.tmp")
    temporary.write_text(
        json.dumps(selection, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(selection_path)
    exporter = public_repo / "scripts/export_public_data.py"
    run(
        [
            sys.executable,
            str(exporter),
            "--source",
            str(SOURCE_DATA),
            "--destination",
            str(public_repo / "public/data"),
            "--selection",
            str(selection_path),
        ],
        public_repo,
    )
    test_output = run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], public_repo)
    build_output = run(["npm.cmd", "run", "build"], public_repo)
    return {
        "selection": selection,
        "git_status": run(["git", "status", "--short"], public_repo).splitlines(),
        "tests_passed": "FAILED" not in test_output,
        "build_passed": "built in" in build_output,
        "deployment_required": bool(
            run(["git", "status", "--short"], public_repo)
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-repo", type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(prepare(args.public_repo), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
