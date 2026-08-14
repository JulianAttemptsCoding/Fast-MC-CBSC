"""Monotone rational-quadratic spline on the unit interval.

Used by the v3 response head to map a uniform base variable onto ``r_T =
T/C(K)`` in ``(0,1)``.  The transform is monotone by construction, so it is
invertible and its log-Jacobian is available in closed form.

Parametrization follows Durkan et al.'s neural spline flows: ``bins`` widths and
heights come from softmaxes adjusted to respect a minimum, and the ``bins+1``
knot derivatives come from a softplus plus a minimum derivative.  The minima are
what keep the inverse well conditioned; they are not tunable safety fudge.

Only the interior of ``(0,1)`` is modelled.  There is no clamp: the caller is
responsible for supplying targets strictly inside the support, because a
clamped target would silently create a second probability atom at the boundary
-- exactly the defect the bounded response head exists to remove.
"""

from __future__ import annotations

import torch
from torch import nn
from torch.nn import functional as F

DEFAULT_BINS = 16
MIN_BIN_WIDTH = 1e-3
MIN_BIN_HEIGHT = 1e-3
MIN_DERIVATIVE = 1e-3


def _normalize(raw: torch.Tensor, minimum: float, bins: int) -> torch.Tensor:
    """Softmax to a simplex, then reserve ``minimum`` for every bin."""
    return minimum + (1.0 - minimum * bins) * F.softmax(raw, dim=-1)


def rational_quadratic_transform(
    inputs: torch.Tensor,
    unnormalized_widths: torch.Tensor,
    unnormalized_heights: torch.Tensor,
    unnormalized_derivatives: torch.Tensor,
    *,
    inverse: bool = False,
    min_bin_width: float = MIN_BIN_WIDTH,
    min_bin_height: float = MIN_BIN_HEIGHT,
    min_derivative: float = MIN_DERIVATIVE,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Apply the spline, returning ``(outputs, log_abs_det_jacobian)``.

    ``inputs`` are in ``(0,1)``.  With ``inverse=False`` this maps the base
    variable to the target; with ``inverse=True`` it maps back.  The returned
    log-determinant always refers to the direction actually applied.
    """
    bins = unnormalized_widths.shape[-1]
    if min_bin_width * bins > 1.0:
        raise ValueError("minimum bin width is too large for the requested bin count")
    if min_bin_height * bins > 1.0:
        raise ValueError("minimum bin height is too large for the requested bin count")

    widths = _normalize(unnormalized_widths, min_bin_width, bins)
    cumwidths = F.pad(widths.cumsum(-1), (1, 0), value=0.0)
    cumwidths = cumwidths / cumwidths[..., -1:].clamp_min(1e-12)
    widths = cumwidths[..., 1:] - cumwidths[..., :-1]

    heights = _normalize(unnormalized_heights, min_bin_height, bins)
    cumheights = F.pad(heights.cumsum(-1), (1, 0), value=0.0)
    cumheights = cumheights / cumheights[..., -1:].clamp_min(1e-12)
    heights = cumheights[..., 1:] - cumheights[..., :-1]

    derivatives = min_derivative + F.softplus(unnormalized_derivatives)

    haystack = cumheights if inverse else cumwidths
    # searchsorted on the interior knots gives the containing bin index
    index = torch.searchsorted(haystack[..., 1:].contiguous(), inputs[..., None].contiguous())
    index = index.clamp(0, bins - 1)

    def gather(source: torch.Tensor) -> torch.Tensor:
        return source.gather(-1, index)[..., 0]

    input_cumwidths = gather(cumwidths[..., :-1])
    input_bin_widths = gather(widths)
    input_cumheights = gather(cumheights[..., :-1])
    input_heights = gather(heights)
    delta = input_heights / input_bin_widths
    input_derivatives = gather(derivatives[..., :-1])
    input_derivatives_plus_one = gather(derivatives[..., 1:])

    if inverse:
        a = (inputs - input_cumheights) * (
            input_derivatives + input_derivatives_plus_one - 2 * delta
        ) + input_heights * (delta - input_derivatives)
        b = input_heights * input_derivatives - (inputs - input_cumheights) * (
            input_derivatives + input_derivatives_plus_one - 2 * delta
        )
        c = -delta * (inputs - input_cumheights)
        discriminant = b.pow(2) - 4 * a * c
        # Monotonicity guarantees a nonnegative discriminant analytically; the
        # clamp only absorbs float round-off at the knots.
        root = (2 * c) / (-b - torch.sqrt(discriminant.clamp_min(0.0)))
        outputs = root * input_bin_widths + input_cumwidths
        theta_one_minus_theta = root * (1 - root)
        denominator = delta + (
            (input_derivatives + input_derivatives_plus_one - 2 * delta) * theta_one_minus_theta
        )
        derivative_numerator = delta.pow(2) * (
            input_derivatives_plus_one * root.pow(2)
            + 2 * delta * theta_one_minus_theta
            + input_derivatives * (1 - root).pow(2)
        )
        logabsdet = -(torch.log(derivative_numerator) - 2 * torch.log(denominator))
        return outputs, logabsdet

    theta = (inputs - input_cumwidths) / input_bin_widths
    theta_one_minus_theta = theta * (1 - theta)
    numerator = input_heights * (
        delta * theta.pow(2) + input_derivatives * theta_one_minus_theta
    )
    denominator = delta + (
        (input_derivatives + input_derivatives_plus_one - 2 * delta) * theta_one_minus_theta
    )
    outputs = input_cumheights + numerator / denominator
    derivative_numerator = delta.pow(2) * (
        input_derivatives_plus_one * theta.pow(2)
        + 2 * delta * theta_one_minus_theta
        + input_derivatives * (1 - theta).pow(2)
    )
    logabsdet = torch.log(derivative_numerator) - 2 * torch.log(denominator)
    return outputs, logabsdet


class ConditionalRationalQuadraticSpline(nn.Module):
    """Condition-dependent monotone spline on ``(0,1)``."""

    def __init__(self, cond_dim: int = 128, hidden: int = 192, bins: int = DEFAULT_BINS) -> None:
        super().__init__()
        self.bins = int(bins)
        self.net = nn.Sequential(
            nn.Linear(cond_dim, hidden),
            nn.SiLU(),
            nn.Linear(hidden, hidden),
            nn.SiLU(),
            nn.Linear(hidden, 3 * self.bins + 1),
        )

    def parameters_for(self, cond: torch.Tensor):
        raw = self.net(cond)
        widths = raw[..., : self.bins]
        heights = raw[..., self.bins : 2 * self.bins]
        derivatives = raw[..., 2 * self.bins :]
        return widths, heights, derivatives

    def forward(
        self, base: torch.Tensor, cond: torch.Tensor, *, inverse: bool = False
    ) -> tuple[torch.Tensor, torch.Tensor]:
        widths, heights, derivatives = self.parameters_for(cond)
        return rational_quadratic_transform(
            base, widths, heights, derivatives, inverse=inverse
        )

    def normalized_parameters(self, cond: torch.Tensor) -> dict[str, torch.Tensor]:
        """Expose the constrained parameters so tests can assert the minima."""
        widths, heights, derivatives = self.parameters_for(cond)
        return {
            "widths": _normalize(widths, MIN_BIN_WIDTH, self.bins),
            "heights": _normalize(heights, MIN_BIN_HEIGHT, self.bins),
            "derivatives": MIN_DERIVATIVE + F.softplus(derivatives),
        }
