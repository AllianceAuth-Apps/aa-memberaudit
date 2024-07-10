"""Celery tasks for Member Audit."""

# pylint: disable=redefined-builtin, too-many-lines

import inspect
import random
from typing import Callable, Iterable, List, Optional

from celery import chain, shared_task

from django.apps import apps
from django.contrib.auth.models import Group, User
from esi.models import Token
from eveuniverse.constants import POST_UNIVERSE_NAMES_MAX_ITEMS
from eveuniverse.models import EveEntity, EveMarketPrice

from allianceauth.notifications import notify
from allianceauth.services.hooks import get_extension_logger
from allianceauth.services.tasks import QueueOnce
from app_utils.esi import EsiErrorLimitExceeded, EsiOffline
from app_utils.logging import LoggerAddTag

from memberaudit import __title__, utils
from memberaudit.app_settings import (
    MEMBERAUDIT_BULK_METHODS_BATCH_SIZE,
    MEMBERAUDIT_SECTION_STALE_MINUTES_GLOBAL_DEFAULT,
    MEMBERAUDIT_TASKS_LOW_PRIORITY,
    MEMBERAUDIT_TASKS_MAX_ASSETS_PER_PASS,
    MEMBERAUDIT_TASKS_NORMAL_PRIORITY,
    MEMBERAUDIT_TASKS_OBJECT_CACHE_TIMEOUT,
    MEMBERAUDIT_TASKS_TIME_LIMIT,
)
from memberaudit.core import data_exporters
from memberaudit.decorators import when_esi_is_available
from memberaudit.helpers import determine_task_priority
from memberaudit.models import (
    Character,
    CharacterAsset,
    CharacterContract,
    ComplianceGroupDesignation,
    General,
    Location,
    MailEntity,
    enabled_sections_by_stale_minutes,
)

logger = LoggerAddTag(get_extension_logger(__name__), __title__)

MAX_RETRIES_DEFAULT = 3
MAX_RETRIES_STRUCTURES = 5
MAX_RETRIES_MAIL_ENTITIES = 5

TASK_DEFAULTS = {
    "time_limit": MEMBERAUDIT_TASKS_TIME_LIMIT,
    "max_retries": MAX_RETRIES_DEFAULT,
}
"""Default params for all tasks."""

TASK_DEFAULTS_BIND = {**TASK_DEFAULTS, **{"bind": True}}
"""Default params for tasks that need access to self."""

TASK_DEFAULTS_ONCE = {**TASK_DEFAULTS, **{"base": QueueOnce}}
"""Default params for tasks that need run once only."""

TASK_DEFAULTS_BIND_ONCE = {**TASK_DEFAULTS, **{"bind": True, "base": QueueOnce}}
"""Default params for tasks that need access to self and run once only."""


@shared_task(**TASK_DEFAULTS_ONCE)
def run_regular_updates() -> None:
    """Run regular updates for Member Audit."""
    update_market_prices.apply_async(priority=MEMBERAUDIT_TASKS_LOW_PRIORITY)
    update_all_characters.apply_async(priority=MEMBERAUDIT_TASKS_LOW_PRIORITY)
    if ComplianceGroupDesignation.objects.exists():
        update_compliance_groups_for_all.apply_async(
            priority=MEMBERAUDIT_TASKS_NORMAL_PRIORITY
        )


@shared_task(**TASK_DEFAULTS_BIND_ONCE)
@when_esi_is_available
def update_all_characters(
    self, force_update: bool = False, ignore_stale: bool = False
) -> None:
    """Update all enabled characters from ESI and disable update for orphans.

    Args:
    - force_update: When set to True will always refresh from data from ESI,
        even if it has not changed
    - ignore_stale: When True, will start updating all sections regardless
        of it's stale status
    """
    Character.objects.disable_characters_with_no_owner()

    # start sync for all enabled characters
    enabled_characters = list(
        Character.objects.filter(is_disabled=False).values_list("pk", flat=True)
    )
    if enabled_characters:
        priority = determine_task_priority(self) or MEMBERAUDIT_TASKS_LOW_PRIORITY
        for character_pk in enabled_characters:
            update_character.apply_async(
                kwargs={
                    "character_pk": character_pk,
                    "force_update": force_update,
                    "ignore_stale": ignore_stale,
                },
                priority=priority,
            )
        logger.info("Started updates for %d characters", len(enabled_characters))

    else:
        logger.info("No enabled characters found for update.")


# Main character update tasks


@shared_task(**TASK_DEFAULTS_BIND_ONCE)
def update_character(
    self, character_pk: int, force_update: bool = False, ignore_stale: bool = False
) -> bool:
    """Update all sections of a character from ESI.

    Args:
    - character_pk: PL of character to update
    - force_update: When set to True will always refresh from data from ESI,
        even if it has not changed
    - ignore_stale: When True, will start updating all sections regardless
        of it's stale status

    Return True when update of sections was started, else False.
    """
    character: Character = Character.objects.prefetch_related("update_status_set").get(
        pk=character_pk
    )
    if character.is_orphan:
        logger.info("%s: Skipping update for orphaned character", character)
        return False

    character.reset_token_error_notified_if_status_ok()
    character.clear_cache()

    character_needs_update = character.calc_update_needed()
    if not ignore_stale and not character_needs_update:
        logger.info("%s: No update required", character)
        return False

    msg = f"{character}: Starting character update ({force_update=}, {ignore_stale=})"
    logger.info(msg)
    priority = determine_task_priority(self) or MEMBERAUDIT_TASKS_LOW_PRIORITY

    for section in enabled_sections_by_stale_minutes():
        if ignore_stale or character_needs_update.for_section(section):
            task_name = f"update_character_{section.value}"
            task = globals()[task_name]
            task.apply_async(
                kwargs={"character_pk": character.pk, "force_update": force_update},
                priority=priority,
            )

    if character.is_shared:
        check_character_consistency.apply_async(
            kwargs={"character_pk": character.pk}, priority=priority
        )

    return True


# Updating sections with simple update logic


_update_character_params = {
    **TASK_DEFAULTS_ONCE,
    **{"once": {"keys": ["character_pk", "force_update"], "graceful": True}},
}


@shared_task(**_update_character_params)
@when_esi_is_available
def update_character_attributes(character_pk: int, force_update: bool) -> None:
    """Update attributes for a character from ESI."""
    _update_character_section(
        character_pk=character_pk,
        section=Character.UpdateSection.ATTRIBUTES,
        force_update=force_update,
    )


@shared_task(**_update_character_params)
@when_esi_is_available
def update_character_character_details(character_pk: int, force_update: bool) -> None:
    """Update character_details for a character from ESI."""
    _update_character_section(
        character_pk=character_pk,
        section=Character.UpdateSection.CHARACTER_DETAILS,
        force_update=force_update,
    )


@shared_task(**_update_character_params)
@when_esi_is_available
def update_character_corporation_history(character_pk: int, force_update: bool) -> None:
    """Update corporation_history for a character from ESI."""
    _update_character_section(
        character_pk=character_pk,
        section=Character.UpdateSection.CORPORATION_HISTORY,
        force_update=force_update,
    )


@shared_task(**_update_character_params)
@when_esi_is_available
def update_character_fw_stats(character_pk: int, force_update: bool) -> None:
    """Update fw_stats for a character from ESI."""
    _update_character_section(
        character_pk=character_pk,
        section=Character.UpdateSection.FW_STATS,
        force_update=force_update,
    )


@shared_task(**_update_character_params)
@when_esi_is_available
def update_character_implants(character_pk: int, force_update: bool) -> None:
    """Update implants for a character from ESI."""
    _update_character_section(
        character_pk=character_pk,
        section=Character.UpdateSection.IMPLANTS,
        force_update=force_update,
    )


@shared_task(**_update_character_params)
@when_esi_is_available
def update_character_jump_clones(character_pk: int, force_update: bool) -> None:
    """Update jump_clones for a character from ESI."""
    _update_character_section(
        character_pk=character_pk,
        section=Character.UpdateSection.JUMP_CLONES,
        force_update=force_update,
    )


@shared_task(**_update_character_params)
@when_esi_is_available
def update_character_location(character_pk: int, force_update: bool) -> None:
    """Update location for a character from ESI."""
    _update_character_section(
        character_pk=character_pk,
        section=Character.UpdateSection.LOCATION,
        force_update=force_update,
    )


@shared_task(**_update_character_params)
@when_esi_is_available
def update_character_loyalty(character_pk: int, force_update: bool) -> None:
    """Update loyalty for a character from ESI."""
    _update_character_section(
        character_pk=character_pk,
        section=Character.UpdateSection.LOYALTY,
        force_update=force_update,
    )


@shared_task(**_update_character_params)
@when_esi_is_available
def update_character_mining_ledger(character_pk: int, force_update: bool) -> None:
    """Update mining_ledger for a character from ESI."""
    _update_character_section(
        character_pk=character_pk,
        section=Character.UpdateSection.MINING_LEDGER,
        force_update=force_update,
    )


@shared_task(**_update_character_params)
@when_esi_is_available
def update_character_online_status(character_pk: int, force_update: bool) -> None:
    """Update online_status for a character from ESI."""
    _update_character_section(
        character_pk=character_pk,
        section=Character.UpdateSection.ONLINE_STATUS,
        force_update=force_update,
    )


@shared_task(**_update_character_params)
@when_esi_is_available
def update_character_planets(character_pk: int, force_update: bool) -> None:
    """Update planets for a character from ESI."""
    _update_character_section(
        character_pk=character_pk,
        section=Character.UpdateSection.PLANETS,
        force_update=force_update,
    )


@shared_task(**_update_character_params)
@when_esi_is_available
def update_character_roles(character_pk: int, force_update: bool) -> None:
    """Update roles for a character from ESI."""
    _update_character_section(
        character_pk=character_pk,
        section=Character.UpdateSection.ROLES,
        force_update=force_update,
    )


@shared_task(**_update_character_params)
@when_esi_is_available
def update_character_ship(character_pk: int, force_update: bool) -> None:
    """Update ship for a character from ESI."""
    _update_character_section(
        character_pk=character_pk,
        section=Character.UpdateSection.SHIP,
        force_update=force_update,
    )


@shared_task(**_update_character_params)
@when_esi_is_available
def update_character_skill_queue(character_pk: int, force_update: bool) -> None:
    """Update skill_queue for a character from ESI."""
    _update_character_section(
        character_pk=character_pk,
        section=Character.UpdateSection.SKILL_QUEUE,
        force_update=force_update,
    )


@shared_task(**_update_character_params)
@when_esi_is_available
def update_character_skill_sets(character_pk: int, force_update: bool) -> None:
    """Update skill_sets for a character from ESI."""
    _update_character_section(
        character_pk=character_pk,
        section=Character.UpdateSection.SKILL_SETS,
        force_update=force_update,
    )


@shared_task(**_update_character_params)
@when_esi_is_available
def update_character_skills(character_pk: int, force_update: bool) -> None:
    """Update skills for a character from ESI."""
    _update_character_section(
        character_pk=character_pk,
        section=Character.UpdateSection.SKILLS,
        force_update=force_update,
    )


@shared_task(**_update_character_params)
@when_esi_is_available
def update_character_standings(character_pk: int, force_update: bool) -> None:
    """Update standings for a character from ESI."""
    _update_character_section(
        character_pk=character_pk,
        section=Character.UpdateSection.STANDINGS,
        force_update=force_update,
    )


@shared_task(**_update_character_params)
@when_esi_is_available
def update_character_titles(character_pk: int, force_update: bool) -> None:
    """Update titles for a character from ESI."""
    _update_character_section(
        character_pk=character_pk,
        section=Character.UpdateSection.TITLES,
        force_update=force_update,
    )


@shared_task(**_update_character_params)
@when_esi_is_available
def update_character_wallet_balance(character_pk: int, force_update: bool) -> None:
    """Update wallet_balance for a character from ESI."""
    _update_character_section(
        character_pk=character_pk,
        section=Character.UpdateSection.WALLET_BALLANCE,
        force_update=force_update,
    )


@shared_task(**_update_character_params)
@when_esi_is_available
def update_character_wallet_journal(character_pk: int, force_update: bool) -> None:
    """Update wallet_journal for a character from ESI."""
    _update_character_section(
        character_pk=character_pk,
        section=Character.UpdateSection.WALLET_JOURNAL,
        force_update=force_update,
    )


@shared_task(**_update_character_params)
@when_esi_is_available
def update_character_wallet_transactions(character_pk: int, force_update: bool) -> None:
    """Update wallet_transactions for a character from ESI."""
    _update_character_section(
        character_pk=character_pk,
        section=Character.UpdateSection.WALLET_TRANSACTIONS,
        force_update=force_update,
    )


def _update_character_section(
    character_pk: int, section: str, force_update: bool
) -> None:
    """Update a section for a character from ESI."""
    section = Character.UpdateSection(section)
    character: Character = Character.objects.get_cached(
        pk=character_pk, timeout=MEMBERAUDIT_TASKS_OBJECT_CACHE_TIMEOUT
    )
    character.reset_update_section(section)
    logger.info("%s: Updating %s", character, section.label)

    method: Callable = getattr(character, section.method_name)
    method_signature = inspect.signature(method)
    if "force_update" in method_signature.parameters:
        kwargs = {"force_update": force_update}
    else:
        kwargs = {}

    result = character.perform_update_with_error_logging(
        section=section, method=method, **kwargs
    )
    character.update_section_log_result(
        section, is_success=True, is_updated=result.is_updated
    )


@shared_task(**TASK_DEFAULTS_ONCE)
@when_esi_is_available
def update_unresolved_eve_entities() -> None:
    """Bulk resolved all unresolved EveEntity objects in database.

    This task is used by other apps. Do not remove!
    """
    unresolved_ids = EveEntity.objects.filter(name="")[
        :POST_UNIVERSE_NAMES_MAX_ITEMS
    ].values_list("id", flat=True)
    if unresolved_ids:
        updated_count = EveEntity.objects.update_from_esi_by_id(unresolved_ids)
        logger.info("Updating %d unresolved entities from ESI", updated_count)


# Special tasks for updating assets


_update_task_params_with_bind = {
    **TASK_DEFAULTS_BIND_ONCE,
    **{"once": {"keys": ["character_pk", "force_update"], "graceful": True}},
}


@shared_task(**_update_task_params_with_bind)
def update_character_assets(self, character_pk: int, force_update: bool) -> None:
    """Update the assets of a character from ESI."""
    character: Character = Character.objects.get_cached(
        pk=character_pk, timeout=MEMBERAUDIT_TASKS_OBJECT_CACHE_TIMEOUT
    )
    section = Character.UpdateSection.ASSETS
    logger.info("%s: Updating %s", character, section.label)
    character.reset_update_section(section=section)
    priority = determine_task_priority(self) or MEMBERAUDIT_TASKS_LOW_PRIORITY
    chain(
        assets_build_list_from_esi.s(character.pk, force_update).set(priority=priority),
        assets_preload_objects.s(character.pk).set(priority=priority),
        assets_create_parents.s(character.pk).set(priority=priority),
    ).delay()


@shared_task(**TASK_DEFAULTS_ONCE)
@when_esi_is_available
def assets_build_list_from_esi(
    character_pk: int, force_update: bool = False
) -> Optional[dict]:
    """Retrieve asset list for a character from ESI and return it
    or return None if asset list is unchanged.
    """
    character: Character = Character.objects.get_cached(
        pk=character_pk, timeout=MEMBERAUDIT_TASKS_OBJECT_CACHE_TIMEOUT
    )
    result = character.perform_update_with_error_logging(
        section=Character.UpdateSection.ASSETS,
        method=character.assets_build_list_from_esi,
        force_update=force_update,
    )
    if not result.is_changed and not force_update:
        return None

    asset_list = result.data
    if asset_list:
        ship_asset_record = character.generate_asset_from_current_ship_and_location()
        if ship_asset_record:
            ship_item_id = ship_asset_record["item_id"]
            asset_item_ids = {item["item_id"] for item in asset_list}
            if ship_item_id not in asset_item_ids:
                asset_list.append(ship_asset_record)
                logger.info("%s: Added current ship to assets", character)

    return asset_list


@shared_task(**TASK_DEFAULTS)
def assets_preload_objects(
    asset_list: Optional[list], character_pk: int
) -> Optional[list]:
    """Preload asset objects for a character from ESI."""
    if asset_list is None:
        return None  # Exit when assets are unchanged

    character: Character = Character.objects.get_cached(
        pk=character_pk, timeout=MEMBERAUDIT_TASKS_OBJECT_CACHE_TIMEOUT
    )
    character.perform_update_with_error_logging(
        Character.UpdateSection.ASSETS,
        character.assets_preload_objects,
        asset_list,
    )
    return asset_list


@shared_task(**TASK_DEFAULTS_BIND)
def assets_create_parents(self, asset_list: Optional[list], character_pk: int) -> None:
    """Create the parent assets from an asset list.

    Parent assets are assets attached directly to a Location object (e.g. station)

    This task will recursively call itself until all possible parent assets
    from the asset list have been created.
    Then call another task to create child assets.
    """
    character: Character = Character.objects.get_cached(
        pk=character_pk, timeout=MEMBERAUDIT_TASKS_OBJECT_CACHE_TIMEOUT
    )
    if asset_list is None:
        character.update_section_log_result(
            Character.UpdateSection.ASSETS, is_success=True, is_updated=False
        )
        return

    priority = determine_task_priority(self) or MEMBERAUDIT_TASKS_LOW_PRIORITY

    asset_data_initial = {asset["item_id"]: asset for asset in asset_list}
    asset_data = _assets_create_parents_chunk(
        character=character, asset_data=asset_data_initial, cycle=1
    )

    if asset_data:
        assets_create_children.apply_async(
            kwargs={
                "asset_list": list(asset_data.values()),
                "character_pk": character.pk,
            },
            priority=priority,
        )
    else:
        character.update_section_log_result(
            Character.UpdateSection.ASSETS, is_success=True, is_updated=True
        )


def _assets_create_parents_chunk(character: Character, asset_data: dict, cycle: int):
    """Create chunk of parent assets for a character."""
    logger.info("%s: Creating parent assets - pass %s", character, cycle)
    new_assets = []
    if cycle == 1:
        character.assets.all().delete()

    known_location_ids = set(Location.objects.values_list("id", flat=True))
    parent_asset_ids = {
        item_id
        for item_id, asset_info in asset_data.items()
        if asset_info["location_id"] in known_location_ids
    }
    for item_id in parent_asset_ids:
        item = asset_data[item_id]
        new_assets.append(
            CharacterAsset(
                character=character,
                item_id=item_id,
                location_id=item["location_id"],
                eve_type_id=item["type_id"],
                name=item["name"],
                is_blueprint_copy=item.get("is_blueprint_copy"),
                is_singleton=item["is_singleton"],
                location_flag=item["location_flag"],
                quantity=item["quantity"],
            )
        )
        asset_data.pop(item_id)
        if len(new_assets) >= MEMBERAUDIT_TASKS_MAX_ASSETS_PER_PASS:
            break

    created_objs = CharacterAsset.objects.bulk_create_with_fallback(
        new_assets, batch_size=MEMBERAUDIT_BULK_METHODS_BATCH_SIZE
    )
    logger.info("%s: Created %s parent assets", character, len(created_objs))

    if len(parent_asset_ids) > len(new_assets):
        # there are more parent assets to create
        asset_data = _assets_create_parents_chunk(
            character=character, asset_data=asset_data, cycle=cycle + 1
        )

    return asset_data


@shared_task(**TASK_DEFAULTS_BIND)
def assets_create_children(
    self, asset_list: list, character_pk: int, cycle: int = 1
) -> None:
    """Create child assets from given asset list.

    Child assets are assets located within other assets (aka containers)

    This task will recursively call itself until all possible assets from the
    asset list are included into the asset tree
    """
    character: Character = Character.objects.get_cached(
        pk=character_pk, timeout=MEMBERAUDIT_TASKS_OBJECT_CACHE_TIMEOUT
    )
    logger.info("%s: Creating child assets - pass %s", character, cycle)

    # for debug
    # store_list_to_disk(character, asset_data, f"child_asset_list_{cycle}")

    priority = determine_task_priority(self) or MEMBERAUDIT_TASKS_LOW_PRIORITY
    asset_data = {asset["item_id"]: asset for asset in asset_list}
    new_assets = []
    parent_asset_ids = set(character.assets.values_list("item_id", flat=True))
    child_asset_ids = {
        item_id
        for item_id, item in asset_data.items()
        if item["location_id"] in parent_asset_ids
    }
    for item_id in child_asset_ids:
        item = asset_data[item_id]
        new_assets.append(
            CharacterAsset(
                character=character,
                item_id=item_id,
                parent=character.assets.get(item_id=item["location_id"]),
                eve_type_id=item["type_id"],
                name=item["name"],
                is_blueprint_copy=item.get("is_blueprint_copy"),
                is_singleton=item["is_singleton"],
                location_flag=item["location_flag"],
                quantity=item["quantity"],
            )
        )
        asset_data.pop(item_id)
        if len(new_assets) >= MEMBERAUDIT_TASKS_MAX_ASSETS_PER_PASS:
            break

    if new_assets:
        created_objs = CharacterAsset.objects.bulk_create_with_fallback(
            new_assets, batch_size=MEMBERAUDIT_BULK_METHODS_BATCH_SIZE
        )
        logger.info("%s: Created %s child assets", character, len(created_objs))

    if new_assets and asset_data:
        # there are more child assets to create
        assets_create_children.apply_async(
            kwargs={
                "asset_list": list(asset_data.values()),
                "character_pk": character.pk,
                "cycle": cycle + 1,
            },
            priority=priority,
        )
    else:
        if len(asset_data) > 0:
            error_text = "child assets could not be added (orphans)"
            character.update_section_log_result(
                Character.UpdateSection.ASSETS,
                is_success=False,
                error_message=(f"{len(asset_data)} {error_text}"),
            )
            logger.warning("%s: %d %s", character, len(asset_data), error_text)

            # additional infos for analyzing issues #152
            logger.debug("Item IDs of orphans: %s", sorted(asset_data.keys()))
            orphan_location_ids = sorted(
                {item["location_id"] for item in asset_data.values()}
            )
            logger.debug("Location IDs of orphans: %s", orphan_location_ids)
            logger.debug("Parent asset items IDs: %s", sorted(parent_asset_ids))

        else:
            character.update_section_log_result(
                Character.UpdateSection.ASSETS, is_success=True, is_updated=True
            )


# Special tasks for updating mail section


@shared_task(**_update_task_params_with_bind)
def update_character_mails(self, character_pk: int, force_update: bool) -> None:
    """Update mails of a character from ESI."""
    character: Character = Character.objects.get_cached(
        pk=character_pk, timeout=MEMBERAUDIT_TASKS_OBJECT_CACHE_TIMEOUT
    )
    section = Character.UpdateSection.MAILS
    logger.info("%s: Updating %s", character, section.label)
    character.reset_update_section(section=section)
    priority = determine_task_priority(self) or MEMBERAUDIT_TASKS_LOW_PRIORITY
    chain(
        update_character_mailing_lists.si(
            character.pk,
            force_update=force_update,
        ).set(priority=priority),
        update_character_mail_labels.si(
            character.pk,
            force_update=force_update,
        ).set(priority=priority),
        update_character_mails_headers_and_bodies.si(
            character.pk,
            force_update=force_update,
        ).set(priority=priority),
    ).delay()


@shared_task(**TASK_DEFAULTS_ONCE)
@when_esi_is_available
def update_character_mailing_lists(
    character_pk: int, force_update: bool = False
) -> None:
    """Update mailing list for a character."""
    character: Character = Character.objects.get_cached(
        pk=character_pk, timeout=MEMBERAUDIT_TASKS_OBJECT_CACHE_TIMEOUT
    )
    character.perform_update_with_error_logging(
        section=Character.UpdateSection.MAILS,
        method=character.update_mailing_lists,
        force_update=force_update,
    )


@shared_task(**TASK_DEFAULTS_ONCE)
@when_esi_is_available
def update_character_mail_labels(character_pk: int, force_update: bool = False) -> None:
    """Update mail labels for a character."""
    character: Character = Character.objects.get_cached(
        pk=character_pk, timeout=MEMBERAUDIT_TASKS_OBJECT_CACHE_TIMEOUT
    )
    character.perform_update_with_error_logging(
        section=Character.UpdateSection.MAILS,
        method=character.update_mail_labels,
        force_update=force_update,
    )


@shared_task(**TASK_DEFAULTS_BIND_ONCE)
@when_esi_is_available
def update_character_mails_headers_and_bodies(
    self, character_pk: int, force_update: bool = False
) -> List[int]:
    """Update mail headers & bodies for a character from ESI."""
    character: Character = Character.objects.get_cached(
        pk=character_pk, timeout=MEMBERAUDIT_TASKS_OBJECT_CACHE_TIMEOUT
    )
    result = character.perform_update_with_error_logging(
        section=Character.UpdateSection.MAILS,
        method=character.update_mail_headers,
        force_update=force_update,
    )
    if result.is_changed or force_update:
        mail_ids = result.data.keys()
        mails_to_fetch = character.mails.filter(mail_id__in=mail_ids)
        if not force_update:
            mails_to_fetch = mails_to_fetch.filter(body="")

        priority = determine_task_priority(self) or MEMBERAUDIT_TASKS_LOW_PRIORITY
        logger.info(
            "%s: Loading %d mail bodies from ESI", character, mails_to_fetch.count()
        )
        for mail_id in mails_to_fetch.values_list("mail_id", flat=True):
            update_mail_body_esi.apply_async(
                kwargs={
                    "character_pk": character.pk,
                    "mail_id": mail_id,
                    "force_update": force_update,
                },
                priority=priority,
            )

    # the last task in the chain logs success (if any)
    character.update_section_log_result(
        Character.UpdateSection.MAILS, is_success=True, is_updated=result.is_updated
    )


@shared_task(**TASK_DEFAULTS_ONCE)
@when_esi_is_available
def update_mail_body_esi(character_pk: int, mail_id: int, force_update: bool = False):
    """Update the body of a character's mail from ESI."""
    character: Character = Character.objects.get_cached(
        pk=character_pk, timeout=MEMBERAUDIT_TASKS_OBJECT_CACHE_TIMEOUT
    )
    mail = character.mails.get(mail_id=mail_id)
    character.perform_update_with_error_logging(
        section=Character.UpdateSection.MAILS,
        method=character.update_mail_body,
        mail=mail,
        force_update=force_update,
    )


# special tasks for updating contacts


@shared_task(**_update_task_params_with_bind)
def update_character_contacts(self, character_pk: int, force_update: bool) -> None:
    """Update contacts of a character from ESI."""
    character: Character = Character.objects.get_cached(
        pk=character_pk, timeout=MEMBERAUDIT_TASKS_OBJECT_CACHE_TIMEOUT
    )
    section = Character.UpdateSection.CONTACTS
    character.reset_update_section(section=section)
    logger.info("%s: Updating %s", character, section.label)
    priority = determine_task_priority(self) or MEMBERAUDIT_TASKS_LOW_PRIORITY
    chain(
        update_character_contact_labels.si(character.pk, force_update=force_update).set(
            priority=priority
        ),
        update_character_contacts_2.si(character.pk, force_update=force_update).set(
            priority=priority
        ),
    ).delay()


@shared_task(**TASK_DEFAULTS_ONCE)
@when_esi_is_available
def update_character_contact_labels(
    character_pk: int, force_update: bool = False
) -> None:
    """Update contact labels for a character from ESI."""
    character: Character = Character.objects.get_cached(
        pk=character_pk, timeout=MEMBERAUDIT_TASKS_OBJECT_CACHE_TIMEOUT
    )
    character.perform_update_with_error_logging(
        section=Character.UpdateSection.CONTACTS,
        method=character.update_contact_labels,
        force_update=force_update,
    )


@shared_task(**TASK_DEFAULTS_ONCE)
@when_esi_is_available
def update_character_contacts_2(character_pk: int, force_update: bool = False) -> None:
    """Update contacts for a character from ESI."""
    character: Character = Character.objects.get_cached(
        pk=character_pk, timeout=MEMBERAUDIT_TASKS_OBJECT_CACHE_TIMEOUT
    )
    result = character.perform_update_with_error_logging(
        section=Character.UpdateSection.CONTACTS,
        method=character.update_contacts,
        force_update=force_update,
    )
    character.update_section_log_result(
        Character.UpdateSection.CONTACTS, is_success=True, is_updated=result.is_updated
    )


# special tasks for updating contracts


@shared_task(**_update_task_params_with_bind)
def update_character_contracts(self, character_pk: int, force_update: bool) -> None:
    """Update contracts of a character from ESI."""
    character: Character = Character.objects.get_cached(
        pk=character_pk, timeout=MEMBERAUDIT_TASKS_OBJECT_CACHE_TIMEOUT
    )
    section = Character.UpdateSection.CONTRACTS
    character.reset_update_section(section=section)
    logger.info("%s: Updating %s", character, section.label)
    priority = determine_task_priority(self) or MEMBERAUDIT_TASKS_LOW_PRIORITY
    chain(
        update_character_contract_headers.si(
            character.pk, force_update=force_update
        ).set(priority=priority),
        update_character_contracts_items.si(character.pk).set(priority=priority),
        update_character_contracts_bids.si(character.pk).set(priority=priority),
    ).delay()


@shared_task(**TASK_DEFAULTS_ONCE)
@when_esi_is_available
def update_character_contract_headers(character_pk: int, force_update: bool = False):
    """Update contract headers for a character from ESI."""
    character: Character = Character.objects.get_cached(
        pk=character_pk, timeout=MEMBERAUDIT_TASKS_OBJECT_CACHE_TIMEOUT
    )
    result = character.perform_update_with_error_logging(
        section=Character.UpdateSection.CONTRACTS,
        method=character.update_contract_headers,
        force_update=force_update,
    )
    character.update_section_log_result(
        Character.UpdateSection.CONTRACTS, is_success=True, is_updated=result.is_updated
    )


@shared_task(**TASK_DEFAULTS_BIND_ONCE)
def update_character_contracts_items(self, character_pk: int):
    """Update items for all contracts of a character from ESI."""
    character: Character = Character.objects.get_cached(
        pk=character_pk, timeout=MEMBERAUDIT_TASKS_OBJECT_CACHE_TIMEOUT
    )
    contract_pks = set(
        character.contracts.filter(
            contract_type__in=[
                CharacterContract.TYPE_ITEM_EXCHANGE,
                CharacterContract.TYPE_AUCTION,
                # Courier contracts have no items
            ],
            items__isnull=True,
        ).values_list("pk", flat=True)
    )
    if len(contract_pks) > 0:
        logger.info(
            "%s: Starting updating items for %s contracts", character, len(contract_pks)
        )
        priority = determine_task_priority(self) or MEMBERAUDIT_TASKS_LOW_PRIORITY
        for contract_pk in contract_pks:
            update_contract_items_esi.apply_async(
                kwargs={"character_pk": character.pk, "contract_pk": contract_pk},
                priority=priority,
            )

    else:
        logger.info("%s: No items to update", character)


@shared_task(**TASK_DEFAULTS_ONCE)
@when_esi_is_available
def update_contract_items_esi(character_pk: int, contract_pk: int):
    """Update the items of a character contract from ESI."""
    character: Character = Character.objects.get_cached(
        pk=character_pk, timeout=MEMBERAUDIT_TASKS_OBJECT_CACHE_TIMEOUT
    )
    contract = CharacterContract.objects.get(pk=contract_pk)
    character.update_contract_items(contract)


@shared_task(**TASK_DEFAULTS_BIND_ONCE)
def update_character_contracts_bids(self, character_pk: int):
    """Update bids for all contracts of a character from ESI."""
    character: Character = Character.objects.get_cached(
        pk=character_pk, timeout=MEMBERAUDIT_TASKS_OBJECT_CACHE_TIMEOUT
    )
    contract_pks = set(
        character.contracts.filter(
            contract_type__in=[CharacterContract.TYPE_AUCTION],
            status=CharacterContract.STATUS_OUTSTANDING,
        ).values_list("pk", flat=True)
    )
    if len(contract_pks) > 0:
        logger.info(
            "%s: Starting updating bids for %s contracts", character, len(contract_pks)
        )
        priority = determine_task_priority(self) or MEMBERAUDIT_TASKS_LOW_PRIORITY
        for contract_pk in contract_pks:
            update_contract_bids_esi.apply_async(
                kwargs={"character_pk": character.pk, "contract_pk": contract_pk},
                priority=priority,
            )

    else:
        logger.info("%s: No bids to update", character)


@shared_task(**TASK_DEFAULTS_ONCE)
@when_esi_is_available
def update_contract_bids_esi(character_pk: int, contract_pk: int):
    """Update bids of a character contract from ESI."""
    character: Character = Character.objects.get_cached(
        pk=character_pk, timeout=MEMBERAUDIT_TASKS_OBJECT_CACHE_TIMEOUT
    )
    contract = CharacterContract.objects.get(pk=contract_pk)
    character.update_contract_bids(contract)


# Tasks for other objects


@shared_task(**TASK_DEFAULTS_ONCE)
@when_esi_is_available
def update_market_prices():
    """Update market prices from ESI."""
    EveMarketPrice.objects.update_from_esi(
        minutes_until_stale=MEMBERAUDIT_SECTION_STALE_MINUTES_GLOBAL_DEFAULT
    )


@shared_task(
    **{
        **TASK_DEFAULTS_BIND_ONCE,
        **{
            "once": {"keys": ["id"], "graceful": True},
            "max_retries": MAX_RETRIES_STRUCTURES,
        },
    }
)
def update_structure_esi(self, id: int, token_pk: int):
    """Update a structure object from ESI.

    If the ESI error limit has already been reached retry later.
    """
    token = Token.objects.get(pk=token_pk)

    try:
        Location.objects.structure_update_or_create_esi(id, token)

    except EsiOffline as ex:
        backoff_jitter = int(random.uniform(2, 4) ** self.request.retries)
        countdown = (15 + backoff_jitter) * 60
        logger.warning(
            "Location #%s: ESI appears to be offline. Trying again in %d seconds.",
            id,
            countdown,
        )
        raise self.retry(countdown=countdown) from ex

    except EsiErrorLimitExceeded as ex:
        backoff_jitter = int(random.uniform(2, 4) ** self.request.retries)
        countdown = ex.retry_in + backoff_jitter
        logger.warning(
            "Location #%s: ESI error limit threshold reached. "
            "Trying again in %s seconds",
            id,
            countdown,
        )
        raise self.retry(countdown=countdown) from ex


@shared_task(
    **{
        **TASK_DEFAULTS_ONCE,
        **{
            "once": {"keys": ["id"], "graceful": True},
            "max_retries": MAX_RETRIES_MAIL_ENTITIES,
        },
    }
)
def update_mail_entity_esi(id: int, category: Optional[str] = None):
    """Update a mail entity object from ESI
    and retry later if the ESI error limit has already been reached.
    """
    MailEntity.objects.update_or_create_esi(id=id, category=category)


@shared_task(**TASK_DEFAULTS_BIND_ONCE)
def update_characters_skill_checks(self, force_update: bool = False) -> None:
    """Start the update of skill checks for all registered characters.

    Args:
        - force_update: When set to True will always update regardless of stale status
    """
    priority = determine_task_priority(self) or MEMBERAUDIT_TASKS_LOW_PRIORITY
    for character in Character.objects.all():
        if force_update or character.is_update_needed_for_section(
            Character.UpdateSection.SKILL_SETS
        ):
            update_character_skill_sets.apply_async(
                kwargs={"character_pk": character.pk, "force_update": force_update},
                priority=priority,
            )


@shared_task(**TASK_DEFAULTS_ONCE)
def check_character_consistency(character_pk) -> None:
    """Check consistency of a character."""
    character: Character = Character.objects.get_cached(
        pk=character_pk, timeout=MEMBERAUDIT_TASKS_OBJECT_CACHE_TIMEOUT
    )
    character.update_sharing_consistency()


@shared_task(**TASK_DEFAULTS)
def delete_objects(model_name: str, obj_pks: Iterable[int]) -> None:
    """Delete multiple objects of a model."""
    model_class = apps.get_model("memberaudit", str(model_name))
    objs_to_delete = model_class.objects.filter(pk__in=obj_pks)
    amount = objs_to_delete.count()
    objs_to_delete.delete()
    logger.info("Deleted %d %s objects", amount, model_class.__name__)


@shared_task(**TASK_DEFAULTS_BIND)
def export_data(self, user_pk: Optional[int] = None) -> None:
    """Export data to files."""
    priority = determine_task_priority(self) or MEMBERAUDIT_TASKS_LOW_PRIORITY
    tasks = [
        _export_data_for_topic.si(topic).set(priority=priority)
        for topic in data_exporters.DataExporter.topics()
    ]
    if user_pk:
        tasks.append(_export_data_inform_user.si(user_pk))
    chain(tasks).delay()


@shared_task(**TASK_DEFAULTS_BIND)
def export_data_for_topic(self, topic: str, user_pk: int):
    """Export data for a topic."""
    priority = determine_task_priority(self) or MEMBERAUDIT_TASKS_LOW_PRIORITY
    chain(
        _export_data_for_topic.si(topic).set(priority=priority),
        _export_data_inform_user.si(user_pk, topic).set(priority=priority),
    ).delay()


@shared_task(**TASK_DEFAULTS_ONCE)
def _export_data_for_topic(topic: str, destination_folder: Optional[str] = None) -> str:
    """Export data for given topic into a zipped file in destination."""
    file_path = data_exporters.export_topic_to_archive(
        topic=topic, destination_folder=destination_folder
    )
    return str(file_path)


@shared_task(**TASK_DEFAULTS)
def _export_data_inform_user(user_pk: int, topic: Optional[str] = None):
    user = User.objects.get(pk=user_pk)
    if topic:
        title = f"{__title__}: Data export for {topic} completed"
        message = f"Data export has been completed for topic {topic}."
    else:
        title = f"{__title__}: Full data export completed"
        message = (
            "Data export for all topics has been completed. "
            "It covers the following:\n"
        )
        for obj in data_exporters.DataExporter.topics():
            message += f"- {obj}\n"  # pylint: disable=consider-using-join
    notify(user=user, title=title, message=message, level="INFO")


@shared_task(**TASK_DEFAULTS_BIND_ONCE)
def update_compliance_groups_for_all(self):
    """Update compliance groups for all users."""
    if ComplianceGroupDesignation.objects.exists():
        priority = determine_task_priority(self) or MEMBERAUDIT_TASKS_LOW_PRIORITY
        for user in User.objects.all():
            update_compliance_groups_for_user.apply_async(
                kwargs={"user_pk": user.pk}, priority=priority
            )


@shared_task(**TASK_DEFAULTS)
def update_compliance_groups_for_user(user_pk: int):
    """Update compliance groups for user."""
    user = User.objects.get(pk=user_pk)
    ComplianceGroupDesignation.objects.update_user(user)


@shared_task(**TASK_DEFAULTS)
def add_compliant_users_to_group(group_pk: int):
    """Add compliant users to given group."""
    group = Group.objects.get(pk=group_pk)
    General.add_compliant_users_to_group(group)


@shared_task(**TASK_DEFAULTS)
def clear_users_from_group(group_pk: int):
    """Clear all users from given group."""
    group = Group.objects.get(pk=group_pk)
    utils.clear_users_from_group(group)
