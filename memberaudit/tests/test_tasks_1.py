import datetime as dt
from typing import Dict
from unittest.mock import patch

from bravado.exception import HTTPError
from celery.exceptions import Retry as CeleryRetry

from django.test import TestCase, override_settings, tag
from django.utils.dateparse import parse_datetime
from django.utils.timezone import now
from esi.models import Token
from eveuniverse.models import EveSolarSystem, EveType
from eveuniverse.tests.testdata.factories import create_eve_entity

from allianceauth.eveonline.models import EveCharacter
from app_utils.esi import EsiErrorLimitExceeded, EsiOffline, EsiStatus
from app_utils.esi_testing import EsiClientStub, EsiEndpoint, build_http_error
from app_utils.testing import (  # NoSocketsTestCase,
    create_authgroup,
    create_user_from_evecharacter,
    generate_invalid_pk,
)

from memberaudit import tasks
from memberaudit.helpers import UpdateSectionResult
from memberaudit.models import (
    Character,
    CharacterContract,
    CharacterUpdateStatus,
    Location,
)

from .testdata.esi_client_stub import esi_client_stub, esi_error_stub, esi_stub
from .testdata.factories import (
    create_character,
    create_character_asset,
    create_character_contract,
    create_character_contract_item,
    create_character_mail,
    create_character_update_status,
    create_compliance_group_designation,
    create_mail_entity_from_eve_entity,
)
from .testdata.load_entities import load_entities
from .testdata.load_eveuniverse import load_eveuniverse
from .testdata.load_locations import load_locations
from .utils import create_memberaudit_character, reset_celery_once_locks

MODELS_PATH = "memberaudit.models"
MANAGERS_PATH = "memberaudit.managers"
TASKS_PATH = "memberaudit.tasks"


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
        group = create_authgroup(internal=False)
        create_compliance_group_designation(group)
        # when
        tasks.run_regular_updates()
        # then
        self.assertTrue(mock_update_market_prices.apply_async.called)
        self.assertTrue(mock_update_all_characters.apply_async.called)
        self.assertTrue(mock_update_compliance_groups_for_all.apply_async.called)


@patch(MANAGERS_PATH + ".general.fetch_esi_status", lambda: EsiStatus(True, 99, 60))
@patch(MANAGERS_PATH + ".character_sections_1.data_retention_cutoff", lambda: None)
@patch(MANAGERS_PATH + ".character_sections_2.data_retention_cutoff", lambda: None)
@patch(MANAGERS_PATH + ".character_sections_3.data_retention_cutoff", lambda: None)
@patch(MANAGERS_PATH + ".character_sections_1.esi", esi_stub)
@patch(MANAGERS_PATH + ".character_sections_2.esi", esi_stub)
@patch(MANAGERS_PATH + ".character_sections_3.esi", esi_stub)
@patch(MANAGERS_PATH + ".general.esi", esi_stub)
@override_settings(
    CELERY_ALWAYS_EAGER=True,
    CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
    APP_UTILS_OBJECT_CACHE_DISABLED=True,
)
class TestUpdateCharacter(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        load_locations()
        reset_celery_once_locks()

    def setUp(self) -> None:
        self.character_1001 = create_memberaudit_character(1001)

    @tag("breaks_with_tox")  # FIXME: Find solution
    @patch(MODELS_PATH + ".characters.MEMBERAUDIT_FEATURE_ROLES_ENABLED", True)
    def test_should_update_all_sections_from_scratch(self):
        # when
        result = tasks.update_character(self.character_1001.pk)

        # then
        self.assertTrue(result)

        status_all: Dict[str, CharacterUpdateStatus] = {
            obj.section: obj for obj in self.character_1001.update_status_set.all()
        }
        for section in Character.UpdateSection:
            with self.subTest(section=section):
                self.assertTrue(status_all[section].is_success)

    @tag("breaks_with_tox")  # FXME: Find solution
    @patch(MODELS_PATH + ".characters.MEMBERAUDIT_FEATURE_ROLES_ENABLED", False)
    def test_should_update_enabled_sections_only(self):
        # given
        run_started_at = now() - dt.timedelta(hours=24)
        for section in Character.UpdateSection:
            create_character_update_status(
                character=self.character_1001,
                section=section,
                is_success=True,
                run_started_at=run_started_at,
                run_finished_at=run_started_at,
            )

        # when
        result = tasks.update_character(self.character_1001.pk)

        # then
        self.assertTrue(result)

        for section in Character.UpdateSection.enabled_sections():
            with self.subTest(section=section):
                self.assertFalse(
                    self.character_1001.is_update_needed_for_section(section=section)
                )

        self.assertTrue(
            self.character_1001.is_update_needed_for_section(
                section=Character.UpdateSection.ROLES
            )
        )

    @patch(TASKS_PATH + ".Character.update_loyalty", spec=True)
    def test_should_update_normal_section_only_when_stale(self, update_loyalty):
        # given
        create_character_update_status(
            character=self.character_1001,
            section=Character.UpdateSection.LOYALTY,
            is_success=True,
            run_started_at=now() - dt.timedelta(seconds=30),
            run_finished_at=now(),
        )
        # when
        tasks.update_character(self.character_1001.pk)
        # then
        self.assertFalse(update_loyalty.called)

    @patch(TASKS_PATH + ".update_character_mails", spec=True)
    def test_should_update_special_section_only_when_stale(
        self, mock_update_character_mails
    ):
        # given
        create_character_update_status(
            character=self.character_1001,
            section=Character.UpdateSection.MAILS,
            is_success=True,
            run_started_at=now() - dt.timedelta(seconds=30),
            run_finished_at=now(),
        )
        # when
        tasks.update_character(self.character_1001.pk)
        # then
        self.assertFalse(mock_update_character_mails.apply_async.called)

    def test_should_update_section_when_not_stale_but_force_update_requested(self):
        # given
        status = create_character_update_status(
            character=self.character_1001,
            section=Character.UpdateSection.SKILLS.value,
            is_success=True,
            run_started_at=now() - dt.timedelta(seconds=30),
            run_finished_at=now(),
        )
        last_finished = status.run_finished_at
        # when
        tasks.update_character(
            self.character_1001.pk, force_update=True, ignore_stale=True
        )
        # then
        status.refresh_from_db()
        self.assertGreater(status.run_finished_at, last_finished)
        self.assertTrue(status.update_finished_at)

    def test_should_update_section_when_not_stale_but_ignore_stale(self):
        # given
        tasks.update_character_skills(self.character_1001.pk, force_update=True)
        status = self.character_1001.update_status_for_section("skills")
        status.update_finished_at = None
        status.save()
        # when
        tasks.update_character(self.character_1001.pk, ignore_stale=True)
        # then
        status.refresh_from_db()
        self.assertIsNone(status.update_finished_at)

    def test_should_do_nothing_when_not_required(self):
        # given
        for section in Character.UpdateSection.values:
            create_character_update_status(
                character=self.character_1001,
                section=section,
                is_success=True,
                run_started_at=now() - dt.timedelta(seconds=30),
                run_finished_at=now(),
            )
        # when
        result = tasks.update_character(self.character_1001.pk)
        # then
        self.assertFalse(result)

    def test_can_do_forced_update(self):
        # when
        result = tasks.update_character(self.character_1001.pk, force_update=True)
        # then
        self.assertTrue(result)
        self.assertTrue(self.character_1001.is_update_status_ok())

    def test_skip_update_for_orphans(self):
        # given
        character = create_character(EveCharacter.objects.get(character_id=1121))
        # when
        result = tasks.update_character(character.pk)
        # then
        self.assertFalse(result)
        self.assertIsNone(character.is_update_status_ok())


@patch(MANAGERS_PATH + ".general.fetch_esi_status", lambda: EsiStatus(True, 99, 60))
@patch(MANAGERS_PATH + ".character_sections_1.data_retention_cutoff", lambda: None)
@patch(MANAGERS_PATH + ".character_sections_2.data_retention_cutoff", lambda: None)
@patch(MANAGERS_PATH + ".character_sections_3.data_retention_cutoff", lambda: None)
@patch(MANAGERS_PATH + ".character_sections_1.esi", esi_error_stub)
@patch(MANAGERS_PATH + ".character_sections_2.esi", esi_error_stub)
@patch(MANAGERS_PATH + ".character_sections_3.esi", esi_error_stub)
@patch(MANAGERS_PATH + ".general.esi", esi_error_stub)
@override_settings(
    CELERY_ALWAYS_EAGER=True,
    CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
    APP_UTILS_OBJECT_CACHE_DISABLED=True,
)
class TestUpdateCharacterErrorReporting(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        load_locations()
        reset_celery_once_locks()

    def setUp(self) -> None:
        self.character_1001 = create_memberaudit_character(1001)

    def test_should_report_errors_during_updates(self):
        # when
        with self.assertRaises(HTTPError):  # raised when trying to fetch attributes
            tasks.update_character(self.character_1001.pk)
        # then
        self.assertFalse(self.character_1001.is_update_status_ok())
        status = self.character_1001.update_status_set.filter(
            character=self.character_1001, is_success=False
        ).first()
        self.assertEqual(status.error_message, "HTTPBadGateway: 502 Test exception")
        self.assertTrue(status.run_finished_at)


@override_settings(
    CELERY_ALWAYS_EAGER=True,
    CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
    APP_UTILS_OBJECT_CACHE_DISABLED=True,
)
@patch(MANAGERS_PATH + ".character_sections_1.esi")
class TestUpdateCharacterAssets(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        load_locations()
        cls.character_1001 = create_memberaudit_character(1001)
        cls.character_1002 = create_memberaudit_character(1002)
        cls.token = (
            cls.character_1001.eve_character.character_ownership.user.token_set.first()
        )
        cls.jita = EveSolarSystem.objects.get(id=30000142)
        cls.jita_44 = Location.objects.get(id=60003760)
        cls.amamake = EveSolarSystem.objects.get(id=30002537)
        cls.structure_1 = Location.objects.get(id=1_000_000_000_001)
        reset_celery_once_locks()

    def test_should_create_assets_from_scratch(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub

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
                1_100_000_000_006,
                1_100_000_000_007,
                1_100_000_000_008,
            },
        )

        asset = self.character_1001.assets.get(item_id=1_100_000_000_001)
        self.assertTrue(asset.is_blueprint_copy)
        self.assertTrue(asset.is_singleton)
        self.assertEqual(asset.location_flag, "Hangar")
        self.assertEqual(asset.location_id, 60003760)
        self.assertEqual(asset.quantity, 1)
        self.assertEqual(asset.eve_type, EveType.objects.get(id=20185))
        self.assertEqual(asset.name, "Parent Item 1")

        asset = self.character_1001.assets.get(item_id=1_100_000_000_002)
        self.assertFalse(asset.is_blueprint_copy)
        self.assertTrue(asset.is_singleton)
        self.assertEqual(asset.location_flag, "???")
        self.assertEqual(asset.parent.item_id, 1_100_000_000_001)
        self.assertEqual(asset.quantity, 1)
        self.assertEqual(asset.eve_type, EveType.objects.get(id=19540))
        self.assertEqual(asset.name, "Leaf Item 2")

        asset = self.character_1001.assets.get(item_id=1_100_000_000_003)
        self.assertEqual(asset.parent.item_id, 1_100_000_000_001)
        self.assertEqual(asset.eve_type, EveType.objects.get(id=23))

        asset = self.character_1001.assets.get(item_id=1_100_000_000_004)
        self.assertEqual(asset.parent.item_id, 1_100_000_000_003)
        self.assertEqual(asset.eve_type, EveType.objects.get(id=19553))

        asset = self.character_1001.assets.get(item_id=1_100_000_000_005)
        self.assertEqual(asset.location, self.structure_1)
        self.assertEqual(asset.eve_type, EveType.objects.get(id=20185))

        asset = self.character_1001.assets.get(item_id=1_100_000_000_006)
        self.assertEqual(asset.parent.item_id, 1_100_000_000_005)
        self.assertEqual(asset.eve_type, EveType.objects.get(id=19540))

        asset = self.character_1001.assets.get(item_id=1_100_000_000_007)
        self.assertEqual(asset.location_id, 30000142)
        self.assertEqual(asset.name, "")
        self.assertEqual(asset.eve_type, EveType.objects.get(id=19540))

        asset = self.character_1001.assets.get(item_id=1_100_000_000_008)
        self.assertEqual(asset.location_id, 1_000_000_000_001)

    def test_should_remove_obsolete_assets(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        create_character_asset(
            character=self.character_1001, item_id=1100000000666, location=self.jita_44
        )

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
                1_100_000_000_006,
                1_100_000_000_007,
                1_100_000_000_008,
            },
        )

    def test_should_update_existing_assets(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        create_character_asset(
            character=self.character_1001,
            item_id=1_100_000_000_001,
            location=self.jita_44,
            eve_type=EveType.objects.get(id=20185),
            is_singleton=True,
            name="Parent Item 1",
            quantity=10,
        )

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
                1_100_000_000_006,
                1_100_000_000_007,
                1_100_000_000_008,
            },
        )

        asset = self.character_1001.assets.get(item_id=1_100_000_000_001)
        self.assertTrue(asset.is_singleton)
        self.assertEqual(asset.location_id, 60003760)
        self.assertEqual(asset.quantity, 1)
        self.assertEqual(asset.eve_type, EveType.objects.get(id=20185))
        self.assertEqual(asset.name, "Parent Item 1")

    def test_should_keep_assets_which_are_moved_to_different_locations(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        parent_asset = create_character_asset(
            character=self.character_1001,
            item_id=1100000000666,
            location=self.jita_44,
            eve_type=EveType.objects.get(id=20185),
        )
        create_character_asset(
            character=self.character_1001,
            item_id=1_100_000_000_002,
            parent=parent_asset,
            eve_type=EveType.objects.get(id=19540),
            quantity=1,
        )

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
                1_100_000_000_006,
                1_100_000_000_007,
                1_100_000_000_008,
            },
        )

    def test_should_report_update_success_when_update_succeeded(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub

        # when
        tasks.update_character_assets(self.character_1001.pk, True)

        # then
        status = self.character_1001.update_status_set.get(
            section=Character.UpdateSection.ASSETS
        )
        self.assertTrue(status.is_success)
        self.assertFalse(status.error_message)

    def test_should_report_the_error_when_update_failed(self, mock_esi):
        # given
        exception = build_http_error(502, "Test exception")
        mock_esi.client.Assets.get_characters_character_id_assets.side_effect = (
            exception
        )

        # when
        with self.assertRaises(HTTPError):
            tasks.update_character_assets(self.character_1001.pk, True)

        # then
        status = self.character_1001.update_status_set.get(
            section=Character.UpdateSection.ASSETS
        )
        self.assertFalse(status.is_success)
        self.assertEqual(status.error_message, "HTTPBadGateway: 502 Test exception")

    def test_should_report_error_when_preload_objects_failed(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub

        # when
        with patch(
            MANAGERS_PATH + ".general.LocationManager.get_or_create_esi_async",
            spec=True,
        ) as m:
            exception = build_http_error(502, "Test exception")
            m.side_effect = exception
            with self.assertRaises(HTTPError):
                tasks.update_character_assets(self.character_1001.pk, True)

        # then
        status = self.character_1001.update_status_set.get(
            section=Character.UpdateSection.ASSETS
        )
        self.assertFalse(status.is_success)
        self.assertEqual(status.error_message, "HTTPBadGateway: 502 Test exception")

    def test_should_report_the_error_when_building_the_asset_tree_failed(
        self, mock_esi
    ):
        # given
        mock_esi.client = esi_client_stub

        # when
        with patch(MANAGERS_PATH + ".character_sections_1.logger") as m:
            exception = build_http_error(502, "Test exception")
            m.info.side_effect = exception
            with self.assertRaises(HTTPError):
                tasks.update_character_assets(self.character_1001.pk, True)

        # then
        status = self.character_1001.update_status_set.get(
            section=Character.UpdateSection.ASSETS
        )
        self.assertFalse(status.is_success)
        self.assertEqual(status.error_message, "HTTPBadGateway: 502 Test exception")

    def test_should_not_recreate_asset_tree_when_info_from_ESI_is_unchanged(
        self, mock_esi
    ):
        # given
        mock_esi.client = esi_client_stub
        self.character_1001.reset_update_section(Character.UpdateSection.ASSETS)
        tasks.update_character_assets(self.character_1001.pk, True)
        asset = self.character_1001.assets.get(item_id=1_100_000_000_001)
        asset.name = "New Name"
        asset.save()

        # when
        tasks.update_character_assets(self.character_1001.pk, False)

        # then
        asset = self.character_1001.assets.get(item_id=1_100_000_000_001)
        self.assertEqual(asset.name, "New Name")

        status = self.character_1001.update_status_set.get(
            section=Character.UpdateSection.ASSETS
        )
        self.assertTrue(status.is_success)

    def test_should_recreate_asset_tree_when_info_from_ESI_is_unchanged_and_is_forced(
        self, mock_esi
    ):
        # given
        mock_esi.client = esi_client_stub
        self.character_1001.reset_update_section(Character.UpdateSection.ASSETS)
        tasks.update_character_assets(self.character_1001.pk, True)
        asset = self.character_1001.assets.get(item_id=1_100_000_000_001)
        asset.name = "New Name"
        asset.save()

        # when
        tasks.update_character_assets(self.character_1001.pk, force_update=True)

        # then
        asset = self.character_1001.assets.get(item_id=1_100_000_000_001)
        self.assertEqual(asset.name, "Parent Item 1")

        status = self.character_1001.update_status_set.get(
            section=Character.UpdateSection.ASSETS
        )
        self.assertTrue(status.is_success)


@override_settings(
    CELERY_ALWAYS_EAGER=True,
    CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
    APP_UTILS_OBJECT_CACHE_DISABLED=True,
)
@patch(MANAGERS_PATH + ".general.fetch_esi_status", lambda: EsiStatus(True, 99, 60))
@patch(MANAGERS_PATH + ".character_sections_1.esi")
class TestUpdateCharacterContacts(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        cls.character_1001 = create_memberaudit_character(1001)
        cls.token = (
            cls.character_1001.eve_character.character_ownership.user.token_set.first()
        )
        reset_celery_once_locks()

    def test_update_ok(self, mock_esi):
        """when update succeeded then report update success"""
        mock_esi.client = esi_client_stub

        tasks.update_character_contacts(self.character_1001.pk, True)

        status = self.character_1001.update_status_set.get(
            section=Character.UpdateSection.CONTACTS
        )
        self.assertTrue(status.is_success)
        self.assertFalse(status.error_message)

    def test_detect_error(self, mock_esi):
        """when update failed then report the error"""
        exception = build_http_error(502, "Test exception")
        mock_esi.client.Contacts.get_characters_character_id_contacts_labels.side_effect = (
            exception
        )

        with self.assertRaises(HTTPError):
            tasks.update_character_contacts(self.character_1001.pk, True)

        status = self.character_1001.update_status_set.get(
            section=Character.UpdateSection.CONTACTS
        )
        self.assertFalse(status.is_success)
        self.assertEqual(status.error_message, "HTTPBadGateway: 502 Test exception")


@override_settings(
    CELERY_ALWAYS_EAGER=True,
    CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
    APP_UTILS_OBJECT_CACHE_DISABLED=True,
)
@patch(MANAGERS_PATH + ".general.fetch_esi_status", lambda: EsiStatus(True, 99, 60))
@patch(MANAGERS_PATH + ".character_sections_1.data_retention_cutoff", lambda: None)
@patch(MANAGERS_PATH + ".character_sections_1.esi")
class TestUpdateCharacterContracts(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        reset_celery_once_locks()
        load_eveuniverse()
        load_entities()
        load_locations()
        cls.character_1001 = create_memberaudit_character(1001)
        cls.token = (
            cls.character_1001.eve_character.character_ownership.user.token_set.first()
        )

    def test_should_record_success_when_update_completed_successfully(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub

        # when
        tasks.update_character_contracts(self.character_1001.pk, True)

        # then
        status = self.character_1001.update_status_set.get(
            section=Character.UpdateSection.CONTRACTS
        )
        self.assertTrue(status.is_success)
        self.assertFalse(status.error_message)
        self.assertTrue(status.run_finished_at)
        self.assertTrue(status.update_finished_at)

    def test_should_record_error_when_update_failed(self, mock_esi):
        # given
        exception = build_http_error(502, "Test exception")
        mock_esi.client.Contracts.get_characters_character_id_contracts.side_effect = (
            exception
        )

        # when
        with self.assertRaises(HTTPError):
            tasks.update_character_contracts(self.character_1001.pk, True)

        # then
        status = self.character_1001.update_status_set.get(
            section=Character.UpdateSection.CONTRACTS
        )
        self.assertFalse(status.is_success)
        self.assertEqual(status.error_message, "HTTPBadGateway: 502 Test exception")

    def test_should_store_new_item_exchange_contract_with_items(self, mock_esi):
        # given
        endpoints = [
            EsiEndpoint(
                "Contracts",
                "get_characters_character_id_contracts",
                "character_id",
                needs_token=True,
                data={
                    "1001": [
                        {
                            "acceptor_id": 1101,
                            "assignee_id": 2101,
                            "availability": "personal",
                            "buyout": None,
                            "collateral": 0.0,
                            "contract_id": 100000011,
                            "date_accepted": "2019-09-13T17:23:44Z",
                            "date_completed": "2019-09-13T17:23:44Z",
                            "date_expired": "2019-10-15T23:08:38Z",
                            "date_issued": "2019-09-12T23:08:38Z",
                            "days_to_complete": 0,
                            "end_location_id": 1000000000001,
                            "for_corporation": False,
                            "issuer_corporation_id": 2001,
                            "issuer_id": 1001,
                            "price": 270000000.0,
                            "reward": 0.0,
                            "start_location_id": 1000000000001,
                            "status": "finished",
                            "title": "Alpha Contract",
                            "type": "item_exchange",
                            "volume": 486000.0,
                        }
                    ]
                },
            ),
            EsiEndpoint(
                "Contracts",
                "get_characters_character_id_contracts_contract_id_items",
                ("character_id", "contract_id"),
                needs_token=True,
                data={
                    "1001": {
                        "100000011": [
                            {
                                "is_included": True,
                                "is_singleton": False,
                                "quantity": 3,
                                "record_id": 1,
                                "type_id": 19540,
                            }
                        ]
                    }
                },
            ),
        ]
        mock_esi.client = EsiClientStub.create_from_endpoints(endpoints)

        # when
        tasks.update_character_contracts(self.character_1001.pk, False)

        # then
        self.assertEqual(self.character_1001.contracts.count(), 1)
        contract = self.character_1001.contracts.get(contract_id=100000011)
        self.assertEqual(contract.title, "Alpha Contract")
        self.assertEqual(contract.items.count(), 1)
        item = contract.items.get(record_id=1)
        self.assertEqual(item.quantity, 3)

    def test_should_fetch_items_for_new_contracts_only(self, mock_esi):
        # given esi has two contracts
        endpoints = [
            EsiEndpoint(
                "Contracts",
                "get_characters_character_id_contracts",
                "character_id",
                needs_token=True,
                data={
                    "1001": [
                        {
                            "acceptor_id": 1101,
                            "assignee_id": 2101,
                            "availability": "personal",
                            "buyout": None,
                            "collateral": 0.0,
                            "contract_id": 100000011,
                            "date_accepted": "2019-09-13T17:23:44Z",
                            "date_completed": "2019-09-13T17:23:44Z",
                            "date_expired": "2019-10-15T23:08:38Z",
                            "date_issued": "2019-09-12T23:08:38Z",
                            "days_to_complete": 0,
                            "end_location_id": 1000000000001,
                            "for_corporation": False,
                            "issuer_corporation_id": 2001,
                            "issuer_id": 1001,
                            "price": 1000000.0,
                            "reward": 0.0,
                            "start_location_id": 1000000000001,
                            "status": "finished",
                            "title": "Alpha Contract",
                            "type": "item_exchange",
                            "volume": 486000.0,
                        },
                        {
                            "acceptor_id": 1101,
                            "assignee_id": 2101,
                            "availability": "personal",
                            "buyout": None,
                            "collateral": 0.0,
                            "contract_id": 100000012,
                            "date_accepted": "2019-09-13T17:23:44Z",
                            "date_completed": "2019-09-13T17:23:44Z",
                            "date_expired": "2019-10-15T23:08:38Z",
                            "date_issued": "2019-09-12T23:08:38Z",
                            "days_to_complete": 0,
                            "end_location_id": 1000000000001,
                            "for_corporation": False,
                            "issuer_corporation_id": 2001,
                            "issuer_id": 1001,
                            "price": 2000000.0,
                            "reward": 0.0,
                            "start_location_id": 1000000000001,
                            "status": "finished",
                            "title": "Bravo Contract",
                            "type": "item_exchange",
                            "volume": 486000.0,
                        },
                    ]
                },
            ),
            EsiEndpoint(
                "Contracts",
                "get_characters_character_id_contracts_contract_id_items",
                ("character_id", "contract_id"),
                needs_token=True,
                data={
                    "1001": {
                        "100000011": [
                            {
                                "is_included": True,
                                "is_singleton": False,
                                "quantity": 3,
                                "record_id": 1,
                                "type_id": 19540,
                            }
                        ],
                        "100000012": [
                            {
                                "is_included": True,
                                "is_singleton": False,
                                "quantity": 5,
                                "record_id": 1,
                                "type_id": 19551,
                            }
                        ],
                    }
                },
            ),
        ]
        mock_esi.client = EsiClientStub.create_from_endpoints(endpoints)

        # and one contract already exists in the database
        contract_11 = create_character_contract(
            character=self.character_1001,
            contract_id=100000011,
            availability=CharacterContract.AVAILABILITY_PERSONAL,
            contract_type=CharacterContract.TYPE_ITEM_EXCHANGE,
            date_accepted=parse_datetime("2019-09-13T17:23:44Z"),
            date_completed=parse_datetime("2019-09-13T17:23:44Z"),
            date_expired=parse_datetime("2019-10-15T23:08:38Z"),
            date_issued=parse_datetime("2019-09-12T23:08:38Z"),
            for_corporation=False,
            issuer_id=1001,
            issuer_corporation_id=2001,
            status=CharacterContract.STATUS_FINISHED,
            title="Old Alpha Contract",  # = "Alpha Contract" in esi data
            end_location_id=1000000000001,
        )
        create_character_contract_item(
            contract=contract_11,
            record_id=1,
            is_included=True,
            is_singleton=False,
            quantity=1,  # = 3 in esi data
            eve_type_id=19540,
        )

        # when contracts are updated
        with patch(
            TASKS_PATH + ".update_contract_items_esi",
            wraps=tasks.update_contract_items_esi,
        ) as spy_update_contract_items_esi:
            tasks.update_character_contracts(self.character_1001.pk, False)

            # then we still have two contracts in the database
            # and contract 11 still has the "old" data (= not updated)
            self.assertEqual(self.character_1001.contracts.count(), 2)

            contract_11 = self.character_1001.contracts.get(contract_id=100000011)
            self.assertEqual(contract_11.title, "Old Alpha Contract")
            self.assertEqual(contract_11.items.count(), 1)
            item = contract_11.items.get(record_id=1)
            self.assertEqual(item.quantity, 1)

            contract_12 = self.character_1001.contracts.get(contract_id=100000012)
            self.assertEqual(contract_12.title, "Bravo Contract")
            self.assertEqual(contract_12.items.count(), 1)
            item = contract_12.items.get(record_id=1)
            self.assertEqual(item.quantity, 5)

            # and the task for fetching contract items has been called
            # for then new contract (#12) only
            contract_pks = {
                o[1]["kwargs"]["contract_pk"]
                for o in spy_update_contract_items_esi.apply_async.call_args_list
            }
            self.assertSetEqual(contract_pks, {contract_12.pk})


@override_settings(
    CELERY_ALWAYS_EAGER=True,
    CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
    APP_UTILS_OBJECT_CACHE_DISABLED=True,
)
@patch(MANAGERS_PATH + ".character_sections_2.data_retention_cutoff", lambda: None)
@patch(MANAGERS_PATH + ".general.fetch_esi_status", lambda: EsiStatus(True, 99, 60))
@patch(MANAGERS_PATH + ".character_sections_2.esi")
@patch(MANAGERS_PATH + ".general.esi")
class TestUpdateCharacterMails(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        cls.character_1001 = create_memberaudit_character(1001)
        reset_celery_once_locks()

        endpoints = [
            EsiEndpoint(
                "Mail",
                "get_characters_character_id_mail_lists",
                "character_id",
                needs_token=True,
                data={
                    "1001": [
                        {
                            "mailing_list_id": 9001,
                            "name": "Dummy 1",
                        }
                    ]
                },
            ),
            EsiEndpoint(
                "Mail",
                "get_characters_character_id_mail_labels",
                "character_id",
                needs_token=True,
                data={
                    "1001": {
                        "labels": [
                            {
                                "color": "#660066",
                                "label_id": 1,
                                "name": "PINK",
                                "unread_count": 7,
                            }
                        ],
                        "total_unread_count": 1,
                    }
                },
            ),
            EsiEndpoint(
                "Mail",
                "get_characters_character_id_mail",
                "character_id",
                needs_token=True,
                data={
                    "1001": [
                        {
                            "from": 1002,
                            "labels": None,
                            "mail_id": 1,
                            "recipients": [
                                {"recipient_id": 1001, "recipient_type": "character"}
                            ],
                            "subject": "subject 1",
                            "timestamp": "2015-09-30T18:07:00Z",
                        },
                        {
                            "from": 9001,
                            "labels": [1],
                            "mail_id": 2,
                            "recipients": [
                                {"recipient_id": 1001, "recipient_type": "character"}
                            ],
                            "subject": "subject 2",
                            "timestamp": "2015-09-30T19:07:00Z",
                        },
                    ]
                },
            ),
            EsiEndpoint(
                "Mail",
                "get_characters_character_id_mail_mail_id",
                "mail_id",
                needs_token=True,
                data={
                    "1": {
                        "body": "body 1",
                        "from": 1002,
                        "labels": None,
                        "read": True,
                        "subject": "subject 1",
                        "timestamp": "2015-09-30T18:07:00Z",
                    },
                    "2": {
                        "body": "body 2",
                        "from": 9001,
                        "labels": [1],
                        "read": False,
                        "subject": "subject 2",
                        "timestamp": "2015-09-30T18:07:00Z",
                    },
                },
            ),
        ]
        cls.esi_client_stub = EsiClientStub.create_from_endpoints(endpoints)

    def test_should_update_mails_from_scratch_and_report_success(
        self, mock_esi_general, mock_esi_sections
    ):
        # given
        mock_esi_general.client = self.esi_client_stub
        mock_esi_sections.client = self.esi_client_stub

        # when
        tasks.update_character_mails.delay(self.character_1001.pk, True)

        # then
        status: CharacterUpdateStatus = self.character_1001.update_status_set.get(
            section=Character.UpdateSection.MAILS
        )
        self.assertTrue(status.is_success)
        self.assertFalse(status.error_message)
        self.assertTrue(status.run_started_at)
        self.assertTrue(status.run_finished_at)
        self.assertTrue(status.update_started_at)
        self.assertTrue(status.update_finished_at)

        mail_ids = set(self.character_1001.mails.values_list("mail_id", flat=True))
        self.assertSetEqual(mail_ids, {1, 2})

        mail = self.character_1001.mails.get(mail_id=1)
        self.assertEqual(mail.subject, "subject 1")
        self.assertEqual(mail.body, "body 1")

        mail = self.character_1001.mails.get(mail_id=2)
        self.assertEqual(mail.subject, "subject 2")
        self.assertEqual(mail.body, "body 2")
        label_ids = set(mail.labels.values_list("label_id", flat=True))
        self.assertEqual(label_ids, {1})

    # TODO: Add test to check force update works

    def test_should_report_error_when_update_failed(
        self, mock_esi_general, mock_esi_sections
    ):
        # given
        mock_esi_general.client = self.esi_client_stub
        exception = build_http_error(502, "Test exception")
        mock_esi_sections.client.Mail.get_characters_character_id_mail_labels.side_effect = (
            exception
        )
        # when
        with self.assertRaises(HTTPError):
            tasks.update_character_mails(self.character_1001.pk, True)

        # then
        status: CharacterUpdateStatus = self.character_1001.update_status_set.get(
            section=Character.UpdateSection.MAILS
        )
        self.assertFalse(status.is_success)
        self.assertEqual(status.error_message, "HTTPBadGateway: 502 Test exception")
        self.assertTrue(status.run_started_at)
        self.assertTrue(status.run_finished_at)
        self.assertIsNone(status.update_started_at)
        self.assertIsNone(status.update_finished_at)

    def test_should_only_fetch_body_for_new_mails(
        self, mock_esi_general, mock_esi_sections
    ):
        # given
        mock_esi_general.client = self.esi_client_stub
        mock_esi_sections.client = self.esi_client_stub

        sender = create_mail_entity_from_eve_entity(1002)
        recipient = create_mail_entity_from_eve_entity(1001)
        create_character_mail(
            character=self.character_1001,
            recipients=[recipient],
            mail_id=1,
            sender=sender,
            subject="subject 1",
            body="body 1",
            timestamp=parse_datetime("2015-09-30T18:07:00Z"),
        )

        # when
        with patch(
            TASKS_PATH + ".update_mail_body_esi", wraps=tasks.update_mail_body_esi
        ) as spy_update_mail_body_esi:
            tasks.update_character_mails.delay(
                self.character_1001.pk, force_update=False
            )

            # then
            mail_ids = set(self.character_1001.mails.values_list("mail_id", flat=True))
            self.assertSetEqual(mail_ids, {1, 2})

            mail = self.character_1001.mails.get(mail_id=1)
            self.assertEqual(mail.subject, "subject 1")
            self.assertEqual(mail.body, "body 1")

            mail = self.character_1001.mails.get(mail_id=2)
            self.assertEqual(mail.subject, "subject 2")
            self.assertEqual(mail.body, "body 2")

            self.assertEqual(spy_update_mail_body_esi.apply_async.call_count, 1)

    def test_should_fetch_body_for_all_mails_from_header_when_forced(
        self, mock_esi_general, mock_esi_sections
    ):
        # given
        mock_esi_general.client = self.esi_client_stub
        mock_esi_sections.client = self.esi_client_stub

        sender = create_mail_entity_from_eve_entity(1002)
        recipient = create_mail_entity_from_eve_entity(1001)
        create_character_mail(
            character=self.character_1001,
            recipients=[recipient],
            mail_id=1,
            sender=sender,
            subject="subject 1",
            body="body 1",
            timestamp=parse_datetime("2015-09-30T18:07:00Z"),
        )

        # when
        with patch(
            TASKS_PATH + ".update_mail_body_esi", wraps=tasks.update_mail_body_esi
        ) as spy_update_mail_body_esi:
            tasks.update_character_mails.delay(
                self.character_1001.pk, force_update=True
            )

            # then
            mail_ids = set(self.character_1001.mails.values_list("mail_id", flat=True))
            self.assertSetEqual(mail_ids, {1, 2})

            mail = self.character_1001.mails.get(mail_id=1)
            self.assertEqual(mail.subject, "subject 1")
            self.assertEqual(mail.body, "body 1")

            mail = self.character_1001.mails.get(mail_id=2)
            self.assertEqual(mail.subject, "subject 2")
            self.assertEqual(mail.body, "body 2")

            self.assertEqual(spy_update_mail_body_esi.apply_async.call_count, 2)


@patch(MANAGERS_PATH + ".general.fetch_esi_status", lambda: EsiStatus(True, 99, 60))
@patch(TASKS_PATH + ".Location.objects.structure_update_or_create_esi", spec=True)
class TestUpdateStructureEsi(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities()
        cls.character = create_memberaudit_character(1001)
        cls.token = (
            cls.character.eve_character.character_ownership.user.token_set.first()
        )

    def test_normal(self, mock_structure_update_or_create_esi):
        """When ESI status is ok, then create MailEntity"""
        mock_structure_update_or_create_esi.return_value = None
        try:
            tasks.update_structure_esi(id=1_000_000_000_001, token_pk=self.token.pk)
        except Exception as ex:
            self.fail(f"Unexpected exception occurred: {ex}")

    def test_invalid_token(self, mock_structure_update_or_create_esi):
        """When called with invalid token, raise exception"""
        mock_structure_update_or_create_esi.side_effect = EsiOffline

        with self.assertRaises(Token.DoesNotExist):
            tasks.update_structure_esi(
                id=1_000_000_000_001, token_pk=generate_invalid_pk(Token)
            )

    def test_esi_status_1(self, mock_structure_update_or_create_esi):
        """When ESI is offline, then retry"""
        mock_structure_update_or_create_esi.side_effect = EsiOffline

        with self.assertRaises(CeleryRetry):
            tasks.update_structure_esi(id=1_000_000_000_001, token_pk=self.token.pk)

    def test_esi_status_2(self, mock_structure_update_or_create_esi):
        """When ESI error limit reached, then retry"""
        mock_structure_update_or_create_esi.side_effect = EsiErrorLimitExceeded(5)

        with self.assertRaises(CeleryRetry):
            tasks.update_structure_esi(id=1_000_000_000_001, token_pk=self.token.pk)


@patch(MANAGERS_PATH + ".general.fetch_esi_status", lambda: EsiStatus(True, 99, 60))
@patch(TASKS_PATH + ".MailEntity.objects.update_or_create_esi", spec=True)
class TestUpdateMailEntityEsi(TestCase):
    def test_normal(self, mock_update_or_create_esi):
        """When ESI status is ok, then create MailEntity"""
        mock_update_or_create_esi.return_value = None
        try:
            tasks.update_mail_entity_esi(1001)
        except Exception:
            self.fail("Unexpected exception occurred")

    def test_esi_status_1(self, mock_update_or_create_esi):
        """When ESI is offline, then abort"""
        mock_update_or_create_esi.side_effect = EsiOffline

        with self.assertRaises(EsiOffline):
            tasks.update_mail_entity_esi(1001)

    def test_esi_status_2(self, mock_update_or_create_esi):
        """When ESI error limit reached, then abort"""
        mock_update_or_create_esi.side_effect = EsiErrorLimitExceeded(5)

        with self.assertRaises(EsiErrorLimitExceeded):
            tasks.update_mail_entity_esi(1001)


@patch(MANAGERS_PATH + ".general.fetch_esi_status", lambda: EsiStatus(True, 99, 60))
@override_settings(
    CELERY_ALWAYS_EAGER=True,
    CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
    APP_UTILS_OBJECT_CACHE_DISABLED=True,
)
class TestUpdateCharactersDoctrines(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities()
        reset_celery_once_locks()

    @patch(MODELS_PATH + ".characters.Character.update_skill_sets")
    def test_normal(self, mock_update_skill_sets):
        # given
        mock_update_skill_sets.return_value = UpdateSectionResult(
            is_changed=True, is_updated=True
        )
        create_memberaudit_character(1001)

        # when
        tasks.update_characters_skill_checks()

        # then
        self.assertTrue(mock_update_skill_sets.called)


class TestDeleteCharacters(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities()
        Character.objects.all().delete()

    def test_should_delete_a_character(self):
        # given
        character_1001 = create_memberaudit_character(1001)
        character_1002 = create_memberaudit_character(1002)
        # when
        tasks.delete_objects("Character", [character_1001.pk, character_1002.pk])
        # then
        self.assertFalse(Character.objects.exists())

    def test_should_raise_error_when_model_not_found(self):
        # when/then
        with self.assertRaises(LookupError):
            tasks.delete_objects("MyUnknownMOdel", [1])


@override_settings(
    CELERY_ALWAYS_EAGER=True,
    CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
    APP_UTILS_OBJECT_CACHE_DISABLED=True,
)
class TestExportData(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities()
        cls.character = create_memberaudit_character(1001)
        reset_celery_once_locks()

    @patch(TASKS_PATH + ".data_exporters.export_topic_to_archive", spec=True)
    def test_should_export_all_topics(self, mock_export_topic_to_file):
        # when
        tasks.export_data()
        # then
        called_topics = [
            call[1]["topic"] for call in mock_export_topic_to_file.call_args_list
        ]
        self.assertEqual(len(called_topics), 3)
        self.assertSetEqual(
            set(called_topics), {"contract", "contract-item", "wallet-journal"}
        )

    @patch(TASKS_PATH + ".data_exporters.export_topic_to_archive", spec=True)
    def test_should_export_wallet_journal(self, mock_export_topic_to_file):
        # given
        user = self.character.user
        # when
        tasks.export_data_for_topic(topic="abc", user_pk=user.pk)
        # then
        self.assertTrue(mock_export_topic_to_file.called)
        _, kwargs = mock_export_topic_to_file.call_args
        self.assertEqual(kwargs["topic"], "abc")


class TestUpdateComplianceGroupDesignations(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities()

    @patch(TASKS_PATH + ".ComplianceGroupDesignation.objects.update_user", spec=True)
    def test_should_update_for_user(self, mock_update_user):
        # given
        user, _ = create_user_from_evecharacter(
            1001,
            permissions=["memberaudit.basic_access"],
            scopes=Character.get_esi_scopes(),
        )
        # when
        tasks.update_compliance_groups_for_user(user.pk)
        # then
        self.assertTrue(mock_update_user.called)


@patch(TASKS_PATH + ".update_character", spec=True)
class TestUpdateAllCharacters(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        load_locations()

    def test_should_update_all_enabled_characters(self, mock_update_character):
        # given
        character_1001 = create_memberaudit_character(1001)
        character_1002 = create_memberaudit_character(1002)
        character_1003 = create_memberaudit_character(1003)
        character_1003.is_disabled = True
        character_1003.save()
        # when
        tasks.update_all_characters()
        # then
        self.assertTrue(mock_update_character.apply_async.called)
        called_pks = {
            o[1]["kwargs"]["character_pk"]
            for o in mock_update_character.apply_async.call_args_list
        }
        self.assertSetEqual(called_pks, {character_1001.pk, character_1002.pk})

    def test_should_disable_orphaned_characters(self, mock_update_character):
        # given
        character_1001 = create_memberaudit_character(1001)
        eve_character_1002 = EveCharacter.objects.get(character_id=1002)
        character_1002 = create_character(eve_character_1002)
        # when
        tasks.update_all_characters()
        # then
        character_1001.refresh_from_db()
        self.assertFalse(character_1001.is_disabled)
        character_1002.refresh_from_db()
        self.assertTrue(character_1002.is_disabled)


@patch(TASKS_PATH + ".EveEntity.objects.update_from_esi_by_id", spec=True)
class TestUpdateUnresolvedEveEntities(TestCase):
    def test_should_not_attempt_to_update_when_no_unresolved_entities(
        self, mock_update_from_esi_by_id
    ):
        # given
        create_eve_entity(id=1, name="alpha")
        # when
        tasks.update_unresolved_eve_entities()
        # then
        self.assertFalse(mock_update_from_esi_by_id.called)

    def test_should_update_unresolved_entities(self, mock_update_from_esi_by_id):
        # given
        create_eve_entity(id=1)
        # when
        tasks.update_unresolved_eve_entities()
        # then
        self.assertTrue(mock_update_from_esi_by_id.called)
        args, _ = mock_update_from_esi_by_id.call_args
        self.assertEqual(list(args[0]), [1])


@patch(TASKS_PATH + ".check_character_consistency", spec=True)
class TestCheckCharacterConsistency(TestCase):
    def test_should_run_checks(self, mock_check_character_consistency):
        # given
        load_entities()
        character = create_memberaudit_character(1001)
        # when
        tasks.check_character_consistency(character.pk)
        # then
        self.assertTrue(mock_check_character_consistency.called)


class TestUpdateMarketPrices(TestCase):
    @patch(TASKS_PATH + ".EveMarketPrice.objects.update_from_esi", spec=True)
    def test_update_market_prices(self, mock_update_from_esi):
        tasks.update_market_prices()
        self.assertTrue(mock_update_from_esi.called)
