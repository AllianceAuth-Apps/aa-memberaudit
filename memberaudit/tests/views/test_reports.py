from http import HTTPStatus

from django.contrib.auth.models import User
from django.test import RequestFactory
from django.urls import reverse

from allianceauth.tests.auth_utils import AuthUtils
from app_utils.testdata_factories import (
    EveAllianceInfoFactory,
    EveCharacterFactory,
    EveCorporationInfoFactory,
    UserMainFactory,
)
from app_utils.testing import (
    NoSocketsTestCase,
    add_character_to_user,
    multi_assert_in,
    multi_assert_not_in,
)

from memberaudit.models import Character, CharacterSkill, SkillSetGroup
from memberaudit.tests.testdata.factories_2 import (
    CharacterFactory,
    CharacterOrphanFactory,
    NavigationSkillTypeFactory,
    SkillSetFactory,
    SkillSetGroupFactory,
    SkillSetSkillFactory,
)
from memberaudit.tests.utils import json_response_to_dict_2
from memberaudit.views.reports import (
    corporation_compliance_report_data,
    reports,
    skill_sets_report_data,
    user_compliance_report_data,
)


class TestReports(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.factory = RequestFactory()

    def test_can_open_reports_view(self):
        # given
        user = UserMainFactory(
            permissions__=["memberaudit.basic_access", "memberaudit.reports_access"]
        )
        request = self.factory.get(reverse("memberaudit:reports"))
        request.user = user
        # when
        response = reports(request)
        # then
        self.assertEqual(response.status_code, HTTPStatus.OK)


class TestUserComplianceReportTestData_UserFilter(NoSocketsTestCase):
    user_compliance_report_data_view_name = "memberaudit:user_compliance_report_data"

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.factory = RequestFactory()

        cls.alliance_3001 = EveAllianceInfoFactory()
        cls.corporation_2001 = EveCorporationInfoFactory(alliance=cls.alliance_3001)
        cls.corporation_2002 = EveCorporationInfoFactory(alliance=cls.alliance_3001)
        cls.corporation_2103 = EveCorporationInfoFactory()
        cls.member_state = AuthUtils.get_member_state()
        cls.member_state.member_alliances.add(cls.alliance_3001)
        cls.member_state.member_corporations.add(cls.corporation_2103)

        cls.user_1001 = UserMainFactory(
            username="user_1001",
            main_character__character=EveCharacterFactory(
                corporation=cls.corporation_2001
            ),
            permissions__=["memberaudit.basic_access"],
        )
        CharacterFactory(id=1001, user=cls.user_1001)

        cls.user_1002 = UserMainFactory(
            username="user_1002",
            main_character__character=EveCharacterFactory(
                corporation=cls.corporation_2001
            ),
            permissions__=["memberaudit.basic_access"],
        )
        CharacterFactory(id=1002, user=cls.user_1002)

        cls.user_1003 = UserMainFactory(
            username="user_1003",
            main_character__character=EveCharacterFactory(
                corporation=cls.corporation_2002
            ),
            permissions__=["memberaudit.basic_access"],
        )
        CharacterFactory(id=1003, user=cls.user_1003)

        cls.user_1101 = UserMainFactory(
            username="user_1101",
            main_character__character=EveCharacterFactory(
                corporation=cls.corporation_2103
            ),
            permissions__=["memberaudit.basic_access"],
        )
        CharacterFactory(id=1101, user=cls.user_1101)

        cls.user_1103 = UserMainFactory(
            username="user_1103",
            permissions__=["memberaudit.basic_access"],
        )
        CharacterFactory(id=1103, user=cls.user_1103)

        UserMainFactory(username="user_XXX")  # this user should not show up in any view

    def _execute_request(self, user) -> list[User]:
        request = self.factory.get(reverse(self.user_compliance_report_data_view_name))
        request.user = user
        response = user_compliance_report_data(request)
        self.assertEqual(response.status_code, HTTPStatus.OK)
        result = json_response_to_dict_2(response)
        return [User.objects.get(pk=pk) for pk in result.keys()]

    def test_should_show_own_user_only_when_member_and_reports_access(self):
        # given
        user = UserMainFactory(
            main_character__character=EveCharacterFactory(
                corporation__alliance=self.alliance_3001
            ),
            permissions__=["memberaudit.basic_access", "memberaudit.reports_access"],
        )
        CharacterFactory(user=user)

        # when
        got = self._execute_request(user)

        # then
        self.assertCountEqual(got, [user])

    def test_should_return_non_guests_only(self):
        # given
        user = UserMainFactory(
            main_character__character=EveCharacterFactory(
                corporation__alliance=self.alliance_3001
            ),
            permissions__=[
                "memberaudit.basic_access",
                "memberaudit.reports_access",
                "memberaudit.view_everything",
            ],
        )
        # when
        got = self._execute_request(user)

        # then
        want = [
            user,
            self.user_1001,
            self.user_1002,
            self.user_1003,
            self.user_1101,
        ]
        self.assertCountEqual(got, want)

    def test_should_include_character_links(self):
        # given
        user = UserMainFactory(
            main_character__character=EveCharacterFactory(
                corporation__alliance=self.alliance_3001
            ),
            permissions__=[
                "memberaudit.basic_access",
                "memberaudit.reports_access",
                "memberaudit.view_everything",
                "memberaudit.characters_access",
            ],
        )
        # when
        got = self._execute_request(user)

        # then
        want = [
            user,
            self.user_1001,
            self.user_1002,
            self.user_1003,
            self.user_1101,
        ]
        self.assertCountEqual(got, want)


class TestUserComplianceReportTestData_Counts(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.factory = RequestFactory()

    def test_char_counts(self):
        # given
        corporation = EveCorporationInfoFactory()
        member_state = AuthUtils.get_member_state()
        member_state.member_corporations.add(corporation)
        user = UserMainFactory(
            main_character__character=EveCharacterFactory(corporation=corporation),
            permissions__=[
                "memberaudit.basic_access",
                "memberaudit.reports_access",
                "memberaudit.view_everything",
            ],
        )
        CharacterFactory(user=user)
        add_character_to_user(user=user, character=EveCharacterFactory())

        # when
        request = self.factory.get(reverse("memberaudit:user_compliance_report_data"))
        request.user = user
        response = user_compliance_report_data(request)
        self.assertEqual(response.status_code, HTTPStatus.OK)
        result = json_response_to_dict_2(response)

        # then
        result_1002 = result[user.pk]
        self.assertEqual(result_1002["total_chars"], 2)
        self.assertEqual(result_1002["unregistered_chars"], 1)


class TestCorporationComplianceReportTestData(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()

    def test_should_return_full_list(self):
        # given
        alliance_3001 = EveAllianceInfoFactory()
        corporation_2001 = EveCorporationInfoFactory(
            corporation_id=2001,
            corporation_name="Wayne Technologies",
            alliance=alliance_3001,
        )
        corporation_2002 = EveCorporationInfoFactory(
            corporation_id=2002, corporation_name="Wayne Foods", alliance=alliance_3001
        )
        corporation_2110 = EveCorporationInfoFactory(corporation_id=2110)
        member_state = AuthUtils.get_member_state()
        member_state.member_alliances.add(alliance_3001)
        member_state.member_corporations.add(corporation_2110)

        user_1001 = UserMainFactory(
            username="user_1001",
            main_character__character=EveCharacterFactory(corporation=corporation_2001),
            permissions__=[
                "memberaudit.basic_access",
                "memberaudit.reports_access",
                "memberaudit.view_everything",
            ],
        )
        CharacterFactory(id=1001, user=user_1001)
        CharacterFactory(id=1011, user=user_1001, is_main=False)

        user_1002 = UserMainFactory(
            username="user_1002",
            main_character__character=EveCharacterFactory(corporation=corporation_2001),
            permissions__=["memberaudit.basic_access"],
        )
        CharacterFactory(id=1002, user=user_1002)
        add_character_to_user(user_1002, EveCharacterFactory())
        add_character_to_user(user_1002, EveCharacterFactory())
        add_character_to_user(user_1002, EveCharacterFactory())

        user_1003 = UserMainFactory(
            username="user_1003",
            main_character__character=EveCharacterFactory(corporation=corporation_2002),
            permissions__=["memberaudit.basic_access"],
        )
        CharacterFactory(id=1003, user=user_1003, is_main=True)
        CharacterFactory(id=1031, user=user_1003, is_main=False)
        CharacterFactory(id=1032, user=user_1003, is_main=False)

        user_1101 = UserMainFactory(
            username="user_1101",
            main_character__character=EveCharacterFactory(corporation=corporation_2110),
            permissions__=["memberaudit.basic_access"],
        )
        CharacterFactory(id=1101, user=user_1101)

        user_1103 = UserMainFactory(
            username="user_1103",
            permissions__=["memberaudit.basic_access"],
        )
        CharacterFactory(id=1103, user=user_1103)

        UserMainFactory(username="user_XXX")  # this user should not show up in any view

        # when
        request = self.factory.get(
            reverse("memberaudit:corporation_compliance_report_data")
        )
        request.user = user_1001
        response = corporation_compliance_report_data(request)
        self.assertEqual(response.status_code, HTTPStatus.OK)
        result = json_response_to_dict_2(response)

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
        self.assertEqual(row["corporation_name"], "Wayne Foods")
        self.assertEqual(row["mains_count"], 1)
        self.assertEqual(row["characters_count"], 3)
        self.assertEqual(row["unregistered_count"], 0)
        self.assertEqual(row["compliance_percent"], 100)
        self.assertTrue(row["is_compliant"])
        self.assertTrue(row["is_partly_compliant"])


class TestSkillSetReportData(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.factory = RequestFactory()

        alliance_3001 = EveAllianceInfoFactory()
        corporation_2001 = EveCorporationInfoFactory(alliance=alliance_3001)
        corporation_2002 = EveCorporationInfoFactory(alliance=alliance_3001)
        state = AuthUtils.get_member_state()
        state.member_alliances.add(alliance_3001)

        cls.user = UserMainFactory(
            main_character__character=EveCharacterFactory(
                character_name="Bruce Wayne", corporation=corporation_2001
            ),
            permissions__=[
                "memberaudit.basic_access",
                "memberaudit.reports_access",
                "memberaudit.view_everything",
            ],
        )
        cls.character_1001 = CharacterFactory(id=1001, user=cls.user)

        user_1002 = UserMainFactory(
            main_character__character=EveCharacterFactory(
                character_name="Clark Kent", corporation=corporation_2001
            ),
            permissions__=["memberaudit.basic_access"],
        )
        cls.character_1002 = CharacterFactory(id=1002, user=user_1002, is_main=True)
        cls.character_1101 = CharacterFactory(
            id=1101,
            alt_character=EveCharacterFactory(character_name="Lex Luther"),
            user=user_1002,
            is_main=False,
        )

        user_1003 = UserMainFactory(
            main_character__character=EveCharacterFactory(corporation=corporation_2002),
            permissions__=["memberaudit.basic_access"],
        )
        cls.character_1003 = CharacterFactory(id=1003, user=user_1003)

        user_1103 = UserMainFactory(permissions__=["memberaudit.basic_access"])
        cls.character_1103 = CharacterFactory(id=1103, user=user_1103)

        cls.skill_type_1 = NavigationSkillTypeFactory()
        cls.skill_type_2 = NavigationSkillTypeFactory()

        UserMainFactory(username="user_XXX")  # this user should not show up in any view
        CharacterOrphanFactory(id=1121)

    def test_normal(self):
        # define doctrines
        ship_1 = SkillSetFactory(name="Ship 1")
        SkillSetSkillFactory(
            skill_set=ship_1, eve_type=self.skill_type_1, required_level=3
        )

        ship_2 = SkillSetFactory(name="Ship 2")
        SkillSetSkillFactory(
            skill_set=ship_2, eve_type=self.skill_type_1, required_level=5
        )
        SkillSetSkillFactory(
            skill_set=ship_2, eve_type=self.skill_type_2, required_level=3
        )

        ship_3 = SkillSetFactory(name="Ship 3")
        SkillSetSkillFactory(
            skill_set=ship_3, eve_type=self.skill_type_1, required_level=1
        )

        doctrine_1 = SkillSetGroupFactory(name="Alpha")
        doctrine_1.skill_sets.add(ship_1)
        doctrine_1.skill_sets.add(ship_2)

        doctrine_2 = SkillSetGroupFactory(name="Bravo", is_doctrine=True)
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

        self.assertEqual(response.status_code, HTTPStatus.OK)
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
    #     character = CharacterFactory(1102)
    #     user = character.eve_character.character_ownership.user
    #     user.profile.main_character = None
    #     user.profile.save()

    #     ship_1 = SkillSetFactory(name="Ship 1")
    #     SkillSetSkillFactory(
    #         skill_set=ship_1, eve_type=self.skill_type_1, required_level=3
    #     )
    #     doctrine_1 = SkillSetGroupFactory(name="Alpha")
    #     doctrine_1.skill_sets.add(ship_1)

    #     request = self.factory.get(reverse("memberaudit:skill_sets_report_data"))
    #     request.user = self.user
    #     response = skill_sets_report_data(request)
    #     data = json_response_to_dict_2(response)
    #     self.assertEqual(len(data), 4)


def make_data_id(doctrine: SkillSetGroup, character: Character) -> str:
    doctrine_pk = doctrine.pk if doctrine else 0
    return f"{doctrine_pk}_{character.pk}"
