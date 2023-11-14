import hashlib
import json

from django.utils.timezone import now

from app_utils.testing import NoSocketsTestCase

from memberaudit.models import Character
from memberaudit.tests.testdata.factories import create_character_update_status
from memberaudit.tests.testdata.load_entities import load_entities
from memberaudit.tests.utils import create_memberaudit_character


class TestCharacterUpdateStatus(NoSocketsTestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        load_entities()
        cls.character_1001 = create_memberaudit_character(1001)
        cls.content = {"alpha": 1, "bravo": 2}

    def test_str(self):
        # given
        status = create_character_update_status(
            character=self.character_1001, section=Character.UpdateSection.ASSETS
        )
        # when/then
        self.assertEqual(str(status), f"{self.character_1001}-assets")

    def test_reset_1(self):
        # given
        status = create_character_update_status(
            character=self.character_1001,
            is_success=True,
            last_error_message="abc",
            root_task_id="a",
            parent_task_id="b",
        )
        # when
        status.reset()
        # then
        status.refresh_from_db()
        self.assertIsNone(status.is_success)
        self.assertEqual(status.last_error_message, "")
        self.assertEqual(status.root_task_id, "")
        self.assertEqual(status.parent_task_id, "")

    def test_reset_2(self):
        # given
        status = create_character_update_status(
            character=self.character_1001,
            is_success=True,
            last_error_message="abc",
            root_task_id="a",
            parent_task_id="b",
        )
        # when
        status.reset(root_task_id="1", parent_task_id="2")
        # then
        status.refresh_from_db()
        self.assertIsNone(status.is_success)
        self.assertEqual(status.last_error_message, "")
        self.assertEqual(status.root_task_id, "1")
        self.assertEqual(status.parent_task_id, "2")

    def test_has_changed_1(self):
        """When hash is different, then return True"""
        status = create_character_update_status(
            character=self.character_1001, content_hash_1="abc"
        )
        self.assertTrue(status.has_changed(self.content))

    def test_has_changed_2(self):
        """When no hash exists, then return True"""
        status = create_character_update_status(
            character=self.character_1001, content_hash_1=""
        )
        self.assertTrue(status.has_changed(self.content))

    def test_has_changed_3a(self):
        """When hash is equal, then return False"""
        status = create_character_update_status(
            character=self.character_1001,
            content_hash_1=hashlib.md5(
                json.dumps(self.content).encode("utf-8")
            ).hexdigest(),
        )
        self.assertFalse(status.has_changed(self.content))

    def test_has_changed_3b(self):
        """When hash is equal, then return False"""
        status = create_character_update_status(
            character=self.character_1001,
            content_hash_2=hashlib.md5(
                json.dumps(self.content).encode("utf-8")
            ).hexdigest(),
        )
        self.assertFalse(status.has_changed(content=self.content, hash_num=2))

    def test_has_changed_3c(self):
        """When hash is equal, then return False"""
        status = create_character_update_status(
            character=self.character_1001,
            content_hash_3=hashlib.md5(
                json.dumps(self.content).encode("utf-8")
            ).hexdigest(),
        )
        self.assertFalse(status.has_changed(content=self.content, hash_num=3))

    def test_is_updating_1(self):
        """When started_at exist and finished_at does not exist, return True"""
        status = create_character_update_status(
            character=self.character_1001, started_at=now(), finished_at=None
        )
        self.assertTrue(status.is_updating)

    def test_is_updating_2(self):
        """When started_at and finished_at does not exist, return False"""
        status = create_character_update_status(
            character=self.character_1001, started_at=None, finished_at=None
        )
        self.assertFalse(status.is_updating)
