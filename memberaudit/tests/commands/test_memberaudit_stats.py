from io import StringIO

from django.core.management import call_command

from app_utils.testing import TestCase

from memberaudit.management.commands import memberaudit_stats
from memberaudit.tests.testdata.factories import create_character_update_status
from memberaudit.tests.testdata.load_entities import load_entities
from memberaudit.tests.utils import create_memberaudit_character


class TestStats(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities()

    def setUp(self) -> None:
        memberaudit_stats.clear_cache()

    def test_command_should_work(self):
        # given
        character_1001 = create_memberaudit_character(1001)
        create_character_update_status(character_1001)
        character_1002 = create_memberaudit_character(1002)
        create_character_update_status(character_1002)
        out = StringIO()

        # when/then
        call_command("memberaudit_stats", stdout=out)
