"""Logic for standings in Eve Online."""

from django.db import models
from django.utils.translation import gettext_lazy as _


class Standing(models.IntegerChoices):
    """An Eve Online standing."""

    EXCELLENT = 10, _("excellent standing")
    GOOD = 5, _("good standing")
    NEUTRAL = 0, _("neutral standing")
    BAD = -5, _("bad standing")
    TERRIBLE = -10, _("terrible standing")

    @classmethod
    def from_value(cls, value: float) -> "Standing":
        """Create new objects from standing number."""
        if value > 5:
            return cls.EXCELLENT

        if 5 >= value > 0:
            return cls.GOOD

        if value == 0:
            return cls.NEUTRAL

        if 0 > value >= -5:
            return cls.BAD

        return cls.TERRIBLE


def calc_effective_standing(
    unadjusted_standing, skill_level, skill_modifier, max_possible_standing
):
    """Calculate effective after applying skill."""
    effective_standing = unadjusted_standing + (
        (max_possible_standing - unadjusted_standing) * skill_modifier * skill_level
    )
    return effective_standing
