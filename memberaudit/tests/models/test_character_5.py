from unittest.mock import patch

from app_utils.testing import NoSocketsTestCase

# from ..testdata.factories import create_character
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
