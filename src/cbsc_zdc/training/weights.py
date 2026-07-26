from __future__ import annotations
from typing import Iterable
import math
import torch

DEFAULT_LOSS_WEIGHTS={
 'visible':1.0,'response':1.0,'first_layer':0.5,'active':0.5,'profile_flow':1.0,
 'count':0.75,'support_bce':1.0,'support_rank':0.25,'share_flow':1.0,
}


def weighted_total(losses:dict[str,torch.Tensor],weights:dict[str,float]):
    unknown=set(losses)-set(weights)
    if unknown: raise KeyError(f'missing weights for losses: {sorted(unknown)}')
    return sum(losses[name]*float(weights[name]) for name in losses)


def calibrate_loss_weights(
    model,
    batches: Iterable[dict[str, torch.Tensor]],
    compute_losses,
    max_batches: int = 64,
    clip=(0.25, 4.0),
    expected_losses: set[str] | None = None,
):
    """Gradient-norm calibration inspired by GradNorm, returning fixed auditable weights.

    It measures median gradient norm of each component with respect to the shared condition
    encoder. Returned weights equalize those medians, are clipped, then normalized to mean 1.
    This is a calibration heuristic, not a claim of universal optimality.
    """
    if not 1 <= int(max_batches) <= 64:
        raise ValueError("loss calibration max_batches must be in [1,64]")
    clip_min, clip_max = (float(clip[0]), float(clip[1]))
    if not (
        math.isfinite(clip_min)
        and math.isfinite(clip_max)
        and 0 < clip_min <= clip_max
    ):
        raise ValueError(
            "loss calibration clip bounds must be finite, positive, and ordered"
        )
    records={}
    batches_consumed = 0
    params=[p for p in model.condition.parameters() if p.requires_grad]
    for batch_index,batch in enumerate(batches):
        if batch_index>=max_batches: break
        batches_consumed += 1
        losses=compute_losses(batch)
        for name,loss in losses.items():
            grads=torch.autograd.grad(loss,params,retain_graph=True,allow_unused=True)
            norm=torch.sqrt(sum((g.detach().float().square().sum() for g in grads if g is not None),start=torch.tensor(0.0,device=loss.device)))
            if torch.isfinite(norm) and norm>0: records.setdefault(name,[]).append(float(norm.cpu()))
    medians={name:float(torch.tensor(values).median()) for name,values in records.items() if values}
    if not medians: raise RuntimeError('no finite gradient norms were measured')
    expected = set(medians if expected_losses is None else expected_losses)
    missing = sorted(expected - set(medians))
    extra = sorted(set(medians) - expected)
    if missing or extra:
        raise RuntimeError(
            "gradient calibration component mismatch: "
            f"missing={missing}, extra={extra}"
        )
    nonpositive = sorted(
        name for name, value in medians.items()
        if not math.isfinite(value) or value <= 0
    )
    if nonpositive:
        raise RuntimeError(
            f"gradient calibration has nonpositive/nonfinite medians: {nonpositive}"
        )
    geometric=math.exp(sum(math.log(v) for v in medians.values())/len(medians))
    raw={
        name:max(clip_min,min(clip_max,geometric/value))
        for name,value in medians.items()
    }
    scale=len(raw)/sum(raw.values()); weights={name:value*scale for name,value in raw.items()}
    return {
        'method':'fixed_gradient_norm_calibration',
        'gradient_norm_median':medians,
        'weights':weights,
        'clip':[clip_min,clip_max],
        'max_batches':max_batches,
        'batches_consumed':batches_consumed,
        'measured_components':sorted(medians),
        'pass':True,
    }
