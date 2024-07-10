from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.db import IntegrityError
from django.test import TestCase, tag

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


@patch(MODULE_PATH + ".tasks.update_character_wallet_transactions", spec=True)
@patch(MODULE_PATH + ".tasks.update_character_location", spec=True)
@patch(MODULE_PATH + ".tasks.update_character_jump_clones", spec=True)
@patch(MODULE_PATH + ".tasks.update_character_contracts", spec=True)
@patch(MODULE_PATH + ".tasks.update_character_assets", spec=True)
class TestFixInvalidLocations(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        cls.character_1001 = create_memberaudit_character(1001)

    def _extract_character_from_called_task(self, mock_task):
        assets_task_calls = [
            o[1]["kwargs"] for o in mock_task.apply_async.call_args_list
        ]
        self.assertEqual(len(assets_task_calls), 1)
        params = assets_task_calls[0]
        return params["character_pk"]

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
        mock_task_update_character_jump_clones,
        mock_task_update_character_location,
        mock_task_update_character_wallet_transactions,
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

        called_character_pk_in_task = self._extract_character_from_called_task(
            mock_task_update_character_assets
        )
        self.assertEqual(called_character_pk_in_task, self.character_1001.pk)

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

        called_character_pk_in_task = self._extract_character_from_called_task(
            mock_task_update_character_jump_clones
        )
        self.assertEqual(called_character_pk_in_task, self.character_1001.pk)

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

        called_character_pk_in_task = self._extract_character_from_called_task(
            mock_task_update_character_location
        )
        self.assertEqual(called_character_pk_in_task, self.character_1001.pk)

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

        called_character_pk_in_task = self._extract_character_from_called_task(
            mock_task_update_character_wallet_transactions
        )
        self.assertEqual(called_character_pk_in_task, self.character_1001.pk)

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

        called_character_pk_in_task = self._extract_character_from_called_task(
            mock_task_update_character_contracts
        )
        self.assertEqual(called_character_pk_in_task, self.character_1001.pk)

    @tag("breaks_with_py311")  # FIXME: Find solution
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
        mock_task_update_character_jump_clones,
        mock_task_update_character_location,
        mock_task_update_character_wallet_transactions,
    ):
        # given
        character_pks = memberaudit_fix_locations.CharacterPkContainer()
        assets_pk = 1001
        character_pks.assets.add(assets_pk)
        clones_pk = 1002
        character_pks.clones.add(clones_pk)
        contracts_pk = 1002
        character_pks.contracts.add(contracts_pk)
        location_pk = 1003
        character_pks.locations.add(location_pk)
        transactions_pk = 1004
        character_pks.transactions.add(transactions_pk)

        # when
        memberaudit_fix_locations.start_character_updates(character_pks)

        # then
        character_pk_called = self._extract_character_from_called_task(
            mock_task_update_character_assets
        )
        self.assertEqual(character_pk_called, assets_pk)

        character_pk_called = self._extract_character_from_called_task(
            mock_task_update_character_contracts
        )
        self.assertEqual(character_pk_called, contracts_pk)

        character_pk_called = self._extract_character_from_called_task(
            mock_task_update_character_jump_clones
        )
        self.assertEqual(character_pk_called, clones_pk)

        character_pk_called = self._extract_character_from_called_task(
            mock_task_update_character_location
        )
        self.assertEqual(character_pk_called, location_pk)

        character_pk_called = self._extract_character_from_called_task(
            mock_task_update_character_wallet_transactions
        )
        self.assertEqual(character_pk_called, transactions_pk)

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

    def test_should_fix_locations_in_batches(self, *args, **kwargs):
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
        with patch(
            MODULE_PATH + ".fix_invalid_locations",
            wraps=memberaudit_fix_locations.fix_invalid_locations,
        ) as spy_fix_corrupted_character_section:
            call_command(
                "memberaudit_fix_locations",
                "--noinput",
                "--batch-size-update",
                "1",
                stdout=out,
            )

            # then
            self.assertEqual(spy_fix_corrupted_character_section.call_count, 3)
            for corrupted_asset in [
                corrupted_asset_1,
                corrupted_asset_2,
                corrupted_asset_3,
            ]:
                corrupted_asset.refresh_from_db()
                self.assertEqual(
                    corrupted_asset.location.id, Location.LOCATION_UNKNOWN_ID
                )

    def test_should_fetch_locations_in_batches(self, *args, **kwargs):
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
        create_character_asset(
            character=self.character_1001, location=invalid_location_1
        )
        create_character_asset(
            character=self.character_1001,
            location=valid_location,
            item_id=invalid_location_2.id,
        )
        create_character_asset(
            character=self.character_1001, location=invalid_location_2
        )
        create_character_asset(
            character=self.character_1001,
            location=valid_location,
            item_id=invalid_location_3.id,
        )
        create_character_asset(
            character=self.character_1001, location=invalid_location_3
        )

        out = StringIO()

        # when
        with patch(
            MODULE_PATH + "._find_invalid_locations_chunk",
            wraps=memberaudit_fix_locations._find_invalid_locations_chunk,
        ) as spy_find_invalid_locations:
            call_command(
                "memberaudit_fix_locations",
                "--noinput",
                "--batch-size-fetch",
                "1",
                stdout=out,
            )

            # then
            self.assertEqual(spy_find_invalid_locations.call_count, 6 * 2)
