"""Character and CharacterUpdateStatus models."""

# pylint: disable = too-many-lines

import datetime as dt
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Set

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
from allianceauth.notifications import notify
from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag

from memberaudit import __title__
from memberaudit.app_settings import (
    MEMBERAUDIT_APP_NAME,
    MEMBERAUDIT_FEATURE_ROLES_ENABLED,
    MEMBERAUDIT_NOTIFY_TOKEN_ERRORS,
    MEMBERAUDIT_SECTION_STALE_MINUTES_CONFIG,
    MEMBERAUDIT_SECTION_STALE_MINUTES_GLOBAL_DEFAULT,
    MEMBERAUDIT_SECTION_STALE_MINUTES_SECTION_DEFAULTS,
)
from memberaudit.constants import EveGroupId
from memberaudit.errors import TokenDoesNotExist
from memberaudit.helpers import UpdateSectionResult
from memberaudit.managers.characters import (
    CharacterManager,
    CharacterUpdateStatusManager,
)
from memberaudit.models._helpers import (
    AddGenericReprMixin,
    store_character_data_to_disk_when_enabled,
)

logger = LoggerAddTag(get_extension_logger(__name__), __title__)


@dataclass(frozen=True)
class _CharacterNeedsUpdate:
    """An object which knows what character sections need to be updated."""

    section_map: Dict["Character.UpdateSection", bool]
    character: "Character"

    def __bool__(self) -> bool:
        """Return True if any section needs to be updated, else False."""
        return any(self.section_map.values())

    def for_section(self, section: "Character.UpdateSection") -> bool:
        """Return True if the given section needs to be updated, else False."""
        return self.section_map[Character.UpdateSection(section)]


class Character(
    AddGenericReprMixin, models.Model
):  # pylint: disable=too-many-public-methods
    """A character in Eve Online managed by Member Audit."""

    # TODO: Maybe move this enum to outside, so it can be imported more easily
    # by other modules
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
        ROLES = "roles", _("roles")
        SHIP = "ship", _("ship")
        SKILLS = "skills", _("skills")
        SKILL_QUEUE = "skill_queue", _("skill queue")
        SKILL_SETS = "skill_sets", _("skill sets")
        STANDINGS = "standings", _("standings")
        TITLES = "titles", _("titles")
        WALLET_BALLANCE = "wallet_balance", _("wallet balance")
        WALLET_JOURNAL = "wallet_journal", _("wallet journal")
        WALLET_TRANSACTIONS = "wallet_transactions", _("wallet transactions")

        @property
        def method_name(self) -> str:
            """Return name of update method corresponding with this section."""
            return f"update_{self.value}"

        @classmethod
        def enabled_sections(cls) -> Set["Character.UpdateSection"]:
            """Return enabled sections."""
            sections = set(Character.UpdateSection)
            if not MEMBERAUDIT_FEATURE_ROLES_ENABLED:
                sections.discard(Character.UpdateSection.ROLES)
            return sections

        @classmethod
        def time_until_section_updates_are_stale(
            cls,
        ) -> Dict["Character.UpdateSection", int]:
            """Return map of each section and their time until an update is stale."""
            config = {
                section: MEMBERAUDIT_SECTION_STALE_MINUTES_GLOBAL_DEFAULT
                for section in cls
            }

            section_defaults = MEMBERAUDIT_SECTION_STALE_MINUTES_SECTION_DEFAULTS
            for key, value in section_defaults.items():
                config[cls(key)] = value

            section_config = MEMBERAUDIT_SECTION_STALE_MINUTES_CONFIG
            for key, value in section_config.items():
                try:
                    config[cls(key)] = value
                except ValueError:
                    logger.warning(
                        "Ignoring invalid section name '%s' in config "
                        "for stale minutes. "
                        "Please correct the invalid config.",
                        value,
                    )

            return config

    class TotalUpdateStatus(models.TextChoices):
        """An summary update status of a character
        representing the update status of all sections.
        """

        DISABLED = "disabled", _("disabled")
        ERROR = "error", _("error")
        LIMITED_TOKEN = "limited_token", _("limited token")
        INCOMPLETE = "incomplete", _("incomplete")
        IN_PROGRESS = "in_progress", _("in progress")
        OK = "ok", _("ok")

        def has_issue(self) -> bool:
            """Return True when status is representing an issue."""
            return self in {
                self.DISABLED,
                self.ERROR,
                self.INCOMPLETE,
                self.LIMITED_TOKEN,
            }

        def bootstrap_style_class(self) -> str:
            """Return bootstrap corresponding bootstrap style class."""
            my_map = {
                self.DISABLED: "text-muted",
                self.ERROR: "text-danger",
                self.IN_PROGRESS: "text-info",
                self.INCOMPLETE: "text-warning",
                self.LIMITED_TOKEN: "text-warning",
                self.OK: "text-success",
            }
            return my_map.get(self, "")

        def description(self) -> str:
            """Return description for an enum object."""
            my_map = {
                self.DISABLED: _("Update is disabled"),
                self.ERROR: _("Errors occurred during update"),
                self.IN_PROGRESS: _("Update is in progress"),
                self.INCOMPLETE: _("One or more sections have not yet been updated"),
                self.LIMITED_TOKEN: _(
                    "One section can not be updated due to a token error"
                ),
                self.OK: _("Update completed successfully"),
            }
            return my_map.get(self, "")

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
    token_error_notified_at = models.DateTimeField(
        default=None,
        null=True,
        help_text=_("Time when user was last notified about a token error."),
    )

    objects = CharacterManager()

    class Meta:
        default_permissions = ()
        verbose_name = _("character")
        verbose_name_plural = _("characters")

    def __str__(self) -> str:
        try:
            return f"{self.eve_character.character_name} (ID:{self.id})"
        except EveCharacter.DoesNotExist:
            return f"Character ID {self.id}"

    # def __repr__(self) -> str:
    #     return f"Character(pk={self.pk}, eve_character='{self.eve_character}')"

    def save(self, *args, **kwargs: dict):
        ignore_cache = kwargs.pop("ignore_cache", False)  # needed for NoSocketsTestCase
        super().save(*args, **kwargs)
        if self.pk and not ignore_cache:  # clear this object from cache if it is there
            self.clear_cache()

    @cached_property
    def name(self) -> str:
        """Return the name of this character."""
        return str(self.eve_character.character_name)

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
        """Return True if this character is a main character, else False."""
        try:
            return self.main_character.character_id == self.eve_character.character_id
        except AttributeError:
            return False

    @cached_property
    def is_orphan(self) -> bool:
        """Return True if this character is an orphan else False.

        An orphan is a character that is not owned anymore by a user."""
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
        """Returns True if the given user has the permission to access this character."""
        try:
            if self.user == user:  # shortcut for better performance
                return True
        except AttributeError:
            pass
        return Character.objects.user_has_scope(user).filter(pk=self.pk).exists()

    def user_has_access(self, user: User) -> bool:
        """Returns True if given user has permission to access this character
        in the character viewer.
        """
        try:
            if self.user == user:  # shortcut for better performance
                return True
        except AttributeError:
            pass
        return Character.objects.user_has_access(user).filter(pk=self.pk).exists()

    def has_token_issue(self) -> bool:
        """Return True if character has run into a token error during update, else False."""
        return (
            self.update_status_set.filter_enabled_sections()
            .filter(has_token_error=True)
            .exists()
        )

    def calc_total_update_status(self) -> TotalUpdateStatus:
        """Calculate and return the total update status of this character."""
        if self.is_disabled:
            return self.TotalUpdateStatus.DISABLED

        qs = Character.objects.filter(pk=self.pk).annotate_total_update_status()
        total_update_status = list(qs.values_list("total_update_status", flat=True))[0]
        return self.TotalUpdateStatus(total_update_status)

    def is_update_status_ok(self) -> Optional[bool]:
        """Return summary status of last update for this character.

        Returns:
        - True: if update was complete and without errors
        - False if there where any errors
        - None: if last update is incomplete
        """
        status = self.calc_total_update_status()
        if status == Character.TotalUpdateStatus.OK:
            return True
        if status == Character.TotalUpdateStatus.ERROR:
            return False
        return None

    def reset_token_error_notified_if_status_ok(self):
        """Reset last notification on token error when update is OK again."""
        if self.token_error_notified_at:
            if self.calc_total_update_status() == Character.TotalUpdateStatus.OK:
                self.token_error_notified_at = None
                self.save(update_fields=["token_error_notified_at"])

    def calc_update_needed(self) -> _CharacterNeedsUpdate:
        """Return map of section and if they need to be update."""
        sections_needs_update = {
            section: True for section in self.UpdateSection.enabled_sections()
        }
        status_all: List[CharacterUpdateStatus] = self.update_status_set.all()
        sections_current = {
            obj.section: obj.is_update_needed()
            for obj in status_all
            if obj.section in sections_needs_update
        }
        sections_needs_update.update(sections_current)
        return _CharacterNeedsUpdate(sections_needs_update, self)

    def update_status_for_section(
        self, section: UpdateSection
    ) -> Optional["CharacterUpdateStatus"]:
        "Return update status for a section when it exists or None."
        section = self.UpdateSection(section)
        try:
            return self.update_status_set.get(section=section)
        except CharacterUpdateStatus.DoesNotExist:
            return None

    def is_update_needed_for_section(self, section: UpdateSection) -> bool:
        """Return True if the given section needs to be updated,
        else False.
        """
        status = self.update_status_for_section(section)
        if not status:
            return True
        return status.is_update_needed()

    def has_section_changed(
        self, section: UpdateSection, content: Any, hash_num: int = 1
    ) -> bool:
        """Return False if the content hash for this character's section
        has not changed, else return True.
        """
        status = self.update_status_for_section(section)
        if not status:
            return True
        return status.has_changed(content=content, hash_num=hash_num)

    def update_section_content_hash(
        self, section: UpdateSection, content: Any, hash_num: int = 1
    ) -> None:
        """Update hash for a section."""
        section_obj: CharacterUpdateStatus = self.update_status_set.get_or_create(
            character=self, section=section
        )[0]
        section_obj.update_content_hash(content=content, hash_num=hash_num)

    def reset_update_section(self, section: UpdateSection) -> "CharacterUpdateStatus":
        """Reset status of given update section and returns it."""
        update_status_obj: CharacterUpdateStatus = self.update_status_set.get_or_create(
            section=section
        )[0]
        update_status_obj.reset()
        return update_status_obj

    def update_status_as_dict(self) -> Dict[str, Any]:
        """Return current update status for this character as dict."""
        return {obj.section: obj for obj in self.update_status_set.all()}

    def update_section_if_changed(
        self,
        section: UpdateSection,
        fetch_func: Callable,
        store_func: Optional[Callable],
        force_update: bool = False,
        hash_num: int = 1,
    ) -> UpdateSectionResult:
        """Update a character's section from ESI if it has changed or is forced.

        Args:
            - section: Section this update is related to
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
        section = self.UpdateSection(section)
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
            return UpdateSectionResult(is_changed=None, is_updated=False)

        store_character_data_to_disk_when_enabled(
            character=self,
            data=data,
            section=section,
            suffix=hash_num if hash_num > 1 else "",
        )

        is_changed = self.has_section_changed(
            section=section, content=data, hash_num=hash_num
        )
        if not force_update and not is_changed:
            logger.info("%s: %s has not changed", self, section.label)
            return UpdateSectionResult(is_changed=is_changed, is_updated=False)

        if store_func:
            ids_to_resolve = store_func(self, data)
            is_updated = True
            if ids_to_resolve:
                logger.debug(
                    "%s: Received %d EveEntity IDs from %s "
                    "which might need to be resolved",
                    self,
                    len(ids_to_resolve),
                    section,
                )
                EveEntity.objects.bulk_resolve_ids(ids_to_resolve)
        else:
            is_updated = False

        self.update_section_content_hash(
            section=section, content=data, hash_num=hash_num
        )
        return UpdateSectionResult(
            is_changed=is_changed, is_updated=is_updated, data=data
        )

    def update_section_log_result(
        self,
        section: UpdateSection,
        is_success: bool,
        is_updated: bool = False,
        error_message: str = None,
    ) -> None:
        """Log update result for a character's section."""
        error_message = error_message if error_message else ""
        defaults = {
            "is_success": is_success,
            "has_token_error": False,
            "error_message": error_message,
            "run_finished_at": now(),
        }
        obj: CharacterUpdateStatus = self.update_status_set.update_or_create(
            section=section, defaults=defaults
        )[0]
        if is_updated:
            obj.update_started_at = obj.run_started_at
            obj.update_finished_at = now()
            obj.save()

        status = "successfully" if is_success else "with errors"
        logger.info("%s: %s update run completed %s", self, section.label, status)

    def perform_update_with_error_logging(
        self, section: UpdateSection, method: Callable, *args, **kwargs
    ) -> UpdateSectionResult:
        """Facilitate catching and logging of exceptions potentially occurring
        during a character update.
        """
        try:
            result = method(*args, **kwargs)
        except Exception as ex:
            error_message = f"{type(ex).__name__}: {str(ex)}"
            is_token_error = isinstance(ex, (TokenError))
            logger.error(
                "%s: %s: Error ocurred: %s",
                self,
                section.label,
                error_message,
                exc_info=not is_token_error,  # hide details when token error
            )
            self.update_status_set.update_or_create(
                character=self,
                section=section,
                defaults={
                    "is_success": False,
                    "has_token_error": is_token_error,
                    "error_message": error_message,
                    "run_finished_at": now(),
                },
            )
            raise ex

        if not isinstance(result, UpdateSectionResult):
            raise TypeError(
                f"{method}: Method must have return type: UpdateSectionResult"
            )

        return result

    def fetch_token(self, scopes=None) -> Token:
        """Return a valid token for this character and scope.

        Args:
            - scopes: Optionally provide the required scopes.
            Otherwise will use all scopes defined for this character.

        Exceptions:
            - TokenDoesNotExist: If no matching token is found
            - TokenError: Various token errors
        """
        if self.is_orphan:
            raise TokenError(f"Orphaned characters have no token: {self}") from None

        token = (
            Token.objects.prefetch_related("scopes")
            .filter(user=self.user, character_id=self.eve_character.character_id)
            .require_scopes(scopes if scopes else self.get_esi_scopes())
            .require_valid()
            .first()
        )
        if not token:
            if (
                MEMBERAUDIT_NOTIFY_TOKEN_ERRORS
                and self.user
                and not self.token_error_notified_at
            ):
                title = (
                    f"{__title__}: Invalid or missing token for {self.eve_character}"
                )
                message = (
                    f"{MEMBERAUDIT_APP_NAME} could not find a valid token for your "
                    f"character {self.eve_character}.\n"
                    f"Please re-add that character to {MEMBERAUDIT_APP_NAME} "
                    "at your earliest convenience to update your token."
                )
                notify.danger(user=self.user, title=title, message=message)
                self.token_error_notified_at = now()
                self.save(update_fields=["token_error_notified_at"])

            raise TokenDoesNotExist(
                f"Could not find a matching token for {self} with scopes: {scopes}."
            )
        return token

    def assets_build_list_from_esi(self, force_update=False) -> UpdateSectionResult:
        """Fetch character's assets from ESI and return it.

        Or return None if no update is required.
        """
        return self.assets.fetch_from_esi(self, force_update)

    def assets_preload_objects(self, asset_list: list) -> UpdateSectionResult:
        """Preload objects needed to build the character's asset tree from ESI."""
        return self.assets.preload_objects_from_esi(self, asset_list)

    def update_attributes(self, force_update: bool = False) -> UpdateSectionResult:
        """Update the character's learning attributes from ESI."""
        from memberaudit.models import CharacterAttributes

        return CharacterAttributes.objects.update_or_create_esi(self, force_update)

    def update_character_details(
        self, force_update: bool = False
    ) -> UpdateSectionResult:
        """Update the character's details from ESI."""
        from memberaudit.models import CharacterDetails

        return CharacterDetails.objects.update_or_create_esi(self, force_update)

    def update_contact_labels(self, force_update: bool = False) -> UpdateSectionResult:
        """Update character's contact labels from ESI."""
        return self.contact_labels.update_or_create_esi(self, force_update)

    def update_contacts(self, force_update: bool = False) -> UpdateSectionResult:
        """Update character's contacts from ESI."""
        return self.contacts.update_or_create_esi(self, force_update)

    def update_contract_headers(
        self, force_update: bool = False
    ) -> UpdateSectionResult:
        """Update the character's contract headers from ESI."""
        return self.contracts.update_or_create_esi(self, force_update)

    def update_contract_items(self, contract) -> UpdateSectionResult:
        """Update the character's contract items from ESI."""
        return contract.items.update_or_create_esi(self, contract)

    def update_contract_bids(self, contract) -> UpdateSectionResult:
        """Update the character's contract bids from ESI."""
        return contract.bids.update_or_create_esi(self, contract)

    def update_corporation_history(
        self, force_update: bool = False
    ) -> UpdateSectionResult:
        """Update the character's corporation history from ESI."""
        return self.corporation_history.update_or_create_esi(self, force_update)

    def update_fw_stats(self, force_update: bool = False) -> UpdateSectionResult:
        """Update character's FW stats from ESI."""
        from memberaudit.models import CharacterFwStats

        return CharacterFwStats.objects.update_or_create_esi(self, force_update)

    def update_implants(self, force_update: bool = False) -> UpdateSectionResult:
        """Update the character's current implants from ESI."""
        return self.implants.update_or_create_esi(self, force_update)

    def update_location(self, force_update: bool = False) -> UpdateSectionResult:
        """Update the character's current location from ESI."""
        from memberaudit.models import CharacterLocation

        return CharacterLocation.objects.update_or_create_esi(self, force_update)

    def update_loyalty(self, force_update: bool = False) -> UpdateSectionResult:
        """Update the character's loyalty entries from ESI."""
        return self.loyalty_entries.update_or_create_esi(self, force_update)

    def update_jump_clones(self, force_update: bool = False) -> UpdateSectionResult:
        """Update the character's jump clones from ESI."""
        return self.jump_clones.update_or_create_esi(self, force_update)

    def update_mailing_lists(self, force_update: bool = False) -> UpdateSectionResult:
        """Update the character's mailing lists from ESI."""
        return self.mailing_lists.update_or_create_mailing_lists_esi(self, force_update)

    def update_mail_labels(self, force_update: bool = False) -> UpdateSectionResult:
        """Update the character's mail labels from ESI."""
        return self.mail_labels.update_or_create_esi(self, force_update)

    def update_mail_headers(self, force_update: bool = False) -> UpdateSectionResult:
        """Update the character's mail headers from ESI."""
        return self.mails.update_or_create_headers_esi(self, force_update)

    def update_mail_body(self, mail, force_update: bool = False) -> UpdateSectionResult:
        """Update the characters's mail body from ESI."""
        return self.mails.update_or_create_body_esi(self, mail, force_update)

    def update_mining_ledger(self, force_update: bool = False) -> UpdateSectionResult:
        """Update character's mining ledger from ESI."""
        return self.mining_ledger.update_or_create_esi(self, force_update)

    def update_online_status(self, force_update: bool = False) -> UpdateSectionResult:
        """Update the character's online status from ESI."""
        from memberaudit.models import CharacterOnlineStatus

        return CharacterOnlineStatus.objects.update_or_create_esi(self, force_update)

    def update_planets(self, force_update: bool = False) -> UpdateSectionResult:
        """Update the character's planets from ESI."""
        return self.planets.update_or_create_esi(self, force_update)

    def update_roles(self, force_update: bool = False) -> UpdateSectionResult:
        """Update the character's corporation roles from ESI."""
        return self.roles.update_or_create_esi(self, force_update)

    def update_titles(self, force_update: bool = False) -> UpdateSectionResult:
        """Update the character's corporation titles from ESI."""
        return self.titles.update_or_create_esi(self, force_update)

    def update_ship(self, force_update: bool = False) -> UpdateSectionResult:
        """Update the character's current ship from ESI."""
        from memberaudit.models import CharacterShip

        return CharacterShip.objects.update_or_create_esi(self, force_update)

    def update_skill_queue(self, force_update: bool = False) -> UpdateSectionResult:
        """Update the character's skill queue from ESI."""
        return self.skillqueue.update_or_create_esi(self, force_update)

    def update_skill_sets(self) -> UpdateSectionResult:
        """Update the character's skill sets."""
        return self.skill_set_checks.update_for_character(self)

    def update_skills(self, force_update: bool = False) -> UpdateSectionResult:
        """Update the character's skills from ESI."""
        return self.skills.update_or_create_esi(self, force_update)

    def update_standings(self, force_update: bool = False) -> UpdateSectionResult:
        """Update the character's standings from ESI."""
        return self.standings.update_or_create_esi(self, force_update)

    def update_wallet_balance(self, force_update: bool = False) -> UpdateSectionResult:
        """Update the character's wallet balance from ESI."""
        from memberaudit.models import CharacterWalletBalance

        return CharacterWalletBalance.objects.update_or_create_esi(self, force_update)

    def update_wallet_journal(self, force_update: bool = False) -> UpdateSectionResult:
        """Update the character's wallet journal from ESI."""
        return self.wallet_journal.update_or_create_esi(self, force_update)

    def update_wallet_transactions(
        self, force_update: bool = False
    ) -> UpdateSectionResult:
        """Update the character's wallet transactions from ESI."""
        return self.wallet_transactions.update_or_create_esi(self, force_update)

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

    def generate_asset_from_current_ship_and_location(self) -> Optional[dict]:
        """Return generated asset item record from current ship and location
        or None it can not be generated.
        """
        from .character_sections_2 import CharacterLocation
        from .character_sections_3 import CharacterShip
        from .general import Location

        try:
            ship: CharacterShip = CharacterShip.objects.select_related("eve_type").get(
                character_id=self.id
            )
        except CharacterShip.DoesNotExist:
            return None

        if not ship.item_id:
            return None  # item ID is 0 from the migration

        if ship.eve_type.eve_group_id == EveGroupId.CAPSULE:
            return None  # we don't add capsules

        try:
            character_location: CharacterLocation = (
                CharacterLocation.objects.select_related(
                    "eve_solar_system",
                    "location",
                    "location__eve_solar_system",
                    "location__eve_type",
                ).get(character_id=self.id)
            )
            location = character_location.location_safe()
        except CharacterLocation.DoesNotExist:
            location, _ = Location.objects.get_or_create_unknown_location()

        ship_asset_record = {
            "is_blueprint_copy": False,
            "is_singleton": True,
            "item_id": ship.item_id,
            "location_flag": "Hangar",
            "location_id": location.id,
            "location_type": location.asset_location_type(),
            "name": ship.name,
            "quantity": 1,
            "type_id": ship.eve_type.id,
        }
        return ship_asset_record

    def clear_cache(self) -> None:
        """Remove this character from cache."""
        Character.objects.clear_cache(pk=self.pk)

    @staticmethod
    def get_esi_scopes() -> List[str]:
        """Return all enabled ESI scopes required to update this character."""
        scopes = [
            "esi-assets.read_assets.v1",
            "esi-bookmarks.read_character_bookmarks.v1",
            "esi-calendar.read_calendar_events.v1",
            "esi-characters.read_agents_research.v1",
            "esi-characters.read_blueprints.v1",
            "esi-characters.read_contacts.v1",
            "esi-characters.read_corporation_roles.v1",
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
        return sorted(scopes)


class CharacterUpdateStatus(AddGenericReprMixin, models.Model):
    """An object for tracking the update status of a character's section."""

    character = models.ForeignKey(
        Character, on_delete=models.CASCADE, related_name="update_status_set"
    )
    section = models.CharField(
        max_length=64, choices=Character.UpdateSection.choices, db_index=True
    )

    content_hash_1 = models.CharField(max_length=32, default="")
    content_hash_2 = models.CharField(max_length=32, default="")
    content_hash_3 = models.CharField(max_length=32, default="")
    has_token_error = models.BooleanField(
        default=False, help_text="Whether this section has a token error."
    )
    is_success = models.BooleanField(
        null=True,
        default=None,
        db_index=True,
    )
    error_message = models.TextField()
    run_finished_at = models.DateTimeField(
        null=True,
        default=None,
        db_index=True,
        help_text="Finish time of an update attempt",
    )
    run_started_at = models.DateTimeField(
        null=True,
        default=None,
        db_index=True,
        help_text="Start time of an update attempt",
    )
    update_finished_at = models.DateTimeField(
        null=True,
        default=None,
        db_index=True,
        help_text="Finish time of an actual update",
    )
    update_started_at = models.DateTimeField(
        null=True,
        default=None,
        db_index=True,
        help_text="Start time of an actual update",
    )

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
    def is_enabled(self) -> bool:
        """Return True if this section is currently enabled."""
        return self.section in Character.UpdateSection.enabled_sections()

    @property
    def is_updating(self) -> bool:
        """Return True if this section is currently being updated."""
        if not self.run_started_at and not self.run_finished_at:
            return False

        return self.run_started_at is not None and self.run_finished_at is None

    def has_changed(self, content: Any, hash_num: int = 1) -> bool:
        """Return True when given content is not the same as previous one, else False.

        Specify optionally which sub section to update via the hash_num (1, 2 or 3).
        """
        new_hash = self._calculate_hash(content)
        if hash_num == 2:
            content_hash = self.content_hash_2
        elif hash_num == 3:
            content_hash = self.content_hash_3
        else:
            content_hash = self.content_hash_1

        result = new_hash != content_hash
        return result

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

    def is_update_needed(self) -> bool:
        """Return True if this status is stale and needs to be updated, else False.
        But never report sections with token error as stale.
        """
        section = Character.UpdateSection(self.section)
        if not self.is_success or not self.run_finished_at:
            needs_update = True
        else:
            minutes = section_time_until_stale[section]
            deadline = now() - dt.timedelta(minutes=minutes)
            needs_update = self.run_finished_at <= deadline

        if needs_update and self.has_token_error:
            logger.warning(
                "%s: Ignoring update need because of token error for section: %s",
                self.character,
                section.label,
            )
            return False

        return needs_update

    @staticmethod
    def _calculate_hash(content: Any) -> str:
        return hashlib.md5(
            json.dumps(content, cls=DjangoJSONEncoder).encode("utf-8")
        ).hexdigest()

    def reset(self) -> None:
        """Reset this update status."""
        self.is_success = None
        self.error_message = ""
        self.has_token_error = False
        self.run_started_at = now()
        self.run_finished_at = None
        self.save()
        # TODO: Check if the hash also needs to be reset?


section_time_until_stale = (
    Character.UpdateSection.time_until_section_updates_are_stale()
)
"""Mapping of all sections with effective stale minutes."""


def enabled_sections_by_stale_minutes() -> List[Character.UpdateSection]:
    """Return list of enabled sections, ordered by stale minutes ascending."""
    sections_and_minutes = {
        section: value
        for section, value in section_time_until_stale.items()
        if section in Character.UpdateSection.enabled_sections()
    }
    sections = [
        obj[0] for obj in sorted(sections_and_minutes.items(), key=lambda o: o[1])
    ]

    return sections
