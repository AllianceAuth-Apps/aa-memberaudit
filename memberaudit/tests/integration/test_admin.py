from unittest.mock import patch

from django.test import TestCase, override_settings

from app_utils.esi import EsiStatus
from app_utils.testdata_factories import UserFactory

from memberaudit.models import Character, SkillSet
from memberaudit.tests.testdata.esi_client_stub import esi_stub
from memberaudit.tests.testdata.factories import create_skill_set
from memberaudit.tests.testdata.load_entities import load_entities
from memberaudit.tests.testdata.load_eveuniverse import load_eveuniverse
from memberaudit.tests.utils import (
    create_memberaudit_character,
    reset_celery_once_locks,
)

MANAGERS_PATH = "memberaudit.managers"
MODELS_PATH = "memberaudit.models"
TASKS_PATH = "memberaudit.tasks"


@patch(
    TASKS_PATH + ".Character.objects.get_cached",
    lambda pk, timeout: Character.objects.get(pk=pk),
)
@patch(MANAGERS_PATH + ".general.fetch_esi_status", lambda: EsiStatus(True, 99, 60))
@patch(MANAGERS_PATH + ".character_sections_1.esi", esi_stub)
@patch(MANAGERS_PATH + ".character_sections_2.esi", esi_stub)
@patch(MANAGERS_PATH + ".character_sections_3.esi", esi_stub)
@patch(MANAGERS_PATH + ".general.esi", esi_stub)
@override_settings(
    CELERY_ALWAYS_EAGER=True,
    CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
    APP_UTILS_OBJECT_CACHE_DISABLED=True,
)
class TestAdminSite(TestCase):
    fixtures = ["disable_analytics.json"]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        cls.user = UserFactory(is_staff=True, is_superuser=True)
        reset_celery_once_locks()

    def test_should_delete_selected_characters(self):
        # given 2 characters
        character_1001 = create_memberaudit_character(1001)
        character_1002 = create_memberaudit_character(1002)
        character_1003 = create_memberaudit_character(1003)
        self.client.force_login(self.user)

        # when selected 2 characters for deletion
        response = self.client.post(
            "/admin/memberaudit/character/",
            data={
                "action": "delete_objects",
                "select_across": 0,
                "index": 0,
                "_selected_action": [character_1001.pk, character_1002.pk],
            },
        )

        # then user is asked to confirm the 2 selected characters
        self.assertEqual(response.status_code, 200)
        text = response.content.decode("utf-8")
        self.assertIn(str(character_1001), text)
        self.assertIn(str(character_1002), text)
        self.assertNotIn(str(character_1003), text)

        # when user clicked on confirm
        response = self.client.post(
            "/admin/memberaudit/character/",
            data={
                "action": "delete_objects",
                "apply": "Delete",
                "_selected_action": [character_1001.pk, character_1002.pk],
            },
        )

        # then the selected characters are deleted, but the other character remains
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/admin/memberaudit/character/")
        self.assertFalse(
            Character.objects.filter(
                pk__in=[character_1001.pk, character_1002.pk]
            ).exists()
        )
        self.assertTrue(Character.objects.filter(pk=character_1003.pk).exists())

    def test_should_delete_selected_skill_sets(self):
        # given 3 objects
        obj_1 = create_skill_set()
        obj_2 = create_skill_set()
        obj_3 = create_skill_set()
        self.client.force_login(self.user)

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
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/admin/memberaudit/skillset/")
        self.assertFalse(SkillSet.objects.filter(pk__in=[obj_1.pk, obj_2.pk]).exists())
        self.assertTrue(SkillSet.objects.filter(pk=obj_3.pk).exists())

    def test_should_update_location_for_characters(self):
        # given 2 characters
        character_1001 = create_memberaudit_character(1001)
        self.client.force_login(self.user)

        # when user starts action
        self.client.post(
            "/admin/memberaudit/character/",
            data={
                "action": "update_section_location",
                "_selected_action": [character_1001.pk],
            },
        )

        # then character is updated
        self.assertEqual(character_1001.location.location.eve_solar_system.name, "Jita")
