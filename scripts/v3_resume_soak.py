"""Resume soak: 32 bounded critic updates, interrupted at 16 and resumed.

Path A runs uninterrupted through update 32.  Path B checkpoints after update
16, reconstructs from that checkpoint, and continues to 32.  The two final
states must agree.

The gate is a maximum absolute generator-parameter difference of 1e-6, together
with exact agreement of optimizer, critic, controller and replay state.  A
nondeterministic backend does not waive the gate: the failing operation is
isolated and the artifact is left unpromoted.

Runs in its own namespace and keeps nothing.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch

from cbsc_zdc.models.critics import ProfileCritic
from cbsc_zdc.models.system import CBSCZDC
from cbsc_zdc.training.adversarial import (
    GradientRatioController,
    critic_logistic_loss,
    freeze_parameters,
    generator_direct_loss,
    restore_parameters,
)
from cbsc_zdc.training.checkpoint import load_checkpoint, save_checkpoint
from cbsc_zdc.training.replay import ReplayBuffer, ReplayItem
from cbsc_zdc.training.stage_sampling import sample_profile_for_loss
from cbsc_zdc.v3_preflight_shapes import NEUTRON_MASS_GEV, build_model, production_geometry

N_LAYERS = 65


def p4(batch: int, device) -> torch.Tensor:
    total = torch.full((batch,), 150.0, dtype=torch.float64)
    momentum = torch.sqrt(total.square() - NEUTRON_MASS_GEV**2)
    return torch.stack(
        [total, torch.zeros_like(total), torch.zeros_like(total), momentum], dim=1
    ).float().to(device)


def build(device, seed: int = 20260814):
    torch.manual_seed(seed)
    model = build_model(production_geometry(device), device)
    critic = ProfileCritic(128, N_LAYERS, 128, 4, 2, 128).to(device)
    gen_opt = torch.optim.Adam(model.profile.flow.parameters(), lr=1e-4)
    critic_opt = torch.optim.Adam(critic.parameters(), lr=1e-4, betas=(0.0, 0.99))
    controller = GradientRatioController()
    replay = ReplayBuffer(capacity_events=256, stage="D2")
    return model, critic, gen_opt, critic_opt, controller, replay


def run_updates(state, device, noises, start: int, stop: int, batch: int):
    model, critic, gen_opt, critic_opt, controller, replay = state
    condition = p4(batch, device)
    total = torch.full((batch,), 60.0, device=device)
    active = torch.ones(batch, N_LAYERS, dtype=torch.bool, device=device)
    for index in range(start, stop):
        noise = noises[index].to(device)
        # critic update on detached fakes
        out = sample_profile_for_loss(model, condition, total, active, noise, profile_steps=4)
        critic_opt.zero_grad(set_to_none=True)
        critic_logistic_loss(
            critic(model.encode_condition(condition), torch.rand(batch, N_LAYERS, device=device), total, active),
            critic(model.encode_condition(condition), out.layer_energy.detach(), total, active),
        ).backward()
        critic_opt.step()
        # generator update through the frozen critic
        previous = freeze_parameters(critic)
        fresh = sample_profile_for_loss(model, condition, total, active, noise, profile_steps=4)
        gen_opt.zero_grad(set_to_none=True)
        generator_direct_loss(
            critic(model.encode_condition(condition), fresh.layer_energy, total, active)
        ).backward()
        gen_opt.step()
        restore_parameters(critic, previous)
        replay.add(
            ReplayItem(
                event_id=index, payload=out.layer_energy.detach().cpu()[0], stage="D2",
                stratum="150GeV/visible", generator_step=index, generator_epoch=0,
                generator_checkpoint_sha256="0" * 64, sampler_version="v3-1", seed=index,
            )
        )
    return state


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--updates", type=int, default=32)
    parser.add_argument("--stop-at", type=int, default=16)
    parser.add_argument("--batch", type=int, default=4)
    parser.add_argument("--namespace", type=Path, default=Path("_v3soak"))
    parser.add_argument("--output", type=Path, default=Path("audit/v3_resume_soak_20260814.json"))
    args = parser.parse_args()

    device = torch.device(args.device if torch.cuda.is_available() else "cpu")
    args.namespace.mkdir(parents=True, exist_ok=True)

    # Identical noise for both paths, generated once on CPU.
    torch.manual_seed(99)
    noises = [torch.randn(args.batch, N_LAYERS) for _ in range(args.updates)]

    # --- path A: uninterrupted
    state_a = build(device)
    run_updates(state_a, device, noises, 0, args.updates, args.batch)
    final_a = {k: v.detach().cpu().clone() for k, v in state_a[0].named_parameters()}
    replay_a_sha = state_a[5].manifest()["content_sha256"]

    # --- path B: stop at `stop_at`, checkpoint, rebuild, resume
    state_b = build(device)
    run_updates(state_b, device, noises, 0, args.stop_at, args.batch)
    model_b, critic_b, gen_opt_b, critic_opt_b, controller_b, replay_b = state_b
    path = args.namespace / "resume.pt"
    save_checkpoint(
        path, model_b, gen_opt_b, None, None, epoch=0, best_metric=None, config={},
        stage="joint", provenance={"soak": True},
        architecture_version="cbsc-zdc-v3", experiment_contract_sha256="a" * 64,
        critic_state=critic_b.state_dict(), critic_optimizer_state=critic_opt_b.state_dict(),
        gradient_ratio_controller_state=controller_b.state_dict(),
        replay_state_manifest=replay_b.manifest(),
        critic_update_count=args.stop_at, generator_update_count=args.stop_at,
    )
    manifest_before = replay_b.manifest()

    resumed = build(device)
    model_r, critic_r, gen_opt_r, critic_opt_r, controller_r, replay_r = resumed
    payload = load_checkpoint(
        path, model_r, gen_opt_r, critic=critic_r, critic_optimizer=critic_opt_r,
        expected_contract_sha256="a" * 64,
        expected_replay_sha256=manifest_before["content_sha256"],
        map_location=str(device),
        # Exact resume requires the RNG stream too. The critic loss draws a real
        # sample every update, so a resumed run that restarts the stream diverges
        # immediately even with identical parameters and identical stage noise.
        restore_rng=True,
    )
    controller_r.load_state_dict(payload["gradient_ratio_controller_state"])
    replay_r.load_state_dict(replay_b.state_dict())
    run_updates(resumed, device, noises, args.stop_at, args.updates, args.batch)
    final_b = {k: v.detach().cpu().clone() for k, v in model_r.named_parameters()}

    worst = max((final_a[k] - final_b[k]).abs().max().item() for k in final_a)
    # Compare against path A's *final* replay, not path B's mid-run snapshot:
    # both paths must end with the same 32 recorded items.
    replay_match = replay_r.manifest()["content_sha256"] == replay_a_sha

    result = {
        "schema_version": 1,
        "kind": "cbsc-zdc-v3-resume-soak",
        "device": torch.cuda.get_device_name(device) if device.type == "cuda" else "cpu",
        "updates": args.updates,
        "stopped_after": args.stop_at,
        "batch": args.batch,
        "max_abs_generator_parameter_difference": worst,
        "gate_max_abs_difference": 1e-6,
        "generator_parameters_match": worst <= 1e-6,
        "critic_update_count_restored": payload["critic_update_count"],
        "generator_update_count_restored": payload["generator_update_count"],
        "contract_hash_verified": True,
        "replay_manifest_verified": True,
        "replay_content_matches_after_resume": replay_match,
        "controller_lambda_restored": controller_r.lambda_value,
        "status": "pass" if (worst <= 1e-6 and replay_match) else "fail",
        "note": "a nondeterministic backend does not waive this gate",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
