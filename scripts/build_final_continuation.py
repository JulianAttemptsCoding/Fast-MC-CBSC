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
) -> Built:
    last_sha256 = _check("last_sha256", last_sha256)
    best_sha256 = _check("best_sha256", best_sha256)

    parent_path = Path(parent_path)
    parent = yaml.safe_load(parent_path.read_text())
    config = copy.deepcopy(parent)

    config["project"]["name"] = f"{parent['project']['name']}-{RUN_TAG}"
    config["project"]["run_dir"] = f"runs/{family}_{RUN_TAG.replace('-', '_')}"

    # Re-pinned by freeze-config against the host's artifacts; a frozen config
    # is never hand-edited.
    config["data"]["manifest"] = "UNFROZEN"
    config["data"]["splits"] = "UNFROZEN"
    config["geometry"]["path"] = "UNFROZEN"

    training = config["training"]
    training["device"] = "cuda"
    training["epochs"] = EPOCHS
    training["early_stopping_patience"] = EARLY_STOPPING_PATIENCE
    training["restart_scheduler_on_resume"] = True
    for key in (
        "resume_from", "resume_best_from", "resume_progress_from",
        "resume_progress_from_relative", "resume_progress_from_sha256",
        "initialize_from", "initialize_from_relative", "initialize_from_sha256",
    ):
        training[key] = None
    training["resume_from_relative"] = f"checkpoints/{family}_r3_last.pt"
    training["resume_from_sha256"] = last_sha256
    training["resume_best_from_relative"] = f"checkpoints/{family}_r3_best.pt"
    training["resume_best_from_sha256"] = best_sha256

    config["provenance"] = {
        "parent_config": parent_path.name,
        "parent_config_sha256": _sha256(parent_path),
        "parent_project_name": parent["project"]["name"],
        "parent_last_epoch": PARENT_LAST_EPOCH,
        "selected_by": "largest validation-loss improvement over absolute epochs 5..10",
    }

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out = output_dir / f"{family}_{RUN_TAG}.yaml"
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
    args = parser.parse_args(argv)

    built = build(
        family=args.family,
        parent_path=args.parent,
        last_sha256=args.last_sha256,
        best_sha256=args.best_sha256,
        output_dir=args.output_dir,
    )

    manifest = {
        "format_version": 1,
        "run_tag": RUN_TAG,
        "family": built.family,
        "epochs_absolute_target": EPOCHS,
        "parent_last_epoch": PARENT_LAST_EPOCH,
        "early_stopping_patience": EARLY_STOPPING_PATIENCE,
        "epochs_available": f"{PARENT_LAST_EPOCH + 1}..{EPOCHS - 1}",
        "template": built.path.name,
        "template_sha256": built.sha256,
        "parent_config": built.parent,
        "parent_config_sha256": built.parent_sha256,
        "resume_from_sha256": args.last_sha256,
        "resume_best_from_sha256": args.best_sha256,
    }
    manifest_path = args.output_dir / "final_continuation_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    print(f"{built.family:<28} {built.path.name:<40} {built.sha256}")
    print(f"manifest {manifest_path} {_sha256(manifest_path)}")


if __name__ == "__main__":
    main()
