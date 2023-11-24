import math
from typing import List, Set

from django.core.management.base import BaseCommand
from django.db.models import QuerySet

from app_utils.helpers import chunks

from memberaudit import tasks
from memberaudit.app_settings import MEMBERAUDIT_BULK_METHODS_BATCH_SIZE
from memberaudit.models import (
    Character,
    CharacterAsset,
    CharacterContract,
    CharacterJumpClone,
    CharacterLocation,
    CharacterUpdateStatus,
    CharacterWalletTransaction,
    Location,
)

from . import get_input

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

        characters_updateable_pks = self._identify_updateable_characters(
            character_pks_all
        )

        if not characters_updateable_pks:
            self.stdout.write(self.style.SUCCESS("Done"))
            return

        self.stdout.write(
            f"Data for up to {len(characters_updateable_pks):,} characters may have been "
            "disrupted by invalid locations."
        )
        if not options["noinput"]:
            self.stdout.write(
                "Do you want to (s)tart an immediate update for these characters?"
            )
            self.stdout.write(
                "Or do you want to (w)ait for the update to happen "
                "with the regular schedule?"
            )
            user_input = get_input("(S/w)?")
        else:
            user_input = "s"

        if user_input.lower() != "w":
            self._start_character_updates(characters_updateable_pks)
        else:
            self.stdout.write("Character will be updated with the next regular update.")

        self.stdout.write(self.style.SUCCESS("Done"))

    def _identify_updateable_characters(self, character_pks) -> Set[int]:
        characters_updateable_pks = set(
            Character.objects.filter(
                pk__in=character_pks,
                is_disabled=False,
                eve_character__character_ownership__isnull=False,
            ).values_list("pk", flat=True)
        )
        return characters_updateable_pks

    def _fix_data_corruption_and_remove_invalid_locations(
        self, invalid_locations: QuerySet[Location]
    ) -> Set[int]:
        invalid_location_ids = list(invalid_locations.values_list("id", flat=True))
        invalid_location_count = len(invalid_location_ids)
        self.stdout.write(f"Found {invalid_location_count:,} invalid locations.")
        self.stdout.write("")

        unknown_location, _ = Location.objects.get_or_create_unknown_location()  # type: ignore
        character_pks_all = set()
        batch_count = math.ceil(invalid_location_count / BATCH_SIZE)
        for batch_num, location_ids_chunk in enumerate(
            chunks(invalid_location_ids, BATCH_SIZE), start=1
        ):
            if batch_count > 1:
                self.stdout.write(f"Batch {batch_num} / {batch_count}")

            character_pks_all = character_pks_all.union(
                self._fix_corrupted_character_section(
                    location_ids=location_ids_chunk,
                    unknown_location=unknown_location,
                    section=Character.UpdateSection.ASSETS,
                    model_class=CharacterAsset,
                )
            )
            character_pks_all = character_pks_all.union(
                self._fix_corrupted_character_section(
                    location_ids=location_ids_chunk,
                    unknown_location=unknown_location,
                    section=Character.UpdateSection.JUMP_CLONES,
                    model_class=CharacterJumpClone,
                )
            )
            character_pks_all = character_pks_all.union(
                self._fix_corrupted_character_section(
                    location_ids=location_ids_chunk,
                    unknown_location=unknown_location,
                    section=Character.UpdateSection.CONTRACTS,
                    model_class=CharacterContract,
                    field_name="start_location",
                )
            )
            character_pks_all = character_pks_all.union(
                self._fix_corrupted_character_section(
                    location_ids=location_ids_chunk,
                    unknown_location=unknown_location,
                    section=Character.UpdateSection.CONTRACTS,
                    model_class=CharacterContract,
                    field_name="end_location",
                )
            )
            character_pks_all = character_pks_all.union(
                self._fix_corrupted_character_section(
                    location_ids=location_ids_chunk,
                    unknown_location=unknown_location,
                    section=Character.UpdateSection.LOCATION,
                    model_class=CharacterLocation,
                )
            )
            character_pks_all = character_pks_all.union(
                self._fix_corrupted_character_section(
                    location_ids=location_ids_chunk,
                    unknown_location=unknown_location,
                    section=Character.UpdateSection.WALLET_TRANSACTIONS,
                    model_class=CharacterWalletTransaction,
                )
            )

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

    def _fix_corrupted_character_section(
        self,
        location_ids: List[int],
        unknown_location: Location,
        section: Character.UpdateSection,
        model_class: type,
        field_name: str = "location",
    ) -> Set[int]:
        params_filter = {f"{field_name}__in": location_ids}
        corrupted_objs = model_class.objects.filter(**params_filter)  # type: ignore
        if not corrupted_objs.exists():
            return set()

        character_pks = set(
            corrupted_objs.values_list("character__pk", flat=True).distinct()
        )
        self.stdout.write(
            f"Fixing {corrupted_objs.count():,} corrupted {section.label} "
            f"across {len(character_pks):,} characters...."
        )
        params_update = {field_name: unknown_location}
        corrupted_objs.update(**params_update)

        self.stdout.write(
            f"Marking {len(character_pks):,} characters "
            f"for needing an {section.label} update."
        )
        CharacterUpdateStatus.objects.filter(
            character__pk__in=character_pks, section=section
        ).update(content_hash_1="", content_hash_2="", content_hash_3="")

        return character_pks

    def _start_character_updates(self, character_pks: Set[int]):
        for character_pk in character_pks:
            for section in [
                Character.UpdateSection.CONTRACTS,
                Character.UpdateSection.LOCATION,
                Character.UpdateSection.JUMP_CLONES,
                Character.UpdateSection.WALLET_TRANSACTIONS,
            ]:
                tasks.update_character_section.apply_async(
                    kwargs={
                        "character_pk": character_pk,
                        "section": section,
                        "force_update": True,
                    },
                    priority=tasks.MEMBERAUDIT_TASKS_LOW_PRIORITY,
                )  # type: ignore

            tasks.update_character_assets.apply_async(
                kwargs={
                    "character_pk": character_pk,
                    "force_update": True,
                },
                priority=tasks.MEMBERAUDIT_TASKS_LOW_PRIORITY,
            )  # type: ignore

        self.stdout.write(
            "Immediate updates has been started for "
            f"{len(character_pks):,} characters."
        )
