from io import StringIO
from unittest.mock import patch

from django.core.management import call_command

from app_utils.testing import NoSocketsTestCase

from memberaudit.tests.testdata.factories_2 import CharacterFactory

MODULE_PATH = "memberaudit.management.commands.memberaudit_update_characters"


@patch(MODULE_PATH + ".tasks")
class TestUpdateCharacters(NoSocketsTestCase):
    def test_should_reset_section_data_for_characters(self, mock_tasks):
        # given
        CharacterFactory()
        out = StringIO()

        # when
        call_command("memberaudit_update_characters", "--noinput", "assets", stdout=out)

        # then
        self.assertTrue(mock_tasks.update_character_assets.apply_async.called)
