from __future__ import annotations
import copy
from pathlib import Path
from typing import Any
import numpy as np
import torch
from torch.utils.data import DataLoader

from ..data.dataset import ShardedSparseDataset,load_geometry
from ..models.system import CBSCZDC
from ..preflight import validate_frozen_artifacts
from ..training.checkpoint import load_checkpoint
from ..utils import dump_json,load_yaml
from .invariants import invariant_report
from .metrics import c2st_auc,distribution_metrics,high_level_features,response_bins,wasserstein_1d


def _apply_gates(report,gates):
    checks={}; bins=report['response_bins']
    minimum=int(gates.get('min_events_per_energy_bin',2))
    checks['evaluation_event_count']=report['n_events']>=int(gates.get('min_total_evaluation_events',1))
    checks['energy_bin_coverage']=all(row['n']>=minimum for row in bins)
    checks['mean_bias_bins']=checks['energy_bin_coverage'] and all(abs(row['mean_bias_fraction'])<=float(gates['max_abs_mean_bias_fraction']) for row in bins)
    checks['resolution_bins']=checks['energy_bin_coverage'] and all(abs(row['resolution_difference_fraction'])<=float(gates['max_abs_resolution_difference_fraction']) for row in bins)
    checks['zero_response']=abs(report['generated_zero_fraction']-report['truth_zero_fraction'])<=float(gates['max_zero_fraction_absolute_difference'])
    checks['response_wasserstein']=report['response_wasserstein_normalized']<=float(gates['max_response_wasserstein_normalized'])
    checks['hit_count_wasserstein']=report['hit_count_wasserstein_normalized']<=float(gates['max_hit_count_wasserstein_normalized'])
    auc=report.get('high_level_c2st_auc'); checks['high_level_c2st']=auc is not None and np.isfinite(auc) and auc<=float(gates['max_high_level_c2st_auc'])
    checks['structural']=bool(report['invariants']['pass'])
    return {'checks':checks,'pass':all(checks.values())}


def evaluate_checkpoint(checkpoint_path,geometry_path,manifest_path,splits_path,split,output_path,device='cpu',batch_size=16,max_events=None,gates_path=None,seed=20260723):
    geometry=load_geometry(geometry_path,device); payload=torch.load(checkpoint_path,map_location=device,weights_only=False); config=payload['config']
    runtime_config = copy.deepcopy(config)
    runtime_config["geometry"]["path"] = str(Path(geometry_path).resolve())
    runtime_config["data"]["manifest"] = str(Path(manifest_path).resolve())
    runtime_config["data"]["splits"] = str(Path(splits_path).resolve())
    preflight = validate_frozen_artifacts(runtime_config, verify_shards=True)
    model=CBSCZDC(geometry,config).to(device).eval(); model.load_state_dict(payload['model_state'])
    d=config['data']; ds=ShardedSparseDataset(manifest_path,splits_path,split,tuple(d['evaluation_kinetic_gev']),int(config['geometry']['n_nodes']))
    loader=DataLoader(ds,batch_size=batch_size,shuffle=False,num_workers=0)
    truth=[]; generated=[]; kinetic=[]; inv_reports=[]
    seen=0
    with torch.no_grad():
        for batch in loader:
            if max_events is not None and seen>=max_events: break
            if max_events is not None:
                remaining = max_events - seen
                if remaining < len(batch["p4_total_gev"]):
                    batch = {name: value[:remaining] for name, value in batch.items()}
            p4=batch['p4_total_gev'].to(device); out=model.sample(p4,int(config['evaluation'].get('profile_steps',8)),int(config['evaluation'].get('share_steps',8)),seed+seen,True)
            truth.append(batch['cell_energy_gev'].numpy()); generated.append(out.cell_energy.cpu().numpy()); kinetic.append(batch['kinetic_energy_gev'].numpy())
            inv_reports.append(invariant_report(output=out, layer_index=model.layer_index, valid_mask=model.valid_mask, threshold_gev=model.threshold_gev, tolerance=float(config['evaluation'].get('closure_tolerance_gev',2e-5))))
            seen+=len(p4)
    if not truth:
        raise RuntimeError('evaluation selection is empty')
    truth=np.concatenate(truth); generated=np.concatenate(generated); kinetic=np.concatenate(kinetic)
    # Structural check per collected batch, reduced conservatively.
    invariants={'pass':all(x['pass'] for x in inv_reports)}
    for key in inv_reports[0]:
        if key=='pass': continue
        invariants[key]=max(x[key] for x in inv_reports)
    total_t=truth.sum(axis=1); total_g=generated.sum(axis=1); hits_t=(truth>0).sum(axis=1); hits_g=(generated>0).sum(axis=1)
    layer_index=model.layer_index.cpu().numpy(); positions=geometry['positions_mm'].cpu().numpy()
    w_resp=wasserstein_1d(total_t,total_g); w_hit=wasserstein_1d(hits_t,hits_g)
    report={'n_events':int(len(truth)),'preflight':preflight,'truth_zero_fraction':float(np.mean(total_t==0)),'generated_zero_fraction':float(np.mean(total_g==0)),'response_bins':response_bins(kinetic,total_t,total_g,np.array(config['evaluation']['energy_bin_edges_gev'])),'response_wasserstein_gev':w_resp,'response_wasserstein_normalized':float(w_resp/max(np.std(total_t),1e-9)),'hit_count_wasserstein':w_hit,'hit_count_wasserstein_normalized':float(w_hit/max(np.std(hits_t),1e-9)),'high_level_c2st_auc':c2st_auc(high_level_features(truth,layer_index,positions),high_level_features(generated,layer_index,positions),seed),'distribution_metrics':distribution_metrics(truth,generated,layer_index,positions,seed),'invariants':invariants}
    if gates_path: report['decision']=_apply_gates(report,load_yaml(gates_path))
    dump_json(report,output_path); return report
