"""Build the tracked synthetic ROOT schema fixture.

The fixture contains no detector-production events.  It has 1,000 identical,
synthetic primary-neutron records and empty hit collections, which is sufficient
to lock exact EDM4hep branch spellings/types and exercise primary selection.
"""

from __future__ import annotations

import argparse
import datetime as datetime_module
import types
import uuid
from contextlib import contextmanager
from pathlib import Path

import awkward as ak
import numpy as np
import uproot


FIXED_FILE_UUID = uuid.UUID("c05c7dc0-b42c-4c2f-a75d-f7f39bc46f86")
FIXED_CREATED_ON = datetime_module.datetime(2026, 7, 23, 0, 0, 0)


class _FixedDateTime(datetime_module.datetime):
    @classmethod
    def now(cls, tz=None):
        value = FIXED_CREATED_ON
        return value if tz is None else value.replace(tzinfo=tz)


@contextmanager
def _fixed_uproot_metadata_time():
    """Freeze ROOT key timestamps that Uproot otherwise takes from the clock."""
    import uproot.writing._cascade as cascade
    import uproot.writing._cascadetree as cascadetree
    import uproot.writing.writable as writable

    modules = (cascade, cascadetree, writable)
    originals = [module.datetime for module in modules]
    frozen = types.SimpleNamespace(datetime=_FixedDateTime)
    try:
        for module in modules:
            module.datetime = frozen
        yield
    finally:
        for module, original in zip(modules, originals):
            module.datetime = original


def build_fixture(output: Path, entries: int = 1000) -> None:
    if entries != 1000:
        raise RuntimeError("the frozen schema fixture contract requires 1,000 entries")
    output.parent.mkdir(parents=True, exist_ok=True)

    primary_int = ak.Array([[value] for value in np.full(entries, 2112, dtype=np.int32)])
    status = ak.Array([[value] for value in np.ones(entries, dtype=np.int32)])
    mass = ak.Array([[value] for value in np.full(entries, 0.939565, dtype=np.float64)])
    zero = ak.Array([[0.0] for _ in range(entries)])
    momentum_z = ak.Array([[100.0] for _ in range(entries)])
    empty_u64 = ak.Array([np.array([], dtype=np.uint64) for _ in range(entries)])
    empty_f64 = ak.Array([np.array([], dtype=np.float64) for _ in range(entries)])

    branch_types = {
        "MCParticles/MCParticles.PDG": "var * int32",
        "MCParticles/MCParticles.generatorStatus": "var * int32",
        "MCParticles/MCParticles.mass": "var * float64",
        "MCParticles/MCParticles.momentum.x": "var * float64",
        "MCParticles/MCParticles.momentum.y": "var * float64",
        "MCParticles/MCParticles.momentum.z": "var * float64",
        "MCParticles/MCParticles.vertex.x": "var * float64",
        "MCParticles/MCParticles.vertex.y": "var * float64",
        "MCParticles/MCParticles.vertex.z": "var * float64",
        "EcalFarForwardZDCHits/EcalFarForwardZDCHits.cellID": "var * uint64",
        "EcalFarForwardZDCHits/EcalFarForwardZDCHits.energy": "var * float64",
        "EcalFarForwardZDCHits/EcalFarForwardZDCHits.position.x": "var * float64",
        "EcalFarForwardZDCHits/EcalFarForwardZDCHits.position.y": "var * float64",
        "EcalFarForwardZDCHits/EcalFarForwardZDCHits.position.z": "var * float64",
        "HcalFarForwardZDCHits/HcalFarForwardZDCHits.cellID": "var * uint64",
        "HcalFarForwardZDCHits/HcalFarForwardZDCHits.energy": "var * float64",
        "HcalFarForwardZDCHits/HcalFarForwardZDCHits.position.x": "var * float64",
        "HcalFarForwardZDCHits/HcalFarForwardZDCHits.position.y": "var * float64",
        "HcalFarForwardZDCHits/HcalFarForwardZDCHits.position.z": "var * float64",
    }
    arrays = {
        "MCParticles/MCParticles.PDG": primary_int,
        "MCParticles/MCParticles.generatorStatus": status,
        "MCParticles/MCParticles.mass": mass,
        "MCParticles/MCParticles.momentum.x": zero,
        "MCParticles/MCParticles.momentum.y": zero,
        "MCParticles/MCParticles.momentum.z": momentum_z,
        "MCParticles/MCParticles.vertex.x": zero,
        "MCParticles/MCParticles.vertex.y": zero,
        "MCParticles/MCParticles.vertex.z": zero,
        "EcalFarForwardZDCHits/EcalFarForwardZDCHits.cellID": empty_u64,
        "EcalFarForwardZDCHits/EcalFarForwardZDCHits.energy": empty_f64,
        "EcalFarForwardZDCHits/EcalFarForwardZDCHits.position.x": empty_f64,
        "EcalFarForwardZDCHits/EcalFarForwardZDCHits.position.y": empty_f64,
        "EcalFarForwardZDCHits/EcalFarForwardZDCHits.position.z": empty_f64,
        "HcalFarForwardZDCHits/HcalFarForwardZDCHits.cellID": empty_u64,
        "HcalFarForwardZDCHits/HcalFarForwardZDCHits.energy": empty_f64,
        "HcalFarForwardZDCHits/HcalFarForwardZDCHits.position.x": empty_f64,
        "HcalFarForwardZDCHits/HcalFarForwardZDCHits.position.y": empty_f64,
        "HcalFarForwardZDCHits/HcalFarForwardZDCHits.position.z": empty_f64,
    }

    with _fixed_uproot_metadata_time():
        with uproot.recreate(output, uuid_function=lambda: FIXED_FILE_UUID) as root:
            tree = root.mktree("events", branch_types)
            tree.extend(arrays)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("fixtures/outfile_neutron1_schema_fixture.root"),
    )
    args = parser.parse_args()
    build_fixture(args.output)


if __name__ == "__main__":
    main()
