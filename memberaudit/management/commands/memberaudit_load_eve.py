from django.core.management import call_command
from django.core.management.base import BaseCommand

from allianceauth.services.hooks import get_extension_logger

from memberaudit import __title__
from memberaudit.constants import EveCategoryId

logger = get_extension_logger(__name__)


class Command(BaseCommand):
    help = "Preloads data required for this app from ESI"

    def handle(self, *args, **options):
        call_command(
            "eveuniverse_load_types",
            __title__,
            "--category_id_with_dogma",
            str(EveCategoryId.BLUEPRINT.value),
            "--category_id_with_dogma",
            str(EveCategoryId.SHIP.value),
            "--category_id_with_dogma",
            str(EveCategoryId.MODULE.value),
            "--category_id_with_dogma",
            str(EveCategoryId.CHARGE.value),
            "--category_id_with_dogma",
            str(EveCategoryId.SKILL.value),
            "--category_id_with_dogma",
            str(EveCategoryId.DRONE.value),
            "--category_id_with_dogma",
            str(EveCategoryId.IMPLANT.value),
            "--category_id_with_dogma",
            str(EveCategoryId.FIGHTER.value),
            "--category_id_with_dogma",
            str(EveCategoryId.SUBSYSTEM.value),
            "--category_id",
            str(EveCategoryId.STRUCTURE.value),
        )
