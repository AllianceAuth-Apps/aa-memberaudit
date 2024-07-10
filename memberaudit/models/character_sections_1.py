"""
Character sections models
"""

from typing import Optional

from django.db import models
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from eveuniverse.models import EveEntity, EveType

from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag

from memberaudit import __title__
from memberaudit.helpers import EveEntityIdsMixin
from memberaudit.managers.character_sections_1 import (
    CharacterAssetManager,
    CharacterAttributesManager,
    CharacterContactLabelManager,
    CharacterContactManager,
    CharacterContractBidManager,
    CharacterContractItemManager,
    CharacterContractManager,
)

from ._helpers import AddGenericReprMixin
from .characters import Character
from .constants import CURRENCY_MAX_DECIMALS, CURRENCY_MAX_DIGITS, NAMES_MAX_LENGTH
from .general import Location

logger = LoggerAddTag(get_extension_logger(__name__), __title__)


class CharacterAsset(AddGenericReprMixin, models.Model):
    """An Eve Online asset belonging to a character."""

    id = models.BigAutoField(primary_key=True)

    character = models.ForeignKey(
        Character, on_delete=models.CASCADE, related_name="assets"
    )
    item_id = models.PositiveBigIntegerField()

    location = models.ForeignKey(
        Location, on_delete=models.CASCADE, default=None, null=True
    )
    parent = models.ForeignKey(
        "CharacterAsset",
        on_delete=models.CASCADE,
        default=None,
        null=True,
        related_name="children",
    )

    eve_type = models.ForeignKey(EveType, on_delete=models.CASCADE, related_name="+")
    is_blueprint_copy = models.BooleanField(default=None, null=True, db_index=True)
    is_singleton = models.BooleanField()
    location_flag = models.CharField(max_length=NAMES_MAX_LENGTH)
    name = models.CharField(max_length=NAMES_MAX_LENGTH, default="")
    quantity = models.PositiveIntegerField()

    objects = CharacterAssetManager()

    class Meta:
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(
                fields=["character", "item_id"],
                name="functional_pk_characterasset",
            )
        ]

    def __str__(self) -> str:
        return f"{self.character}-{self.item_id}-{self.name_display}"

    @property
    def name_display(self) -> str:
        """Return name of this asset to be displayed to user."""
        name = self.name if self.name else self.eve_type.name
        if self.is_blueprint_copy:
            name += " [BPC]"
        return name

    @property
    def icon_url(self) -> str:
        """Return URL for an icon."""
        variant = self.eve_type.IconVariant.BPC if self.is_blueprint_copy else None
        return self.eve_type.icon_url(variant=variant)

    @property
    def group_display(self) -> str:
        """Return group name of this asset to be displayed to user."""
        return self.eve_type.name if self.name else self.eve_type.eve_group.name


class CharacterAttributes(AddGenericReprMixin, models.Model):
    """The training attributes of a character."""

    character = models.OneToOneField(
        Character,
        primary_key=True,
        on_delete=models.CASCADE,
        related_name="attributes",
        help_text="character these attributes belongs to",
    )

    accrued_remap_cooldown_date = models.DateTimeField(default=None, null=True)
    last_remap_date = models.DateTimeField(default=None, null=True)
    bonus_remaps = models.PositiveIntegerField()
    charisma = models.PositiveIntegerField()
    intelligence = models.PositiveIntegerField()
    memory = models.PositiveIntegerField()
    perception = models.PositiveIntegerField()
    willpower = models.PositiveIntegerField()
    objects = CharacterAttributesManager()

    class Meta:
        default_permissions = ()

    def __str__(self) -> str:
        return str(self.character)


class CharacterCloneInfo(AddGenericReprMixin, models.Model):
    """General clone infos for this character."""

    character = models.OneToOneField(
        Character, on_delete=models.CASCADE, related_name="clone_info"
    )

    home_location = models.ForeignKey(
        Location, on_delete=models.CASCADE, null=True, default=None
    )
    last_clone_jump_date = models.DateTimeField(default=None, null=True)
    last_station_change_date = models.DateTimeField(default=None, null=True)

    class Meta:
        default_permissions = ()

    def __str__(self) -> str:
        return str(self.character)


class CharacterContactLabel(AddGenericReprMixin, models.Model):
    """An Eve Online contact label belonging to a Character."""

    character = models.ForeignKey(
        Character, on_delete=models.CASCADE, related_name="contact_labels"
    )
    label_id = models.PositiveBigIntegerField()
    name = models.CharField(max_length=NAMES_MAX_LENGTH)

    objects = CharacterContactLabelManager()

    class Meta:
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(
                fields=["character", "label_id"], name="functional_pk_characterlabel"
            )
        ]

    def __str__(self) -> str:
        return f"{self.character}-{self.name}"


class CharacterContact(AddGenericReprMixin, models.Model):
    """An Eve Online contact belonging to a Character."""

    character = models.ForeignKey(
        Character, on_delete=models.CASCADE, related_name="contacts"
    )
    eve_entity = models.ForeignKey(
        EveEntity, on_delete=models.CASCADE, related_name="+"
    )

    is_blocked = models.BooleanField(default=None, null=True)
    is_watched = models.BooleanField(default=None, null=True)
    standing = models.FloatField()
    labels = models.ManyToManyField(CharacterContactLabel, related_name="contacts")

    objects = CharacterContactManager()

    class Meta:
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(
                fields=["character", "eve_entity"],
                name="functional_pk_charactercontact",
            )
        ]

    def __str__(self) -> str:
        return f"{self.character}-{self.eve_entity.name}"


class CharacterContract(EveEntityIdsMixin, AddGenericReprMixin, models.Model):
    """An Eve Online contract belonging to a Character"""

    AVAILABILITY_ALLIANCE = "AL"
    AVAILABILITY_CORPORATION = "CO"
    AVAILABILITY_PERSONAL = "PR"
    AVAILABILITY_PUBLIC = "PU"
    AVAILABILITY_CHOICES = (
        (AVAILABILITY_ALLIANCE, _("alliance")),
        (AVAILABILITY_CORPORATION, _("corporation")),
        (AVAILABILITY_PERSONAL, _("private")),
        (AVAILABILITY_PUBLIC, _("public")),
    )
    ESI_AVAILABILITY_MAP = {
        "alliance": AVAILABILITY_ALLIANCE,
        "corporation": AVAILABILITY_CORPORATION,
        "personal": AVAILABILITY_PERSONAL,
        "public": AVAILABILITY_PUBLIC,
    }

    STATUS_OUTSTANDING = "OS"
    STATUS_IN_PROGRESS = "IP"
    STATUS_FINISHED_ISSUER = "FI"
    STATUS_FINISHED_CONTRACTOR = "FC"
    STATUS_FINISHED = "FS"
    STATUS_CANCELED = "CA"
    STATUS_REJECTED = "RJ"
    STATUS_FAILED = "FL"
    STATUS_DELETED = "DL"
    STATUS_REVERSED = "RV"
    STATUS_CHOICES = (
        (STATUS_CANCELED, _("canceled")),
        (STATUS_DELETED, _("deleted")),
        (STATUS_FAILED, _("failed")),
        (STATUS_FINISHED, _("finished")),
        (STATUS_FINISHED_CONTRACTOR, _("finished contractor")),
        (STATUS_FINISHED_ISSUER, _("finished issuer")),
        (STATUS_IN_PROGRESS, _("in progress")),
        (STATUS_OUTSTANDING, _("outstanding")),
        (STATUS_REJECTED, _("rejected")),
        (STATUS_REVERSED, _("reversed")),
    )
    ESI_STATUS_MAP = {
        "canceled": STATUS_CANCELED,
        "deleted": STATUS_DELETED,
        "failed": STATUS_FAILED,
        "finished": STATUS_FINISHED,
        "finished_contractor": STATUS_FINISHED_CONTRACTOR,
        "finished_issuer": STATUS_FINISHED_ISSUER,
        "in_progress": STATUS_IN_PROGRESS,
        "outstanding": STATUS_OUTSTANDING,
        "rejected": STATUS_REJECTED,
        "reversed": STATUS_REVERSED,
    }

    TYPE_AUCTION = "AT"
    TYPE_COURIER = "CR"
    TYPE_ITEM_EXCHANGE = "IE"
    TYPE_LOAN = "LN"
    TYPE_UNKNOWN = "UK"
    TYPE_CHOICES = (
        (TYPE_AUCTION, _("auction")),
        (TYPE_COURIER, _("courier")),
        (TYPE_ITEM_EXCHANGE, _("item exchange")),
        (TYPE_LOAN, _("loan")),
        (TYPE_UNKNOWN, _("unknown")),
    )
    ESI_TYPE_MAP = {
        "auction": TYPE_AUCTION,
        "courier": TYPE_COURIER,
        "item_exchange": TYPE_ITEM_EXCHANGE,
        "loan": TYPE_LOAN,
        "unknown": TYPE_UNKNOWN,
    }

    character = models.ForeignKey(
        Character, on_delete=models.CASCADE, related_name="contracts"
    )
    contract_id = models.IntegerField()

    acceptor = models.ForeignKey(
        EveEntity,
        on_delete=models.CASCADE,
        default=None,
        null=True,
        related_name="+",
        help_text="Who will accept the contract if character",
    )
    acceptor_corporation = models.ForeignKey(
        EveEntity,
        on_delete=models.CASCADE,
        default=None,
        null=True,
        related_name="+",
        help_text="corporation of acceptor",
    )  # TODO: This field is currently unused
    assignee = models.ForeignKey(
        EveEntity,
        on_delete=models.CASCADE,
        default=None,
        null=True,
        related_name="+",
        help_text="To whom the contract is assigned, can be a corporation or a character",
    )
    availability = models.CharField(
        max_length=2,
        choices=AVAILABILITY_CHOICES,
        help_text="To whom the contract is available",
    )
    buyout = models.DecimalField(
        max_digits=CURRENCY_MAX_DIGITS,
        decimal_places=CURRENCY_MAX_DECIMALS,
        default=None,
        null=True,
    )
    collateral = models.DecimalField(
        max_digits=CURRENCY_MAX_DIGITS,
        decimal_places=CURRENCY_MAX_DECIMALS,
        default=None,
        null=True,
    )
    contract_type = models.CharField(max_length=2, choices=TYPE_CHOICES)
    date_accepted = models.DateTimeField(default=None, null=True)
    date_completed = models.DateTimeField(default=None, null=True)
    date_expired = models.DateTimeField()
    date_issued = models.DateTimeField()
    days_to_complete = models.IntegerField(default=None, null=True)
    end_location = models.ForeignKey(
        Location,
        on_delete=models.CASCADE,
        related_name="contract_end_location",
        default=None,
        null=True,
    )
    for_corporation = models.BooleanField()
    issuer_corporation = models.ForeignKey(
        EveEntity, on_delete=models.CASCADE, related_name="+"
    )
    issuer = models.ForeignKey(EveEntity, on_delete=models.CASCADE, related_name="+")
    price = models.DecimalField(
        max_digits=CURRENCY_MAX_DIGITS,
        decimal_places=CURRENCY_MAX_DECIMALS,
        default=None,
        null=True,
    )
    reward = models.DecimalField(
        max_digits=CURRENCY_MAX_DIGITS,
        decimal_places=CURRENCY_MAX_DECIMALS,
        default=None,
        null=True,
    )
    start_location = models.ForeignKey(
        Location,
        on_delete=models.CASCADE,
        related_name="contract_start_location",
        default=None,
        null=True,
    )
    status = models.CharField(max_length=2, choices=STATUS_CHOICES)
    title = models.CharField(max_length=NAMES_MAX_LENGTH, default="")
    volume = models.FloatField(default=None, null=True)

    objects = CharacterContractManager()

    class Meta:
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(
                fields=["character", "contract_id"],
                name="functional_pk_charactercontract",
            )
        ]

    def __str__(self) -> str:
        return f"{self.character}-{self.contract_id}"

    @property
    def is_completed(self) -> bool:
        """Return True when this contract is completed, else False."""
        return self.status in [
            self.STATUS_FINISHED_ISSUER,
            self.STATUS_FINISHED_CONTRACTOR,
            self.STATUS_FINISHED_ISSUER,
            self.STATUS_CANCELED,
            self.STATUS_REJECTED,
            self.STATUS_DELETED,
            self.STATUS_FINISHED,
            self.STATUS_FAILED,
        ]

    @property
    def is_in_progress(self) -> bool:
        """Return True when contract is in progress, else False."""
        return self.status == self.STATUS_IN_PROGRESS

    @property
    def is_failed(self) -> bool:
        """Return True when contract is failed, else False."""
        return self.status == self.STATUS_FAILED

    @property
    def has_expired(self) -> bool:
        """Return True when this contract is expired, else False."""
        return self.date_expired < now()

    @property
    def hours_issued_2_completed(self) -> Optional[float]:
        """Return amount of hours between issues and completed.
        Or return None if still pending.
        """
        if not self.date_completed:
            return None
        deadline = self.date_completed - self.date_issued
        return deadline.days * 24 + (deadline.seconds / 3600)

    def summary(self) -> str:
        """Return summary text for this contract."""
        if self.contract_type == CharacterContract.TYPE_COURIER:
            if not self.start_location or not self.end_location:
                return ""
            return (
                f"{self.start_location.eve_solar_system} >> "
                f"{self.end_location.eve_solar_system} "
                f"({self.volume:.0f} m3)"
            )

        if self.items.filter(is_included=True).count() > 1:
            return _("[Multiple Items]")

        first_item = self.items.first()
        return first_item.eve_type.name if first_item else "(no items)"


class CharacterContractBid(models.Model):
    """A bid belonging to a character contract."""

    contract = models.ForeignKey(
        CharacterContract, on_delete=models.CASCADE, related_name="bids"
    )
    bid_id = models.PositiveIntegerField(db_index=True)

    amount = models.FloatField()
    bidder = models.ForeignKey(EveEntity, on_delete=models.CASCADE, related_name="+")
    date_bid = models.DateTimeField()

    objects = CharacterContractBidManager()

    class Meta:
        default_permissions = ()

    def __str__(self) -> str:
        return f"{self.contract}-{self.bid_id}"


class CharacterContractItem(AddGenericReprMixin, models.Model):
    """An item belonging to a character contract."""

    contract = models.ForeignKey(
        CharacterContract, on_delete=models.CASCADE, related_name="items"
    )
    record_id = models.PositiveBigIntegerField(db_index=True)

    is_included = models.BooleanField(db_index=True)
    is_singleton = models.BooleanField()
    quantity = models.PositiveIntegerField()
    raw_quantity = models.IntegerField(default=None, null=True)
    eve_type = models.ForeignKey(EveType, on_delete=models.CASCADE, related_name="+")

    objects = CharacterContractItemManager()

    class Meta:
        default_permissions = ()

    def __str__(self) -> str:
        return f"{self.contract}-{self.record_id}"

    @property
    def is_blueprint_original(self) -> bool:
        """Return True if item is an original blueprint, else False."""
        return self.raw_quantity == -1

    @property
    def is_blueprint_copy(self) -> bool:
        """Return True if item is a blueprint copy, else False."""
        return self.raw_quantity == -2

    @property
    def is_blueprint(self) -> bool:
        """Return True if item is any kind of blueprint, else False."""
        return self.raw_quantity in [-1, -2]

    @property
    def name_display(self) -> str:
        """Return name to be displayed to user."""
        name = self.eve_type.name
        if self.is_blueprint_copy:
            name += " [BPC]"
        return name
