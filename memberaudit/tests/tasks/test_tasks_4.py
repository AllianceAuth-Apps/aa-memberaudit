import datetime as dt

from django.utils.timezone import now

from app_utils.testing import NoSocketsTestCase

from memberaudit import tasks
from memberaudit.tests.testdata.factories_2 import CharacterFactory

MODULE_PATH = "memberaudit.tasks"


class TestUnshareExpiredCharacters(NoSocketsTestCase):
    def test_should_unshare_when_expired(self):
        # given
        timeout = 3
        shared_at = now() - dt.timedelta(minutes=timeout, seconds=1)
        character = CharacterFactory(is_shared=True, shared_at=shared_at)

        # when
        got = tasks.unshare_expired_characters(timeout)

        # then
        self.assertEqual(got, 1)
        character.refresh_from_db()
        self.assertFalse(character.is_shared)
        self.assertIsNone(character.shared_at)

    def test_should_not_unshare_when_not_expired(self):
        # given
        timeout = 3
        shared_at = now() - dt.timedelta(minutes=2)
        character = CharacterFactory(is_shared=True, shared_at=shared_at)

        # when
        got = tasks.unshare_expired_characters(timeout)

        # then
        self.assertEqual(got, 0)
        character.refresh_from_db()
        self.assertTrue(character.is_shared)
        self.assertIsNotNone(character.shared_at)

    def test_should_not_nothing_when_timeout_not_set(self):
        # given
        timeout = 0
        shared_at = now() - dt.timedelta(minutes=2)
        character = CharacterFactory(is_shared=True, shared_at=shared_at)

        # when
        got = tasks.unshare_expired_characters(timeout)

        # then
        self.assertEqual(got, 0)
        character.refresh_from_db()
        self.assertTrue(character.is_shared)
        self.assertIsNotNone(character.shared_at)
