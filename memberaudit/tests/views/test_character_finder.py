from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase
from django.urls import reverse

from allianceauth.eveonline.models import EveCharacter
from app_utils.testing import create_user_from_evecharacter, json_response_to_python

from memberaudit.tests.testdata.factories import create_character
from memberaudit.tests.testdata.load_entities import load_entities
from memberaudit.tests.testdata.load_eveuniverse import load_eveuniverse
from memberaudit.tests.testdata.load_locations import load_locations
from memberaudit.tests.utils import (
    add_auth_character_to_user,
    add_memberaudit_character_to_user,
    create_memberaudit_character,
    json_response_to_python_2,
)
from memberaudit.views.character_finder import (
    CharacterFinderListJson,
    character_finder,
    character_finder_list_fdd_data,
)

MODULE_PATH = "memberaudit.views.character_finder"


class TestCharacterFinderViews(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        load_eveuniverse()
        load_entities()
        load_locations()
        cls.user, _ = create_user_from_evecharacter(
            1001,
            permissions=[
                "memberaudit.basic_access",
                "memberaudit.finder_access",
                "memberaudit.view_everything",
            ],
        )

    def test_can_open_character_finder_view(self):
        # given
        request = self.factory.get(reverse("memberaudit:character_finder"))
        request.user = self.user
        # when
        response = character_finder(request)
        # then
        self.assertEqual(response.status_code, 200)

    def test_should_return_all_existing_characters_for_list(self):
        # given
        add_memberaudit_character_to_user(self.user, 1001)
        add_memberaudit_character_to_user(self.user, 1002)
        add_auth_character_to_user(self.user, 1003)
        user_wo_main, _ = create_user_from_evecharacter(
            1101, permissions=["memberaudit.basic_access"]
        )
        user_wo_main.profile.main_character = None
        user_wo_main.profile.save()
        # orphaned character, i.e. without a user
        create_character(EveCharacter.objects.get(character_id=1121))
        request = self.factory.get(reverse("memberaudit:character_finder_data"))
        request.user = self.user
        # when
        response = CharacterFinderListJson.as_view()(request)
        # then
        self.assertEqual(response.status_code, 200)
        data = json_response_to_python_2(response)
        self.assertSetEqual({x[12] for x in data}, {1001, 1002, 1003, 1101, 1121})

    def test_should_raise_permission_denied(self):
        # given
        user, _ = create_user_from_evecharacter(
            1002,
            permissions=["memberaudit.basic_access"],
        )
        request = self.factory.get(reverse("memberaudit:character_finder_data"))
        request.user = user
        # when
        with self.assertRaises(PermissionDenied):
            CharacterFinderListJson.as_view()(request)

    def test_should_include_shared_character(self):
        # given
        user, _ = create_user_from_evecharacter(
            1002,
            permissions=[
                "memberaudit.basic_access",
                "memberaudit.finder_access",
                "memberaudit.view_shared_characters",
            ],
        )
        character_1101 = create_memberaudit_character(1101)
        character_1101.is_shared = True
        character_1101.save()
        request = self.factory.get(reverse("memberaudit:character_finder_data"))
        request.user = user
        # when
        response = CharacterFinderListJson.as_view()(request)
        # then
        self.assertEqual(response.status_code, 200)
        data = json_response_to_python_2(response)
        self.assertSetEqual({x[12] for x in data}, {1002, 1101})

    def test_should_not_include_shared_character(self):
        # given
        user, _ = create_user_from_evecharacter(
            1002,
            permissions=["memberaudit.basic_access", "memberaudit.finder_access"],
        )
        character_1101 = create_memberaudit_character(1101)
        character_1101.is_shared = True
        character_1101.save()
        request = self.factory.get(reverse("memberaudit:character_finder_data"))
        request.user = user
        # when
        response = CharacterFinderListJson.as_view()(request)
        # then
        self.assertEqual(response.status_code, 200)
        data = json_response_to_python_2(response)
        self.assertSetEqual({x[12] for x in data}, {1002})

    def test_should_not_include_orphaned_character(self):
        # given
        user, _ = create_user_from_evecharacter(
            1002,
            permissions=["memberaudit.basic_access", "memberaudit.finder_access"],
        )
        create_character(EveCharacter.objects.get(character_id=1121))
        request = self.factory.get(reverse("memberaudit:character_finder_data"))
        request.user = user
        # when
        response = CharacterFinderListJson.as_view()(request)
        # then
        self.assertEqual(response.status_code, 200)
        data = json_response_to_python_2(response)
        self.assertSetEqual({x[12] for x in data}, {1002})

    def test_should_return_all_data_for_character_finder_dff_list(self):
        # given
        add_memberaudit_character_to_user(self.user, 1001)
        add_memberaudit_character_to_user(self.user, 1101)
        add_auth_character_to_user(self.user, 1102)
        user_wo_main, _ = create_user_from_evecharacter(
            1103, permissions=["memberaudit.basic_access"]
        )
        user_wo_main.profile.main_character = None
        user_wo_main.profile.save()
        # orphaned character, i.e. without a user
        create_character(EveCharacter.objects.get(character_id=1121))
        request = self.factory.get(
            reverse("memberaudit:character_finder_list_fdd_data")
            + "?columns=alliance_name,corporation_name,main_alliance_name,main_corporation_name,main_str,unregistered_str,state_name"
        )
        request.user = self.user
        # when
        response = character_finder_list_fdd_data(request)
        # then
        self.assertEqual(response.status_code, 200)
        data = json_response_to_python(response)
        self.assertListEqual(
            data["alliance_name"], ["Hydra", "Lex Global Inc.", "Wayne Enterprises"]
        )
        self.assertListEqual(
            data["corporation_name"],
            [
                "Harley Quinn inc.",
                "Lexcorp",
                "Operations",
                "Suicide Squad",
                "Wayne Technologies",
            ],
        )
        self.assertListEqual(data["main_alliance_name"], ["Wayne Enterprises"])
        self.assertListEqual(data["main_corporation_name"], ["Wayne Technologies"])
        self.assertListEqual(data["main_str"], ["Bruce Wayne"])
        self.assertListEqual(data["unregistered_str"], ["no", "yes"])
        self.assertListEqual(data["state_name"], ["-", "Guest"])
