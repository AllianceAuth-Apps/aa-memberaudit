"""Character sections models."""

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from eveuniverse.models import EveEntity, EvePlanet, EveSolarSystem, EveType

from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag

from memberaudit import __title__
from memberaudit.core import standings
from memberaudit.helpers import EveEntityIdsMixin
from memberaudit.managers.character_sections_3 import (
    CharacterMiningLedgerEntryManager,
    CharacterOnlineStatusManager,
    CharacterPlanetManager,
    CharacterRoleManager,
    CharacterShipManager,
    CharacterSkillManager,
    CharacterSkillqueueEntryManager,
    CharacterSkillSetCheckManager,
    CharacterStandingManager,
    CharacterTitleManager,
    CharacterWalletBalanceManager,
    CharacterWalletJournalEntryManager,
    CharacterWalletTransactionManager,
)

from ._helpers import AddGenericReprMixin
from .characters import Character
from .constants import CURRENCY_MAX_DECIMALS, CURRENCY_MAX_DIGITS, NAMES_MAX_LENGTH
from .general import Location

logger = LoggerAddTag(get_extension_logger(__name__), __title__)


class CharacterMiningLedgerEntry(AddGenericReprMixin, models.Model):
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


class CharacterOnlineStatus(AddGenericReprMixin, models.Model):
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


class CharacterPlanet(AddGenericReprMixin, models.Model):
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
        """Return name of the planet type."""
        return self.eve_planet.eve_type.name


class CharacterRole(AddGenericReprMixin, models.Model):
    """A character's corporation role."""

    class Location(models.TextChoices):
        """A location for a role."""

        BASE = "BS", _("base")
        HQ = "HQ", _("headquarters")
        OTHER = "OT", _("other")
        UNIVERSAL = "UV", _("universal")

    class Role(models.TextChoices):
        """A corporation role."""

        ACCOUNT_TAKE_1 = "AT1", _("account take 1")
        ACCOUNT_TAKE_2 = "AT2", _("account take 2")
        ACCOUNT_TAKE_3 = "AT3", _("account take 3")
        ACCOUNT_TAKE_4 = "AT4", _("account take 4")
        ACCOUNT_TAKE_5 = "AT5", _("account take 5")
        ACCOUNT_TAKE_6 = "AT6", _("account take 6")
        ACCOUNT_TAKE_7 = "AT7", _("account take 7")
        ACCOUNTANT = "ACT", _("accountant")
        AUDITOR = "AUD", _("auditor")
        COMMUNICATIONS_OFFICER = "COM", _("communications officer")
        CONFIG_EQUIPMENT = "CEQ", _("config equipment")
        CONFIG_STARBASE_EQUIPMENT = "CSE", _("config starbase equipment")
        CONTAINER_TAKE_1 = "CT1", _("container take 1")
        CONTAINER_TAKE_2 = "CT2", _("container take 2")
        CONTAINER_TAKE_3 = "CT3", _("container take 3")
        CONTAINER_TAKE_4 = "CT4", _("container take 4")
        CONTAINER_TAKE_5 = "CT5", _("container take 5")
        CONTAINER_TAKE_6 = "CT6", _("container take 6")
        CONTAINER_TAKE_7 = "CT7", _("container take 7")
        CONTRACT_MANAGER = "CMG", _("contract manager")
        DIPLOMAT = "DPL", _("diplomat")
        DIRECTOR = "DRT", _("director")
        FACTORY_MANAGER = "FCM", _("factory manager")
        FITTING_MANAGER = "FTM", _("fitting manager")
        HANGAR_QUERY_1 = "HQ1", _("hangar query 1")
        HANGAR_QUERY_2 = "HQ2", _("hangar query 2")
        HANGAR_QUERY_3 = "HQ3", _("hangar query 3")
        HANGAR_QUERY_4 = "HQ4", _("hangar query 4")
        HANGAR_QUERY_5 = "HQ5", _("hangar query 5")
        HANGAR_QUERY_6 = "HQ6", _("hangar query 6")
        HANGAR_QUERY_7 = "HQ7", _("hangar query 7")
        HANGAR_TAKE_1 = "HT1", _("hangar take 1")
        HANGAR_TAKE_2 = "HT2", _("hangar take 2")
        HANGAR_TAKE_3 = "HT3", _("hangar take 3")
        HANGAR_TAKE_4 = "HT4", _("hangar take 4")
        HANGAR_TAKE_5 = "HT5", _("hangar take 5")
        HANGAR_TAKE_6 = "HT6", _("hangar take 6")
        HANGAR_TAKE_7 = "HT7", _("hangar take 7")
        JUNIOR_ACCOUNTANT = "JAC", _("junior accountant")
        PERSONNEL_MANAGER = "PSM", _("personnel manager")
        RENT_FACTORY_FACILITY = "RFF", _("rent factory facility")
        RENT_OFFICE = "RFC", _("rent office")
        RENT_RESEARCH_FACILITY = "RRF", _("rent research facility")
        SECURITY_OFFICER = "SCO", _("security officer")
        SKILL_PLAN_MANAGER = "SPM", _("skill plan manager")
        STARBASE_DEFENSE_OPERATOR = "SDO", _("starbase defense operator")
        STARBASE_FUEL_TECHNICIAN = "SFT", _("starbase fuel technician")
        STATION_MANAGER = "STM", _("station manager")
        TRADER = "TRD", _("trader")

    _ROLES_HANGER_ACCESS = {
        Role.HANGAR_QUERY_1,
        Role.HANGAR_QUERY_2,
        Role.HANGAR_QUERY_3,
        Role.HANGAR_QUERY_4,
        Role.HANGAR_QUERY_5,
        Role.HANGAR_QUERY_6,
        Role.HANGAR_QUERY_7,
        Role.HANGAR_TAKE_1,
        Role.HANGAR_TAKE_2,
        Role.HANGAR_TAKE_3,
        Role.HANGAR_TAKE_4,
        Role.HANGAR_TAKE_5,
        Role.HANGAR_TAKE_6,
        Role.HANGAR_TAKE_7,
    }
    _ROLES_CONTAINER_ACCESS = {
        Role.CONTAINER_TAKE_1,
        Role.CONTAINER_TAKE_2,
        Role.CONTAINER_TAKE_3,
        Role.CONTAINER_TAKE_4,
        Role.CONTAINER_TAKE_5,
        Role.CONTAINER_TAKE_6,
        Role.CONTAINER_TAKE_7,
    }
    ROLES_GROUPED = [
        {
            "title": _("general roles"),
            "location": Location.UNIVERSAL,
            "roles": {
                Role.ACCOUNTANT,
                Role.AUDITOR,
                Role.COMMUNICATIONS_OFFICER,
                Role.CONFIG_EQUIPMENT,
                Role.CONFIG_STARBASE_EQUIPMENT,
                Role.CONTRACT_MANAGER,
                Role.DIPLOMAT,
                Role.DIRECTOR,
                Role.FITTING_MANAGER,
                Role.JUNIOR_ACCOUNTANT,
                Role.PERSONNEL_MANAGER,
                Role.STARBASE_DEFENSE_OPERATOR,
                Role.STARBASE_FUEL_TECHNICIAN,
            },
        },
        {
            "title": _("station services"),
            "location": Location.UNIVERSAL,
            "roles": {
                Role.FACTORY_MANAGER,
                Role.RENT_FACTORY_FACILITY,
                Role.RENT_OFFICE,
                Role.RENT_RESEARCH_FACILITY,
                Role.SECURITY_OFFICER,
                Role.STATION_MANAGER,
                Role.TRADER,
            },
        },
        {
            "title": _("accounting (divisional)"),
            "location": Location.UNIVERSAL,
            "roles": {
                Role.ACCOUNT_TAKE_1,
                Role.ACCOUNT_TAKE_2,
                Role.ACCOUNT_TAKE_3,
                Role.ACCOUNT_TAKE_4,
                Role.ACCOUNT_TAKE_5,
                Role.ACCOUNT_TAKE_6,
                Role.ACCOUNT_TAKE_7,
            },
        },
        {
            "title": _("hangar access (headquarters)"),
            "location": Location.HQ,
            "roles": _ROLES_HANGER_ACCESS,
        },
        {
            "title": _("container access (headquarters)"),
            "location": Location.HQ,
            "roles": _ROLES_CONTAINER_ACCESS,
        },
        {
            "title": _("hangar access (based at)"),
            "location": Location.HQ,
            "roles": _ROLES_HANGER_ACCESS,
        },
        {
            "title": _("container access (based at)"),
            "location": Location.BASE,
            "roles": _ROLES_CONTAINER_ACCESS,
        },
        {
            "title": _("hangar access (other)"),
            "location": Location.OTHER,
            "roles": _ROLES_HANGER_ACCESS,
        },
        {
            "title": _("container access (other)"),
            "location": Location.OTHER,
            "roles": _ROLES_CONTAINER_ACCESS,
        },
    ]

    character = models.ForeignKey(
        Character, on_delete=models.CASCADE, related_name="roles"
    )

    location = models.CharField(
        max_length=2,
        choices=Location.choices,
        help_text=_("Location where this role is applicable."),
    )
    role = models.CharField(
        max_length=3, choices=Role.choices, help_text=_("Role of a character")
    )

    objects = CharacterRoleManager()

    class Meta:
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(
                fields=["character", "location", "role"],
                name="functional_pk_characterrole",
            )
        ]


class CharacterShip(AddGenericReprMixin, models.Model):
    """The current ship of a character."""

    character = models.OneToOneField(
        Character, on_delete=models.CASCADE, related_name="ship"
    )

    eve_type = models.ForeignKey(EveType, on_delete=models.CASCADE, related_name="+")
    item_id = models.PositiveBigIntegerField()
    name = models.CharField(max_length=255)

    objects = CharacterShipManager()

    class Meta:
        default_permissions = ()

    def __str__(self) -> str:
        return str(f"{self.character}-{self.eve_type.name}")


class CharacterSkill(AddGenericReprMixin, models.Model):
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


class CharacterSkillpoints(AddGenericReprMixin, models.Model):
    """The skill points of a character."""

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

    def __str__(self):
        return str(self.character)


class CharacterSkillqueueEntry(AddGenericReprMixin, models.Model):
    """An entry in the skillqueue of a character."""

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


class CharacterSkillSetCheck(AddGenericReprMixin, models.Model):
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
        """Return True if character has all required skills for this skill set,
        else False.
        """
        return not self.failed_required_skills.exists()


class CharacterStanding(AddGenericReprMixin, models.Model):
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
        criminal_connections_skill_level: int,  # pylint: disable=unused-argument
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


class CharacterTitle(AddGenericReprMixin, models.Model):
    """Title of a character."""

    character = models.ForeignKey(
        Character, on_delete=models.CASCADE, related_name="titles"
    )
    title_id = models.PositiveIntegerField()

    name = models.CharField(max_length=NAMES_MAX_LENGTH)

    objects = CharacterTitleManager()

    class Meta:
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(
                fields=["character", "title_id"],
                name="functional_pk_charactertitle",
            )
        ]

    def __str__(self) -> str:
        return f"{self.character}-{self.name}"


class CharacterWalletBalance(AddGenericReprMixin, models.Model):
    """A wallet balance of a character."""

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

    def __str__(self):
        return str(self.character)


class CharacterWalletJournalEntry(EveEntityIdsMixin, AddGenericReprMixin, models.Model):
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
        """Return context type matching the query string, else UNDEFINED."""
        result = cls.CONTEXT_ID_MAPS.get(query)
        if result:
            return result

        return cls.CONTEXT_ID_TYPE_UNDEFINED


class CharacterWalletTransaction(EveEntityIdsMixin, AddGenericReprMixin, models.Model):
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
