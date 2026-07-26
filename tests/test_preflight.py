from pathlib import Path

import yaml

from cbsc_zdc.data.audit import audit_dataset
from cbsc_zdc.data.split import create_split
from cbsc_zdc.data.synthetic import create_synthetic_dataset
from cbsc_zdc.preflight import validate_frozen_artifacts
from cbsc_zdc.utils import load_json, sha256_file


def test_frozen_artifact_preflight_verifies_hash_chain(tmp_path: Path):
    created = create_synthetic_dataset(
        tmp_path, n_events=192, n_layers=4, nodes_per_layer=4, shard_size=64, seed=7
    )
    split_path = tmp_path / "splits.json"
    create_split(created["manifest"], split_path, group_by="event_hash", seed=11)
    audit_path = tmp_path / "train_audit.json"
    audit_dataset(
        created["manifest"], split_path, "train", audit_path, (0.0, 300.0)
    )

    config = yaml.safe_load(
        (Path(__file__).parents[1] / "configs/templates/train_full_0_300_raw.yaml")
        .read_text(encoding="utf-8")
    )
    geometry_path = tmp_path / "geometry"
    geometry_manifest_path = geometry_path / "geometry_manifest.json"
    geometry_manifest = load_json(geometry_manifest_path)
    split = load_json(split_path)
    config["data"]["manifest"] = str(Path(created["manifest"]).resolve())
    config["data"]["splits"] = str(split_path.resolve())
    config["geometry"].update(
        {
            "path": str(geometry_path.resolve()),
            "n_nodes": created["n_nodes"],
            "n_layers": 4,
            "geometry_hash": geometry_manifest["geometry_hash"],
        }
    )
    config["provenance"] = {
        "geometry_manifest_sha256": sha256_file(geometry_manifest_path),
        "dataset_manifest_sha256": sha256_file(created["manifest"]),
        "split_manifest_sha256": sha256_file(split_path),
        "dataset_geometry_hash": geometry_manifest["geometry_hash"],
        "split_assignment_sha256": split["assignment_sha256"],
    }

    report = validate_frozen_artifacts(config, verify_shards=True)
    assert report["pass"]
    assert report["verified_shards"] == 3
    assert all(count > 0 for count in report["selection_counts"].values())
