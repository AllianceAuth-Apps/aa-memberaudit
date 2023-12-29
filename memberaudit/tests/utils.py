"""Shared utils for tests."""

import json
import logging
from typing import Any, Tuple

from django.contrib.auth.models import Permission, User
from django.db.models import QuerySet
from django.http import JsonResponse
from django.test import TestCase
from esi.models import Token

from allianceauth.authentication.backends import StateBackend
from allianceauth.authentication.models import CharacterOwnership
from allianceauth.eveonline.models import EveCharacter
from allianceauth.tests.auth_utils import AuthUtils
from app_utils.allianceauth import get_redis_client
from app_utils.testing import NoSocketsTestCase, add_character_to_user, response_text

from memberaudit.models import Character

from .testdata.factories import create_character

logger = logging.getLogger(__name__)


def create_user_from_evecharacter_with_access(
    character_id: int, disconnect_signals: bool = True
) -> Tuple[User, CharacterOwnership]:
    """Create user with access from an existing eve character and use it as main."""
    auth_character = EveCharacter.objects.get(character_id=character_id)
    username = StateBackend.iterate_username(auth_character.character_name)
    user = AuthUtils.create_user(username, disconnect_signals=disconnect_signals)
    user = AuthUtils.add_permission_to_user_by_name(
        "memberaudit.basic_access", user, disconnect_signals=disconnect_signals
    )
    character_ownership = add_character_to_user(
        user,
        auth_character,
        is_main=True,
        scopes=Character.get_esi_scopes(),
        disconnect_signals=disconnect_signals,
    )
    return user, character_ownership


def create_memberaudit_character(
    character_id: int, disconnect_signals: bool = True, **kwargs
) -> Character:
    """Create a memberaudit character from an existing auth character
    incl. user and making it the main.
    """
    _, character_ownership = create_user_from_evecharacter_with_access(
        character_id, disconnect_signals=disconnect_signals
    )
    return create_character(eve_character=character_ownership.character, **kwargs)


def add_auth_character_to_user(
    user: User, character_id: int, scopes=None, disconnect_signals=True
) -> CharacterOwnership:
    auth_character = EveCharacter.objects.get(character_id=character_id)
    if not scopes:
        scopes = Character.get_esi_scopes()

    return add_character_to_user(
        user,
        auth_character,
        is_main=False,
        scopes=scopes,
        disconnect_signals=disconnect_signals,
    )


def add_memberaudit_character_to_user(
    user: User, character_id: int, disconnect_signals: bool = True, **kwargs
) -> Character:
    character_ownership = add_auth_character_to_user(
        user, character_id, disconnect_signals=disconnect_signals
    )
    return create_character(eve_character=character_ownership.character, **kwargs)


def scope_names_set(token: Token) -> set:
    return set(token.scopes.values_list("name", flat=True))


def json_response_to_python_2(response: JsonResponse, data_key="data") -> Any:
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


def reset_celery_once_locks():
    """Reset celery once locks for given tasks."""
    r = get_redis_client()
    app_label = "memberaudit"
    if keys := r.keys(f":?:qo_{app_label}.*"):
        deleted_count = r.delete(*keys)
        logger.info("Removed %d stuck celery once keys", deleted_count)
    else:
        deleted_count = 0
