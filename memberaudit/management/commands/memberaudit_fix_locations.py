import math
from typing import List, Set

from tqdm import tqdm

from django.core.management.base import BaseCommand

from allianceauth.services.hooks import get_extension_logger
from app_utils.helpers import chunks
from app_utils.logging import LoggerAddTag

from memberaudit import __title__, tasks
from memberaudit.constants import IS_TESTING
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

logger = LoggerAddTag(get_extension_logger(__name__), __title__)

# [ ] Fix major performance issue of this script or find alternative solution (e.g. run as task?)
# [x] Add ability to conduct mass test in dev environment to tune performance of this script
# [ ] Maybe deliver fix w/o script first? Need to mark invalid locations with a migration, then exclude from asset update and others


class Command(BaseCommand):
    help = "Remove invalid locations and corrupted data caused by issue #153"

    def add_arguments(self, parser):
        parser.add_argument(
            "--noinput",
            "--no-input",
            action="store_true",
            help="Do NOT prompt the user for input of any kind.",
        )

        parser.add_argument(
            "--batch-size",
            default=100,
            help="Maximum number of locations fixed per batch run",
        )

    def handle(self, *args, **options):
        self.stdout.write("Looking for invalid locations...")
        invalid_location_ids = self._find_invalid_locations()

        if not invalid_location_ids:
            self.stdout.write(self.style.SUCCESS("No invalid locations found."))
            return

        if not options["noinput"]:
            self.stdout.write(
                f"This command will remove {len(invalid_location_ids):,} "
                "invalid locations "
                "and fix related character data corruption caused by issue #153. "
                "Details will be logged to the extensions log."
            )
            self.stdout.write("This process can take a while to complete.")
            user_input = get_input("Are you sure you want to proceed (Y/n)?")
        else:
            user_input = "y"

        if user_input.lower() == "n":
            self.stdout.write(self.style.WARNING("Aborted"))
            return

        self.stdout.write("")

        character_pks_all = self._fix_data_corruption_and_remove_invalid_locations(
            invalid_location_ids, options["batch_size"]
        )

        characters_updateable_pks = self._identify_updateable_characters(
            character_pks_all
        )

        if not characters_updateable_pks:
            self.stdout.write(self.style.SUCCESS("Done"))
            return

        self.stdout.write(
            f"Data for up to {len(characters_updateable_pks):,} characters may "
            "have been disrupted by invalid locations."
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
            msg = (
                "Immediate updates has been started for "
                f"{len(characters_updateable_pks):,} characters."
            )
            logger.info(msg)
            self.stdout.write(msg)

        else:
            self.stdout.write(
                "Characters will be updated with the next regular update."
            )

        self.stdout.write(self.style.SUCCESS("Done"))

    def _fix_data_corruption_and_remove_invalid_locations(
        self, invalid_location_ids: List[int], batch_size: int
    ) -> Set[int]:
        invalid_location_count = len(invalid_location_ids)
        logger.info(
            "Started fixing %d invalid locations with batch size %d",
            invalid_location_count,
            batch_size,
        )

        unknown_location, _ = Location.objects.get_or_create_unknown_location()  # type: ignore
        character_pks_all = set()
        batch_count = math.ceil(invalid_location_count / batch_size)

        for location_ids_chunk in tqdm(
            chunks(invalid_location_ids, batch_size),
            desc="Fixing locations",
            total=batch_count,
            leave=False,
            unit_scale=batch_size,
            disable=IS_TESTING,
        ):
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
            locations_chunk = Location.objects.filter(id__in=location_ids_chunk)
            locations_chunk._raw_delete(locations_chunk.db)  # type: ignore
            logger.info("Deleted %d invalid locations", len(location_ids_chunk))

        msg = (
            f"Fixing complete: Removed {invalid_location_count:,} invalid locations "
            "and related corrupted data"
        )
        logger.info(msg)
        self.stdout.write(msg)
        self.stdout.write("")
        return character_pks_all

    def _find_invalid_locations(self) -> List[int]:
        asset_item_ids = list(CharacterAsset.objects.values_list("item_id", flat=True))
        invalid_locations = Location.objects.filter(id__in=asset_item_ids)
        invalid_location_ids = list(invalid_locations.values_list("id", flat=True))
        return invalid_location_ids

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
        corrupted_objs_count = corrupted_objs.count()
        if not corrupted_objs_count:
            return set()

        character_pks = set(
            corrupted_objs.values_list("character__pk", flat=True).distinct()
        )
        params_update = {field_name: unknown_location}
        corrupted_objs.update(**params_update)
        CharacterUpdateStatus.objects.filter(
            character__pk__in=character_pks, section=section
        ).update(content_hash_1="", content_hash_2="", content_hash_3="")
        logger.info(
            "Fixed %s corrupted %s across %d characters",
            corrupted_objs_count,
            section.label,
            len(character_pks),
        )

        return character_pks

    def _identify_updateable_characters(self, character_pks) -> Set[int]:
        characters_updateable_pks = set(
            Character.objects.filter(
                pk__in=character_pks,
                is_disabled=False,
                eve_character__character_ownership__isnull=False,
            ).values_list("pk", flat=True)
        )
        return characters_updateable_pks

    def _start_character_updates(self, character_pks: Set[int]):
        for character_pk in character_pks:
            for section in [
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

            tasks.update_character_contracts.apply_async(
                kwargs={
                    "character_pk": character_pk,
                    "force_update": True,
                },
                priority=tasks.MEMBERAUDIT_TASKS_LOW_PRIORITY,
            )  # type: ignore
