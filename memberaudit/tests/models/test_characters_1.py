import datetime as dt
import hashlib
import json
from unittest.mock import patch

from django.utils.timezone import now
from esi.errors import TokenError
from esi.models import Token
from eveuniverse.tests.testdata.factories_2 import (
    EveSolarSystemFactory,
    ShipTypeFactory,
    SolarSystemTypeFactory,
)

from app_utils.testdata_factories import UserMainFactory
from app_utils.testing import NoSocketsTestCase

from memberaudit.errors import TokenDoesNotExist
from memberaudit.models import (
    Character,
    CharacterUpdateStatus,
    Location,
    characters,
    enabled_sections_by_stale_minutes,
)
from memberaudit.tests.testdata.constants import EveGroupId
from memberaudit.tests.testdata.factories_2 import (
    CharacterFactory,
    CharacterLocationFactory,
    CharacterOrphanFactory,
    CharacterShipFactory,
    CharacterUpdateStatusFactory,
    LocationSolarSystemFactory,
    LocationStationFactory,
    LocationStructureFactory,
    UserMainBasicAccessFactory,
)
from memberaudit.tests.utils import scope_names_set

MODELS_PATH = "memberaudit.models.characters"
MANAGERS_PATH = "memberaudit.managers"
TASKS_PATH = "memberaudit.tasks"


class TestCharacter(NoSocketsTestCase):
    def test_user_should_produce_str(self):
        # given
        character = CharacterFactory()
        # when/then
        self.assertTrue(str(character))

    def test_user_should_produce_repr(self):
        # given
        character = CharacterFactory()
        # when/then
        self.assertTrue(repr(character))

    @patch(MODELS_PATH + ".Character.objects.clear_cache")
    def test_should_clear_cache(self, mock_clear_cache):
        # given
        character = CharacterFactory()
        # when
        character.clear_cache()
        # then
        self.assertTrue(mock_clear_cache.called)
        _, kwargs = mock_clear_cache.call_args
        self.assertTrue(kwargs["pk"], character.pk)


class TestCharacter_User(NoSocketsTestCase):
    def test_should_return_user(self):
        # given
        character = CharacterFactory()
        # when
        got = character.user
        # then
        want = character.eve_character.character_ownership.user
        self.assertEqual(got, want)

    def test_should_return_none_when_orphan(self):
        # given
        character = CharacterOrphanFactory()
        # when/then
        self.assertIsNone(character.user)


class TestCharacter_MainCharacter(NoSocketsTestCase):
    def test_should_return_main_when_character_is_main(self):
        # given
        character = CharacterFactory()
        # when
        got = character.main_character
        # then
        want = character.eve_character.character_ownership.user.profile.main_character
        self.assertEqual(got, want)

    def test_should_return_main_when_character_is_not_main(self):
        # given
        character = CharacterFactory(is_main=False)
        # when
        got = character.main_character
        # then
        want = character.eve_character.character_ownership.user.profile.main_character
        self.assertEqual(got, want)

    def test_should_return_none_when_user_has_no_main(self):
        # given
        character = CharacterFactory()
        user = character.eve_character.character_ownership.user
        user.profile.main_character = None
        user.profile.save()
        # when
        got = character.main_character
        # then
        self.assertIsNone(got)

    def test_should_return_none_when_orphan(self):
        # given
        character = CharacterOrphanFactory()
        # when
        got = character.main_character
        # then
        self.assertIsNone(got)


class TestCharacter_IsMain(NoSocketsTestCase):
    def test_should_return_true_when_main(self):
        # given
        character = CharacterFactory()
        # when/then
        self.assertTrue(character.is_main)

    def test_should_return_false_when_not_main(self):
        # given
        character = CharacterFactory(is_main=False)
        # when/then
        self.assertFalse(character.is_main)

    def test_should_be_false_when_no_main(self):
        # given
        character = CharacterFactory()
        user = character.eve_character.character_ownership.user
        user.profile.main_character = None
        user.profile.save()
        # when/then
        self.assertFalse(character.is_main)

    def test_should_return_false_when_orphan(self):
        # given
        character = CharacterOrphanFactory()
        # when/then
        self.assertFalse(character.is_main)


class TestCharacter_IsOrphan(NoSocketsTestCase):
    def test_should_be_true_when_orphan(self):
        # given
        character = CharacterOrphanFactory()
        # when/then
        self.assertTrue(character.is_orphan)

    def test_should_be_false_when_not_a_orphan(self):
        # given
        character = CharacterFactory()
        # when/then
        self.assertFalse(character.is_orphan)


class TestCharacter_UserIsOwner(NoSocketsTestCase):
    def test_should_return_true_when_owner(self):
        # given
        user = UserMainBasicAccessFactory()
        character = CharacterFactory(user=user)
        # when/then
        self.assertTrue(character.user_is_owner(user))

    def test_should_return_false_when_not_owner(self):
        # given
        user = UserMainBasicAccessFactory()
        character = CharacterFactory()
        # when/then
        self.assertFalse(character.user_is_owner(user))

    def test_should_return_false_when_orphan(self):
        # given
        user = UserMainBasicAccessFactory()
        character = CharacterOrphanFactory()
        # when/then
        self.assertFalse(character.user_is_owner(user))


class TestCharacter_UpdateSharingConsistency(NoSocketsTestCase):
    def test_should_keep_sharing(self):
        # given
        user = UserMainFactory(
            permissions__=["memberaudit.basic_access", "memberaudit.share_characters"]
        )
        character = CharacterFactory(user=user, is_shared=True)
        # when
        character.update_sharing_consistency()
        # then
        character.refresh_from_db()
        self.assertTrue(character.is_shared)

    def test_should_remove_sharing(self):
        # given
        user = UserMainFactory(permissions__=["memberaudit.basic_access"])
        character = CharacterFactory(user=user, is_shared=True)
        # when
        character.update_sharing_consistency()
        # then
        character.refresh_from_db()
        self.assertFalse(character.is_shared)


class TestCharacter_FetchToken2(NoSocketsTestCase):
    def test_should_return_token_with_default_scopes(self):
        # given
        character = CharacterFactory()
        # when
        token = character.fetch_token()
        # then
        self.assertIsInstance(token, Token)
        self.assertSetEqual(scope_names_set(token), set(Character.esi_scopes()))

    def test_should_return_token_with_specified_scope(self):
        # given
        character = CharacterFactory()
        # when
        token = character.fetch_token("esi-mail.read_mail.v1")
        self.assertIsInstance(token, Token)
        self.assertIn("esi-mail.read_mail.v1", scope_names_set(token))

    def test_should_raise_exception_with_scope_not_found_for_orphans(self):
        # given
        character = CharacterOrphanFactory()
        # when
        with self.assertRaises(TokenError):
            character.fetch_token()

    @patch(MODELS_PATH + ".MEMBERAUDIT_NOTIFY_TOKEN_ERRORS", True)
    @patch(MODELS_PATH + ".notify.danger")
    def test_should_raise_exception_and_notify_user_if_scope_not_found(
        self, mock_notify_danger
    ):
        # given
        character = CharacterFactory()
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
        character = CharacterFactory(token_error_notified_at=now())
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
        character = CharacterFactory()
        # when
        with self.assertRaises(TokenDoesNotExist):
            character.fetch_token("invalid_scope")
        # then
        self.assertFalse(mock_notify_danger.called)


class TestCharacter_IsUpdateStatusOk(NoSocketsTestCase):
    def test_should_return_true_when_all_sections_exist_and_have_no_error(self):
        # given
        character = CharacterFactory()
        for s in Character.UpdateSection.enabled_sections():
            CharacterUpdateStatusFactory(character=character, section=s)
        # when/then
        self.assertTrue(character.is_update_status_ok())

    def test_should_return_none_when_not_all_sections_exist(self):
        # given
        character = CharacterFactory()
        CharacterUpdateStatusFactory(character=character)
        # when/then
        self.assertIsNone(character.is_update_status_ok())

    def test_should_return_false_when_a_section_has_errors(self):
        # given
        character = CharacterFactory()
        CharacterUpdateStatusFactory(character=character, is_success=False)
        # when/then
        self.assertFalse(character.is_update_status_ok())

    @patch(MODELS_PATH + ".MEMBERAUDIT_FEATURE_ROLES_ENABLED", False)
    def test_should_ignore_error_in_disabled_sections(self):
        # given
        character = CharacterFactory()
        for s in Character.UpdateSection.enabled_sections():
            CharacterUpdateStatusFactory(character=character, section=s)

        CharacterUpdateStatusFactory(
            character=character, is_success=False, section=Character.UpdateSection.ROLES
        )
        # when/then
        self.assertTrue(character.is_update_status_ok())


class TestCharacter_UpdateSectionLogResult(NoSocketsTestCase):
    def test_should_log_success_for_section(self):
        # given
        character = CharacterFactory()
        section = Character.UpdateSection.LOCATION
        # when
        character.update_section_log_result(section=section, is_success=True)
        # then
        status: CharacterUpdateStatus = character.update_status_set.get(section=section)
        self.assertTrue(status.is_success)
        self.assertFalse(status.has_token_error)
        self.assertEqual(status.error_message, "")
        self.assertTrue(status.run_finished_at)

    def test_should_log_error_for_section(self):
        # given
        character = CharacterFactory()
        section = Character.UpdateSection.LOCATION
        # when
        character.update_section_log_result(
            section=section, is_success=False, error_message="some issue"
        )
        # then
        status: CharacterUpdateStatus = character.update_status_set.get(section=section)
        self.assertFalse(status.is_success)
        self.assertFalse(status.has_token_error)
        self.assertEqual(status.error_message, "some issue")
        self.assertTrue(status.run_finished_at)


class TestCharacter_ResetUpdateSection(NoSocketsTestCase):
    def test_should_reset_existing_section(self):
        # given
        character = CharacterFactory()
        section = Character.UpdateSection.ASSETS
        CharacterUpdateStatusFactory(
            character=character, error_message="abc", is_success=False, section=section
        )
        # when
        section = character.reset_update_section(section)

        self.assertIsNone(section.is_success)
        self.assertEqual(section.error_message, "")

    def test_should_create_section_when_not_exists(self):
        """when section does not exist, then create it"""
        # given
        character = CharacterFactory()
        section = Character.UpdateSection.ASSETS
        # when
        section = character.reset_update_section(section)
        self.assertIsNone(section.is_success)
        self.assertEqual(section.error_message, "")


class TestCharacter_HasChanged(NoSocketsTestCase):
    def test_return_changed_result_from_default_hash(self):
        # given
        character = CharacterFactory()
        content = {"alpha": 1}
        section = Character.UpdateSection.ASSETS
        status = CharacterUpdateStatusFactory(
            character=character,
            section=section,
            is_success=True,
            content_hash_1=hashlib.md5(json.dumps(content).encode("utf-8")).hexdigest(),
        )
        # when
        got = status.has_changed(content)
        # then
        want = character.has_section_changed(section=section, content=content)
        self.assertEqual(got, want)

    def test_return_changed_result_from_2nd_hash(self):
        # given
        character = CharacterFactory()
        content = {"alpha": 1}
        section = Character.UpdateSection.ASSETS
        status = CharacterUpdateStatusFactory(
            character=character,
            section=section,
            is_success=True,
            content_hash_2=hashlib.md5(json.dumps(content).encode("utf-8")).hexdigest(),
        )
        # when
        got = status.has_changed(content, hash_num=2)
        # then
        want = character.has_section_changed(
            section=section, content=content, hash_num=2
        )
        self.assertEqual(got, want)

    def test_return_changed_result_from_3rd_hash(self):
        # given
        character = CharacterFactory()
        content = {"alpha": 1}
        section = Character.UpdateSection.ASSETS
        status = CharacterUpdateStatusFactory(
            character=character,
            section=section,
            is_success=True,
            content_hash_3=hashlib.md5(json.dumps(content).encode("utf-8")).hexdigest(),
        )
        # when
        got = status.has_changed(content, hash_num=3)
        # then
        want = character.has_section_changed(
            section=section, content=content, hash_num=3
        )
        self.assertEqual(got, want)

    def test_should_return_true_when_section_does_not_exist(self):
        # given
        character = CharacterFactory()
        section = Character.UpdateSection.ASSETS
        # when/then
        self.assertTrue(character.has_section_changed(section=section, content="xyz"))


class TestCharacter_UpdateStatusForSection(NoSocketsTestCase):
    def test_should_return_status_when_section_has_status(self):
        # given
        character = CharacterFactory()
        section = Character.UpdateSection.ASSETS
        status = CharacterUpdateStatusFactory(character=character, section=section)
        # when
        got = character.update_status_for_section(section)
        # then
        self.assertEqual(got, status)

    def test_should_return_none_when_status_does_not_exist_for_section(self):
        # when
        character = CharacterFactory()
        section = Character.UpdateSection.ASSETS
        # when
        got = character.update_status_for_section(section)
        # then
        self.assertIsNone(got)

    def test_should_raise_error_when_called_with_invalid_section(self):
        # given
        character = CharacterFactory()
        # when/then
        with self.assertRaises(ValueError):
            character.update_status_for_section("invalid")


class TestCharacter_CalcUpdateNeeded(NoSocketsTestCase):
    def test_should_return_false_when_all_sections_are_current(self):
        # given
        character = CharacterFactory()
        for section in Character.UpdateSection.enabled_sections():
            CharacterUpdateStatusFactory(character=character, section=section)

        status = character.calc_update_needed()

        # when/then
        self.assertFalse(status.is_update_needed())

    def test_should_return_true_when_one_section_is_outdated(self):
        # given
        section = Character.UpdateSection.ASSETS
        other_sections = Character.UpdateSection.enabled_sections() - {
            Character.UpdateSection.ASSETS
        }
        character = CharacterFactory()
        for section in other_sections:
            CharacterUpdateStatusFactory(character=character, section=section)

        run_started_at = now() - dt.timedelta(hours=24)
        run_finished_at = run_started_at + dt.timedelta(minutes=5)
        CharacterUpdateStatusFactory(
            character=character,
            section=Character.UpdateSection.ASSETS,
            run_started_at=run_started_at,
            run_finished_at=run_finished_at,
        )

        status = character.calc_update_needed()

        # when/then
        self.assertTrue(status.is_update_needed())


class TestCharacter_GenerateShipAsset(NoSocketsTestCase):
    def test_should_generate_asset_when_in_station(self):
        # given
        character = CharacterFactory()
        ship = CharacterShipFactory(character=character)
        location = LocationStationFactory()
        CharacterLocationFactory(character=character, location=location)

        # when
        obj = character.generate_asset_from_current_ship_and_location()

        # then
        self.assertEqual(obj["name"], ship.name)
        self.assertEqual(obj["item_id"], ship.item_id)
        self.assertEqual(obj["is_singleton"], True)
        self.assertEqual(obj["location_id"], location.id)
        self.assertEqual(obj["location_flag"], "Hangar")
        self.assertEqual(obj["location_type"], "station")
        self.assertEqual(obj["quantity"], 1)
        self.assertEqual(obj["type_id"], ship.eve_type.id)

    def test_should_generate_asset_when_in_structure_2(self):
        # given
        character = CharacterFactory()
        ship = CharacterShipFactory(character=character)
        location = LocationStructureFactory()
        CharacterLocationFactory(character=character, location=location)

        # when
        obj = character.generate_asset_from_current_ship_and_location()

        # then
        self.assertEqual(obj["name"], ship.name)
        self.assertEqual(obj["item_id"], ship.item_id)
        self.assertEqual(obj["is_singleton"], True)
        self.assertEqual(obj["location_id"], location.id)
        self.assertEqual(obj["location_flag"], "Hangar")
        self.assertEqual(obj["location_type"], "item")
        self.assertEqual(obj["quantity"], 1)
        self.assertEqual(obj["type_id"], ship.eve_type.id)

    def test_should_generate_asset_when_in_space(self):
        # given
        character = CharacterFactory()
        ship = CharacterShipFactory(character=character)
        location = LocationSolarSystemFactory()
        CharacterLocationFactory(character=character, location=location)

        # when
        obj = character.generate_asset_from_current_ship_and_location()

        # then
        self.assertEqual(obj["name"], ship.name)
        self.assertEqual(obj["item_id"], ship.item_id)
        self.assertEqual(obj["is_singleton"], True)
        self.assertEqual(obj["location_id"], location.id)
        self.assertEqual(obj["location_flag"], "Hangar")
        self.assertEqual(obj["location_type"], "solar_system")
        self.assertEqual(obj["quantity"], 1)
        self.assertEqual(obj["type_id"], ship.eve_type.id)

    def test_should_generate_asset_when_partial_location_only(self):
        # given
        SolarSystemTypeFactory()
        character = CharacterFactory()
        ship = CharacterShipFactory(character=character)
        location = CharacterLocationFactory(
            character=character, location=None, eve_solar_system=EveSolarSystemFactory()
        )

        # when
        obj = character.generate_asset_from_current_ship_and_location()

        # then
        self.assertEqual(obj["name"], ship.name)
        self.assertEqual(obj["item_id"], ship.item_id)
        self.assertEqual(obj["is_singleton"], True)
        self.assertEqual(obj["location_id"], location.eve_solar_system.id)
        self.assertEqual(obj["location_flag"], "Hangar")
        self.assertEqual(obj["location_type"], "solar_system")
        self.assertEqual(obj["quantity"], 1)
        self.assertEqual(obj["type_id"], ship.eve_type.id)

    def test_should_generate_asset_when_no_location(self):
        # given
        SolarSystemTypeFactory()
        character = CharacterFactory()
        ship = CharacterShipFactory(character=character)

        # when
        obj = character.generate_asset_from_current_ship_and_location()

        # then
        self.assertEqual(obj["name"], ship.name)
        self.assertEqual(obj["item_id"], ship.item_id)
        self.assertEqual(obj["is_singleton"], True)
        self.assertEqual(obj["location_id"], Location.LOCATION_UNKNOWN_ID)
        self.assertEqual(obj["location_flag"], "Hangar")
        self.assertEqual(obj["location_type"], "solar_system")
        self.assertEqual(obj["quantity"], 1)
        self.assertEqual(obj["type_id"], ship.eve_type.id)

    def test_should_not_generate_asset_when_no_location_and_no_ship(self):
        # given
        character = CharacterFactory()

        # when
        obj = character.generate_asset_from_current_ship_and_location()

        # then
        self.assertIsNone(obj)

    def test_should_not_generate_asset_when_no_ship(self):
        # given
        character = CharacterFactory()
        CharacterLocationFactory(character=character)

        # when
        obj = character.generate_asset_from_current_ship_and_location()

        # then
        self.assertIsNone(obj)

    def test_should_not_generate_asset_when_no_valid_ship_item_id(self):
        # given
        character = CharacterFactory()
        CharacterShipFactory(character=character, item_id=0)
        CharacterLocationFactory(character=character)

        # when
        obj = character.generate_asset_from_current_ship_and_location()

        # then
        self.assertIsNone(obj)

    def test_should_not_generate_asset_when_it_is_a_capsule(self):
        # given
        character = CharacterFactory()
        CharacterShipFactory(
            character=character,
            eve_type=ShipTypeFactory(eve_group__id=EveGroupId.CAPSULE),
        )
        CharacterLocationFactory(character=character)

        # when
        obj = character.generate_asset_from_current_ship_and_location()

        # then
        self.assertIsNone(obj)


class TestCharacterUpdateSection_TimeUntilSectionUpdatesAreStale(NoSocketsTestCase):
    def test_method_name(self):
        # given
        section = Character.UpdateSection.CORPORATION_HISTORY
        # when/then
        self.assertEqual(section.method_name, "update_corporation_history")

    @patch(MODELS_PATH + ".MEMBERAUDIT_SECTION_STALE_MINUTES_CONFIG", {"titles": 98})
    @patch(MODELS_PATH + ".MEMBERAUDIT_SECTION_STALE_MINUTES_GLOBAL_DEFAULT", 42)
    def test_should_return_correct_map(self):
        # when
        result = Character.UpdateSection.time_until_section_updates_are_stale()
        # then
        for section in Character.UpdateSection:
            with self.subTest(section=section):
                self.assertIn(section, result)

        self.assertEqual(result[Character.UpdateSection.MAILS], 42)  # global default
        self.assertEqual(
            result[Character.UpdateSection.ASSETS], 480
        )  # section defaults
        self.assertEqual(result[Character.UpdateSection.TITLES], 98)  # custom setting

    @patch(MODELS_PATH + ".MEMBERAUDIT_SECTION_STALE_MINUTES_CONFIG", {"invalid": 98})
    @patch(MODELS_PATH + ".MEMBERAUDIT_SECTION_STALE_MINUTES_GLOBAL_DEFAULT", 42)
    @patch(MODELS_PATH + ".logger", wraps=characters.logger)
    def test_should_ignore_invalid_config(self, spy_logger):
        # when
        result = Character.UpdateSection.time_until_section_updates_are_stale()

        # then
        for section in Character.UpdateSection:
            with self.subTest(section=section):
                self.assertIn(section, result)

        self.assertTrue(spy_logger.warning.called)


class TestCharacterUpdateSection_EnabledSections(NoSocketsTestCase):
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


class TestEnabledSectionsByStaleMinutes(NoSocketsTestCase):
    def test_should_order_correctly(self):
        # when
        with patch(
            MODELS_PATH + ".section_time_until_stale",
            {
                Character.UpdateSection.MAILS: 10,
                Character.UpdateSection.ASSETS: 5,
                Character.UpdateSection.LOCATION: 7,
            },
        ):
            result = enabled_sections_by_stale_minutes()
        # then
        excepted_result = [
            Character.UpdateSection.ASSETS,
            Character.UpdateSection.LOCATION,
            Character.UpdateSection.MAILS,
        ]
        self.assertListEqual(result, excepted_result)

    def test_should_include_enabled_sections_only(self):
        # when
        result = enabled_sections_by_stale_minutes()
        # then
        self.assertEqual(set(result), Character.UpdateSection.enabled_sections())
