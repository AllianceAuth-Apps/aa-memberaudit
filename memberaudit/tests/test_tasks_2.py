"""New style asset tests.

These tests do not use the esi testdata fixtures.
"""

from unittest.mock import patch

from django.test import TestCase, override_settings
from eveuniverse.models import EveSolarSystem

from app_utils.esi_testing import EsiClientStub, EsiEndpoint

from memberaudit import tasks
from memberaudit.models import Location
from memberaudit.tests.testdata.constants import EveTypeId
from memberaudit.tests.testdata.load_entities import load_entities
from memberaudit.tests.testdata.load_eveuniverse import load_eveuniverse
from memberaudit.tests.testdata.load_locations import load_locations
from memberaudit.tests.utils import (
    create_memberaudit_character,
    reset_celery_once_locks,
)

from .testdata.factories import (
    create_character_location,
    create_character_ship,
    create_location_eve_solar_system,
)

MODELS_PATH = "memberaudit.models"
MANAGERS_PATH = "memberaudit.managers"
TASKS_PATH = "memberaudit.tasks"


@patch(MANAGERS_PATH + ".character_sections_1.esi")
class TestUpdateCharacterAssetsBuildListFromEsi(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
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
        self.assertIn(1_100_000_000_999, result.keys())

    def test_should_not_add_current_ship_when_not_generated(self, mock_esi):
        # given
        mock_esi.client = self.esi_client_stub

        # when
        result = tasks.assets_build_list_from_esi(self.character_1001.pk)

        # then
        item_ids = set(result.keys())
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
        obj = result[1_100_000_000_001]
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
    def setUpTestData(cls) -> None:
        load_eveuniverse()
        load_entities()
        load_locations()
        cls.character_1001 = create_memberaudit_character(1001)
        cls.jita = EveSolarSystem.objects.get(id=30000142)
        cls.jita_44 = Location.objects.get(id=60003760)
        cls.amamake = EveSolarSystem.objects.get(id=30002537)
        cls.structure_1 = Location.objects.get(id=1_000_000_000_001)
        reset_celery_once_locks()

    def test_should_create_assets_from_scratch(self, mock_esi):
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
                            "item_id": 1100000000001,
                            "location_flag": "Hangar",
                            "location_id": 60003760,
                            "location_type": "station",
                            "quantity": 1,
                            "type_id": EveTypeId.CHARON.value,
                        },
                        {
                            "is_blueprint_copy": False,
                            "is_singleton": False,
                            "item_id": 1100000000002,
                            "location_flag": "Hangar",
                            "location_id": 60003760,
                            "location_type": "station",
                            "quantity": 1,
                            "type_id": EveTypeId.VELDSPAR.value,
                        },
                        {
                            "is_blueprint_copy": False,
                            "is_singleton": False,
                            "item_id": 1100000000003,
                            "location_flag": "Hangar",
                            "location_id": 1100000000001,  # Charon
                            "location_type": "item",
                            "quantity": 1,
                            "type_id": EveTypeId.CARGO_CONTAINER.value,
                        },
                        {
                            "is_blueprint_copy": False,
                            "is_singleton": False,
                            "item_id": 1100000000004,
                            "location_flag": "???",
                            "location_id": 1100000000003,  # Cargo container
                            "location_type": "item",
                            "quantity": 1,
                            "type_id": EveTypeId.VELDSPAR.value,
                        },
                        {
                            "is_blueprint_copy": False,
                            "is_singleton": False,
                            "item_id": 1100000000005,
                            "location_flag": "???",
                            "location_id": 1000000000003,  # Cargo container
                            "location_type": "item",
                            "quantity": 1,
                            "type_id": EveTypeId.LIQUID_OZONE.value,
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
                        {"item_id": 1100000000001, "name": "Freighter"},
                    ]
                },
            ),
        ]
        mock_esi.client = EsiClientStub.create_from_endpoints(endpoints)
        # when
        tasks.update_character_assets(self.character_1001.pk, True)

        # then
        self.assertSetEqual(
            self.character_1001.assets.item_ids(),
            {
                1_100_000_000_001,
                1_100_000_000_002,
                1_100_000_000_003,
                1_100_000_000_004,
                1_100_000_000_005,
            },
        )

    # @patch(TASKS_PATH + ".logger", wraps=tasks.logger)
    # def test_log_warning_when_there_are_leftovers(self, mock_logger, mock_esi):
    #     pass
    #   self.assertTrue(mock_logger.called)
