from __future__ import annotations

import numpy as np
import pytest

from scripts.export_external_validation_bank import dense_pairs_to_sparse_arrays
from scripts.run_external_accepted_best_metrics import (
    monitoring_corpus_summary,
    paired_stratified_partitions,
)


def test_dense_pairs_export_balanced_pair_grouped_sparse_contract():
    truth = np.asarray([[1.0, 0.0, 2.0], [0.0, 3.0, 0.0]], dtype=np.float32)
    generated = np.asarray([[0.5, 0.0, 2.5], [0.0, 0.0, 4.0]], dtype=np.float32)
    p4 = np.asarray([[10.0, 0.0, 0.0, 9.9], [20.0, 0.0, 0.0, 19.9]])
    out = dense_pairs_to_sparse_arrays(truth, generated, p4, np.asarray([101, 202]))

    assert out["event_ptr"].tolist() == [0, 2, 3, 5, 6]
    assert out["label"].tolist() == [1, 1, 0, 0]
    assert out["pair_id"].tolist() == [101, 202, 101, 202]
    assert out["cbsc_source_split_code"].tolist() == [1, 1, 1, 1]
    assert out["p4_total_gev"].shape == (4, 4)
    assert out["cell_energy_gev"].sum() == pytest.approx(13.0)


def test_dense_pairs_export_rejects_duplicate_pair_ids():
    deposits = np.ones((2, 3), dtype=np.float32)
    p4 = np.ones((2, 4), dtype=np.float32)
    with pytest.raises(ValueError, match="not unique"):
        dense_pairs_to_sparse_arrays(deposits, deposits, p4, np.asarray([7, 7]))


def test_paired_partition_never_splits_a_condition_and_stays_balanced():
    pair = np.concatenate([np.arange(80), np.arange(80)])
    kinetic = np.linspace(50.0, 249.0, 80)
    energy = kinetic + 0.93956542052
    momentum = np.sqrt(energy**2 - 0.93956542052**2)
    p4_once = np.column_stack([energy, np.zeros(80), np.zeros(80), momentum])
    p4 = np.concatenate([p4_once, p4_once])
    partition = paired_stratified_partitions(pair, p4, seed=17)

    for pair_id in range(80):
        assert len(set(partition[pair == pair_id])) == 1
    for code in (0, 1, 2):
        # First half is Geant4 and second half is Fast-MC in the bank contract.
        assert np.sum(partition[:80] == code) == np.sum(partition[80:] == code)


def test_paired_partition_rejects_mismatched_pair_conditions():
    pair = np.asarray([1, 2, 1, 2])
    p4 = np.asarray(
        [
            [100.0, 0.0, 0.0, 99.0],
            [120.0, 0.0, 0.0, 119.0],
            [101.0, 0.0, 0.0, 100.0],
            [120.0, 0.0, 0.0, 119.0],
        ]
    )
    with pytest.raises(ValueError, match="identical incident"):
        paired_stratified_partitions(pair, p4, seed=3)


def test_monitor_holdout_is_never_labeled_as_cbsc_test():
    summary = {
        "n_events": 20,
        "partition_counts": {"train": 14, "validation": 3, "test": 3},
    }
    normalized = monitoring_corpus_summary(summary)
    assert normalized["partition_counts"] == {
        "train": 14,
        "validation": 3,
        "monitoring_holdout": 3,
    }
    assert summary["partition_counts"]["test"] == 3
