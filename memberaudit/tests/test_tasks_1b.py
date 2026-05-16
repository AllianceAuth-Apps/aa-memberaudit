import datetime as dt
from contextlib import nullcontext
from http import HTTPStatus
from unittest.mock import patch

import pook
from bravado.exception import HTTPError
from celery.exceptions import Retry as CeleryRetry

from django.test import TestCase, override_settings
from django.utils.timezone import now
from esi.models import Token
from eveuniverse.models import EveEntity
from eveuniverse.tests.testdata.factories_2 import (
    EveEntityCharacterFactory,
    EveEntityFactory,
)

from allianceauth.eveonline.models import EveCharacter
from app_utils.esi_testing import build_http_error
from app_utils.testing import (
    NoSocketsTestCase,
    create_user_from_evecharacter,
    generate_invalid_pk,
)

from memberaudit import tasks
from memberaudit.helpers import UpdateSectionResult
from memberaudit.models import Character, CharacterMail, CharacterUpdateStatus
from memberaudit.tests.testdata.factories_2 import (
    CharacterFactory,
    CharacterMailFactory,
    TokenFactory2,
    make_esi_url,
)
from memberaudit.tests.utils import TestCaseWithClearCache, extract

from .testdata.factories import create_character
from .testdata.load_entities import load_entities
from .testdata.load_eveuniverse import load_eveuniverse
from .testdata.load_locations import load_locations
from .utils import create_memberaudit_character, reset_celery_once_locks

MODELS_PATH = "memberaudit.models"
MANAGERS_PATH = "memberaudit.managers"
TASKS_PATH = "memberaudit.tasks"


@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
class TestUpdateCharacterMails(TestCaseWithClearCache):
    @pook.on
    def test_should_update_mails_from_scratch_and_report_success(self):
        # given
        character = CharacterFactory()
        timestamp = now() - dt.timedelta(hours=1)
        character_1 = EveEntityCharacterFactory()
        character_2 = EveEntityCharacterFactory()
        pook.get(
            make_esi_url(f"characters/{character.character_id}/mail/lists"),
            reply=HTTPStatus.OK,
            response_json=[
                {
                    "mailing_list_id": 9001,
                    "name": "Dummy 1",
                }
            ],
        )
        pook.get(
            make_esi_url(f"characters/{character.character_id}/mail/labels"),
            reply=HTTPStatus.OK,
            response_json={
                "labels": [
                    {
                        "color": "#660066",
                        "label_id": 1,
                        "name": "PINK",
                        "unread_count": 7,
                    }
                ],
                "total_unread_count": 42,
            },
        )
        pook.get(
            make_esi_url(f"characters/{character.character_id}/mail"),
            reply=HTTPStatus.OK,
            response_json=[
                {
                    "from": character_2.id,
                    "mail_id": 1,
                    "recipients": [
                        {"recipient_id": character_1.id, "recipient_type": "character"}
                    ],
                    "subject": "subject 1",
                    "timestamp": timestamp.isoformat(),
                },
                {
                    "from": 9001,
                    "labels": [1],
                    "mail_id": 2,
                    "recipients": [
                        {"recipient_id": character_1.id, "recipient_type": "character"}
                    ],
                    "subject": "subject 2",
                    "timestamp": timestamp.isoformat(),
                },
            ],
        )
        pook.get(
            make_esi_url(f"characters/{character.character_id}/mail/1"),
            reply=HTTPStatus.OK,
            response_json={
                "body": "body 1",
                "from": character_2.id,
                "read": True,
                "subject": "subject 1",
                "timestamp": timestamp.isoformat(),
            },
        )
        pook.get(
            make_esi_url(f"characters/{character.character_id}/mail/2"),
            reply=HTTPStatus.OK,
            response_json={
                "body": "body 2",
                "from": 9001,
                "labels": [1],
                "read": False,
                "subject": "subject 2",
                "timestamp": timestamp.isoformat(),
            },
        )

        # when
        tasks.update_character_mails.delay(character.pk, force_update=False)

        # then
        status: CharacterUpdateStatus = character.update_status_set.get(
            section=Character.UpdateSection.MAILS
        )
        self.assertTrue(status.is_success)
        self.assertFalse(status.error_message)
        self.assertTrue(status.run_started_at)
        self.assertTrue(status.run_finished_at)
        self.assertTrue(status.update_started_at)
        self.assertTrue(status.update_finished_at)

        mail_ids = extract(character.mails, "mail_id")
        self.assertSetEqual(mail_ids, {1, 2})

        mail: CharacterMail = character.mails.get(mail_id=1)
        self.assertEqual(mail.subject, "subject 1")
        self.assertEqual(mail.body, "body 1")

        mail: CharacterMail = character.mails.get(mail_id=2)
        self.assertEqual(mail.subject, "subject 2")
        self.assertEqual(mail.body, "body 2")
        label_ids = extract(mail.labels, "label_id")
        self.assertEqual(label_ids, {1})

    # TODO: Add test to check force update works

    @pook.on
    def test_should_only_fetch_body_for_new_mails(self):
        # given
        character = CharacterFactory()
        mail_1 = CharacterMailFactory(character=character)
        timestamp = now() - dt.timedelta(hours=1)
        character_1 = EveEntityCharacterFactory()
        character_2 = EveEntityCharacterFactory()
        pook.get(
            make_esi_url(f"characters/{character.character_id}/mail/lists"),
            reply=HTTPStatus.OK,
            response_json=[],
        )
        pook.get(
            make_esi_url(f"characters/{character.character_id}/mail/labels"),
            reply=HTTPStatus.OK,
            response_json={
                "labels": [],
                "total_unread_count": 42,
            },
        )
        mail_2_id = 42
        pook.get(
            make_esi_url(f"characters/{character.character_id}/mail"),
            reply=HTTPStatus.OK,
            response_json=[
                {
                    "from": mail_1.sender.id,
                    "mail_id": mail_1.mail_id,
                    "recipients": [
                        {
                            "recipient_id": mail_1.recipients.first().id,
                            "recipient_type": "character",
                        }
                    ],
                    "subject": mail_1.subject,
                    "timestamp": mail_1.timestamp.isoformat(),
                },
                {
                    "from": character_2.id,
                    "mail_id": mail_2_id,
                    "recipients": [
                        {"recipient_id": character_1.id, "recipient_type": "character"}
                    ],
                    "subject": "subject 1",
                    "timestamp": timestamp.isoformat(),
                },
            ],
        )
        pook.get(
            make_esi_url(f"characters/{character.character_id}/mail/{mail_2_id}"),
            reply=HTTPStatus.OK,
            response_json={
                "body": "body 2",
                "from": character_2.id,
                "read": True,
                "subject": "subject 2",
                "timestamp": timestamp.isoformat(),
            },
        )

        # when
        tasks.update_character_mails.delay(character.pk, force_update=False)

        # then
        mail_ids = extract(character.mails, "mail_id")
        self.assertSetEqual(mail_ids, {mail_1.mail_id, mail_2_id})
        mail_2: CharacterMail = character.mails.get(mail_id=mail_2_id)
        self.assertTrue(mail_2.body)

    @pook.on
    def test_should_fetch_body_for_all_mails_when_forced(self):
        # given
        character = CharacterFactory()
        mail_1 = CharacterMailFactory(character=character)
        timestamp = now() - dt.timedelta(hours=1)
        character_1 = EveEntityCharacterFactory()
        character_2 = EveEntityCharacterFactory()
        pook.get(
            make_esi_url(f"characters/{character.character_id}/mail/lists"),
            reply=HTTPStatus.OK,
            response_json=[],
        )
        pook.get(
            make_esi_url(f"characters/{character.character_id}/mail/labels"),
            reply=HTTPStatus.OK,
            response_json={
                "labels": [],
                "total_unread_count": 42,
            },
        )
        mail_2_id = 42
        pook.get(
            make_esi_url(f"characters/{character.character_id}/mail"),
            reply=HTTPStatus.OK,
            response_json=[
                {
                    "from": mail_1.sender.id,
                    "mail_id": mail_1.mail_id,
                    "recipients": [
                        {
                            "recipient_id": mail_1.recipients.first().id,
                            "recipient_type": "character",
                        }
                    ],
                    "subject": mail_1.subject,
                    "timestamp": mail_1.timestamp.isoformat(),
                },
                {
                    "from": character_2.id,
                    "mail_id": mail_2_id,
                    "recipients": [
                        {"recipient_id": character_1.id, "recipient_type": "character"}
                    ],
                    "subject": "subject 1",
                    "timestamp": timestamp.isoformat(),
                },
            ],
        )
        pook.get(
            make_esi_url(f"characters/{character.character_id}/mail/{mail_1.mail_id}"),
            reply=HTTPStatus.OK,
            response_json={
                "body": "body 1",
                "from": character_2.id,
                "read": True,
                "subject": "subject 1",
                "timestamp": timestamp.isoformat(),
            },
        )
        pook.get(
            make_esi_url(f"characters/{character.character_id}/mail/{mail_2_id}"),
            reply=HTTPStatus.OK,
            response_json={
                "body": "body 2",
                "from": character_2.id,
                "read": True,
                "subject": "subject 2",
                "timestamp": timestamp.isoformat(),
            },
        )

        # when
        tasks.update_character_mails.delay(character.pk, force_update=True)

        # then
        mail_ids = extract(character.mails, "mail_id")
        self.assertSetEqual(mail_ids, {mail_1.mail_id, mail_2_id})

        mail_1.refresh_from_db()
        self.assertTrue(mail_1.body)

        mail_2: CharacterMail = character.mails.get(mail_id=mail_2_id)
        self.assertTrue(mail_2.body)


@patch("celery.app.task.Context.called_directly", False)  # make retry work with eager
@patch(TASKS_PATH + ".Location.objects.structure_update_or_create_esi", spec=True)
class TestUpdateStructureEsi(TestCaseWithClearCache):
    def test_should_complete_normally_when_no_issue(self, _):
        token = TokenFactory2()
        tasks.update_structure_esi(id=1_000_000_000_001, token_pk=token.pk)

    def test_should_raise_exception_when_token_is_invalid(self, _):
        with self.assertRaises(Token.DoesNotExist):
            tasks.update_structure_esi(
                id=1_000_000_000_001, token_pk=generate_invalid_pk(Token)
            )

    def test_should_retry_when_esi_is_offline(self, mock_update_or_create_esi):
        mock_update_or_create_esi.side_effect = build_http_error(502)
        token = TokenFactory2()
        with self.assertRaises(CeleryRetry):
            tasks.update_structure_esi(id=1_000_000_000_001, token_pk=token.pk)

    def test_should_retry_when_esi_error_limit_breached(
        self, mock_update_or_create_esi
    ):
        mock_update_or_create_esi.side_effect = build_http_error(420)
        token = TokenFactory2()
        with self.assertRaises(CeleryRetry):
            tasks.update_structure_esi(id=1_000_000_000_001, token_pk=token.pk)

    def test_should_raise_other_http_errors(self, mock_update_or_create_esi):
        mock_update_or_create_esi.side_effect = build_http_error(400)
        token = TokenFactory2()
        with self.assertRaises(HTTPError):
            tasks.update_structure_esi(id=1_000_000_000_001, token_pk=token.pk)


@patch("celery.app.task.Context.called_directly", False)  # make retry work with eager
@patch(TASKS_PATH + ".MailEntity.objects.update_or_create_esi", spec=True)
class TestUpdateMailEntityEsi(TestCaseWithClearCache):
    def test_should_complete_normally_when_no_issue(self, _):
        tasks.update_mail_entity_esi(1001)

    def test_should_retry_when_esi_is_offline(self, mock_update_or_create_esi):
        mock_update_or_create_esi.side_effect = build_http_error(502)

        with self.assertRaises(CeleryRetry):
            tasks.update_mail_entity_esi(1001)

    def test_should_retry_when_esi_error_limit_breached(
        self, mock_update_or_create_esi
    ):
        mock_update_or_create_esi.side_effect = build_http_error(420)

        with self.assertRaises(CeleryRetry):
            tasks.update_mail_entity_esi(1001)

    def test_should_raise_other_http_errors(self, mock_update_or_create_esi):
        mock_update_or_create_esi.side_effect = build_http_error(400)

        with self.assertRaises(HTTPError):
            tasks.update_mail_entity_esi(1001)


class TestUpdateCharactersDoctrines(TestCaseWithClearCache):
    @patch(TASKS_PATH + ".update_character_skill_sets")
    @patch(MODELS_PATH + ".characters.Character.update_skill_sets")
    def test_normal(self, mock_update_skill_sets, mock_update_character_skill_sets):
        # given
        mock_update_skill_sets.return_value = UpdateSectionResult(
            is_changed=True, is_updated=True
        )
        CharacterFactory()

        # when
        tasks.update_characters_skill_checks()

        # then
        self.assertTrue(mock_update_character_skill_sets.apply_async.called)


class TestDeleteCharacters(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities()
        Character.objects.all().delete()

    def test_should_delete_a_character(self):
        # given
        character_1001 = create_memberaudit_character(1001)
        character_1002 = create_memberaudit_character(1002)
        # when
        tasks.delete_objects("Character", [character_1001.pk, character_1002.pk])
        # then
        self.assertFalse(Character.objects.exists())

    def test_should_raise_error_when_model_not_found(self):
        # when/then
        with self.assertRaises(LookupError):
            tasks.delete_objects("MyUnknownMOdel", [1])


@override_settings(
    CELERY_ALWAYS_EAGER=True,
    CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
    APP_UTILS_OBJECT_CACHE_DISABLED=True,
)
class TestExportData(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities()
        cls.character = create_memberaudit_character(1001)
        reset_celery_once_locks()

    @patch(TASKS_PATH + ".data_exporters.export_topic_to_archive", spec=True)
    def test_should_export_all_topics(self, mock_export_topic_to_file):
        # when
        tasks.export_data()
        # then
        called_topics = [
            call[1]["topic"] for call in mock_export_topic_to_file.call_args_list
        ]
        self.assertEqual(len(called_topics), 3)
        self.assertSetEqual(
            set(called_topics), {"contract", "contract-item", "wallet-journal"}
        )

    @patch(TASKS_PATH + ".data_exporters.export_topic_to_archive", spec=True)
    def test_should_export_wallet_journal(self, mock_export_topic_to_file):
        # given
        user = self.character.user
        # when
        tasks.export_data_for_topic(topic="abc", user_pk=user.pk)
        # then
        self.assertTrue(mock_export_topic_to_file.called)
        _, kwargs = mock_export_topic_to_file.call_args
        self.assertEqual(kwargs["topic"], "abc")


class TestUpdateComplianceGroupDesignations(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities()

    @patch(TASKS_PATH + ".ComplianceGroupDesignation.objects.update_user", spec=True)
    def test_should_update_for_user(self, mock_update_user):
        # given
        user, _ = create_user_from_evecharacter(
            1001,
            permissions=["memberaudit.basic_access"],
            scopes=Character.esi_scopes(),
        )
        # when
        tasks.update_compliance_groups_for_user(user.pk)
        # then
        self.assertTrue(mock_update_user.called)


@patch(TASKS_PATH + ".esi_status.unavailable_sections", lambda: set())
@patch(TASKS_PATH + ".check_character_consistency", spec=True)
@patch(TASKS_PATH + ".update_character", spec=True)
class TestUpdateAllCharacters(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        load_locations()

    def test_should_update_all_enabled_characters(
        self, mock_update_character, mock_check_character_consistency
    ):
        # given
        character_1001 = create_memberaudit_character(1001)
        character_1002 = create_memberaudit_character(1002)
        character_1003 = create_memberaudit_character(1003)
        character_1003.is_disabled = True
        character_1003.save()
        # when
        tasks.update_all_characters()
        # then
        self.assertTrue(mock_update_character.apply_async.called)
        called_pks = {
            o[1]["kwargs"]["character_pk"]
            for o in mock_update_character.apply_async.call_args_list
        }
        self.assertSetEqual(called_pks, {character_1001.pk, character_1002.pk})

    def test_should_disable_orphaned_characters(
        self, mock_update_character, mock_check_character_consistency
    ):
        # given
        character_1001 = create_memberaudit_character(1001)
        eve_character_1002 = EveCharacter.objects.get(character_id=1002)
        character_1002 = create_character(eve_character_1002)
        # when
        tasks.update_all_characters()
        # then
        character_1001.refresh_from_db()
        self.assertFalse(character_1001.is_disabled)
        character_1002.refresh_from_db()
        self.assertTrue(character_1002.is_disabled)

    def test_should_unshare_characters_without_share_permission(
        self, mock_update_character, mock_check_character_consistency
    ):
        # given
        character_1001 = create_memberaudit_character(1001)
        character_1001.is_shared = True
        character_1001.save()
        character_1002 = create_memberaudit_character(1002)
        character_1002.is_shared = False
        character_1002.save()
        # when
        tasks.update_all_characters()
        # then
        character_1001.refresh_from_db()
        self.assertEqual(mock_check_character_consistency.apply_async.call_count, 1)
        _, kwargs = mock_check_character_consistency.apply_async.call_args
        self.assertEqual(kwargs["kwargs"]["character_pk"], character_1001.pk)


@patch(TASKS_PATH + ".EveEntity.objects.update_from_esi_by_id", spec=True)
class TestUpdateUnresolvedEveEntities(TestCase):
    def test_should_not_attempt_to_update_when_no_unresolved_entities(
        self, mock_update_from_esi_by_id
    ):
        # given
        EveEntityFactory(id=42, name="alpha")
        # when
        with patch(
            TASKS_PATH + ".retry_task_on_esi_error_and_offline",
            return_value=nullcontext(),
        ):
            tasks.update_unresolved_eve_entities()
        # then
        self.assertFalse(mock_update_from_esi_by_id.called)

    def test_should_update_unresolved_entities(self, mock_update_from_esi_by_id):
        # given
        EveEntity.objects.create(id=42)
        # when
        with patch(
            TASKS_PATH + ".retry_task_on_esi_error_and_offline",
            return_value=nullcontext(),
        ):
            tasks.update_unresolved_eve_entities()
        # then
        self.assertTrue(mock_update_from_esi_by_id.called)
        args, _ = mock_update_from_esi_by_id.call_args
        self.assertEqual(list(args[0]), [42])


@patch(TASKS_PATH + ".check_character_consistency", spec=True)
class TestCheckCharacterConsistency(TestCase):
    def test_should_run_checks(self, mock_check_character_consistency):
        # given
        load_entities()
        character = create_memberaudit_character(1001)
        # when
        tasks.check_character_consistency(character.pk)
        # then
        self.assertTrue(mock_check_character_consistency.called)


class TestUpdateMarketPrices(NoSocketsTestCase):
    @patch(TASKS_PATH + ".EveMarketPrice.objects.update_from_esi", spec=True)
    def test_update_market_prices(self, mock_update_from_esi):
        with patch(
            TASKS_PATH + ".retry_task_on_esi_error_and_offline",
            return_value=nullcontext(),
        ):
            tasks.update_market_prices()

        self.assertTrue(mock_update_from_esi.called)
