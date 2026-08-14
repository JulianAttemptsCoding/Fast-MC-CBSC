"""Bounded fake-sample replay for critic training."""

from __future__ import annotations

import pytest
import torch

from cbsc_zdc.training.replay import (
    DENSE_STORAGE_LIMIT_BYTES,
    FINAL_CAPACITY_EVENTS,
    PILOT_CAPACITY_EVENTS,
    ReplayBuffer,
    ReplayError,
    ReplayItem,
    age_distribution,
    largest_remainder_composition,
)


def item(event_id: int, *, anchor: bool = False, step: int = 0, size: int = 4) -> ReplayItem:
    return ReplayItem(
        event_id=event_id,
        payload=torch.zeros(size),
        stage="D1",
        stratum="50-75GeV/visible",
        generator_step=step,
        generator_epoch=step // 10,
        generator_checkpoint_sha256="a" * 64,
        sampler_version="v3-1",
        seed=1234,
        is_anchor=anchor,
    )


def test_pilot_and_final_capacity_are_enforced() -> None:
    assert PILOT_CAPACITY_EVENTS == 8192
    assert FINAL_CAPACITY_EVENTS == 65536
    buffer = ReplayBuffer(capacity_events=4)
    for i in range(10):
        buffer.add(item(i))
    assert len(buffer.recent) == 4
    # FIFO: the oldest are evicted, the newest retained
    assert [i.event_id for i in buffer.recent] == [6, 7, 8, 9]


def test_batch4_composition_is_two_fresh_one_recent_one_anchor() -> None:
    assert largest_remainder_composition(4) == {"fresh": 2, "recent": 1, "anchor": 1}
    buffer = ReplayBuffer(capacity_events=64)
    for i in range(10):
        buffer.add(item(i, step=i))
    buffer.set_anchors([item(100 + i, anchor=True) for i in range(4)])
    drawn = buffer.sample(4, fresh=[item(200 + i, step=50) for i in range(4)])
    assert drawn["composition"] == {"fresh": 2, "recent": 1, "anchor": 1}
    assert len(drawn["items"]) == 4
    assert drawn["warmup"] is None


def test_composition_totals_are_exact_for_other_batch_sizes() -> None:
    for size in (1, 2, 3, 4, 8, 16, 7, 13):
        composition = largest_remainder_composition(size)
        assert sum(composition.values()) == size
        assert all(v >= 0 for v in composition.values())


def test_warmup_replaces_missing_history_with_fresh_and_logs_it() -> None:
    buffer = ReplayBuffer(capacity_events=64)
    fresh = [item(200 + i, step=0) for i in range(4)]
    drawn = buffer.sample(4, fresh=fresh)  # no history, no anchors yet
    assert len(drawn["items"]) == 4
    assert drawn["composition"]["fresh"] == 4
    assert drawn["warmup"] is not None
    assert drawn["warmup"]["substituted_fresh"] == 2
    assert buffer.warmup_log


def test_recent_fifo_excludes_anchor_pool() -> None:
    buffer = ReplayBuffer(capacity_events=64)
    for i in range(6):
        buffer.add(item(i))
    buffer.set_anchors([item(100, anchor=True)])
    assert all(not i.is_anchor for i in buffer.recent)
    with pytest.raises(ReplayError, match="anchors are installed"):
        buffer.add(item(101, anchor=True))


def test_no_validation_or_test_ids_can_be_inserted() -> None:
    buffer = ReplayBuffer(capacity_events=16, allowed_event_ids=frozenset({1, 2, 3}))
    buffer.add(item(1))
    with pytest.raises(ReplayError, match="train-only replay population"):
        buffer.add(item(999))
    with pytest.raises(ReplayError, match="train-only replay population"):
        buffer.set_anchors([item(999, anchor=True)])
    with pytest.raises(ReplayError, match="train-only replay population"):
        buffer.sample(2, fresh=[item(999)])


def test_anchor_pool_may_not_mix_checkpoints() -> None:
    buffer = ReplayBuffer(capacity_events=16)
    a, b = item(1, anchor=True), item(2, anchor=True)
    b.generator_checkpoint_sha256 = "b" * 64
    with pytest.raises(ReplayError, match="mixes"):
        buffer.set_anchors([a, b])


def test_strata_and_checkpoint_hash_are_retained() -> None:
    buffer = ReplayBuffer(capacity_events=16)
    buffer.add(item(1, step=7))
    manifest = buffer.manifest()
    assert manifest["recent_events"] == 1
    assert len(manifest["content_sha256"]) == 64
    stored = buffer.recent[0]
    assert stored.stratum == "50-75GeV/visible"
    assert stored.generator_checkpoint_sha256 == "a" * 64
    assert stored.sampler_version == "v3-1"


def test_dense_over_1gib_selects_sparse_csr_without_capacity_change() -> None:
    assert DENSE_STORAGE_LIMIT_BYTES == 1_073_741_824
    buffer = ReplayBuffer(capacity_events=FINAL_CAPACITY_EVENTS)
    # 6790 float32 per event x 65536 events is far above the byte limit
    buffer.add(item(1, size=6790))
    assert buffer.storage_mode == "sparse_csr"
    assert buffer.capacity_events == FINAL_CAPACITY_EVENTS  # never silently shrunk


def test_small_payloads_stay_dense() -> None:
    buffer = ReplayBuffer(capacity_events=8)
    buffer.add(item(1, size=4))
    assert buffer.storage_mode == "dense"


def test_serialize_restore_preserves_content_rng_and_next_sample() -> None:
    buffer = ReplayBuffer(capacity_events=32)
    for i in range(8):
        buffer.add(item(i, step=i))
    buffer.set_anchors([item(100 + i, anchor=True) for i in range(3)])
    fresh = [item(200 + i, step=20) for i in range(4)]
    state = buffer.state_dict()
    first = buffer.sample(4, fresh=fresh)

    restored = ReplayBuffer(capacity_events=32)
    restored.load_state_dict(state)
    second = restored.sample(4, fresh=fresh)

    assert restored.manifest()["content_sha256"] == state["manifest"]["content_sha256"]
    assert [i.event_id for i in first["items"]] == [i.event_id for i in second["items"]]


def test_age_distribution_reports_replay_staleness() -> None:
    items = [item(i, step=i) for i in range(5)]
    ages = age_distribution(items, current_step=10)
    assert ages["count"] == 5
    assert ages["min"] == 6.0
    assert ages["max"] == 10.0
    assert age_distribution([], 3) == {"count": 0}
