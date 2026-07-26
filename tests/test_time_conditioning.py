from pathlib import Path
import torch

from cbsc_zdc.data.dataset import load_geometry
from cbsc_zdc.data.synthetic import create_synthetic_dataset
from cbsc_zdc.models.system import CBSCZDC


def test_profile_velocity_depends_on_flow_time(tmp_path: Path):
    made = create_synthetic_dataset(tmp_path, n_events=8, n_layers=4, nodes_per_layer=4, seed=5)
    geom = load_geometry(made["geometry"])
    cfg = {
        "data": {"target_mode": "raw_deposit", "threshold_gev": 0.0},
        "model": {"condition_dim": 24, "hidden_dim": 24, "response_hidden": 32,
                  "response_components": 2, "profile_hidden": 24, "count_hidden": 32,
                  "graph_blocks": 1, "attention_heads": 4, "attention_layers": 1,
                  "layer_context": "bidirectional", "dropout": 0.0},
    }
    model = CBSCZDC(geom, cfg)
    state = torch.randn(2, 4)
    cond = torch.randn(2, 24)
    total = torch.tensor([10.0, 20.0])
    active = torch.ones(2, 4, dtype=torch.bool)
    v0 = model.profile.flow(state, torch.zeros(2, 1), cond, total, active)
    v1 = model.profile.flow(state, torch.ones(2, 1), cond, total, active)
    assert not torch.allclose(v0, v1)
