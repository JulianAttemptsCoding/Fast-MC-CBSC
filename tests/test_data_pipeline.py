from pathlib import Path
import numpy as np

from cbsc_zdc.data.dataset import ShardedSparseDataset
from cbsc_zdc.data.split import create_split
from cbsc_zdc.data.synthetic import create_synthetic_dataset
from cbsc_zdc.utils import load_json


def test_synthetic_dataset_and_group_split(tmp_path: Path):
    result = create_synthetic_dataset(tmp_path, n_events=192, n_layers=4, nodes_per_layer=9, shard_size=64, seed=9)
    split_path = tmp_path / "splits.json"
    report = create_split(result["manifest"], split_path, seed=11, group_by="source_group")
    assert sum(report["counts"].values()) == 192
    assert all(value > 0 for value in report["counts"].values())

    assignment_file = split_path.parent / load_json(split_path)["assignment_file"]
    assignments = np.load(assignment_file)["split_code"]
    base = ShardedSparseDataset(result["manifest"])
    groups = []
    for shard_i in range(len(base.shards)):
        groups.append(base._load_shard(shard_i)["source_group"])
    groups = np.concatenate(groups)
    for group in np.unique(groups):
        assert np.unique(assignments[groups == group]).size == 1

    train = ShardedSparseDataset(result["manifest"], split_path, "train", (0, 300), result["n_nodes"])
    item = train[0]
    assert item["cell_energy_gev"].shape == (result["n_nodes"],)
    assert item["p4_total_gev"].shape == (4,)
