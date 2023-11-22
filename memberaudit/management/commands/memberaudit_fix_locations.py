from django.core.management.base import BaseCommand

from memberaudit import tasks
from memberaudit.models import (
    Character,
    CharacterAsset,
    CharacterUpdateStatus,
    Location,
)

from . import get_input


class Command(BaseCommand):
    help = "Remove invalid locations caused by issue #153"

    def add_arguments(self, parser):
        parser.add_argument(
            "--noinput",
            "--no-input",
            action="store_true",
            help="Do NOT prompt the user for input of any kind.",
        )

    def handle(self, *args, **options):
        self.stdout.write("Looking for invalid locations...")
        asset_item_ids = list(CharacterAsset.objects.values_list("item_id", flat=True))
        invalid_locations = Location.objects.filter(id__in=asset_item_ids)

        if not invalid_locations.exists():
            self.stdout.write(self.style.SUCCESS("No invalid locations found."))
            return

        invalid_assets = CharacterAsset.objects.filter(location__in=invalid_locations)
        character_pks = set(
            CharacterAsset.objects.values_list("character__pk", flat=True).distinct()
        )
        if not options["noinput"]:
            self.stdout.write(
                f"This command will fix {invalid_assets.count():,} corrupted assets "
                f"across {len(character_pks):,} characters "
                f"and remove {invalid_locations.count():,} invalid locations "
                "caused by issue #154."
            )
            user_input = get_input("Are you sure you want to proceed (y/N)?")
        else:
            user_input = "y"

        if user_input.lower() != "y":
            self.stdout.write(self.style.WARNING("Aborted"))
            return

        self.stdout.write("Fixing corrupted data...")
        unknown_location, _ = Location.objects.get_or_create_unknown_location()
        invalid_assets.update(location=unknown_location)
        invalid_locations.delete()
        CharacterUpdateStatus.objects.filter(
            character__pk__in=character_pks, section=Character.UpdateSection.ASSETS
        ).update(content_hash_1="")
        self.stdout.write(self.style.SUCCESS("Corrupted data removed."))
        self.stdout.write()

        characters_updateable_pks = set(
            Character.objects.filter(
                pk__in=character_pks,
                is_disabled=False,
                eve_character__character_ownership__isnull=False,
            ).values_list("pk", flat=True)
        )
        self.stdout.write(
            "The character's asset data may have been damaged by the data corruption."
        )
        self.stdout.write(
            "This data can be restored from ESI for "
            f"{len(characters_updateable_pks):,} affected characters."
        )
        if not options["noinput"]:
            self.stdout.write(
                "Do you want to start the tasks now, "
                "to conduct an immediate asset update for these characters? "
            )
            user_input = get_input(
                "Otherwise the assets will be automatically "
                "updated with the next regular character update. (y/N)?"
            )
        else:
            user_input = "y"

        if user_input.lower() == "y":
            for character_pk in characters_updateable_pks:
                tasks.update_character_assets.apply_async(
                    kwargs={"character_pk": character_pk, "force_update": True},
                    priority=tasks.MEMBERAUDIT_TASKS_LOW_PRIORITY,
                )

            self.stdout.write(
                "Asset update has been started for "
                f"{len(characters_updateable_pks):,} characters."
            )

        self.stdout.write(self.style.SUCCESS("Done"))
