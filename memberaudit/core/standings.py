from django.db import models
from django.utils.translation import gettext_lazy as _


class Standing(models.IntegerChoices):
    EXCELLENT = 10, _("excellent standing")
    GOOD = 5, _("good standing")
    NEUTRAL = 0, _("neutral standing")
    BAD = -5, _("bad standing")
    TERRIBLE = -10, _("terrible standing")

    @classmethod
    def from_value(cls, value: float) -> "Standing":
        if value > 5:
            return cls.EXCELLENT

        if 5 >= value > 0:
            return cls.GOOD

        if value == 0:
            return cls.NEUTRAL

        if 0 > value >= -5:
            return cls.BAD

        return cls.TERRIBLE
