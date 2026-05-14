from unittest.mock import patch

from bravado.exception import HTTPError
from celery.exceptions import Retry as CeleryRetry

from django.test import TestCase, override_settings
from django.utils.dateparse import parse_datetime
from esi.models import Token
from eveuniverse.models import EveEntity
from eveuniverse.tests.testdata.factories_2 import EveEntityFactory

from allianceauth.eveonline.models import EveCharacter
from app_utils.esi import reset_retry_task_on_esi_error_and_offline
from app_utils.esi_testing import EsiClientStub, EsiEndpoint, build_http_error
from app_utils.testing import create_user_from_evecharacter, generate_invalid_pk

from memberaudit import tasks
from memberaudit.helpers import UpdateSectionResult
from memberaudit.models import Character, CharacterUpdateStatus
from memberaudit.tests.utils import extract

from .testdata.factories import (
    create_character,
    create_character_mail,
    create_mail_entity_from_eve_entity,
)
from .testdata.load_entities import load_entities
from .testdata.load_eveuniverse import load_eveuniverse
from .testdata.load_locations import load_locations
from .utils import create_memberaudit_character, reset_celery_once_locks

MODELS_PATH = "memberaudit.models"
MANAGERS_PATH = "memberaudit.managers"
TASKS_PATH = "memberaudit.tasks"


@override_settings(
    CELERY_ALWAYS_EAGER=True,
    CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
    APP_UTILS_OBJECT_CACHE_DISABLED=True,
)
@patch(MANAGERS_PATH + ".character_sections_2.data_retention_cutoff", lambda: None)
@patch(MANAGERS_PATH + ".character_sections_2.esi")
@patch(MANAGERS_PATH + ".general.esi")
class TestUpdateCharacterMails(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        cls.character_1001 = create_memberaudit_character(1001)
        reset_celery_once_locks()

        endpoints = [
            EsiEndpoint(
                "Mail",
                "get_characters_character_id_mail_lists",
                "character_id",
                needs_token=True,
                data={
                    "1001": [
                        {
                            "mailing_list_id": 9001,
                            "name": "Dummy 1",
                        }
                    ]
                },
            ),
            EsiEndpoint(
                "Mail",
                "get_characters_character_id_mail_labels",
                "character_id",
                needs_token=True,
                data={
                    "1001": {
                        "labels": [
                            {
                                "color": "#660066",
                                "label_id": 1,
                                "name": "PINK",
                                "unread_count": 7,
                            }
                        ],
                        "total_unread_count": 1,
                    }
                },
            ),
            EsiEndpoint(
                "Mail",
                "get_characters_character_id_mail",
                "character_id",
                needs_token=True,
                data={
                    "1001": [
                        {
                            "from": 1002,
                            "labels": None,
                            "mail_id": 1,
                            "recipients": [
                                {"recipient_id": 1001, "recipient_type": "character"}
                            ],
                            "subject": "subject 1",
                            "timestamp": "2015-09-30T18:07:00Z",
                        },
                        {
                            "from": 9001,
                            "labels": [1],
                            "mail_id": 2,
                            "recipients": [
                                {"recipient_id": 1001, "recipient_type": "character"}
                            ],
                            "subject": "subject 2",
                            "timestamp": "2015-09-30T19:07:00Z",
                        },
                    ]
                },
            ),
            EsiEndpoint(
                "Mail",
                "get_characters_character_id_mail_mail_id",
                "mail_id",
                needs_token=True,
                data={
                    "1": {
                        "body": "body 1",
                        "from": 1002,
                        "labels": None,
                        "read": True,
                        "subject": "subject 1",
                        "timestamp": "2015-09-30T18:07:00Z",
                    },
                    "2": {
                        "body": "body 2",
                        "from": 9001,
                        "labels": [1],
                        "read": False,
                        "subject": "subject 2",
                        "timestamp": "2015-09-30T18:07:00Z",
                    },
                },
            ),
        ]
        cls.esi_client_stub = EsiClientStub.create_from_endpoints(endpoints)

    def test_should_update_mails_from_scratch_and_report_success(
        self, mock_esi_general, mock_esi_sections
    ):
        # given
        mock_esi_general.client = self.esi_client_stub
        mock_esi_sections.client = self.esi_client_stub

        # when
        tasks.update_character_mails.delay(self.character_1001.pk, True)

        # then
        status: CharacterUpdateStatus = self.character_1001.update_status_set.get(
            section=Character.UpdateSection.MAILS
        )
        self.assertTrue(status.is_success)
        self.assertFalse(status.error_message)
        self.assertTrue(status.run_started_at)
        self.assertTrue(status.run_finished_at)
        self.assertTrue(status.update_started_at)
        self.assertTrue(status.update_finished_at)

        mail_ids = extract(self.character_1001.mails, "mail_id")
        self.assertSetEqual(mail_ids, {1, 2})

        mail = self.character_1001.mails.get(mail_id=1)
        self.assertEqual(mail.subject, "subject 1")
        self.assertEqual(mail.body, "body 1")

        mail = self.character_1001.mails.get(mail_id=2)
        self.assertEqual(mail.subject, "subject 2")
        self.assertEqual(mail.body, "body 2")
        label_ids = extract(mail.labels, "label_id")
        self.assertEqual(label_ids, {1})

    # TODO: Add test to check force update works

    def test_should_only_fetch_body_for_new_mails(
        self, mock_esi_general, mock_esi_sections
    ):
        # given
        mock_esi_general.client = self.esi_client_stub
        mock_esi_sections.client = self.esi_client_stub

        sender = create_mail_entity_from_eve_entity(1002)
        recipient = create_mail_entity_from_eve_entity(1001)
        create_character_mail(
            character=self.character_1001,
            recipients=[recipient],
            mail_id=1,
            sender=sender,
            subject="subject 1",
            body="body 1",
            timestamp=parse_datetime("2015-09-30T18:07:00Z"),
        )

        # when
        with patch(
            TASKS_PATH + ".update_mail_body_esi", wraps=tasks.update_mail_body_esi
        ) as spy_update_mail_body_esi:
            tasks.update_character_mails.delay(
                self.character_1001.pk, force_update=False
            )

            # then
            mail_ids = extract(self.character_1001.mails, "mail_id")
            self.assertSetEqual(mail_ids, {1, 2})

            mail = self.character_1001.mails.get(mail_id=1)
            self.assertEqual(mail.subject, "subject 1")
            self.assertEqual(mail.body, "body 1")

            mail = self.character_1001.mails.get(mail_id=2)
            self.assertEqual(mail.subject, "subject 2")
            self.assertEqual(mail.body, "body 2")

            self.assertEqual(spy_update_mail_body_esi.apply_async.call_count, 1)

    def test_should_fetch_body_for_all_mails_from_header_when_forced(
        self, mock_esi_general, mock_esi_sections
    ):
        # given
        mock_esi_general.client = self.esi_client_stub
        mock_esi_sections.client = self.esi_client_stub

        sender = create_mail_entity_from_eve_entity(1002)
        recipient = create_mail_entity_from_eve_entity(1001)
        create_character_mail(
            character=self.character_1001,
            recipients=[recipient],
            mail_id=1,
            sender=sender,
            subject="subject 1",
            body="body 1",
            timestamp=parse_datetime("2015-09-30T18:07:00Z"),
        )

        # when
        with patch(
            TASKS_PATH + ".update_mail_body_esi", wraps=tasks.update_mail_body_esi
        ) as spy_update_mail_body_esi:
            tasks.update_character_mails.delay(
                self.character_1001.pk, force_update=True
            )

            # then
            mail_ids = extract(self.character_1001.mails, "mail_id")
            self.assertSetEqual(mail_ids, {1, 2})

            mail = self.character_1001.mails.get(mail_id=1)
            self.assertEqual(mail.subject, "subject 1")
            self.assertEqual(mail.body, "body 1")

            mail = self.character_1001.mails.get(mail_id=2)
            self.assertEqual(mail.subject, "subject 2")
            self.assertEqual(mail.body, "body 2")

            self.assertEqual(spy_update_mail_body_esi.apply_async.call_count, 2)


@patch("celery.app.task.Context.called_directly", False)  # make retry work with eager
@patch(TASKS_PATH + ".Location.objects.structure_update_or_create_esi", spec=True)
class TestUpdateStructureEsi(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities()
        cls.character = create_memberaudit_character(1001)
        cls.token = (
            cls.character.eve_character.character_ownership.user.token_set.first()
        )

    def setUp(self):
        reset_retry_task_on_esi_error_and_offline()

    def test_should_complete_normally_when_no_issue(self, mock_update_or_create_esi):
        mock_update_or_create_esi.return_value = None
        tasks.update_structure_esi(id=1_000_000_000_001, token_pk=self.token.pk)

    def test_should_raise_exception_when_token_is_invalid(
        self, mock_update_or_create_esi
    ):
        mock_update_or_create_esi.return_value = None
        with self.assertRaises(Token.DoesNotExist):
            tasks.update_structure_esi(
                id=1_000_000_000_001, token_pk=generate_invalid_pk(Token)
            )

    def test_should_retry_when_esi_is_offline(self, mock_update_or_create_esi):
        mock_update_or_create_esi.side_effect = build_http_error(502)

        with self.assertRaises(CeleryRetry):
            tasks.update_structure_esi(id=1_000_000_000_001, token_pk=self.token.pk)

    def test_should_retry_when_esi_error_limit_breached(
        self, mock_update_or_create_esi
    ):
        mock_update_or_create_esi.side_effect = build_http_error(420)

        with self.assertRaises(CeleryRetry):
            tasks.update_structure_esi(id=1_000_000_000_001, token_pk=self.token.pk)

    def test_should_raise_other_http_errors(self, mock_update_or_create_esi):
        mock_update_or_create_esi.side_effect = build_http_error(400)

        with self.assertRaises(HTTPError):
            tasks.update_structure_esi(id=1_000_000_000_001, token_pk=self.token.pk)


@patch("celery.app.task.Context.called_directly", False)  # make retry work with eager
@patch(TASKS_PATH + ".MailEntity.objects.update_or_create_esi", spec=True)
class TestUpdateMailEntityEsi(TestCase):
    def setUp(self):
        reset_retry_task_on_esi_error_and_offline()

    def test_should_complete_normally_when_no_issue(self, mock_update_or_create_esi):
        mock_update_or_create_esi.return_value = None
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


@override_settings(
    CELERY_ALWAYS_EAGER=True,
    CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
    APP_UTILS_OBJECT_CACHE_DISABLED=True,
)
class TestUpdateCharactersDoctrines(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities()
        reset_celery_once_locks()

    @patch(MODELS_PATH + ".characters.Character.update_skill_sets")
    def test_normal(self, mock_update_skill_sets):
        # given
        mock_update_skill_sets.return_value = UpdateSectionResult(
            is_changed=True, is_updated=True
        )
        create_memberaudit_character(1001)

        # when
        tasks.update_characters_skill_checks()

        # then
        self.assertTrue(mock_update_skill_sets.called)


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
        tasks.update_unresolved_eve_entities()
        # then
        self.assertFalse(mock_update_from_esi_by_id.called)

    def test_should_update_unresolved_entities(self, mock_update_from_esi_by_id):
        # given
        EveEntity.objects.create(id=42)
        # when
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


class TestUpdateMarketPrices(TestCase):
    @patch(TASKS_PATH + ".EveMarketPrice.objects.update_from_esi", spec=True)
    def test_update_market_prices(self, mock_update_from_esi):
        tasks.update_market_prices()
        self.assertTrue(mock_update_from_esi.called)
