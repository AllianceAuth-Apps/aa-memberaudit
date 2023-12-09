from unittest.mock import patch

from django.test import TestCase

from allianceauth.eveonline.models import EveAllianceInfo, EveCharacter
from allianceauth.tests.auth_utils import AuthUtils

from memberaudit.models import Character
from memberaudit.tests.testdata.factories import (
    create_character,
    create_character_from_user,
    create_character_update_status,
)
from memberaudit.tests.testdata.load_entities import load_entities
from memberaudit.tests.utils import (
    add_auth_character_to_user,
    add_memberaudit_character_to_user,
    create_memberaudit_character,
    create_user_from_evecharacter_with_access,
)

MODELS_PATH = "memberaudit.models.characters"


class TestCharacterQuerySet(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities()

    def test_should_return_set_of_eve_character_ids(self):
        # given
        create_memberaudit_character(1001)
        create_memberaudit_character(1002)
        # when/then
        self.assertSetEqual(Character.objects.all().eve_character_ids(), {1001, 1002})

    def test_should_return_characters_owner_by_user_only(self):
        # given
        character_1001 = create_memberaudit_character(1001)
        user = character_1001.character_ownership.user
        create_memberaudit_character(1002)
        # when
        result = Character.objects.owned_by_user(user)
        # then
        character_ids = {
            obj.character_ownership.character.character_id for obj in result
        }
        self.assertSetEqual(character_ids, {1001})

    def test_should_return_no_characters(self):
        # given
        user = AuthUtils.create_user("dummy")
        create_memberaudit_character(1001)
        # when
        result = Character.objects.owned_by_user(user)
        # then
        character_ids = {
            obj.character_ownership.character.character_id for obj in result
        }
        self.assertSetEqual(character_ids, set())


# Includes testing of Character.calc_total_update_status() to ensure they are in sync
class TestCharacterAnnotateTotalUpdateStatus(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities()
        cls.user, _ = create_user_from_evecharacter_with_access(1001)

    @patch(MODELS_PATH + ".MEMBERAUDIT_FEATURE_ROLES_ENABLED", True)
    def test_should_annotate_ok(self):
        # given
        character = create_character_from_user(self.user)
        for section in Character.UpdateSection:
            create_character_update_status(character, section=section)
        # when/then
        self.assertEqual(
            character.calc_total_update_status(), Character.TotalUpdateStatus.OK
        )
        # when
        qs = Character.objects.annotate_total_update_status()
        # then
        obj = qs.first()
        self.assertEqual(obj.total_update_status, Character.TotalUpdateStatus.OK)

    @patch(MODELS_PATH + ".MEMBERAUDIT_FEATURE_ROLES_ENABLED", False)
    def test_should_annotate_ok_when_all_enabled_sections_are_ok(self):
        # given
        character = create_character_from_user(self.user)
        for section in Character.UpdateSection.enabled_sections():
            create_character_update_status(character, section=section)
        create_character_update_status(
            character=character, is_success=False, section=Character.UpdateSection.ROLES
        )
        # when/then
        self.assertEqual(
            character.calc_total_update_status(), Character.TotalUpdateStatus.OK
        )
        # when
        qs = Character.objects.annotate_total_update_status()
        # then
        obj = qs.first()
        self.assertEqual(obj.total_update_status, Character.TotalUpdateStatus.OK)

    @patch(MODELS_PATH + ".MEMBERAUDIT_FEATURE_ROLES_ENABLED", True)
    def test_should_annotate_error(self):
        # given
        character = create_character_from_user(self.user)
        create_character_update_status(
            character, section=Character.UpdateSection.ASSETS, is_success=False
        )
        # when/then
        self.assertEqual(
            character.calc_total_update_status(), Character.TotalUpdateStatus.ERROR
        )
        # when
        qs = Character.objects.annotate_total_update_status()
        # then
        obj = qs.first()
        self.assertEqual(obj.total_update_status, Character.TotalUpdateStatus.ERROR)

    @patch(MODELS_PATH + ".MEMBERAUDIT_FEATURE_ROLES_ENABLED", True)
    def test_should_annotate_incomplete(self):
        # given
        character = create_character_from_user(self.user)
        sections_to_update = [
            obj
            for obj in Character.UpdateSection
            if obj != Character.UpdateSection.ASSETS
        ]
        for section in sections_to_update:
            create_character_update_status(character, section=section)
        # when/then
        self.assertEqual(
            character.calc_total_update_status(), Character.TotalUpdateStatus.INCOMPLETE
        )
        # when
        qs = Character.objects.annotate_total_update_status()
        # then
        obj = qs.first()
        self.assertEqual(
            obj.total_update_status, Character.TotalUpdateStatus.INCOMPLETE
        )

    @patch(MODELS_PATH + ".MEMBERAUDIT_FEATURE_ROLES_ENABLED", True)
    def test_should_annotate_in_progress(self):
        # given
        character = create_character_from_user(self.user)
        for section in Character.UpdateSection:
            if section == Character.UpdateSection.ASSETS:
                create_character_update_status(
                    character, section=section, is_success=None
                )
            else:
                create_character_update_status(character, section=section)
        # when/then
        self.assertEqual(
            character.calc_total_update_status(),
            Character.TotalUpdateStatus.IN_PROGRESS,
        )
        # when
        qs = Character.objects.annotate_total_update_status()
        # then
        obj = qs.first()
        self.assertEqual(
            obj.total_update_status, Character.TotalUpdateStatus.IN_PROGRESS
        )

    def test_should_annotate_disabled(self):
        # given
        character = create_character_from_user(self.user, is_disabled=True)
        # when/then
        self.assertEqual(
            character.calc_total_update_status(), Character.TotalUpdateStatus.DISABLED
        )
        # when
        qs = Character.objects.annotate_total_update_status()
        # then
        obj = qs.first()
        self.assertEqual(obj.total_update_status, Character.TotalUpdateStatus.DISABLED)

    @patch(MODELS_PATH + ".MEMBERAUDIT_FEATURE_ROLES_ENABLED", True)
    def test_should_annotate_limited_token_when_one_token_issue_only(self):
        # given
        character = create_character_from_user(self.user)
        create_character_update_status(
            character,
            section=Character.UpdateSection.ASSETS,
            is_success=False,
            has_token_error=True,
        )
        # when/then
        self.assertEqual(
            character.calc_total_update_status(),
            Character.TotalUpdateStatus.LIMITED_TOKEN,
        )
        # when
        qs = Character.objects.annotate_total_update_status()
        # then
        obj = qs.first()
        self.assertEqual(
            obj.total_update_status, Character.TotalUpdateStatus.LIMITED_TOKEN
        )

    @patch(MODELS_PATH + ".MEMBERAUDIT_FEATURE_ROLES_ENABLED", True)
    def test_should_annotate_error_when_several_token_issues(self):
        # given
        character = create_character_from_user(self.user)
        create_character_update_status(
            character,
            section=Character.UpdateSection.ASSETS,
            is_success=False,
            has_token_error=True,
        )
        create_character_update_status(
            character,
            section=Character.UpdateSection.LOCATION,
            is_success=False,
            has_token_error=True,
        )
        # when/then
        self.assertEqual(
            character.calc_total_update_status(), Character.TotalUpdateStatus.ERROR
        )
        # when
        qs = Character.objects.annotate_total_update_status()
        # then
        obj = qs.first()
        self.assertEqual(obj.total_update_status, Character.TotalUpdateStatus.ERROR)


class TestCharacterUserHasScope(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities()
        # main character with alts
        cls.character_1001 = create_memberaudit_character(1001)  # main
        cls.character_1110 = add_memberaudit_character_to_user(  # alt
            cls.character_1001.eve_character.character_ownership.user, 1110
        )
        cls.character_1121 = add_memberaudit_character_to_user(  # alt
            cls.character_1001.eve_character.character_ownership.user, 1121
        )
        # main character with alts
        cls.character_1002 = create_memberaudit_character(1002)
        cls.character_1002.is_shared = True
        cls.character_1002.save()
        cls.character_1103 = add_memberaudit_character_to_user(
            cls.character_1002.eve_character.character_ownership.user, 1103
        )
        # main characters
        cls.character_1003 = create_memberaudit_character(1003)
        cls.character_1101 = create_memberaudit_character(1101)
        cls.character_1102 = create_memberaudit_character(1102)
        cls.character_1102.is_shared = True
        cls.character_1102.save()
        cls.character_1111 = create_memberaudit_character(1111)
        cls.character_1122 = create_memberaudit_character(1122)
        cls.member_state = AuthUtils.get_member_state()
        cls.member_state.member_alliances.add(
            EveAllianceInfo.objects.get(alliance_id=3001)
        )

    def test_user_owning_character_has_scope(self):
        """
        when user is the owner of characters
        then include those characters only
        """
        result_qs = Character.objects.user_has_scope(
            user=self.character_1001.eve_character.character_ownership.user
        )
        self.assertSetEqual(result_qs.eve_character_ids(), {1001, 1110, 1121})

    def test_view_own_corporation_1(self):
        """
        when user has scope to view own corporation
        then include characters of corporations members (mains + alts)
        """
        user = self.character_1001.eve_character.character_ownership.user
        user = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_same_corporation", user
        )
        result_qs = Character.objects.user_has_scope(user=user)
        self.assertSetEqual(
            result_qs.eve_character_ids(), {1001, 1110, 1121, 1002, 1103}
        )

    def test_view_own_alliance_1(self):
        """
        when user has scope to view own alliance
        then include characters of alliance members (mains + alts)
        """
        user = self.character_1001.eve_character.character_ownership.user
        user = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_same_alliance", user
        )
        result_qs = Character.objects.user_has_scope(user=user)
        self.assertSetEqual(
            result_qs.eve_character_ids(), {1001, 1110, 1121, 1002, 1003, 1103}
        )

    def test_view_own_alliance_2(self):
        """
        when user has permission to view own alliance
        and does not belong to any alliance
        then do not include any alliance characters
        """
        user = self.character_1102.eve_character.character_ownership.user
        user = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_same_alliance", user
        )
        result_qs = Character.objects.user_has_scope(user=user)
        self.assertSetEqual(result_qs.eve_character_ids(), {1102})

    def test_view_everything_1(self):
        """
        when user has scope to view everything
        then include all characters
        """
        user = self.character_1001.eve_character.character_ownership.user
        user = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_everything", user
        )
        result_qs = Character.objects.user_has_scope(user=user)
        self.assertSetEqual(
            result_qs.eve_character_ids(),
            {1001, 1002, 1003, 1101, 1102, 1103, 1110, 1111, 1121, 1122},
        )


class TestCharacterUserHasAccess(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities()
        # main character with alts
        cls.character_1001 = create_memberaudit_character(1001)  # main
        cls.character_1110 = add_memberaudit_character_to_user(  # alt
            cls.character_1001.eve_character.character_ownership.user, 1110
        )
        cls.character_1121 = add_memberaudit_character_to_user(  # alt
            cls.character_1001.eve_character.character_ownership.user, 1121
        )
        # main character with alts
        cls.character_1002 = create_memberaudit_character(1002)
        cls.character_1002.is_shared = True
        cls.character_1002.save()
        AuthUtils.add_permission_to_user_by_name(
            "memberaudit.share_characters",
            cls.character_1002.eve_character.character_ownership.user,
        )
        cls.character_1103 = add_memberaudit_character_to_user(
            cls.character_1002.eve_character.character_ownership.user, 1103
        )
        # main characters
        cls.character_1003 = create_memberaudit_character(1003)
        cls.character_1101 = create_memberaudit_character(1101)
        cls.character_1102 = create_memberaudit_character(1102)
        cls.character_1102.is_shared = True
        cls.character_1102.save()
        AuthUtils.add_permission_to_user_by_name(
            "memberaudit.share_characters",
            cls.character_1102.eve_character.character_ownership.user,
        )
        cls.character_1111 = create_memberaudit_character(1111)
        cls.character_1122 = create_memberaudit_character(1122)
        cls.member_state = AuthUtils.get_member_state()
        cls.member_state.member_alliances.add(
            EveAllianceInfo.objects.get(alliance_id=3001)
        )

    def test_user_owning_character_has_access(self):
        """
        when user is the owner of characters
        then include those characters only
        """
        result_qs = Character.objects.user_has_access(
            user=self.character_1001.eve_character.character_ownership.user
        )
        self.assertSetEqual(result_qs.eve_character_ids(), {1001, 1110, 1121})

    def test_view_own_corporation_1(self):
        """
        when user has permission to view own corporation and not characters_access
        then include own characters only
        """
        user = self.character_1001.eve_character.character_ownership.user
        user = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_same_corporation", user
        )
        result_qs = Character.objects.user_has_access(user=user)
        self.assertSetEqual(result_qs.eve_character_ids(), {1001, 1110, 1121})

    def test_view_own_corporation_2(self):
        """
        when user has permission to view own corporation and characters_access
        then include characters of corporations members (mains + alts)
        """
        user = self.character_1001.eve_character.character_ownership.user
        user = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_same_corporation", user
        )
        user = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.characters_access", user
        )
        result_qs = Character.objects.user_has_access(user=user)
        self.assertSetEqual(
            result_qs.eve_character_ids(), {1001, 1110, 1121, 1002, 1103}
        )

    def test_view_own_alliance_1a(self):
        """
        when user has permission to view own alliance and not characters_access
        then include own character only
        """
        user = self.character_1001.eve_character.character_ownership.user
        user = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_same_alliance", user
        )
        result_qs = Character.objects.user_has_access(user=user)
        self.assertSetEqual(result_qs.eve_character_ids(), {1001, 1110, 1121})

    def test_view_own_alliance_1b(self):
        """
        when user has permission to view own alliance and characters_access
        then include characters of alliance members (mains + alts)
        """
        user = self.character_1001.eve_character.character_ownership.user
        user = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_same_alliance", user
        )
        user = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.characters_access", user
        )
        result_qs = Character.objects.user_has_access(user=user)
        self.assertSetEqual(
            result_qs.eve_character_ids(), {1001, 1110, 1121, 1002, 1003, 1103}
        )

    def test_view_own_alliance_2(self):
        """
        when user has permission to view own alliance and characters_access
        and does not belong to any alliance
        then do not include any alliance characters
        """
        user = self.character_1102.eve_character.character_ownership.user
        user = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_same_alliance", user
        )
        user = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.characters_access", user
        )
        result_qs = Character.objects.user_has_access(user=user)
        self.assertSetEqual(result_qs.eve_character_ids(), {1102})

    def test_view_everything_1(self):
        """
        when user has permission to view everything and no characters_access
        then include own character only
        """
        user = self.character_1001.eve_character.character_ownership.user
        user = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_everything", user
        )
        result_qs = Character.objects.user_has_access(user=user)
        self.assertSetEqual(result_qs.eve_character_ids(), {1001, 1110, 1121})

    def test_view_everything_2(self):
        """
        when user has permission to view everything and characters_access
        then include all characters
        """
        user = self.character_1001.eve_character.character_ownership.user
        user = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_everything", user
        )
        user = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.characters_access", user
        )
        result_qs = Character.objects.user_has_access(user=user)
        self.assertSetEqual(
            result_qs.eve_character_ids(),
            {1001, 1002, 1003, 1101, 1102, 1103, 1110, 1111, 1121, 1122},
        )

    def test_recruiter_access(self):
        """
        when user has recruiter permission
        then include own character plus shared characters from members
        """
        user = self.character_1001.eve_character.character_ownership.user
        user = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_shared_characters", user
        )
        result_qs = Character.objects.user_has_access(user=user)
        self.assertSetEqual(
            result_qs.eve_character_ids(), {1001, 1002, 1102, 1110, 1121}
        )

    def test_recruiter_should_loose_access_once_recruit_becomes_member(self):
        # given
        character_1107 = create_memberaudit_character(1107)
        character_1107.is_shared = True
        character_1107.save()
        user = self.character_1001.eve_character.character_ownership.user
        user = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_shared_characters", user
        )
        # when
        result_qs = Character.objects.user_has_access(user=user)
        self.assertNotIn(1107, result_qs.eve_character_ids())


class TestCharacterUnregisteredCharacterCount(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities()
        # main character with alts
        cls.character_1001 = create_memberaudit_character(1001)
        cls.user = cls.character_1001.character_ownership.user

    def test_should_return_zero_when_no_unregistered(self):
        # when
        result = Character.objects.characters_of_user_to_register_count(self.user)
        # then
        self.assertEqual(result, 0)

    def test_should_return_count_including_unregistered(self):
        # given
        add_auth_character_to_user(self.user, 1002)
        # when
        result = Character.objects.characters_of_user_to_register_count(self.user)
        # then
        self.assertEqual(result, 1)

    @patch(MODELS_PATH + ".MEMBERAUDIT_FEATURE_ROLES_ENABLED", True)
    def test_should_return_count_including_registered_with_token_error(self):
        # given
        character_1002 = add_memberaudit_character_to_user(self.user, 1002)
        create_character_update_status(
            character_1002,
            section=Character.UpdateSection.ASSETS,
            is_success=False,
            has_token_error=True,
            error_message="TokenError 1",
        )
        create_character_update_status(
            character_1002,
            section=Character.UpdateSection.CONTRACTS,
            is_success=False,
            error_message="TokenError 2",
        )
        # when
        result = Character.objects.characters_of_user_to_register_count(self.user)
        # then
        self.assertEqual(result, 1)

    @patch(MODELS_PATH + ".MEMBERAUDIT_FEATURE_ROLES_ENABLED", False)
    def test_should_return_count_not_including_token_errors_for_disabled_sections(self):
        # given
        character_1002 = add_memberaudit_character_to_user(self.user, 1002)
        create_character_update_status(
            character_1002,
            section=Character.UpdateSection.ROLES,
            is_success=False,
            has_token_error=True,
            error_message="TokenError 1",
        )
        # when
        result = Character.objects.characters_of_user_to_register_count(self.user)
        # then
        self.assertEqual(result, 0)

    @patch(MODELS_PATH + ".MEMBERAUDIT_FEATURE_ROLES_ENABLED", False)
    def test_should_return_count_disabled_characters(self):
        # given
        character_1002 = add_memberaudit_character_to_user(
            self.user, 1002, is_disabled=True
        )
        create_character_update_status(
            character_1002,
            section=Character.UpdateSection.ASSETS,
            is_success=False,
            has_token_error=True,
            error_message="TokenError 1",
        )

        # when
        result = Character.objects.characters_of_user_to_register_count(self.user)
        # then
        self.assertEqual(result, 1)

    @patch(MODELS_PATH + ".MEMBERAUDIT_FEATURE_ROLES_ENABLED", False)
    def test_should_not_count_disabled_and_token_errors_twice(self):
        # given
        add_memberaudit_character_to_user(self.user, 1002, is_disabled=True)
        # when
        result = Character.objects.characters_of_user_to_register_count(self.user)
        # then
        self.assertEqual(result, 1)


class TestCharacterDisableCharacterWithoutOwner(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities()
        cls.character = create_memberaudit_character(1001)

    def test_should_disable_orphans(self):
        # given
        orphan_1 = create_character(
            EveCharacter.objects.get(character_id=1121), is_disabled=False
        )
        orphan_2 = create_character(
            EveCharacter.objects.get(character_id=1111), is_disabled=False
        )
        # when
        result = Character.objects.disable_characters_with_no_owner()
        # then
        self.assertEqual(result, 2)
        orphan_1.refresh_from_db()
        self.assertTrue(orphan_1.is_disabled)
        orphan_2.refresh_from_db()
        self.assertTrue(orphan_2.is_disabled)
        self.assertFalse(self.character.is_disabled)

    def test_should_ignore_already_disables_orphans(self):
        # given
        orphan_disabled = create_character(
            EveCharacter.objects.get(character_id=1121), is_disabled=True
        )
        orphan_enabled = create_character(
            EveCharacter.objects.get(character_id=1111), is_disabled=False
        )
        # when
        result = Character.objects.disable_characters_with_no_owner()
        # then
        self.assertEqual(result, 1)
        orphan_disabled.refresh_from_db()
        self.assertTrue(orphan_disabled.is_disabled)
        orphan_enabled.refresh_from_db()
        self.assertTrue(orphan_enabled.is_disabled)
        self.assertFalse(self.character.is_disabled)

    def test_should_return_zero_when_nothing_to_disable(self):
        # given
        orphan_disabled = create_character(
            EveCharacter.objects.get(character_id=1121), is_disabled=True
        )
        # when
        result = Character.objects.disable_characters_with_no_owner()
        # then
        self.assertEqual(result, 0)
        orphan_disabled.refresh_from_db()
        self.assertTrue(orphan_disabled.is_disabled)
        self.assertFalse(self.character.is_disabled)


class TestCharacterUpdateStatusFilterEnabledSections(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities()
        cls.character_1001 = create_memberaudit_character(1001)

    @patch(MODELS_PATH + ".MEMBERAUDIT_FEATURE_ROLES_ENABLED", True)
    def test_should_return_enabled_sections_only_1(self):
        # given
        create_character_update_status(
            self.character_1001, section=Character.UpdateSection.ASSETS
        )
        create_character_update_status(
            self.character_1001, section=Character.UpdateSection.ROLES
        )
        # when
        result = self.character_1001.update_status_set.filter_enabled_sections()
        # then
        expected = {Character.UpdateSection.ASSETS, Character.UpdateSection.ROLES}
        sections = set(result.values_list("section", flat=True))
        self.assertSetEqual(sections, expected)

    @patch(MODELS_PATH + ".MEMBERAUDIT_FEATURE_ROLES_ENABLED", False)
    def test_should_return_enabled_sections_only_2(self):
        # given
        create_character_update_status(
            self.character_1001, section=Character.UpdateSection.ASSETS
        )
        create_character_update_status(
            self.character_1001, section=Character.UpdateSection.ROLES
        )
        # when
        result = self.character_1001.update_status_set.filter_enabled_sections()
        # then
        expected = {Character.UpdateSection.ASSETS}
        sections = set(result.values_list("section", flat=True))
        self.assertSetEqual(sections, expected)
