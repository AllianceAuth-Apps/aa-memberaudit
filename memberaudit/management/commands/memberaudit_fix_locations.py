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
        # Valid locations IDs do not have an asset item with the same ID
        data = CharacterAsset.objects.values("item_id", "location_id")
        asset_item_ids = {obj["item_id"] for obj in data}
        asset_location_ids = {obj["location_id"] for obj in data}
        valid_asset_location_ids = asset_location_ids - asset_item_ids

        # Location which are references by items on other sections are also valid
        invalid_locations = (
            Location.objects.exclude(id__in=valid_asset_location_ids)
            .exclude(contract_start_location__isnull=False)
            .exclude(contract_end_location__isnull=False)
            .exclude(characterlocation__isnull=False)
            .exclude(characterjumpclone__isnull=False)
            .exclude(characterwallettransaction__isnull=False)
            .exclude(id=Location.LOCATION_UNKNOWN_ID)
        )

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

        self.stdout.write("Applying changes...")
        unknown_location, _ = Location.objects.get_or_create_unknown_location()
        invalid_assets.update(location=unknown_location)
        invalid_locations.delete()
        CharacterUpdateStatus.objects.filter(
            character__pk__in=character_pks, section=Character.UpdateSection.ASSETS
        ).update(content_hash_1="")
        self.stdout.write("Fixing complete")
        self.stdout.write(
            f"The assets of {len(character_pks):,} characters have "
            "been corrupted and need to be updated from ESI."
        )
        if not options["noinput"]:
            user_input = get_input(
                "Do you want to trigger the update tasks now? Otherwise the updates will "
                "run with the next scheduled periodic update. (y/N)?"
            )
        else:
            user_input = "y"

        if user_input.lower() == "y":
            for character_pk in character_pks:
                tasks.update_character_assets.apply_async(
                    kwargs={"character_pk": character_pk, "force_update": True},
                    priority=tasks.MEMBERAUDIT_TASKS_LOW_PRIORITY,
                )

            self.stdout.write(
                f"Asset update has been triggered for {len(character_pks):,} characters."
            )

        self.stdout.write(self.style.SUCCESS("Done"))
