from typing import List, Set

from django.core.management.base import BaseCommand
from django.db.models import QuerySet

from app_utils.helpers import chunks

from memberaudit import tasks
from memberaudit.app_settings import MEMBERAUDIT_BULK_METHODS_BATCH_SIZE
from memberaudit.models import (
    Character,
    CharacterAsset,
    CharacterJumpClone,
    CharacterUpdateStatus,
    Location,
)

from . import get_input

# [x]: Make updates in chunks
# [x]: Add logic for removing invalid locations also from characterasset_set
# [x]: Add logic for removing invalid locations also from characterjumpclone_set
# [ ]: Add logic for removing invalid locations also from characterlocation_set
# [ ]: Add logic for removing invalid locations also from characterwallettransaction_set
# [ ]: Add logic for removing invalid locations also from contract_start_location and contract_end_location

BATCH_SIZE = MEMBERAUDIT_BULK_METHODS_BATCH_SIZE


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
        if not options["noinput"]:
            self.stdout.write(
                "This command will fix corrupted character assets and remove "
                "invalid locations caused by issue #153."
            )
            self.stdout.write(
                "Please note that this process can take a couple of minutes to complete. "
            )
            user_input = get_input("Are you sure you want to proceed (Y/n)?")
        else:
            user_input = "y"

        if user_input.lower() == "n":
            self.stdout.write(self.style.WARNING("Aborted"))
            return

        self.stdout.write("")
        self.stdout.write("Looking for invalid locations...")
        invalid_locations = self._find_invalid_locations()

        if not invalid_locations.exists():
            self.stdout.write(self.style.SUCCESS("No invalid locations found."))
            return

        character_pks_all = self._fix_data_corruption_and_remove_invalid_locations(
            invalid_locations
        )

        self.stdout.write(
            f"Data for up to {len(character_pks_all):,} characters may have been "
            "disrupted by invalid locations."
        )
        if not options["noinput"]:
            self.stdout.write(
                "Do you want to start an immediate update for these characters (s)?"
            )
            self.stdout.write(
                "Or do you want to wait for the update to happen "
                "with the regular schedule (w)?"
            )
            user_input = get_input("(S/w)?")
        else:
            user_input = "s"

        if user_input.lower() != "w":
            self._start_character_updates(character_pks_all)
        else:
            self.stdout.write("Character will be updated with the next regular update.")

        self.stdout.write(self.style.SUCCESS("Done"))

    def _fix_data_corruption_and_remove_invalid_locations(
        self, invalid_locations: QuerySet[Location]
    ) -> Set[int]:
        invalid_location_ids = list(invalid_locations.values_list("id", flat=True))
        self.stdout.write(f"Found {len(invalid_location_ids):,} invalid locations.")

        unknown_location, _ = Location.objects.get_or_create_unknown_location()  # type: ignore
        character_pks_all = set()
        batch_count = (
            len(invalid_location_ids) / BATCH_SIZE
            + len(invalid_location_ids) % BATCH_SIZE
        )
        for batch_num, location_ids_chunk in enumerate(
            chunks(invalid_location_ids, BATCH_SIZE), start=1
        ):
            self.stdout.write(f"Batch {batch_num} / {batch_count}")

            character_pks_for_assets_chunk = self._fixing_assets(
                location_ids_chunk, unknown_location
            )
            character_pks_all = character_pks_all.union(character_pks_for_assets_chunk)

            character_pks_for_clones_chunk = self._fixing_implants(
                location_ids_chunk, unknown_location
            )
            character_pks_all = character_pks_all.union(character_pks_for_clones_chunk)

            self.stdout.write(
                f"Deleting {len(location_ids_chunk):,} invalid locations..."
            )
            invalid_locations.delete()

        self.stdout.write(self.style.SUCCESS("Corrupted data removed."))
        self.stdout.write("")
        return character_pks_all

    def _find_invalid_locations(self) -> QuerySet[Location]:
        asset_item_ids = list(CharacterAsset.objects.values_list("item_id", flat=True))
        invalid_locations = Location.objects.filter(id__in=asset_item_ids)
        return invalid_locations

    def _fixing_assets(
        self, location_ids_chunk: List[int], unknown_location: Location
    ) -> Set[int]:
        invalid_assets = CharacterAsset.objects.filter(
            location_id__in=location_ids_chunk
        )
        if not invalid_assets.exists():
            return set()

        character_pks_for_assets_chunk = set(
            invalid_assets.values_list("character__pk", flat=True).distinct()
        )
        self.stdout.write(
            f"Fixing {invalid_assets.count():,} corrupted assets "
            f"across {len(character_pks_for_assets_chunk):,} characters...."
        )
        invalid_assets.update(location=unknown_location)

        self._marking_characters_for_update(
            character_pks_for_assets_chunk, Character.UpdateSection.ASSETS
        )
        return character_pks_for_assets_chunk

    def _fixing_implants(
        self, location_ids_chunk: List[int], unknown_location: Location
    ) -> Set[int]:
        invalid_clones = CharacterJumpClone.objects.filter(
            location_id__in=location_ids_chunk
        )
        if not invalid_clones.exists():
            return set()

        character_pks = set(
            invalid_clones.values_list("character__pk", flat=True).distinct()
        )
        self.stdout.write(
            f"Fixing {invalid_clones.count():,} corrupted jump clones "
            f"across {len(character_pks):,} characters...."
        )
        invalid_clones.update(location=unknown_location)

        self._marking_characters_for_update(
            character_pks, Character.UpdateSection.JUMP_CLONES
        )
        return character_pks

    def _marking_characters_for_update(
        self, character_pks: Set[int], section: Character.UpdateSection
    ):
        self.stdout.write(
            f"Marking {len(character_pks):,} characters "
            f"for needing an {section.label} update."
        )
        CharacterUpdateStatus.objects.filter(
            character__pk__in=character_pks, section=section
        ).update(content_hash_1="", content_hash_2="", content_hash_3="")

    def _start_character_updates(self, character_pks: Set[int]):
        characters_updateable_pks = list(
            Character.objects.filter(
                pk__in=character_pks,
                is_disabled=False,
                eve_character__character_ownership__isnull=False,
            ).values_list("pk", flat=True)
        )
        for character_pk in characters_updateable_pks:
            tasks.update_character_assets.apply_async(
                kwargs={"character_pk": character_pk, "force_update": True},
                priority=tasks.MEMBERAUDIT_TASKS_LOW_PRIORITY,
            )  # type: ignore
            tasks.update_character_section.apply_async(
                kwargs={
                    "character_pk": character_pk,
                    "section": Character.UpdateSection.JUMP_CLONES,
                    "force_update": True,
                },
                priority=tasks.MEMBERAUDIT_TASKS_LOW_PRIORITY,
            )  # type: ignore

        self.stdout.write(
            "Immediate updates has been started for "
            f"{len(characters_updateable_pks):,} characters."
        )
