from io import StringIO

from django.core.management import call_command

from app_utils.testing import NoSocketsTestCase

from memberaudit.tests.testdata.factories import create_character_contract
from memberaudit.tests.testdata.load_entities import load_entities
from memberaudit.tests.utils import create_memberaudit_character


class TestResetCharacters(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities()

    def test_should_reset_section_data_for_characters(self):
        # given
        character_1001 = create_memberaudit_character(1001)
        create_character_contract(character_1001)
        out = StringIO()

        # when
        call_command("memberaudit_reset_characters", "--noinput", stdout=out)

        # then
        self.assertFalse(character_1001.contracts.exists())
