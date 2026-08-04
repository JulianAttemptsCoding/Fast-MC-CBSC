"""Create a non-destructive index of the permitted DiCOS project workdir.

This script organizes by classification and provenance, not by moving old run
evidence.  It writes only an atomic `_workspace/{inventory.json,README.md}`
inside the explicitly supplied project root.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

ACTIVE = {
    ".venv": "RTX 4090 training environment",
    ".venv_3090": "RTX 3090 diagnostic environment",
    "repo": "shared clean source checkout",
    "prep": "immutable prepared corpus, geometry, splits, and frozen inputs",
    "_runs": "namespaced training runs and immutable launcher records",
    "_diag": "namespaced 4090-to-3090 checkpoint/metric handoff",
    "_workspace": "generated workspace index and operator orientation",
}
HISTORICAL = {
    ".venv_" + "a" + "100": (
        "retired 80 GB datacentre environment; never activate without owner instruction"
    ),
    ".venv_dcgpu": "retired environment; never activate without owner instruction",
    "_bench": "historical hardware measurements; nonbinding",
    "_setup": "historical setup evidence",
}
TRANSIENT = {"_tmp": "temporary QA workspace; inspect before any cleanup"}


def _inside(root: Path, path: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _git(root: Path) -> dict:
    repo = root / "repo"
    if not (repo / ".git").exists():
        return {"present": False}

    def run(*args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()

    return {
        "present": True,
        "commit": run("rev-parse", "HEAD"),
        "status": run("status", "--short").splitlines(),
        "origin_main_vs_head": run(
            "rev-list", "--left-right", "--count", "origin/main...HEAD"
        ).split(),
    }


def build(root: Path, output_dir: Path) -> dict:
    root = root.resolve()
    destination = (root / output_dir).resolve()
    if output_dir.is_absolute() or not _inside(root, destination):
        raise ValueError("output directory must remain inside the project root")
    destination.mkdir(parents=True, exist_ok=True)

    entries = []
    for path in sorted(root.iterdir(), key=lambda item: item.name):
        if path.name in ACTIVE:
            role, disposition = ACTIVE[path.name], "active"
        elif path.name in HISTORICAL:
            role, disposition = HISTORICAL[path.name], "historical-preserve"
        elif path.name in TRANSIENT:
            role, disposition = TRANSIENT[path.name], "transient-review"
        else:
            role, disposition = "unclassified; review before use", "review"
        entries.append(
            {
                "name": path.name,
                "kind": "directory" if path.is_dir() else "file",
                "disposition": disposition,
                "role": role,
            }
        )

    run_root = root / "_runs"
    run_directories = []
    launcher_records = []
    if run_root.is_dir():
        for path in sorted(run_root.iterdir(), key=lambda item: item.name):
            target = run_directories if path.is_dir() else launcher_records
            target.append(path.name)
    diag_namespaces = []
    diag_root = root / "_diag"
    if diag_root.is_dir():
        diag_namespaces = sorted(
            path.name for path in diag_root.iterdir() if path.is_dir()
        )

    payload = {
        "schema_version": 1,
        "kind": "cbsc-zdc-dicos-workspace-inventory",
        "root": str(root),
        "mutation_policy": (
            "index only; historical evidence is not moved or deleted"
        ),
        "gpu_roles": {
            "RTX 4090": ".venv / sole training writer",
            "RTX 3090": ".venv_3090 / per-epoch diagnostic consumer",
        },
        "entries": entries,
        "runs": {
            "namespaced_directories": run_directories,
            "immutable_launcher_records": launcher_records,
        },
        "diagnostic_namespaces": diag_namespaces,
        "repo": _git(root),
    }
    markdown = """# DiCOS CBSC-ZDC workspace

This index is generated without moving or deleting evidence. The only active
environments are `.venv` (RTX 4090 training) and `.venv_3090` (RTX 3090
per-epoch diagnostics). Retired environments and historical measurements are
preserved but must not be activated for current work.

Operational state lives in four places:

- `repo/`: synchronized source checkout;
- `prep/`: immutable prepared inputs and frozen configs;
- `_runs/<family>_<tag>/`: one writer and all run evidence;
- `_diag/<tag>/`: namespaced checkpoint queue, metrics, and quarantine state.

Loose `.log`/`.pid` files under `_runs/` are immutable launcher records from
older wrappers. Do not move them: recovery procedures refer to their original
paths. `_tmp/` is reviewable transient QA material, never an input.

See `repo/docs/TWO_GPU_PIPELINE.md` for the executable epoch state machine and
`inventory.json` for the complete classified listing.
"""
    for path, text in (
        (destination / "inventory.json", json.dumps(payload, indent=2) + "\n"),
        (destination / "README.md", markdown),
    ):
        temporary = path.with_name(f".{path.name}.tmp")
        temporary.write_text(text, encoding="utf-8")
        temporary.replace(path)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output-dir", type=Path, default=Path("_workspace"))
    args = parser.parse_args(argv)
    payload = build(args.root, args.output_dir)
    print(
        json.dumps(
            {
                "entries": len(payload["entries"]),
                "run_directories": len(payload["runs"]["namespaced_directories"]),
                "diagnostic_namespaces": payload["diagnostic_namespaces"],
                "repo_commit": payload["repo"].get("commit"),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
