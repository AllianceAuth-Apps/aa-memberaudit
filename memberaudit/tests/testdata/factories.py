"""Factories for creating test objects with defaults."""

import datetime as dt
import random
from itertools import count
from pathlib import Path
from typing import Iterable

from django.contrib.auth.models import Group, User
from django.utils.timezone import now
from eveuniverse.models import EveEntity, EvePlanet, EveSolarSystem, EveType

from allianceauth.authentication.models import State
from allianceauth.eveonline.models import EveCharacter
from app_utils.testing import create_authgroup

from memberaudit.constants import EveCategoryId
from memberaudit.core.fittings import Fitting, Item, Module
from memberaudit.core.skill_plans import SkillPlan
from memberaudit.core.skills import Skill
from memberaudit.models import (
    Character,
    CharacterAsset,
    CharacterContact,
    CharacterContract,
    CharacterContractBid,
    CharacterContractItem,
    CharacterFwStats,
    CharacterMail,
    CharacterMailLabel,
    CharacterMiningLedgerEntry,
    CharacterOnlineStatus,
    CharacterPlanet,
    CharacterRole,
    CharacterSkill,
    CharacterSkillSetCheck,
    CharacterStanding,
    CharacterTitle,
    CharacterUpdateStatus,
    CharacterWalletJournalEntry,
    ComplianceGroupDesignation,
    MailEntity,
    SkillSet,
    SkillSetGroup,
    SkillSetSkill,
)


def create_character(eve_character: EveCharacter, **kwargs) -> Character:
    params = {"eve_character": eve_character}
    params.update(kwargs)
    return Character.objects.create(**params)


def create_character_from_user(user: User, **kwargs):
    """Create new Character object from user. The user needs to have a main character.

    This factory is designed to work with both the old and new variant of Character
    introduced in version 2.
    """
    try:
        character_ownership = user.profile.main_character.character_ownership
    except AttributeError:
        raise ValueError("User needs to have a main character.") from None
    if hasattr(Character, "eve_character"):
        params = {"eve_character": character_ownership.character}
    else:
        params = {"character_ownership": character_ownership}
    params.update(kwargs)
    return Character.objects.create(**params)


def create_character_asset(
    character: Character, eve_type: EveType, **kwargs
) -> CharacterAsset:
    item_id = kwargs.get("item_id", next_number("asset_item_id"))
    params = {
        "character": character,
        "item_id": item_id,
        "eve_type": eve_type,
        "is_singleton": True,
        "quantity": 1,
        "location_flag": "Hangar",
        "name": "",
    }
    params.update(kwargs)
    if params["is_singleton"] and not params["name"]:
        params["name"] = (f"Generated asset #{item_id}",)
    return CharacterAsset.objects.create(**params)


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


def create_character_contract(character: Character, **kwargs) -> CharacterContract:
    date_issued = now() if "date_issued" not in kwargs else kwargs["date_issued"]
    params = {
        "character": character,
        "contract_id": next_number("contract_id"),
        "availability": CharacterContract.AVAILABILITY_PERSONAL,
        "contract_type": CharacterContract.TYPE_ITEM_EXCHANGE,
        "assignee_id": 1002,
        "date_issued": date_issued,
        "date_expired": date_issued + dt.timedelta(days=3),
        "for_corporation": False,
        "issuer_id": 1001,
        "issuer_corporation_id": 2001,
        "status": CharacterContract.STATUS_OUTSTANDING,
        "title": "Dummy info",
    }
    params.update(kwargs)
    return CharacterContract.objects.create(**params)


def create_character_contract_item(
    contract: CharacterContract, **kwargs
) -> CharacterContractItem:
    params = {
        "contract": contract,
        "record_id": next_number("contract_item_record_id"),
        "is_included": True,
        "is_singleton": False,
        "quantity": 1,
    }
    if "eve_type" not in kwargs and "eve_type_id" not in kwargs:
        params["eve_type_id"] = 603
    params.update(kwargs)
    return CharacterContractItem.objects.create(**params)


def create_character_contract_bid(
    contract: CharacterContract, bidder: EveEntity, **kwargs
) -> CharacterContractBid:
    params = {
        "contract": contract,
        "bid_id": next_number("contract_item_bid_id"),
        "amount": random.randint(1_000_000, 10_000_000_000),
        "bidder": bidder,
        "date_bid": now(),
    }
    params.update(kwargs)
    return CharacterContractBid.objects.create(**params)


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
    if "faction" not in kwargs and "faction_id" not in kwargs:
        params["faction_id"] = 500001
    params.update(kwargs)
    return CharacterFwStats.objects.create(**params)


def create_character_mail(
    character: Character,
    recipients: Iterable[MailEntity] = None,
    labels: Iterable[CharacterMailLabel] = None,
    **kwargs,
) -> CharacterMail:
    timestamp = now() if "timestamp" not in kwargs else kwargs["timestamp"]
    params = {
        "character": character,
        "subject": "Test Mail",
        "body": "Test Body",
        "timestamp": timestamp,
    }
    if "mail_id" not in kwargs:
        params["mail_id"] = next_number("mail_id")
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
    label_id = next_number("mail_label_id")
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


def create_character_skill(character: Character, **kwargs) -> CharacterSkill:
    params = {
        "character": character,
        "active_skill_level": 3,
        "skillpoints_in_skill": 1000,
        "trained_skill_level": 3,
    }
    params.update(kwargs)
    return CharacterSkill.objects.create(**params)


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
    title_id = (
        next_number("title_id") if "title_id" not in kwargs else kwargs["title_id"]
    )
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
        "started_at": now() - dt.timedelta(minutes=5),
        "finished_at": now(),
    }
    params.update(kwargs)
    return CharacterUpdateStatus.objects.create(**params)


def create_character_wallet_journal_entry(
    character: Character, **kwargs
) -> CharacterWalletJournalEntry:
    params = {
        "character": character,
        "entry_id": next_number("wallet_journal_entry_id"),
        "amount": 1000000.0,
        "balance": 20000000.0,
        "ref_type": "player_donation",
        "context_id_type": CharacterWalletJournalEntry.CONTEXT_ID_TYPE_UNDEFINED,
        "date": now(),
        "description": "test description",
        "first_party_id": 1001,
        "second_party_id": 1002,
        "reason": "test reason",
    }
    params.update(kwargs)
    return CharacterWalletJournalEntry.objects.create(**params)


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


def create_mail_entity_from_eve_entity(id: int) -> MailEntity:
    obj, _ = MailEntity.objects.update_or_create_from_eve_entity_id(id=id)
    return obj


def create_mailing_list(**kwargs) -> MailEntity:
    my_id = next_number("mailing_list_id")
    params = {
        "id": my_id,
        "name": f"Mailing List #{my_id}",
        "category": MailEntity.Category.MAILING_LIST,
    }
    params.update(kwargs)
    return MailEntity.objects.create(**params)


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
    params = {"name": f"Test Set {my_id}", "description": "Generated skill set"}
    params.update(kwargs)
    return SkillSet.objects.create(**params)


def create_skill_set_group(**kwargs) -> SkillSetGroup:
    my_id = next_number("skill_set_group_id")
    params = {"name": f"Test Group {my_id}", "description": "Generated skill set group"}
    params.update(kwargs)
    return SkillSetGroup.objects.create(**params)


def create_skill_set_skill(
    skill_set, eve_type, required_level=1, **kwargs
) -> SkillSetSkill:
    params = {
        "skill_set": skill_set,
        "eve_type": eve_type,
        "required_level": required_level,
    }
    params.update(kwargs)
    return SkillSetSkill.objects.create(**params)


def next_number(key=None) -> int:
    if key is None:
        key = "_general"
    try:
        return next_number._counter[key].__next__()
    except AttributeError:
        next_number._counter = {}
    except KeyError:
        pass
    next_number._counter[key] = count(start=1)
    return next_number._counter[key].__next__()
