from allianceauth.tests.auth_utils import AuthUtils
from app_utils.testing import NoSocketsTestCase, create_user_from_evecharacter

from memberaudit.models import Character

from .testdata.factories import create_character_from_user
from .testdata.load_entities import load_entities


class TestCreateCharacterFromUser(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities()

    def test_should_create_character(self):
        # given
        user, _ = create_user_from_evecharacter(1001)
        # when
        obj = create_character_from_user(user)
        # then
        self.assertIsInstance(obj, Character)

    def test_should_raise_error_when_no_main(self):
        # given
        user = AuthUtils.create_user("some_user")
        # when/then
        with self.assertRaises(ValueError):
            create_character_from_user(user)
