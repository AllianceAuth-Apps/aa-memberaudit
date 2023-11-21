import datetime as dt
from unittest.mock import patch

from django.test import override_settings
from django.utils.dateparse import parse_datetime
from django.utils.timezone import now
from eveuniverse.models import EveEntity, EveType

from app_utils.testing import NoSocketsTestCase

from memberaudit.models import (
    CharacterAsset,
    CharacterAttributes,
    CharacterContactLabel,
    CharacterContract,
    CharacterContractBid,
    CharacterContractItem,
    Location,
)
from memberaudit.tests.testdata.constants import EveStationId, EveTypeId
from memberaudit.tests.testdata.esi_client_stub import esi_client_stub
from memberaudit.tests.testdata.factories import (
    create_character_asset,
    create_character_attributes,
    create_character_contact,
    create_character_contact_label,
    create_character_contract,
    create_character_contract_bid,
    create_character_from_user,
    create_character_skillqueue_entry,
    create_eve_market_price,
)
from memberaudit.tests.testdata.load_entities import load_entities
from memberaudit.tests.testdata.load_eveuniverse import load_eveuniverse
from memberaudit.tests.testdata.load_locations import load_locations
from memberaudit.tests.utils import (
    create_memberaudit_character,
    create_user_from_evecharacter_with_access,
)

MODULE_PATH = "memberaudit.managers.character_sections_1"


class TestCharacterSkillQueue(NoSocketsTestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        load_eveuniverse()
        load_entities()
        cls.character = create_memberaudit_character(1001)
        cls.skill_type_1 = EveType.objects.get(id=24311)
        cls.skill_type_2 = EveType.objects.get(id=24312)

    def test_is_active_1(self):
        """when training is active and skill is in first position then return True"""
        entry = create_character_skillqueue_entry(
            character=self.character,
            eve_type=self.skill_type_1,
            finish_date=now() + dt.timedelta(days=3),
            queue_position=0,
            start_date=now() - dt.timedelta(days=1),
        )
        self.assertTrue(entry.is_active)

    def test_is_active_2(self):
        """when training is active and skill is not in first position then return False"""
        entry = create_character_skillqueue_entry(
            character=self.character,
            eve_type=self.skill_type_1,
            finish_date=now() + dt.timedelta(days=3),
            finished_level=5,
            queue_position=1,
            start_date=now() - dt.timedelta(days=1),
        )
        self.assertFalse(entry.is_active)

    def test_is_active_3(self):
        """when training is not active and skill is in first position then return False"""
        entry = create_character_skillqueue_entry(
            character=self.character,
            eve_type=self.skill_type_1,
            finished_level=5,
            queue_position=0,
        )
        self.assertFalse(entry.is_active)


class TestCharacterAssetManager(NoSocketsTestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        load_eveuniverse()
        load_entities()
        load_locations()
        cls.character = create_memberaudit_character(1001)
        cls.jita_44 = Location.objects.get(id=60003760)
        cls.merlin = EveType.objects.get(id=603)

    def test_can_calculate_pricing(self):
        create_character_asset(
            character=self.character, eve_type=self.merlin, quantity=5
        )
        create_eve_market_price(eve_type=self.merlin, average_price=500000)
        asset = CharacterAsset.objects.annotate_pricing().first()
        self.assertEqual(asset.price, 500000)
        self.assertEqual(asset.total, 2500000)

    def test_does_not_price_blueprint_copies(self):
        create_character_asset(
            character=self.character,
            eve_type=self.merlin,
            is_blueprint_copy=True,
            quantity=1,
        )
        create_eve_market_price(eve_type=self.merlin, average_price=500000)
        asset = CharacterAsset.objects.annotate_pricing().first()
        self.assertIsNone(asset.price)
        self.assertIsNone(asset.total)


@patch(MODULE_PATH + ".esi")
class TestCharacterAssetsFetchFromEsi(NoSocketsTestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        load_eveuniverse()
        load_entities()
        cls.character = create_memberaudit_character(1001)

    def test_can_fetch_new_assets(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        # when
        result = CharacterAsset.objects.fetch_from_esi(self.character)
        # then
        asset_data = {asset["item_id"]: asset for asset in result}
        self.assertSetEqual(
            set(asset_data.keys()),
            {
                1100000000001,
                1100000000002,
                1100000000003,
                1100000000004,
                1100000000005,
                1100000000006,
                1100000000007,
                1100000000008,
            },
        )
        obj = asset_data[1100000000001]
        self.assertEqual(obj["name"], "Parent Item 1")
        self.assertTrue(obj["is_blueprint_copy"])
        self.assertTrue(obj["is_singleton"])
        self.assertEqual(obj["location_flag"], "Hangar")
        self.assertEqual(obj["location_id"], EveStationId.JITA_44.value)
        self.assertEqual(obj["quantity"], 1)
        self.assertEqual(obj["type_id"], EveTypeId.CHARON.value)

    def test_should_always_return_assets_when_forced(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        CharacterAsset.objects.fetch_from_esi(self.character)
        # when
        result = CharacterAsset.objects.fetch_from_esi(
            self.character, force_update=True
        )
        # then
        self.assertIsNotNone(result)


@patch("memberaudit.models.Location.objects.create_missing_esi", spec=True)
@patch(MODULE_PATH + ".EveType.objects.bulk_get_or_create_esi", spec=True)
class TestCharacterAssetsPreloadObjects(NoSocketsTestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        load_eveuniverse()
        load_entities()
        cls.user, _ = create_user_from_evecharacter_with_access(1001)

    def test_do_nothing_when_asset_list_is_empty(
        self, mock_eve_entity_create, mock_preload_locations
    ):
        # given
        character = create_character_from_user(self.user)
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
        character = create_character_from_user(self.user)
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
class TestCharacterAttributesManager(NoSocketsTestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        load_entities()
        cls.character = create_memberaudit_character(1001)

    def test_can_create_from_scratch(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        # when
        CharacterAttributes.objects.update_or_create_esi(self.character)
        # then
        self.assertEqual(
            self.character.attributes.accrued_remap_cooldown_date,
            parse_datetime("2016-10-24T09:00:00Z"),
        )
        self.assertEqual(
            self.character.attributes.last_remap_date,
            parse_datetime("2016-10-24T09:00:00Z"),
        )
        self.assertEqual(self.character.attributes.charisma, 16)
        self.assertEqual(self.character.attributes.intelligence, 17)
        self.assertEqual(self.character.attributes.memory, 18)
        self.assertEqual(self.character.attributes.perception, 19)
        self.assertEqual(self.character.attributes.willpower, 20)

    def test_can_update_existing_attributes(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub

        create_character_attributes(
            character=self.character,
            accrued_remap_cooldown_date=None,
            last_remap_date=None,
            bonus_remaps=4,
            charisma=102,
            intelligence=103,
            memory=104,
            perception=105,
            willpower=106,
        )
        # when
        CharacterAttributes.objects.update_or_create_esi(self.character)
        # then
        self.character.attributes.refresh_from_db()
        self.assertEqual(
            self.character.attributes.accrued_remap_cooldown_date,
            parse_datetime("2016-10-24T09:00:00Z"),
        )
        self.assertEqual(
            self.character.attributes.last_remap_date,
            parse_datetime("2016-10-24T09:00:00Z"),
        )
        self.assertEqual(self.character.attributes.charisma, 16)
        self.assertEqual(self.character.attributes.intelligence, 17)
        self.assertEqual(self.character.attributes.memory, 18)
        self.assertEqual(self.character.attributes.perception, 19)
        self.assertEqual(self.character.attributes.willpower, 20)


@patch(MODULE_PATH + ".esi")
class TestCharacterContactLabelManager(NoSocketsTestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        load_entities()
        cls.character = create_memberaudit_character(1001)

    def test_should_do_nothing(self, mock_esi):
        # when
        CharacterContactLabel.objects._update_or_create_objs(
            character=self.character, labels=[]
        )
        # then
        self.assertEqual(CharacterContactLabel.objects.count(), 0)

    def test_update_contact_labels_1(self, mock_esi):
        """can create new contact labels from scratch"""
        mock_esi.client = esi_client_stub

        self.character.update_contact_labels()
        self.assertEqual(self.character.contact_labels.count(), 2)

        label = self.character.contact_labels.get(label_id=1)
        self.assertEqual(label.name, "friend")

        label = self.character.contact_labels.get(label_id=2)
        self.assertEqual(label.name, "pirate")

    def test_update_contact_labels_2(self, mock_esi):
        """can remove obsolete labels"""
        mock_esi.client = esi_client_stub
        create_character_contact_label(character=self.character, label_id=99)

        self.character.update_contact_labels()
        self.assertEqual(
            {x.label_id for x in self.character.contact_labels.all()}, {1, 2}
        )

    def test_update_contact_labels_3(self, mock_esi):
        """can update existing labels"""
        mock_esi.client = esi_client_stub
        create_character_contact_label(character=self.character, label_id=1)

        self.character.update_contact_labels()
        self.assertEqual(
            {x.label_id for x in self.character.contact_labels.all()}, {1, 2}
        )

        label = self.character.contact_labels.get(label_id=1)
        self.assertEqual(label.name, "friend")

    def test_update_contact_labels_4(self, mock_esi):
        """when data from ESI has not changed, then skip update"""
        mock_esi.client = esi_client_stub

        self.character.update_contact_labels()
        label = self.character.contact_labels.get(label_id=1)
        label.name = "foe"
        label.save()

        self.character.update_contact_labels()

        self.assertEqual(self.character.contact_labels.count(), 2)
        label = self.character.contact_labels.get(label_id=1)
        self.assertEqual(label.name, "foe")

    def test_update_contact_labels_5(self, mock_esi):
        """when data from ESI has not changed and update is forced, then do update"""
        mock_esi.client = esi_client_stub

        self.character.update_contact_labels()
        label = self.character.contact_labels.get(label_id=1)
        label.name = "foe"
        label.save()

        self.character.update_contact_labels(force_update=True)

        self.assertEqual(self.character.contact_labels.count(), 2)
        label = self.character.contact_labels.get(label_id=1)
        self.assertEqual(label.name, "friend")


@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
@patch(MODULE_PATH + ".esi")
class TestCharacterContactsManager(NoSocketsTestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        load_entities()
        cls.character = create_memberaudit_character(1001)

    def test_update_contacts_1(self, mock_esi):
        """can create contacts"""
        mock_esi.client = esi_client_stub
        create_character_contact_label(character=self.character, label_id=1)
        create_character_contact_label(character=self.character, label_id=2)

        self.character.update_contacts()

        self.assertEqual(self.character.contacts.count(), 2)

        obj = self.character.contacts.get(eve_entity_id=1101)
        self.assertEqual(obj.eve_entity.category, EveEntity.CATEGORY_CHARACTER)
        self.assertFalse(obj.is_blocked)
        self.assertTrue(obj.is_watched)
        self.assertEqual(obj.standing, -10)
        self.assertEqual({x.label_id for x in obj.labels.all()}, {2})

        obj = self.character.contacts.get(eve_entity_id=2002)
        self.assertEqual(obj.eve_entity.category, EveEntity.CATEGORY_CORPORATION)
        self.assertFalse(obj.is_blocked)
        self.assertFalse(obj.is_watched)
        self.assertEqual(obj.standing, 5)
        self.assertEqual(obj.labels.count(), 0)

    def test_update_contacts_2(self, mock_esi):
        """can remove obsolete contacts"""
        mock_esi.client = esi_client_stub
        create_character_contact_label(character=self.character, label_id=1)
        create_character_contact_label(character=self.character, label_id=2)
        create_character_contact(
            character=self.character,
            eve_entity=EveEntity.objects.get(id=3101),
            standing=-5,
        )

        self.character.update_contacts()

        self.assertEqual(
            {x.eve_entity_id for x in self.character.contacts.all()}, {1101, 2002}
        )

    def test_update_contacts_3(self, mock_esi):
        """can update existing contacts"""
        mock_esi.client = esi_client_stub
        create_character_contact_label(character=self.character, label_id=2)
        my_label = create_character_contact_label(character=self.character, label_id=1)
        my_contact = create_character_contact(
            character=self.character,
            eve_entity=EveEntity.objects.get(id=1101),
            is_blocked=True,
            is_watched=False,
            standing=-5,
        )
        my_contact.labels.add(my_label)

        self.character.update_contacts()

        obj = self.character.contacts.get(eve_entity_id=1101)
        self.assertEqual(obj.eve_entity.category, EveEntity.CATEGORY_CHARACTER)
        self.assertFalse(obj.is_blocked)
        self.assertTrue(obj.is_watched)
        self.assertEqual(obj.standing, -10)
        self.assertEqual({x.label_id for x in obj.labels.all()}, {2})

    def test_update_contacts_4(self, mock_esi):
        """when ESI data has not changed, then skip update"""
        mock_esi.client = esi_client_stub
        create_character_contact_label(character=self.character, label_id=1)
        create_character_contact_label(character=self.character, label_id=2)

        self.character.update_contacts()
        obj = self.character.contacts.get(eve_entity_id=1101)
        obj.is_watched = False
        obj.save()

        self.character.update_contacts()

        obj = self.character.contacts.get(eve_entity_id=1101)
        self.assertFalse(obj.is_watched)

    def test_update_contacts_5(self, mock_esi):
        """when ESI data has not changed and update is forced, then update"""
        mock_esi.client = esi_client_stub
        create_character_contact_label(character=self.character, label_id=1)
        create_character_contact_label(character=self.character, label_id=2)

        self.character.update_contacts()
        obj = self.character.contacts.get(eve_entity_id=1101)
        obj.is_watched = False
        obj.save()

        self.character.update_contacts(force_update=True)

        obj = self.character.contacts.get(eve_entity_id=1101)
        self.assertTrue(obj.is_watched)


@patch(MODULE_PATH + ".esi")
class TestCharacterContractsUpdate(NoSocketsTestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        load_eveuniverse()
        load_entities()
        load_locations()
        cls.character = create_memberaudit_character(1001)
        cls.jita_44 = Location.objects.get(id=60003760)
        cls.structure_1 = Location.objects.get(id=1000000000001)

    @patch(MODULE_PATH + ".data_retention_cutoff", lambda: None)
    def test_can_create_new_courier_contract(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        # when
        CharacterContract.objects.update_or_create_esi(self.character)
        # then
        self.assertSetEqual(
            set(self.character.contracts.values_list("contract_id", flat=True)),
            {100000001, 100000002, 100000003},
        )

        obj = self.character.contracts.get(contract_id=100000001)
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
        create_character_contract(
            character=self.character,
            contract_id=190000001,
            contract_type=CharacterContract.TYPE_COURIER,
            assignee=EveEntity.objects.get(id=1002),
            issuer=EveEntity.objects.get(id=1001),
            issuer_corporation=EveEntity.objects.get(id=2001),
            status=CharacterContract.STATUS_IN_PROGRESS,
            start_location=self.jita_44,
            end_location=self.structure_1,
        )
        # when
        CharacterContract.objects.update_or_create_esi(self.character)
        # then
        self.assertEqual(self.character.contracts.count(), 4)

    @patch(MODULE_PATH + ".data_retention_cutoff", lambda: None)
    def test_should_update_existing_contracts(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        create_character_contract(
            character=self.character,
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
        CharacterContract.objects.update_or_create_esi(self.character)
        # then
        obj = self.character.contracts.get(contract_id=100000001)
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
        self.character.update_contract_headers()
        obj = self.character.contracts.get(contract_id=100000001)
        obj.status = CharacterContract.STATUS_FINISHED
        obj.save()
        # when
        CharacterContract.objects.update_or_create_esi(self.character)
        # then
        obj = self.character.contracts.get(contract_id=100000001)
        self.assertEqual(obj.status, CharacterContract.STATUS_FINISHED)

    @patch(MODULE_PATH + ".data_retention_cutoff", lambda: None)
    def test_always_update_when_forced(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        self.character.update_contract_headers()
        obj = self.character.contracts.get(contract_id=100000001)
        obj.status = CharacterContract.STATUS_FINISHED
        obj.save()
        # when
        CharacterContract.objects.update_or_create_esi(
            self.character, force_update=True
        )
        # then
        obj = self.character.contracts.get(contract_id=100000001)
        self.assertEqual(obj.status, CharacterContract.STATUS_IN_PROGRESS)

    @patch(
        MODULE_PATH + ".data_retention_cutoff",
        lambda: dt.datetime(2019, 10, 11, 1, 15, tzinfo=dt.timezone.utc),
    )
    def test_when_updating_then_use_retention_limit(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        # when
        CharacterContract.objects.update_or_create_esi(self.character)
        # then
        self.assertSetEqual(
            set(self.character.contracts.values_list("contract_id", flat=True)),
            {100000002, 100000003},
        )

    @patch(
        MODULE_PATH + ".data_retention_cutoff",
        lambda: dt.datetime(2019, 10, 6, 1, 15, tzinfo=dt.timezone.utc),
    )
    def test_when_retention_limit_is_set_then_remove_outdated_contracts(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        create_character_contract(
            character=self.character,
            contract_id=100_000_004,
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
        CharacterContract.objects.update_or_create_esi(self.character)
        # then
        self.assertSetEqual(
            set(self.character.contracts.values_list("contract_id", flat=True)),
            {100000001, 100000002, 100000003},
        )

    @patch(MODULE_PATH + ".data_retention_cutoff", lambda: None)
    def test_can_create_new_item_exchange_contract(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        CharacterContract.objects.update_or_create_esi(self.character)
        contract = self.character.contracts.get(contract_id=100000002)
        self.assertEqual(contract.contract_type, CharacterContract.TYPE_ITEM_EXCHANGE)
        self.assertEqual(float(contract.price), 270000000.0)
        self.assertEqual(contract.volume, 486000.0)
        self.assertEqual(contract.status, CharacterContract.STATUS_FINISHED)
        # when
        CharacterContractItem.objects.update_or_create_esi(self.character, contract)
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
        CharacterContract.objects.update_or_create_esi(self.character)
        contract = self.character.contracts.get(contract_id=100000003)
        self.assertEqual(contract.contract_type, CharacterContract.TYPE_AUCTION)
        self.assertEqual(float(contract.buyout), 200_000_000.0)
        self.assertEqual(float(contract.price), 20_000_000.0)
        self.assertEqual(contract.volume, 400.0)
        self.assertEqual(contract.status, CharacterContract.STATUS_OUTSTANDING)
        CharacterContractItem.objects.update_or_create_esi(self.character, contract)
        self.assertEqual(contract.items.count(), 1)
        item = contract.items.get(record_id=1)
        self.assertTrue(item.is_included)
        self.assertFalse(item.is_singleton)
        self.assertEqual(item.quantity, 3)
        self.assertEqual(item.eve_type, EveType.objects.get(id=19540))
        # when
        CharacterContractBid.objects.update_or_create_esi(self.character, contract)
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
        contract = create_character_contract(
            character=self.character,
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
        create_character_contract_bid(
            contract=contract,
            bid_id=2,
            amount=21_000_000,
            bidder=EveEntity.objects.get(id=1003),
            date_bid=now(),
        )
        self.character.update_contract_headers()
        # when
        self.character.update_contract_bids(contract=contract)
        # then
        contract.refresh_from_db()
        self.assertEqual(contract.bids.count(), 2)

        bid = contract.bids.get(bid_id=1)
        self.assertEqual(float(bid.amount), 1_000_000.23)
        self.assertEqual(bid.date_bid, parse_datetime("2017-01-01T10:10:10Z"))
        self.assertEqual(bid.bidder, EveEntity.objects.get(id=1101))

        bid = contract.bids.get(bid_id=2)
        self.assertEqual(float(bid.amount), 21_000_000)


class TestCharacterContractBidManager(NoSocketsTestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        load_entities()
        cls.character = create_memberaudit_character(1001)

    def test_should_do_nothing_when_there_are_no_bids(self):
        # given
        contract = create_character_contract(
            character=self.character, contract_type=CharacterContract.TYPE_AUCTION
        )
        # when
        CharacterContractBid.objects._update_or_create_objs(
            contract=contract, bids_list={}
        )
        # then
        self.assertEqual(CharacterContractBid.objects.count(), 0)

    def test_should_do_nothing_when_there_are_no_new_bids(self):
        # given
        contract = create_character_contract(
            character=self.character, contract_type=CharacterContract.TYPE_AUCTION
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
