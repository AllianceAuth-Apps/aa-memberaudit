from io import StringIO
from unittest.mock import patch

from django.core.management import call_command

from app_utils.testing import NoSocketsTestCase

from memberaudit.tests.testdata.load_entities import load_entities
from memberaudit.tests.utils import create_memberaudit_character

MODULE_PATH = "memberaudit.management.commands.memberaudit_update_characters"


@patch(MODULE_PATH + ".tasks")
class TestUpdateCharacters(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities()

    def test_should_reset_section_data_for_characters(self, mock_tasks):
        # given
        create_memberaudit_character(1001)
        out = StringIO()

        # when
        call_command("memberaudit_update_characters", "--noinput", "assets", stdout=out)

        # then
        self.assertTrue(mock_tasks.update_character_assets.apply_async.called)
