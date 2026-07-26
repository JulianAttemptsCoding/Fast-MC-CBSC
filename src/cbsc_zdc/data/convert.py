from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from .root_io import (
    collection_energy_accounting,
    collection_hits,
    iter_root_chunks,
    load_branch_schema,
    select_primary_neutron,
)
from ..utils import dump_json, load_json, sha256_file


def convert_root_corpus(
    root_paths: list[str|Path], schema_path: str|Path, geometry_dir: str|Path,
    output_dir: str|Path, target_mode: str='raw_deposit', threshold_gev: float=0.0,
    min_kinetic_gev: float=0.0, max_kinetic_gev: float=300.0,
    shard_size: int=4096, step_size: int=2048, fixed_vertex_tolerance_mm: float=1e-3,
) -> dict[str,Any]:
    if target_mode not in {'raw_deposit','thresholded_readout'}: raise ValueError('invalid target_mode')
    if target_mode=='raw_deposit' and threshold_gev!=0: raise ValueError('raw_deposit requires threshold_gev=0')
    if target_mode=='thresholded_readout' and threshold_gev<=0: raise ValueError('thresholded_readout requires threshold_gev>0')
    schema=load_branch_schema(schema_path); geometry_dir=Path(geometry_dir)
    geometry_manifest=load_json(geometry_dir/'geometry_manifest.json'); cell_map=load_json(geometry_dir/'cell_map.json')
    output=Path(output_dir); output.mkdir(parents=True,exist_ok=True)
    pending=[]; shards=[]; rejected={'primary_selection':0,'energy_range':0,'vertex':0,'unknown_cell':0,'invalid_hit':0}
    fixed_vertex=None; global_id=0; source_group_map={str(Path(p).resolve()):i for i,p in enumerate(root_paths)}
    event_total_residual_max = 0.0
    modeled_readout_residual_max = 0.0
    excluded_sentinel_energy_total = 0.0
    excluded_sentinel_energy_max = 0.0
    excluded_sentinel_event_count = 0
    map_groups: dict[tuple[int, int], tuple[np.ndarray, np.ndarray]] = {}
    grouped_entries: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for text_key, node_index in cell_map.items():
        parts = text_key.split(":")
        if len(parts) == 2:
            subdetector, cell_id = parts
            raw_layer = -1
        elif len(parts) == 3:
            subdetector, raw_layer, cell_id = parts
        else:
            raise ValueError(f"invalid frozen cell-map key: {text_key}")
        grouped_entries.setdefault(
            (int(subdetector), int(raw_layer)), []
        ).append((int(cell_id), int(node_index)))
    for group_key, entries in grouped_entries.items():
        entries.sort()
        group_ids = np.asarray([entry[0] for entry in entries], dtype=np.uint64)
        if len(group_ids) != len(np.unique(group_ids)):
            raise ValueError(f"duplicate cell ID in frozen map group {group_key}")
        map_groups[group_key] = (
            group_ids,
            np.asarray([entry[1] for entry in entries], dtype=np.int64),
        )

    def flush():
        nonlocal pending
        if not pending: return
        p4=np.stack([x['p4'] for x in pending]); kinetic=np.array([x['kinetic'] for x in pending],dtype=np.float32)
        event_id=np.array([x['event_id'] for x in pending],dtype=np.int64); source_group=np.array([x['source_group'] for x in pending],dtype=np.int64)
        ptr=[0]; indices=[]; energies=[]
        for x in pending:
            indices.extend(x['indices']); energies.extend(x['energies']); ptr.append(len(indices))
        path=output/f"shard_{len(shards):05d}.npz"
        np.savez_compressed(path,p4_total_gev=p4.astype(np.float32),kinetic_energy_gev=kinetic,event_id=event_id,source_group=source_group,event_ptr=np.array(ptr,dtype=np.int64),cell_index=np.array(indices,dtype=np.int32),cell_energy_gev=np.array(energies,dtype=np.float32))
        shards.append({'path':path.name,'n_events':len(pending),'n_hits':len(indices),'sha256':sha256_file(path)})
        pending=[]

    try: import awkward as ak  # type: ignore
    except ImportError as exc: raise RuntimeError("install root extras") from exc

    def map_collection(collection, subdetector):
        ids, layer_ids, energies = collection[:3]
        if target_mode == "thresholded_readout":
            retained = energies >= threshold_gev
            ids = ids[retained]
            energies = energies[retained]
            if layer_ids is not None:
                layer_ids = layer_ids[retained]
        counts = ak.to_numpy(ak.num(ids, axis=1)).astype(np.int64, copy=False)
        flat_ids = ak.to_numpy(ak.flatten(ids, axis=None)).astype(np.uint64, copy=False)
        if layer_ids is None:
            flat_layers = np.full(flat_ids.shape, -1, dtype=np.int64)
        else:
            flat_layers = ak.to_numpy(ak.flatten(layer_ids, axis=None)).astype(
                np.int64, copy=False
            )
        mapped = np.empty(flat_ids.size, dtype=np.int64)
        for raw_layer in np.unique(flat_layers):
            group_key = (int(subdetector), int(raw_layer))
            if group_key not in map_groups:
                raise ValueError(
                    "unknown frozen channel group encountered: "
                    f"subdetector={group_key[0]}, layer_id={group_key[1]}"
                )
            group_mask = flat_layers == raw_layer
            query_ids = flat_ids[group_mask]
            group_ids, group_values = map_groups[group_key]
            positions = np.searchsorted(group_ids, query_ids)
            in_bounds = positions < len(group_ids)
            matches = np.zeros(len(query_ids), dtype=bool)
            matches[in_bounds] = (
                group_ids[positions[in_bounds]] == query_ids[in_bounds]
            )
            if not matches.all():
                bad_id = int(query_ids[np.where(~matches)[0][0]])
                raise ValueError(
                    "unknown frozen channel encountered: "
                    f"subdetector={group_key[0]}, "
                    f"layer_id={group_key[1]}, cell_id={bad_id}"
                )
            mapped[group_mask] = group_values[positions]
        return ak.unflatten(mapped, counts), energies

    for source,start,arrays in iter_root_chunks(root_paths,schema,step_size):
        if start % max(step_size * 25, 1) == 0:
            print(
                f"conversion source={source.name} entry_start={start} accepted={global_id}",
                flush=True,
            )
        p4,kinetic,vertex,valid=select_primary_neutron(arrays,schema)
        if start == 0:
            print("conversion-first-chunk primary-selection complete", flush=True)
        ecal=collection_hits(arrays,schema.ecal,schema); hcal=collection_hits(arrays,schema.hcal,schema)
        ecal_all, ecal_modeled, ecal_excluded = collection_energy_accounting(
            arrays, schema.ecal, schema
        )
        hcal_all, hcal_modeled, hcal_excluded = collection_energy_accounting(
            arrays, schema.hcal, schema
        )
        all_hit_energy = ecal_all + hcal_all
        modeled_hit_energy = ecal_modeled + hcal_modeled
        excluded_hit_energy = ecal_excluded + hcal_excluded
        if start == 0:
            print("conversion-first-chunk hit-validation complete", flush=True)
        ecal_indices, ecal_energies = map_collection(ecal, 0)
        if start == 0:
            print("conversion-first-chunk ECAL mapping complete", flush=True)
        hcal_indices, hcal_energies = map_collection(hcal, 1)
        if start == 0:
            print("conversion-first-chunk HCAL mapping complete", flush=True)
        for local in range(len(valid)):
            if schema.event_total_energy is not None:
                stored = ak.to_numpy(arrays[schema.event_total_energy][local])
                if stored.size != 1 or not np.isfinite(stored[0]):
                    raise ValueError(
                        f"invalid event-total reference in {source} at entry {start + local}"
                    )
                residual = abs(float(all_hit_energy[local]) - float(stored[0]))
                event_total_residual_max = max(event_total_residual_max, residual)
                if residual > 1e-6:
                    raise ValueError(
                        f"all-hit sum disagrees with event total in {source} at entry "
                        f"{start + local}: residual={residual:.6g} GeV"
                    )
            excluded = float(excluded_hit_energy[local])
            excluded_sentinel_energy_total += excluded
            excluded_sentinel_energy_max = max(
                excluded_sentinel_energy_max, excluded
            )
            excluded_sentinel_event_count += int(excluded > 0)
            if not valid[local]: rejected['primary_selection']+=1; continue
            if not (
                np.isfinite(p4[local]).all()
                and np.isfinite(kinetic[local])
                and np.isfinite(vertex[local]).all()
            ):
                raise ValueError(
                    f"nonfinite primary values in {source} at entry {start + local}"
                )
            k=float(kinetic[local])
            if not (min_kinetic_gev<=k<=max_kinetic_gev): rejected['energy_range']+=1; continue
            if fixed_vertex is None: fixed_vertex=vertex[local].astype(np.float64)
            if np.max(np.abs(vertex[local]-fixed_vertex))>fixed_vertex_tolerance_mm: rejected['vertex']+=1; continue
            event_indices = np.concatenate(
                [
                    ak.to_numpy(ecal_indices[local]).astype(np.int64, copy=False),
                    ak.to_numpy(hcal_indices[local]).astype(np.int64, copy=False),
                ]
            )
            event_energies = np.concatenate(
                [
                    ak.to_numpy(ecal_energies[local]).astype(np.float64, copy=False),
                    ak.to_numpy(hcal_energies[local]).astype(np.float64, copy=False),
                ]
            )
            if event_indices.size:
                unique_indices, inverse = np.unique(event_indices, return_inverse=True)
                summed = np.zeros(unique_indices.size, dtype=np.float64)
                np.add.at(summed, inverse, event_energies)
                positive = summed > 0
                unique_indices = unique_indices[positive]
                summed = summed[positive]
                accumulation = {
                    int(index): float(energy)
                    for index, energy in zip(unique_indices, summed)
                }
            else:
                accumulation = {}
            modeled_residual = abs(
                float(sum(accumulation.values())) - float(modeled_hit_energy[local])
            )
            modeled_readout_residual_max = max(
                modeled_readout_residual_max, modeled_residual
            )
            if modeled_residual > 1e-6:
                raise ValueError(
                    f"mapped readout sum disagrees with non-sentinel hit sum in "
                    f"{source} at entry {start + local}: "
                    f"residual={modeled_residual:.6g} GeV"
                )
            ids=sorted(accumulation); vals=[accumulation[i] for i in ids]
            pending.append({'p4':p4[local],'kinetic':k,'event_id':global_id,'source_group':source_group_map[str(source.resolve())],'indices':ids,'energies':vals})
            global_id+=1
            if len(pending)>=shard_size: flush()
    flush()
    n_events=sum(x['n_events'] for x in shards)
    if n_events==0: raise RuntimeError('conversion produced zero events')
    manifest={'format_version':1,'target_mode':target_mode,'threshold_gev':threshold_gev,'n_events':n_events,'n_nodes':geometry_manifest['n_nodes'],'n_layers':geometry_manifest['n_layers'],'geometry_hash':geometry_manifest['geometry_hash'],'schema_sha256':sha256_file(schema_path),'source_files':[{'path':str(Path(p).resolve()),'sha256':sha256_file(p),'source_group':source_group_map[str(Path(p).resolve())]} for p in root_paths],'shards':shards,'rejected':rejected,'fixed_vertex_mm':fixed_vertex.tolist() if fixed_vertex is not None else None,'event_total_reference_semantics':'all stored deposits including sentinel non-readout hits' if schema.event_total_energy is not None else None,'event_total_residual_max_gev':event_total_residual_max if schema.event_total_energy is not None else None,'modeled_target_semantics':'raw non-sentinel readout deposits','modeled_readout_residual_max_gev':modeled_readout_residual_max,'excluded_sentinel_energy_total_gev':excluded_sentinel_energy_total,'excluded_sentinel_energy_max_gev':excluded_sentinel_energy_max,'excluded_sentinel_event_count':excluded_sentinel_event_count}
    dump_json(manifest,output/'dataset_manifest.json'); return manifest
