"""ROOT adapter skeleton.

The production branch map is deliberately external. Do not infer layer/channel codecs
from names. Install optional dependencies with ``pip install -e .[root]``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BranchMap:
    e: str
    px: str
    py: str
    pz: str
    ecal_id: str
    ecal_energy: str
    hcal_id: str
    hcal_layer: str
    hcal_energy: str


def inspect_root(path: str | Path) -> dict[str, str]:
    try:
        import uproot
    except ImportError as exc:
        raise RuntimeError(
            "Install uproot/awkward using the root extra"
        ) from exc
    root_file = uproot.open(Path(path))
    return {key: str(value.classname) for key, value in root_file.items()}
