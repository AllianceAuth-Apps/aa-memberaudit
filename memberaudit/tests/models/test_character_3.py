import datetime as dt
from unittest.mock import patch

from bravado.exception import HTTPNotFound
from pytz import utc

from django.test import TestCase, override_settings
from django.utils.dateparse import parse_datetime
from django.utils.timezone import now
from eveuniverse.models import EveEntity, EveType

from app_utils.esi import EsiStatus
from app_utils.esi_testing import BravadoResponseStub, build_http_error
from app_utils.testing import NoSocketsTestCase

from memberaudit.core.xml_converter import eve_xml_to_html

from ...models import (
    CharacterMail,
    CharacterMailLabel,
    CharacterShip,
    CharacterWalletJournalEntry,
    Location,
    MailEntity,
)
from ..testdata.esi_client_stub import esi_client_stub
from ..utils import CharacterUpdateTestDataMixin

MODELS_PATH = "memberaudit.models"
MANAGERS_PATH = "memberaudit.managers"
TASKS_PATH = "memberaudit.tasks"


@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
@patch(MODELS_PATH + ".character.esi")
class TestCharacterUpdateMails(CharacterUpdateTestDataMixin, TestCase):
    def test_update_mailing_lists_1(self, mock_esi):
        """can create new mailing lists from scratch"""
        mock_esi.client = esi_client_stub

        self.character_1001.update_mailing_lists()

        self.assertSetEqual(
            set(MailEntity.objects.values_list("id", flat=True)), {9001, 9002}
        )
        self.assertSetEqual(
            set(self.character_1001.mailing_lists.values_list("id", flat=True)),
            {9001, 9002},
        )

        obj = MailEntity.objects.get(id=9001)
        self.assertEqual(obj.name, "Dummy 1")

        obj = MailEntity.objects.get(id=9002)
        self.assertEqual(obj.name, "Dummy 2")

    def test_update_mailing_lists_2(self, mock_esi):
        """does not remove obsolete mailing lists"""
        mock_esi.client = esi_client_stub
        MailEntity.objects.create(
            id=5, category=MailEntity.Category.MAILING_LIST, name="Obsolete"
        )

        self.character_1001.update_mailing_lists()

        self.assertSetEqual(
            set(MailEntity.objects.values_list("id", flat=True)), {9001, 9002, 5}
        )
        self.assertSetEqual(
            set(self.character_1001.mailing_lists.values_list("id", flat=True)),
            {9001, 9002},
        )

    def test_update_mailing_lists_3(self, mock_esi):
        """updates existing mailing lists"""
        mock_esi.client = esi_client_stub
        MailEntity.objects.create(
            id=9001, category=MailEntity.Category.MAILING_LIST, name="Update me"
        )

        self.character_1001.update_mailing_lists()

        self.assertSetEqual(
            set(MailEntity.objects.values_list("id", flat=True)), {9001, 9002}
        )
        self.assertSetEqual(
            set(self.character_1001.mailing_lists.values_list("id", flat=True)),
            {9001, 9002},
        )
        obj = MailEntity.objects.get(id=9001)
        self.assertEqual(obj.name, "Dummy 1")

    def test_update_mailing_lists_4(self, mock_esi):
        """when data from ESI has not changed, then skip update"""
        mock_esi.client = esi_client_stub

        self.character_1001.update_mailing_lists()
        obj = MailEntity.objects.get(id=9001)
        obj.name = "Extravaganza"
        obj.save()
        self.character_1001.mailing_lists.clear()

        self.character_1001.update_mailing_lists()
        obj = MailEntity.objects.get(id=9001)
        self.assertEqual(obj.name, "Extravaganza")
        self.assertSetEqual(
            set(self.character_1001.mailing_lists.values_list("id", flat=True)), set()
        )

    def test_update_mailing_lists_5(self, mock_esi):
        """when data from ESI has not changed and update is forced, then do update"""
        mock_esi.client = esi_client_stub

        self.character_1001.update_mailing_lists()
        obj = MailEntity.objects.get(id=9001)
        obj.name = "Extravaganza"
        obj.save()

        self.character_1001.update_mailing_lists(force_update=True)
        obj = MailEntity.objects.get(id=9001)
        self.assertEqual(obj.name, "Dummy 1")

    def test_update_mail_labels_1(self, mock_esi):
        """can create from scratch"""
        mock_esi.client = esi_client_stub

        self.character_1001.update_mail_labels()

        self.assertEqual(self.character_1001.unread_mail_count.total, 5)
        self.assertSetEqual(
            set(self.character_1001.mail_labels.values_list("label_id", flat=True)),
            {3, 17},
        )

        obj = self.character_1001.mail_labels.get(label_id=3)
        self.assertEqual(obj.name, "PINK")
        self.assertEqual(obj.unread_count, 4)
        self.assertEqual(obj.color, "#660066")

        obj = self.character_1001.mail_labels.get(label_id=17)
        self.assertEqual(obj.name, "WHITE")
        self.assertEqual(obj.unread_count, 1)
        self.assertEqual(obj.color, "#ffffff")

    def test_update_mail_labels_2(self, mock_esi):
        """will remove obsolete labels"""
        mock_esi.client = esi_client_stub
        CharacterMailLabel.objects.create(
            character=self.character_1001, label_id=666, name="Obsolete"
        )

        self.character_1001.update_mail_labels()

        self.assertSetEqual(
            set(self.character_1001.mail_labels.values_list("label_id", flat=True)),
            {3, 17},
        )

    def test_update_mail_labels_3(self, mock_esi):
        """will update existing labels"""
        mock_esi.client = esi_client_stub
        CharacterMailLabel.objects.create(
            character=self.character_1001,
            label_id=3,
            name="Update me",
            unread_count=0,
            color=0,
        )

        self.character_1001.update_mail_labels()

        self.assertSetEqual(
            set(self.character_1001.mail_labels.values_list("label_id", flat=True)),
            {3, 17},
        )

        obj = self.character_1001.mail_labels.get(label_id=3)
        self.assertEqual(obj.name, "PINK")
        self.assertEqual(obj.unread_count, 4)
        self.assertEqual(obj.color, "#660066")

    def test_update_mail_labels_4(self, mock_esi):
        """when data from ESI has not changed, then skip update"""
        mock_esi.client = esi_client_stub

        self.character_1001.update_mail_labels()
        obj = self.character_1001.mail_labels.get(label_id=3)
        obj.name = "MAGENTA"
        obj.save()

        self.character_1001.update_mail_labels()

        obj = self.character_1001.mail_labels.get(label_id=3)
        self.assertEqual(obj.name, "MAGENTA")

    def test_update_mail_labels_5(self, mock_esi):
        """when data from ESI has not changed and update is forced, then do update"""
        mock_esi.client = esi_client_stub

        self.character_1001.update_mail_labels()
        obj = self.character_1001.mail_labels.get(label_id=3)
        obj.name = "MAGENTA"
        obj.save()

        self.character_1001.update_mail_labels(force_update=True)

        obj = self.character_1001.mail_labels.get(label_id=3)
        self.assertEqual(obj.name, "PINK")

    @staticmethod
    def stub_eve_entity_get_or_create_esi(id, *args, **kwargs):
        """will return EveEntity if it exists else None, False"""
        try:
            obj = EveEntity.objects.get(id=id)
            return obj, True
        except EveEntity.DoesNotExist:
            return None, False

    @patch(MODELS_PATH + ".character.MEMBERAUDIT_DATA_RETENTION_LIMIT", None)
    @patch(MANAGERS_PATH + ".general.fetch_esi_status")
    @patch(MANAGERS_PATH + ".sections.EveEntity.objects.get_or_create_esi")
    def test_update_mail_headers_1(
        self, mock_eve_entity, mock_fetch_esi_status, mock_esi
    ):
        """can create new mail from scratch"""
        mock_esi.client = esi_client_stub
        mock_eve_entity.side_effect = self.stub_eve_entity_get_or_create_esi
        mock_fetch_esi_status.return_value = EsiStatus(True, 99, 60)

        self.character_1001.update_mailing_lists()
        self.character_1001.update_mail_labels()
        self.character_1001.update_mail_headers()
        self.assertSetEqual(
            set(self.character_1001.mails.values_list("mail_id", flat=True)),
            {1, 2, 3},
        )

        obj = self.character_1001.mails.get(mail_id=1)
        self.assertEqual(obj.sender.id, 1002)
        self.assertTrue(obj.is_read)
        self.assertEqual(obj.subject, "Mail 1")
        self.assertEqual(obj.timestamp, parse_datetime("2015-09-05T16:07:00Z"))
        self.assertFalse(obj.body)
        self.assertTrue(obj.recipients.filter(id=1001).exists())
        self.assertTrue(obj.recipients.filter(id=9001).exists())
        self.assertSetEqual(set(obj.labels.values_list("label_id", flat=True)), {3})

        obj = self.character_1001.mails.get(mail_id=2)
        self.assertEqual(obj.sender_id, 9001)
        self.assertFalse(obj.is_read)
        self.assertEqual(obj.subject, "Mail 2")
        self.assertEqual(obj.timestamp, parse_datetime("2015-09-10T18:07:00Z"))
        self.assertFalse(obj.body)
        self.assertSetEqual(set(obj.labels.values_list("label_id", flat=True)), {3})

        obj = self.character_1001.mails.get(mail_id=3)
        self.assertEqual(obj.sender_id, 1002)
        self.assertTrue(obj.recipients.filter(id=9003).exists())
        self.assertEqual(obj.timestamp, parse_datetime("2015-09-20T12:07:00Z"))

    @patch(MODELS_PATH + ".character.MEMBERAUDIT_DATA_RETENTION_LIMIT", None)
    @patch(MANAGERS_PATH + ".general.fetch_esi_status")
    @patch(MANAGERS_PATH + ".sections.EveEntity.objects.get_or_create_esi")
    def test_update_mail_headers_2(
        self, mock_eve_entity, mock_fetch_esi_status, mock_esi
    ):
        """can update existing mail"""
        mock_esi.client = esi_client_stub
        mock_eve_entity.side_effect = self.stub_eve_entity_get_or_create_esi
        mock_fetch_esi_status.return_value = EsiStatus(True, 99, 60)
        sender, _ = MailEntity.objects.update_or_create_from_eve_entity_id(id=1002)
        mail = CharacterMail.objects.create(
            character=self.character_1001,
            mail_id=1,
            sender=sender,
            subject="Mail 1",
            timestamp=parse_datetime("2015-09-05T16:07:00Z"),
            is_read=False,  # to be updated
        )
        recipient_1, _ = MailEntity.objects.update_or_create_from_eve_entity_id(id=1001)
        recipient_2 = MailEntity.objects.create(
            id=9001, category=MailEntity.Category.MAILING_LIST, name="Dummy 2"
        )
        mail.recipients.set([recipient_1, recipient_2])

        self.character_1001.update_mailing_lists()
        self.character_1001.update_mail_labels()
        label = self.character_1001.mail_labels.get(label_id=17)
        mail.labels.add(label)  # to be updated

        self.character_1001.update_mail_headers()
        self.assertSetEqual(
            set(self.character_1001.mails.values_list("mail_id", flat=True)),
            {1, 2, 3},
        )

        obj = self.character_1001.mails.get(mail_id=1)
        self.assertEqual(obj.sender_id, 1002)
        self.assertTrue(obj.is_read)
        self.assertEqual(obj.subject, "Mail 1")
        self.assertEqual(obj.timestamp, parse_datetime("2015-09-05T16:07:00Z"))
        self.assertFalse(obj.body)
        self.assertTrue(obj.recipients.filter(id=1001).exists())
        self.assertTrue(obj.recipients.filter(id=9001).exists())
        self.assertSetEqual(set(obj.labels.values_list("label_id", flat=True)), {3})

    @patch(MODELS_PATH + ".character.MEMBERAUDIT_DATA_RETENTION_LIMIT", None)
    @patch(MANAGERS_PATH + ".general.fetch_esi_status")
    @patch(MANAGERS_PATH + ".sections.EveEntity.objects.get_or_create_esi")
    def test_update_mail_headers_3(
        self, mock_eve_entity, mock_fetch_esi_status, mock_esi
    ):
        """when ESI data is unchanged, then skip update"""
        mock_esi.client = esi_client_stub
        mock_eve_entity.side_effect = self.stub_eve_entity_get_or_create_esi
        mock_fetch_esi_status.return_value = EsiStatus(True, 99, 60)

        self.character_1001.update_mailing_lists()
        self.character_1001.update_mail_labels()
        self.character_1001.update_mail_headers()
        obj = self.character_1001.mails.get(mail_id=1)
        obj.is_read = False
        obj.save()

        self.character_1001.update_mail_headers()

        obj = self.character_1001.mails.get(mail_id=1)
        self.assertFalse(obj.is_read)

    @patch(MODELS_PATH + ".character.MEMBERAUDIT_DATA_RETENTION_LIMIT", None)
    @patch(MANAGERS_PATH + ".general.fetch_esi_status")
    @patch(MANAGERS_PATH + ".sections.EveEntity.objects.get_or_create_esi")
    def test_update_mail_headers_4(
        self, mock_eve_entity, mock_fetch_esi_status, mock_esi
    ):
        """when ESI data is unchanged and update forced, then do update"""
        mock_esi.client = esi_client_stub
        mock_eve_entity.side_effect = self.stub_eve_entity_get_or_create_esi
        mock_fetch_esi_status.return_value = EsiStatus(True, 99, 60)

        self.character_1001.update_mailing_lists()
        self.character_1001.update_mail_labels()
        self.character_1001.update_mail_headers()
        obj = self.character_1001.mails.get(mail_id=1)
        obj.is_read = False
        obj.save()

        self.character_1001.update_mail_headers(force_update=True)

        obj = self.character_1001.mails.get(mail_id=1)
        self.assertTrue(obj.is_read)

    @patch(MODELS_PATH + ".character.MEMBERAUDIT_DATA_RETENTION_LIMIT", 15)
    @patch(MANAGERS_PATH + ".general.fetch_esi_status")
    @patch(MANAGERS_PATH + ".sections.EveEntity.objects.get_or_create_esi")
    def test_update_mail_headers_6(
        self, mock_eve_entity, mock_fetch_esi_status, mock_esi
    ):
        """when data retention limit is set, then only fetch mails within that limit"""
        mock_esi.client = esi_client_stub
        mock_eve_entity.side_effect = self.stub_eve_entity_get_or_create_esi
        mock_fetch_esi_status.return_value = EsiStatus(True, 99, 60)

        with patch(MODELS_PATH + ".character.now") as mock_now:
            mock_now.return_value = dt.datetime(2015, 9, 20, 20, 5, tzinfo=utc)
            self.character_1001.update_mailing_lists()
            self.character_1001.update_mail_labels()
            self.character_1001.update_mail_headers()

        self.assertSetEqual(
            set(self.character_1001.mails.values_list("mail_id", flat=True)),
            {2, 3},
        )

    @patch(MODELS_PATH + ".character.MEMBERAUDIT_DATA_RETENTION_LIMIT", 15)
    @patch(MANAGERS_PATH + ".general.fetch_esi_status")
    @patch(MANAGERS_PATH + ".sections.EveEntity.objects.get_or_create_esi")
    def test_update_mail_headers_7(
        self, mock_eve_entity, mock_fetch_esi_status, mock_esi
    ):
        """when data retention limit is set, then remove old data beyond that limit"""
        mock_esi.client = esi_client_stub
        mock_eve_entity.side_effect = self.stub_eve_entity_get_or_create_esi
        mock_fetch_esi_status.return_value = EsiStatus(True, 99, 60)
        sender, _ = MailEntity.objects.update_or_create_from_eve_entity_id(id=1002)
        CharacterMail.objects.create(
            character=self.character_1001,
            mail_id=99,
            sender=sender,
            subject="Mail Old",
            timestamp=parse_datetime("2015-09-02T14:02:00Z"),
            is_read=False,
        )

        with patch(MODELS_PATH + ".character.now") as mock_now:
            mock_now.return_value = dt.datetime(2015, 9, 20, 20, 5, tzinfo=utc)
            self.character_1001.update_mailing_lists()
            self.character_1001.update_mail_labels()
            self.character_1001.update_mail_headers()

        self.assertSetEqual(
            set(self.character_1001.mails.values_list("mail_id", flat=True)),
            {2, 3},
        )

    def test_should_update_existing_mail_body(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        sender, _ = MailEntity.objects.update_or_create_from_eve_entity_id(id=1002)
        mail = CharacterMail.objects.create(
            character=self.character_1001,
            mail_id=1,
            sender=sender,
            subject="Mail 1",
            body="Update me",
            is_read=False,
            timestamp=parse_datetime("2015-09-30T16:07:00Z"),
        )
        recipient_1001, _ = MailEntity.objects.update_or_create_from_eve_entity_id(
            id=1001
        )
        recipient_9001 = MailEntity.objects.create(
            id=9001, category=MailEntity.Category.MAILING_LIST, name="Dummy 2"
        )
        mail.recipients.add(recipient_1001, recipient_9001)
        # when
        self.character_1001.update_mail_body(mail)
        # then
        obj = self.character_1001.mails.get(mail_id=1)
        self.assertEqual(obj.body, "blah blah blah 😓")

    @patch(MODELS_PATH + ".character.eve_xml_to_html")
    def test_should_update_mail_body_from_scratch(self, mock_eve_xml_to_html, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        mock_eve_xml_to_html.side_effect = lambda x: eve_xml_to_html(x)
        sender, _ = MailEntity.objects.update_or_create_from_eve_entity_id(id=1002)
        mail = CharacterMail.objects.create(
            character=self.character_1001,
            mail_id=2,
            sender=sender,
            subject="Mail 1",
            is_read=False,
            timestamp=parse_datetime("2015-09-30T16:07:00Z"),
        )
        recipient_1, _ = MailEntity.objects.update_or_create_from_eve_entity_id(id=1001)
        mail.recipients.add(recipient_1)
        # when
        self.character_1001.update_mail_body(mail)
        # then
        obj = self.character_1001.mails.get(mail_id=2)
        self.assertTrue(obj.body)
        self.assertTrue(mock_eve_xml_to_html.called)

    def test_should_delete_mail_header_when_fetching_body_returns_404(self, mock_esi):
        # given
        mock_esi.client.Mail.get_characters_character_id_mail_mail_id.side_effect = (
            HTTPNotFound(response=BravadoResponseStub(404, "Test"))
        )
        sender, _ = MailEntity.objects.update_or_create_from_eve_entity_id(id=1002)
        mail = CharacterMail.objects.create(
            character=self.character_1001,
            mail_id=1,
            sender=sender,
            subject="Mail 1",
            is_read=False,
            timestamp=parse_datetime("2015-09-30T16:07:00Z"),
        )
        recipient_1001, _ = MailEntity.objects.update_or_create_from_eve_entity_id(
            id=1001
        )
        recipient_9001 = MailEntity.objects.create(
            id=9001, category=MailEntity.Category.MAILING_LIST, name="Dummy 2"
        )
        mail.recipients.add(recipient_1001, recipient_9001)
        # when
        self.character_1001.update_mail_body(mail)
        # then
        self.assertFalse(self.character_1001.mails.filter(mail_id=1).exists())


@patch(MODELS_PATH + ".character.esi")
class TestCharacterUpdateLoyalty(CharacterUpdateTestDataMixin, NoSocketsTestCase):
    def test_create(self, mock_esi):
        """can create from scratch"""
        mock_esi.client = esi_client_stub

        self.character_1001.update_loyalty()
        self.assertEqual(self.character_1001.loyalty_entries.count(), 1)

        obj = self.character_1001.loyalty_entries.get(corporation_id=2002)
        self.assertEqual(obj.loyalty_points, 100)

    def test_update(self, mock_esi):
        """can update existing loyalty"""
        mock_esi.client = esi_client_stub
        self.character_1001.loyalty_entries.create(
            corporation=self.corporation_2001, loyalty_points=200
        )

        self.character_1001.update_loyalty()
        self.assertEqual(self.character_1001.loyalty_entries.count(), 1)

        obj = self.character_1001.loyalty_entries.get(corporation=self.corporation_2002)
        self.assertEqual(obj.loyalty_points, 100)

    def test_skip_update_1(self, mock_esi):
        """when data from ESI has not changed, then skip update"""
        mock_esi.client = esi_client_stub

        self.character_1001.update_loyalty()
        obj = self.character_1001.loyalty_entries.get(corporation=self.corporation_2002)
        obj.loyalty_points = 200
        obj.save()
        self.character_1001.update_loyalty()

        obj = self.character_1001.loyalty_entries.get(corporation=self.corporation_2002)
        self.assertEqual(obj.loyalty_points, 200)

    def test_skip_update_2(self, mock_esi):
        """when data from ESI has not changed and update is forced, then do update"""
        mock_esi.client = esi_client_stub

        self.character_1001.update_loyalty()
        obj = self.character_1001.loyalty_entries.get(corporation=self.corporation_2002)
        obj.loyalty_points = 200
        obj.save()

        self.character_1001.update_loyalty(force_update=True)

        obj = self.character_1001.loyalty_entries.get(corporation=self.corporation_2002)
        self.assertEqual(obj.loyalty_points, 100)

    def test_should_thread_http_500_as_empty_loyalty_list(self, mock_esi):
        # given
        exception = build_http_error(
            500, '{"error":"Unhandled internal error encountered!"}'
        )
        mock_esi.client.Loyalty.get_characters_character_id_loyalty_points.side_effect = (
            exception
        )
        self.character_1001.loyalty_entries.create(
            corporation=self.corporation_2001, loyalty_points=100
        )
        # when
        self.character_1001.update_loyalty()
        # then
        self.assertEqual(self.character_1001.loyalty_entries.count(), 1)
        obj = self.character_1001.loyalty_entries.get(corporation=self.corporation_2001)
        self.assertEqual(obj.loyalty_points, 100)


@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
@patch(MODELS_PATH + ".character.esi")
class TestCharacterUpdateLocation(CharacterUpdateTestDataMixin, NoSocketsTestCase):
    def test_update_location_1(self, mock_esi):
        mock_esi.client = esi_client_stub

        self.character_1001.update_location()
        self.assertEqual(self.character_1001.location.eve_solar_system, self.jita)
        self.assertEqual(self.character_1001.location.location, self.jita_44)

    def test_update_location_2(self, mock_esi):
        mock_esi.client = esi_client_stub

        self.character_1002.update_location()
        self.assertEqual(self.character_1002.location.eve_solar_system, self.amamake)
        self.assertEqual(self.character_1002.location.location, self.structure_1)


@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
@patch(MODELS_PATH + ".character.esi")
class TestCharacterUpdateOnlineStatus(CharacterUpdateTestDataMixin, NoSocketsTestCase):
    def test_update_online_status(self, mock_esi):
        mock_esi.client = esi_client_stub

        self.character_1001.update_online_status()
        self.assertEqual(
            self.character_1001.online_status.last_login,
            parse_datetime("2017-01-02T03:04:05Z"),
        )
        self.assertEqual(
            self.character_1001.online_status.last_logout,
            parse_datetime("2017-01-02T04:05:06Z"),
        )
        self.assertEqual(self.character_1001.online_status.logins, 9001)


@patch(MODELS_PATH + ".character.esi")
class TestCharacterUpdateShip(CharacterUpdateTestDataMixin, NoSocketsTestCase):
    def test_should_update_all_fields(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        # when
        self.character_1001.update_ship()
        # then
        self.assertEqual(self.character_1001.ship.eve_type_id, 603)
        self.assertEqual(self.character_1001.ship.name, "Shooter Boy")

    def test_should_ignore_error_500(self, mock_esi):
        # given
        error_500 = build_http_error(
            500, '{"error":"Undefined 404 response. Original message: Ship not found"}'
        )
        mock_esi.client.Location.get_characters_character_id_ship.side_effect = (
            error_500
        )
        CharacterShip.objects.create(
            character=self.character_1001, eve_type_id=603, name="Shooter Boy"
        )
        # when
        self.character_1001.update_ship()
        # then
        self.character_1001.refresh_from_db()
        self.assertEqual(self.character_1001.ship.eve_type_id, 603)
        self.assertEqual(self.character_1001.ship.name, "Shooter Boy")


@patch(MODELS_PATH + ".character.esi")
class TestCharacterUpdateSkillQueue(CharacterUpdateTestDataMixin, NoSocketsTestCase):
    def test_create(self, mock_esi):
        """can create skill queue from scratch"""
        mock_esi.client = esi_client_stub

        self.character_1001.update_skill_queue()
        self.assertEqual(self.character_1001.skillqueue.count(), 3)

        entry = self.character_1001.skillqueue.get(queue_position=0)
        self.assertEqual(entry.eve_type, EveType.objects.get(id=24311))
        self.assertEqual(entry.finish_date, parse_datetime("2016-06-29T10:47:00Z"))
        self.assertEqual(entry.finished_level, 3)
        self.assertEqual(entry.start_date, parse_datetime("2016-06-29T10:46:00Z"))

        entry = self.character_1001.skillqueue.get(queue_position=1)
        self.assertEqual(entry.eve_type, EveType.objects.get(id=24312))
        self.assertEqual(entry.finish_date, parse_datetime("2016-07-15T10:47:00Z"))
        self.assertEqual(entry.finished_level, 4)
        self.assertEqual(entry.level_end_sp, 1000)
        self.assertEqual(entry.level_start_sp, 100)
        self.assertEqual(entry.start_date, parse_datetime("2016-06-29T10:47:00Z"))
        self.assertEqual(entry.training_start_sp, 50)

        entry = self.character_1001.skillqueue.get(queue_position=2)
        self.assertEqual(entry.eve_type, EveType.objects.get(id=24312))
        self.assertEqual(entry.finished_level, 5)

    def test_update_1(self, mock_esi):
        """can update existing skill queue"""
        mock_esi.client = esi_client_stub
        self.character_1001.skillqueue.create(
            queue_position=0,
            eve_type=EveType.objects.get(id=24311),
            finish_date=now() + dt.timedelta(days=1),
            finished_level=4,
            start_date=now() - dt.timedelta(days=1),
        )

        self.character_1001.update_skill_queue()
        self.assertEqual(self.character_1001.skillqueue.count(), 3)

        entry = self.character_1001.skillqueue.get(queue_position=0)
        self.assertEqual(entry.eve_type, EveType.objects.get(id=24311))
        self.assertEqual(entry.finish_date, parse_datetime("2016-06-29T10:47:00Z"))
        self.assertEqual(entry.finished_level, 3)
        self.assertEqual(entry.start_date, parse_datetime("2016-06-29T10:46:00Z"))

    def test_skip_update_1(self, mock_esi):
        """when ESI data has not changed, then skip update"""
        mock_esi.client = esi_client_stub

        self.character_1001.update_skill_queue()
        entry = self.character_1001.skillqueue.get(queue_position=0)
        entry.finished_level = 4
        entry.save()

        self.character_1001.update_skill_queue()
        entry = self.character_1001.skillqueue.get(queue_position=0)
        self.assertEqual(entry.finished_level, 4)

    def test_skip_update_2(self, mock_esi):
        """when ESI data has not changed and update is forced, then do update"""
        mock_esi.client = esi_client_stub

        self.character_1001.update_skill_queue()
        entry = self.character_1001.skillqueue.get(queue_position=0)
        entry.finished_level = 4
        entry.save()

        self.character_1001.update_skill_queue(force_update=True)
        entry = self.character_1001.skillqueue.get(queue_position=0)
        self.assertEqual(entry.finished_level, 3)


@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
@patch(MODELS_PATH + ".character.esi")
class TestCharacterUpdateWalletJournal(CharacterUpdateTestDataMixin, NoSocketsTestCase):
    def test_update_wallet_balance(self, mock_esi):
        mock_esi.client = esi_client_stub

        self.character_1001.update_wallet_balance()
        self.assertEqual(self.character_1001.wallet_balance.total, 123456789)

    @patch(MODELS_PATH + ".character.MEMBERAUDIT_DATA_RETENTION_LIMIT", None)
    def test_update_wallet_journal_1(self, mock_esi):
        """can create wallet journal entry from scratch"""
        mock_esi.client = esi_client_stub

        self.character_1001.update_wallet_journal()

        self.assertSetEqual(
            set(self.character_1001.wallet_journal.values_list("entry_id", flat=True)),
            {89, 91},
        )
        obj = self.character_1001.wallet_journal.get(entry_id=89)
        self.assertEqual(obj.amount, -100_000)
        self.assertEqual(float(obj.balance), 500_000.43)
        self.assertEqual(obj.context_id, 4)
        self.assertEqual(obj.context_id_type, obj.CONTEXT_ID_TYPE_CONTRACT_ID)
        self.assertEqual(obj.date, parse_datetime("2018-02-23T14:31:32Z"))
        self.assertEqual(obj.description, "Contract Deposit")
        self.assertEqual(obj.first_party.id, 2001)
        self.assertEqual(obj.reason, "just for fun")
        self.assertEqual(obj.ref_type, "contract_deposit")
        self.assertEqual(obj.second_party.id, 2002)

        obj = self.character_1001.wallet_journal.get(entry_id=91)
        self.assertEqual(
            obj.ref_type, "agent_mission_time_bonus_reward_corporation_tax"
        )

    @patch(MODELS_PATH + ".character.MEMBERAUDIT_DATA_RETENTION_LIMIT", None)
    def test_update_wallet_journal_2(self, mock_esi):
        """can add entry to existing wallet journal"""
        mock_esi.client = esi_client_stub
        CharacterWalletJournalEntry.objects.create(
            character=self.character_1001,
            entry_id=1,
            amount=1_000_000,
            balance=10_000_000,
            context_id_type=CharacterWalletJournalEntry.CONTEXT_ID_TYPE_UNDEFINED,
            date=now(),
            description="dummy",
            first_party=EveEntity.objects.get(id=1001),
            second_party=EveEntity.objects.get(id=1002),
        )

        self.character_1001.update_wallet_journal()

        self.assertSetEqual(
            set(self.character_1001.wallet_journal.values_list("entry_id", flat=True)),
            {1, 89, 91},
        )

        obj = self.character_1001.wallet_journal.get(entry_id=89)
        self.assertEqual(obj.amount, -100_000)
        self.assertEqual(float(obj.balance), 500_000.43)
        self.assertEqual(obj.context_id, 4)
        self.assertEqual(obj.context_id_type, obj.CONTEXT_ID_TYPE_CONTRACT_ID)
        self.assertEqual(obj.date, parse_datetime("2018-02-23T14:31:32Z"))
        self.assertEqual(obj.description, "Contract Deposit")
        self.assertEqual(obj.first_party.id, 2001)
        self.assertEqual(obj.ref_type, "contract_deposit")
        self.assertEqual(obj.second_party.id, 2002)

    @patch(MODELS_PATH + ".character.MEMBERAUDIT_DATA_RETENTION_LIMIT", None)
    def test_update_wallet_journal_3(self, mock_esi):
        """does not update existing entries"""
        mock_esi.client = esi_client_stub
        CharacterWalletJournalEntry.objects.create(
            character=self.character_1001,
            entry_id=89,
            amount=1_000_000,
            balance=10_000_000,
            context_id_type=CharacterWalletJournalEntry.CONTEXT_ID_TYPE_UNDEFINED,
            date=now(),
            description="dummy",
            first_party=EveEntity.objects.get(id=1001),
            second_party=EveEntity.objects.get(id=1002),
        )

        self.character_1001.update_wallet_journal()

        self.assertSetEqual(
            set(self.character_1001.wallet_journal.values_list("entry_id", flat=True)),
            {89, 91},
        )
        obj = self.character_1001.wallet_journal.get(entry_id=89)
        self.assertEqual(obj.amount, 1_000_000)
        self.assertEqual(float(obj.balance), 10_000_000)
        self.assertEqual(
            obj.context_id_type, CharacterWalletJournalEntry.CONTEXT_ID_TYPE_UNDEFINED
        )
        self.assertEqual(obj.description, "dummy")
        self.assertEqual(obj.first_party.id, 1001)
        self.assertEqual(obj.second_party.id, 1002)

    @patch(MODELS_PATH + ".character.MEMBERAUDIT_DATA_RETENTION_LIMIT", 10)
    def test_update_wallet_journal_4(self, mock_esi):
        """When new wallet entry is older than retention limit, then do not store it"""
        mock_esi.client = esi_client_stub

        with patch(MODELS_PATH + ".character.now") as mock_now:
            mock_now.return_value = dt.datetime(2018, 3, 11, 20, 5, tzinfo=utc)
            self.character_1001.update_wallet_journal()

        self.assertSetEqual(
            set(self.character_1001.wallet_journal.values_list("entry_id", flat=True)),
            {91},
        )

    @patch(MODELS_PATH + ".character.MEMBERAUDIT_DATA_RETENTION_LIMIT", 20)
    def test_update_wallet_journal_5(self, mock_esi):
        """When wallet existing entry is older than retention limit, then delete it"""
        mock_esi.client = esi_client_stub
        CharacterWalletJournalEntry.objects.create(
            character=self.character_1001,
            entry_id=55,
            amount=1_000_000,
            balance=10_000_000,
            context_id_type=CharacterWalletJournalEntry.CONTEXT_ID_TYPE_UNDEFINED,
            date=dt.datetime(2018, 2, 11, 20, 5, tzinfo=utc),
            description="dummy",
            first_party=EveEntity.objects.get(id=1001),
            second_party=EveEntity.objects.get(id=1002),
        )

        with patch(MODELS_PATH + ".character.now") as mock_now:
            mock_now.return_value = dt.datetime(2018, 3, 11, 20, 5, tzinfo=utc)
            self.character_1001.update_wallet_journal()

        self.assertSetEqual(
            set(self.character_1001.wallet_journal.values_list("entry_id", flat=True)),
            {89, 91},
        )


@patch(MODELS_PATH + ".character.esi")
class TestCharacterUpdateWalletTransaction(
    CharacterUpdateTestDataMixin, NoSocketsTestCase
):
    def test_should_add_wallet_transactions_from_scratch(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        # when
        with patch(MODELS_PATH + ".character.MEMBERAUDIT_DATA_RETENTION_LIMIT", None):
            self.character_1001.update_wallet_transactions()
        # then
        self.assertSetEqual(
            set(
                self.character_1001.wallet_transactions.values_list(
                    "transaction_id", flat=True
                )
            ),
            {42},
        )
        obj = self.character_1001.wallet_transactions.get(transaction_id=42)
        self.assertEqual(obj.client, EveEntity.objects.get(id=1003))
        self.assertEqual(obj.date, parse_datetime("2016-10-24T09:00:00Z"))
        self.assertTrue(obj.is_buy)
        self.assertTrue(obj.is_personal)
        self.assertIsNone(obj.journal_ref)
        self.assertEqual(obj.location, Location.objects.get(id=60003760))
        self.assertEqual(obj.quantity, 3)
        self.assertEqual(obj.eve_type, EveType.objects.get(id=603))
        self.assertEqual(float(obj.unit_price), 450000.99)

    def test_should_add_wallet_transactions_from_scratch_with_journal_ref(
        self, mock_esi
    ):
        # given
        mock_esi.client = esi_client_stub
        journal_entry = CharacterWalletJournalEntry.objects.create(
            character=self.character_1001,
            entry_id=67890,
            amount=450000.99,
            balance=10_000_000,
            context_id_type=CharacterWalletJournalEntry.CONTEXT_ID_TYPE_UNDEFINED,
            date=parse_datetime("2016-10-24T09:00:00Z"),
            description="dummy",
            first_party=EveEntity.objects.get(id=1001),
            second_party=EveEntity.objects.get(id=1003),
        )
        # when
        with patch(MODELS_PATH + ".character.MEMBERAUDIT_DATA_RETENTION_LIMIT", None):
            self.character_1001.update_wallet_transactions()
        # then
        self.assertSetEqual(
            set(
                self.character_1001.wallet_transactions.values_list(
                    "transaction_id", flat=True
                )
            ),
            {42},
        )
        obj = self.character_1001.wallet_transactions.get(transaction_id=42)
        self.assertEqual(obj.journal_ref, journal_entry)


# class TestCharacterMailingList(CharacterUpdateTestDataMixin, NoSocketsTestCase):
#     def test_name_plus_1(self):
#         """when mailing list has name then return it's name"""
#         mailing_list = CharacterMailingList(
#             self.character_1001, list_id=99, name="Avengers Talk"
#         )
#         self.assertEqual(mailing_list.name_plus, "Avengers Talk")

#     def test_name_plus_2(self):
#         """when mailing list has no name then return a generic name"""
#         mailing_list = CharacterMailingList(self.character_1001, list_id=99)
#         self.assertEqual(mailing_list.name_plus, "Mailing list #99")
