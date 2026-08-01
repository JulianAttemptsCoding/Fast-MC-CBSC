"""The shard cache decides how often bytes are rebuilt, never which bytes.

Decompressing one 50 MB production shard costs ~225 ms and verifying its
SHA-256 another ~25 ms. The cache held four shards against a corpus of 187, so
a shuffled sampler missed on nearly every sample and a batch of six paid that
six times -- the measured 35.5 min/epoch on the RTX 4090, with the GPU idle.

Raising the cache is only admissible mid-comparison if it provably changes no
sample and drops no verification. These tests are that proof.
"""

from pathlib import Path

import numpy as np
import pytest
import torch

from cbsc_zdc.data.dataset import DEFAULT_SHARD_CACHE, ShardedSparseDataset
from cbsc_zdc.data.synthetic import create_synthetic_dataset


def _corpus(tmp_path: Path):
    return create_synthetic_dataset(
        tmp_path, n_events=192, n_layers=4, nodes_per_layer=9, shard_size=16, seed=5
    )


def _drain(dataset: ShardedSparseDataset) -> list[dict[str, torch.Tensor]]:
    """Read every item in an order that thrashes a small cache."""
    order = list(range(len(dataset)))[::-1]
    return [dataset[i] for i in order]


def test_a_larger_cache_returns_byte_identical_samples(tmp_path: Path) -> None:
    """The whole justification for the change: same bytes, fewer rebuilds."""
    result = _corpus(tmp_path)
    small = ShardedSparseDataset(result["manifest"], shard_cache_size=1)
    large = ShardedSparseDataset(result["manifest"], shard_cache_size=0)
    assert len(small.shards) >= 8, "need enough shards for the cache to matter"

    for lhs, rhs in zip(_drain(small), _drain(large)):
        assert lhs.keys() == rhs.keys()
        for key in lhs:
            assert torch.equal(lhs[key], rhs[key]), key
            assert lhs[key].dtype == rhs[key].dtype, key


def test_an_unbounded_cache_holds_every_shard(tmp_path: Path) -> None:
    result = _corpus(tmp_path)
    dataset = ShardedSparseDataset(result["manifest"], shard_cache_size=0)
    _drain(dataset)
    assert len(dataset._shard_cache) == len(dataset.shards)


def test_a_bounded_cache_never_exceeds_its_size(tmp_path: Path) -> None:
    """Unbounded is opt-in; a bounded cache must stay bounded or a worker on a
    smaller box trades a slow epoch for an OOM kill."""
    result = _corpus(tmp_path)
    dataset = ShardedSparseDataset(result["manifest"], shard_cache_size=3)
    _drain(dataset)
    assert len(dataset._shard_cache) == 3


def test_the_default_cache_size_is_unchanged(tmp_path: Path) -> None:
    """Call sites that pass nothing must behave exactly as before, so this
    change cannot alter any run that did not ask for it."""
    assert DEFAULT_SHARD_CACHE == 4
    result = _corpus(tmp_path)
    dataset = ShardedSparseDataset(result["manifest"])
    _drain(dataset)
    assert len(dataset._shard_cache) == DEFAULT_SHARD_CACHE


def test_the_cache_size_can_come_from_the_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The dataset is built deep inside the trainer from a frozen config. An
    environment variable lets a run opt in without hand-editing a frozen config
    or changing any config hash."""
    monkeypatch.setenv("CBSC_ZDC_SHARD_CACHE", "2")
    result = _corpus(tmp_path)
    dataset = ShardedSparseDataset(result["manifest"])
    _drain(dataset)
    assert len(dataset._shard_cache) == 2


def test_an_explicit_size_beats_the_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CBSC_ZDC_SHARD_CACHE", "2")
    result = _corpus(tmp_path)
    dataset = ShardedSparseDataset(result["manifest"], shard_cache_size=5)
    _drain(dataset)
    assert len(dataset._shard_cache) == 5


def test_a_corrupt_shard_is_still_caught_with_a_large_cache(tmp_path: Path) -> None:
    """A bigger cache means each shard is verified once per process instead of
    thousands of times -- but never zero times. Every shard's bytes are still
    hashed before anything reads them."""
    result = _corpus(tmp_path)
    dataset = ShardedSparseDataset(result["manifest"], shard_cache_size=0)
    target = Path(dataset.root) / dataset.shards[-1]["path"]
    payload = bytearray(target.read_bytes())
    payload[-1] ^= 0xFF
    target.write_bytes(bytes(payload))

    with pytest.raises(RuntimeError, match="shard hash mismatch"):
        _drain(dataset)


def test_a_cached_shard_is_not_rehashed(tmp_path: Path, monkeypatch) -> None:
    """The saving is real: repeated access must not re-read or re-hash."""
    result = _corpus(tmp_path)
    dataset = ShardedSparseDataset(result["manifest"], shard_cache_size=0)

    calls: list[str] = []
    import cbsc_zdc.data.dataset as module

    original = module.sha256_file
    monkeypatch.setattr(
        module, "sha256_file", lambda p: calls.append(str(p)) or original(p)
    )
    _drain(dataset)
    first = len(calls)
    _drain(dataset)

    assert first == len(dataset.shards)
    assert len(calls) == first, "second pass re-hashed a cached shard"


def test_samples_survive_eviction_and_reload(tmp_path: Path) -> None:
    """Evicting and reloading a shard must reproduce the sample exactly, or the
    cache size would silently become a scientific variable."""
    result = _corpus(tmp_path)
    dataset = ShardedSparseDataset(result["manifest"], shard_cache_size=1)
    first = dataset[0]
    _drain(dataset)  # evicts shard 0 many times over
    again = dataset[0]
    for key in first:
        assert torch.equal(first[key], again[key]), key


def test_the_dense_target_is_unaffected_by_cache_size(tmp_path: Path) -> None:
    """The scatter into the dense vector reads from the cached arrays; a shared
    cached array must not be mutated by a previous __getitem__."""
    result = _corpus(tmp_path)
    dataset = ShardedSparseDataset(result["manifest"], shard_cache_size=0)
    baseline = dataset[3]["cell_energy_gev"].clone()
    for _ in range(4):
        dataset[3]
    assert torch.equal(dataset[3]["cell_energy_gev"], baseline)
    assert np.isfinite(baseline.numpy()).all()
