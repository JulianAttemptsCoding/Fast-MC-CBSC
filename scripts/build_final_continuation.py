"""Build the solo continuation for the family that won the six-epoch comparison.

The comparison phase (`build_dicos_continuations.py`) ran all four calibrated
families over the same absolute epochs 5..10 with `early_stopping_patience`
deliberately widened to 6, so that no family could stop early during a
comparison. This builder starts the next, different phase: the winner alone,
trained until validation stops it.

It therefore changes exactly three things against the winning parent config:

  * `early_stopping_patience` returns to 3 -- real early stopping, restored;
  * `epochs` becomes a horizon far enough out that early stopping, not the
    ceiling, is what ends the run (still an ABSOLUTE target: the trainer
    resumes at checkpoint_epoch + 1 and runs `range(start_epoch, epochs)`);
  * the resume pair points at the winner's own wave3 checkpoints, staged under
    `prep/checkpoints` and hash-verified before a weight is loaded.

Everything the backend-portability contract lists as invariant -- learning
rate, batch size, accumulation, workers, precision, seed, solver steps --
carries over untouched.

Usage:
    python scripts/build_final_continuation.py \
        --family calibrated_lr3e4 \
        --parent configs/templates/dicos_continuation_20260801/calibrated_lr3e4_dicos-r2.yaml \
        --last-sha256 <sha> --best-sha256 <sha>
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

RUN_TAG = "dicos-final"

#: Last absolute epoch of the comparison wave (epochs 5..10 inclusive).
PARENT_LAST_EPOCH = 10

#: Restored from the comparison phase's widened 6. This is the whole point of
#: the phase: let validation end the run.
EARLY_STOPPING_PATIENCE = 3

#: Absolute epoch target. Generous on purpose -- it is a ceiling that early
#: stopping is expected to reach first, not a planned horizon. Epochs 11..39.
EPOCHS = 40

#: Relative term for the structural closure tolerance, declared 2026-08-05.
#:
#: The two closure invariants compare float32 reductions over thousands of
#: cells, so their residual is a few units in the last place of the magnitude
#: being summed and therefore grows with it. The absolute 2e-5 GeV floor cannot
#: express that and ended `dicos-p10` at epoch 40 on a residual of
#: 2.6702880859375e-05 GeV -- seven float32 ULP at that event's 33.1646 GeV
#: response, with every structural field exactly zero.
#:
#: 1e-5 comes from the 100 measured per-position rows in
#: `_diag/dicos-p10/viz_invariants_epoch_{0040,0039_control}.json`: the residual
#: never exceeded 7 ULP (p95 5, median 1), i.e. 8.052e-07 relative. 1e-5 sits
#: 12x above that ceiling and roughly two orders of magnitude below the residual
#: a single mis-decoded cell would produce, so it admits float32 noise without
#: admitting a defect. The absolute floor is unchanged and still binds below the
#: 2 GeV crossover.
#:
#: Setting this is a DECLARED THRESHOLD CHANGE. Anything compared across it is
#: a new declared experiment.
CLOSURE_TOLERANCE_RELATIVE = 1.0e-05

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class Built:
    family: str
    path: Path
    sha256: str
    parent: str
    parent_sha256: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _check(label: str, value: str) -> str:
    if not _SHA256.match(value or ""):
        raise ValueError(f"{label} is not a sha256 digest: {value!r}")
    return value


def build(
    family: str,
    parent_path: Path,
    last_sha256: str,
    best_sha256: str,
    output_dir: Path,
    patience: int | None = None,
    epochs: int | None = None,
    run_tag: str = RUN_TAG,
    parent_last_epoch: int | None = None,
    checkpoint_stem: str = "r3",
    selected_by: str = (
        "largest validation-loss improvement over absolute epochs 5..10"
    ),
    restart_scheduler: bool = True,
    closure_tolerance_relative: float | None = None,
) -> Built:
    last_sha256 = _check("last_sha256", last_sha256)
    best_sha256 = _check("best_sha256", best_sha256)

    # Defaults restore the real early stopping; widening is possible but only
    # by asking, so the comparison phase's patience can never be inherited.
    patience = EARLY_STOPPING_PATIENCE if patience is None else int(patience)
    epochs = EPOCHS if epochs is None else int(epochs)
    # A later phase continues from a later parent. The default keeps the
    # wave-three value, so an omitted argument cannot silently move the horizon.
    parent_last_epoch = (
        PARENT_LAST_EPOCH if parent_last_epoch is None else int(parent_last_epoch)
    )
    available = epochs - (parent_last_epoch + 1)
    if available <= 0:
        raise ValueError(
            f"horizon leaves no epochs to run: epochs={epochs} against a parent "
            f"ending at {parent_last_epoch}. `epochs` is an ABSOLUTE target."
        )
    # A horizon no longer than the patience is a legitimate declared choice --
    # the comparison wave used exactly that to guarantee a fixed six epochs --
    # but it means early stopping can never fire. The hazard is getting that
    # silently, so it is recorded rather than forbidden.
    early_stopping_can_fire = available > patience

    parent_path = Path(parent_path)
    parent = yaml.safe_load(parent_path.read_text())
    config = copy.deepcopy(parent)

    config["project"]["name"] = f"{parent['project']['name']}-{run_tag}"
    config["project"]["run_dir"] = f"runs/{family}_{run_tag.replace('-', '_')}"

    # Re-pinned by freeze-config against the host's artifacts; a frozen config
    # is never hand-edited.
    config["data"]["manifest"] = "UNFROZEN"
    config["data"]["splits"] = "UNFROZEN"
    config["geometry"]["path"] = "UNFROZEN"

    training = config["training"]
    training["device"] = "cuda"
    training["epochs"] = epochs
    training["early_stopping_patience"] = patience
    # Restarting sets the learning rate straight back to its peak, which makes
    # a model resumed from the end of an anneal worse by construction. Not
    # restarting instead reloads the saved scheduler state, so the cosine
    # continues from where it stopped -- and because CosineAnnealingLR is
    # periodic in 2*T_max, it climbs smoothly back toward the peak rather than
    # jumping there.
    training["restart_scheduler_on_resume"] = bool(restart_scheduler)
    for key in (
        "resume_from", "resume_best_from", "resume_progress_from",
        "resume_progress_from_relative", "resume_progress_from_sha256",
        "initialize_from", "initialize_from_relative", "initialize_from_sha256",
    ):
        training[key] = None
    training["resume_from_relative"] = f"checkpoints/{family}_{checkpoint_stem}_last.pt"
    training["resume_from_sha256"] = last_sha256
    training["resume_best_from_relative"] = f"checkpoints/{family}_{checkpoint_stem}_best.pt"
    training["resume_best_from_sha256"] = best_sha256

    # Declared 2026-08-05. The absolute floor is untouched; this adds the
    # scale term the residual actually needs. A parent frozen before this date
    # has no such key, so its own runs stay bit-reproducible under the old rule.
    closure_tolerance_relative = (
        CLOSURE_TOLERANCE_RELATIVE
        if closure_tolerance_relative is None
        else float(closure_tolerance_relative)
    )
    if closure_tolerance_relative < 0:
        raise ValueError("closure_tolerance_relative must be nonnegative")
    parent_relative = float(
        parent.get("evaluation", {}).get("closure_tolerance_relative", 0.0)
    )
    config.setdefault("evaluation", {})
    config["evaluation"]["closure_tolerance_relative"] = closure_tolerance_relative

    config["provenance"] = {
        "parent_config": parent_path.name,
        "parent_config_sha256": _sha256(parent_path),
        "parent_project_name": parent["project"]["name"],
        "parent_last_epoch": parent_last_epoch,
        "selected_by": selected_by,
        "epochs_available": available,
        "early_stopping_patience": patience,
        "early_stopping_can_fire": early_stopping_can_fire,
        "restart_scheduler_on_resume": bool(restart_scheduler),
        "closure_tolerance_gev": float(
            config["evaluation"].get("closure_tolerance_gev", 2e-5)
        ),
        "closure_tolerance_relative": closure_tolerance_relative,
        "parent_closure_tolerance_relative": parent_relative,
        "closure_tolerance_relative_changed": (
            closure_tolerance_relative != parent_relative
        ),
    }

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out = output_dir / f"{family}_{run_tag}.yaml"
    out.write_text(yaml.safe_dump(config, sort_keys=False))
    return Built(
        family=family,
        path=out,
        sha256=_sha256(out),
        parent=parent_path.name,
        parent_sha256=_sha256(parent_path),
    )


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family", required=True)
    parser.add_argument("--parent", required=True, type=Path)
    parser.add_argument("--last-sha256", required=True)
    parser.add_argument("--best-sha256", required=True)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("configs/templates/dicos_final_20260802"),
    )
    parser.add_argument("--run-tag", default=RUN_TAG)
    parser.add_argument(
        "--patience",
        type=int,
        default=EARLY_STOPPING_PATIENCE,
        help="Widen only deliberately: patience 3 cannot survive a high-LR "
             "scheduler restart, because the resumed best was reached at the "
             "end of an anneal.",
    )
    parser.add_argument("--epochs", type=int, default=EPOCHS)
    parser.add_argument(
        "--parent-last-epoch",
        type=int,
        default=PARENT_LAST_EPOCH,
        help="Absolute last epoch of the parent checkpoint. `epochs` is an "
             "ABSOLUTE target, so this is what decides how many epochs run.",
    )
    parser.add_argument(
        "--checkpoint-stem",
        default="r3",
        help="Infix of the staged resume pair, "
             "checkpoints/<family>_<stem>_{last,best}.pt",
    )
    parser.add_argument(
        "--no-restart-scheduler", action="store_true",
        help="continue the saved cosine instead of resetting it to the peak "
             "learning rate; use when resuming from the end of an anneal",
    )
    parser.add_argument(
        "--closure-tolerance-relative",
        type=float,
        default=CLOSURE_TOLERANCE_RELATIVE,
        help="relative term added to the absolute closure tolerance, so the "
             "bound is max(absolute, relative * total_response). Declared "
             "2026-08-05 after an absolute-only tolerance ended dicos-p10 on "
             "seven float32 ULP. Pass 0.0 to reproduce the old absolute rule.",
    )
    parser.add_argument(
        "--selected-by",
        default="largest validation-loss improvement over absolute epochs 5..10",
        help="Why this family is being continued. Recorded in provenance.",
    )
    args = parser.parse_args(argv)

    built = build(
        family=args.family,
        parent_path=args.parent,
        last_sha256=args.last_sha256,
        best_sha256=args.best_sha256,
        output_dir=args.output_dir,
        patience=args.patience,
        epochs=args.epochs,
        run_tag=args.run_tag,
        parent_last_epoch=args.parent_last_epoch,
        closure_tolerance_relative=args.closure_tolerance_relative,
        checkpoint_stem=args.checkpoint_stem,
        selected_by=args.selected_by,
        restart_scheduler=not args.no_restart_scheduler,
    )

    manifest = {
        "format_version": 1,
        "run_tag": args.run_tag,
        "family": built.family,
        "epochs_absolute_target": args.epochs,
        "parent_last_epoch": args.parent_last_epoch,
        "early_stopping_patience": args.patience,
        "patience_widened_from_default": args.patience != EARLY_STOPPING_PATIENCE,
        "epochs_available": f"{args.parent_last_epoch + 1}..{args.epochs - 1}",
        "selected_by": args.selected_by,
        "restart_scheduler_on_resume": not args.no_restart_scheduler,
        "resume_from_relative": f"checkpoints/{args.family}_{args.checkpoint_stem}_last.pt",
        "resume_best_from_relative": f"checkpoints/{args.family}_{args.checkpoint_stem}_best.pt",
        "manifest_note": "epochs is an ABSOLUTE target; the trainer resumes at checkpoint_epoch + 1",
        "template": built.path.name,
        "template_sha256": built.sha256,
        "parent_config": built.parent,
        "parent_config_sha256": built.parent_sha256,
        "resume_from_sha256": args.last_sha256,
        "resume_best_from_sha256": args.best_sha256,
    }
    # Per family and run tag. A fixed name silently overwrote the first
    # family's provenance when a phase built two of them into one directory --
    # which is why dicos_p6_20260802/ carries a manifest for only one of the
    # two templates beside it.
    manifest_path = (
        args.output_dir / f"{args.family}_{args.run_tag}_manifest.json"
    )
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    print(f"{built.family:<28} {built.path.name:<40} {built.sha256}")
    print(f"manifest {manifest_path} {_sha256(manifest_path)}")


if __name__ == "__main__":
    main()
