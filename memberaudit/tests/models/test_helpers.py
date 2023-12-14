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

    def test_should_store_given_data(self, mock_settings):
        # given
        mock_settings.BASE_DIR = self.root_path
        data = [{"dummy": 1}]

        # when
        path = _helpers.store_character_data_to_disk(
            character=self.character, data=data, section=Character.UpdateSection.ASSETS
        )

        # then
        self.assertTrue(path.exists())

        with path.open("r") as file:
            data_2 = json.load(file)

        self.assertEqual(data, data_2)

    # def test_should_store_when_enabled(self):
    #     ...

    # def test_should_not_store_when_disabled(self,mock_settings):
    #     # given
    #     mock_settings.BASE_DIR = self.root_path

    # def test_should_store_selected_sections_only(self):
    #     ...

    # def test_should_store_selected_characters_only(self):
    #     ...
