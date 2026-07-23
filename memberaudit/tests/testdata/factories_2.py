import datetime as dt
import math
import urllib.parse
from pathlib import Path
from typing import Generic, TypeVar

import factory
import factory.fuzzy

from django.contrib.auth.models import Group
from django.utils.timezone import now
from esi.tests.factories_2 import ScopeFactory
from esi.tests.factories_2 import TokenFactory as _TokenFactory
from eveuniverse.tests.testdata.factories_2 import (
    CitadelTypeFactory,
    EveBloodlineFactory,
    EveDogmaAttributeFactory,
    EveEntityCharacterFactory,
    EveEntityCorporationFactory,
    EveFactionFactory,
    EveGroupFactory,
    EvePlanetFactory,
    EveRaceFactory,
    EveSolarSystemFactory,
    EveTypeFactory,
    ShipTypeFactory,
    SolarSystemTypeFactory,
    StationTypeFactory,
)

from allianceauth.authentication.models import State
from allianceauth.authentication.signals import post_save
from allianceauth.groupmanagement.models import AuthGroup
from app_utils.testdata_factories import EveCharacterFactory, UserMainFactory
from app_utils.testing import add_character_to_user

from memberaudit.models import (
    Character,
    CharacterAsset,
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
    CharacterMail,
    CharacterMailLabel,
    CharacterMiningLedgerEntry,
    CharacterOnlineStatus,
    CharacterPlanet,
    CharacterRole,
    CharacterShip,
    CharacterSkill,
    CharacterSkillpoints,
    CharacterSkillqueueEntry,
    CharacterSkillSetCheck,
    CharacterStanding,
    CharacterTitle,
    CharacterUpdateStatus,
    CharacterWalletBalance,
    CharacterWalletJournalEntry,
    CharacterWalletTransaction,
    ComplianceGroupDesignation,
    Location,
    MailEntity,
    SkillSet,
    SkillSetGroup,
    SkillSetSkill,
)
from memberaudit.tests.testdata.constants import (
    EveCategoryId,
    EveDogmaAttributeId,
    EveGroupId,
    EveTypeId,
)

T = TypeVar("T")
_BASE_URL = "https://esi.evetech.net/"


def make_esi_url(path: str) -> str:
    if path.startswith("/"):
        raise ValueError("path can not start with a slash")
    if path.endswith("/"):
        raise ValueError("path can not end with a slash")

    url = urllib.parse.urljoin(_BASE_URL, path)
    return url


class BaseMetaFactory(Generic[T], factory.base.FactoryMetaClass):
    def __call__(cls, *args, **kwargs) -> T:
        return super().__call__(*args, **kwargs)


def create_fitting_text(file_name: str) -> str:
    testdata_folder = Path(__file__).parent / "fittings"
    fitting_file = testdata_folder / file_name
    with fitting_file.open("r") as file:
        return file.read()


# esi


@factory.django.mute_signals(post_save)
class TokenFactory2(_TokenFactory):
    """Token factory that does not trigger the character ownership update
    in Alliance Auth.
    """

    @factory.post_generation
    def scopes(self, create, extracted, **kwargs):
        if not create or not extracted:
            return

        for name in extracted:
            self.scopes.add(ScopeFactory(name=name))


# eveuniverse


class AssetSafetyWrapTypeFactory(EveTypeFactory):
    eve_group = factory.SubFactory(
        EveGroupFactory,
        eve_category__id=EveCategoryId.ABSTRACT,
        eve_category__name="Abstract",
        id=EveGroupId.MISCELLANEOUS,
        name="Miscellaneous",
    )
    id = EveTypeId.ASSET_SAFETY_WRAP
    name = "Asset Safety Wrap"


class CyberimplantTypeFactory(EveTypeFactory):
    eve_group = factory.SubFactory(
        EveGroupFactory,
        eve_category__id=EveCategoryId.IMPLANT,
        eve_category__name="Implant",
        id=EveGroupId.CYBERIMPLANT,
        name="Cyberimplant",
    )
    volume = 1.0
    enabled_sections = 1  # Dogmas

    @factory.post_generation
    def slot_num(self, create, extracted, **kwargs):
        if not create or extracted is False:
            return

        num = extracted or 1
        da = EveDogmaAttributeFactory(id=EveDogmaAttributeId.IMPLANT_SLOT)
        self.dogma_attributes.get_or_create(
            eve_dogma_attribute=da, defaults={"value": num}
        )


class NavigationSkillTypeFactory(EveTypeFactory):
    eve_group = factory.SubFactory(
        EveGroupFactory,
        eve_category__id=EveCategoryId.SKILL,
        eve_category__name="Skill",
        id=EveGroupId.NAVIGATION,
        name="Navigation",
    )


class SpaceshipCommandSkillTypeFactory(EveTypeFactory):
    eve_group = factory.SubFactory(
        EveGroupFactory,
        eve_category__id=EveCategoryId.SKILL,
        eve_category__name="Skill",
        id=EveGroupId.SPACESHIP_COMMAND,
        name="Spaceship Command",
    )


# allianceauth


class GroupFactory(factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[Group]):
    class Meta:
        model = Group

    name = factory.Sequence(lambda n: f"Group #{n + 1}")

    @factory.post_generation
    def authgroup(self, create, extracted, **kwargs):
        authgroup: AuthGroup = self.authgroup

        if kwargs:
            for field in ["states", "group_leaders", "group_leader_groups"]:
                if field in kwargs:
                    x = kwargs.pop(field)
                    getattr(self.authgroup, field).add(*x)

            for field, value in kwargs.items():
                setattr(authgroup, field, value)

        authgroup.save()


class StateFactory(factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[State]):
    class Meta:
        model = State

    name = factory.LazyAttribute(lambda o: f"State #{o.priority}")
    priority = factory.Sequence(lambda n: n + 900)
    public = False

    @factory.post_generation
    def permissions(self, create, extracted, **kwargs):
        if not create or not extracted:
            return

        self.permissions.add(*extracted)

    @factory.post_generation
    def member_characters(self, create, extracted, **kwargs):
        if not create or not extracted:
            return

        self.member_characters.add(*extracted)

    @factory.post_generation
    def member_corporations(self, create, extracted, **kwargs):
        if not create or not extracted:
            return

        self.member_corporations.add(*extracted)

    @factory.post_generation
    def member_alliances(self, create, extracted, **kwargs):
        if not create or not extracted:
            return

        self.member_alliances.add(*extracted)

    @factory.post_generation
    def member_factions(self, create, extracted, **kwargs):
        if not create or not extracted:
            return

        self.member_factions.add(*extracted)


# General


class UserMainBasicAccessFactory(UserMainFactory):
    main_character__scopes = Character.esi_scopes()
    permissions__ = ["memberaudit.basic_access"]


class ComplianceGroupFactory(GroupFactory):
    @factory.post_generation
    def compliancegroupdesignation(self, create, extracted, **kwargs):
        if not create:
            return

        if extracted:
            self.compliancegroupdesignation = extracted
        else:
            ComplianceGroupDesignationFactory(group=self)


class ComplianceGroupDesignationFactory(
    factory.django.DjangoModelFactory,
    metaclass=BaseMetaFactory[ComplianceGroupDesignation],
):
    class Meta:
        model = ComplianceGroupDesignation

    group = factory.SubFactory(GroupFactory)


class LocationAssetSafetyFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[Location]
):
    class Meta:
        model = Location

    id = Location.ASSET_SAFETY_ID
    name = "ASSET SAFETY"
    eve_type = factory.SubFactory(AssetSafetyWrapTypeFactory)


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


class LocationUnknownFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[Location]
):
    class Meta:
        model = Location

    id = Location.LOCATION_UNKNOWN_ID
    name = "Location unknown"
    eve_type = factory.SubFactory(SolarSystemTypeFactory)


class MailEntityAllianceFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[MailEntity]
):
    class Meta:
        model = MailEntity

    id = factory.Sequence(lambda n: 99_900_001 + n)
    category = MailEntity.Category.ALLIANCE
    name = factory.LazyAttribute(lambda o: f"Alliance #{o.id}")


class MailEntityCharacterFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[MailEntity]
):
    class Meta:
        model = MailEntity

    id = factory.Sequence(lambda n: 90_900_001 + n)
    category = MailEntity.Category.CHARACTER
    name = factory.LazyAttribute(lambda o: f"Character #{o.id}")


class MailEntityCorporationFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[MailEntity]
):
    class Meta:
        model = MailEntity

    id = factory.Sequence(lambda n: 98_900_001 + n)
    category = MailEntity.Category.CORPORATION
    name = factory.LazyAttribute(lambda o: f"Corporation #{o.id}")


class MailEntityMailingListFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[MailEntity]
):
    class Meta:
        model = MailEntity

    id = factory.Sequence(lambda n: 10_900_001 + n)
    category = MailEntity.Category.MAILING_LIST
    name = factory.LazyAttribute(lambda o: f"Mailing List #{o.id}")


class MailEntityUnknownFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[MailEntity]
):
    class Meta:
        model = MailEntity

    id = factory.Sequence(lambda n: 50_900_001 + n)
    category = MailEntity.Category.UNKNOWN


class SkillSetFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[SkillSet]
):
    class Meta:
        model = SkillSet

    description = factory.Faker("sentence")
    is_visible = True
    name = factory.Sequence(lambda n: f"Skill Set #{1 + n}")
    ship_type = None

    @factory.post_generation
    def groups(self, create, extracted, **kwargs):
        if not create or not extracted:
            return

        self.groups.add(*extracted)


class SkillSetGroupFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[SkillSetGroup]
):
    class Meta:
        model = SkillSetGroup

    description = factory.Faker("paragraph")
    is_doctrine = False
    is_active = True
    name = factory.Sequence(lambda n: f"Skill Group #{1 + n}")


class SkillSetSkillFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[SkillSetSkill]
):
    class Meta:
        model = SkillSetSkill

    skill_set = factory.SubFactory(SkillSetFactory)
    eve_type = factory.SubFactory(NavigationSkillTypeFactory)
    required_level = 3
    recommended_level = None


# Character


class CharacterFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[Character]
):
    class Meta:
        model = Character
        exclude = ("user",)

    class Params:
        is_main = True
        alt_character = None

    user = factory.SubFactory(UserMainBasicAccessFactory)

    @factory.lazy_attribute
    def eve_character(self):
        if self.is_main:
            return self.user.profile.main_character

        ec = self.alt_character or EveCharacterFactory()
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


# Character Sections


class CharacterAssetFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[CharacterAsset]
):
    class Meta:
        model = CharacterAsset

    character = factory.SubFactory(CharacterFactory)
    eve_type = factory.SubFactory(EveTypeFactory)
    is_blueprint_copy = False
    is_singleton = False
    item_id = factory.Sequence(lambda n: 1_200_000_000_000 + n)
    location = factory.SubFactory(LocationStationFactory)
    location_flag = "Hangar"
    parent = None
    quantity = factory.fuzzy.FuzzyInteger(1, 10_000)


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
    name = factory.Faker("color_name")


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
    title = factory.Faker("words")

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
    def items(self, create, extracted, **kwargs):
        if not create or extracted is False:
            return
        if extracted:
            self.contracts.add(*extracted)
        else:
            CharacterContractItemFactory(contract=self)


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
    def items(self, create, extracted, **kwargs):
        if not create or extracted is False:
            return
        if extracted:
            self.contracts.add(*extracted)
        else:
            CharacterContractItemFactory(contract=self)

    @factory.post_generation
    def bids(self, create, extracted, **kwargs):
        if not create or not extracted:
            return

        for _ in range(extracted):
            CharacterContractBidFactory(contract=self)


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
    faction = factory.SubFactory(EveFactionFactory, id=500001, name="Caldari State")
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
    name = factory.Faker("color_name")


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


class CharacterMailFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[CharacterMail]
):
    class Meta:
        model = CharacterMail

    body = factory.Faker("paragraph")
    character = factory.SubFactory(CharacterFactory)
    is_read = False
    mail_id = factory.Sequence(lambda n: 101 + n)
    sender = factory.SubFactory(MailEntityCharacterFactory)
    subject = factory.Faker("sentence")
    timestamp = factory.LazyFunction(now)

    @factory.post_generation
    def recipients(self, create, extracted, **kwargs):
        if not create or extracted is False:
            return

        if extracted:
            self.recipients.add(*extracted)
        else:
            self.recipients.add(MailEntityCharacterFactory())

    @factory.post_generation
    def labels(self, create, extracted, **kwargs):
        if not create or not extracted:
            return

        self.labels.add(*extracted)


class CharacterMailLabelFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[CharacterMailLabel]
):
    class Meta:
        model = CharacterMailLabel

    character = factory.SubFactory(CharacterFactory)
    label_id = factory.Sequence(lambda n: 1 + n)
    name = factory.Faker("word")
    color = factory.Faker("color")
    unread_count = 0


class CharacterMiningLedgerEntryFactory(
    factory.django.DjangoModelFactory,
    metaclass=BaseMetaFactory[CharacterMiningLedgerEntry],
):
    class Meta:
        model = CharacterMiningLedgerEntry

    character = factory.SubFactory(CharacterFactory)
    date = factory.LazyAttribute(lambda _: now().date())
    eve_solar_system = factory.SubFactory(EveSolarSystemFactory)
    eve_type = factory.SubFactory(EveTypeFactory)
    quantity = factory.fuzzy.FuzzyInteger(100, 10_000)


class CharacterOnlineStatusFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[CharacterOnlineStatus]
):
    class Meta:
        model = CharacterOnlineStatus

    character = factory.SubFactory(CharacterFactory)
    last_login = factory.fuzzy.FuzzyDateTime(now() - dt.timedelta(days=7), now())
    last_logout = factory.fuzzy.FuzzyDateTime(now() - dt.timedelta(days=7), now())
    logins = factory.fuzzy.FuzzyInteger(1, 5_000)


class CharacterPlanetFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[CharacterPlanet]
):
    class Meta:
        model = CharacterPlanet

    character = factory.SubFactory(CharacterFactory)
    eve_planet = factory.SubFactory(EvePlanetFactory)
    last_update_at = factory.LazyFunction(now)
    num_pins = factory.fuzzy.FuzzyInteger(1, 50)
    upgrade_level = factory.fuzzy.FuzzyInteger(0, 5)


class CharacterRoleFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[CharacterRole]
):
    class Meta:
        model = CharacterRole

    character = factory.SubFactory(CharacterFactory)
    location = CharacterRole.Location.UNIVERSAL
    role = factory.fuzzy.FuzzyChoice(CharacterRole.Role.values)


class CharacterShipFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[CharacterShip]
):
    class Meta:
        model = CharacterShip

    character = factory.SubFactory(CharacterFactory)
    eve_type = factory.SubFactory(ShipTypeFactory)
    item_id = factory.Sequence(lambda n: 100_009_001 + n)
    name = factory.Faker("word")


class CharacterSkillFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[CharacterSkill]
):
    class Meta:
        model = CharacterSkill

    character = factory.SubFactory(CharacterFactory)
    eve_type = factory.SubFactory(NavigationSkillTypeFactory)
    active_skill_level = factory.fuzzy.FuzzyInteger(0, 5)
    trained_skill_level = factory.LazyAttribute(lambda o: o.active_skill_level)

    @factory.lazy_attribute
    def skillpoints_in_skill(self):
        rank = factory.fuzzy.FuzzyInteger(1, 16).fuzz()
        n = self.trained_skill_level
        return 250 * rank * math.sqrt(math.pow(32, n - 1))


class CharacterSkillqueueEntryFactory(
    factory.django.DjangoModelFactory,
    metaclass=BaseMetaFactory[CharacterSkillqueueEntry],
):
    class Meta:
        model = CharacterSkillqueueEntry

    character = factory.SubFactory(CharacterFactory)
    eve_type = factory.SubFactory(NavigationSkillTypeFactory)
    finish_date = factory.fuzzy.FuzzyDateTime(
        now() + dt.timedelta(hours=1), now() + dt.timedelta(days=15)
    )
    finished_level = factory.fuzzy.FuzzyInteger(1, 5)
    level_end_sp = factory.LazyAttribute(lambda o: o.level_start_sp + 100_000)
    level_start_sp = factory.fuzzy.FuzzyInteger(0, 10_000)
    queue_position = factory.Sequence(lambda n: 1 + n)
    start_date = factory.fuzzy.FuzzyDateTime(
        now() - dt.timedelta(days=15), now() - dt.timedelta(hours=1)
    )
    training_start_sp = 0


class CharacterSkillpointsFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[CharacterSkillpoints]
):
    class Meta:
        model = CharacterSkillpoints

    character = factory.SubFactory(CharacterFactory)
    total = factory.fuzzy.FuzzyInteger(10_000, 10_000_000)


class CharacterStandingFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[CharacterStanding]
):
    class Meta:
        model = CharacterStanding

    character = factory.SubFactory(CharacterFactory)
    eve_entity = factory.SubFactory(EveEntityCharacterFactory)
    standing = factory.fuzzy.FuzzyFloat(-10, 10)


class CharacterSkillSetCheckFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[CharacterSkillSetCheck]
):
    class Meta:
        model = CharacterSkillSetCheck

    character = factory.SubFactory(CharacterFactory)


class CharacterTitleFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[CharacterTitle]
):
    class Meta:
        model = CharacterTitle

    character = factory.SubFactory(CharacterFactory)
    name = factory.Faker("word")
    title_id = factory.Sequence(lambda n: 1 + n)


class CharacterWalletBalanceFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[CharacterWalletBalance]
):
    class Meta:
        model = CharacterWalletBalance

    character = factory.SubFactory(CharacterFactory)
    total = factory.fuzzy.FuzzyDecimal(0, 10_000_000_000)


class CharacterWalletJournalEntryFactory(
    factory.django.DjangoModelFactory,
    metaclass=BaseMetaFactory[CharacterWalletJournalEntry],
):
    class Meta:
        model = CharacterWalletJournalEntry

    amount = factory.fuzzy.FuzzyDecimal(0, 10_000_000_000)
    balance = factory.fuzzy.FuzzyDecimal(0, 10_000_000_000)
    context_id_type = CharacterWalletJournalEntry.CONTEXT_ID_TYPE_UNDEFINED
    character = factory.SubFactory(CharacterFactory)
    date = factory.LazyFunction(now)
    description = factory.Faker("sentence")
    entry_id = factory.Sequence(lambda n: 1 + n)
    first_party = factory.SubFactory(EveEntityCharacterFactory)
    reason = factory.Faker("sentence")
    ref_type = "player_donation"
    second_party = factory.SubFactory(EveEntityCharacterFactory)


class CharacterWalletTransactionFactory(
    factory.django.DjangoModelFactory,
    metaclass=BaseMetaFactory[CharacterWalletTransaction],
):
    class Meta:
        model = CharacterWalletTransaction

    character = factory.SubFactory(CharacterFactory)
    client = factory.SubFactory(EveEntityCharacterFactory)
    date = factory.LazyFunction(now)
    eve_type = factory.SubFactory(EveTypeFactory)
    is_buy = True
    is_personal = True
    journal_ref = None
    location = factory.SubFactory(LocationStationFactory)
    quantity = factory.fuzzy.FuzzyInteger(1, 10_000)
    transaction_id = factory.Sequence(lambda n: 1 + n)
    unit_price = factory.fuzzy.FuzzyDecimal(0, 500_000_000)
