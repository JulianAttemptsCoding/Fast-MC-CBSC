from __future__ import annotations
import torch


def invariant_report(output,layer_index,valid_mask,threshold_gev:float=0.0,tolerance:float=2e-5):
    cell=output.cell_energy; positive=cell>0
    layer_sum=torch.zeros_like(output.layer_energy); layer_sum.scatter_add_(1,layer_index[None].expand(cell.shape[0],-1),cell)
    counts=torch.zeros_like(output.realized_counts); counts.scatter_add_(1,layer_index[None].expand(cell.shape[0],-1),output.support_mask.long())
    report={'nonfinite':int((~torch.isfinite(cell)).sum()),'negative':int((cell<0).sum()),'outside_valid_support':int((positive&(~valid_mask[None])).sum()),'support_mask_mismatch':int((positive!=output.support_mask).sum()),'count_mismatch_max':int((counts-output.realized_counts).abs().max()),'requested_realized_mismatch_max':int((output.requested_counts-output.realized_counts).abs().max()),'layer_closure_max_gev':float((layer_sum-output.layer_energy).abs().max()),'event_closure_max_gev':float((cell.sum(dim=1)-output.total_response).abs().max()),'dust_cells':int(((cell>0)&(cell<threshold_gev)).sum()) if threshold_gev>0 else 0}
    report['pass']=report['nonfinite']==0 and report['negative']==0 and report['outside_valid_support']==0 and report['support_mask_mismatch']==0 and report['count_mismatch_max']==0 and report['requested_realized_mismatch_max']==0 and report['layer_closure_max_gev']<=tolerance and report['event_closure_max_gev']<=tolerance and report['dust_cells']==0
    return report
