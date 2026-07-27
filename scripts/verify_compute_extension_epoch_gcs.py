from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlparse

import torch
import yaml
from google.cloud import storage

try:
    from scripts.verify_component_stage_output import (
        _assert_cross_epoch_visual_contract,
        _assert_invariants,
        _assert_weighted_history,
        _optimizer_steps,
        _visualization_population_metrics,
    )
except ModuleNotFoundError:
    from verify_component_stage_output import (
        _assert_cross_epoch_visual_contract,
        _assert_invariants,
        _assert_weighted_history,
        _optimizer_steps,
        _visualization_population_metrics,
    )


T4_TOTAL_MEMORY_BYTES = 15_655_829_504


def _parse_gs(uri: str) -> tuple[str, str]:
    parsed = urlparse(uri)
    if parsed.scheme != "gs" or not parsed.netloc:
        raise ValueError(f"expected gs:// URI, got {uri}")
    return parsed.netloc, parsed.path.lstrip("/").rstrip("/")


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _finite_tensors(value: Any) -> tuple[int, list[str]]:
    count = 0
    failures: list[str] = []

    def visit(item: Any, path: str) -> None:
        nonlocal count
        if torch.is_tensor(item):
            count += 1
            if not torch.isfinite(item.detach().cpu()).all():
                failures.append(path)
        elif isinstance(item, dict):
            for key, child in item.items():
                visit(child, f"{path}.{key}")
        elif isinstance(item, (list, tuple)):
            for index, child in enumerate(item):
                visit(child, f"{path}[{index}]")

    visit(value, "checkpoint")
    return count, failures


def _checkpoint(content: bytes) -> dict[str, Any]:
    return torch.load(io.BytesIO(content), map_location="cpu", weights_only=False)


def verify(
    project: str,
    output_uri: str,
    input_uri: str,
    parent_output_uri: str,
    name: str,
    expected_epoch: int,
    history_start_epoch: int,
    expected_training_epochs: int,
    parent_epoch: int,
    expected_parent_best_sha256: str,
    expected_parent_last_sha256: str,
    expected_batch_size: int,
    expected_gradient_accumulation: int,
    expected_selection_sha256: str,
) -> dict[str, Any]:
    if expected_epoch <= parent_epoch:
        raise ValueError("expected epoch must follow parent epoch")
    if history_start_epoch != parent_epoch + 1:
        raise ValueError("history must start immediately after parent epoch")

    client = storage.Client(project=project)
    bucket_name, output_prefix = _parse_gs(output_uri)
    input_bucket_name, input_prefix = _parse_gs(input_uri)
    parent_bucket_name, parent_prefix = _parse_gs(parent_output_uri)
    if len({bucket_name, input_bucket_name, parent_bucket_name}) != 1:
        raise ValueError("stream verifier expects one GCS bucket")
    bucket = client.bucket(bucket_name)

    failure_blob = bucket.blob(f"{output_prefix}/vertex_failure.json")
    if failure_blob.exists(client):
        raise RuntimeError("vertex_failure.json exists")

    snapshot_prefix = f"{output_prefix}/progress/epoch_{expected_epoch:04d}/"
    blobs = list(client.list_blobs(bucket, prefix=snapshot_prefix))
    if not blobs:
        raise RuntimeError("immutable epoch snapshot is missing")
    by_relative = {
        blob.name[len(snapshot_prefix) :]: blob
        for blob in blobs
        if blob.name[len(snapshot_prefix) :]
    }
    if len(by_relative) != len(blobs):
        raise RuntimeError("duplicate or empty snapshot object")

    required = {
        "checkpoints/best.pt",
        "checkpoints/last.pt",
        "environment.json",
        "logs/history.csv",
        f"reports/invariant_epoch_{expected_epoch:04d}.json",
        "reports/preflight.json",
        f"reports/progress_epoch_{expected_epoch:04d}.json",
        f"reports/visualization/epoch_{expected_epoch:04d}.json",
        "reports/visualization/geometry.json",
        "reports/visualization/manifest.json",
        "resolved_config.json",
        "runtime_config.yaml",
        "staged_input_manifest.json",
    }
    missing = sorted(required - set(by_relative))
    if missing:
        raise RuntimeError(f"snapshot missing required objects: {missing}")

    content_cache: dict[str, bytes] = {}

    def content(relative: str) -> bytes:
        if relative not in content_cache:
            content_cache[relative] = by_relative[relative].download_as_bytes()
        return content_cache[relative]

    object_hashes = {
        relative: _sha256(content(relative)) for relative in sorted(by_relative)
    }
    best_bytes = content_cache.pop("checkpoints/best.pt")
    last_bytes = content_cache.pop("checkpoints/last.pt")
    best_hash = _sha256(best_bytes)
    last_hash = _sha256(last_bytes)
    best = _checkpoint(best_bytes)
    last = _checkpoint(last_bytes)
    del best_bytes, last_bytes

    parent_best_relative = (
        f"checkpoints/{name}_best_epoch{parent_epoch}.pt"
    )
    parent_last_relative = (
        f"checkpoints/{name}_last_epoch{parent_epoch}.pt"
    )
    parent_best_bytes = bucket.blob(
        f"{input_prefix}/{parent_best_relative}"
    ).download_as_bytes()
    parent_last_bytes = bucket.blob(
        f"{input_prefix}/{parent_last_relative}"
    ).download_as_bytes()
    if _sha256(parent_best_bytes) != expected_parent_best_sha256:
        raise RuntimeError("parent best checkpoint SHA-256 mismatch")
    if _sha256(parent_last_bytes) != expected_parent_last_sha256:
        raise RuntimeError("parent last checkpoint SHA-256 mismatch")
    parent_best = _checkpoint(parent_best_bytes)
    parent_last = _checkpoint(parent_last_bytes)
    del parent_best_bytes, parent_last_bytes

    for label, checkpoint in (
        ("parent_best", parent_best),
        ("parent_last", parent_last),
        ("best", best),
        ("last", last),
    ):
        tensor_count, failures = _finite_tensors(checkpoint)
        if tensor_count == 0 or failures:
            raise RuntimeError(f"{label} nonfinite tensors: {failures}")
    assert parent_best["stage"] == parent_last["stage"] == "joint"
    assert best["stage"] == last["stage"] == "joint"
    assert int(parent_last["epoch"]) == parent_epoch
    assert int(last["epoch"]) == expected_epoch
    assert parent_last.get("rng_state", {}).get("torch") is not None
    assert parent_last.get("rng_state", {}).get("cuda") is not None
    assert last.get("rng_state", {}).get("torch") is not None
    assert last.get("rng_state", {}).get("cuda") is not None
    changed_tensors = [
        key
        for key, value in parent_last["model_state"].items()
        if not torch.equal(
            value.detach().cpu(), last["model_state"][key].detach().cpu()
        )
    ]
    assert changed_tensors

    history = list(
        csv.DictReader(io.StringIO(content("logs/history.csv").decode("utf-8")))
    )
    assert [int(row["epoch"]) for row in history] == list(
        range(history_start_epoch, expected_epoch + 1)
    )
    runtime = yaml.safe_load(content("runtime_config.yaml"))
    training = runtime["training"]
    assert training["stage"] == "joint"
    assert training["amp"] is False
    assert int(training["epochs"]) == expected_training_epochs
    assert int(training["batch_size"]) == expected_batch_size
    assert (
        int(training["gradient_accumulation"])
        == expected_gradient_accumulation
    )
    assert int(training["checkpoint_interval_updates"]) == 50
    assert training["resume_from_sha256"] == expected_parent_last_sha256
    assert training["resume_best_from_sha256"] == expected_parent_best_sha256
    assert training["restart_scheduler_on_resume"] is True
    assert int(runtime["viability"]["test_events_used"]) == 0
    _assert_weighted_history(history, "joint", runtime["loss_weights"])
    for row in history:
        for field, value in row.items():
            if field in {"stage", "cuda_peak_memory_bytes"} or not value:
                continue
            assert math.isfinite(float(value)), (field, value)

    preflight = json.loads(content("reports/preflight.json"))
    assert preflight["pass"] is True
    assert preflight["synthetic"] is False
    assert int(preflight["verified_shards"]) == 187
    assert preflight["selection_counts"] == {
        "train": 26624,
        "validation": 4096,
        "test": 0,
    }
    staged = json.loads(content("staged_input_manifest.json"))
    assert len(staged) == 212
    staged_paths = [row["relative_path"] for row in staged]
    assert len(staged_paths) == len(set(staged_paths))
    assert not any("legacy" in path.lower() for path in staged_paths)
    assert not any(
        part.lower() == "test"
        for path in staged_paths
        for part in PurePosixPath(path).parts
    )

    batches_per_epoch = 26624 // expected_batch_size
    updates_per_epoch = math.ceil(
        batches_per_epoch / expected_gradient_accumulation
    )
    assert _optimizer_steps(last) == {
        updates_per_epoch * (expected_epoch + 1)
    }
    assert int(last["scheduler_state"]["last_epoch"]) == updates_per_epoch * (
        expected_epoch - history_start_epoch + 1
    )
    validation_losses = [
        float(parent_best["best_metric"]),
        *[float(row["validation_loss"]) for row in history],
    ]
    selected_validation = min(validation_losses)
    assert math.isclose(
        float(best["best_metric"]), selected_validation, rel_tol=0, abs_tol=1e-12
    )
    assert math.isclose(
        float(last["best_metric"]), selected_validation, rel_tol=0, abs_tol=1e-12
    )

    progress = json.loads(
        content(f"reports/progress_epoch_{expected_epoch:04d}.json")
    )
    assert int(progress["epoch"]) == expected_epoch
    assert progress["best_checkpoint_sha256"] == best_hash
    assert progress["last_checkpoint_sha256"] == last_hash

    tolerance = float(runtime["evaluation"]["closure_tolerance_gev"])
    invariants = json.loads(
        content(f"reports/invariant_epoch_{expected_epoch:04d}.json")
    )
    _assert_invariants(invariants, tolerance)
    visualization_bytes = content(
        f"reports/visualization/epoch_{expected_epoch:04d}.json"
    )
    visualization = json.loads(visualization_bytes)
    assert visualization["schema_version"] == 1
    assert visualization["split"] == "validation"
    assert visualization["synthetic_source"] is False
    assert visualization["stage"] == "joint"
    assert int(visualization["epoch"]) == expected_epoch
    assert int(visualization["sample_count"]) == 50
    assert int(visualization["draws_per_condition"]) == 5
    assert int(visualization["profile_steps"]) == 8
    assert int(visualization["share_steps"]) == 8
    assert visualization["checkpoint_sha256"] == last_hash
    assert visualization["selection_sha256"] == expected_selection_sha256
    assert len(visualization["groups"]) == 50
    assert all(len(group["p4_total_gev"]) == 4 for group in visualization["groups"])
    assert all(len(group["fast_mc"]) == 5 for group in visualization["groups"])
    qa = visualization["qa"]
    assert qa["pass"] is True
    assert int(qa["test_events_used"]) == 0
    assert int(qa["groups_with_exact_draw_count"]) == 50
    for field in (
        "truth_nonfinite",
        "generated_nonfinite",
        "truth_negative",
        "generated_negative",
    ):
        assert int(qa[field]) == 0
    _assert_invariants(qa["invariants"], tolerance)
    manifest = json.loads(content("reports/visualization/manifest.json"))
    assert int(manifest["latest_epoch"]) == expected_epoch
    manifest_rows = {int(row["epoch"]): row for row in manifest["epochs"]}
    assert manifest_rows[expected_epoch]["sha256"] == _sha256(
        visualization_bytes
    )

    parent_visualization = json.loads(
        bucket.blob(
            f"{parent_prefix}/progress/epoch_{parent_epoch:04d}/"
            f"reports/visualization/epoch_{parent_epoch:04d}.json"
        ).download_as_bytes()
    )
    cross_epoch = _assert_cross_epoch_visual_contract(
        parent_visualization, visualization
    )
    population = _visualization_population_metrics(visualization)
    trend = {
        key: float(value)
        for key, value in visualization["aggregate"]["trend"].items()
    }
    assert all(math.isfinite(value) for value in trend.values())

    last_row = history[-1]
    peak_bytes = int(float(last_row["cuda_peak_memory_bytes"]))
    headroom_fraction = 1.0 - peak_bytes / T4_TOTAL_MEMORY_BYTES
    assert headroom_fraction >= 0.15
    parent_validation = float(parent_best["best_metric"])
    current_validation = float(last_row["validation_loss"])
    relative_change = (parent_validation - current_validation) / parent_validation

    return {
        "pass": True,
        "terminal": False,
        "name": name,
        "stage": "joint",
        "epoch": expected_epoch,
        "snapshot": {
            "uri": f"{output_uri}/progress/epoch_{expected_epoch:04d}",
            "object_count": len(by_relative),
            "bytes": sum(int(blob.size or 0) for blob in blobs),
            "hashes": object_hashes,
        },
        "history": history,
        "checkpoint": {
            "best_sha256": best_hash,
            "last_sha256": last_hash,
            "best_epoch": int(best["epoch"]),
            "last_epoch": int(last["epoch"]),
            "last_optimizer_steps": sorted(_optimizer_steps(last)),
            "last_scheduler_step": int(last["scheduler_state"]["last_epoch"]),
            "changed_tensor_count": len(changed_tensors),
            "parent_best_sha256": expected_parent_best_sha256,
            "parent_last_sha256": expected_parent_last_sha256,
        },
        "validation": {
            "parent_best": parent_validation,
            "current": current_validation,
            "selected_best": selected_validation,
            "relative_improvement_from_parent": relative_change,
            "improved_from_parent": current_validation < parent_validation,
        },
        "invariants": invariants,
        "visualization": {
            "sha256": _sha256(visualization_bytes),
            "selection_sha256": visualization["selection_sha256"],
            "cross_epoch_contract": cross_epoch,
            "population": population,
            "trend": trend,
            "qa": qa,
        },
        "resources": {
            "peak_memory_bytes": peak_bytes,
            "t4_total_memory_bytes": T4_TOTAL_MEMORY_BYTES,
            "headroom_fraction": headroom_fraction,
        },
        "test_events_used": 0,
        "scientific_status": (
            "validation-only immutable epoch; not physics validation"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--output-uri", required=True)
    parser.add_argument("--input-uri", required=True)
    parser.add_argument("--parent-output-uri", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--expected-epoch", type=int, required=True)
    parser.add_argument("--history-start-epoch", type=int, required=True)
    parser.add_argument("--expected-training-epochs", type=int, required=True)
    parser.add_argument("--parent-epoch", type=int, required=True)
    parser.add_argument("--expected-parent-best-sha256", required=True)
    parser.add_argument("--expected-parent-last-sha256", required=True)
    parser.add_argument("--expected-batch-size", type=int, required=True)
    parser.add_argument("--expected-gradient-accumulation", type=int, required=True)
    parser.add_argument("--expected-selection-sha256", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    report = verify(
        project=args.project,
        output_uri=args.output_uri,
        input_uri=args.input_uri,
        parent_output_uri=args.parent_output_uri,
        name=args.name,
        expected_epoch=args.expected_epoch,
        history_start_epoch=args.history_start_epoch,
        expected_training_epochs=args.expected_training_epochs,
        parent_epoch=args.parent_epoch,
        expected_parent_best_sha256=args.expected_parent_best_sha256,
        expected_parent_last_sha256=args.expected_parent_last_sha256,
        expected_batch_size=args.expected_batch_size,
        expected_gradient_accumulation=args.expected_gradient_accumulation,
        expected_selection_sha256=args.expected_selection_sha256,
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
