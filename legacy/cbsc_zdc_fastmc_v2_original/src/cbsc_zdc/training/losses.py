from __future__ import annotations

import torch


def dust_fraction(cell_energy: torch.Tensor, threshold_gev: float) -> torch.Tensor:
    """Fraction of cells with forbidden 0 < E < threshold."""
    if threshold_gev <= 0:
        return torch.zeros((), device=cell_energy.device, dtype=cell_energy.dtype)
    dust = (cell_energy > 0) & (cell_energy < threshold_gev)
    return dust.float().mean()


def support_binary_cross_entropy(
    logits: torch.Tensor,
    truth_mask: torch.Tensor,
    positive_weight: torch.Tensor | None = None,
) -> torch.Tensor:
    return torch.nn.functional.binary_cross_entropy_with_logits(
        logits,
        truth_mask.to(logits.dtype),
        pos_weight=positive_weight,
    )


def count_cross_entropy(
    count_logits: torch.Tensor,
    truth_counts: torch.Tensor,
) -> torch.Tensor:
    return torch.nn.functional.cross_entropy(
        count_logits.reshape(-1, count_logits.shape[-1]),
        truth_counts.reshape(-1),
    )


def positive_log_energy_loss(
    generated: torch.Tensor,
    truth: torch.Tensor,
    generated_mask: torch.Tensor,
    truth_mask: torch.Tensor,
    eps: float = 1e-8,
) -> torch.Tensor:
    """Simple diagnostic loss on positive hit spectra.

    A production experiment should supplement this with distributional losses rather than
    relying on an eventwise matching of independent Geant4 showers.
    """
    g = torch.log(generated[generated_mask] + eps)
    t = torch.log(truth[truth_mask] + eps)
    if g.numel() == 0 or t.numel() == 0:
        return generated.new_zeros(())
    # Quantile matching avoids requiring one-to-one hit correspondence.  Evaluate both
    # samples on the same probability grid; truncating sorted arrays would bias the
    # comparison toward the lower tail when the sample sizes differ.
    n_quantiles = min(max(min(g.numel(), t.numel()), 2), 256)
    probability = torch.linspace(
        0.0, 1.0, n_quantiles, device=generated.device, dtype=generated.dtype
    )
    generated_quantiles = torch.quantile(g, probability)
    truth_quantiles = torch.quantile(t, probability)
    return torch.nn.functional.smooth_l1_loss(
        generated_quantiles, truth_quantiles
    )
