import datetime as dt
import urllib.parse
from typing import Generic, TypeVar

import factory
import factory.fuzzy

from django.utils.timezone import now
from eveuniverse.tests.testdata.factories_2 import (
    CitadelTypeFactory,
    EveBloodlineFactory,
    EveEntityCharacterFactory,
    EveEntityCorporationFactory,
    EveFactionFactory,
    EveGroupFactory,
    EveRaceFactory,
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
    CharacterCloneInfo,
    CharacterContact,
    CharacterContactLabel,
    CharacterContract,
    CharacterContractBid,
    CharacterContractItem,
    CharacterCorporationHistory,
    CharacterDetails,
    CharacterFwStats,
    CharacterImplant,
    CharacterJumpClone,
    CharacterJumpCloneImplant,
    CharacterLocation,
    CharacterLoyaltyEntry,
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


# eveuniverse


class CyberimplantTypeFactory(EveTypeFactory):
    eve_group = factory.SubFactory(
        EveGroupFactory,
        eve_category__id=EveCategoryId.IMPLANT,
        eve_category__name="Implant",
        id=EveGroupId.CYBERIMPLANT,
        name="Cyberimplant",
    )


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


class LocationStationFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[Location]
):
    class Meta:
        model = Location

    id = factory.Sequence(lambda n: 60_900_000 + n)
    name = factory.LazyAttribute(lambda o: f"{o.eve_solar_system} - Station #{o.id}")
    eve_solar_system = factory.SubFactory(EveSolarSystemFactory)
    eve_type = factory.SubFactory(StationTypeFactory)
    owner = factory.SubFactory(EveEntityCorporationFactory)


class LocationStructureFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[Location]
):
    class Meta:
        model = Location

    id = factory.Sequence(lambda n: 1_000_900_000_000 + n)
    name = factory.LazyAttribute(lambda o: f"{o.eve_solar_system} - Structure #{o.id}")
    eve_solar_system = factory.SubFactory(EveSolarSystemFactory)
    eve_type = factory.SubFactory(CitadelTypeFactory)
    owner = factory.SubFactory(EveEntityCorporationFactory)


class LocationSolarSystemFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[Location]
):
    class Meta:
        model = Location

    id = factory.LazyAttribute(lambda o: o.eve_solar_system.id)
    eve_solar_system = factory.SubFactory(EveSolarSystemFactory)
    eve_type = factory.SubFactory(
        EveTypeFactory,
        id=EveTypeId.SOLAR_SYSTEM,
        eve_group__id=EveGroupId.SOLAR_SYSTEM,
        eve_group__eve_category__id=EveCategoryId.CELESTIAL,
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
    character = factory.SubFactory(CharacterFactory)
    charisma = factory.fuzzy.FuzzyInteger(17, 32)
    intelligence = factory.fuzzy.FuzzyInteger(17, 32)
    last_remap_date = factory.fuzzy.FuzzyDateTime(now() - dt.timedelta(days=3))
    memory = factory.fuzzy.FuzzyInteger(17, 32)
    perception = factory.fuzzy.FuzzyInteger(17, 32)
    willpower = factory.fuzzy.FuzzyInteger(17, 32)


class CharacterCloneInfoFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[CharacterCloneInfo]
):
    class Meta:
        model = CharacterCloneInfo

    character = factory.SubFactory(CharacterFactory)
    home_location = factory.SubFactory(LocationStationFactory)
    last_clone_jump_date = factory.fuzzy.FuzzyDateTime(
        now() - dt.timedelta(days=7), now()
    )
    last_station_change_date = factory.fuzzy.FuzzyDateTime(
        now() - dt.timedelta(days=100), now()
    )


class CharacterContactFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[CharacterContact]
):
    class Meta:
        model = CharacterContact

    character = factory.SubFactory(CharacterFactory)
    eve_entity = factory.SubFactory(EveEntityCharacterFactory)
    standing = factory.fuzzy.FuzzyFloat(-10.0, 10.0)


class CharacterContactLabelFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[CharacterContactLabel]
):
    class Meta:
        model = CharacterContactLabel

    character = factory.SubFactory(CharacterFactory)
    label_id = factory.Sequence(lambda n: 1 + n)
    name = factory.faker.Faker("color")


class _CharacterContractFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[CharacterContract]
):
    class Meta:
        model = CharacterContract

    character = factory.SubFactory(CharacterFactory)
    contract_id = factory.Sequence(lambda n: 109_000_000 + n)
    availability = CharacterContract.AVAILABILITY_PUBLIC
    date_issued = factory.fuzzy.FuzzyDateTime(now() - dt.timedelta(hours=12), now())

    date_expired = factory.LazyAttribute(lambda o: o.date_issued + dt.timedelta(days=3))
    for_corporation = False
    issuer = factory.SubFactory(EveEntityCharacterFactory)
    issuer_corporation = factory.SubFactory(EveEntityCorporationFactory)
    status = CharacterContract.STATUS_OUTSTANDING
    title = factory.faker.Faker("words")

    class Params:
        accepted = factory.Trait(
            status=CharacterContract.STATUS_IN_PROGRESS,
            acceptor=factory.SubFactory(EveEntityCharacterFactory),
            date_accepted=factory.LazyAttribute(
                lambda o: o.date_issued + dt.timedelta(hours=1)
            ),
        )
        finished = factory.Trait(
            status=CharacterContract.STATUS_FINISHED,
            acceptor=factory.SubFactory(EveEntityCharacterFactory),
            date_accepted=factory.LazyAttribute(
                lambda o: o.date_issued + dt.timedelta(hours=1)
            ),
            date_completed=factory.LazyAttribute(
                lambda o: o.date_issued + dt.timedelta(hours=3)
            ),
        )


class CharacterContractItemFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[CharacterContractItem]
):
    class Meta:
        model = CharacterContractItem

    contract = factory.SubFactory(CharacterFactory)
    record_id = factory.Sequence(lambda n: 1 + n)
    eve_type = factory.SubFactory(EveTypeFactory)
    is_included = True
    is_singleton = False
    quantity = 1
    raw_quantity = False


class CharacterContractItemExchangeFactory(_CharacterContractFactory):
    contract_type = CharacterContract.TYPE_ITEM_EXCHANGE
    price = factory.fuzzy.FuzzyFloat(10_000, 10_000_000_000)

    @factory.post_generation
    def create_items(obj, create, extracted, **kwargs):
        if not create or extracted is False:
            return

        CharacterContractItemFactory(contract=obj)


class CharacterContractBidFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[CharacterContractBid]
):
    class Meta:
        model = CharacterContractBid

    contract = factory.SubFactory(CharacterFactory)
    bid_id = factory.Sequence(lambda n: 1 + n)
    amount = factory.fuzzy.FuzzyFloat(10_000, 10_000_000_000)
    bidder = factory.SubFactory(EveEntityCharacterFactory)

    @factory.LazyAttribute
    def date_bid(self):
        return factory.fuzzy.FuzzyDateTime(self.contract.date_issued, now()).fuzz()


class CharacterContractAuctionFactory(_CharacterContractFactory):
    contract_type = CharacterContract.TYPE_AUCTION
    buyout = factory.fuzzy.FuzzyFloat(10_000, 10_000_000_000)

    @factory.post_generation
    def create_items(obj, create, extracted, **kwargs):
        if not create or extracted is False:
            return

        CharacterContractItemFactory(contract=obj)

    @factory.post_generation
    def create_bids(obj, create, extracted, **kwargs):
        if not create or not extracted:
            return

        for _ in range(extracted):
            CharacterContractBidFactory(contract=obj)


class CharacterContractCourierFactory(_CharacterContractFactory):
    contract_type = CharacterContract.TYPE_COURIER
    start_location = factory.SubFactory(LocationStationFactory)
    end_location = factory.SubFactory(LocationStationFactory)
    reward = factory.fuzzy.FuzzyFloat(10_000, 10_000_000_000)
    days_to_complete = factory.fuzzy.FuzzyInteger(1, 7)
    collateral = factory.fuzzy.FuzzyFloat(10_000, 10_000_000_000)
    volume = factory.fuzzy.FuzzyFloat(1, 300_000_000)


class CharacterCorporationHistoryFactory(
    factory.django.DjangoModelFactory,
    metaclass=BaseMetaFactory[CharacterCorporationHistory],
):
    class Meta:
        model = CharacterCorporationHistory

    character = factory.SubFactory(CharacterFactory)
    corporation = factory.SubFactory(EveEntityCorporationFactory)
    is_deleted = False
    record_id = factory.Sequence(lambda n: 1 + n)
    start_date = factory.fuzzy.FuzzyDateTime(now() - dt.timedelta(days=1000), now())


class CharacterDetailsFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[CharacterDetails]
):
    class Meta:
        model = CharacterDetails

    birthday = factory.fuzzy.FuzzyDateTime(now() - dt.timedelta(days=1000), now())
    character = factory.SubFactory(CharacterFactory)
    corporation = factory.SubFactory(EveEntityCorporationFactory)
    description = factory.Faker("paragraph")
    eve_bloodline = factory.SubFactory(EveBloodlineFactory)
    eve_race = factory.SubFactory(EveRaceFactory)
    gender = CharacterDetails.GENDER_MALE
    name = factory.LazyAttribute(lambda o: o.character.eve_character.character_name)
    security_status = factory.fuzzy.FuzzyFloat(-10, 10)
    title = factory.Faker("job")


class CharacterFwStatsFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[CharacterFwStats]
):
    class Meta:
        model = CharacterFwStats

    character = factory.SubFactory(CharacterFactory)
    current_rank = factory.fuzzy.FuzzyInteger(0, 9)
    enlisted_on = factory.fuzzy.FuzzyDateTime(now() - dt.timedelta(days=1000), now())
    faction = factory.SubFactory(EveFactionFactory)
    highest_rank = factory.LazyAttribute(lambda o: o.current_rank)
    kills_last_week = factory.fuzzy.FuzzyInteger(0, 100)
    kills_total = factory.LazyAttribute(lambda o: o.kills_last_week + o.kills_yesterday)
    kills_yesterday = factory.fuzzy.FuzzyInteger(0, 10)
    victory_points_last_week = factory.fuzzy.FuzzyInteger(0, 100)
    victory_points_total = factory.LazyAttribute(
        lambda o: o.victory_points_last_week + o.victory_points_yesterday
    )
    victory_points_yesterday = factory.fuzzy.FuzzyInteger(0, 10)


class CharacterImplantFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[CharacterImplant]
):
    class Meta:
        model = CharacterImplant

    character = factory.SubFactory(CharacterFactory)
    eve_type = factory.SubFactory(CyberimplantTypeFactory)


class CharacterJumpCloneFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[CharacterJumpClone]
):
    class Meta:
        model = CharacterJumpClone

    character = factory.SubFactory(CharacterFactory)
    jump_clone_id = factory.Sequence(lambda n: 1 + n)
    location = factory.SubFactory(LocationStationFactory)
    name = factory.Faker("color")


class CharacterJumpCloneImplantFactory(
    factory.django.DjangoModelFactory,
    metaclass=BaseMetaFactory[CharacterJumpCloneImplant],
):
    class Meta:
        model = CharacterJumpCloneImplant

    jump_clone = factory.SubFactory(CharacterJumpCloneFactory)
    eve_type = factory.SubFactory(CyberimplantTypeFactory)


class CharacterLocationFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[CharacterLocation]
):
    class Meta:
        model = CharacterLocation

    character = factory.SubFactory(CharacterFactory)
    eve_solar_system = factory.LazyAttribute(lambda o: o.location.eve_solar_system)
    location = factory.SubFactory(LocationStationFactory)


class CharacterLoyaltyEntryFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[CharacterLoyaltyEntry]
):
    class Meta:
        model = CharacterLoyaltyEntry

    character = factory.SubFactory(CharacterFactory)
    corporation = factory.SubFactory(EveEntityCorporationFactory)
    loyalty_points = factory.fuzzy.FuzzyInteger(0, 10_000_000)


class CharacterShipFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[CharacterShip]
):
    class Meta:
        model = CharacterShip

    character = factory.SubFactory(CharacterFactory)
    eve_type = factory.SubFactory(ShipTypeFactory)
    item_id = factory.Sequence(lambda n: 100_000_001 + n)
    name = factory.faker.Faker("word")
