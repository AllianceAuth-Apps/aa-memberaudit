import datetime as dt
import urllib.parse
from typing import Generic, TypeVar

import factory
import factory.fuzzy

from django.utils.timezone import now
from eveuniverse.tests.testdata.factories_2 import (
    CitadelTypeFactory,
    EveEntityCorporationFactory,
    EveSolarSystemFactory,
    EveTypeFactory,
    ShipTypeFactory,
    StationTypeFactory,
)

from app_utils.testdata_factories import EveCharacterFactory, UserMainFactory
from app_utils.testing import add_character_to_user

from memberaudit.models import (
    Character,
    CharacterAttributes,
    CharacterLocation,
    CharacterShip,
    CharacterUpdateStatus,
    Location,
)
from memberaudit.tests.testdata.constants import EveCategoryId, EveGroupId, EveTypeId

T = TypeVar("T")
_BASE_URL = "https://esi.evetech.net/"


def make_esi_url(path: str) -> str:
    if path.startswith("/"):
        raise ValueError("path can not start with a slash")
    if path.endswith("/"):
        raise ValueError("path can not end with a slash")

    url = urllib.parse.urljoin(_BASE_URL, "latest/" + path + "/")
    return url


class BaseMetaFactory(Generic[T], factory.base.FactoryMetaClass):
    def __call__(cls, *args, **kwargs) -> T:
        return super().__call__(*args, **kwargs)


class BasicUserFactory(UserMainFactory):
    main_character__scopes = Character.esi_scopes()
    permissions__ = ["memberaudit.basic_access"]


class CharacterFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[Character]
):
    class Meta:
        model = Character
        exclude = ("user",)

    class Params:
        is_main = True
        is_orphan = False

    user = factory.SubFactory(BasicUserFactory)

    @factory.lazy_attribute
    def eve_character(self):
        if self.is_orphan:
            return EveCharacterFactory()

        if self.is_main:
            return self.user.profile.main_character

        ec = EveCharacterFactory()
        add_character_to_user(
            self.user, ec, is_main=False, scopes=Character.esi_scopes()
        )
        return ec


class CharacterOrphanFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[Character]
):
    class Meta:
        model = Character

    eve_character = factory.SubFactory(EveCharacterFactory)


class CharacterUpdateStatusFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[CharacterUpdateStatus]
):
    class Meta:
        model = CharacterUpdateStatus

    character = factory.SubFactory(CharacterFactory)
    is_success = True
    run_started_at = factory.fuzzy.FuzzyDateTime(
        now() - dt.timedelta(minutes=5), now() - dt.timedelta(seconds=1)
    )
    run_finished_at = factory.LazyFunction(now)
    section = factory.fuzzy.FuzzyChoice(Character.UpdateSection.values)


# General


class LocationFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[Location]
):
    class Meta:
        model = Location

    id = factory.Sequence(lambda n: 60_900_000 + n)
    name = factory.faker.Faker("city")
    eve_solar_system = factory.SubFactory(EveSolarSystemFactory)
    eve_type = factory.SubFactory(StationTypeFactory)
    owner = factory.SubFactory(EveEntityCorporationFactory)

    class Params:
        is_structure = factory.Trait(
            id=factory.Sequence(lambda n: 1_000_900_000_000 + n),
            eve_type=factory.SubFactory(CitadelTypeFactory),
        )
        is_solar_system = factory.Trait(
            id=factory.LazyAttribute(lambda o: o.eve_solar_system.id),
            eve_type=factory.SubFactory(
                EveTypeFactory,
                id=EveTypeId.SOLAR_SYSTEM,
                eve_group__id=EveGroupId.SOLAR_SYSTEM,
                eve_group__eve_category__id=EveCategoryId.CELESTIAL,
            ),
        )


# Character Sections


class CharacterAttributesFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[CharacterAttributes]
):
    class Meta:
        model = CharacterAttributes

    accrued_remap_cooldown_date = factory.fuzzy.FuzzyDateTime(
        now(), now() + dt.timedelta(days=90)
    )
    bonus_remaps = 3
    charisma = factory.fuzzy.FuzzyInteger(17, 32)
    intelligence = factory.fuzzy.FuzzyInteger(17, 32)
    last_remap_date = factory.fuzzy.FuzzyDateTime(now() - dt.timedelta(days=3))
    memory = factory.fuzzy.FuzzyInteger(17, 32)
    perception = factory.fuzzy.FuzzyInteger(17, 32)
    willpower = factory.fuzzy.FuzzyInteger(17, 32)


class CharacterLocationFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[CharacterLocation]
):
    class Meta:
        model = CharacterLocation

    character = factory.SubFactory(CharacterFactory)
    location = factory.SubFactory(LocationFactory)
    eve_solar_system = factory.LazyAttribute(lambda o: o.location.eve_solar_system)


class CharacterShipFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[CharacterShip]
):
    class Meta:
        model = CharacterShip

    character = factory.SubFactory(CharacterFactory)
    eve_type = factory.SubFactory(ShipTypeFactory)
    item_id = factory.Sequence(lambda n: 100_000_001 + n)
    name = factory.faker.Faker("word")
