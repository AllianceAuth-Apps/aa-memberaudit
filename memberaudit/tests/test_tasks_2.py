import datetime as dt
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils.timezone import now
from eveuniverse.models import EveSolarSystem

from app_utils.esi_testing import EsiClientStub, EsiEndpoint

from memberaudit import tasks
from memberaudit.helpers import UpdateSectionResult
from memberaudit.models import (
    Character,
    CharacterAsset,
    CharacterUpdateStatus,
    Location,
)
from memberaudit.tests.testdata.constants import EveTypeId
from memberaudit.tests.testdata.load_entities import load_entities
from memberaudit.tests.testdata.load_eveuniverse import load_eveuniverse
from memberaudit.tests.testdata.load_locations import load_locations
from memberaudit.tests.utils import (
    create_memberaudit_character,
    create_user_from_evecharacter_with_access,
    reset_celery_once_locks,
)

from .testdata.factories import (
    create_character_asset,
    create_character_from_user,
    create_character_location,
    create_character_ship,
    create_character_update_status,
    create_location_eve_solar_system,
)

MODELS_PATH = "memberaudit.models"
MANAGERS_PATH = "memberaudit.managers"
TASKS_PATH = "memberaudit.tasks"


@patch(MANAGERS_PATH + ".character_sections_1.esi")
class TestUpdateCharacterAssetsBuildListFromEsi(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        load_locations()
        cls.character_1001 = create_memberaudit_character(1001)
        cls.jita = EveSolarSystem.objects.get(name="Jita")
        cls.location_jita_44 = Location.objects.get(id=60003760)
        cls.amamake = EveSolarSystem.objects.get(name="Amamake")
        cls.location_structure_1 = Location.objects.get(id=1_000_000_000_001)
        cls.location_jita = create_location_eve_solar_system(id=cls.jita.id)
        cls.item_ids = {1_100_000_000_001}
        cls.endpoints = [
            EsiEndpoint(
                "Assets",
                "get_characters_character_id_assets",
                "character_id",
                needs_token=True,
                data={
                    "1001": [
                        {
                            "is_blueprint_copy": False,
                            "is_singleton": True,
                            "item_id": 1_100_000_000_001,
                            "location_flag": "Hangar",
                            "location_id": cls.location_jita_44.id,
                            "location_type": "station",
                            "quantity": 1,
                            "type_id": EveTypeId.VELDSPAR,
                        }
                    ]
                },
            ),
            EsiEndpoint(
                "Assets",
                "post_characters_character_id_assets_names",
                "character_id",
                needs_token=True,
                data={
                    "1001": [
                        {"item_id": 1_100_000_000_001, "name": "ESI asset"},
                    ]
                },
            ),
        ]
        cls.esi_client_stub = EsiClientStub.create_from_endpoints(cls.endpoints)

    def test_should_add_current_ship_when_it_not_in_assets(self, mock_esi):
        # given
        mock_esi.client = self.esi_client_stub
        create_character_ship(
            character=self.character_1001,
            item_id=1_100_000_000_999,
            eve_type_id=EveTypeId.MERLIN,
            name="Joy Ride",
        )
        create_character_location(
            character=self.character_1001, location=self.location_jita_44
        )

        # when
        result = tasks.assets_build_list_from_esi(self.character_1001.pk)

        # then
        asset_data = {asset["item_id"]: asset for asset in result}
        self.assertIn(1_100_000_000_999, asset_data.keys())

    def test_should_not_add_current_ship_when_not_generated(self, mock_esi):
        # given
        mock_esi.client = self.esi_client_stub

        # when
        result = tasks.assets_build_list_from_esi(self.character_1001.pk)

        # then
        item_ids = {asset["item_id"] for asset in result}
        self.assertSetEqual(item_ids, {1_100_000_000_001})

    def test_should_not_add_current_ship_when_already_in_assets(self, mock_esi):
        # given
        mock_esi.client = self.esi_client_stub
        create_character_ship(
            character=self.character_1001,
            item_id=1_100_000_000_001,
            eve_type_id=EveTypeId.MERLIN,
            name="Joy Ride",
        )
        create_character_location(
            character=self.character_1001, location=self.location_jita
        )

        # when
        result = tasks.assets_build_list_from_esi(self.character_1001.pk)

        # then
        asset_data = {asset["item_id"]: asset for asset in result}
        obj = asset_data[1_100_000_000_001]
        self.assertNotEqual(obj["name"], "Joy Ride")

    def test_should_return_none_when_asset_list_is_unchanged_wo_ship(self, mock_esi):
        # given
        mock_esi.client = self.esi_client_stub
        tasks.assets_build_list_from_esi(self.character_1001.pk)

        # when
        result = tasks.assets_build_list_from_esi(self.character_1001.pk)

        # then
        self.assertIsNone(result)

    def test_should_return_none_when_asset_list_is_unchanged_w_ship(self, mock_esi):
        # given
        mock_esi.client = self.esi_client_stub
        create_character_ship(
            character=self.character_1001,
            item_id=1_100_000_000_999,
            eve_type_id=EveTypeId.MERLIN,
            name="Joy Ride",
        )
        create_character_location(
            character=self.character_1001, location=self.location_jita
        )
        tasks.assets_build_list_from_esi(self.character_1001.pk)

        # when
        result = tasks.assets_build_list_from_esi(self.character_1001.pk)

        # then
        self.assertIsNone(result)


@override_settings(
    CELERY_ALWAYS_EAGER=True,
    CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
    APP_UTILS_OBJECT_CACHE_DISABLED=True,
)
@patch(MANAGERS_PATH + ".character_sections_1.esi")
class TestUpdateCharacterAssets2(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        reset_celery_once_locks()
        load_eveuniverse()
        load_entities()
        load_locations()
        cls.character_1001 = create_memberaudit_character(1001)
        cls.jita = EveSolarSystem.objects.get(id=30000142)
        cls.jita_44 = Location.objects.get(id=60003760)
        cls.amamake = EveSolarSystem.objects.get(id=30002537)
        cls.structure_1 = Location.objects.get(id=1_000_000_000_001)
        endpoints = [
            EsiEndpoint(
                "Assets",
                "get_characters_character_id_assets",
                "character_id",
                needs_token=True,
                data={
                    "1001": [
                        {
                            "is_blueprint_copy": False,
                            "is_singleton": True,
                            "item_id": 1_100_000_000_001,
                            "location_flag": "Hangar",
                            "location_id": cls.jita_44.id,
                            "location_type": "station",
                            "quantity": 1,
                            "type_id": EveTypeId.CHARON.value,
                        },
                        {
                            "is_blueprint_copy": False,
                            "is_singleton": False,
                            "item_id": 1_100_000_000_002,
                            "location_flag": "Hangar",
                            "location_id": cls.jita_44.id,
                            "location_type": "station",
                            "quantity": 1,
                            "type_id": EveTypeId.VELDSPAR.value,
                        },
                        {
                            "is_blueprint_copy": False,
                            "is_singleton": False,
                            "item_id": 1_100_000_000_003,
                            "location_flag": "Hangar",
                            "location_id": 1_100_000_000_001,  # Charon
                            "location_type": "item",
                            "quantity": 1,
                            "type_id": EveTypeId.CARGO_CONTAINER.value,
                        },
                        {
                            "is_blueprint_copy": False,
                            "is_singleton": False,
                            "item_id": 1_100_000_000_004,
                            "location_flag": "???",
                            "location_id": 1_100_000_000_003,  # Cargo container
                            "location_type": "item",
                            "quantity": 1,
                            "type_id": EveTypeId.VELDSPAR.value,
                        },
                        {
                            "is_blueprint_copy": False,
                            "is_singleton": True,
                            "item_id": 1_100_000_000_005,
                            "location_flag": "???",
                            "location_id": 1_100_000_000_003,  # Cargo container
                            "location_type": "item",
                            "quantity": 1,
                            "type_id": EveTypeId.MERLIN.value,
                        },
                        {
                            "is_blueprint_copy": False,
                            "is_singleton": False,
                            "item_id": 1_100_000_000_006,
                            "location_flag": "???",
                            "location_id": 1_100_000_000_005,  # Merlin
                            "location_type": "item",
                            "quantity": 1,
                            "type_id": EveTypeId.VELDSPAR.value,
                        },
                    ]
                },
            ),
            EsiEndpoint(
                "Assets",
                "post_characters_character_id_assets_names",
                "character_id",
                needs_token=True,
                data={
                    "1001": [
                        {"item_id": 1_100_000_000_001, "name": "Freighter"},
                        {"item_id": 1_100_000_000_005, "name": "Fighter"},
                    ]
                },
            ),
        ]
        cls.esi_client = EsiClientStub.create_from_endpoints(endpoints)

    def test_should_create_assets_from_scratch(self, mock_esi):
        # given
        mock_esi.client = self.esi_client

        # when
        tasks.update_character_assets.delay(self.character_1001.pk, True)

        # then
        self.assertSetEqual(
            self.character_1001.assets.item_ids(),
            {
                1_100_000_000_001,
                1_100_000_000_002,
                1_100_000_000_003,
                1_100_000_000_004,
                1_100_000_000_005,
                1_100_000_000_006,
            },
        )

        obj: CharacterAsset = self.character_1001.assets.get(item_id=1_100_000_000_001)
        self.assertFalse(obj.is_blueprint_copy)
        self.assertTrue(obj.is_singleton)
        self.assertEqual(obj.location_flag, "Hangar")
        self.assertEqual(obj.location.id, self.jita_44.id)
        self.assertEqual(obj.quantity, 1)
        self.assertEqual(obj.eve_type.id, EveTypeId.CHARON)
        self.assertEqual(obj.name, "Freighter")

    def test_should_remove_obsolete_assets(self, mock_esi):
        # given
        mock_esi.client = self.esi_client
        create_character_asset(
            character=self.character_1001, item_id=1100000000666, location=self.jita_44
        )

        # when
        tasks.update_character_assets.delay(self.character_1001.pk, True)

        self.assertSetEqual(
            self.character_1001.assets.item_ids(),
            {
                1_100_000_000_001,
                1_100_000_000_002,
                1_100_000_000_003,
                1_100_000_000_004,
                1_100_000_000_005,
                1_100_000_000_006,
            },
        )
        status = self.character_1001.update_status_for_section(
            Character.UpdateSection.ASSETS
        )
        self.assertTrue(status.is_success)

    def test_should_update_existing_assets(self, mock_esi):
        # given
        mock_esi.client = self.esi_client
        create_character_asset(
            character=self.character_1001,
            item_id=1_100_000_000_002,
            location=self.jita_44,
            eve_type_id=EveTypeId.LIQUID_OZONE,
            is_singleton=False,
            quantity=10,
        )

        # when
        tasks.update_character_assets.delay(self.character_1001.pk, True)

        # then
        obj: CharacterAsset = self.character_1001.assets.get(item_id=1_100_000_000_002)
        self.assertEqual(obj.quantity, 1)
        status = self.character_1001.update_status_for_section(
            Character.UpdateSection.ASSETS
        )
        self.assertTrue(status.is_success)

    def test_should_do_nothing_when_assets_have_not_changed(self, mock_esi):
        # given
        mock_esi.client = self.esi_client
        tasks.update_character_assets.delay(self.character_1001.pk, True)

        # when
        tasks.update_character_assets.delay(self.character_1001.pk, False)

        status = self.character_1001.update_status_for_section(
            Character.UpdateSection.ASSETS
        )
        self.assertTrue(status.is_success)
        self.assertGreater(status.run_finished_at, status.update_finished_at)

    @patch(TASKS_PATH + ".logger", wraps=tasks.logger)
    def test_log_warning_when_there_are_leftovers_1(self, mock_logger, mock_esi):
        # given
        asset_data = {
            1_100_000_000_001: {
                "is_blueprint_copy": False,
                "is_singleton": False,
                "item_id": 1_100_000_000_001,
                "location_flag": "Hangar",
                "location_id": self.jita_44.id,
                "location_type": "station",
                "quantity": 1,
                "type_id": EveTypeId.VELDSPAR.value,
            },
            1_100_000_000_002: {
                "is_blueprint_copy": False,
                "is_singleton": True,
                "item_id": 1_100_000_000_002,
                "location_flag": "Hangar",
                "location_id": self.jita_44.id,
                "location_type": "station",
                "quantity": 1,
                "type_id": EveTypeId.CHARON.value,
            },
            1_100_000_000_003: {
                "is_blueprint_copy": False,
                "is_singleton": False,
                "item_id": 1_100_000_000_003,
                "location_flag": "Hangar",
                "location_id": 1_100_000_000_009,  # Unknown location
                "location_type": "item",
                "quantity": 1,
                "type_id": EveTypeId.VELDSPAR.value,
            },
        }

        endpoints = [
            EsiEndpoint(
                "Assets",
                "get_characters_character_id_assets",
                "character_id",
                needs_token=True,
                data={"1001": list(asset_data.values())},
            ),
            EsiEndpoint(
                "Assets",
                "post_characters_character_id_assets_names",
                "character_id",
                needs_token=True,
                data={
                    "1001": [
                        {"item_id": 1_100_000_000_002, "name": "Freighter"},
                    ]
                },
            ),
        ]
        mock_esi.client = EsiClientStub.create_from_endpoints(endpoints)
        # when
        with patch(TASKS_PATH + ".Character.assets_preload_objects", spec=True) as mock:
            mock.return_value = UpdateSectionResult(None, False)
            tasks.update_character_assets.delay(self.character_1001.pk, True)

        # then
        self.assertSetEqual(
            self.character_1001.assets.item_ids(),
            {1_100_000_000_001, 1_100_000_000_002},
        )
        self.assertTrue(mock_logger.warning.called)
        status = self.character_1001.update_status_for_section(
            Character.UpdateSection.ASSETS
        )
        self.assertFalse(status.is_success)

    @patch(TASKS_PATH + ".MEMBERAUDIT_TASKS_MAX_ASSETS_PER_PASS", 1)
    @patch(TASKS_PATH + ".assets_create_children", wraps=tasks.assets_create_children)
    @patch(
        TASKS_PATH + "._assets_create_parents_chunk",
        wraps=tasks._assets_create_parents_chunk,
    )
    def test_should_create_parent_and_child_assets_in_chunks_when_too_many(
        self, mock_assets_create_parents_chunk, mock_assets_create_children, mock_esi
    ):
        # given
        mock_esi.client = self.esi_client

        # when
        tasks.update_character_assets.delay(self.character_1001.pk, True)

        # then
        self.assertSetEqual(
            self.character_1001.assets.item_ids(),
            {
                1_100_000_000_001,
                1_100_000_000_002,
                1_100_000_000_003,
                1_100_000_000_004,
                1_100_000_000_005,
                1_100_000_000_006,
            },
        )
        self.assertEqual(len(mock_assets_create_parents_chunk.mock_calls), 2)
        self.assertEqual(len(mock_assets_create_children.mock_calls), 4)

    def test_should_create_parent_assets_only(self, mock_esi):
        # given
        asset_data = {
            1_100_000_000_001: {
                "is_blueprint_copy": False,
                "is_singleton": False,
                "item_id": 1_100_000_000_001,
                "location_flag": "Hangar",
                "location_id": self.jita_44.id,
                "location_type": "station",
                "quantity": 1,
                "type_id": EveTypeId.VELDSPAR.value,
            }
        }

        endpoints = [
            EsiEndpoint(
                "Assets",
                "get_characters_character_id_assets",
                "character_id",
                needs_token=True,
                data={"1001": list(asset_data.values())},
            ),
            EsiEndpoint(
                "Assets",
                "post_characters_character_id_assets_names",
                "character_id",
                needs_token=True,
                data={"1001": []},
            ),
        ]
        mock_esi.client = EsiClientStub.create_from_endpoints(endpoints)
        # when
        with patch(TASKS_PATH + ".Character.assets_preload_objects", spec=True) as mock:
            mock.return_value = UpdateSectionResult(None, False)
            tasks.update_character_assets.delay(self.character_1001.pk, True)

        # then
        self.assertSetEqual(self.character_1001.assets.item_ids(), {1_100_000_000_001})
        status = self.character_1001.update_status_for_section(
            Character.UpdateSection.ASSETS
        )
        self.assertTrue(status.is_success)


@patch(TASKS_PATH + ".Character.update_implants")
class TestUpdateCharacterSection(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        cls.user, _ = create_user_from_evecharacter_with_access(1001)

    def test_should_log_success_and_updated_when_update_succeeded(
        self, mock_update_implants
    ):
        # given
        mock_update_implants.return_value = UpdateSectionResult(True, True)
        character = create_character_from_user(self.user)
        character.clear_cache()

        # when
        tasks.update_character_implants(character_pk=character.pk, force_update=False)

        # then
        self.assertTrue(mock_update_implants.called)
        status: CharacterUpdateStatus = character.update_status_set.get(
            section=Character.UpdateSection.IMPLANTS
        )
        self.assertTrue(status.is_success)
        self.assertFalse(status.error_message)
        self.assertTrue(status.run_finished_at)
        self.assertTrue(status.update_started_at)
        self.assertTrue(status.update_finished_at)

    def test_should_pass_though_exceptions_from_update_method(
        self, mock_update_implants
    ):
        # given
        mock_update_implants.side_effect = RuntimeError
        character = create_character_from_user(self.user)
        character.clear_cache()

        # when
        with self.assertRaises(RuntimeError):
            tasks.update_character_implants(
                character_pk=character.pk, force_update=False
            )

        # then
        self.assertTrue(mock_update_implants.called)
        status: CharacterUpdateStatus = character.update_status_set.get(
            section=Character.UpdateSection.IMPLANTS
        )
        self.assertFalse(status.is_success)
        self.assertTrue(status.error_message)
        self.assertTrue(status.run_finished_at)
        self.assertIsNone(status.update_started_at)
        self.assertIsNone(status.update_finished_at)

    def test_should_clear_previous_errors_when_update_succeeded(
        self, mock_update_implants
    ):
        # given
        mock_update_implants.return_value = UpdateSectionResult(True, True)
        character = create_character_from_user(self.user)
        character.clear_cache()
        run_finished_at = now() - dt.timedelta(hours=4)
        status = create_character_update_status(
            character=character,
            section=Character.UpdateSection.IMPLANTS,
            is_success=False,
            error_message="some error",
            run_finished_at=run_finished_at,
        )

        # when
        tasks.update_character_implants(character_pk=character.pk, force_update=False)

        # then
        self.assertTrue(mock_update_implants.called)
        status.refresh_from_db()
        self.assertTrue(status.is_success)
        self.assertFalse(status.error_message)
        self.assertGreater(status.run_finished_at, run_finished_at)
        self.assertTrue(status.update_started_at)
        self.assertTrue(status.update_finished_at)

    def test_should_log_success_and_leave_update_dates_unchanged_when_no_update_1(
        self, mock_update_implants
    ):
        # given
        mock_update_implants.return_value = UpdateSectionResult(False, False)
        character = create_character_from_user(self.user)
        character.clear_cache()

        # when
        tasks.update_character_implants(character_pk=character.pk, force_update=False)

        # then
        self.assertTrue(mock_update_implants.called)
        status: CharacterUpdateStatus = character.update_status_set.get(
            section=Character.UpdateSection.IMPLANTS
        )
        self.assertTrue(status.is_success)
        self.assertFalse(status.error_message)
        self.assertTrue(status.run_finished_at)
        self.assertIsNone(status.update_started_at)
        self.assertIsNone(status.update_finished_at)

    def test_should_log_success_and_leave_update_dates_unchanged_when_no_update_2(
        self, mock_update_implants
    ):
        # given
        mock_update_implants.return_value = UpdateSectionResult(False, False)
        character = create_character_from_user(self.user)
        character.clear_cache()
        update_started_at = now() - dt.timedelta(hours=4)
        update_finished_at = now() - dt.timedelta(hours=3)
        status = create_character_update_status(
            character=character,
            section=Character.UpdateSection.IMPLANTS,
            is_success=True,
            update_started_at=update_started_at,
            update_finished_at=update_finished_at,
        )

        # when
        tasks.update_character_implants(character_pk=character.pk, force_update=False)

        # then
        self.assertTrue(mock_update_implants.called)
        status.refresh_from_db()
        self.assertTrue(status.is_success)
        self.assertFalse(status.error_message)
        self.assertTrue(status.run_finished_at)
        self.assertEqual(status.update_started_at, update_started_at)
        self.assertEqual(status.update_finished_at, update_finished_at)
