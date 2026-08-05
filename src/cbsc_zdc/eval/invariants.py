from __future__ import annotations
import torch


def closure_tolerances(config) -> tuple[float, float]:
    """Read the absolute floor and the relative term from a frozen config.

    One reader for every caller, so the four gates cannot drift apart. The
    relative default is 0.0 -- a config frozen before 2026-08-05 has no such key
    and must keep meaning exactly what it meant when its run was accepted.
    """
    evaluation = config.get("evaluation", {}) or {}
    return (
        float(evaluation.get("closure_tolerance_gev", 2e-5)),
        float(evaluation.get("closure_tolerance_relative", 0.0)),
    )


def invariant_report(output,layer_index,valid_mask,threshold_gev:float=0.0,tolerance:float=2e-5,relative_tolerance:float=0.0):
    """Structural invariants for one generated batch.

    The two closure fields compare float32 reductions over thousands of cells,
    so the residual they carry is not a constant: it is a small number of units
    in the last place of the magnitude being summed, and therefore grows with
    that magnitude. `tolerance` alone is absolute and cannot express this. It
    ended `dicos-p10` at epoch 40 of a 39..62 horizon on a residual of
    2.6702880859375e-05 GeV against 2e-5 -- exactly seven float32 ULP at that
    event's 33.1646 GeV response, with every structural field exactly zero.

    `relative_tolerance` adds the missing scale term. The bound applied is

        max(tolerance, relative_tolerance * closure_scale_gev)

    where the scale is the largest total event response in the batch, which is
    the magnitude the reduction actually ran over. **The default is 0.0, so a
    caller that does not pass it gets precisely the historical absolute rule**
    and every frozen config predating this field still means what it meant.

    Every term is written into the report, so any verdict can be recomputed
    from the record without re-running the generator.
    """
    cell=output.cell_energy; positive=cell>0
    layer_sum=torch.zeros_like(output.layer_energy); layer_sum.scatter_add_(1,layer_index[None].expand(cell.shape[0],-1),cell)
    counts=torch.zeros_like(output.realized_counts); counts.scatter_add_(1,layer_index[None].expand(cell.shape[0],-1),output.support_mask.long())
    report={'nonfinite':int((~torch.isfinite(cell)).sum()),'negative':int((cell<0).sum()),'outside_valid_support':int((positive&(~valid_mask[None])).sum()),'support_mask_mismatch':int((positive!=output.support_mask).sum()),'count_mismatch_max':int((counts-output.realized_counts).abs().max()),'requested_realized_mismatch_max':int((output.requested_counts-output.realized_counts).abs().max()),'layer_closure_max_gev':float((layer_sum-output.layer_energy).abs().max()),'event_closure_max_gev':float((cell.sum(dim=1)-output.total_response).abs().max()),'dust_cells':int(((cell>0)&(cell<threshold_gev)).sum()) if threshold_gev>0 else 0}
    absolute=float(tolerance); relative=float(relative_tolerance)
    scale=float(output.total_response.abs().max()) if output.total_response.numel() else 0.0
    # Only a declared relative term may participate. `max(absolute, 0.0)` would
    # silently raise a deliberately negative tolerance to 0.0, which is how a
    # test that forces failure by setting -1.0 would start passing.
    effective=max(absolute,relative*scale) if relative>0.0 else absolute
    report['closure_tolerance_absolute_gev']=absolute
    report['closure_tolerance_relative']=relative
    report['closure_scale_gev']=scale
    report['closure_tolerance_effective_gev']=effective
    report['pass']=report['nonfinite']==0 and report['negative']==0 and report['outside_valid_support']==0 and report['support_mask_mismatch']==0 and report['count_mismatch_max']==0 and report['requested_realized_mismatch_max']==0 and report['layer_closure_max_gev']<=effective and report['event_closure_max_gev']<=effective and report['dust_cells']==0
    return report
