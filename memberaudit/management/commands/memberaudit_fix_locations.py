import math
from dataclasses import dataclass, field
from typing import List, Set

from tqdm import tqdm

from django.core.management.base import BaseCommand
from django.db import DatabaseError

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

DEFAULT_BATCH_SIZE_FETCH = 10_000
DEFAULT_BATCH_SIZE_UPDATE = 100

logger = LoggerAddTag(get_extension_logger(__name__), __title__)


@dataclass
class CharacterPkContainer:
    """Container for character PKs."""

    assets: Set[int] = field(default_factory=set)
    clones: Set[int] = field(default_factory=set)
    contracts: Set[int] = field(default_factory=set)
    locations: Set[int] = field(default_factory=set)
    transactions: Set[int] = field(default_factory=set)

    def __bool__(self) -> bool:
        return (
            bool(self.assets)
            or bool(self.clones)
            or bool(self.contracts)
            or bool(self.locations)
            or bool(self.transactions)
        )

    def __len__(self) -> int:
        return len(self.all())

    def all(self) -> Set[int]:
        """Return all character PKs."""
        return (
            self.assets
            | self.clones
            | self.contracts
            | self.locations
            | self.transactions
        )


class Command(BaseCommand):
    help = "Remove invalid locations and corrupted data caused by issue #153"

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size-fetch",
            type=int,
            default=DEFAULT_BATCH_SIZE_FETCH,
            help="Maximum number of invalid locations fetched per batch",
        )

        parser.add_argument(
            "--batch-size-update",
            type=int,
            default=DEFAULT_BATCH_SIZE_UPDATE,
            help="Maximum number of invalid locations fixed per batch",
        )

        parser.add_argument(
            "--noinput",
            "--no-input",
            action="store_true",
            help="Do NOT prompt the user for input of any kind",
        )

        parser.add_argument(
            "--verbose-log",
            action="store_true",
            help="Log additional details",
        )

        parser.add_argument(
            "--exclude-locations",
            nargs="+",
            type=int,
            help="Exclude locations given by their IDs",
        )

    def handle(self, *args, **options):
        logger.info("Started command for fixing invalid locations")

        batch_size = options["batch_size_fetch"]
        exclude_location_ids = (
            set(options["exclude_locations"]) if options["exclude_locations"] else set()
        )
        is_verbose_log = options["verbose_log"]

        invalid_location_ids = find_invalid_locations(
            batch_size=batch_size,
            exclude_location_ids=exclude_location_ids,
            is_verbose_log=is_verbose_log,
        )

        if not invalid_location_ids:
            self.stdout.write(self.style.SUCCESS("No invalid locations found"))
            return

        if not options["noinput"]:
            self.stdout.write(
                f"This command will remove {len(invalid_location_ids):,} "
                "invalid locations "
                "and fix related character data corruption caused by issue #153. "
                "Details will be logged to the extensions log"
            )
            self.stdout.write("This process can take a while to complete")
            user_input = get_input("Are you sure you want to proceed (Y/n)?")
        else:
            user_input = "y"

        if user_input.lower() == "n":
            self.stdout.write(self.style.WARNING("Aborted"))
            return

        self.stdout.write("")

        character_pks_all = self._fix_data_corruption_and_remove_invalid_locations(
            invalid_location_ids, options
        )

        remaining_invalid_location_ids = find_invalid_locations(
            batch_size=batch_size,
            exclude_location_ids=exclude_location_ids,
            is_verbose_log=is_verbose_log,
        )
        self.stdout.write(
            f"{len(remaining_invalid_location_ids)} invalid locations remaining"
        )

        characters_updateable_pks = identify_updateable_characters(
            character_pks=character_pks_all, is_verbose_log=is_verbose_log
        )

        if not characters_updateable_pks:
            self.stdout.write(self.style.SUCCESS("Done"))
            return

        self.stdout.write(
            f"Data for up to {len(characters_updateable_pks):,} characters may "
            "have been disrupted by invalid locations"
        )
        if not options["noinput"]:
            self.stdout.write(
                "Do you want to (s)tart an immediate update for these characters?"
            )
            self.stdout.write(
                "Or do you want to (w)ait for the update to happen "
                "with the regular schedule?"
            )
            user_input = get_input("(s/W)?")
        else:
            user_input = "s"

        if user_input.lower() == "s":
            start_character_updates(characters_updateable_pks)
            msg = (
                "Immediate updates has been started for "
                f"{len(characters_updateable_pks):,} characters"
            )
            logger.info(msg)
            self.stdout.write(msg)

        else:
            self.stdout.write("Characters will be updated with the next regular update")

        self.stdout.write(self.style.SUCCESS("Done"))

    def _fix_data_corruption_and_remove_invalid_locations(
        self, invalid_location_ids: List[int], options: dict
    ) -> CharacterPkContainer:
        invalid_location_count = len(invalid_location_ids)
        batch_size: int = options["batch_size_update"]
        logger.info(
            "Started fixing %d invalid locations (batch size: %d)",
            invalid_location_count,
            batch_size,
        )

        unknown_location, _ = Location.objects.get_or_create_unknown_location()  # type: ignore
        character_pks = CharacterPkContainer()
        batch_count = math.ceil(invalid_location_count / batch_size)
        removed_location_ids = []
        error_count = 0

        for location_ids_chunk in tqdm(
            chunks(invalid_location_ids, size=batch_size),
            desc="Fixing locations",
            total=batch_count,
            leave=False,
            unit_scale=batch_size,
            disable=IS_TESTING,
        ):
            is_success = fix_invalid_locations(
                location_ids=location_ids_chunk,
                character_pks=character_pks,
                unknown_location=unknown_location,
                is_verbose_log=options["verbose_log"],
            )
            if is_success:
                removed_location_ids += location_ids_chunk
            else:
                error_count += 1

        msg = (
            f"Process completed: Removed {len(removed_location_ids):,} "
            "invalid locations and repaired related character data"
        )
        logger.info(msg)
        self.stdout.write(msg)

        if error_count:
            msg = f"{error_count:,} errors occurred. Please check logs for details"
            self.stdout.write(self.style.ERROR(msg))
            logger.warning(msg)

        self.stdout.write("")
        return character_pks


def find_invalid_locations(
    batch_size: int, exclude_location_ids: Set[int], is_verbose_log: bool
) -> List[int]:
    """Return IDs of invalid locations.
    An empty list means no invalid locations where found.
    """
    asset_item_ids = set(CharacterAsset.objects.values_list("item_id", flat=True))
    if exclude_location_ids:
        asset_item_ids -= set(exclude_location_ids)
        logger.info("Ignoring location IDs: %s", exclude_location_ids)

    asset_items_count = len(asset_item_ids)
    logger.info(
        "Looking for invalid locations among %d asset items (batch size: %d)",
        asset_items_count,
        batch_size,
    )
    batch_count = math.ceil(asset_items_count / batch_size)
    invalid_location_ids = []
    for asset_item_ids_chunk in tqdm(
        chunks(list(asset_item_ids), size=batch_size),
        desc="Finding invalid locations",
        total=batch_count,
        leave=False,
        unit_scale=batch_size,
        disable=IS_TESTING,
    ):
        invalid_location_ids += _find_invalid_locations_chunk(asset_item_ids_chunk)

    invalid_location_ids.sort()

    if is_verbose_log:
        logger.info(
            "Found %d invalid locations: %s",
            len(invalid_location_ids),
            invalid_location_ids,
        )
    else:
        logger.info("Found %d invalid locations", len(invalid_location_ids))

    return invalid_location_ids


def _find_invalid_locations_chunk(asset_item_ids_chunk: List[int]) -> List[int]:
    invalid_locations = Location.objects.filter(id__in=asset_item_ids_chunk)
    invalid_location_ids = list(invalid_locations.values_list("id", flat=True))
    return invalid_location_ids


def fix_invalid_locations(
    location_ids: List[int],
    character_pks: CharacterPkContainer,
    unknown_location: Location,
    is_verbose_log: bool,
) -> bool:
    """Fix corruption in character data and remove invalid locations.

    Return True, when successful, else False.
    """
    try:
        character_pks.assets |= _fix_corrupted_character_section(
            location_ids=location_ids,
            unknown_location=unknown_location,
            section=Character.UpdateSection.ASSETS,
            model_class=CharacterAsset,
            is_verbose_log=is_verbose_log,
        )
        character_pks.clones |= _fix_corrupted_character_section(
            location_ids=location_ids,
            unknown_location=unknown_location,
            section=Character.UpdateSection.JUMP_CLONES,
            model_class=CharacterJumpClone,
            is_verbose_log=is_verbose_log,
        )
        character_pks.contracts |= _fix_corrupted_character_section(
            location_ids=location_ids,
            unknown_location=unknown_location,
            section=Character.UpdateSection.CONTRACTS,
            model_class=CharacterContract,
            field_name="start_location",
            is_verbose_log=is_verbose_log,
        )
        character_pks.contracts |= _fix_corrupted_character_section(
            location_ids=location_ids,
            unknown_location=unknown_location,
            section=Character.UpdateSection.CONTRACTS,
            model_class=CharacterContract,
            field_name="end_location",
            is_verbose_log=is_verbose_log,
        )
        character_pks.locations |= _fix_corrupted_character_section(
            location_ids=location_ids,
            unknown_location=unknown_location,
            section=Character.UpdateSection.LOCATION,
            model_class=CharacterLocation,
            is_verbose_log=is_verbose_log,
        )
        character_pks.transactions |= _fix_corrupted_character_section(
            location_ids=location_ids,
            unknown_location=unknown_location,
            section=Character.UpdateSection.WALLET_TRANSACTIONS,
            model_class=CharacterWalletTransaction,
            is_verbose_log=is_verbose_log,
        )
        locations_chunk = Location.objects.filter(id__in=location_ids)
        locations_chunk._raw_delete(locations_chunk.db)  # type: ignore

    except DatabaseError:
        logger.exception(
            "Failed to remove %d invalid locations. Skipping to next chunk",
            len(location_ids),
        )
        return False

    logger.info("Deleted %d invalid locations", len(location_ids))
    return True


def _fix_corrupted_character_section(
    section: Character.UpdateSection,
    location_ids: List[int],
    unknown_location: Location,
    model_class: type,
    field_name: str = "location",
    is_verbose_log: bool = False,
) -> Set[int]:
    """Entangle locations from a character section of any related characters.

    Return character PKs, when updates where successful, else empty set.
    """
    params_filter = {f"{field_name}__in": location_ids}
    corrupted_objs = model_class.objects.filter(**params_filter)  # type: ignore
    corrupted_objs_count = corrupted_objs.count()
    if not corrupted_objs_count:
        return set()

    character_pks = list(
        sorted(corrupted_objs.values_list("character__pk", flat=True).distinct())
    )
    params_update = {field_name: unknown_location}
    corrupted_objs.update(**params_update)

    CharacterUpdateStatus.objects.filter(
        character__pk__in=character_pks, section=section
    ).update(content_hash_1="", content_hash_2="", content_hash_3="")
    if is_verbose_log:
        logger.info(
            "Removed %d invalid locations from %d corrupted %s across %d characters: %s",
            len(location_ids),
            corrupted_objs_count,
            section.label,
            len(character_pks),
            character_pks,
        )
    else:
        logger.info(
            "Removed %d invalid locations from %d corrupted %s across %d characters",
            len(location_ids),
            corrupted_objs_count,
            section.label,
            len(character_pks),
        )

    return set(character_pks)


def identify_updateable_characters(
    character_pks: CharacterPkContainer, is_verbose_log: bool
) -> CharacterPkContainer:
    """Return selection of character PKs, which can be updated."""
    params = {}
    for section in ["assets", "clones", "contracts", "locations", "transactions"]:
        params[section] = set(
            Character.objects.filter(
                pk__in=getattr(character_pks, section),
                is_disabled=False,
                eve_character__character_ownership__isnull=False,
            ).values_list("pk", flat=True)
        )

    updateable_character_pks = CharacterPkContainer(**params)

    if is_verbose_log:
        logger.info(
            "From %d repaired characters, %d can be updated: %s",
            len(character_pks),
            len(updateable_character_pks),
            updateable_character_pks,
        )
    else:
        logger.info(
            "From %d repaired characters, %d can be updated",
            len(character_pks),
            len(updateable_character_pks),
        )

    return updateable_character_pks


def start_character_updates(character_pks: CharacterPkContainer) -> None:
    """Start character section updates for characters as needed."""
    for character_pk in character_pks.assets:
        tasks.update_character_assets.apply_async(
            kwargs={"character_pk": character_pk, "force_update": True},
            priority=tasks.MEMBERAUDIT_TASKS_LOW_PRIORITY,
        )  # type: ignore

    for character_pk in character_pks.contracts:
        tasks.update_character_contracts.apply_async(
            kwargs={"character_pk": character_pk, "force_update": True},
            priority=tasks.MEMBERAUDIT_TASKS_LOW_PRIORITY,
        )  # type: ignore

    for character_pk in character_pks.clones:
        tasks.update_character_jump_clones.apply_async(
            kwargs={"character_pk": character_pk, "force_update": True},
            priority=tasks.MEMBERAUDIT_TASKS_LOW_PRIORITY,
        )  # type: ignore

    for character_pk in character_pks.locations:
        tasks.update_character_location.apply_async(
            kwargs={"character_pk": character_pk, "force_update": True},
            priority=tasks.MEMBERAUDIT_TASKS_LOW_PRIORITY,
        )  # type: ignore

    for character_pk in character_pks.transactions:
        tasks.update_character_wallet_transactions.apply_async(
            kwargs={"character_pk": character_pk, "force_update": True},
            priority=tasks.MEMBERAUDIT_TASKS_LOW_PRIORITY,
        )  # type: ignore
