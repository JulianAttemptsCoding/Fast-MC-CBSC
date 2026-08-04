"""Restore ignored dashboard evidence files from their immutable transports.

The dashboard manifest is tracked, while the large per-epoch JSON payloads are
not.  This command makes a clean checkout reproducible: every download is
addressed by the transport metadata already frozen in the manifest and is
accepted only when its SHA-256 and scientific payload contract match.

This is a read-only remote operation.  It does not launch training, alter a
remote run, update the manifest, or accept an unpinned replacement object.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path, PurePosixPath

try:
    from scripts.sync_vertex_visualizations import _validate_epoch
except ModuleNotFoundError:  # Direct execution: scripts/ is sys.path[0].
    from sync_vertex_visualizations import _validate_epoch


BytesFetcher = Callable[[dict], bytes]


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _safe_destination(root: Path, relative: str) -> Path:
    posix = PurePosixPath(relative)
    if posix.is_absolute() or ".." in posix.parts or len(posix.parts) != 1:
        raise RuntimeError(f"unsafe dashboard payload path: {relative!r}")
    resolved_root = root.resolve()
    destination = (resolved_root / posix.name).resolve()
    if destination.parent != resolved_root:
        raise RuntimeError(f"dashboard payload escapes destination: {relative!r}")
    return destination


def _validate_content(content: bytes, row: dict) -> None:
    expected = str(row["sha256"])
    actual = _sha256(content)
    if actual != expected:
        raise RuntimeError(
            f"immutable payload hash mismatch for {row['id']}: {actual} != {expected}"
        )
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid JSON payload for {row['id']}") from exc
    _validate_epoch(payload, str(row["id"]))
    if int(payload["epoch"]) != int(row["epoch"]):
        raise RuntimeError(f"epoch mismatch for {row['id']}")
    if str(payload["checkpoint_sha256"]) != str(row["checkpoint_sha256"]):
        raise RuntimeError(f"checkpoint hash mismatch for {row['id']}")


def _atomic_write(content: bytes, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    temporary.write_bytes(content)
    os.replace(temporary, destination)


def hydrate_manifest(
    manifest_path: Path,
    destination: Path,
    fetch_gcs: BytesFetcher,
    fetch_dicos: BytesFetcher,
) -> dict[str, int]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = manifest.get("epochs", [])
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("dashboard manifest contains no epoch rows")

    counts = {"verified": 0, "downloaded_gcs": 0, "downloaded_dicos": 0}
    for row in rows:
        local_path = _safe_destination(destination, str(row["path"]))
        if local_path.exists():
            _validate_content(local_path.read_bytes(), row)
            counts["verified"] += 1
            continue

        has_gcs = "gcs_object" in row and "gcs_generation" in row
        has_dicos = "dicos_object" in row
        if has_gcs == has_dicos:
            raise RuntimeError(
                f"row {row.get('id')} must define exactly one pinned transport"
            )
        if has_gcs:
            content = fetch_gcs(row)
            counter = "downloaded_gcs"
        else:
            content = fetch_dicos(row)
            counter = "downloaded_dicos"
        _validate_content(content, row)
        _atomic_write(content, local_path)
        counts[counter] += 1
    return counts


def gcs_fetcher(bucket_name: str) -> BytesFetcher:
    from google.cloud import storage  # type: ignore

    client = storage.Client()
    bucket = client.bucket(bucket_name)

    def fetch(row: dict) -> bytes:
        blob = bucket.blob(
            str(row["gcs_object"]), generation=int(row["gcs_generation"])
        )
        return blob.download_as_bytes(if_generation_match=int(row["gcs_generation"]))

    return fetch


def dicos_fetcher(config: Path, client_script: Path) -> BytesFetcher:
    def fetch(row: dict) -> bytes:
        with tempfile.TemporaryDirectory(prefix="cbsc-dashboard-") as temporary:
            local = Path(temporary) / "payload.json"
            command = [
                sys.executable,
                str(client_script),
                "get",
                str(row["dicos_object"]),
                str(local),
            ]
            environment = dict(os.environ)
            environment["DICOS_CONFIG"] = str(config)
            subprocess.run(command, check=True, env=environment)
            return local.read_bytes()

    return fetch


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Restore and hash-verify ignored dashboard evidence payloads"
    )
    parser.add_argument(
        "--manifest", type=Path, default=Path("dashboard/public/data/manifest.json")
    )
    parser.add_argument(
        "--destination", type=Path, default=Path("dashboard/public/data")
    )
    parser.add_argument("--gcs-bucket", default="asiop-zdc-1-zdc-reco-us-central1")
    parser.add_argument(
        "--dicos-config", type=Path, default=Path.home() / ".dicos" / "config.json"
    )
    parser.add_argument(
        "--dicos-client", type=Path, default=Path(__file__).with_name("dicos.py")
    )
    args = parser.parse_args()

    result = hydrate_manifest(
        args.manifest,
        args.destination,
        gcs_fetcher(args.gcs_bucket),
        dicos_fetcher(args.dicos_config, args.dicos_client),
    )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
