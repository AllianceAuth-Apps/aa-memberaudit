from io import StringIO
from unittest import skip

from django.core.management import call_command

from app_utils.testing import NoSocketsTestCase

from memberaudit.models import Character
from memberaudit.tests.testdata.load_entities import load_entities
from memberaudit.tests.utils import (
    add_auth_character_to_user,
    create_user_from_evecharacter_with_access,
)


@skip("Maria DB breaks")
class TestResetCharacters(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities()

    def test_normal(self):
        """can recreate member audit characters from main and alt of matching tokens"""
        user, co_1001 = create_user_from_evecharacter_with_access(1001)
        co_1002 = add_auth_character_to_user(user, 1002)

        out = StringIO()
        call_command("memberaudit_reset_characters", "--noinput", stdout=out)

        self.assertSetEqual(
            set(
                Character.objects.values_list(
                    "eve_character__character_ownership__id", flat=True
                )
            ),
            {co_1001.id, co_1002.id},
        )

    def test_orphaned_tokens(self):
        """
        given a matching token exists and the respective auth character
        is now owner by another user
        and no longer has a matching token
        when creating member audit characters
        then no member audit character is created for the switched auth character
        """
        user_1, co_1001 = create_user_from_evecharacter_with_access(1001)
        add_auth_character_to_user(user_1, 1002)
        user_2, co_1101 = create_user_from_evecharacter_with_access(1101)

        # re-add auth character 1002 to another user, but without member audit scopes
        add_auth_character_to_user(user_2, 1002, scopes="publicData")

        out = StringIO()
        call_command("memberaudit_reset_characters", "--noinput", stdout=out)

        self.assertSetEqual(
            set(
                Character.objects.values_list(
                    "eve_character__character_ownership__id", flat=True
                )
            ),
            {co_1001.id, co_1101.id},
        )
