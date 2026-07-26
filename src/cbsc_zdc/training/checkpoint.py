from __future__ import annotations
from pathlib import Path
import random
import numpy as np
import torch
from ..utils import atomic_torch_save,environment_snapshot


def rng_state():
    return {'python':random.getstate(),'numpy':np.random.get_state(),'torch':torch.get_rng_state(),'cuda':torch.cuda.get_rng_state_all() if torch.cuda.is_available() else None}


def _cpu_byte_rng_tensor(value, name: str):
    if not torch.is_tensor(value):
        raise TypeError(f"{name} RNG state must be a torch tensor")
    return value.detach().to(device="cpu", dtype=torch.uint8)


def restore_rng_state(state):
    if not state:
        return
    random.setstate(state['python'])
    np.random.set_state(state['numpy'])
    # Loading a checkpoint with map_location="cuda" also maps the serialized
    # CPU RNG ByteTensor to CUDA. torch.set_rng_state and
    # torch.cuda.set_rng_state_all both require CPU ByteTensors.
    torch.set_rng_state(_cpu_byte_rng_tensor(state['torch'], "torch"))
    if torch.cuda.is_available() and state.get('cuda') is not None:
        torch.cuda.set_rng_state_all(
            [
                _cpu_byte_rng_tensor(value, f"cuda[{index}]")
                for index, value in enumerate(state['cuda'])
            ]
        )


def save_checkpoint(
    path,
    model,
    optimizer,
    scheduler,
    scaler,
    epoch,
    best_metric,
    config,
    stage,
    provenance,
    progress=None,
):
    atomic_torch_save(
        {
            'format_version':3,
            'model_state':model.state_dict(),
            'optimizer_state':optimizer.state_dict() if optimizer else None,
            'scheduler_state':scheduler.state_dict() if scheduler else None,
            'scaler_state':scaler.state_dict() if scaler else None,
            'epoch':epoch,
            'best_metric':best_metric,
            'config':config,
            'stage':stage,
            'provenance':provenance,
            'rng_state':rng_state(),
            'environment':environment_snapshot(),
            'progress':progress,
        },
        path,
    )


def load_checkpoint(path,model,optimizer=None,scheduler=None,scaler=None,map_location='cpu',expected_stage=None,restore_rng=False):
    payload=torch.load(Path(path),map_location=map_location,weights_only=False)
    if expected_stage is not None and payload.get('stage')!=expected_stage: raise ValueError(f"checkpoint stage {payload.get('stage')} != expected {expected_stage}")
    model.load_state_dict(payload['model_state'])
    if optimizer is not None and payload.get('optimizer_state') is not None: optimizer.load_state_dict(payload['optimizer_state'])
    if scheduler is not None and payload.get('scheduler_state') is not None: scheduler.load_state_dict(payload['scheduler_state'])
    if scaler is not None and payload.get('scaler_state') is not None: scaler.load_state_dict(payload['scaler_state'])
    if restore_rng: restore_rng_state(payload.get('rng_state'))
    return payload
