import datetime as dt
from unittest.mock import patch

from eveuniverse.models import EvePlanet

from app_utils.esi_testing import EsiClientStub, EsiEndpoint
from app_utils.testing import NoSocketsTestCase

from memberaudit.models import CharacterPlanet

from ..testdata.factories import create_character_planet
from ..testdata.load_entities import load_entities
from ..testdata.load_eveuniverse import load_eveuniverse
from ..utils import create_memberaudit_character

MODELS_PATH = "memberaudit.models.character"
# MANAGERS_PATH = "memberaudit.managers"
# TASKS_PATH = "memberaudit.tasks"


@patch(MODELS_PATH + ".Character._preload_all_locations", spec=True)
@patch(MODELS_PATH + ".EveType.objects.bulk_get_or_create_esi", spec=True)
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
        self.assertEqual(kwargs["incoming_ids"], {420, 421})


@patch(MODELS_PATH + ".MEMBERAUDIT_DATA_RETENTION_LIMIT", None)
@patch(MODELS_PATH + ".esi")
class TestCharacterPlanet(NoSocketsTestCase):
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
