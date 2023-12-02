import datetime as dt
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import RequestFactory
from django.urls import reverse
from django.utils.timezone import now

from allianceauth.tests.auth_utils import AuthUtils
from app_utils.testing import NoSocketsTestCase

from memberaudit.models import SkillSet
from memberaudit.tests.testdata.factories import (
    create_fitting_text,
    create_skill_set,
    create_skill_set_group,
)
from memberaudit.tests.testdata.load_eveuniverse import load_eveuniverse
from memberaudit.views import admin

VIEWS_PATH = "memberaudit.views.admin"
MANAGERS_PATH = "memberaudit.managers.general"


@patch(VIEWS_PATH + ".messages", spec=True)
@patch(VIEWS_PATH + ".tasks", spec=True)
class TestCreateSkillSetFromFitting(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        load_eveuniverse()
        cls.superuser = User.objects.create_superuser("Superman")
        cls.fitting_text = create_fitting_text("fitting_tristan.txt")

    def test_should_open_page(self, mock_tasks, mock_messages):
        # given
        request = self.factory.get(
            reverse("memberaudit:admin_create_skillset_from_fitting")
        )
        request.user = self.superuser
        # when
        response = admin.admin_create_skillset_from_fitting(request)
        # then
        self.assertEqual(response.status_code, 200)

    def test_should_create_new_skillset(self, mock_tasks, mock_messages):
        # given
        request = self.factory.post(
            reverse("memberaudit:admin_create_skillset_from_fitting"),
            data={"fitting_text": self.fitting_text},
        )
        request.user = self.superuser
        my_now = now()
        # when
        with patch(MANAGERS_PATH + ".now", lambda: my_now):
            response = admin.admin_create_skillset_from_fitting(request)
        # then
        self.assertEqual(response.status_code, 302)
        self.assertTrue(mock_tasks.update_characters_skill_checks.delay.called)
        self.assertTrue(mock_messages.info.called)
        self.assertEqual(SkillSet.objects.count(), 1)
        obj: SkillSet = SkillSet.objects.first()
        self.assertEqual(obj.last_modified_at, my_now)
        self.assertEqual(obj.last_modified_by, self.superuser)

    def test_should_overwrite_existing_skillset(self, mock_tasks, mock_messages):
        # given
        other_user = AuthUtils.create_user("nobody")
        old_dt = now() - dt.timedelta(days=10)
        skill_set = create_skill_set(
            name="Tristan - Standard Kite (cap stable)",
            last_modified_by=other_user,
            last_modified_at=old_dt,
        )
        request = self.factory.post(
            reverse("memberaudit:admin_create_skillset_from_fitting"),
            data={"fitting_text": self.fitting_text, "can_overwrite": True},
        )
        request.user = self.superuser
        my_now = now()
        # when
        with patch(MANAGERS_PATH + ".now", lambda: my_now):
            response = admin.admin_create_skillset_from_fitting(request)
        # then
        self.assertEqual(response.status_code, 302)
        self.assertTrue(mock_tasks.update_characters_skill_checks.delay.called)
        self.assertTrue(mock_messages.info.called)
        skill_set.refresh_from_db()
        self.assertGreater(skill_set.skills.count(), 0)
        self.assertEqual(skill_set.last_modified_at, my_now)
        self.assertEqual(skill_set.last_modified_by, self.superuser)

    def test_should_create_new_skillset_and_assign_group(
        self, mock_tasks, mock_messages
    ):
        # given
        skill_set_group = create_skill_set_group()
        request = self.factory.post(
            reverse("memberaudit:admin_create_skillset_from_fitting"),
            data={
                "fitting_text": self.fitting_text,
                "skill_set_group": skill_set_group.id,
            },
        )
        request.user = self.superuser
        # when
        response = admin.admin_create_skillset_from_fitting(request)
        # then
        self.assertEqual(response.status_code, 302)
        self.assertTrue(mock_messages.info.called)
        self.assertTrue(mock_tasks.update_characters_skill_checks.delay.called)
        skill_set = SkillSet.objects.first()
        self.assertIn(skill_set, skill_set_group.skill_sets.all())

    def test_should_create_new_skillset_with_custom_name(
        self, mock_tasks, mock_messages
    ):
        # given
        skill_set = create_skill_set(name="Tristan - Standard Kite (cap stable)")
        request = self.factory.post(
            reverse("memberaudit:admin_create_skillset_from_fitting"),
            data={"fitting_text": self.fitting_text, "skill_set_name": "My-Name"},
        )
        request.user = self.superuser
        # when
        response = admin.admin_create_skillset_from_fitting(request)
        # then
        self.assertEqual(response.status_code, 302)
        self.assertTrue(mock_tasks.update_characters_skill_checks.delay.called)
        self.assertTrue(mock_messages.info.called)
        skill_set = SkillSet.objects.last()
        self.assertEqual(skill_set.name, "My-Name")


@patch(VIEWS_PATH + ".messages", spec=True)
@patch(VIEWS_PATH + ".tasks", spec=True)
class TestCreateSkillSetFromSkillPlan(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        load_eveuniverse()
        cls.superuser = User.objects.create_superuser("Superman")
        cls.skill_plan_text = """
        Caldari Core Systems 5
        Caldari Strategic Cruiser 3
        """

    def test_should_open_page(self, mock_tasks, mock_messages):
        # given
        request = self.factory.get(
            reverse("memberaudit:admin_create_skillset_from_skill_plan")
        )
        request.user = self.superuser
        # when
        response = admin.admin_create_skillset_from_skill_plan(request)
        # then
        self.assertEqual(response.status_code, 200)

    def test_should_create_new_skillset(self, mock_tasks, mock_messages):
        # given
        request = self.factory.post(
            reverse("memberaudit:admin_create_skillset_from_skill_plan"),
            data={
                "skill_set_name": "My Skill Set",
                "skill_plan_text": self.skill_plan_text,
            },
        )
        request.user = self.superuser
        my_now = now()
        # when
        with patch(MANAGERS_PATH + ".now", lambda: my_now):
            response = admin.admin_create_skillset_from_skill_plan(request)
        # then
        self.assertEqual(response.status_code, 302)
        self.assertTrue(mock_tasks.update_characters_skill_checks.delay.called)
        self.assertTrue(mock_messages.info.called)
        self.assertEqual(SkillSet.objects.count(), 1)
        obj: SkillSet = SkillSet.objects.first()
        self.assertEqual(obj.last_modified_at, my_now)
        self.assertEqual(obj.last_modified_by, self.superuser)

    def test_should_overwrite_existing_skillset_when_requested(
        self, mock_tasks, mock_messages
    ):
        # given
        other_user = AuthUtils.create_user("nobody")
        old_dt = now() - dt.timedelta(days=10)
        skill_set = create_skill_set(
            name="My Skill Set", last_modified_by=other_user, last_modified_at=old_dt
        )
        request = self.factory.post(
            reverse("memberaudit:admin_create_skillset_from_skill_plan"),
            data={
                "skill_set_name": "My Skill Set",
                "skill_plan_text": self.skill_plan_text,
                "can_overwrite": True,
            },
        )
        request.user = self.superuser
        my_now = now()
        # when
        with patch(MANAGERS_PATH + ".now", lambda: my_now):
            response = admin.admin_create_skillset_from_skill_plan(request)
        # then
        self.assertEqual(response.status_code, 302)
        self.assertTrue(mock_tasks.update_characters_skill_checks.delay.called)
        self.assertTrue(mock_messages.info.called)
        skill_set.refresh_from_db()
        self.assertGreater(skill_set.skills.count(), 0)
        self.assertEqual(skill_set.last_modified_at, my_now)
        self.assertEqual(skill_set.last_modified_by, self.superuser)

    def test_should_create_new_skillset_and_assign_group(
        self, mock_tasks, mock_messages
    ):
        # given
        skill_set_group = create_skill_set_group()
        request = self.factory.post(
            reverse("memberaudit:admin_create_skillset_from_skill_plan"),
            data={
                "skill_set_name": "My Skill Set",
                "skill_plan_text": self.skill_plan_text,
                "skill_set_group": skill_set_group.id,
            },
        )
        request.user = self.superuser
        # when
        response = admin.admin_create_skillset_from_skill_plan(request)
        # then
        self.assertEqual(response.status_code, 302)
        self.assertTrue(mock_messages.info.called)
        self.assertTrue(mock_tasks.update_characters_skill_checks.delay.called)
        skill_set = SkillSet.objects.first()
        self.assertIn(skill_set, skill_set_group.skill_sets.all())
