"""Delete all character section data."""

from tqdm import tqdm

from django.core.management.base import BaseCommand

from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag

from memberaudit import __title__
from memberaudit.constants import IS_TESTING
from memberaudit.helpers import character_section_models
from memberaudit.models import Character
from memberaudit.tasks import update_all_characters

from . import get_input

logger = LoggerAddTag(get_extension_logger(__name__), __title__)


class Command(BaseCommand):
    help = str(__doc__)

    def add_arguments(self, parser):
        parser.add_argument(
            "--reload",
            action="store_true",
            help="Also start reloading",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help=(
                "Delete all character data, incl. from those "
                "which can not be reloaded from ESI"
            ),
        )
        parser.add_argument(
            "--noinput",
            "--no-input",
            action="store_true",
            help="Do NOT prompt the user for input of any kind.",
        )

    def handle(self, *args, **options):
        if options["all"]:
            characters_query = Character.objects.all()
            orphan_text = "are included."
        else:
            characters_query = Character.objects.filter(
                is_disabled=False, eve_character__character_ownership__isnull=False
            )
            orphan_text = "are not included."

        character_count = characters_query.count()
        self.stdout.write(
            f"This will delete the section data for {character_count} characters. "
            f"Orphans and disabled characters {orphan_text}."
        )
        self.stdout.write(
            "All other local data incl. doctrines and the characters themselves will stay intact."
        )
        if options["reload"]:
            self.stdout.write("Will also start the task for reloading all characters.")

        self.stdout.write(
            self.style.NOTICE(
                "Please make sure your supervisors are shut down "
                "before running this command."
            )
        )
        if not options["noinput"]:
            user_input = get_input("Are you sure you want to proceed? (y/N)?")
        else:
            user_input = "y"

        if user_input.lower() != "y":
            self.stdout.write(self.style.WARNING("Aborted"))
            return

        logger.info(
            "Running command reset_characters for %s characters.", character_count
        )
        section_models = character_section_models()
        for character in tqdm(
            characters_query.iterator(),
            desc="Deleting characters",
            total=character_count,
            disable=IS_TESTING,
        ):
            for model_class in section_models:
                if hasattr(model_class, "character"):
                    model_class.objects.filter(character=character).delete()

        if options["reload"]:
            update_all_characters.delay(force_update=True, ignore_stale=True)
            self.stdout.write("Started task to reload all character data")

        self.stdout.write(self.style.SUCCESS("Done"))
