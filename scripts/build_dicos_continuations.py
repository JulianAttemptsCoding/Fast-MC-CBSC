"""Build continuation templates for the four calibrated families on DiCOS.

Each family resumes from its own latest run. The parent frozen configs are the
authority for everything scientific -- model, loss weights, seed, batch,
accumulation, learning rate, precision -- and this builder changes only what a
backend move and a declared six-epoch extension require:

  * data/geometry paths are returned to UNFROZEN so `cbsc-zdc freeze-config`
    re-pins them against the DiCOS artifacts and recomputes provenance;
  * `epochs` becomes 6;
  * `early_stopping_patience` becomes 6, so no family can stop early during a
    phase whose whole purpose is to compare all four over the same six epochs
    (the winner's continuation restores real early stopping);
  * the resume pair points at the checkpoints staged under `prep/checkpoints`,
    with their SHA-256s, so the runner verifies them before loading.

`num_workers`, `batch_size`, `gradient_accumulation`, `amp`, `seed` and the
solver step counts are deliberately carried over unchanged: the backend
portability contract lists them as invariant across a move.

Usage:
    python scripts/build_dicos_continuations.py --output-dir configs/templates/dicos_continuation_20260801
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import yaml

#: Latest run per family, resolved from the `project.name` resume chain
#: recorded in each output's resolved_config.json.
PARENTS: dict[str, str] = {
    "calibrated_lr3e4":
        "compute_extension_20260727_r1/frozen_calibrated_lr3e4_compute-extension-r1.yaml",
    "calibrated_lr1e4":
        "compute_extension_20260727_r2/frozen_calibrated_lr1e4_compute-extension-r2.yaml",
    "calibrated_lr1e4_halfbatch":
        "compute_extension_20260727_r1/"
        "frozen_calibrated_lr1e4_halfbatch_compute-extension-r1.yaml",
    "calibrated_lr3e5":
        "compute_extension_20260727_r2/frozen_calibrated_lr3e5_compute-extension-r2.yaml",
}

#: SHA-256 of each staged checkpoint, verified against the GCS objects on
#: download and again on the host after upload.
CHECKPOINTS: dict[str, dict[str, str]] = {
    "calibrated_lr3e4": {
        "last": "42782827de374dedcbba50a784460833ad16129c474f98553622b39d6467720a",
        "best": "3f1022b87361b8a14d9f8432273dcd6c72f6a5e599c1be1575e7f37f4014803d",
    },
    "calibrated_lr1e4": {
        "last": "0a9a229495004681e2df9ebe5099889e40de5af2def05eb2cf48098f0ccb8915",
        "best": "f4469a912275480507f758c9bdcd98bc58e94c459e50f5c73d9916446bebf945",
    },
    "calibrated_lr1e4_halfbatch": {
        "last": "999d4e3a49c18941a20eeb001a01f56d2d77a2e5e3147e940e0d8347f0d475d4",
        "best": "d14458bba3fcfbc35d5c3da0b106735fc8041ea2c191969ccb0b86eb484d91ca",
    },
    "calibrated_lr3e5": {
        "last": "83758012275d20a4a23c1495ccc30e240913c95a416f3fb31c0b5d472c10aaf8",
        "best": "949c8e0e199def5eba8cc6cc3f7be7d76aa9e110297fc4382b0e2f82c3b2e064",
    },
}

RUN_TAG = "dicos-r2"

#: `training.epochs` is an ABSOLUTE epoch target, not a count of additional
#: epochs. The trainer resumes at `checkpoint_epoch + 1` and runs
#: `range(start_epoch, epochs)`, so a parent that ended at epoch 4 with
#: `epochs: 6` yields a single epoch, and the cosine restart anneals to
#: min_learning_rate across that one epoch. The first wave was launched with
#: `epochs: 6` and did exactly that before being stopped.
#:
#: All four parents end at epoch 4, read from the staged `*_last.pt` payloads.
PARENT_LAST_EPOCH = 4
ADDITIONAL_EPOCHS = 6
EPOCHS = PARENT_LAST_EPOCH + 1 + ADDITIONAL_EPOCHS  # 11 -> epochs 5..10


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


def build(family: str, parent_path: Path, output_dir: Path) -> Built:
    parent = yaml.safe_load(parent_path.read_text())
    config = copy.deepcopy(parent)

    config["project"]["name"] = f"{parent['project']['name']}-{RUN_TAG}"
    config["project"]["run_dir"] = f"runs/{family}_{RUN_TAG.replace('-', '_')}"

    # Re-pinned by freeze-config against this host's artifacts.
    config["data"]["manifest"] = "UNFROZEN"
    config["data"]["splits"] = "UNFROZEN"
    config["geometry"]["path"] = "UNFROZEN"

    training = config["training"]
    training["device"] = "cuda"
    training["epochs"] = EPOCHS
    training["early_stopping_patience"] = ADDITIONAL_EPOCHS
    training["resume_from"] = None
    training["resume_best_from"] = None
    training["resume_progress_from"] = None
    training["resume_progress_from_relative"] = None
    training["resume_progress_from_sha256"] = None
    training["initialize_from"] = None
    training["initialize_from_relative"] = None
    training["initialize_from_sha256"] = None
    training["resume_from_relative"] = f"checkpoints/{family}_last.pt"
    training["resume_from_sha256"] = CHECKPOINTS[family]["last"]
    training["resume_best_from_relative"] = f"checkpoints/{family}_best.pt"
    training["resume_best_from_sha256"] = CHECKPOINTS[family]["best"]
    training["restart_scheduler_on_resume"] = True

    # freeze-config recomputes provenance; keep only the lineage that records
    # which run this continues, which nothing else preserves.
    config["provenance"] = {
        "parent_config": parent_path.name,
        "parent_config_sha256": _sha256(parent_path),
        "parent_project_name": parent["project"]["name"],
    }

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
    parser.add_argument("--templates-root", default="configs/templates")
    parser.add_argument(
        "--output-dir", default="configs/templates/dicos_continuation_20260801"
    )
    args = parser.parse_args(argv)

    root = Path(args.templates_root)
    output_dir = Path(args.output_dir)
    built = [
        build(family, root / relative, output_dir)
        for family, relative in sorted(PARENTS.items())
    ]

    manifest = {
        "format_version": 1,
        "run_tag": RUN_TAG,
        "epochs_absolute_target": EPOCHS,
        "parent_last_epoch": PARENT_LAST_EPOCH,
        "additional_epochs": ADDITIONAL_EPOCHS,
        "epochs_run": f"{PARENT_LAST_EPOCH + 1}..{EPOCHS - 1}",
        "early_stopping_disabled_for_comparison": True,
        "templates": [
            {
                "family": b.family,
                "template": b.path.name,
                "template_sha256": b.sha256,
                "parent_config": b.parent,
                "parent_config_sha256": b.parent_sha256,
                "resume_from_sha256": CHECKPOINTS[b.family]["last"],
                "resume_best_from_sha256": CHECKPOINTS[b.family]["best"],
            }
            for b in built
        ],
    }
    manifest_path = output_dir / "continuation_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    for b in built:
        print(f"{b.family:<28} {b.path.name:<44} {b.sha256}")
    print(f"\nmanifest {manifest_path} {_sha256(manifest_path)}")


if __name__ == "__main__":
    main()
