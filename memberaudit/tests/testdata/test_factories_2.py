from app_utils.testdata_factories import EveCharacterFactory
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
    def test_can_create_basic(self):
        character = CharacterFactory()
        self.assertTrue(character)

    def test_can_create_for_given_user(self):
        user = UserMainBasicAccessFactory()
        character = CharacterFactory(user=user)
        self.assertEqual(character.user, user)
        self.assertEqual(character.eve_character, user.profile.main_character)

    def test_can_create_alt_for_given_user(self):
        user = UserMainBasicAccessFactory()
        character = CharacterFactory(user=user, is_main=False)
        self.assertEqual(character.user, user)
        self.assertNotEqual(character.eve_character, user.profile.main_character)

    def test_can_create_for_given_user_and_eve_character(self):
        user = UserMainBasicAccessFactory()
        eve_character = EveCharacterFactory()
        character = CharacterFactory(
            user=user, is_main=False, alt_character=eve_character
        )
        self.assertEqual(character.user, user)
        self.assertEqual(character.eve_character, eve_character)

    def test_can_create_multiple_characters_for_user(self):
        user = UserMainBasicAccessFactory()
        character_1 = CharacterFactory(user=user)
        character_2 = CharacterFactory(user=user, is_main=False)
        self.assertNotEqual(character_1.eve_character, character_2.eve_character)
