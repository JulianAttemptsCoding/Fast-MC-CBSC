from __future__ import annotations

import csv
import math
import shutil
import time
from pathlib import Path
from typing import Any

import torch
from torch.utils.data import DataLoader

from ..config import RunPaths
from ..contracts import NEUTRON_MASS_GEV
from ..data.dataset import ShardedSparseDataset,load_geometry
from ..eval.invariants import invariant_report
from ..eval.visualization import export_epoch_visualization
from ..models.system import CBSCZDC
from ..preflight import validate_frozen_artifacts
from ..utils import (
    dump_json,
    environment_snapshot,
    seed_everything,
    sha256_file,
    sha256_json,
)
from .checkpoint import load_checkpoint,save_checkpoint
from .flow_matching import linear_flow_tuple,masked_mse
from .losses import count_cross_entropy,support_bce,support_pairwise_ranking
from .truth import derive_truth
from .weights import weighted_total


STAGE_LOSSES={
 'response':{'visible','response'},
 'profile':{'first_layer','active','profile_flow'},
 'count':{'count'},
 'support':{'support_bce','support_rank'},
 'share':{'share_flow'},
 'joint':{'visible','response','first_layer','active','profile_flow','count','support_bce','support_rank','share_flow'},
}
EXPECTED_PREVIOUS_STAGE = {
    "profile": "response",
    "count": "profile",
    "support": "count",
    "share": "support",
}


def move_batch(batch,device): return {k:v.to(device,non_blocking=True) for k,v in batch.items()}


def compute_component_losses(model:CBSCZDC,batch:dict[str,torch.Tensor],stage:str='joint'):
    if stage not in STAGE_LOSSES:
        raise ValueError(f"unknown training stage {stage}")
    requested = STAGE_LOSSES[stage]
    p4 = batch["p4_total_gev"]
    cell = batch["cell_energy_gev"]
    cond = model.encode_condition(p4)
    truth = derive_truth(cell, model.layer_index, model.n_layers, model.threshold_gev)
    losses = {}

    if requested & {"visible", "response"}:
        visible_loss, response_loss = model.response.nll(
            cond, truth["total"], truth["visible"]
        )
        losses["visible"] = visible_loss
        losses["response"] = response_loss

    if requested & {"first_layer", "active", "profile_flow"}:
        visible = truth["visible"]
        first_safe = truth["first"].clamp_min(0)
        first_logits = model.profile.first_logits(cond, truth["total"])
        losses["first_layer"] = (
            torch.nn.functional.cross_entropy(
                first_logits[visible], truth["first"][visible]
            )
            if visible.any()
            else cond.new_zeros(())
        )
        active_logits = model.profile.active_logits(cond, truth["total"], first_safe)
        active_mask = visible[:, None].expand_as(active_logits)
        losses["active"] = (
            torch.nn.functional.binary_cross_entropy_with_logits(
                active_logits[active_mask],
                truth["active"][active_mask].to(cond.dtype),
            )
            if active_mask.any()
            else cond.new_zeros(())
        )
        profile_state, flow_time, profile_velocity = linear_flow_tuple(
            truth["profile_target"], truth["active"]
        )
        predicted_profile = model.profile.flow(
            profile_state,
            flow_time.reshape(cond.shape[0], -1)[:, :1],
            cond,
            truth["total"],
            truth["active"],
        )
        losses["profile_flow"] = masked_mse(
            predicted_profile, profile_velocity, truth["active"]
        )

    if "count" in requested:
        count_logits = model.counts.logits(
            cond,
            truth["layer_energy"],
            truth["active"],
            model.threshold_gev,
        )
        losses["count"] = count_cross_entropy(
            count_logits, truth["counts"], truth["active"]
        )

    if requested & {"support_bce", "support_rank"}:
        support_logits = model.support_logits(
            cond, truth["layer_energy"], truth["counts"]
        )
        losses["support_bce"] = support_bce(
            support_logits, truth["support"], model.valid_mask
        )
        losses["support_rank"] = support_pairwise_ranking(
            support_logits, truth["support"], model.valid_mask
        )

    if "share_flow" in requested:
        share_state, share_time, share_velocity = linear_flow_tuple(
            truth["share_target"], truth["support"]
        )
        predicted_share = model.share_velocity(
            share_state,
            share_time.reshape(cond.shape[0], -1)[:, :1],
            cond,
            truth["layer_energy"],
            truth["counts"],
            truth["support"],
        )
        losses["share_flow"] = masked_mse(
            predicted_share, share_velocity, truth["support"]
        )

    return losses, truth


def _set_trainable(model:CBSCZDC,stage:str,train_condition_encoder:bool=False):
    for p in model.parameters(): p.requires_grad=False
    modules={'response':[model.response],'profile':[model.profile],'count':[model.counts],'support':[model.support],'share':[model.share],'joint':[model]}
    for module in modules[stage]:
        for p in module.parameters(): p.requires_grad=True
    if stage=='response' or train_condition_encoder:
        for p in model.condition.parameters(): p.requires_grad=True


def _seed_worker(worker_id:int) -> None:
    # Match PyTorch's documented DataLoader reproducibility pattern.
    import random
    import numpy as np
    worker_seed=torch.initial_seed() % (2**32)
    np.random.seed(worker_seed)
    random.seed(worker_seed)


def _make_loader(config,split,shuffle):
    d=config['data']; low,high=(d['train_kinetic_gev'] if split=='train' else d['evaluation_kinetic_gev'])
    ds=ShardedSparseDataset(d['manifest'],d['splits'],split,(float(low),float(high)),int(config['geometry']['n_nodes']))
    generator=torch.Generator().manual_seed(int(config['training']['seed']))
    return DataLoader(ds,batch_size=int(config['training']['batch_size']),shuffle=shuffle,num_workers=int(config['training'].get('num_workers',0)),pin_memory=torch.cuda.is_available(),drop_last=shuffle,generator=generator,worker_init_fn=_seed_worker,persistent_workers=int(config['training'].get('num_workers',0))>0)


def _checkpoint_invariant_gate(model: CBSCZDC, config: dict[str, Any], seed: int):
    kinetic = torch.tensor(
        [0.0, 50.0, 100.0, 150.0, 200.0, 250.0, 300.0],
        device=model.node_features.device,
        dtype=torch.float64,
    )
    total = kinetic + NEUTRON_MASS_GEV
    momentum = torch.sqrt(torch.clamp(total.square() - NEUTRON_MASS_GEV**2, min=0.0))
    p4 = torch.stack(
        [total, torch.zeros_like(total), torch.zeros_like(total), momentum], dim=1
    ).to(torch.float32)
    output = model.sample(
        p4,
        int(config["evaluation"].get("profile_steps", 8)),
        int(config["evaluation"].get("share_steps", 8)),
        seed=seed,
        stochastic=True,
    )
    return invariant_report(
        output,
        model.layer_index,
        model.valid_mask,
        model.threshold_gev,
        float(config["evaluation"].get("closure_tolerance_gev", 2e-5)),
    )


def _restore_resume_best(
    resume_best: str | Path,
    last_payload: dict[str, Any],
    stage: str,
    destination: Path,
) -> float:
    """Validate and preserve the selected best checkpoint for a resumed run."""
    best_payload=torch.load(
        Path(resume_best),map_location='cpu',weights_only=False
    )
    if best_payload.get('stage') != stage:
        raise ValueError(
            f"resume best checkpoint stage {best_payload.get('stage')} "
            f"!= expected {stage}"
        )
    if int(best_payload.get('epoch',-1)) > int(last_payload['epoch']):
        raise ValueError("resume best checkpoint is newer than last checkpoint")
    best=float(last_payload['best_metric'])
    best_file_metric=float(best_payload.get('best_metric',float('nan')))
    if not math.isfinite(best) or not math.isfinite(best_file_metric):
        raise ValueError("resume checkpoint best metric must be finite")
    if not math.isclose(best,best_file_metric,rel_tol=1e-12,abs_tol=1e-12):
        raise ValueError(
            "resume last/best metric mismatch: "
            f"last={best}, best={best_file_metric}"
        )
    if best_payload.get('provenance') != last_payload.get('provenance'):
        raise ValueError("resume last/best checkpoint provenance mismatch")
    shutil.copy2(Path(resume_best),destination)
    return best


def _mid_epoch_contract(
    config: dict[str, Any],
    *,
    include_template_provenance: bool,
) -> dict[str, Any]:
    training_excluded = {
        "checkpoint_interval_updates",
        "initialize_from",
        "initialize_from_relative",
        "initialize_from_sha256",
        "resume_from",
        "resume_from_relative",
        "resume_from_sha256",
        "resume_progress_from",
        "resume_progress_from_relative",
        "resume_progress_from_sha256",
        "resume_best_from",
        "resume_best_from_relative",
        "resume_best_from_sha256",
    }
    data_excluded = {"manifest", "splits"}
    geometry_excluded = {"path"}
    contract = {
        "data": {
            key:value
            for key,value in config["data"].items()
            if key not in data_excluded
        },
        "geometry": {
            key:value
            for key,value in config["geometry"].items()
            if key not in geometry_excluded
        },
        "model": config["model"],
        "training": {
            key:value
            for key,value in config["training"].items()
            if key not in training_excluded
        },
        "loss_weights": config["loss_weights"],
        "evaluation": config["evaluation"],
        "provenance": {
            key:value
            for key,value in config.get("provenance", {}).items()
            if (
                (key.endswith("_sha256") or key == "dataset_geometry_hash")
                and (include_template_provenance or key != "template_sha256")
            )
        },
    }
    return contract


def _mid_epoch_contract_sha256(config: dict[str, Any]) -> str:
    """Hash every setting that can change an in-flight training trajectory."""
    return sha256_json(
        _mid_epoch_contract(config, include_template_provenance=False)
    )


def _legacy_mid_epoch_contract_sha256(config: dict[str, Any]) -> str:
    """Reproduce format-v3 progress hashes written before resume-template QA."""
    return sha256_json(
        _mid_epoch_contract(config, include_template_provenance=True)
    )


def _validate_mid_epoch_progress(
    payload: dict[str, Any],
    loader_batches: int,
    accumulation: int,
    batch_size: int,
    seed: int,
    contract_sha256: str,
) -> dict[str, Any]:
    progress = payload.get("progress")
    if not isinstance(progress, dict):
        raise ValueError("resume_progress_from checkpoint has no progress payload")
    required = {
        "epoch",
        "next_step",
        "loader_batches",
        "gradient_accumulation",
        "batch_size",
        "epoch_seed",
        "optimizer_boundary",
        "train_sum",
        "train_count",
        "component_sum",
        "updates",
        "elapsed_seconds",
        "contract_sha256",
    }
    missing = required - set(progress)
    if missing:
        raise ValueError(
            f"mid-epoch progress payload missing fields: {sorted(missing)}"
        )
    epoch = int(progress["epoch"])
    next_step = int(progress["next_step"])
    if int(payload.get("epoch", -1)) != epoch:
        raise ValueError("mid-epoch checkpoint epoch/payload mismatch")
    if int(progress["loader_batches"]) != loader_batches:
        raise ValueError("mid-epoch DataLoader length changed")
    if int(progress["gradient_accumulation"]) != accumulation:
        raise ValueError("mid-epoch gradient accumulation changed")
    if int(progress["batch_size"]) != batch_size:
        raise ValueError("mid-epoch batch size changed")
    if int(progress["epoch_seed"]) != seed + epoch:
        raise ValueError("mid-epoch data-order seed changed")
    progress_contract_sha256 = str(progress["contract_sha256"])
    if progress_contract_sha256 != contract_sha256:
        source_config = payload.get("config")
        legacy_compatible = (
            isinstance(source_config, dict)
            and _mid_epoch_contract_sha256(source_config) == contract_sha256
            and _legacy_mid_epoch_contract_sha256(source_config)
            == progress_contract_sha256
        )
        if not legacy_compatible:
            raise ValueError("mid-epoch training contract changed")
    if not bool(progress["optimizer_boundary"]):
        raise ValueError("mid-epoch checkpoint was not saved at optimizer boundary")
    if not 0 < next_step < loader_batches:
        raise ValueError("mid-epoch next_step must be inside the epoch")
    if next_step % accumulation != 0:
        raise ValueError("mid-epoch next_step is not an accumulation boundary")
    if int(progress["train_count"]) != next_step:
        raise ValueError("mid-epoch train_count/next_step mismatch")
    if int(progress["updates"]) <= 0:
        raise ValueError("mid-epoch completed update count must be positive")
    if float(progress["elapsed_seconds"]) < 0:
        raise ValueError("mid-epoch elapsed time must be nonnegative")
    if not isinstance(progress["component_sum"], dict):
        raise ValueError("mid-epoch component_sum must be a mapping")
    numeric = [
        float(progress["train_sum"]),
        float(progress["elapsed_seconds"]),
        *[float(value) for value in progress["component_sum"].values()],
    ]
    if not all(math.isfinite(value) for value in numeric):
        raise ValueError("mid-epoch progress contains nonfinite aggregates")
    return progress


def train_from_config(
    config:dict[str,Any],
    epoch_callback=None,
    progress_callback=None,
) -> dict[str,Any]:
    stage=config['training'].get('stage','joint')
    if stage not in STAGE_LOSSES: raise ValueError(f'unknown training stage {stage}')
    preflight = validate_frozen_artifacts(config, verify_shards=True)
    seed=int(config['training']['seed']); deterministic=bool(config['training'].get('deterministic_debug',False)); seed_everything(seed,deterministic)
    device=torch.device(config['training'].get('device','cuda' if torch.cuda.is_available() else 'cpu'))
    geometry=load_geometry(config['geometry']['path'],device); model=CBSCZDC(geometry,config).to(device)
    initialize=config['training'].get('initialize_from')
    if stage in {'profile','count','support','share'} and not initialize:
        raise ValueError(f'{stage} stage requires training.initialize_from so the shared condition encoder is not random')
    if initialize:
        expected_previous = EXPECTED_PREVIOUS_STAGE.get(stage)
        initialized = load_checkpoint(
            initialize,
            model,
            map_location=device,
            expected_stage=expected_previous,
        )
        if stage == "joint" and initialized.get("stage") not in {"share", "joint"}:
            raise ValueError(
                "joint initialization must come from a share or joint checkpoint"
            )
    _set_trainable(model,stage,bool(config['training'].get('train_condition_encoder',False)))
    train_loader=_make_loader(config,'train',True); val_loader=_make_loader(config,'validation',False)
    parameters=[p for p in model.parameters() if p.requires_grad]
    optimizer=torch.optim.AdamW(parameters,lr=float(config['training']['learning_rate']),betas=tuple(config['training'].get('betas',[0.9,0.999])),eps=float(config['training'].get('eps',1e-8)),weight_decay=float(config['training'].get('weight_decay',0.01)))
    epochs=int(config['training']['epochs']); total_updates=max(1,math.ceil(len(train_loader)/int(config['training'].get('gradient_accumulation',1)))*epochs)
    scheduler=torch.optim.lr_scheduler.CosineAnnealingLR(optimizer,T_max=total_updates,eta_min=float(config['training'].get('min_learning_rate',1e-6)))
    amp_enabled=device.type=='cuda' and bool(config['training'].get('amp',True)); scaler=torch.amp.GradScaler('cuda',enabled=amp_enabled)
    run=RunPaths(Path(config['project']['run_dir'])); run.create(); dump_json(environment_snapshot(),run.root/'environment.json')
    dump_json(preflight, run.reports/'preflight.json')
    dump_json(config,run.root/'resolved_config.json')
    resume=config['training'].get('resume_from')
    resume_progress=config['training'].get('resume_progress_from')
    start_epoch=0
    best=float('inf')
    mid_epoch_progress = None
    if resume:
        resume_best=config['training'].get('resume_best_from')
        if not resume_best:
            raise ValueError(
                "resume requires training.resume_best_from so checkpoint "
                "selection survives a worker restart"
            )
        payload=load_checkpoint(
            resume,model,optimizer,scheduler,scaler,device,stage,restore_rng=True
        )
        best=_restore_resume_best(
            resume_best,payload,stage,run.checkpoints/'best.pt'
        )
        start_epoch=int(payload['epoch'])+1
        if start_epoch >= epochs:
            raise ValueError(
                f"resume checkpoint epoch {payload['epoch']} leaves no epoch "
                f"before configured training.epochs={epochs}"
            )
    weights={k:float(v) for k,v in config['loss_weights'].items()}; accumulation=int(config['training'].get('gradient_accumulation',1)); clip=float(config['training'].get('gradient_clip_norm',1.0)); patience=int(config['training'].get('early_stopping_patience',10)); stale=0
    if resume_progress:
        payload=load_checkpoint(
            resume_progress,
            model,
            optimizer,
            scheduler,
            scaler,
            device,
            stage,
            restore_rng=True,
        )
        mid_epoch_progress = _validate_mid_epoch_progress(
            payload,
            len(train_loader),
            accumulation,
            int(config['training']['batch_size']),
            seed,
            _mid_epoch_contract_sha256(config),
        )
        best=float(payload['best_metric'])
        resume_best=config['training'].get('resume_best_from')
        if math.isfinite(best):
            if not resume_best:
                raise ValueError(
                    "finite mid-epoch best metric requires resume_best_from"
                )
            best=_restore_resume_best(
                resume_best,payload,stage,run.checkpoints/'best.pt'
            )
        elif not (
            math.isinf(best)
            and best > 0
            and int(mid_epoch_progress["epoch"]) == 0
            and not resume_best
        ):
            raise ValueError(
                "mid-epoch checkpoint without prior best is allowed only in epoch 0"
            )
        start_epoch=int(mid_epoch_progress["epoch"])
        if start_epoch >= epochs:
            raise ValueError(
                f"mid-epoch checkpoint epoch {start_epoch} is outside "
                f"training.epochs={epochs}"
            )
    checkpoint_interval = int(
        config['training'].get('checkpoint_interval_updates', 0)
    )
    history_path=run.logs/'history.csv'; write_header=not history_path.exists()
    provenance={'geometry_sha256':sha256_file(Path(config['geometry']['path'])/'geometry.npz' if Path(config['geometry']['path']).is_dir() else config['geometry']['path']),'manifest_sha256':sha256_file(config['data']['manifest']),'splits_sha256':sha256_file(config['data']['splits']),'seed':seed}
    updates=(
        int(mid_epoch_progress["updates"])
        if mid_epoch_progress is not None
        else 0
    )
    for epoch in range(start_epoch,epochs):
        # Make each epoch's order a pure function of the frozen seed and epoch.
        # A restarted worker can therefore reconstruct the same permutation
        # without depending on generator state consumed by earlier epochs.
        if train_loader.generator is not None:
            train_loader.generator.manual_seed(seed + epoch)
        if val_loader.generator is not None:
            val_loader.generator.manual_seed(seed + 1_000_000 + epoch)
        if device.type == "cuda":
            torch.cuda.reset_peak_memory_stats(device)
        resume_this_epoch = (
            mid_epoch_progress
            if mid_epoch_progress is not None
            and epoch == int(mid_epoch_progress["epoch"])
            else None
        )
        resume_next_step = (
            int(resume_this_epoch["next_step"])
            if resume_this_epoch is not None
            else 0
        )
        model.train()
        optimizer.zero_grad(set_to_none=True)
        train_sum=(
            float(resume_this_epoch["train_sum"])
            if resume_this_epoch is not None
            else 0.
        )
        train_count=(
            int(resume_this_epoch["train_count"])
            if resume_this_epoch is not None
            else 0
        )
        component_sum=(
            {
                str(name):float(value)
                for name,value in resume_this_epoch["component_sum"].items()
            }
            if resume_this_epoch is not None
            else {}
        )
        elapsed_before_resume=(
            float(resume_this_epoch["elapsed_seconds"])
            if resume_this_epoch is not None
            else 0.
        )
        begin=time.perf_counter()
        remainder=len(train_loader)%accumulation
        final_window_start=len(train_loader)-remainder if remainder else len(train_loader)
        for step,batch in enumerate(train_loader):
            if step < resume_next_step:
                continue
            batch=move_batch(batch,device)
            divisor=(remainder if remainder and step>=final_window_start else accumulation)
            with torch.autocast(device_type=device.type,dtype=torch.float16,enabled=amp_enabled):
                losses,_=compute_component_losses(model,batch,stage); unscaled_total=weighted_total(losses,weights); total=unscaled_total/divisor
            if not torch.isfinite(unscaled_total):
                raise FloatingPointError(f'non-finite training loss at epoch={epoch}, step={step}: {float(unscaled_total.detach())}')
            scaler.scale(total).backward(); train_sum+=float(unscaled_total.detach()); train_count+=1
            for name,value in losses.items(): component_sum[name]=component_sum.get(name,0.)+float(value.detach())
            if (step+1)%accumulation==0 or step+1==len(train_loader):
                scaler.unscale_(optimizer); grad_norm=torch.nn.utils.clip_grad_norm_(parameters,clip)
                if not torch.isfinite(torch.as_tensor(grad_norm)):
                    raise FloatingPointError(f'non-finite gradient norm at epoch={epoch}, step={step}')
                scaler.step(optimizer); scaler.update(); optimizer.zero_grad(set_to_none=True); scheduler.step(); updates+=1
                next_step=step+1
                if (
                    checkpoint_interval > 0
                    and updates % checkpoint_interval == 0
                    and next_step < len(train_loader)
                ):
                    progress = {
                        "epoch": int(epoch),
                        "next_step": int(next_step),
                        "loader_batches": int(len(train_loader)),
                        "gradient_accumulation": int(accumulation),
                        "batch_size": int(config['training']['batch_size']),
                        "epoch_seed": int(seed + epoch),
                        "optimizer_boundary": True,
                        "train_sum": float(train_sum),
                        "train_count": int(train_count),
                        "component_sum": dict(component_sum),
                        "updates": int(updates),
                        "elapsed_seconds": float(
                            elapsed_before_resume + time.perf_counter() - begin
                        ),
                        "contract_sha256": _mid_epoch_contract_sha256(config),
                    }
                    progress_path=run.checkpoints/'progress.pt'
                    save_checkpoint(
                        progress_path,
                        model,
                        optimizer,
                        scheduler,
                        scaler,
                        epoch,
                        best,
                        config,
                        stage,
                        provenance,
                        progress=progress,
                    )
                    if progress_callback is not None:
                        progress_callback(progress,run,progress_path)
        model.eval(); val_sum=0.; val_count=0
        with torch.no_grad():
            for batch in val_loader:
                batch=move_batch(batch,device)
                with torch.autocast(device_type=device.type,dtype=torch.float16,enabled=amp_enabled):
                    losses,_=compute_component_losses(model,batch,stage); total=weighted_total(losses,weights)
                if not torch.isfinite(total):
                    raise FloatingPointError(
                        f"non-finite validation loss at epoch={epoch}: {float(total.detach())}"
                    )
                val_sum+=float(total); val_count+=1
        train_loss=train_sum/max(train_count,1); val_loss=val_sum/max(val_count,1); elapsed=elapsed_before_resume+time.perf_counter()-begin
        model.eval()
        checkpoint_invariants = _checkpoint_invariant_gate(model, config, seed + epoch)
        dump_json(
            checkpoint_invariants,
            run.reports/f"invariant_epoch_{epoch:04d}.json",
        )
        if not checkpoint_invariants["pass"]:
            raise RuntimeError(
                f"structural invariant gate failed for checkpoint candidate at epoch {epoch}"
            )
        peak_memory = (
            int(torch.cuda.max_memory_allocated(device))
            if device.type == "cuda"
            else None
        )
        row={'epoch':epoch,'stage':stage,'train_loss':train_loss,'validation_loss':val_loss,'learning_rate':optimizer.param_groups[0]['lr'],'seconds':elapsed,'examples_per_second':len(train_loader.dataset)/max(elapsed,1e-12),'cuda_peak_memory_bytes':peak_memory,**{f'train_{k}':v/max(train_count,1) for k,v in component_sum.items()}}
        with history_path.open('a',newline='',encoding='utf-8') as handle:
            writer=csv.DictWriter(handle,fieldnames=list(row));
            if write_header: writer.writeheader(); write_header=False
            writer.writerow(row)
        if val_loss<best:
            best=val_loss; stale=0; save_checkpoint(run.checkpoints/'best.pt',model,optimizer,scheduler,scaler,epoch,best,config,stage,provenance)
        else: stale+=1
        # Persist last only after checkpoint selection so its best_metric is
        # the selected value for this epoch.  Saving it before this branch
        # made epoch-zero recovery carry +inf even when best.pt was valid.
        save_checkpoint(run.checkpoints/'last.pt',model,optimizer,scheduler,scaler,epoch,best,config,stage,provenance)
        # In-flight state is superseded by last.pt at epoch completion.  Keep a
        # stale next_step checkpoint out of immutable completed-epoch output.
        (run.checkpoints/'progress.pt').unlink(missing_ok=True)
        visualization = config.get("evaluation", {}).get("visualization", {})
        if bool(visualization.get("enabled", False)):
            export_epoch_visualization(
                model,
                config,
                epoch,
                run.reports / "visualization",
                run.checkpoints / "last.pt",
            )
        if epoch_callback is not None:
            epoch_callback(epoch, run, row)
        if stale>=patience: break
        mid_epoch_progress = None
    result={'stage':stage,'best_validation_loss':best,'run_dir':str(run.root),'best_checkpoint':str(run.checkpoints/'best.pt'),'last_checkpoint':str(run.checkpoints/'last.pt'),'updates':updates}
    dump_json(result,run.reports/'training_summary.json'); return result
