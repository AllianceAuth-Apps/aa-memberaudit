import datetime as dt
from unittest.mock import Mock, patch

from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils.timezone import now
from eveuniverse.models import EveType

from allianceauth.tests.auth_utils import AuthUtils
from app_utils.testing import create_user_from_evecharacter, generate_invalid_pk

from memberaudit.models import Character
from memberaudit.tests.testdata.factories import (
    create_character_from_user,
    create_character_mining_ledger_entry,
    create_character_skillpoints,
    create_character_wallet_balance,
    create_character_wallet_journal_entry,
    create_compliance_group,
    create_eve_market_price,
)
from memberaudit.tests.testdata.load_entities import load_entities
from memberaudit.tests.testdata.load_eveuniverse import load_eveuniverse
from memberaudit.tests.utils import (
    add_auth_character_to_user,
    add_memberaudit_character_to_user,
    create_memberaudit_character,
    create_user_from_evecharacter_with_access,
)
from memberaudit.views.launcher import (
    _dashboard_panel,
    add_character,
    index,
    launcher,
    player_count_data,
    remove_character,
    share_character,
    unshare_character,
)

MODULE_PATH = "memberaudit.views.launcher"


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


class TestDashboardPanel(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        cls.factory = RequestFactory()

    def test_user_with_complete_data(self):
        # given
        character_1001 = create_memberaudit_character(1001)
        user = character_1001.user
        character_1002 = add_memberaudit_character_to_user(user, 1002)
        add_auth_character_to_user(user, 1003)

        create_character_skillpoints(character_1001, total=1_000)
        create_character_skillpoints(character_1002, total=3_000)

        create_character_wallet_balance(character_1001, total=10_000)
        create_character_wallet_balance(character_1002, total=5_000)

        today = now().date()
        ore_type = EveType.objects.get(name="Veldspar")
        create_eve_market_price(eve_type=ore_type, average_price=100)
        create_character_mining_ledger_entry(
            character_1001,
            eve_type=ore_type,
            quantity=4,
            date=today - dt.timedelta(days=1),
        )
        create_character_mining_ledger_entry(
            character_1001, eve_type=ore_type, quantity=3, date=today
        )
        create_character_mining_ledger_entry(
            character_1002, eve_type=ore_type, quantity=2, date=today
        )
        not_this_month = now() - dt.timedelta(days=40)
        create_character_mining_ledger_entry(
            character_1002, eve_type=ore_type, quantity=2, date=not_this_month
        )

        create_character_wallet_journal_entry(
            character_1001, amount=4_000, ref_type="bounty_prizes", date=now()
        )
        create_character_wallet_journal_entry(
            character_1001, amount=3_000, ref_type="bounty_prizes", date=now()
        )
        create_character_wallet_journal_entry(
            character_1002, amount=2_000, ref_type="bounty_prizes", date=now()
        )
        not_this_month = now() - dt.timedelta(days=40)
        create_character_wallet_journal_entry(
            character_1002,
            amount=2_000,
            ref_type="bounty_prizes",
            date=not_this_month,
        )

        request = self.factory.get("/")
        request.user = user

        # when
        context = _dashboard_panel(request)

        # then
        self.assertEqual(context["registered_count"], 2)
        self.assertEqual(context["known_characters_count"], 3)
        self.assertEqual(context["registered_percent"], 67)
        self.assertEqual(context["total_wallet_isk"], 15_000)
        self.assertEqual(context["total_ratted_isk"], 9_000)
        self.assertEqual(context["total_mined_isk"], 900)
        self.assertEqual(context["total_character_skillpoints"], 4_000)

    def test_user_with_memberaudit_character_and_no_data(self):
        # given
        character_1001 = create_memberaudit_character(1001)
        user = character_1001.user
        request = self.factory.get("/")
        request.user = user

        # when
        context = _dashboard_panel(request)

        # then
        self.assertEqual(context["registered_count"], 1)
        self.assertEqual(context["known_characters_count"], 1)
        self.assertEqual(context["registered_percent"], 100)
        self.assertIsNone(context["total_wallet_isk"])
        self.assertEqual(context["total_ratted_isk"], 0)
        self.assertEqual(context["total_mined_isk"], 0)
        self.assertIsNone(context["total_character_skillpoints"])

    def test_user_with_memberaudit_character_and_no_current_mining_and_ratting_data(
        self,
    ):
        # given
        character_1001 = create_memberaudit_character(1001)
        user = character_1001.user
        not_this_month = now().date() - dt.timedelta(days=40)
        create_character_mining_ledger_entry(character_1001, date=not_this_month)
        create_character_wallet_journal_entry(
            character_1001, ref_type="bounty_prizes", date=not_this_month
        )

        request = self.factory.get("/")
        request.user = user

        # when
        context = _dashboard_panel(request)

        # then
        self.assertEqual(context["total_ratted_isk"], 0)
        self.assertEqual(context["total_mined_isk"], 0)


@patch(MODULE_PATH + ".eve_status.player_count", spec=True)
class TestPlayerCountData(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        load_entities()
        character = create_memberaudit_character(1001)
        cls.user = character.user

    def test_should_return_player_count(self, mock_player_count):
        # given
        mock_player_count.return_value = 42
        request = self.factory.get("/")
        request.user = self.user

        # when
        response = player_count_data(request)

        # then
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content.decode("utf-8"), {"player_count": 42})
