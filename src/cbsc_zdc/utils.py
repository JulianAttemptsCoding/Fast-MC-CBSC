from __future__ import annotations

import hashlib
import json
import os
import platform
import random
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import torch
import yaml


#: Shards held resident per dataset instance, so per DataLoader worker, unless
#: a caller or CBSC_ZDC_SHARD_CACHE says otherwise. Kept at the historical
#: value so no existing run changes behaviour by upgrading.
DEFAULT_SHARD_CACHE = 4

#: Environment override, so a run on a host with the memory to hold the corpus
#: can opt in without hand-editing a frozen config or changing a config hash.
#: 0 or negative means "hold every shard".
SHARD_CACHE_ENV = "CBSC_ZDC_SHARD_CACHE"


def _shard_cache_size(explicit: int | None = None) -> int:
    if explicit is not None:
        return int(explicit)
    raw = os.environ.get(SHARD_CACHE_ENV)
    if raw is None or not raw.strip():
        return DEFAULT_SHARD_CACHE
    return int(raw)


#: Public name; `_shard_cache_size` is the same function used by the snapshot.
resolve_shard_cache_size = _shard_cache_size


def sha256_file(path: str | Path, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_json(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def load_yaml(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return value


def dump_yaml(payload: Any, path: str | Path) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False)


def load_json(path: str | Path) -> Any:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def dump_json(payload: Any, path: str | Path) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Reports and progress markers are read by other processes on the shared
    # DiCOS filesystem.  A direct write exposes a valid filename containing a
    # partial JSON document; write beside the destination and publish it with
    # one atomic rename instead.
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def seed_everything(seed: int, deterministic: bool = False) -> None:
    random.seed(seed)
    np.random.seed(seed % (2**32))
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    if deterministic:
        torch.use_deterministic_algorithms(True, warn_only=False)
        if torch.backends.cudnn.is_available():
            torch.backends.cudnn.benchmark = False
            torch.backends.cudnn.deterministic = True


def environment_snapshot() -> dict[str, Any]:
    try:
        git_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, text=True
        ).strip()
    except Exception:
        git_commit = None
    cuda_available = torch.cuda.is_available()
    cuda_device_count = torch.cuda.device_count() if cuda_available else 0
    return {
        "python": sys.version,
        "platform": platform.platform(),
        "torch": torch.__version__,
        "numpy": np.__version__,
        "cuda_available": cuda_available,
        "cuda_version": torch.version.cuda,
        "cuda_device_count": cuda_device_count,
        "cuda_device_names": [
            torch.cuda.get_device_name(index) for index in range(cuda_device_count)
        ],
        "cuda_device_total_memory_bytes": [
            int(torch.cuda.get_device_properties(index).total_memory)
            for index in range(cuda_device_count)
        ],
        "cudnn_version": torch.backends.cudnn.version() if torch.backends.cudnn.is_available() else None,
        # How many shards each loader worker holds resident. Changes no sample,
        # only how often one is rebuilt -- but it changes how a run executes, so
        # it belongs in that run's evidence.
        "shard_cache_size": _shard_cache_size(),
        "hostname": platform.node(),
        "pid": os.getpid(),
        "git_commit": git_commit,
    }


def atomic_torch_save(payload: Any, path: str | Path) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    torch.save(payload, temporary)
    temporary.replace(destination)
