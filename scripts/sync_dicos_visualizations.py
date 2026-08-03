"""Merge DiCOS epoch visualisations into the dashboard data directory.

`sync_vertex_visualizations.py` speaks GCS and cannot reach DiCOS, so the
DiCOS-produced epochs in `dashboard/public/data/manifest.json` were assembled
by hand. Hand-assembly is where provenance quietly goes wrong -- a mistyped
hash or a silently overwritten immutable snapshot -- so this applies exactly
the same contracts as the Vertex path, importing them rather than restating
them:

  * schema version, validation split, `qa.pass`, `test_events_used == 0`,
    sample count, five draws per condition, per-group draw count;
  * a snapshot ID already present must not change hash (immutability);
  * geometry and the fixed 50x5 selection must not change across epochs;
  * prior manifest row order is preserved, new rows appended.

It differs from the Vertex path in one field only: rows carry `dicos_object`
(the path on the shared filesystem) instead of `gcs_object`/`gcs_generation`,
matching the DiCOS rows already in the manifest.

Payloads are downloaded separately (`scripts/dicos.py get`); this consumes
local files plus the remote path each came from.

Usage:
    python scripts/sync_dicos_visualizations.py \
        --destination dashboard/public/data \
        --run-label dicos-p6-calibrated-lr3e4 \
        --payload local/epoch_0015.json \
        --dicos-object "_runs/calibrated_lr3e4_dicos-p6/reports/visualization/epoch_0015.json"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sync_vertex_visualizations import (  # noqa: E402
    _atomic_write_bytes,
    _load_json_bytes,
    _normalize_existing_rows,
    _sha256_bytes,
    _snapshot_id,
    _validate_epoch,
)


def sync(
    destination: Path,
    run_label: str,
    payloads: list[tuple[Path, str]],
    geometry: Path | None = None,
) -> dict:
    if not payloads:
        raise ValueError("no payloads given")

    manifest_path = destination / "manifest.json"
    existing = (
        json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest_path.exists()
        else None
    )
    if existing is None:
        raise RuntimeError(
            "refusing to create a dashboard manifest from scratch; this merges "
            "into an existing one"
        )
    existing_rows = _normalize_existing_rows(existing)
    existing_by_id = {str(row["id"]): row for row in existing_rows}
    if len(existing_by_id) != len(existing_rows):
        raise RuntimeError("duplicate stage-qualified visualization snapshot IDs")

    geometry_hash = existing.get("geometry_sha256")
    selection_hash = existing.get("selection_sha256")
    current_rows: list[dict] = []
    written = 0

    for local_path, remote_object in sorted(payloads, key=lambda p: str(p[0])):
        content = Path(local_path).read_bytes()
        digest = _sha256_bytes(content)
        payload = _load_json_bytes(content, str(local_path))
        _validate_epoch(payload, str(local_path))

        epoch = int(payload["epoch"])
        stage = str(payload["stage"])
        snapshot_id = _snapshot_id(stage, epoch, run_label)

        existing_row = existing_by_id.get(snapshot_id)
        if existing_row is not None and str(existing_row["sha256"]) != digest:
            raise RuntimeError(
                f"immutable snapshot {snapshot_id} hash changed: "
                f"{existing_row['sha256']} != {digest}"
            )

        # The published epochs are only comparable because every one of them
        # draws the same 50 validation conditions from the same geometry.
        if geometry_hash != str(payload["geometry_sha256"]):
            raise RuntimeError(
                f"geometry changed for {snapshot_id}: "
                f"{geometry_hash} != {payload['geometry_sha256']}"
            )
        if selection_hash != str(payload["selection_sha256"]):
            raise RuntimeError(
                f"validation selection changed for {snapshot_id}: "
                f"{selection_hash} != {payload['selection_sha256']}"
            )

        local_name = (
            str(existing_row["path"])
            if existing_row is not None
            else f"{run_label}_{stage}_epoch_{epoch:04d}.json"
        )
        target = destination / local_name
        if target.exists() and _sha256_bytes(target.read_bytes()) != digest:
            raise RuntimeError(
                f"immutable local file hash mismatch for {snapshot_id}: {target}"
            )
        if not target.exists():
            _atomic_write_bytes(content, target)
            written += 1

        current_rows.append(
            {
                "id": snapshot_id,
                "epoch": epoch,
                "stage": stage,
                "run_label": run_label,
                "path": target.name,
                "sha256": digest,
                "checkpoint_sha256": payload["checkpoint_sha256"],
                "qa_pass": True,
                "elapsed_seconds": payload["elapsed_seconds"],
                "trend": payload["aggregate"]["trend"],
                "dicos_object": remote_object,
            }
        )

    if geometry is not None:
        geometry_payload = json.loads(Path(geometry).read_text(encoding="utf-8"))
        if geometry_payload.get("geometry_sha256") != geometry_hash:
            raise RuntimeError("refusing to publish a different visualization geometry")

    merged_by_id = dict(existing_by_id)
    for row in current_rows:
        merged_by_id[str(row["id"])] = row
    prior_ids = [str(row["id"]) for row in existing_rows]
    appended_ids = [
        str(row["id"]) for row in current_rows if str(row["id"]) not in existing_by_id
    ]
    epoch_rows = [merged_by_id[snapshot_id] for snapshot_id in prior_ids + appended_ids]

    manifest = dict(existing)
    manifest["epochs"] = epoch_rows
    manifest["schema_version"] = 3
    manifest["geometry_sha256"] = geometry_hash
    manifest["selection_sha256"] = selection_hash
    manifest["sync"] = {
        "test_events_used": 0,
        "exact_epoch_snapshot_only": True,
        "downloaded_this_pass": written,
    }
    _atomic_write_bytes(
        (json.dumps(manifest, separators=(",", ":"), sort_keys=True) + "\n").encode(),
        manifest_path,
    )
    return {
        "written": written,
        "rows": len(epoch_rows),
        "added": appended_ids,
        "status": "ready",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--run-label", required=True)
    parser.add_argument("--payload", type=Path, action="append", required=True)
    parser.add_argument("--dicos-object", action="append", required=True)
    parser.add_argument("--geometry", type=Path)
    args = parser.parse_args(argv)

    if len(args.payload) != len(args.dicos_object):
        raise SystemExit("--payload and --dicos-object must be given in pairs")

    result = sync(
        destination=args.destination,
        run_label=args.run_label,
        payloads=list(zip(args.payload, args.dicos_object)),
        geometry=args.geometry,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
