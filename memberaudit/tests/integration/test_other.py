from unittest.mock import patch

from django.utils.dateparse import parse_datetime
from eveuniverse.models import EveEntity

from app_utils.testing import NoSocketsTestCase

from memberaudit.models import MailEntity
from memberaudit.tests.testdata.esi_client_stub import esi_client_stub
from memberaudit.tests.testdata.factories import (
    create_character_mail,
    create_mailing_list,
)
from memberaudit.tests.testdata.load_entities import load_entities
from memberaudit.tests.utils import create_memberaudit_character

MANAGERS_PATH = "memberaudit.managers"
MODELS_PATH = "memberaudit.models"
TASKS_PATH = "memberaudit.tasks"


@patch(MANAGERS_PATH + ".character_sections_2.esi")
@patch(MANAGERS_PATH + ".general.esi")
class TestCharacterMailUpdate(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities()
        cls.character = create_memberaudit_character(1001)

    @staticmethod
    def stub_eve_entity_get_or_create_esi(id, *args, **kwargs):
        """will return EveEntity if it exists else None, False"""
        try:
            obj = EveEntity.objects.get(id=id)
            return obj, True
        except EveEntity.DoesNotExist:
            return None, False

    @patch(MANAGERS_PATH + ".character_sections_2.data_retention_cutoff", lambda: None)
    @patch(MANAGERS_PATH + ".character_sections_2.EveEntity.objects.get_or_create_esi")
    def test_should_update_existing_mail_headers(
        self,
        mock_eve_entity,
        mock_esi_character,
        mock_esi_sections,
    ):
        # given
        mock_esi_character.client = esi_client_stub
        mock_esi_sections.client = esi_client_stub
        mock_eve_entity.side_effect = self.stub_eve_entity_get_or_create_esi
        sender, _ = MailEntity.objects.update_or_create_from_eve_entity_id(id=1002)
        mail = create_character_mail(
            character=self.character,
            mail_id=1,
            sender=sender,
            subject="Mail 1",
            body="My body text",
            timestamp=parse_datetime("2015-09-05T16:07:00Z"),
            is_read=False,  # to be updated
        )
        recipient_1, _ = MailEntity.objects.update_or_create_from_eve_entity_id(id=1001)
        recipient_2 = create_mailing_list()
        mail.recipients.set([recipient_1, recipient_2])

        self.character.update_mailing_lists()
        self.character.update_mail_labels()

        label = self.character.mail_labels.get(label_id=17)
        mail.labels.add(label)  # to be updated

        # when
        self.character.update_mail_headers()

        # then
        self.assertSetEqual(
            set(self.character.mails.values_list("mail_id", flat=True)),
            {1, 2, 3},
        )

        obj = self.character.mails.get(mail_id=1)
        self.assertEqual(obj.sender_id, 1002)
        self.assertTrue(obj.is_read)
        self.assertEqual(obj.subject, "Mail 1")
        self.assertEqual(obj.timestamp, parse_datetime("2015-09-05T16:07:00Z"))
        self.assertEqual(obj.body, "My body text")
        recipient_ids = set(obj.recipients.values_list("id", flat=True))
        self.assertSetEqual(recipient_ids, {recipient_1.id, recipient_2.id})
        label_ids = set(obj.labels.values_list("label_id", flat=True))
        self.assertSetEqual(label_ids, {3})
