from http import HTTPStatus

import pook

from django.test import override_settings

from app_utils.testdata_factories import UserFactory
from app_utils.testing import NoSocketsTestCase

from memberaudit.models import Character, SkillSet
from memberaudit.tests.testdata.factories_2 import (
    CharacterFactory,
    LocationStationFactory,
    SkillSetFactory,
    make_esi_url,
)
from memberaudit.tests.utils import TestCaseWithClearCache


@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
class TestAdminSite(NoSocketsTestCase):
    def test_should_delete_selected_characters(self):
        # given 2 characters
        character_1 = CharacterFactory()
        character_2 = CharacterFactory()
        character_3 = CharacterFactory()
        user = UserFactory(is_staff=True, is_superuser=True)
        self.client.force_login(user)

        # when selected 2 characters for deletion
        response = self.client.post(
            "/admin/memberaudit/character/",
            data={
                "action": "delete_objects",
                "select_across": 0,
                "index": 0,
                "_selected_action": [character_1.pk, character_2.pk],
            },
        )

        # then user is asked to confirm the 2 selected characters
        self.assertEqual(response.status_code, 200)
        text = response.content.decode("utf-8")
        self.assertIn(str(character_1), text)
        self.assertIn(str(character_2), text)
        self.assertNotIn(str(character_3), text)

        # when user clicked on confirm
        response = self.client.post(
            "/admin/memberaudit/character/",
            data={
                "action": "delete_objects",
                "apply": "Delete",
                "_selected_action": [character_1.pk, character_2.pk],
            },
        )

        # then the selected characters are deleted, but the other character remains
        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response.url, "/admin/memberaudit/character/")
        self.assertFalse(
            Character.objects.filter(pk__in=[character_1.pk, character_2.pk]).exists()
        )
        self.assertTrue(Character.objects.filter(pk=character_3.pk).exists())

    def test_should_delete_selected_skill_sets(self):
        # given 3 objects
        obj_1 = SkillSetFactory()
        obj_2 = SkillSetFactory()
        obj_3 = SkillSetFactory()
        user = UserFactory(is_staff=True, is_superuser=True)
        self.client.force_login(user)

        # when user selects 2 for deletion
        response = self.client.post(
            "/admin/memberaudit/skillset/",
            data={
                "action": "delete_objects",
                "apply": "Delete",
                "_selected_action": [obj_1.pk, obj_2.pk],
            },
        )

        # then the selected objects are deleted, but the other object remains
        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response.url, "/admin/memberaudit/skillset/")
        self.assertFalse(SkillSet.objects.filter(pk__in=[obj_1.pk, obj_2.pk]).exists())
        self.assertTrue(SkillSet.objects.filter(pk=obj_3.pk).exists())


@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
class TestAdminSite_2(TestCaseWithClearCache):
    @pook.on
    def test_should_update_location_for_characters(self):
        # given
        character = CharacterFactory()
        location = LocationStationFactory()
        pook.get(
            make_esi_url(f"characters/{character.character_id}/location"),
            reply=HTTPStatus.OK,
            response_json={
                "solar_system_id": location.eve_solar_system.id,
                "station_id": location.id,
            },
        )
        user = UserFactory(is_staff=True, is_superuser=True)
        self.client.force_login(user)

        # when
        self.client.post(
            "/admin/memberaudit/character/",
            data={
                "action": "update_section_location",
                "_selected_action": [character.pk],
            },
        )

        # then
        self.assertEqual(character.location.location.name, location.name)
