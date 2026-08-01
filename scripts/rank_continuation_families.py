"""Rank the four calibrated families after the six-epoch continuation.

The selection rule is the one set for this phase: **the largest improvement in
validation loss from the beginning of the continuation to its end.**

"Beginning" is the parent's epoch-4 validation loss, not the continuation's
first epoch. Epoch 5 has already had a full epoch of training, so measuring
from it would hide the very progress being compared. "End" is the final epoch,
epoch 10 -- not the best epoch. A cosine restart raises validation loss before
it lowers it, so only the endpoints are meaningful, and picking the best epoch
instead would reward a family for a lucky mid-run dip.

Where the best epoch is not the final epoch, that is reported rather than
discarded, because it is exactly the situation in which the ranking deserves a
second look before a long solo run is launched on the result.

This script only reads and reports. It selects nothing on its own and writes no
config.

Usage:
    python scripts/rank_continuation_families.py --runs-root _runs
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict
from pathlib import Path

#: Validation loss of each family's accepted epoch-4 checkpoint -- the state
#: every continuation resumed from, and so the baseline for "beginning".
PARENT_VALIDATION: dict[str, float] = {
    "calibrated_lr3e4": 4.738041,
    "calibrated_lr1e4": 4.827105,
    "calibrated_lr1e4_halfbatch": 4.845029,
    "calibrated_lr3e5": 4.897327,
}

#: Last epoch of the accepted parents, and so the epoch whose validation loss
#: PARENT_VALIDATION records. Cross-checked against
#: exhibition/data/training_history.csv by the test suite.
PARENT_LAST_EPOCH = 4

FIRST_EPOCH = 5
LAST_EPOCH = 10
EXPECTED_EPOCHS = 6

RUN_TAG = "dicos-r3"


@dataclass(frozen=True)
class FamilyResult:
    family: str
    parent_validation_loss: float
    first_validation_loss: float
    final_validation_loss: float
    best_validation_loss: float
    best_epoch: int
    improvement: float
    improvement_within_continuation: float
    best_differs_from_final: bool
    epochs: list[int]


def _load(family: str, runs_root: Path) -> list[tuple[int, float]]:
    reports = Path(runs_root) / f"{family}_{RUN_TAG}" / "reports"
    if not reports.is_dir():
        raise FileNotFoundError(f"no reports directory for {family}: {reports}")
    rows: list[tuple[int, float]] = []
    for path in sorted(reports.glob("progress_epoch_*.json")):
        payload = json.loads(path.read_text())
        value = payload.get("row", {}).get("validation_loss")
        if value is None:
            continue
        rows.append((int(payload["epoch"]), float(value)))
    if not rows:
        raise FileNotFoundError(f"no epoch snapshots for {family} in {reports}")
    return sorted(rows)


def summarise(family: str, runs_root: Path) -> FamilyResult:
    rows = _load(family, runs_root)
    epochs = [epoch for epoch, _ in rows]
    if len(rows) != EXPECTED_EPOCHS or epochs[0] != FIRST_EPOCH or epochs[-1] != LAST_EPOCH:
        raise ValueError(
            f"{family} is incomplete: expected epochs "
            f"{FIRST_EPOCH}..{LAST_EPOCH}, found {epochs}"
        )
    parent = PARENT_VALIDATION[family]
    best_epoch, best = min(rows, key=lambda row: row[1])
    final = rows[-1][1]
    return FamilyResult(
        family=family,
        parent_validation_loss=parent,
        first_validation_loss=rows[0][1],
        final_validation_loss=final,
        best_validation_loss=best,
        best_epoch=best_epoch,
        improvement=parent - final,
        improvement_within_continuation=rows[0][1] - final,
        best_differs_from_final=best_epoch != rows[-1][0],
        epochs=epochs,
    )


def rank(families: list[str], runs_root: Path) -> list[FamilyResult]:
    return sorted(
        (summarise(family, runs_root) for family in families),
        key=lambda result: result.improvement,
        reverse=True,
    )


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-root", type=Path, default=Path("_runs"))
    parser.add_argument("--json", action="store_true", help="emit machine-readable")
    args = parser.parse_args(argv)

    ranked = rank(sorted(PARENT_VALIDATION), args.runs_root)

    if args.json:
        print(json.dumps([asdict(r) for r in ranked], indent=2, sort_keys=True))
        return

    header = f"{'family':<28}{'parent':>10}{'e5':>10}{'e10':>10}{'best':>10}{'improve':>10}"
    print(header)
    print("-" * len(header))
    for result in ranked:
        print(
            f"{result.family:<28}"
            f"{result.parent_validation_loss:>10.6f}"
            f"{result.first_validation_loss:>10.6f}"
            f"{result.final_validation_loss:>10.6f}"
            f"{result.best_validation_loss:>10.6f}"
            f"{result.improvement:>+10.6f}"
        )
    print()
    winner = ranked[0]
    print(f"largest improvement: {winner.family} ({winner.improvement:+.6f})")
    if winner.improvement <= 0:
        print(
            "WARNING: the leading family did not improve on its parent. Six more "
            "epochs made every family worse; report that, do not launch on it "
            "without saying so."
        )
    for result in ranked:
        if result.best_differs_from_final:
            print(
                f"note: {result.family} was best at epoch {result.best_epoch} "
                f"({result.best_validation_loss:.6f}), not at epoch "
                f"{LAST_EPOCH} ({result.final_validation_loss:.6f})"
            )


if __name__ == "__main__":
    main()
