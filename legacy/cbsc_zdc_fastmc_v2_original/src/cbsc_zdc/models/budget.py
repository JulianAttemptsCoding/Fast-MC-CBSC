"""Compatibility exports for the revised profile model.

The original sequential sigmoid stick-breaking scaffold was removed because it introduced
an avoidable depth-order bias over 65 layers. The revised implementation generates exact
layer support first and allocates total response on a masked simplex; the remaining budget
is then monotone by cumulative accounting rather than by a fragile product of 65 fractions.
"""

from .profile import LongitudinalProfileModel, ProfileOutput

__all__ = ["LongitudinalProfileModel", "ProfileOutput"]
