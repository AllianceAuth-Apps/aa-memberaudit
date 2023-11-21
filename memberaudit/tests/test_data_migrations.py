from importlib import import_module

from django.apps import apps
from django.db import connection
from django.test import TestCase

from memberaudit.models import Location
from memberaudit.tests.testdata.factories import (
    create_character_asset,
    create_character_contract_courier,
    create_character_jump_clone,
    create_character_location,
    create_character_wallet_transaction,
    create_location,
)
from memberaudit.tests.testdata.load_entities import load_entities
from memberaudit.tests.testdata.load_eveuniverse import load_eveuniverse
from memberaudit.tests.utils import create_memberaudit_character

data_migration = import_module("memberaudit.migrations.0016_fix_invalid_locations")


class TestFixInvalidLocations(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        cls.character = create_memberaudit_character(1001)

    def test_should_do_nothing_when_no_invalid_locations(self):
        # given
        asset = create_character_asset(
            character=self.character, location=create_location()
        )
        contract = create_character_contract_courier(
            character=self.character,
            start_location=create_location(),
            end_location=create_location(),
        )
        location = create_character_location(
            character=self.character, location=create_location()
        )
        jump_clone = create_character_jump_clone(
            character=self.character, location=create_location()
        )
        wallet = create_character_wallet_transaction(
            character=self.character, location=create_location()
        )
        # when
        data_migration.forwards(apps, connection.schema_editor())
        # then
        asset.refresh_from_db()
        self.assertTrue(asset.location)
        contract.refresh_from_db()
        self.assertTrue(contract.start_location)
        self.assertTrue(contract.end_location)
        location.refresh_from_db()
        self.assertTrue(location.location)
        jump_clone.refresh_from_db()
        self.assertTrue(jump_clone.location)
        wallet.refresh_from_db()
        self.assertTrue(wallet.location)

    def test_should_delete_invalid_locations_and_fix_related_assets(self):
        # given
        valid_location = create_location()
        invalid_location = create_location()
        normal_asset = create_character_asset(
            item_id=invalid_location.id,
            character=self.character,
            location=valid_location,
        )
        corrupted_asset = create_character_asset(
            character=self.character, location=invalid_location
        )

        # when
        data_migration.forwards(apps, connection.schema_editor())

        # then
        location_ids = set(Location.objects.values_list("id", flat=True))
        self.assertSetEqual(
            location_ids, {valid_location.id, Location.LOCATION_UNKNOWN_ID}
        )
        normal_asset.refresh_from_db()
        self.assertEqual(normal_asset.location, valid_location)
        corrupted_asset.refresh_from_db()
        self.assertEqual(corrupted_asset.location.id, Location.LOCATION_UNKNOWN_ID)
