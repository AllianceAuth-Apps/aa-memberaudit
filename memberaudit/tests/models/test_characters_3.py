import hashlib
import json

from django.utils.timezone import now
from eveuniverse.tests.testdata.factories_2 import (
    EveSolarSystemFactory,
    SolarSystemTypeFactory,
)

from app_utils.testing import NoSocketsTestCase

from memberaudit.models import Character
from memberaudit.tests.testdata.factories_2 import (
    CharacterFactory,
    CharacterLocationFactory,
    CharacterUpdateStatusFactory,
    LocationStationFactory,
)


class TestCharacterUpdateStatus(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.character = CharacterFactory()
        cls.content = {"alpha": 1, "bravo": 2}

    def test_str(self):
        # given
        status = CharacterUpdateStatusFactory(
            character=self.character, section=Character.UpdateSection.ASSETS
        )
        # when/then
        self.assertEqual(str(status), f"{self.character}-assets")

    def test_reset_1(self):
        # given
        status = CharacterUpdateStatusFactory(
            character=self.character, is_success=True, error_message="abc"
        )
        # when
        status.reset()
        # then
        status.refresh_from_db()
        self.assertIsNone(status.is_success)
        self.assertEqual(status.error_message, "")

    def test_reset_2(self):
        # given
        status = CharacterUpdateStatusFactory(
            character=self.character, is_success=True, error_message="abc"
        )
        # when
        status.reset()
        # then
        status.refresh_from_db()
        self.assertIsNone(status.is_success)
        self.assertEqual(status.error_message, "")

    def test_has_changed_1(self):
        """When hash is different, then return True"""
        status = CharacterUpdateStatusFactory(
            character=self.character, content_hash_1="abc"
        )
        self.assertTrue(status.has_changed(self.content))

    def test_has_changed_2(self):
        """When no hash exists, then return True"""
        status = CharacterUpdateStatusFactory(
            character=self.character, content_hash_1=""
        )
        self.assertTrue(status.has_changed(self.content))

    def test_has_changed_3a(self):
        """When hash is equal, then return False"""
        status = CharacterUpdateStatusFactory(
            character=self.character,
            content_hash_1=hashlib.md5(
                json.dumps(self.content).encode("utf-8")
            ).hexdigest(),
        )
        self.assertFalse(status.has_changed(self.content))

    def test_has_changed_3b(self):
        """When hash is equal, then return False"""
        status = CharacterUpdateStatusFactory(
            character=self.character,
            content_hash_2=hashlib.md5(
                json.dumps(self.content).encode("utf-8")
            ).hexdigest(),
        )
        self.assertFalse(status.has_changed(content=self.content, hash_num=2))

    def test_has_changed_3c(self):
        """When hash is equal, then return False"""
        status = CharacterUpdateStatusFactory(
            character=self.character,
            content_hash_3=hashlib.md5(
                json.dumps(self.content).encode("utf-8")
            ).hexdigest(),
        )
        self.assertFalse(status.has_changed(content=self.content, hash_num=3))

    def test_is_updating_1(self):
        """When run_started_at exist and run_finished_at does not exist, return True"""
        status = CharacterUpdateStatusFactory(
            character=self.character, run_started_at=now(), run_finished_at=None
        )
        self.assertTrue(status.is_updating)

    def test_is_updating_2(self):
        """When run_started_at and run_finished_at does not exist, return False"""
        status = CharacterUpdateStatusFactory(
            character=self.character, run_started_at=None, run_finished_at=None
        )
        self.assertFalse(status.is_updating)


class TestCharacterLocation(NoSocketsTestCase):
    def test_should_return_location_when_it_exists(self):
        # given
        location = LocationStationFactory()
        obj = CharacterLocationFactory(location=location)
        # when
        result = obj.location_safe()
        # then
        self.assertEqual(result, location)

    def test_should_return_return_solar_system_when_location_does_not_exist(self):
        # given
        SolarSystemTypeFactory()
        eve_solar_system = EveSolarSystemFactory()
        obj = CharacterLocationFactory(eve_solar_system=eve_solar_system, location=None)
        # when
        result = obj.location_safe()
        # then
        self.assertEqual(result.id, eve_solar_system.id)
        self.assertTrue(result.is_solar_system)
