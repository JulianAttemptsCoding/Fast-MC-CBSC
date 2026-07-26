from pathlib import Path
import torch

from cbsc_zdc.data.dataset import load_geometry
from cbsc_zdc.data.synthetic import create_synthetic_dataset
from cbsc_zdc.eval.invariants import invariant_report
from cbsc_zdc.models.system import CBSCZDC
from cbsc_zdc.contracts import NEUTRON_MASS_GEV


def config(geometry_path, nodes, layers):
    return {
        "project": {"name": "test", "run_dir": "unused"},
        "data": {
            "target_mode": "raw_deposit", "threshold_gev": 0.0,
            "response_cap_ratio": 2.0, "response_cap_absolute_gev": 500.0,
        },
        "geometry": {"path": str(geometry_path), "n_nodes": nodes, "n_layers": layers},
        "model": {
            "condition_dim": 24, "hidden_dim": 24, "response_hidden": 32,
            "response_components": 2, "response_scale_gev": 10.0,
            "profile_hidden": 24, "count_hidden": 32, "graph_blocks": 1,
            "attention_heads": 4, "attention_layers": 1,
            "layer_context": "bidirectional", "dropout": 0.0,
        },
    }


def p4(kinetic):
    total = torch.tensor(kinetic, dtype=torch.float64) + NEUTRON_MASS_GEV
    momentum = torch.sqrt(total.square() - NEUTRON_MASS_GEV**2)
    return torch.stack([total, torch.zeros_like(total), torch.zeros_like(total), momentum], dim=1).float()


def test_untrained_model_still_satisfies_structural_invariants(tmp_path: Path):
    created = create_synthetic_dataset(tmp_path, n_events=32, n_layers=4, nodes_per_layer=4, seed=2)
    geometry = load_geometry(created["geometry"])
    model = CBSCZDC(geometry, config(created["geometry"], 16, 4)).eval()
    out = model.sample(p4([0.0, 50.0, 150.0, 250.0]), profile_steps=2, share_steps=2, seed=3)
    report = invariant_report(out, model.layer_index, model.valid_mask, model.threshold_gev)
    assert report["pass"]
    assert out.cell_energy[0].sum().item() == 0.0
