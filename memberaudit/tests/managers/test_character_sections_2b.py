import datetime as dt
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils.dateparse import parse_datetime
from eveuniverse.models import EveEntity, EveSolarSystem

from app_utils.esi_testing import build_http_error
from app_utils.testing import NoSocketsTestCase

from memberaudit.core.xml_converter import eve_xml_to_html
from memberaudit.models import (
    CharacterLocation,
    CharacterLoyaltyEntry,
    CharacterMail,
    CharacterMailLabel,
    Location,
    MailEntity,
)
from memberaudit.tests.testdata.esi_client_stub import esi_client_stub, esi_stub
from memberaudit.tests.testdata.factories import (
    create_character_mail,
    create_character_mail_label,
    create_mail_entity_from_eve_entity,
    create_mailing_list,
)
from memberaudit.tests.testdata.factories_2 import CharacterLocationFactory
from memberaudit.tests.testdata.load_entities import load_entities
from memberaudit.tests.testdata.load_eveuniverse import load_eveuniverse
from memberaudit.tests.testdata.load_locations import load_locations
from memberaudit.tests.utils import create_memberaudit_character

MODULE_PATH = "memberaudit.managers.character_sections_2"


@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
@patch(MODULE_PATH + ".esi")
class TestCharacterLocationManager(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        load_locations()
        cls.character_1001 = create_memberaudit_character(1001)
        cls.character_1002 = create_memberaudit_character(1002)
        cls.amamake = EveSolarSystem.objects.get(id=30002537)
        cls.jita = EveSolarSystem.objects.get(id=30000142)
        cls.jita_44 = Location.objects.get(id=60003760)
        cls.structure_1 = Location.objects.get(id=1000000000001)

    def test_should_create_location_from_scratch_for_station(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        # when
        CharacterLocation.objects.update_or_create_esi(self.character_1001)
        # then
        self.assertEqual(self.character_1001.location.eve_solar_system, self.jita)
        self.assertEqual(self.character_1001.location.location, self.jita_44)

    def test_should_create_location_from_scratch_for_structure(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        # when
        CharacterLocation.objects.update_or_create_esi(self.character_1002)
        # then
        self.assertEqual(self.character_1002.location.eve_solar_system, self.amamake)
        self.assertEqual(self.character_1002.location.location, self.structure_1)

    def test_should_create_location_from_scratch_for_solar_system(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        character_1003 = create_memberaudit_character(1003)
        # when
        CharacterLocation.objects.update_or_create_esi(character_1003)
        # then
        self.assertEqual(character_1003.location.eve_solar_system, self.amamake)
        self.assertEqual(
            character_1003.location.location.eve_solar_system, self.amamake
        )

    def test_should_update_location(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        CharacterLocationFactory(
            character=self.character_1001,
            eve_solar_system=self.amamake,
            location=self.structure_1,
        )
        # when
        CharacterLocation.objects.update_or_create_esi(self.character_1001)
        # then
        self.character_1001.refresh_from_db()
        self.assertEqual(self.character_1001.location.eve_solar_system, self.jita)
        self.assertEqual(self.character_1001.location.location, self.jita_44)


@patch(MODULE_PATH + ".esi")
class TestCharacterLoyaltyEntryManager(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        cls.character_1001 = create_memberaudit_character(1001)
        cls.character_1002 = create_memberaudit_character(1002)
        cls.corporation_2001 = EveEntity.objects.get(id=2001)
        cls.corporation_2002 = EveEntity.objects.get(id=2002)

    def test_can_create_from_scratch(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        # when
        CharacterLoyaltyEntry.objects.update_or_create_esi(self.character_1001)
        # then
        self.assertEqual(self.character_1001.loyalty_entries.count(), 1)
        obj = self.character_1001.loyalty_entries.get(corporation_id=2002)
        self.assertEqual(obj.loyalty_points, 100)

    def test_can_update_existing_entries(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        self.character_1001.loyalty_entries.create(
            corporation=self.corporation_2001, loyalty_points=200
        )
        # when
        CharacterLoyaltyEntry.objects.update_or_create_esi(self.character_1001)
        # then
        self.assertEqual(self.character_1001.loyalty_entries.count(), 1)
        obj = self.character_1001.loyalty_entries.get(corporation=self.corporation_2002)
        self.assertEqual(obj.loyalty_points, 100)

    def test_can_remove_obsolete_entries(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        obsolete_entry = self.character_1001.loyalty_entries.create(
            corporation=EveEntity.objects.get(id=2101), loyalty_points=200
        )

        # when
        CharacterLoyaltyEntry.objects.update_or_create_esi(self.character_1001)

        # then
        self.assertEqual(self.character_1001.loyalty_entries.count(), 1)
        obj = self.character_1001.loyalty_entries.get(corporation=self.corporation_2002)
        self.assertEqual(obj.loyalty_points, 100)

        self.assertFalse(
            self.character_1001.loyalty_entries.filter(
                corporation_id=obsolete_entry.corporation_id
            ).exists()
        )

    def test_should_skip_update_when_no_change(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        CharacterLoyaltyEntry.objects.update_or_create_esi(self.character_1001)
        obj = self.character_1001.loyalty_entries.get(corporation=self.corporation_2002)
        obj.loyalty_points = 200
        obj.save()
        # when
        CharacterLoyaltyEntry.objects.update_or_create_esi(self.character_1001)
        # then
        obj = self.character_1001.loyalty_entries.get(corporation=self.corporation_2002)
        self.assertEqual(obj.loyalty_points, 200)

    def test_should_always_update_when_forced(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        CharacterLoyaltyEntry.objects.update_or_create_esi(self.character_1001)
        obj = self.character_1001.loyalty_entries.get(corporation=self.corporation_2002)
        obj.loyalty_points = 200
        obj.save()
        # when
        CharacterLoyaltyEntry.objects.update_or_create_esi(
            self.character_1001, force_update=True
        )
        # then
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
        CharacterLoyaltyEntry.objects.update_or_create_esi(self.character_1001)
        # then
        self.assertEqual(self.character_1001.loyalty_entries.count(), 1)
        obj = self.character_1001.loyalty_entries.get(corporation=self.corporation_2001)
        self.assertEqual(obj.loyalty_points, 100)


@patch(MODULE_PATH + ".esi")
class TestUpdateCharacterMailHeaders(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        load_locations()
        cls.character_1001 = create_memberaudit_character(1001)
        cls.character_1002 = create_memberaudit_character(1002)
        cls.corporation_2001 = EveEntity.objects.get(id=2001)
        cls.corporation_2002 = EveEntity.objects.get(id=2002)

    @patch(MODULE_PATH + ".data_retention_cutoff", lambda: None)
    def test_can_create_new_mail_from_scratch(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        create_mail_entity_from_eve_entity(1002)
        create_mailing_list(id=9001)
        create_character_mail_label(character=self.character_1001, label_id=3)

        # when
        result = self.character_1001.update_mail_headers()

        # then
        self.assertTrue(result.is_changed)
        self.assertTrue(result.is_updated)

        mail_ids = set(self.character_1001.mails.values_list("mail_id", flat=True))
        self.assertSetEqual(mail_ids, {1, 2, 3})
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

    @patch(MODULE_PATH + ".data_retention_cutoff", lambda: None)
    def test_should_skip_update_when_no_change(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        create_mail_entity_from_eve_entity(1002)
        create_mailing_list(id=9001)
        create_character_mail_label(character=self.character_1001, label_id=3)
        self.character_1001.update_mail_headers()
        obj = self.character_1001.mails.get(mail_id=1)
        obj.is_read = False
        obj.save()

        # when
        result = self.character_1001.update_mail_headers()

        # then
        self.assertFalse(result.is_changed)
        self.assertFalse(result.is_updated)

        obj = self.character_1001.mails.get(mail_id=1)
        self.assertFalse(obj.is_read)

    @patch(MODULE_PATH + ".data_retention_cutoff", lambda: None)
    def test_should_always_update_when_forced(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        create_mail_entity_from_eve_entity(1002)
        create_mailing_list(id=9001)
        create_character_mail_label(character=self.character_1001, label_id=3)
        self.character_1001.update_mail_headers()
        obj = self.character_1001.mails.get(mail_id=1)
        obj.is_read = False
        obj.save()

        # when
        result = self.character_1001.update_mail_headers(force_update=True)

        # then
        self.assertFalse(result.is_changed)
        self.assertTrue(result.is_updated)

        obj = self.character_1001.mails.get(mail_id=1)
        self.assertTrue(obj.is_read)

    @patch(
        MODULE_PATH + ".data_retention_cutoff",
        lambda: dt.datetime(2015, 9, 20, 20, 5, tzinfo=dt.timezone.utc)
        - dt.timedelta(days=15),
    )
    def test_update_mail_headers_6(self, mock_esi):
        """when data retention limit is set, then only fetch mails within that limit"""
        mock_esi.client = esi_client_stub
        create_mail_entity_from_eve_entity(1002)
        create_mailing_list(id=9001)
        create_character_mail_label(character=self.character_1001, label_id=3)

        self.character_1001.update_mail_headers()

        mail_ids = set(self.character_1001.mails.values_list("mail_id", flat=True))
        self.assertSetEqual(mail_ids, {2, 3})

    @patch(
        MODULE_PATH + ".data_retention_cutoff",
        lambda: dt.datetime(2015, 9, 20, 20, 5, tzinfo=dt.timezone.utc)
        - dt.timedelta(days=15),
    )
    def test_update_mail_headers_7(self, mock_esi):
        """when data retention limit is set, then remove old data beyond that limit"""
        # given
        mock_esi.client = esi_client_stub
        sender, _ = MailEntity.objects.update_or_create_from_eve_entity_id(id=1002)
        create_character_mail(
            character=self.character_1001,
            mail_id=99,
            sender=sender,
            subject="Mail Old",
            timestamp=parse_datetime("2015-09-02T14:02:00Z"),
            is_read=False,
        )

        create_mail_entity_from_eve_entity(1002)
        create_mailing_list(id=9001)
        create_character_mail_label(character=self.character_1001, label_id=3)

        # when
        self.character_1001.update_mail_headers()

        # then
        mail_ids = set(self.character_1001.mails.values_list("mail_id", flat=True))
        self.assertSetEqual(mail_ids, {2, 3})


@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
@patch(MODULE_PATH + ".esi")
class TestUpdateCharacterMailBody(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        load_locations()
        cls.character_1001 = create_memberaudit_character(1001)
        cls.character_1002 = create_memberaudit_character(1002)
        cls.corporation_2001 = EveEntity.objects.get(id=2001)
        cls.corporation_2002 = EveEntity.objects.get(id=2002)

    def test_should_update_existing_mail_body(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        sender = create_mail_entity_from_eve_entity(1002)
        mail = create_character_mail(
            character=self.character_1001,
            mail_id=1,
            sender=sender,
            subject="Mail 1",
            body="Update me",
            is_read=False,
            timestamp=parse_datetime("2015-09-30T16:07:00Z"),
        )
        recipient_1001 = create_mail_entity_from_eve_entity(1001)
        recipient_9001 = create_mailing_list(
            id=9001, category=MailEntity.Category.MAILING_LIST, name="Dummy 2"
        )
        mail.recipients.add(recipient_1001, recipient_9001)

        # when
        result = self.character_1001.update_mail_body(mail)

        # then
        self.assertTrue(result.is_changed)
        self.assertTrue(result.is_updated)
        obj = self.character_1001.mails.get(mail_id=1)
        self.assertEqual(obj.body, "blah blah blah 😓")

    def test_should_not_update_when_body_has_not_changed(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        sender = create_mail_entity_from_eve_entity(1002)
        mail = create_character_mail(
            character=self.character_1001,
            mail_id=1,
            sender=sender,
            subject="Mail 1",
            body="blah blah blah 😓",
            is_read=False,
            timestamp=parse_datetime("2015-09-30T16:07:00Z"),
        )
        recipient_1001 = create_mail_entity_from_eve_entity(1001)
        recipient_9001 = create_mailing_list(
            id=9001, category=MailEntity.Category.MAILING_LIST, name="Dummy 2"
        )
        mail.recipients.add(recipient_1001, recipient_9001)

        # when
        result = self.character_1001.update_mail_body(mail)

        # then
        self.assertFalse(result.is_changed)
        self.assertFalse(result.is_updated)
        obj = self.character_1001.mails.get(mail_id=1)
        self.assertEqual(obj.body, "blah blah blah 😓")

    def test_should_update_when_body_has_not_changed_but_forced(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        sender = create_mail_entity_from_eve_entity(1002)
        mail = create_character_mail(
            character=self.character_1001,
            mail_id=1,
            sender=sender,
            subject="Mail 1",
            body="blah blah blah 😓",
            is_read=False,
            timestamp=parse_datetime("2015-09-30T16:07:00Z"),
        )
        recipient_1001 = create_mail_entity_from_eve_entity(1001)
        recipient_9001 = create_mailing_list(
            id=9001, category=MailEntity.Category.MAILING_LIST, name="Dummy 2"
        )
        mail.recipients.add(recipient_1001, recipient_9001)

        # when
        result = self.character_1001.update_mail_body(mail, force_update=True)

        # then
        self.assertFalse(result.is_changed)
        self.assertTrue(result.is_updated)
        obj = self.character_1001.mails.get(mail_id=1)
        self.assertEqual(obj.body, "blah blah blah 😓")

    @patch(MODULE_PATH + ".eve_xml_to_html")
    def test_should_update_mail_body_from_scratch(self, mock_eve_xml_to_html, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        mock_eve_xml_to_html.side_effect = lambda x: eve_xml_to_html(x)
        sender = create_mail_entity_from_eve_entity(1002)
        mail = create_character_mail(
            character=self.character_1001,
            mail_id=2,
            sender=sender,
            subject="Mail 1",
            is_read=False,
            timestamp=parse_datetime("2015-09-30T16:07:00Z"),
        )
        recipient_1 = create_mail_entity_from_eve_entity(1001)
        mail.recipients.add(recipient_1)

        # when
        result = self.character_1001.update_mail_body(mail)

        # then
        self.assertTrue(result.is_changed)
        self.assertTrue(result.is_updated)
        obj = self.character_1001.mails.get(mail_id=2)
        self.assertTrue(obj.body)
        self.assertTrue(mock_eve_xml_to_html.called)

    def test_should_delete_mail_header_when_fetching_body_returns_404(self, mock_esi):
        # given
        mock_esi.client.Mail.get_characters_character_id_mail_mail_id.side_effect = (
            build_http_error(404, "Test")
        )
        sender = create_mail_entity_from_eve_entity(1002)
        mail = create_character_mail(
            character=self.character_1001,
            mail_id=1,
            sender=sender,
            subject="Mail 1",
            is_read=False,
            timestamp=parse_datetime("2015-09-30T16:07:00Z"),
        )
        recipient_1001 = create_mail_entity_from_eve_entity(1001)
        recipient_9001 = create_mailing_list(
            id=9001, category=MailEntity.Category.MAILING_LIST, name="Dummy 2"
        )
        mail.recipients.add(recipient_1001, recipient_9001)

        # when
        result = self.character_1001.update_mail_body(mail)

        # then
        self.assertTrue(result.is_changed)
        self.assertTrue(result.is_updated)
        self.assertFalse(self.character_1001.mails.filter(mail_id=1).exists())

    @patch("memberaudit.models.MailEntity.objects.get_or_create_esi_async")
    def test_can_preload_mail_senders(self, mock_get_or_create_esi_async, mock_esi):
        # given
        create_mailing_list(id=9001)
        headers = {1: {"from": 9001, "mail_id": 1}, 2: {"from": 9002, "mail_id": 2}}
        # when
        CharacterMail.objects._preload_mail_senders(headers)
        # then
        self.assertTrue(mock_get_or_create_esi_async.called)
        mail_entity_ids = {
            o[1]["id"] for o in mock_get_or_create_esi_async.call_args_list
        }
        self.assertSetEqual(mail_entity_ids, {9002})


@patch(MODULE_PATH + ".esi", esi_stub)
class TestCharacterMailLabelManager(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities()
        cls.character_1001 = create_memberaudit_character(1001)

    def test_should_return_all_known_labels_1(self):
        label_1 = create_character_mail_label(character=self.character_1001, label_id=1)
        label_2 = create_character_mail_label(character=self.character_1001, label_id=2)
        labels = CharacterMailLabel.objects.get_all_labels()
        self.assertDictEqual(
            labels, {label_1.label_id: label_1, label_2.label_id: label_2}
        )

    def test_should_return_all_known_labels_2(self):
        labels = CharacterMailLabel.objects.get_all_labels()
        self.assertDictEqual(labels, {})

    def test_should_create_labels_from_scratch(self):
        # when
        result = self.character_1001.update_mail_labels()

        # then
        self.assertTrue(result.is_changed)
        self.assertTrue(result.is_updated)
        self.assertEqual(self.character_1001.unread_mail_count.total, 5)
        label_ids = set(
            self.character_1001.mail_labels.values_list("label_id", flat=True)
        )
        self.assertSetEqual(label_ids, {3, 17})

        obj = self.character_1001.mail_labels.get(label_id=3)
        self.assertEqual(obj.name, "PINK")
        self.assertEqual(obj.unread_count, 4)
        self.assertEqual(obj.color, "#660066")

        obj = self.character_1001.mail_labels.get(label_id=17)
        self.assertEqual(obj.name, "WHITE")
        self.assertEqual(obj.unread_count, 1)
        self.assertEqual(obj.color, "#ffffff")

    def test_should_remove_obsolete_labels(self):
        # given
        create_character_mail_label(
            character=self.character_1001, label_id=666, name="Obsolete"
        )

        # when
        result = self.character_1001.update_mail_labels()

        # then
        self.assertTrue(result.is_changed)
        self.assertTrue(result.is_updated)
        label_ids = set(
            self.character_1001.mail_labels.values_list("label_id", flat=True)
        )
        self.assertSetEqual(label_ids, {3, 17})

    def test_should_update_existing_labels(self):
        # given
        create_character_mail_label(
            character=self.character_1001,
            label_id=3,
            name="Update me",
            unread_count=0,
            color=0,
        )

        # when
        result = self.character_1001.update_mail_labels()

        # then
        self.assertTrue(result.is_changed)
        self.assertTrue(result.is_updated)
        self.assertSetEqual(
            set(self.character_1001.mail_labels.values_list("label_id", flat=True)),
            {3, 17},
        )

        obj = self.character_1001.mail_labels.get(label_id=3)
        self.assertEqual(obj.name, "PINK")
        self.assertEqual(obj.unread_count, 4)
        self.assertEqual(obj.color, "#660066")

    def test_should_skip_update_when_esi_data_has_not_changed(self):
        # given
        self.character_1001.update_mail_labels()
        obj = self.character_1001.mail_labels.get(label_id=3)
        obj.name = "MAGENTA"
        obj.save()

        # when
        result = self.character_1001.update_mail_labels()

        # then
        self.assertFalse(result.is_changed)
        self.assertFalse(result.is_updated)
        obj = self.character_1001.mail_labels.get(label_id=3)
        self.assertEqual(obj.name, "MAGENTA")

    def test_should_update_when_esi_data_has_not_changed_but_forced(self):
        # given
        self.character_1001.update_mail_labels()
        obj = self.character_1001.mail_labels.get(label_id=3)
        obj.name = "MAGENTA"
        obj.save()

        # then
        result = self.character_1001.update_mail_labels(force_update=True)

        self.assertFalse(result.is_changed)
        self.assertTrue(result.is_updated)
        obj = self.character_1001.mail_labels.get(label_id=3)
        self.assertEqual(obj.name, "PINK")
