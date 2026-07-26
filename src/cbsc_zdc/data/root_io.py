from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

import numpy as np

from .schema import BranchSchema
from ..utils import load_yaml, sha256_file


def _require_root_stack():
    try:
        import awkward as ak  # type: ignore
        import uproot  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "ROOT support is optional. Install it with: python -m pip install -e '.[root]'"
        ) from exc
    return uproot, ak


def load_branch_schema(path: str | Path) -> BranchSchema:
    return BranchSchema.from_dict(load_yaml(path))


def inspect_root_file(path: str | Path, schema: BranchSchema | None = None) -> dict[str, Any]:
    uproot, _ = _require_root_stack()
    source = Path(path)
    with uproot.open(source) as root_file:
        keys = {str(key): str(value.classname) for key, value in root_file.items()}
        result: dict[str, Any] = {
            "path": str(source.resolve()),
            "sha256": sha256_file(source),
            "keys": keys,
        }
        if schema is not None:
            if schema.tree not in root_file:
                raise KeyError(f"tree {schema.tree!r} not found in {source}")
            tree = root_file[schema.tree]
            available = set(str(k) for k in tree.keys())
            missing = sorted(set(schema.all_branches()) - available)
            result["tree"] = schema.tree
            result["entries"] = int(tree.num_entries)
            result["missing_branches"] = missing
            result["branch_types"] = {
                name: str(tree[name].interpretation) for name in schema.all_branches() if name in available
            }
        return result


def iter_root_chunks(
    paths: list[str | Path],
    schema: BranchSchema,
    step_size: int = 2048,
) -> Iterator[tuple[Path, int, dict[str, Any]]]:
    uproot, _ = _require_root_stack()
    for source_path in paths:
        source = Path(source_path)
        with uproot.open(source) as root_file:
            if schema.tree not in root_file:
                raise KeyError(f"tree {schema.tree!r} not found in {source}")
            tree = root_file[schema.tree]
            missing = sorted(set(schema.all_branches()) - set(str(k) for k in tree.keys()))
            if missing:
                raise KeyError(f"missing required branches in {source}: {missing}")
            start = 0
            for arrays in tree.iterate(schema.all_branches(), step_size=step_size, library="ak"):
                yield source, start, arrays
                start += len(arrays[schema.primary.pdg])


def _signed_or_uint64_sentinel_mask(values, sentinels: tuple[int, ...]):
    _, ak = _require_root_stack()
    mask = ak.zeros_like(values, dtype=np.bool_)
    for sentinel in sentinels:
        try:
            mask = mask | (values == sentinel)
        except (OverflowError, ValueError):
            # NumPy 2/Awkward correctly rejects comparing a negative Python
            # integer to an unsigned cell-ID buffer. The wrapped uint64 form
            # below is the only representable spelling in that case.
            pass
        if sentinel < 0:
            try:
                mask = mask | (values == np.uint64(sentinel % (1 << 64)))
            except (OverflowError, ValueError):
                # Signed buffers cannot represent the wrapped uint64 spelling;
                # they were already checked against the signed sentinel.
                pass
    return mask


def select_primary_neutron(arrays: dict[str, Any], schema: BranchSchema):
    """Select exactly one generator-level primary neutron per event.

    Returns p4_total_gev [B,4], kinetic_energy_gev [B], and vertex_mm [B,3].
    Events with zero or multiple matching primaries are marked invalid rather than guessed.
    """
    _, ak = _require_root_stack()
    p = schema.primary
    pdg = arrays[p.pdg]
    mask = pdg == schema.neutron_pdg
    if p.generator_status is not None:
        status = arrays[p.generator_status]
        mask = mask & (status == schema.generator_status_value)
    counts = ak.sum(mask, axis=1)
    valid = counts == 1
    selected_mass = ak.firsts(arrays[p.mass][mask]) * schema.mass_unit_to_gev
    px = ak.firsts(arrays[p.momentum_x][mask]) * schema.momentum_unit_to_gev
    py = ak.firsts(arrays[p.momentum_y][mask]) * schema.momentum_unit_to_gev
    pz = ak.firsts(arrays[p.momentum_z][mask]) * schema.momentum_unit_to_gev
    vx = ak.firsts(arrays[p.vertex_x][mask]) * schema.position_unit_to_mm
    vy = ak.firsts(arrays[p.vertex_y][mask]) * schema.position_unit_to_mm
    vz = ak.firsts(arrays[p.vertex_z][mask]) * schema.position_unit_to_mm
    momentum2 = px * px + py * py + pz * pz
    total = np.sqrt(ak.to_numpy(momentum2) + ak.to_numpy(selected_mass) ** 2)
    p4 = np.stack(
        [total, ak.to_numpy(px), ak.to_numpy(py), ak.to_numpy(pz)], axis=-1
    ).astype(np.float32)
    kinetic = (total - ak.to_numpy(selected_mass)).astype(np.float32)
    vertex = np.stack([ak.to_numpy(vx), ak.to_numpy(vy), ak.to_numpy(vz)], axis=-1).astype(np.float32)
    return p4, kinetic, vertex, ak.to_numpy(valid).astype(bool)


def collection_hits(arrays: dict[str, Any], collection, schema: BranchSchema):
    _, ak = _require_root_stack()
    cell_id = arrays[collection.cell_id]
    energy = arrays[collection.energy] * schema.energy_unit_to_gev
    x = arrays[collection.position_x] * schema.position_unit_to_mm
    y = arrays[collection.position_y] * schema.position_unit_to_mm
    z = arrays[collection.position_z] * schema.position_unit_to_mm
    layer_id = arrays[collection.layer_id] if collection.layer_id is not None else None
    sentinel = _signed_or_uint64_sentinel_mask(cell_id, schema.cell_id_sentinels)
    finite_energy = np.isfinite(energy)
    finite_geometry = np.isfinite(x) & np.isfinite(y) & np.isfinite(z)
    if layer_id is not None:
        finite_geometry = finite_geometry & np.isfinite(layer_id)
    invalid = (~finite_energy) | (energy < 0) | ((~sentinel) & (~finite_geometry))
    if bool(ak.any(invalid)):
        raise ValueError(
            f"collection {collection.name!r} contains a negative/nonfinite energy "
            "or a nonfinite non-sentinel geometry value"
        )
    keep = ~sentinel
    kept_layer = layer_id[keep] if layer_id is not None else None
    return cell_id[keep], kept_layer, energy[keep], x[keep], y[keep], z[keep]


def collection_energy_accounting(arrays: dict[str, Any], collection, schema: BranchSchema):
    """Return per-event all-hit, modeled-readout, and sentinel energy sums.

    Sentinel cell IDs denote deposits without a modeled readout channel. Their
    energy remains part of the stored event-total closure check, but it must not
    be assigned to a valid detector node.
    """
    _, ak = _require_root_stack()
    cell_id = arrays[collection.cell_id]
    energy = arrays[collection.energy] * schema.energy_unit_to_gev
    sentinel = _signed_or_uint64_sentinel_mask(cell_id, schema.cell_id_sentinels)
    invalid = (~np.isfinite(energy)) | (energy < 0)
    if bool(ak.any(invalid)):
        raise ValueError(
            f"collection {collection.name!r} contains a negative or nonfinite energy"
        )
    all_energy = ak.to_numpy(ak.sum(energy, axis=1)).astype(np.float64, copy=False)
    excluded = ak.to_numpy(ak.sum(energy[sentinel], axis=1)).astype(
        np.float64, copy=False
    )
    modeled = all_energy - excluded
    return all_energy, modeled, excluded


def channel_key(subdetector: int, cell_id: int, layer_id: int | None = None) -> str:
    """Return the frozen readout key.

    ECAL and globally unique-ID collections use ``subdetector:cellID``.
    Layer-local HCAL IDs use ``subdetector:layerID:cellID``.
    """
    if layer_id is None:
        return f"{int(subdetector)}:{int(cell_id)}"
    return f"{int(subdetector)}:{int(layer_id)}:{int(cell_id)}"


def write_inspection_json(result: dict[str, Any], path: str | Path) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
