from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.db import IntegrityError
from django.test import TestCase

from allianceauth.eveonline.models import EveCharacter

from memberaudit.management.commands import memberaudit_fix_locations
from memberaudit.models import Character, Location
from memberaudit.tests.testdata.factories import (
    create_character,
    create_character_asset,
    create_character_contract_courier,
    create_character_jump_clone,
    create_character_location,
    create_character_update_status,
    create_character_wallet_transaction,
    create_location,
)
from memberaudit.tests.testdata.load_entities import load_entities
from memberaudit.tests.testdata.load_eveuniverse import load_eveuniverse
from memberaudit.tests.utils import create_memberaudit_character

MODULE_PATH = "memberaudit.management.commands.memberaudit_fix_locations"


@patch(MODULE_PATH + ".tasks.update_character_section", spec=True)
@patch(MODULE_PATH + ".tasks.update_character_contracts", spec=True)
@patch(MODULE_PATH + ".tasks.update_character_assets", spec=True)
class TestFixInvalidLocations(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        cls.character_1001 = create_memberaudit_character(1001)

    def test_should_do_nothing_when_no_invalid_locations(self, *args, **kwargs):
        # given
        asset = create_character_asset(
            character=self.character_1001, location=create_location()
        )
        contract = create_character_contract_courier(
            character=self.character_1001,
            start_location=create_location(),
            end_location=create_location(),
        )
        location = create_character_location(
            character=self.character_1001, location=create_location()
        )
        jump_clone = create_character_jump_clone(
            character=self.character_1001, location=create_location()
        )
        wallet = create_character_wallet_transaction(
            character=self.character_1001, location=create_location()
        )
        out = StringIO()

        # when
        call_command("memberaudit_fix_locations", "--noinput", stdout=out)

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

    def test_should_delete_invalid_locations_and_fix_related_assets(
        self,
        mock_task_update_character_assets,
        mock_task_update_character_contracts,
        mock_task_update_character_section,
    ):
        # given characters
        character_1002 = create_memberaudit_character(1002)
        character_1002.is_disabled = True
        character_1002.save()
        character_1101 = create_character(  # orphan
            EveCharacter.objects.get(character_id=1101)
        )
        character_1003 = create_memberaudit_character(1003)  # no corruption

        # given locations
        valid_location_1 = create_location()
        valid_location_2 = create_location()
        invalid_location_1 = create_location()
        invalid_location_2 = create_location()

        # given assets
        normal_asset_1001 = create_character_asset(
            item_id=invalid_location_1.id,
            character=self.character_1001,
            location=valid_location_1,
        )
        corrupted_asset_1001 = create_character_asset(
            character=self.character_1001, location=invalid_location_1
        )
        status_assets_1001 = create_character_update_status(
            character=self.character_1001,
            section=Character.UpdateSection.ASSETS,
            content_hash_1="some_data",
        )

        corrupted_asset_1002 = create_character_asset(
            character=character_1002, location=invalid_location_1
        )
        status_assets_1002 = create_character_update_status(
            character=character_1002,
            section=Character.UpdateSection.ASSETS,
            content_hash_1="some_data",
        )

        corrupted_asset_1101 = create_character_asset(
            character=character_1101, location=invalid_location_1
        )
        status_assets_1101 = create_character_update_status(
            character=character_1101,
            section=Character.UpdateSection.ASSETS,
            content_hash_1="some_data",
        )
        corrupted_asset_1101 = create_character_jump_clone(
            character=character_1101, location=invalid_location_1
        )

        normal_asset_1003 = create_character_asset(
            item_id=invalid_location_2.id,
            character=character_1003,
            location=valid_location_1,
        )

        # given clones
        normal_clone_1001 = create_character_jump_clone(
            character=self.character_1001, location=valid_location_1
        )
        corrupted_clone_1001 = create_character_jump_clone(
            character=self.character_1001, location=invalid_location_1
        )
        status_clones_1001 = create_character_update_status(
            character=self.character_1001,
            section=Character.UpdateSection.JUMP_CLONES,
            content_hash_1="some_data",
        )

        corrupted_clone_1002 = create_character_jump_clone(
            character=character_1002, location=invalid_location_1
        )
        status_clones_1002 = create_character_update_status(
            character=character_1002,
            section=Character.UpdateSection.JUMP_CLONES,
            content_hash_1="some_data",
        )

        corrupted_clone_1101 = create_character_jump_clone(
            character=character_1101, location=invalid_location_1
        )
        status_clones_1101 = create_character_update_status(
            character=character_1101,
            section=Character.UpdateSection.JUMP_CLONES,
            content_hash_1="some_data",
        )

        # given character locations
        corrupted_location_1001 = create_character_location(
            character=self.character_1001, location=invalid_location_1
        )
        status_location_1001 = create_character_update_status(
            character=self.character_1001,
            section=Character.UpdateSection.LOCATION,
            content_hash_1="some_data",
        )

        corrupted_location_1002 = create_character_location(
            character=character_1002, location=invalid_location_1
        )
        status_location_1002 = create_character_update_status(
            character=character_1002,
            section=Character.UpdateSection.LOCATION,
            content_hash_1="some_data",
        )

        normal_location_1003 = create_character_location(
            character=character_1003, location=valid_location_1
        )
        status_location_1003 = create_character_update_status(
            character=character_1003,
            section=Character.UpdateSection.LOCATION,
            content_hash_1="some_data",
        )

        corrupted_location_1101 = create_character_location(
            character=character_1101, location=invalid_location_1
        )
        status_location_1101 = create_character_update_status(
            character=character_1101,
            section=Character.UpdateSection.LOCATION,
            content_hash_1="some_data",
        )

        # given wallet transactions
        normal_transaction_1001 = create_character_wallet_transaction(
            character=self.character_1001, location=valid_location_1
        )
        corrupted_transaction_1001 = create_character_wallet_transaction(
            character=self.character_1001, location=invalid_location_1
        )
        status_transactions_1001 = create_character_update_status(
            character=self.character_1001,
            section=Character.UpdateSection.WALLET_TRANSACTIONS,
            content_hash_1="some_data",
        )

        corrupted_transaction_1002 = create_character_wallet_transaction(
            character=character_1002, location=invalid_location_1
        )
        status_transactions_1002 = create_character_update_status(
            character=character_1002,
            section=Character.UpdateSection.WALLET_TRANSACTIONS,
            content_hash_1="some_data",
        )

        corrupted_transaction_1101 = create_character_wallet_transaction(
            character=character_1101, location=invalid_location_1
        )
        status_transactions_1101 = create_character_update_status(
            character=character_1101,
            section=Character.UpdateSection.WALLET_TRANSACTIONS,
            content_hash_1="some_data",
        )

        # given courier contracts
        normal_contract_1001 = create_character_contract_courier(
            character=self.character_1001,
            start_location=valid_location_1,
            end_location=valid_location_2,
        )
        corrupted_contract_1001 = create_character_contract_courier(
            character=self.character_1001,
            start_location=invalid_location_1,
            end_location=invalid_location_2,
        )
        status_contracts_1001 = create_character_update_status(
            character=self.character_1001,
            section=Character.UpdateSection.CONTRACTS,
            content_hash_1="some_data",
        )

        corrupted_contract_1002 = create_character_contract_courier(
            character=character_1002,
            start_location=invalid_location_1,
            end_location=invalid_location_2,
        )
        status_contracts_1002 = create_character_update_status(
            character=character_1002,
            section=Character.UpdateSection.CONTRACTS,
            content_hash_1="some_data",
        )

        corrupted_contract_1101 = create_character_contract_courier(
            character=character_1101,
            start_location=invalid_location_1,
            end_location=invalid_location_2,
        )
        status_contracts_1101 = create_character_update_status(
            character=character_1101,
            section=Character.UpdateSection.CONTRACTS,
            content_hash_1="some_data",
        )
        out = StringIO()

        # when
        call_command("memberaudit_fix_locations", "--noinput", stdout=out)

        # then locations
        location_ids = set(Location.objects.values_list("id", flat=True))
        self.assertSetEqual(
            location_ids,
            {valid_location_1.id, valid_location_2.id, Location.LOCATION_UNKNOWN_ID},
        )

        # then assets
        normal_asset_1001.refresh_from_db()
        self.assertEqual(normal_asset_1001.location, valid_location_1)
        corrupted_asset_1001.refresh_from_db()
        self.assertEqual(corrupted_asset_1001.location.id, Location.LOCATION_UNKNOWN_ID)
        status_assets_1001.refresh_from_db()
        self.assertFalse(status_assets_1001.content_hash_1)

        corrupted_asset_1002.refresh_from_db()
        self.assertEqual(corrupted_asset_1002.location.id, Location.LOCATION_UNKNOWN_ID)
        status_assets_1002.refresh_from_db()
        self.assertFalse(status_assets_1002.content_hash_1)

        corrupted_asset_1101.refresh_from_db()
        self.assertEqual(corrupted_asset_1101.location.id, Location.LOCATION_UNKNOWN_ID)
        status_assets_1101.refresh_from_db()
        self.assertFalse(status_assets_1101.content_hash_1)

        normal_asset_1003.refresh_from_db()
        self.assertEqual(normal_asset_1003.location, valid_location_1)

        assets_task_calls = [
            o[1]["kwargs"]
            for o in mock_task_update_character_assets.apply_async.call_args_list
        ]
        self.assertEqual(
            len(assets_task_calls), 1
        )  # only start tasks for 1001 character
        params = assets_task_calls[0]
        self.assertEqual(params["character_pk"], self.character_1001.pk)

        # parse section task calls into dict
        section_tasks_calls_list = [
            o[1]["kwargs"]
            for o in mock_task_update_character_section.apply_async.call_args_list
        ]
        self.assertEqual(
            len(section_tasks_calls_list), 3
        )  # only start tasks for 1001 character
        section_tasks_calls = {
            params["section"]: params for params in section_tasks_calls_list
        }

        # then clones
        normal_clone_1001.refresh_from_db()
        self.assertEqual(normal_clone_1001.location, valid_location_1)
        corrupted_clone_1001.refresh_from_db()
        self.assertEqual(corrupted_clone_1001.location.id, Location.LOCATION_UNKNOWN_ID)
        status_clones_1001.refresh_from_db()
        self.assertFalse(status_clones_1001.content_hash_1)

        corrupted_clone_1002.refresh_from_db()
        self.assertEqual(corrupted_clone_1002.location.id, Location.LOCATION_UNKNOWN_ID)
        status_clones_1002.refresh_from_db()
        self.assertFalse(status_clones_1002.content_hash_1)

        corrupted_clone_1101.refresh_from_db()
        self.assertEqual(corrupted_clone_1101.location.id, Location.LOCATION_UNKNOWN_ID)
        status_clones_1101.refresh_from_db()
        self.assertFalse(status_clones_1101.content_hash_1)

        params = section_tasks_calls[Character.UpdateSection.JUMP_CLONES.value]
        self.assertEqual(params["character_pk"], self.character_1001.pk)

        # then character locations
        corrupted_location_1001.refresh_from_db()
        self.assertEqual(
            corrupted_location_1001.location.id, Location.LOCATION_UNKNOWN_ID
        )
        status_location_1001.refresh_from_db()
        self.assertFalse(status_location_1001.content_hash_1)

        corrupted_location_1002.refresh_from_db()
        self.assertEqual(
            corrupted_location_1002.location.id, Location.LOCATION_UNKNOWN_ID
        )
        status_location_1002.refresh_from_db()
        self.assertFalse(status_location_1002.content_hash_1)

        normal_location_1003.refresh_from_db()
        self.assertEqual(normal_location_1003.location, valid_location_1)
        self.assertTrue(status_location_1003.content_hash_1)

        corrupted_location_1101.refresh_from_db()
        self.assertEqual(
            corrupted_location_1101.location.id, Location.LOCATION_UNKNOWN_ID
        )
        status_location_1101.refresh_from_db()
        self.assertFalse(status_location_1101.content_hash_1)

        params = section_tasks_calls[Character.UpdateSection.LOCATION.value]
        self.assertEqual(params["character_pk"], self.character_1001.pk)

        # then wallet transactions
        normal_transaction_1001.refresh_from_db()
        self.assertEqual(normal_transaction_1001.location, valid_location_1)
        corrupted_transaction_1001.refresh_from_db()
        self.assertEqual(
            corrupted_transaction_1001.location.id, Location.LOCATION_UNKNOWN_ID
        )
        status_transactions_1001.refresh_from_db()
        self.assertFalse(status_transactions_1001.content_hash_1)

        corrupted_transaction_1002.refresh_from_db()
        self.assertEqual(
            corrupted_transaction_1002.location.id, Location.LOCATION_UNKNOWN_ID
        )
        status_transactions_1002.refresh_from_db()
        self.assertFalse(status_transactions_1002.content_hash_1)

        corrupted_transaction_1101.refresh_from_db()
        self.assertEqual(
            corrupted_transaction_1101.location.id, Location.LOCATION_UNKNOWN_ID
        )
        status_transactions_1101.refresh_from_db()
        self.assertFalse(status_transactions_1101.content_hash_1)

        params = section_tasks_calls[Character.UpdateSection.WALLET_TRANSACTIONS.value]
        self.assertEqual(params["character_pk"], self.character_1001.pk)

        # then contracts
        normal_contract_1001.refresh_from_db()
        self.assertEqual(normal_contract_1001.start_location, valid_location_1)
        self.assertEqual(normal_contract_1001.end_location, valid_location_2)
        corrupted_contract_1001.refresh_from_db()
        self.assertEqual(
            corrupted_contract_1001.start_location.id, Location.LOCATION_UNKNOWN_ID
        )
        self.assertEqual(
            corrupted_contract_1001.end_location.id, Location.LOCATION_UNKNOWN_ID
        )
        status_contracts_1001.refresh_from_db()
        self.assertFalse(status_contracts_1001.content_hash_1)

        corrupted_contract_1002.refresh_from_db()
        self.assertEqual(
            corrupted_contract_1002.start_location.id, Location.LOCATION_UNKNOWN_ID
        )
        self.assertEqual(
            corrupted_contract_1002.end_location.id, Location.LOCATION_UNKNOWN_ID
        )
        status_contracts_1002.refresh_from_db()
        self.assertFalse(status_contracts_1002.content_hash_1)

        corrupted_contract_1101.refresh_from_db()
        self.assertEqual(
            corrupted_contract_1101.start_location.id, Location.LOCATION_UNKNOWN_ID
        )
        self.assertEqual(
            corrupted_contract_1101.end_location.id, Location.LOCATION_UNKNOWN_ID
        )

        status_contracts_1101.refresh_from_db()
        self.assertFalse(status_contracts_1101.content_hash_1)

        contract_task_calls = [
            o[1]["kwargs"]
            for o in mock_task_update_character_contracts.apply_async.call_args_list
        ]
        self.assertEqual(
            len(contract_task_calls), 1
        )  # only start tasks for 1001 character
        params = contract_task_calls[0]
        self.assertEqual(params["character_pk"], self.character_1001.pk)

    def test_should_ignore_db_issue_when_fixing_section(self, *args, **kwargs):
        # given
        valid_location = create_location()
        invalid_location = create_location()

        asset = create_character_asset(
            character=self.character_1001,
            location=valid_location,
            item_id=invalid_location.id,
        )
        corrupted_asset = create_character_asset(
            character=self.character_1001, location=invalid_location
        )
        out = StringIO()

        # when
        with patch(
            MODULE_PATH + ".CharacterAsset",
            wraps=memberaudit_fix_locations.CharacterAsset,
        ) as mock:
            mock.objects.filter.return_value.update.side_effect = IntegrityError
            call_command("memberaudit_fix_locations", "--noinput", stdout=out)

        # then
        asset.refresh_from_db()
        self.assertTrue(asset.location)
        corrupted_asset.refresh_from_db()
        self.assertEqual(corrupted_asset.location.id, invalid_location.id)

    def test_should_start_update_tasks_for_needed_characters_only(
        self,
        mock_task_update_character_assets,
        mock_task_update_character_contracts,
        mock_task_update_character_section,
    ):
        # given
        character_pks = memberaudit_fix_locations.CharacterPkContainer()
        asset_pk = 1001
        character_pks.assets.add(asset_pk)
        clone_pk = 1002
        character_pks.clones.add(clone_pk)
        contract_pk = 1002
        character_pks.contracts.add(contract_pk)
        location_pk = 1003
        character_pks.locations.add(location_pk)
        transaction_pk = 1004
        character_pks.transactions.add(transaction_pk)

        # when
        memberaudit_fix_locations.start_character_updates(character_pks)

        # then
        section_tasks_calls_list = [
            o[1]["kwargs"]
            for o in mock_task_update_character_section.apply_async.call_args_list
        ]
        self.assertEqual(len(section_tasks_calls_list), 3)
        section_tasks_calls = {
            params["section"]: params for params in section_tasks_calls_list
        }

        assets_task_calls = [
            o[1]["kwargs"]
            for o in mock_task_update_character_assets.apply_async.call_args_list
        ]
        self.assertEqual(len(assets_task_calls), 1)
        params = assets_task_calls[0]
        self.assertEqual(params["character_pk"], asset_pk)
        self.assertTrue(params["force_update"])

        params = section_tasks_calls[Character.UpdateSection.JUMP_CLONES.value]
        self.assertEqual(params["character_pk"], clone_pk)
        self.assertTrue(params["force_update"])

        contract_task_calls = [
            o[1]["kwargs"]
            for o in mock_task_update_character_contracts.apply_async.call_args_list
        ]
        self.assertEqual(len(contract_task_calls), 1)
        params = contract_task_calls[0]
        self.assertEqual(params["character_pk"], contract_pk)
        self.assertTrue(params["force_update"])

        params = section_tasks_calls[Character.UpdateSection.LOCATION.value]
        self.assertEqual(params["character_pk"], location_pk)
        self.assertTrue(params["force_update"])

        params = section_tasks_calls[Character.UpdateSection.WALLET_TRANSACTIONS.value]
        self.assertEqual(params["character_pk"], transaction_pk)
        self.assertTrue(params["force_update"])

    def test_should_allow_excluding_locations(self, *args, **kwargs):
        # given
        valid_location = create_location()
        invalid_location_1 = create_location()
        invalid_location_2 = create_location()
        invalid_location_3 = create_location()

        create_character_asset(
            character=self.character_1001,
            location=valid_location,
            item_id=invalid_location_1.id,
        )
        corrupted_asset_1 = create_character_asset(
            character=self.character_1001, location=invalid_location_1
        )
        create_character_asset(
            character=self.character_1001,
            location=valid_location,
            item_id=invalid_location_2.id,
        )
        corrupted_asset_2 = create_character_asset(
            character=self.character_1001, location=invalid_location_2
        )
        create_character_asset(
            character=self.character_1001,
            location=valid_location,
            item_id=invalid_location_3.id,
        )
        corrupted_asset_3 = create_character_asset(
            character=self.character_1001, location=invalid_location_3
        )

        out = StringIO()

        # when
        call_command(
            "memberaudit_fix_locations",
            "--noinput",
            "--exclude-locations",
            str(invalid_location_1.id),
            str(invalid_location_3.id),
            stdout=out,
        )

        # then
        corrupted_asset_1.refresh_from_db()
        self.assertEqual(corrupted_asset_1.location.id, invalid_location_1.id)

        corrupted_asset_2.refresh_from_db()
        self.assertEqual(corrupted_asset_2.location.id, Location.LOCATION_UNKNOWN_ID)

        corrupted_asset_3.refresh_from_db()
        self.assertEqual(corrupted_asset_3.location.id, invalid_location_3.id)
