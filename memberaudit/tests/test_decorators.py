from django.http import HttpResponse
from django.test import RequestFactory
from esi.errors import TokenError
from esi.models import Token

from app_utils.testdata_factories import UserMainFactory
from app_utils.testing import NoSocketsTestCase, generate_invalid_pk

from memberaudit.decorators import fetch_character_if_allowed, fetch_token_for_character
from memberaudit.models import Character
from memberaudit.tests.testdata.factories_2 import (
    CharacterFactory,
    UserMainBasicAccessFactory,
)
from memberaudit.tests.utils import scope_names_set

MODULE_PATH = "memberaudit.decorators"

DUMMY_URL = "http://www.example.com"


class TestFetchOwnerIfAllowed(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        cls.user = UserMainBasicAccessFactory()

    def test_passthrough_when_fetch_owner_if_allowed(self):
        @fetch_character_if_allowed()
        def dummy(request, character_pk, character):
            self.assertEqual(character, my_character)
            self.assertIn("eve_character", character._state.fields_cache)
            return HttpResponse("ok")

        # given
        my_character = CharacterFactory(user=self.user)
        request = self.factory.get(DUMMY_URL)
        request.user = self.user

        # when
        response = dummy(request, my_character.pk)

        # then
        self.assertEqual(response.status_code, 200)

    def test_returns_404_when_owner_not_found(self):
        @fetch_character_if_allowed()
        def dummy(request, character_pk, character):
            self.assertTrue(False)

        # given
        CharacterFactory(user=self.user)
        request = self.factory.get(DUMMY_URL)
        request.user = self.user

        # when
        response = dummy(request, generate_invalid_pk(Character))

        # then
        self.assertEqual(response.status_code, 404)

    def test_returns_403_when_user_has_not_access(self):
        @fetch_character_if_allowed()
        def dummy(request, character_pk, character):
            self.assertTrue(False)

        # given
        my_character = CharacterFactory(user=self.user)
        user = UserMainFactory()
        request = self.factory.get(DUMMY_URL)
        request.user = user

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


class TestFetchToken(NoSocketsTestCase):
    def test_defaults(self):
        @fetch_token_for_character()
        def dummy(self, character, token):
            self.assertIsInstance(token, Token)
            self.assertSetEqual(scope_names_set(token), set(Character.esi_scopes()))

        character = CharacterFactory()
        dummy(self, character)

    def test_specified_scope(self):
        @fetch_token_for_character("esi-mail.read_mail.v1")
        def dummy(self, character, token):
            self.assertIsInstance(token, Token)
            self.assertIn("esi-mail.read_mail.v1", scope_names_set(token))

        character = CharacterFactory()
        dummy(self, character)

    def test_exceptions_if_not_found(self):
        @fetch_token_for_character("invalid_scope")
        def dummy(self, character, token):
            pass

        character = CharacterFactory()
        with self.assertRaises(TokenError):
            dummy(self, character)
