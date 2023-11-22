import tempfile
from io import StringIO
from pathlib import Path
from unittest import skip
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from allianceauth.eveonline.models import EveCharacter
from app_utils.testing import NoSocketsTestCase

from memberaudit.models import Character, Location
from memberaudit.tests.testdata.factories import (
    create_character,
    create_character_asset,
    create_character_contract,
    create_character_contract_courier,
    create_character_contract_item,
    create_character_jump_clone,
    create_character_location,
    create_character_update_status,
    create_character_wallet_transaction,
    create_location,
)
from memberaudit.tests.testdata.load_entities import load_entities
from memberaudit.tests.testdata.load_eveuniverse import load_eveuniverse
from memberaudit.tests.utils import (
    add_auth_character_to_user,
    create_memberaudit_character,
    create_user_from_evecharacter_with_access,
)

DATA_EXPORTERS_PATH = "memberaudit.core.data_exporters"
PACKAGE_PATH = "memberaudit.management.commands"


@skip("Maria DB breaks")
class TestResetCharacters(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities()

    def test_normal(self):
        """can recreate member audit characters from main and alt of matching tokens"""
        user, co_1001 = create_user_from_evecharacter_with_access(1001)
        co_1002 = add_auth_character_to_user(user, 1002)

        out = StringIO()
        call_command("memberaudit_reset_characters", "--noinput", stdout=out)

        self.assertSetEqual(
            set(
                Character.objects.values_list(
                    "eve_character__character_ownership__id", flat=True
                )
            ),
            {co_1001.id, co_1002.id},
        )

    def test_orphaned_tokens(self):
        """
        given a matching token exists and the respective auth character
        is now owner by another user
        and no longer has a matching token
        when creating member audit characters
        then no member audit character is created for the switched auth character
        """
        user_1, co_1001 = create_user_from_evecharacter_with_access(1001)
        add_auth_character_to_user(user_1, 1002)
        user_2, co_1101 = create_user_from_evecharacter_with_access(1101)

        # re-add auth character 1002 to another user, but without member audit scopes
        add_auth_character_to_user(user_2, 1002, scopes="publicData")

        out = StringIO()
        call_command("memberaudit_reset_characters", "--noinput", stdout=out)

        self.assertSetEqual(
            set(
                Character.objects.values_list(
                    "eve_character__character_ownership__id", flat=True
                )
            ),
            {co_1001.id, co_1101.id},
        )


class TestDataExport(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities()
        load_eveuniverse()
        cls.character_1001 = create_memberaudit_character(1001)

    def test_should_export_contract_item(self):
        with tempfile.TemporaryDirectory() as tmpdirname:
            # given
            contract = create_character_contract(character=self.character_1001)
            create_character_contract_item(contract=contract, record_id=12)
            out = StringIO()
            # when
            call_command(
                "memberaudit_data_export",
                "contract-item",
                "--destination",
                tmpdirname,
                stdout=out,
            )
            # then
            output_file = Path(tmpdirname) / Path(
                "memberaudit_contract-item"
            ).with_suffix(".csv")
            self.assertTrue(output_file.exists())


@patch(
    PACKAGE_PATH + ".memberaudit_fix_locations.tasks.update_character_assets", spec=True
)
class TestFixInvalidLocations(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        cls.character_1001 = create_memberaudit_character(1001)

    def test_should_do_nothing_when_no_invalid_locations(self, mock):
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

        # when
        out = StringIO()
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
        self, mock_task_update_character_assets
    ):
        # given
        valid_location = create_location()
        invalid_location = create_location()

        normal_asset_1001 = create_character_asset(
            item_id=invalid_location.id,
            character=self.character_1001,
            location=valid_location,
        )
        corrupted_asset_1001 = create_character_asset(
            character=self.character_1001, location=invalid_location
        )
        status_1001 = create_character_update_status(
            character=self.character_1001, section=Character.UpdateSection.ASSETS
        )
        status_1001.update_content_hash(["some data"])

        character_1002 = create_memberaudit_character(1002)
        character_1002.is_disabled = True
        character_1002.save()
        corrupted_asset_1002 = create_character_asset(
            character=character_1002, location=invalid_location
        )
        status_1002 = create_character_update_status(
            character=character_1002, section=Character.UpdateSection.ASSETS
        )
        status_1002.update_content_hash(["some data"])

        character_1101 = create_character(
            EveCharacter.objects.get(character_id=1101)
        )  # orphan
        corrupted_asset_1101 = create_character_asset(
            character=character_1101, location=invalid_location
        )
        status_1101 = create_character_update_status(
            character=character_1101, section=Character.UpdateSection.ASSETS
        )
        status_1101.update_content_hash(["some data"])

        # when
        out = StringIO()
        call_command("memberaudit_fix_locations", "--noinput", stdout=out)

        # then
        location_ids = set(Location.objects.values_list("id", flat=True))
        self.assertSetEqual(
            location_ids, {valid_location.id, Location.LOCATION_UNKNOWN_ID}
        )
        normal_asset_1001.refresh_from_db()
        self.assertEqual(normal_asset_1001.location, valid_location)
        corrupted_asset_1001.refresh_from_db()
        self.assertEqual(corrupted_asset_1001.location.id, Location.LOCATION_UNKNOWN_ID)
        status_1001.refresh_from_db()
        self.assertFalse(status_1001.content_hash_1)

        corrupted_asset_1002.refresh_from_db()
        self.assertEqual(corrupted_asset_1002.location.id, Location.LOCATION_UNKNOWN_ID)
        status_1002.refresh_from_db()
        self.assertFalse(status_1002.content_hash_1)

        corrupted_asset_1101.refresh_from_db()
        self.assertEqual(corrupted_asset_1101.location.id, Location.LOCATION_UNKNOWN_ID)
        status_1101.refresh_from_db()
        self.assertFalse(status_1101.content_hash_1)

        calls = [
            o[1]["kwargs"]
            for o in mock_task_update_character_assets.apply_async.call_args_list
        ]
        self.assertEqual(len(calls), 1)  # only start tasks for 1001 character
        params = calls[0]
        self.assertEqual(params["character_pk"], self.character_1001.pk)
        self.assertTrue(params["force_update"])
