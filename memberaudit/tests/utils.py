"""Shared utils for tests."""

import json
import os
from typing import Tuple

from django.contrib.auth.models import Permission, User
from django.db.models import QuerySet
from django.http import JsonResponse
from django.test import RequestFactory, TestCase
from esi.models import Token
from eveuniverse.models import EveEntity, EveSolarSystem, EveType

from allianceauth.authentication.models import CharacterOwnership
from allianceauth.eveonline.models import EveCharacter
from allianceauth.tests.auth_utils import AuthUtils
from app_utils.testing import NoSocketsTestCase, add_character_to_user, response_text

from memberaudit.models import Character, Location

from .testdata.factories import create_character
from .testdata.load_entities import load_entities
from .testdata.load_eveuniverse import load_eveuniverse
from .testdata.load_locations import load_locations


class CharacterUpdateTestDataMixin:
    """Mixin for TestCase class defining a complete character and setting up fixtures."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        load_locations()
        cls.character_1001 = create_memberaudit_character(1001)
        cls.character_1002 = create_memberaudit_character(1002)
        cls.corporation_2001 = EveEntity.objects.get(id=2001)
        cls.corporation_2002 = EveEntity.objects.get(id=2002)
        cls.token = cls.character_1001.user.token_set.first()
        cls.jita = EveSolarSystem.objects.get(id=30000142)
        cls.jita_44 = Location.objects.get(id=60003760)
        cls.amamake = EveSolarSystem.objects.get(id=30002537)
        cls.structure_1 = Location.objects.get(id=1000000000001)


class TestCharacterUpdateBase(TestCase):
    """TestCase variant defining a complete character and setting up fixtures."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        load_locations()
        cls.character_1001 = create_memberaudit_character(1001)
        cls.character_1002 = create_memberaudit_character(1002)
        cls.corporation_2001 = EveEntity.objects.get(id=2001)
        cls.corporation_2002 = EveEntity.objects.get(id=2002)
        cls.token = (
            cls.character_1001.eve_character.character_ownership.user.token_set.first()
        )
        cls.jita = EveSolarSystem.objects.get(id=30000142)
        cls.jita_44 = Location.objects.get(id=60003760)
        cls.amamake = EveSolarSystem.objects.get(id=30002537)
        cls.structure_1 = Location.objects.get(id=1000000000001)


def create_user_from_evecharacter_with_access(
    character_id: int,
) -> Tuple[User, CharacterOwnership]:
    """Create user with access from an existing eve character and use it as main."""
    auth_character = EveCharacter.objects.get(character_id=character_id)
    user = AuthUtils.create_user(auth_character.character_name)
    user = AuthUtils.add_permission_to_user_by_name("memberaudit.basic_access", user)
    character_ownership = add_character_to_user(
        user, auth_character, is_main=True, scopes=Character.get_esi_scopes()
    )
    return user, character_ownership


def create_memberaudit_character(character_id: int, **kwargs) -> Character:
    """Create a memberaudit character from an existing auth character
    incl. user and making it the main.
    """
    _, character_ownership = create_user_from_evecharacter_with_access(character_id)
    return create_character(eve_character=character_ownership.character, **kwargs)


def add_auth_character_to_user(
    user: User, character_id: int, scopes=None
) -> CharacterOwnership:
    auth_character = EveCharacter.objects.get(character_id=character_id)
    if not scopes:
        scopes = Character.get_esi_scopes()

    return add_character_to_user(user, auth_character, is_main=False, scopes=scopes)


def add_memberaudit_character_to_user(
    user: User, character_id: int, **kwargs
) -> Character:
    character_ownership = add_auth_character_to_user(user, character_id)
    return create_character(eve_character=character_ownership.character, **kwargs)


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
        cls.amarr_carrier_skill_type = EveType.objects.get(id=24311)
        cls.caldari_carrier_skill_type = EveType.objects.get(id=24312)
        cls.gallente_carrier_skill_type = EveType.objects.get(id=24313)
        cls.minmatar_carrier_skill_type = EveType.objects.get(id=24314)
        cls.high_grade_snake_alpha_type = EveType.objects.get(id=19540)
        cls.high_grade_snake_bravo_type = EveType.objects.get(id=19551)


def json_response_to_python_2(response: JsonResponse, data_key="data") -> object:
    """Convert JSON response into Python object."""
    data = json.loads(response_text(response))
    return data[data_key]


def json_response_to_dict_2(response: JsonResponse, key="id", data_key="data") -> dict:
    """Convert JSON response into dict by given key."""
    return {o[key]: o for o in json_response_to_python_2(response, data_key)}


class TestCaseWithFixtures(TestCase):
    fixtures = ["disable_analytics.json"]


class NoSocketsTestCaseFixtures(NoSocketsTestCase):
    fixtures = ["disable_analytics.json"]


def permissions_for_model(model_class) -> QuerySet:
    """Return all permissions defined for a model."""
    app_label = model_class._meta.app_label
    model_name = model_class._meta.model_name
    return Permission.objects.filter(
        content_type__app_label=app_label, content_type__model=model_name
    )


TOX_IS_RUNNING = os.getenv("TOX_IS_RUNNING") == "1"
