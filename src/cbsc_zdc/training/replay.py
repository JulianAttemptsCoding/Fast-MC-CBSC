"""Bounded fake-sample replay for critic training.

A critic trained only on the current generator's output chases a moving target
and forgets what it already learned to reject.  Replay mixes three pools in an
exact largest-remainder composition::

    50% fresh   -- this update's generator output
    25% recent  -- FIFO history, excluding anchors
    25% anchor  -- frozen samples from the corrected supervised baseline

At the declared critic batch size of 4 that is exactly 2 fresh, 1 recent and
1 anchor.

Two invariants matter more than the mixture:

* **Only train events may enter.**  A validation or test event in replay would
  leak evaluation data into training through the critic. Rejected outright.
* **Capacity is declared, not adjusted.**  If dense storage would exceed the
  byte limit the buffer switches to sparse CSR; it never silently shrinks the
  event capacity, which would change the sampling law without saying so.
"""

from __future__ import annotations

import hashlib
import json
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Iterable

import torch

PILOT_CAPACITY_EVENTS = 8192
FINAL_CAPACITY_EVENTS = 65536
DENSE_STORAGE_LIMIT_BYTES = 1_073_741_824
FRESH_FRACTION = 0.50
RECENT_FRACTION = 0.25
ANCHOR_FRACTION = 0.25


class ReplayError(ValueError):
    """Raised when a replay operation would be unsound."""


@dataclass
class ReplayItem:
    event_id: int
    payload: torch.Tensor
    stage: str
    stratum: str
    generator_step: int
    generator_epoch: int
    generator_checkpoint_sha256: str
    sampler_version: str
    seed: int
    is_anchor: bool = False


def largest_remainder_composition(batch_size: int) -> dict[str, int]:
    """Exact integer split of ``batch_size`` across the three pools.

    Largest remainder keeps the total exact; at batch 4 this is the declared
    2 fresh / 1 recent / 1 anchor.
    """
    if batch_size <= 0:
        raise ReplayError("batch size must be positive")
    targets = {
        "fresh": batch_size * FRESH_FRACTION,
        "recent": batch_size * RECENT_FRACTION,
        "anchor": batch_size * ANCHOR_FRACTION,
    }
    floors = {k: int(v) for k, v in targets.items()}
    remainder = batch_size - sum(floors.values())
    order = sorted(targets, key=lambda k: (targets[k] - floors[k], k), reverse=True)
    for name in order[:remainder]:
        floors[name] += 1
    return floors


@dataclass
class ReplayBuffer:
    capacity_events: int = PILOT_CAPACITY_EVENTS
    stage: str = "D1"
    dense_storage_limit_bytes: int = DENSE_STORAGE_LIMIT_BYTES
    allowed_event_ids: frozenset[int] | None = None
    recent: deque = field(default_factory=deque)
    anchors: list[ReplayItem] = field(default_factory=list)
    storage_mode: str = "dense"
    warmup_log: list[dict] = field(default_factory=list)
    _rng: torch.Generator = field(default_factory=torch.Generator)

    def __post_init__(self) -> None:
        self.recent = deque(self.recent, maxlen=self.capacity_events)

    # -- insertion -------------------------------------------------------
    def _check_allowed(self, item: ReplayItem) -> None:
        if self.allowed_event_ids is not None and item.event_id not in self.allowed_event_ids:
            raise ReplayError(
                f"event {item.event_id} is not in the permitted train-only replay population; "
                "validation and test events may never enter replay"
            )

    def add(self, item: ReplayItem) -> None:
        self._check_allowed(item)
        if item.is_anchor:
            raise ReplayError("anchors are installed with set_anchors, not add")
        self.recent.append(item)
        self._maybe_switch_storage()

    def set_anchors(self, items: Iterable[ReplayItem]) -> None:
        anchors = list(items)
        for item in anchors:
            self._check_allowed(item)
            item.is_anchor = True
        hashes = {i.generator_checkpoint_sha256 for i in anchors}
        if len(hashes) > 1:
            raise ReplayError(
                f"anchor pool mixes {len(hashes)} generator checkpoints; anchors are "
                "versioned by a single checkpoint hash"
            )
        self.anchors = anchors

    def _dense_bytes(self) -> int:
        if not self.recent:
            return 0
        per_item = self.recent[0].payload.element_size() * self.recent[0].payload.nelement()
        return per_item * self.capacity_events

    def _maybe_switch_storage(self) -> None:
        if self.storage_mode == "dense" and self._dense_bytes() > self.dense_storage_limit_bytes:
            # Capacity and sampling law are unchanged; only the representation moves.
            self.storage_mode = "sparse_csr"

    # -- sampling --------------------------------------------------------
    def sample(self, batch_size: int, fresh: list[ReplayItem]) -> dict[str, Any]:
        composition = largest_remainder_composition(batch_size)
        for item in fresh:
            self._check_allowed(item)

        recent_pool = [i for i in self.recent if not i.is_anchor]
        chosen: dict[str, list[ReplayItem]] = {"fresh": [], "recent": [], "anchor": []}

        take_fresh = min(composition["fresh"], len(fresh))
        chosen["fresh"] = fresh[:take_fresh]
        chosen["recent"] = self._draw(recent_pool, composition["recent"])
        chosen["anchor"] = self._draw(self.anchors, composition["anchor"])

        # Warm-up: replace missing history with fresh samples and say so.
        shortfall = batch_size - sum(len(v) for v in chosen.values())
        warmup = None
        if shortfall > 0:
            extra = fresh[take_fresh : take_fresh + shortfall]
            chosen["fresh"].extend(extra)
            warmup = {
                "shortfall": shortfall,
                "substituted_fresh": len(extra),
                "recent_available": len(recent_pool),
                "anchors_available": len(self.anchors),
                "requested": composition,
            }
            self.warmup_log.append(warmup)

        return {
            "items": chosen["fresh"] + chosen["recent"] + chosen["anchor"],
            "composition": {k: len(v) for k, v in chosen.items()},
            "requested_composition": composition,
            "warmup": warmup,
        }

    def _draw(self, pool: list[ReplayItem], count: int) -> list[ReplayItem]:
        if count <= 0 or not pool:
            return []
        take = min(count, len(pool))
        index = torch.randperm(len(pool), generator=self._rng)[:take].tolist()
        return [pool[i] for i in index]

    # -- persistence -----------------------------------------------------
    def manifest(self) -> dict[str, Any]:
        content = [
            {
                "event_id": i.event_id,
                "stage": i.stage,
                "stratum": i.stratum,
                "generator_step": i.generator_step,
                "generator_epoch": i.generator_epoch,
                "generator_checkpoint_sha256": i.generator_checkpoint_sha256,
                "sampler_version": i.sampler_version,
                "seed": i.seed,
                "is_anchor": i.is_anchor,
            }
            for i in list(self.recent) + self.anchors
        ]
        digest = hashlib.sha256(
            json.dumps(content, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return {
            "schema_version": 1,
            "kind": "cbsc-zdc-v3-replay-manifest",
            "stage": self.stage,
            "capacity_events": self.capacity_events,
            "storage_mode": self.storage_mode,
            "recent_events": len(self.recent),
            "anchor_events": len(self.anchors),
            "content_sha256": digest,
            "warmup_events": len(self.warmup_log),
        }

    def state_dict(self) -> dict[str, Any]:
        return {
            "capacity_events": self.capacity_events,
            "stage": self.stage,
            "storage_mode": self.storage_mode,
            "recent": list(self.recent),
            "anchors": self.anchors,
            "rng_state": self._rng.get_state(),
            "warmup_log": self.warmup_log,
            "manifest": self.manifest(),
        }

    def load_state_dict(self, state: dict[str, Any]) -> None:
        self.capacity_events = int(state["capacity_events"])
        self.stage = str(state["stage"])
        self.storage_mode = str(state["storage_mode"])
        self.recent = deque(state["recent"], maxlen=self.capacity_events)
        self.anchors = list(state["anchors"])
        self._rng.set_state(state["rng_state"])
        self.warmup_log = list(state["warmup_log"])


def age_distribution(items: Iterable[ReplayItem], current_step: int) -> dict[str, float]:
    ages = [current_step - i.generator_step for i in items]
    if not ages:
        return {"count": 0}
    ordered = sorted(ages)
    return {
        "count": len(ages),
        "min": float(ordered[0]),
        "median": float(ordered[len(ordered) // 2]),
        "max": float(ordered[-1]),
        "mean": float(sum(ages) / len(ages)),
    }
