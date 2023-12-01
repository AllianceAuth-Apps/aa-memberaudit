# flake8: noqa
"""This is a standalone scripts that generates many test characters for Member Audit."""

import os
import sys
from pathlib import Path

myauth_dir = Path(__file__).parent.parent.parent.parent.parent / "myauth"
sys.path.insert(0, str(myauth_dir))

import django

# init and setup django project
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myauth.settings.local")
print("AA starting up...")
django.setup()

"""MAIN"""

import random
from typing import Any, Tuple

import requests
from tqdm import tqdm

from django.db.models import Max
from eveuniverse.models import EveEntity, EveType

from allianceauth.authentication.models import State
from allianceauth.eveonline.models import EveCharacter
from allianceauth.tests.auth_utils import AuthUtils

from memberaudit.models import Character, Location, SkillSet
from memberaudit.tests.testdata.constants import EveTypeId
from memberaudit.tests.testdata.factories import (
    create_character_asset,
    create_character_jump_clone,
    create_character_jump_clone_implant,
    create_character_skill_set_check,
    create_location,
)
from memberaudit.tests.utils import create_memberaudit_character

# configuration
CHARACTER_COUNT = 100  # max number of characters to generate
CORRUPTED_ASSETS_PER_CHARACTER = 100  # set to 0 to disable
CREATE_SKILL_SET_SKILLS = False

CORPORATION_IDS = [
    98615046,  # KarmaFleet University
    98627389,  # Alpha Academic
    98614492,  # Pandemic Horde High Sec
    98609240,  # Caladrius Hive
]  # eve characters are chosen randomly from these corporations

# setup globals
item_eve_type, _ = EveType.objects.get_or_create_esi(id=EveTypeId.VELDSPAR)
implant_eve_type, _ = EveType.objects.get_or_create_esi(
    id=EveTypeId.HIGH_GRADE_SNAKE_ALPHA
)

locations = Location.objects.filter(
    eve_type__isnull=False, eve_solar_system__isnull=False
)
valid_location_1 = locations.first()
valid_location_2 = locations.last()
if not valid_location_1 or valid_location_1 == valid_location_2:
    raise RuntimeError("Need two valid locations to exist")

character_entity = EveEntity.objects.filter(
    category=EveEntity.CATEGORY_CHARACTER
).first()
if not character_entity:
    raise RuntimeError("Need a character in eve entities to exist")

corporation_entity = EveEntity.objects.filter(
    category=EveEntity.CATEGORY_CORPORATION
).first()
if not corporation_entity:
    raise RuntimeError("Need a corporation in eve entities to exist")

next_location_id = (
    max(1_700_000_000_000, Location.objects.aggregate(Max("id"))["id__max"]) + 1
)


def main():
    my_state = _get_or_create_state_for_test_users()
    _delete_previous_test_characters(my_state)

    created_count = 0
    character_ids = _fetching_random_character_ids()[:CHARACTER_COUNT]
    for character_id in tqdm(
        character_ids, desc="Creating test characters", unit="objects"
    ):
        try:
            eve_character, created = get_or_create_eve_character(character_id)
        except OSError:
            continue
        if created:
            created_count += 1
            my_state.member_characters.add(eve_character)
            character = create_memberaudit_character(character_id, is_disabled=True)
            if CREATE_SKILL_SET_SKILLS:
                set_character_skill_set_checks(character)
            if CORRUPTED_ASSETS_PER_CHARACTER:
                add_invalid_assets_to_character(character)


def _delete_previous_test_characters(my_state):
    num, _ = EveCharacter.objects.filter(
        character_ownership__user__profile__state=my_state
    ).delete()
    if num > 0:
        print(f"Deleted stale test characters.")


def _get_or_create_state_for_test_users():
    my_state, created = State.objects.get_or_create(
        name="Test users", defaults={"priority": 75}
    )
    if created:
        basic_perm = AuthUtils.get_permission_by_name("memberaudit.basic_access")
        my_state.permissions.add(basic_perm)
    return my_state


def _fetching_random_character_ids():
    print(f"Selecting random character IDs from {len(CORPORATION_IDS)} corporations")
    character_ids = set()
    for corporation_id in CORPORATION_IDS:
        r = requests.get(f"https://evewho.com/api/corplist/{corporation_id}")
        if r.ok:
            data = r.json()
            character_ids |= {obj["character_id"] for obj in data["characters"]}

    character_ids = list(character_ids)
    random.shuffle(character_ids)
    return character_ids


def set_character_skill_set_checks(character: Character):
    for skill_set in SkillSet.objects.all():
        obj = create_character_skill_set_check(character=character, skill_set=skill_set)
        if random.choice([True, False, False]):
            skill = skill_set.skills.first()
            obj.failed_recommended_skills.add(skill)


def get_or_create_eve_character(character_id: int) -> Tuple[Any, bool]:
    """Get or create EveCharacter object."""
    try:
        return EveCharacter.objects.get(character_id=character_id), False
    except EveCharacter.DoesNotExist:
        return EveCharacter.objects.create_character(character_id=character_id), True


def add_invalid_assets_to_character(character: Character):
    global next_location_id

    for _ in range(CORRUPTED_ASSETS_PER_CHARACTER):
        next_location_id += 1
        asset = create_character_asset(
            character=character,
            eve_type=item_eve_type,
            location=valid_location_1,
            item_id=next_location_id,
        )
        invalid_location = create_location(id=asset.item_id)
        create_character_asset(
            character=character,
            eve_type=item_eve_type,
            location=invalid_location,
        )
        jump_clone = create_character_jump_clone(
            character=character, location=invalid_location
        )
        create_character_jump_clone_implant(
            jump_clone=jump_clone, eve_type=implant_eve_type
        )


if __name__ == "__main__":
    main()
