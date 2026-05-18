from io import StringIO
from unittest.mock import patch

from django.core.management import call_command

from app_utils.testing import NoSocketsTestCase

from memberaudit.tests.testdata.factories_2 import (
    CharacterFactory,
    CharacterUpdateStatusFactory,
)

MODULE_PATH = "memberaudit.management.commands.memberaudit_stats"


@patch(MODULE_PATH + ".get_input")
class TestStats(NoSocketsTestCase):
    def test_command_should_work_1(self, mock_get_input):
        # given
        out = StringIO()
        character_1001 = CharacterFactory()
        character_1002 = CharacterFactory()
        CharacterUpdateStatusFactory(character=character_1001)
        CharacterUpdateStatusFactory(character=character_1002)

        cases = ["1", "2", "3", "4"]
        for case in cases:
            mock_get_input.return_value = case

            # when/then
            with self.subTest(input=case):
                call_command("memberaudit_stats", stdout=out)
