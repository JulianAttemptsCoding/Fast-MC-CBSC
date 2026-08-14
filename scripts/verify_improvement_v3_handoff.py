from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys


BASE_HASHES = {
    "AGENTS.md": "4e39294b165a61161507a492cc8964c4c4e9250984bfd34b644afb800fdd55b8",
    "src/cbsc_zdc/models/system.py": "84e086357a1345bf8d27759d157c8a6a898a3a0059914c669771b0ae464d6822",
    "src/cbsc_zdc/models/response.py": "d02727c5ba2ad74431f0e45dab4a9e641bf6eee08b5332af762b0605c773c1cc",
    "src/cbsc_zdc/models/profile.py": "64bb03c5293347cdba5e546c33a313da10207c171f3d83aa3fc7bbc06162285e",
    "src/cbsc_zdc/models/counts.py": "3bca32a46ab5ebb02a1e517dc46a65b9e3fef3e148603d494e69846ea661f8dd",
    "src/cbsc_zdc/models/support.py": "514f2c3fbbaa12ac4f4a21931afd3086ab53407a93d16fcac9fce84a0f65f865",
    "src/cbsc_zdc/models/node_fields.py": "2bad8562e00e5836d91d182d133a07d1685fafb4b0208e54d78e96e954107cfd",
    "src/cbsc_zdc/training/trainer.py": "b542dd075d80bf32dcb739f50cee836f3bcd48c70c561371aefa9a13a4a5301f",
    "src/cbsc_zdc/training/losses.py": "f926dd69567c8023516ed3ecbfff40649dd5965f565723615cd28e2df7794b1f",
    "src/cbsc_zdc/config.py": "091197f456492a040162bda4d76acaa52b35c1b544d2779e5bf926874b7b7139",
    "configs/templates/train_full_0_300_raw.yaml": "9ffb04ca4947ebb7d225a20a2a1d0a7eed9bc49046350712f040d3089f508a91",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        digest, separator, relative = line.partition("  ")
        if not separator or len(digest) != 64 or not relative:
            raise ValueError(f"invalid manifest line {line_number}: {raw!r}")
        if relative in entries:
            raise ValueError(f"duplicate manifest path: {relative}")
        entries[relative] = digest
    return entries


def validate_yaml(path: Path) -> None:
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("PyYAML is required to validate the handoff") from exc
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must decode to a mapping")


def validate_csv(path: Path) -> int:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f"{path} has no CSV header")
        return sum(1 for _ in reader)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--require-audited-base", action="store_true")
    args = parser.parse_args()
    root = args.repo_root.resolve()
    handoff_doc = root / "docs" / "improvement_v3" / "README.md"
    manifest_path = root / "specs" / "improvement_v3" / "MANIFEST.sha256"
    if not handoff_doc.is_file() or not manifest_path.is_file():
        raise SystemExit("handoff files are not installed at the supplied repository root")

    manifest = load_manifest(manifest_path)
    missing: list[str] = []
    changed: list[str] = []
    for relative, expected in manifest.items():
        target = root / relative
        if not target.is_file():
            missing.append(relative)
        elif sha256(target) != expected:
            changed.append(relative)

    yaml_files = sorted((root / "specs" / "improvement_v3").glob("*.yaml"))
    for path in yaml_files:
        validate_yaml(path)
    csv_counts = {
        str(path.relative_to(root)): validate_csv(path)
        for path in sorted((root / "specs" / "improvement_v3").glob("*.csv"))
    }

    base_status: dict[str, str] = {}
    for relative, expected in BASE_HASHES.items():
        target = root / relative
        if not target.is_file():
            base_status[relative] = "missing"
        else:
            actual = sha256(target)
            base_status[relative] = "audited_match" if actual == expected else f"live_diff:{actual}"

    result = {
        "status": "pass" if not missing and not changed else "fail",
        "repo_root": str(root),
        "manifest_entries": len(manifest),
        "missing": missing,
        "changed": changed,
        "yaml_files_validated": [str(path.relative_to(root)) for path in yaml_files],
        "csv_data_rows": csv_counts,
        "audited_base_status": base_status,
        "base_matches_all": all(value == "audited_match" for value in base_status.values()),
        "base_note": "live differences require reconciliation and must not be reverted automatically",
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    if missing or changed:
        return 2
    if args.require_audited_base and not result["base_matches_all"]:
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())

