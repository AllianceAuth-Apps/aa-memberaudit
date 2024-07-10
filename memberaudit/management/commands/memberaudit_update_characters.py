"""Start update for updateable characters."""

from tqdm import tqdm

from django.core.management.base import BaseCommand, CommandError

from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag

from memberaudit import __title__, tasks
from memberaudit.constants import IS_TESTING
from memberaudit.models import Character

logger = LoggerAddTag(get_extension_logger(__name__), __title__)


class Command(BaseCommand):
    help = str(__doc__)

    def add_arguments(self, parser):
        parser.add_argument("sections", nargs="*", help="sections to update")
        parser.add_argument(
            "--all",
            action="store_true",
            help="Update all sections",
        )

        parser.add_argument(
            "--noinput",
            "--no-input",
            action="store_true",
            help="Do NOT prompt the user for input of any kind",
        )

    def handle(self, *args, **options):
        updateable_characters = Character.objects.filter(
            is_disabled=False,
            eve_character__character_ownership__isnull=False,
        )

        if options["all"]:
            selected_sections = Character.UpdateSection.enabled_sections()

        elif options["sections"]:
            selected_sections = []
            for section_name in options["sections"]:
                try:
                    selected_sections.append(Character.UpdateSection(section_name))
                except ValueError:
                    raise CommandError(
                        f"'{section_name}' is not a valid section"
                    ) from None

        else:
            raise CommandError("You must specify which sections to update.")

        sections_text = ", ".join(
            sorted(str(section.label) for section in selected_sections)
        )
        updatable_count = updateable_characters.count()
        all_count = Character.objects.count()
        self.stdout.write(
            f"{updatable_count} of {all_count} character are currently updateable "
            "(i.e. are not disabled or orphans)."
        )
        self.stdout.write(
            "Are you sure you want to start updating the following sections "
            "for these characters: "
        )
        self.stdout.write(f"{sections_text}? ", ending="")
        answer = input("[Y/n]") if not options["noinput"] else "y"
        if answer.lower() == "n":
            self.stdout.write(self.style.WARNING("Aborted"))
            return

        for character in tqdm(
            updateable_characters,
            desc="Starting update tasks",
            total=updatable_count,
            leave=False,
            disable=IS_TESTING,
            unit="character",
        ):
            for section in selected_sections:
                task_name = f"update_character_{section.value}"
                task = getattr(tasks, task_name)
                task.apply_async(
                    kwargs={"character_pk": character.pk, "force_update": True},
                    priority=tasks.MEMBERAUDIT_TASKS_LOW_PRIORITY,
                )

        msg = (
            f"Started forced update of {sections_text} for {updatable_count} characters"
        )
        logger.info(msg)
        self.stdout.write(msg)
        self.stdout.write(self.style.SUCCESS("Done"))
