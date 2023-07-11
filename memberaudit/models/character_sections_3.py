"""
Character sections models
"""

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from eveuniverse.models import EveEntity, EvePlanet, EveSolarSystem, EveType

from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag

from memberaudit import __title__
from memberaudit.core import standings
from memberaudit.managers.character_sections_3 import (
    CharacterMiningLedgerEntryManager,
    CharacterOnlineStatusManager,
    CharacterPlanetManager,
    CharacterShipManager,
    CharacterSkillManager,
    CharacterSkillqueueEntryManager,
    CharacterSkillSetCheckManager,
    CharacterStandingManager,
    CharacterWalletBalanceManager,
    CharacterWalletJournalEntryManager,
    CharacterWalletTransactionManager,
)

from .characters import Character
from .constants import CURRENCY_MAX_DECIMALS, CURRENCY_MAX_DIGITS
from .general import Location

logger = LoggerAddTag(get_extension_logger(__name__), __title__)


class CharacterMiningLedgerEntry(models.Model):
    """Mining ledger entry of a character."""

    character = models.ForeignKey(
        Character, on_delete=models.CASCADE, related_name="mining_ledger"
    )
    date = models.DateField(db_index=True)
    quantity = models.PositiveIntegerField()
    eve_solar_system = models.ForeignKey(
        EveSolarSystem, on_delete=models.CASCADE, related_name="+"
    )
    eve_type = models.ForeignKey(EveType, on_delete=models.CASCADE, related_name="+")

    objects = CharacterMiningLedgerEntryManager()

    class Meta:
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(
                fields=["character", "date", "eve_solar_system", "eve_type"],
                name="functional_pk_characterminingledgerentry",
            )
        ]

    def __str__(self) -> str:
        return f"{self.character} {self.id}"


class CharacterOnlineStatus(models.Model):
    """Online Status of a character."""

    character = models.OneToOneField(
        Character,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="online_status",
    )

    last_login = models.DateTimeField(default=None, null=True)
    last_logout = models.DateTimeField(default=None, null=True)
    logins = models.PositiveIntegerField(default=None, null=True)

    objects = CharacterOnlineStatusManager()

    class Meta:
        default_permissions = ()

    def __str__(self) -> str:
        return str(self.character)


class CharacterPlanet(models.Model):
    """A planetary colony belonging to a character."""

    character = models.ForeignKey(
        Character, on_delete=models.CASCADE, related_name="planets"
    )
    eve_planet = models.ForeignKey(
        EvePlanet, on_delete=models.CASCADE, related_name="+"
    )

    last_update_at = models.DateTimeField()
    num_pins = models.PositiveIntegerField()
    upgrade_level = models.PositiveIntegerField()

    objects = CharacterPlanetManager()

    class Meta:
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(
                fields=["character", "eve_planet"], name="functional_pk_characterplanet"
            )
        ]

    def __str__(self) -> str:
        return f"{self.character}-{self.eve_planet.name}"

    def planet_type(self) -> str:
        return self.eve_planet.eve_type.name


class CharacterShip(models.Model):
    """Current ship of a character"""

    character = models.OneToOneField(
        Character, on_delete=models.CASCADE, related_name="ship"
    )
    name = models.CharField(max_length=255)
    eve_type = models.ForeignKey(EveType, on_delete=models.CASCADE, related_name="+")

    objects = CharacterShipManager()

    class Meta:
        default_permissions = ()

    def __str__(self) -> str:
        return str(f"{self.character}-{self.eve_type.name}")


class CharacterSkill(models.Model):
    """A trained skill of a character."""

    character = models.ForeignKey(
        Character, on_delete=models.CASCADE, related_name="skills"
    )
    eve_type = models.ForeignKey(EveType, on_delete=models.CASCADE, related_name="+")

    active_skill_level = models.PositiveIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    skillpoints_in_skill = models.PositiveBigIntegerField()
    trained_skill_level = models.PositiveBigIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(5)]
    )

    objects = CharacterSkillManager()

    class Meta:
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(
                fields=["character", "eve_type"], name="functional_pk_characterskill"
            )
        ]

    def __str__(self) -> str:
        return f"{self.character}-{self.eve_type.name}"


class CharacterSkillpoints(models.Model):
    """Skill points of a character"""

    character = models.OneToOneField(
        Character,
        primary_key=True,
        on_delete=models.CASCADE,
        related_name="skillpoints",
    )
    total = models.PositiveBigIntegerField()
    unallocated = models.PositiveIntegerField(default=None, null=True)

    class Meta:
        default_permissions = ()


class CharacterSkillqueueEntry(models.Model):
    """Entry in the skillqueue of a character"""

    character = models.ForeignKey(
        Character,
        on_delete=models.CASCADE,
        related_name="skillqueue",
    )
    queue_position = models.PositiveIntegerField(db_index=True)

    finish_date = models.DateTimeField(default=None, null=True)
    finished_level = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    level_end_sp = models.PositiveIntegerField(default=None, null=True)
    level_start_sp = models.PositiveIntegerField(default=None, null=True)
    eve_type = models.ForeignKey(EveType, on_delete=models.CASCADE, related_name="+")
    start_date = models.DateTimeField(default=None, null=True)
    training_start_sp = models.PositiveIntegerField(default=None, null=True)

    objects = CharacterSkillqueueEntryManager()

    class Meta:
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(
                fields=["character", "queue_position"],
                name="functional_pk_characterskillqueueentry",
            )
        ]

    def __str__(self) -> str:
        return f"{self.character}-{self.queue_position}"

    @property
    def is_active(self) -> bool:
        """Returns true when this skill is currently being trained"""
        return bool(self.finish_date) and self.queue_position == 0


class CharacterSkillSetCheck(models.Model):
    """The result of a skill check of a character against a skill set."""

    character = models.ForeignKey(
        Character, on_delete=models.CASCADE, related_name="skill_set_checks"
    )
    skill_set = models.ForeignKey("SkillSet", on_delete=models.CASCADE)

    failed_required_skills = models.ManyToManyField(
        "SkillSetSkill", related_name="failed_required_skill_set_checks"
    )
    failed_recommended_skills = models.ManyToManyField(
        "SkillSetSkill", related_name="failed_recommended_skill_set_checks"
    )

    objects = CharacterSkillSetCheckManager()

    class Meta:
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(
                fields=["character", "skill_set"],
                name="functional_pk_characterskillsetcheck",
            )
        ]

    def __str__(self) -> str:
        return f"{self.character}-{self.skill_set}"

    @property
    def can_fly(self) -> bool:
        return self.failed_required_skills.count() == 0


class CharacterStanding(models.Model):
    """Standing of a character with an NPC entity in Eve Online."""

    character = models.ForeignKey(
        Character, on_delete=models.CASCADE, related_name="standings"
    )
    eve_entity = models.ForeignKey(
        EveEntity, on_delete=models.CASCADE, related_name="+"
    )

    standing = models.FloatField()

    objects = CharacterStandingManager()

    class Meta:
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(
                fields=["character", "eve_entity"],
                name="functional_pk_characterstanding",
            )
        ]

    def __str__(self) -> str:
        return f"{self.character}-{self.eve_entity}"

    def effective_standing(
        self,
        connections_skill_level: int,
        criminal_connections_skill_level: int,
        diplomacy_skill_level: int,
    ) -> float:
        """Return effective standing for this NPC after applying social skill."""
        unadjusted_standing = self.standing
        if unadjusted_standing >= 0:
            skill_level = connections_skill_level
            skill_modifier = 0.04
            # TODO: Add variant for criminal connection
        else:
            skill_level = diplomacy_skill_level
            skill_modifier = 0.04

        max_possible_standing = 10
        effective_standing = standings.calc_effective_standing(
            unadjusted_standing, skill_level, skill_modifier, max_possible_standing
        )
        return effective_standing


class CharacterWalletBalance(models.Model):
    """Wallet balance of a character"""

    character = models.OneToOneField(
        Character,
        primary_key=True,
        on_delete=models.CASCADE,
        related_name="wallet_balance",
    )
    total = models.DecimalField(
        max_digits=CURRENCY_MAX_DIGITS, decimal_places=CURRENCY_MAX_DECIMALS
    )

    objects = CharacterWalletBalanceManager()

    class Meta:
        default_permissions = ()


class CharacterWalletJournalEntry(models.Model):
    """A wallet journal entry of a character in Eve Online."""

    CONTEXT_ID_TYPE_UNDEFINED = "NON"
    CONTEXT_ID_TYPE_STRUCTURE_ID = "STR"
    CONTEXT_ID_TYPE_STATION_ID = "STA"
    CONTEXT_ID_TYPE_MARKET_TRANSACTION_ID = "MTR"
    CONTEXT_ID_TYPE_CHARACTER_ID = "CHR"
    CONTEXT_ID_TYPE_CORPORATION_ID = "COR"
    CONTEXT_ID_TYPE_ALLIANCE_ID = "ALL"
    CONTEXT_ID_TYPE_EVE_SYSTEM = "EVE"
    CONTEXT_ID_TYPE_INDUSTRY_JOB_ID = "INJ"
    CONTEXT_ID_TYPE_CONTRACT_ID = "CNT"
    CONTEXT_ID_TYPE_PLANET_ID = "PLN"
    CONTEXT_ID_TYPE_SYSTEM_ID = "SYS"
    CONTEXT_ID_TYPE_TYPE_ID = "TYP"
    CONTEXT_ID_CHOICES = (
        (CONTEXT_ID_TYPE_UNDEFINED, _("undefined")),
        (CONTEXT_ID_TYPE_STATION_ID, _("station ID")),
        (CONTEXT_ID_TYPE_MARKET_TRANSACTION_ID, _("market transaction ID")),
        (CONTEXT_ID_TYPE_CHARACTER_ID, _("character ID")),
        (CONTEXT_ID_TYPE_CORPORATION_ID, _("corporation ID")),
        (CONTEXT_ID_TYPE_ALLIANCE_ID, _("alliance ID")),
        (CONTEXT_ID_TYPE_EVE_SYSTEM, _("eve system")),
        (CONTEXT_ID_TYPE_INDUSTRY_JOB_ID, _("industry job ID")),
        (CONTEXT_ID_TYPE_CONTRACT_ID, _("contract ID")),
        (CONTEXT_ID_TYPE_PLANET_ID, _("planet ID")),
        (CONTEXT_ID_TYPE_SYSTEM_ID, _("system ID")),
        (CONTEXT_ID_TYPE_TYPE_ID, _("type ID")),
    )
    CONTEXT_ID_MAPS = {
        "undefined": CONTEXT_ID_TYPE_UNDEFINED,
        "station_id": CONTEXT_ID_TYPE_STATION_ID,
        "market_transaction_id": CONTEXT_ID_TYPE_MARKET_TRANSACTION_ID,
        "character_id": CONTEXT_ID_TYPE_CHARACTER_ID,
        "corporation_id": CONTEXT_ID_TYPE_CORPORATION_ID,
        "alliance_id": CONTEXT_ID_TYPE_ALLIANCE_ID,
        "eve_system": CONTEXT_ID_TYPE_EVE_SYSTEM,
        "industry_job_id": CONTEXT_ID_TYPE_INDUSTRY_JOB_ID,
        "contract_id": CONTEXT_ID_TYPE_CONTRACT_ID,
        "planet_id": CONTEXT_ID_TYPE_PLANET_ID,
        "system_id": CONTEXT_ID_TYPE_SYSTEM_ID,
        "type_id": CONTEXT_ID_TYPE_TYPE_ID,
    }

    character = models.ForeignKey(
        Character, on_delete=models.CASCADE, related_name="wallet_journal"
    )
    entry_id = models.PositiveBigIntegerField(db_index=True)

    amount = models.DecimalField(
        max_digits=CURRENCY_MAX_DIGITS,
        decimal_places=CURRENCY_MAX_DECIMALS,
        default=None,
        null=True,
        blank=True,
    )
    balance = models.DecimalField(
        max_digits=CURRENCY_MAX_DIGITS,
        decimal_places=CURRENCY_MAX_DECIMALS,
        default=None,
        null=True,
        blank=True,
    )
    context_id = models.PositiveBigIntegerField(default=None, null=True)
    context_id_type = models.CharField(max_length=3, choices=CONTEXT_ID_CHOICES)
    date = models.DateTimeField()
    description = models.TextField()
    first_party = models.ForeignKey(
        EveEntity,
        on_delete=models.SET_DEFAULT,
        default=None,
        null=True,
        blank=True,
        related_name="+",
    )
    reason = models.TextField()
    ref_type = models.CharField(max_length=64)
    second_party = models.ForeignKey(
        EveEntity,
        on_delete=models.SET_DEFAULT,
        default=None,
        null=True,
        blank=True,
        related_name="+",
    )
    tax = models.DecimalField(
        max_digits=CURRENCY_MAX_DIGITS,
        decimal_places=CURRENCY_MAX_DECIMALS,
        default=None,
        null=True,
        blank=True,
    )
    tax_receiver = models.ForeignKey(
        EveEntity,
        on_delete=models.SET_DEFAULT,
        default=None,
        null=True,
        blank=True,
        related_name="+",
    )

    objects = CharacterWalletJournalEntryManager()

    class Meta:
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(
                fields=["character", "entry_id"],
                name="functional_pk_characterwalletjournalentry",
            )
        ]

    def __str__(self) -> str:
        return str(self.character) + " " + str(self.entry_id)

    @classmethod
    def match_context_type_id(cls, query: str) -> str:
        result = cls.CONTEXT_ID_MAPS.get(query)
        if result:
            return result

        return cls.CONTEXT_ID_TYPE_UNDEFINED


class CharacterWalletTransaction(models.Model):
    """A wallet transaction of a character in Eve Online."""

    character = models.ForeignKey(
        Character, on_delete=models.CASCADE, related_name="wallet_transactions"
    )
    transaction_id = models.PositiveBigIntegerField(db_index=True)

    client = models.ForeignKey(EveEntity, on_delete=models.CASCADE, related_name="+")
    date = models.DateTimeField()
    is_buy = models.BooleanField()
    is_personal = models.BooleanField()
    journal_ref = models.OneToOneField(
        CharacterWalletJournalEntry,
        on_delete=models.SET_DEFAULT,
        default=None,
        null=True,
        related_name="wallet_transaction",
    )
    location = models.ForeignKey(Location, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    eve_type = models.ForeignKey(EveType, on_delete=models.CASCADE)
    unit_price = models.DecimalField(
        max_digits=CURRENCY_MAX_DIGITS, decimal_places=CURRENCY_MAX_DECIMALS
    )

    objects = CharacterWalletTransactionManager()

    class Meta:
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(
                fields=["character", "transaction_id"],
                name="functional_pk_characterwallettransactions",
            )
        ]

    def __str__(self) -> str:
        return str(self.character) + " " + str(self.transaction_id)
