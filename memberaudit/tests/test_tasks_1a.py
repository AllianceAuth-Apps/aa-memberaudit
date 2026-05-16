import datetime as dt
from contextlib import ExitStack
from http import HTTPStatus
from unittest.mock import patch

import pook

from django.test import TestCase, override_settings  # , tag
from django.utils.timezone import now
from eveuniverse.tests.testdata.factories_2 import (
    EveEntityCharacterFactory,
    EveEntityCorporationFactory,
    EveTypeFactory,
)

from app_utils.testing import NoSocketsTestCase

from memberaudit import tasks
from memberaudit.models import (
    Character,
    CharacterAsset,
    CharacterContact,
    CharacterContactLabel,
    CharacterContract,
    CharacterContractItem,
    CharacterUpdateStatus,
)
from memberaudit.tests.testdata.factories_2 import (
    CharacterAssetFactory,
    CharacterContractItemExchangeFactory,
    CharacterFactory,
    CharacterOrphanFactory,
    CharacterUpdateStatusFactory,
    ComplianceGroupFactory,
    LocationSolarSystemFactory,
    LocationStationFactory,
    LocationStructureFactory,
    make_esi_url,
)
from memberaudit.tests.utils import TestCaseWithClearCache, extract

MODELS_PATH = "memberaudit.models"
TASKS_PATH = "memberaudit.tasks"


TASK_NAMES: frozenset[str] = frozenset(
    [
        "update_character_assets",
        "update_character_attributes",
        "update_character_character_details",
        "update_character_contacts",
        "update_character_contracts",
        "update_character_corporation_history",
        "update_character_fw_stats",
        "update_character_implants",
        "update_character_jump_clones",
        "update_character_location",
        "update_character_loyalty",
        "update_character_mails",
        "update_character_mining_ledger",
        "update_character_online_status",
        "update_character_planets",
        "update_character_roles",
        "update_character_ship",
        "update_character_skill_queue",
        "update_character_skill_sets",
        "update_character_skills",
        "update_character_standings",
        "update_character_titles",
        "update_character_wallet_balance",
        "update_character_wallet_journal",
        "update_character_wallet_transactions",
    ]
)


# @tag("breaks_with_tox")  # FIXME: Find solution


@patch(TASKS_PATH + ".update_compliance_groups_for_all", spec=True)
@patch(TASKS_PATH + ".update_all_characters", spec=True)
@patch(TASKS_PATH + ".update_market_prices", spec=True)
class TestRegularUpdates(TestCase):
    def test_should_run_update_for_all_except_compliance_groups(
        self,
        mock_update_market_prices,
        mock_update_all_characters,
        mock_update_compliance_groups_for_all,
    ):
        # when
        tasks.run_regular_updates()

        # then
        self.assertTrue(mock_update_market_prices.apply_async.called)
        self.assertTrue(mock_update_all_characters.apply_async.called)
        self.assertFalse(mock_update_compliance_groups_for_all.apply_async.called)

    def test_should_run_update_for_all_incl_compliance_groups(
        self,
        mock_update_market_prices,
        mock_update_all_characters,
        mock_update_compliance_groups_for_all,
    ):
        # given
        ComplianceGroupFactory()

        # when
        tasks.run_regular_updates()

        # then
        self.assertTrue(mock_update_market_prices.apply_async.called)
        self.assertTrue(mock_update_all_characters.apply_async.called)
        self.assertTrue(mock_update_compliance_groups_for_all.apply_async.called)


@patch(TASKS_PATH + ".esi_status.unavailable_sections", lambda: set())
@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
class TestUpdateCharacter(NoSocketsTestCase):
    def test_should_update_all_sections(self):
        # given
        character = CharacterFactory()
        with patch(MODELS_PATH + ".characters.MEMBERAUDIT_FEATURE_ROLES_ENABLED", True):
            with ExitStack() as stack:
                mocks = [
                    stack.enter_context(patch(TASKS_PATH + f".{name}", name=name))
                    for name in TASK_NAMES
                ]

                # when
                result = tasks.update_character(character.pk)

                # then
                self.assertTrue(result)
                for m in mocks:
                    with self.subTest(name=m._mock_name):
                        self.assertTrue(m.apply_async.called)

    def test_should_update_enabled_sections_only(self):
        # given
        character = CharacterFactory()
        with patch(
            MODELS_PATH + ".characters.MEMBERAUDIT_FEATURE_ROLES_ENABLED", False
        ):
            with ExitStack() as stack:
                mocks = [
                    stack.enter_context(patch(TASKS_PATH + f".{name}", name=name))
                    for name in TASK_NAMES - {"update_character_roles"}
                ]

                # when
                result = tasks.update_character(character.pk)

                # then
                self.assertTrue(result)
                for m in mocks:
                    with self.subTest(name=m._mock_name):
                        self.assertTrue(m.apply_async.called)

    def test_should_not_update_when_sections_are_current(self):
        # given
        character = CharacterFactory()
        for section in Character.UpdateSection.enabled_sections():
            CharacterUpdateStatusFactory(
                character=character, section=section, is_success=True
            )

        # when
        got = tasks.update_character(character.pk)

        # then
        self.assertFalse(got)

    def test_should_update_section_when_stale(self):
        # given
        character = CharacterFactory()
        sections = Character.UpdateSection.enabled_sections()
        sections.remove(Character.UpdateSection.LOYALTY)
        for section in sections:
            CharacterUpdateStatusFactory(
                character=character, section=section, is_success=True
            )

        CharacterUpdateStatusFactory(
            character=character,
            section=Character.UpdateSection.LOYALTY,
            is_success=True,
            run_finished_at=now() - dt.timedelta(hours=24),
        )

        with patch(TASKS_PATH + ".update_character_loyalty", spec=True) as m:
            # when
            got = tasks.update_character(character.pk)

            # then
            self.assertTrue(got)
            self.assertTrue(m.apply_async.called)

    def test_should_update_section_when_previous_update_failed(self):
        # given
        character = CharacterFactory()
        sections = Character.UpdateSection.enabled_sections()
        sections.remove(Character.UpdateSection.LOYALTY)
        for section in sections:
            CharacterUpdateStatusFactory(
                character=character, section=section, is_success=True
            )

        CharacterUpdateStatusFactory(
            character=character,
            section=Character.UpdateSection.LOYALTY,
            is_success=False,
        )

        with patch(TASKS_PATH + ".update_character_loyalty", spec=True) as m:
            # when
            got = tasks.update_character(character.pk)

            # then
            self.assertTrue(got)
            self.assertTrue(m.apply_async.called)

    def test_should_update_current_sections_when_requested(self):
        # given
        character = CharacterFactory()
        for section in Character.UpdateSection.enabled_sections():
            CharacterUpdateStatusFactory(
                character=character, section=section, is_success=True
            )

        with patch(MODELS_PATH + ".characters.MEMBERAUDIT_FEATURE_ROLES_ENABLED", True):
            with ExitStack() as stack:
                mocks = [
                    stack.enter_context(patch(TASKS_PATH + f".{name}", name=name))
                    for name in TASK_NAMES
                ]

                # when
                result = tasks.update_character(character.pk, ignore_stale=True)

                # then
                self.assertTrue(result)
                for m in mocks:
                    with self.subTest(name=m._mock_name):
                        self.assertTrue(m.apply_async.called)

    def test_should_skip_update_for_orphans(self):
        # given
        character = CharacterOrphanFactory()

        # when
        result = tasks.update_character(character.pk)

        # then
        self.assertFalse(result)


@patch(MODELS_PATH + ".characters.MEMBERAUDIT_FEATURE_ROLES_ENABLED", True)
@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
class TestUpdateCharacter_EsiIssues(NoSocketsTestCase):
    def test_should_not_update_sections_where_esi_endpoint_is_down(self):
        # given
        character = CharacterFactory()
        broken_section = Character.UpdateSection.LOYALTY
        with patch(
            TASKS_PATH + ".esi_status.unavailable_sections", lambda: {broken_section}
        ):
            with ExitStack() as stack:
                mocks = [
                    stack.enter_context(patch(TASKS_PATH + f".{name}", name=name))
                    for name in TASK_NAMES
                ]

                # when
                result = tasks.update_character(character.pk, ignore_stale=True)

                # then
                self.assertTrue(result)
                for m in mocks:
                    with self.subTest(name=m._mock_name):
                        if m._mock_name == "update_character_loyalty":
                            self.assertFalse(m.apply_async.called)
                        else:
                            self.assertTrue(m.apply_async.called)

    def test_should_not_update_when_no_esi_status_available(self):
        # given
        character = CharacterFactory()

        with patch(TASKS_PATH + ".esi_status.unavailable_sections", lambda: None):
            # when
            got = tasks.update_character(character.pk)

            # then
            self.assertFalse(got)


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
        tasks.update_character_assets(character_pk=character.pk, force_update=False)

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
        CharacterAssetFactory(character=character, location=station)  # to be removed
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
        tasks.update_character_assets(character_pk=character.pk, force_update=False)

        # then
        got = extract(character.assets, "item_id")
        want = {1_100_000_000_001}
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
        tasks.update_character_assets(character_pk=character.pk, force_update=False)

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
        tasks.update_character_assets(character_pk=character.pk, force_update=False)

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
        tasks.update_character_assets(character_pk=character.pk, force_update=False)

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
        tasks.update_character_assets(character.pk, force_update=False)

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
        tasks.update_character_assets(character_pk=character.pk, force_update=True)

        # then
        item_2: CharacterAsset = character.assets.get(item_id=item_id)
        self.assertEqual(item_2.name, name)

        status: CharacterUpdateStatus = character.update_status_set.get(
            section=Character.UpdateSection.ASSETS
        )
        self.assertTrue(status.is_success)


@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
class TestUpdateCharacterContacts(TestCase):
    @pook.on
    def test_should_report_success_when_update_ok(self):
        # given
        character = CharacterFactory()
        label_id = 7
        pook.get(
            make_esi_url(f"characters/{character.character_id}/contacts/labels"),
            reply=200,
            response_headers={"X-Pages": "1"},
            response_json=[{"label_id": label_id, "label_name": "alpha"}],
        )
        eve_entity = EveEntityCharacterFactory()
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
                    "standing": 5.0,
                }
            ],
        )

        # when
        tasks.update_character_contacts(character.pk, True)

        # then
        status: CharacterUpdateStatus = character.update_status_set.get(
            section=Character.UpdateSection.CONTACTS
        )
        self.assertTrue(status.is_success)

        contact: CharacterContact = character.contacts.first()
        self.assertEqual(contact.eve_entity, eve_entity)

        label: CharacterContactLabel = character.contact_labels.first()
        self.assertEqual(label.label_id, label_id)


@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
class TestUpdateCharacterContracts(TestCaseWithClearCache):
    @pook.on
    def test_should_record_success_when_update_completed_successfully(self):
        # given
        character = CharacterFactory()
        pook.get(
            make_esi_url(f"characters/{character.character_id}/contracts"),
            reply=200,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "assignee_id": 0,
                    "acceptor_id": 0,
                    "availability": "public",
                    "contract_id": 42,
                    "date_expired": now().isoformat(),
                    "date_issued": now().isoformat(),
                    "end_location_id": LocationStationFactory().id,
                    "for_corporation": False,
                    "issuer_corporation_id": EveEntityCorporationFactory().id,
                    "issuer_id": EveEntityCharacterFactory().id,
                    "reward": 123.45,
                    "start_location_id": LocationStationFactory().id,
                    "status": "outstanding",
                    "type": "courier",
                },
            ],
        )

        # when
        tasks.update_character_contracts(character_pk=character.pk, force_update=False)

        # then
        status: CharacterUpdateStatus = character.update_status_set.get(
            section=Character.UpdateSection.CONTRACTS
        )
        self.assertTrue(status.is_success)
        self.assertFalse(status.error_message)
        self.assertTrue(status.run_finished_at)
        self.assertTrue(status.update_finished_at)

    @pook.on
    def test_should_store_new_item_exchange_contract_with_items(self):
        # given
        character = CharacterFactory()
        contract_id = 42
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
                    "date_expired": now().isoformat(),
                    "date_issued": now().isoformat(),
                    "for_corporation": False,
                    "issuer_corporation_id": EveEntityCorporationFactory().id,
                    "issuer_id": EveEntityCharacterFactory().id,
                    "status": "outstanding",
                    "type": "item_exchange",
                }
            ],
        )
        record_id = 1
        quantity = 3
        eve_type = EveTypeFactory()
        pook.get(
            make_esi_url(
                f"characters/{character.character_id}/contracts/{contract_id}/items"
            ),
            reply=200,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "is_included": True,
                    "is_singleton": False,
                    "quantity": quantity,
                    "record_id": record_id,
                    "type_id": eve_type.id,
                }
            ],
        )

        # when
        tasks.update_character_contracts(character_pk=character.pk, force_update=False)

        # then
        self.assertEqual(character.contracts.count(), 1)
        contract: CharacterContract = character.contracts.first()
        self.assertEqual(contract.contract_id, contract_id)

        self.assertEqual(contract.items.count(), 1)
        item: CharacterContractItem = contract.items.first()
        self.assertEqual(item.record_id, record_id)

    @pook.on
    def test_should_fetch_items_for_new_contracts_only(self):
        # given
        character = CharacterFactory()
        contract_1 = CharacterContractItemExchangeFactory(
            character=character, contract_type=CharacterContract.TYPE_ITEM_EXCHANGE
        )
        contract_2_id = 42
        pook.get(
            make_esi_url(f"characters/{character.character_id}/contracts"),
            reply=200,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "acceptor_id": 0,
                    "assignee_id": 0,
                    "availability": "public",
                    "contract_id": contract_1.contract_id,
                    "date_expired": contract_1.date_expired.isoformat(),
                    "date_issued": contract_1.date_issued.isoformat(),
                    "for_corporation": contract_1.for_corporation,
                    "issuer_corporation_id": contract_1.issuer_corporation.id,
                    "issuer_id": contract_1.issuer.id,
                    "price": contract_1.price,
                    "status": "outstanding",
                    "type": "item_exchange",
                },
                {
                    "assignee_id": 0,
                    "acceptor_id": 0,
                    "availability": "public",
                    "contract_id": contract_2_id,
                    "date_expired": now().isoformat(),
                    "date_issued": now().isoformat(),
                    "for_corporation": False,
                    "issuer_corporation_id": EveEntityCorporationFactory().id,
                    "issuer_id": EveEntityCharacterFactory().id,
                    "status": "outstanding",
                    "type": "item_exchange",
                },
            ],
        )
        record_id = 1
        quantity = 3
        eve_type = EveTypeFactory()
        pook.get(
            make_esi_url(
                f"characters/{character.character_id}/contracts/{contract_2_id}/items"
            ),
            reply=200,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "is_included": True,
                    "is_singleton": False,
                    "quantity": quantity,
                    "record_id": record_id,
                    "type_id": eve_type.id,
                }
            ],
        )
        # only the route for contract_2 is provided.
        # Test would break when it tries to fetch items for contract 1.

        # when
        tasks.update_character_contracts(character_pk=character.pk, force_update=False)

        # then
        got = extract(character.contracts, "contract_id")
        want = {contract_1.contract_id, contract_2_id}
        self.assertSetEqual(got, want)
