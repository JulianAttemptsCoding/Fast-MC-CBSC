from __future__ import annotations
import torch


def scatter_layer_sum(cell:torch.Tensor,layer_index:torch.Tensor,n_layers:int):
    out=torch.zeros(cell.shape[0],n_layers,device=cell.device,dtype=cell.dtype)
    out.scatter_add_(1,layer_index[None].expand(cell.shape[0],-1),cell)
    return out


def derive_truth(cell_energy:torch.Tensor,layer_index:torch.Tensor,n_layers:int,threshold_gev:float=0.0):
    support=cell_energy>threshold_gev if threshold_gev>0 else cell_energy>0
    positive=torch.where(support,cell_energy,torch.zeros_like(cell_energy))
    layer_energy=scatter_layer_sum(positive,layer_index,n_layers)
    counts=torch.zeros(cell_energy.shape[0],n_layers,device=cell_energy.device,dtype=torch.long)
    counts.scatter_add_(1,layer_index[None].expand(cell_energy.shape[0],-1),support.long())
    active=counts>0; visible=active.any(dim=1); ids=torch.arange(n_layers,device=cell_energy.device)[None].expand(cell_energy.shape[0],-1)
    first=torch.where(active,ids,torch.full_like(ids,n_layers)).min(dim=1).values
    first=torch.where(visible,first,torch.full_like(first,-1)); total=layer_energy.sum(dim=1)
    layer_share=layer_energy/total[:,None].clamp_min(1e-12)
    profile_target=torch.log(layer_share.clamp_min(1e-8))
    profile_mean=(profile_target*active).sum(dim=1,keepdim=True)/active.sum(dim=1,keepdim=True).clamp_min(1)
    profile_target=(profile_target-profile_mean)*active
    cell_share=positive/layer_energy[:,layer_index].clamp_min(1e-12)
    share_target=torch.log(cell_share.clamp_min(1e-8))
    per_layer_log_sum=scatter_layer_sum(share_target*support,layer_index,n_layers)
    per_layer_mean=per_layer_log_sum/counts.clamp_min(1)
    share_target=(share_target-per_layer_mean[:,layer_index])*support
    return {'visible':visible,'total':total,'layer_energy':layer_energy,'counts':counts,'active':active,'first':first,'support':support,'profile_target':profile_target,'share_target':share_target}
