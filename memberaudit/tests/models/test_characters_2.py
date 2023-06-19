from unittest.mock import MagicMock, patch

from django.test import TestCase

from allianceauth.eveonline.models import EveCharacter
from allianceauth.tests.auth_utils import AuthUtils
from app_utils.esi_testing import build_http_error
from app_utils.testing import create_user_from_evecharacter

from ..testdata.factories import create_character
from ..testdata.load_entities import load_entities
from ..utils import (
    add_memberaudit_character_to_user,
    create_memberaudit_character,
    create_user_from_evecharacter_with_access,
)

MODULE_PATH = "memberaudit.models.characters"


class TestCharacterUserHasAccess(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        load_entities()

    def test_user_owning_character_has_access(self):
        # given
        character_1001 = create_memberaudit_character(1001)
        user = character_1001.eve_character.character_ownership.user
        # when/then
        self.assertTrue(character_1001.user_has_access(user))

    def test_other_user_has_no_access(self):
        # given
        character_1001 = create_memberaudit_character(1001)
        user = AuthUtils.create_user("Lex Luthor")
        # when/then
        self.assertFalse(character_1001.user_has_access(user))

    def test_has_no_access_for_view_everything_without_scope_permission(self):
        # given
        character_1001 = create_memberaudit_character(1101)
        user, _ = create_user_from_evecharacter(
            1001,
            permissions=["memberaudit.basic_access", "memberaudit.view_everything"],
        )
        # when/then
        self.assertFalse(character_1001.user_has_access(user))

    def test_has_access_for_view_everything_with_scope_permission(self):
        # given
        character_1001 = create_memberaudit_character(1001)
        user, _ = create_user_from_evecharacter(
            1002,
            permissions=[
                "memberaudit.basic_access",
                "memberaudit.view_everything",
                "memberaudit.characters_access",
            ],
        )
        # when/then
        self.assertTrue(character_1001.user_has_access(user))

    def test_has_access_for_view_everything_with_scope_permission_to_orphan(self):
        # given
        character_1121 = create_character(EveCharacter.objects.get(character_id=1121))
        user, _ = create_user_from_evecharacter(
            1002,
            permissions=[
                "memberaudit.basic_access",
                "memberaudit.view_everything",
                "memberaudit.characters_access",
            ],
        )
        # when/then
        self.assertTrue(character_1121.user_has_access(user))

    def test_view_same_corporation_1a(self):
        """
        when user has view_same_corporation permission and not characters_access
        and is in the same corporation as the character owner (main)
        then return False
        """
        # given
        character_1001 = create_memberaudit_character(1001)
        user, _ = create_user_from_evecharacter(
            1002,
            permissions=[
                "memberaudit.basic_access",
                "memberaudit.view_same_corporation",
            ],
        )
        # when/then
        self.assertFalse(character_1001.user_has_access(user))

    def test_view_same_corporation_1b(self):
        """
        when user has view_same_corporation permission and characters_access
        and is in the same corporation as the character owner (main)
        then return True
        """
        # given
        character_1001 = create_memberaudit_character(1001)
        user_3, _ = create_user_from_evecharacter_with_access(1002)
        user_3 = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_same_corporation", user_3
        )
        user_3 = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.characters_access", user_3
        )
        # when/then
        self.assertTrue(character_1001.user_has_access(user_3))

    def test_view_same_corporation_2a(self):
        """
        when user has view_same_corporation permission and not characters_access
        and is in the same corporation as the character owner (alt)
        then return False
        """
        # given
        character_1001 = create_memberaudit_character(1001)
        user_3, _ = create_user_from_evecharacter_with_access(1002)
        user_3 = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_same_corporation", user_3
        )
        character_1103 = add_memberaudit_character_to_user(
            character_1001.eve_character.character_ownership.user, 1103
        )
        # when/then
        self.assertFalse(character_1103.user_has_access(user_3))

    def test_view_same_corporation_2b(self):
        """
        when user has view_same_corporation permission and characters_access
        and is in the same corporation as the character owner (alt)
        then return True
        """
        # given
        character_1001 = create_memberaudit_character(1001)
        user_3, _ = create_user_from_evecharacter_with_access(1002)
        user_3 = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_same_corporation", user_3
        )
        user_3 = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.characters_access", user_3
        )
        character_1103 = add_memberaudit_character_to_user(
            character_1001.eve_character.character_ownership.user, 1103
        )
        self.assertTrue(character_1103.user_has_access(user_3))

    def test_view_same_corporation_3(self):
        """
        when user has view_same_corporation permission and characters_access
        and is NOT in the same corporation as the character owner
        then return False
        """
        # given
        character_1001 = create_memberaudit_character(1001)
        user_3, _ = create_user_from_evecharacter_with_access(1003)
        user_3 = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_same_corporation", user_3
        )
        user_3 = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.characters_access", user_3
        )
        # when/then
        self.assertFalse(character_1001.user_has_access(user_3))

    def test_view_same_alliance_1a(self):
        """
        when user has view_same_alliance permission and not characters_access
        and is in the same alliance as the character's owner (main)
        then return False
        """
        # given
        character_1001 = create_memberaudit_character(1001)
        user_3, _ = create_user_from_evecharacter_with_access(1003)
        user_3 = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_same_alliance", user_3
        )
        # when/then
        self.assertFalse(character_1001.user_has_access(user_3))

    def test_view_same_alliance_1b(self):
        """
        when user has view_same_alliance permission and characters_access
        and is in the same alliance as the character's owner (main)
        then return True
        """
        # given
        character_1001 = create_memberaudit_character(1001)
        user_3, _ = create_user_from_evecharacter_with_access(1003)
        user_3 = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_same_alliance", user_3
        )
        user_3 = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.characters_access", user_3
        )
        # when/then
        self.assertTrue(character_1001.user_has_access(user_3))

    def test_view_same_alliance_2a(self):
        """
        when user has view_same_alliance permission and not characters_access
        and is in the same alliance as the character's owner (alt)
        then return False
        """
        # given
        character_1001 = create_memberaudit_character(1001)
        user_3, _ = create_user_from_evecharacter_with_access(1003)
        user_3 = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_same_alliance", user_3
        )
        character_1103 = add_memberaudit_character_to_user(
            character_1001.eve_character.character_ownership.user, 1103
        )
        # when/then
        self.assertFalse(character_1103.user_has_access(user_3))

    def test_view_same_alliance_2b(self):
        """
        when user has view_same_alliance permission and characters_access
        and is in the same alliance as the character's owner (alt)
        then return True
        """
        # given
        character_1001 = create_memberaudit_character(1001)
        user_3, _ = create_user_from_evecharacter_with_access(1003)
        user_3 = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_same_alliance", user_3
        )
        user_3 = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.characters_access", user_3
        )
        character_1103 = add_memberaudit_character_to_user(
            character_1001.eve_character.character_ownership.user, 1103
        )
        # when/then
        self.assertTrue(character_1103.user_has_access(user_3))

    def test_view_same_alliance_3(self):
        """
        when user has view_same_alliance permission and characters_access
        and is NOT in the same alliance as the character owner
        then return False
        """
        # given
        character_1001 = create_memberaudit_character(1001)
        user_3, _ = create_user_from_evecharacter_with_access(1101)
        user_3 = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_same_alliance", user_3
        )
        user_3 = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.characters_access", user_3
        )
        # when/then
        self.assertFalse(character_1001.user_has_access(user_3))

    def test_recruiter_access_1(self):
        """
        when user has recruiter permission
        and character is shared
        then return True
        """
        # given
        character_1001 = create_memberaudit_character(1001)
        character_1001.is_shared = True
        character_1001.save()
        AuthUtils.add_permission_to_user_by_name(
            "memberaudit.share_characters",
            character_1001.eve_character.character_ownership.user,
        )
        user_3, _ = create_user_from_evecharacter_with_access(1101)
        user_3 = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_shared_characters", user_3
        )
        # when/then
        self.assertTrue(character_1001.user_has_access(user_3))

    def test_recruiter_access_2(self):
        """
        when user has recruiter permission
        and character is NOT shared
        then return False
        """
        # given
        character_1001 = create_memberaudit_character(1001)
        character_1001.is_shared = False
        character_1001.save()
        AuthUtils.add_permission_to_user_by_name(
            "memberaudit.share_characters",
            character_1001.eve_character.character_ownership.user,
        )
        user_3, _ = create_user_from_evecharacter_with_access(1101)
        user_3 = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_shared_characters", user_3
        )
        # when/then
        self.assertFalse(character_1001.user_has_access(user_3))


class TestCharacterUserHasScope(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        load_entities()

    def test_user_owning_character_has_scope(self):
        # given
        character_1001 = create_memberaudit_character(1001)
        user = character_1001.eve_character.character_ownership.user
        # when/then
        self.assertTrue(character_1001.user_has_scope(user))

    def test_other_user_has_no_scope(self):
        # given
        character_1001 = create_memberaudit_character(1001)
        user = AuthUtils.create_user("Lex Luthor")
        # when/then
        self.assertFalse(character_1001.user_has_scope(user))

    def test_has_no_scope_for_view_everything_without_scope_permission(self):
        # given
        character_1001 = create_memberaudit_character(1101)
        user, _ = create_user_from_evecharacter(
            1001,
        )
        # when/then
        self.assertFalse(character_1001.user_has_scope(user))

    def test_has_scope_for_view_everything_with_scope_permission(self):
        # given
        character_1001 = create_memberaudit_character(1001)
        user, _ = create_user_from_evecharacter(
            1002,
            permissions=[
                "memberaudit.view_everything",
            ],
        )
        # when/then
        self.assertTrue(character_1001.user_has_scope(user))

    def test_has_scope_for_view_everything_with_scope_permission_to_orphan(self):
        # given
        character_1121 = create_character(EveCharacter.objects.get(character_id=1121))
        user, _ = create_user_from_evecharacter(
            1002,
            permissions=[
                "memberaudit.view_everything",
            ],
        )
        # when/then
        self.assertTrue(character_1121.user_has_scope(user))

    def test_view_same_corporation_1(self):
        """
        when user has view_same_corporation permission
        and is in the same corporation as the character owner (main)
        then return True
        """
        # given
        character_1001 = create_memberaudit_character(1001)
        user_3, _ = create_user_from_evecharacter_with_access(1002)
        user_3 = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_same_corporation", user_3
        )
        # when/then
        self.assertTrue(character_1001.user_has_scope(user_3))

    def test_view_same_corporation_2(self):
        """
        when user has view_same_corporation permission
        and is in the same corporation as the character owner (alt)
        then return True
        """
        # given
        character_1001 = create_memberaudit_character(1001)
        user_3, _ = create_user_from_evecharacter_with_access(1002)
        user_3 = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_same_corporation", user_3
        )
        character_1103 = add_memberaudit_character_to_user(
            character_1001.eve_character.character_ownership.user, 1103
        )
        self.assertTrue(character_1103.user_has_scope(user_3))

    def test_view_same_corporation_3(self):
        """
        when user has view_same_corporation permission
        and is NOT in the same corporation as the character owner
        then return False
        """
        # given
        character_1001 = create_memberaudit_character(1001)
        user_3, _ = create_user_from_evecharacter_with_access(1003)
        user_3 = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_same_corporation", user_3
        )
        # when/then
        self.assertFalse(character_1001.user_has_scope(user_3))

    def test_view_same_alliance_1(self):
        """
        when user has view_same_alliance permission
        and is in the same alliance as the character's owner (main)
        then return True
        """
        # given
        character_1001 = create_memberaudit_character(1001)
        user_3, _ = create_user_from_evecharacter_with_access(1003)
        user_3 = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_same_alliance", user_3
        )
        # when/then
        self.assertTrue(character_1001.user_has_scope(user_3))

    def test_view_same_alliance_2(self):
        """
        when user has view_same_alliance permission
        and is in the same alliance as the character's owner (alt)
        then return True
        """
        # given
        character_1001 = create_memberaudit_character(1001)
        user_3, _ = create_user_from_evecharacter_with_access(1003)
        user_3 = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_same_alliance", user_3
        )
        character_1103 = add_memberaudit_character_to_user(
            character_1001.eve_character.character_ownership.user, 1103
        )
        # when/then
        self.assertTrue(character_1103.user_has_scope(user_3))

    def test_view_same_alliance_3(self):
        """
        when user has view_same_alliance permission
        and is NOT in the same alliance as the character owner
        then return False
        """
        # given
        character_1001 = create_memberaudit_character(1001)
        user_3, _ = create_user_from_evecharacter_with_access(1101)
        user_3 = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_same_alliance", user_3
        )
        # when/then
        self.assertFalse(character_1001.user_has_scope(user_3))


@patch(MODULE_PATH + ".Character.update_section_content_hash")
@patch(MODULE_PATH + ".Character.has_section_changed")
class TestCharacterUpdateDataIfChangedOrForced(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        load_entities()

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
        character = create_memberaudit_character(1001)
        fetch_func_mock = MagicMock(side_effect=self._fetch_func_template)
        store_func_mock = MagicMock(side_effect=self._store_func_template)
        mock_has_section_changed.return_value = True
        # when
        result = character.update_data_if_changed_or_forced(
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
        self.assertListEqual(result, ["alpha"])

    def test_should_not_store_data_when_not_changed(
        self, mock_has_section_changed, mock_update_section_content_hash
    ):
        # given
        character = create_memberaudit_character(1001)
        fetch_func_mock = MagicMock(side_effect=self._fetch_func_template)
        store_func_mock = MagicMock(side_effect=self._store_func_template)
        mock_has_section_changed.return_value = False
        # when
        character.update_data_if_changed_or_forced(
            section=character.UpdateSection.LOCATION,
            fetch_func=fetch_func_mock,
            store_func=store_func_mock,
            force_update=False,
        )
        # then
        self.assertTrue(fetch_func_mock.called)
        self.assertFalse(store_func_mock.called)
        self.assertFalse(mock_update_section_content_hash.called)

    def test_should_always_store_data_when_forced(
        self, mock_has_section_changed, mock_update_section_content_hash
    ):
        # given
        character = create_memberaudit_character(1001)
        fetch_func_mock = MagicMock(side_effect=self._fetch_func_template)
        store_func_mock = MagicMock(side_effect=self._store_func_template)
        mock_has_section_changed.return_value = False
        # when
        character.update_data_if_changed_or_forced(
            section=character.UpdateSection.LOCATION,
            fetch_func=fetch_func_mock,
            store_func=store_func_mock,
            force_update=True,
        )
        # then
        self.assertTrue(fetch_func_mock.called)
        self.assertTrue(store_func_mock.called)
        self.assertTrue(mock_update_section_content_hash.called)

    def test_should_not_store_anything_when_esi_returns_http_500_and_return_none(
        self, mock_has_section_changed, mock_update_section_content_hash
    ):
        # given
        character = create_memberaudit_character(1001)
        fetch_func_mock = MagicMock(side_effect=build_http_error(500, "Test exception"))
        store_func_mock = MagicMock(side_effect=self._store_func_template)
        mock_has_section_changed.side_effect = RuntimeError("Should not be called")
        # when
        result = character.update_data_if_changed_or_forced(
            section=character.UpdateSection.LOCATION,
            fetch_func=fetch_func_mock,
            store_func=store_func_mock,
            force_update=False,
        )
        # then
        self.assertTrue(fetch_func_mock.called)
        self.assertFalse(store_func_mock.called)
        self.assertFalse(mock_update_section_content_hash.called)
        self.assertIsNone(result)

    def test_should_store_data_when_changed_and_use_hash_num(
        self, mock_has_section_changed, mock_update_section_content_hash
    ):
        # given
        character = create_memberaudit_character(1001)
        fetch_func_mock = MagicMock(side_effect=self._fetch_func_template)
        store_func_mock = MagicMock(side_effect=self._store_func_template)
        mock_has_section_changed.return_value = True
        # when
        character.update_data_if_changed_or_forced(
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
