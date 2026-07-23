import datetime as dt
from http import HTTPStatus
from unittest.mock import MagicMock, patch

from django.utils.timezone import now
from esi.errors import TokenError

from app_utils.testdata_factories import UserMainFactory
from app_utils.testing import NoSocketsTestCase

from memberaudit.helpers import UpdateSectionResult
from memberaudit.models import Character, CharacterUpdateStatus
from memberaudit.tests.testdata.factories_2 import (
    CharacterFactory,
    CharacterSkillFactory,
    CharacterUpdateStatusFactory,
    SkillSetFactory,
    SkillSetGroupFactory,
    SkillSetSkillFactory,
    SpaceshipCommandSkillTypeFactory,
    UserMainBasicAccessFactory,
)
from memberaudit.tests.utils import extract, make_http_server_error

MODULE_PATH = "memberaudit.models.characters"


class TestCharacter_UserHasAccess(NoSocketsTestCase):  # see also manager for more tests
    def test_user_owning_character_has_access(self):
        # given
        user = UserMainFactory(permissions__=["memberaudit.basic_access"])
        character = CharacterFactory(user=user)
        # when/then
        self.assertTrue(character.user_has_access(user))

    def test_other_user_has_no_access(self):
        # given
        user = UserMainFactory(permissions__=["memberaudit.basic_access"])
        character = CharacterFactory()
        # when/then
        self.assertFalse(character.user_has_access(user))

    def test_has_access_for_view_everything_with_scope_permission(self):
        # given
        user = UserMainFactory(
            permissions__=[
                "memberaudit.basic_access",
                "memberaudit.view_everything",
                "memberaudit.characters_access",
            ],
        )
        character = CharacterFactory()
        # when/then
        self.assertTrue(character.user_has_access(user))


class TestCharacter_UserHasScope(NoSocketsTestCase):  # see also manager for more tests
    def test_user_owning_character_has_scope(self):
        # given
        user = UserMainFactory(permissions__=["memberaudit.basic_access"])
        character = CharacterFactory(user=user)
        # when/then
        self.assertTrue(character.user_has_scope(user))

    def test_other_user_has_no_access(self):
        # given
        user = UserMainFactory(permissions__=["memberaudit.basic_access"])
        character = CharacterFactory()
        # when/then
        self.assertFalse(character.user_has_scope(user))

    def test_has_access_for_view_everything_with_scope_permission(self):
        # given
        user = UserMainFactory(
            permissions__=[
                "memberaudit.basic_access",
                "memberaudit.view_everything",
            ],
        )
        character = CharacterFactory()
        # when/then
        self.assertTrue(character.user_has_scope(user))


@patch(MODULE_PATH + ".Character.update_section_content_hash")
@patch(MODULE_PATH + ".Character.has_section_changed")
class TestCharacterManager_UpdateSectionIfChanged(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = UserMainBasicAccessFactory()
        cls.character_1002 = CharacterFactory(id=1002, user=cls.user)

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
        character = CharacterFactory(user=self.user, is_main=False)
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
        character = CharacterFactory(user=self.user, is_main=False)
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
        character = CharacterFactory(user=self.user, is_main=False)
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
        character = CharacterFactory(user=self.user, is_main=False)
        fetch_func_mock = MagicMock(
            side_effect=make_http_server_error(HTTPStatus.INTERNAL_SERVER_ERROR)
        )
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
        character = CharacterFactory(user=self.user, is_main=False)
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
        character = CharacterFactory(user=self.user, is_main=False)
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


class TestCharacter_HasTokenIssue(NoSocketsTestCase):
    def test_should_return_false_when_no_error(self):
        # given
        character = CharacterFactory()

        # when/then
        self.assertFalse(character.has_token_issue())

    def test_should_return_true_when_token_error(self):
        # given
        character = CharacterFactory()
        CharacterUpdateStatusFactory(
            character=character,
            section=Character.UpdateSection.ASSETS,
            is_success=False,
            has_token_error=True,
            error_message="TokenError",
        )
        # when/then
        self.assertTrue(character.has_token_issue())

    def test_should_return_false_when_other_error(self):
        # given
        character = CharacterFactory()
        CharacterUpdateStatusFactory(
            character=character,
            section=Character.UpdateSection.ASSETS,
            is_success=False,
            has_token_error=False,
            error_message="other error",
        )
        # when/then
        self.assertFalse(character.has_token_issue())

    @patch(MODULE_PATH + ".MEMBERAUDIT_FEATURE_ROLES_ENABLED", False)
    def test_should_return_false_when_token_error_for_disabled_section(self):
        # given
        character = CharacterFactory()
        CharacterUpdateStatusFactory(
            character=character,
            section=Character.UpdateSection.ROLES,
            is_success=False,
            has_token_error=True,
            error_message="TokenError",
        )
        # when/then
        self.assertFalse(character.has_token_issue())


class TestCharacter_ResetTokenErrorNotifiedIfStatusOk(NoSocketsTestCase):
    def test_should_reset_when_ok_again(self):
        # given
        character = CharacterFactory(token_error_notified_at=now())
        for section in Character.UpdateSection:
            CharacterUpdateStatusFactory(
                character=character,
                section=section,
            )

        # when
        character.reset_token_error_notified_if_status_ok()

        # then
        character.refresh_from_db()
        self.assertIsNone(character.token_error_notified_at)

    def test_should_not_reset_when_not_yet_ok(self):
        # given
        character = CharacterFactory(token_error_notified_at=now())
        CharacterUpdateStatusFactory(
            character=character,
            section=Character.UpdateSection.ASSETS,
            is_success=False,
        )

        # when
        character.reset_token_error_notified_if_status_ok()

        # then
        character.refresh_from_db()
        self.assertTrue(character.token_error_notified_at)

    def test_should_ignore_when_not_set(self):
        # given
        character = CharacterFactory(token_error_notified_at=None)
        CharacterUpdateStatusFactory(
            character=character,
            section=Character.UpdateSection.ASSETS,
            is_success=False,
        )

        # when
        character.reset_token_error_notified_if_status_ok()

        # then
        character.refresh_from_db()
        self.assertIsNone(character.token_error_notified_at)


class TestCharacter_EsiScopes(NoSocketsTestCase):
    @patch(MODULE_PATH + ".MEMBERAUDIT_FEATURE_ROLES_ENABLED", False)
    def test_should_return_all_scopes(self):
        # when
        result = Character.esi_scopes()
        # then
        expected = {
            "esi-assets.read_assets.v1",
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


class TestCharacter_PerformUpdateWithErrorLogging(NoSocketsTestCase):
    def test_should_execute_method_and_return_value(self):
        # given
        def my_method(dummy):
            return UpdateSectionResult(
                data=f"return-value-{dummy}", is_changed=True, is_updated=True
            )

        character = CharacterFactory()
        section = Character.UpdateSection.LOCATION

        # when
        result = character.perform_update_with_error_logging(
            section=section, method=my_method, dummy="alpha"
        )

        # then
        self.assertEqual(result.data, "return-value-alpha")
        self.assertTrue(result.is_updated)

    def test_should_mark_section_as_failed_when_general_exception_is_raised(self):
        # given
        def my_method():
            raise RuntimeError("Test exception")

        character = CharacterFactory()
        section = Character.UpdateSection.LOCATION

        # when
        with self.assertRaises(RuntimeError):
            character.perform_update_with_error_logging(
                section=section, method=my_method
            )

        # then
        status: CharacterUpdateStatus = character.update_status_set.get(section=section)
        self.assertFalse(status.is_success)
        self.assertFalse(status.has_token_error)
        self.assertIn("RuntimeError", status.error_message)
        self.assertTrue(status.run_finished_at)

    def test_should_mark_section_as_failed_when_token_error_is_raised(self):
        # given
        def my_method():
            raise TokenError("Test exception")

        character = CharacterFactory()
        section = Character.UpdateSection.LOCATION

        # when/then
        with self.assertRaises(TokenError):
            character.perform_update_with_error_logging(
                section=section, method=my_method
            )
        # then
        status: CharacterUpdateStatus = character.update_status_set.get(section=section)
        self.assertFalse(status.is_success)
        self.assertTrue(status.has_token_error)
        self.assertIn("TokenError", status.error_message)
        self.assertTrue(status.run_finished_at)


class TestCharacter_UpdateStatusAsDict(NoSocketsTestCase):
    def test_should_return_dict_with_status(self):
        # given
        character = CharacterFactory()
        status = CharacterUpdateStatusFactory(
            character=character,
            section=Character.UpdateSection.LOCATION,
            is_success=True,
        )

        # when
        result = character.update_status_as_dict()

        # then
        self.assertDictEqual(result, {"location": status})

    def test_should_return_empty_dict(self):
        # given
        character = CharacterFactory()

        # when
        result = character.update_status_as_dict()

        # then
        self.assertDictEqual(result, {})


@patch(MODULE_PATH + ".section_time_until_stale", {"assets": 640})
class TestCharacter_IsUpdateNeeded(NoSocketsTestCase):
    def test_should_report_false_when_section_not_stale(self):
        # given
        character = CharacterFactory()
        status = CharacterUpdateStatusFactory(
            character=character,
            section=Character.UpdateSection.ASSETS,
            is_success=True,
            run_started_at=now() - dt.timedelta(seconds=30),
            run_finished_at=now(),
        )
        # when/then
        self.assertFalse(status.is_update_needed())

    def test_should_report_true_when_section_has_error(self):
        # given
        character = CharacterFactory()
        status = CharacterUpdateStatusFactory(
            character=character,
            section=Character.UpdateSection.ASSETS,
            is_success=False,
        )
        # when/then
        self.assertTrue(status.is_update_needed())

    def test_should_report_true_when_section_is_stale(self):
        # given
        character = CharacterFactory()
        run_started_at = now() - dt.timedelta(hours=12)
        run_finished_at = run_started_at + dt.timedelta(minutes=10)
        status = CharacterUpdateStatusFactory(
            character=character,
            section=Character.UpdateSection.ASSETS,
            is_success=True,
            run_started_at=run_started_at,
            run_finished_at=run_finished_at,
        )
        # when/then
        self.assertTrue(status.is_update_needed())

    def test_should_report_false_when_section_has_token_error_and_stale(self):
        # given
        character = CharacterFactory()
        run_started_at = now() - dt.timedelta(hours=12)
        status = CharacterUpdateStatusFactory(
            character=character,
            section=Character.UpdateSection.ASSETS,
            is_success=False,
            run_started_at=run_started_at,
            has_token_error=True,
        )
        # when/then
        self.assertFalse(status.is_update_needed())

    def test_should_report_false_when_section_has_token_error_and_not_stale(self):
        # given
        character = CharacterFactory()
        status = CharacterUpdateStatusFactory(
            character=character,
            section=Character.UpdateSection.ASSETS,
            is_success=False,
            has_token_error=True,
        )
        # when/then
        self.assertFalse(status.is_update_needed())


class TestCharacter_SkillSetChecks_2(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.amarr_carrier_skill_type = SpaceshipCommandSkillTypeFactory(
            name="Amarr Carrier"
        )
        cls.caldari_carrier_skill_type = SpaceshipCommandSkillTypeFactory(
            name="Caldari Carrier"
        )
        cls.gallente_carrier_skill_type = SpaceshipCommandSkillTypeFactory(
            name="Gallente Carrier"
        )
        cls.minmatar_carrier_skill_type = SpaceshipCommandSkillTypeFactory(
            name="Minmatar Carrier"
        )

    def test_should_return_all(self):
        # given
        character = CharacterFactory()
        CharacterSkillFactory(
            character=character,
            eve_type=self.amarr_carrier_skill_type,
            active_skill_level=4,
            skillpoints_in_skill=10,
            trained_skill_level=4,
        )
        CharacterSkillFactory(
            character=character,
            eve_type=self.caldari_carrier_skill_type,
            active_skill_level=2,
            skillpoints_in_skill=10,
            trained_skill_level=5,
        )

        doctrine_1 = SkillSetGroupFactory(name="Alpha")
        doctrine_2 = SkillSetGroupFactory(name="Bravo", is_doctrine=True)

        # can fly ship 1
        ship_1 = SkillSetFactory(name="Ship 1", groups=[doctrine_1, doctrine_2])
        SkillSetSkillFactory(
            skill_set=ship_1,
            eve_type=self.amarr_carrier_skill_type,
            required_level=3,
            recommended_level=5,
        )

        # can not fly ship 2
        ship_2 = SkillSetFactory(name="Ship 2", groups=[doctrine_1])
        SkillSetSkillFactory(
            skill_set=ship_2, eve_type=self.amarr_carrier_skill_type, required_level=3
        )
        SkillSetSkillFactory(
            skill_set=ship_2, eve_type=self.caldari_carrier_skill_type, required_level=3
        )

        # can fly ship 3 (No SkillSetGroup)
        ship_3 = SkillSetFactory(name="Ship 3")
        SkillSetSkillFactory(
            skill_set=ship_3, eve_type=self.amarr_carrier_skill_type, required_level=1
        )

        character.update_skill_sets()

        # given
        got = character.skill_set_checks_2()

        # then
        self.assertEqual(
            extract(got, "skill_set__pk"), {ship_1.pk, ship_2.pk, ship_3.pk}
        )
