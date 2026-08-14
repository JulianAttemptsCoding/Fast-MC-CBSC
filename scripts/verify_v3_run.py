"""Verify a v3 implementation or run.

``--mode software`` checks that the implementation is present and coherent
without touching a GPU or any data: modules importable, declared constants at
their contract values, test files present, and the v2.2 defaults intact.

``--mode run`` additionally checks a run directory's artifacts.

This is a *verifier*, not a test runner.  It fails closed and prints JSON.
"""

from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
from typing import Any

REQUIRED_MODULES = [
    "cbsc_zdc.models.axis_features",
    "cbsc_zdc.models.splines",
    "cbsc_zdc.models.response_v3",
    "cbsc_zdc.models.response_envelope",
    "cbsc_zdc.models.first_layer",
    "cbsc_zdc.models.activity",
    "cbsc_zdc.models.counts_ar",
    "cbsc_zdc.models.critics",
    "cbsc_zdc.training.adversarial",
    "cbsc_zdc.training.replay",
    "cbsc_zdc.training.role_partition",
    "cbsc_zdc.training.stage_sampling",
    "cbsc_zdc.training.migration",
    "cbsc_zdc.eval.topology",
    "cbsc_zdc.eval.correlations",
    "cbsc_zdc.eval.diversity",
]

REQUIRED_TESTS = [
    "tests/test_v3_compatibility.py",
    "tests/test_axis_features.py",
    "tests/test_response_spline.py",
    "tests/test_response_envelope.py",
    "tests/test_hierarchical_first_layer.py",
    "tests/test_longitudinal_activity.py",
    "tests/test_autoregressive_counts.py",
    "tests/test_support_temperature.py",
    "tests/test_differentiable_stage_sampling.py",
    "tests/test_conditional_critics.py",
    "tests/test_adversarial_gradient_isolation.py",
    "tests/test_replay_buffer.py",
    "tests/test_critic_role_partition.py",
    "tests/test_v3_checkpoint_resume.py",
    "tests/test_topology_metrics.py",
    "tests/test_correlation_metrics.py",
    "tests/test_v3_end_to_end_smoke.py",
]


def check_constants() -> list[dict[str, Any]]:
    """Assert declared constants equal their contract values."""
    from cbsc_zdc.models.response_envelope import BIN_WIDTH_GEV, MAX_MARGIN_FACTOR
    from cbsc_zdc.models.splines import DEFAULT_BINS, MIN_BIN_HEIGHT, MIN_BIN_WIDTH, MIN_DERIVATIVE
    from cbsc_zdc.models.support import SUPPORT_TEMPERATURE_DEFAULT
    from cbsc_zdc.training.adversarial import (
        DEFAULT_R1_GAMMA, DEFAULT_R1_INTERVAL, DEFAULT_RATIO_TARGET, OBSERVED_RATIO_ABORT,
    )
    from cbsc_zdc.training.replay import (
        FINAL_CAPACITY_EVENTS, PILOT_CAPACITY_EVENTS,
    )
    from cbsc_zdc.training.role_partition import ROLE_COUNTS

    expected = [
        ("role_partition.generator_train", ROLE_COUNTS["generator_train"], 551234),
        ("role_partition.critic_real_train", ROLE_COUNTS["critic_real_train"], 30624),
        ("role_partition.critic_monitor_holdout", ROLE_COUNTS["critic_monitor_holdout"], 30624),
        ("response.envelope.bin_width_gev", BIN_WIDTH_GEV, 25.0),
        ("response.envelope.max_margin_factor", MAX_MARGIN_FACTOR, 1.10),
        ("response.spline.bins", DEFAULT_BINS, 16),
        ("response.spline.min_bin_width", MIN_BIN_WIDTH, 1e-3),
        ("response.spline.min_bin_height", MIN_BIN_HEIGHT, 1e-3),
        ("response.spline.min_derivative", MIN_DERIVATIVE, 1e-3),
        ("support.temperature_default", SUPPORT_TEMPERATURE_DEFAULT, 1.0),
        ("critic.r1.gamma", DEFAULT_R1_GAMMA, 1.0),
        ("critic.r1.interval", DEFAULT_R1_INTERVAL, 16),
        ("gradient_ratio.default", DEFAULT_RATIO_TARGET, 0.10),
        ("gradient_ratio.abort", OBSERVED_RATIO_ABORT, 0.25),
        ("replay.pilot_capacity", PILOT_CAPACITY_EVENTS, 8192),
        ("replay.final_capacity", FINAL_CAPACITY_EVENTS, 65536),
    ]
    return [
        {"name": name, "value": value, "expected": want, "ok": value == want}
        for name, value, want in expected
    ]


def check_v2_defaults() -> dict[str, Any]:
    """A config with no architecture_version must still mean v2.2."""
    from cbsc_zdc.config import ARCHITECTURE_V2_2, EXPECTED_LOSS_WEIGHTS, architecture_version

    return {
        "absent_version_means_v2_2": architecture_version({"model": {}}) == ARCHITECTURE_V2_2,
        "v2_2_loss_key_count": len(EXPECTED_LOSS_WEIGHTS),
        "v2_2_loss_keys_unchanged": EXPECTED_LOSS_WEIGHTS == {
            "visible", "response", "first_layer", "active", "profile_flow",
            "count", "support_bce", "support_rank", "share_flow",
        },
    }


def check_exact_sampler_untouched() -> dict[str, Any]:
    """The production sampler must keep its no_grad decorator."""
    import inspect

    from cbsc_zdc.models.system import CBSCZDC
    from cbsc_zdc.training import stage_sampling

    share = inspect.getsource(stage_sampling.sample_share_for_loss)
    profile = inspect.getsource(stage_sampling.sample_profile_for_loss)
    return {
        "exact_sampler_has_no_grad": hasattr(CBSCZDC.sample, "__wrapped__"),
        "share_loss_sampler_is_differentiable": "@torch.no_grad" not in share,
        "profile_loss_sampler_is_differentiable": "@torch.no_grad" not in profile,
        "loss_samplers_do_not_call_exact": "sample_exact" not in share + profile,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["software", "run"], default="software")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--run-dir", type=Path)
    args = parser.parse_args()
    root = args.repo_root.resolve()

    modules, missing_modules = [], []
    for name in REQUIRED_MODULES:
        try:
            importlib.import_module(name)
            modules.append(name)
        except Exception as exc:  # noqa: BLE001 - reported, not swallowed
            missing_modules.append({"module": name, "error": str(exc)})

    missing_tests = [t for t in REQUIRED_TESTS if not (root / t).is_file()]
    constants = check_constants()
    bad_constants = [c for c in constants if not c["ok"]]

    result: dict[str, Any] = {
        "mode": args.mode,
        "repo_root": str(root),
        "modules_importable": len(modules),
        "modules_missing": missing_modules,
        "tests_present": len(REQUIRED_TESTS) - len(missing_tests),
        "tests_missing": missing_tests,
        "constants_checked": len(constants),
        "constants_mismatched": bad_constants,
        "v2_defaults": check_v2_defaults(),
        "exact_sampler": check_exact_sampler_untouched(),
    }

    if args.mode == "run":
        if not args.run_dir:
            raise SystemExit("--mode run requires --run-dir")
        run_dir = args.run_dir.resolve()
        result["run_dir"] = str(run_dir)
        result["run_dir_exists"] = run_dir.is_dir()
        result["checkpoints"] = sorted(p.name for p in (run_dir / "checkpoints").glob("*.pt")) if (run_dir / "checkpoints").is_dir() else []

    failures = (
        bool(missing_modules)
        or bool(missing_tests)
        or bool(bad_constants)
        or not all(result["v2_defaults"].values() if isinstance(result["v2_defaults"], dict) else [])
        or not all(result["exact_sampler"].values())
    )
    result["status"] = "fail" if failures else "pass"
    result["note"] = "software verification only; this is not physics validation"
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
