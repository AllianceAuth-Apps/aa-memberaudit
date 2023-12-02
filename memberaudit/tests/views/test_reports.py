from django.contrib.auth.models import Group
from django.test import RequestFactory, TestCase
from django.urls import reverse
from eveuniverse.models import EveType

from allianceauth.authentication.models import State
from allianceauth.eveonline.models import (
    EveAllianceInfo,
    EveCharacter,
    EveCorporationInfo,
)
from allianceauth.tests.auth_utils import AuthUtils
from app_utils.testing import (
    create_user_from_evecharacter,
    multi_assert_in,
    multi_assert_not_in,
)

from memberaudit.models import Character, CharacterSkill, SkillSetGroup
from memberaudit.tests.testdata.factories import (
    create_character,
    create_skill_set,
    create_skill_set_group,
    create_skill_set_skill,
)
from memberaudit.tests.testdata.load_entities import load_entities
from memberaudit.tests.testdata.load_eveuniverse import load_eveuniverse
from memberaudit.tests.utils import (
    add_auth_character_to_user,
    add_memberaudit_character_to_user,
    create_memberaudit_character,
    create_user_from_evecharacter_with_access,
    json_response_to_dict_2,
)
from memberaudit.views.reports import (
    corporation_compliance_report_data,
    reports,
    skill_sets_report_data,
    user_compliance_report_data,
)


class TestReports(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        load_entities()

    def test_can_open_reports_view(self):
        # given
        user, _ = create_user_from_evecharacter(
            1001, permissions=["memberaudit.basic_access", "memberaudit.reports_access"]
        )
        request = self.factory.get(reverse("memberaudit:reports"))
        request.user = user
        # when
        response = reports(request)
        # then
        self.assertEqual(response.status_code, 200)


class TestUserComplianceReportTestData(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.factory = RequestFactory()
        load_eveuniverse()
        load_entities()
        # given
        state = AuthUtils.get_member_state()
        state_alliance = EveAllianceInfo.objects.get(alliance_id=3001)
        state.member_alliances.add(state_alliance)
        state_corporation = EveCorporationInfo.objects.get(corporation_id=2103)
        state.member_corporations.add(state_corporation)
        cls.character_1001 = create_memberaudit_character(
            1001, disconnect_signals=False
        )
        cls.character_1002 = create_memberaudit_character(
            1002, disconnect_signals=False
        )
        cls.character_1003 = create_memberaudit_character(
            1003, disconnect_signals=False
        )
        cls.character_1101 = create_memberaudit_character(
            1101, disconnect_signals=False
        )
        cls.user_1103 = create_user_from_evecharacter_with_access(
            1103, disconnect_signals=False
        )[0]
        cls.user = cls.character_1001.eve_character.character_ownership.user
        cls.user = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.reports_access", cls.user
        )
        AuthUtils.create_user("John Doe")  # this user should not show up in view

    def _execute_request(self) -> dict:
        request = self.factory.get(reverse("memberaudit:user_compliance_report_data"))
        request.user = self.user
        response = user_compliance_report_data(request)
        self.assertEqual(response.status_code, 200)
        return json_response_to_dict_2(response)

    def test_should_show_own_user_only(self):
        # when
        result = self._execute_request()
        # then
        self.assertSetEqual(set(result.keys()), {self.user.pk})

    def test_should_return_non_guests_only(self):
        # given
        self.user = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_everything", self.user
        )
        # when
        result = self._execute_request()
        # then
        self.assertSetEqual(
            set(result.keys()),
            {
                self.character_1001.eve_character.character_ownership.user.pk,
                self.character_1002.eve_character.character_ownership.user.pk,
                self.character_1003.eve_character.character_ownership.user.pk,
                self.user_1103.pk,
            },
        )

    def test_should_include_character_links(self):
        # given
        self.user = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_everything", self.user
        )
        self.user = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.characters_access", self.user
        )
        # when
        result = self._execute_request()
        # then
        self.assertSetEqual(
            set(result.keys()),
            {
                self.character_1001.eve_character.character_ownership.user.pk,
                self.character_1002.eve_character.character_ownership.user.pk,
                self.character_1003.eve_character.character_ownership.user.pk,
                self.user_1103.pk,
            },
        )

    def test_char_counts(self):
        # given
        self.user = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_everything", self.user
        )
        user = self.character_1002.eve_character.character_ownership.user
        add_auth_character_to_user(user, 1103, disconnect_signals=False)
        group, _ = Group.objects.get_or_create(name="Test Group")
        AuthUtils.add_permissions_to_groups(
            [AuthUtils.get_permission_by_name("memberaudit.basic_access")], [group]
        )
        user.groups.add(group)
        # when
        result = self._execute_request()
        # then
        result_1002 = result[user.pk]
        self.assertEqual(result_1002["total_chars"], 2)
        self.assertEqual(result_1002["unregistered_chars"], 1)


class TestCorporationComplianceReportTestData(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        load_eveuniverse()
        load_entities()
        # given
        member_state = State.objects.get(name="Member")
        member_state.member_alliances.add(EveAllianceInfo.objects.get(alliance_id=3001))
        member_state.member_corporations.add(
            EveCorporationInfo.objects.get(corporation_id=2110)
        )
        cls.character_1001 = create_memberaudit_character(
            1001, disconnect_signals=False
        )
        add_auth_character_to_user(
            cls.character_1001.eve_character.character_ownership.user, 1107
        )
        cls.character_1002 = create_memberaudit_character(
            1002, disconnect_signals=False
        )
        add_memberaudit_character_to_user(
            cls.character_1002.eve_character.character_ownership.user, 1104
        )
        add_auth_character_to_user(
            cls.character_1002.eve_character.character_ownership.user, 1105
        )
        add_auth_character_to_user(
            cls.character_1002.eve_character.character_ownership.user, 1106
        )
        cls.character_1003 = create_memberaudit_character(
            1003, disconnect_signals=False
        )
        add_memberaudit_character_to_user(
            cls.character_1003.eve_character.character_ownership.user,
            1101,
            disconnect_signals=False,
        )
        add_memberaudit_character_to_user(
            cls.character_1003.eve_character.character_ownership.user,
            1102,
            disconnect_signals=False,
        )
        cls.user_1103 = create_user_from_evecharacter_with_access(
            1103, disconnect_signals=False
        )[0]
        cls.user = cls.character_1001.eve_character.character_ownership.user
        cls.user = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.reports_access", cls.user
        )
        cls.character_1110 = create_memberaudit_character(
            1110, disconnect_signals=False
        )

    def _corporation_compliance_report_data(self, user) -> dict:
        request = self.factory.get(
            reverse("memberaudit:corporation_compliance_report_data")
        )
        request.user = user
        response = corporation_compliance_report_data(request)
        self.assertEqual(response.status_code, 200)
        return json_response_to_dict_2(response)

    def test_should_return_full_list(self):
        # given
        self.user = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_everything", self.user
        )
        # when
        result = self._corporation_compliance_report_data(self.user)
        # then
        self.assertSetEqual(set(result.keys()), {2001, 2002, 2110})
        row = result[2001]
        self.assertEqual(row["corporation_name"], "Wayne Technologies")
        self.assertEqual(row["mains_count"], 2)
        self.assertEqual(row["characters_count"], 6)
        self.assertEqual(row["unregistered_count"], 3)
        self.assertEqual(row["compliance_percent"], 50)
        self.assertFalse(row["is_compliant"])
        self.assertFalse(row["is_partly_compliant"])
        row = result[2002]
        self.assertEqual(row["corporation_name"], "Wayne Food")
        self.assertEqual(row["mains_count"], 1)
        self.assertEqual(row["characters_count"], 3)
        self.assertEqual(row["unregistered_count"], 0)
        self.assertEqual(row["compliance_percent"], 100)
        self.assertTrue(row["is_compliant"])
        self.assertTrue(row["is_partly_compliant"])

    def test_should_return_my_corporation_only(self):
        # given
        self.user = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_same_corporation", self.user
        )
        # when
        result = self._corporation_compliance_report_data(self.user)
        # then
        self.assertSetEqual(set(result.keys()), {2001})


class TestSkillSetReportData(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.factory = RequestFactory()
        load_eveuniverse()
        load_entities()
        state = AuthUtils.get_member_state()
        state.member_alliances.add(EveAllianceInfo.objects.get(alliance_id=3001))

        # user 1 is manager requesting the report
        cls.character_1001 = create_memberaudit_character(
            1001, disconnect_signals=False
        )
        cls.user = cls.character_1001.eve_character.character_ownership.user
        cls.user = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.reports_access", cls.user
        )
        cls.user = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_everything", cls.user
        )

        # user 2 is normal user and has two characters
        cls.character_1002 = create_memberaudit_character(
            1002, disconnect_signals=False
        )
        cls.character_1101 = add_memberaudit_character_to_user(
            cls.character_1002.eve_character.character_ownership.user,
            1101,
            disconnect_signals=False,
        )
        # cls.character_1003 = create_memberaudit_character(1003)

        cls.skill_type_1 = EveType.objects.get(id=24311)
        cls.skill_type_2 = EveType.objects.get(id=24312)

        AuthUtils.create_user("John Doe")  # this user should not show up in view
        cls.character_1103 = create_memberaudit_character(
            1103, disconnect_signals=False
        )

        # orphaned character, i.e. without a user
        create_character(EveCharacter.objects.get(character_id=1121))

    def test_normal(self):
        def make_data_id(doctrine: SkillSetGroup, character: Character) -> str:
            doctrine_pk = doctrine.pk if doctrine else 0
            return f"{doctrine_pk}_{character.pk}"

        # define doctrines
        ship_1 = create_skill_set(name="Ship 1")
        create_skill_set_skill(
            skill_set=ship_1, eve_type=self.skill_type_1, required_level=3
        )

        ship_2 = create_skill_set(name="Ship 2")
        create_skill_set_skill(
            skill_set=ship_2, eve_type=self.skill_type_1, required_level=5
        )
        create_skill_set_skill(
            skill_set=ship_2, eve_type=self.skill_type_2, required_level=3
        )

        ship_3 = create_skill_set(name="Ship 3")
        create_skill_set_skill(
            skill_set=ship_3, eve_type=self.skill_type_1, required_level=1
        )

        doctrine_1 = create_skill_set_group(name="Alpha")
        doctrine_1.skill_sets.add(ship_1)
        doctrine_1.skill_sets.add(ship_2)

        doctrine_2 = create_skill_set_group(name="Bravo", is_doctrine=True)
        doctrine_2.skill_sets.add(ship_1)

        # character 1002
        CharacterSkill.objects.create(
            character=self.character_1002,
            eve_type=self.skill_type_1,
            active_skill_level=5,
            skillpoints_in_skill=10,
            trained_skill_level=5,
        )
        CharacterSkill.objects.create(
            character=self.character_1002,
            eve_type=self.skill_type_2,
            active_skill_level=2,
            skillpoints_in_skill=10,
            trained_skill_level=2,
        )

        # character 1101
        CharacterSkill.objects.create(
            character=self.character_1101,
            eve_type=self.skill_type_1,
            active_skill_level=5,
            skillpoints_in_skill=10,
            trained_skill_level=5,
        )
        CharacterSkill.objects.create(
            character=self.character_1101,
            eve_type=self.skill_type_2,
            active_skill_level=5,
            skillpoints_in_skill=10,
            trained_skill_level=5,
        )

        self.character_1001.update_skill_sets()
        self.character_1002.update_skill_sets()
        self.character_1101.update_skill_sets()
        self.character_1103.update_skill_sets()

        request = self.factory.get(reverse("memberaudit:skill_sets_report_data"))
        request.user = self.user
        response = skill_sets_report_data(request)

        self.assertEqual(response.status_code, 200)
        data = json_response_to_dict_2(response)
        self.assertEqual(len(data), 9)

        mains = {x["main"] for x in data.values()}
        self.assertSetEqual(mains, {"Bruce Wayne", "Clark Kent"})

        row = data[make_data_id(doctrine_1, self.character_1001)]
        self.assertEqual(row["group"], "Alpha")
        self.assertEqual(row["character"], "Bruce Wayne")
        self.assertEqual(row["main"], "Bruce Wayne")
        self.assertEqual(row["is_main_str"], "yes")
        self.assertTrue(multi_assert_not_in(["Ship 1", "Ship 2"], row["has_required"]))

        row = data[make_data_id(doctrine_1, self.character_1002)]
        self.assertEqual(row["group"], "Alpha")
        self.assertEqual(row["character"], "Clark Kent")
        self.assertEqual(row["main"], "Clark Kent")
        self.assertEqual(row["is_main_str"], "yes")

        self.assertTrue(multi_assert_in(["Ship 1"], row["has_required"]))
        self.assertTrue(multi_assert_not_in(["Ship 2", "Ship 3"], row["has_required"]))

        row = data[make_data_id(doctrine_1, self.character_1101)]
        self.assertEqual(row["group"], "Alpha")
        self.assertEqual(row["character"], "Lex Luther")
        self.assertEqual(row["main"], "Clark Kent")
        self.assertEqual(row["is_main_str"], "no")
        self.assertTrue(multi_assert_in(["Ship 1", "Ship 2"], row["has_required"]))

        row = data[make_data_id(doctrine_2, self.character_1101)]
        self.assertEqual(row["group"], "Doctrine: Bravo")
        self.assertEqual(row["character"], "Lex Luther")
        self.assertEqual(row["main"], "Clark Kent")
        self.assertEqual(row["is_main_str"], "no")
        self.assertTrue(multi_assert_in(["Ship 1"], row["has_required"]))
        self.assertTrue(multi_assert_not_in(["Ship 2"], row["has_required"]))

        row = data[make_data_id(None, self.character_1101)]
        self.assertEqual(row["group"], "[Ungrouped]")
        self.assertEqual(row["character"], "Lex Luther")
        self.assertEqual(row["main"], "Clark Kent")
        self.assertEqual(row["is_main_str"], "no")
        self.assertTrue(multi_assert_in(["Ship 3"], row["has_required"]))

    # def test_can_handle_user_without_main(self):
    #     character = create_memberaudit_character(1102)
    #     user = character.eve_character.character_ownership.user
    #     user.profile.main_character = None
    #     user.profile.save()

    #     ship_1 = create_skill_set(name="Ship 1")
    #     create_skill_set_skill(
    #         skill_set=ship_1, eve_type=self.skill_type_1, required_level=3
    #     )
    #     doctrine_1 = create_skill_set_group(name="Alpha")
    #     doctrine_1.skill_sets.add(ship_1)

    #     request = self.factory.get(reverse("memberaudit:skill_sets_report_data"))
    #     request.user = self.user
    #     response = skill_sets_report_data(request)
    #     data = json_response_to_dict_2(response)
    #     self.assertEqual(len(data), 4)
