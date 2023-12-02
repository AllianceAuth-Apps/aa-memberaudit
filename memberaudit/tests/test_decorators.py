from unittest.mock import patch

from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from esi.errors import TokenError
from esi.models import Token

from allianceauth.tests.auth_utils import AuthUtils
from app_utils.esi import EsiDailyDowntime, EsiOffline, EsiStatus
from app_utils.testing import NoSocketsTestCase, generate_invalid_pk

from memberaudit.decorators import (
    fetch_character_if_allowed,
    fetch_token_for_character,
    when_esi_is_available,
)
from memberaudit.models import Character

from .testdata.factories import create_character_from_user
from .testdata.load_entities import load_entities
from .utils import create_user_from_evecharacter_with_access, scope_names_set

MODULE_PATH = "memberaudit.decorators"

DUMMY_URL = "http://www.example.com"


class TestFetchOwnerIfAllowed(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        load_entities()
        cls.user, _ = create_user_from_evecharacter_with_access(1001)

    def test_passthrough_when_fetch_owner_if_allowed(self):
        @fetch_character_if_allowed()
        def dummy(request, character_pk, character):
            self.assertEqual(character, my_character)
            self.assertIn("eve_character", character._state.fields_cache)
            return HttpResponse("ok")

        # given
        my_character = create_character_from_user(self.user)
        user = my_character.eve_character.character_ownership.user
        request = self.factory.get(DUMMY_URL)
        request.user = user
        # when
        response = dummy(request, my_character.pk)
        # then
        self.assertEqual(response.status_code, 200)

    def test_returns_404_when_owner_not_found(self):
        @fetch_character_if_allowed()
        def dummy(request, character_pk, character):
            self.assertTrue(False)

        # given
        my_character = create_character_from_user(self.user)
        user = my_character.eve_character.character_ownership.user
        request = self.factory.get(DUMMY_URL)
        request.user = user
        # when
        response = dummy(request, generate_invalid_pk(Character))
        # then
        self.assertEqual(response.status_code, 404)

    def test_returns_403_when_user_has_not_access(self):
        @fetch_character_if_allowed()
        def dummy(request, character_pk, character):
            self.assertTrue(False)

        # given
        my_character = create_character_from_user(self.user)
        user_2 = AuthUtils.create_user("Lex Luthor")
        request = self.factory.get(DUMMY_URL)
        request.user = user_2
        # when
        response = dummy(request, my_character.pk)
        # then
        self.assertEqual(response.status_code, 403)

    # TODO: create test case with CharacterDetails
    # def test_can_specify_list_for_select_related(self):
    #     @fetch_character_if_allowed("skills")
    #     def dummy(request, character_pk, character):
    #         self.assertEqual(character, self.character)
    #         self.assertIn("skills", character._state.fields_cache)
    #         return HttpResponse("ok")

    #     OwnerSkills.objects.create(character=self.character, total_sp=10000000)
    #     request = self.factory.get(DUMMY_URL)
    #     request.user = self.user
    #     dummy(request, self.character.pk)


class TestFetchToken(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities()
        cls.user, _ = create_user_from_evecharacter_with_access(1001)

    def setUp(self) -> None:
        self.character = create_character_from_user(self.user)

    def test_defaults(self):
        @fetch_token_for_character()
        def dummy(self, character, token):
            self.assertIsInstance(token, Token)
            self.assertSetEqual(scope_names_set(token), set(Character.get_esi_scopes()))

        dummy(self, self.character)

    def test_specified_scope(self):
        @fetch_token_for_character("esi-mail.read_mail.v1")
        def dummy(self, character, token):
            self.assertIsInstance(token, Token)
            self.assertIn("esi-mail.read_mail.v1", scope_names_set(token))

        dummy(self, self.character)

    def test_exceptions_if_not_found(self):
        @fetch_token_for_character("invalid_scope")
        def dummy(self, character, token):
            pass

        with self.assertRaises(TokenError):
            dummy(self, self.character)


@when_esi_is_available
def my_func():
    return "ok"


@patch(MODULE_PATH + ".IS_TESTING", False)
@patch(MODULE_PATH + ".fetch_esi_status")
class TestEsiIsAvailable(NoSocketsTestCase):
    def test_should_run_task_when_esi_is_available(self, mock_fetch_esi_status):
        # given
        mock_fetch_esi_status.return_value = EsiStatus(True, 99, 60)
        # when/then
        result = my_func()
        # then
        self.assertEqual(result, "ok")

    def test_should_raise_error_when_esi_is_offline(self, mock_fetch_esi_status):
        # given
        mock_fetch_esi_status.return_value = EsiStatus(False, 99, 60)
        # when/then
        with self.assertRaises(EsiOffline):
            my_func()

    def test_should_complete_task_early_when_downtime(self, mock_fetch_esi_status):
        # given
        mock_fetch_esi_status.side_effect = EsiDailyDowntime
        # when/then
        result = my_func()
        # then
        self.assertIsNone(result)
