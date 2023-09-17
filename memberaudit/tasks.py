"""Celery tasks for Member Audit."""
# pylint: disable=redefined-builtin, too-many-lines

import inspect
import random
from typing import Iterable, Optional

from celery import chain, shared_task

from django.apps import apps
from django.contrib.auth.models import Group, User
from django.db import transaction
from django.utils.timezone import now
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
    MEMBERAUDIT_LOG_UPDATE_STATS,
    MEMBERAUDIT_TASKS_LOW_PRIORITY,
    MEMBERAUDIT_TASKS_MAX_ASSETS_PER_PASS,
    MEMBERAUDIT_TASKS_NORMAL_PRIORITY,
    MEMBERAUDIT_TASKS_OBJECT_CACHE_TIMEOUT,
    MEMBERAUDIT_TASKS_TIME_LIMIT,
    MEMBERAUDIT_UPDATE_STALE_RING_2,
)
from memberaudit.core import data_exporters
from memberaudit.decorators import when_esi_is_available
from memberaudit.helpers import determine_task_priority
from memberaudit.models import (
    Character,
    CharacterAsset,
    CharacterContract,
    CharacterMail,
    CharacterUpdateStatus,
    ComplianceGroupDesignation,
    General,
    Location,
    MailEntity,
)

logger = LoggerAddTag(get_extension_logger(__name__), __title__)

# default params for all tasks
TASK_DEFAULTS = {"time_limit": MEMBERAUDIT_TASKS_TIME_LIMIT, "max_retries": 3}

# default params for tasks that need access to self
TASK_DEFAULTS_BIND = {**TASK_DEFAULTS, **{"bind": True}}

# default params for tasks that need run once only
TASK_DEFAULTS_ONCE = {**TASK_DEFAULTS, **{"base": QueueOnce}}

# default params for tasks that need access to self and run once only
TASK_DEFAULTS_BIND_ONCE = {**TASK_DEFAULTS, **{"bind": True, "base": QueueOnce}}


@shared_task(**TASK_DEFAULTS_ONCE)
def run_regular_updates() -> None:
    """Main task to be run on a regular basis to keep everything updated and running"""
    update_market_prices.apply_async(priority=MEMBERAUDIT_TASKS_LOW_PRIORITY)
    update_all_characters.apply_async(priority=MEMBERAUDIT_TASKS_LOW_PRIORITY)
    if ComplianceGroupDesignation.objects.exists():
        update_compliance_groups_for_all.apply_async(
            priority=MEMBERAUDIT_TASKS_NORMAL_PRIORITY
        )


@shared_task(**TASK_DEFAULTS_BIND_ONCE)
@when_esi_is_available
def update_all_characters(self, force_update: bool = False) -> None:
    """Start the update of all registered characters

    Args:
    - force_update: When set to True will always update regardless of stale status
    """
    if MEMBERAUDIT_LOG_UPDATE_STATS:
        stats = CharacterUpdateStatus.objects.statistics()
        logger.info(f"Update statistics: {stats}")

    # disable characters without owner
    orphaned_characters = Character.objects.filter(
        eve_character__character_ownership__isnull=True
    )
    if orphaned_count := orphaned_characters.count() > 0:
        orphaned_characters.update(is_disabled=True)
        logger.info(
            "Disabled %d characters which do not belong to a user.", orphaned_count
        )

    # start sync for all enabled characters
    enabled_characters = Character.objects.filter(is_disabled=False).values_list(
        "pk", flat=True
    )
    priority = determine_task_priority(self) or MEMBERAUDIT_TASKS_LOW_PRIORITY
    for character_pk in enabled_characters:
        update_character.apply_async(
            kwargs={"character_pk": character_pk, "force_update": force_update},
            priority=priority,
        )


# Main character update tasks


@shared_task(**TASK_DEFAULTS_BIND_ONCE)
def update_character(self, character_pk: int, force_update: bool = False) -> bool:
    """Start respective update tasks for all stale sections of a character.

    Args:
    - character_pk: PL of character to update
    - force_update: When set to True will always update regardless of stale status

    Returns:
    - True when update was conducted
    - False when no updated was needed
    """
    character: Character = Character.objects.get(pk=character_pk)
    if character.is_orphan:
        logger.info("%s: Skipping update for orphaned character", character)
        return False

    character.reset_token_error_notified_if_status_ok()

    needs_update = force_update | character.is_update_needed()
    if not needs_update:
        logger.info("%s: No update required", character)
        return False

    logger.info(
        "%s: Starting %s character update", character, "forced" if force_update else ""
    )
    all_sections = set(Character.UpdateSection.values)
    sections = all_sections.difference(
        {
            Character.UpdateSection.ASSETS,
            Character.UpdateSection.MAILS,
            Character.UpdateSection.CONTACTS,
            Character.UpdateSection.CONTRACTS,
            Character.UpdateSection.SKILL_SETS,
            Character.UpdateSection.SKILLS,
        }
    )
    Character.objects.clear_cache(pk=character_pk)
    priority = determine_task_priority(self) or MEMBERAUDIT_TASKS_LOW_PRIORITY
    for section in sorted(sections):
        if force_update or character.is_update_section_stale(section):
            update_character_section.apply_async(
                kwargs={
                    "character_pk": character.pk,
                    "section": section,
                    "force_update": force_update,
                    "root_task_id": self.request.parent_id,
                    "parent_task_id": self.request.id,
                },
                priority=priority,
            )

    if force_update or character.is_update_section_stale(Character.UpdateSection.MAILS):
        update_character_mails.apply_async(
            kwargs={
                "character_pk": character.pk,
                "force_update": force_update,
                "root_task_id": self.request.parent_id,
                "parent_task_id": self.request.id,
            },
            priority=priority,
        )
    if force_update or character.is_update_section_stale(
        Character.UpdateSection.CONTACTS
    ):
        update_character_contacts.apply_async(
            kwargs={
                "character_pk": character.pk,
                "force_update": force_update,
                "root_task_id": self.request.parent_id,
                "parent_task_id": self.request.id,
            },
            priority=priority,
        )
    if force_update or character.is_update_section_stale(
        Character.UpdateSection.CONTRACTS
    ):
        update_character_contracts.apply_async(
            kwargs={
                "character_pk": character.pk,
                "force_update": force_update,
                "root_task_id": self.request.parent_id,
                "parent_task_id": self.request.id,
            },
            priority=priority,
        )
    if force_update or character.is_update_section_stale(
        Character.UpdateSection.ASSETS
    ):
        update_character_assets.apply_async(
            kwargs={
                "character_pk": character.pk,
                "force_update": force_update,
                "root_task_id": self.request.parent_id,
                "parent_task_id": self.request.id,
            },
            priority=priority,
        )
    if (
        force_update
        or character.is_update_section_stale(Character.UpdateSection.SKILLS)
        or character.is_update_section_stale(Character.UpdateSection.SKILL_SETS)
    ):
        chain(
            update_character_section.si(
                character.pk,
                Character.UpdateSection.SKILLS,
                force_update,
                self.request.parent_id,
                self.request.id,
            ).set(priority=priority),
            update_character_section.si(
                character.pk,
                Character.UpdateSection.SKILL_SETS,
                force_update,
                self.request.parent_id,
                self.request.id,
            ).set(priority=priority),
        ).delay()
    if character.is_shared:
        check_character_consistency.apply_async(
            kwargs={"character_pk": character.pk}, priority=priority
        )
    return True


# Update sections


@shared_task(
    **{
        **TASK_DEFAULTS_ONCE,
        **{
            "once": {
                "keys": ["character_pk", "section", "force_update"],
                "graceful": True,
            }
        },
    }
)
@when_esi_is_available
def update_character_section(
    character_pk: int,
    section: str,
    force_update: bool,
    root_task_id: Optional[str] = None,
    parent_task_id: Optional[str] = None,
    **kwargs,
) -> None:
    """Task that updates the section of a character"""
    character = Character.objects.get_cached(
        pk=character_pk, timeout=MEMBERAUDIT_TASKS_OBJECT_CACHE_TIMEOUT
    )
    character.reset_update_section(section, root_task_id, parent_task_id)
    logger.info(
        "%s: Updating %s", character, Character.UpdateSection.display_name(section)
    )
    update_method = getattr(character, Character.UpdateSection.method_name(section))
    args = [character, section, update_method]
    if not kwargs:
        kwargs = {}

    method_signature = inspect.signature(update_method)
    if "force_update" in method_signature.parameters:
        kwargs["force_update"] = force_update

    _character_update_with_error_logging(*args, **kwargs)
    _log_character_update_success(character, section)


def _character_update_with_error_logging(
    character: Character, section: str, method: object, *args, **kwargs
):
    """Facilitate catching and logging of exceptions potentially occurring
    during a character update.
    """
    try:
        return method(*args, **kwargs)  # type: ignore
    except Exception as ex:
        error_message = f"{type(ex).__name__}: {str(ex)}"
        logger.error(
            "%s: %s: Error ocurred: %s",
            character,
            Character.UpdateSection.display_name(section),
            error_message,
            exc_info=True,
        )
        CharacterUpdateStatus.objects.update_or_create(
            character=character,
            section=section,
            defaults={
                "is_success": False,
                "last_error_message": error_message,
                "finished_at": now(),
            },
        )
        raise ex


def _log_character_update_success(character: Character, section: str):
    """Logs character update success for a section"""
    logger.info(
        "%s: %s update completed",
        character,
        Character.UpdateSection.display_name(section),
    )
    CharacterUpdateStatus.objects.update_or_create(
        character=character,
        section=section,
        defaults={"is_success": True, "last_error_message": "", "finished_at": now()},
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


@shared_task(
    **{
        **TASK_DEFAULTS_BIND_ONCE,
        **{"once": {"keys": ["character_pk", "force_update"], "graceful": True}},
    }
)
def update_character_assets(
    self,
    character_pk: int,
    force_update: bool,
    root_task_id: Optional[str] = None,
    parent_task_id: Optional[str] = None,
) -> None:
    """Main tasks for updating the character's assets"""
    character = Character.objects.get_cached(
        pk=character_pk, timeout=MEMBERAUDIT_TASKS_OBJECT_CACHE_TIMEOUT
    )
    logger.info(
        "%s: Updating %s",
        character,
        Character.UpdateSection.display_name(Character.UpdateSection.ASSETS),
    )
    character.reset_update_section(
        section=Character.UpdateSection.ASSETS,
        root_task_id=root_task_id,
        parent_task_id=parent_task_id,
    )
    priority = determine_task_priority(self) or MEMBERAUDIT_TASKS_LOW_PRIORITY
    chain(
        assets_build_list_from_esi.s(character.pk, force_update).set(priority=priority),
        assets_preload_objects.s(character.pk).set(priority=priority),
        assets_create_parents.s(character.pk).set(priority=priority),
    ).delay()


@shared_task(**TASK_DEFAULTS_ONCE)
@when_esi_is_available
def assets_build_list_from_esi(character_pk: int, force_update: bool = False) -> dict:
    """Building asset list"""
    character = Character.objects.get_cached(
        pk=character_pk, timeout=MEMBERAUDIT_TASKS_OBJECT_CACHE_TIMEOUT
    )
    asset_list = _character_update_with_error_logging(
        character,
        Character.UpdateSection.ASSETS,
        character.assets_build_list_from_esi,
        force_update,
    )
    return asset_list


@shared_task(**TASK_DEFAULTS)
def assets_preload_objects(asset_list: dict, character_pk: int) -> Optional[dict]:
    """Task for preloading asset objects"""
    if asset_list is None:
        return None

    character = Character.objects.get_cached(
        pk=character_pk, timeout=MEMBERAUDIT_TASKS_OBJECT_CACHE_TIMEOUT
    )
    _character_update_with_error_logging(
        character,
        Character.UpdateSection.ASSETS,
        character.assets_preload_objects,
        asset_list,
    )
    return asset_list


@shared_task(**TASK_DEFAULTS_BIND)
def assets_create_parents(
    self, asset_list: list, character_pk: int, cycle: int = 1
) -> None:
    """creates the parent assets from given asset_list

    Parent assets are assets attached directly to a Location object (e.g. station)

    This task will recursively call itself until all possible parent assets
    from the asset list have been created.
    Then call another task to create child assets.
    """
    character = Character.objects.get_cached(
        pk=character_pk, timeout=MEMBERAUDIT_TASKS_OBJECT_CACHE_TIMEOUT
    )
    if asset_list is None:
        _log_character_update_success(character, Character.UpdateSection.ASSETS)
        return

    logger.info("%s: Creating parent assets - pass %s", character, cycle)

    assets_flat = {int(item["item_id"]): item for item in asset_list}
    new_assets = []
    priority = determine_task_priority(self) or MEMBERAUDIT_TASKS_LOW_PRIORITY
    with transaction.atomic():
        if cycle == 1:
            character.assets.all().delete()

        location_ids = set(Location.objects.values_list("id", flat=True))
        parent_asset_ids = {
            item_id
            for item_id, asset_info in assets_flat.items()
            if asset_info.get("location_id")
            and asset_info["location_id"] in location_ids
        }
        for item_id in parent_asset_ids:
            item = assets_flat[item_id]
            new_assets.append(
                CharacterAsset(
                    character=character,
                    item_id=item_id,
                    location_id=item["location_id"],
                    eve_type_id=item.get("type_id"),
                    name=item.get("name"),
                    is_blueprint_copy=item.get("is_blueprint_copy"),
                    is_singleton=item.get("is_singleton"),
                    location_flag=item.get("location_flag"),
                    quantity=item.get("quantity"),
                )
            )
            assets_flat.pop(item_id)
            if len(new_assets) >= MEMBERAUDIT_TASKS_MAX_ASSETS_PER_PASS:
                break

        logger.info("%s: Writing %s parent assets", character, len(new_assets))
        # TODO: `ignore_conflicts=True` needed as workaround to compensate for
        # occasional duplicate FK constraint errors. Needs to be investigated
        CharacterAsset.objects.bulk_create(
            new_assets,
            batch_size=MEMBERAUDIT_BULK_METHODS_BATCH_SIZE,
            ignore_conflicts=True,
        )

    if len(parent_asset_ids) > len(new_assets):
        # there are more parent assets to create
        assets_create_parents.apply_async(
            kwargs={
                "asset_list": list(assets_flat.values()),
                "character_pk": character.pk,
                "cycle": cycle + 1,
            },
            priority=priority,
        )
    else:
        # all parent assets created
        if assets_flat:
            assets_create_children.apply_async(
                kwargs={
                    "asset_list": list(assets_flat.values()),
                    "character_pk": character.pk,
                },
                priority=priority,
            )
        else:
            _log_character_update_success(character, Character.UpdateSection.ASSETS)


@shared_task(**TASK_DEFAULTS_BIND)
def assets_create_children(
    self, asset_list: dict, character_pk: int, cycle: int = 1
) -> None:
    """Created child assets from given asset list

    Child assets are assets located within other assets (aka containers)

    This task will recursively call itself until all possible assets from the
    asset list are included into the asset tree
    """
    character = Character.objects.get_cached(
        pk=character_pk, timeout=MEMBERAUDIT_TASKS_OBJECT_CACHE_TIMEOUT
    )
    logger.info("%s: Creating child assets - pass %s", character, cycle)

    # for debug
    # store_list_to_disk(character, asset_list, f"child_asset_list_{cycle}")

    new_assets = []
    assets_flat = {int(item["item_id"]): item for item in asset_list}
    priority = determine_task_priority(self) or MEMBERAUDIT_TASKS_LOW_PRIORITY
    with transaction.atomic():
        parent_asset_ids = set(character.assets.values_list("item_id", flat=True))
        child_asset_ids = {
            item_id
            for item_id, item in assets_flat.items()
            if item.get("location_id") and item["location_id"] in parent_asset_ids
        }
        for item_id in child_asset_ids:
            item = assets_flat[item_id]
            new_assets.append(
                CharacterAsset(
                    character=character,
                    item_id=item_id,
                    parent=character.assets.get(item_id=item["location_id"]),
                    eve_type_id=item.get("type_id"),
                    name=item.get("name"),
                    is_blueprint_copy=item.get("is_blueprint_copy"),
                    is_singleton=item.get("is_singleton"),
                    location_flag=item.get("location_flag"),
                    quantity=item.get("quantity"),
                )
            )
            assets_flat.pop(item_id)
            if len(new_assets) >= MEMBERAUDIT_TASKS_MAX_ASSETS_PER_PASS:
                break

        if new_assets:
            logger.info("%s: Writing %s child assets", character, len(new_assets))
            # TODO: `ignore_conflicts=True` needed as workaround to compensate for
            # occasional duplicate FK constraint errors. Needs to be investigated
            CharacterAsset.objects.bulk_create(
                new_assets,
                batch_size=MEMBERAUDIT_BULK_METHODS_BATCH_SIZE,
                ignore_conflicts=True,
            )

    if new_assets and assets_flat:
        # there are more child assets to create
        assets_create_children.apply_async(
            kwargs={
                "asset_list": list(assets_flat.values()),
                "character_pk": character.pk,
                "cycle": cycle + 1,
            },
            priority=priority,
        )
    else:
        _log_character_update_success(character, Character.UpdateSection.ASSETS)
        if len(assets_flat) > 0:
            logger.warning(
                "%s: Failed to add %s assets to the tree: %s",
                character,
                len(assets_flat),
                assets_flat.keys(),
            )


# Special tasks for updating mail section


@shared_task(
    **{
        **TASK_DEFAULTS_BIND_ONCE,
        **{"once": {"keys": ["character_pk", "force_update"], "graceful": True}},
    }
)
def update_character_mails(
    self,
    character_pk: int,
    force_update: bool,
    root_task_id: Optional[str] = None,
    parent_task_id: Optional[str] = None,
) -> None:
    """Main task for updating mails of a character"""
    character = Character.objects.get_cached(
        pk=character_pk, timeout=MEMBERAUDIT_TASKS_OBJECT_CACHE_TIMEOUT
    )
    section = Character.UpdateSection.MAILS
    logger.info(
        "%s: Updating %s", character, Character.UpdateSection.display_name(section)
    )
    character.reset_update_section(
        section=section, root_task_id=root_task_id, parent_task_id=parent_task_id
    )
    priority = determine_task_priority(self) or MEMBERAUDIT_TASKS_LOW_PRIORITY
    chain(
        update_character_mailing_lists.si(character.pk, force_update=force_update).set(
            priority=priority
        ),
        update_character_mail_labels.si(character.pk, force_update=force_update).set(
            priority=priority
        ),
        update_character_mail_headers.si(character.pk, force_update=force_update).set(
            priority=priority
        ),
        update_character_mail_bodies.si(character.pk).set(priority=priority),
    ).delay()


@shared_task(**TASK_DEFAULTS_ONCE)
@when_esi_is_available
def update_character_mailing_lists(
    character_pk: int, force_update: bool = False
) -> None:
    """Update mailing list for a character."""
    character = Character.objects.get_cached(
        pk=character_pk, timeout=MEMBERAUDIT_TASKS_OBJECT_CACHE_TIMEOUT
    )
    _character_update_with_error_logging(
        character,
        Character.UpdateSection.MAILS,
        character.update_mailing_lists,
        force_update=force_update,
    )


@shared_task(**TASK_DEFAULTS_ONCE)
@when_esi_is_available
def update_character_mail_labels(character_pk: int, force_update: bool = False) -> None:
    """Update mail labels for a character."""
    character = Character.objects.get_cached(
        pk=character_pk, timeout=MEMBERAUDIT_TASKS_OBJECT_CACHE_TIMEOUT
    )
    _character_update_with_error_logging(
        character,
        Character.UpdateSection.MAILS,
        character.update_mail_labels,
        force_update=force_update,
    )


@shared_task(**TASK_DEFAULTS_ONCE)
@when_esi_is_available
def update_character_mail_headers(
    character_pk: int, force_update: bool = False
) -> None:
    """Update mail headers for a character."""

    character = Character.objects.get_cached(
        pk=character_pk, timeout=MEMBERAUDIT_TASKS_OBJECT_CACHE_TIMEOUT
    )
    _character_update_with_error_logging(
        character,
        Character.UpdateSection.MAILS,
        character.update_mail_headers,
        force_update=force_update,
    )


@shared_task(**TASK_DEFAULTS_ONCE)
@when_esi_is_available
def update_mail_body_esi(character_pk: int, mail_pk: int):
    """Task for updating the body of a mail from ESI"""
    character = Character.objects.get_cached(
        pk=character_pk, timeout=MEMBERAUDIT_TASKS_OBJECT_CACHE_TIMEOUT
    )
    mail = CharacterMail.objects.get(pk=mail_pk)
    _character_update_with_error_logging(
        character,
        Character.UpdateSection.MAILS,
        character.update_mail_body,
        mail,
    )


@shared_task(**TASK_DEFAULTS_BIND_ONCE)
def update_character_mail_bodies(self, character_pk: int, *args, **kwargs) -> None:
    """Update mail bodies for a character."""

    character = Character.objects.get_cached(
        pk=character_pk, timeout=MEMBERAUDIT_TASKS_OBJECT_CACHE_TIMEOUT
    )
    mails_without_body_qs = character.mails.filter(body="")
    mails_without_body_count = mails_without_body_qs.count()

    if mails_without_body_count > 0:
        logger.info("%s: Loading %s mail bodies", character, mails_without_body_count)
        priority = determine_task_priority(self) or MEMBERAUDIT_TASKS_LOW_PRIORITY
        for mail in mails_without_body_qs:
            update_mail_body_esi.apply_async(
                kwargs={"character_pk": character.pk, "mail_pk": mail.pk},
                priority=priority,
            )

    # the last task in the chain logs success (if any)
    _log_character_update_success(character, Character.UpdateSection.MAILS)


# special tasks for updating contacts


@shared_task(
    **{
        **TASK_DEFAULTS_BIND_ONCE,
        **{"once": {"keys": ["character_pk", "force_update"], "graceful": True}},
    }
)
def update_character_contacts(
    self,
    character_pk: int,
    force_update: bool,
    root_task_id: Optional[str] = None,
    parent_task_id: Optional[str] = None,
) -> None:
    """Main task for updating contacts of a character"""
    character = Character.objects.get_cached(
        pk=character_pk, timeout=MEMBERAUDIT_TASKS_OBJECT_CACHE_TIMEOUT
    )
    section = Character.UpdateSection.CONTACTS
    character.reset_update_section(
        section=section, root_task_id=root_task_id, parent_task_id=parent_task_id
    )
    logger.info(
        "%s: Updating %s", character, Character.UpdateSection.display_name(section)
    )
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
    """Update contact labels for a character."""

    character = Character.objects.get_cached(
        pk=character_pk, timeout=MEMBERAUDIT_TASKS_OBJECT_CACHE_TIMEOUT
    )
    _character_update_with_error_logging(
        character,
        Character.UpdateSection.CONTACTS,
        character.update_contact_labels,
        force_update=force_update,
    )


@shared_task(**TASK_DEFAULTS_ONCE)
@when_esi_is_available
def update_character_contacts_2(character_pk: int, force_update: bool = False) -> None:
    """Update contacts for a character."""

    character = Character.objects.get_cached(
        pk=character_pk, timeout=MEMBERAUDIT_TASKS_OBJECT_CACHE_TIMEOUT
    )
    _character_update_with_error_logging(
        character,
        Character.UpdateSection.CONTACTS,
        character.update_contacts,
        force_update=force_update,
    )
    _log_character_update_success(character, Character.UpdateSection.CONTACTS)


# special tasks for updating contracts


@shared_task(
    **{
        **TASK_DEFAULTS_BIND_ONCE,
        **{"once": {"keys": ["character_pk", "force_update"], "graceful": True}},
    }
)
def update_character_contracts(
    self,
    character_pk: int,
    force_update: bool,
    root_task_id: Optional[str] = None,
    parent_task_id: Optional[str] = None,
) -> None:
    """Main task for updating contracts of a character"""
    character = Character.objects.get_cached(
        pk=character_pk, timeout=MEMBERAUDIT_TASKS_OBJECT_CACHE_TIMEOUT
    )
    section = Character.UpdateSection.CONTRACTS
    character.reset_update_section(
        section=section, root_task_id=root_task_id, parent_task_id=parent_task_id
    )
    logger.info(
        "%s: Updating %s", character, Character.UpdateSection.display_name(section)
    )
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
    """Update contract headers for a character."""

    character = Character.objects.get_cached(
        pk=character_pk, timeout=MEMBERAUDIT_TASKS_OBJECT_CACHE_TIMEOUT
    )
    _character_update_with_error_logging(
        character,
        Character.UpdateSection.CONTRACTS,
        character.update_contract_headers,
        force_update=force_update,
    )


@shared_task(**TASK_DEFAULTS_BIND_ONCE)
def update_character_contracts_items(self, character_pk: int):
    """Update items for all contracts of a character"""
    character = Character.objects.get_cached(
        pk=character_pk, timeout=MEMBERAUDIT_TASKS_OBJECT_CACHE_TIMEOUT
    )
    contract_pks = set(
        character.contracts.filter(
            contract_type__in=[
                CharacterContract.TYPE_ITEM_EXCHANGE,
                CharacterContract.TYPE_AUCTION,
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
    """Task for updating the items of a contract from ESI"""
    character = Character.objects.get_cached(
        pk=character_pk, timeout=MEMBERAUDIT_TASKS_OBJECT_CACHE_TIMEOUT
    )
    contract = CharacterContract.objects.get(pk=contract_pk)
    character.update_contract_items(contract)


@shared_task(**TASK_DEFAULTS_BIND_ONCE)
def update_character_contracts_bids(self, character_pk: int):
    """Update bids for all contracts of a character"""
    character = Character.objects.get_cached(
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
    _log_character_update_success(character, Character.UpdateSection.CONTRACTS)


@shared_task(**TASK_DEFAULTS_ONCE)
@when_esi_is_available
def update_contract_bids_esi(character_pk: int, contract_pk: int):
    """Task for updating the bids of a contract from ESI"""
    character = Character.objects.get_cached(
        pk=character_pk, timeout=MEMBERAUDIT_TASKS_OBJECT_CACHE_TIMEOUT
    )
    contract = CharacterContract.objects.get(pk=contract_pk)
    character.update_contract_bids(contract)


# Tasks for other objects


@shared_task(**TASK_DEFAULTS_ONCE)
@when_esi_is_available
def update_market_prices():
    """Update market prices from ESI"""
    EveMarketPrice.objects.update_from_esi(
        minutes_until_stale=MEMBERAUDIT_UPDATE_STALE_RING_2
    )


@shared_task(
    **{
        **TASK_DEFAULTS_BIND_ONCE,
        **{"once": {"keys": ["id"], "graceful": True}, "max_retries": None},
    }
)
def update_structure_esi(self, id: int, token_pk: int):
    """Updates a structure object from ESI
    and retries later if the ESI error limit has already been reached
    """
    try:
        token = Token.objects.get(pk=token_pk)
    except Token.DoesNotExist as ex:
        raise Token.DoesNotExist(
            f"Location #{id}: Requested token with pk {token_pk} does not exist"
        ) from ex

    try:
        Location.objects.structure_update_or_create_esi(id, token)
    except EsiOffline as ex:
        countdown = (30 + int(random.uniform(1, 20))) * 60
        logger.warning(
            "Location #%s: ESI appears to be offline. Trying again in %d minutes.",
            id,
            countdown,
        )
        raise self.retry(countdown=countdown) from ex
    except EsiErrorLimitExceeded as ex:
        logger.warning(
            "Location #%s: ESI error limit threshold reached. "
            "Trying again in %s seconds",
            id,
            ex.retry_in,
        )
        raise self.retry(countdown=ex.retry_in) from ex


@shared_task(
    **{
        **TASK_DEFAULTS_ONCE,
        **{"once": {"keys": ["id"], "graceful": True}, "max_retries": None},
    }
)
def update_mail_entity_esi(id: int, category: Optional[str] = None):
    """Updates a mail entity object from ESI
    and retries later if the ESI error limit has already been reached
    """
    MailEntity.objects.update_or_create_esi(id=id, category=category)


@shared_task(**TASK_DEFAULTS_BIND_ONCE)
def update_characters_skill_checks(self, force_update: bool = False) -> None:
    """Start the update of skill checks for all registered characters

    Args:
    - force_update: When set to True will always update regardless of stale status
    """
    section = Character.UpdateSection.SKILL_SETS
    priority = determine_task_priority(self) or MEMBERAUDIT_TASKS_LOW_PRIORITY
    for character in Character.objects.all():
        if force_update or character.is_update_section_stale(section):
            update_character_section.apply_async(
                kwargs={
                    "character_pk": character.pk,
                    "section": section,
                    "force_update": force_update,
                },
                priority=priority,
            )


@shared_task(**TASK_DEFAULTS_ONCE)
def check_character_consistency(character_pk) -> None:
    """Check consistency of a character."""
    character = Character.objects.get_cached(
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
