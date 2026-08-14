"""Deterministic train-only critic role partition.

The partition splits the 612,482 canonical training events into a generator
bank, a critic-real bank and a critic-monitor holdout.  It must be reproducible
from the event IDs alone, must never touch validation or test, and must be
disjoint and exhaustive -- a leak here would silently invalidate every critic
experiment downstream.
"""

from __future__ import annotations

import pytest

from cbsc_zdc.training.role_partition import (
    DIGEST_PREFIX,
    ROLE_COUNTS,
    RolePartitionError,
    build_role_partition,
    role_digest,
)


def test_exact_counts_are_551234_30624_30624() -> None:
    assert ROLE_COUNTS == {
        "generator_train": 551234,
        "critic_real_train": 30624,
        "critic_monitor_holdout": 30624,
    }
    assert sum(ROLE_COUNTS.values()) == 612482


def test_assignment_is_digest_then_event_id_deterministic() -> None:
    ids = list(range(200))
    counts = {"generator_train": 100, "critic_real_train": 60, "critic_monitor_holdout": 40}
    first = build_role_partition(ids, counts=counts, split_sha256="a" * 64)
    second = build_role_partition(list(reversed(ids)), counts=counts, split_sha256="a" * 64)
    # Input order must not matter: the sort key is (digest, event_id).
    assert first["assignment"] == second["assignment"]
    assert first["assignment_sha256"] == second["assignment_sha256"]

    ordered = sorted(ids, key=lambda e: (role_digest(e), e))
    assert [e for e, r in first["assignment"] if r == "generator_train"] == sorted(ordered[:100])


def test_the_digest_prefix_is_the_declared_seed_string() -> None:
    assert DIGEST_PREFIX == "cbsc-v3-critic-20260813:"
    import hashlib

    expected = hashlib.sha256(f"{DIGEST_PREFIX}12345".encode("utf-8")).hexdigest()
    assert role_digest(12345) == expected


def test_roles_are_disjoint_and_exhaustive_over_train() -> None:
    ids = list(range(300))
    counts = {"generator_train": 150, "critic_real_train": 90, "critic_monitor_holdout": 60}
    result = build_role_partition(ids, counts=counts, split_sha256="b" * 64)
    buckets: dict[str, set[int]] = {role: set() for role in counts}
    for event_id, role in result["assignment"]:
        buckets[role].add(event_id)
    assert sum(len(v) for v in buckets.values()) == len(ids)
    assert set().union(*buckets.values()) == set(ids)
    for a in buckets:
        for b in buckets:
            if a != b:
                assert not buckets[a] & buckets[b]


def test_zero_validation_and_test_ids() -> None:
    ids = list(range(100))
    counts = {"generator_train": 50, "critic_real_train": 30, "critic_monitor_holdout": 20}
    result = build_role_partition(
        ids, counts=counts, split_sha256="c" * 64,
        validation_ids={200, 201}, test_ids={300},
    )
    assert result["validation_ids_present"] == 0
    assert result["test_ids_present"] == 0

    with pytest.raises(RolePartitionError, match="validation"):
        build_role_partition(
            ids + [200], counts={**counts, "generator_train": 51},
            split_sha256="c" * 64, validation_ids={200}, test_ids=set(),
        )
    with pytest.raises(RolePartitionError, match="test"):
        build_role_partition(
            ids + [300], counts={**counts, "generator_train": 51},
            split_sha256="c" * 64, validation_ids=set(), test_ids={300},
        )


def test_a_count_total_that_does_not_match_the_input_is_fatal() -> None:
    with pytest.raises(RolePartitionError, match="counts"):
        build_role_partition(
            list(range(10)),
            counts={"generator_train": 5, "critic_real_train": 3, "critic_monitor_holdout": 3},
            split_sha256="d" * 64,
        )


def test_duplicate_event_ids_are_fatal() -> None:
    with pytest.raises(RolePartitionError, match="duplicate"):
        build_role_partition(
            [1, 2, 2, 3],
            counts={"generator_train": 2, "critic_real_train": 1, "critic_monitor_holdout": 1},
            split_sha256="e" * 64,
        )


def test_changed_split_hash_invalidates_manifest() -> None:
    ids = list(range(50))
    counts = {"generator_train": 25, "critic_real_train": 15, "critic_monitor_holdout": 10}
    a = build_role_partition(ids, counts=counts, split_sha256="1" * 64)
    b = build_role_partition(ids, counts=counts, split_sha256="2" * 64)
    # The role assignment itself is a function of the IDs only, but the manifest
    # is bound to the split it was derived from so a changed split cannot be
    # silently reused.
    assert a["assignment"] == b["assignment"]
    assert a["input_split_sha256"] != b["input_split_sha256"]
    assert a["manifest_sha256"] != b["manifest_sha256"]


def test_manifest_records_algorithm_and_counts() -> None:
    ids = list(range(20))
    counts = {"generator_train": 10, "critic_real_train": 6, "critic_monitor_holdout": 4}
    result = build_role_partition(ids, counts=counts, split_sha256="f" * 64)
    assert result["algorithm"] == "sha256(prefix + decimal_event_id), sort by (digest, event_id)"
    assert result["digest_prefix"] == DIGEST_PREFIX
    assert result["counts"] == counts
    assert result["allowed_parent_split"] == "train"
