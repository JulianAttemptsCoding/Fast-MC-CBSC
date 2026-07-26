from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import PurePosixPath
from urllib.parse import urlparse

import yaml
from google.cloud import storage


SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _parse_gs(uri: str) -> tuple[str, str]:
    parsed = urlparse(uri)
    if parsed.scheme != "gs" or not parsed.netloc:
        raise ValueError(f"expected gs:// URI, got {uri}")
    return parsed.netloc, parsed.path.lstrip("/").rstrip("/")


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _safe_relative(value: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe staged relative path: {value}")
    return path.as_posix()


def _checkpoint_spec(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise ValueError("checkpoint spec must be RELATIVE_PATH=SHA256")
    relative, expected = value.rsplit("=", 1)
    relative = _safe_relative(relative)
    if not SHA256_PATTERN.fullmatch(expected):
        raise ValueError("checkpoint spec SHA256 must be lowercase hexadecimal")
    return relative, expected


def _list_prefix(
    client: storage.Client, uri: str
) -> tuple[storage.Bucket, dict[str, storage.Blob]]:
    bucket_name, prefix = _parse_gs(uri)
    bucket = client.bucket(bucket_name)
    boundary = f"{prefix}/" if prefix else ""
    objects: dict[str, storage.Blob] = {}
    for blob in client.list_blobs(bucket, prefix=boundary):
        relative = blob.name[len(boundary) :]
        if not relative:
            continue
        objects[relative] = blob
    if not objects:
        raise RuntimeError(f"no staged objects found under {uri}")
    return bucket, objects


def verify(
    base_uri: str,
    overlay_uris: list[str],
    config_relative: str,
    manifest_relative: str,
    splits_relative: str,
    geometry_relative: str,
    resolve_training_checkpoints: bool = True,
    extra_checkpoints: list[tuple[str, str]] | None = None,
) -> dict:
    normalized_extra = [
        _checkpoint_spec(f"{relative}={expected}")
        for relative, expected in (extra_checkpoints or [])
    ]
    if not resolve_training_checkpoints and not normalized_extra:
        raise RuntimeError(
            "skipping training checkpoints requires an exact extra checkpoint"
        )
    client = storage.Client()
    merged: dict[str, tuple[str, storage.Blob]] = {}
    source_counts: dict[str, int] = {}
    for uri in [base_uri, *overlay_uris]:
        _, objects = _list_prefix(client, uri)
        source_counts[uri] = len(objects)
        for relative, blob in objects.items():
            if relative in merged:
                raise RuntimeError(
                    f"staging collision for {relative}: "
                    f"{merged[relative][0]} and {uri}"
                )
            merged[relative] = (uri, blob)

    required = {
        _safe_relative(config_relative),
        _safe_relative(manifest_relative),
        _safe_relative(splits_relative),
        _safe_relative(f"{geometry_relative}/geometry.npz"),
        _safe_relative(f"{geometry_relative}/geometry_manifest.json"),
    }
    missing = sorted(required - set(merged))
    if missing:
        raise RuntimeError(f"merged staging is missing required paths: {missing}")

    def content(relative: str) -> bytes:
        return merged[relative][1].download_as_bytes()

    config_bytes = content(_safe_relative(config_relative))
    config = yaml.safe_load(config_bytes)
    if not isinstance(config, dict):
        raise RuntimeError("frozen config is not a mapping")
    if config["data"]["manifest"] == "UNFROZEN":
        raise RuntimeError("config is not frozen")
    provenance = config["provenance"]

    manifest_bytes = content(_safe_relative(manifest_relative))
    splits_bytes = content(_safe_relative(splits_relative))
    geometry_manifest_bytes = content(
        _safe_relative(f"{geometry_relative}/geometry_manifest.json")
    )
    split_manifest = json.loads(splits_bytes)
    assignment_relative = _safe_relative(
        str(PurePosixPath(splits_relative).parent / split_manifest["assignment_file"])
    )
    if assignment_relative not in merged:
        raise RuntimeError(
            f"merged staging is missing split assignment: {assignment_relative}"
        )
    assignment_bytes = content(assignment_relative)

    expected_hashes = {
        "dataset_manifest_sha256": _sha256(manifest_bytes),
        "split_manifest_sha256": _sha256(splits_bytes),
        "geometry_manifest_sha256": _sha256(geometry_manifest_bytes),
        "split_assignment_sha256": _sha256(assignment_bytes),
    }
    for field, actual in expected_hashes.items():
        if provenance[field] != actual:
            raise RuntimeError(
                f"{field} mismatch: frozen={provenance[field]} staged={actual}"
            )

    checkpoint_rows = []
    checkpoint_specs: list[tuple[str, str, str]] = []
    if resolve_training_checkpoints:
        training = config["training"]
        for field in (
            "initialize_from",
            "resume_from",
            "resume_progress_from",
            "resume_best_from",
        ):
            relative = training.get(f"{field}_relative")
            if relative is None:
                continue
            checkpoint_specs.append(
                (
                    field,
                    _safe_relative(str(relative)),
                    str(training[f"{field}_sha256"]),
                )
            )
    checkpoint_specs.extend(
        ("extra", relative, expected)
        for relative, expected in normalized_extra
    )
    if len({relative for _, relative, _ in checkpoint_specs}) != len(
        checkpoint_specs
    ):
        raise RuntimeError("duplicate checkpoint path in staging verification")
    for field, relative, expected in checkpoint_specs:
        if relative not in merged:
            raise RuntimeError(
                f"merged staging is missing {field} checkpoint: {relative}"
            )
        actual = _sha256(content(relative))
        if actual != expected:
            raise RuntimeError(
                f"checkpoint hash mismatch for {relative}: "
                f"expected={expected} actual={actual}"
            )
        checkpoint_rows.append(
            {
                "field": field,
                "relative_path": relative,
                "sha256": actual,
                "size": int(merged[relative][1].size or 0),
                "generation": str(merged[relative][1].generation),
            }
        )

    forbidden = sorted(
        relative
        for relative in merged
        if "legacy" in relative.lower()
        or relative.lower().startswith("test/")
        or "/test/" in relative.lower()
    )
    if forbidden:
        raise RuntimeError(f"forbidden staged paths: {forbidden}")

    return {
        "pass": True,
        "base_uri": base_uri,
        "overlay_uris": overlay_uris,
        "source_object_counts": source_counts,
        "merged_object_count": len(merged),
        "merged_bytes": sum(int(blob.size or 0) for _, blob in merged.values()),
        "required_paths": sorted(required | {assignment_relative}),
        "hashes": expected_hashes,
        "checkpoints": checkpoint_rows,
        "forbidden_path_count": 0,
        "config_sha256": _sha256(config_bytes),
        "stage": config["training"]["stage"],
        "synthetic": bool(json.loads(manifest_bytes).get("synthetic", False)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--overlay", action="append", default=[])
    parser.add_argument("--config-relative", required=True)
    parser.add_argument(
        "--manifest-relative",
        default="artifacts/data/dataset_manifest.json",
    )
    parser.add_argument("--splits-relative", default="artifacts/splits.json")
    parser.add_argument("--geometry-relative", default="artifacts/geometry")
    parser.add_argument(
        "--skip-training-checkpoints",
        action="store_true",
        help=(
            "do not require historical training initializers; use only for "
            "post-training analysis with --extra-checkpoint"
        ),
    )
    parser.add_argument(
        "--extra-checkpoint",
        action="append",
        default=[],
        metavar="RELATIVE_PATH=SHA256",
    )
    parser.add_argument("--output")
    args = parser.parse_args()
    report = verify(
        args.base,
        args.overlay,
        args.config_relative,
        args.manifest_relative,
        args.splits_relative,
        args.geometry_relative,
        resolve_training_checkpoints=not args.skip_training_checkpoints,
        extra_checkpoints=[
            _checkpoint_spec(value) for value in args.extra_checkpoint
        ],
    )
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        from pathlib import Path

        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix + ".tmp")
        temporary.write_text(rendered, encoding="utf-8")
        temporary.replace(output)
    print(rendered, end="")


if __name__ == "__main__":
    main()
