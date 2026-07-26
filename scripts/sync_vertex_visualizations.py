from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import urlparse


EPOCH_OBJECT = re.compile(
    r"/progress/epoch_(?P<snapshot>\d{4})/"
    r"reports/visualization/epoch_(?P<artifact>\d{4})\.json$"
)


def _parse_gs(uri: str) -> tuple[str, str]:
    parsed = urlparse(uri)
    if parsed.scheme != "gs" or not parsed.netloc:
        raise ValueError(f"expected gs://bucket/prefix, got {uri}")
    return parsed.netloc, parsed.path.lstrip("/").rstrip("/")


def _atomic_write_bytes(content: bytes, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_bytes(content)
    temporary.replace(destination)


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _load_json_bytes(content: bytes, source: str) -> dict:
    payload = json.loads(content)
    if not isinstance(payload, dict):
        raise RuntimeError(f"visualization object is not a mapping: {source}")
    return payload


def _validate_epoch(payload: dict, source: str) -> None:
    if payload.get("schema_version") != 1:
        raise RuntimeError(f"unsupported visualization schema in {source}")
    if payload.get("split") != "validation":
        raise RuntimeError(f"non-validation visualization object rejected: {source}")
    qa = payload.get("qa", {})
    if not qa.get("pass") or int(qa.get("test_events_used", -1)) != 0:
        raise RuntimeError(f"visualization QA/test-data contract failed: {source}")
    if int(payload.get("sample_count", 0)) <= 0:
        raise RuntimeError(f"empty visualization sample in {source}")
    if int(payload.get("draws_per_condition", 0)) != 5:
        raise RuntimeError(f"expected exactly five Fast-MC draws in {source}")
    if len(payload.get("groups", [])) != int(payload["sample_count"]):
        raise RuntimeError(f"visualization group count mismatch in {source}")
    if any(
        len(group.get("fast_mc", [])) != 5 for group in payload.get("groups", [])
    ):
        raise RuntimeError(f"per-condition draw count mismatch in {source}")


def _safe_label(value: str, kind: str) -> str:
    if not re.fullmatch(r"[a-z][a-z0-9_-]*", value):
        raise RuntimeError(f"unsafe visualization {kind} name: {value!r}")
    return value


def _snapshot_id(stage: str, epoch: int, run_label: str | None = None) -> str:
    safe_stage = _safe_label(stage, "stage")
    if run_label is None:
        return f"{safe_stage}:{epoch:04d}"
    return f"{_safe_label(run_label, 'run-label')}:{safe_stage}:{epoch:04d}"


def _normalize_existing_rows(existing: dict | None) -> list[dict]:
    rows = []
    for row in (existing or {}).get("epochs", []):
        normalized = dict(row)
        normalized["id"] = str(
            row.get("id") or _snapshot_id(str(row["stage"]), int(row["epoch"]))
        )
        rows.append(normalized)
    return rows


def sync_once(
    source_uri: str,
    destination: Path,
    run_label: str | None = None,
) -> dict:
    try:
        from google.cloud import storage  # type: ignore
    except ImportError as exc:
        raise RuntimeError("install the cloud extra: pip install '.[cloud]'") from exc

    bucket_name, prefix = _parse_gs(source_uri)
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    listing_prefix = f"{prefix}/progress/" if prefix else "progress/"
    exact_epoch_blobs = {}
    for blob in client.list_blobs(bucket, prefix=listing_prefix):
        match = EPOCH_OBJECT.search(f"/{blob.name}")
        if not match:
            continue
        snapshot = int(match.group("snapshot"))
        artifact = int(match.group("artifact"))
        if snapshot == artifact:
            exact_epoch_blobs[artifact] = blob

    if not exact_epoch_blobs:
        return {"downloaded": 0, "epochs": 0, "status": "waiting_for_first_epoch"}

    existing_manifest_path = destination / "manifest.json"
    existing = (
        json.loads(existing_manifest_path.read_text(encoding="utf-8"))
        if existing_manifest_path.exists()
        else None
    )
    existing_rows = _normalize_existing_rows(existing)
    existing_by_id = {str(row["id"]): row for row in existing_rows}
    if len(existing_by_id) != len(existing_rows):
        raise RuntimeError("duplicate stage-qualified visualization snapshot IDs")
    geometry_hash = (existing or {}).get("geometry_sha256")
    selection_hash = (existing or {}).get("selection_sha256")
    current_rows = []
    downloaded = 0
    current_stage = None

    for epoch, blob in sorted(exact_epoch_blobs.items()):
        content = blob.download_as_bytes()
        digest = _sha256_bytes(content)
        payload = _load_json_bytes(content, blob.name)
        _validate_epoch(payload, blob.name)
        if int(payload["epoch"]) != epoch:
            raise RuntimeError(f"epoch path/payload mismatch: {blob.name}")
        stage = str(payload["stage"])
        snapshot_id = _snapshot_id(stage, epoch, run_label)
        current_stage = current_stage or stage
        if current_stage != stage:
            raise RuntimeError("one Vertex output prefix contains multiple stages")
        existing_row = existing_by_id.get(snapshot_id)
        if existing_row is not None and str(existing_row["sha256"]) != digest:
            raise RuntimeError(
                f"immutable local snapshot {snapshot_id} hash changed: "
                f"{existing_row['sha256']} != {digest}"
            )
        current_geometry = str(payload["geometry_sha256"])
        current_selection = str(payload["selection_sha256"])
        geometry_hash = geometry_hash or current_geometry
        selection_hash = selection_hash or current_selection
        if geometry_hash != current_geometry:
            raise RuntimeError("geometry changed across visualization epochs")
        if selection_hash != current_selection:
            raise RuntimeError("validation selection changed across visualization epochs")
        local_name = (
            str(existing_row["path"])
            if existing_row is not None
            else (
                f"{run_label}_{stage}_epoch_{epoch:04d}.json"
                if run_label is not None
                else f"{stage}_epoch_{epoch:04d}.json"
            )
        )
        local_epoch = destination / local_name
        if local_epoch.exists() and _sha256_bytes(local_epoch.read_bytes()) != digest:
            raise RuntimeError(
                f"immutable local file hash mismatch for {snapshot_id}: {local_epoch}"
            )
        if not local_epoch.exists():
            _atomic_write_bytes(content, local_epoch)
            downloaded += 1
        current_rows.append(
            {
                "id": snapshot_id,
                "epoch": epoch,
                "stage": stage,
                "run_label": run_label,
                "path": local_epoch.name,
                "sha256": digest,
                "checkpoint_sha256": payload["checkpoint_sha256"],
                "qa_pass": True,
                "elapsed_seconds": payload["elapsed_seconds"],
                "trend": payload["aggregate"]["trend"],
                "gcs_object": blob.name,
                "gcs_generation": str(blob.generation),
            }
        )

    merged_by_id = dict(existing_by_id)
    for row in current_rows:
        merged_by_id[str(row["id"])] = row
    prior_ids = [str(row["id"]) for row in existing_rows]
    appended_ids = [
        str(row["id"]) for row in current_rows if str(row["id"]) not in existing_by_id
    ]
    epoch_rows = [merged_by_id[snapshot_id] for snapshot_id in prior_ids + appended_ids]

    latest_epoch = max(exact_epoch_blobs)
    latest_id = _snapshot_id(str(current_stage), latest_epoch, run_label)
    latest_blob = exact_epoch_blobs[latest_epoch]
    geometry_name = (
        latest_blob.name.rsplit("/", 1)[0] + "/geometry.json"
    )
    geometry_blob = bucket.blob(geometry_name)
    if not geometry_blob.exists(client):
        raise RuntimeError(f"missing visualization geometry: {geometry_name}")
    geometry_content = geometry_blob.download_as_bytes()
    geometry_payload = _load_json_bytes(geometry_content, geometry_name)
    if geometry_payload.get("geometry_sha256") != geometry_hash:
        raise RuntimeError("downloaded geometry hash contract mismatch")
    local_geometry = destination / "geometry.json"
    if local_geometry.exists():
        local_payload = json.loads(local_geometry.read_text(encoding="utf-8"))
        if local_payload.get("geometry_sha256") != geometry_hash:
            raise RuntimeError("refusing to overwrite different local geometry")
    else:
        _atomic_write_bytes(geometry_content, local_geometry)
        downloaded += 1

    manifest = {
        "schema_version": 3,
        "source_uri": source_uri,
        "geometry_path": "geometry.json",
        "geometry_sha256": geometry_hash,
        "selection_sha256": selection_hash,
        "latest_epoch": latest_epoch,
        "latest_id": latest_id,
        "epochs": epoch_rows,
        "sync": {
            "test_events_used": 0,
            "exact_epoch_snapshot_only": True,
            "downloaded_this_pass": downloaded,
        },
    }
    _atomic_write_bytes(
        (json.dumps(manifest, separators=(",", ":"), sort_keys=True) + "\n").encode(),
        existing_manifest_path,
    )
    return {
        "downloaded": downloaded,
        "epochs": len(epoch_rows),
        "latest_epoch": latest_epoch,
        "latest_id": latest_id,
        "status": "ready",
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Synchronize immutable Vertex epoch visualizations to localhost"
    )
    parser.add_argument("--source", required=True, help="Vertex run output gs:// prefix")
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument(
        "--run-label",
        help="safe run identity used to distinguish repeated stage/epoch pairs",
    )
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--interval-seconds", type=int, default=60)
    args = parser.parse_args()
    if args.interval_seconds < 15:
        raise ValueError("interval-seconds must be at least 15")
    while True:
        result = sync_once(args.source, args.destination, args.run_label)
        print(json.dumps(result, sort_keys=True), flush=True)
        if not args.watch:
            break
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    main()
