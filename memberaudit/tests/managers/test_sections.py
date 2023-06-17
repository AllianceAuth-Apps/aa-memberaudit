import datetime as dt
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils.dateparse import parse_datetime
from django.utils.timezone import now
from eveuniverse.models import (
    EveEntity,
    EveMarketPrice,
    EvePlanet,
    EveSolarSystem,
    EveType,
)

from app_utils.esi_testing import EsiClientStub, EsiEndpoint, build_http_error
from app_utils.testing import NoSocketsTestCase

from memberaudit.core.xml_converter import eve_xml_to_html
from memberaudit.models import (
    Character,
    CharacterAsset,
    CharacterAttributes,
    CharacterContact,
    CharacterContactLabel,
    CharacterContract,
    CharacterContractBid,
    CharacterContractItem,
    CharacterCorporationHistory,
    CharacterDetails,
    CharacterFwStats,
    CharacterJumpClone,
    CharacterLocation,
    CharacterLoyaltyEntry,
    CharacterMail,
    CharacterMailLabel,
    CharacterOnlineStatus,
    CharacterPlanet,
    CharacterShip,
    CharacterSkill,
    CharacterSkillqueueEntry,
    CharacterWalletBalance,
    CharacterWalletJournalEntry,
    CharacterWalletTransaction,
    Location,
    MailEntity,
)

from ..testdata.esi_client_stub import esi_client_stub
from ..testdata.factories import (
    create_character_contract,
    create_character_contract_bid,
    create_character_mail_label,
    create_character_mining_ledger_entry,
    create_character_planet,
    create_mail_entity_from_eve_entity,
    create_mailing_list,
)
from ..testdata.load_entities import load_entities
from ..testdata.load_eveuniverse import load_eveuniverse
from ..testdata.load_locations import load_locations
from ..utils import CharacterUpdateTestDataMixin, create_memberaudit_character

MODULE_PATH = "memberaudit.managers.sections"


class TestCharacterAssetManager(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        load_locations()
        cls.character = create_memberaudit_character(1001)
        cls.jita_44 = Location.objects.get(id=60003760)
        cls.merlin = EveType.objects.get(id=603)

    def test_can_calculate_pricing(self):
        CharacterAsset.objects.create(
            character=self.character,
            item_id=1100000000666,
            location=self.jita_44,
            eve_type=self.merlin,
            is_singleton=False,
            quantity=5,
        )
        EveMarketPrice.objects.create(eve_type=self.merlin, average_price=500000)
        asset = CharacterAsset.objects.annotate_pricing().first()
        self.assertEqual(asset.price, 500000)
        self.assertEqual(asset.total, 2500000)

    def test_does_not_price_blueprint_copies(self):
        CharacterAsset.objects.create(
            character=self.character,
            item_id=1100000000666,
            location=self.jita_44,
            eve_type=self.merlin,
            is_blueprint_copy=True,
            is_singleton=False,
            quantity=1,
        )
        EveMarketPrice.objects.create(eve_type=self.merlin, average_price=500000)
        asset = CharacterAsset.objects.annotate_pricing().first()
        self.assertIsNone(asset.price)
        self.assertIsNone(asset.total)


@patch("memberaudit.models.Location.objects.create_missing_esi", spec=True)
@patch(MODULE_PATH + ".EveType.objects.bulk_get_or_create_esi", spec=True)
class TestCharacterAssetsPreloadObjects(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        load_eveuniverse()
        load_entities()

    def test_do_nothing_when_asset_list_is_empty(
        self, mock_eve_entity_create, mock_preload_locations
    ):
        # given
        character = create_memberaudit_character(1001)
        asset_list = []
        # when
        character.assets_preload_objects(asset_list)
        # then
        self.assertFalse(mock_eve_entity_create.called)
        self.assertFalse(mock_preload_locations.called)

    def test_fetch_missing_eve_entity_objects_and_locations(
        self, mock_eve_entity_create, mock_preload_locations
    ):
        # given
        character = create_memberaudit_character(1001)
        asset_list = [
            {"item_id": 1, "type_id": 3, "location_id": 420},
            {"item_id": 2, "type_id": 4, "location_id": 421},
        ]
        # when
        character.assets_preload_objects(asset_list)
        # then
        self.assertTrue(mock_eve_entity_create.called)
        _, kwargs = mock_eve_entity_create.call_args
        self.assertEqual(set(kwargs["ids"]), {3, 4})
        self.assertTrue(mock_preload_locations.called)
        _, kwargs = mock_preload_locations.call_args
        self.assertEqual(kwargs["location_ids"], {420, 421})


@patch(MODULE_PATH + ".esi")
class TestCharacterUpdateAttributes(CharacterUpdateTestDataMixin, NoSocketsTestCase):
    def test_can_create_from_scratch(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        # when
        CharacterAttributes.objects.update_or_create_esi(self.character_1001)
        # then
        self.assertEqual(
            self.character_1001.attributes.accrued_remap_cooldown_date,
            parse_datetime("2016-10-24T09:00:00Z"),
        )
        self.assertEqual(
            self.character_1001.attributes.last_remap_date,
            parse_datetime("2016-10-24T09:00:00Z"),
        )
        self.assertEqual(self.character_1001.attributes.charisma, 16)
        self.assertEqual(self.character_1001.attributes.intelligence, 17)
        self.assertEqual(self.character_1001.attributes.memory, 18)
        self.assertEqual(self.character_1001.attributes.perception, 19)
        self.assertEqual(self.character_1001.attributes.willpower, 20)

    def test_can_update_existing_attributes(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        CharacterAttributes.objects.create(
            character=self.character_1001,
            accrued_remap_cooldown_date="2020-10-24T09:00:00Z",
            last_remap_date="2020-10-24T09:00:00Z",
            bonus_remaps=4,
            charisma=102,
            intelligence=103,
            memory=104,
            perception=105,
            willpower=106,
        )
        # when
        CharacterAttributes.objects.update_or_create_esi(self.character_1001)
        # then
        self.character_1001.attributes.refresh_from_db()
        self.assertEqual(
            self.character_1001.attributes.accrued_remap_cooldown_date,
            parse_datetime("2016-10-24T09:00:00Z"),
        )
        self.assertEqual(
            self.character_1001.attributes.last_remap_date,
            parse_datetime("2016-10-24T09:00:00Z"),
        )
        self.assertEqual(self.character_1001.attributes.charisma, 16)
        self.assertEqual(self.character_1001.attributes.intelligence, 17)
        self.assertEqual(self.character_1001.attributes.memory, 18)
        self.assertEqual(self.character_1001.attributes.perception, 19)
        self.assertEqual(self.character_1001.attributes.willpower, 20)


class TestCharacterUpdateBase(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        load_locations()
        cls.character_1001 = create_memberaudit_character(1001)
        cls.character_1002 = create_memberaudit_character(1002)
        cls.corporation_2001 = EveEntity.objects.get(id=2001)
        cls.corporation_2002 = EveEntity.objects.get(id=2002)
        cls.token = (
            cls.character_1001.eve_character.character_ownership.user.token_set.first()
        )
        cls.jita = EveSolarSystem.objects.get(id=30000142)
        cls.jita_44 = Location.objects.get(id=60003760)
        cls.amamake = EveSolarSystem.objects.get(id=30002537)
        cls.structure_1 = Location.objects.get(id=1000000000001)


class TestCharacterContactLabelManager(TestCharacterUpdateBase):
    def test_should_do_nothing(self):
        # when
        CharacterContactLabel.objects._update_or_create_objs(
            character=self.character_1001, labels=[]
        )
        # then
        self.assertEqual(CharacterContactLabel.objects.count(), 0)


@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
@patch(MODULE_PATH + ".esi")
class TestCharacterContactsManager(CharacterUpdateTestDataMixin, NoSocketsTestCase):
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


@patch(MODULE_PATH + ".esi")
class TestCharacterContractsUpdate(CharacterUpdateTestDataMixin, NoSocketsTestCase):
    @patch(MODULE_PATH + ".data_retention_cutoff", lambda: None)
    def test_can_create_new_courier_contract(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        # when
        CharacterContract.objects.update_or_create_esi(self.character_1001)
        # then
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

    @patch(MODULE_PATH + ".data_retention_cutoff", lambda: None)
    def test_should_keep_old_contracts_when_updating(self, mock_esi):
        # given
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
        # when
        CharacterContract.objects.update_or_create_esi(self.character_1001)
        # then
        self.assertEqual(self.character_1001.contracts.count(), 4)

    @patch(MODULE_PATH + ".data_retention_cutoff", lambda: None)
    def test_should_update_existing_contracts(self, mock_esi):
        # given
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
        # when
        CharacterContract.objects.update_or_create_esi(self.character_1001)
        # then
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

    @patch(MODULE_PATH + ".data_retention_cutoff", lambda: None)
    def test_should_skip_updates_when_there_is_no_change(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        self.character_1001.update_contract_headers()
        obj = self.character_1001.contracts.get(contract_id=100000001)
        obj.status = CharacterContract.STATUS_FINISHED
        obj.save()
        # when
        CharacterContract.objects.update_or_create_esi(self.character_1001)
        # then
        obj = self.character_1001.contracts.get(contract_id=100000001)
        self.assertEqual(obj.status, CharacterContract.STATUS_FINISHED)

    @patch(MODULE_PATH + ".data_retention_cutoff", lambda: None)
    def test_always_update_when_forced(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        self.character_1001.update_contract_headers()
        obj = self.character_1001.contracts.get(contract_id=100000001)
        obj.status = CharacterContract.STATUS_FINISHED
        obj.save()
        # when
        CharacterContract.objects.update_or_create_esi(
            self.character_1001, force_update=True
        )
        # then
        obj = self.character_1001.contracts.get(contract_id=100000001)
        self.assertEqual(obj.status, CharacterContract.STATUS_IN_PROGRESS)

    @patch(
        MODULE_PATH + ".data_retention_cutoff",
        lambda: dt.datetime(2019, 10, 11, 1, 15, tzinfo=dt.timezone.utc),
    )
    def test_when_updating_then_use_retention_limit(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        # when
        CharacterContract.objects.update_or_create_esi(self.character_1001)
        # then
        self.assertSetEqual(
            set(self.character_1001.contracts.values_list("contract_id", flat=True)),
            {100000002, 100000003},
        )

    @patch(
        MODULE_PATH + ".data_retention_cutoff",
        lambda: dt.datetime(2019, 10, 6, 1, 15, tzinfo=dt.timezone.utc),
    )
    def test_when_retention_limit_is_set_then_remove_outdated_contracts(self, mock_esi):
        # given
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
        # when
        CharacterContract.objects.update_or_create_esi(self.character_1001)
        # then
        self.assertSetEqual(
            set(self.character_1001.contracts.values_list("contract_id", flat=True)),
            {100000001, 100000002, 100000003},
        )

    @patch(MODULE_PATH + ".data_retention_cutoff", lambda: None)
    def test_can_create_new_item_exchange_contract(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        CharacterContract.objects.update_or_create_esi(self.character_1001)
        contract = self.character_1001.contracts.get(contract_id=100000002)
        self.assertEqual(contract.contract_type, CharacterContract.TYPE_ITEM_EXCHANGE)
        self.assertEqual(float(contract.price), 270000000.0)
        self.assertEqual(contract.volume, 486000.0)
        self.assertEqual(contract.status, CharacterContract.STATUS_FINISHED)
        # when
        CharacterContractItem.objects.update_or_create_esi(
            self.character_1001, contract
        )
        # then
        self.assertEqual(contract.items.count(), 2)

        item = contract.items.get(record_id=1)
        self.assertTrue(item.is_included)
        self.assertFalse(item.is_singleton)
        self.assertEqual(item.quantity, 3)
        self.assertEqual(item.eve_type, EveType.objects.get(id=19540))

        item = contract.items.get(record_id=2)
        self.assertTrue(item.is_included)
        self.assertFalse(item.is_singleton)
        self.assertEqual(item.quantity, 5)
        self.assertEqual(item.raw_quantity, -1)
        self.assertEqual(item.eve_type, EveType.objects.get(id=19551))

    @patch(MODULE_PATH + ".data_retention_cutoff", lambda: None)
    def test_can_create_auction_contract(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        CharacterContract.objects.update_or_create_esi(self.character_1001)
        contract = self.character_1001.contracts.get(contract_id=100000003)
        self.assertEqual(contract.contract_type, CharacterContract.TYPE_AUCTION)
        self.assertEqual(float(contract.buyout), 200_000_000.0)
        self.assertEqual(float(contract.price), 20_000_000.0)
        self.assertEqual(contract.volume, 400.0)
        self.assertEqual(contract.status, CharacterContract.STATUS_OUTSTANDING)
        CharacterContractItem.objects.update_or_create_esi(
            self.character_1001, contract
        )
        self.assertEqual(contract.items.count(), 1)
        item = contract.items.get(record_id=1)
        self.assertTrue(item.is_included)
        self.assertFalse(item.is_singleton)
        self.assertEqual(item.quantity, 3)
        self.assertEqual(item.eve_type, EveType.objects.get(id=19540))
        # when
        CharacterContractBid.objects.update_or_create_esi(self.character_1001, contract)
        # then
        self.assertEqual(contract.bids.count(), 1)
        bid = contract.bids.get(bid_id=1)
        self.assertEqual(float(bid.amount), 1_000_000.23)
        self.assertEqual(bid.date_bid, parse_datetime("2017-01-01T10:10:10Z"))
        self.assertEqual(bid.bidder, EveEntity.objects.get(id=1101))

    @patch(MODULE_PATH + ".data_retention_cutoff", lambda: None)
    def test_can_add_new_bids_to_auction_contract(self, mock_esi):
        # given
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
        # when
        self.character_1001.update_contract_bids(contract=contract)
        # then
        contract.refresh_from_db()
        self.assertEqual(contract.bids.count(), 2)

        bid = contract.bids.get(bid_id=1)
        self.assertEqual(float(bid.amount), 1_000_000.23)
        self.assertEqual(bid.date_bid, parse_datetime("2017-01-01T10:10:10Z"))
        self.assertEqual(bid.bidder, EveEntity.objects.get(id=1101))

        bid = contract.bids.get(bid_id=2)
        self.assertEqual(float(bid.amount), 21_000_000)


class TestCharacterContractBidManager(TestCharacterUpdateBase):
    def test_should_do_nothing_when_there_are_no_bids(self):
        # given
        contract = create_character_contract(
            character=self.character_1001, contract_type=CharacterContract.TYPE_AUCTION
        )
        # when
        CharacterContractBid.objects._update_or_create_objs(
            contract=contract, bids_list=dict()
        )
        # then
        self.assertEqual(CharacterContractBid.objects.count(), 0)

    def test_should_do_nothing_when_there_are_no_new_bids(self):
        # given
        contract = create_character_contract(
            character=self.character_1001, contract_type=CharacterContract.TYPE_AUCTION
        )
        bidder = EveEntity.objects.get(id=1002)
        bid = create_character_contract_bid(contract=contract, bidder=bidder)
        bids_list = {
            bid.bid_id: {
                "amount": bid.amount,
                "bid_id": bid.bid_id,
                "bidder_id": bidder.id,
                "date_bid": bid.date_bid,
            }
        }
        # when
        CharacterContractBid.objects._update_or_create_objs(
            contract=contract, bids_list=bids_list
        )
        # then
        self.assertEqual(CharacterContractBid.objects.count(), 1)


@patch(MODULE_PATH + ".esi")
class TestCharacterCorporationHistoryManager(
    CharacterUpdateTestDataMixin, NoSocketsTestCase
):
    def test_can_create_from_scratch(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        # when
        CharacterCorporationHistory.objects.update_or_create_esi(self.character_1001)
        # then
        self.assertEqual(self.character_1001.corporation_history.count(), 2)

        obj = self.character_1001.corporation_history.get(record_id=500)
        self.assertEqual(obj.corporation, self.corporation_2001)
        self.assertTrue(obj.is_deleted)
        self.assertEqual(obj.start_date, parse_datetime("2016-06-26T20:00:00Z"))

        obj = self.character_1001.corporation_history.get(record_id=501)
        self.assertEqual(obj.corporation, self.corporation_2002)
        self.assertFalse(obj.is_deleted)
        self.assertEqual(obj.start_date, parse_datetime("2016-07-26T20:00:00Z"))

    def test_can_update_existing_history(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        self.character_1001.corporation_history.create(
            record_id=500, corporation=self.corporation_2002, start_date=now()
        )
        # when
        CharacterCorporationHistory.objects.update_or_create_esi(self.character_1001)
        # then
        self.assertEqual(self.character_1001.corporation_history.count(), 2)

        obj = self.character_1001.corporation_history.get(record_id=500)
        self.assertEqual(obj.corporation, self.corporation_2001)
        self.assertTrue(obj.is_deleted)
        self.assertEqual(obj.start_date, parse_datetime("2016-06-26T20:00:00Z"))

    def test_should_skip_update_when_data_on_ESI_has_not_changed(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        self.character_1001.update_corporation_history()
        obj = self.character_1001.corporation_history.get(record_id=500)
        obj.corporation = self.corporation_2002
        obj.save()
        # when
        CharacterCorporationHistory.objects.update_or_create_esi(self.character_1001)
        # then
        obj = self.character_1001.corporation_history.get(record_id=500)
        self.assertEqual(obj.corporation, self.corporation_2002)

    def test_should_update_always_when_forced(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        self.character_1001.update_corporation_history()
        obj = self.character_1001.corporation_history.get(record_id=500)
        obj.corporation = self.corporation_2002
        obj.save()
        # when
        CharacterCorporationHistory.objects.update_or_create_esi(
            self.character_1001, force_update=True
        )
        # then
        obj = self.character_1001.corporation_history.get(record_id=500)
        self.assertEqual(obj.corporation, self.corporation_2001)

    def test_should_handle_empty_response(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        # when
        CharacterCorporationHistory.objects.update_or_create_esi(self.character_1002)
        # then
        self.assertEqual(self.character_1001.corporation_history.count(), 0)


@patch(MODULE_PATH + ".eve_xml_to_html")
@patch(MODULE_PATH + ".esi")
class TestCharacterDetailManager(CharacterUpdateTestDataMixin, NoSocketsTestCase):
    def test_can_create_from_scratch(self, mock_esi, mock_eve_xml_to_html):
        # given
        mock_esi.client = esi_client_stub
        mock_eve_xml_to_html.side_effect = lambda x: eve_xml_to_html(x)
        # when
        CharacterDetails.objects.update_or_create_esi(self.character_1001)
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


@patch(MODULE_PATH + ".esi")
class TestCharacterFwStatsManager(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        cls.character_1001 = create_memberaudit_character(1001)
        cls.endpoints = [
            EsiEndpoint(
                "Faction_Warfare",
                "get_characters_character_id_fw_stats",
                "character_id",
                needs_token=True,
                data={
                    "1001": {
                        "current_rank": 3,
                        "enlisted_on": dt.datetime(
                            2023, 3, 21, 15, 0, tzinfo=dt.timezone.utc
                        ),
                        "faction_id": 500001,
                        "highest_rank": 4,
                        "kills": {
                            "last_week": 893,
                            "total": 684350,
                            "yesterday": 136,
                        },
                        "victory_points": {
                            "last_week": 102640,
                            "total": 52658260,
                            "yesterday": 15980,
                        },
                    }
                },
            ),
        ]
        cls.esi_client_stub = EsiClientStub.create_from_endpoints(cls.endpoints)

    def test_should_add_new_entry_from_scratch(self, mock_esi):
        # given
        mock_esi.client = self.esi_client_stub
        # when
        with patch(MODULE_PATH + ".data_retention_cutoff", lambda: None):
            CharacterFwStats.objects.update_or_create_esi(self.character_1001)
        # then
        obj: CharacterFwStats = self.character_1001.fw_stats
        self.assertEqual(obj.current_rank, 3)
        self.assertEqual(
            obj.enlisted_on,
            dt.datetime(2023, 3, 21, 15, 0, tzinfo=dt.timezone.utc),
        )
        self.assertEqual(obj.faction_id, 500001)
        self.assertEqual(obj.highest_rank, 4)
        self.assertEqual(obj.kills_last_week, 893)
        self.assertEqual(obj.kills_total, 684350)
        self.assertEqual(obj.kills_yesterday, 136)
        self.assertEqual(obj.victory_points_last_week, 102640)
        self.assertEqual(obj.victory_points_total, 52658260)
        self.assertEqual(obj.victory_points_yesterday, 15980)

    def test_should_update_existing_entries(self, mock_esi):
        # given
        mock_esi.client = self.esi_client_stub
        CharacterFwStats.objects.create(
            character=self.character_1001,
            kills_last_week=0,
            kills_total=0,
            kills_yesterday=0,
            victory_points_last_week=0,
            victory_points_total=0,
            victory_points_yesterday=0,
        )
        # when
        with patch(MODULE_PATH + ".data_retention_cutoff", lambda: None):
            CharacterFwStats.objects.update_or_create_esi(self.character_1001)
        # then
        self.character_1001.refresh_from_db()
        obj: CharacterFwStats = self.character_1001.fw_stats
        self.assertEqual(obj.current_rank, 3)
        self.assertEqual(
            obj.enlisted_on,
            dt.datetime(2023, 3, 21, 15, 0, tzinfo=dt.timezone.utc),
        )
        self.assertEqual(obj.faction_id, 500001)
        self.assertEqual(obj.highest_rank, 4)
        self.assertEqual(obj.kills_last_week, 893)
        self.assertEqual(obj.kills_total, 684350)
        self.assertEqual(obj.kills_yesterday, 136)
        self.assertEqual(obj.victory_points_last_week, 102640)
        self.assertEqual(obj.victory_points_total, 52658260)
        self.assertEqual(obj.victory_points_yesterday, 15980)

    def test_should_add_new_entry_from_scratch_for_unlisted(self, mock_esi):
        # given
        endpoints = [
            EsiEndpoint(
                "Faction_Warfare",
                "get_characters_character_id_fw_stats",
                "character_id",
                needs_token=True,
                data={
                    "1001": {
                        "kills": {
                            "last_week": 0,
                            "total": 684350,
                            "yesterday": 0,
                        },
                        "victory_points": {
                            "last_week": 0,
                            "total": 52658260,
                            "yesterday": 0,
                        },
                    }
                },
            ),
        ]
        mock_esi.client = EsiClientStub.create_from_endpoints(endpoints)
        # when
        with patch(MODULE_PATH + ".data_retention_cutoff", lambda: None):
            CharacterFwStats.objects.update_or_create_esi(self.character_1001)
        # then
        obj: CharacterFwStats = self.character_1001.fw_stats
        self.assertIsNone(obj.current_rank)
        self.assertIsNone(obj.enlisted_on)
        self.assertIsNone(obj.faction)
        self.assertIsNone(obj.highest_rank)
        self.assertEqual(obj.kills_last_week, 0)
        self.assertEqual(obj.kills_total, 684350)
        self.assertEqual(obj.kills_yesterday, 0)
        self.assertEqual(obj.victory_points_last_week, 0)
        self.assertEqual(obj.victory_points_total, 52658260)
        self.assertEqual(obj.victory_points_yesterday, 0)

    # FIXME: Test stopped working after moving it over
    # @patch(MODULE_PATH + ".CharacterFwStats.objects.update_for_character")
    # def test_should_not_update_when_not_changed(
    #     self, mock_update_for_character, mock_esi
    # ):
    #     # given
    #     mock_esi.client = self.esi_client_stub
    #     # when
    #     with patch(
    #         MODULE_PATH + ".Character.has_section_changed"
    #     ) as mock_has_section_changed:
    #         mock_has_section_changed.return_value = False
    #         CharacterFwStats.objects.update_or_create_esi(self.character_1001)
    #     # then
    #     self.assertFalse(mock_update_for_character.called)


@patch(MODULE_PATH + ".esi")
class TestCharacterImplantsManager(CharacterUpdateTestDataMixin, NoSocketsTestCase):
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
@patch(MODULE_PATH + ".esi")
class TestCharacterJumpClonesManager(CharacterUpdateTestDataMixin, NoSocketsTestCase):
    def test_can_update_with_implants(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        # when
        CharacterJumpClone.objects.update_or_create_esi(self.character_1001)
        # then
        self.assertEqual(self.character_1001.jump_clones.count(), 1)
        obj = self.character_1001.jump_clones.get(jump_clone_id=12345)
        self.assertEqual(obj.location, self.jita_44)
        self.assertEqual(
            {x for x in obj.implants.values_list("eve_type", flat=True)},
            {19540, 19551, 19553},
        )

    def test_can_update_without_implants(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        # when
        CharacterJumpClone.objects.update_or_create_esi(self.character_1002)
        # then
        self.assertEqual(self.character_1002.jump_clones.count(), 1)
        obj = self.character_1002.jump_clones.get(jump_clone_id=12345)
        self.assertEqual(obj.location, self.jita_44)
        self.assertEqual(obj.implants.count(), 0)

    def test_skip_update_when_no_new_data(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        CharacterJumpClone.objects.update_or_create_esi(self.character_1001)
        obj = self.character_1001.jump_clones.get(jump_clone_id=12345)
        obj.location = self.structure_1
        obj.save()
        # when
        CharacterJumpClone.objects.update_or_create_esi(self.character_1001)
        # then
        obj = self.character_1001.jump_clones.get(jump_clone_id=12345)
        self.assertEqual(obj.location, self.structure_1)

    def test_update_always_when_forced(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        CharacterJumpClone.objects.update_or_create_esi(self.character_1001)
        obj = self.character_1001.jump_clones.get(jump_clone_id=12345)
        obj.location = self.structure_1
        obj.save()
        # when
        CharacterJumpClone.objects.update_or_create_esi(
            self.character_1001, force_update=True
        )
        # then
        obj = self.character_1001.jump_clones.get(jump_clone_id=12345)
        self.assertEqual(obj.location, self.jita_44)


@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
@patch(MODULE_PATH + ".esi")
class TestCharacterLocationManager(CharacterUpdateTestDataMixin, NoSocketsTestCase):
    def test_update_location_1(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        # when
        CharacterLocation.objects.update_or_create_esi(self.character_1001)
        # then
        self.assertEqual(self.character_1001.location.eve_solar_system, self.jita)
        self.assertEqual(self.character_1001.location.location, self.jita_44)

    def test_update_location_2(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        # when
        CharacterLocation.objects.update_or_create_esi(self.character_1002)
        # then
        self.assertEqual(self.character_1002.location.eve_solar_system, self.amamake)
        self.assertEqual(self.character_1002.location.location, self.structure_1)


@patch(MODULE_PATH + ".esi")
class TestCharacterLoyaltyManager(CharacterUpdateTestDataMixin, NoSocketsTestCase):
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


@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
@patch(MODULE_PATH + ".esi")
class TestCharacterMailManager(CharacterUpdateTestDataMixin, NoSocketsTestCase):
    @patch(MODULE_PATH + ".data_retention_cutoff", lambda: None)
    def test_can_create_new_mail_from_scratch(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        create_mail_entity_from_eve_entity(1002)
        create_mailing_list(id=9001)
        create_character_mail_label(character=self.character_1001, label_id=3)
        # when
        self.character_1001.update_mail_headers()
        # then
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
        self.character_1001.update_mail_headers()
        # then
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
        self.character_1001.update_mail_headers(force_update=True)
        # then
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

        self.assertSetEqual(
            set(self.character_1001.mails.values_list("mail_id", flat=True)),
            {2, 3},
        )

    @patch(
        MODULE_PATH + ".data_retention_cutoff",
        lambda: dt.datetime(2015, 9, 20, 20, 5, tzinfo=dt.timezone.utc)
        - dt.timedelta(days=15),
    )
    def test_update_mail_headers_7(self, mock_esi):
        """when data retention limit is set, then remove old data beyond that limit"""
        mock_esi.client = esi_client_stub
        sender, _ = MailEntity.objects.update_or_create_from_eve_entity_id(id=1002)
        CharacterMail.objects.create(
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

        self.character_1001.update_mail_headers()

        self.assertSetEqual(
            set(self.character_1001.mails.values_list("mail_id", flat=True)),
            {2, 3},
        )

    def test_should_update_existing_mail_body(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        sender = create_mail_entity_from_eve_entity(1002)
        mail = CharacterMail.objects.create(
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
        self.character_1001.update_mail_body(mail)
        # then
        obj = self.character_1001.mails.get(mail_id=1)
        self.assertEqual(obj.body, "blah blah blah 😓")

    @patch(MODULE_PATH + ".eve_xml_to_html")
    def test_should_update_mail_body_from_scratch(self, mock_eve_xml_to_html, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        mock_eve_xml_to_html.side_effect = lambda x: eve_xml_to_html(x)
        sender = create_mail_entity_from_eve_entity(1002)
        mail = CharacterMail.objects.create(
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
        self.character_1001.update_mail_body(mail)
        # then
        obj = self.character_1001.mails.get(mail_id=2)
        self.assertTrue(obj.body)
        self.assertTrue(mock_eve_xml_to_html.called)

    def test_should_delete_mail_header_when_fetching_body_returns_404(self, mock_esi):
        # given
        mock_esi.client.Mail.get_characters_character_id_mail_mail_id.side_effect = (
            build_http_error(404, "Test")
        )
        sender = create_mail_entity_from_eve_entity(1002)
        mail = CharacterMail.objects.create(
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
        self.character_1001.update_mail_body(mail)
        # then
        self.assertFalse(self.character_1001.mails.filter(mail_id=1).exists())

    @patch("memberaudit.models.MailEntity.objects.get_or_create_esi_async")
    def test_can_preload_mail_senders(self, mock_get_or_create_esi_async, mock_esi):
        # given
        create_mailing_list(id=9001)
        headers = {1: {"from": 9001, "mail_id": 1}, 2: {"from": 9002, "mail_id": 2}}
        # when
        CharacterMail.objects._preload_mail_senders(self.character_1001, headers)
        # then
        self.assertTrue(mock_get_or_create_esi_async.called)
        mail_entity_ids = {
            o[1]["id"] for o in mock_get_or_create_esi_async.call_args_list
        }
        self.assertSetEqual(mail_entity_ids, {9002})


class TestCharacterMailLabelManager(TestCharacterUpdateBase):
    def test_normal(self):
        label_1 = CharacterMailLabel.objects.create(
            character=self.character_1001, label_id=1, name="Alpha"
        )
        label_2 = CharacterMailLabel.objects.create(
            character=self.character_1001, label_id=2, name="Bravo"
        )
        labels = CharacterMailLabel.objects.get_all_labels()
        self.assertDictEqual(
            labels, {label_1.label_id: label_1, label_2.label_id: label_2}
        )

    def test_empty(self):
        labels = CharacterMailLabel.objects.get_all_labels()
        self.assertDictEqual(labels, dict())


@patch(MODULE_PATH + ".esi")
class TestCharacterMailLabelManagerEsi(CharacterUpdateTestDataMixin, TestCase):
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


@patch(MODULE_PATH + ".esi")
class TestCharacterMiningLedgerManager(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        cls.character_1001 = create_memberaudit_character(1001)
        cls.endpoints = [
            EsiEndpoint(
                "Industry",
                "get_characters_character_id_mining",
                "character_id",
                needs_token=True,
                data={
                    "1001": [
                        {
                            "date": "2017-09-19",
                            "quantity": 7004,
                            "solar_system_id": 30002537,
                            "type_id": 17471,
                        },
                        {
                            "date": "2017-09-18",
                            "quantity": 5199,
                            "solar_system_id": 30002537,
                            "type_id": 17471,
                        },
                    ]
                },
            ),
        ]
        cls.esi_client_stub = EsiClientStub.create_from_endpoints(cls.endpoints)

    def test_should_add_new_entry_from_scratch(self, mock_esi):
        # given
        mock_esi.client = self.esi_client_stub
        # when
        self.character_1001.update_mining_ledger()
        # then
        self.assertEqual(self.character_1001.mining_ledger.count(), 2)
        obj = self.character_1001.mining_ledger.first()
        self.assertEqual(obj.date, dt.date(2017, 9, 19))
        self.assertEqual(obj.eve_type, EveType.objects.get(name="Dense Veldspar"))
        self.assertEqual(
            obj.eve_solar_system, EveSolarSystem.objects.get(name="Amamake")
        )
        self.assertEqual(obj.quantity, 7004)

    def test_should_update_existing_entries(self, mock_esi):
        # given
        mock_esi.client = self.esi_client_stub
        create_character_mining_ledger_entry(
            character=self.character_1001,
            date=dt.date(2017, 9, 19),
            eve_solar_system=EveSolarSystem.objects.get(name="Amamake"),
            eve_type=EveType.objects.get(name="Dense Veldspar"),
            quantity=5,
        )
        # when
        self.character_1001.update_mining_ledger()
        # then
        self.assertEqual(self.character_1001.mining_ledger.count(), 2)
        obj = self.character_1001.mining_ledger.get(
            date=dt.date(2017, 9, 19),
            eve_solar_system=EveSolarSystem.objects.get(name="Amamake"),
            eve_type=EveType.objects.get(name="Dense Veldspar"),
        )
        self.assertEqual(obj.quantity, 7004)


@patch(MODULE_PATH + ".esi")
class TestCharacterShipManager(CharacterUpdateTestDataMixin, NoSocketsTestCase):
    def test_should_update_all_fields(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        # when
        CharacterShip.objects.update_or_create_esi(self.character_1001)
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
        CharacterShip.objects.update_or_create_esi(self.character_1001)
        # then
        self.character_1001.refresh_from_db()
        self.assertEqual(self.character_1001.ship.eve_type_id, 603)
        self.assertEqual(self.character_1001.ship.name, "Shooter Boy")


@patch(MODULE_PATH + ".esi")
class TestCharacterSkillQueueManager(CharacterUpdateTestDataMixin, NoSocketsTestCase):
    def test_can_create_from_scratch(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        # when
        CharacterSkillqueueEntry.objects.update_or_create_esi(self.character_1001)
        # then
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

    def test_can_update_existing_queue(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        self.character_1001.skillqueue.create(
            queue_position=0,
            eve_type=EveType.objects.get(id=24311),
            finish_date=now() + dt.timedelta(days=1),
            finished_level=4,
            start_date=now() - dt.timedelta(days=1),
        )
        # when
        CharacterSkillqueueEntry.objects.update_or_create_esi(self.character_1001)
        # then
        self.assertEqual(self.character_1001.skillqueue.count(), 3)

        entry = self.character_1001.skillqueue.get(queue_position=0)
        self.assertEqual(entry.eve_type, EveType.objects.get(id=24311))
        self.assertEqual(entry.finish_date, parse_datetime("2016-06-29T10:47:00Z"))
        self.assertEqual(entry.finished_level, 3)
        self.assertEqual(entry.start_date, parse_datetime("2016-06-29T10:46:00Z"))

    def test_should_skip_update_when_no_change(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        CharacterSkillqueueEntry.objects.update_or_create_esi(self.character_1001)
        entry = self.character_1001.skillqueue.get(queue_position=0)
        entry.finished_level = 4
        entry.save()
        # when
        CharacterSkillqueueEntry.objects.update_or_create_esi(self.character_1001)
        # then
        entry = self.character_1001.skillqueue.get(queue_position=0)
        self.assertEqual(entry.finished_level, 4)

    def test_should_always_update_when_forced(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        CharacterSkillqueueEntry.objects.update_or_create_esi(self.character_1001)
        entry = self.character_1001.skillqueue.get(queue_position=0)
        entry.finished_level = 4
        entry.save()
        # when
        CharacterSkillqueueEntry.objects.update_or_create_esi(
            self.character_1001, force_update=True
        )
        # then
        entry = self.character_1001.skillqueue.get(queue_position=0)
        self.assertEqual(entry.finished_level, 3)


@patch(MODULE_PATH + ".esi")
class TestCharacterOnlineStatusManager(CharacterUpdateTestDataMixin, NoSocketsTestCase):
    def test_update_online_status(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        # when
        CharacterOnlineStatus.objects.update_or_create_esi(self.character_1001)
        # then
        self.assertEqual(
            self.character_1001.online_status.last_login,
            parse_datetime("2017-01-02T03:04:05Z"),
        )
        self.assertEqual(
            self.character_1001.online_status.last_logout,
            parse_datetime("2017-01-02T04:05:06Z"),
        )
        self.assertEqual(self.character_1001.online_status.logins, 9001)


@patch(MODULE_PATH + ".esi")
class TestCharacterPlanetManager(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        cls.character_1001 = create_memberaudit_character(1001)
        cls.endpoints = [
            EsiEndpoint(
                "Planetary_Interaction",
                "get_characters_character_id_planets",
                "character_id",
                needs_token=True,
                data={
                    "1001": [
                        {
                            "last_update": "2016-11-28T16:42:51Z",
                            "num_pins": 1,
                            "owner_id": 1001,
                            "planet_id": 40161463,
                            "planet_type": "barren",
                            "solar_system_id": 30002537,
                            "upgrade_level": 0,
                        }
                    ]
                },
            ),
        ]
        cls.esi_client_stub = EsiClientStub.create_from_endpoints(cls.endpoints)

    def test_should_add_new_planet(self, mock_esi):
        # given
        mock_esi.client = self.esi_client_stub
        # when
        self.character_1001.update_planets()
        # then
        self.assertEqual(self.character_1001.planets.count(), 1)
        obj: CharacterPlanet = self.character_1001.planets.first()
        self.assertIsInstance(obj.last_update_at, dt.datetime)
        self.assertEqual(obj.eve_planet, EvePlanet.objects.get(id=40161463))
        self.assertEqual(obj.num_pins, 1)
        self.assertEqual(obj.upgrade_level, 0)

    def test_should_update_existing_entries(self, mock_esi):
        # given
        mock_esi.client = self.esi_client_stub
        create_character_planet(character=self.character_1001)
        # when
        self.character_1001.update_planets()
        # then
        self.assertEqual(self.character_1001.planets.count(), 1)
        obj: CharacterPlanet = self.character_1001.planets.first()
        self.assertIsInstance(obj.last_update_at, dt.datetime)
        self.assertEqual(obj.eve_planet, EvePlanet.objects.get(id=40161463))
        self.assertEqual(obj.num_pins, 1)
        self.assertEqual(obj.upgrade_level, 0)


@patch(MODULE_PATH + ".esi")
class TestCharacterSkillsManager(CharacterUpdateTestDataMixin, NoSocketsTestCase):
    def test_can_create_new_skills(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        # when
        CharacterSkill.objects.update_or_create_esi(character=self.character_1001)
        # then
        self.assertEqual(self.character_1001.skillpoints.total, 30_000)
        self.assertEqual(self.character_1001.skillpoints.unallocated, 1_000)
        self.assertSetEqual(
            set(self.character_1001.skills.values_list("eve_type_id", flat=True)),
            {24311, 24312},
        )
        skill = self.character_1001.skills.get(eve_type_id=24311)
        self.assertEqual(skill.active_skill_level, 3)
        self.assertEqual(skill.skillpoints_in_skill, 20_000)
        self.assertEqual(skill.trained_skill_level, 4)

        skill = self.character_1001.skills.get(eve_type_id=24312)
        self.assertEqual(skill.active_skill_level, 1)
        self.assertEqual(skill.skillpoints_in_skill, 10_000)
        self.assertEqual(skill.trained_skill_level, 1)

    def test_caen_update_existing_skills(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        CharacterSkill.objects.create(
            character=self.character_1001,
            eve_type=EveType.objects.get(id=24311),
            active_skill_level=1,
            skillpoints_in_skill=1,
            trained_skill_level=1,
        )
        # when
        CharacterSkill.objects.update_or_create_esi(character=self.character_1001)
        # then
        self.assertEqual(self.character_1001.skills.count(), 2)
        skill = self.character_1001.skills.get(eve_type_id=24311)
        self.assertEqual(skill.active_skill_level, 3)
        self.assertEqual(skill.skillpoints_in_skill, 20_000)
        self.assertEqual(skill.trained_skill_level, 4)

    def test_can_delete_obsolete_skills(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        CharacterSkill.objects.create(
            character=self.character_1001,
            eve_type=EveType.objects.get(id=20185),
            active_skill_level=1,
            skillpoints_in_skill=1,
            trained_skill_level=1,
        )
        # when
        CharacterSkill.objects.update_or_create_esi(character=self.character_1001)
        # then
        self.assertSetEqual(
            set(self.character_1001.skills.values_list("eve_type_id", flat=True)),
            {24311, 24312},
        )

    def test_update_skills_4(self, mock_esi):
        """when ESI info has not changed, then do not update local data"""
        # given
        mock_esi.client = esi_client_stub
        self.character_1001.reset_update_section(Character.UpdateSection.SKILLS)
        self.character_1001.update_skills()
        skill = self.character_1001.skills.get(eve_type_id=24311)
        skill.active_skill_level = 4
        skill.save()
        # when
        CharacterSkill.objects.update_or_create_esi(character=self.character_1001)
        # then
        skill.refresh_from_db()
        self.assertEqual(skill.active_skill_level, 4)

    def test_update_skills_5(self, mock_esi):
        """when ESI info has not changed and update forced, then update local data"""
        # given
        mock_esi.client = esi_client_stub
        self.character_1001.reset_update_section(Character.UpdateSection.SKILLS)
        # when
        CharacterSkill.objects.update_or_create_esi(character=self.character_1001)
        # then
        skill = self.character_1001.skills.get(eve_type_id=24311)
        skill.active_skill_level = 4
        skill.save()
        self.character_1001.update_skills(force_update=True)
        skill = self.character_1001.skills.get(eve_type_id=24311)
        self.assertEqual(skill.active_skill_level, 3)


@patch(MODULE_PATH + ".esi")
class TestCharacterWalletBalanceManager(
    CharacterUpdateTestDataMixin, NoSocketsTestCase
):
    def test_update_wallet_balance(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        # when
        CharacterWalletBalance.objects.update_or_create_esi(self.character_1001)
        # then
        self.assertEqual(self.character_1001.wallet_balance.total, 123456789)


@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
@patch(MODULE_PATH + ".esi")
class TestCharacterWalletJournalManager(
    CharacterUpdateTestDataMixin, NoSocketsTestCase
):
    @patch(MODULE_PATH + ".data_retention_cutoff", lambda: None)
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

    @patch(MODULE_PATH + ".data_retention_cutoff", lambda: None)
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

    @patch(MODULE_PATH + ".data_retention_cutoff", lambda: None)
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

    def test_update_wallet_journal_4(self, mock_esi):
        """When new wallet entry is older than retention limit, then do not store it"""
        mock_esi.client = esi_client_stub

        with patch(
            MODULE_PATH + ".data_retention_cutoff",
            lambda: dt.datetime(2018, 3, 11, 20, 5, tzinfo=dt.timezone.utc)
            - dt.timedelta(days=10),
        ):
            self.character_1001.update_wallet_journal()

        self.assertSetEqual(
            set(self.character_1001.wallet_journal.values_list("entry_id", flat=True)),
            {91},
        )

    def test_update_wallet_journal_5(self, mock_esi):
        """When wallet existing entry is older than retention limit, then delete it"""
        mock_esi.client = esi_client_stub
        CharacterWalletJournalEntry.objects.create(
            character=self.character_1001,
            entry_id=55,
            amount=1_000_000,
            balance=10_000_000,
            context_id_type=CharacterWalletJournalEntry.CONTEXT_ID_TYPE_UNDEFINED,
            date=dt.datetime(2018, 2, 11, 20, 5, tzinfo=dt.timezone.utc),
            description="dummy",
            first_party=EveEntity.objects.get(id=1001),
            second_party=EveEntity.objects.get(id=1002),
        )

        with patch(
            MODULE_PATH + ".data_retention_cutoff",
            lambda: dt.datetime(2018, 3, 11, 20, 5, tzinfo=dt.timezone.utc)
            - dt.timedelta(days=20),
        ):
            self.character_1001.update_wallet_journal()

        self.assertSetEqual(
            set(self.character_1001.wallet_journal.values_list("entry_id", flat=True)),
            {89, 91},
        )


@patch(MODULE_PATH + ".esi")
class TestCharacterWalletTransactionManager(
    CharacterUpdateTestDataMixin, NoSocketsTestCase
):
    def test_should_add_wallet_transactions_from_scratch(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        # when
        with patch(MODULE_PATH + ".data_retention_cutoff", lambda: None):
            CharacterWalletTransaction.objects.update_or_create_esi(self.character_1001)
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
        with patch(MODULE_PATH + ".data_retention_cutoff", lambda: None):
            CharacterWalletTransaction.objects.update_or_create_esi(self.character_1001)
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
