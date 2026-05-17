from app_utils.testing import NoSocketsTestCase

from .factories_2 import (
    CharacterFactory,
    ComplianceGroupFactory,
    GroupFactory,
    UserBasicFactory,
)


class TestGroupFactory(NoSocketsTestCase):
    def test_can_set_auth_group(self):
        g = GroupFactory(authgroup__public=True)
        self.assertTrue(g.authgroup.public)


class TestComplianceGroupFactory(NoSocketsTestCase):
    def test_basic(self):
        g = ComplianceGroupFactory()
        self.assertTrue(g)


class TestCharacterFactory(NoSocketsTestCase):
    def test_can_create_multiple_characters_for_user(self):
        user = UserBasicFactory()
        character_1 = CharacterFactory(user=user)
        character_2 = CharacterFactory(user=user, is_main=False)
        self.assertNotEqual(character_1.eve_character, character_2.eve_character)
