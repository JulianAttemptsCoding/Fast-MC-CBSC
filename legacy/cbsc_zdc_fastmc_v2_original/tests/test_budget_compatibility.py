from cbsc_zdc.models.budget import LongitudinalProfileModel, ProfileOutput
from cbsc_zdc.models.profile import (
    LongitudinalProfileModel as CanonicalLongitudinalProfileModel,
)
from cbsc_zdc.models.profile import ProfileOutput as CanonicalProfileOutput


def test_budget_module_reexports_revised_profile_types():
    assert LongitudinalProfileModel is CanonicalLongitudinalProfileModel
    assert ProfileOutput is CanonicalProfileOutput
