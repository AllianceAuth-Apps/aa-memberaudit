"""
Character and CharacterUpdateStatus models
"""

import datetime as dt
import hashlib
import json
from typing import Any, Callable, Optional, Tuple

from bravado.exception import HTTPInternalServerError

from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from esi.errors import TokenError
from esi.models import Token
from eveuniverse.models import EveEntity

from allianceauth.authentication.models import CharacterOwnership
from allianceauth.eveonline.models import EveCharacter
from allianceauth.services.hooks import get_extension_logger
from app_utils.allianceauth import notify_throttled
from app_utils.logging import LoggerAddTag

from memberaudit import __title__
from memberaudit.app_settings import (
    MEMBERAUDIT_APP_NAME,
    MEMBERAUDIT_DEVELOPER_MODE,
    MEMBERAUDIT_UPDATE_STALE_OFFSET,
    MEMBERAUDIT_UPDATE_STALE_RING_1,
    MEMBERAUDIT_UPDATE_STALE_RING_2,
    MEMBERAUDIT_UPDATE_STALE_RING_3,
)
from memberaudit.helpers import store_debug_data_to_disk
from memberaudit.managers.characters import (
    CharacterManager,
    CharacterUpdateStatusManager,
)

logger = LoggerAddTag(get_extension_logger(__name__), __title__)


class Character(models.Model):  # pylint: disable=too-many-public-methods
    """A character synced by this app

    This is the head model for all characters
    """

    class UpdateSection(models.TextChoices):
        """A section of content for a character that can be updated separately."""

        ASSETS = "assets", _("assets")
        ATTRIBUTES = "attributes", _("attributes")
        CHARACTER_DETAILS = "character_details", ("character details")
        CONTACTS = "contacts", _("contacts")
        CONTRACTS = "contracts", _("contracts")
        CORPORATION_HISTORY = "corporation_history", _("corporation history")
        FW_STATS = "fw_stats", _("faction warfare statistics")
        IMPLANTS = "implants", _("implants")
        JUMP_CLONES = "jump_clones", _("jump clones")
        LOCATION = "location", _("location")
        LOYALTY = "loyalty", _("loyalty")
        MAILS = "mails", _("mails")
        MINING_LEDGER = "mining_ledger", _("mining ledger")
        ONLINE_STATUS = "online_status", _("online status")
        PLANETS = "planets", _("planets")
        SHIP = "ship", _("ship")
        SKILLS = "skills", _("skills")
        SKILL_QUEUE = "skill_queue", _("skill queue")
        SKILL_SETS = "skill_sets", _("skill sets")
        STANDINGS = "standings", _("standings")
        WALLET_BALLANCE = "wallet_balance", _("wallet balance")
        WALLET_JOURNAL = "wallet_journal", _("wallet journal")
        WALLET_TRANSACTIONS = "wallet_transactions", _("wallet transactions")

        @classmethod
        def method_name(cls, section: str) -> str:
            """returns name of update method corresponding with the given section

            Raises:
            - ValueError if section is invalid
            """
            if section not in cls.values:
                raise ValueError(f"Unknown section: {section}")

            return f"update_{section}"

        @classmethod
        def display_name(cls, section: str) -> str:
            """returns display name of given section

            Raises:
            - ValueError if section is invalid
            """
            for short_name, long_name in cls.choices:
                if short_name == section:
                    return long_name

            raise ValueError(f"Unknown section: {section}")

    UPDATE_SECTION_RINGS_MAP = {
        UpdateSection.ASSETS: 3,
        UpdateSection.ATTRIBUTES: 3,
        UpdateSection.CHARACTER_DETAILS: 2,
        UpdateSection.CONTACTS: 2,
        UpdateSection.CONTRACTS: 2,
        UpdateSection.CORPORATION_HISTORY: 2,
        UpdateSection.FW_STATS: 3,
        UpdateSection.IMPLANTS: 2,
        UpdateSection.JUMP_CLONES: 2,
        UpdateSection.LOCATION: 1,
        UpdateSection.LOYALTY: 2,
        UpdateSection.MAILS: 2,
        UpdateSection.MINING_LEDGER: 2,
        UpdateSection.ONLINE_STATUS: 1,
        UpdateSection.PLANETS: 2,
        UpdateSection.SHIP: 1,
        UpdateSection.SKILLS: 2,
        UpdateSection.SKILL_SETS: 2,
        UpdateSection.SKILL_QUEUE: 1,
        UpdateSection.STANDINGS: 21,
        UpdateSection.WALLET_BALLANCE: 2,
        UpdateSection.WALLET_JOURNAL: 2,
        UpdateSection.WALLET_TRANSACTIONS: 2,
    }

    class UpdateStatus(models.TextChoices):
        """Update status of a character."""

        OK = "ok", _("ok")
        IN_PROGRESS = "in_progress", _("in progress")
        INCOMPLETE = "incomplete", _("incomplete")
        ERROR = "error", _("error")
        DISABLED = "disabled", _("disabled")

    id = models.AutoField(primary_key=True)
    eve_character = models.OneToOneField(
        EveCharacter,
        related_name="memberaudit_character",
        on_delete=models.CASCADE,
        verbose_name=_("eve character"),
    )

    created_at = models.DateTimeField(
        auto_now_add=True, db_index=True, verbose_name=_("created at")
    )
    is_shared = models.BooleanField(
        default=False,
        verbose_name=_("is shared"),
        help_text="Shared characters can be viewed by recruiters",
    )
    is_disabled = models.BooleanField(
        default=False,
        verbose_name=_("is disabled"),
        help_text="Disabled characters are no longer updated from ESI.",
    )
    mailing_lists = models.ManyToManyField(
        "MailEntity", related_name="characters", verbose_name=_("mailing lists")
    )

    objects = CharacterManager()

    class Meta:
        default_permissions = ()
        verbose_name = _("character")
        verbose_name_plural = _("characters")

    def __str__(self) -> str:
        return f"{self.eve_character.character_name} (PK:{self.pk})"

    def __repr__(self) -> str:
        return f"Character(pk={self.pk}, eve_character='{self.eve_character}')"

    @cached_property
    def name(self) -> str:
        """Return the name of this character."""
        return self.eve_character.character_name

    @cached_property
    def character_ownership(self) -> Optional[CharacterOwnership]:
        """Return the character ownership object of this character."""
        try:
            return self.eve_character.character_ownership
        except ObjectDoesNotExist:
            return None

    @cached_property
    def user(self) -> Optional[User]:
        """Return the user this character belongs to or None."""
        try:
            return self.character_ownership.user
        except AttributeError:
            return None

    @cached_property
    def main_character(self) -> Optional[EveCharacter]:
        """Return the main character related to this character or None."""
        try:
            return self.character_ownership.user.profile.main_character
        except AttributeError:
            return None

    @cached_property
    def is_main(self) -> bool:
        """Return True if this character is a main character, else False"""
        try:
            return self.main_character.character_id == self.eve_character.character_id
        except AttributeError:
            return False

    @cached_property
    def is_orphan(self) -> bool:
        """Whether this character is not owned by a user."""
        return self.character_ownership is None

    def details_or_none(self):
        """Return character details or None if it does not exist."""
        try:
            return self.details
        except ObjectDoesNotExist:
            return None

    def user_is_owner(self, user: User) -> bool:
        """Return True if the given user is owner of this character"""
        try:
            return self.user == user
        except AttributeError:
            return False

    def user_has_scope(self, user: User) -> bool:
        """Returns True if given user has scope to access this character"""
        try:
            if self.user == user:  # shortcut for better performance
                return True
        except AttributeError:
            pass
        return Character.objects.user_has_scope(user).filter(pk=self.pk).exists()

    def user_has_access(self, user: User) -> bool:
        """Returns True if given user has permission to access this character
        in the character viewer
        """
        try:
            if self.user == user:  # shortcut for better performance
                return True
        except AttributeError:
            pass
        return Character.objects.user_has_access(user).filter(pk=self.pk).exists()

    def is_update_status_ok(self) -> Optional[bool]:
        """returns status of last update

        Returns:
        - True: If update was complete and without errors
        - False if there where any errors
        - None: if last update is incomplete
        """
        errors_count = self.update_status_set.filter(is_success=False).count()
        ok_count = self.update_status_set.filter(is_success=True).count()
        if errors_count > 0:
            return False
        if ok_count == len(Character.UpdateSection.choices):
            return True
        return None

    @classmethod
    def update_section_time_until_stale(cls, section: str) -> dt.timedelta:
        """time until given update section is considered stale"""
        ring = cls.UPDATE_SECTION_RINGS_MAP[cls.UpdateSection(section)]
        if ring == 1:
            minutes = MEMBERAUDIT_UPDATE_STALE_RING_1
        elif ring == 2:
            minutes = MEMBERAUDIT_UPDATE_STALE_RING_2
        else:
            minutes = MEMBERAUDIT_UPDATE_STALE_RING_3

        # setting reduced by offset to ensure all sections are stale when
        # periodic task starts
        return dt.timedelta(minutes=minutes - MEMBERAUDIT_UPDATE_STALE_OFFSET)

    @classmethod
    def sections_in_ring(cls, ring: int) -> set:
        """returns set of sections for given ring"""
        return {
            section
            for section, ring_num in cls.UPDATE_SECTION_RINGS_MAP.items()
            if ring_num == ring
        }

    def is_update_section_stale(self, section: str) -> bool:
        """returns True if the give update section is stale, else False"""
        try:
            update_status = self.update_status_set.get(
                section=section,
                is_success=True,
                started_at__isnull=False,
                finished_at__isnull=False,
            )
        except (CharacterUpdateStatus.DoesNotExist, ObjectDoesNotExist, AttributeError):
            return True

        deadline = now() - self.update_section_time_until_stale(section)
        return update_status.started_at < deadline

    def has_section_changed(
        self, section: str, content: Any, hash_num: int = 1
    ) -> bool:
        """returns False if the content hash for this section has not changed, else True"""
        try:
            section_obj: CharacterUpdateStatus = self.update_status_set.get(
                section=section
            )
        except CharacterUpdateStatus.DoesNotExist:
            return True
        return section_obj.has_changed(content=content, hash_num=hash_num)

    def update_section_content_hash(
        self, section: str, content: Any, hash_num: int = 1
    ) -> None:
        """Update hash for a section."""
        try:
            section_obj: CharacterUpdateStatus = self.update_status_set.get(
                section=section
            )
        except CharacterUpdateStatus.DoesNotExist:
            section_obj, _ = CharacterUpdateStatus.objects.get_or_create(
                character=self, section=section
            )
        section_obj.update_content_hash(content=content, hash_num=hash_num)

    def reset_update_section(
        self,
        section: str,
        root_task_id: Optional[str] = None,
        parent_task_id: Optional[str] = None,
    ) -> "CharacterUpdateStatus":
        """Reset status of given update section and returns it."""
        try:
            section_onj: CharacterUpdateStatus = self.update_status_set.get(
                section=section
            )
        except CharacterUpdateStatus.DoesNotExist:
            section_onj, _ = CharacterUpdateStatus.objects.get_or_create(
                character=self, section=section
            )
        section_onj.reset(root_task_id, parent_task_id)
        return section_onj

    def is_section_updating(self, section: str) -> bool:
        """returns True if section is currently updating, or does not exist, else False"""
        try:
            section_obj = self.update_status_set.get(section=section)
        except CharacterUpdateStatus.DoesNotExist:
            return True
        return section_obj.is_updating

    def update_data_if_changed_or_forced(
        self,
        section: str,
        fetch_func: Callable,
        store_func: Optional[Callable],
        force_update: bool = False,
        hash_num: int = 1,
    ) -> Tuple[Any, Optional[bool]]:
        """Fetch data from ESI and store it if it has changed or it is forced.

        Args:
            - section: Name of the section this update related to
            - fetch_func: A function that fetched the data from ESI
            - store_func: A function that stored the data in the DB.
                This can be skipped by providing None.
                store_func can optionally return a list of entity IDs to resolve
            - forced_update: Data will always be stored when set to True
            - hash_num: To access sub-sections by ID

        Returns:
            - A tuple of the result data or None if data is unchanged
                and a flag that is True if data was changed,
                False when it was not change, else None
        """

        try:
            data = fetch_func(character=self)
        except HTTPInternalServerError as ex:
            # handle the occasional occurring http 500 error from this endpoint
            logger.warning(
                "%s: Received an HTTP internal server error "
                "when trying to fetch %s: %s ",
                self,
                section,
                ex,
            )
            return None, None

        if MEMBERAUDIT_DEVELOPER_MODE:
            store_debug_data_to_disk(self, data, f"{section}_{hash_num}")

        if not force_update and not self.has_section_changed(
            section=section, content=data, hash_num=hash_num
        ):
            logger.info("%s: %s has not changed", section, self)
            return None, False

        if store_func:
            ids_to_resolve = store_func(self, data)
            if ids_to_resolve:
                logger.info(
                    "%s: Trying to resolve %d EveEntity IDs for %s",
                    self,
                    len(ids_to_resolve),
                    section,
                )
                EveEntity.objects.bulk_resolve_ids(ids_to_resolve)

        self.update_section_content_hash(
            section=section, content=data, hash_num=hash_num
        )
        return data, True

    def fetch_token(self, scopes=None) -> Token:
        """returns valid token for character

        Args:
        - scopes: Optionally provide the required scopes.
        Otherwise will use all scopes defined for this character.

        Exceptions:
        - TokenError: If no valid token can be found
        """
        if self.is_orphan:
            raise TokenError(
                f"Can not find token for orphaned character: {self}"
            ) from None
        token = (
            Token.objects.prefetch_related("scopes")
            .filter(user=self.user, character_id=self.eve_character.character_id)
            .require_scopes(scopes if scopes else self.get_esi_scopes())
            .require_valid()
            .first()
        )
        if not token:
            message_id = f"{__title__}-fetch_token-{self.pk}-TokenError"
            title = f"{__title__}: Invalid or missing token for {self.eve_character}"
            message = (
                f"{MEMBERAUDIT_APP_NAME} could not find a valid token for your "
                f"character {self.eve_character}.\n"
                f"Please re-add that character to {MEMBERAUDIT_APP_NAME} "
                "at your earliest convenience to update your token."
            )
            if self.user:
                notify_throttled(
                    message_id=message_id, user=self.user, title=title, message=message
                )
            raise TokenError(f"Could not find a matching token for {self}")
        return token

    def assets_build_list_from_esi(self, force_update=False) -> Optional[list]:
        """fetches assets from ESI and preloads related objects from ESI

        returns the asset_list or None if no update is required
        """
        return self.assets.fetch_from_esi(self, force_update)

    def assets_preload_objects(self, asset_list: list) -> None:
        """preloads objects needed to build the asset tree"""
        self.assets.preload_objects_from_esi(self, asset_list)

    def update_attributes(self, force_update: bool = False):
        """update the character's attributes"""
        from memberaudit.models import CharacterAttributes

        CharacterAttributes.objects.update_or_create_esi(self, force_update)

    def update_character_details(self, force_update: bool = False):
        """syncs the character details for the given character"""
        from memberaudit.models import CharacterDetails

        CharacterDetails.objects.update_or_create_esi(self, force_update)

    def update_contact_labels(self, force_update: bool = False):
        """Update contact labels for this character."""
        self.contact_labels.update_or_create_esi(self, force_update)

    def update_contacts(self, force_update: bool = False):
        """Update contacts for this character."""
        self.contacts.update_or_create_esi(self, force_update)

    def update_contract_headers(self, force_update: bool = False):
        """Update the character's contract headers."""
        self.contracts.update_or_create_esi(self, force_update)

    def update_contract_items(self, contract):
        """Update the character's contract items."""
        contract.items.update_or_create_esi(self, contract)

    def update_contract_bids(self, contract):
        """Update the character's contract bids."""
        contract.bids.update_or_create_esi(self, contract)

    def update_corporation_history(self, force_update: bool = False):
        """syncs the character's corporation history"""
        self.corporation_history.update_or_create_esi(self, force_update)

    def update_fw_stats(self, force_update: bool = False):
        """Update FW stats  for the given character"""
        from memberaudit.models import CharacterFwStats

        CharacterFwStats.objects.update_or_create_esi(self, force_update)

    def update_implants(self, force_update: bool = False):
        """update the character's implants"""
        self.implants.update_or_create_esi(self, force_update)

    def update_location(self, force_update: bool = False):
        """update the location for the given character"""
        from memberaudit.models import CharacterLocation

        CharacterLocation.objects.update_or_create_esi(self, force_update)

    def update_loyalty(self, force_update: bool = False):
        """syncs the character's loyalty entries"""
        self.loyalty_entries.update_or_create_esi(self, force_update)

    def update_jump_clones(self, force_update: bool = False):
        """updates the character's jump clones"""
        self.jump_clones.update_or_create_esi(self, force_update)

    def update_mailing_lists(self, force_update: bool = False):
        """Update mailing lists with input from given character."""
        self.mailing_lists.update_or_create_mailing_lists_esi(self, force_update)

    def update_mail_labels(self, force_update: bool = False):
        """Update the mail labels for the given character"""
        self.mail_labels.update_or_create_esi(self, force_update)

    def update_mail_headers(self, force_update: bool = False):
        """Update the mail headers for the given character"""
        self.mails.update_or_create_headers_esi(self, force_update)

    def update_mail_body(self, mail) -> None:
        """Update the mail body for the given character"""
        self.mails.update_or_create_body_esi(self, mail)

    def update_mining_ledger(self, force_update: bool = False):
        """Update mining ledger from ESI for this character."""
        self.mining_ledger.update_or_create_esi(self, force_update)

    def update_online_status(self, force_update: bool = False):
        """Update the character's online status"""
        from memberaudit.models import CharacterOnlineStatus

        CharacterOnlineStatus.objects.update_or_create_esi(self, force_update)

    def update_planets(self, force_update: bool = False):
        """Update the character's planets."""
        self.planets.update_or_create_esi(self, force_update)

    def update_ship(self, force_update: bool = False):
        """Update the ship for the given character."""
        from memberaudit.models import CharacterShip

        CharacterShip.objects.update_or_create_esi(self, force_update)

    def update_skill_queue(self, force_update: bool = False):
        """update the character's skill queue"""
        self.skillqueue.update_or_create_esi(self, force_update)

    def update_skill_sets(self):
        """Checks if character has the skills needed for skill sets
        and updates results in database
        """
        self.skill_set_checks.update_for_character(self)

    def update_skills(self, force_update: bool = False):
        """update the character's skill"""
        self.skills.update_or_create_esi(self, force_update)

    def update_standings(self, force_update: bool = False):
        """Update the character's standings."""
        self.standings.update_or_create_esi(self, force_update)

    def update_wallet_balance(self, force_update: bool = False):
        """syncs the character's wallet balance"""
        from memberaudit.models import CharacterWalletBalance

        CharacterWalletBalance.objects.update_or_create_esi(self, force_update)

    def update_wallet_journal(self, force_update: bool = False) -> None:
        """syncs the character's wallet journal"""
        self.wallet_journal.update_or_create_esi(self, force_update)

    def update_wallet_transactions(self, force_update: bool = False):
        """syncs the character's wallet transactions"""
        self.wallet_transactions.update_or_create_esi(self, force_update)

    @classmethod
    def get_esi_scopes(cls) -> list:
        """Return the ESI scopes required to update this character."""
        return [
            "esi-assets.read_assets.v1",
            "esi-bookmarks.read_character_bookmarks.v1",
            "esi-calendar.read_calendar_events.v1",
            "esi-characters.read_agents_research.v1",
            "esi-characters.read_blueprints.v1",
            "esi-characters.read_contacts.v1",
            "esi-characters.read_fatigue.v1",
            "esi-characters.read_fw_stats.v1",
            "esi-characters.read_loyalty.v1",
            "esi-characters.read_medals.v1",
            "esi-characters.read_notifications.v1",
            "esi-characters.read_opportunities.v1",
            "esi-characters.read_standings.v1",
            "esi-characters.read_titles.v1",
            "esi-clones.read_clones.v1",
            "esi-clones.read_implants.v1",
            "esi-contracts.read_character_contracts.v1",
            "esi-corporations.read_corporation_membership.v1",
            "esi-industry.read_character_jobs.v1",
            "esi-industry.read_character_mining.v1",
            "esi-killmails.read_killmails.v1",
            "esi-location.read_location.v1",
            "esi-location.read_online.v1",
            "esi-location.read_ship_type.v1",
            "esi-mail.organize_mail.v1",
            "esi-mail.read_mail.v1",
            "esi-markets.read_character_orders.v1",
            "esi-markets.structure_markets.v1",
            "esi-planets.manage_planets.v1",
            "esi-planets.read_customs_offices.v1",
            "esi-search.search_structures.v1",
            "esi-skills.read_skillqueue.v1",
            "esi-skills.read_skills.v1",
            "esi-universe.read_structures.v1",
            "esi-wallet.read_character_wallet.v1",
        ]

    def update_sharing_consistency(self):
        """Update sharing to ensure consistency with permissions."""
        if (
            self.is_shared
            and self.user
            and not self.user.has_perm("memberaudit.share_characters")
        ):
            self.is_shared = False
            self.save()
            logger.info(
                "%s: Unshared this character, "
                "because it's owner no longer has the permission to share characters.",
                self,
            )


class CharacterUpdateStatus(models.Model):
    """Update status for a character"""

    character = models.ForeignKey(
        Character, on_delete=models.CASCADE, related_name="update_status_set"
    )

    section = models.CharField(
        max_length=64, choices=Character.UpdateSection.choices, db_index=True
    )
    is_success = models.BooleanField(
        null=True,
        default=None,
        db_index=True,
    )
    content_hash_1 = models.CharField(max_length=32, default="")
    content_hash_2 = models.CharField(max_length=32, default="")
    content_hash_3 = models.CharField(max_length=32, default="")
    last_error_message = models.TextField()
    root_task_id = models.CharField(
        max_length=36,
        default="",
        db_index=True,
        help_text="ID of update_all_characters task that started this update",
    )
    parent_task_id = models.CharField(
        max_length=36,
        default="",
        db_index=True,
        help_text="ID of character_update task that started this update",
    )
    started_at = models.DateTimeField(null=True, default=None, db_index=True)
    finished_at = models.DateTimeField(null=True, default=None, db_index=True)

    objects = CharacterUpdateStatusManager()

    class Meta:
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(
                fields=["character", "section"],
                name="functional_pk_charactersyncstatus",
            )
        ]
        verbose_name = _("character update status")
        verbose_name_plural = _("character update status")

    def __str__(self) -> str:
        return f"{self.character}-{self.section}"

    @property
    def is_updating(self) -> bool:
        """Return True if this section is currently being updated."""
        if not self.started_at and not self.finished_at:
            return False

        return self.started_at is not None and self.finished_at is None

    def has_changed(self, content: Any, hash_num: int = 1) -> bool:
        """Returns True if given content is not the same as previous one, else False.

        Specify optionally which sub section to update via the hash_num (1, 2 or 3).
        """
        new_hash = self._calculate_hash(content)
        if hash_num == 2:
            content_hash = self.content_hash_2
        elif hash_num == 3:
            content_hash = self.content_hash_3
        else:
            content_hash = self.content_hash_1

        return new_hash != content_hash

    def update_content_hash(self, content: Any, hash_num: int = 1):
        """Update content hash for this update status.

        Specify optionally which sub section to update via the hash_num (1, 2 or 3).
        """
        new_hash = self._calculate_hash(content)
        if hash_num == 2:
            self.content_hash_2 = new_hash
        elif hash_num == 3:
            self.content_hash_3 = new_hash
        else:
            self.content_hash_1 = new_hash

        self.save()

    @staticmethod
    def _calculate_hash(content: Any) -> str:
        return hashlib.md5(
            json.dumps(content, cls=DjangoJSONEncoder).encode("utf-8")
        ).hexdigest()

    def reset(
        self, root_task_id: Optional[str] = None, parent_task_id: Optional[str] = None
    ) -> None:
        """resets this update status"""
        self.is_success = None
        self.last_error_message = ""
        self.started_at = now()
        self.finished_at = None
        self.root_task_id = root_task_id if root_task_id else ""
        self.parent_task_id = parent_task_id if root_task_id else ""
        self.save()
