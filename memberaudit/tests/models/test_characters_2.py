import datetime as dt
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils.timezone import now
from esi.errors import TokenError

from allianceauth.eveonline.models import EveCharacter
from allianceauth.tests.auth_utils import AuthUtils
from app_utils.esi_testing import build_http_error
from app_utils.testing import NoSocketsTestCase, create_user_from_evecharacter

from memberaudit.helpers import UpdateSectionResult
from memberaudit.models import Character, CharacterUpdateStatus
from memberaudit.tests.testdata.factories import (
    create_character,
    create_character_from_user,
    create_character_update_status,
)
from memberaudit.tests.testdata.load_entities import load_entities
from memberaudit.tests.utils import (
    add_memberaudit_character_to_user,
    create_memberaudit_character,
    create_user_from_evecharacter_with_access,
)

MODULE_PATH = "memberaudit.models.characters"


class TestCharacterUserHasAccess(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities()
        cls.user_1001, _ = create_user_from_evecharacter_with_access(1001)

    def test_user_owning_character_has_access(self):
        # given
        character_1001 = create_character_from_user(self.user_1001)
        # when/then
        self.assertTrue(character_1001.user_has_access(self.user_1001))

    def test_other_user_has_no_access(self):
        # given
        character_1001 = create_character_from_user(self.user_1001)
        user_lex = AuthUtils.create_user("Lex_Luthor")
        # when/then
        self.assertFalse(character_1001.user_has_access(user_lex))

    def test_has_no_access_for_view_everything_without_scope_permission(self):
        # given
        character_1101 = create_memberaudit_character(1101)
        user_1002, _ = create_user_from_evecharacter(
            1002,
            permissions=["memberaudit.basic_access", "memberaudit.view_everything"],
        )
        # when/then
        self.assertFalse(character_1101.user_has_access(user_1002))

    def test_has_access_for_view_everything_with_scope_permission(self):
        # given
        character_1001 = create_character_from_user(self.user_1001)
        user_1002, _ = create_user_from_evecharacter(
            1002,
            permissions=[
                "memberaudit.basic_access",
                "memberaudit.view_everything",
                "memberaudit.characters_access",
            ],
        )
        # when/then
        self.assertTrue(character_1001.user_has_access(user_1002))

    def test_has_access_for_view_everything_with_scope_permission_to_orphan(self):
        # given
        character_1121 = create_character(EveCharacter.objects.get(character_id=1121))
        user_1002, _ = create_user_from_evecharacter(
            1002,
            permissions=[
                "memberaudit.basic_access",
                "memberaudit.view_everything",
                "memberaudit.characters_access",
            ],
        )
        # when/then
        self.assertTrue(character_1121.user_has_access(user_1002))

    def test_view_same_corporation_1a(self):
        """
        when user has view_same_corporation permission and not characters_access
        and is in the same corporation as the character owner (main)
        then return False
        """
        # given
        character_1001 = create_character_from_user(self.user_1001)
        user_1002, _ = create_user_from_evecharacter(
            1002,
            permissions=[
                "memberaudit.basic_access",
                "memberaudit.view_same_corporation",
            ],
        )
        # when/then
        self.assertFalse(character_1001.user_has_access(user_1002))

    def test_view_same_corporation_1b(self):
        """
        when user has view_same_corporation permission and characters_access
        and is in the same corporation as the character owner (main)
        then return True
        """
        # given
        character_1001 = create_character_from_user(self.user_1001)
        user_1002, _ = create_user_from_evecharacter_with_access(1002)
        user_1002 = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_same_corporation", user_1002
        )
        user_1002 = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.characters_access", user_1002
        )
        # when/then
        self.assertTrue(character_1001.user_has_access(user_1002))

    def test_view_same_corporation_2a(self):
        """
        when user has view_same_corporation permission and not characters_access
        and is in the same corporation as the character owner (alt)
        then return False
        """
        # given
        character_1001 = create_character_from_user(self.user_1001)
        user_1002, _ = create_user_from_evecharacter_with_access(1002)
        user_1002 = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_same_corporation", user_1002
        )
        character_1103 = add_memberaudit_character_to_user(
            character_1001.eve_character.character_ownership.user, 1103
        )
        # when/then
        self.assertFalse(character_1103.user_has_access(user_1002))

    def test_view_same_corporation_2b(self):
        """
        when user has view_same_corporation permission and characters_access
        and is in the same corporation as the character owner (alt)
        then return True
        """
        # given
        character_1001 = create_character_from_user(self.user_1001)
        user_1002, _ = create_user_from_evecharacter_with_access(1002)
        user_1002 = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_same_corporation", user_1002
        )
        user_1002 = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.characters_access", user_1002
        )
        character_1103 = add_memberaudit_character_to_user(
            character_1001.eve_character.character_ownership.user, 1103
        )
        self.assertTrue(character_1103.user_has_access(user_1002))

    def test_view_same_corporation_3(self):
        """
        when user has view_same_corporation permission and characters_access
        and is NOT in the same corporation as the character owner
        then return False
        """
        # given
        character_1001 = create_character_from_user(self.user_1001)
        user_1003, _ = create_user_from_evecharacter_with_access(1003)
        user_1003 = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_same_corporation", user_1003
        )
        user_1003 = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.characters_access", user_1003
        )
        # when/then
        self.assertFalse(character_1001.user_has_access(user_1003))

    def test_view_same_alliance_1a(self):
        """
        when user has view_same_alliance permission and not characters_access
        and is in the same alliance as the character's owner (main)
        then return False
        """
        # given
        character_1001 = create_character_from_user(self.user_1001)
        user_1003, _ = create_user_from_evecharacter_with_access(1003)
        user_1003 = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_same_alliance", user_1003
        )
        # when/then
        self.assertFalse(character_1001.user_has_access(user_1003))

    def test_view_same_alliance_1b(self):
        """
        when user has view_same_alliance permission and characters_access
        and is in the same alliance as the character's owner (main)
        then return True
        """
        # given
        character_1001 = create_character_from_user(self.user_1001)
        user_1003, _ = create_user_from_evecharacter_with_access(1003)
        user_1003 = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_same_alliance", user_1003
        )
        user_1003 = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.characters_access", user_1003
        )
        # when/then
        self.assertTrue(character_1001.user_has_access(user_1003))

    def test_view_same_alliance_2a(self):
        """
        when user has view_same_alliance permission and not characters_access
        and is in the same alliance as the character's owner (alt)
        then return False
        """
        # given
        character_1001 = create_character_from_user(self.user_1001)
        user_1003, _ = create_user_from_evecharacter_with_access(1003)
        user_1003 = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_same_alliance", user_1003
        )
        character_1103 = add_memberaudit_character_to_user(
            character_1001.eve_character.character_ownership.user, 1103
        )
        # when/then
        self.assertFalse(character_1103.user_has_access(user_1003))

    def test_view_same_alliance_2b(self):
        """
        when user has view_same_alliance permission and characters_access
        and is in the same alliance as the character's owner (alt)
        then return True
        """
        # given
        character_1001 = create_character_from_user(self.user_1001)
        user_1003, _ = create_user_from_evecharacter_with_access(1003)
        user_1003 = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_same_alliance", user_1003
        )
        user_1003 = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.characters_access", user_1003
        )
        character_1103 = add_memberaudit_character_to_user(
            character_1001.eve_character.character_ownership.user, 1103
        )
        # when/then
        self.assertTrue(character_1103.user_has_access(user_1003))

    def test_view_same_alliance_3(self):
        """
        when user has view_same_alliance permission and characters_access
        and is NOT in the same alliance as the character owner
        then return False
        """
        # given
        character_1001 = create_character_from_user(self.user_1001)
        user_1101, _ = create_user_from_evecharacter_with_access(1101)
        user_1101 = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_same_alliance", user_1101
        )
        user_1101 = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.characters_access", user_1101
        )
        # when/then
        self.assertFalse(character_1001.user_has_access(user_1101))

    def test_recruiter_access_1(self):
        """
        when user has recruiter permission
        and character is shared
        then return True
        """
        # given
        character_1001 = create_character_from_user(self.user_1001)
        character_1001.is_shared = True
        character_1001.save()
        AuthUtils.add_permission_to_user_by_name(
            "memberaudit.share_characters",
            character_1001.eve_character.character_ownership.user,
        )
        user_1101, _ = create_user_from_evecharacter_with_access(1101)
        user_1101 = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_shared_characters", user_1101
        )
        # when/then
        self.assertTrue(character_1001.user_has_access(user_1101))

    def test_recruiter_access_2(self):
        """
        when user has recruiter permission
        and character is NOT shared
        then return False
        """
        # given
        character_1001 = create_character_from_user(self.user_1001)
        character_1001.is_shared = False
        character_1001.save()
        AuthUtils.add_permission_to_user_by_name(
            "memberaudit.share_characters",
            character_1001.eve_character.character_ownership.user,
        )
        user_1101, _ = create_user_from_evecharacter_with_access(1101)
        user_1101 = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_shared_characters", user_1101
        )
        # when/then
        self.assertFalse(character_1001.user_has_access(user_1101))


class TestCharacterUserHasScope(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities()
        cls.user_1001, _ = create_user_from_evecharacter_with_access(1001)

    def test_user_owning_character_has_scope(self):
        # given
        character_1001 = create_character_from_user(self.user_1001)
        # when/then
        self.assertTrue(character_1001.user_has_scope(self.user_1001))

    def test_other_user_has_no_scope(self):
        # given
        character_1001 = create_character_from_user(self.user_1001)
        user_lex = AuthUtils.create_user("Lex Luthor")
        # when/then
        self.assertFalse(character_1001.user_has_scope(user_lex))

    def test_has_no_scope_for_view_everything_without_scope_permission(self):
        # given
        character_1001 = create_memberaudit_character(1101)
        user_1002, _ = create_user_from_evecharacter(1002)
        # when/then
        self.assertFalse(character_1001.user_has_scope(user_1002))

    def test_has_scope_for_view_everything_with_scope_permission(self):
        # given
        character_1001 = create_character_from_user(self.user_1001)
        user_1002, _ = create_user_from_evecharacter(
            1002, permissions=["memberaudit.view_everything"]
        )
        # when/then
        self.assertTrue(character_1001.user_has_scope(user_1002))

    def test_has_scope_for_view_everything_with_scope_permission_to_orphan(self):
        # given
        character_1121 = create_character(EveCharacter.objects.get(character_id=1121))
        user_1002, _ = create_user_from_evecharacter(
            1002, permissions=["memberaudit.view_everything"]
        )
        # when/then
        self.assertTrue(character_1121.user_has_scope(user_1002))

    def test_view_same_corporation_1(self):
        """
        when user has view_same_corporation permission
        and is in the same corporation as the character owner (main)
        then return True
        """
        # given
        character_1001 = create_character_from_user(self.user_1001)
        user_1002, _ = create_user_from_evecharacter_with_access(1002)
        user_1002 = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_same_corporation", user_1002
        )
        # when/then
        self.assertTrue(character_1001.user_has_scope(user_1002))

    def test_view_same_corporation_2(self):
        """
        when user has view_same_corporation permission
        and is in the same corporation as the character owner (alt)
        then return True
        """
        # given
        character_1001 = create_character_from_user(self.user_1001)
        user_1002, _ = create_user_from_evecharacter_with_access(1002)
        user_1002 = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_same_corporation", user_1002
        )
        character_1103 = add_memberaudit_character_to_user(
            character_1001.eve_character.character_ownership.user, 1103
        )
        self.assertTrue(character_1103.user_has_scope(user_1002))

    def test_view_same_corporation_3(self):
        """
        when user has view_same_corporation permission
        and is NOT in the same corporation as the character owner
        then return False
        """
        # given
        character_1001 = create_character_from_user(self.user_1001)
        user_1003, _ = create_user_from_evecharacter_with_access(1003)
        user_1003 = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_same_corporation", user_1003
        )
        # when/then
        self.assertFalse(character_1001.user_has_scope(user_1003))

    def test_view_same_alliance_1(self):
        """
        when user has view_same_alliance permission
        and is in the same alliance as the character's owner (main)
        then return True
        """
        # given
        character_1001 = create_character_from_user(self.user_1001)
        user_1003, _ = create_user_from_evecharacter_with_access(1003)
        user_1003 = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_same_alliance", user_1003
        )
        # when/then
        self.assertTrue(character_1001.user_has_scope(user_1003))

    def test_view_same_alliance_2(self):
        """
        when user has view_same_alliance permission
        and is in the same alliance as the character's owner (alt)
        then return True
        """
        # given
        character_1001 = create_character_from_user(self.user_1001)
        user_1003, _ = create_user_from_evecharacter_with_access(1003)
        user_1003 = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_same_alliance", user_1003
        )
        character_1103 = add_memberaudit_character_to_user(
            character_1001.eve_character.character_ownership.user, 1103
        )
        # when/then
        self.assertTrue(character_1103.user_has_scope(user_1003))

    def test_view_same_alliance_3(self):
        """
        when user has view_same_alliance permission
        and is NOT in the same alliance as the character owner
        then return False
        """
        # given
        character_1001 = create_character_from_user(self.user_1001)
        user_1101, _ = create_user_from_evecharacter_with_access(1101)
        user_1101 = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_same_alliance", user_1101
        )
        # when/then
        self.assertFalse(character_1001.user_has_scope(user_1101))


@patch(MODULE_PATH + ".Character.update_section_content_hash")
@patch(MODULE_PATH + ".Character.has_section_changed")
class TestCharacterUpdateDataIfChangedOrForced(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities()
        cls.character_1002 = create_memberaudit_character(1002)
        cls.user, _ = create_user_from_evecharacter_with_access(1001)

    @staticmethod
    def _fetch_func_template(character):
        return ["alpha"]

    @staticmethod
    def _store_func_template(character, data):
        pass

    def test_should_store_data_when_changed(
        self, mock_has_section_changed, mock_update_section_content_hash
    ):
        # given
        character = create_character_from_user(self.user)
        fetch_func_mock = MagicMock(side_effect=self._fetch_func_template)
        store_func_mock = MagicMock(side_effect=self._store_func_template)
        mock_has_section_changed.return_value = True
        # when
        result = character.update_section_if_changed(
            section=character.UpdateSection.LOCATION,
            fetch_func=fetch_func_mock,
            store_func=store_func_mock,
            force_update=False,
        )
        # then
        self.assertTrue(fetch_func_mock.called)
        self.assertTrue(store_func_mock.called)
        args, _ = store_func_mock.call_args
        self.assertEqual(args[1], ["alpha"])
        self.assertTrue(mock_update_section_content_hash.called)
        _, kwargs = mock_update_section_content_hash.call_args
        self.assertEqual(kwargs["content"], ["alpha"])
        self.assertListEqual(result.data, ["alpha"])
        self.assertTrue(result.is_changed)
        self.assertTrue(result.is_updated)

    def test_should_not_store_data_when_not_changed(
        self, mock_has_section_changed, mock_update_section_content_hash
    ):
        # given
        character = create_character_from_user(self.user)
        fetch_func_mock = MagicMock(side_effect=self._fetch_func_template)
        store_func_mock = MagicMock(side_effect=self._store_func_template)
        mock_has_section_changed.return_value = False
        # when
        result = character.update_section_if_changed(
            section=character.UpdateSection.LOCATION,
            fetch_func=fetch_func_mock,
            store_func=store_func_mock,
            force_update=False,
        )
        # then
        self.assertTrue(fetch_func_mock.called)
        self.assertFalse(store_func_mock.called)
        self.assertFalse(mock_update_section_content_hash.called)
        self.assertIsNone(result.data)
        self.assertFalse(result.is_changed)
        self.assertFalse(result.is_updated)

    def test_should_always_store_data_when_forced(
        self, mock_has_section_changed, mock_update_section_content_hash
    ):
        # given
        character = create_character_from_user(self.user)
        fetch_func_mock = MagicMock(side_effect=self._fetch_func_template)
        store_func_mock = MagicMock(side_effect=self._store_func_template)
        mock_has_section_changed.return_value = False
        # when
        result = character.update_section_if_changed(
            section=character.UpdateSection.LOCATION,
            fetch_func=fetch_func_mock,
            store_func=store_func_mock,
            force_update=True,
        )
        # then
        self.assertTrue(fetch_func_mock.called)
        self.assertTrue(store_func_mock.called)
        self.assertTrue(mock_update_section_content_hash.called)
        self.assertListEqual(result.data, ["alpha"])
        self.assertFalse(result.is_changed)
        self.assertTrue(result.is_updated)

    def test_should_not_store_anything_when_esi_returns_http_500_and_return_none(
        self, mock_has_section_changed, mock_update_section_content_hash
    ):
        # given
        character = create_character_from_user(self.user)
        fetch_func_mock = MagicMock(side_effect=build_http_error(500, "Test exception"))
        store_func_mock = MagicMock(side_effect=self._store_func_template)
        mock_has_section_changed.side_effect = RuntimeError("Should not be called")
        # when
        result = character.update_section_if_changed(
            section=character.UpdateSection.LOCATION,
            fetch_func=fetch_func_mock,
            store_func=store_func_mock,
            force_update=False,
        )
        # then
        self.assertTrue(fetch_func_mock.called)
        self.assertFalse(store_func_mock.called)
        self.assertFalse(mock_update_section_content_hash.called)
        self.assertIsNone(result.is_changed)
        self.assertFalse(result.is_updated)

    def test_should_store_data_when_changed_and_use_hash_num(
        self, mock_has_section_changed, mock_update_section_content_hash
    ):
        # given
        character = create_character_from_user(self.user)
        fetch_func_mock = MagicMock(side_effect=self._fetch_func_template)
        store_func_mock = MagicMock(side_effect=self._store_func_template)
        mock_has_section_changed.return_value = True
        # when
        character.update_section_if_changed(
            section=character.UpdateSection.LOCATION,
            fetch_func=fetch_func_mock,
            store_func=store_func_mock,
            force_update=False,
            hash_num=2,
        )
        # then
        self.assertTrue(fetch_func_mock.called)
        self.assertTrue(store_func_mock.called)
        args, _ = store_func_mock.call_args
        self.assertEqual(args[1], ["alpha"])
        _, kwargs = mock_has_section_changed.call_args
        self.assertEqual(kwargs["hash_num"], 2)
        _, kwargs = mock_update_section_content_hash.call_args
        self.assertEqual(kwargs["hash_num"], 2)

    def test_should_skip_storing_data_when_no_store_func_provided(
        self, mock_has_section_changed, mock_update_section_content_hash
    ):
        # given
        character = create_character_from_user(self.user)
        fetch_func_mock = MagicMock(side_effect=self._fetch_func_template)
        mock_has_section_changed.return_value = True
        # when
        result = character.update_section_if_changed(
            section=character.UpdateSection.LOCATION,
            fetch_func=fetch_func_mock,
            store_func=None,
        )
        # then
        self.assertTrue(fetch_func_mock.called)
        self.assertTrue(mock_update_section_content_hash.called)
        self.assertListEqual(result.data, ["alpha"])
        self.assertTrue(result.is_changed)
        self.assertFalse(result.is_updated)

    @patch(MODULE_PATH + ".EveEntity.objects.bulk_resolve_ids")
    def test_should_resolve_eve_entity_ids_when_provided(
        self,
        mock_bulk_resolve_ids,
        mock_has_section_changed,
        mock_update_section_content_hash,
    ):
        # given
        def my_store_func(character, data):
            return [1, 2]

        fetch_func_mock = MagicMock(side_effect=self._fetch_func_template)
        mock_has_section_changed.return_value = True
        # when
        self.character_1002.update_section_if_changed(
            section=Character.UpdateSection.LOCATION,
            fetch_func=fetch_func_mock,
            store_func=my_store_func,
            force_update=False,
        )
        # then
        self.assertTrue(fetch_func_mock.called)
        self.assertTrue(mock_bulk_resolve_ids.called)
        args, _ = mock_bulk_resolve_ids.call_args
        self.assertListEqual(args[0], [1, 2])

    @patch(MODULE_PATH + ".EveEntity.objects.bulk_resolve_ids")
    def test_should_not_resolve_eve_entity_ids_when_not_provided(
        self,
        mock_bulk_resolve_ids,
        mock_has_section_changed,
        mock_update_section_content_hash,
    ):
        # given
        def my_store_func(character, data):
            return []

        fetch_func_mock = MagicMock(side_effect=self._fetch_func_template)
        mock_has_section_changed.return_value = True
        # when
        self.character_1002.update_section_if_changed(
            section=Character.UpdateSection.LOCATION,
            fetch_func=fetch_func_mock,
            store_func=my_store_func,
            force_update=False,
        )
        # then
        self.assertTrue(fetch_func_mock.called)
        self.assertFalse(mock_bulk_resolve_ids.called)


class TestCharacterHasTokenError(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities()
        cls.character = create_memberaudit_character(1001)

    def test_should_return_false_when_no_error(self):
        # when/then
        self.assertFalse(self.character.has_token_issue())

    def test_should_return_true_when_token_error(self):
        # given
        create_character_update_status(
            self.character,
            section=Character.UpdateSection.ASSETS,
            is_success=False,
            has_token_error=True,
            error_message="TokenError",
        )
        # when/then
        self.assertTrue(self.character.has_token_issue())

    def test_should_return_false_when_other_error(self):
        # given
        create_character_update_status(
            self.character,
            section=Character.UpdateSection.ASSETS,
            is_success=False,
            has_token_error=False,
            error_message="other error",
        )
        # when/then
        self.assertFalse(self.character.has_token_issue())

    @patch(MODULE_PATH + ".MEMBERAUDIT_FEATURE_ROLES_ENABLED", False)
    def test_should_return_false_when_token_error_for_disabled_section(self):
        # given
        create_character_update_status(
            self.character,
            section=Character.UpdateSection.ROLES,
            is_success=False,
            has_token_error=True,
            error_message="TokenError",
        )
        # when/then
        self.assertFalse(self.character.has_token_issue())


class TestCharacterResetTokenErrorNotifiedIfStatusOk(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities()
        cls.user, _ = create_user_from_evecharacter_with_access(1001)

    def test_should_reset_when_ok_again(self):
        # given
        character = create_character_from_user(self.user, token_error_notified_at=now())
        for section in Character.UpdateSection:
            create_character_update_status(character, section=section)

        # when
        character.reset_token_error_notified_if_status_ok()

        # then
        character.refresh_from_db()
        self.assertIsNone(character.token_error_notified_at)

    def test_should_not_reset_when_not_yet_ok(self):
        # given
        character = create_character_from_user(self.user, token_error_notified_at=now())
        create_character_update_status(
            character, section=Character.UpdateSection.ASSETS, is_success=False
        )

        # when
        character.reset_token_error_notified_if_status_ok()

        # then
        character.refresh_from_db()
        self.assertTrue(character.token_error_notified_at)

    def test_should_ignore_when_not_set(self):
        # given
        character = create_character_from_user(self.user, token_error_notified_at=None)
        create_character_update_status(
            character, section=Character.UpdateSection.ASSETS, is_success=False
        )

        # when
        character.reset_token_error_notified_if_status_ok()

        # then
        character.refresh_from_db()
        self.assertIsNone(character.token_error_notified_at)


class TestCharacterGetEsiScopes(TestCase):
    @patch(MODULE_PATH + ".MEMBERAUDIT_FEATURE_ROLES_ENABLED", False)
    def test_should_return_all_scopes(self):
        # when
        result = Character.get_esi_scopes()
        # then
        expected = {
            "esi-assets.read_assets.v1",
            "esi-bookmarks.read_character_bookmarks.v1",
            "esi-calendar.read_calendar_events.v1",
            "esi-characters.read_agents_research.v1",
            "esi-characters.read_blueprints.v1",
            "esi-characters.read_contacts.v1",
            "esi-characters.read_corporation_roles.v1",  # NEW
            "esi-characters.read_fatigue.v1",
            "esi-characters.read_fw_stats.v1",
            "esi-characters.read_loyalty.v1",
            "esi-characters.read_medals.v1",
            "esi-characters.read_notifications.v1",
            "esi-characters.read_opportunities.v1",
            "esi-characters.read_standings.v1",
            "esi-characters.read_titles.v1",
            "esi-clones.read_clones.v1",
            "esi-clones.read_implants.v1",
            "esi-contracts.read_character_contracts.v1",
            "esi-corporations.read_corporation_membership.v1",
            "esi-industry.read_character_jobs.v1",
            "esi-industry.read_character_mining.v1",
            "esi-killmails.read_killmails.v1",
            "esi-location.read_location.v1",
            "esi-location.read_online.v1",
            "esi-location.read_ship_type.v1",
            "esi-mail.organize_mail.v1",
            "esi-mail.read_mail.v1",
            "esi-markets.read_character_orders.v1",
            "esi-markets.structure_markets.v1",
            "esi-planets.manage_planets.v1",
            "esi-planets.read_customs_offices.v1",
            "esi-search.search_structures.v1",
            "esi-skills.read_skillqueue.v1",
            "esi-skills.read_skills.v1",
            "esi-universe.read_structures.v1",
            "esi-wallet.read_character_wallet.v1",
        }
        self.assertSetEqual(set(result), expected)


class TestCharacterPerformUpdateWithErrorLogging(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities()
        cls.character = create_memberaudit_character(1001)

    def setUp(self) -> None:
        self.character.update_status_set.all().delete()

    def test_should_execute_method_and_return_value(self):
        # given
        def my_method(dummy):
            return UpdateSectionResult(
                data=f"return-value-{dummy}", is_changed=True, is_updated=True
            )

        section = Character.UpdateSection.LOCATION
        # when
        result = self.character.perform_update_with_error_logging(
            section=section, method=my_method, dummy="alpha"
        )
        # then
        self.assertEqual(result.data, "return-value-alpha")
        self.assertTrue(result.is_updated)

    def test_should_mark_section_as_failed_when_general_exception_is_raised(self):
        # given
        def my_method():
            raise RuntimeError("Test exception")

        section = Character.UpdateSection.LOCATION
        # when/then
        with self.assertRaises(RuntimeError):
            self.character.perform_update_with_error_logging(
                section=section, method=my_method
            )
        # then
        status: CharacterUpdateStatus = self.character.update_status_set.get(
            section=section
        )
        self.assertFalse(status.is_success)
        self.assertFalse(status.has_token_error)
        self.assertIn("RuntimeError", status.error_message)
        self.assertTrue(status.run_finished_at)

    def test_should_mark_section_as_failed_when_token_error_is_raised(self):
        # given
        def my_method():
            raise TokenError("Test exception")

        section = Character.UpdateSection.LOCATION
        # when/then
        with self.assertRaises(TokenError):
            self.character.perform_update_with_error_logging(
                section=section, method=my_method
            )
        # then
        status: CharacterUpdateStatus = self.character.update_status_set.get(
            section=section
        )
        self.assertFalse(status.is_success)
        self.assertTrue(status.has_token_error)
        self.assertIn("TokenError", status.error_message)
        self.assertTrue(status.run_finished_at)


class TestCharacterUpdateStatusAsDict(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities()
        cls.character = create_memberaudit_character(1001)

    def test_should_return_dict_with_status(self):
        # given
        status = create_character_update_status(
            self.character, section=Character.UpdateSection.LOCATION, is_success=True
        )
        # when
        result = self.character.update_status_as_dict()
        # then
        self.assertDictEqual(result, {"location": status})

    def test_should_return_empty_dict(self):
        # when
        result = self.character.update_status_as_dict()
        # then
        self.assertDictEqual(result, {})


@patch(MODULE_PATH + ".section_time_until_stale", {"assets": 640})
class TestCharacterUpdateStatusIsUpdateNeeded(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities()
        cls.section = Character.UpdateSection.ASSETS
        cls.character = create_memberaudit_character(1001)

    def test_should_report_false_when_section_not_stale(self):
        # given
        status = create_character_update_status(
            character=self.character,
            section=self.section,
            is_success=True,
            run_started_at=now() - dt.timedelta(seconds=30),
            run_finished_at=now(),
        )
        # when/then
        self.assertFalse(status.is_update_needed())

    def test_should_report_true_when_section_has_error(self):
        # given
        status = create_character_update_status(
            character=self.character, section=self.section, is_success=False
        )
        # when/then
        self.assertTrue(status.is_update_needed())

    def test_should_report_true_when_section_is_stale(self):
        # given
        run_started_at = now() - dt.timedelta(hours=12)
        run_finished_at = run_started_at + dt.timedelta(minutes=10)
        status = create_character_update_status(
            character=self.character,
            section=self.section,
            is_success=True,
            run_started_at=run_started_at,
            run_finished_at=run_finished_at,
        )
        # when/then
        self.assertTrue(status.is_update_needed())

    def test_should_report_false_when_section_has_token_error_and_stale(self):
        # given
        run_started_at = now() - dt.timedelta(hours=12)
        status = create_character_update_status(
            character=self.character,
            section=self.section,
            is_success=False,
            run_started_at=run_started_at,
            has_token_error=True,
        )
        # when/then
        self.assertFalse(status.is_update_needed())

    def test_should_report_false_when_section_has_token_error_and_not_stale(self):
        # given
        status = create_character_update_status(
            character=self.character,
            section=self.section,
            is_success=False,
            has_token_error=True,
        )
        # when/then
        self.assertFalse(status.is_update_needed())
