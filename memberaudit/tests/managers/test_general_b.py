import datetime as dt
from unittest.mock import MagicMock, patch

from bravado.exception import HTTPForbidden, HTTPNotFound, HTTPUnauthorized
from celery_once import AlreadyQueued

from django.test import TestCase, override_settings
from django.utils.timezone import now
from esi.models import Token
from eveuniverse.models import EveEntity, EveSolarSystem, EveType

from app_utils.esi_testing import BravadoOperationStub, BravadoResponseStub
from app_utils.testing import NoSocketsTestCase

from memberaudit.models import Location, MailEntity
from memberaudit.tests.testdata.constants import EveTypeId
from memberaudit.tests.testdata.esi_client_stub import esi_client_stub
from memberaudit.tests.testdata.factories import create_location, create_mail_entity
from memberaudit.tests.testdata.load_entities import load_entities
from memberaudit.tests.testdata.load_eveuniverse import load_eveuniverse
from memberaudit.tests.utils import create_memberaudit_character, extract

MANAGERS_PATH = "memberaudit.managers.general"
TASKS_PATH = "memberaudit.tasks"


@patch(MANAGERS_PATH + ".esi")
@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
class TestLocationManager(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        cls.jita = EveSolarSystem.objects.get(id=30000142)
        cls.amamake = EveSolarSystem.objects.get(id=30002537)
        cls.astrahus = EveType.objects.get(id=35832)
        cls.athanor = EveType.objects.get(id=35835)
        cls.jita_trade_hub = EveType.objects.get(id=52678)
        cls.corporation_2001 = EveEntity.objects.get(id=2001)
        cls.corporation_2002 = EveEntity.objects.get(id=2002)
        cls.character = create_memberaudit_character(1001)
        cls.token = (
            cls.character.eve_character.character_ownership.user.token_set.first()
        )

    def test_can_create_structure(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub

        # when
        obj, created = Location.objects.update_or_create_esi(
            id=1000000000001, token=self.token
        )

        # then
        self.assertTrue(created)
        self.assertEqual(obj.id, 1000000000001)
        self.assertEqual(obj.name, "Amamake - Test Structure Alpha")
        self.assertEqual(obj.eve_solar_system, self.amamake)
        self.assertEqual(obj.eve_type, self.astrahus)
        self.assertEqual(obj.owner, self.corporation_2001)

    def test_can_handle_incomplete_data_from_esi(self, mock_esi):
        # given
        mock_esi.client.Universe.get_universe_structures_structure_id.return_value = (
            BravadoOperationStub(
                {
                    "owner_id": None,
                    "name": "Incomplete data",
                    "solar_system_id": 30002537,
                }
            )
        )

        # when
        obj, created = Location.objects.update_or_create_esi(
            id=1000000000666, token=self.token
        )

        # then
        self.assertTrue(created)
        self.assertEqual(obj.id, 1000000000666)
        self.assertEqual(obj.name, "Incomplete data")
        self.assertEqual(obj.eve_solar_system, self.amamake)
        self.assertIsNone(obj.eve_type)
        self.assertIsNone(obj.owner)

    def test_can_update_structure(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub

        # when
        obj, _ = Location.objects.update_or_create_esi(
            id=1000000000001, token=self.token
        )

        # then
        obj.name = "Not my structure"
        obj.eve_solar_system = self.jita
        obj.eve_type = self.jita_trade_hub
        obj.owner = self.corporation_2002
        obj.save()
        obj, created = Location.objects.update_or_create_esi(
            id=1000000000001, token=self.token
        )
        self.assertFalse(created)
        self.assertEqual(obj.id, 1000000000001)
        self.assertEqual(obj.name, "Amamake - Test Structure Alpha")
        self.assertEqual(obj.eve_solar_system, self.amamake)
        self.assertEqual(obj.eve_type, self.astrahus)
        self.assertEqual(obj.owner, self.corporation_2001)

    def test_does_not_update_existing_location_during_grace_period(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        obj_existing = Location.objects.create(
            id=1000000000001,
            name="Existing Structure",
            eve_solar_system=self.jita,
            eve_type=self.jita_trade_hub,
            owner=self.corporation_2002,
        )

        # when
        obj, created = Location.objects.get_or_create_esi(
            id=1000000000001, token=self.token
        )
        # then
        self.assertFalse(created)
        self.assertEqual(obj, obj_existing)

    def test_always_update_existing_empty_locations_after_grace_period_1(
        self, mock_esi
    ):
        # given
        mock_esi.client = esi_client_stub
        Location.objects.create(id=1000000000001)

        # when
        obj, _ = Location.objects.get_or_create_esi(id=1000000000001, token=self.token)

        # then
        self.assertIsNone(obj.eve_solar_system)

    def test_always_update_existing_empty_locations_after_grace_period_2(
        self, mock_esi
    ):
        # given
        mock_esi.client = esi_client_stub
        mocked_update_at = now() - dt.timedelta(minutes=6)

        # when
        with patch(
            "django.utils.timezone.now", MagicMock(return_value=mocked_update_at)
        ):
            Location.objects.create(id=1000000000001)
            obj, _ = Location.objects.get_or_create_esi(
                id=1000000000001, token=self.token
            )

        # then
        self.assertEqual(obj.eve_solar_system, self.amamake)

    @patch(MANAGERS_PATH + ".MEMBERAUDIT_LOCATION_STALE_HOURS", 24)
    def test_always_update_existing_locations_which_are_stale(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        mocked_update_at = now() - dt.timedelta(hours=25)
        with patch(
            "django.utils.timezone.now", MagicMock(return_value=mocked_update_at)
        ):
            Location.objects.create(
                id=1000000000001,
                name="Existing Structure",
                eve_solar_system=self.jita,
                eve_type=self.jita_trade_hub,
                owner=self.corporation_2002,
            )

        # when
        obj, created = Location.objects.get_or_create_esi(
            id=1000000000001, token=self.token
        )

        # then
        self.assertFalse(created)
        self.assertEqual(obj.eve_solar_system, self.amamake)

    def test_propagates_http_error_on_structure_create(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub

        # when/Then
        with self.assertRaises(HTTPNotFound):
            Location.objects.update_or_create_esi(id=1000000000099, token=self.token)

    def test_always_creates_empty_location_for_invalid_ids(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub

        # when
        obj, created = Location.objects.update_or_create_esi(
            id=80000000, token=self.token
        )

        # then
        self.assertTrue(created)
        self.assertTrue(obj.is_empty)

    def test_propagates_exceptions_on_structure_create(self, mock_esi):
        mock_esi.client.Universe.get_universe_structures_structure_id.side_effect = (
            RuntimeError
        )

        with self.assertRaises(RuntimeError):
            Location.objects.update_or_create_esi(id=1000000000099, token=self.token)

    def test_can_create_empty_location_on_access_error_1(self, mock_esi):
        mock_esi.client.Universe.get_universe_structures_structure_id.side_effect = (
            HTTPForbidden(response=BravadoResponseStub(403, "Test exception"))
        )

        obj, created = Location.objects.update_or_create_esi(
            id=1000000000099, token=self.token
        )
        self.assertTrue(created)
        self.assertEqual(obj.id, 1000000000099)

    def test_can_create_empty_location_on_access_error_2(self, mock_esi):
        mock_esi.client.Universe.get_universe_structures_structure_id.side_effect = (
            HTTPUnauthorized(response=BravadoResponseStub(401, "Test exception"))
        )

        obj, created = Location.objects.update_or_create_esi(
            id=1000000000099, token=self.token
        )
        self.assertTrue(created)
        self.assertEqual(obj.id, 1000000000099)

    def test_does_not_creates_empty_location_on_access_errors_if_requested(
        self, mock_esi
    ):
        mock_esi.client.Universe.get_universe_structures_structure_id.side_effect = (
            RuntimeError
        )
        with self.assertRaises(RuntimeError):
            Location.objects.update_or_create_esi(id=1000000000099, token=self.token)

    def test_records_esi_error_on_access_error(self, mock_esi):
        mock_esi.client.Universe.get_universe_structures_structure_id.side_effect = (
            HTTPForbidden(
                response=BravadoResponseStub(
                    403,
                    "Test exception",
                    headers={
                        "X-Esi-Error-Limit-Remain": "40",
                        "X-Esi-Error-Limit-Reset": "30",
                    },
                )
            )
        )

        _, created = Location.objects.update_or_create_esi(
            id=1000000000099, token=self.token
        )
        self.assertTrue(created)

    def test_should_raise_value_error_when_token_is_needed_but_not_passed(
        self, mock_esi
    ):
        # given
        mock_esi.client = esi_client_stub

        # when/then
        with self.assertRaises(ValueError):
            Location.objects.get_or_create_esi(id=1000000000099, token=None)

    # stations

    def test_can_create_station(self, mock_esi):
        mock_esi.client = esi_client_stub

        obj, created = Location.objects.update_or_create_esi(
            id=60003760, token=self.token
        )
        self.assertTrue(created)
        self.assertEqual(obj.id, 60003760)
        self.assertEqual(obj.name, "Jita IV - Moon 4 - Caldari Navy Assembly Plant")
        self.assertEqual(obj.eve_solar_system, self.jita)
        self.assertEqual(obj.eve_type, self.jita_trade_hub)
        self.assertEqual(obj.owner, self.corporation_2002)

    def test_can_update_station(self, mock_esi):
        mock_esi.client = esi_client_stub

        obj, created = Location.objects.update_or_create_esi(
            id=60003760, token=self.token
        )
        obj.name = "Not my station"
        obj.eve_solar_system = self.amamake
        obj.eve_type = self.astrahus
        obj.owner = self.corporation_2001
        obj.save()

        obj, created = Location.objects.update_or_create_esi(
            id=60003760, token=self.token
        )
        self.assertFalse(created)
        self.assertEqual(obj.id, 60003760)
        self.assertEqual(obj.name, "Jita IV - Moon 4 - Caldari Navy Assembly Plant")
        self.assertEqual(obj.eve_solar_system, self.jita)
        self.assertEqual(obj.eve_type, self.jita_trade_hub)
        self.assertEqual(obj.owner, self.corporation_2002)

    def test_propagates_http_error_on_station_create(self, mock_esi):
        mock_esi.client = esi_client_stub

        with self.assertRaises(HTTPNotFound):
            Location.objects.update_or_create_esi(id=63999999, token=self.token)

    # Solar System

    def test_can_create_solar_system(self, mock_esi):
        mock_esi.client = esi_client_stub

        obj, created = Location.objects.update_or_create_esi(
            id=30002537, token=self.token
        )
        self.assertTrue(created)
        self.assertEqual(obj.id, 30002537)
        self.assertEqual(obj.name, "Amamake")
        self.assertEqual(obj.eve_solar_system, self.amamake)
        self.assertEqual(obj.eve_type, EveType.objects.get(id=EveTypeId.SOLAR_SYSTEM))
        self.assertIsNone(obj.owner)

    # Asset Safety

    def test_can_create_asset_safety(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        # when
        obj, created = Location.objects.update_or_create_esi(id=2004, token=self.token)
        # then
        self.assertTrue(created)
        self.assertEqual(obj.id, 2004)
        self.assertEqual(obj.name, "ASSET SAFETY")
        self.assertIsNone(obj.eve_solar_system)
        self.assertIsNone(obj.owner)
        self.assertEqual(
            obj.eve_type, EveType.objects.get(id=EveTypeId.ASSET_SAFETY_WRAP)
        )

    # Unknown location placeholder

    def test_can_create_unknown_location(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        # when
        obj, created = Location.objects.update_or_create_esi(id=888, token=self.token)
        # then
        self.assertTrue(created)
        self.assertEqual(obj.id, 888)
        self.assertEqual(obj.name, "Location unknown")
        self.assertIsNone(obj.eve_solar_system)
        self.assertIsNone(obj.owner)
        self.assertEqual(obj.eve_type_id, EveTypeId.SOLAR_SYSTEM)

    def test_should_create_obj_from_solar_system(self, mock_esi):
        # when
        obj, created = Location.objects.get_or_create_from_eve_solar_system(self.jita)
        # then
        self.assertTrue(created)
        self.assertEqual(obj.id, self.jita.id)
        self.assertEqual(obj.name, self.jita.name)
        self.assertEqual(obj.eve_solar_system, self.jita)
        self.assertEqual(obj.eve_type_id, EveTypeId.SOLAR_SYSTEM)

    def test_should_get_existing_obj_from_solar_system(self, mock_esi):
        # given
        create_location(
            id=self.jita.id,
            eve_solar_system=self.jita,
            name=self.jita.name,
            eve_type_id=EveTypeId.SOLAR_SYSTEM,
        )
        # when
        obj, created = Location.objects.get_or_create_from_eve_solar_system(self.jita)
        # then
        self.assertFalse(created)
        self.assertEqual(obj.id, self.jita.id)
        self.assertEqual(obj.name, self.jita.name)
        self.assertEqual(obj.eve_solar_system, self.jita)
        self.assertEqual(obj.eve_type_id, EveTypeId.SOLAR_SYSTEM)

    def test_should_create_unknown_location_object_when_it_does_not_exist(
        self, mock_esi
    ):
        # when
        obj, created = Location.objects.get_or_create_unknown_location()
        # then
        self.assertTrue(created)
        self.assertTrue(obj.is_unknown_location)

    def test_should_return_existing_unknown_location_object(self, mock_esi):
        # given
        Location.objects.get_or_create_unknown_location()
        # when
        obj, created = Location.objects.get_or_create_unknown_location()
        # then
        self.assertFalse(created)
        self.assertTrue(obj.is_unknown_location)


@patch(MANAGERS_PATH + ".esi")
@patch(MANAGERS_PATH + ".LocationManager.get_or_create_esi_async")
class TestLocationManagerPreload(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        cls.token = MagicMock(spec=Token)

    def test_can_preload_missing_locations(
        self, mock_get_or_create_esi_async, mock_esi
    ):
        # given
        mock_esi.client = esi_client_stub
        Location.objects.update_or_create_esi(id=60003760, token=self.token)
        # when
        result = Location.objects.create_missing_esi([60003760, 30002537], self.token)
        # then
        self.assertEqual(mock_get_or_create_esi_async.call_count, 1)
        _, kwargs = mock_get_or_create_esi_async.call_args
        self.assertEqual(kwargs["id"], 30002537)
        self.assertSetEqual(result, {60003760, 30002537})

    def test_can_do_nothing_when_all_locations_found(
        self, mock_get_or_create_esi_async, mock_esi
    ):
        # given
        mock_esi.client = esi_client_stub
        Location.objects.update_or_create_esi(id=60003760, token=self.token)
        Location.objects.update_or_create_esi(id=30002537, token=self.token)
        # when
        result = Location.objects.create_missing_esi([60003760, 30002537], self.token)
        # then
        self.assertEqual(mock_get_or_create_esi_async.call_count, 0)
        self.assertSetEqual(result, {60003760, 30002537})

    def test_can_do_nothing_when_no_ids_provided(
        self, mock_get_or_create_esi_async, mock_esi
    ):
        # given
        mock_esi.client = esi_client_stub
        # when
        result = Location.objects.create_missing_esi([], self.token)
        # then
        self.assertEqual(mock_get_or_create_esi_async.call_count, 0)
        self.assertSetEqual(result, set())


@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
class TestLocationManagerAsync(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        cls.jita = EveSolarSystem.objects.get(id=30000142)
        cls.amamake = EveSolarSystem.objects.get(id=30002537)
        cls.astrahus = EveType.objects.get(id=35832)
        cls.athanor = EveType.objects.get(id=35835)
        cls.jita_trade_hub = EveType.objects.get(id=52678)
        cls.corporation_2001 = EveEntity.objects.get(id=2001)
        cls.corporation_2002 = EveEntity.objects.get(id=2002)
        cls.character = create_memberaudit_character(1001)
        cls.token = (
            cls.character.eve_character.character_ownership.user.token_set.first()
        )

    @patch(MANAGERS_PATH + ".esi")
    def test_can_create_structure_async(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        # when
        obj, created = Location.objects.update_or_create_esi_async(
            id=1000000000001, token=self.token
        )
        # then
        self.assertTrue(created)
        self.assertEqual(obj.id, 1000000000001)
        self.assertIsNone(obj.eve_solar_system)
        self.assertIsNone(obj.eve_type)
        obj.refresh_from_db()
        self.assertEqual(obj.name, "Amamake - Test Structure Alpha")
        self.assertEqual(obj.eve_solar_system, self.amamake)
        self.assertEqual(obj.eve_type, self.astrahus)
        self.assertEqual(obj.owner, self.corporation_2001)

    @patch(TASKS_PATH + ".update_structure_esi", spec=True)
    def test_should_create_location_and_ignore_already_queued(
        self, mock_task_update_structure_esi
    ):
        # given
        mock_task_update_structure_esi.apply_async.side_effect = AlreadyQueued(10)
        # when
        obj, created = Location.objects.update_or_create_esi_async(
            id=1000000000001, token=self.token
        )
        # then
        self.assertTrue(created)
        self.assertEqual(obj.id, 1000000000001)
        self.assertIsNone(obj.eve_solar_system)
        self.assertIsNone(obj.eve_type)
        self.assertTrue(mock_task_update_structure_esi.apply_async.called)


@patch(MANAGERS_PATH + ".esi")
class TestCharacterMailingLists(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities()
        cls.character = create_memberaudit_character(1001)

    def test_update_mailing_lists_1(self, mock_esi):
        """can create new mailing lists from scratch"""
        mock_esi.client = esi_client_stub

        self.character.update_mailing_lists()

        self.assertSetEqual(extract(MailEntity.objects, "id"), {9001, 9002})
        self.assertSetEqual(
            extract(self.character.mailing_lists, "id"),
            {9001, 9002},
        )

        obj = MailEntity.objects.get(id=9001)
        self.assertEqual(obj.name, "Dummy 1")

        obj = MailEntity.objects.get(id=9002)
        self.assertEqual(obj.name, "Dummy 2")

    def test_update_mailing_lists_2(self, mock_esi):
        """does not remove obsolete mailing lists"""
        mock_esi.client = esi_client_stub
        create_mail_entity(
            id=5, category=MailEntity.Category.MAILING_LIST, name="Obsolete"
        )

        self.character.update_mailing_lists()

        self.assertSetEqual(extract(MailEntity.objects, "id"), {9001, 9002, 5})
        self.assertSetEqual(
            extract(self.character.mailing_lists, "id"),
            {9001, 9002},
        )

    def test_update_mailing_lists_3(self, mock_esi):
        """updates existing mailing lists"""
        mock_esi.client = esi_client_stub
        create_mail_entity(
            id=9001, category=MailEntity.Category.MAILING_LIST, name="Update me"
        )

        self.character.update_mailing_lists()

        self.assertSetEqual(extract(MailEntity.objects, "id"), {9001, 9002})
        self.assertSetEqual(
            extract(self.character.mailing_lists, "id"),
            {9001, 9002},
        )
        obj = MailEntity.objects.get(id=9001)
        self.assertEqual(obj.name, "Dummy 1")

    def test_update_mailing_lists_4(self, mock_esi):
        """when data from ESI has not changed, then skip update"""
        mock_esi.client = esi_client_stub

        self.character.update_mailing_lists()
        obj = MailEntity.objects.get(id=9001)
        obj.name = "Extravaganza"
        obj.save()
        self.character.mailing_lists.clear()

        self.character.update_mailing_lists()
        obj = MailEntity.objects.get(id=9001)
        self.assertEqual(obj.name, "Extravaganza")
        self.assertSetEqual(extract(self.character.mailing_lists, "id"), set())

    def test_update_mailing_lists_5(self, mock_esi):
        """when data from ESI has not changed and update is forced, then do update"""
        mock_esi.client = esi_client_stub

        self.character.update_mailing_lists()
        obj = MailEntity.objects.get(id=9001)
        obj.name = "Extravaganza"
        obj.save()

        self.character.update_mailing_lists(force_update=True)
        obj = MailEntity.objects.get(id=9001)
        self.assertEqual(obj.name, "Dummy 1")
