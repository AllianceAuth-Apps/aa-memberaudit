from io import StringIO
from unittest.mock import patch

from django.core.management import call_command

from app_utils.testing import TestCase

from memberaudit.tests.testdata.factories import create_character_update_status
from memberaudit.tests.testdata.load_entities import load_entities
from memberaudit.tests.utils import create_memberaudit_character

MODULE_PATH = "memberaudit.management.commands.memberaudit_stats"


@patch(MODULE_PATH + ".get_input")
class TestStats(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities()

    def test_command_should_work_1(self, mock_get_input):
        # given
        out = StringIO()
        character_1001 = create_memberaudit_character(1001)
        character_1002 = create_memberaudit_character(1002)
        create_character_update_status(character_1001)
        create_character_update_status(character_1002)

        cases = ["1", "2", "3", "4"]
        for case in cases:
            mock_get_input.return_value = case

            # when/then
            with self.subTest(input=case):
                call_command("memberaudit_stats", stdout=out)
