from http import HTTPStatus
from unittest.mock import patch

import pook

from django.test import override_settings
from eveuniverse.tests.testdata.factories_2 import EveTypeFactory

from memberaudit import tasks
from memberaudit.helpers import UpdateSectionResult
from memberaudit.models import Character, CharacterAsset, CharacterUpdateStatus
from memberaudit.tests.testdata.factories_2 import (
    CharacterAssetFactory,
    CharacterFactory,
    CharacterLocationFactory,
    CharacterShipFactory,
    LocationSolarSystemFactory,
    LocationStationFactory,
    LocationStructureFactory,
    make_esi_url,
)
from memberaudit.tests.utils import TestCaseWithClearCache, extract

TASKS_PATH = "memberaudit.tasks"


class TestUpdateCharacterAssetsBuildListFromEsi(TestCaseWithClearCache):
    @pook.on
    def test_should_add_current_ship_when_it_not_in_assets(self):
        # given
        character = CharacterFactory()
        ship = CharacterShipFactory(character=character)
        CharacterLocationFactory(character=character)
        pook.get(
            make_esi_url(f"characters/{character.character_id}/assets"),
            reply=HTTPStatus.OK,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "is_blueprint_copy": False,
                    "is_singleton": False,
                    "item_id": 1_100_000_000_001,
                    "location_flag": "Hangar",
                    "location_id": LocationStationFactory().id,
                    "location_type": "station",
                    "quantity": 3,
                    "type_id": EveTypeFactory().id,
                },
            ],
        )
        pook.post(
            make_esi_url(f"characters/{character.character_id}/assets/names"),
            reply=HTTPStatus.OK,
            response_json=[],
        )

        # when
        result = tasks.assets_build_list_from_esi(character.pk)

        # then
        asset_data = {asset["item_id"]: asset for asset in result}
        self.assertIn(ship.item_id, asset_data.keys())

    @pook.on
    def test_should_not_add_current_ship_when_not_generated(self):
        # given
        character = CharacterFactory()
        pook.get(
            make_esi_url(f"characters/{character.character_id}/assets"),
            reply=HTTPStatus.OK,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "is_blueprint_copy": False,
                    "is_singleton": False,
                    "item_id": 1_100_000_000_001,
                    "location_flag": "Hangar",
                    "location_id": LocationStationFactory().id,
                    "location_type": "station",
                    "quantity": 3,
                    "type_id": EveTypeFactory().id,
                },
            ],
        )
        pook.post(
            make_esi_url(f"characters/{character.character_id}/assets/names"),
            reply=HTTPStatus.OK,
            response_json=[],
        )
        # when
        result = tasks.assets_build_list_from_esi(character.pk)

        # then
        item_ids = {asset["item_id"] for asset in result}
        self.assertSetEqual(item_ids, {1_100_000_000_001})

    @pook.on
    def test_should_not_add_current_ship_when_already_in_assets(self):
        # given
        character = CharacterFactory()
        ship = CharacterShipFactory(character=character)
        location = CharacterLocationFactory(character=character)
        pook.get(
            make_esi_url(f"characters/{character.character_id}/assets"),
            reply=HTTPStatus.OK,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "is_blueprint_copy": False,
                    "is_singleton": True,
                    "item_id": ship.item_id,
                    "location_flag": "Hangar",
                    "location_id": location.eve_solar_system.id,
                    "location_type": "solar_system",
                    "quantity": 1,
                    "type_id": ship.eve_type.id,
                },
            ],
        )
        pook.post(
            make_esi_url(f"characters/{character.character_id}/assets/names"),
            reply=HTTPStatus.OK,
            response_json=[
                {"item_id": ship.item_id, "name": "Joy Ride"},
            ],
        )

        # when
        result = tasks.assets_build_list_from_esi(character.pk)

        # then
        asset_data = {asset["item_id"]: asset for asset in result}
        obj = asset_data[ship.item_id]
        self.assertEqual(obj["name"], "Joy Ride")

    @pook.on
    def test_should_return_none_when_asset_list_is_unchanged(self):
        # given
        character = CharacterFactory()
        pook.get(
            make_esi_url(f"characters/{character.character_id}/assets"),
            reply=HTTPStatus.OK,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "is_blueprint_copy": False,
                    "is_singleton": False,
                    "item_id": 1_100_000_000_001,
                    "location_flag": "Hangar",
                    "location_id": LocationStationFactory().id,
                    "location_type": "station",
                    "quantity": 3,
                    "type_id": EveTypeFactory().id,
                },
            ],
            persist=True,
        )
        pook.post(
            make_esi_url(f"characters/{character.character_id}/assets/names"),
            reply=HTTPStatus.OK,
            response_json=[],
            persist=True,
        )
        tasks.assets_build_list_from_esi(character.pk)

        # when
        result = tasks.assets_build_list_from_esi(character.pk)

        # then
        self.assertIsNone(result)


@patch("celery.app.task.Context.called_directly", False)  # make retry work with eager
@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
class TestUpdateCharacterAssets(TestCaseWithClearCache):
    @pook.on
    def test_should_create_assets_from_scratch(self):
        # given
        character = CharacterFactory()
        station = LocationStationFactory()
        in_space = LocationSolarSystemFactory()
        structure = LocationStructureFactory()
        type_1 = EveTypeFactory()
        type_2 = EveTypeFactory()
        type_3 = EveTypeFactory()
        type_4 = EveTypeFactory()
        pook.get(
            make_esi_url(f"characters/{character.character_id}/assets"),
            reply=HTTPStatus.OK,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "is_blueprint_copy": True,
                    "is_singleton": True,
                    "item_id": 1100000000001,
                    "location_flag": "Hangar",
                    "location_id": station.id,
                    "location_type": "station",
                    "quantity": 1,
                    "type_id": type_4.id,
                },
                {
                    "is_blueprint_copy": False,
                    "is_singleton": True,
                    "item_id": 1100000000002,
                    "location_flag": "Hangar",
                    "location_id": 1100000000001,
                    "location_type": "item",
                    "quantity": 1,
                    "type_id": type_2.id,
                },
                {
                    "is_blueprint_copy": False,
                    "is_singleton": True,
                    "item_id": 1100000000003,
                    "location_flag": "Hangar",
                    "location_id": 1100000000001,
                    "location_type": "item",
                    "quantity": 1,
                    "type_id": type_1.id,
                },
                {
                    "is_blueprint_copy": False,
                    "is_singleton": True,
                    "item_id": 1100000000004,
                    "location_flag": "Hangar",
                    "location_id": 1100000000003,
                    "location_type": "item",
                    "quantity": 1,
                    "type_id": type_3.id,
                },
                {
                    "is_blueprint_copy": True,
                    "is_singleton": True,
                    "item_id": 1100000000005,
                    "location_flag": "Hangar",
                    "location_id": structure.id,
                    "location_type": "other",
                    "quantity": 1,
                    "type_id": type_4.id,
                },
                {
                    "is_blueprint_copy": False,
                    "is_singleton": True,
                    "item_id": 1100000000006,
                    "location_flag": "Hangar",
                    "location_id": 1100000000005,
                    "location_type": "item",
                    "quantity": 1,
                    "type_id": type_2.id,
                },
                {
                    "is_blueprint_copy": False,
                    "is_singleton": True,
                    "item_id": 1100000000007,
                    "location_flag": "Hangar",
                    "location_id": in_space.id,
                    "location_type": "solar_system",
                    "quantity": 1,
                    "type_id": type_2.id,
                },
                {
                    "is_blueprint_copy": False,
                    "is_singleton": True,
                    "item_id": 1100000000008,
                    "location_flag": "Hangar",
                    "location_id": structure.id,
                    "location_type": "item",
                    "quantity": 1,
                    "type_id": type_2.id,
                },
            ],
        )
        pook.post(
            make_esi_url(f"characters/{character.character_id}/assets/names"),
            reply=HTTPStatus.OK,
            response_json=[
                {"item_id": 1100000000001, "name": "Parent Item 1"},
                {"item_id": 1100000000002, "name": "Leaf Item 2"},
                {"item_id": 1100000000003, "name": "Leaf Item 3"},
                {"item_id": 1100000000004, "name": "Leaf Item 4"},
                {"item_id": 1100000000005, "name": "Parent Item 2"},
                {"item_id": 1100000000006, "name": "Leaf Item 6"},
                {"item_id": 1100000000007, "name": "None"},
                {"item_id": 1100000000008, "name": "None"},
            ],
        )

        # when
        tasks.update_character_assets.delay(
            character_pk=character.pk, force_update=False
        )

        # then
        self.assertSetEqual(
            extract(character.assets, "item_id"),
            {
                1_100_000_000_001,
                1_100_000_000_002,
                1_100_000_000_003,
                1_100_000_000_004,
                1_100_000_000_005,
                1_100_000_000_006,
                1_100_000_000_007,
                1_100_000_000_008,
            },
        )

        obj_1: CharacterAsset = character.assets.get(item_id=1_100_000_000_001)
        self.assertTrue(obj_1.is_blueprint_copy)
        self.assertTrue(obj_1.is_singleton)
        self.assertEqual(obj_1.location_flag, "Hangar")
        self.assertEqual(obj_1.location, station)
        self.assertEqual(obj_1.quantity, 1)
        self.assertEqual(obj_1.eve_type, type_4)
        self.assertEqual(obj_1.name, "Parent Item 1")

        obj_2: CharacterAsset = character.assets.get(item_id=1_100_000_000_002)
        self.assertFalse(obj_2.is_blueprint_copy)
        self.assertTrue(obj_2.is_singleton)
        self.assertEqual(obj_2.location_flag, "Hangar")
        self.assertEqual(obj_2.parent.item_id, 1_100_000_000_001)
        self.assertEqual(obj_2.quantity, 1)
        self.assertEqual(obj_2.eve_type, type_2)
        self.assertEqual(obj_2.name, "Leaf Item 2")

        obj_3: CharacterAsset = character.assets.get(item_id=1_100_000_000_003)
        self.assertEqual(obj_3.parent.item_id, 1_100_000_000_001)
        self.assertEqual(obj_3.eve_type, type_1)

        obj_4: CharacterAsset = character.assets.get(item_id=1_100_000_000_004)
        self.assertEqual(obj_4.parent.item_id, 1_100_000_000_003)
        self.assertEqual(obj_4.eve_type, type_3)

        obj_5: CharacterAsset = character.assets.get(item_id=1_100_000_000_005)
        self.assertEqual(obj_5.location, structure)
        self.assertEqual(obj_5.eve_type, type_4)

        obj_6: CharacterAsset = character.assets.get(item_id=1_100_000_000_006)
        self.assertEqual(obj_6.parent.item_id, 1_100_000_000_005)
        self.assertEqual(obj_6.eve_type, type_2)

        obj_7: CharacterAsset = character.assets.get(item_id=1_100_000_000_007)
        self.assertEqual(obj_7.location, in_space)
        self.assertEqual(obj_7.name, "")
        self.assertEqual(obj_7.eve_type, type_2)

        obj_8: CharacterAsset = character.assets.get(item_id=1_100_000_000_008)
        self.assertEqual(obj_8.location, structure)

    @pook.on
    def test_should_remove_stale_assets(self):
        # given
        character = CharacterFactory()
        station = LocationStationFactory()
        eve_type = EveTypeFactory()
        item_id = 1_100_000_000_001
        CharacterAssetFactory(character=character, location=station)  # to be removed
        pook.get(
            make_esi_url(f"characters/{character.character_id}/assets"),
            reply=HTTPStatus.OK,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "is_blueprint_copy": False,
                    "is_singleton": False,
                    "item_id": item_id,
                    "location_flag": "Hangar",
                    "location_id": station.id,
                    "location_type": "station",
                    "quantity": 3,
                    "type_id": eve_type.id,
                },
            ],
        )
        pook.post(
            make_esi_url(f"characters/{character.character_id}/assets/names"),
            reply=HTTPStatus.OK,
            response_json=[],
        )

        # when
        tasks.update_character_assets.delay(
            character_pk=character.pk, force_update=False
        )

        # then
        got = extract(character.assets, "item_id")
        want = {item_id}
        self.assertSetEqual(got, want)

    @pook.on
    def test_should_update_existing_assets(self):
        # given
        character = CharacterFactory()
        item_1 = CharacterAssetFactory(character=character)
        structure = LocationStructureFactory()
        eve_type = EveTypeFactory()
        location_flag = "MobileDepotHold"
        quantity = 1
        is_blueprint_copy = True
        is_singleton = True
        pook.get(
            make_esi_url(f"characters/{character.character_id}/assets"),
            reply=HTTPStatus.OK,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "is_blueprint_copy": is_blueprint_copy,
                    "is_singleton": is_singleton,
                    "item_id": item_1.item_id,
                    "location_flag": location_flag,
                    "location_id": structure.id,
                    "location_type": "item",
                    "quantity": quantity,
                    "type_id": eve_type.id,
                },
            ],
        )
        name = "Alpha"
        pook.post(
            make_esi_url(f"characters/{character.character_id}/assets/names"),
            reply=HTTPStatus.OK,
            response_json=[{"item_id": item_1.item_id, "name": name}],
        )

        # when
        tasks.update_character_assets.delay(
            character_pk=character.pk, force_update=False
        )

        # then
        item_2: CharacterAsset = character.assets.get(item_id=item_1.item_id)
        self.assertEqual(item_2.eve_type, eve_type)
        self.assertEqual(item_2.is_blueprint_copy, is_blueprint_copy)
        self.assertEqual(item_2.is_singleton, is_singleton)
        self.assertEqual(item_2.location_flag, location_flag)
        self.assertEqual(item_2.location, structure)
        self.assertEqual(item_2.name, name)
        self.assertEqual(item_2.quantity, quantity)

    @pook.on
    def test_should_keep_assets_which_are_moved_to_different_locations(self):
        # given
        character = CharacterFactory()
        station = LocationStationFactory()
        item_1 = CharacterAssetFactory(character=character, location=station)
        item_2 = CharacterAssetFactory(character=character, parent=item_1)
        pook.get(
            make_esi_url(f"characters/{character.character_id}/assets"),
            reply=HTTPStatus.OK,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "is_blueprint_copy": item_1.is_blueprint_copy,
                    "is_singleton": item_1.is_singleton,
                    "item_id": item_1.item_id,
                    "location_flag": "Hangar",
                    "location_id": station.id,
                    "location_type": "station",
                    "quantity": item_1.quantity,
                    "type_id": item_1.eve_type.id,
                },
                {
                    "is_blueprint_copy": item_2.is_blueprint_copy,
                    "is_singleton": item_2.is_singleton,
                    "item_id": item_2.item_id,
                    "location_flag": "Hangar",
                    "location_id": station.id,
                    "location_type": "station",
                    "quantity": item_2.quantity,
                    "type_id": item_2.eve_type.id,
                },
            ],
        )
        pook.post(
            make_esi_url(f"characters/{character.character_id}/assets/names"),
            reply=HTTPStatus.OK,
            response_json=[],
        )

        # when
        tasks.update_character_assets.delay(
            character_pk=character.pk, force_update=False
        )

        # then
        got = extract(character.assets, "item_id")
        want = {item_1.item_id, item_2.item_id}
        self.assertSetEqual(got, want)

    @pook.on
    def test_should_report_update_success_when_update_succeeded(self):
        # given
        character = CharacterFactory()
        station = LocationStationFactory()
        eve_type = EveTypeFactory()
        pook.get(
            make_esi_url(f"characters/{character.character_id}/assets"),
            reply=HTTPStatus.OK,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "is_blueprint_copy": False,
                    "is_singleton": False,
                    "item_id": 1100000000001,
                    "location_flag": "Hangar",
                    "location_id": station.id,
                    "location_type": "station",
                    "quantity": 3,
                    "type_id": eve_type.id,
                },
            ],
        )
        pook.post(
            make_esi_url(f"characters/{character.character_id}/assets/names"),
            reply=HTTPStatus.OK,
            response_json=[],
        )

        # when
        tasks.update_character_assets.delay(
            character_pk=character.pk, force_update=False
        )

        # then
        status: CharacterUpdateStatus = character.update_status_set.get(
            section=Character.UpdateSection.ASSETS
        )
        self.assertTrue(status.is_success)
        self.assertFalse(status.error_message)

    @pook.on
    def test_should_not_recreate_asset_tree_when_info_from_ESI_is_unchanged(self):
        # given
        character = CharacterFactory()
        station = LocationStationFactory()
        eve_type = EveTypeFactory()
        item_id = 1100000000001
        name = "Karoshi"
        pook.get(
            make_esi_url(f"characters/{character.character_id}/assets"),
            reply=HTTPStatus.OK,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "is_blueprint_copy": False,
                    "is_singleton": False,
                    "item_id": item_id,
                    "location_flag": "Hangar",
                    "location_id": station.id,
                    "location_type": "station",
                    "quantity": 3,
                    "type_id": eve_type.id,
                },
            ],
            persist=True,
        )
        pook.post(
            make_esi_url(f"characters/{character.character_id}/assets/names"),
            reply=HTTPStatus.OK,
            response_json=[{"item_id": item_id, "name": name}],
            persist=True,
        )
        character.reset_update_section(Character.UpdateSection.ASSETS)
        tasks.update_character_assets(character_pk=character.pk, force_update=False)
        item: CharacterAsset = character.assets.get(item_id=item_id)
        item.name = "New Name"
        item.save()

        # when
        tasks.update_character_assets.delay(character.pk, force_update=False)

        # then
        item.refresh_from_db()
        self.assertEqual(item.name, "New Name")

        status: CharacterUpdateStatus = character.update_status_set.get(
            section=Character.UpdateSection.ASSETS
        )
        self.assertTrue(status.is_success)

    @pook.on
    def test_should_recreate_asset_tree_when_info_from_ESI_is_unchanged_and_is_forced(
        self,
    ):
        # given
        character = CharacterFactory()
        station = LocationStationFactory()
        eve_type = EveTypeFactory()
        item_id = 1100000000001
        name = "Karoshi"
        pook.get(
            make_esi_url(f"characters/{character.character_id}/assets"),
            reply=HTTPStatus.OK,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "is_blueprint_copy": False,
                    "is_singleton": False,
                    "item_id": item_id,
                    "location_flag": "Hangar",
                    "location_id": station.id,
                    "location_type": "station",
                    "quantity": 3,
                    "type_id": eve_type.id,
                },
            ],
            persist=True,
        )
        pook.post(
            make_esi_url(f"characters/{character.character_id}/assets/names"),
            reply=HTTPStatus.OK,
            response_json=[{"item_id": item_id, "name": name}],
            persist=True,
        )
        character.reset_update_section(Character.UpdateSection.ASSETS)
        tasks.update_character_assets(character_pk=character.pk, force_update=False)
        item_1: CharacterAsset = character.assets.get(item_id=item_id)
        item_1.name = "New Name"
        item_1.save()

        # when
        tasks.update_character_assets.delay(
            character_pk=character.pk, force_update=True
        )

        # then
        item_2: CharacterAsset = character.assets.get(item_id=item_id)
        self.assertEqual(item_2.name, name)

        status: CharacterUpdateStatus = character.update_status_set.get(
            section=Character.UpdateSection.ASSETS
        )
        self.assertTrue(status.is_success)


@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
class TestUpdateCharacterAssets2(TestCaseWithClearCache):
    @pook.on
    def test_log_warning_when_there_are_leftovers(self):
        # given
        character = CharacterFactory()
        station = LocationStationFactory()
        type_1 = EveTypeFactory()
        type_2 = EveTypeFactory()
        pook.get(
            make_esi_url(f"characters/{character.character_id}/assets"),
            reply=HTTPStatus.OK,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "is_blueprint_copy": False,
                    "is_singleton": False,
                    "item_id": 1_100_000_000_001,
                    "location_flag": "Hangar",
                    "location_id": station.id,
                    "location_type": "station",
                    "quantity": 1,
                    "type_id": type_1.id,
                },
                {
                    "is_blueprint_copy": False,
                    "is_singleton": True,
                    "item_id": 1_100_000_000_002,
                    "location_flag": "Hangar",
                    "location_id": station.id,
                    "location_type": "station",
                    "quantity": 1,
                    "type_id": type_2.id,
                },
                {
                    "is_blueprint_copy": False,
                    "is_singleton": False,
                    "item_id": 1_100_000_000_003,
                    "location_flag": "Hangar",
                    "location_id": 1_100_000_000_009,  # Unknown location
                    "location_type": "item",
                    "quantity": 1,
                    "type_id": type_1.id,
                },
            ],
        )
        pook.post(
            make_esi_url(f"characters/{character.character_id}/assets/names"),
            reply=HTTPStatus.OK,
            response_json=[],
        )

        with patch(TASKS_PATH + ".logger", wraps=tasks.logger) as mock_logger:
            # when
            with patch(
                TASKS_PATH + ".Character.assets_preload_objects", spec=True
            ) as mock:
                mock.return_value = UpdateSectionResult(None, False)
                tasks.update_character_assets.delay(character.pk, True)

            # then
            self.assertSetEqual(
                extract(character.assets, "item_id"),
                {1_100_000_000_001, 1_100_000_000_002},
            )
            self.assertTrue(mock_logger.warning.called)
            status = character.update_status_for_section(Character.UpdateSection.ASSETS)
            self.assertFalse(status.is_success)

    @pook.on
    def test_should_create_parent_and_child_assets_in_chunks_when_too_many(self):
        # given
        character = CharacterFactory()
        station = LocationStationFactory()
        eve_type = EveTypeFactory()
        item_1_id = 1_100_000_000_001
        item_2_id = 1_100_000_000_002
        item_1a_id = 1_100_000_000_003
        item_1b_id = 1_100_000_000_004
        pook.get(
            make_esi_url(f"characters/{character.character_id}/assets"),
            reply=HTTPStatus.OK,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "is_blueprint_copy": False,
                    "is_singleton": True,
                    "item_id": item_1_id,
                    "location_flag": "Hangar",
                    "location_id": station.id,
                    "location_type": "station",
                    "quantity": 1,
                    "type_id": eve_type.id,
                },
                {
                    "is_blueprint_copy": False,
                    "is_singleton": False,
                    "item_id": item_2_id,
                    "location_flag": "Hangar",
                    "location_id": station.id,
                    "location_type": "station",
                    "quantity": 7,
                    "type_id": eve_type.id,
                },
                {
                    "is_blueprint_copy": False,
                    "is_singleton": False,
                    "item_id": item_1a_id,
                    "location_flag": "Hangar",
                    "location_id": item_1_id,
                    "location_type": "item",
                    "quantity": 3,
                    "type_id": eve_type.id,
                },
                {
                    "is_blueprint_copy": False,
                    "is_singleton": False,
                    "item_id": item_1b_id,
                    "location_flag": "Hangar",
                    "location_id": item_1_id,
                    "location_type": "item",
                    "quantity": 5,
                    "type_id": eve_type.id,
                },
            ],
        )
        pook.post(
            make_esi_url(f"characters/{character.character_id}/assets/names"),
            reply=HTTPStatus.OK,
            response_json=[],
        )

        with (
            patch(TASKS_PATH + ".MEMBERAUDIT_TASKS_MAX_ASSETS_PER_PASS", 1),
            patch(
                TASKS_PATH + ".assets_create_children",
                wraps=tasks.assets_create_children,
            ) as mock_assets_create_parents_chunk,
            patch(
                TASKS_PATH + "._assets_create_parents_chunk",
                wraps=tasks._assets_create_parents_chunk,
            ) as mock_assets_create_children,
        ):
            # when
            tasks.update_character_assets.delay(character.pk, True)

            # then
            got = extract(character.assets, "item_id")
            want = {item_1_id, item_2_id, item_1a_id, item_1b_id}
            self.assertSetEqual(got, want)
            self.assertEqual(len(mock_assets_create_parents_chunk.mock_calls), 2)
            self.assertEqual(len(mock_assets_create_children.mock_calls), 2)
