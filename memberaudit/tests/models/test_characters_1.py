import datetime as dt
import hashlib
import json
from unittest.mock import patch

from django.test import TestCase
from django.utils.timezone import now
from esi.errors import TokenError
from esi.models import Token
from eveuniverse.models import EveSolarSystem, EveType

from allianceauth.eveonline.models import EveCharacter
from app_utils.testing import NoSocketsTestCase, create_user_from_evecharacter

from memberaudit.errors import TokenDoesNotExist
from memberaudit.models import Character, CharacterUpdateStatus, Location
from memberaudit.tests.testdata.constants import EveTypeId
from memberaudit.tests.testdata.factories import (
    create_character,
    create_character_from_user,
    create_character_location,
    create_character_ship,
    create_character_skill,
    create_character_update_status,
    create_location_eve_solar_system,
    create_skill_set,
    create_skill_set_group,
    create_skill_set_skill,
)
from memberaudit.tests.testdata.load_entities import load_entities
from memberaudit.tests.testdata.load_eveuniverse import load_eveuniverse
from memberaudit.tests.testdata.load_locations import load_locations
from memberaudit.tests.utils import (
    add_memberaudit_character_to_user,
    create_memberaudit_character,
    create_user_from_evecharacter_with_access,
    scope_names_set,
)

MODELS_PATH = "memberaudit.models.characters"
MANAGERS_PATH = "memberaudit.managers"
TASKS_PATH = "memberaudit.tasks"


class TestCharacter(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        load_entities()
        cls.character_1001 = create_memberaudit_character(1001)

    def test_user_should_produce_str(self):
        # when/then
        self.assertTrue(str(self.character_1001))

    def test_user_should_produce_repr(self):
        # when/then
        self.assertTrue(repr(self.character_1001))

    def test_user_should_return_user_when_not_orphan(self):
        # given
        user = self.character_1001.eve_character.character_ownership.user
        # when/then
        self.assertEqual(self.character_1001.user, user)

    def test_user_should_be_None_when_orphan(self):
        # given
        character = create_character(EveCharacter.objects.get(character_id=1121))
        # when/then
        self.assertIsNone(character.user)

    def test_should_return_main_when_it_exists_1(self):
        # given
        user = self.character_1001.eve_character.character_ownership.user
        main_character = user.profile.main_character
        # when/then
        self.assertEqual(self.character_1001.main_character, main_character)

    def test_should_return_main_when_it_exists_2(self):
        # given
        user = self.character_1001.eve_character.character_ownership.user
        main_character = user.profile.main_character
        character_1101 = add_memberaudit_character_to_user(user, 1101)
        # when/then
        self.assertEqual(character_1101.main_character, main_character)

    def test_should_return_none_when_user_has_no_main(self):
        # given
        character_1002 = create_memberaudit_character(1002)
        user = character_1002.eve_character.character_ownership.user
        user.profile.main_character = None
        user.profile.save()
        # when/then
        self.assertIsNone(character_1002.main_character)

    def test_should_be_None_when_orphan(self):
        # given
        character = create_character(EveCharacter.objects.get(character_id=1121))
        # when/then
        self.assertIsNone(character.main_character)

    def test_should_identify_main(self):
        # when/then
        self.assertTrue(self.character_1001.is_main)

    def test_should_be_true_for_main_only(self):
        # given
        user = self.character_1001.eve_character.character_ownership.user
        character_1101 = add_memberaudit_character_to_user(user, 1101)
        # when/then
        self.assertTrue(self.character_1001.is_main)
        self.assertFalse(character_1101.is_main)

    def test_should_be_false_when_no_main(self):
        # given
        character_1002 = create_memberaudit_character(1002)
        user = character_1002.eve_character.character_ownership.user
        user.profile.main_character = None
        user.profile.save()
        # when/then
        self.assertFalse(character_1002.is_main)

    def test_should_be_false_when_orphan(self):
        # given
        character = create_character(EveCharacter.objects.get(character_id=1121))
        # when/then
        self.assertFalse(character.is_main)

    def test_should_be_true_when_orphan(self):
        # given
        character = create_character(EveCharacter.objects.get(character_id=1121))
        # when/then
        self.assertTrue(character.is_orphan)

    def test_should_be_false_when_not_a_orphan(self):
        # when/then
        self.assertFalse(self.character_1001.is_orphan)

    def test_should_keep_sharing(self):
        # given
        _, character_ownership = create_user_from_evecharacter(
            1002,
            permissions=["memberaudit.basic_access", "memberaudit.share_characters"],
        )
        character_1002 = create_character(
            eve_character=character_ownership.character, is_shared=True
        )
        # when
        character_1002.update_sharing_consistency()
        # then
        character_1002.refresh_from_db()
        self.assertTrue(character_1002.is_shared)

    def test_should_identify_user_of_a_character(self):
        # given
        user = self.character_1001.eve_character.character_ownership.user
        # when/then
        self.assertTrue(self.character_1001.user_is_owner(user))

    def test_should_identify_not_user_of_a_character(self):
        # given
        user = create_user_from_evecharacter(1002)
        # when/then
        self.assertFalse(self.character_1001.user_is_owner(user))

    def test_should_identify_not_user_of_an_orphan(self):
        # given
        character = create_character(EveCharacter.objects.get(character_id=1121))
        user = create_user_from_evecharacter(1002)
        # when/then
        self.assertFalse(character.user_is_owner(user))

    def test_should_remove_sharing(self):
        # given
        _, character_ownership = create_user_from_evecharacter(
            1002,
            permissions=["memberaudit.basic_access"],
        )
        character_1002 = create_character(
            eve_character=character_ownership.character, is_shared=True
        )
        # when
        character_1002.update_sharing_consistency()
        # then
        character_1002.refresh_from_db()
        self.assertFalse(character_1002.is_shared)

    @patch(MODELS_PATH + ".Character.objects.clear_cache")
    def test_should_clear_cache(self, mock_clear_cache):
        # when
        self.character_1001.clear_cache()
        # then
        self.assertTrue(mock_clear_cache.called)
        _, kwargs = mock_clear_cache.call_args
        self.assertTrue(kwargs["pk"], self.character_1001.pk)


class TestCharacterFetchToken(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        load_entities()
        cls.user, _ = create_user_from_evecharacter_with_access(1001)

    def test_should_return_token_with_default_scopes(self):
        # given
        character = create_character_from_user(self.user)
        # when
        token = character.fetch_token()
        # then
        self.assertIsInstance(token, Token)
        self.assertSetEqual(scope_names_set(token), set(Character.get_esi_scopes()))

    def test_should_return_token_with_specified_scope(self):
        # given
        character = create_character_from_user(self.user)
        # when
        token = character.fetch_token("esi-mail.read_mail.v1")
        self.assertIsInstance(token, Token)
        self.assertIn("esi-mail.read_mail.v1", scope_names_set(token))

    def test_should_raise_exception_with_scope_not_found_for_orphans(self):
        # given
        character = create_character(EveCharacter.objects.get(character_id=1121))
        # when
        with self.assertRaises(TokenError):
            character.fetch_token()

    @patch(MODELS_PATH + ".MEMBERAUDIT_NOTIFY_TOKEN_ERRORS", True)
    @patch(MODELS_PATH + ".notify.danger")
    def test_should_raise_exception_and_notify_user_if_scope_not_found(
        self, mock_notify_danger
    ):
        # given
        character = create_character_from_user(self.user)
        # when
        with self.assertRaises(TokenDoesNotExist):
            character.fetch_token("invalid_scope")
        # then
        self.assertTrue(mock_notify_danger.called)
        _, kwargs = mock_notify_danger.call_args
        self.assertEqual(
            kwargs["user"], character.eve_character.character_ownership.user
        )
        character.refresh_from_db()
        self.assertTrue(character.token_error_notified_at)

    @patch(MODELS_PATH + ".MEMBERAUDIT_NOTIFY_TOKEN_ERRORS", True)
    @patch(MODELS_PATH + ".notify")
    def test_should_not_notify_user_on_token_error_when_already_notified(
        self, mock_notify_danger
    ):
        # given
        character = create_character_from_user(self.user, token_error_notified_at=now())
        # when
        with self.assertRaises(TokenDoesNotExist):
            character.fetch_token("invalid_scope")
        # then
        self.assertFalse(mock_notify_danger.called)

    @patch(MODELS_PATH + ".MEMBERAUDIT_NOTIFY_TOKEN_ERRORS", False)
    @patch(MODELS_PATH + ".notify")
    def test_should_not_notify_user_on_token_error_when_feature_is_disabled(
        self, mock_notify_danger
    ):
        # given
        character = create_character_from_user(self.user)
        # when
        with self.assertRaises(TokenDoesNotExist):
            character.fetch_token("invalid_scope")
        # then
        self.assertFalse(mock_notify_danger.called)


class TestCharacterStatus(NoSocketsTestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        load_entities()
        cls.character = create_memberaudit_character(1001)

    @patch(MODELS_PATH + ".MEMBERAUDIT_FEATURE_ROLES_ENABLED", True)
    def test_should_return_none_when_not_all_sections_exist(self):
        # when/then
        self.assertIsNone(self.character.is_update_status_ok())

    @patch(MODELS_PATH + ".MEMBERAUDIT_FEATURE_ROLES_ENABLED", True)
    def test_should_return_false_when_a_section_has_errors(self):
        # given
        create_character_update_status(character=self.character, is_success=False)
        # when/then
        self.assertFalse(self.character.is_update_status_ok())

    @patch(MODELS_PATH + ".MEMBERAUDIT_FEATURE_ROLES_ENABLED", False)
    def test_should_ignore_error_in_disabled_sections(self):
        # given
        create_character_update_status(
            character=self.character,
            is_success=False,
            section=Character.UpdateSection.ROLES,
        )
        # when/then
        self.assertIsNone(self.character.is_update_status_ok())

    @patch(MODELS_PATH + ".MEMBERAUDIT_FEATURE_ROLES_ENABLED", True)
    def test_should_return_true_when_all_sections_exist_and_have_no_error(self):
        # given
        for section in Character.UpdateSection:
            create_character_update_status(
                character=self.character, is_success=True, section=section.value
            )
        # when/then
        self.assertTrue(self.character.is_update_status_ok())

    @patch(MODELS_PATH + ".MEMBERAUDIT_FEATURE_ROLES_ENABLED", False)
    def test_should_return_true_when_all_enabled_sections_exist_and_have_no_error(self):
        # given
        for section in Character.UpdateSection.enabled_sections():
            create_character_update_status(
                character=self.character, is_success=True, section=section.value
            )
        create_character_update_status(
            character=self.character,
            is_success=False,
            section=Character.UpdateSection.ROLES,
        )

        # when/then
        self.assertTrue(self.character.is_update_status_ok())

    def test_should_log_success_for_section(self):
        # given
        section = Character.UpdateSection.LOCATION
        # when
        self.character.update_section_log_result(section=section, is_success=True)
        # then
        status: CharacterUpdateStatus = self.character.update_status_set.get(
            section=section
        )
        self.assertTrue(status.is_success)
        self.assertFalse(status.has_token_error)
        self.assertEqual(status.last_error_message, "")
        self.assertTrue(status.finished_at)

    def test_should_log_error_for_section(self):
        # given
        section = Character.UpdateSection.LOCATION
        # when
        self.character.update_section_log_result(
            section=section, is_success=False, last_error_message="some issue"
        )
        # then
        status: CharacterUpdateStatus = self.character.update_status_set.get(
            section=section
        )
        self.assertFalse(status.is_success)
        self.assertFalse(status.has_token_error)
        self.assertEqual(status.last_error_message, "some issue")
        self.assertTrue(status.finished_at)


class TestCharacterUpdateSection(NoSocketsTestCase):
    def test_method_name(self):
        # given
        section = Character.UpdateSection.CORPORATION_HISTORY
        # when/then
        self.assertEqual(section.method_name, "update_corporation_history")


class TestCharacterUpdateSectionEnabledSections(NoSocketsTestCase):
    @patch(MODELS_PATH + ".MEMBERAUDIT_FEATURE_ROLES_ENABLED", True)
    def test_should_return_all_sections(self):
        # when
        result = Character.UpdateSection.enabled_sections()
        # then
        expected = set(Character.UpdateSection)
        self.assertSetEqual(result, expected)

    @patch(MODELS_PATH + ".MEMBERAUDIT_FEATURE_ROLES_ENABLED", False)
    def test_should_return_all_sections_except_roles(self):
        # when
        result = Character.UpdateSection.enabled_sections()
        # then
        expected = set(Character.UpdateSection) - {Character.UpdateSection.ROLES}
        self.assertSetEqual(result, expected)


class TestCharacterUpdateSectionMethods(NoSocketsTestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        load_entities()
        cls.character_1001 = create_memberaudit_character(1001)
        cls.section = Character.UpdateSection.ASSETS
        cls.content = {"alpha": 1, "bravo": 2}

    def test_reset_1(self):
        """when section exists, reset it"""
        create_character_update_status(
            character=self.character_1001,
            section=self.section,
            is_success=False,
            last_error_message="abc",
        )

        section = self.character_1001.reset_update_section(self.section)

        self.assertIsNone(section.is_success)
        self.assertEqual(section.last_error_message, "")

    def test_reset_2(self):
        """when section does not exist, then create it"""
        section = self.character_1001.reset_update_section(self.section)

        self.assertIsNone(section.is_success)
        self.assertEqual(section.last_error_message, "")

    def test_has_changed_1a(self):
        """When section exists, then return result from has_changed"""
        section = create_character_update_status(
            character=self.character_1001,
            section=self.section,
            is_success=True,
            content_hash_1=hashlib.md5(
                json.dumps(self.content).encode("utf-8")
            ).hexdigest(),
        )
        self.assertEqual(
            self.character_1001.has_section_changed(
                section=self.section, content=self.content
            ),
            section.has_changed(self.content),
        )

    def test_has_changed_1b(self):
        """When section exists, then return result from has_changed"""
        section = create_character_update_status(
            character=self.character_1001,
            section=self.section,
            is_success=True,
            content_hash_2=hashlib.md5(
                json.dumps(self.content).encode("utf-8")
            ).hexdigest(),
        )
        self.assertEqual(
            self.character_1001.has_section_changed(
                section=self.section, content=self.content, hash_num=2
            ),
            section.has_changed(self.content, hash_num=2),
        )

    def test_has_changed_1c(self):
        """When section exists, then return result from has_changed"""
        section = create_character_update_status(
            character=self.character_1001,
            section=self.section,
            is_success=True,
            content_hash_3=hashlib.md5(
                json.dumps(self.content).encode("utf-8")
            ).hexdigest(),
        )
        self.assertEqual(
            self.character_1001.has_section_changed(
                section=self.section, content=self.content, hash_num=3
            ),
            section.has_changed(self.content, hash_num=3),
        )

    def test_has_changed_2(self):
        """When section does not exist, then return True"""
        self.assertTrue(
            self.character_1001.has_section_changed(
                section=self.section, content=self.content
            )
        )

    def test_should_return_existing_status_for_section(self):
        # given
        status = create_character_update_status(
            character=self.character_1001, section=self.section
        )
        # when
        result = self.character_1001.update_status_for_section(self.section)
        # then
        self.assertEqual(result, status)

    def test_should_return_none_when_status_does_not_exist_for_section(self):
        # when
        result = self.character_1001.update_status_for_section(self.section)
        # then
        self.assertIsNone(result)

    def test_should_raise_error_when_called_with_invalid_section(self):
        # when/then
        with self.assertRaises(ValueError):
            self.character_1001.update_status_for_section("invalid")


@patch(MODELS_PATH + ".MEMBERAUDIT_UPDATE_STALE_RING_3", 640)
class TestCharacterIsUpdateNeededForSection(NoSocketsTestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        load_entities()
        cls.section = Character.UpdateSection.ASSETS
        cls.user, _ = create_user_from_evecharacter_with_access(1001)

    def setUp(self) -> None:
        self.character = create_character_from_user(self.user)

    def test_should_report_false_when_section_not_stale(self):
        # given
        create_character_update_status(
            character=self.character,
            section=self.section,
            is_success=True,
            started_at=now() - dt.timedelta(seconds=30),
            finished_at=now(),
        )
        # when/then
        self.assertFalse(self.character.is_update_needed_for_section(self.section))

    def test_should_report_true_when_section_has_error(self):
        # given
        create_character_update_status(
            character=self.character, section=self.section, is_success=False
        )
        # when/then
        self.assertTrue(self.character.is_update_needed_for_section(self.section))

    def test_should_report_true_when_section_is_stale(self):
        # given
        started_at = now() - dt.timedelta(hours=12)
        create_character_update_status(
            character=self.character,
            section=self.section,
            is_success=True,
            started_at=started_at,
        )
        # when/then
        self.assertTrue(self.character.is_update_needed_for_section(self.section))

    def test_should_return_true_when_section_does_not_exist(self):
        # when/then
        self.assertTrue(self.character.is_update_needed_for_section(self.section))

    def test_should_report_false_when_section_has_token_error_and_stale(self):
        # given
        started_at = now() - dt.timedelta(hours=12)
        create_character_update_status(
            character=self.character,
            section=self.section,
            is_success=False,
            started_at=started_at,
            has_token_error=True,
        )
        # when/then
        self.assertFalse(self.character.is_update_needed_for_section(self.section))

    def test_should_report_false_when_section_has_token_error_and_not_stale(self):
        # given
        create_character_update_status(
            character=self.character,
            section=self.section,
            is_success=False,
            has_token_error=True,
        )
        # when/then
        self.assertFalse(self.character.is_update_needed_for_section(self.section))


class TestCharacterUpdateSkillSets(NoSocketsTestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        load_eveuniverse()
        load_entities()
        cls.character = create_memberaudit_character(1001)
        cls.skill_type_1 = EveType.objects.get(id=24311)
        cls.skill_type_2 = EveType.objects.get(id=24312)

    def test_has_all_skills(self):
        create_character_skill(
            character=self.character,
            eve_type=self.skill_type_1,
            active_skill_level=5,
            skillpoints_in_skill=10,
            trained_skill_level=5,
        )
        create_character_skill(
            character=self.character,
            eve_type=self.skill_type_2,
            active_skill_level=5,
            skillpoints_in_skill=10,
            trained_skill_level=5,
        )
        skill_set = create_skill_set()
        create_skill_set_skill(
            skill_set=skill_set, eve_type=self.skill_type_1, required_level=5
        )
        create_skill_set_skill(
            skill_set=skill_set, eve_type=self.skill_type_2, required_level=3
        )
        skill_set_group = create_skill_set_group()
        skill_set_group.skill_sets.add(skill_set)

        self.character.update_skill_sets()

        self.assertEqual(self.character.skill_set_checks.count(), 1)
        first = self.character.skill_set_checks.first()
        self.assertEqual(first.skill_set.pk, skill_set.pk)
        self.assertEqual(first.failed_required_skills.count(), 0)

    def test_one_skill_below(self):
        create_character_skill(
            character=self.character,
            eve_type=self.skill_type_1,
            active_skill_level=5,
            skillpoints_in_skill=10,
            trained_skill_level=5,
        )
        create_character_skill(
            character=self.character,
            eve_type=self.skill_type_2,
            active_skill_level=2,
            skillpoints_in_skill=10,
            trained_skill_level=5,
        )
        skill_set = create_skill_set()
        create_skill_set_skill(
            skill_set=skill_set, eve_type=self.skill_type_1, required_level=5
        )
        skill_2 = create_skill_set_skill(
            skill_set=skill_set, eve_type=self.skill_type_2, required_level=3
        )
        skill_set_group = create_skill_set_group()
        skill_set_group.skill_sets.add(skill_set)

        self.character.update_skill_sets()

        self.assertEqual(self.character.skill_set_checks.count(), 1)
        first = self.character.skill_set_checks.first()
        self.assertEqual(first.skill_set.pk, skill_set.pk)
        self.assertEqual(
            {obj.pk for obj in first.failed_required_skills.all()}, {skill_2.pk}
        )

    def test_misses_one_skill(self):
        create_character_skill(
            character=self.character,
            eve_type=self.skill_type_1,
            active_skill_level=5,
            skillpoints_in_skill=10,
            trained_skill_level=5,
        )
        skill_set = create_skill_set()
        create_skill_set_skill(
            skill_set=skill_set, eve_type=self.skill_type_1, required_level=5
        )
        skill_2 = create_skill_set_skill(
            skill_set=skill_set, eve_type=self.skill_type_2, required_level=3
        )
        skill_set_group = create_skill_set_group()
        skill_set_group.skill_sets.add(skill_set)

        self.character.update_skill_sets()

        self.assertEqual(self.character.skill_set_checks.count(), 1)
        first = self.character.skill_set_checks.first()
        self.assertEqual(first.skill_set.pk, skill_set.pk)
        self.assertEqual(
            {obj.pk for obj in first.failed_required_skills.all()}, {skill_2.pk}
        )

    def test_passed_required_and_misses_recommended_skill(self):
        create_character_skill(
            character=self.character,
            eve_type=self.skill_type_1,
            active_skill_level=4,
            skillpoints_in_skill=10,
            trained_skill_level=4,
        )
        skill_set = create_skill_set()
        skill_1 = create_skill_set_skill(
            skill_set=skill_set,
            eve_type=self.skill_type_1,
            required_level=3,
            recommended_level=5,
        )
        self.character.update_skill_sets()

        self.assertEqual(self.character.skill_set_checks.count(), 1)
        first = self.character.skill_set_checks.first()
        self.assertEqual(first.skill_set.pk, skill_set.pk)
        self.assertEqual({obj.pk for obj in first.failed_required_skills.all()}, set())
        self.assertEqual(
            {obj.pk for obj in first.failed_recommended_skills.all()}, {skill_1.pk}
        )

    def test_misses_recommended_skill_only(self):
        create_character_skill(
            character=self.character,
            eve_type=self.skill_type_1,
            active_skill_level=4,
            skillpoints_in_skill=10,
            trained_skill_level=4,
        )
        skill_set = create_skill_set()
        skill_1 = create_skill_set_skill(
            skill_set=skill_set,
            eve_type=self.skill_type_1,
            recommended_level=5,
        )
        self.character.update_skill_sets()

        self.assertEqual(self.character.skill_set_checks.count(), 1)
        first = self.character.skill_set_checks.first()
        self.assertEqual(first.skill_set.pk, skill_set.pk)
        self.assertEqual({obj.pk for obj in first.failed_required_skills.all()}, set())
        self.assertEqual(
            {obj.pk for obj in first.failed_recommended_skills.all()}, {skill_1.pk}
        )

    def test_misses_all_skills(self):
        skill_set = create_skill_set()
        skill_1 = create_skill_set_skill(
            skill_set=skill_set, eve_type=self.skill_type_1, required_level=5
        )
        skill_2 = create_skill_set_skill(
            skill_set=skill_set, eve_type=self.skill_type_2, required_level=3
        )
        skill_set_group = create_skill_set_group()
        skill_set_group.skill_sets.add(skill_set)

        self.character.update_skill_sets()

        self.assertEqual(self.character.skill_set_checks.count(), 1)
        first = self.character.skill_set_checks.first()
        self.assertEqual(first.skill_set.pk, skill_set.pk)
        self.assertEqual(
            {obj.pk for obj in first.failed_required_skills.all()},
            {skill_1.pk, skill_2.pk},
        )

    def test_does_not_require_doctrine_definition(self):
        skill_set = create_skill_set()
        skill_1 = create_skill_set_skill(
            skill_set=skill_set, eve_type=self.skill_type_1, required_level=5
        )
        skill_2 = create_skill_set_skill(
            skill_set=skill_set, eve_type=self.skill_type_2, required_level=3
        )

        self.character.update_skill_sets()

        self.assertEqual(self.character.skill_set_checks.count(), 1)
        first = self.character.skill_set_checks.first()
        self.assertEqual(first.skill_set.pk, skill_set.pk)
        self.assertEqual(
            {obj.pk for obj in first.failed_required_skills.all()},
            {skill_1.pk, skill_2.pk},
        )


class TestCharacterGenerateShipAsset(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        load_eveuniverse()
        load_entities()
        load_locations()
        cls.character = create_memberaudit_character(1001)
        cls.jita = EveSolarSystem.objects.get(name="Jita")
        cls.location_jita_44 = Location.objects.get(id=60003760)
        cls.amamake = EveSolarSystem.objects.get(name="Amamake")
        cls.location_structure_1 = Location.objects.get(id=1_000_000_000_001)
        cls.location_jita = create_location_eve_solar_system(id=cls.jita.id)

    def test_should_generate_asset_when_in_station(self):
        # given
        create_character_ship(
            character=self.character,
            item_id=1_100_000_000_999,
            eve_type_id=EveTypeId.MERLIN,
            name="Joy Ride",
        )
        create_character_location(
            character=self.character, location=self.location_jita_44
        )

        # when
        obj = self.character.generate_asset_from_current_ship_and_location()

        # then
        self.assertEqual(obj["name"], "Joy Ride")
        self.assertEqual(obj["item_id"], 1_100_000_000_999)
        self.assertEqual(obj["is_singleton"], True)
        self.assertEqual(obj["location_id"], self.location_jita_44.id)
        self.assertEqual(obj["location_flag"], "Hangar")
        self.assertEqual(obj["location_type"], "station")
        self.assertEqual(obj["quantity"], 1)
        self.assertEqual(obj["type_id"], EveTypeId.MERLIN)

    def test_should_generate_asset_when_in_structure(self):
        # given
        create_character_ship(
            character=self.character,
            item_id=1_100_000_000_999,
            eve_type_id=EveTypeId.MERLIN,
            name="Joy Ride",
        )
        create_character_location(
            character=self.character, location=self.location_structure_1
        )

        # when
        obj = self.character.generate_asset_from_current_ship_and_location()

        # then
        self.assertEqual(obj["name"], "Joy Ride")
        self.assertEqual(obj["item_id"], 1_100_000_000_999)
        self.assertEqual(obj["is_singleton"], True)
        self.assertEqual(obj["location_id"], self.location_structure_1.id)
        self.assertEqual(obj["location_flag"], "Hangar")
        self.assertEqual(obj["location_type"], "item")
        self.assertEqual(obj["quantity"], 1)
        self.assertEqual(obj["type_id"], EveTypeId.MERLIN)

    def test_should_generate_asset_when_in_space(self):
        # given
        create_character_ship(
            character=self.character,
            item_id=1_100_000_000_999,
            eve_type_id=EveTypeId.MERLIN,
            name="Joy Ride",
        )
        create_character_location(character=self.character, location=self.location_jita)

        # when
        obj = self.character.generate_asset_from_current_ship_and_location()

        # then
        self.assertEqual(obj["name"], "Joy Ride")
        self.assertEqual(obj["item_id"], 1_100_000_000_999)
        self.assertEqual(obj["is_singleton"], True)
        self.assertEqual(obj["location_id"], self.location_jita.id)
        self.assertEqual(obj["location_flag"], "Hangar")
        self.assertEqual(obj["location_type"], "solar_system")
        self.assertEqual(obj["quantity"], 1)
        self.assertEqual(obj["type_id"], EveTypeId.MERLIN)

    def test_should_generate_asset_when_partial_location_only(self):
        # given
        create_character_ship(
            character=self.character,
            item_id=1_100_000_000_999,
            eve_type_id=EveTypeId.MERLIN,
            name="Joy Ride",
        )
        create_character_location(
            character=self.character, eve_solar_system=self.jita, location=None
        )

        # when
        obj = self.character.generate_asset_from_current_ship_and_location()

        # then
        self.assertEqual(obj["name"], "Joy Ride")
        self.assertEqual(obj["item_id"], 1_100_000_000_999)
        self.assertEqual(obj["is_singleton"], True)
        self.assertEqual(obj["location_id"], self.jita.id)
        self.assertEqual(obj["location_flag"], "Hangar")
        self.assertEqual(obj["location_type"], "solar_system")
        self.assertEqual(obj["quantity"], 1)
        self.assertEqual(obj["type_id"], EveTypeId.MERLIN)

    def test_should_generate_asset_when_no_location(self):
        # given
        create_character_ship(
            character=self.character,
            item_id=1_100_000_000_999,
            eve_type_id=EveTypeId.MERLIN,
            name="Joy Ride",
        )

        # when
        obj = self.character.generate_asset_from_current_ship_and_location()

        # then
        self.assertEqual(obj["name"], "Joy Ride")
        self.assertEqual(obj["item_id"], 1_100_000_000_999)
        self.assertEqual(obj["is_singleton"], True)
        self.assertEqual(obj["location_id"], Location.LOCATION_UNKNOWN_ID)
        self.assertEqual(obj["location_flag"], "Hangar")
        self.assertEqual(obj["location_type"], "solar_system")
        self.assertEqual(obj["quantity"], 1)
        self.assertEqual(obj["type_id"], EveTypeId.MERLIN)

    def test_should_not_generate_asset_when_no_location_and_no_ship(self):
        # given

        # when
        obj = self.character.generate_asset_from_current_ship_and_location()

        # then
        self.assertIsNone(obj)

    def test_should_not_generate_asset_when_no_ship(self):
        # given
        create_character_location(character=self.character, location=self.location_jita)

        # when
        obj = self.character.generate_asset_from_current_ship_and_location()

        # then
        self.assertIsNone(obj)

    def test_should_not_generate_asset_when_no_valid_ship_item_id(self):
        # given
        create_character_ship(
            character=self.character,
            item_id=0,
            eve_type_id=EveTypeId.MERLIN,
            name="Joy Ride",
        )
        create_character_location(character=self.character, location=self.location_jita)

        # when
        obj = self.character.generate_asset_from_current_ship_and_location()

        # then
        self.assertIsNone(obj)

    def test_should_not_generate_asset_when_it_is_a_capsule(self):
        # given
        create_character_ship(
            character=self.character,
            item_id=1_100_000_000_999,
            eve_type_id=EveTypeId.CAPSULE,
            name="Bruce Wayne's Capsule",
        )
        create_character_location(character=self.character, location=self.location_jita)

        # when
        obj = self.character.generate_asset_from_current_ship_and_location()

        # then
        self.assertIsNone(obj)
