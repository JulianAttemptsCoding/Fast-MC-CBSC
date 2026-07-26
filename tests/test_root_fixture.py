from pathlib import Path

import pytest

pytest.importorskip("awkward")
import awkward as ak
import numpy as np
uproot = pytest.importorskip("uproot")

from cbsc_zdc.data.root_io import (  # noqa: E402
    _signed_or_uint64_sentinel_mask,
    channel_key,
    collection_energy_accounting,
    inspect_root_file,
    load_branch_schema,
    select_primary_neutron,
)
from cbsc_zdc.data.geometry import _merge_physical_positions  # noqa: E402


REPOSITORY = Path(__file__).parents[1]


def test_sample_schema_matches_the_bundled_root_fixture():
    fixture = REPOSITORY / "fixtures/outfile_neutron1_schema_fixture.root"
    schema = load_branch_schema(REPOSITORY / "configs/schema_sample_edm4hep.yaml")
    inspection = inspect_root_file(fixture, schema)
    assert inspection["entries"] == 1000
    assert inspection["missing_branches"] == []
    assert set(inspection["branch_types"]) == set(schema.all_branches())

    with uproot.open(fixture) as root_file:
        arrays = root_file[schema.tree].arrays(
            schema.all_branches(), entry_start=0, entry_stop=8, library="ak"
        )
    p4, kinetic, vertex, valid = select_primary_neutron(arrays, schema)
    assert valid.all()
    assert p4.shape == (8, 4)
    assert kinetic.shape == (8,)
    assert vertex.shape == (8, 3)


def test_layer_local_channel_keys_are_distinct():
    assert channel_key(1, 65, 3) != channel_key(1, 65, 4)
    assert channel_key(0, 230) == "0:230"


def test_negative_sentinel_is_safe_for_unsigned_cell_ids():
    wrapped = np.uint64((-100) % (1 << 64))
    values = ak.unflatten(
        np.array([1, wrapped, 2], dtype=np.uint64),
        np.array([2, 1], dtype=np.int64),
    )
    mask = _signed_or_uint64_sentinel_mask(values, (-100,))
    assert ak.to_list(mask) == [[False, True], [False]]


def test_sentinel_energy_is_excluded_from_modeled_readout_but_closes_total():
    class Collection:
        name = "test"
        cell_id = "cell"
        energy = "energy"

    class Schema:
        energy_unit_to_gev = 1.0
        cell_id_sentinels = (-100,)

    arrays = {
        "cell": ak.Array([[1, -100, 2], [-100]]),
        "energy": ak.Array([[1.5, 0.25, 2.0], [0.5]]),
    }
    all_energy, modeled, excluded = collection_energy_accounting(
        arrays, Collection(), Schema()
    )
    np.testing.assert_allclose(all_energy, [3.75, 0.5])
    np.testing.assert_allclose(modeled, [3.5, 0.0])
    np.testing.assert_allclose(excluded, [0.25, 0.5])


def test_ganged_readout_geometry_uses_unweighted_distinct_position_centroid():
    observation = {}
    first_chunk = np.array(
        [[0.0, 0.0, 10.0], [0.0, 0.0, 10.0], [40.0, 20.0, 12.0]],
        dtype=np.float64,
    )
    second_chunk = np.array(
        [[40.0, 20.0, 12.0], [40.0, 20.0, 12.0]],
        dtype=np.float64,
    )
    _merge_physical_positions(observation, first_chunk, tolerance_mm=1e-3)
    _merge_physical_positions(observation, second_chunk, tolerance_mm=1e-3)
    distinct = np.stack(list(observation["physical_positions"].values()))
    assert distinct.shape == (2, 3)
    # The duplicated second physical center must not pull the static centroid.
    np.testing.assert_allclose(distinct.mean(axis=0), [20.0, 10.0, 11.0])
