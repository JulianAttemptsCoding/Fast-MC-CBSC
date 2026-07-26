# Line-by-line executable-source audit

This ledger inventories every physical line in the Python source, tests, and utility scripts. Blank separator lines are included in each file’s physical-line count but omitted from the tables because they contain no executable or semantic content. `STATIC+EXECUTED` means coverage instrumentation observed the line during the 30-test synthetic suite; `STATIC+MANUAL` means the line compiled and was manually inspected but was not executed by that suite; `DOC/COMMENT` means prose or a comment was checked against the implementation scope. Coverage is evidence of execution, not proof of physics correctness, detector fidelity, or complete real-data integration.

## Audit summary

- Static compilation: `PYTHONPATH=src python -m compileall -q src tests scripts` — **passed**.
- Unit tests: `PYTHONPATH=src pytest -q` — **30 passed**, with seven repeated PyTorch performance warnings from `norm_first=True`.
- Instrumented coverage: **100% measured statement/branch coverage** over all imported source modules and all tests (`980` statements, `132` branches).
- The optional ROOT adapter import/error paths are tested with controlled fakes; actual production ROOT decoding still requires the frozen branch map and optional `uproot`/`awkward` dependencies.
- The complete Vertex training/evaluation pipeline and real Geant4 fidelity remain future empirical work.

## `scripts/smoke_train.py`

- SHA-256: `1a9827c07a1d851145a8bc302ca6803cbd9c242fce64bb17cb791a4e80f12c7e`
- Physical lines: 60; nonblank lines listed below: 46.
- The utility script compiled, was manually reviewed, and was executed once with `--nodes 65 --steps 1`; coverage instrumentation was reserved for source/tests.

| Line | Audit | Source |
|---:|---|---|
| 1 | DOC/COMMENT | <code>"""Run one synthetic forward sample and print algebraic invariant diagnostics."""</code> |
| 3 | STATIC+MANUAL | <code>from __future__ import annotations</code> |
| 5 | STATIC+MANUAL | <code>import argparse</code> |
| 6 | STATIC+MANUAL | <code>from pathlib import Path</code> |
| 8 | STATIC+MANUAL | <code>import torch</code> |
| 9 | STATIC+MANUAL | <code>import yaml</code> |
| 11 | STATIC+MANUAL | <code>from cbsc_zdc.eval.diagnostics import invariant_report</code> |
| 12 | STATIC+MANUAL | <code>from cbsc_zdc.models.system import CBSCZDC</code> |
| 14 | STATIC+MANUAL | <code>NEUTRON_MASS_GEV = 0.93956542052</code> |
| 17 | STATIC+MANUAL | <code>def parse_args() -&gt; argparse.Namespace:</code> |
| 18 | STATIC+MANUAL | <code>    parser = argparse.ArgumentParser()</code> |
| 19 | STATIC+MANUAL | <code>    parser.add_argument("--config", type=Path, default=Path("configs/pilot.yaml"))</code> |
| 20 | STATIC+MANUAL | <code>    parser.add_argument(</code> |
| 21 | STATIC+MANUAL | <code>        "--nodes",</code> |
| 22 | STATIC+MANUAL | <code>        type=int,</code> |
| 23 | STATIC+MANUAL | <code>        default=None,</code> |
| 24 | STATIC+MANUAL | <code>        help="Optional smaller synthetic node count; must be at least the layer count.",</code> |
| 25 | STATIC+MANUAL | <code>    )</code> |
| 26 | STATIC+MANUAL | <code>    parser.add_argument("--steps", type=int, default=None)</code> |
| 27 | STATIC+MANUAL | <code>    return parser.parse_args()</code> |
| 30 | STATIC+MANUAL | <code>def main() -&gt; None:</code> |
| 31 | STATIC+MANUAL | <code>    args = parse_args()</code> |
| 32 | STATIC+MANUAL | <code>    with args.config.open("r", encoding="utf-8") as handle:</code> |
| 33 | STATIC+MANUAL | <code>        config = yaml.safe_load(handle)</code> |
| 35 | STATIC+MANUAL | <code>    n_layers = int(config["detector"]["n_layers"])</code> |
| 36 | STATIC+MANUAL | <code>    n_nodes = int(args.nodes or config["detector"]["n_nodes"])</code> |
| 37 | STATIC+MANUAL | <code>    if n_nodes &lt; n_layers:</code> |
| 38 | STATIC+MANUAL | <code>        raise ValueError("synthetic node count must be at least the layer count")</code> |
| 39 | STATIC+MANUAL | <code>    steps = int(args.steps or config["sampling"]["steps"])</code> |
| 41 | STATIC+MANUAL | <code>    layer_index = torch.arange(n_nodes) % n_layers</code> |
| 42 | STATIC+MANUAL | <code>    node_features = torch.randn(n_nodes, 8)</code> |
| 43 | STATIC+MANUAL | <code>    valid_mask = torch.ones(n_nodes, dtype=torch.bool)</code> |
| 44 | STATIC+MANUAL | <code>    model = CBSCZDC(</code> |
| 45 | STATIC+MANUAL | <code>        node_features,</code> |
| 46 | STATIC+MANUAL | <code>        layer_index,</code> |
| 47 | STATIC+MANUAL | <code>        valid_mask,</code> |
| 48 | STATIC+MANUAL | <code>        cond_dim=int(config["model"]["condition_dim"]),</code> |
| 49 | STATIC+MANUAL | <code>        latent_dim=int(config["model"]["event_latent_dim"]),</code> |
| 50 | STATIC+MANUAL | <code>    ).eval()</code> |
| 52 | STATIC+MANUAL | <code>    momentum = torch.tensor([[0.0, 0.0, 99.995586]])</code> |
| 53 | STATIC+MANUAL | <code>    energy = torch.sqrt(momentum.square().sum(dim=-1) + NEUTRON_MASS_GEV**2).unsqueeze(-1)</code> |
| 54 | STATIC+MANUAL | <code>    p4 = torch.cat((energy, momentum), dim=-1)</code> |
| 55 | STATIC+MANUAL | <code>    output = model.sample(p4, steps=steps, seed=7)</code> |
| 56 | STATIC+MANUAL | <code>    print(invariant_report(p4, output, layer_index=layer_index))</code> |
| 59 | STATIC+MANUAL | <code>if __name__ == "__main__":</code> |
| 60 | STATIC+MANUAL | <code>    main()</code> |

## `src/cbsc_zdc/__init__.py`

- SHA-256: `671fadc4e2fde08445e091534d4ec0091690a562c30c8cadcb8186eea52b83f2`
- Physical lines: 3; nonblank lines listed below: 2.

| Line | Audit | Source |
|---:|---|---|
| 1 | STATIC+EXECUTED | <code>from .models.system import CBSCOutput, CBSCZDC</code> |
| 3 | STATIC+EXECUTED | <code>__all__ = ["CBSCZDC", "CBSCOutput"]</code> |

## `src/cbsc_zdc/contracts.py`

- SHA-256: `81d3cda69f16ccb62344d6216cd32d12ac264cca507b6e1f2e9df0ff5a18b0a3`
- Physical lines: 57; nonblank lines listed below: 47.

| Line | Audit | Source |
|---:|---|---|
| 1 | STATIC+EXECUTED | <code>from __future__ import annotations</code> |
| 3 | STATIC+EXECUTED | <code>from dataclasses import dataclass</code> |
| 5 | STATIC+EXECUTED | <code>import torch</code> |
| 7 | STATIC+EXECUTED | <code>NEUTRON_MASS_GEV = 0.93956542052</code> |
| 10 | STATIC+EXECUTED | <code>@dataclass(frozen=True)</code> |
| 11 | STATIC+EXECUTED | <code>class DetectorSpec:</code> |
| 12 | STATIC+EXECUTED | <code>    n_layers: int = 65</code> |
| 13 | STATIC+EXECUTED | <code>    n_nodes: int = 6790</code> |
| 14 | STATIC+EXECUTED | <code>    n_ecal: int = 400</code> |
| 15 | STATIC+EXECUTED | <code>    n_hcal: int = 6390</code> |
| 18 | STATIC+EXECUTED | <code>def validate_p4(p4: torch.Tensor, rtol_energy: float = 1e-5) -&gt; None:</code> |
| 19 | DOC/COMMENT | <code>    """Validate a neutron four-vector using a numerically stable mass-shell test.</code> |
| 21 | DOC/COMMENT | <code>    Directly subtracting ``E**2 - &#124;p&#124;**2`` is ill-conditioned for 50--300 GeV</code> |
| 22 | DOC/COMMENT | <code>    float32 inputs because two large nearly equal numbers are subtracted.  The</code> |
| 23 | DOC/COMMENT | <code>    implementation therefore compares ``E`` with ``sqrt(&#124;p&#124;**2 + m_n**2)`` in</code> |
| 24 | DOC/COMMENT | <code>    float64.  A signed mass-squared residual can still be reported separately for QA.</code> |
| 25 | DOC/COMMENT | <code>    """</code> |
| 26 | STATIC+EXECUTED | <code>    if p4.ndim != 2 or p4.shape[-1] != 4:</code> |
| 27 | STATIC+EXECUTED | <code>        raise ValueError(f"p4 must have shape [B,4], got {tuple(p4.shape)}")</code> |
| 28 | STATIC+EXECUTED | <code>    if not torch.is_floating_point(p4):</code> |
| 29 | STATIC+EXECUTED | <code>        raise ValueError("p4 must use a floating-point dtype")</code> |
| 30 | STATIC+EXECUTED | <code>    if not torch.isfinite(p4).all():</code> |
| 31 | STATIC+EXECUTED | <code>        raise ValueError("p4 contains NaN/Inf")</code> |
| 32 | STATIC+EXECUTED | <code>    p4_64 = p4.to(torch.float64)</code> |
| 33 | STATIC+EXECUTED | <code>    e = p4_64[:, 0]</code> |
| 34 | STATIC+EXECUTED | <code>    momentum = p4_64[:, 1:]</code> |
| 35 | STATIC+EXECUTED | <code>    if (e &lt;= 0).any():</code> |
| 36 | STATIC+EXECUTED | <code>        raise ValueError("incident energy must be positive")</code> |
| 37 | STATIC+EXECUTED | <code>    expected_e = torch.sqrt(momentum.square().sum(dim=-1) + NEUTRON_MASS_GEV**2)</code> |
| 38 | STATIC+EXECUTED | <code>    relative_energy_residual = (e - expected_e).abs() / e.clamp_min(1e-12)</code> |
| 39 | STATIC+EXECUTED | <code>    if (relative_energy_residual &gt; rtol_energy).any():</code> |
| 40 | STATIC+EXECUTED | <code>        raise ValueError(</code> |
| 41 | STATIC+MANUAL | <code>            "neutron mass-shell energy residual exceeds tolerance: "</code> |
| 42 | STATIC+MANUAL | <code>            f"{relative_energy_residual.max().item():.3e}"</code> |
| 43 | STATIC+MANUAL | <code>        )</code> |
| 46 | STATIC+EXECUTED | <code>def mass_shell_diagnostics(p4: torch.Tensor) -&gt; dict[str, torch.Tensor]:</code> |
| 47 | DOC/COMMENT | <code>    """Return stable and conventional neutron mass-shell diagnostics."""</code> |
| 48 | STATIC+EXECUTED | <code>    if p4.ndim != 2 or p4.shape[-1] != 4:</code> |
| 49 | STATIC+EXECUTED | <code>        raise ValueError(f"p4 must have shape [B,4], got {tuple(p4.shape)}")</code> |
| 50 | STATIC+EXECUTED | <code>    p4_64 = p4.to(torch.float64)</code> |
| 51 | STATIC+EXECUTED | <code>    e = p4_64[:, 0]</code> |
| 52 | STATIC+EXECUTED | <code>    momentum2 = p4_64[:, 1:].square().sum(dim=-1)</code> |
| 53 | STATIC+EXECUTED | <code>    expected_e = torch.sqrt(momentum2 + NEUTRON_MASS_GEV**2)</code> |
| 54 | STATIC+EXECUTED | <code>    return {</code> |
| 55 | STATIC+MANUAL | <code>        "relative_energy_residual": (e - expected_e).abs() / e.clamp_min(1e-12),</code> |
| 56 | STATIC+MANUAL | <code>        "mass_squared_residual_gev2": e.square() - momentum2 - NEUTRON_MASS_GEV**2,</code> |
| 57 | STATIC+MANUAL | <code>    }</code> |

## `src/cbsc_zdc/data/__init__.py`

- SHA-256: `ba189ab0c0cfff268b4ac144db00e984a0087cdbc9ae4a9edb982778be4f03a1`
- Physical lines: 5; nonblank lines listed below: 3.

| Line | Audit | Source |
|---:|---|---|
| 1 | DOC/COMMENT | <code>"""Data-adapter contracts for CBSC-ZDC."""</code> |
| 3 | STATIC+EXECUTED | <code>from .root_adapter import BranchMap, inspect_root</code> |
| 5 | STATIC+EXECUTED | <code>__all__ = ["BranchMap", "inspect_root"]</code> |

## `src/cbsc_zdc/data/root_adapter.py`

- SHA-256: `f2aa0e32e2ee69a8932120cb32617b5e81576bd5b4935f50903f85e4ff307a28`
- Physical lines: 34; nonblank lines listed below: 27.

| Line | Audit | Source |
|---:|---|---|
| 1 | DOC/COMMENT | <code>"""ROOT adapter skeleton.</code> |
| 3 | DOC/COMMENT | <code>The production branch map is deliberately external. Do not infer layer/channel codecs</code> |
| 4 | DOC/COMMENT | <code>from names. Install optional dependencies with ``pip install -e .[root]``.</code> |
| 5 | DOC/COMMENT | <code>"""</code> |
| 7 | STATIC+EXECUTED | <code>from __future__ import annotations</code> |
| 9 | STATIC+EXECUTED | <code>from dataclasses import dataclass</code> |
| 10 | STATIC+EXECUTED | <code>from pathlib import Path</code> |
| 13 | STATIC+EXECUTED | <code>@dataclass(frozen=True)</code> |
| 14 | STATIC+EXECUTED | <code>class BranchMap:</code> |
| 15 | STATIC+EXECUTED | <code>    e: str</code> |
| 16 | STATIC+EXECUTED | <code>    px: str</code> |
| 17 | STATIC+EXECUTED | <code>    py: str</code> |
| 18 | STATIC+EXECUTED | <code>    pz: str</code> |
| 19 | STATIC+EXECUTED | <code>    ecal_id: str</code> |
| 20 | STATIC+EXECUTED | <code>    ecal_energy: str</code> |
| 21 | STATIC+EXECUTED | <code>    hcal_id: str</code> |
| 22 | STATIC+EXECUTED | <code>    hcal_layer: str</code> |
| 23 | STATIC+EXECUTED | <code>    hcal_energy: str</code> |
| 26 | STATIC+EXECUTED | <code>def inspect_root(path: str &#124; Path) -&gt; dict[str, str]:</code> |
| 27 | STATIC+EXECUTED | <code>    try:</code> |
| 28 | STATIC+EXECUTED | <code>        import uproot</code> |
| 29 | STATIC+EXECUTED | <code>    except ImportError as exc:</code> |
| 30 | STATIC+EXECUTED | <code>        raise RuntimeError(</code> |
| 31 | STATIC+MANUAL | <code>            "Install uproot/awkward using the root extra"</code> |
| 32 | STATIC+MANUAL | <code>        ) from exc</code> |
| 33 | STATIC+EXECUTED | <code>    root_file = uproot.open(Path(path))</code> |
| 34 | STATIC+EXECUTED | <code>    return {key: str(value.classname) for key, value in root_file.items()}</code> |

## `src/cbsc_zdc/eval/__init__.py`

- SHA-256: `e1c39d78f92df2ab2b03cf77544c9293741c83fa1eec511b6c0cec517cbde516`
- Physical lines: 5; nonblank lines listed below: 3.

| Line | Audit | Source |
|---:|---|---|
| 1 | DOC/COMMENT | <code>"""Evaluation diagnostics for CBSC-ZDC."""</code> |
| 3 | STATIC+EXECUTED | <code>from .diagnostics import invariant_report</code> |
| 5 | STATIC+EXECUTED | <code>__all__ = ["invariant_report"]</code> |

## `src/cbsc_zdc/eval/diagnostics.py`

- SHA-256: `9e08c654f4affffa53cd097963f476162e164b39918ae4e702697c5d50dca8f7`
- Physical lines: 57; nonblank lines listed below: 54.

| Line | Audit | Source |
|---:|---|---|
| 1 | STATIC+EXECUTED | <code>from __future__ import annotations</code> |
| 3 | STATIC+EXECUTED | <code>import torch</code> |
| 6 | STATIC+EXECUTED | <code>def invariant_report(</code> |
| 7 | STATIC+MANUAL | <code>    p4: torch.Tensor,</code> |
| 8 | STATIC+MANUAL | <code>    out,</code> |
| 9 | STATIC+MANUAL | <code>    threshold_gev: float = 0.0,</code> |
| 10 | STATIC+MANUAL | <code>    layer_index: torch.Tensor &#124; None = None,</code> |
| 11 | STATIC+MANUAL | <code>    atol: float = 1e-5,</code> |
| 12 | STATIC+MANUAL | <code>) -&gt; dict[str, float &#124; int]:</code> |
| 13 | STATIC+EXECUTED | <code>    cell = out.cell_energy</code> |
| 14 | STATIC+EXECUTED | <code>    positive = cell &gt; 0</code> |
| 15 | STATIC+EXECUTED | <code>    dust = (</code> |
| 16 | STATIC+MANUAL | <code>        positive &amp; (cell &lt; threshold_gev)</code> |
| 17 | STATIC+MANUAL | <code>        if threshold_gev &gt; 0</code> |
| 18 | STATIC+MANUAL | <code>        else torch.zeros_like(positive)</code> |
| 19 | STATIC+MANUAL | <code>    )</code> |
| 20 | STATIC+EXECUTED | <code>    modeled_accounting = (</code> |
| 21 | STATIC+MANUAL | <code>        cell.sum(dim=-1, keepdim=True)</code> |
| 22 | STATIC+MANUAL | <code>        + out.subthreshold_residual.sum(dim=-1, keepdim=True)</code> |
| 23 | STATIC+MANUAL | <code>        + out.reserve</code> |
| 24 | STATIC+MANUAL | <code>    )</code> |
| 25 | STATIC+EXECUTED | <code>    report: dict[str, float &#124; int] = {</code> |
| 26 | STATIC+MANUAL | <code>        "nonfinite": int((~torch.isfinite(cell)).sum().item()),</code> |
| 27 | STATIC+MANUAL | <code>        "negative": int((cell &lt; 0).sum().item()),</code> |
| 28 | STATIC+MANUAL | <code>        "dust_cells": int(dust.sum().item()),</code> |
| 29 | STATIC+MANUAL | <code>        "total_over_incident": int(</code> |
| 30 | STATIC+MANUAL | <code>            (out.total.squeeze(-1) &gt; p4[:, 0] + atol).sum().item()</code> |
| 31 | STATIC+MANUAL | <code>        ),</code> |
| 32 | STATIC+MANUAL | <code>        "accounting_identity_max": float(</code> |
| 33 | STATIC+MANUAL | <code>            (modeled_accounting - out.total).abs().max().item()</code> |
| 34 | STATIC+MANUAL | <code>        ),</code> |
| 35 | STATIC+MANUAL | <code>        "support_count_mismatch_max": float(</code> |
| 36 | STATIC+MANUAL | <code>            (</code> |
| 37 | STATIC+MANUAL | <code>                out.support_mask.sum(dim=-1)</code> |
| 38 | STATIC+MANUAL | <code>                - out.realized_counts.sum(dim=-1)</code> |
| 39 | STATIC+MANUAL | <code>            )</code> |
| 40 | STATIC+MANUAL | <code>            .abs()</code> |
| 41 | STATIC+MANUAL | <code>            .max()</code> |
| 42 | STATIC+MANUAL | <code>            .item()</code> |
| 43 | STATIC+MANUAL | <code>        ),</code> |
| 44 | STATIC+MANUAL | <code>    }</code> |
| 45 | STATIC+EXECUTED | <code>    if layer_index is not None:</code> |
| 46 | STATIC+EXECUTED | <code>        n_layers = out.layer_energy.shape[1]</code> |
| 47 | STATIC+EXECUTED | <code>        cell_by_layer = torch.zeros_like(out.layer_energy)</code> |
| 48 | STATIC+EXECUTED | <code>        cell_by_layer.scatter_add_(</code> |
| 49 | STATIC+MANUAL | <code>            1,</code> |
| 50 | STATIC+MANUAL | <code>            layer_index[None].expand(cell.shape[0], -1),</code> |
| 51 | STATIC+MANUAL | <code>            cell,</code> |
| 52 | STATIC+MANUAL | <code>        )</code> |
| 53 | STATIC+EXECUTED | <code>        resolved_target = out.layer_energy - out.subthreshold_residual</code> |
| 54 | STATIC+EXECUTED | <code>        report["resolved_layer_mismatch_max"] = float(</code> |
| 55 | STATIC+MANUAL | <code>            (cell_by_layer - resolved_target).abs().max().item()</code> |
| 56 | STATIC+MANUAL | <code>        )</code> |
| 57 | STATIC+EXECUTED | <code>    return report</code> |

## `src/cbsc_zdc/features.py`

- SHA-256: `39376dc2e9c489d5a0a7f250311bc99791a923556262fc167afcb161be862b95`
- Physical lines: 17; nonblank lines listed below: 13.

| Line | Audit | Source |
|---:|---|---|
| 1 | STATIC+EXECUTED | <code>from __future__ import annotations</code> |
| 3 | STATIC+EXECUTED | <code>import torch</code> |
| 5 | STATIC+EXECUTED | <code>from .contracts import validate_p4</code> |
| 8 | STATIC+EXECUTED | <code>def p4_features(p4: torch.Tensor, energy_scale_gev: float = 1.0) -&gt; torch.Tensor:</code> |
| 9 | DOC/COMMENT | <code>    """Return the minimal deterministic condition ``[log(E/E0), ux, uy, uz]``."""</code> |
| 10 | STATIC+EXECUTED | <code>    if energy_scale_gev &lt;= 0:</code> |
| 11 | STATIC+EXECUTED | <code>        raise ValueError("energy_scale_gev must be positive")</code> |
| 12 | STATIC+EXECUTED | <code>    validate_p4(p4)</code> |
| 13 | STATIC+EXECUTED | <code>    e, px, py, pz = p4.unbind(-1)</code> |
| 14 | STATIC+EXECUTED | <code>    momentum = torch.sqrt(px.square() + py.square() + pz.square()).clamp_min(1e-12)</code> |
| 15 | STATIC+EXECUTED | <code>    direction = torch.stack((px / momentum, py / momentum, pz / momentum), dim=-1)</code> |
| 16 | STATIC+EXECUTED | <code>    log_energy = torch.log(e / energy_scale_gev).unsqueeze(-1)</code> |
| 17 | STATIC+EXECUTED | <code>    return torch.cat((log_energy, direction), dim=-1)</code> |

## `src/cbsc_zdc/models/__init__.py`

- SHA-256: `3fc3132c64f2412367e89369423f69c90d23c0c2819fae62985c64e65dfae343`
- Physical lines: 5; nonblank lines listed below: 3.

| Line | Audit | Source |
|---:|---|---|
| 1 | DOC/COMMENT | <code>"""Model components for CBSC-ZDC."""</code> |
| 3 | STATIC+EXECUTED | <code>from .system import CBSCOutput, CBSCZDC</code> |
| 5 | STATIC+EXECUTED | <code>__all__ = ["CBSCZDC", "CBSCOutput"]</code> |

## `src/cbsc_zdc/models/blocks.py`

- SHA-256: `505e45a7c3e184457cffc56434295e0b19058b053e36d3a8f8da4b94198ae96c`
- Physical lines: 52; nonblank lines listed below: 42.

| Line | Audit | Source |
|---:|---|---|
| 1 | STATIC+EXECUTED | <code>from __future__ import annotations</code> |
| 3 | STATIC+EXECUTED | <code>import torch</code> |
| 4 | STATIC+EXECUTED | <code>from torch import nn</code> |
| 7 | STATIC+EXECUTED | <code>class ResidualMLP(nn.Module):</code> |
| 8 | STATIC+EXECUTED | <code>    def __init__(self, dim: int, hidden: int, blocks: int = 2):</code> |
| 9 | STATIC+EXECUTED | <code>        super().__init__()</code> |
| 10 | STATIC+EXECUTED | <code>        self.blocks = nn.ModuleList(</code> |
| 11 | STATIC+MANUAL | <code>            [</code> |
| 12 | STATIC+MANUAL | <code>                nn.Sequential(</code> |
| 13 | STATIC+MANUAL | <code>                    nn.LayerNorm(dim),</code> |
| 14 | STATIC+MANUAL | <code>                    nn.Linear(dim, hidden),</code> |
| 15 | STATIC+MANUAL | <code>                    nn.SiLU(),</code> |
| 16 | STATIC+MANUAL | <code>                    nn.Linear(hidden, dim),</code> |
| 17 | STATIC+MANUAL | <code>                )</code> |
| 18 | STATIC+MANUAL | <code>                for _ in range(blocks)</code> |
| 19 | STATIC+MANUAL | <code>            ]</code> |
| 20 | STATIC+MANUAL | <code>        )</code> |
| 22 | STATIC+EXECUTED | <code>    def forward(self, x: torch.Tensor) -&gt; torch.Tensor:</code> |
| 23 | STATIC+EXECUTED | <code>        for block in self.blocks:</code> |
| 24 | STATIC+EXECUTED | <code>            x = x + block(x)</code> |
| 25 | STATIC+EXECUTED | <code>        return x</code> |
| 28 | STATIC+EXECUTED | <code>class ConditionEncoder(nn.Module):</code> |
| 29 | STATIC+EXECUTED | <code>    def __init__(self, out_dim: int = 128):</code> |
| 30 | STATIC+EXECUTED | <code>        super().__init__()</code> |
| 31 | STATIC+EXECUTED | <code>        self.net = nn.Sequential(</code> |
| 32 | STATIC+MANUAL | <code>            nn.Linear(4, out_dim),</code> |
| 33 | STATIC+MANUAL | <code>            nn.SiLU(),</code> |
| 34 | STATIC+MANUAL | <code>            ResidualMLP(out_dim, out_dim * 2, 2),</code> |
| 35 | STATIC+MANUAL | <code>            nn.LayerNorm(out_dim),</code> |
| 36 | STATIC+MANUAL | <code>        )</code> |
| 38 | STATIC+EXECUTED | <code>    def forward(self, x: torch.Tensor) -&gt; torch.Tensor:</code> |
| 39 | STATIC+EXECUTED | <code>        return self.net(x)</code> |
| 42 | STATIC+EXECUTED | <code>class FiLM(nn.Module):</code> |
| 43 | STATIC+EXECUTED | <code>    def __init__(self, cond_dim: int, feat_dim: int):</code> |
| 44 | STATIC+EXECUTED | <code>        super().__init__()</code> |
| 45 | STATIC+EXECUTED | <code>        self.proj = nn.Linear(cond_dim, feat_dim * 2)</code> |
| 47 | STATIC+EXECUTED | <code>    def forward(self, x: torch.Tensor, condition: torch.Tensor) -&gt; torch.Tensor:</code> |
| 48 | STATIC+EXECUTED | <code>        gain, bias = self.proj(condition).chunk(2, dim=-1)</code> |
| 49 | STATIC+EXECUTED | <code>        while gain.ndim &lt; x.ndim:</code> |
| 50 | STATIC+EXECUTED | <code>            gain = gain.unsqueeze(1)</code> |
| 51 | STATIC+EXECUTED | <code>            bias = bias.unsqueeze(1)</code> |
| 52 | STATIC+EXECUTED | <code>        return x * (1 + gain) + bias</code> |

## `src/cbsc_zdc/models/budget.py`

- SHA-256: `b0e1fd31120388189b9c814a270d801fef641538035182fd639b608a80b36c01`
- Physical lines: 11; nonblank lines listed below: 8.

| Line | Audit | Source |
|---:|---|---|
| 1 | DOC/COMMENT | <code>"""Compatibility exports for the revised profile model.</code> |
| 3 | DOC/COMMENT | <code>The original sequential sigmoid stick-breaking scaffold was removed because it introduced</code> |
| 4 | DOC/COMMENT | <code>an avoidable depth-order bias over 65 layers. The revised implementation generates exact</code> |
| 5 | DOC/COMMENT | <code>layer support first and allocates total response on a masked simplex; the remaining budget</code> |
| 6 | DOC/COMMENT | <code>is then monotone by cumulative accounting rather than by a fragile product of 65 fractions.</code> |
| 7 | DOC/COMMENT | <code>"""</code> |
| 9 | STATIC+EXECUTED | <code>from .profile import LongitudinalProfileModel, ProfileOutput</code> |
| 11 | STATIC+EXECUTED | <code>__all__ = ["LongitudinalProfileModel", "ProfileOutput"]</code> |

## `src/cbsc_zdc/models/counts.py`

- SHA-256: `9a1025539d0598ecf0092dd395d280c3a97d1beb703dd69bd0b0940183025357`
- Physical lines: 98; nonblank lines listed below: 90.

| Line | Audit | Source |
|---:|---|---|
| 1 | STATIC+EXECUTED | <code>from __future__ import annotations</code> |
| 3 | STATIC+EXECUTED | <code>import torch</code> |
| 4 | STATIC+EXECUTED | <code>from torch import nn</code> |
| 7 | STATIC+EXECUTED | <code>class LayerCountHead(nn.Module):</code> |
| 8 | DOC/COMMENT | <code>    """Finite-support categorical hit-count model for each detector layer.</code> |
| 10 | DOC/COMMENT | <code>    A categorical count model avoids the Poisson mean=variance restriction and permits</code> |
| 11 | DOC/COMMENT | <code>    exact masking of impossible counts when a positive readout threshold is used.</code> |
| 12 | DOC/COMMENT | <code>    """</code> |
| 14 | STATIC+EXECUTED | <code>    def __init__(</code> |
| 15 | STATIC+MANUAL | <code>        self,</code> |
| 16 | STATIC+MANUAL | <code>        cond_dim: int = 128,</code> |
| 17 | STATIC+MANUAL | <code>        n_layers: int = 65,</code> |
| 18 | STATIC+MANUAL | <code>        max_counts: list[int] &#124; None = None,</code> |
| 19 | STATIC+MANUAL | <code>        hidden: int = 192,</code> |
| 20 | STATIC+MANUAL | <code>        layer_embedding_dim: int = 24,</code> |
| 21 | STATIC+MANUAL | <code>    ):</code> |
| 22 | STATIC+EXECUTED | <code>        super().__init__()</code> |
| 23 | STATIC+EXECUTED | <code>        self.n_layers = n_layers</code> |
| 24 | STATIC+EXECUTED | <code>        default_counts = [400] + [100] * 63 + [90]</code> |
| 25 | STATIC+EXECUTED | <code>        max_counts = max_counts or default_counts</code> |
| 26 | STATIC+EXECUTED | <code>        if len(max_counts) != n_layers:</code> |
| 27 | STATIC+EXECUTED | <code>            raise ValueError("max_counts length must equal n_layers")</code> |
| 28 | STATIC+EXECUTED | <code>        self.register_buffer("max_counts", torch.tensor(max_counts, dtype=torch.long))</code> |
| 29 | STATIC+EXECUTED | <code>        self.max_global = int(max(max_counts))</code> |
| 30 | STATIC+EXECUTED | <code>        self.layer_embedding = nn.Embedding(n_layers, layer_embedding_dim)</code> |
| 31 | STATIC+EXECUTED | <code>        self.net = nn.Sequential(</code> |
| 32 | STATIC+MANUAL | <code>            nn.Linear(cond_dim + 2 + layer_embedding_dim, hidden),</code> |
| 33 | STATIC+MANUAL | <code>            nn.SiLU(),</code> |
| 34 | STATIC+MANUAL | <code>            nn.Linear(hidden, hidden),</code> |
| 35 | STATIC+MANUAL | <code>            nn.SiLU(),</code> |
| 36 | STATIC+MANUAL | <code>            nn.Linear(hidden, self.max_global + 1),</code> |
| 37 | STATIC+MANUAL | <code>        )</code> |
| 39 | STATIC+EXECUTED | <code>    def logits(</code> |
| 40 | STATIC+MANUAL | <code>        self,</code> |
| 41 | STATIC+MANUAL | <code>        cond: torch.Tensor,</code> |
| 42 | STATIC+MANUAL | <code>        layer_energy: torch.Tensor,</code> |
| 43 | STATIC+MANUAL | <code>        active_layers: torch.Tensor,</code> |
| 44 | STATIC+MANUAL | <code>        threshold_gev: float = 0.0,</code> |
| 45 | STATIC+MANUAL | <code>    ) -&gt; torch.Tensor:</code> |
| 46 | STATIC+EXECUTED | <code>        batch, n_layers = layer_energy.shape</code> |
| 47 | STATIC+EXECUTED | <code>        if n_layers != self.n_layers:</code> |
| 48 | STATIC+EXECUTED | <code>            raise ValueError("layer_energy has the wrong layer dimension")</code> |
| 49 | STATIC+EXECUTED | <code>        layer_ids = torch.arange(self.n_layers, device=cond.device)</code> |
| 50 | STATIC+EXECUTED | <code>        emb = self.layer_embedding(layer_ids)[None].expand(batch, -1, -1)</code> |
| 51 | STATIC+EXECUTED | <code>        cond_expanded = cond[:, None, :].expand(-1, self.n_layers, -1)</code> |
| 52 | STATIC+EXECUTED | <code>        features = torch.cat(</code> |
| 53 | STATIC+MANUAL | <code>            (</code> |
| 54 | STATIC+MANUAL | <code>                cond_expanded,</code> |
| 55 | STATIC+MANUAL | <code>                torch.log1p(layer_energy)[..., None],</code> |
| 56 | STATIC+MANUAL | <code>                active_layers[..., None],</code> |
| 57 | STATIC+MANUAL | <code>                emb,</code> |
| 58 | STATIC+MANUAL | <code>            ),</code> |
| 59 | STATIC+MANUAL | <code>            dim=-1,</code> |
| 60 | STATIC+MANUAL | <code>        )</code> |
| 61 | STATIC+EXECUTED | <code>        logits = self.net(features)</code> |
| 63 | STATIC+EXECUTED | <code>        counts = torch.arange(self.max_global + 1, device=cond.device)</code> |
| 64 | STATIC+EXECUTED | <code>        max_by_geometry = self.max_counts[None, :, None]</code> |
| 65 | STATIC+EXECUTED | <code>        feasible = counts[None, None, :] &lt;= max_by_geometry</code> |
| 66 | STATIC+EXECUTED | <code>        if threshold_gev &gt; 0:</code> |
| 67 | STATIC+EXECUTED | <code>            max_by_budget = torch.floor(layer_energy / threshold_gev).long()</code> |
| 68 | STATIC+EXECUTED | <code>            feasible = feasible &amp; (counts[None, None, :] &lt;= max_by_budget[..., None])</code> |
| 69 | DOC/COMMENT | <code>        # Inactive layers must have count zero. Active positive-budget layers must have</code> |
| 70 | DOC/COMMENT | <code>        # at least one hit whenever the threshold permits one.</code> |
| 71 | STATIC+EXECUTED | <code>        inactive = active_layers &lt;= 0</code> |
| 72 | STATIC+EXECUTED | <code>        feasible = torch.where(</code> |
| 73 | STATIC+MANUAL | <code>            inactive[..., None], counts[None, None, :] == 0, feasible</code> |
| 74 | STATIC+MANUAL | <code>        )</code> |
| 75 | STATIC+EXECUTED | <code>        can_resolve = (layer_energy &gt;= threshold_gev) if threshold_gev &gt; 0 else (layer_energy &gt; 0)</code> |
| 76 | STATIC+EXECUTED | <code>        require_positive = (~inactive) &amp; can_resolve</code> |
| 77 | STATIC+EXECUTED | <code>        feasible = feasible &amp; ~(</code> |
| 78 | STATIC+MANUAL | <code>            require_positive[..., None] &amp; (counts[None, None, :] == 0)</code> |
| 79 | STATIC+MANUAL | <code>        )</code> |
| 80 | STATIC+EXECUTED | <code>        return logits.masked_fill(~feasible, torch.finfo(logits.dtype).min)</code> |
| 82 | STATIC+EXECUTED | <code>    def sample(</code> |
| 83 | STATIC+MANUAL | <code>        self,</code> |
| 84 | STATIC+MANUAL | <code>        cond: torch.Tensor,</code> |
| 85 | STATIC+MANUAL | <code>        layer_energy: torch.Tensor,</code> |
| 86 | STATIC+MANUAL | <code>        active_layers: torch.Tensor,</code> |
| 87 | STATIC+MANUAL | <code>        threshold_gev: float = 0.0,</code> |
| 88 | STATIC+MANUAL | <code>        stochastic: bool = True,</code> |
| 89 | STATIC+MANUAL | <code>    ) -&gt; tuple[torch.Tensor, torch.Tensor]:</code> |
| 90 | STATIC+EXECUTED | <code>        logits = self.logits(cond, layer_energy, active_layers, threshold_gev)</code> |
| 91 | STATIC+EXECUTED | <code>        if stochastic:</code> |
| 92 | STATIC+EXECUTED | <code>            flat = torch.distributions.Categorical(</code> |
| 93 | STATIC+MANUAL | <code>                logits=logits.reshape(-1, logits.shape[-1])</code> |
| 94 | STATIC+MANUAL | <code>            ).sample()</code> |
| 95 | STATIC+EXECUTED | <code>            counts = flat.reshape(logits.shape[:-1])</code> |
| 96 | STATIC+MANUAL | <code>        else:</code> |
| 97 | STATIC+EXECUTED | <code>            counts = logits.argmax(dim=-1)</code> |
| 98 | STATIC+EXECUTED | <code>        return counts.long(), logits</code> |

## `src/cbsc_zdc/models/graph.py`

- SHA-256: `c7dbe1bc098f9c81248a4462dca6b38e193396751a222dedbf730a80d10c9263`
- Physical lines: 64; nonblank lines listed below: 57.

| Line | Audit | Source |
|---:|---|---|
| 1 | STATIC+EXECUTED | <code>from __future__ import annotations</code> |
| 3 | STATIC+EXECUTED | <code>import torch</code> |
| 4 | STATIC+EXECUTED | <code>from torch import nn</code> |
| 7 | STATIC+EXECUTED | <code>class EdgeMessageBlock(nn.Module):</code> |
| 8 | DOC/COMMENT | <code>    """Residual edge-conditioned message passing using only core PyTorch operations.</code> |
| 10 | DOC/COMMENT | <code>    The geometry builder, not this block, is responsible for supplying physically valid</code> |
| 11 | DOC/COMMENT | <code>    lateral and directed longitudinal edges. Edge processing is chunked to limit memory.</code> |
| 12 | DOC/COMMENT | <code>    """</code> |
| 14 | STATIC+EXECUTED | <code>    def __init__(</code> |
| 15 | STATIC+MANUAL | <code>        self,</code> |
| 16 | STATIC+MANUAL | <code>        hidden: int,</code> |
| 17 | STATIC+MANUAL | <code>        edge_dim: int,</code> |
| 18 | STATIC+MANUAL | <code>        message_hidden: int &#124; None = None,</code> |
| 19 | STATIC+MANUAL | <code>        edge_chunk_size: int = 16384,</code> |
| 20 | STATIC+MANUAL | <code>    ):</code> |
| 21 | STATIC+EXECUTED | <code>        super().__init__()</code> |
| 22 | STATIC+EXECUTED | <code>        message_hidden = message_hidden or hidden * 2</code> |
| 23 | STATIC+EXECUTED | <code>        self.edge_dim = edge_dim</code> |
| 24 | STATIC+EXECUTED | <code>        self.edge_chunk_size = edge_chunk_size</code> |
| 25 | STATIC+EXECUTED | <code>        self.message = nn.Sequential(</code> |
| 26 | STATIC+MANUAL | <code>            nn.Linear(hidden * 2 + edge_dim, message_hidden),</code> |
| 27 | STATIC+MANUAL | <code>            nn.SiLU(),</code> |
| 28 | STATIC+MANUAL | <code>            nn.Linear(message_hidden, hidden),</code> |
| 29 | STATIC+MANUAL | <code>        )</code> |
| 30 | STATIC+EXECUTED | <code>        self.update = nn.Sequential(</code> |
| 31 | STATIC+MANUAL | <code>            nn.LayerNorm(hidden * 2),</code> |
| 32 | STATIC+MANUAL | <code>            nn.Linear(hidden * 2, hidden * 2),</code> |
| 33 | STATIC+MANUAL | <code>            nn.SiLU(),</code> |
| 34 | STATIC+MANUAL | <code>            nn.Linear(hidden * 2, hidden),</code> |
| 35 | STATIC+MANUAL | <code>        )</code> |
| 37 | STATIC+EXECUTED | <code>    def forward(</code> |
| 38 | STATIC+MANUAL | <code>        self,</code> |
| 39 | STATIC+MANUAL | <code>        h: torch.Tensor,</code> |
| 40 | STATIC+MANUAL | <code>        edge_index: torch.Tensor,</code> |
| 41 | STATIC+MANUAL | <code>        edge_features: torch.Tensor,</code> |
| 42 | STATIC+MANUAL | <code>    ) -&gt; torch.Tensor:</code> |
| 43 | STATIC+EXECUTED | <code>        if edge_index.ndim != 2 or edge_index.shape[0] != 2:</code> |
| 44 | STATIC+EXECUTED | <code>            raise ValueError("edge_index must have shape [2,E]")</code> |
| 45 | STATIC+EXECUTED | <code>        if edge_features.shape != (edge_index.shape[1], self.edge_dim):</code> |
| 46 | STATIC+EXECUTED | <code>            raise ValueError("edge feature shape mismatch")</code> |
| 47 | STATIC+EXECUTED | <code>        batch, n_nodes, hidden = h.shape</code> |
| 48 | STATIC+EXECUTED | <code>        if edge_index.numel() and (</code> |
| 49 | STATIC+MANUAL | <code>            edge_index.min() &lt; 0 or edge_index.max() &gt;= n_nodes</code> |
| 50 | STATIC+MANUAL | <code>        ):</code> |
| 51 | STATIC+EXECUTED | <code>            raise ValueError("edge_index contains an invalid node id")</code> |
| 53 | STATIC+EXECUTED | <code>        aggregate = torch.zeros_like(h)</code> |
| 54 | STATIC+EXECUTED | <code>        source_all, target_all = edge_index</code> |
| 55 | STATIC+EXECUTED | <code>        for start in range(0, edge_index.shape[1], self.edge_chunk_size):</code> |
| 56 | STATIC+EXECUTED | <code>            stop = min(start + self.edge_chunk_size, edge_index.shape[1])</code> |
| 57 | STATIC+EXECUTED | <code>            source = source_all[start:stop]</code> |
| 58 | STATIC+EXECUTED | <code>            target = target_all[start:stop]</code> |
| 59 | STATIC+EXECUTED | <code>            edge = edge_features[start:stop][None].expand(batch, -1, -1)</code> |
| 60 | STATIC+EXECUTED | <code>            msg = self.message(</code> |
| 61 | STATIC+MANUAL | <code>                torch.cat((h[:, source], h[:, target], edge), dim=-1)</code> |
| 62 | STATIC+MANUAL | <code>            )</code> |
| 63 | STATIC+EXECUTED | <code>            aggregate.index_add_(1, target, msg)</code> |
| 64 | STATIC+EXECUTED | <code>        return h + self.update(torch.cat((h, aggregate), dim=-1))</code> |

## `src/cbsc_zdc/models/profile.py`

- SHA-256: `0d5d069f100afefe4b8de8b506268f9c95a9afbc8b79e9d112aff5e823a27404`
- Physical lines: 295; nonblank lines listed below: 259.

| Line | Audit | Source |
|---:|---|---|
| 1 | STATIC+EXECUTED | <code>from __future__ import annotations</code> |
| 3 | STATIC+EXECUTED | <code>from dataclasses import dataclass</code> |
| 5 | STATIC+EXECUTED | <code>import torch</code> |
| 6 | STATIC+EXECUTED | <code>from torch import nn</code> |
| 7 | STATIC+EXECUTED | <code>from torch.distributions import Beta, Categorical</code> |
| 10 | STATIC+EXECUTED | <code>@dataclass</code> |
| 11 | STATIC+EXECUTED | <code>class ProfileOutput:</code> |
| 12 | STATIC+EXECUTED | <code>    visible: torch.Tensor</code> |
| 13 | STATIC+EXECUTED | <code>    response_fraction: torch.Tensor</code> |
| 14 | STATIC+EXECUTED | <code>    total: torch.Tensor</code> |
| 15 | STATIC+EXECUTED | <code>    first_visible_layer: torch.Tensor</code> |
| 16 | STATIC+EXECUTED | <code>    active_layers: torch.Tensor</code> |
| 17 | STATIC+EXECUTED | <code>    layer_energy: torch.Tensor</code> |
| 18 | STATIC+EXECUTED | <code>    reserve: torch.Tensor</code> |
| 19 | STATIC+EXECUTED | <code>    layer_weights: torch.Tensor</code> |
| 22 | STATIC+EXECUTED | <code>class VisibleResponseHead(nn.Module):</code> |
| 23 | DOC/COMMENT | <code>    """Bernoulli hurdle for events with no modeled visible response."""</code> |
| 25 | STATIC+EXECUTED | <code>    def __init__(self, cond_dim: int = 128, latent_dim: int = 32, hidden: int = 128):</code> |
| 26 | STATIC+EXECUTED | <code>        super().__init__()</code> |
| 27 | STATIC+EXECUTED | <code>        self.latent_dim = latent_dim</code> |
| 28 | STATIC+EXECUTED | <code>        self.net = nn.Sequential(</code> |
| 29 | STATIC+MANUAL | <code>            nn.Linear(cond_dim + latent_dim, hidden),</code> |
| 30 | STATIC+MANUAL | <code>            nn.SiLU(),</code> |
| 31 | STATIC+MANUAL | <code>            nn.Linear(hidden, 1),</code> |
| 32 | STATIC+MANUAL | <code>        )</code> |
| 34 | STATIC+EXECUTED | <code>    def forward(self, cond: torch.Tensor, z: torch.Tensor) -&gt; torch.Tensor:</code> |
| 35 | STATIC+EXECUTED | <code>        return self.net(torch.cat((cond, z), dim=-1))</code> |
| 38 | STATIC+EXECUTED | <code>class MixtureBetaResponse(nn.Module):</code> |
| 39 | DOC/COMMENT | <code>    """Bounded mixture model for rho = E_dep / E_inc in [0, 1].</code> |
| 41 | DOC/COMMENT | <code>    This support is appropriate only after the stored target has been audited as raw</code> |
| 42 | DOC/COMMENT | <code>    deposited energy with no legitimate overflow beyond incident total energy.</code> |
| 43 | DOC/COMMENT | <code>    """</code> |
| 45 | STATIC+EXECUTED | <code>    def __init__(</code> |
| 46 | STATIC+MANUAL | <code>        self,</code> |
| 47 | STATIC+MANUAL | <code>        cond_dim: int = 128,</code> |
| 48 | STATIC+MANUAL | <code>        latent_dim: int = 32,</code> |
| 49 | STATIC+MANUAL | <code>        hidden: int = 192,</code> |
| 50 | STATIC+MANUAL | <code>        components: int = 4,</code> |
| 51 | STATIC+MANUAL | <code>        concentration_floor: float = 0.2,</code> |
| 52 | STATIC+MANUAL | <code>    ):</code> |
| 53 | STATIC+EXECUTED | <code>        super().__init__()</code> |
| 54 | STATIC+EXECUTED | <code>        self.components = components</code> |
| 55 | STATIC+EXECUTED | <code>        self.concentration_floor = concentration_floor</code> |
| 56 | STATIC+EXECUTED | <code>        self.net = nn.Sequential(</code> |
| 57 | STATIC+MANUAL | <code>            nn.Linear(cond_dim + latent_dim, hidden),</code> |
| 58 | STATIC+MANUAL | <code>            nn.SiLU(),</code> |
| 59 | STATIC+MANUAL | <code>            nn.Linear(hidden, hidden),</code> |
| 60 | STATIC+MANUAL | <code>            nn.SiLU(),</code> |
| 61 | STATIC+MANUAL | <code>            nn.Linear(hidden, 3 * components),</code> |
| 62 | STATIC+MANUAL | <code>        )</code> |
| 64 | STATIC+EXECUTED | <code>    def parameters_from_condition(</code> |
| 65 | STATIC+MANUAL | <code>        self, cond: torch.Tensor, z: torch.Tensor</code> |
| 66 | STATIC+MANUAL | <code>    ) -&gt; tuple[torch.Tensor, torch.Tensor, torch.Tensor]:</code> |
| 67 | STATIC+EXECUTED | <code>        raw = self.net(torch.cat((cond, z), dim=-1))</code> |
| 68 | STATIC+EXECUTED | <code>        mix_logits, raw_alpha, raw_beta = raw.chunk(3, dim=-1)</code> |
| 69 | STATIC+EXECUTED | <code>        alpha = torch.nn.functional.softplus(raw_alpha) + self.concentration_floor</code> |
| 70 | STATIC+EXECUTED | <code>        beta = torch.nn.functional.softplus(raw_beta) + self.concentration_floor</code> |
| 71 | STATIC+EXECUTED | <code>        return mix_logits, alpha, beta</code> |
| 73 | STATIC+EXECUTED | <code>    def sample(</code> |
| 74 | STATIC+MANUAL | <code>        self,</code> |
| 75 | STATIC+MANUAL | <code>        cond: torch.Tensor,</code> |
| 76 | STATIC+MANUAL | <code>        z: torch.Tensor,</code> |
| 77 | STATIC+MANUAL | <code>        stochastic: bool = True,</code> |
| 78 | STATIC+MANUAL | <code>    ) -&gt; torch.Tensor:</code> |
| 79 | STATIC+EXECUTED | <code>        mix_logits, alpha, beta = self.parameters_from_condition(cond, z)</code> |
| 80 | STATIC+EXECUTED | <code>        if stochastic:</code> |
| 81 | STATIC+EXECUTED | <code>            component = Categorical(logits=mix_logits).sample()</code> |
| 82 | STATIC+MANUAL | <code>        else:</code> |
| 83 | STATIC+EXECUTED | <code>            component = mix_logits.argmax(dim=-1)</code> |
| 84 | STATIC+EXECUTED | <code>        chosen_alpha = alpha.gather(1, component[:, None]).squeeze(1)</code> |
| 85 | STATIC+EXECUTED | <code>        chosen_beta = beta.gather(1, component[:, None]).squeeze(1)</code> |
| 86 | STATIC+EXECUTED | <code>        if stochastic:</code> |
| 87 | STATIC+EXECUTED | <code>            response = Beta(chosen_alpha, chosen_beta).sample()</code> |
| 88 | STATIC+MANUAL | <code>        else:</code> |
| 89 | STATIC+EXECUTED | <code>            response = chosen_alpha / (chosen_alpha + chosen_beta)</code> |
| 90 | STATIC+EXECUTED | <code>        return response[:, None]</code> |
| 93 | STATIC+EXECUTED | <code>class FirstVisibleLayerHazard(nn.Module):</code> |
| 94 | DOC/COMMENT | <code>    """Discrete survival/hazard model for the first visible detector layer."""</code> |
| 96 | STATIC+EXECUTED | <code>    def __init__(</code> |
| 97 | STATIC+MANUAL | <code>        self,</code> |
| 98 | STATIC+MANUAL | <code>        cond_dim: int = 128,</code> |
| 99 | STATIC+MANUAL | <code>        latent_dim: int = 32,</code> |
| 100 | STATIC+MANUAL | <code>        n_layers: int = 65,</code> |
| 101 | STATIC+MANUAL | <code>        hidden: int = 192,</code> |
| 102 | STATIC+MANUAL | <code>    ):</code> |
| 103 | STATIC+EXECUTED | <code>        super().__init__()</code> |
| 104 | STATIC+EXECUTED | <code>        self.n_layers = n_layers</code> |
| 105 | STATIC+EXECUTED | <code>        self.net = nn.Sequential(</code> |
| 106 | STATIC+MANUAL | <code>            nn.Linear(cond_dim + latent_dim + 1, hidden),</code> |
| 107 | STATIC+MANUAL | <code>            nn.SiLU(),</code> |
| 108 | STATIC+MANUAL | <code>            nn.Linear(hidden, hidden),</code> |
| 109 | STATIC+MANUAL | <code>            nn.SiLU(),</code> |
| 110 | STATIC+MANUAL | <code>            nn.Linear(hidden, n_layers),</code> |
| 111 | STATIC+MANUAL | <code>        )</code> |
| 113 | STATIC+EXECUTED | <code>    def conditional_start_logits(</code> |
| 114 | STATIC+MANUAL | <code>        self, cond: torch.Tensor, z: torch.Tensor, response_fraction: torch.Tensor</code> |
| 115 | STATIC+MANUAL | <code>    ) -&gt; torch.Tensor:</code> |
| 116 | STATIC+EXECUTED | <code>        hazard_logits = self.net(torch.cat((cond, z, response_fraction), dim=-1))</code> |
| 117 | STATIC+EXECUTED | <code>        log_hazard = torch.nn.functional.logsigmoid(hazard_logits)</code> |
| 118 | STATIC+EXECUTED | <code>        log_survival = torch.nn.functional.logsigmoid(-hazard_logits)</code> |
| 119 | STATIC+EXECUTED | <code>        prefix = torch.cat(</code> |
| 120 | STATIC+MANUAL | <code>            (</code> |
| 121 | STATIC+MANUAL | <code>                torch.zeros_like(log_survival[:, :1]),</code> |
| 122 | STATIC+MANUAL | <code>                torch.cumsum(log_survival[:, :-1], dim=-1),</code> |
| 123 | STATIC+MANUAL | <code>            ),</code> |
| 124 | STATIC+MANUAL | <code>            dim=-1,</code> |
| 125 | STATIC+MANUAL | <code>        )</code> |
| 126 | DOC/COMMENT | <code>        # Categorical sampling normalizes over starts that occur inside the detector.</code> |
| 127 | STATIC+EXECUTED | <code>        return log_hazard + prefix</code> |
| 130 | STATIC+EXECUTED | <code>class LayerActivityHead(nn.Module):</code> |
| 131 | DOC/COMMENT | <code>    """Correlated layer-activity logits conditioned on a shared event latent.</code> |
| 133 | DOC/COMMENT | <code>    The output is a stochastic binary support over ECAL + HCAL layers. Exact inactive</code> |
| 134 | DOC/COMMENT | <code>    layers are generated before positive layer-energy allocation, avoiding the dense</code> |
| 135 | DOC/COMMENT | <code>    positive support induced by a plain softmax.</code> |
| 136 | DOC/COMMENT | <code>    """</code> |
| 138 | STATIC+EXECUTED | <code>    def __init__(</code> |
| 139 | STATIC+MANUAL | <code>        self,</code> |
| 140 | STATIC+MANUAL | <code>        cond_dim: int = 128,</code> |
| 141 | STATIC+MANUAL | <code>        latent_dim: int = 32,</code> |
| 142 | STATIC+MANUAL | <code>        n_layers: int = 65,</code> |
| 143 | STATIC+MANUAL | <code>        hidden: int = 192,</code> |
| 144 | STATIC+MANUAL | <code>    ):</code> |
| 145 | STATIC+EXECUTED | <code>        super().__init__()</code> |
| 146 | STATIC+EXECUTED | <code>        self.n_layers = n_layers</code> |
| 147 | STATIC+EXECUTED | <code>        self.net = nn.Sequential(</code> |
| 148 | STATIC+MANUAL | <code>            nn.Linear(cond_dim + latent_dim + 1, hidden),</code> |
| 149 | STATIC+MANUAL | <code>            nn.SiLU(),</code> |
| 150 | STATIC+MANUAL | <code>            nn.Linear(hidden, hidden),</code> |
| 151 | STATIC+MANUAL | <code>            nn.SiLU(),</code> |
| 152 | STATIC+MANUAL | <code>            nn.Linear(hidden, n_layers),</code> |
| 153 | STATIC+MANUAL | <code>        )</code> |
| 155 | STATIC+EXECUTED | <code>    def forward(</code> |
| 156 | STATIC+MANUAL | <code>        self, cond: torch.Tensor, z: torch.Tensor, response_fraction: torch.Tensor</code> |
| 157 | STATIC+MANUAL | <code>    ) -&gt; torch.Tensor:</code> |
| 158 | STATIC+EXECUTED | <code>        return self.net(torch.cat((cond, z, response_fraction), dim=-1))</code> |
| 161 | STATIC+EXECUTED | <code>class MaskedSimplexProfile(nn.Module):</code> |
| 162 | DOC/COMMENT | <code>    """Stochastic positive allocation over active layers plus a reserve channel.</code> |
| 164 | DOC/COMMENT | <code>    The current implementation is a logistic-normal reference sampler. The research</code> |
| 165 | DOC/COMMENT | <code>    specification permits replacing this module with a low-dimensional conditional flow</code> |
| 166 | DOC/COMMENT | <code>    matching model over the same masked-simplex target without changing the decoder.</code> |
| 167 | DOC/COMMENT | <code>    """</code> |
| 169 | STATIC+EXECUTED | <code>    def __init__(</code> |
| 170 | STATIC+MANUAL | <code>        self,</code> |
| 171 | STATIC+MANUAL | <code>        cond_dim: int = 128,</code> |
| 172 | STATIC+MANUAL | <code>        latent_dim: int = 32,</code> |
| 173 | STATIC+MANUAL | <code>        n_layers: int = 65,</code> |
| 174 | STATIC+MANUAL | <code>        hidden: int = 256,</code> |
| 175 | STATIC+MANUAL | <code>    ):</code> |
| 176 | STATIC+EXECUTED | <code>        super().__init__()</code> |
| 177 | STATIC+EXECUTED | <code>        self.n_layers = n_layers</code> |
| 178 | STATIC+EXECUTED | <code>        self.net = nn.Sequential(</code> |
| 179 | STATIC+MANUAL | <code>            nn.Linear(cond_dim + latent_dim + 1, hidden),</code> |
| 180 | STATIC+MANUAL | <code>            nn.SiLU(),</code> |
| 181 | STATIC+MANUAL | <code>            nn.Linear(hidden, hidden),</code> |
| 182 | STATIC+MANUAL | <code>            nn.SiLU(),</code> |
| 183 | STATIC+MANUAL | <code>            nn.Linear(hidden, n_layers + 1),</code> |
| 184 | STATIC+MANUAL | <code>        )</code> |
| 186 | STATIC+EXECUTED | <code>    def forward(</code> |
| 187 | STATIC+MANUAL | <code>        self,</code> |
| 188 | STATIC+MANUAL | <code>        cond: torch.Tensor,</code> |
| 189 | STATIC+MANUAL | <code>        z: torch.Tensor,</code> |
| 190 | STATIC+MANUAL | <code>        total: torch.Tensor,</code> |
| 191 | STATIC+MANUAL | <code>        active_layers: torch.Tensor,</code> |
| 192 | STATIC+MANUAL | <code>    ) -&gt; tuple[torch.Tensor, torch.Tensor, torch.Tensor]:</code> |
| 193 | STATIC+EXECUTED | <code>        raw = self.net(torch.cat((cond, z, total), dim=-1))</code> |
| 194 | STATIC+EXECUTED | <code>        layer_logits = raw[:, : self.n_layers]</code> |
| 195 | STATIC+EXECUTED | <code>        reserve_logit = raw[:, self.n_layers :]</code> |
| 196 | STATIC+EXECUTED | <code>        neg_inf = torch.finfo(layer_logits.dtype).min</code> |
| 197 | STATIC+EXECUTED | <code>        masked_layer_logits = torch.where(</code> |
| 198 | STATIC+MANUAL | <code>            active_layers.bool(), layer_logits, torch.full_like(layer_logits, neg_inf)</code> |
| 199 | STATIC+MANUAL | <code>        )</code> |
| 200 | STATIC+EXECUTED | <code>        logits = torch.cat((masked_layer_logits, reserve_logit), dim=-1)</code> |
| 201 | STATIC+EXECUTED | <code>        weights = torch.softmax(logits, dim=-1)</code> |
| 202 | STATIC+EXECUTED | <code>        layer_energy = total * weights[:, : self.n_layers]</code> |
| 203 | STATIC+EXECUTED | <code>        reserve = total * weights[:, self.n_layers :]</code> |
| 204 | STATIC+EXECUTED | <code>        return layer_energy, reserve, weights</code> |
| 207 | STATIC+EXECUTED | <code>class LongitudinalProfileModel(nn.Module):</code> |
| 208 | DOC/COMMENT | <code>    """Hurdle + bounded response + exact-zero layer support + simplex allocation."""</code> |
| 210 | STATIC+EXECUTED | <code>    def __init__(</code> |
| 211 | STATIC+MANUAL | <code>        self,</code> |
| 212 | STATIC+MANUAL | <code>        cond_dim: int = 128,</code> |
| 213 | STATIC+MANUAL | <code>        latent_dim: int = 32,</code> |
| 214 | STATIC+MANUAL | <code>        n_layers: int = 65,</code> |
| 215 | STATIC+MANUAL | <code>        response_components: int = 4,</code> |
| 216 | STATIC+MANUAL | <code>    ):</code> |
| 217 | STATIC+EXECUTED | <code>        super().__init__()</code> |
| 218 | STATIC+EXECUTED | <code>        self.latent_dim = latent_dim</code> |
| 219 | STATIC+EXECUTED | <code>        self.n_layers = n_layers</code> |
| 220 | STATIC+EXECUTED | <code>        self.visible_head = VisibleResponseHead(cond_dim, latent_dim)</code> |
| 221 | STATIC+EXECUTED | <code>        self.response = MixtureBetaResponse(</code> |
| 222 | STATIC+MANUAL | <code>            cond_dim, latent_dim, components=response_components</code> |
| 223 | STATIC+MANUAL | <code>        )</code> |
| 224 | STATIC+EXECUTED | <code>        self.start = FirstVisibleLayerHazard(cond_dim, latent_dim, n_layers)</code> |
| 225 | STATIC+EXECUTED | <code>        self.activity = LayerActivityHead(cond_dim, latent_dim, n_layers)</code> |
| 226 | STATIC+EXECUTED | <code>        self.profile = MaskedSimplexProfile(cond_dim, latent_dim, n_layers)</code> |
| 228 | STATIC+EXECUTED | <code>    def sample(</code> |
| 229 | STATIC+MANUAL | <code>        self,</code> |
| 230 | STATIC+MANUAL | <code>        incident_e: torch.Tensor,</code> |
| 231 | STATIC+MANUAL | <code>        cond: torch.Tensor,</code> |
| 232 | STATIC+MANUAL | <code>        z_event: torch.Tensor &#124; None = None,</code> |
| 233 | STATIC+MANUAL | <code>        stochastic: bool = True,</code> |
| 234 | STATIC+MANUAL | <code>    ) -&gt; ProfileOutput:</code> |
| 235 | STATIC+EXECUTED | <code>        batch = cond.shape[0]</code> |
| 236 | STATIC+EXECUTED | <code>        if z_event is None:</code> |
| 237 | STATIC+EXECUTED | <code>            if stochastic:</code> |
| 238 | STATIC+EXECUTED | <code>                z_event = torch.randn(</code> |
| 239 | STATIC+MANUAL | <code>                    batch,</code> |
| 240 | STATIC+MANUAL | <code>                    self.latent_dim,</code> |
| 241 | STATIC+MANUAL | <code>                    device=cond.device,</code> |
| 242 | STATIC+MANUAL | <code>                    dtype=cond.dtype,</code> |
| 243 | STATIC+MANUAL | <code>                )</code> |
| 244 | STATIC+MANUAL | <code>            else:</code> |
| 245 | STATIC+EXECUTED | <code>                z_event = torch.zeros(</code> |
| 246 | STATIC+MANUAL | <code>                    batch,</code> |
| 247 | STATIC+MANUAL | <code>                    self.latent_dim,</code> |
| 248 | STATIC+MANUAL | <code>                    device=cond.device,</code> |
| 249 | STATIC+MANUAL | <code>                    dtype=cond.dtype,</code> |
| 250 | STATIC+MANUAL | <code>                )</code> |
| 251 | STATIC+EXECUTED | <code>        visible_prob = torch.sigmoid(self.visible_head(cond, z_event))</code> |
| 252 | STATIC+EXECUTED | <code>        if stochastic:</code> |
| 253 | STATIC+EXECUTED | <code>            visible = torch.bernoulli(visible_prob)</code> |
| 254 | STATIC+MANUAL | <code>        else:</code> |
| 255 | STATIC+EXECUTED | <code>            visible = (visible_prob &gt;= 0.5).to(cond.dtype)</code> |
| 257 | STATIC+EXECUTED | <code>        rho = self.response.sample(cond, z_event, stochastic=stochastic)</code> |
| 258 | STATIC+EXECUTED | <code>        rho = rho * visible</code> |
| 259 | STATIC+EXECUTED | <code>        total = incident_e * rho</code> |
| 261 | STATIC+EXECUTED | <code>        start_logits = self.start.conditional_start_logits(cond, z_event, rho)</code> |
| 262 | STATIC+EXECUTED | <code>        if stochastic:</code> |
| 263 | STATIC+EXECUTED | <code>            first_visible = Categorical(logits=start_logits).sample()</code> |
| 264 | STATIC+MANUAL | <code>        else:</code> |
| 265 | STATIC+EXECUTED | <code>            first_visible = start_logits.argmax(dim=-1)</code> |
| 266 | STATIC+EXECUTED | <code>        first_visible = torch.where(</code> |
| 267 | STATIC+MANUAL | <code>            visible.squeeze(-1) &gt; 0, first_visible, torch.full_like(first_visible, -1)</code> |
| 268 | STATIC+MANUAL | <code>        )</code> |
| 270 | STATIC+EXECUTED | <code>        activity_logits = self.activity(cond, z_event, rho)</code> |
| 271 | STATIC+EXECUTED | <code>        activity_prob = torch.sigmoid(activity_logits)</code> |
| 272 | STATIC+EXECUTED | <code>        if stochastic:</code> |
| 273 | STATIC+EXECUTED | <code>            active = torch.bernoulli(activity_prob)</code> |
| 274 | STATIC+MANUAL | <code>        else:</code> |
| 275 | STATIC+EXECUTED | <code>            active = (activity_prob &gt;= 0.5).to(cond.dtype)</code> |
| 276 | STATIC+EXECUTED | <code>        layer_ids = torch.arange(self.n_layers, device=cond.device)[None]</code> |
| 277 | STATIC+EXECUTED | <code>        before_start = layer_ids &lt; first_visible.clamp_min(0)[:, None]</code> |
| 278 | STATIC+EXECUTED | <code>        active = active.masked_fill(before_start, 0.0) * visible</code> |
| 279 | STATIC+EXECUTED | <code>        visible_rows = visible.squeeze(-1) &gt; 0</code> |
| 280 | STATIC+EXECUTED | <code>        if visible_rows.any():</code> |
| 281 | STATIC+EXECUTED | <code>            active[visible_rows, first_visible[visible_rows]] = 1.0</code> |
| 283 | STATIC+EXECUTED | <code>        layer_energy, reserve, weights = self.profile(</code> |
| 284 | STATIC+MANUAL | <code>            cond, z_event, total, active</code> |
| 285 | STATIC+MANUAL | <code>        )</code> |
| 286 | STATIC+EXECUTED | <code>        return ProfileOutput(</code> |
| 287 | STATIC+MANUAL | <code>            visible=visible,</code> |
| 288 | STATIC+MANUAL | <code>            response_fraction=rho,</code> |
| 289 | STATIC+MANUAL | <code>            total=total,</code> |
| 290 | STATIC+MANUAL | <code>            first_visible_layer=first_visible,</code> |
| 291 | STATIC+MANUAL | <code>            active_layers=active,</code> |
| 292 | STATIC+MANUAL | <code>            layer_energy=layer_energy,</code> |
| 293 | STATIC+MANUAL | <code>            reserve=reserve,</code> |
| 294 | STATIC+MANUAL | <code>            layer_weights=weights,</code> |
| 295 | STATIC+MANUAL | <code>        )</code> |

## `src/cbsc_zdc/models/spatial.py`

- SHA-256: `12a43ceabc5f3193f16fe0fe0f7b642e986f4904f1f158eb565bd529b9624b58`
- Physical lines: 132; nonblank lines listed below: 122.

| Line | Audit | Source |
|---:|---|---|
| 1 | STATIC+EXECUTED | <code>from __future__ import annotations</code> |
| 3 | STATIC+EXECUTED | <code>import torch</code> |
| 4 | STATIC+EXECUTED | <code>from torch import nn</code> |
| 6 | STATIC+EXECUTED | <code>from .blocks import FiLM</code> |
| 7 | STATIC+EXECUTED | <code>from .graph import EdgeMessageBlock</code> |
| 10 | STATIC+EXECUTED | <code>class ParallelCausalSpatialField(nn.Module):</code> |
| 11 | DOC/COMMENT | <code>    """Parallel time-dependent graph field with causal longitudinal layer attention.</code> |
| 13 | DOC/COMMENT | <code>    Every solver step updates all nodes simultaneously. Edge-conditioned message passing</code> |
| 14 | DOC/COMMENT | <code>    represents local detector geometry. Layer l may attend to itself and earlier layers</code> |
| 15 | DOC/COMMENT | <code>    through a causal mask, preserving longitudinal context without a 65-call rollout.</code> |
| 16 | DOC/COMMENT | <code>    """</code> |
| 18 | STATIC+EXECUTED | <code>    def __init__(</code> |
| 19 | STATIC+MANUAL | <code>        self,</code> |
| 20 | STATIC+MANUAL | <code>        node_dim: int = 8,</code> |
| 21 | STATIC+MANUAL | <code>        edge_dim: int = 4,</code> |
| 22 | STATIC+MANUAL | <code>        cond_dim: int = 128,</code> |
| 23 | STATIC+MANUAL | <code>        hidden: int = 96,</code> |
| 24 | STATIC+MANUAL | <code>        n_layers: int = 65,</code> |
| 25 | STATIC+MANUAL | <code>        graph_blocks: int = 2,</code> |
| 26 | STATIC+MANUAL | <code>        transformer_blocks: int = 3,</code> |
| 27 | STATIC+MANUAL | <code>        heads: int = 4,</code> |
| 28 | STATIC+MANUAL | <code>        edge_chunk_size: int = 16384,</code> |
| 29 | STATIC+MANUAL | <code>    ):</code> |
| 30 | STATIC+EXECUTED | <code>        super().__init__()</code> |
| 31 | STATIC+EXECUTED | <code>        if hidden % heads != 0:</code> |
| 32 | STATIC+EXECUTED | <code>            raise ValueError("hidden dimension must be divisible by the number of heads")</code> |
| 33 | STATIC+EXECUTED | <code>        self.n_layers = n_layers</code> |
| 34 | STATIC+EXECUTED | <code>        self.edge_dim = edge_dim</code> |
| 35 | STATIC+EXECUTED | <code>        self.node_in = nn.Linear(node_dim + 2 + 2, hidden)</code> |
| 36 | STATIC+EXECUTED | <code>        self.time_embed = nn.Sequential(</code> |
| 37 | STATIC+MANUAL | <code>            nn.Linear(1, hidden), nn.SiLU(), nn.Linear(hidden, hidden)</code> |
| 38 | STATIC+MANUAL | <code>        )</code> |
| 39 | STATIC+EXECUTED | <code>        self.film = FiLM(cond_dim, hidden)</code> |
| 40 | STATIC+EXECUTED | <code>        self.graph_blocks = nn.ModuleList(</code> |
| 41 | STATIC+MANUAL | <code>            [</code> |
| 42 | STATIC+MANUAL | <code>                EdgeMessageBlock(</code> |
| 43 | STATIC+MANUAL | <code>                    hidden=hidden,</code> |
| 44 | STATIC+MANUAL | <code>                    edge_dim=edge_dim,</code> |
| 45 | STATIC+MANUAL | <code>                    edge_chunk_size=edge_chunk_size,</code> |
| 46 | STATIC+MANUAL | <code>                )</code> |
| 47 | STATIC+MANUAL | <code>                for _ in range(graph_blocks)</code> |
| 48 | STATIC+MANUAL | <code>            ]</code> |
| 49 | STATIC+MANUAL | <code>        )</code> |
| 50 | STATIC+EXECUTED | <code>        encoder_layer = nn.TransformerEncoderLayer(</code> |
| 51 | STATIC+MANUAL | <code>            hidden,</code> |
| 52 | STATIC+MANUAL | <code>            heads,</code> |
| 53 | STATIC+MANUAL | <code>            hidden * 4,</code> |
| 54 | STATIC+MANUAL | <code>            batch_first=True,</code> |
| 55 | STATIC+MANUAL | <code>            norm_first=True,</code> |
| 56 | STATIC+MANUAL | <code>            activation="gelu",</code> |
| 57 | STATIC+MANUAL | <code>        )</code> |
| 58 | STATIC+EXECUTED | <code>        self.layer_mixer = nn.TransformerEncoder(</code> |
| 59 | STATIC+MANUAL | <code>            encoder_layer, transformer_blocks</code> |
| 60 | STATIC+MANUAL | <code>        )</code> |
| 61 | STATIC+EXECUTED | <code>        self.node_out = nn.Sequential(</code> |
| 62 | STATIC+MANUAL | <code>            nn.LayerNorm(hidden),</code> |
| 63 | STATIC+MANUAL | <code>            nn.Linear(hidden, hidden),</code> |
| 64 | STATIC+MANUAL | <code>            nn.SiLU(),</code> |
| 65 | STATIC+MANUAL | <code>            nn.Linear(hidden, 2),</code> |
| 66 | STATIC+MANUAL | <code>        )</code> |
| 67 | STATIC+EXECUTED | <code>        causal = torch.triu(</code> |
| 68 | STATIC+MANUAL | <code>            torch.ones(n_layers, n_layers, dtype=torch.bool), diagonal=1</code> |
| 69 | STATIC+MANUAL | <code>        )</code> |
| 70 | STATIC+EXECUTED | <code>        self.register_buffer("causal_layer_mask", causal)</code> |
| 72 | STATIC+EXECUTED | <code>    def forward(</code> |
| 73 | STATIC+MANUAL | <code>        self,</code> |
| 74 | STATIC+MANUAL | <code>        x_t: torch.Tensor,</code> |
| 75 | STATIC+MANUAL | <code>        t: torch.Tensor,</code> |
| 76 | STATIC+MANUAL | <code>        cond: torch.Tensor,</code> |
| 77 | STATIC+MANUAL | <code>        node_features: torch.Tensor,</code> |
| 78 | STATIC+MANUAL | <code>        layer_index: torch.Tensor,</code> |
| 79 | STATIC+MANUAL | <code>        layer_budget: torch.Tensor,</code> |
| 80 | STATIC+MANUAL | <code>        layer_counts: torch.Tensor,</code> |
| 81 | STATIC+MANUAL | <code>        max_counts: torch.Tensor,</code> |
| 82 | STATIC+MANUAL | <code>        valid_mask: torch.Tensor &#124; None = None,</code> |
| 83 | STATIC+MANUAL | <code>        edge_index: torch.Tensor &#124; None = None,</code> |
| 84 | STATIC+MANUAL | <code>        edge_features: torch.Tensor &#124; None = None,</code> |
| 85 | STATIC+MANUAL | <code>    ) -&gt; torch.Tensor:</code> |
| 86 | STATIC+EXECUTED | <code>        batch, n_nodes, state_dim = x_t.shape</code> |
| 87 | STATIC+EXECUTED | <code>        if state_dim != 2:</code> |
| 88 | STATIC+EXECUTED | <code>            raise ValueError("x_t must have two node-state channels")</code> |
| 89 | STATIC+EXECUTED | <code>        if node_features.shape[0] != n_nodes or layer_index.shape != (n_nodes,):</code> |
| 90 | STATIC+EXECUTED | <code>            raise ValueError("node geometry shape mismatch")</code> |
| 91 | STATIC+EXECUTED | <code>        if valid_mask is None:</code> |
| 92 | STATIC+EXECUTED | <code>            valid_mask = torch.ones(n_nodes, dtype=torch.bool, device=x_t.device)</code> |
| 93 | STATIC+EXECUTED | <code>        if valid_mask.shape != (n_nodes,):</code> |
| 94 | STATIC+EXECUTED | <code>            raise ValueError("valid_mask must have shape [nodes]")</code> |
| 95 | STATIC+EXECUTED | <code>        if (edge_index is None) != (edge_features is None):</code> |
| 96 | STATIC+EXECUTED | <code>            raise ValueError("edge_index and edge_features must be supplied together")</code> |
| 98 | STATIC+EXECUTED | <code>        node_static = node_features[None].expand(batch, -1, -1)</code> |
| 99 | STATIC+EXECUTED | <code>        expanded_layer = layer_index[None].expand(batch, -1)</code> |
| 100 | STATIC+EXECUTED | <code>        budget_node = layer_budget.gather(1, expanded_layer)</code> |
| 101 | STATIC+EXECUTED | <code>        count_fraction = (</code> |
| 102 | STATIC+MANUAL | <code>            layer_counts.float() / max_counts[None].clamp_min(1).float()</code> |
| 103 | STATIC+MANUAL | <code>        ).gather(1, expanded_layer)</code> |
| 104 | STATIC+EXECUTED | <code>        dynamic = torch.stack((torch.log1p(budget_node), count_fraction), dim=-1)</code> |
| 105 | STATIC+EXECUTED | <code>        h = self.node_in(torch.cat((x_t, node_static, dynamic), dim=-1))</code> |
| 106 | STATIC+EXECUTED | <code>        h = h + self.time_embed(t.reshape(batch, 1))[:, None, :]</code> |
| 107 | STATIC+EXECUTED | <code>        h = self.film(h, cond)</code> |
| 108 | STATIC+EXECUTED | <code>        h = h * valid_mask[None, :, None].to(h.dtype)</code> |
| 110 | STATIC+EXECUTED | <code>        if edge_index is not None and edge_features is not None:</code> |
| 111 | STATIC+EXECUTED | <code>            for block in self.graph_blocks:</code> |
| 112 | STATIC+EXECUTED | <code>                h = block(h, edge_index, edge_features)</code> |
| 113 | STATIC+EXECUTED | <code>                h = h * valid_mask[None, :, None].to(h.dtype)</code> |
| 115 | STATIC+EXECUTED | <code>        layer_sum = torch.zeros(</code> |
| 116 | STATIC+MANUAL | <code>            batch, self.n_layers, h.shape[-1], device=h.device, dtype=h.dtype</code> |
| 117 | STATIC+MANUAL | <code>        )</code> |
| 118 | STATIC+EXECUTED | <code>        gather_index = layer_index.view(1, n_nodes, 1).expand(</code> |
| 119 | STATIC+MANUAL | <code>            batch, n_nodes, h.shape[-1]</code> |
| 120 | STATIC+MANUAL | <code>        )</code> |
| 121 | STATIC+EXECUTED | <code>        layer_sum.scatter_add_(1, gather_index, h)</code> |
| 122 | STATIC+EXECUTED | <code>        valid_count = torch.zeros(</code> |
| 123 | STATIC+MANUAL | <code>            self.n_layers, device=h.device, dtype=h.dtype</code> |
| 124 | STATIC+MANUAL | <code>        )</code> |
| 125 | STATIC+EXECUTED | <code>        valid_count.scatter_add_(0, layer_index, valid_mask.to(h.dtype))</code> |
| 126 | STATIC+EXECUTED | <code>        layer_tokens = layer_sum / valid_count.clamp_min(1).view(1, -1, 1)</code> |
| 127 | STATIC+EXECUTED | <code>        layer_tokens = self.layer_mixer(</code> |
| 128 | STATIC+MANUAL | <code>            layer_tokens, mask=self.causal_layer_mask</code> |
| 129 | STATIC+MANUAL | <code>        )</code> |
| 130 | STATIC+EXECUTED | <code>        h = h + layer_tokens.gather(1, gather_index)</code> |
| 131 | STATIC+EXECUTED | <code>        out = self.node_out(h)</code> |
| 132 | STATIC+EXECUTED | <code>        return out * valid_mask[None, :, None].to(out.dtype)</code> |

## `src/cbsc_zdc/models/support.py`

- SHA-256: `b4c0b555e089639c7bb5cd00b1d36087c9fd167cd614aa6eb60f9cfb9a8f0ef7`
- Physical lines: 156; nonblank lines listed below: 133.

| Line | Audit | Source |
|---:|---|---|
| 1 | STATIC+EXECUTED | <code>from __future__ import annotations</code> |
| 3 | STATIC+EXECUTED | <code>from dataclasses import dataclass</code> |
| 5 | STATIC+EXECUTED | <code>import torch</code> |
| 8 | STATIC+EXECUTED | <code>@dataclass</code> |
| 9 | STATIC+EXECUTED | <code>class DecodeOutput:</code> |
| 10 | STATIC+EXECUTED | <code>    cell_energy: torch.Tensor</code> |
| 11 | STATIC+EXECUTED | <code>    resolved_layer_energy: torch.Tensor</code> |
| 12 | STATIC+EXECUTED | <code>    subthreshold_residual: torch.Tensor</code> |
| 13 | STATIC+EXECUTED | <code>    realized_counts: torch.Tensor</code> |
| 14 | STATIC+EXECUTED | <code>    support_mask: torch.Tensor</code> |
| 17 | STATIC+EXECUTED | <code>def _sample_gumbel_like(x: torch.Tensor, eps: float = 1e-8) -&gt; torch.Tensor:</code> |
| 18 | STATIC+EXECUTED | <code>    u = torch.rand_like(x).clamp_(eps, 1.0 - eps)</code> |
| 19 | STATIC+EXECUTED | <code>    return -torch.log(-torch.log(u))</code> |
| 22 | STATIC+EXECUTED | <code>def gumbel_topk_mask(</code> |
| 23 | STATIC+MANUAL | <code>    logits: torch.Tensor,</code> |
| 24 | STATIC+MANUAL | <code>    k: int,</code> |
| 25 | STATIC+MANUAL | <code>    stochastic: bool = True,</code> |
| 26 | STATIC+MANUAL | <code>) -&gt; torch.Tensor:</code> |
| 27 | DOC/COMMENT | <code>    """Return an exact k-hot mask for one score vector."""</code> |
| 28 | STATIC+EXECUTED | <code>    if logits.ndim != 1:</code> |
| 29 | STATIC+EXECUTED | <code>        raise ValueError("gumbel_topk_mask expects a one-dimensional score vector")</code> |
| 30 | STATIC+EXECUTED | <code>    if k &lt; 0 or k &gt; logits.numel():</code> |
| 31 | STATIC+EXECUTED | <code>        raise ValueError("k is outside the available support")</code> |
| 32 | STATIC+EXECUTED | <code>    mask = torch.zeros_like(logits, dtype=torch.bool)</code> |
| 33 | STATIC+EXECUTED | <code>    if k == 0:</code> |
| 34 | STATIC+EXECUTED | <code>        return mask</code> |
| 35 | STATIC+EXECUTED | <code>    scores = logits + _sample_gumbel_like(logits) if stochastic else logits</code> |
| 36 | STATIC+EXECUTED | <code>    selected = torch.topk(scores, k=k).indices</code> |
| 37 | STATIC+EXECUTED | <code>    mask[selected] = True</code> |
| 38 | STATIC+EXECUTED | <code>    return mask</code> |
| 41 | STATIC+EXECUTED | <code>def _batched_exact_k_mask(</code> |
| 42 | STATIC+MANUAL | <code>    logits: torch.Tensor,</code> |
| 43 | STATIC+MANUAL | <code>    k: torch.Tensor,</code> |
| 44 | STATIC+MANUAL | <code>    stochastic: bool,</code> |
| 45 | STATIC+MANUAL | <code>) -&gt; torch.Tensor:</code> |
| 46 | DOC/COMMENT | <code>    """Vectorized exact-k support selection for a batch of score vectors."""</code> |
| 47 | STATIC+EXECUTED | <code>    if logits.ndim != 2 or k.ndim != 1 or logits.shape[0] != k.shape[0]:</code> |
| 48 | STATIC+EXECUTED | <code>        raise ValueError("batched top-k shape mismatch")</code> |
| 49 | STATIC+EXECUTED | <code>    if (k &lt; 0).any() or (k &gt; logits.shape[1]).any():</code> |
| 50 | STATIC+EXECUTED | <code>        raise ValueError("batched top-k request is infeasible")</code> |
| 51 | STATIC+EXECUTED | <code>    scores = logits + _sample_gumbel_like(logits) if stochastic else logits</code> |
| 52 | STATIC+EXECUTED | <code>    order = torch.argsort(scores, dim=1, descending=True)</code> |
| 53 | STATIC+EXECUTED | <code>    rank_selected = torch.arange(logits.shape[1], device=logits.device)[None, :] &lt; k[:, None]</code> |
| 54 | STATIC+EXECUTED | <code>    mask = torch.zeros_like(logits, dtype=torch.bool)</code> |
| 55 | STATIC+EXECUTED | <code>    mask.scatter_(1, order, rank_selected)</code> |
| 56 | STATIC+EXECUTED | <code>    return mask</code> |
| 59 | STATIC+EXECUTED | <code>def threshold_safe_layer_decoder(</code> |
| 60 | STATIC+MANUAL | <code>    support_logits: torch.Tensor,</code> |
| 61 | STATIC+MANUAL | <code>    share_logits: torch.Tensor,</code> |
| 62 | STATIC+MANUAL | <code>    layer_budget: torch.Tensor,</code> |
| 63 | STATIC+MANUAL | <code>    requested_counts: torch.Tensor,</code> |
| 64 | STATIC+MANUAL | <code>    layer_index: torch.Tensor,</code> |
| 65 | STATIC+MANUAL | <code>    valid_mask: torch.Tensor,</code> |
| 66 | STATIC+MANUAL | <code>    threshold_gev: float = 0.0,</code> |
| 67 | STATIC+MANUAL | <code>    stochastic_support: bool = True,</code> |
| 68 | STATIC+MANUAL | <code>) -&gt; DecodeOutput:</code> |
| 69 | DOC/COMMENT | <code>    """Decode exact sparse cell energies without low-energy dust.</code> |
| 71 | DOC/COMMENT | <code>    For each layer with budget B and realized count K, selected cells obey</code> |
| 73 | DOC/COMMENT | <code>        e_i = tau + (B - K*tau) * softmax(r)_i,</code> |
| 75 | DOC/COMMENT | <code>    and every unselected cell is exactly zero. If B &lt; tau, no above-threshold</code> |
| 76 | DOC/COMMENT | <code>    cell is possible; B is retained as a layer-level subthreshold residual.</code> |
| 78 | DOC/COMMENT | <code>    The hard support operation is intended for sampling and evaluation. During</code> |
| 79 | DOC/COMMENT | <code>    training, support logits require a supervised or relaxed discrete objective;</code> |
| 80 | DOC/COMMENT | <code>    this decoder alone does not provide gradients through the selected indices.</code> |
| 81 | DOC/COMMENT | <code>    """</code> |
| 82 | STATIC+EXECUTED | <code>    if threshold_gev &lt; 0:</code> |
| 83 | STATIC+EXECUTED | <code>        raise ValueError("threshold_gev must be nonnegative")</code> |
| 84 | STATIC+EXECUTED | <code>    if support_logits.ndim != 2:</code> |
| 85 | STATIC+EXECUTED | <code>        raise ValueError("support_logits must have shape [batch,nodes]")</code> |
| 86 | STATIC+EXECUTED | <code>    batch, n_nodes = support_logits.shape</code> |
| 87 | STATIC+EXECUTED | <code>    if share_logits.shape != (batch, n_nodes):</code> |
| 88 | STATIC+EXECUTED | <code>        raise ValueError("share_logits shape mismatch")</code> |
| 89 | STATIC+EXECUTED | <code>    if layer_index.shape != (n_nodes,) or valid_mask.shape != (n_nodes,):</code> |
| 90 | STATIC+EXECUTED | <code>        raise ValueError("layer_index and valid_mask must have shape [nodes]")</code> |
| 91 | STATIC+EXECUTED | <code>    if layer_budget.shape != requested_counts.shape:</code> |
| 92 | STATIC+EXECUTED | <code>        raise ValueError("layer_budget and requested_counts must have the same shape")</code> |
| 94 | STATIC+EXECUTED | <code>    n_layers = layer_budget.shape[1]</code> |
| 95 | STATIC+EXECUTED | <code>    cell = torch.zeros_like(share_logits)</code> |
| 96 | STATIC+EXECUTED | <code>    support = torch.zeros_like(support_logits, dtype=torch.bool)</code> |
| 97 | STATIC+EXECUTED | <code>    resolved = torch.zeros_like(layer_budget)</code> |
| 98 | STATIC+EXECUTED | <code>    residual = torch.zeros_like(layer_budget)</code> |
| 99 | STATIC+EXECUTED | <code>    realized_counts = torch.zeros_like(requested_counts)</code> |
| 101 | STATIC+EXECUTED | <code>    for layer in range(n_layers):</code> |
| 102 | STATIC+EXECUTED | <code>        ids = torch.where((layer_index == layer) &amp; valid_mask)[0]</code> |
| 103 | STATIC+EXECUTED | <code>        budget = layer_budget[:, layer]</code> |
| 104 | STATIC+EXECUTED | <code>        requested = requested_counts[:, layer].long().clamp_min(0)</code> |
| 105 | STATIC+EXECUTED | <code>        if ids.numel() == 0:</code> |
| 106 | STATIC+EXECUTED | <code>            residual[:, layer] = budget</code> |
| 107 | STATIC+EXECUTED | <code>            continue</code> |
| 109 | STATIC+EXECUTED | <code>        if threshold_gev &gt; 0:</code> |
| 110 | STATIC+EXECUTED | <code>            feasible_by_budget = torch.floor(budget / threshold_gev).long()</code> |
| 111 | STATIC+MANUAL | <code>        else:</code> |
| 112 | STATIC+EXECUTED | <code>            feasible_by_budget = torch.where(</code> |
| 113 | STATIC+MANUAL | <code>                budget &gt; 0,</code> |
| 114 | STATIC+MANUAL | <code>                torch.full_like(requested, ids.numel()),</code> |
| 115 | STATIC+MANUAL | <code>                torch.zeros_like(requested),</code> |
| 116 | STATIC+MANUAL | <code>            )</code> |
| 117 | STATIC+EXECUTED | <code>        k = torch.minimum(requested, feasible_by_budget)</code> |
| 118 | STATIC+EXECUTED | <code>        k = torch.minimum(k, torch.full_like(k, ids.numel())).clamp_min(0)</code> |
| 120 | STATIC+EXECUTED | <code>        local_support = _batched_exact_k_mask(</code> |
| 121 | STATIC+MANUAL | <code>            support_logits[:, ids], k, stochastic=stochastic_support</code> |
| 122 | STATIC+MANUAL | <code>        )</code> |
| 123 | STATIC+EXECUTED | <code>        support[:, ids] = local_support</code> |
| 124 | STATIC+EXECUTED | <code>        realized_counts[:, layer] = k</code> |
| 126 | STATIC+EXECUTED | <code>        selected_share_logits = share_logits[:, ids]</code> |
| 127 | DOC/COMMENT | <code>        # Stable masked softmax that remains exactly zero when k=0.</code> |
| 128 | STATIC+EXECUTED | <code>        selected_for_max = torch.where(</code> |
| 129 | STATIC+MANUAL | <code>            local_support, selected_share_logits, torch.zeros_like(selected_share_logits)</code> |
| 130 | STATIC+MANUAL | <code>        )</code> |
| 131 | STATIC+EXECUTED | <code>        row_max = selected_for_max.max(dim=1, keepdim=True).values</code> |
| 132 | STATIC+EXECUTED | <code>        exponent = torch.exp(</code> |
| 133 | STATIC+MANUAL | <code>            torch.where(</code> |
| 134 | STATIC+MANUAL | <code>                local_support,</code> |
| 135 | STATIC+MANUAL | <code>                selected_share_logits - row_max,</code> |
| 136 | STATIC+MANUAL | <code>                torch.full_like(selected_share_logits, -torch.inf),</code> |
| 137 | STATIC+MANUAL | <code>            )</code> |
| 138 | STATIC+MANUAL | <code>        )</code> |
| 139 | STATIC+EXECUTED | <code>        shares = exponent / exponent.sum(dim=1, keepdim=True).clamp_min(1e-30)</code> |
| 141 | STATIC+EXECUTED | <code>        base = threshold_gev * k.to(budget.dtype)</code> |
| 142 | STATIC+EXECUTED | <code>        allocatable = (budget - base).clamp_min(0.0)</code> |
| 143 | STATIC+EXECUTED | <code>        values = local_support.to(budget.dtype) * (</code> |
| 144 | STATIC+MANUAL | <code>            threshold_gev + allocatable[:, None] * shares</code> |
| 145 | STATIC+MANUAL | <code>        )</code> |
| 146 | STATIC+EXECUTED | <code>        cell[:, ids] = values</code> |
| 147 | STATIC+EXECUTED | <code>        resolved[:, layer] = values.sum(dim=1)</code> |
| 148 | STATIC+EXECUTED | <code>        residual[:, layer] = budget - resolved[:, layer]</code> |
| 150 | STATIC+EXECUTED | <code>    return DecodeOutput(</code> |
| 151 | STATIC+MANUAL | <code>        cell_energy=cell,</code> |
| 152 | STATIC+MANUAL | <code>        resolved_layer_energy=resolved,</code> |
| 153 | STATIC+MANUAL | <code>        subthreshold_residual=residual,</code> |
| 154 | STATIC+MANUAL | <code>        realized_counts=realized_counts,</code> |
| 155 | STATIC+MANUAL | <code>        support_mask=support,</code> |
| 156 | STATIC+MANUAL | <code>    )</code> |

## `src/cbsc_zdc/models/system.py`

- SHA-256: `54a56ce74bb79b0638967c26c9e7e76c78766957cea31f83058158e5a494d431`
- Physical lines: 180; nonblank lines listed below: 169.

| Line | Audit | Source |
|---:|---|---|
| 1 | STATIC+EXECUTED | <code>from __future__ import annotations</code> |
| 3 | STATIC+EXECUTED | <code>from dataclasses import dataclass</code> |
| 5 | STATIC+EXECUTED | <code>import torch</code> |
| 6 | STATIC+EXECUTED | <code>from torch import nn</code> |
| 8 | STATIC+EXECUTED | <code>from ..features import p4_features</code> |
| 9 | STATIC+EXECUTED | <code>from .blocks import ConditionEncoder</code> |
| 10 | STATIC+EXECUTED | <code>from .counts import LayerCountHead</code> |
| 11 | STATIC+EXECUTED | <code>from .profile import LongitudinalProfileModel</code> |
| 12 | STATIC+EXECUTED | <code>from .spatial import ParallelCausalSpatialField</code> |
| 13 | STATIC+EXECUTED | <code>from .support import DecodeOutput, threshold_safe_layer_decoder</code> |
| 16 | STATIC+EXECUTED | <code>@dataclass</code> |
| 17 | STATIC+EXECUTED | <code>class CBSCOutput:</code> |
| 18 | STATIC+EXECUTED | <code>    cell_energy: torch.Tensor</code> |
| 19 | STATIC+EXECUTED | <code>    total: torch.Tensor</code> |
| 20 | STATIC+EXECUTED | <code>    layer_energy: torch.Tensor</code> |
| 21 | STATIC+EXECUTED | <code>    reserve: torch.Tensor</code> |
| 22 | STATIC+EXECUTED | <code>    subthreshold_residual: torch.Tensor</code> |
| 23 | STATIC+EXECUTED | <code>    requested_counts: torch.Tensor</code> |
| 24 | STATIC+EXECUTED | <code>    realized_counts: torch.Tensor</code> |
| 25 | STATIC+EXECUTED | <code>    support_mask: torch.Tensor</code> |
| 26 | STATIC+EXECUTED | <code>    first_visible_layer: torch.Tensor</code> |
| 27 | STATIC+EXECUTED | <code>    active_layers: torch.Tensor</code> |
| 30 | STATIC+EXECUTED | <code>class CBSCZDC(nn.Module):</code> |
| 31 | DOC/COMMENT | <code>    """Reference sampler for the revised CBSC-ZDC factorization.</code> |
| 33 | DOC/COMMENT | <code>    This class is an executable architecture scaffold. It is not a trained simulator and</code> |
| 34 | DOC/COMMENT | <code>    does not implement the complete Vertex training pipeline by itself.</code> |
| 35 | DOC/COMMENT | <code>    """</code> |
| 37 | STATIC+EXECUTED | <code>    def __init__(</code> |
| 38 | STATIC+MANUAL | <code>        self,</code> |
| 39 | STATIC+MANUAL | <code>        node_features: torch.Tensor,</code> |
| 40 | STATIC+MANUAL | <code>        layer_index: torch.Tensor,</code> |
| 41 | STATIC+MANUAL | <code>        valid_mask: torch.Tensor,</code> |
| 42 | STATIC+MANUAL | <code>        edge_index: torch.Tensor &#124; None = None,</code> |
| 43 | STATIC+MANUAL | <code>        edge_features: torch.Tensor &#124; None = None,</code> |
| 44 | STATIC+MANUAL | <code>        cond_dim: int = 128,</code> |
| 45 | STATIC+MANUAL | <code>        latent_dim: int = 32,</code> |
| 46 | STATIC+MANUAL | <code>        threshold_gev: float = 0.0,</code> |
| 47 | STATIC+MANUAL | <code>    ):</code> |
| 48 | STATIC+EXECUTED | <code>        super().__init__()</code> |
| 49 | STATIC+EXECUTED | <code>        if threshold_gev &lt; 0:</code> |
| 50 | STATIC+EXECUTED | <code>            raise ValueError("threshold_gev must be nonnegative")</code> |
| 51 | STATIC+EXECUTED | <code>        if node_features.ndim != 2:</code> |
| 52 | STATIC+EXECUTED | <code>            raise ValueError("node_features must have shape [nodes,features]")</code> |
| 53 | STATIC+EXECUTED | <code>        n_nodes = node_features.shape[0]</code> |
| 54 | STATIC+EXECUTED | <code>        if layer_index.shape != (n_nodes,) or valid_mask.shape != (n_nodes,):</code> |
| 55 | STATIC+EXECUTED | <code>            raise ValueError("layer_index and valid_mask must have shape [nodes]")</code> |
| 56 | STATIC+EXECUTED | <code>        if (layer_index &lt; 0).any():</code> |
| 57 | STATIC+EXECUTED | <code>            raise ValueError("layer_index must be nonnegative")</code> |
| 58 | STATIC+EXECUTED | <code>        if not valid_mask.any():</code> |
| 59 | STATIC+EXECUTED | <code>            raise ValueError("the detector must contain at least one valid node")</code> |
| 60 | STATIC+EXECUTED | <code>        self.threshold_gev = float(threshold_gev)</code> |
| 61 | STATIC+EXECUTED | <code>        self.register_buffer("node_features", node_features.float())</code> |
| 62 | STATIC+EXECUTED | <code>        self.register_buffer("layer_index", layer_index.long())</code> |
| 63 | STATIC+EXECUTED | <code>        self.register_buffer("valid_mask", valid_mask.bool())</code> |
| 64 | STATIC+EXECUTED | <code>        if (edge_index is None) != (edge_features is None):</code> |
| 65 | STATIC+EXECUTED | <code>            raise ValueError("edge_index and edge_features must be supplied together")</code> |
| 66 | STATIC+EXECUTED | <code>        if edge_index is None:</code> |
| 67 | STATIC+EXECUTED | <code>            edge_index = torch.empty(2, 0, dtype=torch.long)</code> |
| 68 | STATIC+EXECUTED | <code>            edge_features = torch.empty(0, 4, dtype=torch.float32)</code> |
| 69 | STATIC+EXECUTED | <code>        self.register_buffer("edge_index", edge_index.long())</code> |
| 70 | STATIC+EXECUTED | <code>        self.register_buffer("edge_features", edge_features.float())</code> |
| 71 | STATIC+EXECUTED | <code>        n_layers = int(layer_index.max().item()) + 1</code> |
| 72 | STATIC+EXECUTED | <code>        self.n_layers = n_layers</code> |
| 73 | STATIC+EXECUTED | <code>        max_counts = [</code> |
| 74 | STATIC+MANUAL | <code>            int(((layer_index == layer) &amp; valid_mask).sum().item())</code> |
| 75 | STATIC+MANUAL | <code>            for layer in range(n_layers)</code> |
| 76 | STATIC+MANUAL | <code>        ]</code> |
| 77 | STATIC+EXECUTED | <code>        if any(count &lt;= 0 for count in max_counts):</code> |
| 78 | STATIC+EXECUTED | <code>            raise ValueError("every modeled layer must contain at least one valid node")</code> |
| 79 | STATIC+EXECUTED | <code>        self.register_buffer("max_counts", torch.tensor(max_counts, dtype=torch.long))</code> |
| 80 | STATIC+EXECUTED | <code>        self.condition = ConditionEncoder(cond_dim)</code> |
| 81 | STATIC+EXECUTED | <code>        self.profile = LongitudinalProfileModel(</code> |
| 82 | STATIC+MANUAL | <code>            cond_dim=cond_dim, latent_dim=latent_dim, n_layers=n_layers</code> |
| 83 | STATIC+MANUAL | <code>        )</code> |
| 84 | STATIC+EXECUTED | <code>        self.counts = LayerCountHead(</code> |
| 85 | STATIC+MANUAL | <code>            cond_dim=cond_dim, n_layers=n_layers, max_counts=max_counts</code> |
| 86 | STATIC+MANUAL | <code>        )</code> |
| 87 | STATIC+EXECUTED | <code>        self.spatial = ParallelCausalSpatialField(</code> |
| 88 | STATIC+MANUAL | <code>            node_dim=node_features.shape[1],</code> |
| 89 | STATIC+MANUAL | <code>            edge_dim=edge_features.shape[1],</code> |
| 90 | STATIC+MANUAL | <code>            cond_dim=cond_dim,</code> |
| 91 | STATIC+MANUAL | <code>            n_layers=n_layers,</code> |
| 92 | STATIC+MANUAL | <code>        )</code> |
| 94 | STATIC+EXECUTED | <code>    @torch.no_grad()</code> |
| 95 | STATIC+EXECUTED | <code>    def sample(</code> |
| 96 | STATIC+MANUAL | <code>        self,</code> |
| 97 | STATIC+MANUAL | <code>        p4: torch.Tensor,</code> |
| 98 | STATIC+MANUAL | <code>        steps: int = 8,</code> |
| 99 | STATIC+MANUAL | <code>        seed: int &#124; None = None,</code> |
| 100 | STATIC+MANUAL | <code>        stochastic: bool = True,</code> |
| 101 | STATIC+MANUAL | <code>    ) -&gt; CBSCOutput:</code> |
| 102 | STATIC+EXECUTED | <code>        if steps &lt;= 0:</code> |
| 103 | STATIC+EXECUTED | <code>            raise ValueError("steps must be positive")</code> |
| 104 | STATIC+EXECUTED | <code>        devices = [p4.device] if p4.is_cuda else []</code> |
| 105 | STATIC+EXECUTED | <code>        with torch.random.fork_rng(devices=devices):</code> |
| 106 | STATIC+EXECUTED | <code>            if seed is not None:</code> |
| 107 | STATIC+EXECUTED | <code>                torch.manual_seed(seed)</code> |
| 108 | STATIC+EXECUTED | <code>            cond = self.condition(p4_features(p4))</code> |
| 109 | STATIC+EXECUTED | <code>            incident_e = p4[:, :1]</code> |
| 110 | STATIC+EXECUTED | <code>            profile = self.profile.sample(</code> |
| 111 | STATIC+MANUAL | <code>                incident_e, cond, stochastic=stochastic</code> |
| 112 | STATIC+MANUAL | <code>            )</code> |
| 113 | STATIC+EXECUTED | <code>            requested_counts, _ = self.counts.sample(</code> |
| 114 | STATIC+MANUAL | <code>                cond,</code> |
| 115 | STATIC+MANUAL | <code>                profile.layer_energy,</code> |
| 116 | STATIC+MANUAL | <code>                profile.active_layers,</code> |
| 117 | STATIC+MANUAL | <code>                threshold_gev=self.threshold_gev,</code> |
| 118 | STATIC+MANUAL | <code>                stochastic=stochastic,</code> |
| 119 | STATIC+MANUAL | <code>            )</code> |
| 120 | STATIC+EXECUTED | <code>            if stochastic:</code> |
| 121 | STATIC+EXECUTED | <code>                state = torch.randn(</code> |
| 122 | STATIC+MANUAL | <code>                    p4.shape[0],</code> |
| 123 | STATIC+MANUAL | <code>                    self.node_features.shape[0],</code> |
| 124 | STATIC+MANUAL | <code>                    2,</code> |
| 125 | STATIC+MANUAL | <code>                    device=p4.device,</code> |
| 126 | STATIC+MANUAL | <code>                    dtype=p4.dtype,</code> |
| 127 | STATIC+MANUAL | <code>                )</code> |
| 128 | STATIC+MANUAL | <code>            else:</code> |
| 129 | STATIC+EXECUTED | <code>                state = torch.zeros(</code> |
| 130 | STATIC+MANUAL | <code>                    p4.shape[0],</code> |
| 131 | STATIC+MANUAL | <code>                    self.node_features.shape[0],</code> |
| 132 | STATIC+MANUAL | <code>                    2,</code> |
| 133 | STATIC+MANUAL | <code>                    device=p4.device,</code> |
| 134 | STATIC+MANUAL | <code>                    dtype=p4.dtype,</code> |
| 135 | STATIC+MANUAL | <code>                )</code> |
| 136 | STATIC+EXECUTED | <code>            dt = 1.0 / steps</code> |
| 137 | STATIC+EXECUTED | <code>            for step in range(steps):</code> |
| 138 | STATIC+EXECUTED | <code>                t = torch.full(</code> |
| 139 | STATIC+MANUAL | <code>                    (p4.shape[0], 1),</code> |
| 140 | STATIC+MANUAL | <code>                    step / steps,</code> |
| 141 | STATIC+MANUAL | <code>                    device=p4.device,</code> |
| 142 | STATIC+MANUAL | <code>                    dtype=p4.dtype,</code> |
| 143 | STATIC+MANUAL | <code>                )</code> |
| 144 | STATIC+EXECUTED | <code>                velocity = self.spatial(</code> |
| 145 | STATIC+MANUAL | <code>                    state,</code> |
| 146 | STATIC+MANUAL | <code>                    t,</code> |
| 147 | STATIC+MANUAL | <code>                    cond,</code> |
| 148 | STATIC+MANUAL | <code>                    self.node_features,</code> |
| 149 | STATIC+MANUAL | <code>                    self.layer_index,</code> |
| 150 | STATIC+MANUAL | <code>                    profile.layer_energy,</code> |
| 151 | STATIC+MANUAL | <code>                    requested_counts,</code> |
| 152 | STATIC+MANUAL | <code>                    self.max_counts,</code> |
| 153 | STATIC+MANUAL | <code>                    self.valid_mask,</code> |
| 154 | STATIC+MANUAL | <code>                    self.edge_index,</code> |
| 155 | STATIC+MANUAL | <code>                    self.edge_features,</code> |
| 156 | STATIC+MANUAL | <code>                )</code> |
| 157 | STATIC+EXECUTED | <code>                state = state + dt * velocity</code> |
| 159 | STATIC+EXECUTED | <code>            decoded: DecodeOutput = threshold_safe_layer_decoder(</code> |
| 160 | STATIC+MANUAL | <code>                support_logits=state[..., 0],</code> |
| 161 | STATIC+MANUAL | <code>                share_logits=state[..., 1],</code> |
| 162 | STATIC+MANUAL | <code>                layer_budget=profile.layer_energy,</code> |
| 163 | STATIC+MANUAL | <code>                requested_counts=requested_counts,</code> |
| 164 | STATIC+MANUAL | <code>                layer_index=self.layer_index,</code> |
| 165 | STATIC+MANUAL | <code>                valid_mask=self.valid_mask,</code> |
| 166 | STATIC+MANUAL | <code>                threshold_gev=self.threshold_gev,</code> |
| 167 | STATIC+MANUAL | <code>                stochastic_support=stochastic,</code> |
| 168 | STATIC+MANUAL | <code>            )</code> |
| 169 | STATIC+EXECUTED | <code>            return CBSCOutput(</code> |
| 170 | STATIC+MANUAL | <code>                cell_energy=decoded.cell_energy,</code> |
| 171 | STATIC+MANUAL | <code>                total=profile.total,</code> |
| 172 | STATIC+MANUAL | <code>                layer_energy=profile.layer_energy,</code> |
| 173 | STATIC+MANUAL | <code>                reserve=profile.reserve,</code> |
| 174 | STATIC+MANUAL | <code>                subthreshold_residual=decoded.subthreshold_residual,</code> |
| 175 | STATIC+MANUAL | <code>                requested_counts=requested_counts,</code> |
| 176 | STATIC+MANUAL | <code>                realized_counts=decoded.realized_counts,</code> |
| 177 | STATIC+MANUAL | <code>                support_mask=decoded.support_mask,</code> |
| 178 | STATIC+MANUAL | <code>                first_visible_layer=profile.first_visible_layer,</code> |
| 179 | STATIC+MANUAL | <code>                active_layers=profile.active_layers,</code> |
| 180 | STATIC+MANUAL | <code>            )</code> |

## `src/cbsc_zdc/training/__init__.py`

- SHA-256: `6bc7348bb86180c0f86e0be3ad72bbd0ffa8cfeb1c579fc504247c188e5db4ac`
- Physical lines: 5; nonblank lines listed below: 3.

| Line | Audit | Source |
|---:|---|---|
| 1 | DOC/COMMENT | <code>"""Training utilities for CBSC-ZDC."""</code> |
| 3 | STATIC+EXECUTED | <code>from .flow_matching import flow_matching_mse, linear_flow_matching_batch</code> |
| 5 | STATIC+EXECUTED | <code>__all__ = ["linear_flow_matching_batch", "flow_matching_mse"]</code> |

## `src/cbsc_zdc/training/flow_matching.py`

- SHA-256: `ab4e9127d58fc4a813eb6e4c3108d2b975060acd57c777509a5b6bf690454375`
- Physical lines: 36; nonblank lines listed below: 30.

| Line | Audit | Source |
|---:|---|---|
| 1 | STATIC+EXECUTED | <code>from __future__ import annotations</code> |
| 3 | STATIC+EXECUTED | <code>import torch</code> |
| 6 | STATIC+EXECUTED | <code>def linear_flow_matching_batch(</code> |
| 7 | STATIC+MANUAL | <code>    target: torch.Tensor,</code> |
| 8 | STATIC+MANUAL | <code>    condition: torch.Tensor &#124; None = None,</code> |
| 9 | STATIC+MANUAL | <code>) -&gt; tuple[torch.Tensor, torch.Tensor, torch.Tensor]:</code> |
| 10 | DOC/COMMENT | <code>    """Construct a straight-line conditional flow-matching training tuple.</code> |
| 12 | DOC/COMMENT | <code>    x_0 ~ N(0, I), t ~ U(0, 1), x_t = (1-t)x_0 + t x_1,</code> |
| 13 | DOC/COMMENT | <code>    and the target velocity is u_t = x_1 - x_0.</code> |
| 14 | DOC/COMMENT | <code>    """</code> |
| 15 | DOC/COMMENT | <code>    del condition  # condition is consumed by the caller's vector field</code> |
| 16 | STATIC+EXECUTED | <code>    source = torch.randn_like(target)</code> |
| 17 | STATIC+EXECUTED | <code>    t_shape = (target.shape[0],) + (1,) * (target.ndim - 1)</code> |
| 18 | STATIC+EXECUTED | <code>    t = torch.rand(t_shape, device=target.device, dtype=target.dtype)</code> |
| 19 | STATIC+EXECUTED | <code>    x_t = (1.0 - t) * source + t * target</code> |
| 20 | STATIC+EXECUTED | <code>    velocity_target = target - source</code> |
| 21 | STATIC+EXECUTED | <code>    return x_t, t, velocity_target</code> |
| 24 | STATIC+EXECUTED | <code>def flow_matching_mse(</code> |
| 25 | STATIC+MANUAL | <code>    predicted_velocity: torch.Tensor,</code> |
| 26 | STATIC+MANUAL | <code>    target_velocity: torch.Tensor,</code> |
| 27 | STATIC+MANUAL | <code>    mask: torch.Tensor &#124; None = None,</code> |
| 28 | STATIC+MANUAL | <code>) -&gt; torch.Tensor:</code> |
| 29 | STATIC+EXECUTED | <code>    error = (predicted_velocity - target_velocity).square()</code> |
| 30 | STATIC+EXECUTED | <code>    if mask is not None:</code> |
| 31 | STATIC+EXECUTED | <code>        while mask.ndim &lt; error.ndim:</code> |
| 32 | STATIC+EXECUTED | <code>            mask = mask.unsqueeze(-1)</code> |
| 33 | STATIC+EXECUTED | <code>        error = error * mask</code> |
| 34 | STATIC+EXECUTED | <code>        denominator = mask.expand_as(error).sum().clamp_min(1)</code> |
| 35 | STATIC+EXECUTED | <code>        return error.sum() / denominator</code> |
| 36 | STATIC+EXECUTED | <code>    return error.mean()</code> |

## `src/cbsc_zdc/training/losses.py`

- SHA-256: `3633f7a1c515b33d6d1e6189426bd86c18e192833e98372350d4bc25f88bedc0`
- Physical lines: 63; nonblank lines listed below: 53.

| Line | Audit | Source |
|---:|---|---|
| 1 | STATIC+EXECUTED | <code>from __future__ import annotations</code> |
| 3 | STATIC+EXECUTED | <code>import torch</code> |
| 6 | STATIC+EXECUTED | <code>def dust_fraction(cell_energy: torch.Tensor, threshold_gev: float) -&gt; torch.Tensor:</code> |
| 7 | DOC/COMMENT | <code>    """Fraction of cells with forbidden 0 &lt; E &lt; threshold."""</code> |
| 8 | STATIC+EXECUTED | <code>    if threshold_gev &lt;= 0:</code> |
| 9 | STATIC+EXECUTED | <code>        return torch.zeros((), device=cell_energy.device, dtype=cell_energy.dtype)</code> |
| 10 | STATIC+EXECUTED | <code>    dust = (cell_energy &gt; 0) &amp; (cell_energy &lt; threshold_gev)</code> |
| 11 | STATIC+EXECUTED | <code>    return dust.float().mean()</code> |
| 14 | STATIC+EXECUTED | <code>def support_binary_cross_entropy(</code> |
| 15 | STATIC+MANUAL | <code>    logits: torch.Tensor,</code> |
| 16 | STATIC+MANUAL | <code>    truth_mask: torch.Tensor,</code> |
| 17 | STATIC+MANUAL | <code>    positive_weight: torch.Tensor &#124; None = None,</code> |
| 18 | STATIC+MANUAL | <code>) -&gt; torch.Tensor:</code> |
| 19 | STATIC+EXECUTED | <code>    return torch.nn.functional.binary_cross_entropy_with_logits(</code> |
| 20 | STATIC+MANUAL | <code>        logits,</code> |
| 21 | STATIC+MANUAL | <code>        truth_mask.to(logits.dtype),</code> |
| 22 | STATIC+MANUAL | <code>        pos_weight=positive_weight,</code> |
| 23 | STATIC+MANUAL | <code>    )</code> |
| 26 | STATIC+EXECUTED | <code>def count_cross_entropy(</code> |
| 27 | STATIC+MANUAL | <code>    count_logits: torch.Tensor,</code> |
| 28 | STATIC+MANUAL | <code>    truth_counts: torch.Tensor,</code> |
| 29 | STATIC+MANUAL | <code>) -&gt; torch.Tensor:</code> |
| 30 | STATIC+EXECUTED | <code>    return torch.nn.functional.cross_entropy(</code> |
| 31 | STATIC+MANUAL | <code>        count_logits.reshape(-1, count_logits.shape[-1]),</code> |
| 32 | STATIC+MANUAL | <code>        truth_counts.reshape(-1),</code> |
| 33 | STATIC+MANUAL | <code>    )</code> |
| 36 | STATIC+EXECUTED | <code>def positive_log_energy_loss(</code> |
| 37 | STATIC+MANUAL | <code>    generated: torch.Tensor,</code> |
| 38 | STATIC+MANUAL | <code>    truth: torch.Tensor,</code> |
| 39 | STATIC+MANUAL | <code>    generated_mask: torch.Tensor,</code> |
| 40 | STATIC+MANUAL | <code>    truth_mask: torch.Tensor,</code> |
| 41 | STATIC+MANUAL | <code>    eps: float = 1e-8,</code> |
| 42 | STATIC+MANUAL | <code>) -&gt; torch.Tensor:</code> |
| 43 | DOC/COMMENT | <code>    """Simple diagnostic loss on positive hit spectra.</code> |
| 45 | DOC/COMMENT | <code>    A production experiment should supplement this with distributional losses rather than</code> |
| 46 | DOC/COMMENT | <code>    relying on an eventwise matching of independent Geant4 showers.</code> |
| 47 | DOC/COMMENT | <code>    """</code> |
| 48 | STATIC+EXECUTED | <code>    g = torch.log(generated[generated_mask] + eps)</code> |
| 49 | STATIC+EXECUTED | <code>    t = torch.log(truth[truth_mask] + eps)</code> |
| 50 | STATIC+EXECUTED | <code>    if g.numel() == 0 or t.numel() == 0:</code> |
| 51 | STATIC+EXECUTED | <code>        return generated.new_zeros(())</code> |
| 52 | DOC/COMMENT | <code>    # Quantile matching avoids requiring one-to-one hit correspondence.  Evaluate both</code> |
| 53 | DOC/COMMENT | <code>    # samples on the same probability grid; truncating sorted arrays would bias the</code> |
| 54 | DOC/COMMENT | <code>    # comparison toward the lower tail when the sample sizes differ.</code> |
| 55 | STATIC+EXECUTED | <code>    n_quantiles = min(max(min(g.numel(), t.numel()), 2), 256)</code> |
| 56 | STATIC+EXECUTED | <code>    probability = torch.linspace(</code> |
| 57 | STATIC+MANUAL | <code>        0.0, 1.0, n_quantiles, device=generated.device, dtype=generated.dtype</code> |
| 58 | STATIC+MANUAL | <code>    )</code> |
| 59 | STATIC+EXECUTED | <code>    generated_quantiles = torch.quantile(g, probability)</code> |
| 60 | STATIC+EXECUTED | <code>    truth_quantiles = torch.quantile(t, probability)</code> |
| 61 | STATIC+EXECUTED | <code>    return torch.nn.functional.smooth_l1_loss(</code> |
| 62 | STATIC+MANUAL | <code>        generated_quantiles, truth_quantiles</code> |
| 63 | STATIC+MANUAL | <code>    )</code> |

## `tests/test_budget.py`

- SHA-256: `13b667bd19e9ac0e4ad55b55a5df96818e1cf96eb842e550af71fe8b26b9cdda`
- Physical lines: 45; nonblank lines listed below: 38.

| Line | Audit | Source |
|---:|---|---|
| 1 | STATIC+EXECUTED | <code>import torch</code> |
| 3 | STATIC+EXECUTED | <code>from cbsc_zdc.models.profile import LongitudinalProfileModel</code> |
| 6 | STATIC+EXECUTED | <code>def test_profile_identity_and_nonmonotone_deposits_allowed():</code> |
| 7 | STATIC+EXECUTED | <code>    torch.manual_seed(3)</code> |
| 8 | STATIC+EXECUTED | <code>    model = LongitudinalProfileModel(cond_dim=8, latent_dim=4, n_layers=5)</code> |
| 9 | STATIC+EXECUTED | <code>    cond = torch.randn(32, 8)</code> |
| 10 | STATIC+EXECUTED | <code>    incident = torch.full((32, 1), 100.0)</code> |
| 11 | STATIC+EXECUTED | <code>    out = model.sample(incident, cond, stochastic=True)</code> |
| 12 | STATIC+EXECUTED | <code>    assert torch.all(out.total &gt;= 0)</code> |
| 13 | STATIC+EXECUTED | <code>    assert torch.all(out.total &lt;= incident)</code> |
| 14 | STATIC+EXECUTED | <code>    assert torch.all(out.layer_energy &gt;= 0)</code> |
| 15 | STATIC+EXECUTED | <code>    assert torch.all(out.reserve &gt;= 0)</code> |
| 16 | STATIC+EXECUTED | <code>    assert torch.allclose(</code> |
| 17 | STATIC+MANUAL | <code>        out.layer_energy.sum(dim=-1, keepdim=True) + out.reserve,</code> |
| 18 | STATIC+MANUAL | <code>        out.total,</code> |
| 19 | STATIC+MANUAL | <code>        atol=1e-5,</code> |
| 20 | STATIC+MANUAL | <code>    )</code> |
| 21 | STATIC+EXECUTED | <code>    assert torch.all(out.layer_energy[out.active_layers == 0] == 0)</code> |
| 22 | STATIC+EXECUTED | <code>    assert out.layer_energy.shape == (32, 5)</code> |
| 25 | STATIC+EXECUTED | <code>def test_first_visible_layer_is_active_and_preceding_layers_are_inactive():</code> |
| 26 | STATIC+EXECUTED | <code>    torch.manual_seed(9)</code> |
| 27 | STATIC+EXECUTED | <code>    model = LongitudinalProfileModel(cond_dim=8, latent_dim=4, n_layers=7)</code> |
| 28 | STATIC+EXECUTED | <code>    cond = torch.randn(64, 8)</code> |
| 29 | STATIC+EXECUTED | <code>    incident = torch.full((64, 1), 80.0)</code> |
| 30 | STATIC+EXECUTED | <code>    out = model.sample(incident, cond, stochastic=True)</code> |
| 31 | STATIC+EXECUTED | <code>    visible_rows = out.visible.squeeze(-1) &gt; 0</code> |
| 32 | STATIC+EXECUTED | <code>    for event in torch.where(visible_rows)[0]:</code> |
| 33 | STATIC+EXECUTED | <code>        start = int(out.first_visible_layer[event].item())</code> |
| 34 | STATIC+EXECUTED | <code>        assert out.active_layers[event, start] == 1</code> |
| 35 | STATIC+EXECUTED | <code>        assert torch.all(out.active_layers[event, :start] == 0)</code> |
| 38 | STATIC+EXECUTED | <code>def test_profile_accepts_explicit_event_latent():</code> |
| 39 | STATIC+EXECUTED | <code>    torch.manual_seed(4)</code> |
| 40 | STATIC+EXECUTED | <code>    model = LongitudinalProfileModel(cond_dim=8, latent_dim=4, n_layers=5)</code> |
| 41 | STATIC+EXECUTED | <code>    cond = torch.randn(3, 8)</code> |
| 42 | STATIC+EXECUTED | <code>    incident = torch.full((3, 1), 60.0)</code> |
| 43 | STATIC+EXECUTED | <code>    z_event = torch.zeros(3, 4)</code> |
| 44 | STATIC+EXECUTED | <code>    out = model.sample(incident, cond, z_event=z_event, stochastic=False)</code> |
| 45 | STATIC+EXECUTED | <code>    assert out.layer_energy.shape == (3, 5)</code> |

## `tests/test_budget_compatibility.py`

- SHA-256: `568e268c904901b597997675995f40de94e3c201dd31d2eebb8f85b5ce67b287`
- Physical lines: 10; nonblank lines listed below: 8.

| Line | Audit | Source |
|---:|---|---|
| 1 | STATIC+EXECUTED | <code>from cbsc_zdc.models.budget import LongitudinalProfileModel, ProfileOutput</code> |
| 2 | STATIC+EXECUTED | <code>from cbsc_zdc.models.profile import (</code> |
| 3 | STATIC+MANUAL | <code>    LongitudinalProfileModel as CanonicalLongitudinalProfileModel,</code> |
| 4 | STATIC+MANUAL | <code>)</code> |
| 5 | STATIC+EXECUTED | <code>from cbsc_zdc.models.profile import ProfileOutput as CanonicalProfileOutput</code> |
| 8 | STATIC+EXECUTED | <code>def test_budget_module_reexports_revised_profile_types():</code> |
| 9 | STATIC+EXECUTED | <code>    assert LongitudinalProfileModel is CanonicalLongitudinalProfileModel</code> |
| 10 | STATIC+EXECUTED | <code>    assert ProfileOutput is CanonicalProfileOutput</code> |

## `tests/test_contracts.py`

- SHA-256: `de3b87fde2752e48c0fb757df43475876d9ba06dd6027783339fca97f9398773`
- Physical lines: 45; nonblank lines listed below: 35.

| Line | Audit | Source |
|---:|---|---|
| 1 | STATIC+EXECUTED | <code>import math</code> |
| 3 | STATIC+EXECUTED | <code>import pytest</code> |
| 4 | STATIC+EXECUTED | <code>import torch</code> |
| 6 | STATIC+EXECUTED | <code>from cbsc_zdc.contracts import mass_shell_diagnostics, validate_p4</code> |
| 7 | STATIC+EXECUTED | <code>from cbsc_zdc.features import p4_features</code> |
| 10 | STATIC+EXECUTED | <code>def neutron_p4(energy: float, dtype: torch.dtype = torch.float32) -&gt; torch.Tensor:</code> |
| 11 | STATIC+EXECUTED | <code>    mass = 0.93956542052</code> |
| 12 | STATIC+EXECUTED | <code>    momentum = math.sqrt(energy**2 - mass**2)</code> |
| 13 | STATIC+EXECUTED | <code>    return torch.tensor([[energy, 0.0, 0.0, momentum]], dtype=dtype)</code> |
| 16 | STATIC+EXECUTED | <code>def test_high_energy_float32_mass_shell_is_not_rejected_by_cancellation():</code> |
| 17 | STATIC+EXECUTED | <code>    for energy in (50.0, 100.0, 250.0, 300.0):</code> |
| 18 | STATIC+EXECUTED | <code>        p4 = neutron_p4(energy)</code> |
| 19 | STATIC+EXECUTED | <code>        validate_p4(p4)</code> |
| 20 | STATIC+EXECUTED | <code>        diagnostics = mass_shell_diagnostics(p4)</code> |
| 21 | STATIC+EXECUTED | <code>        assert diagnostics["relative_energy_residual"].item() &lt; 1e-6</code> |
| 22 | STATIC+EXECUTED | <code>        features = p4_features(p4)</code> |
| 23 | STATIC+EXECUTED | <code>        assert features.shape == (1, 4)</code> |
| 24 | STATIC+EXECUTED | <code>        assert torch.isfinite(features).all()</code> |
| 27 | STATIC+EXECUTED | <code>def test_malformed_four_vector_is_rejected():</code> |
| 28 | STATIC+EXECUTED | <code>    malformed = torch.tensor([[100.0, 0.0, 0.0, 90.0]])</code> |
| 29 | STATIC+EXECUTED | <code>    with pytest.raises(ValueError, match="mass-shell"):</code> |
| 30 | STATIC+EXECUTED | <code>        validate_p4(malformed)</code> |
| 33 | STATIC+EXECUTED | <code>def test_p4_validation_error_paths_and_feature_scale():</code> |
| 34 | STATIC+EXECUTED | <code>    with pytest.raises(ValueError, match="shape"):</code> |
| 35 | STATIC+EXECUTED | <code>        validate_p4(torch.zeros(4))</code> |
| 36 | STATIC+EXECUTED | <code>    with pytest.raises(ValueError, match="floating-point"):</code> |
| 37 | STATIC+EXECUTED | <code>        validate_p4(torch.tensor([[1, 0, 0, 0]]))</code> |
| 38 | STATIC+EXECUTED | <code>    with pytest.raises(ValueError, match="NaN/Inf"):</code> |
| 39 | STATIC+EXECUTED | <code>        validate_p4(torch.tensor([[float("nan"), 0.0, 0.0, 0.0]]))</code> |
| 40 | STATIC+EXECUTED | <code>    with pytest.raises(ValueError, match="positive"):</code> |
| 41 | STATIC+EXECUTED | <code>        validate_p4(torch.tensor([[0.0, 0.0, 0.0, 0.0]]))</code> |
| 42 | STATIC+EXECUTED | <code>    with pytest.raises(ValueError, match="shape"):</code> |
| 43 | STATIC+EXECUTED | <code>        mass_shell_diagnostics(torch.zeros(4))</code> |
| 44 | STATIC+EXECUTED | <code>    with pytest.raises(ValueError, match="energy_scale"):</code> |
| 45 | STATIC+EXECUTED | <code>        p4_features(neutron_p4(50.0), energy_scale_gev=0.0)</code> |

## `tests/test_counts.py`

- SHA-256: `60aa291165da45ff76e81a41418c276b440044824d65632284a4f17fffe37c8f`
- Physical lines: 26; nonblank lines listed below: 23.

| Line | Audit | Source |
|---:|---|---|
| 1 | STATIC+EXECUTED | <code>import pytest</code> |
| 2 | STATIC+EXECUTED | <code>import torch</code> |
| 4 | STATIC+EXECUTED | <code>from cbsc_zdc.models.counts import LayerCountHead</code> |
| 7 | STATIC+EXECUTED | <code>def test_count_head_masks_geometry_threshold_and_activity():</code> |
| 8 | STATIC+EXECUTED | <code>    with pytest.raises(ValueError, match="length"):</code> |
| 9 | STATIC+EXECUTED | <code>        LayerCountHead(cond_dim=4, n_layers=2, max_counts=[3])</code> |
| 10 | STATIC+EXECUTED | <code>    head = LayerCountHead(cond_dim=4, n_layers=2, max_counts=[3, 2], hidden=8)</code> |
| 11 | STATIC+EXECUTED | <code>    cond = torch.zeros(1, 4)</code> |
| 12 | STATIC+EXECUTED | <code>    energy = torch.tensor([[0.025, 0.0]])</code> |
| 13 | STATIC+EXECUTED | <code>    active = torch.tensor([[1.0, 0.0]])</code> |
| 14 | STATIC+EXECUTED | <code>    logits = head.logits(cond, energy, active, threshold_gev=0.01)</code> |
| 15 | STATIC+EXECUTED | <code>    finite = torch.isfinite(logits) &amp; (logits &gt; torch.finfo(logits.dtype).min / 2)</code> |
| 16 | STATIC+EXECUTED | <code>    assert not finite[0, 0, 0]</code> |
| 17 | STATIC+EXECUTED | <code>    assert finite[0, 0, 1]</code> |
| 18 | STATIC+EXECUTED | <code>    assert finite[0, 0, 2]</code> |
| 19 | STATIC+EXECUTED | <code>    assert not finite[0, 0, 3]</code> |
| 20 | STATIC+EXECUTED | <code>    assert finite[0, 1, 0]</code> |
| 21 | STATIC+EXECUTED | <code>    assert not finite[0, 1, 1:].any()</code> |
| 22 | STATIC+EXECUTED | <code>    deterministic, _ = head.sample(cond, energy, active, threshold_gev=0.01, stochastic=False)</code> |
| 23 | STATIC+EXECUTED | <code>    stochastic, _ = head.sample(cond, energy, active, threshold_gev=0.01, stochastic=True)</code> |
| 24 | STATIC+EXECUTED | <code>    assert deterministic.shape == stochastic.shape == (1, 2)</code> |
| 25 | STATIC+EXECUTED | <code>    with pytest.raises(ValueError, match="layer dimension"):</code> |
| 26 | STATIC+EXECUTED | <code>        head.logits(cond, torch.zeros(1, 3), torch.zeros(1, 3))</code> |

## `tests/test_flow_matching.py`

- SHA-256: `2fa3d5fa9aa9190eea2aa03bd40f9967b80877e14f3868dddb0fee73d759d439`
- Physical lines: 30; nonblank lines listed below: 25.

| Line | Audit | Source |
|---:|---|---|
| 1 | STATIC+EXECUTED | <code>import torch</code> |
| 3 | STATIC+EXECUTED | <code>from cbsc_zdc.training.flow_matching import (</code> |
| 4 | STATIC+MANUAL | <code>    flow_matching_mse,</code> |
| 5 | STATIC+MANUAL | <code>    linear_flow_matching_batch,</code> |
| 6 | STATIC+MANUAL | <code>)</code> |
| 9 | STATIC+EXECUTED | <code>def test_linear_flow_matching_tuple_identity_and_condition_passthrough_contract():</code> |
| 10 | STATIC+EXECUTED | <code>    torch.manual_seed(11)</code> |
| 11 | STATIC+EXECUTED | <code>    target = torch.randn(4, 3, 2)</code> |
| 12 | STATIC+EXECUTED | <code>    condition = torch.randn(4, 5)</code> |
| 13 | STATIC+EXECUTED | <code>    x_t, t, velocity = linear_flow_matching_batch(target, condition)</code> |
| 14 | STATIC+EXECUTED | <code>    source = target - velocity</code> |
| 15 | STATIC+EXECUTED | <code>    assert x_t.shape == target.shape</code> |
| 16 | STATIC+EXECUTED | <code>    assert t.shape == (4, 1, 1)</code> |
| 17 | STATIC+EXECUTED | <code>    assert torch.all((t &gt;= 0) &amp; (t &lt; 1))</code> |
| 18 | STATIC+EXECUTED | <code>    assert torch.allclose(x_t, (1 - t) * source + t * target)</code> |
| 19 | STATIC+EXECUTED | <code>    assert torch.allclose(velocity, target - source)</code> |
| 22 | STATIC+EXECUTED | <code>def test_flow_matching_mse_masked_and_unmasked():</code> |
| 23 | STATIC+EXECUTED | <code>    predicted = torch.tensor([[[1.0], [4.0]], [[2.0], [8.0]]])</code> |
| 24 | STATIC+EXECUTED | <code>    target = torch.zeros_like(predicted)</code> |
| 25 | STATIC+EXECUTED | <code>    assert torch.allclose(flow_matching_mse(predicted, target), predicted.square().mean())</code> |
| 26 | STATIC+EXECUTED | <code>    mask = torch.tensor([[1.0, 0.0], [1.0, 0.0]])</code> |
| 27 | STATIC+EXECUTED | <code>    expected = torch.tensor((1.0**2 + 2.0**2) / 2.0)</code> |
| 28 | STATIC+EXECUTED | <code>    assert torch.allclose(flow_matching_mse(predicted, target, mask), expected)</code> |
| 29 | STATIC+EXECUTED | <code>    zero_mask = torch.zeros_like(mask)</code> |
| 30 | STATIC+EXECUTED | <code>    assert flow_matching_mse(predicted, target, zero_mask).item() == 0.0</code> |

## `tests/test_graph.py`

- SHA-256: `83d6e3bef0b24c7f037a775ea26de7e0495f35bde58360ed6644d3cafa1919db`
- Physical lines: 36; nonblank lines listed below: 30.

| Line | Audit | Source |
|---:|---|---|
| 1 | STATIC+EXECUTED | <code>import pytest</code> |
| 2 | STATIC+EXECUTED | <code>import torch</code> |
| 4 | STATIC+EXECUTED | <code>from cbsc_zdc.models.graph import EdgeMessageBlock</code> |
| 7 | STATIC+EXECUTED | <code>def test_edge_message_block_changes_destination_and_rejects_invalid_edges():</code> |
| 8 | STATIC+EXECUTED | <code>    torch.manual_seed(2)</code> |
| 9 | STATIC+EXECUTED | <code>    block = EdgeMessageBlock(hidden=8, edge_dim=3, edge_chunk_size=1).eval()</code> |
| 10 | STATIC+EXECUTED | <code>    h = torch.randn(2, 3, 8)</code> |
| 11 | STATIC+EXECUTED | <code>    edge_index = torch.tensor([[0, 1], [1, 2]])</code> |
| 12 | STATIC+EXECUTED | <code>    edge_features = torch.randn(2, 3)</code> |
| 13 | STATIC+EXECUTED | <code>    with torch.no_grad():</code> |
| 14 | STATIC+EXECUTED | <code>        out = block(h, edge_index, edge_features)</code> |
| 15 | STATIC+EXECUTED | <code>    assert out.shape == h.shape</code> |
| 16 | STATIC+EXECUTED | <code>    assert not torch.allclose(out, h)</code> |
| 18 | STATIC+EXECUTED | <code>    bad = torch.tensor([[0], [3]])</code> |
| 19 | STATIC+EXECUTED | <code>    with pytest.raises(ValueError, match="invalid node id"):</code> |
| 20 | STATIC+EXECUTED | <code>        block(h, bad, torch.randn(1, 3))</code> |
| 23 | STATIC+EXECUTED | <code>def test_edge_message_block_rejects_bad_shapes():</code> |
| 24 | STATIC+EXECUTED | <code>    block = EdgeMessageBlock(hidden=8, edge_dim=3)</code> |
| 25 | STATIC+EXECUTED | <code>    h = torch.randn(1, 3, 8)</code> |
| 26 | STATIC+EXECUTED | <code>    with torch.no_grad():</code> |
| 27 | STATIC+EXECUTED | <code>        empty_out = block(</code> |
| 28 | STATIC+MANUAL | <code>            h,</code> |
| 29 | STATIC+MANUAL | <code>            torch.empty(2, 0, dtype=torch.long),</code> |
| 30 | STATIC+MANUAL | <code>            torch.empty(0, 3),</code> |
| 31 | STATIC+MANUAL | <code>        )</code> |
| 32 | STATIC+EXECUTED | <code>    assert empty_out.shape == h.shape</code> |
| 33 | STATIC+EXECUTED | <code>    with pytest.raises(ValueError, match="shape"):</code> |
| 34 | STATIC+EXECUTED | <code>        block(h, torch.tensor([0, 1]), torch.randn(1, 3))</code> |
| 35 | STATIC+EXECUTED | <code>    with pytest.raises(ValueError, match="feature"):</code> |
| 36 | STATIC+EXECUTED | <code>        block(h, torch.tensor([[0], [1]]), torch.randn(1, 2))</code> |

## `tests/test_losses.py`

- SHA-256: `7c738547dc279e750c1e2f0075c50a9edd336947068b15fa56645f39dce3c6c8`
- Physical lines: 42; nonblank lines listed below: 36.

| Line | Audit | Source |
|---:|---|---|
| 1 | STATIC+EXECUTED | <code>import torch</code> |
| 3 | STATIC+EXECUTED | <code>from cbsc_zdc.training.losses import positive_log_energy_loss</code> |
| 6 | STATIC+EXECUTED | <code>def test_positive_spectrum_loss_uses_common_quantiles_for_unequal_counts():</code> |
| 7 | STATIC+EXECUTED | <code>    generated = torch.tensor([[1.0, 2.0, 3.0, 4.0]])</code> |
| 8 | STATIC+EXECUTED | <code>    truth = torch.tensor([[1.0, 4.0]])</code> |
| 9 | STATIC+EXECUTED | <code>    generated_mask = torch.ones_like(generated, dtype=torch.bool)</code> |
| 10 | STATIC+EXECUTED | <code>    truth_mask = torch.ones_like(truth, dtype=torch.bool)</code> |
| 11 | STATIC+EXECUTED | <code>    loss = positive_log_energy_loss(</code> |
| 12 | STATIC+MANUAL | <code>        generated, truth, generated_mask, truth_mask</code> |
| 13 | STATIC+MANUAL | <code>    )</code> |
| 14 | STATIC+EXECUTED | <code>    assert torch.isfinite(loss)</code> |
| 15 | STATIC+EXECUTED | <code>    assert loss &gt;= 0</code> |
| 18 | STATIC+EXECUTED | <code>def test_loss_helpers_and_empty_positive_spectrum():</code> |
| 19 | STATIC+EXECUTED | <code>    from cbsc_zdc.training.losses import (</code> |
| 20 | STATIC+MANUAL | <code>        count_cross_entropy,</code> |
| 21 | STATIC+MANUAL | <code>        dust_fraction,</code> |
| 22 | STATIC+MANUAL | <code>        support_binary_cross_entropy,</code> |
| 23 | STATIC+MANUAL | <code>    )</code> |
| 25 | STATIC+EXECUTED | <code>    cell = torch.tensor([[0.0, 0.005, 0.02]])</code> |
| 26 | STATIC+EXECUTED | <code>    assert dust_fraction(cell, 0.0).item() == 0.0</code> |
| 27 | STATIC+EXECUTED | <code>    assert torch.isclose(dust_fraction(cell, 0.01), torch.tensor(1.0 / 3.0))</code> |
| 28 | STATIC+EXECUTED | <code>    support_loss = support_binary_cross_entropy(</code> |
| 29 | STATIC+MANUAL | <code>        torch.tensor([[0.0, 1.0]]), torch.tensor([[False, True]])</code> |
| 30 | STATIC+MANUAL | <code>    )</code> |
| 31 | STATIC+EXECUTED | <code>    assert torch.isfinite(support_loss)</code> |
| 32 | STATIC+EXECUTED | <code>    count_loss = count_cross_entropy(</code> |
| 33 | STATIC+MANUAL | <code>        torch.tensor([[[2.0, 0.0], [0.0, 2.0]]]), torch.tensor([[0, 1]])</code> |
| 34 | STATIC+MANUAL | <code>    )</code> |
| 35 | STATIC+EXECUTED | <code>    assert torch.isfinite(count_loss)</code> |
| 36 | STATIC+EXECUTED | <code>    empty = positive_log_energy_loss(</code> |
| 37 | STATIC+MANUAL | <code>        torch.zeros(1, 2),</code> |
| 38 | STATIC+MANUAL | <code>        torch.zeros(1, 2),</code> |
| 39 | STATIC+MANUAL | <code>        torch.zeros(1, 2, dtype=torch.bool),</code> |
| 40 | STATIC+MANUAL | <code>        torch.zeros(1, 2, dtype=torch.bool),</code> |
| 41 | STATIC+MANUAL | <code>    )</code> |
| 42 | STATIC+EXECUTED | <code>    assert empty.item() == 0.0</code> |

## `tests/test_root_adapter.py`

- SHA-256: `fa9784a6f468ecc38a01643519011f584c7afe0f4047eeb8075c98687cad247b`
- Physical lines: 45; nonblank lines listed below: 32.

| Line | Audit | Source |
|---:|---|---|
| 1 | STATIC+EXECUTED | <code>import builtins</code> |
| 2 | STATIC+EXECUTED | <code>import sys</code> |
| 3 | STATIC+EXECUTED | <code>from types import SimpleNamespace</code> |
| 5 | STATIC+EXECUTED | <code>import pytest</code> |
| 7 | STATIC+EXECUTED | <code>from cbsc_zdc.data.root_adapter import BranchMap, inspect_root</code> |
| 10 | STATIC+EXECUTED | <code>def test_branch_map_is_frozen_and_complete():</code> |
| 11 | STATIC+EXECUTED | <code>    branches = BranchMap("e", "px", "py", "pz", "eid", "ee", "hid", "hl", "he")</code> |
| 12 | STATIC+EXECUTED | <code>    assert branches.hcal_energy == "he"</code> |
| 13 | STATIC+EXECUTED | <code>    with pytest.raises(Exception):</code> |
| 14 | STATIC+EXECUTED | <code>        branches.e = "changed"</code> |
| 17 | STATIC+EXECUTED | <code>def test_inspect_root_reports_missing_optional_dependency(monkeypatch, tmp_path):</code> |
| 18 | STATIC+EXECUTED | <code>    original_import = builtins.__import__</code> |
| 20 | STATIC+EXECUTED | <code>    def guarded_import(name, *args, **kwargs):</code> |
| 21 | STATIC+EXECUTED | <code>        if name == "uproot":</code> |
| 22 | STATIC+EXECUTED | <code>            raise ImportError("simulated missing uproot")</code> |
| 23 | STATIC+EXECUTED | <code>        return original_import(name, *args, **kwargs)</code> |
| 25 | STATIC+EXECUTED | <code>    monkeypatch.setattr(builtins, "__import__", guarded_import)</code> |
| 26 | STATIC+EXECUTED | <code>    monkeypatch.delitem(sys.modules, "uproot", raising=False)</code> |
| 27 | STATIC+EXECUTED | <code>    with pytest.raises(RuntimeError, match="Install uproot/awkward"):</code> |
| 28 | STATIC+EXECUTED | <code>        inspect_root(tmp_path / "missing.root")</code> |
| 31 | STATIC+EXECUTED | <code>def test_inspect_root_uses_uproot_and_returns_classnames(monkeypatch, tmp_path):</code> |
| 32 | STATIC+EXECUTED | <code>    class FakeRootFile:</code> |
| 33 | STATIC+EXECUTED | <code>        def items(self):</code> |
| 34 | STATIC+EXECUTED | <code>            return [("myTree;1", SimpleNamespace(classname="TTree"))]</code> |
| 36 | STATIC+EXECUTED | <code>    opened = []</code> |
| 38 | STATIC+EXECUTED | <code>    def fake_open(path):</code> |
| 39 | STATIC+EXECUTED | <code>        opened.append(path)</code> |
| 40 | STATIC+EXECUTED | <code>        return FakeRootFile()</code> |
| 42 | STATIC+EXECUTED | <code>    monkeypatch.setitem(sys.modules, "uproot", SimpleNamespace(open=fake_open))</code> |
| 43 | STATIC+EXECUTED | <code>    path = tmp_path / "sample.root"</code> |
| 44 | STATIC+EXECUTED | <code>    assert inspect_root(path) == {"myTree;1": "TTree"}</code> |
| 45 | STATIC+EXECUTED | <code>    assert opened == [path]</code> |

## `tests/test_spatial_time.py`

- SHA-256: `3e63643d0ec5e24443875e384643d73b1631ddf72545803341e4db9f08ef89d2`
- Physical lines: 71; nonblank lines listed below: 63.

| Line | Audit | Source |
|---:|---|---|
| 1 | STATIC+EXECUTED | <code>import torch</code> |
| 3 | STATIC+EXECUTED | <code>from cbsc_zdc.models.spatial import ParallelCausalSpatialField</code> |
| 6 | STATIC+EXECUTED | <code>def test_spatial_field_depends_on_flow_time():</code> |
| 7 | STATIC+EXECUTED | <code>    torch.manual_seed(4)</code> |
| 8 | STATIC+EXECUTED | <code>    n_layers = 3</code> |
| 9 | STATIC+EXECUTED | <code>    nodes_per_layer = 2</code> |
| 10 | STATIC+EXECUTED | <code>    n_nodes = n_layers * nodes_per_layer</code> |
| 11 | STATIC+EXECUTED | <code>    model = ParallelCausalSpatialField(</code> |
| 12 | STATIC+MANUAL | <code>        node_dim=5,</code> |
| 13 | STATIC+MANUAL | <code>        cond_dim=8,</code> |
| 14 | STATIC+MANUAL | <code>        hidden=16,</code> |
| 15 | STATIC+MANUAL | <code>        n_layers=n_layers,</code> |
| 16 | STATIC+MANUAL | <code>        transformer_blocks=1,</code> |
| 17 | STATIC+MANUAL | <code>        heads=4,</code> |
| 18 | STATIC+MANUAL | <code>        graph_blocks=1,</code> |
| 19 | STATIC+MANUAL | <code>        edge_dim=3,</code> |
| 20 | STATIC+MANUAL | <code>    ).eval()</code> |
| 21 | STATIC+EXECUTED | <code>    x = torch.randn(2, n_nodes, 2)</code> |
| 22 | STATIC+EXECUTED | <code>    cond = torch.randn(2, 8)</code> |
| 23 | STATIC+EXECUTED | <code>    node_features = torch.randn(n_nodes, 5)</code> |
| 24 | STATIC+EXECUTED | <code>    layer_index = torch.arange(n_nodes) // nodes_per_layer</code> |
| 25 | STATIC+EXECUTED | <code>    budget = torch.rand(2, n_layers)</code> |
| 26 | STATIC+EXECUTED | <code>    counts = torch.ones(2, n_layers, dtype=torch.long)</code> |
| 27 | STATIC+EXECUTED | <code>    max_counts = torch.full((n_layers,), nodes_per_layer, dtype=torch.long)</code> |
| 28 | STATIC+EXECUTED | <code>    edge_index = torch.tensor([[0, 1, 2, 3], [1, 2, 3, 4]])</code> |
| 29 | STATIC+EXECUTED | <code>    edge_features = torch.randn(4, 3)</code> |
| 30 | STATIC+EXECUTED | <code>    with torch.no_grad():</code> |
| 31 | STATIC+EXECUTED | <code>        a = model(x, torch.zeros(2, 1), cond, node_features, layer_index, budget, counts, max_counts, edge_index=edge_index, edge_features=edge_features)</code> |
| 32 | STATIC+EXECUTED | <code>        b = model(x, torch.ones(2, 1), cond, node_features, layer_index, budget, counts, max_counts, edge_index=edge_index, edge_features=edge_features)</code> |
| 33 | STATIC+EXECUTED | <code>    assert not torch.allclose(a, b)</code> |
| 36 | STATIC+EXECUTED | <code>def test_spatial_field_validation_and_default_valid_mask():</code> |
| 37 | STATIC+EXECUTED | <code>    import pytest</code> |
| 39 | STATIC+EXECUTED | <code>    with pytest.raises(ValueError, match="divisible"):</code> |
| 40 | STATIC+EXECUTED | <code>        ParallelCausalSpatialField(hidden=10, heads=4)</code> |
| 42 | STATIC+EXECUTED | <code>    model = ParallelCausalSpatialField(</code> |
| 43 | STATIC+MANUAL | <code>        node_dim=3,</code> |
| 44 | STATIC+MANUAL | <code>        edge_dim=2,</code> |
| 45 | STATIC+MANUAL | <code>        cond_dim=4,</code> |
| 46 | STATIC+MANUAL | <code>        hidden=8,</code> |
| 47 | STATIC+MANUAL | <code>        n_layers=2,</code> |
| 48 | STATIC+MANUAL | <code>        graph_blocks=0,</code> |
| 49 | STATIC+MANUAL | <code>        transformer_blocks=1,</code> |
| 50 | STATIC+MANUAL | <code>        heads=2,</code> |
| 51 | STATIC+MANUAL | <code>    ).eval()</code> |
| 52 | STATIC+EXECUTED | <code>    x = torch.zeros(1, 4, 2)</code> |
| 53 | STATIC+EXECUTED | <code>    t = torch.zeros(1, 1)</code> |
| 54 | STATIC+EXECUTED | <code>    cond = torch.zeros(1, 4)</code> |
| 55 | STATIC+EXECUTED | <code>    nodes = torch.zeros(4, 3)</code> |
| 56 | STATIC+EXECUTED | <code>    layers = torch.tensor([0, 0, 1, 1])</code> |
| 57 | STATIC+EXECUTED | <code>    budget = torch.ones(1, 2)</code> |
| 58 | STATIC+EXECUTED | <code>    counts = torch.ones(1, 2, dtype=torch.long)</code> |
| 59 | STATIC+EXECUTED | <code>    maxima = torch.tensor([2, 2])</code> |
| 60 | STATIC+EXECUTED | <code>    with torch.no_grad():</code> |
| 61 | STATIC+EXECUTED | <code>        out = model(x, t, cond, nodes, layers, budget, counts, maxima)</code> |
| 62 | STATIC+EXECUTED | <code>    assert out.shape == x.shape</code> |
| 64 | STATIC+EXECUTED | <code>    with pytest.raises(ValueError, match="two node-state"):</code> |
| 65 | STATIC+EXECUTED | <code>        model(torch.zeros(1, 4, 1), t, cond, nodes, layers, budget, counts, maxima)</code> |
| 66 | STATIC+EXECUTED | <code>    with pytest.raises(ValueError, match="geometry"):</code> |
| 67 | STATIC+EXECUTED | <code>        model(x, t, cond, nodes[:3], layers, budget, counts, maxima)</code> |
| 68 | STATIC+EXECUTED | <code>    with pytest.raises(ValueError, match="valid_mask"):</code> |
| 69 | STATIC+EXECUTED | <code>        model(x, t, cond, nodes, layers, budget, counts, maxima, valid_mask=torch.ones(3, dtype=torch.bool))</code> |
| 70 | STATIC+EXECUTED | <code>    with pytest.raises(ValueError, match="supplied together"):</code> |
| 71 | STATIC+EXECUTED | <code>        model(x, t, cond, nodes, layers, budget, counts, maxima, edge_index=torch.empty(2, 0, dtype=torch.long))</code> |

## `tests/test_support_decoder.py`

- SHA-256: `693b0efabb410df3d5eb79f434ae86d6e5b62c3a95cd6a1858aaf3c9ff2e51f1`
- Physical lines: 133; nonblank lines listed below: 115.

| Line | Audit | Source |
|---:|---|---|
| 1 | STATIC+EXECUTED | <code>import torch</code> |
| 3 | STATIC+EXECUTED | <code>from cbsc_zdc.models.support import threshold_safe_layer_decoder</code> |
| 6 | STATIC+EXECUTED | <code>def test_threshold_safe_decoder_has_no_dust_and_exact_budget():</code> |
| 7 | STATIC+EXECUTED | <code>    layer_index = torch.tensor([0, 0, 0, 1, 1, 1, 1])</code> |
| 8 | STATIC+EXECUTED | <code>    valid = torch.ones(7, dtype=torch.bool)</code> |
| 9 | STATIC+EXECUTED | <code>    support_logits = torch.tensor([[4.0, 3.0, 2.0, 1.0, 0.0, -1.0, -2.0]])</code> |
| 10 | STATIC+EXECUTED | <code>    share_logits = torch.tensor([[0.0, 1.0, 2.0, 0.0, 0.5, 1.0, 1.5]])</code> |
| 11 | STATIC+EXECUTED | <code>    budget = torch.tensor([[0.050, 0.100]])</code> |
| 12 | STATIC+EXECUTED | <code>    counts = torch.tensor([[2, 3]])</code> |
| 13 | STATIC+EXECUTED | <code>    threshold = 0.010</code> |
| 14 | STATIC+EXECUTED | <code>    out = threshold_safe_layer_decoder(</code> |
| 15 | STATIC+MANUAL | <code>        support_logits,</code> |
| 16 | STATIC+MANUAL | <code>        share_logits,</code> |
| 17 | STATIC+MANUAL | <code>        budget,</code> |
| 18 | STATIC+MANUAL | <code>        counts,</code> |
| 19 | STATIC+MANUAL | <code>        layer_index,</code> |
| 20 | STATIC+MANUAL | <code>        valid,</code> |
| 21 | STATIC+MANUAL | <code>        threshold_gev=threshold,</code> |
| 22 | STATIC+MANUAL | <code>        stochastic_support=False,</code> |
| 23 | STATIC+MANUAL | <code>    )</code> |
| 24 | STATIC+EXECUTED | <code>    positive = out.cell_energy[out.cell_energy &gt; 0]</code> |
| 25 | STATIC+EXECUTED | <code>    assert positive.numel() == 5</code> |
| 26 | STATIC+EXECUTED | <code>    assert torch.all(positive &gt;= threshold)</code> |
| 27 | STATIC+EXECUTED | <code>    assert torch.allclose(out.resolved_layer_energy, budget, atol=1e-7)</code> |
| 28 | STATIC+EXECUTED | <code>    assert torch.allclose(out.subthreshold_residual, torch.zeros_like(budget), atol=1e-7)</code> |
| 29 | STATIC+EXECUTED | <code>    assert torch.equal(out.support_mask.sum(dim=-1), out.realized_counts.sum(dim=-1))</code> |
| 32 | STATIC+EXECUTED | <code>def test_budget_below_threshold_becomes_residual_not_dust():</code> |
| 33 | STATIC+EXECUTED | <code>    layer_index = torch.tensor([0, 0, 0])</code> |
| 34 | STATIC+EXECUTED | <code>    valid = torch.ones(3, dtype=torch.bool)</code> |
| 35 | STATIC+EXECUTED | <code>    out = threshold_safe_layer_decoder(</code> |
| 36 | STATIC+MANUAL | <code>        support_logits=torch.zeros(1, 3),</code> |
| 37 | STATIC+MANUAL | <code>        share_logits=torch.zeros(1, 3),</code> |
| 38 | STATIC+MANUAL | <code>        layer_budget=torch.tensor([[0.005]]),</code> |
| 39 | STATIC+MANUAL | <code>        requested_counts=torch.tensor([[1]]),</code> |
| 40 | STATIC+MANUAL | <code>        layer_index=layer_index,</code> |
| 41 | STATIC+MANUAL | <code>        valid_mask=valid,</code> |
| 42 | STATIC+MANUAL | <code>        threshold_gev=0.010,</code> |
| 43 | STATIC+MANUAL | <code>        stochastic_support=False,</code> |
| 44 | STATIC+MANUAL | <code>    )</code> |
| 45 | STATIC+EXECUTED | <code>    assert torch.equal(out.cell_energy, torch.zeros_like(out.cell_energy))</code> |
| 46 | STATIC+EXECUTED | <code>    assert torch.allclose(out.subthreshold_residual, torch.tensor([[0.005]]))</code> |
| 47 | STATIC+EXECUTED | <code>    assert out.realized_counts.item() == 0</code> |
| 50 | STATIC+EXECUTED | <code>def test_vectorized_decoder_handles_mixed_zero_and_positive_counts():</code> |
| 51 | STATIC+EXECUTED | <code>    layer_index = torch.tensor([0, 0, 0, 1, 1])</code> |
| 52 | STATIC+EXECUTED | <code>    valid = torch.ones(5, dtype=torch.bool)</code> |
| 53 | STATIC+EXECUTED | <code>    out = threshold_safe_layer_decoder(</code> |
| 54 | STATIC+MANUAL | <code>        support_logits=torch.tensor([[2.0, 1.0, 0.0, 2.0, 1.0], [1.0, 2.0, 0.0, 1.0, 2.0]]),</code> |
| 55 | STATIC+MANUAL | <code>        share_logits=torch.zeros(2, 5),</code> |
| 56 | STATIC+MANUAL | <code>        layer_budget=torch.tensor([[0.0, 0.03], [0.02, 0.0]]),</code> |
| 57 | STATIC+MANUAL | <code>        requested_counts=torch.tensor([[0, 2], [2, 0]]),</code> |
| 58 | STATIC+MANUAL | <code>        layer_index=layer_index,</code> |
| 59 | STATIC+MANUAL | <code>        valid_mask=valid,</code> |
| 60 | STATIC+MANUAL | <code>        threshold_gev=0.01,</code> |
| 61 | STATIC+MANUAL | <code>        stochastic_support=False,</code> |
| 62 | STATIC+MANUAL | <code>    )</code> |
| 63 | STATIC+EXECUTED | <code>    assert torch.equal(out.realized_counts, torch.tensor([[0, 2], [2, 0]]))</code> |
| 64 | STATIC+EXECUTED | <code>    assert torch.allclose(out.cell_energy.sum(dim=1), torch.tensor([0.03, 0.02]))</code> |
| 65 | STATIC+EXECUTED | <code>    assert torch.all(out.cell_energy[(out.cell_energy &gt; 0)] &gt;= 0.01)</code> |
| 68 | STATIC+EXECUTED | <code>def test_single_vector_gumbel_topk_and_decoder_validation_paths():</code> |
| 69 | STATIC+EXECUTED | <code>    import pytest</code> |
| 71 | STATIC+EXECUTED | <code>    from cbsc_zdc.models.support import gumbel_topk_mask</code> |
| 73 | STATIC+EXECUTED | <code>    logits = torch.tensor([3.0, 2.0, 1.0])</code> |
| 74 | STATIC+EXECUTED | <code>    assert gumbel_topk_mask(logits, 0, stochastic=False).sum() == 0</code> |
| 75 | STATIC+EXECUTED | <code>    assert gumbel_topk_mask(logits, 2, stochastic=False).tolist() == [True, True, False]</code> |
| 76 | STATIC+EXECUTED | <code>    assert gumbel_topk_mask(logits, 2, stochastic=True).sum() == 2</code> |
| 77 | STATIC+EXECUTED | <code>    with pytest.raises(ValueError, match="one-dimensional"):</code> |
| 78 | STATIC+EXECUTED | <code>        gumbel_topk_mask(logits[None], 1)</code> |
| 79 | STATIC+EXECUTED | <code>    with pytest.raises(ValueError, match="outside"):</code> |
| 80 | STATIC+EXECUTED | <code>        gumbel_topk_mask(logits, 4)</code> |
| 82 | STATIC+EXECUTED | <code>    base = dict(</code> |
| 83 | STATIC+MANUAL | <code>        support_logits=torch.zeros(1, 3),</code> |
| 84 | STATIC+MANUAL | <code>        share_logits=torch.zeros(1, 3),</code> |
| 85 | STATIC+MANUAL | <code>        layer_budget=torch.zeros(1, 1),</code> |
| 86 | STATIC+MANUAL | <code>        requested_counts=torch.zeros(1, 1, dtype=torch.long),</code> |
| 87 | STATIC+MANUAL | <code>        layer_index=torch.zeros(3, dtype=torch.long),</code> |
| 88 | STATIC+MANUAL | <code>        valid_mask=torch.ones(3, dtype=torch.bool),</code> |
| 89 | STATIC+MANUAL | <code>    )</code> |
| 90 | STATIC+EXECUTED | <code>    with pytest.raises(ValueError, match="nonnegative"):</code> |
| 91 | STATIC+EXECUTED | <code>        threshold_safe_layer_decoder(**base, threshold_gev=-1.0)</code> |
| 92 | STATIC+EXECUTED | <code>    bad = dict(base)</code> |
| 93 | STATIC+EXECUTED | <code>    bad["support_logits"] = torch.zeros(3)</code> |
| 94 | STATIC+EXECUTED | <code>    with pytest.raises(ValueError, match="support_logits"):</code> |
| 95 | STATIC+EXECUTED | <code>        threshold_safe_layer_decoder(**bad)</code> |
| 96 | STATIC+EXECUTED | <code>    bad = dict(base)</code> |
| 97 | STATIC+EXECUTED | <code>    bad["share_logits"] = torch.zeros(1, 2)</code> |
| 98 | STATIC+EXECUTED | <code>    with pytest.raises(ValueError, match="share_logits"):</code> |
| 99 | STATIC+EXECUTED | <code>        threshold_safe_layer_decoder(**bad)</code> |
| 100 | STATIC+EXECUTED | <code>    bad = dict(base)</code> |
| 101 | STATIC+EXECUTED | <code>    bad["valid_mask"] = torch.ones(2, dtype=torch.bool)</code> |
| 102 | STATIC+EXECUTED | <code>    with pytest.raises(ValueError, match="layer_index"):</code> |
| 103 | STATIC+EXECUTED | <code>        threshold_safe_layer_decoder(**bad)</code> |
| 104 | STATIC+EXECUTED | <code>    bad = dict(base)</code> |
| 105 | STATIC+EXECUTED | <code>    bad["requested_counts"] = torch.zeros(1, 2, dtype=torch.long)</code> |
| 106 | STATIC+EXECUTED | <code>    with pytest.raises(ValueError, match="same shape"):</code> |
| 107 | STATIC+EXECUTED | <code>        threshold_safe_layer_decoder(**bad)</code> |
| 110 | STATIC+EXECUTED | <code>def test_decoder_routes_budget_for_layer_with_no_valid_nodes():</code> |
| 111 | STATIC+EXECUTED | <code>    out = threshold_safe_layer_decoder(</code> |
| 112 | STATIC+MANUAL | <code>        support_logits=torch.zeros(1, 2),</code> |
| 113 | STATIC+MANUAL | <code>        share_logits=torch.zeros(1, 2),</code> |
| 114 | STATIC+MANUAL | <code>        layer_budget=torch.tensor([[0.0, 0.4]]),</code> |
| 115 | STATIC+MANUAL | <code>        requested_counts=torch.tensor([[0, 1]]),</code> |
| 116 | STATIC+MANUAL | <code>        layer_index=torch.tensor([0, 0]),</code> |
| 117 | STATIC+MANUAL | <code>        valid_mask=torch.ones(2, dtype=torch.bool),</code> |
| 118 | STATIC+MANUAL | <code>        threshold_gev=0.0,</code> |
| 119 | STATIC+MANUAL | <code>        stochastic_support=False,</code> |
| 120 | STATIC+MANUAL | <code>    )</code> |
| 121 | STATIC+EXECUTED | <code>    assert torch.allclose(out.subthreshold_residual, torch.tensor([[0.0, 0.4]]))</code> |
| 124 | STATIC+EXECUTED | <code>def test_batched_topk_private_validation_paths():</code> |
| 125 | STATIC+EXECUTED | <code>    import pytest</code> |
| 127 | STATIC+EXECUTED | <code>    from cbsc_zdc.models.support import _batched_exact_k_mask</code> |
| 129 | STATIC+EXECUTED | <code>    logits = torch.zeros(2, 3)</code> |
| 130 | STATIC+EXECUTED | <code>    with pytest.raises(ValueError, match="shape mismatch"):</code> |
| 131 | STATIC+EXECUTED | <code>        _batched_exact_k_mask(logits[0], torch.tensor([1, 1]), stochastic=False)</code> |
| 132 | STATIC+EXECUTED | <code>    with pytest.raises(ValueError, match="infeasible"):</code> |
| 133 | STATIC+EXECUTED | <code>        _batched_exact_k_mask(logits, torch.tensor([1, 4]), stochastic=False)</code> |

## `tests/test_system.py`

- SHA-256: `b86a9c84b3c0eed5bb87901a791852d8015b8ec6451db51c2a520cf71be67b71`
- Physical lines: 135; nonblank lines listed below: 122.

| Line | Audit | Source |
|---:|---|---|
| 1 | STATIC+EXECUTED | <code>import torch</code> |
| 3 | STATIC+EXECUTED | <code>from cbsc_zdc.eval.diagnostics import invariant_report</code> |
| 4 | STATIC+EXECUTED | <code>from cbsc_zdc.models.system import CBSCZDC</code> |
| 7 | STATIC+EXECUTED | <code>def test_sampling_invariants_small_geometry():</code> |
| 8 | STATIC+EXECUTED | <code>    n_layers = 5</code> |
| 9 | STATIC+EXECUTED | <code>    nodes_per_layer = 8</code> |
| 10 | STATIC+EXECUTED | <code>    n_nodes = n_layers * nodes_per_layer</code> |
| 11 | STATIC+EXECUTED | <code>    layer = torch.arange(n_nodes) // nodes_per_layer</code> |
| 12 | STATIC+EXECUTED | <code>    features = torch.randn(n_nodes, 8)</code> |
| 13 | STATIC+EXECUTED | <code>    valid = torch.ones(n_nodes, dtype=torch.bool)</code> |
| 14 | STATIC+EXECUTED | <code>    model = CBSCZDC(</code> |
| 15 | STATIC+MANUAL | <code>        features,</code> |
| 16 | STATIC+MANUAL | <code>        layer,</code> |
| 17 | STATIC+MANUAL | <code>        valid,</code> |
| 18 | STATIC+MANUAL | <code>        cond_dim=32,</code> |
| 19 | STATIC+MANUAL | <code>        latent_dim=8,</code> |
| 20 | STATIC+MANUAL | <code>        threshold_gev=0.001,</code> |
| 21 | STATIC+MANUAL | <code>    )</code> |
| 22 | STATIC+EXECUTED | <code>    mass = 0.93956542052</code> |
| 23 | STATIC+EXECUTED | <code>    momentum = torch.tensor([[0.0, 0.0, 50.0], [1.0, 2.0, 100.0]])</code> |
| 24 | STATIC+EXECUTED | <code>    energy = torch.sqrt((momentum * momentum).sum(dim=-1) + mass**2)[:, None]</code> |
| 25 | STATIC+EXECUTED | <code>    p4 = torch.cat((energy, momentum), dim=-1)</code> |
| 26 | STATIC+EXECUTED | <code>    out = model.sample(p4, steps=2, seed=1)</code> |
| 27 | STATIC+EXECUTED | <code>    report = invariant_report(</code> |
| 28 | STATIC+MANUAL | <code>        p4,</code> |
| 29 | STATIC+MANUAL | <code>        out,</code> |
| 30 | STATIC+MANUAL | <code>        threshold_gev=0.001,</code> |
| 31 | STATIC+MANUAL | <code>        layer_index=layer,</code> |
| 32 | STATIC+MANUAL | <code>    )</code> |
| 33 | STATIC+EXECUTED | <code>    assert report["nonfinite"] == 0</code> |
| 34 | STATIC+EXECUTED | <code>    assert report["negative"] == 0</code> |
| 35 | STATIC+EXECUTED | <code>    assert report["dust_cells"] == 0</code> |
| 36 | STATIC+EXECUTED | <code>    assert report["total_over_incident"] == 0</code> |
| 37 | STATIC+EXECUTED | <code>    assert report["accounting_identity_max"] &lt; 1e-4</code> |
| 38 | STATIC+EXECUTED | <code>    assert report["support_count_mismatch_max"] == 0</code> |
| 39 | STATIC+EXECUTED | <code>    assert report["resolved_layer_mismatch_max"] &lt; 1e-4</code> |
| 42 | STATIC+EXECUTED | <code>def test_seeded_sampling_is_reproducible():</code> |
| 43 | STATIC+EXECUTED | <code>    n_layers = 3</code> |
| 44 | STATIC+EXECUTED | <code>    nodes_per_layer = 4</code> |
| 45 | STATIC+EXECUTED | <code>    n_nodes = n_layers * nodes_per_layer</code> |
| 46 | STATIC+EXECUTED | <code>    layer = torch.arange(n_nodes) // nodes_per_layer</code> |
| 47 | STATIC+EXECUTED | <code>    features = torch.randn(n_nodes, 8)</code> |
| 48 | STATIC+EXECUTED | <code>    valid = torch.ones(n_nodes, dtype=torch.bool)</code> |
| 49 | STATIC+EXECUTED | <code>    model = CBSCZDC(features, layer, valid, cond_dim=16, latent_dim=4, threshold_gev=0.0)</code> |
| 50 | STATIC+EXECUTED | <code>    mass = 0.93956542052</code> |
| 51 | STATIC+EXECUTED | <code>    momentum = torch.tensor([[0.5, 1.0, 20.0]])</code> |
| 52 | STATIC+EXECUTED | <code>    energy = torch.sqrt((momentum * momentum).sum(dim=-1) + mass**2)[:, None]</code> |
| 53 | STATIC+EXECUTED | <code>    p4 = torch.cat((energy, momentum), dim=-1)</code> |
| 54 | STATIC+EXECUTED | <code>    a = model.sample(p4, steps=2, seed=17)</code> |
| 55 | STATIC+EXECUTED | <code>    b = model.sample(p4, steps=2, seed=17)</code> |
| 56 | STATIC+EXECUTED | <code>    assert torch.equal(a.support_mask, b.support_mask)</code> |
| 57 | STATIC+EXECUTED | <code>    assert torch.allclose(a.cell_energy, b.cell_energy)</code> |
| 60 | STATIC+EXECUTED | <code>def test_nonstochastic_sampling_is_deterministic_without_a_seed():</code> |
| 61 | STATIC+EXECUTED | <code>    n_layers = 3</code> |
| 62 | STATIC+EXECUTED | <code>    nodes_per_layer = 4</code> |
| 63 | STATIC+EXECUTED | <code>    n_nodes = n_layers * nodes_per_layer</code> |
| 64 | STATIC+EXECUTED | <code>    layer = torch.arange(n_nodes) // nodes_per_layer</code> |
| 65 | STATIC+EXECUTED | <code>    features = torch.randn(n_nodes, 8)</code> |
| 66 | STATIC+EXECUTED | <code>    valid = torch.ones(n_nodes, dtype=torch.bool)</code> |
| 67 | STATIC+EXECUTED | <code>    model = CBSCZDC(</code> |
| 68 | STATIC+MANUAL | <code>        features,</code> |
| 69 | STATIC+MANUAL | <code>        layer,</code> |
| 70 | STATIC+MANUAL | <code>        valid,</code> |
| 71 | STATIC+MANUAL | <code>        cond_dim=16,</code> |
| 72 | STATIC+MANUAL | <code>        latent_dim=4,</code> |
| 73 | STATIC+MANUAL | <code>        threshold_gev=0.0,</code> |
| 74 | STATIC+MANUAL | <code>    ).eval()</code> |
| 75 | STATIC+EXECUTED | <code>    mass = 0.93956542052</code> |
| 76 | STATIC+EXECUTED | <code>    momentum = torch.tensor([[0.5, 1.0, 20.0]])</code> |
| 77 | STATIC+EXECUTED | <code>    energy = torch.sqrt((momentum * momentum).sum(dim=-1) + mass**2)[:, None]</code> |
| 78 | STATIC+EXECUTED | <code>    p4 = torch.cat((energy, momentum), dim=-1)</code> |
| 79 | STATIC+EXECUTED | <code>    a = model.sample(p4, steps=2, stochastic=False)</code> |
| 80 | STATIC+EXECUTED | <code>    b = model.sample(p4, steps=2, stochastic=False)</code> |
| 81 | STATIC+EXECUTED | <code>    assert torch.equal(a.support_mask, b.support_mask)</code> |
| 82 | STATIC+EXECUTED | <code>    assert torch.allclose(a.cell_energy, b.cell_energy)</code> |
| 85 | STATIC+EXECUTED | <code>def test_system_constructor_and_sampling_validation_paths():</code> |
| 86 | STATIC+EXECUTED | <code>    import pytest</code> |
| 88 | STATIC+EXECUTED | <code>    features = torch.zeros(4, 8)</code> |
| 89 | STATIC+EXECUTED | <code>    layers = torch.tensor([0, 0, 1, 1])</code> |
| 90 | STATIC+EXECUTED | <code>    valid = torch.ones(4, dtype=torch.bool)</code> |
| 91 | STATIC+EXECUTED | <code>    with pytest.raises(ValueError, match="nonnegative"):</code> |
| 92 | STATIC+EXECUTED | <code>        CBSCZDC(features, layers, valid, threshold_gev=-1.0)</code> |
| 93 | STATIC+EXECUTED | <code>    with pytest.raises(ValueError, match="node_features"):</code> |
| 94 | STATIC+EXECUTED | <code>        CBSCZDC(torch.zeros(4), layers, valid)</code> |
| 95 | STATIC+EXECUTED | <code>    with pytest.raises(ValueError, match="shape"):</code> |
| 96 | STATIC+EXECUTED | <code>        CBSCZDC(features, layers[:3], valid)</code> |
| 97 | STATIC+EXECUTED | <code>    with pytest.raises(ValueError, match="nonnegative"):</code> |
| 98 | STATIC+EXECUTED | <code>        CBSCZDC(features, torch.tensor([0, 0, -1, 1]), valid)</code> |
| 99 | STATIC+EXECUTED | <code>    with pytest.raises(ValueError, match="at least one valid"):</code> |
| 100 | STATIC+EXECUTED | <code>        CBSCZDC(features, layers, torch.zeros(4, dtype=torch.bool))</code> |
| 101 | STATIC+EXECUTED | <code>    with pytest.raises(ValueError, match="supplied together"):</code> |
| 102 | STATIC+EXECUTED | <code>        CBSCZDC(features, layers, valid, edge_index=torch.empty(2, 0, dtype=torch.long))</code> |
| 103 | STATIC+EXECUTED | <code>    with pytest.raises(ValueError, match="every modeled layer"):</code> |
| 104 | STATIC+EXECUTED | <code>        CBSCZDC(features, torch.tensor([0, 0, 2, 2]), valid)</code> |
| 106 | STATIC+EXECUTED | <code>    model = CBSCZDC(features, layers, valid, cond_dim=16, latent_dim=4)</code> |
| 107 | STATIC+EXECUTED | <code>    mass = 0.93956542052</code> |
| 108 | STATIC+EXECUTED | <code>    momentum = torch.tensor([[0.0, 0.0, 10.0]])</code> |
| 109 | STATIC+EXECUTED | <code>    energy = torch.sqrt((momentum * momentum).sum(dim=-1) + mass**2)[:, None]</code> |
| 110 | STATIC+EXECUTED | <code>    p4 = torch.cat((energy, momentum), dim=-1)</code> |
| 111 | STATIC+EXECUTED | <code>    with pytest.raises(ValueError, match="steps"):</code> |
| 112 | STATIC+EXECUTED | <code>        model.sample(p4, steps=0)</code> |
| 115 | STATIC+EXECUTED | <code>def test_invariant_report_without_layer_breakdown_and_explicit_empty_graph():</code> |
| 116 | STATIC+EXECUTED | <code>    n_nodes = 4</code> |
| 117 | STATIC+EXECUTED | <code>    features = torch.zeros(n_nodes, 8)</code> |
| 118 | STATIC+EXECUTED | <code>    layers = torch.tensor([0, 0, 1, 1])</code> |
| 119 | STATIC+EXECUTED | <code>    valid = torch.ones(n_nodes, dtype=torch.bool)</code> |
| 120 | STATIC+EXECUTED | <code>    model = CBSCZDC(</code> |
| 121 | STATIC+MANUAL | <code>        features,</code> |
| 122 | STATIC+MANUAL | <code>        layers,</code> |
| 123 | STATIC+MANUAL | <code>        valid,</code> |
| 124 | STATIC+MANUAL | <code>        cond_dim=16,</code> |
| 125 | STATIC+MANUAL | <code>        latent_dim=4,</code> |
| 126 | STATIC+MANUAL | <code>        edge_index=torch.empty(2, 0, dtype=torch.long),</code> |
| 127 | STATIC+MANUAL | <code>        edge_features=torch.empty(0, 4),</code> |
| 128 | STATIC+MANUAL | <code>    )</code> |
| 129 | STATIC+EXECUTED | <code>    mass = 0.93956542052</code> |
| 130 | STATIC+EXECUTED | <code>    momentum = torch.tensor([[0.0, 0.0, 10.0]])</code> |
| 131 | STATIC+EXECUTED | <code>    energy = torch.sqrt((momentum * momentum).sum(dim=-1) + mass**2)[:, None]</code> |
| 132 | STATIC+EXECUTED | <code>    p4 = torch.cat((energy, momentum), dim=-1)</code> |
| 133 | STATIC+EXECUTED | <code>    out = model.sample(p4, steps=1, stochastic=False)</code> |
| 134 | STATIC+EXECUTED | <code>    report = invariant_report(p4, out)</code> |
| 135 | STATIC+EXECUTED | <code>    assert "resolved_layer_mismatch_max" not in report</code> |

