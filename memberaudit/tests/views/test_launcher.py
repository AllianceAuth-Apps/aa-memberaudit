import datetime as dt
from http import HTTPStatus
from unittest.mock import Mock, patch

from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, override_settings
from django.urls import reverse
from django.utils.timezone import now
from eveuniverse.tests.testdata.factories_2 import EveMarketPriceFactory, EveTypeFactory

from app_utils.testdata_factories import (
    EveCharacterFactory,
    UserFactory,
    UserMainFactory,
    add_character_to_user,
)
from app_utils.testing import NoSocketsTestCase, generate_invalid_pk

from memberaudit.core import player_count
from memberaudit.models import Character
from memberaudit.tests.testdata.factories_2 import (
    CharacterFactory,
    CharacterMiningLedgerEntryFactory,
    CharacterSkillpointsFactory,
    CharacterWalletBalanceFactory,
    CharacterWalletJournalEntryFactory,
    ComplianceGroupFactory,
    UserMainBasicAccessFactory,
)
from memberaudit.views.launcher import (
    _dashboard_panel,
    add_character,
    index,
    launcher,
    player_count_data,
)

MODULE_PATH = "memberaudit.views.launcher"


class TestCharacterViews(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()

    def test_can_open_index_view(self):
        user = UserMainFactory(permissions__=["memberaudit.basic_access"])
        request = self.factory.get(reverse("memberaudit:index"))
        request.user = user
        response = index(request)
        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response.url, reverse("memberaudit:launcher"))

    def test_can_open_launcher_view_1(self):
        user = UserMainFactory(permissions__=["memberaudit.basic_access"])
        request = self.factory.get(reverse("memberaudit:launcher"))
        request.user = user
        response = launcher(request)
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_can_open_launcher_view_2(self):
        user = UserFactory(permissions__=["memberaudit.basic_access"])  # no main
        request = self.factory.get(reverse("memberaudit:launcher"))
        request.user = user
        response = launcher(request)
        self.assertEqual(response.status_code, HTTPStatus.OK)


@patch(MODULE_PATH + ".messages")
@patch(MODULE_PATH + ".tasks")
@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
class TestAddCharacter(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        ComplianceGroupFactory()

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
        user = UserMainBasicAccessFactory()
        token = user.token_set.first()
        # when
        response = self._add_character(user, token)
        # then
        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response.url, reverse("memberaudit:launcher"))
        self.assertTrue(mock_tasks.update_character.apply_async.called)
        self.assertTrue(mock_tasks.update_compliance_groups_for_user.apply_async.called)
        self.assertTrue(mock_messages.success.called)
        self.assertTrue(
            Character.objects.filter(eve_character=user.profile.main_character).exists()
        )

    def test_should_reenable_disabled_character(self, mock_tasks, mock_messages):
        # given
        user = UserMainBasicAccessFactory()
        character = CharacterFactory(user=user, is_disabled=True)
        token = user.token_set.first()
        # when
        response = self._add_character(user, token)
        # then
        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response.url, reverse("memberaudit:launcher"))
        self.assertTrue(mock_tasks.update_character.apply_async.called)
        self.assertTrue(mock_tasks.update_compliance_groups_for_user.apply_async.called)
        self.assertTrue(mock_messages.success.called)
        character.refresh_from_db()
        self.assertFalse(character.is_disabled)


@patch(MODULE_PATH + ".messages")
@patch(MODULE_PATH + ".tasks")
class TestRemoveCharacter_(NoSocketsTestCase):
    def test_should_remove_own_character_and_notify_user(
        self, mock_tasks, mock_messages
    ):
        # given
        user = UserMainFactory(permissions__=["memberaudit.basic_access"])
        character = CharacterFactory(user=user)
        self.client.force_login(user)

        # when
        response = self.client.post(
            reverse("memberaudit:remove_character", args=[character.pk])
        )

        # then
        self.assertRedirects(response, reverse("memberaudit:launcher"))
        self.assertFalse(Character.objects.filter(pk=character.pk).exists())
        self.assertTrue(mock_messages.success.called)

    def test_should_remove_own_character_and_update_compliance_groups(
        self, mock_tasks, mock_messages
    ):
        # given
        ComplianceGroupFactory()
        user = UserMainFactory(permissions__=["memberaudit.basic_access"])
        character = CharacterFactory(user=user)
        self.client.force_login(user)

        # when
        response = self.client.post(
            reverse("memberaudit:remove_character", args=[character.pk])
        )

        # then
        self.assertRedirects(response, reverse("memberaudit:launcher"))
        self.assertFalse(Character.objects.filter(pk=character.pk).exists())
        self.assertTrue(mock_tasks.update_compliance_groups_for_user.apply_async.called)

    def test_should_remove_own_character_and_not_notify_auditors(
        self, mock_tasks, mock_messages
    ):
        # given
        user = UserMainFactory(permissions__=["memberaudit.basic_access"])
        character = CharacterFactory(user=user)
        auditor = UserMainFactory(
            permissions__=[
                "memberaudit.basic_access",
                "memberaudit.notified_on_character_removal",
                "memberaudit.view_same_corporation",
            ]
        )
        self.client.force_login(user)

        # when
        response = self.client.post(
            reverse("memberaudit:remove_character", args=[character.pk])
        )

        # then
        self.assertRedirects(response, reverse("memberaudit:launcher"))
        self.assertFalse(Character.objects.filter(pk=character.pk).exists())
        self.assertEqual(auditor.notification_set.count(), 0)

    def test_should_remove_own_character_and_notify_auditors(
        self, mock_tasks, mock_messages
    ):
        # given
        user = UserMainFactory(permissions__=["memberaudit.basic_access"])
        character = CharacterFactory(user=user)
        auditor = UserMainFactory(
            permissions__=[
                "memberaudit.basic_access",
                "memberaudit.notified_on_character_removal",
                "memberaudit.view_everything",
            ]
        )
        self.client.force_login(user)

        # when
        response = self.client.post(
            reverse("memberaudit:remove_character", args=[character.pk])
        )

        # then
        self.assertRedirects(response, reverse("memberaudit:launcher"))
        self.assertFalse(Character.objects.filter(pk=character.pk).exists())

        expected_removal_notification_title = (
            "Member Audit: Character has been removed!"
        )
        expected_removal_notification_message = (
            f"{user.username} has removed character {character.name}"
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
        user = UserMainBasicAccessFactory()
        character = CharacterFactory()
        self.client.force_login(user)

        # when
        response = self.client.post(
            reverse("memberaudit:remove_character", args=[character.pk])
        )

        # then
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.assertTrue(Character.objects.filter(pk=character.pk).exists())
        self.assertFalse(mock_messages.success.called)

    def test_should_respond_with_not_found_for_invalid_characters(
        self, mock_tasks, mock_messages
    ):
        # given
        user = UserMainBasicAccessFactory()
        invalid_character_pk = generate_invalid_pk(Character)
        self.client.force_login(user)

        # when
        response = self.client.post(
            reverse("memberaudit:remove_character", args=[invalid_character_pk])
        )

        # then
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)
        self.assertFalse(mock_messages.success.called)


class TestShareCharacter(NoSocketsTestCase):
    def test_user_can_share_his_character_when_he_has_permission(self):
        # given
        user = UserMainFactory(
            permissions__=["memberaudit.basic_access", "memberaudit.share_characters"]
        )
        character = CharacterFactory(user=user)
        self.client.force_login(user)

        # when
        response = self.client.post(
            reverse("memberaudit:share_character", args=[character.pk])
        )

        # then
        self.assertRedirects(response, reverse("memberaudit:launcher"))
        character.refresh_from_db()
        self.assertTrue(character.is_shared)
        self.assertTrue(character.shared_at)

    def test_user_can_not_share_his_character_when_not_has_permission(self):
        # given
        user = UserMainFactory(permissions__=["memberaudit.basic_access"])
        character = CharacterFactory(user=user)
        self.client.force_login(user)

        # when
        response = self.client.post(
            reverse("memberaudit:share_character", args=[character.pk])
        )

        # then
        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertIn(reverse("login"), response.url)
        character.refresh_from_db()
        self.assertFalse(character.is_shared)

    def test_should_raise_permission_error_when_user_tries_to_share_foreign_character(
        self,
    ):
        # given
        user = UserMainFactory(
            permissions__=["memberaudit.basic_access", "memberaudit.share_characters"]
        )
        character = CharacterFactory()
        self.client.force_login(user)

        # when
        response = self.client.post(
            reverse("memberaudit:share_character", args=[character.pk])
        )

        # then
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        character.refresh_from_db()
        self.assertFalse(character.is_shared)

    def test_should_raise_404_when_character_not_found(self):
        # given
        user = UserMainFactory(
            permissions__=["memberaudit.basic_access", "memberaudit.share_characters"]
        )
        self.client.force_login(user)
        invalid_character_pk = generate_invalid_pk(Character)

        # when
        response = self.client.post(
            reverse("memberaudit:share_character", args=[invalid_character_pk])
        )

        # then
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)


class TestUnshareCharacter(NoSocketsTestCase):
    def test_user_can_unshare_his_character(self):
        # given
        user = UserMainFactory(permissions__=["memberaudit.basic_access"])
        character = CharacterFactory(user=user, is_shared=True, shared_at=now())
        self.client.force_login(user)

        # when
        response = self.client.post(
            reverse("memberaudit:unshare_character", args=[character.pk])
        )

        # then
        self.assertRedirects(response, reverse("memberaudit:launcher"))
        character.refresh_from_db()
        self.assertFalse(character.is_shared)
        self.assertIsNone(character.shared_at)

    def test_user_can_unshare_own_character_when_no_permission(self):
        # given
        user = UserMainFactory()
        character = CharacterFactory(user=user, is_shared=True)
        self.client.force_login(user)

        # when
        response = self.client.post(
            reverse("memberaudit:unshare_character", args=[character.pk])
        )

        # then
        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertIn(reverse("login"), response.url)
        character.refresh_from_db()
        self.assertTrue(character.is_shared)

    def test_should_raise_permission_error_when_user_tries_to_unshare_foreign_character(
        self,
    ):
        # given
        user = UserMainFactory(permissions__=["memberaudit.basic_access"])
        character = CharacterFactory()
        self.client.force_login(user)

        # when
        response = self.client.post(
            reverse("memberaudit:unshare_character", args=[character.pk])
        )

        # then
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        character.refresh_from_db()
        self.assertFalse(character.is_shared)

    def test_should_raise_404_when_character_not_found(self):
        # given
        user = UserMainFactory(permissions__=["memberaudit.basic_access"])
        self.client.force_login(user)
        invalid_character_pk = generate_invalid_pk(Character)

        # when
        response = self.client.post(
            reverse("memberaudit:unshare_character", args=[invalid_character_pk])
        )

        # then
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)


class TestDashboardPanel(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()

    def setUp(self) -> None:
        player_count.clear_cache()

    def test_user_with_complete_data(self):
        # given
        user = UserMainBasicAccessFactory()
        character_1 = CharacterFactory(user=user)
        character_2 = CharacterFactory(user=user, is_main=False)
        add_character_to_user(user=user, character=EveCharacterFactory())

        CharacterSkillpointsFactory(character=character_1, total=1_000)
        CharacterSkillpointsFactory(character=character_2, total=3_000)

        CharacterWalletBalanceFactory(character=character_1, total=10_000)
        CharacterWalletBalanceFactory(character=character_2, total=5_000)

        today = now().date()
        ore_type = EveTypeFactory(name="Veldspar")
        EveMarketPriceFactory(eve_type=ore_type, average_price=100)
        CharacterMiningLedgerEntryFactory(
            character=character_1,
            eve_type=ore_type,
            quantity=4,
            date=today - dt.timedelta(days=1),
        )
        CharacterMiningLedgerEntryFactory(
            character=character_1, eve_type=ore_type, quantity=3, date=today
        )
        CharacterMiningLedgerEntryFactory(
            character=character_2, eve_type=ore_type, quantity=2, date=today
        )
        not_this_month = now() - dt.timedelta(days=40)
        CharacterMiningLedgerEntryFactory(
            character=character_2, eve_type=ore_type, quantity=2, date=not_this_month
        )
        CharacterWalletJournalEntryFactory(
            character=character_1, amount=4_000, ref_type="bounty_prizes", date=now()
        )
        CharacterWalletJournalEntryFactory(
            character=character_1, amount=3_000, ref_type="bounty_prizes", date=now()
        )
        CharacterWalletJournalEntryFactory(
            character=character_2, amount=2_000, ref_type="bounty_prizes", date=now()
        )
        not_this_month = now() - dt.timedelta(days=40)
        CharacterWalletJournalEntryFactory(
            character=character_2,
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
        self.assertEqual(context["total_mined_isk"], 900.0)
        self.assertEqual(context["total_character_skillpoints"], 4_000)

    def test_user_with_memberaudit_character_and_no_data(self):
        # given
        character_1001 = CharacterFactory()
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
        user = UserMainBasicAccessFactory()
        character = CharacterFactory(user=user)
        not_this_month = now().date() - dt.timedelta(days=40)
        CharacterMiningLedgerEntryFactory(character=character, date=not_this_month)
        CharacterWalletJournalEntryFactory(
            character=character, ref_type="bounty_prizes", date=not_this_month
        )

        request = self.factory.get("/")
        request.user = user

        # when
        context = _dashboard_panel(request)

        # then
        self.assertEqual(context["total_ratted_isk"], 0)
        self.assertEqual(context["total_mined_isk"], 0)


@patch(MODULE_PATH + ".player_count.get", spec=True)
class TestPlayerCountData(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()

    def test_should_return_player_count(self, mock_player_count):
        # given
        user = UserMainBasicAccessFactory()
        mock_player_count.return_value = 42
        request = self.factory.get("/")
        request.user = user

        # when
        response = player_count_data(request)

        # then
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertJSONEqual(response.content.decode("utf-8"), {"player_count": 42})
