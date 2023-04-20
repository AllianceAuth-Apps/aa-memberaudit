import json
from typing import Tuple

from django.contrib.auth.models import User
from django.http import JsonResponse
from django.test import RequestFactory, TestCase
from esi.models import Token
from eveuniverse.models import EveEntity, EveSolarSystem, EveType

from allianceauth.authentication.models import CharacterOwnership
from allianceauth.eveonline.models import EveCharacter
from allianceauth.tests.auth_utils import AuthUtils
from allianceauth.utils.cache import get_redis_client
from app_utils.testing import NoSocketsTestCase, add_character_to_user, response_text

from ..models import Character, Location
from .testdata.load_entities import load_entities
from .testdata.load_eveuniverse import load_eveuniverse
from .testdata.load_locations import load_locations


def create_user_from_evecharacter_with_access(
    character_id: int,
) -> Tuple[User, CharacterOwnership]:
    auth_character = EveCharacter.objects.get(character_id=character_id)
    user = AuthUtils.create_user(auth_character.character_name)
    user = AuthUtils.add_permission_to_user_by_name("memberaudit.basic_access", user)
    character_ownership = add_character_to_user(
        user, auth_character, is_main=True, scopes=Character.get_esi_scopes()
    )
    return user, character_ownership


def create_memberaudit_character(character_id: int) -> Character:
    _, character_ownership = create_user_from_evecharacter_with_access(character_id)
    return Character.objects.create(eve_character=character_ownership.character)


def add_auth_character_to_user(
    user: User, character_id: int, scopes=None
) -> CharacterOwnership:
    auth_character = EveCharacter.objects.get(character_id=character_id)
    if not scopes:
        scopes = Character.get_esi_scopes()

    return add_character_to_user(user, auth_character, is_main=False, scopes=scopes)


def add_memberaudit_character_to_user(user: User, character_id: int) -> Character:
    character_ownership = add_auth_character_to_user(user, character_id)
    return Character.objects.create(eve_character=character_ownership.character)


def scope_names_set(token: Token) -> set:
    return set(token.scopes.values_list("name", flat=True))


class LoadTestDataMixin:
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.factory = RequestFactory()
        load_eveuniverse()
        load_entities()
        load_locations()
        cls.character = create_memberaudit_character(1001)
        cls.user = cls.character.user
        cls.jita = EveSolarSystem.objects.get(id=30000142)
        cls.jita_trade_hub = EveType.objects.get(id=52678)
        cls.corporation_2001 = EveEntity.objects.get(id=2001)
        cls.jita_44 = Location.objects.get(id=60003760)
        cls.structure_1 = Location.objects.get(id=1000000000001)
        cls.skill_type_1 = EveType.objects.get(id=24311)
        cls.skill_type_2 = EveType.objects.get(id=24312)
        cls.skill_type_3 = EveType.objects.get(id=24313)
        cls.skill_type_4 = EveType.objects.get(id=24314)
        cls.item_type_1 = EveType.objects.get(id=19540)
        cls.item_type_2 = EveType.objects.get(id=19551)


def json_response_to_python_2(response: JsonResponse, data_key="data") -> object:
    """Convert JSON response into Python object."""
    data = json.loads(response_text(response))
    return data[data_key]


def json_response_to_dict_2(response: JsonResponse, key="id", data_key="data") -> dict:
    """Convert JSON response into dict by given key."""
    return {x[key]: x for x in json_response_to_python_2(response, data_key)}


def clear_celery_once_locks():
    """Clear all celery once locks (if any exist)."""
    r = get_redis_client()
    if keys := r.keys(":?:qo_memberaudit.*"):
        r.delete(*keys)


class TestCaseWithFixtures(TestCase):
    fixtures = ["disable_analytics.json"]


class NoSocketsTestCaseFixtures(NoSocketsTestCase):
    fixtures = ["disable_analytics.json"]
