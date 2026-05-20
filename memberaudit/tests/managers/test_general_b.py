import datetime as dt
from http import HTTPStatus
from unittest.mock import MagicMock, patch

import pook
from celery_once import AlreadyQueued

from django.test import override_settings
from django.utils.timezone import now
from esi.exceptions import HTTPClientError
from eveuniverse.tests.testdata.factories_2 import (
    CitadelTypeFactory,
    EveEntityCorporationFactory,
    EveSolarSystemFactory,
    EveTypeFactory,
    PositionFactory,
    SolarSystemTypeFactory,
)

from app_utils.testing import NoSocketsTestCase

from memberaudit.app_settings import MEMBERAUDIT_LOCATION_STALE_HOURS
from memberaudit.models import Location
from memberaudit.tests.testdata.factories_2 import (
    AssetSafetyWrapTypeFactory,
    LocationSolarSystemFactory,
    LocationStationFactory,
    LocationStructureFactory,
    TokenFactory2,
    make_esi_url,
)
from memberaudit.tests.utils import TestCaseWithClearCache

MANAGERS_PATH = "memberaudit.managers.general"
TASKS_PATH = "memberaudit.tasks"

_ESI_SCOPES = ["esi-universe.read_structures.v1"]


class TestLocationManager_GetOrCreateEsi(TestCaseWithClearCache):
    @pook.on
    def test_does_not_update_existing_location_before_stale(self):
        # given
        location = LocationStructureFactory()
        pook.get(
            make_esi_url(f"universe/structures/{location.id}"),
            reply=HTTPStatus.OK,
            response_json={
                "owner_id": location.owner.id,
                "name": "changed name",
                "position": PositionFactory(),
                "solar_system_id": location.eve_solar_system.id,
                "type_id": location.eve_type.id,
            },
        )
        token = TokenFactory2(scopes=_ESI_SCOPES)

        # when
        obj, created = Location.objects.get_or_create_esi(id=location.id, token=token)

        # then
        self.assertFalse(created)
        self.assertEqual(obj, location)

    @pook.on
    def test_should_update_existing_locations_when_stale(self):
        # given
        deadline = now() - dt.timedelta(
            hours=MEMBERAUDIT_LOCATION_STALE_HOURS, seconds=1
        )
        with patch("django.utils.timezone.now", MagicMock(return_value=deadline)):
            location = LocationStructureFactory()

        solar_system = EveSolarSystemFactory()
        name = f"{solar_system.name} - Alpha"
        owner = EveEntityCorporationFactory()
        eve_type = CitadelTypeFactory()
        pook.get(
            make_esi_url(f"universe/structures/{location.id}"),
            reply=HTTPStatus.OK,
            response_json={
                "owner_id": owner.id,
                "name": name,
                "position": PositionFactory(),
                "solar_system_id": solar_system.id,
                "type_id": eve_type.id,
            },
        )
        token = TokenFactory2(scopes=_ESI_SCOPES)

        # when
        obj: Location
        obj, created = Location.objects.get_or_create_esi(id=location.id, token=token)

        # then
        self.assertFalse(created)
        self.assertEqual(obj.id, location.id)
        self.assertEqual(obj.name, name)
        self.assertEqual(obj.eve_solar_system, solar_system)
        self.assertEqual(obj.eve_type, eve_type)
        self.assertEqual(obj.owner, owner)

    @pook.on
    def test_should_not_update_empty_locations_during_grace_period(self):
        # given
        token = TokenFactory2(scopes=_ESI_SCOPES)
        location = Location.objects.create(id=1000000000001)
        pook.get(
            make_esi_url(f"universe/structures/{location.id}"),
            reply=HTTPStatus.OK,
            response_json={
                "owner_id": EveEntityCorporationFactory().id,
                "name": "name",
                "position": PositionFactory(),
                "solar_system_id": EveSolarSystemFactory().id,
                "type_id": CitadelTypeFactory().id,
            },
        )

        # when
        obj, _ = Location.objects.get_or_create_esi(id=location.id, token=token)

        # then
        self.assertIsNone(obj.eve_solar_system)

    @pook.on
    def test_should_update_empty_locations_after_grace_period(self):
        # given
        token = TokenFactory2(scopes=_ESI_SCOPES)
        deadline = now() - dt.timedelta(minutes=6)
        with patch("django.utils.timezone.now", MagicMock(return_value=deadline)):
            location = Location.objects.create(id=1000000000001)

        solar_system = EveSolarSystemFactory()
        name = f"{solar_system.name} - Alpha"
        owner = EveEntityCorporationFactory()
        eve_type = CitadelTypeFactory()
        pook.get(
            make_esi_url(f"universe/structures/{location.id}"),
            reply=HTTPStatus.OK,
            response_json={
                "owner_id": owner.id,
                "name": name,
                "position": PositionFactory(),
                "solar_system_id": solar_system.id,
                "type_id": eve_type.id,
            },
        )

        # when
        obj: Location
        obj, created = Location.objects.get_or_create_esi(id=location.id, token=token)

        # then
        self.assertFalse(created)
        self.assertEqual(obj.id, location.id)
        self.assertEqual(obj.name, name)
        self.assertEqual(obj.eve_solar_system, solar_system)
        self.assertEqual(obj.eve_type, eve_type)
        self.assertEqual(obj.owner, owner)


class TestLocationManager_Structure_UpdateOrCreateEsi(TestCaseWithClearCache):
    @pook.on
    def test_can_create_minimal_structure(self):
        # given
        token = TokenFactory2(scopes=_ESI_SCOPES)
        solar_system = EveSolarSystemFactory()
        name = f"{solar_system.name} - Alpha"
        structure_id = 1000000000001
        owner = EveEntityCorporationFactory()
        pook.get(
            make_esi_url(f"universe/structures/{structure_id}"),
            reply=HTTPStatus.OK,
            response_json={
                "owner_id": owner.id,
                "name": name,
                "position": PositionFactory(),
                "solar_system_id": solar_system.id,
            },
        )

        # when
        obj: Location
        obj, created = Location.objects.update_or_create_esi(
            id=structure_id, token=token
        )

        # then
        self.assertTrue(created)
        self.assertEqual(obj.id, structure_id)
        self.assertEqual(obj.name, name)
        self.assertEqual(obj.eve_solar_system, solar_system)
        self.assertIsNone(obj.eve_type)
        self.assertEqual(obj.owner, owner)

    @pook.on
    def test_can_create_full_structure(self):
        # given
        token = TokenFactory2(scopes=_ESI_SCOPES)
        solar_system = EveSolarSystemFactory()
        name = f"{solar_system.name} - Alpha"
        structure_id = 1000000000001
        owner = EveEntityCorporationFactory()
        eve_type = CitadelTypeFactory()
        pook.get(
            make_esi_url(f"universe/structures/{structure_id}"),
            reply=HTTPStatus.OK,
            response_json={
                "owner_id": owner.id,
                "name": name,
                "position": PositionFactory(),
                "solar_system_id": solar_system.id,
                "type_id": eve_type.id,
            },
        )
        # when
        obj: Location
        obj, created = Location.objects.update_or_create_esi(
            id=structure_id, token=token
        )

        # then
        self.assertTrue(created)
        self.assertEqual(obj.id, structure_id)
        self.assertEqual(obj.name, name)
        self.assertEqual(obj.eve_solar_system, solar_system)
        self.assertEqual(obj.eve_type, eve_type)
        self.assertEqual(obj.owner, owner)

    @pook.on
    def test_can_update_structure(self):
        # given
        token = TokenFactory2(scopes=_ESI_SCOPES)
        location = LocationStructureFactory()
        solar_system = EveSolarSystemFactory()
        name = f"{solar_system.name} - Alpha"
        owner = EveEntityCorporationFactory()
        eve_type = CitadelTypeFactory()
        pook.get(
            make_esi_url(f"universe/structures/{location.id}"),
            reply=HTTPStatus.OK,
            response_json={
                "owner_id": owner.id,
                "name": name,
                "position": PositionFactory(),
                "solar_system_id": solar_system.id,
                "type_id": eve_type.id,
            },
        )

        # when
        obj: Location
        obj, created = Location.objects.update_or_create_esi(
            id=location.id, token=token
        )

        # then
        self.assertFalse(created)
        self.assertEqual(obj.id, location.id)
        self.assertEqual(obj.name, name)
        self.assertEqual(obj.eve_solar_system, solar_system)
        self.assertEqual(obj.eve_type, eve_type)
        self.assertEqual(obj.owner, owner)

    @pook.on
    def test_should_propagates_http_error_on_structure_create(self):
        # given
        token = TokenFactory2(scopes=_ESI_SCOPES)
        structure_id = 1000000000001
        pook.get(
            make_esi_url(f"universe/structures/{structure_id}"),
            reply=HTTPStatus.NOT_FOUND,
            response_json={"error": "not found"},
        )

        # when/Then
        with self.assertRaises(HTTPClientError):
            Location.objects.update_or_create_esi(id=structure_id, token=token)

    @pook.on
    def test_should_create_empty_location_for_invalid_id(self):
        # given
        token = TokenFactory2(scopes=_ESI_SCOPES)
        structure_id = 80000000
        pook.get(
            make_esi_url(f"universe/structures/{structure_id}"),
            reply=HTTPStatus.NOT_FOUND,
            response_json={"error": "not found"},
        )
        # when
        obj, created = Location.objects.update_or_create_esi(
            id=structure_id, token=token
        )

        # then
        self.assertTrue(created)
        self.assertTrue(obj.is_empty)

    @pook.on
    def test_should_create_empty_location_on_access_error_1(self):
        # given
        token = TokenFactory2(scopes=_ESI_SCOPES)
        structure_id = 1000000000001
        pook.get(
            make_esi_url(f"universe/structures/{structure_id}"),
            reply=HTTPStatus.UNAUTHORIZED,
            response_json={"error": "not found"},
        )

        # when
        obj, created = Location.objects.update_or_create_esi(
            id=structure_id, token=token
        )

        # then
        self.assertTrue(created)
        self.assertTrue(obj.is_empty)

    @pook.on
    def test_should_create_empty_location_on_access_error_2(self):
        # given
        token = TokenFactory2(scopes=_ESI_SCOPES)
        structure_id = 1000000000001
        pook.get(
            make_esi_url(f"universe/structures/{structure_id}"),
            reply=HTTPStatus.FORBIDDEN,
            response_json={"error": "not found"},
        )

        # when
        obj, created = Location.objects.update_or_create_esi(
            id=structure_id, token=token
        )

        # then
        self.assertTrue(created)
        self.assertTrue(obj.is_empty)

    @pook.on
    def test_should_raise_value_error_when_token_is_needed_but_not_passed(self):
        # when/then
        with self.assertRaises(ValueError):
            Location.objects.get_or_create_esi(id=1000000000099, token=None)


@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
class TestLocationManager_Structure_UpdateOrCreateEsiAsync(TestCaseWithClearCache):
    @pook.on
    def test_can_create_full_structure(self):
        # given
        token = TokenFactory2(scopes=_ESI_SCOPES)
        solar_system = EveSolarSystemFactory()
        name = f"{solar_system.name} - Alpha"
        structure_id = 1000000000001
        owner = EveEntityCorporationFactory()
        eve_type = CitadelTypeFactory()
        pook.get(
            make_esi_url(f"universe/structures/{structure_id}"),
            reply=HTTPStatus.OK,
            response_json={
                "owner_id": owner.id,
                "name": name,
                "position": PositionFactory(),
                "solar_system_id": solar_system.id,
                "type_id": eve_type.id,
            },
        )
        # when
        obj: Location
        obj, created = Location.objects.update_or_create_esi_async(
            id=structure_id, token=token
        )

        # then
        self.assertTrue(created)
        self.assertEqual(obj.id, structure_id)
        self.assertIsNone(obj.eve_solar_system)
        self.assertIsNone(obj.eve_type)
        obj.refresh_from_db()
        self.assertEqual(obj.id, structure_id)
        self.assertEqual(obj.name, name)
        self.assertEqual(obj.eve_solar_system, solar_system)
        self.assertEqual(obj.eve_type, eve_type)
        self.assertEqual(obj.owner, owner)

    @patch(TASKS_PATH + ".update_structure_esi", spec=True)
    @pook.on
    def test_should_create_location_and_ignore_already_queued_(
        self, mock_task_update_structure_esi
    ):
        # given
        mock_task_update_structure_esi.apply_async.side_effect = AlreadyQueued(10)
        token = TokenFactory2(scopes=_ESI_SCOPES)

        # when
        obj: Location
        obj, created = Location.objects.update_or_create_esi_async(
            id=1000000000001, token=token
        )

        # then
        self.assertTrue(created)
        self.assertEqual(obj.id, 1000000000001)
        self.assertIsNone(obj.eve_solar_system)
        self.assertIsNone(obj.eve_type)
        self.assertTrue(mock_task_update_structure_esi.apply_async.called)


class TestLocationManager_Station_UpdateOrCreateEsi(TestCaseWithClearCache):
    @pook.on
    def test_can_create_station(self):
        # given
        location_id = 60015068
        eve_type = EveTypeFactory()
        solar_system = EveSolarSystemFactory()
        owner = EveEntityCorporationFactory()
        name = f"{solar_system.name} - State Protectorate Assembly Plant"
        pook.get(
            make_esi_url(f"universe/stations/{location_id}"),
            reply=200,
            response_json={
                "max_dockable_ship_volume": 50000000,
                "name": name,
                "office_rental_cost": 118744,
                "owner": owner.id,
                "position": PositionFactory(),
                "race_id": 1,
                "reprocessing_efficiency": 0.2,
                "reprocessing_stations_take": 0.025,
                "services": [
                    "bounty-missions",
                    "courier-missions",
                    "reprocessing-plant",
                    "market",
                    "repair-facilities",
                    "factory",
                    "fitting",
                    "news",
                    "insurance",
                    "docking",
                    "office-rental",
                    "loyalty-point-store",
                    "navy-offices",
                    "security-offices",
                ],
                "station_id": location_id,
                "system_id": solar_system.id,
                "type_id": eve_type.id,
            },
        )

        # when
        obj: Location
        obj, created = Location.objects.update_or_create_esi(id=location_id, token=None)

        # then
        self.assertTrue(created)
        self.assertEqual(obj.id, location_id)
        self.assertEqual(obj.name, name)
        self.assertEqual(obj.eve_solar_system, solar_system)
        self.assertEqual(obj.eve_type, eve_type)
        self.assertEqual(obj.owner, owner)

    @pook.on
    def test_can_update_station(self):
        # given
        location = LocationStationFactory()
        eve_type = EveTypeFactory()
        solar_system = EveSolarSystemFactory()
        owner = EveEntityCorporationFactory()
        name = f"{solar_system.name} - State Protectorate Assembly Plant"
        pook.get(
            make_esi_url(f"universe/stations/{location.id}"),
            reply=200,
            response_json={
                "max_dockable_ship_volume": 50000000,
                "name": name,
                "office_rental_cost": 118744,
                "owner": owner.id,
                "position": PositionFactory(),
                "race_id": 1,
                "reprocessing_efficiency": 0.2,
                "reprocessing_stations_take": 0.025,
                "services": [
                    "bounty-missions",
                    "courier-missions",
                    "reprocessing-plant",
                    "market",
                    "repair-facilities",
                    "factory",
                    "fitting",
                    "news",
                    "insurance",
                    "docking",
                    "office-rental",
                    "loyalty-point-store",
                    "navy-offices",
                    "security-offices",
                ],
                "station_id": location.id,
                "system_id": solar_system.id,
                "type_id": eve_type.id,
            },
        )

        # when
        obj: Location
        obj, created = Location.objects.update_or_create_esi(id=location.id, token=None)

        # then
        self.assertFalse(created)
        self.assertEqual(obj.id, location.id)
        self.assertEqual(obj.name, name)
        self.assertEqual(obj.eve_solar_system, solar_system)
        self.assertEqual(obj.eve_type, eve_type)
        self.assertEqual(obj.owner, owner)

    @pook.on
    def test_should_propagates_http_error_on_create(self):
        # given
        location_id = 63999999
        pook.get(
            make_esi_url(f"universe/stations/{location_id}"),
            reply=HTTPStatus.NOT_FOUND,
            response_json={"error": "not found"},
        )

        # when/Then
        with self.assertRaises(HTTPClientError):
            Location.objects.update_or_create_esi(id=location_id, token=None)


class TestLocationManager_SolarSystem_UpdateOrCreateEsi(NoSocketsTestCase):
    def test_can_create_solar_system(self):
        # given
        location_id = 30045339
        eve_type = SolarSystemTypeFactory()
        solar_system = EveSolarSystemFactory(id=location_id)

        # when
        obj: Location
        obj, created = Location.objects.update_or_create_esi(id=location_id, token=None)

        # then
        self.assertTrue(created)
        self.assertEqual(obj.id, location_id)
        self.assertEqual(obj.name, solar_system.name)
        self.assertEqual(obj.eve_solar_system, solar_system)
        self.assertEqual(obj.eve_type, eve_type)
        self.assertIsNone(obj.owner)


class TestLocationManager_AssetSafety_UpdateOrCreateEsi(NoSocketsTestCase):
    def test_can_create_asset_safety(self):
        # given
        eve_type = AssetSafetyWrapTypeFactory()

        # when
        obj: Location
        obj, created = Location.objects.update_or_create_esi(id=2004, token=None)

        # then
        self.assertTrue(created)
        self.assertEqual(obj.id, 2004)
        self.assertEqual(obj.name, "ASSET SAFETY")
        self.assertIsNone(obj.eve_solar_system)
        self.assertIsNone(obj.owner)
        self.assertEqual(obj.eve_type, eve_type)


class TestLocationManager_UnknownLocation(NoSocketsTestCase):
    def test_can_create_unknown_location(self):
        # given
        location_id = Location.LOCATION_UNKNOWN_ID
        eve_type = SolarSystemTypeFactory()

        # when
        obj: Location
        obj, created = Location.objects.update_or_create_esi(id=location_id, token=None)

        # then
        self.assertTrue(created)
        self.assertEqual(obj.id, location_id)
        self.assertEqual(obj.name, "Location unknown")
        self.assertIsNone(obj.eve_solar_system)
        self.assertIsNone(obj.owner)
        self.assertEqual(obj.eve_type, eve_type)

    def test_should_create_unknown_location_object_when_it_does_not_exist(self):
        # given
        SolarSystemTypeFactory()

        # when
        obj, created = Location.objects.get_or_create_unknown_location()

        # then
        self.assertTrue(created)
        self.assertTrue(obj.is_unknown_location)

    def test_should_return_existing_unknown_location_object(self):
        # given
        SolarSystemTypeFactory()
        Location.objects.get_or_create_unknown_location()

        # when
        obj, created = Location.objects.get_or_create_unknown_location()

        # then
        self.assertFalse(created)
        self.assertTrue(obj.is_unknown_location)


class TestLocationManager_GetOrCreateFromEveSolarSystem(NoSocketsTestCase):
    def test_should_create_obj_from_solar_system(self):
        # given
        solar_system = EveSolarSystemFactory()
        eve_type = SolarSystemTypeFactory()

        # when
        obj, created = Location.objects.get_or_create_from_eve_solar_system(
            solar_system
        )

        # then
        self.assertTrue(created)
        self.assertEqual(obj.id, solar_system.id)
        self.assertEqual(obj.name, solar_system.name)
        self.assertEqual(obj.eve_solar_system, solar_system)
        self.assertEqual(obj.eve_type, eve_type)

    def test_should_get_existing_obj_from_solar_system(self):
        # given
        location = LocationSolarSystemFactory()

        # when
        obj: Location
        obj, created = Location.objects.get_or_create_from_eve_solar_system(
            location.eve_solar_system
        )
        # then
        self.assertFalse(created)
        self.assertEqual(obj, location)


@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
class TestLocationManager_CreateMissingEsi(NoSocketsTestCase):
    def test_can_preload_missing_locations(self):
        # given
        existing_id = 60003760
        unknown_id = 30002537
        LocationStationFactory(id=existing_id)
        EveSolarSystemFactory(id=unknown_id)
        SolarSystemTypeFactory()

        # when
        got = Location.objects.create_missing_esi(
            location_ids=[existing_id, unknown_id], token=None
        )

        # then
        self.assertSetEqual(got, {existing_id, unknown_id})
        self.assertTrue(Location.objects.filter(id=unknown_id).exists())

    def test_should_do_nothing_when_locations_exist(self):
        # given
        location = LocationStationFactory()

        # when
        got = Location.objects.create_missing_esi(
            location_ids=[location.id], token=None
        )

        # then
        self.assertSetEqual(got, {location.id})

    def test_should_do_nothing_when_no_ids_provided(self):
        # when
        got = Location.objects.create_missing_esi(location_ids=[], token=None)

        # then
        self.assertSetEqual(got, set())
