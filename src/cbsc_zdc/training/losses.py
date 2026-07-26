from __future__ import annotations
import torch


def support_bce(logits,truth,valid_mask):
    truth=truth.bool()&valid_mask[None]
    positive=truth.sum().clamp_min(1); negative=((~truth)&valid_mask[None]).sum().clamp_min(1)
    pos_weight=(negative/positive).clamp(1.0,100.0)
    return torch.nn.functional.binary_cross_entropy_with_logits(logits[:,valid_mask],truth[:,valid_mask].to(logits.dtype),pos_weight=pos_weight)


def support_pairwise_ranking(logits,truth,valid_mask,max_pairs:int=256):
    losses=[]
    for row in range(logits.shape[0]):
        pos=torch.where(truth[row]&valid_mask)[0]; neg=torch.where((~truth[row])&valid_mask)[0]
        if pos.numel()==0 or neg.numel()==0: continue
        n=min(max_pairs,pos.numel(),neg.numel()); p=pos[torch.randperm(pos.numel(),device=logits.device)[:n]]; q=neg[torch.randperm(neg.numel(),device=logits.device)[:n]]
        losses.append(torch.nn.functional.softplus(-(logits[row,p]-logits[row,q])).mean())
    return torch.stack(losses).mean() if losses else logits.new_zeros(())


def count_cross_entropy(logits,truth_counts,active):
    selected=active.bool()
    # Include inactive zero-count classes too, but downweight them to avoid domination.
    flat_loss=torch.nn.functional.cross_entropy(logits.reshape(-1,logits.shape[-1]),truth_counts.reshape(-1),reduction='none').reshape_as(truth_counts)
    weights=torch.where(selected,torch.ones_like(flat_loss),torch.full_like(flat_loss,0.2))
    return (flat_loss*weights).sum()/weights.sum().clamp_min(1)
