"""Six HCAL diagnostic panels from the paired Geant4/Fast-MC diagnostic sample.

Reads results.npz produced by `cbsc_zdc.cloud.paired_diagnostics` (run on
Vertex AI) and builds the comparison figures locally -- no GPU needed here.

    python exhibition/build_paired_diagnostics_figures.py --results PATH --out-dir DIR
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from cbsc_zdc.eval.metrics import response_bins

NAVY = "#102A43"
GEN = "#D55E00"  # calibrated_lr3e4's own established color elsewhere in this project
MUTED = "#627D98"
GRID = "#D9E2EC"

ENERGY_EDGES = np.array([0, 25, 50, 75, 100, 125, 150, 175, 200, 225, 250, 275, 300.0001])


def style() -> None:
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 11,
        "axes.titlesize": 13, "axes.titleweight": "bold",
        "axes.edgecolor": GRID, "axes.labelcolor": "#334E68",
        "xtick.color": MUTED, "ytick.color": MUTED,
        "axes.spines.top": False, "axes.spines.right": False,
    })


def clean(ax) -> None:
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)


def save(fig, path: Path) -> None:
    fig.savefig(path, dpi=170, bbox_inches="tight")
    plt.close(fig)
    print("wrote", path)


def panel_1_cell_energy_spectrum(truth: np.ndarray, gen: np.ndarray, out: Path) -> None:
    fig = plt.figure(figsize=(7.2, 6.0))
    gs = fig.add_gridspec(2, 1, height_ratios=[3, 1.2], hspace=0.08)
    ax = fig.add_subplot(gs[0])
    axr = fig.add_subplot(gs[1], sharex=ax)

    lo = min(truth.min(), gen.min())
    hi = max(truth.max(), gen.max())
    edges = np.logspace(np.log10(lo), np.log10(hi), 61)
    t_counts, _ = np.histogram(truth, bins=edges)
    g_counts, _ = np.histogram(gen, bins=edges)

    ax.stairs(t_counts, edges, color=NAVY, lw=1.6, label="Geant4 (truth)")
    ax.stairs(g_counts, edges, color=GEN, lw=1.6, label="Fast-MC (calibrated_lr3e4)")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_ylabel("Number of cells")
    ax.set_title("HCAL cell energy spectrum")
    ax.legend(frameon=False, fontsize=9.5)
    clean(ax)

    ratio = np.divide(g_counts, t_counts, out=np.full_like(g_counts, np.nan, dtype=float),
                       where=t_counts > 0)
    centers = np.sqrt(edges[1:] * edges[:-1])
    axr.plot(centers, ratio, ".", color=MUTED, markersize=3)
    axr.axhline(1.0, color=NAVY, lw=1.0, ls="--")
    axr.set_ylim(0, 2)
    axr.set_ylabel("Gen / Truth")
    axr.set_xlabel("Cell energy [GeV]")
    clean(axr)
    fig.align_ylabels([ax, axr])
    save(fig, out)


def _hist_panel(truth, gen, title_text, xlabel, out: Path, *, logy=True) -> None:
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    lo = min(truth.min(), gen.min())
    hi = max(truth.max(), gen.max())
    edges = np.linspace(lo, hi, 41)
    ax.hist(truth, bins=edges, histtype="step", color=NAVY, lw=1.6, label="Geant4 (truth)")
    ax.hist(gen, bins=edges, histtype="step", color=GEN, lw=1.6, label="Fast-MC (calibrated_lr3e4)")
    if logy:
        ax.set_yscale("log")
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Events")
    ax.set_title(title_text)
    ax.legend(frameon=False, fontsize=9.5)
    clean(ax)
    save(fig, out)


def _vs_energy_panel(kinetic, truth, gen, title_text, ylabel, out: Path) -> None:
    rows = response_bins(kinetic, truth, gen, ENERGY_EDGES)
    centers = [(r["low"] + r["high"]) / 2 for r in rows if r["truth_mean"] is not None]
    truth_mean = [r["truth_mean"] for r in rows if r["truth_mean"] is not None]
    gen_mean = [r["generated_mean"] for r in rows if r["generated_mean"] is not None]

    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    ax.plot(centers, truth_mean, "o-", color=NAVY, label="Geant4 (truth)")
    ax.plot(centers, gen_mean, "s--", color=GEN, label="Fast-MC (calibrated_lr3e4)")
    ax.set_xlabel("Beam (incident kinetic) energy [GeV]")
    ax.set_ylabel(ylabel)
    ax.set_title(title_text)
    ax.legend(frameon=False, fontsize=9.5)
    clean(ax)
    save(fig, out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()
    style()

    d = np.load(args.results)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    kinetic = d["kinetic_energy_gev"].astype(np.float64)
    truth_total = d["truth_hcal_total_gev"].astype(np.float64)
    gen_total = d["generated_hcal_total_gev"].astype(np.float64)
    truth_hits = d["truth_hcal_hits"].astype(np.float64)
    gen_hits = d["generated_hcal_hits"].astype(np.float64)
    # Below ~1 GeV incident kinetic energy the HCAL/beam fraction is not a
    # meaningful quantity -- a near-zero denominator turns an ordinary small
    # residual deposit into an enormous, physically meaningless ratio (e.g.
    # kinetic=0.006 GeV with a 0.3 GeV generated deposit gives a "fraction" of
    # 48). Only 8 of 2000 sampled events fall below this cut.
    fraction_valid = kinetic > 1.0
    safe_kinetic = np.where(fraction_valid, kinetic, np.nan)
    truth_fraction = truth_total / safe_kinetic
    gen_fraction = gen_total / safe_kinetic

    panel_1_cell_energy_spectrum(
        d["truth_hcal_positive_cells_gev"].astype(np.float64),
        d["generated_hcal_positive_cells_gev"].astype(np.float64),
        out_dir / "01_hcal_cell_energy_spectrum.png",
    )
    _hist_panel(truth_total, gen_total, "HCAL total energy response",
                "HCAL energy [GeV]", out_dir / "02_hcal_total_energy_response.png")
    _hist_panel(truth_fraction[~np.isnan(truth_fraction)], gen_fraction[~np.isnan(gen_fraction)],
                "HCAL energy fraction (HCAL / beam energy)",
                "E_HCAL / E_beam", out_dir / "03_hcal_energy_fraction.png")
    _hist_panel(truth_hits, gen_hits, "HCAL hit multiplicity",
                "Hits / event", out_dir / "04_hcal_hit_multiplicity.png", logy=False)
    _vs_energy_panel(kinetic[fraction_valid], truth_fraction[fraction_valid],
                     gen_fraction[fraction_valid],
                     "HCAL energy fraction vs. beam energy", "E_HCAL / E_beam",
                     out_dir / "05_hcal_fraction_vs_energy.png")
    _vs_energy_panel(kinetic, truth_hits, gen_hits,
                     "HCAL hits vs. beam energy", "Avg hits / event",
                     out_dir / "06_hcal_hits_vs_energy.png")


if __name__ == "__main__":
    main()
