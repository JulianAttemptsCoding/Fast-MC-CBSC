"""Deterministic train-only role partition for the v3 critic campaign.

The canonical 612,482 training events are split into three disjoint roles:

======================== ========= ==========================================
role                     events    use
======================== ========= ==========================================
``generator_train``        551,234 the generator's training bank
``critic_real_train``       30,624 real samples shown to the live critic
``critic_monitor_holdout``  30,624 disjoint bank for the non-gradient monitor
======================== ========= ==========================================

Assignment is a pure function of the event IDs: each ID is hashed with a fixed
prefix and the population is sorted by ``(digest, event_id)``, so the partition
is reproducible on any host and independent of input order.

Because the generator's bank is ~10% smaller than the full training split,
**every critic experiment requires a no-critic control trained on the identical
generator partition.**  Comparing a critic run against a full-split baseline
would confound the critic with the data reduction.

Validation and test IDs may never appear.  That is enforced here rather than
left to the caller.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Sequence
from typing import Any

DIGEST_PREFIX = "cbsc-v3-critic-20260813:"

ROLE_COUNTS: dict[str, int] = {
    "generator_train": 551234,
    "critic_real_train": 30624,
    "critic_monitor_holdout": 30624,
}

# Roles are filled in this order from the sorted population.
ROLE_ORDER: tuple[str, ...] = (
    "generator_train",
    "critic_real_train",
    "critic_monitor_holdout",
)

ALGORITHM = "sha256(prefix + decimal_event_id), sort by (digest, event_id)"


class RolePartitionError(ValueError):
    """Raised when a partition would be unsound rather than merely unusual."""


def role_digest(event_id: int) -> str:
    """Digest used to order one event."""
    return hashlib.sha256(f"{DIGEST_PREFIX}{int(event_id)}".encode("utf-8")).hexdigest()


def build_role_partition(
    event_ids: Iterable[int],
    *,
    counts: dict[str, int] | None = None,
    split_sha256: str,
    validation_ids: Iterable[int] | None = None,
    test_ids: Iterable[int] | None = None,
    role_order: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Assign every training event ID to exactly one role.

    ``counts`` defaults to the production :data:`ROLE_COUNTS` and must sum to
    the number of supplied IDs.  Any overlap with ``validation_ids`` or
    ``test_ids`` is fatal.
    """
    counts = dict(ROLE_COUNTS if counts is None else counts)
    order = tuple(role_order or [r for r in ROLE_ORDER if r in counts] or sorted(counts))
    if set(order) != set(counts):
        raise RolePartitionError(f"role order {order} does not cover counts {sorted(counts)}")

    ids = [int(e) for e in event_ids]
    if len(set(ids)) != len(ids):
        seen: set[int] = set()
        duplicate = next(e for e in ids if e in seen or seen.add(e))  # type: ignore[func-returns-value]
        raise RolePartitionError(f"duplicate event id in the training population: {duplicate}")

    total = sum(counts.values())
    if total != len(ids):
        raise RolePartitionError(
            f"counts sum to {total} but {len(ids)} training event ids were supplied"
        )

    forbidden_validation = set(int(e) for e in (validation_ids or ()))
    forbidden_test = set(int(e) for e in (test_ids or ()))
    leaked_validation = sorted(forbidden_validation.intersection(ids))
    if leaked_validation:
        raise RolePartitionError(
            f"validation event ids present in the training population: {leaked_validation[:5]}"
        )
    leaked_test = sorted(forbidden_test.intersection(ids))
    if leaked_test:
        raise RolePartitionError(
            f"test event ids present in the training population: {leaked_test[:5]}"
        )

    ordered = sorted(ids, key=lambda e: (role_digest(e), e))
    assignment: list[tuple[int, str]] = []
    cursor = 0
    for role in order:
        take = counts[role]
        for event_id in ordered[cursor : cursor + take]:
            assignment.append((event_id, role))
        cursor += take
    assignment.sort()

    assignment_sha256 = hashlib.sha256(
        json.dumps(assignment, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    manifest = {
        "schema_version": 1,
        "kind": "cbsc-zdc-v3-role-partition",
        "algorithm": ALGORITHM,
        "digest_prefix": DIGEST_PREFIX,
        "role_order": list(order),
        "counts": counts,
        "allowed_parent_split": "train",
        "input_event_count": len(ids),
        "input_split_sha256": split_sha256,
        "assignment_sha256": assignment_sha256,
        "validation_ids_present": 0,
        "test_ids_present": 0,
    }
    manifest["manifest_sha256"] = hashlib.sha256(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    manifest["assignment"] = assignment
    return manifest


def roles_by_event(manifest: dict[str, Any]) -> dict[int, str]:
    """Invert a manifest's assignment list into an event -> role mapping."""
    return {int(event_id): str(role) for event_id, role in manifest["assignment"]}


def events_for_role(manifest: dict[str, Any], role: str) -> list[int]:
    if role not in manifest["counts"]:
        raise RolePartitionError(f"unknown role {role!r}")
    return [int(e) for e, r in manifest["assignment"] if r == role]
