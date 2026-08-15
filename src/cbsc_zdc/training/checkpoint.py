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


CHECKPOINT_FORMAT_V3 = 3
CHECKPOINT_FORMAT_V4 = 4

# Fields format 4 adds on top of format 3.  Every one is nullable so a
# supervised v3 run round-trips without a critic, but the field must be present
# so a reader can tell "no critic" from "an older writer that did not know".
V4_REQUIRED_FIELDS = (
    'architecture_version',
    'experiment_contract_sha256',
    'critic_state',
    'critic_optimizer_state',
    'critic_scheduler_state',
    'gradient_ratio_controller_state',
    'replay_state_manifest',
    'critic_update_count',
    'generator_update_count',
    'role_partition_sha256',
    'response_envelope_sha256',
    'support_temperature',
)


def require_adversarial_resume_source(payload, path=None):
    """Reject a checkpoint that cannot carry adversarial resume state.

    A format-3 checkpoint has no slot for the critic, its optimizer and
    scheduler, the gradient-ratio controller, the replay manifest, or the update
    counters.  Resuming an adversarial run from one would silently restart the
    critic from scratch against a partly-trained generator, which is a different
    experiment wearing the same run tag.

    This is not hypothetical: `_runs/v3_S1_axis/checkpoints/best.pt` is exactly
    such a file.  S1 was a correct v3 run whose checkpoints were written through
    the v2.2 path, so they hold `architecture_version: null` and omit every
    format-4 field.  They remain perfectly valid for evaluation and for
    weight-only initialization; they are not a resume source.  The file is
    immutable and must never be rewritten or re-stamped to satisfy this check.
    """
    where = f" ({path})" if path else ""
    format_version = payload.get('format_version')
    if format_version != CHECKPOINT_FORMAT_V4:
        raise ValueError(
            f"adversarial resume requires checkpoint format {CHECKPOINT_FORMAT_V4}, "
            f"found {format_version!r}{where}; evaluation and weight-only "
            "initialization are still fine, but this file cannot carry critic state"
        )
    missing = [field for field in V4_REQUIRED_FIELDS if field not in payload]
    if missing:
        raise ValueError(
            f"checkpoint declares format {CHECKPOINT_FORMAT_V4} but omits "
            f"{sorted(missing)}{where}"
        )
    if not payload.get('architecture_version'):
        raise ValueError(f"checkpoint has no architecture_version{where}")
    return payload


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
    architecture_version=None,
    experiment_contract_sha256=None,
    critic_state=None,
    critic_optimizer_state=None,
    critic_scheduler_state=None,
    gradient_ratio_controller_state=None,
    replay_state_manifest=None,
    critic_update_count=0,
    generator_update_count=0,
    role_partition_sha256=None,
    response_envelope_sha256=None,
    support_temperature=None,
):
    """Write a checkpoint.

    Omitting ``architecture_version`` writes format 3 byte-for-byte as before,
    so v2.2 runs are untouched.  Supplying it writes format 4 with the full
    adversarial-resume field set.
    """
    payload = {
        'format_version':CHECKPOINT_FORMAT_V3,
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
    }
    if architecture_version is None:
        if critic_state is not None:
            raise ValueError('critic_state requires architecture_version')
        atomic_torch_save(payload, path)
        return
    # A critic checkpoint that cannot be tied to a contract cannot later be
    # proved compatible with the generator or replay state it was trained with.
    if critic_state is not None and not experiment_contract_sha256:
        raise ValueError('critic_state requires experiment_contract_sha256')
    payload.update({
        'format_version':CHECKPOINT_FORMAT_V4,
        'architecture_version':architecture_version,
        'experiment_contract_sha256':experiment_contract_sha256,
        'critic_state':critic_state,
        'critic_optimizer_state':critic_optimizer_state,
        'critic_scheduler_state':critic_scheduler_state,
        'gradient_ratio_controller_state':gradient_ratio_controller_state,
        'replay_state_manifest':replay_state_manifest,
        'critic_update_count':int(critic_update_count),
        'generator_update_count':int(generator_update_count),
        'role_partition_sha256':role_partition_sha256,
        'response_envelope_sha256':response_envelope_sha256,
        'support_temperature':support_temperature,
    })
    atomic_torch_save(payload, path)


def load_checkpoint(path,model,optimizer=None,scheduler=None,scaler=None,map_location='cpu',expected_stage=None,restore_rng=False,expected_contract_sha256=None,expected_replay_sha256=None,critic=None,critic_optimizer=None,critic_scheduler=None):
    payload=torch.load(Path(path),map_location=map_location,weights_only=False)
    if expected_stage is not None and payload.get('stage')!=expected_stage: raise ValueError(f"checkpoint stage {payload.get('stage')} != expected {expected_stage}")
    if expected_contract_sha256 is not None:
        found=payload.get('experiment_contract_sha256')
        if found!=expected_contract_sha256:
            raise ValueError(f"checkpoint experiment_contract_sha256 {found} != expected {expected_contract_sha256}")
    if expected_replay_sha256 is not None:
        manifest=payload.get('replay_state_manifest') or {}
        found=manifest.get('content_sha256')
        if found!=expected_replay_sha256:
            raise ValueError(f"checkpoint replay manifest {found} != expected {expected_replay_sha256}")
    model.load_state_dict(payload['model_state'])
    if optimizer is not None and payload.get('optimizer_state') is not None: optimizer.load_state_dict(payload['optimizer_state'])
    if scheduler is not None and payload.get('scheduler_state') is not None: scheduler.load_state_dict(payload['scheduler_state'])
    if scaler is not None and payload.get('scaler_state') is not None: scaler.load_state_dict(payload['scaler_state'])
    if critic is not None and payload.get('critic_state') is not None: critic.load_state_dict(payload['critic_state'])
    if critic_optimizer is not None and payload.get('critic_optimizer_state') is not None: critic_optimizer.load_state_dict(payload['critic_optimizer_state'])
    if critic_scheduler is not None and payload.get('critic_scheduler_state') is not None: critic_scheduler.load_state_dict(payload['critic_scheduler_state'])
    if restore_rng: restore_rng_state(payload.get('rng_state'))
    return payload
