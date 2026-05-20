from io import StringIO

from django.core.management import call_command

from app_utils.testing import NoSocketsTestCase

from memberaudit.tests.testdata.factories_2 import (
    CharacterContactFactory,
    CharacterFactory,
)


class TestResetCharacters(NoSocketsTestCase):
    def test_should_reset_section_data_for_characters(self):
        # given
        character = CharacterFactory()
        CharacterContactFactory(character=character)
        out = StringIO()

        # when
        call_command("memberaudit_reset_characters", "--noinput", stdout=out)

        # then
        self.assertFalse(character.contacts.exists())
