"""Derive a versioned live execution contract from the supplied v3 contract.

The supplied ``specs/improvement_v3/contract.yaml`` is a frozen starting
hypothesis and is never mutated.  Live state -- specifically the observed
training device -- may differ from the archive-time observation baked into its
``hardware`` block.  This builder emits a *derived* contract that replaces only
the hardware observation and topology-expression fields, records the exact
field-level diff, and hashes both parent and child.

The topology *principle* is not negotiable and is re-asserted in the derived
contract regardless of device: the live critic and generator are synchronous,
single-process, and on the same CUDA device.  A hardware override may enable a
measured smoke; it never authorizes a training campaign.

Usage::

    python scripts/build_v3_derived_contract.py \
        --hardware audit/v3_live_hardware_20260814.json \
        --output specs/improvement_v3/contract_live_20260814.yaml \
        --report audit/v3_derived_contract_20260814.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

PARENT = Path("specs/improvement_v3/contract.yaml")

# Fields the derived contract is permitted to touch.  Anything outside this set
# is a science change and requires a separately declared contract, not a
# hardware reconciliation.
ALLOWED_DERIVED_PATHS = {
    "contract_id",
    "status",
    "derived_at",
    "hardware.first_critic_topology",
    "hardware.observed_primary_device",
    "hardware.observed_primary_device_uuid",
    "hardware.observed_primary_memory_mib",
    "hardware.observed_at",
    "hardware.archive_time_primary_device",
    "hardware.topology_principle",
    "hardware.resource_preflight_status",
    "hardware.campaign_authorization",
}

# ``derived_from`` is provenance the derived contract adds about itself; it is a
# nested mapping, so its leaves flatten to ``derived_from.<key>``.  Permit that
# subtree by prefix rather than enumerating leaves, which would drift.
ALLOWED_DERIVED_PREFIXES = ("derived_from.",)


def path_is_permitted(path: str) -> bool:
    return path in ALLOWED_DERIVED_PATHS or path.startswith(ALLOWED_DERIVED_PREFIXES)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def flatten(node: Any, prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    if isinstance(node, dict):
        for key, value in node.items():
            out.update(flatten(value, f"{prefix}.{key}" if prefix else str(key)))
    else:
        out[prefix] = node
    return out


def build(hardware_path: Path, output: Path, report: Path) -> dict[str, Any]:
    parent_text = PARENT.read_text(encoding="utf-8")
    parent_sha = sha256_text(parent_text)
    parent = yaml.safe_load(parent_text)

    hardware = json.loads(hardware_path.read_text(encoding="utf-8"))
    primary = next(d for d in hardware["devices"] if d["role"] == "primary_training")

    derived = yaml.safe_load(parent_text)  # independent copy
    derived["contract_id"] = "cbsc-zdc-v3-improvement-live-20260814"
    derived["status"] = "derived_live_execution_contract"
    derived["derived_from"] = {
        "parent_contract_id": parent["contract_id"],
        "parent_sha256": parent_sha,
        "reason": (
            "archive-time hardware observation (L40S) does not match the live "
            "primary training device; only hardware observation and topology "
            "expression fields are replaced"
        ),
    }
    derived["derived_at"] = hardware["observed_at"]

    hw = derived["hardware"]
    hw["archive_time_primary_device"] = "NVIDIA L40S"
    hw["observed_primary_device"] = primary["name"]
    hw["observed_primary_device_uuid"] = primary["uuid"]
    hw["observed_primary_memory_mib"] = primary["memory_total_mib"]
    hw["observed_at"] = hardware["observed_at"]
    hw["first_critic_topology"] = "single_process_same_device_synchronous"
    hw["topology_principle"] = (
        "The live critic and generator are synchronous, single-process, and on "
        "the same CUDA device. The diagnostics GPU cannot carry generator "
        "autograd across a filesystem. Asynchronous critic operation remains a "
        "separately declared staleness ablation. The binding constraint is the "
        "topology, not the device model name."
    )
    hw["resource_preflight_status"] = "pending"
    hw["campaign_authorization"] = (
        "none; this contract authorizes compilation, tests, smoke updates, "
        "inference on existing checkpoints, and bounded resource measurement only"
    )

    flat_parent, flat_derived = flatten(parent), flatten(derived)
    diff = []
    for key in sorted(set(flat_parent) | set(flat_derived)):
        before, after = flat_parent.get(key, "<absent>"), flat_derived.get(key, "<absent>")
        if before != after:
            diff.append({"path": key, "parent": before, "derived": after})

    illegal = [d["path"] for d in diff if not path_is_permitted(d["path"])]
    if illegal:
        raise SystemExit(
            "derived contract changed fields outside the permitted hardware set: "
            + ", ".join(illegal)
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    derived_text = yaml.safe_dump(derived, sort_keys=False, default_flow_style=False)
    output.write_text(derived_text, encoding="utf-8", newline="\n")
    derived_sha = sha256_text(derived_text)

    payload = {
        "schema_version": 1,
        "kind": "cbsc-zdc-v3-derived-contract",
        "parent_contract": str(PARENT).replace("\\", "/"),
        "parent_contract_sha256": parent_sha,
        "derived_contract": str(output).replace("\\", "/"),
        "derived_contract_sha256": derived_sha,
        "observed_at": hardware["observed_at"],
        "gpu_uuid": primary["uuid"],
        "gpu_name": primary["name"],
        "gpu_memory_total_mib": primary["memory_total_mib"],
        "resource_preflight_status": "pending",
        "field_level_diff": diff,
        "retained_constraints": [
            "live critic and generator synchronous, single-process, same device",
            "diagnostics GPU cannot carry generator autograd through a filesystem",
            "asynchronous critic remains a separately declared staleness ablation",
            "no paid cloud work without a new owner budget",
            "critic batch_size 4 remains the first-screen hypothesis until measured "
            "evidence supports a separately versioned change",
        ],
        "parent_unmodified": True,
    }
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hardware", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    payload = build(args.hardware, args.output, args.report)
    print(json.dumps({k: v for k, v in payload.items() if k != "field_level_diff"}, indent=2))
    print(f"field-level diff entries: {len(payload['field_level_diff'])}")
    for entry in payload["field_level_diff"]:
        print(f"  {entry['path']}: {entry['parent']!r} -> {entry['derived']!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
