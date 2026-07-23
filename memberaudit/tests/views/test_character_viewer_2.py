import datetime as dt
from collections import defaultdict
from http import HTTPStatus
from typing import NamedTuple

from django.test import RequestFactory
from django.urls import reverse
from django.utils.html import strip_tags
from django.utils.timezone import now
from eveuniverse.tests.testdata.factories_2 import (
    EveEntityCharacterFactory,
    EveEntityCorporationFactory,
    EveSolarSystemHighSecFactory,
    EveSolarSystemLowSecFactory,
    ShipTypeFactory,
)

from app_utils.testdata_factories import UserMainFactory
from app_utils.testing import NoSocketsTestCase, generate_invalid_pk, multi_assert_in

from memberaudit.models import (
    CharacterMail,
    CharacterRole,
    CharacterWalletJournalEntry,
    Location,
)
from memberaudit.tests.testdata.factories_2 import (
    CharacterFactory,
    CharacterJumpCloneFactory,
    CharacterJumpCloneImplantFactory,
    CharacterMailFactory,
    CharacterMailLabelFactory,
    CharacterMiningLedgerEntryFactory,
    CharacterPlanetFactory,
    CharacterRoleFactory,
    CharacterSkillFactory,
    CharacterSkillqueueEntryFactory,
    CharacterSkillSetCheck,
    CharacterStandingFactory,
    CharacterTitleFactory,
    CharacterWalletJournalEntryFactory,
    CharacterWalletTransactionFactory,
    CyberimplantTypeFactory,
    LocationStationFactory,
    LocationStructureFactory,
    MailEntityCharacterFactory,
    MailEntityMailingListFactory,
    SkillSetFactory,
    SkillSetGroupFactory,
    SkillSetSkillFactory,
    SpaceshipCommandSkillTypeFactory,
    UserMainBasicAccessFactory,
)
from memberaudit.tests.utils import json_response_to_dict_2, json_response_to_python_2
from memberaudit.views.character_viewer_2 import (
    SkillSetMatchLevel,
    _compile_skill_set_details_row,
    character_jump_clones_data,
    character_mail,
    character_mail_headers_by_label_data,
    character_mail_headers_by_list_data,
    character_mining_ledger_data,
    character_planets_data,
    character_roles_data,
    character_skill_sets_data,
    character_skillqueue_data,
    character_skills_data,
    character_standings_data,
    character_titles_data,
    character_wallet_journal_data,
    character_wallet_transactions_data,
)

MODULE_PATH = "memberaudit.views.character_viewer_2"


class TestCharacterJumpClones(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        cls.user = UserMainBasicAccessFactory()
        cls.character = CharacterFactory(user=cls.user)
        jita = EveSolarSystemHighSecFactory(
            id=30000142,
            name="Jita",
            eve_constellation__id=20000020,
            eve_constellation__name="Kimotoro",
            eve_constellation__eve_region__id=10000002,
            eve_constellation__eve_region__name="The Forge",
        )
        cls.jita_44 = LocationStationFactory(
            id=60003760,
            name="Jita IV - Moon 4 - Caldari Navy Assembly Plant",
            eve_solar_system=jita,
        )
        amamake = EveSolarSystemLowSecFactory(
            id=30002537,
            name="Amamake",
            eve_constellation__id=20000372,
            eve_constellation__name="Hed",
            eve_constellation__eve_region__id=10000030,
            eve_constellation__eve_region__name="Heimatar",
            security_status=0.3,
        )
        cls.structure_1 = LocationStructureFactory(
            id=1000000000001, name="Test Structure Alpha", eve_solar_system=amamake
        )
        cls.high_grade_snake_alpha_type = CyberimplantTypeFactory(
            id=19540, name="High-grade Snake Alpha"
        )
        cls.high_grade_snake_beta_type = CyberimplantTypeFactory(
            id=19551, name="High-grade Snake Beta"
        )

    def test_character_jump_clones_data(self):
        # given
        clone_1 = jump_clone = CharacterJumpCloneFactory(
            character=self.character, location=self.jita_44
        )
        CharacterJumpCloneImplantFactory(
            jump_clone=jump_clone, eve_type=self.high_grade_snake_alpha_type
        )
        CharacterJumpCloneImplantFactory(
            jump_clone=jump_clone, eve_type=self.high_grade_snake_beta_type
        )

        location_2 = Location.objects.create(id=123457890)
        clone_2 = jump_clone = CharacterJumpCloneFactory(
            character=self.character, location=location_2
        )
        request = self.factory.get(
            reverse("memberaudit:character_jump_clones_data", args=[self.character.pk])
        )
        request.user = self.user

        # when
        response = character_jump_clones_data(request, self.character.pk)

        # then
        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = json_response_to_dict_2(response)
        self.assertEqual(len(data), 2)

        row = data[clone_1.pk]
        self.assertEqual(row["region"], "The Forge")
        self.assertIn("Jita", row["solar_system"])
        self.assertEqual(
            row["location"], "Jita IV - Moon 4 - Caldari Navy Assembly Plant"
        )
        self.assertTrue(
            multi_assert_in(
                ["High-grade Snake Alpha", "High-grade Snake Beta"], row["implants"]
            )
        )

        row = data[clone_2.pk]
        self.assertEqual(row["region"], "-")
        self.assertEqual(row["solar_system"], "-")
        self.assertEqual(row["location"], "Unknown location #123457890")
        self.assertEqual(row["implants"], "(none)")


class TestCharacterMiningLedgerData(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        cls.user = UserMainBasicAccessFactory()
        cls.character = CharacterFactory(user=cls.user)

    def test_should_return_data(self):
        # given
        entry = CharacterMiningLedgerEntryFactory(character=self.character)
        request = self.factory.get(
            reverse(
                "memberaudit:character_mining_ledger_data", args=[self.character.pk]
            )
        )
        request.user = self.user

        # when
        response = character_mining_ledger_data(request, self.character.pk)

        # then
        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = json_response_to_python_2(response)
        obj = data[0]
        self.assertEqual(obj["quantity"], entry.quantity)


class TestCharacterPlanetData(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        cls.user = UserMainBasicAccessFactory()
        cls.character = CharacterFactory(user=cls.user)

    def test_should_return_data(self):
        # given
        entry = CharacterPlanetFactory(character=self.character)
        request = self.factory.get(
            reverse("memberaudit:character_planets_data", args=[self.character.pk])
        )
        request.user = self.user

        # when
        response = character_planets_data(request, self.character.pk)

        # then
        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = json_response_to_python_2(response)
        obj = data[0]
        self.assertEqual(obj["num_pins"], entry.num_pins)


class TestCharacterRolesData(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        cls.user = UserMainBasicAccessFactory()
        cls.character = CharacterFactory(user=cls.user)

    def test_should_return_correct_character_roles(self):
        # given
        CharacterRoleFactory(
            character=self.character,
            location=CharacterRole.Location.UNIVERSAL,
            role=CharacterRole.Role.ACCOUNTANT,
        )
        request = self.factory.get(
            reverse("memberaudit:character_roles_data", args=[self.character.pk])
        )
        request.user = self.user
        # when
        response = character_roles_data(request, self.character.pk)
        # then
        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = json_response_to_python_2(response)
        result_map = defaultdict(dict)
        for obj in data:
            result_map[obj["group"]][obj["role"]] = obj["has_role"]

        self.assertTrue(result_map["General Roles"]["Accountant"])
        self.assertFalse(result_map["General Roles"]["Auditor"])

    def test_should_return_nothing_when_no_data(self):
        # given
        request = self.factory.get(
            reverse("memberaudit:character_roles_data", args=[self.character.pk])
        )
        request.user = self.user
        # when
        response = character_roles_data(request, self.character.pk)
        # then
        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = json_response_to_python_2(response)
        self.assertEqual(data, [])


class TestMailData(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        cls.user = UserMainBasicAccessFactory()
        cls.character = CharacterFactory(user=cls.user)
        cls.label_1 = CharacterMailLabelFactory(character=cls.character)
        cls.label_2 = CharacterMailLabelFactory(character=cls.character)
        sender = MailEntityCharacterFactory(name="Clark Kent")
        recipient = MailEntityCharacterFactory(name="Bruce Wayne")
        cls.mailing_list_5 = MailEntityMailingListFactory()
        cls.mail_1 = CharacterMailFactory(
            character=cls.character,
            sender=sender,
            recipients=[recipient, cls.mailing_list_5],
            labels=[cls.label_1],
        )
        cls.mail_2 = CharacterMailFactory(
            character=cls.character, sender=sender, labels=[cls.label_2]
        )
        cls.mail_3 = CharacterMailFactory(
            character=cls.character, sender=cls.mailing_list_5
        )
        cls.mail_4 = CharacterMailFactory(
            character=cls.character, sender=sender, recipients=[cls.mailing_list_5]
        )

    def test_mail_by_Label(self):
        """returns list of mails for given label only"""
        # given
        request = self.factory.get(
            reverse(
                "memberaudit:character_mail_headers_by_label_data",
                args=[self.character.pk, self.label_1.label_id],
            )
        )
        request.user = self.user
        # when
        response = character_mail_headers_by_label_data(
            request, self.character.pk, self.label_1.label_id
        )
        # then
        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = json_response_to_python_2(response)
        self.assertSetEqual({x["mail_id"] for x in data}, {self.mail_1.mail_id})
        row = data[0]
        self.assertEqual(row["mail_id"], self.mail_1.mail_id)
        self.assertEqual(row["from"], "Clark Kent")
        self.assertIn("Bruce Wayne", row["to"])
        self.assertIn(self.mailing_list_5.name, row["to"])

    def test_all_mails(self):
        """can return all mails"""
        # given
        request = self.factory.get(
            reverse(
                "memberaudit:character_mail_headers_by_label_data",
                args=[self.character.pk, 0],
            )
        )
        request.user = self.user
        # when
        response = character_mail_headers_by_label_data(request, self.character.pk, 0)
        # then
        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = json_response_to_python_2(response)
        self.assertSetEqual(
            {x["mail_id"] for x in data},
            {
                self.mail_1.mail_id,
                self.mail_2.mail_id,
                self.mail_3.mail_id,
                self.mail_4.mail_id,
            },
        )

    def test_mail_to_mailing_list(self):
        """can return mail sent to mailing list"""
        # given
        request = self.factory.get(
            reverse(
                "memberaudit:character_mail_headers_by_list_data",
                args=[self.character.pk, self.mailing_list_5.id],
            )
        )
        request.user = self.user
        # when
        response = character_mail_headers_by_list_data(
            request, self.character.pk, self.mailing_list_5.id
        )
        # then
        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = json_response_to_python_2(response)
        self.assertSetEqual(
            {x["mail_id"] for x in data}, {self.mail_1.mail_id, self.mail_4.mail_id}
        )
        row = data[0]
        self.assertIn("Bruce Wayne", row["to"])
        self.assertIn("Mailing List", row["to"])

    def test_character_mail_data_normal(self):
        # given
        request = self.factory.get(
            reverse(
                "memberaudit:character_mail", args=[self.character.pk, self.mail_1.pk]
            )
        )
        request.user = self.user
        # when
        response = character_mail(request, self.character.pk, self.mail_1.pk)
        # then
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_character_mail_data_normal_special_chars(self):
        # given
        mail = CharacterMailFactory(character=self.character, body="{}abc")
        request = self.factory.get(
            reverse("memberaudit:character_mail", args=[self.character.pk, mail.pk])
        )
        request.user = self.user
        # when
        response = character_mail(request, self.character.pk, mail.pk)
        # then
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_character_mail_data_error(self):
        invalid_mail_pk = generate_invalid_pk(CharacterMail)
        request = self.factory.get(
            reverse(
                "memberaudit:character_mail",
                args=[self.character.pk, invalid_mail_pk],
            )
        )
        request.user = self.user
        response = character_mail(request, self.character.pk, invalid_mail_pk)
        self.assertEqual(response.status_code, 404)


class TestSkillSetsData(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
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

    def test_skill_sets_data(self):
        # given
        user = UserMainFactory(
            permissions=["memberaudit.basic_access", "memberaudit.view_skill_sets"]
        )
        character = CharacterFactory(user=user)
        CharacterSkillFactory(
            character=character,
            eve_type=self.amarr_carrier_skill_type,
            active_skill_level=4,
        )
        CharacterSkillFactory(
            character=character,
            eve_type=self.caldari_carrier_skill_type,
            active_skill_level=2,
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

        # should not show invisible skill sets
        SkillSetFactory(name="Ship 4", is_visible=False)

        character.update_skill_sets()

        request = self.factory.get(
            reverse("memberaudit:character_skill_sets_data", args=[character.pk])
        )
        request.user = user

        # when
        response = character_skill_sets_data(request, character.pk)

        # then
        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = json_response_to_python_2(response)
        self.assertEqual(len(data), 4)

        row = data[0]
        self.assertEqual(row["group"], "[Ungrouped]")
        self.assertEqual(row["skill_set_name"], "Ship 3")
        self.assertTrue(row["has_required"])
        self.assertEqual(row["failed_required_skills"], "-")
        url = reverse(
            "memberaudit:character_skill_set_details",
            args=[character.pk, ship_3.id],
        )
        self.assertIn(url, row["action"])

        row = data[1]
        self.assertEqual(row["group"], "Alpha")
        self.assertEqual(row["skill_set_name"], "Ship 1")
        self.assertTrue(row["has_required"])
        self.assertEqual(row["failed_required_skills"], "-")
        self.assertIn("Amarr Carrier&nbsp;V", row["failed_recommended_skills"])
        url = reverse(
            "memberaudit:character_skill_set_details",
            args=[character.pk, ship_1.id],
        )
        self.assertIn(url, row["action"])

        row = data[2]
        self.assertEqual(row["group"], "Alpha")
        self.assertEqual(row["skill_set_name"], "Ship 2")
        self.assertFalse(row["has_required"])
        self.assertIn("Caldari Carrier&nbsp;III", row["failed_required_skills"])
        url = reverse(
            "memberaudit:character_skill_set_details",
            args=[character.pk, ship_2.id],
        )
        self.assertIn(url, row["action"])

        row = data[3]
        self.assertEqual(row["group"], "Doctrine: Bravo")
        self.assertEqual(row["skill_set_name"], "Ship 1")
        self.assertTrue(row["has_required"])
        self.assertEqual(row["failed_required_skills"], "-")
        url = reverse(
            "memberaudit:character_skill_set_details",
            args=[character.pk, ship_1.id],
        )
        self.assertIn(url, row["action"])

    def test_need_permission_to_see_data(self):
        # given
        user = UserMainFactory(permissions=["memberaudit.basic_access"])
        character = CharacterFactory(user=user)

        request = self.factory.get(
            reverse("memberaudit:character_skill_sets_data", args=[character.pk])
        )
        request.user = user

        # when
        response = character_skill_sets_data(request, character.pk)

        # then
        self.assertEqual(response.status_code, HTTPStatus.FOUND)


class TestSkillSetsDetails(NoSocketsTestCase):
    def test_should_show_details(self):
        # given
        user = UserMainFactory(
            permissions=["memberaudit.basic_access", "memberaudit.view_skill_sets"]
        )
        character = CharacterFactory(user=user)

        skill_1_type = SpaceshipCommandSkillTypeFactory(name="Alpha")
        skill_2_type = SpaceshipCommandSkillTypeFactory(name="Bravo")
        CharacterSkillFactory(
            character=character,
            eve_type=skill_1_type,
            active_skill_level=4,
        )
        CharacterSkillFactory(
            character=character,
            eve_type=skill_2_type,
            active_skill_level=2,
        )
        skill_set = SkillSetFactory()
        SkillSetSkillFactory(
            skill_set=skill_set,
            eve_type=skill_1_type,
            required_level=3,
            recommended_level=5,
        )
        SkillSetSkillFactory(
            skill_set=skill_set,
            eve_type=skill_2_type,
            required_level=3,
            recommended_level=None,
        )

        character.update_skill_sets()
        self.client.force_login(user)

        # when
        response = self.client.get(
            reverse(
                "memberaudit:character_skill_set_details",
                args=[character.pk, skill_set.pk],
            )
        )

        # then
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(skill_set.name, response.context["name"])
        self.assertContains(response, skill_1_type.name)
        self.assertContains(response, skill_2_type.name)
        self.assertIn("Bravo", response.context["missing_skills_str"])
        self.assertNotIn("Alpha", response.context["missing_skills_str"])
        self.assertFalse(response.context["met_all_required"])

    def test_need_permission_to_see_data(self):
        # given
        user = UserMainFactory(permissions=["memberaudit.basic_access"])
        character = CharacterFactory(user=user)
        skill_set = SkillSetFactory()
        self.client.force_login(user)

        # when
        response = self.client.get(
            reverse(
                "memberaudit:character_skill_set_details",
                args=[character.pk, skill_set.pk],
            )
        )

        # then
        self.assertEqual(response.status_code, HTTPStatus.FOUND)


class TestCompileSkillSetDetailsRow(NoSocketsTestCase):
    def test_should_return_correct_result(self):
        # given
        skill_type = SpaceshipCommandSkillTypeFactory()

        class Case(NamedTuple):
            name: str
            required: int
            recommended: int
            active: int
            result: SkillSetMatchLevel

        cases = [
            Case("has recommended", 3, 5, 5, SkillSetMatchLevel.FULL),
            Case("has required", 3, 5, 3, SkillSetMatchLevel.PARTIAL),
            Case("below required", 3, 5, 2, SkillSetMatchLevel.NONE),
            Case("skill not trained", 3, 5, 0, SkillSetMatchLevel.NONE),
            Case("no required", None, 5, 1, SkillSetMatchLevel.PARTIAL),
            Case(
                "no required and skill not trained",
                None,
                5,
                0,
                SkillSetMatchLevel.PARTIAL,
            ),
        ]

        for tc in cases:
            skill_set = SkillSetFactory()
            skill = SkillSetSkillFactory(
                skill_set=skill_set,
                eve_type=skill_type,
                required_level=tc.required,
                recommended_level=tc.recommended,
            )
            character = CharacterFactory()
            if tc.active:
                character_skill = CharacterSkillFactory(
                    character=character,
                    eve_type=skill_type,
                    active_skill_level=tc.active,
                )
            else:
                character_skill = None

            character.update_skill_sets()
            check: CharacterSkillSetCheck = character.skill_set_checks.first()
            failed_recommended = set(check.failed_recommended_skills.all())
            failed_required = set(check.failed_required_skills.all())

            # when
            _, result = _compile_skill_set_details_row(
                character_skill=character_skill,
                skill=skill,
                has_check=True,
                failed_recommended=failed_recommended,
                failed_required=failed_required,
            )

            # then
            self.assertEqual(result, tc.result, msg=tc.name)

            character.delete()
            skill_set.delete()


class TestSkills(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        cls.user = UserMainBasicAccessFactory()
        cls.character = CharacterFactory(user=cls.user)
        cls.amarr_carrier_skill_type = SpaceshipCommandSkillTypeFactory(
            name="Amarr Carrier"
        )

    def test_can_render_skills_data(self):
        # given
        CharacterSkillFactory(
            character=self.character,
            eve_type=self.amarr_carrier_skill_type,
            active_skill_level=1,
            skillpoints_in_skill=1000,
            trained_skill_level=1,
        )
        request = self.factory.get(
            reverse("memberaudit:character_skills_data", args=[self.character.pk])
        )
        request.user = self.user

        # when
        response = character_skills_data(request, self.character.pk)

        # then
        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = json_response_to_python_2(response)
        self.assertEqual(len(data), 1)
        row = data[0]
        self.assertEqual(row["group"], "Spaceship Command")
        self.assertEqual(row["skill"], "Amarr Carrier")
        self.assertEqual(row["level"], 1)


class TestSkillqueue(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        cls.user = UserMainBasicAccessFactory()
        cls.character = CharacterFactory(user=cls.user)
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

    def test_can_render_active_skillqueue(self):
        # given
        finish_date_1 = now() - dt.timedelta(days=1)
        CharacterSkillqueueEntryFactory(
            character=self.character,
            eve_type=self.gallente_carrier_skill_type,
            finished_level=5,
            queue_position=0,
            start_date=now() - dt.timedelta(days=3),
            finish_date=finish_date_1,
            level_start_sp=0,
            level_end_sp=100,
        )
        finish_date_2 = now() + dt.timedelta(days=3)
        CharacterSkillqueueEntryFactory(
            character=self.character,
            eve_type=self.amarr_carrier_skill_type,
            finished_level=5,
            queue_position=1,
            start_date=finish_date_1,
            finish_date=finish_date_2,
            level_start_sp=0,
            level_end_sp=100,
        )
        finish_date_3 = now() + dt.timedelta(days=10)
        CharacterSkillqueueEntryFactory(
            character=self.character,
            eve_type=self.caldari_carrier_skill_type,
            finish_date=finish_date_3,
            finished_level=5,
            queue_position=2,
            start_date=finish_date_2,
        )
        request = self.factory.get(
            reverse("memberaudit:character_skillqueue_data", args=[self.character.pk])
        )
        request.user = self.user

        # when
        response = character_skillqueue_data(request, self.character.pk)

        # then
        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = json_response_to_python_2(response)
        self.assertEqual(len(data), 3)

        row = data[0]
        self.assertFalse(row["is_active"])
        self.assertTrue(row["is_completed"])
        self.assertEqual(strip_tags(row["skill_html"]), "Gallente Carrier V")
        self.assertEqual(strip_tags(row["remaining_html"]), "Completed")

        row = data[1]
        self.assertTrue(row["is_active"])
        self.assertFalse(row["is_completed"])
        self.assertEqual(strip_tags(row["skill_html"]), "Amarr Carrier V (25%)")
        self.assertEqual(strip_tags(row["remaining_html"]), "2 days")

        row = data[2]
        self.assertFalse(row["is_active"])
        self.assertFalse(row["is_completed"])
        self.assertEqual(strip_tags(row["skill_html"]), "Caldari Carrier V")
        self.assertEqual(strip_tags(row["remaining_html"]), "7 days")

    def test_should_not_show_any_skill_when_not_active(self):
        CharacterSkillqueueEntryFactory(
            character=self.character,
            eve_type=self.amarr_carrier_skill_type,
            finish_date=None,
            finished_level=5,
            queue_position=0,
        )
        request = self.factory.get(
            reverse("memberaudit:character_skillqueue_data", args=[self.character.pk])
        )
        request.user = self.user
        response = character_skillqueue_data(request, self.character.pk)
        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = json_response_to_python_2(response)
        self.assertEqual(len(data), 0)


class TestStandings(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        cls.user = UserMainBasicAccessFactory()
        cls.character = CharacterFactory(user=cls.user)

    def test_should_produce_character_standings_data(self):
        # given
        npc_corp = EveEntityCorporationFactory(id=2901, name="NPC corporation")
        CharacterStandingFactory(
            character=self.character, eve_entity=npc_corp, standing=5.0
        )
        request = self.factory.get(
            reverse("memberaudit:character_standings_data", args=[self.character.pk])
        )
        request.user = self.user

        # when
        response = character_standings_data(request, self.character.pk)

        # then
        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = json_response_to_dict_2(response)
        obj = data[2901]
        self.assertEqual("NPC corporation", obj["name"]["sort"])
        self.assertEqual(obj["type"], "Corporation")
        self.assertEqual(obj["standing"]["sort"], 5.0)


class TestCharacterTitlesData(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        cls.user = UserMainBasicAccessFactory()
        cls.character = CharacterFactory(user=cls.user)

    def test_should_return_correct_character_titles(self):
        # given
        CharacterTitleFactory(character=self.character, name="Bravo", title_id=2)
        CharacterTitleFactory(character=self.character, name="Alpha", title_id=1)
        request = self.factory.get(
            reverse("memberaudit:character_roles_data", args=[self.character.pk])
        )
        request.user = self.user
        # when
        response = character_titles_data(request, self.character.pk)
        # then
        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = json_response_to_python_2(response)
        names = [obj["name"] for obj in data]
        self.assertListEqual(names, ["Alpha", "Bravo"])

    def test_should_return_nothing_when_no_data(self):
        # given
        request = self.factory.get(
            reverse("memberaudit:character_titles_data", args=[self.character.pk])
        )
        request.user = self.user
        # when
        response = character_titles_data(request, self.character.pk)
        # then
        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = json_response_to_python_2(response)
        self.assertEqual(data, [])


class TestWalletJournal(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        cls.user = UserMainBasicAccessFactory()
        cls.character = CharacterFactory(user=cls.user)
        cls.entity_1001 = EveEntityCharacterFactory(id=1001, name="Bruce Wayne")
        cls.entity_1002 = EveEntityCharacterFactory(id=1002, name="Clark Kent")

    def test_character_wallet_journal_data(self):
        # given
        CharacterWalletJournalEntryFactory(
            character=self.character,
            entry_id=1,
            amount=1000000,
            balance=10000000,
            context_id_type=CharacterWalletJournalEntry.CONTEXT_ID_TYPE_UNDEFINED,
            date=now(),
            description="dummy",
            first_party=self.entity_1001,
            second_party=self.entity_1002,
        )
        request = self.factory.get(
            reverse(
                "memberaudit:character_wallet_journal_data", args=[self.character.pk]
            )
        )
        request.user = self.user
        # when
        response = character_wallet_journal_data(request, self.character.pk)
        # then
        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = json_response_to_python_2(response)
        self.assertEqual(len(data), 1)
        row = data[0]
        self.assertEqual(row["amount"], 1000000.00)
        self.assertEqual(row["balance"], 10000000.00)


class TestWalletTransactions(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        cls.user = UserMainBasicAccessFactory()
        cls.character = CharacterFactory(user=cls.user)
        jita = EveSolarSystemHighSecFactory(
            id=30000142,
            name="Jita",
            eve_constellation__id=20000020,
            eve_constellation__name="Kimotoro",
            eve_constellation__eve_region__id=10000002,
            eve_constellation__eve_region__name="The Forge",
        )
        cls.jita_44 = LocationStationFactory(
            id=60003760,
            name="Jita IV - Moon 4 - Caldari Navy Assembly Plant",
            eve_solar_system=jita,
        )
        cls.merlin_type = ShipTypeFactory(
            id=603,
            name="Merlin",
            eve_group__id=25,
            eve_group__name="Frigate",
            volume=16500.0,
        )
        cls.entity_1002 = EveEntityCharacterFactory(id=1002, name="Clark Kent")

    def test_character_wallet_transaction_data(self):
        # given
        my_date = now()
        CharacterWalletTransactionFactory(
            character=self.character,
            client=self.entity_1002,
            date=my_date,
            location=self.jita_44,
            quantity=3,
            eve_type=self.merlin_type,
            unit_price=450000.99,
        )
        request = self.factory.get(
            reverse(
                "memberaudit:character_wallet_transactions_data",
                args=[self.character.pk],
            )
        )
        request.user = self.user

        # when
        response = character_wallet_transactions_data(request, self.character.pk)

        # then
        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = json_response_to_python_2(response)
        self.assertEqual(len(data), 1)
        row = data[0]
        self.assertEqual(row["date"], my_date.isoformat())
        self.assertEqual(row["quantity"], 3)
        self.assertEqual(row["type"], "Merlin")
        self.assertEqual(row["unit_price"], 450_000.99)
        self.assertEqual(row["total"], -1_350_002.97)
        self.assertEqual(row["client"], "Clark Kent")
        self.assertEqual(
            row["location"], "Jita IV - Moon 4 - Caldari Navy Assembly Plant"
        )
