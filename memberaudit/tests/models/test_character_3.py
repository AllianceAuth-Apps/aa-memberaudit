from unittest.mock import patch

from django.utils.dateparse import parse_datetime
from eveuniverse.models import EveEntity

from app_utils.esi import EsiStatus
from app_utils.testing import NoSocketsTestCase

from ...models import CharacterMail, MailEntity
from ..testdata.esi_client_stub import esi_client_stub
from ..utils import CharacterUpdateTestDataMixin

MODELS_PATH = "memberaudit.models"
MANAGERS_PATH = "memberaudit.managers"
TASKS_PATH = "memberaudit.tasks"


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


@patch(MANAGERS_PATH + ".sections.esi")
@patch(MANAGERS_PATH + ".general.esi")
class TestCharacterMailUpdateIntegration(
    CharacterUpdateTestDataMixin, NoSocketsTestCase
):
    @staticmethod
    def stub_eve_entity_get_or_create_esi(id, *args, **kwargs):
        """will return EveEntity if it exists else None, False"""
        try:
            obj = EveEntity.objects.get(id=id)
            return obj, True
        except EveEntity.DoesNotExist:
            return None, False

    @patch(MANAGERS_PATH + ".sections.data_retention_cutoff", lambda: None)
    @patch(MANAGERS_PATH + ".general.fetch_esi_status")
    @patch(MANAGERS_PATH + ".sections.EveEntity.objects.get_or_create_esi")
    def test_update_mail_headers_2(
        self,
        mock_eve_entity,
        mock_fetch_esi_status,
        mock_esi_character,
        mock_esi_sections,
    ):
        """can update existing mail"""
        mock_esi_character.client = esi_client_stub
        mock_esi_sections.client = esi_client_stub
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
