from unittest.mock import patch

from allianceauth.tests.auth_utils import AuthUtils
from app_utils.testdata_factories import (
    EveAllianceInfoFactory,
    EveCharacterFactory,
    EveCorporationInfoFactory,
    UserMainFactory,
)
from app_utils.testing import NoSocketsTestCase

from memberaudit.models import Character
from memberaudit.tests.testdata.factories_2 import (
    CharacterFactory,
    CharacterOrphanFactory,
    CharacterUpdateStatusFactory,
    UserMainBasicAccessFactory,
)
from memberaudit.tests.utils import extract

MODELS_PATH = "memberaudit.models.characters"


class TestCharacterManager_OwnedByUser(NoSocketsTestCase):
    def test_should_return_characters_owner_by_user_only(self):
        # given
        user = UserMainBasicAccessFactory()
        character = CharacterFactory(user=user)
        CharacterFactory()

        # when
        got = Character.objects.owned_by_user(user)

        # then
        want = [character]
        self.assertCountEqual(got, want)

    def test_should_return_empty_when_user_has_no_characters(self):
        # given
        user = UserMainFactory()
        CharacterFactory()

        # when
        got = Character.objects.owned_by_user(user)

        # then
        self.assertFalse(got)


# Includes testing of Character.calc_total_update_status() to ensure they are in sync
class TestCharacterAnnotateTotalUpdateStatus(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = UserMainBasicAccessFactory()

    @patch(MODELS_PATH + ".MEMBERAUDIT_FEATURE_ROLES_ENABLED", True)
    def test_should_annotate_ok(self):
        # given
        character = CharacterFactory(user=self.user)
        for section in Character.UpdateSection:
            CharacterUpdateStatusFactory(character=character, section=section)
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
        character = CharacterFactory(user=self.user)
        for section in Character.UpdateSection.enabled_sections():
            CharacterUpdateStatusFactory(character=character, section=section)
        CharacterUpdateStatusFactory(
            character=character,
            is_success=False,
            section=Character.UpdateSection.ROLES,
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
        character = CharacterFactory(user=self.user)
        CharacterUpdateStatusFactory(
            character=character,
            section=Character.UpdateSection.ASSETS,
            is_success=False,
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
        character = CharacterFactory(user=self.user)
        sections_to_update = [
            obj
            for obj in Character.UpdateSection
            if obj != Character.UpdateSection.ASSETS
        ]
        for section in sections_to_update:
            CharacterUpdateStatusFactory(character=character, section=section)
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
        character = CharacterFactory(user=self.user)
        for section in Character.UpdateSection:
            if section == Character.UpdateSection.ASSETS:
                CharacterUpdateStatusFactory(
                    character=character, section=section, is_success=None
                )
            else:
                CharacterUpdateStatusFactory(character=character, section=section)
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
        character = CharacterFactory(user=self.user, is_disabled=True)
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
        character = CharacterFactory(user=self.user)
        CharacterUpdateStatusFactory(
            character=character,
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
        character = CharacterFactory(user=self.user)
        CharacterUpdateStatusFactory(
            character=character,
            section=Character.UpdateSection.ASSETS,
            is_success=False,
            has_token_error=True,
        )
        CharacterUpdateStatusFactory(
            character=character,
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


class TestCharacterManager_UserHasScope(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.alliance_3001 = EveAllianceInfoFactory()
        cls.corporation_2001 = EveCorporationInfoFactory(alliance=cls.alliance_3001)
        cls.corporation_2002 = EveCorporationInfoFactory(alliance=cls.alliance_3001)
        cls.member_state = AuthUtils.get_member_state()
        cls.member_state.member_alliances.add(cls.alliance_3001)

        cls.user_1001 = UserMainFactory(
            main_character__character=EveCharacterFactory(
                corporation=cls.corporation_2001
            ),
            permissions__=["memberaudit.basic_access"],
        )
        cls.character_1001 = CharacterFactory(id=1001, user=cls.user_1001, is_main=True)
        cls.character_1110 = CharacterFactory(
            id=1110, user=cls.user_1001, is_main=False
        )
        cls.character_1121 = CharacterFactory(
            id=1121, user=cls.user_1001, is_main=False
        )

        user_1002 = UserMainFactory(
            main_character__character=EveCharacterFactory(
                corporation=cls.corporation_2001
            ),
            permissions__=["memberaudit.basic_access"],
        )
        cls.character_1002 = CharacterFactory(id=1002, user=user_1002, is_main=True)
        cls.character_1103 = CharacterFactory(id=1103, user=user_1002, is_main=False)

        user_1003 = UserMainFactory(
            main_character__character=EveCharacterFactory(
                corporation=cls.corporation_2002
            ),
            permissions__=["memberaudit.basic_access"],
        )
        cls.character_1003 = CharacterFactory(id=1003, user=user_1003)

        cls.character_1101 = CharacterFactory(id=1101)

        user_1102 = UserMainFactory(permissions__=["memberaudit.basic_access"])
        cls.character_1102 = CharacterFactory(id=1102, user=user_1102)

        cls.character_1111 = CharacterFactory(id=1111)

        cls.character_1122 = CharacterFactory(id=1122)

    def test_user_owning_character_has_scope(self):
        """
        when user is the owner of characters
        then include those characters only
        """
        # given
        got = Character.objects.user_has_scope(
            user=self.character_1001.eve_character.character_ownership.user
        )

        # then
        want = [self.character_1001, self.character_1110, self.character_1121]
        self.assertCountEqual(got, want)

    def test_view_own_corporation_1(self):
        """
        when user has scope to view own corporation
        then include characters of corporations members (mains + alts)
        """
        # given
        user = UserMainFactory(
            main_character__character=EveCharacterFactory(
                corporation=self.corporation_2001
            ),
            permissions__=[
                "memberaudit.basic_access",
                "memberaudit.view_same_corporation",
            ],
        )
        character = CharacterFactory(user=user)

        # when
        got = Character.objects.user_has_scope(user=user)

        # then
        want = [
            character,
            self.character_1001,
            self.character_1002,
            self.character_1103,
            self.character_1110,
            self.character_1121,
        ]
        self.assertCountEqual(got, want)

    def test_view_own_alliance_1(self):
        """
        when user has scope to view own alliance
        then include characters of alliance members (mains + alts)
        """
        # given
        user = UserMainFactory(
            main_character__character=EveCharacterFactory(
                corporation=self.corporation_2001
            ),
            permissions__=[
                "memberaudit.basic_access",
                "memberaudit.view_same_alliance",
            ],
        )
        character = CharacterFactory(user=user)

        # when
        got = Character.objects.user_has_scope(user=user)

        # then
        want = [
            character,
            self.character_1001,
            self.character_1110,
            self.character_1121,
            self.character_1002,
            self.character_1003,
            self.character_1103,
        ]
        self.assertCountEqual(got, want)

    def test_view_own_alliance_2(self):
        """
        when user has permission to view own alliance
        and does not belong to any alliance
        then do not include any alliance characters
        """
        user = UserMainFactory(
            main_character__character=EveCharacterFactory(corporation__alliance=None),
            permissions__=[
                "memberaudit.basic_access",
                "memberaudit.view_same_alliance",
            ],
        )
        character = CharacterFactory(user=user)

        # when
        got = Character.objects.user_has_scope(user=user)

        # then
        want = [character]
        self.assertCountEqual(got, want)

    def test_view_everything_1(self):
        """
        when user has scope to view everything
        then include all characters
        """
        # given
        user = UserMainFactory(
            permissions__=[
                "memberaudit.basic_access",
                "memberaudit.view_everything",
                "memberaudit.characters_access",
            ],
        )
        character = CharacterFactory(user=user)

        # when
        got = Character.objects.user_has_scope(user=user)

        # then
        want = [
            character,
            self.character_1001,
            self.character_1002,
            self.character_1003,
            self.character_1101,
            self.character_1102,
            self.character_1103,
            self.character_1110,
            self.character_1111,
            self.character_1121,
            self.character_1122,
        ]
        self.assertCountEqual(got, want)


class TestCharacterManager_UserHasAccess(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.alliance_3001 = EveAllianceInfoFactory()
        cls.corporation_2001 = EveCorporationInfoFactory(alliance=cls.alliance_3001)
        cls.corporation_2002 = EveCorporationInfoFactory(alliance=cls.alliance_3001)
        cls.member_state = AuthUtils.get_member_state()
        cls.member_state.member_alliances.add(cls.alliance_3001)

        cls.user_1001 = UserMainFactory(
            main_character__character=EveCharacterFactory(
                corporation=cls.corporation_2001
            ),
            permissions__=["memberaudit.basic_access"],
        )
        cls.character_1001 = CharacterFactory(id=1001, user=cls.user_1001, is_main=True)
        cls.character_1110 = CharacterFactory(
            id=1110, user=cls.user_1001, is_main=False
        )
        cls.character_1121 = CharacterFactory(
            id=1121, user=cls.user_1001, is_main=False
        )

        user_1002 = UserMainFactory(
            main_character__character=EveCharacterFactory(
                corporation=cls.corporation_2001
            ),
            permissions__=["memberaudit.basic_access", "memberaudit.share_characters"],
        )
        cls.character_1002 = CharacterFactory(
            id=1002, user=user_1002, is_main=True, is_shared=True
        )
        cls.character_1103 = CharacterFactory(id=1103, user=user_1002, is_main=False)

        user_1003 = UserMainFactory(
            main_character__character=EveCharacterFactory(
                corporation=cls.corporation_2002
            ),
            permissions__=["memberaudit.basic_access"],
        )
        cls.character_1003 = CharacterFactory(id=1003, user=user_1003)

        cls.character_1101 = CharacterFactory(id=1101)

        user_1102 = UserMainFactory(
            permissions__=["memberaudit.basic_access", "memberaudit.share_characters"]
        )
        cls.character_1102 = CharacterFactory(id=1102, user=user_1102, is_shared=True)

        cls.character_1111 = CharacterFactory(id=1111)

        cls.character_1122 = CharacterOrphanFactory(id=1122)

    def test_should_return_own_characters_only_when_user_has_basic_access(self):
        # when
        got = Character.objects.user_has_access(user=self.user_1001)

        # then
        want = [self.character_1001, self.character_1110, self.character_1121]
        self.assertCountEqual(got, want)

    def test_view_own_corporation_1(self):
        """
        when user has permission to view own corporation and not characters_access
        then include own characters only
        """
        # given
        user = UserMainFactory(
            main_character__character=EveCharacterFactory(
                corporation=self.corporation_2001
            ),
            permissions__=[
                "memberaudit.basic_access",
                "memberaudit.view_same_corporation",
            ],
        )
        character = CharacterFactory(user=user)

        # when
        got = Character.objects.user_has_access(user=user)

        # then
        want = [character]
        self.assertCountEqual(got, want)

    def test_view_own_corporation_2(self):
        """
        when user has permission to view own corporation and characters_access
        then include characters of corporations members (mains + alts)
        """
        # given
        user = UserMainFactory(
            main_character__character=EveCharacterFactory(
                corporation=self.corporation_2001
            ),
            permissions__=[
                "memberaudit.basic_access",
                "memberaudit.view_same_corporation",
                "memberaudit.characters_access",
            ],
        )
        character = CharacterFactory(user=user)

        # when
        got = Character.objects.user_has_access(user=user)

        # then
        want = [
            character,
            self.character_1001,
            self.character_1002,
            self.character_1103,
            self.character_1110,
            self.character_1121,
        ]
        self.assertCountEqual(got, want)

    def test_view_own_alliance_1a(self):
        """
        when user has permission to view own alliance and not characters_access
        then include own character only
        """
        # given
        user = UserMainFactory(
            main_character__character=EveCharacterFactory(
                corporation=self.corporation_2001
            ),
            permissions__=[
                "memberaudit.basic_access",
                "memberaudit.view_same_alliance",
            ],
        )
        character = CharacterFactory(user=user)

        # when
        got = Character.objects.user_has_access(user=user)

        # then
        want = [character]
        self.assertCountEqual(got, want)

    def test_view_own_alliance_1b(self):
        """
        when user has permission to view own alliance and characters_access
        then include characters of alliance members (mains + alts)
        """
        # given
        user = UserMainFactory(
            main_character__character=EveCharacterFactory(
                corporation=self.corporation_2001
            ),
            permissions__=[
                "memberaudit.basic_access",
                "memberaudit.view_same_alliance",
                "memberaudit.characters_access",
            ],
        )
        character = CharacterFactory(user=user)

        # when
        got = Character.objects.user_has_access(user=user)

        # then
        want = [
            character,
            self.character_1001,
            self.character_1110,
            self.character_1121,
            self.character_1002,
            self.character_1003,
            self.character_1103,
        ]
        self.assertCountEqual(got, want)

    def test_view_own_alliance_2(self):
        """
        when user has permission to view own alliance and characters_access
        and does not belong to any alliance
        then do not include any alliance characters
        """
        user = UserMainFactory(
            main_character__character=EveCharacterFactory(corporation__alliance=None),
            permissions__=[
                "memberaudit.basic_access",
                "memberaudit.view_same_alliance",
                "memberaudit.characters_access",
            ],
        )
        character = CharacterFactory(user=user)

        # when
        got = Character.objects.user_has_access(user=user)

        # then
        want = [character]
        self.assertCountEqual(got, want)

    def test_view_everything_1(self):
        """
        when user has permission to view everything and no characters_access
        then include own character only
        """
        # given
        user = UserMainFactory(
            permissions__=[
                "memberaudit.basic_access",
                "memberaudit.view_everything",
            ],
        )
        character = CharacterFactory(user=user)

        # when
        got = Character.objects.user_has_access(user=user)

        # then
        want = [character]
        self.assertCountEqual(got, want)

    def test_view_everything_2(self):
        """
        when user has permission to view everything and characters_access
        then include all characters including orphans
        """
        # given
        user = UserMainFactory(
            permissions__=[
                "memberaudit.basic_access",
                "memberaudit.view_everything",
                "memberaudit.characters_access",
            ],
        )
        character = CharacterFactory(user=user)

        # when
        got = Character.objects.user_has_access(user=user)

        # then
        want = [
            character,
            self.character_1001,
            self.character_1002,
            self.character_1003,
            self.character_1101,
            self.character_1102,
            self.character_1103,
            self.character_1110,
            self.character_1111,
            self.character_1121,
            self.character_1122,
        ]
        self.assertCountEqual(got, want)

    def test_recruiter_access(self):
        """
        when user has recruiter permission
        then include own character plus shared characters from member and guest state
        """
        # given
        user = UserMainFactory(
            main_character__character=EveCharacterFactory(
                corporation__alliance=self.alliance_3001
            ),
            permissions__=[
                "memberaudit.basic_access",
                "memberaudit.view_shared_characters",
            ],
        )
        character = CharacterFactory(user=user)

        # when
        got = Character.objects.user_has_access(user=user)

        # then
        want = [
            character,
            self.character_1002,  # member
            self.character_1102,  # guest
        ]
        self.assertCountEqual(got, want)

    def test_recruiter_should_loose_access_once_recruit_looses_share_permission(self):
        # given
        user = UserMainFactory(
            main_character__character=EveCharacterFactory(
                corporation__alliance=self.alliance_3001
            ),
            permissions__=[
                "memberaudit.basic_access",
                "memberaudit.view_shared_characters",
            ],
        )
        CharacterFactory(user=user)
        user_1107 = UserMainFactory(permissions__=["memberaudit.basic_access"])
        character_1107 = CharacterFactory(id=1107, user=user_1107, is_shared=True)

        # when
        got = Character.objects.user_has_access(user=user)

        # then
        self.assertNotIn(character_1107, got)

        # # given
        # character_1107 = CharacterFactory(id=1107, is_shared=True)
        # user = self.character_1001.eve_character.character_ownership.user
        # user = AuthUtils.add_permission_to_user_by_name(
        #     "memberaudit.view_shared_characters", user
        # )
        # # when
        # result_qs = Character.objects.user_has_access(user=user)
        # self.assertNotIn(1107, extract(result_qs, "eve_character__character_id"))


class TestCharacterManager_CharactersOfUserToRegisterCount(NoSocketsTestCase):
    def test_should_return_zero_when_no_unregistered(self):
        # given
        user = UserMainBasicAccessFactory()
        CharacterFactory(user=user)

        # when
        result = Character.objects.characters_of_user_to_register_count(user)

        # then
        self.assertEqual(result, 0)

    def test_should_return_count_including_unregistered(self):
        # given
        user = UserMainBasicAccessFactory()
        # when
        result = Character.objects.characters_of_user_to_register_count(user)
        # then
        self.assertEqual(result, 1)

    @patch(MODELS_PATH + ".MEMBERAUDIT_FEATURE_ROLES_ENABLED", True)
    def test_should_return_count_including_registered_with_token_error(self):
        # given
        user = UserMainBasicAccessFactory()
        character = CharacterFactory(user=user)
        CharacterUpdateStatusFactory(
            character=character,
            section=Character.UpdateSection.ASSETS,
            is_success=False,
            has_token_error=True,
            error_message="TokenError 1",
        )
        CharacterUpdateStatusFactory(
            character=character,
            section=Character.UpdateSection.CONTRACTS,
            is_success=False,
            error_message="TokenError 2",
        )

        # when
        result = Character.objects.characters_of_user_to_register_count(user)

        # then
        self.assertEqual(result, 1)

    @patch(MODELS_PATH + ".MEMBERAUDIT_FEATURE_ROLES_ENABLED", False)
    def test_should_return_count_not_including_token_errors_for_disabled_sections(self):
        # given
        user = UserMainBasicAccessFactory()
        character = CharacterFactory(user=user)
        CharacterUpdateStatusFactory(
            character=character,
            section=Character.UpdateSection.ROLES,
            is_success=False,
            has_token_error=True,
            error_message="TokenError 1",
        )
        # when
        result = Character.objects.characters_of_user_to_register_count(user)

        # then
        self.assertEqual(result, 0)

    @patch(MODELS_PATH + ".MEMBERAUDIT_FEATURE_ROLES_ENABLED", False)
    def test_should_return_count_disabled_characters(self):
        # given
        user = UserMainBasicAccessFactory()
        character = CharacterFactory(user=user, is_disabled=True)
        CharacterUpdateStatusFactory(
            character=character,
            section=Character.UpdateSection.ASSETS,
            is_success=False,
            has_token_error=True,
            error_message="TokenError 1",
        )

        # when
        result = Character.objects.characters_of_user_to_register_count(user)

        # then
        self.assertEqual(result, 1)

    @patch(MODELS_PATH + ".MEMBERAUDIT_FEATURE_ROLES_ENABLED", False)
    def test_should_not_count_disabled_and_token_errors_twice(self):
        # given
        user = UserMainBasicAccessFactory()
        CharacterFactory(user=user, is_disabled=True)

        # when
        result = Character.objects.characters_of_user_to_register_count(user)

        # then
        self.assertEqual(result, 1)


class TestCharacterManager_DisableCharactersWithNoOwner(NoSocketsTestCase):
    def test_should_disable_orphans(self):
        # given
        character = CharacterFactory()
        orphan_1 = CharacterOrphanFactory()
        orphan_2 = CharacterOrphanFactory()

        # when
        result = Character.objects.disable_characters_with_no_owner()

        # then
        self.assertEqual(result, 2)
        orphan_1.refresh_from_db()
        self.assertTrue(orphan_1.is_disabled)
        orphan_2.refresh_from_db()
        self.assertTrue(orphan_2.is_disabled)
        self.assertFalse(character.is_disabled)

    def test_should_ignore_already_disables_orphans(self):
        # given
        character = CharacterFactory()
        orphan_disabled = CharacterOrphanFactory(is_disabled=True)
        orphan_enabled = CharacterOrphanFactory(is_disabled=False)

        # when
        result = Character.objects.disable_characters_with_no_owner()

        # then
        self.assertEqual(result, 1)
        orphan_disabled.refresh_from_db()
        self.assertTrue(orphan_disabled.is_disabled)
        orphan_enabled.refresh_from_db()
        self.assertTrue(orphan_enabled.is_disabled)
        self.assertFalse(character.is_disabled)

    def test_should_return_zero_when_nothing_to_disable(self):
        # given
        character = CharacterFactory()
        orphan_disabled = CharacterOrphanFactory(is_disabled=True)

        # when
        result = Character.objects.disable_characters_with_no_owner()

        # then
        self.assertEqual(result, 0)
        orphan_disabled.refresh_from_db()
        self.assertTrue(orphan_disabled.is_disabled)
        self.assertFalse(character.is_disabled)


class TestCharacterUpdateStatusManager_FilterEnabledSections(NoSocketsTestCase):
    @patch(MODELS_PATH + ".MEMBERAUDIT_FEATURE_ROLES_ENABLED", True)
    def test_should_return_enabled_sections_only_1(self):
        # given
        character = CharacterFactory()
        CharacterUpdateStatusFactory(
            character=character, section=Character.UpdateSection.ASSETS
        )
        CharacterUpdateStatusFactory(
            character=character, section=Character.UpdateSection.ROLES
        )

        # when
        result = character.update_status_set.filter_enabled_sections()

        # then
        expected = {Character.UpdateSection.ASSETS, Character.UpdateSection.ROLES}
        sections = extract(result, "section")
        self.assertSetEqual(sections, expected)

    @patch(MODELS_PATH + ".MEMBERAUDIT_FEATURE_ROLES_ENABLED", False)
    def test_should_return_enabled_sections_only_2(self):
        # given
        character = CharacterFactory()
        CharacterUpdateStatusFactory(
            character=character, section=Character.UpdateSection.ASSETS
        )
        CharacterUpdateStatusFactory(
            character=character, section=Character.UpdateSection.ROLES
        )
        # when
        result = character.update_status_set.filter_enabled_sections()
        # then
        expected = {Character.UpdateSection.ASSETS}
        sections = extract(result, "section")
        self.assertSetEqual(sections, expected)
