import datetime as dt
from unittest.mock import patch

from pytz import utc

from django.test import override_settings
from django.utils.dateparse import parse_datetime
from django.utils.timezone import now
from eveuniverse.models import EveEntity, EveType

from app_utils.testing import NoSocketsTestCase

from ...core.xml_converter import eve_xml_to_html
from ...models import (
    CharacterContact,
    CharacterContactLabel,
    CharacterContract,
    CharacterContractBid,
    CharacterDetails,
)
from ..testdata.esi_client_stub import esi_client_stub
from ..utils import create_memberaudit_character
from .utils import CharacterUpdateTestDataMixin

MODELS_PATH = "memberaudit.models"
MANAGERS_PATH = "memberaudit.managers"
TASKS_PATH = "memberaudit.tasks"


@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
@patch(MODELS_PATH + ".character.esi")
class TestCharacterUpdateContacts(CharacterUpdateTestDataMixin, NoSocketsTestCase):
    def test_update_contact_labels_1(self, mock_esi):
        """can create new contact labels from scratch"""
        mock_esi.client = esi_client_stub

        self.character_1001.update_contact_labels()
        self.assertEqual(self.character_1001.contact_labels.count(), 2)

        label = self.character_1001.contact_labels.get(label_id=1)
        self.assertEqual(label.name, "friend")

        label = self.character_1001.contact_labels.get(label_id=2)
        self.assertEqual(label.name, "pirate")

    def test_update_contact_labels_2(self, mock_esi):
        """can remove obsolete labels"""
        mock_esi.client = esi_client_stub
        CharacterContactLabel.objects.create(
            character=self.character_1001, label_id=99, name="Obsolete"
        )

        self.character_1001.update_contact_labels()
        self.assertEqual(
            {x.label_id for x in self.character_1001.contact_labels.all()}, {1, 2}
        )

    def test_update_contact_labels_3(self, mock_esi):
        """can update existing labels"""
        mock_esi.client = esi_client_stub
        CharacterContactLabel.objects.create(
            character=self.character_1001, label_id=1, name="Obsolete"
        )

        self.character_1001.update_contact_labels()
        self.assertEqual(
            {x.label_id for x in self.character_1001.contact_labels.all()}, {1, 2}
        )

        label = self.character_1001.contact_labels.get(label_id=1)
        self.assertEqual(label.name, "friend")

    def test_update_contact_labels_4(self, mock_esi):
        """when data from ESI has not changed, then skip update"""
        mock_esi.client = esi_client_stub

        self.character_1001.update_contact_labels()
        label = self.character_1001.contact_labels.get(label_id=1)
        label.name = "foe"
        label.save()

        self.character_1001.update_contact_labels()

        self.assertEqual(self.character_1001.contact_labels.count(), 2)
        label = self.character_1001.contact_labels.get(label_id=1)
        self.assertEqual(label.name, "foe")

    def test_update_contact_labels_5(self, mock_esi):
        """when data from ESI has not changed and update is forced, then do update"""
        mock_esi.client = esi_client_stub

        self.character_1001.update_contact_labels()
        label = self.character_1001.contact_labels.get(label_id=1)
        label.name = "foe"
        label.save()

        self.character_1001.update_contact_labels(force_update=True)

        self.assertEqual(self.character_1001.contact_labels.count(), 2)
        label = self.character_1001.contact_labels.get(label_id=1)
        self.assertEqual(label.name, "friend")

    def test_update_contacts_1(self, mock_esi):
        """can create contacts"""
        mock_esi.client = esi_client_stub
        CharacterContactLabel.objects.create(
            character=self.character_1001, label_id=1, name="friend"
        )
        CharacterContactLabel.objects.create(
            character=self.character_1001, label_id=2, name="pirate"
        )

        self.character_1001.update_contacts()

        self.assertEqual(self.character_1001.contacts.count(), 2)

        obj = self.character_1001.contacts.get(eve_entity_id=1101)
        self.assertEqual(obj.eve_entity.category, EveEntity.CATEGORY_CHARACTER)
        self.assertFalse(obj.is_blocked)
        self.assertTrue(obj.is_watched)
        self.assertEqual(obj.standing, -10)
        self.assertEqual({x.label_id for x in obj.labels.all()}, {2})

        obj = self.character_1001.contacts.get(eve_entity_id=2002)
        self.assertEqual(obj.eve_entity.category, EveEntity.CATEGORY_CORPORATION)
        self.assertFalse(obj.is_blocked)
        self.assertFalse(obj.is_watched)
        self.assertEqual(obj.standing, 5)
        self.assertEqual(obj.labels.count(), 0)

    def test_update_contacts_2(self, mock_esi):
        """can remove obsolete contacts"""
        mock_esi.client = esi_client_stub
        CharacterContactLabel.objects.create(
            character=self.character_1001, label_id=1, name="friend"
        )
        CharacterContactLabel.objects.create(
            character=self.character_1001, label_id=2, name="pirate"
        )
        CharacterContact.objects.create(
            character=self.character_1001,
            eve_entity=EveEntity.objects.get(id=3101),
            standing=-5,
        )

        self.character_1001.update_contacts()

        self.assertEqual(
            {x.eve_entity_id for x in self.character_1001.contacts.all()}, {1101, 2002}
        )

    def test_update_contacts_3(self, mock_esi):
        """can update existing contacts"""
        mock_esi.client = esi_client_stub
        CharacterContactLabel.objects.create(
            character=self.character_1001, label_id=2, name="pirate"
        )
        my_label = CharacterContactLabel.objects.create(
            character=self.character_1001, label_id=1, name="Dummy"
        )
        my_contact = CharacterContact.objects.create(
            character=self.character_1001,
            eve_entity=EveEntity.objects.get(id=1101),
            is_blocked=True,
            is_watched=False,
            standing=-5,
        )
        my_contact.labels.add(my_label)

        self.character_1001.update_contacts()

        obj = self.character_1001.contacts.get(eve_entity_id=1101)
        self.assertEqual(obj.eve_entity.category, EveEntity.CATEGORY_CHARACTER)
        self.assertFalse(obj.is_blocked)
        self.assertTrue(obj.is_watched)
        self.assertEqual(obj.standing, -10)
        self.assertEqual({x.label_id for x in obj.labels.all()}, {2})

    def test_update_contacts_4(self, mock_esi):
        """when ESI data has not changed, then skip update"""
        mock_esi.client = esi_client_stub
        CharacterContactLabel.objects.create(
            character=self.character_1001, label_id=1, name="friend"
        )
        CharacterContactLabel.objects.create(
            character=self.character_1001, label_id=2, name="pirate"
        )

        self.character_1001.update_contacts()
        obj = self.character_1001.contacts.get(eve_entity_id=1101)
        obj.is_watched = False
        obj.save()

        self.character_1001.update_contacts()

        obj = self.character_1001.contacts.get(eve_entity_id=1101)
        self.assertFalse(obj.is_watched)

    def test_update_contacts_5(self, mock_esi):
        """when ESI data has not changed and update is forced, then update"""
        mock_esi.client = esi_client_stub
        CharacterContactLabel.objects.create(
            character=self.character_1001, label_id=1, name="friend"
        )
        CharacterContactLabel.objects.create(
            character=self.character_1001, label_id=2, name="pirate"
        )

        self.character_1001.update_contacts()
        obj = self.character_1001.contacts.get(eve_entity_id=1101)
        obj.is_watched = False
        obj.save()

        self.character_1001.update_contacts(force_update=True)

        obj = self.character_1001.contacts.get(eve_entity_id=1101)
        self.assertTrue(obj.is_watched)


@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
@patch(MODELS_PATH + ".character.esi")
class TestCharacterUpdateContracts(CharacterUpdateTestDataMixin, NoSocketsTestCase):
    @patch(MODELS_PATH + ".character.MEMBERAUDIT_DATA_RETENTION_LIMIT", None)
    def test_update_contracts_1(self, mock_esi):
        """can create new courier contract"""
        mock_esi.client = esi_client_stub

        self.character_1001.update_contract_headers()
        self.assertSetEqual(
            set(self.character_1001.contracts.values_list("contract_id", flat=True)),
            {100000001, 100000002, 100000003},
        )

        obj = self.character_1001.contracts.get(contract_id=100000001)
        self.assertEqual(obj.contract_type, CharacterContract.TYPE_COURIER)
        self.assertEqual(obj.acceptor, EveEntity.objects.get(id=1101))
        self.assertEqual(obj.assignee, EveEntity.objects.get(id=2101))
        self.assertEqual(obj.availability, CharacterContract.AVAILABILITY_PERSONAL)
        self.assertIsNone(obj.buyout)
        self.assertEqual(float(obj.collateral), 550000000.0)
        self.assertEqual(obj.date_accepted, parse_datetime("2019-10-06T13:15:21Z"))
        self.assertEqual(obj.date_completed, parse_datetime("2019-10-07T13:15:21Z"))
        self.assertEqual(obj.date_expired, parse_datetime("2019-10-09T13:15:21Z"))
        self.assertEqual(obj.date_issued, parse_datetime("2019-10-02T13:15:21Z"))
        self.assertEqual(obj.days_to_complete, 3)
        self.assertEqual(obj.end_location, self.structure_1)
        self.assertFalse(obj.for_corporation)
        self.assertEqual(obj.issuer_corporation, EveEntity.objects.get(id=2001))
        self.assertEqual(obj.issuer, EveEntity.objects.get(id=1001))
        self.assertEqual(float(obj.price), 0.0)
        self.assertEqual(float(obj.reward), 500000000.0)
        self.assertEqual(obj.start_location, self.jita_44)
        self.assertEqual(obj.status, CharacterContract.STATUS_IN_PROGRESS)
        self.assertEqual(obj.title, "Test 1")
        self.assertEqual(obj.volume, 486000.0)

    @patch(MODELS_PATH + ".character.MEMBERAUDIT_DATA_RETENTION_LIMIT", None)
    def test_update_contracts_2(self, mock_esi):
        """can create new item exchange contract"""
        mock_esi.client = esi_client_stub

        self.character_1001.update_contract_headers()
        obj = self.character_1001.contracts.get(contract_id=100000002)
        self.assertEqual(obj.contract_type, CharacterContract.TYPE_ITEM_EXCHANGE)
        self.assertEqual(float(obj.price), 270000000.0)
        self.assertEqual(obj.volume, 486000.0)
        self.assertEqual(obj.status, CharacterContract.STATUS_FINISHED)

        self.character_1001.update_contract_items(contract=obj)

        self.assertEqual(obj.items.count(), 2)

        item = obj.items.get(record_id=1)
        self.assertTrue(item.is_included)
        self.assertFalse(item.is_singleton)
        self.assertEqual(item.quantity, 3)
        self.assertEqual(item.eve_type, EveType.objects.get(id=19540))

        item = obj.items.get(record_id=2)
        self.assertTrue(item.is_included)
        self.assertFalse(item.is_singleton)
        self.assertEqual(item.quantity, 5)
        self.assertEqual(item.raw_quantity, -1)
        self.assertEqual(item.eve_type, EveType.objects.get(id=19551))

    @patch(MODELS_PATH + ".character.MEMBERAUDIT_DATA_RETENTION_LIMIT", None)
    def test_update_contracts_3(self, mock_esi):
        """can create new auction contract"""
        mock_esi.client = esi_client_stub

        self.character_1001.update_contract_headers()
        obj = self.character_1001.contracts.get(contract_id=100000003)
        self.assertEqual(obj.contract_type, CharacterContract.TYPE_AUCTION)
        self.assertEqual(float(obj.buyout), 200_000_000.0)
        self.assertEqual(float(obj.price), 20_000_000.0)
        self.assertEqual(obj.volume, 400.0)
        self.assertEqual(obj.status, CharacterContract.STATUS_OUTSTANDING)

        self.character_1001.update_contract_items(contract=obj)

        self.assertEqual(obj.items.count(), 1)
        item = obj.items.get(record_id=1)
        self.assertTrue(item.is_included)
        self.assertFalse(item.is_singleton)
        self.assertEqual(item.quantity, 3)
        self.assertEqual(item.eve_type, EveType.objects.get(id=19540))

        self.character_1001.update_contract_bids(contract=obj)

        self.assertEqual(obj.bids.count(), 1)
        bid = obj.bids.get(bid_id=1)
        self.assertEqual(float(bid.amount), 1_000_000.23)
        self.assertEqual(bid.date_bid, parse_datetime("2017-01-01T10:10:10Z"))
        self.assertEqual(bid.bidder, EveEntity.objects.get(id=1101))

    @patch(MODELS_PATH + ".character.MEMBERAUDIT_DATA_RETENTION_LIMIT", None)
    def test_update_contracts_4(self, mock_esi):
        """old contracts must be kept"""
        mock_esi.client = esi_client_stub

        CharacterContract.objects.create(
            character=self.character_1001,
            contract_id=190000001,
            availability=CharacterContract.AVAILABILITY_PERSONAL,
            contract_type=CharacterContract.TYPE_COURIER,
            assignee=EveEntity.objects.get(id=1002),
            date_issued=now() - dt.timedelta(days=60),
            date_expired=now() - dt.timedelta(days=30),
            for_corporation=False,
            issuer=EveEntity.objects.get(id=1001),
            issuer_corporation=EveEntity.objects.get(id=2001),
            status=CharacterContract.STATUS_IN_PROGRESS,
            start_location=self.jita_44,
            end_location=self.structure_1,
            title="Old contract",
        )

        self.character_1001.update_contract_headers()
        self.assertEqual(self.character_1001.contracts.count(), 4)

    @patch(MODELS_PATH + ".character.MEMBERAUDIT_DATA_RETENTION_LIMIT", None)
    def test_update_contracts_5(self, mock_esi):
        """Existing contracts are updated"""
        mock_esi.client = esi_client_stub

        CharacterContract.objects.create(
            character=self.character_1001,
            contract_id=100000001,
            availability=CharacterContract.AVAILABILITY_PERSONAL,
            contract_type=CharacterContract.TYPE_COURIER,
            assignee=EveEntity.objects.get(id=2101),
            date_issued=parse_datetime("2019-10-02T13:15:21Z"),
            date_expired=parse_datetime("2019-10-09T13:15:21Z"),
            for_corporation=False,
            issuer=EveEntity.objects.get(id=1001),
            issuer_corporation=EveEntity.objects.get(id=2001),
            status=CharacterContract.STATUS_OUTSTANDING,
            start_location=self.jita_44,
            end_location=self.structure_1,
            title="Test 1",
            collateral=550000000,
            reward=500000000,
            volume=486000,
            days_to_complete=3,
        )

        self.character_1001.update_contract_headers()

        obj = self.character_1001.contracts.get(contract_id=100000001)
        self.assertEqual(obj.contract_type, CharacterContract.TYPE_COURIER)
        self.assertEqual(obj.acceptor, EveEntity.objects.get(id=1101))
        self.assertEqual(obj.assignee, EveEntity.objects.get(id=2101))
        self.assertEqual(obj.availability, CharacterContract.AVAILABILITY_PERSONAL)
        self.assertIsNone(obj.buyout)
        self.assertEqual(float(obj.collateral), 550000000.0)
        self.assertEqual(obj.date_accepted, parse_datetime("2019-10-06T13:15:21Z"))
        self.assertEqual(obj.date_completed, parse_datetime("2019-10-07T13:15:21Z"))
        self.assertEqual(obj.date_expired, parse_datetime("2019-10-09T13:15:21Z"))
        self.assertEqual(obj.date_issued, parse_datetime("2019-10-02T13:15:21Z"))
        self.assertEqual(obj.days_to_complete, 3)
        self.assertEqual(obj.end_location, self.structure_1)
        self.assertFalse(obj.for_corporation)
        self.assertEqual(obj.issuer_corporation, EveEntity.objects.get(id=2001))
        self.assertEqual(obj.issuer, EveEntity.objects.get(id=1001))
        self.assertEqual(float(obj.reward), 500000000.0)
        self.assertEqual(obj.start_location, self.jita_44)
        self.assertEqual(obj.status, CharacterContract.STATUS_IN_PROGRESS)
        self.assertEqual(obj.title, "Test 1")
        self.assertEqual(obj.volume, 486000.0)

    @patch(MODELS_PATH + ".character.MEMBERAUDIT_DATA_RETENTION_LIMIT", None)
    def test_update_contracts_6(self, mock_esi):
        """can add new bids to auction contract"""
        mock_esi.client = esi_client_stub
        contract = CharacterContract.objects.create(
            character=self.character_1001,
            contract_id=100000003,
            availability=CharacterContract.AVAILABILITY_PERSONAL,
            contract_type=CharacterContract.TYPE_AUCTION,
            assignee=EveEntity.objects.get(id=2101),
            date_issued=parse_datetime("2019-10-02T13:15:21Z"),
            date_expired=parse_datetime("2019-10-09T13:15:21Z"),
            for_corporation=False,
            issuer=EveEntity.objects.get(id=1001),
            issuer_corporation=EveEntity.objects.get(id=2001),
            status=CharacterContract.STATUS_OUTSTANDING,
            start_location=self.jita_44,
            end_location=self.jita_44,
            buyout=200_000_000,
            price=20_000_000,
            volume=400,
        )
        CharacterContractBid.objects.create(
            contract=contract,
            bid_id=2,
            amount=21_000_000,
            bidder=EveEntity.objects.get(id=1003),
            date_bid=now(),
        )

        self.character_1001.update_contract_headers()
        obj = self.character_1001.contracts.get(contract_id=100000003)
        self.character_1001.update_contract_bids(contract=obj)

        self.assertEqual(obj.bids.count(), 2)

        bid = obj.bids.get(bid_id=1)
        self.assertEqual(float(bid.amount), 1_000_000.23)
        self.assertEqual(bid.date_bid, parse_datetime("2017-01-01T10:10:10Z"))
        self.assertEqual(bid.bidder, EveEntity.objects.get(id=1101))

        bid = obj.bids.get(bid_id=2)
        self.assertEqual(float(bid.amount), 21_000_000)

    @patch(MODELS_PATH + ".character.MEMBERAUDIT_DATA_RETENTION_LIMIT", None)
    def test_update_contracts_7(self, mock_esi):
        """when contract list from ESI has not changed, then skip update"""
        mock_esi.client = esi_client_stub

        self.character_1001.update_contract_headers()
        obj = self.character_1001.contracts.get(contract_id=100000001)
        obj.status = CharacterContract.STATUS_FINISHED
        obj.save()

        self.character_1001.update_contract_headers()

        obj = self.character_1001.contracts.get(contract_id=100000001)
        self.assertEqual(obj.status, CharacterContract.STATUS_FINISHED)

    @patch(MODELS_PATH + ".character.MEMBERAUDIT_DATA_RETENTION_LIMIT", None)
    def test_update_contracts_8(self, mock_esi):
        """
        when contract list from ESI has not changed and update is forced, then update
        """
        mock_esi.client = esi_client_stub

        self.character_1001.update_contract_headers()
        obj = self.character_1001.contracts.get(contract_id=100000001)
        obj.status = CharacterContract.STATUS_FINISHED
        obj.save()

        self.character_1001.update_contract_headers(force_update=True)

        obj = self.character_1001.contracts.get(contract_id=100000001)
        self.assertEqual(obj.status, CharacterContract.STATUS_IN_PROGRESS)

    @patch(MODELS_PATH + ".character.MEMBERAUDIT_DATA_RETENTION_LIMIT", 10)
    def test_update_contracts_9(self, mock_esi):
        """when retention limit is set, then only create contracts younger than limit"""
        mock_esi.client = esi_client_stub

        with patch(MODELS_PATH + ".character.now") as mock_now:
            mock_now.return_value = dt.datetime(2019, 10, 21, 1, 15, tzinfo=utc)
            self.character_1001.update_contract_headers()

        self.assertSetEqual(
            set(self.character_1001.contracts.values_list("contract_id", flat=True)),
            {100000002, 100000003},
        )

    @patch(MODELS_PATH + ".character.MEMBERAUDIT_DATA_RETENTION_LIMIT", 15)
    def test_update_contracts_10(self, mock_esi):
        """when retention limit is set,
        then remove existing contracts older than limit
        """
        mock_esi.client = esi_client_stub
        CharacterContract.objects.create(
            character=self.character_1001,
            contract_id=100000004,
            availability=CharacterContract.AVAILABILITY_PERSONAL,
            contract_type=CharacterContract.TYPE_COURIER,
            assignee=EveEntity.objects.get(id=2101),
            date_issued=parse_datetime("2019-09-02T13:15:21Z"),
            date_expired=parse_datetime("2019-09-09T13:15:21Z"),
            for_corporation=False,
            issuer=EveEntity.objects.get(id=1001),
            issuer_corporation=EveEntity.objects.get(id=2001),
            status=CharacterContract.STATUS_OUTSTANDING,
            start_location=self.jita_44,
            end_location=self.structure_1,
            title="This contract is too old",
            collateral=550000000,
            reward=500000000,
            volume=486000,
            days_to_complete=3,
        )

        with patch(MODELS_PATH + ".character.now") as mock_now:
            mock_now.return_value = dt.datetime(2019, 10, 21, 1, 15, tzinfo=utc)
            self.character_1001.update_contract_headers()

        self.assertSetEqual(
            set(self.character_1001.contracts.values_list("contract_id", flat=True)),
            {100000001, 100000002, 100000003},
        )


@patch(MANAGERS_PATH + ".sections.eve_xml_to_html")
@patch(MODELS_PATH + ".character.esi")
class TestCharacterUpdateCharacterDetails(
    CharacterUpdateTestDataMixin, NoSocketsTestCase
):
    def test_can_create_from_scratch(self, mock_esi, mock_eve_xml_to_html):
        # given
        mock_esi.client = esi_client_stub
        mock_eve_xml_to_html.side_effect = lambda x: eve_xml_to_html(x)
        # when
        self.character_1001.update_character_details()
        # then
        self.assertEqual(self.character_1001.details.eve_ancestry.id, 11)
        self.assertEqual(
            self.character_1001.details.birthday, parse_datetime("2015-03-24T11:37:00Z")
        )
        self.assertEqual(self.character_1001.details.eve_bloodline_id, 1)
        self.assertEqual(self.character_1001.details.corporation, self.corporation_2001)
        self.assertEqual(self.character_1001.details.description, "Scio me nihil scire")
        self.assertEqual(
            self.character_1001.details.gender, CharacterDetails.GENDER_MALE
        )
        self.assertEqual(self.character_1001.details.name, "Bruce Wayne")
        self.assertEqual(self.character_1001.details.eve_race.id, 1)
        self.assertEqual(
            self.character_1001.details.title, "All round pretty awesome guy"
        )
        self.assertTrue(mock_eve_xml_to_html.called)

    def test_can_update_existing_data(self, mock_esi, mock_eve_xml_to_html):
        # given
        mock_esi.client = esi_client_stub
        mock_eve_xml_to_html.side_effect = lambda x: eve_xml_to_html(x)
        CharacterDetails.objects.create(
            character=self.character_1001,
            birthday=now(),
            corporation=self.corporation_2002,
            description="Change me",
            eve_bloodline_id=1,
            eve_race_id=1,
            name="Change me also",
        )
        # when
        self.character_1001.update_character_details()
        # then
        self.character_1001.details.refresh_from_db()
        self.assertEqual(self.character_1001.details.eve_ancestry_id, 11)
        self.assertEqual(
            self.character_1001.details.birthday, parse_datetime("2015-03-24T11:37:00Z")
        )
        self.assertEqual(self.character_1001.details.eve_bloodline_id, 1)
        self.assertEqual(self.character_1001.details.corporation, self.corporation_2001)
        self.assertEqual(self.character_1001.details.description, "Scio me nihil scire")
        self.assertEqual(
            self.character_1001.details.gender, CharacterDetails.GENDER_MALE
        )
        self.assertEqual(self.character_1001.details.name, "Bruce Wayne")
        self.assertEqual(self.character_1001.details.eve_race.id, 1)
        self.assertEqual(
            self.character_1001.details.title, "All round pretty awesome guy"
        )
        self.assertTrue(mock_eve_xml_to_html.called)

    def test_skip_update_1(self, mock_esi, mock_eve_xml_to_html):
        """when data from ESI has not changed, then skip update"""
        # given
        mock_esi.client = esi_client_stub
        mock_eve_xml_to_html.side_effect = lambda x: eve_xml_to_html(x)
        self.character_1001.update_character_details()
        self.character_1001.details.name = "John Doe"
        self.character_1001.details.save()
        # when
        self.character_1001.update_character_details()
        # then
        self.character_1001.details.refresh_from_db()
        self.assertEqual(self.character_1001.details.name, "John Doe")

    def test_skip_update_2(self, mock_esi, mock_eve_xml_to_html):
        """when data from ESI has not changed and update is forced, then do update"""
        # given
        mock_esi.client = esi_client_stub
        mock_eve_xml_to_html.side_effect = lambda x: eve_xml_to_html(x)
        self.character_1001.update_character_details()
        self.character_1001.details.name = "John Doe"
        self.character_1001.details.save()
        # when
        self.character_1001.update_character_details(force_update=True)
        # then
        self.character_1001.details.refresh_from_db()
        self.assertEqual(self.character_1001.details.name, "Bruce Wayne")

    def test_can_handle_u_bug_1(self, mock_esi, mock_eve_xml_to_html):
        # given
        mock_esi.client = esi_client_stub
        mock_eve_xml_to_html.side_effect = lambda x: eve_xml_to_html(x)
        # when
        self.character_1002.update_character_details()
        # then
        self.assertNotEqual(self.character_1002.details.description[:2], "u'")

    def test_can_handle_u_bug_2(self, mock_esi, mock_eve_xml_to_html):
        # given
        mock_esi.client = esi_client_stub
        mock_eve_xml_to_html.side_effect = lambda x: eve_xml_to_html(x)
        character = create_memberaudit_character(1003)
        # when
        character.update_character_details()
        # then
        self.assertNotEqual(character.details.description[:2], "u'")

    def test_can_handle_u_bug_3(self, mock_esi, mock_eve_xml_to_html):
        # given
        mock_esi.client = esi_client_stub
        mock_eve_xml_to_html.side_effect = lambda x: eve_xml_to_html(x)
        character = create_memberaudit_character(1101)
        # when
        character.update_character_details()
        # then
        self.assertNotEqual(character.details.description[:2], "u'")

    # @patch(MANAGERS_PATH + ".sections.get_or_create_esi_or_none")
    # def test_esi_ancestry_bug(
    #     self, mock_get_or_create_esi_or_none, mock_esi, mock_eve_xml_to_html
    # ):
    #     """when esi ancestry endpoint returns http error then ignore it and carry on"""

    #     def my_get_or_create_esi_or_none(prop_name: str, dct: dict, Model: type):
    #         if issubclass(Model, EveAncestry):
    #             raise HTTPInternalServerError(
    #                 response=BravadoResponseStub(500, "Test exception")
    #             )
    #         return get_or_create_esi_or_none(prop_name=prop_name, dct=dct, Model=Model)

    #     mock_esi.client = esi_client_stub
    #     mock_eve_xml_to_html.side_effect = lambda x: eve_xml_to_html(x)
    #     mock_get_or_create_esi_or_none.side_effect = my_get_or_create_esi_or_none

    #     self.character_1001.update_character_details()
    #     self.assertIsNone(self.character_1001.details.eve_ancestry)
    #     self.assertEqual(
    #         self.character_1001.details.birthday, parse_datetime("2015-03-24T11:37:00Z")
    #     )
    #     self.assertEqual(self.character_1001.details.eve_bloodline_id, 1)
    #     self.assertEqual(self.character_1001.details.corporation, self.corporation_2001)
    #     self.assertEqual(self.character_1001.details.description, "Scio me nihil scire")
    #     self.assertEqual(
    #         self.character_1001.details.gender, CharacterDetails.GENDER_MALE
    #     )
    #     self.assertEqual(self.character_1001.details.name, "Bruce Wayne")
    #     self.assertEqual(self.character_1001.details.eve_race.id, 1)
    #     self.assertEqual(
    #         self.character_1001.details.title, "All round pretty awesome guy"
    #     )
    #     self.assertTrue(mock_eve_xml_to_html.called)


@patch(MODELS_PATH + ".character.esi")
class TestCharacterUpdateCorporationHistory(
    CharacterUpdateTestDataMixin, NoSocketsTestCase
):
    def test_create(self, mock_esi):
        """can create corporation history from scratch"""
        mock_esi.client = esi_client_stub
        self.character_1001.update_corporation_history()
        self.assertEqual(self.character_1001.corporation_history.count(), 2)

        obj = self.character_1001.corporation_history.get(record_id=500)
        self.assertEqual(obj.corporation, self.corporation_2001)
        self.assertTrue(obj.is_deleted)
        self.assertEqual(obj.start_date, parse_datetime("2016-06-26T20:00:00Z"))

        obj = self.character_1001.corporation_history.get(record_id=501)
        self.assertEqual(obj.corporation, self.corporation_2002)
        self.assertFalse(obj.is_deleted)
        self.assertEqual(obj.start_date, parse_datetime("2016-07-26T20:00:00Z"))

    def test_update_1(self, mock_esi):
        """can update existing corporation history"""
        mock_esi.client = esi_client_stub
        self.character_1001.corporation_history.create(
            record_id=500, corporation=self.corporation_2002, start_date=now()
        )

        self.character_1001.update_corporation_history()
        self.assertEqual(self.character_1001.corporation_history.count(), 2)

        obj = self.character_1001.corporation_history.get(record_id=500)
        self.assertEqual(obj.corporation, self.corporation_2001)
        self.assertTrue(obj.is_deleted)
        self.assertEqual(obj.start_date, parse_datetime("2016-06-26T20:00:00Z"))

    def test_update_2(self, mock_esi):
        """when data from ESI has not changed, then skip update"""
        mock_esi.client = esi_client_stub

        self.character_1001.update_corporation_history()
        obj = self.character_1001.corporation_history.get(record_id=500)
        obj.corporation = self.corporation_2002
        obj.save()

        self.character_1001.update_corporation_history()
        obj = self.character_1001.corporation_history.get(record_id=500)
        self.assertEqual(obj.corporation, self.corporation_2002)

    def test_update_3(self, mock_esi):
        """when data from ESI has not changed and update is forced, then do update"""
        mock_esi.client = esi_client_stub

        self.character_1001.update_corporation_history()
        obj = self.character_1001.corporation_history.get(record_id=500)
        obj.corporation = self.corporation_2002
        obj.save()

        self.character_1001.update_corporation_history(force_update=True)

        obj = self.character_1001.corporation_history.get(record_id=500)
        self.assertEqual(obj.corporation, self.corporation_2001)

    def test_should_handle_empty_response(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        # when
        self.character_1002.update_corporation_history()
        # then
        self.assertEqual(self.character_1001.corporation_history.count(), 0)


@patch(MODELS_PATH + ".character.esi")
class TestCharacterUpdateImplants(CharacterUpdateTestDataMixin, NoSocketsTestCase):
    def test_update_implants_1(self, mock_esi):
        """can create implants from scratch"""
        mock_esi.client = esi_client_stub

        self.character_1001.update_implants()
        self.assertEqual(self.character_1001.implants.count(), 3)
        self.assertSetEqual(
            set(self.character_1001.implants.values_list("eve_type_id", flat=True)),
            {19540, 19551, 19553},
        )

    def test_update_implants_2(self, mock_esi):
        """can deal with no implants returned from ESI"""
        mock_esi.client = esi_client_stub

        self.character_1002.update_implants()
        self.assertEqual(self.character_1002.implants.count(), 0)

    def test_update_implants_3(self, mock_esi):
        """when data from ESI has not changed, then skip update"""
        mock_esi.client = esi_client_stub

        self.character_1001.update_implants()
        self.character_1001.implants.get(eve_type_id=19540).delete()

        self.character_1001.update_implants()
        self.assertFalse(
            self.character_1001.implants.filter(eve_type_id=19540).exists()
        )

    def test_update_implants_4(self, mock_esi):
        """when data from ESI has not changed and update is forced, then do update"""
        mock_esi.client = esi_client_stub

        self.character_1001.update_implants()
        self.character_1001.implants.get(eve_type_id=19540).delete()

        self.character_1001.update_implants(force_update=True)
        self.assertTrue(self.character_1001.implants.filter(eve_type_id=19540).exists())


@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
@patch(MODELS_PATH + ".character.esi")
class TestCharacterUpdateJumpClones(CharacterUpdateTestDataMixin, NoSocketsTestCase):
    def test_update_jump_clones_1(self, mock_esi):
        """can update jump clones with implants"""
        mock_esi.client = esi_client_stub

        self.character_1001.update_jump_clones()
        self.assertEqual(self.character_1001.jump_clones.count(), 1)

        obj = self.character_1001.jump_clones.get(jump_clone_id=12345)
        self.assertEqual(obj.location, self.jita_44)
        self.assertEqual(
            {x for x in obj.implants.values_list("eve_type", flat=True)},
            {19540, 19551, 19553},
        )

    def test_update_jump_clones_2(self, mock_esi):
        """can update jump clones without implants"""
        mock_esi.client = esi_client_stub

        self.character_1002.update_jump_clones()
        self.assertEqual(self.character_1002.jump_clones.count(), 1)

        obj = self.character_1002.jump_clones.get(jump_clone_id=12345)
        self.assertEqual(obj.location, self.jita_44)
        self.assertEqual(obj.implants.count(), 0)

    def test_skip_update_1(self, mock_esi):
        """when ESI data has not changed, then skip update"""
        mock_esi.client = esi_client_stub

        self.character_1001.update_jump_clones()
        obj = self.character_1001.jump_clones.get(jump_clone_id=12345)
        obj.location = self.structure_1
        obj.save()

        self.character_1001.update_jump_clones()

        obj = self.character_1001.jump_clones.get(jump_clone_id=12345)
        self.assertEqual(obj.location, self.structure_1)

    def test_skip_update_2(self, mock_esi):
        """when ESI data has not changed and update is forced, then do update"""
        mock_esi.client = esi_client_stub

        self.character_1001.update_jump_clones()
        obj = self.character_1001.jump_clones.get(jump_clone_id=12345)
        obj.location = self.structure_1
        obj.save()

        self.character_1001.update_jump_clones(force_update=True)

        obj = self.character_1001.jump_clones.get(jump_clone_id=12345)
        self.assertEqual(obj.location, self.jita_44)
