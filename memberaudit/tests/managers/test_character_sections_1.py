import datetime as dt
from unittest.mock import patch

import pook

from django.db import IntegrityError
from django.utils.timezone import now
from eveuniverse.tests.testdata.factories_2 import (
    EveEntityCharacterFactory,
    EveEntityCorporationFactory,
    EveMarketPriceFactory,
    EveTypeFactory,
)

from app_utils.testing import NoSocketsTestCase

from memberaudit.helpers import UpdateSectionResult
from memberaudit.models import (
    CharacterAsset,
    CharacterAttributes,
    CharacterContact,
    CharacterContactLabel,
    CharacterContract,
    CharacterContractBid,
    CharacterContractItem,
)
from memberaudit.tests.testdata.factories_2 import (
    CharacterAssetFactory,
    CharacterAttributesFactory,
    CharacterContactFactory,
    CharacterContactLabelFactory,
    CharacterContractAuctionFactory,
    CharacterContractCourierFactory,
    CharacterContractItemExchangeFactory,
    CharacterContractItemFactory,
    CharacterFactory,
    LocationStationFactory,
    make_esi_url,
)
from memberaudit.tests.utils import TestCaseWithClearCache, extract

MODULE_PATH = "memberaudit.managers.character_sections_1"


class TestCharacterAssetManager_AnnotatePricing(NoSocketsTestCase):
    def test_can_calculate_pricing(self):
        # given
        character = CharacterFactory()
        ca = CharacterAssetFactory(character=character, quantity=5)
        EveMarketPriceFactory(eve_type=ca.eve_type, average_price=500000)

        # when
        asset = CharacterAsset.objects.annotate_pricing().first()

        # then
        self.assertEqual(asset.price, 500000)
        self.assertEqual(asset.total, 2500000)

    def test_does_not_price_blueprint_copies(self):
        # given
        character = CharacterFactory()
        ca = CharacterAssetFactory(
            character=character, is_blueprint_copy=True, quantity=1
        )
        EveMarketPriceFactory(eve_type=ca.eve_type, average_price=500000)

        # when
        asset = CharacterAsset.objects.annotate_pricing().first()

        # then
        self.assertIsNone(asset.price)
        self.assertIsNone(asset.total)


class TestCharacterAssetManager_BulkCreateWithFallback(NoSocketsTestCase):
    def test_should_create_assets_in_bulk(self):
        # given
        character = CharacterFactory()
        eve_type = EveTypeFactory()
        location = LocationStationFactory()
        objs = [
            CharacterAssetFactory.build(
                character=character, eve_type=eve_type, location=location
            )
            for _ in range(5)
        ]

        # when
        new_objs = CharacterAsset.objects.bulk_create_with_fallback(objs)

        # then
        expected_ids = _extract_item_ids(objs)
        existing_item_ids = extract(character.assets, "item_id")
        self.assertSetEqual(existing_item_ids, expected_ids)
        self.assertSetEqual(_extract_item_ids(new_objs), expected_ids)

    def test_should_create_all_assets_and_ignore_the_problem_obj(self):
        # given
        character = CharacterFactory()
        character = CharacterFactory()
        eve_type = EveTypeFactory()
        location = LocationStationFactory()
        objs = [
            CharacterAssetFactory.build(
                character=character, eve_type=eve_type, location=location
            )
            for _ in range(5)
        ]
        problem_item_id = objs[3].item_id

        def my_save(obj: CharacterAsset, *args, **kwargs):
            if int(obj.item_id) == problem_item_id:
                raise IntegrityError("Test exception")
            super(CharacterAsset, obj).save(*args, **kwargs)

        # when
        with (
            patch.object(CharacterAsset.objects, "bulk_create") as mock_bulk_create,
            patch(
                "memberaudit.models.character_sections_1.CharacterAsset.save", my_save
            ),
        ):
            mock_bulk_create.side_effect = IntegrityError("Test exception")

            new_objs = CharacterAsset.objects.bulk_create_with_fallback(objs)

        # then
        expected_ids = _extract_item_ids(objs) - {problem_item_id}
        self.assertSetEqual(_extract_item_ids(new_objs), expected_ids)

        existing_item_ids = extract(character.assets, "item_id")
        self.assertSetEqual(existing_item_ids, expected_ids)


def _extract_item_ids(objs) -> set:
    return {obj.item_id for obj in objs}


class TestCharacterAssetsManager_FetchFromEsi(TestCaseWithClearCache):
    @pook.on
    def test_can_fetch_new_assets(self):
        # given
        character = CharacterFactory()
        eve_type = EveTypeFactory()
        location = LocationStationFactory()
        item_id = 1_000_900_000_999
        quantity = 3
        pook.get(
            make_esi_url(f"characters/{character.character_id}/assets"),
            reply=200,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "is_blueprint_copy": True,
                    "is_singleton": True,
                    "item_id": item_id,
                    "location_flag": "Hangar",
                    "location_id": location.id,
                    "location_type": "station",
                    "quantity": quantity,
                    "type_id": eve_type.id,
                }
            ],
        )
        pook.post(
            make_esi_url(f"characters/{character.character_id}/assets/names"),
            reply=200,
            response_json=[{"item_id": item_id, "name": "Alpha Boy"}],
        )
        # when
        result: UpdateSectionResult = CharacterAsset.objects.fetch_from_esi(character)
        # then
        self.assertTrue(result.is_changed)
        asset_data = {asset["item_id"]: asset for asset in result.data}
        self.assertSetEqual(set(asset_data.keys()), {item_id})
        obj = asset_data[item_id]
        self.assertEqual(obj["name"], "Alpha Boy")
        self.assertTrue(obj["is_blueprint_copy"])
        self.assertTrue(obj["is_singleton"])
        self.assertEqual(obj["location_flag"], "Hangar")
        self.assertEqual(obj["location_id"], location.id)
        self.assertEqual(obj["quantity"], quantity)
        self.assertEqual(obj["type_id"], eve_type.id)


@patch("memberaudit.models.Location.objects.create_missing_esi", spec=True)
@patch(MODULE_PATH + ".EveType.objects.bulk_get_or_create_esi", spec=True)
class TestCharacter_AssetsPreloadObjects(NoSocketsTestCase):
    def test_do_nothing_when_asset_list_is_empty(
        self, mock_eve_entity_create, mock_preload_locations
    ):
        # given
        character = CharacterFactory()
        asset_list = []

        # when
        result = character.assets_preload_objects(asset_list)

        # then
        self.assertFalse(result.is_updated)
        self.assertFalse(mock_eve_entity_create.called)
        self.assertFalse(mock_preload_locations.called)

    def test_fetch_missing_eve_entity_objects_and_locations(
        self, mock_eve_entity_create, mock_preload_locations
    ):
        # given
        character = CharacterFactory()
        asset_list = [
            {"item_id": 1, "type_id": 3, "location_id": 420},
            {"item_id": 2, "type_id": 4, "location_id": 421},
        ]
        # when
        result = character.assets_preload_objects(asset_list)

        # then
        self.assertTrue(result.is_updated)
        self.assertTrue(mock_eve_entity_create.called)
        _, kwargs = mock_eve_entity_create.call_args
        self.assertEqual(set(kwargs["ids"]), {3, 4})
        self.assertTrue(mock_preload_locations.called)
        _, kwargs = mock_preload_locations.call_args
        self.assertEqual(kwargs["location_ids"], {420, 421})

    def test_fetch_missing_eve_entity_objects_only(
        self, mock_eve_entity_create, mock_preload_locations
    ):
        # given
        LocationStationFactory(id=420)
        LocationStationFactory(id=421)
        character = CharacterFactory()
        asset_list = [
            {"item_id": 1, "type_id": 3, "location_id": 420},
            {"item_id": 2, "type_id": 4, "location_id": 421},
        ]
        # when
        result = character.assets_preload_objects(asset_list)

        # then
        self.assertTrue(result.is_updated)
        self.assertTrue(mock_eve_entity_create.called)
        _, kwargs = mock_eve_entity_create.call_args
        self.assertEqual(set(kwargs["ids"]), {3, 4})
        self.assertFalse(mock_preload_locations.called)


class TestCharacterAttributesManager_UpdateOrCreateEsi(TestCaseWithClearCache):
    @pook.on
    def test_can_create_from_scratch(self):
        # given
        character = CharacterFactory()
        accrued_remap_cooldown_date = now() + dt.timedelta(days=3)
        bonus_remaps = 3
        charisma = 16
        intelligence = 17
        last_remap_date = now() - dt.timedelta(days=3)
        memory = 18
        perception = 19
        willpower = 20
        pook.get(
            make_esi_url(f"characters/{character.character_id}/attributes"),
            reply=200,
            response_json={
                "accrued_remap_cooldown_date": accrued_remap_cooldown_date.isoformat(),
                "bonus_remaps": bonus_remaps,
                "charisma": charisma,
                "intelligence": intelligence,
                "last_remap_date": last_remap_date.isoformat(),
                "memory": memory,
                "perception": perception,
                "willpower": willpower,
            },
        )
        # when
        result: UpdateSectionResult = CharacterAttributes.objects.update_or_create_esi(
            character
        )
        # then
        self.assertTrue(result.is_changed)
        self.assertEqual(
            character.attributes.accrued_remap_cooldown_date,
            accrued_remap_cooldown_date,
        )
        character.attributes.refresh_from_db()
        self.assertEqual(character.attributes.bonus_remaps, bonus_remaps)
        self.assertEqual(character.attributes.charisma, charisma)
        self.assertEqual(character.attributes.intelligence, intelligence)
        self.assertEqual(character.attributes.last_remap_date, last_remap_date)
        self.assertEqual(character.attributes.memory, memory)
        self.assertEqual(character.attributes.perception, perception)
        self.assertEqual(character.attributes.willpower, willpower)

    @pook.on
    def test_can_update_existing_attributes(self):
        # given
        character = CharacterFactory()
        CharacterAttributesFactory(character=character)
        accrued_remap_cooldown_date = now() + dt.timedelta(days=3)
        bonus_remaps = 3
        charisma = 16
        intelligence = 17
        last_remap_date = now() - dt.timedelta(days=3)
        memory = 18
        perception = 19
        willpower = 20
        pook.get(
            make_esi_url(f"characters/{character.character_id}/attributes"),
            reply=200,
            response_json={
                "accrued_remap_cooldown_date": accrued_remap_cooldown_date.isoformat(),
                "bonus_remaps": bonus_remaps,
                "charisma": charisma,
                "intelligence": intelligence,
                "last_remap_date": last_remap_date.isoformat(),
                "memory": memory,
                "perception": perception,
                "willpower": willpower,
            },
        )
        # when
        result: UpdateSectionResult = CharacterAttributes.objects.update_or_create_esi(
            character
        )
        # then
        self.assertTrue(result.is_changed)
        character.attributes.refresh_from_db()
        self.assertEqual(character.attributes.charisma, charisma)
        self.assertEqual(character.attributes.intelligence, intelligence)
        self.assertEqual(character.attributes.last_remap_date, last_remap_date)
        self.assertEqual(character.attributes.memory, memory)
        self.assertEqual(character.attributes.perception, perception)
        self.assertEqual(character.attributes.willpower, willpower)
        self.assertEqual(character.attributes.bonus_remaps, bonus_remaps)
        self.assertEqual(
            character.attributes.accrued_remap_cooldown_date,
            accrued_remap_cooldown_date,
        )


class TestCharacter_UpdateContactLabels(TestCaseWithClearCache):
    @pook.on
    def test_should_create_labels_from_scratch(self):
        # given
        character = CharacterFactory()
        label_id = 42
        label_name = "friend"
        pook.get(
            make_esi_url(f"characters/{character.character_id}/contacts/labels"),
            reply=200,
            response_headers={"X-Pages": "1"},
            response_json=[{"label_id": label_id, "label_name": label_name}],
        )
        # when
        character.update_contact_labels()

        # then
        self.assertEqual(character.contact_labels.count(), 1)

        label: CharacterContactLabel = character.contact_labels.first()
        self.assertEqual(label.label_id, label_id)
        self.assertEqual(label.name, label_name)

    @pook.on
    def test_should_remove_obsolete_labels(self):
        # given
        character = CharacterFactory()
        CharacterContactLabelFactory(character=character, label_id=99)
        # given
        character = CharacterFactory()
        label_id = 42
        label_name = "friend"
        pook.get(
            make_esi_url(f"characters/{character.character_id}/contacts/labels"),
            reply=200,
            response_headers={"X-Pages": "1"},
            response_json=[{"label_id": label_id, "label_name": label_name}],
        )
        # when
        character.update_contact_labels()

        # then
        got = {obj.label_id for obj in character.contact_labels.all()}
        self.assertSetEqual(got, {label_id})

    @pook.on
    def test_should_update_existing_label(self):
        # given
        character = CharacterFactory()
        label = CharacterContactLabelFactory(character=character)
        label_name = "friend"
        pook.get(
            make_esi_url(f"characters/{character.character_id}/contacts/labels"),
            reply=200,
            response_headers={"X-Pages": "1"},
            response_json=[{"label_id": label.label_id, "label_name": label_name}],
        )
        # when
        character.update_contact_labels()

        # then
        label.refresh_from_db()
        self.assertEqual(label.name, "friend")

    @pook.on
    def test_should_remove_contacts_when_esi_returns_empty(self):
        # given
        character = CharacterFactory()
        CharacterContactLabelFactory(character=character)
        pook.get(
            make_esi_url(f"characters/{character.character_id}/contacts/labels"),
            reply=200,
            response_headers={"X-Pages": "1"},
            response_json=[],
        )
        # when
        character.update_contact_labels()

        # then
        got = {obj.label_id for obj in character.contact_labels.all()}
        self.assertFalse(got)


class TestCharacter_UpdateContacts(TestCaseWithClearCache):
    @pook.on
    def test_should_create_from_scratch(self):
        # given
        character = CharacterFactory()
        eve_entity = EveEntityCharacterFactory()
        label_id = 1
        standing = -5
        CharacterContactLabelFactory(character=character, label_id=label_id)
        pook.get(
            make_esi_url(f"characters/{character.character_id}/contacts"),
            reply=200,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "contact_id": eve_entity.id,
                    "contact_type": "character",
                    "is_blocked": False,
                    "is_watched": True,
                    "label_ids": [label_id],
                    "standing": standing,
                }
            ],
        )
        # when
        result = character.update_contacts()

        # then
        self.assertTrue(result.is_changed)
        self.assertEqual(character.contacts.count(), 1)

        obj: CharacterContact = character.contacts.first()
        self.assertEqual(obj.eve_entity, eve_entity)
        self.assertFalse(obj.is_blocked)
        self.assertTrue(obj.is_watched)
        self.assertEqual(obj.standing, standing)
        self.assertEqual({x.label_id for x in obj.labels.all()}, {label_id})

    @pook.on
    def test_should_remove_obsolete_contacts(self):
        # given
        character = CharacterFactory()
        eve_entity = EveEntityCharacterFactory()
        label_id = 1
        standing = -5
        CharacterContactLabelFactory(character=character, label_id=label_id)
        CharacterContactFactory(character=character)
        pook.get(
            make_esi_url(f"characters/{character.character_id}/contacts"),
            reply=200,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "contact_id": eve_entity.id,
                    "contact_type": "character",
                    "is_blocked": False,
                    "is_watched": True,
                    "label_ids": [label_id],
                    "standing": standing,
                }
            ],
        )
        # when
        result = character.update_contacts()

        # then
        self.assertTrue(result.is_changed)
        self.assertEqual(character.contacts.count(), 1)

        obj: CharacterContact = character.contacts.first()
        self.assertEqual(obj.eve_entity, eve_entity)

    @pook.on
    def test_should_update_existing_contact(self):
        # given
        character = CharacterFactory()
        contact = CharacterContactFactory(character=character)
        label_id = 1
        standing = -5
        CharacterContactLabelFactory(character=character, label_id=label_id)
        pook.get(
            make_esi_url(f"characters/{character.character_id}/contacts"),
            reply=200,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "contact_id": contact.eve_entity.id,
                    "contact_type": "character",
                    "is_blocked": False,
                    "is_watched": True,
                    "label_ids": [label_id],
                    "standing": standing,
                }
            ],
        )
        # when
        result = character.update_contacts()

        # then
        self.assertTrue(result.is_changed)
        self.assertEqual(character.contacts.count(), 1)

        obj: CharacterContact = character.contacts.first()
        self.assertFalse(obj.is_blocked)
        self.assertTrue(obj.is_watched)
        self.assertEqual(obj.standing, standing)
        self.assertEqual({x.label_id for x in obj.labels.all()}, {label_id})


class TestCharacter_UpdateContractHeaders(TestCaseWithClearCache):
    @pook.on
    def test_can_create_minimal_courier_contract(self):
        # given
        character = CharacterFactory()
        contract_id = 42
        end_location = LocationStationFactory()
        issuer = EveEntityCharacterFactory()
        issuer_corporation = EveEntityCorporationFactory()
        reward = 1234.56
        start_location = LocationStationFactory()
        date_issued = now() - dt.timedelta(hours=3)
        date_expired = date_issued + dt.timedelta(days=3)
        pook.get(
            make_esi_url(f"characters/{character.character_id}/contracts"),
            reply=200,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "assignee_id": 0,
                    "acceptor_id": 0,
                    "availability": "public",
                    "contract_id": contract_id,
                    "date_expired": date_expired.isoformat(),
                    "date_issued": date_issued.isoformat(),
                    "end_location_id": end_location.id,
                    "for_corporation": False,
                    "issuer_corporation_id": issuer_corporation.id,
                    "issuer_id": issuer.id,
                    "reward": reward,
                    "start_location_id": start_location.id,
                    "status": "outstanding",
                    "type": "courier",
                }
            ],
        )
        # when
        character.update_contract_headers()

        # then
        obj: CharacterContract = character.contracts.first()
        self.assertEqual(float(obj.reward), reward)
        self.assertEqual(obj.availability, CharacterContract.AVAILABILITY_PUBLIC)
        self.assertEqual(obj.contract_type, CharacterContract.TYPE_COURIER)
        self.assertEqual(obj.date_expired, date_expired)
        self.assertEqual(obj.date_issued, date_issued)
        self.assertEqual(obj.end_location, end_location)
        self.assertEqual(obj.issuer_corporation, issuer_corporation)
        self.assertEqual(obj.issuer, issuer)
        self.assertEqual(obj.start_location, start_location)
        self.assertEqual(obj.status, CharacterContract.STATUS_OUTSTANDING)
        self.assertFalse(obj.for_corporation)
        self.assertIsNone(obj.acceptor)
        self.assertIsNone(obj.assignee)
        self.assertIsNone(obj.buyout)
        self.assertIsNone(obj.collateral)
        self.assertIsNone(obj.days_to_complete)

    @pook.on
    def test_can_create_full_courier_contract(self):
        # given
        character = CharacterFactory()
        collateral = 10_000_000
        contract_id = 42
        days_to_complete = 1
        end_location = LocationStationFactory()
        issuer = EveEntityCharacterFactory()
        acceptor = EveEntityCharacterFactory()
        assignee = EveEntityCharacterFactory()
        issuer_corporation = EveEntityCorporationFactory()
        reward = 1234.56
        start_location = LocationStationFactory()
        title = "title"
        volume = 100_000
        date_issued = now() - dt.timedelta(hours=3)
        date_accepted = date_issued - dt.timedelta(hours=2)
        date_completed = date_accepted + dt.timedelta(hours=1)
        date_expired = date_issued + dt.timedelta(days=3)
        pook.get(
            make_esi_url(f"characters/{character.character_id}/contracts"),
            reply=200,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "assignee_id": assignee.id,
                    "acceptor_id": acceptor.id,
                    "availability": "personal",
                    "collateral": collateral,
                    "contract_id": contract_id,
                    "date_accepted": date_accepted.isoformat(),
                    "date_completed": date_completed.isoformat(),
                    "date_expired": date_expired.isoformat(),
                    "date_issued": date_issued.isoformat(),
                    "days_to_complete": days_to_complete,
                    "end_location_id": end_location.id,
                    "for_corporation": False,
                    "issuer_corporation_id": issuer_corporation.id,
                    "issuer_id": issuer.id,
                    "reward": reward,
                    "start_location_id": start_location.id,
                    "status": "finished",
                    "title": title,
                    "type": "courier",
                    "volume": volume,
                }
            ],
        )
        # when
        character.update_contract_headers()

        # then
        obj: CharacterContract = character.contracts.first()
        self.assertEqual(obj.contract_type, CharacterContract.TYPE_COURIER)
        self.assertEqual(obj.acceptor, acceptor)
        self.assertEqual(obj.assignee, assignee)
        self.assertEqual(obj.availability, CharacterContract.AVAILABILITY_PERSONAL)
        self.assertIsNone(obj.buyout)
        self.assertEqual(float(obj.collateral), collateral)
        self.assertEqual(obj.date_accepted, date_accepted)
        self.assertEqual(obj.date_completed, date_completed)
        self.assertEqual(obj.date_expired, date_expired)
        self.assertEqual(obj.date_issued, date_issued)
        self.assertEqual(obj.days_to_complete, days_to_complete)
        self.assertEqual(obj.end_location, end_location)
        self.assertFalse(obj.for_corporation)
        self.assertEqual(obj.issuer_corporation, issuer_corporation)
        self.assertEqual(obj.issuer, issuer)
        self.assertEqual(float(obj.reward), reward)
        self.assertEqual(obj.start_location, start_location)
        self.assertEqual(obj.status, CharacterContract.STATUS_FINISHED)
        self.assertEqual(obj.title, title)
        self.assertEqual(obj.volume, volume)

    @pook.on
    def test_should_keep_old_contracts_when_updating(self):
        # given
        character = CharacterFactory()
        contract_1 = CharacterContractItemExchangeFactory(character=character)
        contract_id = 42
        end_location = LocationStationFactory()
        issuer = EveEntityCharacterFactory()
        assignee = EveEntityCharacterFactory()
        issuer_corporation = EveEntityCorporationFactory()
        start_location = LocationStationFactory()
        date_issued = now() - dt.timedelta(hours=3)
        date_expired = date_issued + dt.timedelta(days=3)
        pook.get(
            make_esi_url(f"characters/{character.character_id}/contracts"),
            reply=200,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "assignee_id": assignee.id,
                    "acceptor_id": 0,
                    "availability": "personal",
                    "collateral": 100_000,
                    "contract_id": contract_id,
                    "date_expired": date_expired.isoformat(),
                    "date_issued": date_issued.isoformat(),
                    "days_to_complete": 3,
                    "end_location_id": end_location.id,
                    "for_corporation": False,
                    "issuer_corporation_id": issuer_corporation.id,
                    "issuer_id": issuer.id,
                    "reward": 10_000,
                    "start_location_id": start_location.id,
                    "status": "outstanding",
                    "type": "courier",
                    "title": "",
                    "volume": 100_000,
                }
            ],
        )
        # when
        character.update_contract_headers()

        # then
        got = extract(character.contracts, "contract_id")
        self.assertSetEqual(got, {contract_1.contract_id, contract_id})

    @pook.on
    def test_should_update_existing_contracts(self):
        # given
        character = CharacterFactory()
        contract = CharacterContractCourierFactory(character=character)
        acceptor = EveEntityCharacterFactory()
        date_accepted = contract.date_issued + dt.timedelta(hours=1)
        date_completed = contract.date_issued + dt.timedelta(hours=12)
        pook.get(
            make_esi_url(f"characters/{character.character_id}/contracts"),
            reply=200,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "acceptor_id": acceptor.id,
                    "assignee_id": 0,
                    "availability": "public",
                    "contract_id": contract.contract_id,
                    "date_accepted": date_accepted.isoformat(),
                    "date_completed": date_completed.isoformat(),
                    "date_expired": contract.date_expired.isoformat(),
                    "date_issued": contract.date_issued.isoformat(),
                    "end_location_id": contract.end_location.id,
                    "for_corporation": contract.for_corporation,
                    "issuer_corporation_id": contract.issuer_corporation.id,
                    "issuer_id": contract.issuer.id,
                    "reward": contract.reward,
                    "start_location_id": contract.start_location.id,
                    "status": "finished",
                    "type": "courier",
                }
            ],
        )
        # when
        character.update_contract_headers()

        # then
        obj: CharacterContract = character.contracts.first()
        self.assertEqual(obj.acceptor, acceptor)
        self.assertEqual(obj.date_accepted, date_accepted)
        self.assertEqual(obj.date_completed, date_completed)
        self.assertEqual(obj.status, CharacterContract.STATUS_FINISHED)

    @pook.on
    def test_should_exclude_and_remove_contracts_older_then_retention_limit(self):
        # given
        character = CharacterFactory()
        contract_1_id = 42
        contract_2_id = 54
        location_1 = LocationStationFactory()
        location_2 = LocationStationFactory()
        retention_cutoff = now() - dt.timedelta(days=30)
        contract_3 = CharacterContractCourierFactory(character=character)
        CharacterContractCourierFactory(
            character=character,
            date_expired=retention_cutoff - dt.timedelta(seconds=1),
        )
        pook.get(
            make_esi_url(f"characters/{character.character_id}/contracts"),
            reply=200,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "assignee_id": 0,
                    "acceptor_id": 0,
                    "availability": "public",
                    "contract_id": contract_1_id,
                    "date_expired": retention_cutoff.isoformat(),
                    "date_issued": retention_cutoff.isoformat(),
                    "end_location_id": location_2.id,
                    "for_corporation": False,
                    "issuer_corporation_id": EveEntityCorporationFactory().id,
                    "issuer_id": EveEntityCharacterFactory().id,
                    "reward": 123.45,
                    "start_location_id": location_1.id,
                    "status": "outstanding",
                    "type": "courier",
                },
                {
                    "assignee_id": 0,
                    "acceptor_id": 0,
                    "availability": "public",
                    "contract_id": contract_2_id,
                    "date_expired": now().isoformat(),
                    "date_issued": now().isoformat(),
                    "end_location_id": location_2.id,
                    "for_corporation": False,
                    "issuer_corporation_id": EveEntityCorporationFactory().id,
                    "issuer_id": EveEntityCharacterFactory().id,
                    "reward": 123.45,
                    "start_location_id": location_1.id,
                    "status": "outstanding",
                    "type": "courier",
                },
            ],
        )
        # when
        with patch(MODULE_PATH + ".data_retention_cutoff", lambda: retention_cutoff):
            character.update_contract_headers()
        # then
        got = extract(character.contracts, "contract_id")
        self.assertSetEqual(got, {contract_2_id, contract_3.contract_id})

    @pook.on
    def test_can_create_minimal_item_exchange_contract(self):
        # given
        character = CharacterFactory()
        contract_id = 42
        issuer = EveEntityCharacterFactory()
        issuer_corporation = EveEntityCorporationFactory()
        date_issued = now() - dt.timedelta(hours=3)
        date_expired = date_issued + dt.timedelta(days=3)
        pook.get(
            make_esi_url(f"characters/{character.character_id}/contracts"),
            reply=200,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "assignee_id": 0,
                    "acceptor_id": 0,
                    "availability": "public",
                    "contract_id": contract_id,
                    "date_expired": date_expired.isoformat(),
                    "date_issued": date_issued.isoformat(),
                    "for_corporation": False,
                    "issuer_corporation_id": issuer_corporation.id,
                    "issuer_id": issuer.id,
                    "status": "outstanding",
                    "type": "item_exchange",
                }
            ],
        )
        # when
        character.update_contract_headers()

        # then
        obj: CharacterContract = character.contracts.first()
        self.assertEqual(obj.availability, CharacterContract.AVAILABILITY_PUBLIC)
        self.assertEqual(obj.contract_type, CharacterContract.TYPE_ITEM_EXCHANGE)
        self.assertEqual(obj.date_expired, date_expired)
        self.assertEqual(obj.date_issued, date_issued)
        self.assertEqual(obj.issuer_corporation, issuer_corporation)
        self.assertEqual(obj.issuer, issuer)
        self.assertEqual(obj.status, CharacterContract.STATUS_OUTSTANDING)
        self.assertFalse(obj.for_corporation)
        self.assertEqual(obj.items.count(), 0)

    @pook.on
    def test_can_create_minimal_auction_contract(self):
        # given
        character = CharacterFactory()
        contract_id = 42
        issuer = EveEntityCharacterFactory()
        issuer_corporation = EveEntityCorporationFactory()
        date_issued = now() - dt.timedelta(hours=3)
        date_expired = date_issued + dt.timedelta(days=3)
        pook.get(
            make_esi_url(f"characters/{character.character_id}/contracts"),
            reply=200,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "assignee_id": 0,
                    "acceptor_id": 0,
                    "availability": "public",
                    "contract_id": contract_id,
                    "date_expired": date_expired.isoformat(),
                    "date_issued": date_issued.isoformat(),
                    "for_corporation": False,
                    "issuer_corporation_id": issuer_corporation.id,
                    "issuer_id": issuer.id,
                    "status": "outstanding",
                    "type": "auction",
                }
            ],
        )
        # when
        character.update_contract_headers()

        # then
        obj: CharacterContract = character.contracts.first()
        self.assertEqual(obj.availability, CharacterContract.AVAILABILITY_PUBLIC)
        self.assertEqual(obj.contract_type, CharacterContract.TYPE_AUCTION)
        self.assertEqual(obj.date_expired, date_expired)
        self.assertEqual(obj.date_issued, date_issued)
        self.assertEqual(obj.issuer_corporation, issuer_corporation)
        self.assertEqual(obj.issuer, issuer)
        self.assertEqual(obj.status, CharacterContract.STATUS_OUTSTANDING)
        self.assertFalse(obj.for_corporation)
        self.assertEqual(obj.items.count(), 0)


class TestCharacter_UpdateContractItems(TestCaseWithClearCache):
    @pook.on
    def test_can_create_new_item_minimal(self):
        character = CharacterFactory()
        contract = CharacterContractItemExchangeFactory(items=False)
        quantity = 3
        record_id = 1
        eve_type = EveTypeFactory()
        is_included = True
        is_singleton = False
        pook.get(
            make_esi_url(
                f"characters/{character.character_id}/contracts/{contract.contract_id}/items"
            ),
            reply=200,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "is_included": is_included,
                    "is_singleton": is_singleton,
                    "quantity": quantity,
                    "record_id": record_id,
                    "type_id": eve_type.id,
                }
            ],
        )
        # when
        character.update_contract_items(contract)

        # then
        self.assertEqual(contract.items.count(), 1)
        item: CharacterContractItem = contract.items.first()
        self.assertEqual(item.is_included, is_included)
        self.assertEqual(item.is_singleton, is_singleton)
        self.assertIsNone(item.raw_quantity)
        self.assertEqual(item.quantity, quantity)
        self.assertEqual(item.eve_type, eve_type)

    @pook.on
    def test_can_create_new_item_full(self):
        character = CharacterFactory()
        contract = CharacterContractItemExchangeFactory(items=False)
        eve_type = EveTypeFactory()
        is_included = True
        is_singleton = True
        quantity = 3
        raw_quantity = -1
        record_id = 1
        pook.get(
            make_esi_url(
                f"characters/{character.character_id}/contracts/{contract.contract_id}/items"
            ),
            reply=200,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "is_included": is_included,
                    "is_singleton": is_singleton,
                    "quantity": quantity,
                    "raw_quantity": raw_quantity,
                    "record_id": record_id,
                    "type_id": eve_type.id,
                }
            ],
        )
        # when
        CharacterContractItem.objects.update_or_create_esi(character, contract)

        # then
        self.assertEqual(contract.items.count(), 1)
        item: CharacterContractItem = contract.items.first()
        self.assertEqual(item.record_id, record_id)
        self.assertEqual(item.is_included, is_included)
        self.assertEqual(item.is_singleton, is_singleton)
        self.assertEqual(item.raw_quantity, raw_quantity)
        self.assertEqual(item.quantity, quantity)
        self.assertEqual(item.eve_type, eve_type)


class TestCharacter_UpdateContractBids(TestCaseWithClearCache):
    @pook.on
    def test_can_add_first_bid(self):
        character = CharacterFactory()
        contract = CharacterContractAuctionFactory()
        amount = 123.45
        bid_id = 42
        bidder = EveEntityCharacterFactory()
        date_bid = now()
        pook.get(
            make_esi_url(
                f"characters/{character.character_id}/contracts/{contract.contract_id}/bids"
            ),
            reply=200,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "amount": amount,
                    "bid_id": bid_id,
                    "bidder_id": bidder.id,
                    "date_bid": date_bid.isoformat(),
                }
            ],
        )
        # when
        character.update_contract_bids(contract)

        # then
        self.assertEqual(contract.bids.count(), 1)
        item: CharacterContractBid = contract.bids.first()
        self.assertEqual(item.amount, amount)
        self.assertEqual(item.bid_id, bid_id)
        self.assertEqual(item.bidder, bidder)
        self.assertEqual(item.date_bid, date_bid)

    @pook.on
    def test_can_add_additional_bids(self):
        character = CharacterFactory()
        contract = CharacterContractAuctionFactory(bids=3)
        amount = 123.45
        bid_id = 42
        bidder = EveEntityCharacterFactory()
        date_bid = now()
        pook.get(
            make_esi_url(
                f"characters/{character.character_id}/contracts/{contract.contract_id}/bids"
            ),
            reply=200,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "amount": amount,
                    "bid_id": bid_id,
                    "bidder_id": bidder.id,
                    "date_bid": date_bid.isoformat(),
                }
            ],
        )
        # when
        character.update_contract_bids(contract)

        # then
        self.assertEqual(contract.bids.count(), 4)
        item: CharacterContractBid = contract.bids.last()
        self.assertEqual(item.amount, amount)
        self.assertEqual(item.bid_id, bid_id)
        self.assertEqual(item.bidder, bidder)
        self.assertEqual(item.date_bid, date_bid)


class TestCharacterContractItemManager_AnnotatePricing(NoSocketsTestCase):
    def test_can_annotate_normal_item(self):
        # given
        contract = CharacterContractItemExchangeFactory(items=False)
        item_1 = CharacterContractItemFactory(
            contract=contract, is_included=True, quantity=2
        )
        EveMarketPriceFactory(eve_type=item_1.eve_type, average_price=5000000)

        # when
        qs = contract.items.annotate_pricing()

        # then
        item_2 = qs.first()
        self.assertEqual(item_2.price, 5000000)
        self.assertEqual(item_2.total, 10000000)

    def test_should_not_annotate_bpos(self):
        # given
        contract = CharacterContractItemExchangeFactory(items=False)
        item_1 = CharacterContractItemFactory(
            contract=contract,
            is_included=True,
            is_singleton=False,
            raw_quantity=-2,
        )
        EveMarketPriceFactory(eve_type=item_1.eve_type, average_price=5000000)

        # when
        qs = contract.items.annotate_pricing()

        # then
        item_2 = qs.first()
        self.assertIsNone(item_2.price)
        self.assertIsNone(item_2.total)
