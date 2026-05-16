from http import HTTPStatus

from django.core.exceptions import PermissionDenied
from django.test import RequestFactory
from django.urls import reverse

from allianceauth.eveonline.models import EveCharacter
from app_utils.testdata_factories import (
    EveAllianceInfoFactory,
    EveCharacterFactory,
    EveCorporationInfoFactory,
    UserMainFactory,
)
from app_utils.testing import (
    NoSocketsTestCase,
    add_character_to_user,
    json_response_to_python,
)

from memberaudit.tests.testdata.factories_2 import (
    CharacterFactory,
    CharacterOrphanFactory,
)
from memberaudit.tests.utils import json_response_to_python_2
from memberaudit.views.character_finder import (
    CharacterFinderListJson,
    character_finder,
    character_finder_list_fdd_data,
)

MODULE_PATH = "memberaudit.views.character_finder"


class TestCharacterFinderViews(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()

    def test_can_open_character_finder_view(self):
        # given
        user = UserMainFactory(
            permissions__=[
                "memberaudit.basic_access",
                "memberaudit.finder_access",
                "memberaudit.view_everything",
            ]
        )
        request = self.factory.get(reverse("memberaudit:character_finder"))
        request.user = user

        # when
        response = character_finder(request)

        # then
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_should_return_all_registered_and_unregistered_characters(self):
        # given
        user = UserMainFactory(
            permissions__=[
                "memberaudit.basic_access",
                "memberaudit.finder_access",
                "memberaudit.view_everything",
            ],
        )
        own_registered = CharacterFactory(user=user)
        foreign_registered = CharacterFactory()
        orphan = CharacterOrphanFactory()
        own_unregistered = EveCharacterFactory()
        add_character_to_user(user, own_unregistered)
        user_2 = UserMainFactory(
            permissions__=["memberaudit.basic_access"],
        )
        foreign_unregistered: EveCharacter = user_2.profile.main_character
        UserMainFactory()  # not shown because user has not access

        request = self.factory.get(reverse("memberaudit:character_finder_data"))
        request.user = user

        # when
        response = CharacterFinderListJson.as_view()(request)

        # then
        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = json_response_to_python_2(response)
        got = {x[12] for x in data}
        want = {
            own_registered.character_id,
            foreign_registered.character_id,
            orphan.character_id,
            own_unregistered.character_id,
            foreign_unregistered.character_id,
        }
        self.assertSetEqual(got, want)

    def test_should_raise_error_when_user_is_missing_required_permission(self):
        # given
        user = UserMainFactory(permissions__=["memberaudit.basic_access"])
        request = self.factory.get(reverse("memberaudit:character_finder_data"))
        request.user = user

        # when/then
        with self.assertRaises(PermissionDenied):
            CharacterFinderListJson.as_view()(request)

    def test_should_include_shared_character_when_user_has_permission(self):
        # given
        user = UserMainFactory(
            permissions__=[
                "memberaudit.basic_access",
                "memberaudit.finder_access",
                "memberaudit.view_shared_characters",
            ],
        )
        own_registered = CharacterFactory(user=user)
        character_shared = CharacterFactory(is_shared=True)
        request = self.factory.get(reverse("memberaudit:character_finder_data"))
        request.user = user

        # when
        response = CharacterFinderListJson.as_view()(request)

        # then
        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = json_response_to_python_2(response)
        got = {x[12] for x in data}
        want = {own_registered.character_id, character_shared.character_id}
        self.assertSetEqual(got, want)

    def test_should_not_include_shared_character_when_user_is_missing_permission(self):
        # given
        user = UserMainFactory(
            permissions__=[
                "memberaudit.basic_access",
                "memberaudit.finder_access",
            ],
        )
        own_registered = CharacterFactory(user=user)
        CharacterFactory(is_shared=True)  # not included
        request = self.factory.get(reverse("memberaudit:character_finder_data"))
        request.user = user

        # when
        response = CharacterFinderListJson.as_view()(request)

        # then
        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = json_response_to_python_2(response)
        got = {x[12] for x in data}
        want = {own_registered.character_id}
        self.assertSetEqual(got, want)

    def test_should_not_include_orphaned_character(self):
        # given
        user = UserMainFactory(
            permissions__=[
                "memberaudit.basic_access",
                "memberaudit.finder_access",
            ],
        )
        own_registered = CharacterFactory(user=user)
        CharacterOrphanFactory()
        request = self.factory.get(reverse("memberaudit:character_finder_data"))
        request.user = user

        # when
        response = CharacterFinderListJson.as_view()(request)

        # then
        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = json_response_to_python_2(response)
        got = {x[12] for x in data}
        want = {own_registered.character_id}
        self.assertSetEqual(got, want)


class TestCharacterFinderViews_FddData(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()

    def test_should_return_all_data_for_character_finder_dff_list(self):
        # given
        alliance = EveAllianceInfoFactory(alliance_name="Wayne Enterprises")
        corporation_1 = EveCorporationInfoFactory(
            corporation_name="Wayne Technologies", alliance=alliance
        )
        ec_1 = EveCharacterFactory(
            character_name="Bruce Wayne", corporation=corporation_1
        )
        user_1 = UserMainFactory(
            permissions__=[
                "memberaudit.basic_access",
                "memberaudit.finder_access",
                "memberaudit.view_everything",
            ],
            main_character__character=ec_1,
        )
        CharacterFactory(user=user_1)
        corporation_2 = EveCorporationInfoFactory(
            corporation_name="Wayne Foods", alliance=alliance
        )
        ec_2 = EveCharacterFactory(
            character_name="Clark Kent", corporation=corporation_2
        )
        UserMainFactory(
            permissions__=["memberaudit.basic_access"], main_character__character=ec_2
        )

        request = self.factory.get(
            reverse("memberaudit:character_finder_list_fdd_data")
            + "?columns=alliance_name,corporation_name,main_alliance_name,main_corporation_name,main_str,unregistered_str,state_name"
        )
        request.user = user_1

        # when
        response = character_finder_list_fdd_data(request)

        # then
        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = json_response_to_python(response)
        self.assertListEqual(data["alliance_name"], ["Wayne Enterprises"])
        self.assertListEqual(
            data["corporation_name"], ["Wayne Foods", "Wayne Technologies"]
        )
        self.assertListEqual(data["main_alliance_name"], ["Wayne Enterprises"])
        self.assertListEqual(
            data["main_corporation_name"], ["Wayne Foods", "Wayne Technologies"]
        )
        self.assertListEqual(data["main_str"], ["Bruce Wayne", "Clark Kent"])
        self.assertListEqual(data["unregistered_str"], ["no", "yes"])
        self.assertListEqual(data["state_name"], ["Guest"])
