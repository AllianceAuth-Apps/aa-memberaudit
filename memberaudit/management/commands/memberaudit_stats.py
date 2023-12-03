"""Return current statistics about Member Audit."""

import json
import logging

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.core.serializers.json import DjangoJSONEncoder

from app_utils.logging import LoggerAddTag

from memberaudit import __title__, app_settings
from memberaudit.models import (
    Character,
    CharacterAsset,
    CharacterContact,
    CharacterContract,
    CharacterMail,
    SkillSet,
    SkillSetGroup,
)

logger = LoggerAddTag(logging.getLogger(__name__), __title__)


class Command(BaseCommand):
    help = __doc__

    def handle(self, *args, **options):
        stats = calc_statistics()
        stats_out = json.dumps(
            stats,
            sort_keys=True,
            indent=4,
            ensure_ascii=False,
            cls=DjangoJSONEncoder,
        )
        self.stdout.write(stats_out)


def calc_statistics() -> dict:
    """Return detailed statistics about Member Audit."""

    user_count = (
        User.objects.filter(
            character_ownerships__character__memberaudit_character__isnull=False
        )
        .distinct()
        .count()
    )

    return {
        "app_totals": {
            "users_count": user_count,
            "characters_count": Character.objects.count(),
            "skill_set_groups_count": SkillSetGroup.objects.count(),
            "skill_sets_count": SkillSet.objects.count(),
            "assets_count": CharacterAsset.objects.count(),
            "mails_count": CharacterMail.objects.count(),
            "contacts_count": CharacterContact.objects.count(),
            "contracts_count": CharacterContract.objects.count(),
        },
        "settings": _fetch_settings(),
    }


def _fetch_settings():
    settings = {
        name: value
        for name, value in vars(app_settings).items()
        if name.startswith("MEMBERAUDIT_")
    }
    return settings
