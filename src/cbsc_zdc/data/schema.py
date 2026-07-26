from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class HitCollectionSchema:
    name: str
    cell_id: str
    energy: str
    position_x: str
    position_y: str
    position_z: str
    layer_id: str | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "HitCollectionSchema":
        return cls(
            name=payload["name"],
            cell_id=payload["cell_id"],
            energy=payload["energy"],
            position_x=payload["position_x"],
            position_y=payload["position_y"],
            position_z=payload["position_z"],
            layer_id=payload.get("layer_id"),
        )


@dataclass(frozen=True)
class PrimarySchema:
    pdg: str
    mass: str
    momentum_x: str
    momentum_y: str
    momentum_z: str
    vertex_x: str
    vertex_y: str
    vertex_z: str
    generator_status: str | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PrimarySchema":
        return cls(
            pdg=payload["pdg"],
            mass=payload["mass"],
            momentum_x=payload["momentum_x"],
            momentum_y=payload["momentum_y"],
            momentum_z=payload["momentum_z"],
            vertex_x=payload["vertex_x"],
            vertex_y=payload["vertex_y"],
            vertex_z=payload["vertex_z"],
            generator_status=payload.get("generator_status"),
        )


@dataclass(frozen=True)
class BranchSchema:
    tree: str
    primary: PrimarySchema
    ecal: HitCollectionSchema
    hcal: HitCollectionSchema
    neutron_pdg: int = 2112
    generator_status_value: int = 1
    cell_id_sentinels: tuple[int, ...] = (-100,)
    energy_unit_to_gev: float = 1.0
    position_unit_to_mm: float = 1.0
    momentum_unit_to_gev: float = 1.0
    mass_unit_to_gev: float = 1.0
    event_total_energy: str | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "BranchSchema":
        return cls(
            tree=payload["tree"],
            primary=PrimarySchema.from_dict(payload["primary"]),
            ecal=HitCollectionSchema.from_dict(payload["ecal"]),
            hcal=HitCollectionSchema.from_dict(payload["hcal"]),
            neutron_pdg=int(payload.get("neutron_pdg", 2112)),
            generator_status_value=int(payload.get("generator_status_value", 1)),
            cell_id_sentinels=tuple(int(x) for x in payload.get("cell_id_sentinels", [-100])),
            energy_unit_to_gev=float(payload.get("energy_unit_to_gev", 1.0)),
            position_unit_to_mm=float(payload.get("position_unit_to_mm", 1.0)),
            momentum_unit_to_gev=float(payload.get("momentum_unit_to_gev", 1.0)),
            mass_unit_to_gev=float(payload.get("mass_unit_to_gev", 1.0)),
            event_total_energy=payload.get("event_total_energy"),
        )

    def all_branches(self) -> list[str]:
        p = self.primary
        collections = (self.ecal, self.hcal)
        names = [
            p.pdg,
            p.mass,
            p.momentum_x,
            p.momentum_y,
            p.momentum_z,
            p.vertex_x,
            p.vertex_y,
            p.vertex_z,
        ]
        if p.generator_status is not None:
            names.append(p.generator_status)
        for collection in collections:
            names.extend(
                [
                    collection.cell_id,
                    collection.energy,
                    collection.position_x,
                    collection.position_y,
                    collection.position_z,
                ]
            )
            if collection.layer_id is not None:
                names.append(collection.layer_id)
        if self.event_total_energy is not None:
            names.append(self.event_total_energy)
        return names
