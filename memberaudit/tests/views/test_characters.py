from unittest.mock import Mock, patch

from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from allianceauth.tests.auth_utils import AuthUtils
from app_utils.testing import create_user_from_evecharacter, generate_invalid_pk

from memberaudit.models import Character
from memberaudit.tests.testdata.factories import (
    create_character_from_user,
    create_compliance_group,
)
from memberaudit.tests.testdata.load_entities import load_entities
from memberaudit.tests.utils import (
    create_memberaudit_character,
    create_user_from_evecharacter_with_access,
)
from memberaudit.views.characters import (
    add_character,
    index,
    launcher,
    remove_character,
    share_character,
    unshare_character,
)

MODULE_PATH = "memberaudit.views.characters"


class TestCharacterViews(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        load_entities()
        cls.user, _ = create_user_from_evecharacter(
            1001, permissions=["memberaudit.basic_access", "memberaudit.reports_access"]
        )

    def test_can_open_index_view(self):
        request = self.factory.get(reverse("memberaudit:index"))
        request.user = self.user
        response = index(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("memberaudit:launcher"))

    def test_can_open_launcher_view_1(self):
        """user with main"""
        request = self.factory.get(reverse("memberaudit:launcher"))
        request.user = self.user
        response = launcher(request)
        self.assertEqual(response.status_code, 200)

    def test_can_open_launcher_view_2(self):
        """user without main"""
        user = AuthUtils.create_user("John Doe")
        user = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.basic_access", user
        )

        request = self.factory.get(reverse("memberaudit:launcher"))
        request.user = user
        response = launcher(request)
        self.assertEqual(response.status_code, 200)


@patch(MODULE_PATH + ".messages")
@patch(MODULE_PATH + ".tasks")
@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
class TestAddCharacter(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        load_entities()
        create_compliance_group()

    def _add_character(self, user, token):
        request = self.factory.get(reverse("memberaudit:add_character"))
        request.user = user
        request.token = token
        middleware = SessionMiddleware(Mock())
        middleware.process_request(request)
        orig_view = add_character.__wrapped__.__wrapped__.__wrapped__
        return orig_view(request, token)

    def test_should_add_character(self, mock_tasks, mock_messages):
        # given
        user, _ = create_user_from_evecharacter(
            1001,
            permissions=["memberaudit.basic_access"],
            scopes=Character.get_esi_scopes(),
        )
        token = user.token_set.get(character_id=1001)
        # when
        response = self._add_character(user, token)
        # then
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("memberaudit:launcher"))
        self.assertTrue(mock_tasks.update_character.apply_async.called)
        self.assertTrue(mock_tasks.update_compliance_groups_for_user.apply_async.called)
        self.assertTrue(mock_messages.success.called)
        self.assertTrue(
            Character.objects.filter(eve_character__character_id=1001).exists()
        )

    def test_should_reenable_disabled_character(self, mock_tasks, mock_messages):
        # given
        character_1001 = create_memberaudit_character(1001)
        character_1001.is_disabled = True
        character_1001.save()
        user = character_1001.character_ownership.user
        token = user.token_set.get(character_id=1001)
        # when
        response = self._add_character(user, token)
        # then
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("memberaudit:launcher"))
        self.assertTrue(mock_tasks.update_character.apply_async.called)
        self.assertTrue(mock_tasks.update_compliance_groups_for_user.apply_async.called)
        self.assertTrue(mock_messages.success.called)
        character_1001.refresh_from_db()
        self.assertFalse(character_1001.is_disabled)


@patch(MODULE_PATH + ".messages")
@patch(MODULE_PATH + ".tasks")
@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
class TestRemoveCharacter(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        load_entities()
        create_compliance_group()
        cls.user, _ = create_user_from_evecharacter_with_access(1001)

    def _remove_character(self, user, character_pk):
        request = self.factory.get(
            reverse("memberaudit:remove_character", args=[character_pk])
        )
        request.user = user
        return remove_character(request, character_pk)

    def test_should_remove_character_without_notification(
        self, mock_tasks, mock_messages
    ):
        # given
        character = create_character_from_user(self.user)
        user = character.eve_character.character_ownership.user
        auditor_character = create_memberaudit_character(1003)
        auditor = auditor_character.eve_character.character_ownership.user
        AuthUtils.add_permissions_to_user_by_name(
            (
                "memberaudit.notified_on_character_removal",
                "memberaudit.view_same_corporation",
            ),
            auditor,
        )
        # when
        response = self._remove_character(user, character.pk)
        # then
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("memberaudit:launcher"))
        self.assertFalse(Character.objects.filter(pk=character.pk).exists())
        self.assertTrue(mock_tasks.update_compliance_groups_for_user.apply_async.called)
        self.assertTrue(mock_messages.success.called)
        self.assertEqual(auditor.notification_set.count(), 0)

    def test_should_remove_character_with_notification(self, mock_tasks, mock_messages):
        # given
        character = create_character_from_user(self.user)
        user = character.eve_character.character_ownership.user
        AuthUtils.add_permission_to_user_by_name("memberaudit.share_characters", user)

        auditor_character = create_memberaudit_character(1002)
        auditor = auditor_character.eve_character.character_ownership.user
        AuthUtils.add_permissions_to_user_by_name(
            (
                "memberaudit.notified_on_character_removal",
                "memberaudit.view_same_corporation",
            ),
            auditor,
        )
        # when
        response = self._remove_character(user, character.pk)
        # then
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("memberaudit:launcher"))
        self.assertFalse(Character.objects.filter(pk=character.pk).exists())
        self.assertTrue(mock_tasks.update_compliance_groups_for_user.apply_async.called)
        self.assertTrue(mock_messages.success.called)

        expected_removal_notification_title = (
            "Member Audit: Character has been removed!"
        )
        expected_removal_notification_message = (
            "Bruce_Wayne has removed character Bruce Wayne"
        )
        latest_auditor_notification = auditor.notification_set.order_by("-pk")[0]
        self.assertEqual(
            latest_auditor_notification.title, expected_removal_notification_title
        )
        self.assertEqual(
            latest_auditor_notification.message, expected_removal_notification_message
        )
        self.assertEqual(latest_auditor_notification.level, "info")

    def test_should_not_remove_character_from_another_user(
        self, mock_tasks, mock_messages
    ):
        # given
        character_1001 = create_character_from_user(self.user)
        user_1002, _ = create_user_from_evecharacter_with_access(1002)
        # when
        response = self._remove_character(user_1002, character_1001.pk)
        # then
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Character.objects.filter(pk=character_1001.pk).exists())
        self.assertFalse(
            mock_tasks.update_compliance_groups_for_user.apply_async.called
        )
        self.assertFalse(mock_messages.success.called)

    def test_should_respond_with_not_found_for_invalid_characters(
        self, mock_tasks, mock_messages
    ):
        # given
        character = create_character_from_user(self.user)
        user = character.eve_character.character_ownership.user
        invalid_character_pk = generate_invalid_pk(Character)
        # when
        response = self._remove_character(user, invalid_character_pk)
        # then
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Character.objects.filter(pk=character.pk).exists())
        self.assertFalse(
            mock_tasks.update_compliance_groups_for_user.apply_async.called
        )
        self.assertFalse(mock_messages.success.called)


class TestShareCharacter(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        load_entities()

    def setUp(self) -> None:
        self.character_1001 = create_memberaudit_character(1001)
        self.user_1001 = self.character_1001.eve_character.character_ownership.user
        self.user_1001 = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.share_characters", self.user_1001
        )

        self.character_1002 = create_memberaudit_character(1002)
        self.user_1002 = self.character_1002.eve_character.character_ownership.user
        self.user_1002 = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.share_characters", self.user_1002
        )

    def test_normal(self):
        request = self.factory.get(
            reverse("memberaudit:share_character", args=[self.character_1001.pk])
        )
        request.user = self.user_1001
        response = share_character(request, self.character_1001.pk)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("memberaudit:launcher"))
        self.assertTrue(Character.objects.get(pk=self.character_1001.pk).is_shared)

    def test_no_permission_1(self):
        """
        when user does not have any permissions
        then redirect to login
        """
        user = AuthUtils.create_user("John Doe")
        request = self.factory.get(
            reverse("memberaudit:share_character", args=[self.character_1001.pk])
        )
        request.user = user
        response = share_character(request, self.character_1001.pk)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_no_permission_2(self):
        """
        when user does has basic_access only
        then redirect to login
        """
        user = AuthUtils.create_user("John Doe")
        user = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.basic_access", user
        )
        request = self.factory.get(
            reverse("memberaudit:share_character", args=[self.character_1001.pk])
        )
        request.user = user
        response = share_character(request, self.character_1001.pk)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_no_permission_3(self):
        request = self.factory.get(
            reverse("memberaudit:share_character", args=[self.character_1001.pk])
        )
        request.user = self.user_1002
        response = share_character(request, self.character_1001.pk)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Character.objects.get(pk=self.character_1001.pk).is_shared)

    def test_not_found(self):
        invalid_character_pk = generate_invalid_pk(Character)
        request = self.factory.get(
            reverse("memberaudit:share_character", args=[invalid_character_pk])
        )
        request.user = self.user_1001
        response = share_character(request, invalid_character_pk)
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Character.objects.get(pk=self.character_1001.pk).is_shared)


class TestUnshareCharacter(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        load_entities()

    def setUp(self) -> None:
        self.character_1001 = create_memberaudit_character(1001)
        self.character_1001.is_shared = True
        self.character_1001.save()
        self.user_1001 = self.character_1001.eve_character.character_ownership.user

        self.character_1002 = create_memberaudit_character(1002)
        self.user_1002 = self.character_1002.eve_character.character_ownership.user

    def test_normal(self):
        request = self.factory.get(
            reverse("memberaudit:unshare_character", args=[self.character_1001.pk])
        )
        request.user = self.user_1001
        response = unshare_character(request, self.character_1001.pk)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("memberaudit:launcher"))
        self.assertFalse(Character.objects.get(pk=self.character_1001.pk).is_shared)

    def test_no_permission(self):
        request = self.factory.get(
            reverse("memberaudit:unshare_character", args=[self.character_1001.pk])
        )
        request.user = self.user_1002
        response = unshare_character(request, self.character_1001.pk)
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Character.objects.get(pk=self.character_1001.pk).is_shared)

    def test_not_found(self):
        invalid_character_pk = generate_invalid_pk(Character)
        request = self.factory.get(
            reverse("memberaudit:unshare_character", args=[invalid_character_pk])
        )
        request.user = self.user_1001
        response = unshare_character(request, invalid_character_pk)
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Character.objects.get(pk=self.character_1001.pk).is_shared)
