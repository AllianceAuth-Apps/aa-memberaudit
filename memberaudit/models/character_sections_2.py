"""Character sections models."""

from django.db import models
from django.utils.html import strip_tags
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from eveuniverse.models import (
    EveAncestry,
    EveBloodline,
    EveEntity,
    EveFaction,
    EveRace,
    EveSolarSystem,
    EveType,
)

from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag

from memberaudit import __title__
from memberaudit.constants import EveFactionId
from memberaudit.core.xml_converter import eve_xml_to_html
from memberaudit.helpers import EveEntityIdsMixin
from memberaudit.managers.character_sections_2 import (
    CharacterCorporationHistoryManager,
    CharacterDetailsManager,
    CharacterFwStatsManager,
    CharacterImplantManager,
    CharacterJumpCloneManager,
    CharacterLocationManager,
    CharacterLoyaltyEntryManager,
    CharacterMailLabelManager,
    CharacterMailManager,
)

from ._helpers import AddGenericReprMixin
from .characters import Character
from .constants import NAMES_MAX_LENGTH
from .general import Location

logger = LoggerAddTag(get_extension_logger(__name__), __title__)


class CharacterCorporationHistory(EveEntityIdsMixin, AddGenericReprMixin, models.Model):
    """A corporation history entry for a character."""

    character = models.ForeignKey(
        Character, on_delete=models.CASCADE, related_name="corporation_history"
    )
    record_id = models.PositiveIntegerField(db_index=True)

    corporation = models.ForeignKey(
        EveEntity, on_delete=models.CASCADE, related_name="+"
    )
    is_deleted = models.BooleanField(null=True, default=None, db_index=True)
    start_date = models.DateTimeField(db_index=True)

    objects = CharacterCorporationHistoryManager()

    class Meta:
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(
                fields=["character", "record_id"],
                name="functional_pk_charactercorporationhistory",
            )
        ]

    def __str__(self) -> str:
        return str(f"{self.character}-{self.record_id}")


class CharacterDetails(EveEntityIdsMixin, AddGenericReprMixin, models.Model):
    """Details for a character"""

    GENDER_MALE = "m"
    GENDER_FEMALE = "f"
    GENDER_CHOICES = (
        (GENDER_MALE, _("male")),
        (GENDER_FEMALE, _("female")),
    )
    character = models.OneToOneField(
        Character,
        primary_key=True,
        on_delete=models.CASCADE,
        related_name="details",
        help_text="character this details belongs to",
    )

    # character public info
    alliance = models.ForeignKey(
        EveEntity,
        on_delete=models.SET_DEFAULT,
        default=None,
        null=True,
        blank=True,
        related_name="+",
    )
    birthday = models.DateTimeField()
    corporation = models.ForeignKey(
        EveEntity, on_delete=models.CASCADE, related_name="+"
    )
    description = models.TextField()
    eve_ancestry = models.ForeignKey(
        EveAncestry,
        on_delete=models.SET_DEFAULT,
        default=None,
        null=True,
        related_name="+",
    )
    eve_bloodline = models.ForeignKey(
        EveBloodline, on_delete=models.CASCADE, related_name="+"
    )
    eve_faction = models.ForeignKey(
        EveFaction,
        on_delete=models.SET_DEFAULT,
        default=None,
        null=True,
        related_name="+",
    )
    eve_race = models.ForeignKey(EveRace, on_delete=models.CASCADE, related_name="+")
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    name = models.CharField(max_length=NAMES_MAX_LENGTH)
    security_status = models.FloatField(default=None, null=True)
    title = models.TextField()

    objects = CharacterDetailsManager()

    class Meta:
        default_permissions = ()

    def __str__(self) -> str:
        return str(self.character)

    def description_plain(self) -> str:
        """returns the description without tags"""
        return strip_tags(eve_xml_to_html(self.description))

    def description_html(self) -> str:
        """returns the description without tags"""
        return mark_safe(eve_xml_to_html(self.description, add_default_style=True))


class CharacterFwStats(AddGenericReprMixin, models.Model):
    """The faction Warfare statistics of a character."""

    RANKS = {
        EveFactionId.AMARR_EMPIRE.value: (
            _("Paladin Crusader"),
            _("Templar Lieutenant"),
            _("Cardinal Lieutenant"),
            _("Arch Lieutenant"),
            _("Imperial Major"),
            _("Marshal Commander"),
            _("Imperator Commander"),
            _("Tribunus Colonel"),
            _("Legatus Commodore"),
            _("Divine Commodore"),
        ),
        EveFactionId.CALDARI_STATE.value: (
            _("Protectorate Ensign"),
            _("Second Lieutenant"),
            _("First Lieutenant"),
            _("Captain"),
            _("Major"),
            _("Lieutenant Colonel"),
            _("Colonel"),
            _("Wing Commander"),
            _("Strike Commander"),
            _("Brigadier General"),
        ),
        EveFactionId.GALLENTE_FEDERATION.value: (
            _("Federation Minuteman"),
            _("Defender Lieutenant"),
            _("Guardian Lieutenant"),
            _("Lieutenant Sentinel"),
            _("Shield Commander"),
            _("Aegis Commander"),
            _("Vice Commander"),
            _("Major General"),
            _("Lieutenant General"),
            _("Luminaire General"),
        ),
        EveFactionId.MINMATAR_REPUBLIC.value: (
            _("Nation Warrior"),
            _("Spike Lieutenant"),
            _("Spear Lieutenant"),
            _("Venge Captain"),
            _("Lance Commander"),
            _("Blade Commander"),
            _("Talon Commander"),
            _("Voshud Major"),
            _("Matar Colonel"),
            _("Valklear General"),
        ),
    }

    character = models.OneToOneField(
        Character, on_delete=models.CASCADE, related_name="fw_stats"
    )

    current_rank = models.PositiveSmallIntegerField(default=None, null=True)
    enlisted_on = models.DateTimeField(default=None, null=True)
    faction = models.ForeignKey(
        EveFaction, on_delete=models.SET_DEFAULT, default=None, null=True
    )
    highest_rank = models.PositiveSmallIntegerField(default=None, null=True)
    kills_last_week = models.PositiveIntegerField(db_index=True)
    kills_total = models.PositiveIntegerField(db_index=True)
    kills_yesterday = models.PositiveIntegerField(db_index=True)
    victory_points_last_week = models.PositiveIntegerField(db_index=True)
    victory_points_total = models.PositiveIntegerField(db_index=True)
    victory_points_yesterday = models.PositiveIntegerField(db_index=True)

    objects = CharacterFwStatsManager()

    class Meta:
        default_permissions = ()

    def __str__(self) -> str:
        return str(self.character)

    def current_rank_name(self) -> str:
        """Name of current rank or empty string when not enlisted."""
        if not self.faction_id or not self.current_rank:
            return ""
        return self.rank_name_generic(self.faction_id, self.current_rank)

    def highest_rank_name(self) -> str:
        """Name of highest rank or empty string when not enlisted."""
        if not self.faction_id or not self.current_rank:
            return ""
        return self.rank_name_generic(self.faction_id, self.current_rank)

    @classmethod
    def rank_name_generic(cls, faction_id: int, rank_id: int) -> str:
        """Name of requested rank.

        Raises ValueError for unknown factions and invalid ranks.
        """
        try:
            return cls.RANKS[faction_id][rank_id]
        except KeyError:
            raise ValueError("Unknown faction") from None
        except IndexError:
            raise ValueError("Invalid rank") from None


class CharacterImplant(AddGenericReprMixin, models.Model):
    """An implant of a character."""

    character = models.ForeignKey(
        Character, on_delete=models.CASCADE, related_name="implants"
    )
    eve_type = models.ForeignKey(EveType, on_delete=models.CASCADE, related_name="+")

    objects = CharacterImplantManager()

    class Meta:
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(
                fields=["character", "eve_type"],
                name="functional_pk_characterimplant",
            )
        ]

    def __str__(self) -> str:
        return str(f"{self.character}-{self.eve_type}")


class CharacterLocation(AddGenericReprMixin, models.Model):
    """The location of a character."""

    character = models.OneToOneField(
        Character, on_delete=models.CASCADE, primary_key=True, related_name="location"
    )

    eve_solar_system = models.ForeignKey(
        EveSolarSystem, on_delete=models.CASCADE, related_name="+"
    )
    location = models.ForeignKey(
        Location, on_delete=models.SET_DEFAULT, default=None, null=True
    )

    objects = CharacterLocationManager()

    class Meta:
        default_permissions = ()

    def __str__(self) -> str:
        return str(f"{self.character}-{self.eve_solar_system}")

    def location_safe(self) -> Location:
        """Return location safely for current object."""
        if self.location:
            return self.location

        location, _ = Location.objects.get_or_create_from_eve_solar_system(
            self.eve_solar_system
        )
        return location


class CharacterLoyaltyEntry(EveEntityIdsMixin, AddGenericReprMixin, models.Model):
    """Loyalty entry for a character"""

    character = models.ForeignKey(
        Character,
        on_delete=models.CASCADE,
        related_name="loyalty_entries",
    )
    corporation = models.ForeignKey(
        EveEntity, on_delete=models.CASCADE, related_name="+"
    )

    loyalty_points = models.PositiveIntegerField()

    objects = CharacterLoyaltyEntryManager()

    class Meta:
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(
                fields=["character", "corporation"],
                name="functional_pk_characterloyaltyentry",
            )
        ]

    def __str__(self) -> str:
        return f"{self.character}-{self.corporation}"


class CharacterJumpClone(AddGenericReprMixin, models.Model):
    """A character's jump clone."""

    character = models.ForeignKey(
        Character, on_delete=models.CASCADE, related_name="jump_clones"
    )
    jump_clone_id = models.PositiveIntegerField(db_index=True)

    location = models.ForeignKey(Location, on_delete=models.CASCADE)
    name = models.CharField(max_length=NAMES_MAX_LENGTH, default="")

    objects = CharacterJumpCloneManager()

    class Meta:
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(
                fields=["character", "jump_clone_id"],
                name="functional_pk_characterjumpclone",
            )
        ]

    def __str__(self) -> str:
        return str(f"{self.character}-{self.jump_clone_id}")


class CharacterJumpCloneImplant(AddGenericReprMixin, models.Model):
    """An jump clone implant."""

    jump_clone = models.ForeignKey(
        CharacterJumpClone, on_delete=models.CASCADE, related_name="implants"
    )
    eve_type = models.ForeignKey(EveType, on_delete=models.CASCADE, related_name="+")

    class Meta:
        default_permissions = ()

    def __str__(self) -> str:
        return str(f"{self.jump_clone}-{self.eve_type}")


class CharacterMail(AddGenericReprMixin, models.Model):
    """Mail of a character"""

    character = models.ForeignKey(
        Character,
        on_delete=models.CASCADE,
        related_name="mails",
        help_text="character this mail belongs to",
    )
    mail_id = models.PositiveIntegerField(db_index=True)

    body = models.TextField()
    is_read = models.BooleanField(null=True, default=None, db_index=True)
    labels = models.ManyToManyField("CharacterMailLabel", related_name="mails")
    recipients = models.ManyToManyField("MailEntity", related_name="recipient_mails")
    # TODO: When migrations are reset remove default for sender
    sender = models.ForeignKey(
        "MailEntity",
        on_delete=models.CASCADE,
        null=True,
        default=None,
        related_name="sender_mails",
    )
    subject = models.CharField(max_length=255, default="")
    timestamp = models.DateTimeField(null=True, default=None)

    objects = CharacterMailManager()

    class Meta:
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(
                fields=["character", "mail_id"], name="functional_pk_charactermail"
            )
        ]

    def __str__(self) -> str:
        return f"{self.character}-{self.mail_id}"

    @property
    def body_html(self) -> str:
        """Return the mail body as html."""
        return mark_safe(eve_xml_to_html(self.body, add_default_style=True))


class CharacterMailLabel(AddGenericReprMixin, models.Model):
    """A mail labels of a character."""

    character = models.ForeignKey(
        Character, on_delete=models.CASCADE, related_name="mail_labels"
    )
    label_id = models.PositiveIntegerField(db_index=True)

    name = models.CharField(max_length=40, db_index=True)
    color = models.CharField(max_length=16, default="")
    unread_count = models.PositiveIntegerField(default=None, null=True)

    objects = CharacterMailLabelManager()

    class Meta:
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(
                fields=["character", "label_id"],
                name="functional_pk_charactermaillabel",
            )
        ]

    def __str__(self) -> str:
        return self.name


class CharacterMailUnreadCount(AddGenericReprMixin, models.Model):
    """The mail unread count of a character."""

    character = models.OneToOneField(
        Character,
        primary_key=True,
        on_delete=models.CASCADE,
        related_name="unread_mail_count",
    )
    total = models.PositiveIntegerField()

    class Meta:
        default_permissions = ()

    def __str__(self):
        return str(self.character)
