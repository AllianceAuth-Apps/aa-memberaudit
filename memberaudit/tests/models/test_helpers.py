import json
import shutil
import tempfile
from unittest.mock import patch

from django.test import TestCase

from memberaudit.models import Character, _helpers
from memberaudit.tests.testdata.load_entities import load_entities
from memberaudit.tests.utils import create_memberaudit_character

MODULE_PATH = "memberaudit.models._helpers"


@patch(MODULE_PATH + ".settings")
class TestStoreCharacterData(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities()
        cls.character = create_memberaudit_character(1001)

    def setUp(self) -> None:
        self.root_path = tempfile.mkdtemp()

    def tearDown(self) -> None:
        shutil.rmtree(self.root_path)

    def test_should_store_when_enabled(self, mock_settings):
        # given
        mock_settings.BASE_DIR = self.root_path
        data = [{"dummy": 1}]

        # when
        with patch(MODULE_PATH + ".MEMBERAUDIT_STORE_ESI_DATA_ENABLED", True):
            result = _helpers.store_character_data_to_disk_when_enabled(
                character=self.character,
                data=data,
                section="assets",
            )

        # then
        self.assertTrue(result.exists())

        with result.open("r") as file:
            data_2 = json.load(file)

        self.assertEqual(data, data_2)

    def test_should_store_when_section_enabled(self, mock_settings):
        # given
        mock_settings.BASE_DIR = self.root_path
        data = [{"dummy": 1}]

        # when
        with patch(MODULE_PATH + ".MEMBERAUDIT_STORE_ESI_DATA_ENABLED", True), patch(
            MODULE_PATH + ".MEMBERAUDIT_STORE_ESI_DATA_SECTIONS", ["assets"]
        ):
            result = _helpers.store_character_data_to_disk_when_enabled(
                character=self.character,
                data=data,
                section="assets",
            )

        # then
        self.assertTrue(result.exists())

    def test_should_also_accept_section_obj(self, mock_settings):
        # given
        mock_settings.BASE_DIR = self.root_path
        data = [{"dummy": 1}]

        # when
        with patch(MODULE_PATH + ".MEMBERAUDIT_STORE_ESI_DATA_ENABLED", True):
            result = _helpers.store_character_data_to_disk_when_enabled(
                character=self.character,
                data=data,
                section=Character.UpdateSection.ASSETS,
            )

        # then
        self.assertTrue(result.exists())

    def test_should_not_store_when_section_not_enabled(self, mock_settings):
        # given
        mock_settings.BASE_DIR = self.root_path
        data = [{"dummy": 1}]

        # when
        with patch(MODULE_PATH + ".MEMBERAUDIT_STORE_ESI_DATA_ENABLED", True), patch(
            MODULE_PATH + ".MEMBERAUDIT_STORE_ESI_DATA_SECTIONS", ["other_section"]
        ):
            result = _helpers.store_character_data_to_disk_when_enabled(
                character=self.character,
                data=data,
                section="assets",
            )

        # then
        self.assertIsNone(result)

    def test_should_store_when_character_enabled(self, mock_settings):
        # given
        mock_settings.BASE_DIR = self.root_path
        data = [{"dummy": 1}]

        # when
        with patch(MODULE_PATH + ".MEMBERAUDIT_STORE_ESI_DATA_ENABLED", True), patch(
            MODULE_PATH + ".MEMBERAUDIT_STORE_ESI_DATA_CHARACTERS", [self.character.id]
        ):
            result = _helpers.store_character_data_to_disk_when_enabled(
                character=self.character,
                data=data,
                section="assets",
            )

        # then
        self.assertTrue(result.exists())

    def test_should_not_store_when_character_not_enabled(self, mock_settings):
        # given
        mock_settings.BASE_DIR = self.root_path
        data = [{"dummy": 1}]

        # when
        with patch(MODULE_PATH + ".MEMBERAUDIT_STORE_ESI_DATA_ENABLED", True), patch(
            MODULE_PATH + ".MEMBERAUDIT_STORE_ESI_DATA_CHARACTERS", [-1]
        ):
            result = _helpers.store_character_data_to_disk_when_enabled(
                character=self.character,
                data=data,
                section="assets",
            )

        # then
        self.assertIsNone(result)

    def test_should_allow_optional_suffix(self, mock_settings):
        # given
        mock_settings.BASE_DIR = self.root_path
        data = [{"dummy": 1}]

        # when
        with patch(MODULE_PATH + ".MEMBERAUDIT_STORE_ESI_DATA_ENABLED", True):
            result = _helpers.store_character_data_to_disk_when_enabled(
                character=self.character,
                data=data,
                section="assets",
                suffix="special",
            )

        # then
        self.assertTrue(result.exists())
        self.assertIn("special", result.name)

    def test_should_not_break_when_section_name_is_wrong(self, mock_settings):
        # given
        mock_settings.BASE_DIR = self.root_path
        data = [{"dummy": 1}]

        # when
        with patch(MODULE_PATH + ".MEMBERAUDIT_STORE_ESI_DATA_ENABLED", True):
            result = _helpers.store_character_data_to_disk_when_enabled(
                character=self.character,
                data=data,
                section="invalid",
            )

        # then
        self.assertIsNone(result)

    def test_should_not_break_when_json_serialization_fails(self, mock_settings):
        # given
        mock_settings.BASE_DIR = self.root_path
        data = [{"dummy": 1}]

        # when
        with patch(MODULE_PATH + ".MEMBERAUDIT_STORE_ESI_DATA_ENABLED", True), patch(
            MODULE_PATH + ".json.dump"
        ) as mock:
            mock.side_effect = TypeError
            result = _helpers.store_character_data_to_disk_when_enabled(
                character=self.character,
                data=data,
                section="assets",
            )

        # then
        self.assertIsNone(result)

    def test_should_not_break_when_write_failed(self, mock_settings):
        # given
        mock_settings.BASE_DIR = self.root_path
        data = [{"dummy": 1}]

        # when
        with patch(MODULE_PATH + ".MEMBERAUDIT_STORE_ESI_DATA_ENABLED", True), patch(
            MODULE_PATH + ".json.dump"
        ) as mock:
            mock.side_effect = OSError
            result = _helpers.store_character_data_to_disk_when_enabled(
                character=self.character,
                data=data,
                section="assets",
            )

        # then
        self.assertIsNone(result)
