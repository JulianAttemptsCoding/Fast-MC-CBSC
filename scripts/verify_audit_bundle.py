#!/usr/bin/env python
"""Re-hash every file in this bundle against MANIFEST.sha256.

Standard library only, so it runs anywhere without installing anything.

    python verify_bundle.py

Exit code 0 means every file is present and byte-identical to what was shipped.
Anything else is reported per file.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "MANIFEST.sha256"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    if not MANIFEST.exists():
        print(f"MANIFEST.sha256 is missing from {HERE}", file=sys.stderr)
        return 2

    expected: dict[str, tuple[str, int]] = {}
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, size, relative = line.split(None, 2)
        expected[relative] = (digest, int(size))

    missing, changed, ok = [], [], 0
    for relative, (digest, size) in sorted(expected.items()):
        path = HERE / relative
        if not path.is_file():
            missing.append(relative)
            continue
        actual_size = path.stat().st_size
        actual = sha256_file(path)
        if actual != digest or actual_size != size:
            changed.append(
                f"{relative}\n    expected {digest} ({size} bytes)"
                f"\n    found    {actual} ({actual_size} bytes)"
            )
        else:
            ok += 1

    present = {
        p.relative_to(HERE).as_posix()
        for p in HERE.rglob("*")
        if p.is_file() and p.name not in {"MANIFEST.sha256"}
    }
    extra = sorted(present - set(expected))

    print(f"manifest entries : {len(expected)}")
    print(f"verified         : {ok}")
    print(f"missing          : {len(missing)}")
    print(f"changed          : {len(changed)}")
    print(f"not in manifest  : {len(extra)}")

    for label, items in (("MISSING", missing), ("CHANGED", changed),
                         ("NOT IN MANIFEST", extra)):
        if items:
            print(f"\n{label}:")
            for item in items:
                print(f"  {item}")

    return 0 if not (missing or changed or extra) else 1


if __name__ == "__main__":
    raise SystemExit(main())
