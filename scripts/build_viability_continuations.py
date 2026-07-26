from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_result(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise ValueError("--result must be NAME=PATH")
    name, path = value.split("=", 1)
    if not name or not path:
        raise ValueError("--result must be NAME=PATH")
    return name, Path(path)


def _write_yaml(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        yaml.safe_dump(value, sort_keys=False),
        encoding="utf-8",
    )
    temporary.replace(path)


def _write_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def build(
    analysis_path: Path,
    result_specs: list[tuple[str, Path]],
    template_dir: Path,
    output_dir: Path,
) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(
            f"refusing to overwrite continuation directory: {output_dir}"
        )
    analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    assert analysis["pass"] is True
    assert int(analysis["test_events_used"]) == 0
    selected = list(analysis["selected_for_two_epoch_continuation"])
    assert 1 <= len(selected) <= 2
    assert set(selected).issubset(set(analysis["nondominated"]))
    results = dict(result_specs)
    assert len(results) == len(result_specs)
    assert set(results) == set(selected)

    output_dir.mkdir(parents=True)
    rows = []
    for name in selected:
        result_path = results[name]
        result = json.loads(result_path.read_text(encoding="utf-8"))
        assert result["pass"] is True
        assert result["terminal"] is True
        assert result["stage"] == "joint"
        assert int(result["epoch"]) == 0
        checkpoint = result["checkpoint"]
        best_sha = str(checkpoint["best_sha256"])
        last_sha = str(checkpoint["last_sha256"])
        assert len(best_sha) == len(last_sha) == 64
        template_path = template_dir / f"{name}.yaml"
        config = yaml.safe_load(template_path.read_text(encoding="utf-8"))
        assert config["training"]["stage"] == "joint"
        assert int(config["training"]["epochs"]) == 1
        assert config["training"]["amp"] is False
        assert config["viability"]["successive_halving_wave"] == 1

        continuation = copy.deepcopy(config)
        continuation["project"]["name"] += "-continuation"
        continuation["project"]["run_dir"] += "_continuation"
        training = continuation["training"]
        training["epochs"] = 3
        training["early_stopping_patience"] = 3
        training["checkpoint_interval_updates"] = 50
        training["initialize_from"] = None
        training["initialize_from_relative"] = None
        training["initialize_from_sha256"] = None
        training["resume_from"] = None
        training["resume_from_relative"] = f"checkpoints/{name}_last_epoch0.pt"
        training["resume_from_sha256"] = last_sha
        training["resume_best_from"] = None
        training["resume_best_from_relative"] = (
            f"checkpoints/{name}_best_epoch0.pt"
        )
        training["resume_best_from_sha256"] = best_sha
        training["restart_scheduler_on_resume"] = True
        continuation["viability"].update(
            {
                "successive_halving_wave": 2,
                "continuation_epochs": 2,
                "parent_result_sha256": _sha256(result_path),
                "selection_analysis_sha256": _sha256(analysis_path),
                "scheduler_contract": (
                    "preserve optimizer moments/scaler/RNG; restart exhausted "
                    "one-epoch cosine over exactly epochs 1-2"
                ),
            }
        )
        output_path = output_dir / f"{name}_continuation.yaml"
        _write_yaml(output_path, continuation)
        rows.append(
            {
                "name": name,
                "template": output_path.name,
                "template_sha256": _sha256(output_path),
                "parent_result_sha256": _sha256(result_path),
                "best_checkpoint_sha256": best_sha,
                "last_checkpoint_sha256": last_sha,
                "learning_rate": float(training["learning_rate"]),
                "batch_size": int(training["batch_size"]),
                "gradient_accumulation": int(
                    training["gradient_accumulation"]
                ),
                "start_epoch": 1,
                "stop_before_epoch": 3,
            }
        )

    manifest = {
        "pass": True,
        "scientific_status": (
            "unfrozen validation-only two-epoch continuations; no job submitted"
        ),
        "analysis_sha256": _sha256(analysis_path),
        "variant_count": len(rows),
        "variants": rows,
        "test_events_used": 0,
    }
    _write_json(output_dir / "continuation_manifest.json", manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--result", action="append", default=[], required=True)
    parser.add_argument("--template-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    report = build(
        args.analysis,
        [_parse_result(value) for value in args.result],
        args.template_dir,
        args.output_dir,
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
