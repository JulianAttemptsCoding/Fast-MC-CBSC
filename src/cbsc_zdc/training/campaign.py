"""Decision logic for an unattended multi-segment training campaign.

A campaign is a chain of calibrated families, each continued in fixed-length
segments until it stops improving, at which point the chain advances. Everything
here is a pure function of recorded evidence so it can be tested without a GPU,
a pod, or a filesystem. `scripts/dicos_campaign.py` supplies the I/O.

Three rules earned elsewhere in this project are encoded here rather than left
to an operator to remember:

* `training.epochs` is an **absolute** target, so a segment of `n` further
  epochs needs `parent_last_epoch + 1 + n`. Misreading it cost the whole
  `dicos-r1` wave.
* `early_stopping_patience` must equal the segment horizon when resuming from a
  best checkpoint reached at the end of an anneal, or the counter is already
  half spent before the run has a chance. That stopped `dicos-p8` at 6 of 24.
* A run killed by a **structural invariant failure** is terminal for its family.
  Its `last.pt` is quarantined and may not be resumed from, and resuming from
  `best.pt` re-runs the identical epochs under restored RNG against a fixed
  visual bank, so it reproduces the same failure forever. A run killed by
  anything else -- pod expiry, OOM, an operator stop -- is ordinarily resumable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

#: A segment that ends without its family improving inside this window has
#: plateaued. The owner's rule: if the best epoch is within `window` epochs of
#: the latest epoch, the family is still moving and earns another segment.
DEFAULT_IMPROVEMENT_WINDOW = 6

#: Further epochs per segment.
DEFAULT_SEGMENT_EPOCHS = 20

Outcome = Literal[
    "continue_same_family",
    "advance_family",
    "resume_same_segment",
    "campaign_complete",
    "halted",
]


class CampaignError(RuntimeError):
    """Raised when the campaign cannot proceed safely."""


@dataclass(frozen=True)
class SegmentPlan:
    """Everything needed to freeze and launch one segment."""

    family: str
    run_tag: str
    parent_run_dir: str
    parent_last_epoch: int
    parent_best_sha256: str
    parent_last_sha256: str
    resume_from_stem: str
    epochs_absolute: int
    patience: int
    additional_epochs: int
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "family": self.family,
            "run_tag": self.run_tag,
            "parent_run_dir": self.parent_run_dir,
            "parent_last_epoch": self.parent_last_epoch,
            "parent_best_sha256": self.parent_best_sha256,
            "parent_last_sha256": self.parent_last_sha256,
            "resume_from_stem": self.resume_from_stem,
            "epochs_absolute": self.epochs_absolute,
            "patience": self.patience,
            "additional_epochs": self.additional_epochs,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class SegmentResult:
    """What a finished segment left behind, read from its own artifacts."""

    exit_code: int
    epochs: list[dict[str, Any]] = field(default_factory=list)
    invariant_failure: bool = False
    last_epoch_written: int | None = None

    @property
    def latest_epoch(self) -> int | None:
        if self.last_epoch_written is not None:
            return self.last_epoch_written
        if not self.epochs:
            return None
        return max(int(row["epoch"]) for row in self.epochs)

    def best(self) -> tuple[int, float] | None:
        """Lowest validation loss and the epoch that produced it."""
        if not self.epochs:
            return None
        rows = [
            (int(r["epoch"]), float(r["validation_loss"]))
            for r in self.epochs
            if r.get("validation_loss") is not None
        ]
        if not rows:
            return None
        best_epoch, best_loss = min(rows, key=lambda pair: (pair[1], pair[0]))
        return best_epoch, best_loss


def absolute_epoch_target(parent_last_epoch: int, additional_epochs: int) -> int:
    """`training.epochs` is an ABSOLUTE target, never a count of new epochs.

    The trainer resumes at `checkpoint_epoch + 1` and iterates
    `range(start_epoch, epochs)`, so `n` further epochs needs
    `parent_last_epoch + 1 + n`.
    """
    if additional_epochs <= 0:
        raise CampaignError("a segment must request at least one further epoch")
    if parent_last_epoch < 0:
        raise CampaignError("parent_last_epoch must be nonnegative")
    return parent_last_epoch + 1 + additional_epochs


def family_is_still_improving(
    result: SegmentResult, window: int = DEFAULT_IMPROVEMENT_WINDOW
) -> bool:
    """The owner's continue rule, stated exactly.

    "If the best loss is within `window` epochs of the most current epoch then
    continue training." A family whose best epoch is still near the end of its
    segment has not finished moving; one whose best sits far behind has
    plateaued and the chain should advance.
    """
    if window < 0:
        raise CampaignError("improvement window must be nonnegative")
    best = result.best()
    latest = result.latest_epoch
    if best is None or latest is None:
        return False
    best_epoch, _ = best
    return (latest - best_epoch) <= window


def classify(
    result: SegmentResult,
    *,
    window: int = DEFAULT_IMPROVEMENT_WINDOW,
    has_next_family: bool,
) -> tuple[Outcome, str]:
    """Decide what the campaign does after a segment, and say why.

    The reason string is not decoration. It is written into the campaign event
    log and is the only record of why an unattended process made this choice.
    """
    if result.invariant_failure:
        # The checkpoint that failed is quarantined, and resuming from the
        # segment's best re-runs the same epochs under restored RNG against a
        # fixed visual bank -- it would reproduce the failure indefinitely.
        if has_next_family:
            return (
                "advance_family",
                "structural invariant failure is terminal for this family: its "
                "last.pt is quarantined and resuming from its best would "
                "deterministically reproduce the same failure",
            )
        return (
            "halted",
            "structural invariant failure with no further family in the chain",
        )

    if result.exit_code != 0:
        latest = result.latest_epoch
        if latest is None:
            return (
                "halted",
                f"segment exited {result.exit_code} without completing an epoch, "
                "so there is no verified checkpoint to resume from",
            )
        return (
            "resume_same_segment",
            f"segment exited {result.exit_code} after completing epoch {latest} "
            "with no invariant failure recorded, which is an external stop "
            "(pod expiry, OOM, operator) and is ordinarily resumable",
        )

    best = result.best()
    latest = result.latest_epoch
    if best is None or latest is None:
        return ("halted", "segment exited 0 but recorded no epoch")

    best_epoch, best_loss = best
    distance = latest - best_epoch
    if family_is_still_improving(result, window):
        return (
            "continue_same_family",
            f"best epoch {best_epoch} ({best_loss:.6f}) is {distance} epochs "
            f"behind the latest epoch {latest}, within the {window}-epoch "
            "window, so this family is still improving",
        )
    if has_next_family:
        return (
            "advance_family",
            f"best epoch {best_epoch} ({best_loss:.6f}) is {distance} epochs "
            f"behind the latest epoch {latest}, outside the {window}-epoch "
            "window, so this family has plateaued",
        )
    return (
        "campaign_complete",
        f"best epoch {best_epoch} ({best_loss:.6f}) is {distance} epochs behind "
        f"the latest epoch {latest} and no family remains in the chain",
    )


#: Fields a generated continuation config is allowed to move against its parent.
#: Anything else appearing in the diff is a defect, not a surprise -- the
#: portability contract lists learning rate, batch, accumulation, workers,
#: precision, seed and solver steps as invariant across a continuation.
ALLOWED_CONFIG_DELTA = frozenset(
    {
        "project.name",
        "project.run_dir",
        "training.device",
        "training.epochs",
        "training.early_stopping_patience",
        "training.restart_scheduler_on_resume",
        "training.resume_from",
        "training.resume_from_relative",
        "training.resume_from_sha256",
        "training.resume_best_from",
        "training.resume_best_from_relative",
        "training.resume_best_from_sha256",
        "training.resume_progress_from",
        "training.resume_progress_from_relative",
        "training.resume_progress_from_sha256",
        "training.initialize_from",
        "training.initialize_from_relative",
        "training.initialize_from_sha256",
        "evaluation.closure_tolerance_relative",
        "data.manifest",
        "data.splits",
        "geometry.path",
    }
)


def _flatten(config: Any, prefix: str = "") -> dict[str, Any]:
    flat: dict[str, Any] = {}
    if isinstance(config, dict):
        for key, value in config.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            flat.update(_flatten(value, child))
    else:
        flat[prefix] = config
    return flat


def config_delta(parent: dict, child: dict) -> dict[str, tuple[Any, Any]]:
    """Every leaf that differs, as `path -> (parent_value, child_value)`."""
    flat_parent = _flatten(parent)
    flat_child = _flatten(child)
    delta: dict[str, tuple[Any, Any]] = {}
    for key in set(flat_parent) | set(flat_child):
        before = flat_parent.get(key, "<absent>")
        after = flat_child.get(key, "<absent>")
        if before != after:
            delta[key] = (before, after)
    return delta


def verify_config_delta(
    parent: dict, child: dict, *, allowed: frozenset[str] = ALLOWED_CONFIG_DELTA
) -> dict[str, tuple[Any, Any]]:
    """Fail closed if a generated config moved anything it should not.

    An unattended process freezes configs with nobody reading the diff, so the
    diff has to be read by the process. `provenance.*` is exempt because it
    exists precisely to record the change.
    """
    delta = config_delta(parent, child)
    unexpected = {
        key: value
        for key, value in delta.items()
        if key not in allowed and not key.startswith("provenance")
    }
    if unexpected:
        rendered = ", ".join(
            f"{key}: {before!r} -> {after!r}"
            for key, (before, after) in sorted(unexpected.items())
        )
        raise CampaignError(
            "generated config moved fields outside the allowed continuation "
            f"delta: {rendered}"
        )
    return delta
