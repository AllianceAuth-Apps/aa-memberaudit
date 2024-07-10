"""
Top level models
"""

from typing import Set

from django.contrib.auth.models import Group, Permission, User
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from eveuniverse.core import dotlan, evewho
from eveuniverse.models import EveEntity, EveSolarSystem, EveType

from allianceauth.services.hooks import get_extension_logger
from app_utils.django import users_with_permission
from app_utils.logging import LoggerAddTag

from memberaudit import __title__
from memberaudit.helpers import arabic_number_to_roman
from memberaudit.managers.general import (
    ComplianceGroupDesignationManager,
    EveShipTypeManger,
    EveSkillTypeManger,
    LocationManager,
    MailEntityManager,
    SkillSetManager,
)

from ._helpers import AddGenericReprMixin
from .constants import NAMES_MAX_LENGTH

logger = LoggerAddTag(get_extension_logger(__name__), __title__)


class General(models.Model):
    """A model defining commonly used properties and methods for Member Audit."""

    class Meta:
        managed = False
        default_permissions = ()
        permissions = (
            (
                "basic_access",
                "Can access this app, register, and view own characters",
            ),
            ("share_characters", "Can share his/her characters"),
            ("finder_access", "Can access character finder feature"),
            ("reports_access", "Can access reports feature"),
            ("characters_access", "Can view characters owned by others"),
            ("exports_access", "Can access data exports"),
            ("view_shared_characters", "Can view shared characters"),
            ("view_same_corporation", "Can view corporation characters"),
            ("view_same_alliance", "Can view alliance characters"),
            ("view_everything", "Can view all characters"),
            ("notified_on_character_removal", "Notified when member drops character"),
            ("view_skill_sets", "Can view skill sets for a character"),
        )

    @classmethod
    def basic_permission(cls):
        """Return basic permission needed to use this app."""
        return Permission.objects.select_related("content_type").get(
            content_type__app_label=cls._meta.app_label, codename="basic_access"
        )

    @classmethod
    def users_with_basic_access(cls) -> models.QuerySet:
        """Return users which have at least basic access to Member Audit."""
        return users_with_permission(cls.basic_permission())

    @classmethod
    def accessible_users(cls, user: User) -> models.QuerySet:
        """Users that the given user can access."""
        if user.has_perm("memberaudit.view_everything"):
            return cls.users_with_basic_access()

        if (
            user.has_perm("memberaudit.view_same_alliance")
            and user.profile.main_character.alliance_id
        ):
            return cls.users_with_basic_access().filter(
                profile__main_character__alliance_id=user.profile.main_character.alliance_id
            )

        if user.has_perm("memberaudit.view_same_corporation"):
            return cls.users_with_basic_access().filter(
                profile__main_character__corporation_id=user.profile.main_character.corporation_id
            )

        return User.objects.filter(pk=user.pk)

    @classmethod
    def compliant_users(cls) -> models.QuerySet:
        """Users which are fully compliant."""
        return cls.users_with_basic_access().exclude(
            character_ownerships__character__memberaudit_character__isnull=True
        )

    @classmethod
    def add_compliant_users_to_group(cls, group: Group):
        """Add group to all compliant users, which are not yet a member."""
        compliant_users_qs = cls.compliant_users().exclude(groups=group)
        if group.authgroup.states.exists():
            compliant_users_qs = compliant_users_qs.filter(
                profile__state__in=list(group.authgroup.states.all())
            )
        # need to add users one by one due to Auth issue #1268
        for user in compliant_users_qs:
            user.groups.add(group)


class ComplianceGroupDesignation(AddGenericReprMixin, models.Model):
    """A designation defining a group as compliance group.

    Note that compliance groups are fully managed by the app.
    """

    group = models.OneToOneField(Group, on_delete=models.CASCADE)

    objects = ComplianceGroupDesignationManager()

    class Meta:
        default_permissions = ()
        verbose_name = _("compliance group designation")
        verbose_name_plural = _("compliance group designations")

    def __str__(self) -> str:
        return str(self.group)

    def save(self, *args, **kwargs) -> None:
        self._ensure_internal_group()
        super().save(*args, **kwargs)

    def _ensure_internal_group(self):
        """Ensure the related group is an internal group."""
        if not self.group.authgroup.internal:
            self.group.authgroup.internal = True
            self.group.authgroup.save()


class Location(AddGenericReprMixin, models.Model):
    """An Eve Online location: Station or Upwell Structure or Solar System."""

    LOCATION_UNKNOWN_ID = 888  # custom ID to signify a location that is not known
    _ASSET_SAFETY_ID = 2004
    _SOLAR_SYSTEM_ID_START = 30_000_000
    _SOLAR_SYSTEM_ID_END = 33_000_000
    _STATION_ID_START = 60_000_000
    _STATION_ID_END = 64_000_000
    _STRUCTURE_ID_START = 1_000_000_000_000

    id = models.PositiveBigIntegerField(
        primary_key=True,
        help_text=(
            "Eve Online location ID, "
            "either item ID for stations or structure ID for structures"
        ),
    )
    name = models.CharField(
        max_length=NAMES_MAX_LENGTH,
        help_text="In-game name of this station or structure",
    )
    eve_solar_system = models.ForeignKey(
        EveSolarSystem,
        on_delete=models.SET_DEFAULT,
        default=None,
        null=True,
        blank=True,
        related_name="+",
    )
    eve_type = models.ForeignKey(
        EveType,
        on_delete=models.SET_DEFAULT,
        default=None,
        null=True,
        blank=True,
        related_name="+",
    )
    owner = models.ForeignKey(
        EveEntity,
        on_delete=models.SET_DEFAULT,
        default=None,
        null=True,
        blank=True,
        related_name="+",
        help_text="corporation this station or structure belongs to",
    )
    updated_at = models.DateTimeField(auto_now=True)

    objects = LocationManager()

    class Meta:
        default_permissions = ()
        verbose_name = _("location")
        verbose_name_plural = _("locations")

    def __str__(self) -> str:
        return self.name

    @property
    def name_plus(self) -> str:
        """Return the actual name or 'Unknown location' for empty locations."""
        if self.is_empty:
            return f"Unknown location #{self.id}"

        return self.name

    @property
    def is_empty(self) -> bool:
        """Return True if this location is empty, else False."""
        return not self.eve_solar_system and not self.eve_type

    @property
    def solar_system_url(self) -> str:
        """Return dotlan URL for this solar system."""
        try:
            return dotlan.solar_system_url(self.eve_solar_system.name)
        except AttributeError:
            return ""

    @property
    def is_solar_system(self) -> bool:
        """Return True if this location is a solar system, else False."""
        return self.is_solar_system_id(self.id)

    @property
    def is_station(self) -> bool:
        """Return True if this location is a station, else False."""
        return self.is_station_id(self.id)

    @property
    def is_structure(self) -> bool:
        """Return True if this location is a structure, else False."""
        return self.is_structure_id(self.id)

    @property
    def is_unknown_location(self) -> bool:
        """Return True if this is the unknown location placeholder, else False."""
        return self.is_location_unknown_id(self.id)

    def asset_location_type(self) -> str:
        """Return asset location type for this Location."""
        if self.is_station:
            return "station"

        if self.is_solar_system or self.is_unknown_location:
            return "solar_system"

        if self.is_structure:
            return "item"

        return "other"

    @classmethod
    def is_solar_system_id(cls, location_id: int) -> bool:
        """Return True if this location ID is a solar system, else False."""
        return cls._SOLAR_SYSTEM_ID_START <= location_id <= cls._SOLAR_SYSTEM_ID_END

    @classmethod
    def is_station_id(cls, location_id: int) -> bool:
        """Return True, if this location ID is a station."""
        return cls._STATION_ID_START <= location_id <= cls._STATION_ID_END

    @classmethod
    def is_structure_id(cls, location_id: int) -> bool:
        """Return True, if this location ID is a structure."""
        return location_id >= cls._STRUCTURE_ID_START

    @classmethod
    def is_asset_safety_id(cls, location_id: int) -> bool:
        """Return True, if this location ID is asset safety."""
        return location_id == cls._ASSET_SAFETY_ID

    @classmethod
    def is_location_unknown_id(cls, location_id: int) -> bool:
        """Return True, if this is the location unknown ID."""
        return location_id == cls.LOCATION_UNKNOWN_ID


class EveShipType(EveType):
    """Subset of EveType for all ship types."""

    class Meta:
        proxy = True

    objects = EveShipTypeManger()


class EveSkillType(EveType):
    """Subset of EveType for all skill types."""

    class Meta:
        proxy = True

    objects = EveSkillTypeManger()


class SkillSetGroup(AddGenericReprMixin, models.Model):
    """A group of SkillSets, e.g. for defining a doctrine."""

    description = models.TextField(blank=True, verbose_name=_("description"))
    is_doctrine = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name=_("is doctrine"),
        help_text=(
            _("This enables a skill set group to show up correctly in doctrine reports")
        ),
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name=_("is active"),
        help_text=_("Whether this skill set group is in active use"),
    )
    last_modified_at = models.DateTimeField(
        null=True, default=None
    )  # TODO: Remove default when migrations are reset
    last_modified_by = models.ForeignKey(
        User, on_delete=models.SET_DEFAULT, null=True, default=None
    )
    name = models.CharField(
        max_length=NAMES_MAX_LENGTH, unique=True, verbose_name=_("name")
    )
    skill_sets = models.ManyToManyField(
        "SkillSet", related_name="groups", verbose_name=_("skill sets")
    )

    class Meta:
        # default_permissions are required for this model
        verbose_name = _("skill set group")
        verbose_name_plural = _("skill set groups")

    def __str__(self) -> str:
        return str(self.name)

    @property
    def name_plus(self) -> str:
        """Return name with potential doctrine prefix."""
        prefix = _("Doctrine: ") if self.is_doctrine else ""
        return f"{prefix}{self.name}"


class SkillSet(AddGenericReprMixin, models.Model):
    """A set of required and recommended skills needed to perform
    a particular task like flying a doctrine ships.
    """

    description = models.TextField(blank=True, verbose_name=_("description"))
    is_visible = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name=_("is visible"),
        help_text=_(
            "Non visible skill sets are not shown to users "
            "on their character sheet and used for audit purposes only."
        ),
    )
    last_modified_at = models.DateTimeField(
        null=True, default=None
    )  # TODO: Remove default when migrations are reset
    last_modified_by = models.ForeignKey(
        User, on_delete=models.SET_DEFAULT, null=True, default=None
    )
    name = models.CharField(
        max_length=NAMES_MAX_LENGTH, unique=True, verbose_name=_("name")
    )
    ship_type = models.ForeignKey(
        EveShipType,
        on_delete=models.SET_DEFAULT,
        default=None,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("ship type"),
        help_text=(
            _(
                "Ship type is used for visual presentation only. "
                "All skill requirements must be explicitly defined."
            )
        ),
    )

    objects = SkillSetManager()

    class Meta:
        # default_permissions are required for this model
        verbose_name = _("skill set")
        verbose_name_plural = _("skill sets")

    def __str__(self) -> str:
        return str(self.name)

    def clone(self, user: User) -> "SkillSet":
        """Create a clone of this skill set and return it."""
        params = {
            "description": self.description,
            "is_visible": self.is_visible,
            "last_modified_at": now(),
            "last_modified_by": user,
            "name": self.name + " 2",
            "ship_type": self.ship_type,
        }
        new_instance = self.__class__(**params)
        new_instance.save()
        cloned_skills = [
            SkillSetSkill(
                skill_set=new_instance,
                eve_type=skill.eve_type,
                required_level=skill.required_level,
                recommended_level=skill.recommended_level,
            )
            for skill in self.skills.all()
        ]
        SkillSetSkill.objects.bulk_create(cloned_skills)
        return new_instance


class SkillSetSkill(AddGenericReprMixin, models.Model):
    """A specific skill within a skill set."""

    skill_set = models.ForeignKey(
        SkillSet,
        on_delete=models.CASCADE,
        related_name="skills",
        verbose_name=_("skills"),
    )
    eve_type = models.ForeignKey(
        EveSkillType,
        on_delete=models.CASCADE,
        verbose_name=_("skill"),
        related_name="+",
    )

    required_level = models.PositiveIntegerField(
        default=None,
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name=_("required level"),
    )
    recommended_level = models.PositiveIntegerField(
        default=None,
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name=_("recommended level"),
    )

    class Meta:
        # default_permissions are required for this model
        verbose_name = _("skill")
        verbose_name_plural = _("skills")
        constraints = [
            models.UniqueConstraint(
                fields=["skill_set", "eve_type"],
                name="functional_pk_skillsetskill",
            )
        ]

    def __str__(self) -> str:
        if self.recommended_level:
            recommended_level_str = " / " + arabic_number_to_roman(
                self.recommended_level
            )
        else:
            recommended_level_str = ""
        return f"{self.skill_set}: {self.required_skill_str}{recommended_level_str}"

    @property
    def is_required(self) -> bool:
        """Return True when skill is required, else False."""
        return bool(self.required_level)

    @property
    def required_skill_str(self) -> str:
        """Return required skill with level in roman numbers."""
        return (
            self._skill_with_roman_level(self.required_level)
            if self.required_level
            else ""
        )

    @property
    def recommended_skill_str(self) -> str:
        """Return recommended skill with level in roman numbers."""
        return (
            self._skill_with_roman_level(self.recommended_level)
            if self.recommended_level
            else ""
        )

    @property
    def maximum_level(self) -> int:
        """Maximum level of this skill."""
        levels = [1]
        if self.recommended_level:
            levels.append(self.recommended_level)
        if self.required_level:
            levels.append(self.required_level)
        return max(levels)

    @property
    def maximum_skill_str(self) -> str:
        """Skill with maximum level as string."""
        return self._skill_with_roman_level(self.maximum_level)

    def _skill_with_roman_level(self, level) -> str:
        """Return skill with level in roman numbers."""
        level_str = arabic_number_to_roman(level)
        return f"{self.eve_type.name} {level_str}"


class MailEntity(AddGenericReprMixin, models.Model):
    """A sender or recipient in a mail."""

    class Category(models.TextChoices):
        """A category of a mail entity."""

        ALLIANCE = "AL", _("Alliance")
        CHARACTER = "CH", _("Character")
        CORPORATION = "CO", _("Corporation")
        MAILING_LIST = "ML", _("Mailing List")
        UNKNOWN = "UN", _("Unknown")

        @classmethod
        def eve_entity_compatible(cls) -> Set["MailEntity.Category"]:
            """Return categories, which are compatible with EveEntity."""
            return {cls.ALLIANCE, cls.CHARACTER, cls.CORPORATION}

    id = models.PositiveIntegerField(primary_key=True)
    category = models.CharField(
        max_length=2, choices=Category.choices, db_index=True
    )  # mandatory
    name = models.CharField(max_length=255, db_index=True)  # optional

    objects = MailEntityManager()

    class Meta:
        default_permissions = ()

    def __str__(self) -> str:
        return self.name

    @property
    def name_plus(self) -> str:
        """Return the name if defined or a generic name based on category and ID."""
        return self.name if self.name else f"{self.get_category_display()} #{self.id}"

    @property
    def eve_entity_categories(self) -> set:
        """Return categories which also exist for EveEntity."""
        return {
            self.Category.ALLIANCE,
            self.Category.CHARACTER,
            self.Category.CORPORATION,
        }

    def save(self, *args, **kwargs):
        if not self.category:
            raise ValidationError("You must specify a category")

        super().save(*args, **kwargs)

    def external_url(self) -> str:
        """Return URL for to show details of this entity on external website."""
        if self.category == self.Category.ALLIANCE and self.name:
            return dotlan.alliance_url(self.name)

        if self.category == self.Category.CHARACTER:
            return evewho.character_url(self.id)

        if self.category == self.Category.CORPORATION and self.name:
            return dotlan.corporation_url(self.name)

        return ""
