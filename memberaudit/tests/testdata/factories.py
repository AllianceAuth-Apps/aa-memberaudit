"""Factories for creating test objects with defaults."""

import datetime as dt
import random
from itertools import count
from pathlib import Path
from typing import Iterable

from django.contrib.auth.models import Group, User
from django.utils.timezone import now
from eveuniverse.models import (
    EveEntity,
    EveMarketPrice,
    EvePlanet,
    EveSolarSystem,
    EveType,
)

from allianceauth.authentication.models import State
from allianceauth.eveonline.models import EveCharacter
from app_utils.testing import create_authgroup

from memberaudit.core.fittings import Fitting, Item, Module
from memberaudit.core.skill_plans import SkillPlan
from memberaudit.core.skills import Skill
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

from .constants import (
    EveCategoryId,
    EveFactionId,
    EveSolarSystemId,
    EveStationId,
    EveTypeId,
)


def create_character(eve_character: EveCharacter, **kwargs) -> Character:
    params = {"eve_character": eve_character}
    params.update(kwargs)
    obj = Character(**params)
    obj.save(ignore_cache=True)
    return obj


def create_character_from_user(user: User, **kwargs):
    """Create new Character object from user. The user needs to have a main character.

    This factory is designed to work with both the old and new variant of Character
    introduced in version 2.
    """
    eve_character = user.profile.main_character
    if not eve_character:
        raise ValueError("User needs to have a main character.")

    kwargs.update({"eve_character": eve_character})
    return create_character(**kwargs)


def build_character_asset(character: Character, **kwargs) -> CharacterAsset:
    item_id = kwargs.get("item_id") or next_number("asset_item_id") + 1_200_000_000_000
    params = {
        "character": character,
        "item_id": item_id,
        "is_singleton": False,
        "quantity": 1,
        "location_flag": "Hangar",
    }
    params.update(kwargs)
    _set_missing_foreign_keys(params, eve_type_id=EveTypeId.VELDSPAR)
    if params["is_singleton"] and not params.get("name"):
        params["name"] = (f"Generated asset #{item_id}",)
    return CharacterAsset(**params)


def create_character_asset(character: Character, **kwargs) -> CharacterAsset:
    obj = build_character_asset(character, **kwargs)
    obj.save()
    return obj


def create_character_attributes(character: Character, **kwargs) -> CharacterAttributes:
    params = {
        "character": character,
        "bonus_remaps": 4,
        "charisma": 16,
        "intelligence": 17,
        "memory": 18,
        "perception": 19,
        "willpower": 20,
    }
    params.update(kwargs)
    return CharacterAttributes.objects.create(**params)


def create_character_clone_info(character: Character, **kwargs) -> CharacterCloneInfo:
    params = {
        "character": character,
        "last_clone_jump_date": now() - dt.timedelta(days=7),
        "last_station_change_date": now() - dt.timedelta(days=90),
    }
    params.update(kwargs)
    _set_missing_foreign_keys(params, home_location_id=1000000000001)
    return CharacterCloneInfo.objects.create(**params)


def create_character_contact(
    character: Character, eve_entity: EveEntity, **kwargs
) -> CharacterContact:
    params = {
        "character": character,
        "eve_entity": eve_entity,
        "is_blocked": False,
        "is_watched": False,
        "standing": 0.0,
    }
    params.update(kwargs)
    return CharacterContact.objects.create(**params)


def create_character_contact_label(
    character: Character, **kwargs
) -> CharacterContactLabel:
    label_id = kwargs.get("label_id") or next_number("character_contact_label_id") + 100
    params = {
        "character": character,
        "label_id": label_id,
        "name": f"Test Label #{label_id}",
    }
    params.update(kwargs)
    return CharacterContactLabel.objects.create(**params)


def create_character_contract(character: Character, **kwargs) -> CharacterContract:
    date_issued = kwargs.get("date_issued") or now()
    contract_id = kwargs.get("contract_id") or next_number("contract_id") + 190_000_000
    params = {
        "character": character,
        "contract_id": contract_id,
        "availability": CharacterContract.AVAILABILITY_PERSONAL,
        "contract_type": CharacterContract.TYPE_ITEM_EXCHANGE,
        "date_issued": date_issued,
        "date_expired": date_issued + dt.timedelta(days=3),
        "for_corporation": False,
        "status": CharacterContract.STATUS_OUTSTANDING,
        "title": f"Test Contract #{contract_id}",
    }
    params.update(kwargs)
    _set_missing_foreign_keys(params, assignee_id=1002)
    if "issuer_id" not in params and "issuer" not in kwargs:
        params["issuer_id"] = 1001
        params["issuer_corporation_id"] = 2001
    return CharacterContract.objects.create(**params)


def create_character_contract_courier(
    character: Character, **kwargs
) -> CharacterContract:
    start_location = kwargs.get("start_location") or create_location()
    end_location = kwargs.get("end_location") or create_location()
    params = {
        "character": character,
        "availability": CharacterContract.AVAILABILITY_PERSONAL,
        "contract_type": CharacterContract.TYPE_COURIER,
        "days_to_complete": 7,
        "end_location": end_location,
        "reward": 100_000_000,
        "start_location": start_location,
        "status": CharacterContract.STATUS_OUTSTANDING,
        "volume": 250_000,
    }
    params.update(kwargs)
    return create_character_contract(**params)


def create_character_contract_item(
    contract: CharacterContract, **kwargs
) -> CharacterContractItem:
    record_id = kwargs.get("record_id") or next_number("contract_item_record_id")
    params = {
        "contract": contract,
        "record_id": record_id,
        "is_included": True,
        "is_singleton": False,
        "quantity": 1,
    }
    params.update(kwargs)
    _set_missing_foreign_keys(params, eve_type_id=EveTypeId.MERLIN)
    return CharacterContractItem.objects.create(**params)


def create_character_contract_bid(
    contract: CharacterContract, bidder: EveEntity, **kwargs
) -> CharacterContractBid:
    bid_id = kwargs.get("bid_id") or next_number("contract_item_bid_id")
    params = {
        "contract": contract,
        "bid_id": bid_id,
        "amount": random.randint(1_000_000, 10_000_000_000),
        "bidder": bidder,
        "date_bid": now(),
    }
    params.update(kwargs)
    return CharacterContractBid.objects.create(**params)


def create_character_corporation_history(
    character: Character, **kwargs
) -> CharacterCorporationHistory:
    record_id = kwargs.get("record_id") or next_number(
        "create_character_details_record_id"
    )
    weeks = max(0, 1000 - record_id * 20)
    params = {
        "character": character,
        "record_id": record_id,
        "start_date": now() - dt.timedelta(weeks=weeks),
    }
    params.update(kwargs)
    return CharacterCorporationHistory.objects.create(**params)


def create_character_details(character: Character, **kwargs) -> CharacterDetails:
    params = {
        "character": character,
        "birthday": now() - dt.timedelta(weeks=200),
        "name": character.eve_character.character_name,
    }
    params.update(kwargs)
    _set_missing_foreign_keys(
        params,
        alliance_id=character.eve_character.alliance_id,
        corporation_id=character.eve_character.corporation_id,
        eve_bloodline_id=1,
        eve_race_id=1,
    )
    return CharacterDetails.objects.create(**params)


def create_character_fw_stats(character: Character, **kwargs) -> CharacterFwStats:
    current_rank = random.randint(1, 5)
    highest_rank = max(current_rank, random.randint(1, 5))
    kills_yesterday = random.randint(1, 100)
    kills_last_week = max(kills_yesterday, random.randint(1, 700))
    kills_total = max(kills_last_week, random.randint(1, 5000))
    victory_points_yesterday = random.randint(1, 1000)
    victory_points_last_week = max(victory_points_yesterday, random.randint(1, 7000))
    victory_points_total = max(victory_points_last_week, random.randint(1, 50000))
    enlisted_on = now() - dt.timedelta(
        days=random.randint(1, 180), hours=random.randint(1, 24)
    )
    params = {
        "character": character,
        "current_rank": current_rank,
        "enlisted_on": enlisted_on,
        "highest_rank": highest_rank,
        "kills_last_week": kills_last_week,
        "kills_total": kills_total,
        "kills_yesterday": kills_yesterday,
        "victory_points_last_week": victory_points_last_week,
        "victory_points_total": victory_points_total,
        "victory_points_yesterday": victory_points_yesterday,
    }
    params.update(kwargs)
    _set_missing_foreign_keys(params, faction_id=EveFactionId.CALDARI_STATE)
    return CharacterFwStats.objects.create(**params)


def create_character_implant(character: Character, **kwargs) -> CharacterImplant:
    params = {"character": character}
    params.update(kwargs)
    _set_missing_foreign_keys(params, eve_type_id=EveTypeId.HIGH_GRADE_SNAKE_ALPHA)
    return CharacterImplant.objects.create(**params)


def create_character_jump_clone(character: Character, **kwargs) -> CharacterJumpClone:
    jump_clone_id = kwargs.get("jump_clone_id") or next_number(
        "create_character_implant_jump_clone_id"
    )
    params = {"character": character, "jump_clone_id": jump_clone_id}
    params.update(kwargs)
    _set_missing_foreign_keys(params, location_id=EveStationId.JITA_44)
    return CharacterJumpClone.objects.create(**params)


def create_character_jump_clone_implant(
    jump_clone: CharacterJumpClone, **kwargs
) -> CharacterJumpCloneImplant:
    params = {"jump_clone": jump_clone}
    params.update(kwargs)
    _set_missing_foreign_keys(params, eve_type_id=EveTypeId.HIGH_GRADE_SNAKE_ALPHA)
    return CharacterJumpCloneImplant.objects.create(**params)


def create_character_location(character: Character, **kwargs) -> CharacterLocation:
    params = {"character": character}
    params.update(kwargs)
    location = kwargs.get("location")
    if location and location.eve_solar_system:
        params["eve_solar_system"] = location.eve_solar_system
    else:
        _set_missing_foreign_keys(params, eve_solar_system_id=EveSolarSystemId.AMAMAKE)
    return CharacterLocation.objects.create(**params)


def create_character_loyalty_entry(
    character: Character, **kwargs
) -> CharacterLoyaltyEntry:
    params = {
        "character": character,
        "loyalty_points": random.randint(100, 1_000_000),
    }
    params.update(kwargs)
    return CharacterLoyaltyEntry.objects.create(**params)


def create_character_mail(
    character: Character,
    recipients: Iterable[MailEntity] = None,
    labels: Iterable[CharacterMailLabel] = None,
    **kwargs,
) -> CharacterMail:
    timestamp = kwargs.get("timestamp") or now()
    mail_id = kwargs.get("mail_id") or next_number("mail_id")
    params = {
        "character": character,
        "mail_id": mail_id,
        "subject": f"Test Subject #{mail_id}",
        "body": f"Test Body #{mail_id}",
        "timestamp": timestamp,
    }
    if "sender" not in kwargs and "sender_id" not in kwargs:
        params["sender"] = create_mail_entity_from_eve_entity(id=1002)
    params.update(kwargs)
    obj = CharacterMail.objects.create(**params)
    if not recipients:
        character_id = character.eve_character.character_id
        recipients = [create_mail_entity_from_eve_entity(id=character_id)]
    obj.recipients.add(*recipients)
    if labels:
        obj.labels.add(*labels)
    return obj


def create_character_mail_label(character: Character, **kwargs) -> CharacterMailLabel:
    label_id = kwargs.get("label_id") or next_number("mail_label_id")
    params = {
        "character": character,
        "label_id": label_id,
        "name": f"Label #{label_id}",
    }
    params.update(kwargs)
    return CharacterMailLabel.objects.create(**params)


def create_character_mining_ledger_entry(
    character: Character, **kwargs
) -> CharacterMiningLedgerEntry:
    solar_system_ids = EveSolarSystem.objects.values_list("id", flat=True)
    ore_type_ids = EveType.objects.filter(
        eve_group__eve_category_id=EveCategoryId.ASTEROID, published=True
    ).values_list("id", flat=True)
    params = {
        "character": character,
        "date": (now() - dt.timedelta(days=random.randint(0, 300))).date(),
        "quantity": random.randint(10_000, 50_000),
        "eve_solar_system": EveSolarSystem.objects.get(
            id=random.choice(solar_system_ids)
        ),
        "eve_type": EveType.objects.get(id=random.choice(ore_type_ids)),
    }
    params.update(kwargs)
    return CharacterMiningLedgerEntry.objects.create(**params)


def create_character_online_status(
    character: Character, **kwargs
) -> CharacterOnlineStatus:
    params = {
        "character": character,
        "last_login": now() - dt.timedelta(days=1),
        "last_logout": now() - dt.timedelta(days=1) + dt.timedelta(hours=4),
        "logins": 42,
    }
    params.update(kwargs)
    return CharacterOnlineStatus.objects.create(**params)


def create_character_planet(character: Character, **kwargs) -> CharacterPlanet:
    all_planets = set(EvePlanet.objects.values_list("id", flat=True))
    colonized_planets = set(
        CharacterPlanet.objects.values_list("eve_planet_id", flat=True)
    )
    available_planets = all_planets - colonized_planets
    if not available_planets:
        raise RuntimeError("No free planet to colonize")
    params = {
        "character": character,
        "last_update_at": now() - dt.timedelta(days=random.randint(0, 300)),
        "num_pins": random.randint(1, 10),
        "eve_planet": EvePlanet.objects.get(id=random.choice(list(available_planets))),
        "upgrade_level": random.randint(0, 5),
    }
    params.update(kwargs)
    return CharacterPlanet.objects.create(**params)


def create_character_role(character: Character, **kwargs) -> CharacterRole:
    params = {
        "character": character,
        "role": CharacterRole.Role.DIRECTOR,
        "location": CharacterRole.Location.UNIVERSAL,
    }
    params.update(kwargs)
    return CharacterRole.objects.create(**params)


def create_character_ship(character: Character, **kwargs) -> CharacterShip:
    item_id = kwargs.get("item_id") or next_number("asset_item_id")
    params = {"character": character, "item_id": item_id, "name": "My sweet ride"}
    params.update(kwargs)
    _set_missing_foreign_keys(params, eve_type_id=EveTypeId.MERLIN)
    return CharacterShip.objects.create(**params)


def create_character_skill(character: Character, **kwargs) -> CharacterSkill:
    params = {
        "character": character,
        "active_skill_level": 3,
        "skillpoints_in_skill": 1000,
        "trained_skill_level": 3,
    }
    params.update(kwargs)
    _set_missing_foreign_keys(params, eve_type_id=EveTypeId.AMARR_CARRIER)
    return CharacterSkill.objects.create(**params)


def create_character_skillqueue_entry(
    character: Character, **kwargs
) -> CharacterSkillqueueEntry:
    queue_position = kwargs.get("queue_position") or next_number(
        "skillqueue_queue_position"
    )
    params = {
        "character": character,
        "finished_level": 3,
        "queue_position": queue_position,
        "level_end_sp": 512,
        "level_start_sp": 128,
        "start_date": now(),
    }
    params.update(kwargs)
    _set_missing_foreign_keys(params, eve_type_id=EveTypeId.AMARR_CARRIER)
    return CharacterSkillqueueEntry.objects.create(**params)


def create_character_skillpoints(
    character: Character, **kwargs
) -> CharacterSkillpoints:
    params = {"character": character, "total": 10_000_000, "unallocated": 500_000}
    params.update(kwargs)
    return CharacterSkillpoints.objects.create(**params)


def create_character_skill_set_check(
    character: Character, skill_set: SkillSet, **kwargs
) -> CharacterSkillSetCheck:
    return CharacterSkillSetCheck.objects.create(
        character=character, skill_set=skill_set, **kwargs
    )


def create_character_standing(
    character: Character, eve_entity: EveEntity, **kwargs
) -> CharacterStanding:
    params = {
        "character": character,
        "eve_entity": eve_entity,
        "standing": 0.0,
    }
    params.update(kwargs)
    return CharacterStanding.objects.create(**params)


def create_character_title(character: Character, **kwargs) -> CharacterRole:
    title_id = kwargs.get("title_id") or next_number("title_id")
    params = {
        "character": character,
        "name": f"Dummy title #{title_id}",
        "title_id": title_id,
    }
    params.update(kwargs)
    return CharacterTitle.objects.create(**params)


def create_character_update_status(
    character: Character, **kwargs
) -> CharacterUpdateStatus:
    params = {
        "character": character,
        "section": Character.UpdateSection.ASSETS,
        "is_success": True,
        "run_started_at": now() - dt.timedelta(minutes=5),
        "run_finished_at": now(),
    }
    params.update(kwargs)
    return CharacterUpdateStatus.objects.create(**params)


def create_character_wallet_balance(
    character: Character, **kwargs
) -> CharacterWalletBalance:
    params = {"character": character, "total": 20_000_000.0}
    params.update(kwargs)
    return CharacterWalletBalance.objects.create(**params)


def create_character_wallet_journal_entry(
    character: Character, **kwargs
) -> CharacterWalletJournalEntry:
    entry_id = kwargs.get("entry_id") or next_number("wallet_journal_entry_id")
    params = {
        "character": character,
        "entry_id": entry_id,
        "amount": 1_000_000.0,
        "balance": 20_000_000.0,
        "ref_type": "player_donation",
        "context_id_type": CharacterWalletJournalEntry.CONTEXT_ID_TYPE_UNDEFINED,
        "date": now(),
        "description": "test description",
        "reason": "test reason",
    }
    params.update(kwargs)
    _set_missing_foreign_keys(params, first_party_id=1001, second_party_id=1002)
    return CharacterWalletJournalEntry.objects.create(**params)


def create_character_wallet_transaction(
    character: Character, **kwargs
) -> CharacterWalletTransaction:
    transaction_id = kwargs.get("transaction_id") or next_number(
        "create_character_wallet_transaction_transaction_id"
    )
    params = {
        "character": character,
        "transaction_id": transaction_id,
        "date": now(),
        "is_buy": True,
        "is_personal": True,
        "quantity": 1,
        "unit_price": float(random.randint(10_000, 100_000_000)) + random.random(),
    }
    params.update(kwargs)
    _set_missing_foreign_keys(
        params,
        client_id=1002,
        location_id=EveStationId.JITA_44,
        eve_type_id=EveTypeId.MERLIN,
    )
    return CharacterWalletTransaction.objects.create(**params)


def create_compliance_group(states: Iterable[State] = None, **kwargs) -> Group:
    group = create_authgroup(states, internal=True, **kwargs)
    create_compliance_group_designation(group)
    return group


def create_compliance_group_designation(
    group: Group, **kwargs
) -> ComplianceGroupDesignation:
    params = {"group": group}
    params.update(kwargs)
    return ComplianceGroupDesignation.objects.create(**params)


def create_fitting(**kwargs):
    """Requires eveuniverse to be loaded."""
    params = {
        "name": "Test fitting",
        "ship_type": EveType.objects.get(name="Tristan"),
        "high_slots": [
            Module(
                EveType.objects.get(name="125mm Gatling AutoCannon II"),
                charge_type=EveType.objects.get(name="EMP S"),
            ),
            None,
        ],
        "medium_slots": [Module(EveType.objects.get(name="Warp Disruptor II")), None],
        "low_slots": [
            Module(EveType.objects.get(name="Drone Damage Amplifier II")),
            None,
        ],
        "rig_slots": [
            Module(EveType.objects.get(name="Small EM Shield Reinforcer I")),
            None,
        ],
        "drone_bay": [Item(EveType.objects.get(name="Acolyte II"), quantity=5)],
        "cargo_bay": [Item(EveType.objects.get(name="EMP S"), quantity=3)],
    }
    params.update(kwargs)
    return Fitting(**params)


def create_fitting_text(file_name: str) -> str:
    testdata_folder = Path(__file__).parent / "fittings"
    fitting_file = testdata_folder / file_name
    with fitting_file.open("r") as file:
        return file.read()


def create_location(**kwargs) -> Location:
    location_id = kwargs.get("id") or next_number("location_id") + 1_700_000_000_000
    params = {
        "id": location_id,
        "name": f"Test Location #{location_id}",
    }
    params.update(kwargs)
    _set_missing_foreign_keys(
        params,
        eve_solar_system_id=EveSolarSystemId.AMAMAKE,
        eve_type_id=EveTypeId.ASTRAHUS,
    )
    return Location.objects.create(**params)


def create_location_eve_solar_system(**kwargs) -> Location:
    solar_system_id = kwargs.get("id") or EveSolarSystemId.AMAMAKE
    eve_solar_system = EveSolarSystem.objects.get(id=solar_system_id)
    params = {"name": eve_solar_system.name, "eve_type_id": EveTypeId.SOLAR_SYSTEM}
    params.update(kwargs)
    return create_location(**params)


def create_mail_entity(**kwargs) -> MailEntity:
    my_id = kwargs.get("id") or next_number("create_mail_entity_id") + 10_000_000
    params = {
        "id": my_id,
        "name": "",
        "category": MailEntity.Category.UNKNOWN,
    }
    params.update(kwargs)
    return MailEntity.objects.create(**params)


def create_mail_entity_from_eve_entity(id: int) -> MailEntity:
    obj, _ = MailEntity.objects.update_or_create_from_eve_entity_id(id=id)
    return obj


def create_mailing_list(**kwargs) -> MailEntity:
    my_id = kwargs.get("id") or next_number("create_mail_entity_id") + 20_000_000
    params = {
        "id": my_id,
        "name": f"Mailing List #{my_id}",
        "category": MailEntity.Category.MAILING_LIST,
    }
    params.update(kwargs)
    return create_mail_entity(**params)


def create_skill(**kwargs) -> Skill:
    params = {}
    if "eve_type" not in kwargs:
        params["eve_type"] = (
            EveType.objects.filter(
                eve_group__eve_category_id=EveCategoryId.SKILL, published=True
            )
            .order_by("?")
            .first()
        )
    if "level" not in kwargs:
        params["level"] = random.randint(1, 5)
    params.update(kwargs)
    return Skill(**params)


def create_skill_plan(**kwargs) -> SkillPlan:
    my_id = next_number("skill_plan_id")
    params = {"name": f"Test Skill Plan {my_id}"}
    if "skills" not in kwargs:
        params["skills"] = [create_skill() for _ in range(random.randint(1, 5))]
    params.update(kwargs)
    return SkillPlan(**params)


def create_skill_set(**kwargs) -> SkillSet:
    my_id = next_number("skill_set_id")
    params = {
        "name": f"Merlin #{my_id}",
        "description": "Generated skill set",
    }
    params.update(kwargs)
    _set_missing_foreign_keys(params, ship_type_id=EveTypeId.MERLIN)
    return SkillSet.objects.create(**params)


def create_skill_set_group(**kwargs) -> SkillSetGroup:
    my_id = next_number("skill_set_group_id")
    params = {
        "name": f"Test Group #{my_id}",
        "description": "Generated skill set group",
    }
    params.update(kwargs)
    return SkillSetGroup.objects.create(**params)


def create_skill_set_skill(skill_set, **kwargs) -> SkillSetSkill:
    params = {
        "skill_set": skill_set,
        "required_level": 1,
    }
    params.update(kwargs)
    _set_missing_foreign_keys(params, eve_type_id=EveTypeId.AMARR_CARRIER)
    return SkillSetSkill.objects.create(**params)


def create_eve_market_price(**kwargs) -> EveMarketPrice:
    average_price = (
        kwargs.get("average_price")
        or float(random.randint(10_000, 100_000_000)) + random.random()
    )
    adjusted_price = kwargs.get("adjusted_price") or average_price
    params = {
        "average_price": average_price,
        "adjusted_price": adjusted_price,
    }
    params.update(kwargs)
    _set_missing_foreign_keys(params, eve_type_id=EveTypeId.VELDSPAR)
    return EveMarketPrice.objects.create(**params)


def next_number(key=None, offset=None) -> int:
    if key is None:
        key = "_general"
    try:
        return next_number._counter[key].__next__()
    except AttributeError:
        next_number._counter = {}
    except KeyError:
        pass
    next_number._counter[key] = count(start=1)
    number = next_number._counter[key].__next__()
    result = number + offset if offset else number
    return result


def _set_missing_foreign_keys(params: dict, **kwargs):
    """Set foreign keys in dict when they and their variant are not present."""
    for key_id, value in kwargs.items():
        key = key_id.replace("_id", "")
        if key not in params and key_id not in params:
            params[key_id] = int(value)
