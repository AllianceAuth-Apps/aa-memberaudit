# flake8: noqa
"""This is a standalone scripts that generates many test characters for Member Audit."""

import inspect
import os
import sys

current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
myauth_dir = (
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))))
    + "/myauth"
)
sys.path.insert(0, myauth_dir)
import django

# init and setup django project
print("Initializing Django...")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myauth.settings.local")
django.setup()

import random
from typing import Any, Tuple

import requests
from tqdm import tqdm

from allianceauth.authentication.models import State
from allianceauth.eveonline.models import EveCharacter
from allianceauth.tests.auth_utils import AuthUtils

from memberaudit.models import Character, SkillSet
from memberaudit.tests.testdata.factories import create_character_skill_set_check
from memberaudit.tests.utils import create_memberaudit_character

CHARACTER_COUNT = 100  # max number of character to generate
CORPORATION_IDS = [
    98615046,  # KarmaFleet University
    98627389,  # Alpha Academic
    98614492,  # Pandemic Horde High Sec
    98609240,  # Caladrius Hive
]  # eve characters are chosen randomly from these corporations


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
            set_character_skill_set_checks(character)


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


if __name__ == "__main__":
    main()
