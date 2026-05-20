from app_utils.testing import NoSocketsTestCase

from .factories_2 import (
    CharacterFactory,
    ComplianceGroupFactory,
    GroupFactory,
    StateFactory,
    UserMainBasicAccessFactory,
)


class TestGroupFactory(NoSocketsTestCase):
    def test_can_set_public(self):
        g = GroupFactory(authgroup__public=True)
        self.assertTrue(g.authgroup.public)

    def test_can_set_states(self):
        s = StateFactory()
        g = GroupFactory(authgroup__states=[s])
        self.assertIn(s, g.authgroup.states.all())


class TestComplianceGroupFactory(NoSocketsTestCase):
    def test_basic(self):
        g = ComplianceGroupFactory()
        self.assertTrue(g)


class TestCharacterFactory(NoSocketsTestCase):
    def test_can_create_multiple_characters_for_user(self):
        user = UserMainBasicAccessFactory()
        character_1 = CharacterFactory(user=user)
        character_2 = CharacterFactory(user=user, is_main=False)
        self.assertNotEqual(character_1.eve_character, character_2.eve_character)
