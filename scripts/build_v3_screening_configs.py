"""Generate the v3 screening-row templates (S1..S5) from a parent frozen config.

Each row turns on exactly one v3 feature relative to its parent, so a promotion
decision is attributable to that change alone.  Templates are written unfrozen;
they are frozen through the repository CLI, which records both hashes.

Nothing here edits a frozen config, and nothing here launches a run.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

import yaml

from cbsc_zdc.config import ARCHITECTURE_V3, V3_LOSS_WEIGHTS
from cbsc_zdc.utils import sha256_file

# Ordered exactly as specs/improvement_v3/experiment_matrix.csv declares them.
ROWS = [
    {
        "id": "S1-axis",
        "change": "incident_axis_features",
        "model": {"axis_features": True},
        "question": "Do incident-axis-relative node coordinates lower the validation loss?",
    },
    {
        "id": "S2-response",
        "change": "bounded_positive_response_spline",
        "model": {"response_mode": "spline"},
        "question": "Does a bounded conditional spline with one zero atom beat the clamped mixture?",
    },
    {
        "id": "S3-first",
        "change": "hierarchical_ecal_hcal_first",
        "model": {"first_layer_mode": "hierarchical"},
        "question": "Does factorizing the first layer fix the underproduced ECAL-start prevalence?",
    },
    {
        "id": "S4-activity-span",
        "change": "span_gap_activity",
        "model": {"activity_head_mode": "span_gaps"},
        "question": "Does a span-plus-gaps activity model beat independent per-layer Bernoullis?",
    },
    {
        "id": "S4-activity-ar",
        "change": "autoregressive_activity",
        "model": {"activity_head_mode": "autoregressive"},
        "question": "Does an autoregressive activity model beat span-plus-gaps?",
    },
    {
        "id": "S5-count-ar",
        "change": "autoregressive_counts",
        "model": {"count_mode": "autoregressive"},
        "question": "Does conditioning counts on the previous layer beat independent counts?",
    },
]

# Weights for the added v3 terms. They start at the same modest value the v2.2
# first-layer and activity terms use, so a screening row tests the head rather
# than a weight change smuggled in alongside it.
ADDED_LOSS_WEIGHTS = {
    "ecal_start": 0.5,
    "hcal_first": 0.5,
    "active_last": 0.5,
    "active_gap": 0.5,
}


def build_row(parent: dict, row: dict, envelope: dict | None, cumulative: dict, horizon: int,
              vertex: list[float] | None) -> dict:
    config = copy.deepcopy(parent)
    model = config.setdefault("model", {})
    model["architecture_version"] = ARCHITECTURE_V3
    # Cumulative: each row keeps the features its predecessors turned on.
    model.update(cumulative)
    model.update(row["model"])

    if model.get("axis_features"):
        if vertex is None:
            raise SystemExit(
                "axis features need the frozen generator vertex; it is recorded as "
                "fixed_vertex_mm in the dataset manifest"
            )
        model["generator_vertex_mm"] = [float(v) for v in vertex]

    if model.get("response_mode") == "spline":
        if envelope is None:
            raise SystemExit(f"{row['id']} selects the response spline but no envelope was supplied")
        model["response_envelope_caps_gev"] = [float(c) for c in envelope["monotone_caps_gev"]]
        model["response_envelope_sha256"] = envelope["envelope_sha256"]

    weights = dict(config.get("loss_weights", {}))
    if model.get("first_layer_mode") == "hierarchical":
        weights["ecal_start"] = ADDED_LOSS_WEIGHTS["ecal_start"]
        weights["hcal_first"] = ADDED_LOSS_WEIGHTS["hcal_first"]
    if model.get("activity_head_mode", "v2") != "v2":
        weights["active_last"] = ADDED_LOSS_WEIGHTS["active_last"]
        weights["active_gap"] = ADDED_LOSS_WEIGHTS["active_gap"]
    unknown = set(weights) - V3_LOSS_WEIGHTS
    if unknown:
        raise SystemExit(f"{row['id']} produced unknown loss weights: {sorted(unknown)}")
    config["loss_weights"] = weights

    # A screening row starts from a migrated checkpoint; it does not continue its
    # parent's schedule. Carrying the parent's resume pointers would resume a
    # v2.2 run under a v3 config, and carrying its absolute epoch target would
    # make the horizon depend on how long the parent happened to train.
    training = config.setdefault("training", {})
    for field in (
        "resume_from", "resume_from_relative", "resume_from_sha256",
        "resume_best_from", "resume_best_from_relative", "resume_best_from_sha256",
        "resume_progress_from", "resume_progress_from_relative", "resume_progress_from_sha256",
        "initialize_from", "initialize_from_relative", "initialize_from_sha256",
    ):
        training.pop(field, None)
    training["epochs"] = int(horizon)
    training["early_stopping_patience"] = int(horizon)
    # Fresh cosine over this row's own horizon. The sawtooth defect came from a
    # restored T_max, and there is no parent schedule to continue here.
    training["restart_scheduler_on_resume"] = False

    provenance = config.setdefault("provenance", {})
    provenance.update({
        "v3_screening_row": row["id"],
        "v3_declared_change": row["change"],
        "v3_scientific_question": row["question"],
        "v3_features_enabled": {k: v for k, v in model.items() if k in
                                ("axis_features", "response_mode", "first_layer_mode",
                                 "count_mode", "activity_head_mode")},
    })
    return config


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--envelope", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--only", nargs="*", help="restrict to these row ids")
    parser.add_argument("--horizon", type=int, default=24,
                        help="epochs and early-stopping patience for each screening row")
    args = parser.parse_args()

    parent = yaml.safe_load(args.parent.read_text(encoding="utf-8"))
    envelope = json.loads(args.envelope.read_text(encoding="utf-8")) if args.envelope else None
    if envelope is not None and not envelope.get("production_ready"):
        raise SystemExit(
            "the supplied response envelope is not production_ready; "
            f"empty bins {envelope.get('empty_visible_bins')}"
        )

    # The frozen generator vertex lives in the dataset manifest as
    # fixed_vertex_mm. Axis coordinates are measured from it, so it travels into
    # the config rather than being rediscovered at train time.
    manifest = json.loads(Path(parent["data"]["manifest"]).read_text(encoding="utf-8"))
    vertex = manifest.get("fixed_vertex_mm")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    cumulative: dict = {}
    written = []
    for row in ROWS:
        cumulative.update(row["model"])
        if args.only and row["id"] not in args.only:
            continue
        config = build_row(parent, row, envelope, dict(cumulative), args.horizon, vertex)
        path = args.output_dir / f"v3_{row['id'].replace('-', '_')}.yaml"
        path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8", newline="\n")
        written.append({
            "id": row["id"],
            "path": str(path).replace("\\", "/"),
            "sha256": sha256_file(path),
            "declared_change": row["change"],
            "features": config["provenance"]["v3_features_enabled"],
            "loss_weight_keys": sorted(config["loss_weights"]),
            "epochs": config["training"]["epochs"],
            "early_stopping_patience": config["training"]["early_stopping_patience"],
        })

    print(json.dumps({
        "parent": str(args.parent).replace("\\", "/"),
        "parent_sha256": sha256_file(args.parent),
        "envelope_sha256": envelope["envelope_sha256"] if envelope else None,
        "generator_vertex_mm": vertex,
        "rows": written,
        "note": "templates are unfrozen; freeze through the repository CLI and record both hashes",
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
