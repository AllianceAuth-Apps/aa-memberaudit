import datetime as dt
from unittest.mock import patch

from bravado.exception import HTTPNotFound
from pytz import utc

from django.test import TestCase, override_settings
from django.utils.dateparse import parse_datetime
from eveuniverse.models import EveEntity

from app_utils.esi import EsiStatus
from app_utils.esi_testing import BravadoResponseStub, build_http_error
from app_utils.testing import NoSocketsTestCase

from memberaudit.core.xml_converter import eve_xml_to_html

from ...models import CharacterMail, CharacterMailLabel, CharacterShip, MailEntity
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

    @patch(MODELS_PATH + ".character.data_retention_cutoff", lambda: None)
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

    @patch(MODELS_PATH + ".character.data_retention_cutoff", lambda: None)
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

    @patch(MODELS_PATH + ".character.data_retention_cutoff", lambda: None)
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

    @patch(MODELS_PATH + ".character.data_retention_cutoff", lambda: None)
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

    @patch(
        MODELS_PATH + ".character.data_retention_cutoff",
        lambda: dt.datetime(2015, 9, 20, 20, 5, tzinfo=utc) - dt.timedelta(days=15),
    )
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

    @patch(
        MODELS_PATH + ".character.data_retention_cutoff",
        lambda: dt.datetime(2015, 9, 20, 20, 5, tzinfo=utc) - dt.timedelta(days=15),
    )
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
