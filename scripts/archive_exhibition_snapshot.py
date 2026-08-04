#!/usr/bin/env python3
"""Create and verify immutable exhibition snapshots for the archive repository.

The command copies an entire ``exhibition/`` tree, records repository state and
per-file SHA-256 values, then atomically installs the snapshot.  It never edits
or removes the source tree and refuses to overwrite an existing snapshot.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid


CONTROL_FILES = {"README.md", "SHA256SUMS.txt", "snapshot.json"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.stdout.strip()


def relative_files(root: Path) -> list[Path]:
    return sorted(
        (path.relative_to(root) for path in root.rglob("*") if path.is_file()),
        key=lambda path: path.as_posix(),
    )


def create_snapshot(args: argparse.Namespace) -> dict[str, object]:
    source_root = args.source_root.resolve(strict=True)
    exhibition = (source_root / "exhibition").resolve(strict=True)
    destination = args.destination.resolve(strict=False)
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite existing snapshot: {destination}")
    if exhibition == destination or exhibition in destination.parents:
        raise ValueError("snapshot destination may not be inside the source exhibition")

    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(f".{destination.name}.partial-{uuid.uuid4().hex}")
    try:
        partial.mkdir()
        copied_exhibition = partial / "exhibition"
        shutil.copytree(exhibition, copied_exhibition)

        files = []
        for relative in relative_files(copied_exhibition):
            path = copied_exhibition / relative
            files.append(
                {
                    "path": f"exhibition/{relative.as_posix()}",
                    "bytes": path.stat().st_size,
                    "sha256": sha256(path),
                }
            )

        status = run_git(source_root, "status", "--short", "--untracked-files=all")
        status_lines = status.splitlines() if status else []
        payload: dict[str, object] = {
            "schema_version": 1,
            "snapshot_id": args.snapshot_id,
            "captured_at": args.captured_at,
            "source_label": args.source_label,
            "source_git": {
                "head": run_git(source_root, "rev-parse", "HEAD"),
                "branch": run_git(source_root, "branch", "--show-current"),
                "origin": run_git(source_root, "remote", "get-url", "origin"),
                "dirty": bool(status_lines),
                "status_lines": status_lines,
                "status_sha256": hashlib.sha256(status.encode("utf-8")).hexdigest(),
            },
            "scope": "complete pre-sync exhibition tree",
            "scientific_boundary": {
                "new_test_events_used": 0,
                "training_started": False,
                "event_generation_started": False,
                "physics_validation_established": False,
            },
            "file_count": len(files),
            "total_bytes": sum(int(item["bytes"]) for item in files),
            "files": files,
        }
        (partial / "snapshot.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        readme = (
            f"# {args.snapshot_id}\n\n"
            f"Complete pre-sync `exhibition/` snapshot from `{args.source_label}`.\n\n"
            f"- Captured: `{args.captured_at}`\n"
            f"- Source commit: `{payload['source_git']['head']}`\n"
            f"- Source dirty: `{str(payload['source_git']['dirty']).lower()}`\n"
            f"- Files: `{payload['file_count']}`\n"
            f"- Bytes: `{payload['total_bytes']}`\n\n"
            "`snapshot.json` records repository state and every exhibition-file hash. "
            "`SHA256SUMS.txt` covers the exhibition plus both snapshot metadata files.\n\n"
            "Scientific boundary: this is optimization/descriptive-validation evidence; "
            "it does not establish Geant4 fidelity. This archive operation used no new "
            "test event and started no training or event generation.\n"
        )
        (partial / "README.md").write_text(readme, encoding="utf-8")

        sum_paths = [
            path for path in relative_files(partial) if path.as_posix() != "SHA256SUMS.txt"
        ]
        sums = "".join(
            f"{sha256(partial / relative)}  {relative.as_posix()}\n"
            for relative in sum_paths
        )
        (partial / "SHA256SUMS.txt").write_text(sums, encoding="utf-8")
        verify_snapshot(partial)
        os.replace(partial, destination)
        return payload
    except Exception:
        if partial.exists():
            shutil.rmtree(partial)
        raise


def parse_sums(path: Path) -> dict[str, str]:
    expected: dict[str, str] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        digest, separator, relative = line.partition("  ")
        if not separator or len(digest) != 64 or not relative:
            raise ValueError(f"invalid SHA256SUMS line {line_number}: {line!r}")
        if relative in expected:
            raise ValueError(f"duplicate SHA256SUMS path: {relative}")
        expected[relative] = digest
    return expected


def verify_snapshot(snapshot_root: Path) -> dict[str, object]:
    snapshot_root = snapshot_root.resolve(strict=True)
    payload = json.loads((snapshot_root / "snapshot.json").read_text(encoding="utf-8"))
    manifest_files = {item["path"]: item for item in payload["files"]}
    actual_exhibition = {
        f"exhibition/{relative.as_posix()}": snapshot_root / "exhibition" / relative
        for relative in relative_files(snapshot_root / "exhibition")
    }
    if set(actual_exhibition) != set(manifest_files):
        missing = sorted(set(manifest_files) - set(actual_exhibition))
        extra = sorted(set(actual_exhibition) - set(manifest_files))
        raise ValueError(f"snapshot manifest mismatch; missing={missing}, extra={extra}")
    for relative, path in actual_exhibition.items():
        item = manifest_files[relative]
        if path.stat().st_size != item["bytes"] or sha256(path) != item["sha256"]:
            raise ValueError(f"snapshot file mismatch: {relative}")

    sums = parse_sums(snapshot_root / "SHA256SUMS.txt")
    expected_sum_paths = {
        relative.as_posix()
        for relative in relative_files(snapshot_root)
        if relative.as_posix() != "SHA256SUMS.txt"
    }
    if set(sums) != expected_sum_paths:
        raise ValueError("SHA256SUMS path inventory does not match snapshot contents")
    for relative, digest in sums.items():
        if sha256(snapshot_root / relative) != digest:
            raise ValueError(f"SHA256SUMS mismatch: {relative}")

    if payload["file_count"] != len(actual_exhibition):
        raise ValueError("snapshot file_count is inconsistent")
    if payload["total_bytes"] != sum(path.stat().st_size for path in actual_exhibition.values()):
        raise ValueError("snapshot total_bytes is inconsistent")
    return {
        "status": "pass",
        "snapshot_id": payload["snapshot_id"],
        "file_count": payload["file_count"],
        "total_bytes": payload["total_bytes"],
        "sha256s_verified": len(sums),
    }


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create", help="create one immutable snapshot")
    create.add_argument("--source-root", type=Path, required=True)
    create.add_argument("--destination", type=Path, required=True)
    create.add_argument("--snapshot-id", required=True)
    create.add_argument("--source-label", required=True)
    create.add_argument("--captured-at", required=True)
    verify = commands.add_parser("verify", help="verify an existing snapshot")
    verify.add_argument("--snapshot-root", type=Path, required=True)
    return root


def main() -> int:
    args = parser().parse_args()
    result = (
        create_snapshot(args)
        if args.command == "create"
        else verify_snapshot(args.snapshot_root)
    )
    json.dump(result, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
