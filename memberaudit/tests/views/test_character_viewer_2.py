import datetime as dt
from collections import defaultdict

from bs4 import BeautifulSoup

from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils.timezone import now
from eveuniverse.models import EveEntity, EveType

from allianceauth.tests.auth_utils import AuthUtils
from app_utils.testing import (
    NoSocketsTestCase,
    generate_invalid_pk,
    multi_assert_in,
    response_text,
)

from memberaudit.models import (
    CharacterMail,
    CharacterRole,
    CharacterWalletJournalEntry,
    Location,
)
from memberaudit.tests.testdata.factories import (
    create_character_jump_clone,
    create_character_jump_clone_implant,
    create_character_mail,
    create_character_mail_label,
    create_character_mining_ledger_entry,
    create_character_planet,
    create_character_role,
    create_character_skill,
    create_character_skillqueue_entry,
    create_character_standing,
    create_character_title,
    create_character_wallet_journal_entry,
    create_character_wallet_transaction,
    create_location,
    create_mail_entity_from_eve_entity,
    create_mailing_list,
    create_skill_set,
    create_skill_set_group,
    create_skill_set_skill,
)
from memberaudit.tests.testdata.load_entities import load_entities
from memberaudit.tests.testdata.load_eveuniverse import load_eveuniverse
from memberaudit.tests.testdata.load_locations import load_locations
from memberaudit.tests.utils import (
    create_memberaudit_character,
    json_response_to_dict_2,
    json_response_to_python_2,
)
from memberaudit.views.character_viewer_2 import (
    character_jump_clones_data,
    character_mail,
    character_mail_headers_by_label_data,
    character_mail_headers_by_list_data,
    character_mining_ledger_data,
    character_planets_data,
    character_roles_data,
    character_skill_set_details,
    character_skill_sets_data,
    character_skillqueue_data,
    character_skills_data,
    character_standings_data,
    character_titles_data,
    character_wallet_journal_data,
    character_wallet_transactions_data,
)

MODULE_PATH = "memberaudit.views.character_viewer_2"


class TestJumpClones(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        load_eveuniverse()
        load_entities()
        load_locations()
        cls.character = create_memberaudit_character(1001)
        cls.user = cls.character.user
        cls.jita_44 = Location.objects.get(id=60003760)
        cls.structure_1 = Location.objects.get(id=1000000000001)

    def test_character_jump_clones_data(self):
        clone_1 = jump_clone = create_character_jump_clone(
            character=self.character, location=self.jita_44
        )
        create_character_jump_clone_implant(
            jump_clone=jump_clone,
            eve_type=EveType.objects.get(name="High-grade Snake Alpha"),
        )
        create_character_jump_clone_implant(
            jump_clone=jump_clone,
            eve_type=EveType.objects.get(name="High-grade Snake Beta"),
        )

        location_2 = create_location(id=123457890, eve_type=None, eve_solar_system=None)
        clone_2 = jump_clone = create_character_jump_clone(
            character=self.character, location=location_2
        )
        request = self.factory.get(
            reverse("memberaudit:character_jump_clones_data", args=[self.character.pk])
        )
        request.user = self.user
        response = character_jump_clones_data(request, self.character.pk)
        self.assertEqual(response.status_code, 200)
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
        load_eveuniverse()
        load_entities()
        cls.character = create_memberaudit_character(1001)
        cls.user = cls.character.eve_character.character_ownership.user

    def test_should_return_data(self):
        # given
        entry = create_character_mining_ledger_entry(self.character)
        request = self.factory.get(
            reverse(
                "memberaudit:character_mining_ledger_data", args=[self.character.pk]
            )
        )
        request.user = self.user
        # when
        response = character_mining_ledger_data(request, self.character.pk)
        # then
        self.assertEqual(response.status_code, 200)
        data = json_response_to_python_2(response)
        obj = data[0]
        self.assertEqual(obj["quantity"], entry.quantity)


class TestCharacterPlanetData(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        load_eveuniverse()
        load_entities()
        cls.character = create_memberaudit_character(1001)
        cls.user = cls.character.eve_character.character_ownership.user

    def test_should_return_data(self):
        # given
        entry = create_character_planet(self.character)
        request = self.factory.get(
            reverse("memberaudit:character_planets_data", args=[self.character.pk])
        )
        request.user = self.user
        # when
        response = character_planets_data(request, self.character.pk)
        # then
        self.assertEqual(response.status_code, 200)
        data = json_response_to_python_2(response)
        obj = data[0]
        self.assertEqual(obj["num_pins"], entry.num_pins)


class TestCharacterRolesData(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        load_eveuniverse()
        load_entities()
        cls.character = create_memberaudit_character(1001)
        cls.user = cls.character.eve_character.character_ownership.user

    def test_should_return_correct_character_roles(self):
        # given
        create_character_role(
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
        self.assertEqual(response.status_code, 200)
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
        self.assertEqual(response.status_code, 200)
        data = json_response_to_python_2(response)
        self.assertEqual(data, [])


class TestMailData(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        load_eveuniverse()
        load_entities()
        cls.character = create_memberaudit_character(1001)
        cls.user = cls.character.eve_character.character_ownership.user
        cls.corporation_2001 = EveEntity.objects.get(id=2001)
        cls.label_1 = create_character_mail_label(character=cls.character)
        cls.label_2 = create_character_mail_label(character=cls.character)
        sender_1002 = create_mail_entity_from_eve_entity(id=1002)
        recipient_1001 = create_mail_entity_from_eve_entity(id=1001)
        cls.mailing_list_5 = create_mailing_list()
        cls.mail_1 = create_character_mail(
            character=cls.character,
            sender=sender_1002,
            recipients=[recipient_1001, cls.mailing_list_5],
            labels=[cls.label_1],
        )
        cls.mail_2 = create_character_mail(
            character=cls.character, sender=sender_1002, labels=[cls.label_2]
        )
        cls.mail_3 = create_character_mail(
            character=cls.character, sender=cls.mailing_list_5
        )
        cls.mail_4 = create_character_mail(
            character=cls.character, sender=sender_1002, recipients=[cls.mailing_list_5]
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
        self.assertEqual(response.status_code, 200)
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
        self.assertEqual(response.status_code, 200)
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
        self.assertEqual(response.status_code, 200)
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
        self.assertEqual(response.status_code, 200)

    def test_character_mail_data_normal_special_chars(self):
        # given
        mail = create_character_mail(character=self.character, body="{}abc")
        request = self.factory.get(
            reverse("memberaudit:character_mail", args=[self.character.pk, mail.pk])
        )
        request.user = self.user
        # when
        response = character_mail(request, self.character.pk, mail.pk)
        # then
        self.assertEqual(response.status_code, 200)

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


class TestSkillSetsData(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        load_eveuniverse()
        load_entities()
        cls.character = create_memberaudit_character(1001)
        cls.user = cls.character.user
        cls.amarr_carrier_skill_type = EveType.objects.get(id=24311)
        cls.caldari_carrier_skill_type = EveType.objects.get(id=24312)
        cls.gallente_carrier_skill_type = EveType.objects.get(id=24313)
        cls.minmatar_carrier_skill_type = EveType.objects.get(id=24314)

    def test_skill_sets_data(self):
        self.user = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_skill_sets", self.user
        )
        create_character_skill(
            character=self.character,
            eve_type=self.amarr_carrier_skill_type,
            active_skill_level=4,
            skillpoints_in_skill=10,
            trained_skill_level=4,
        )
        create_character_skill(
            character=self.character,
            eve_type=self.caldari_carrier_skill_type,
            active_skill_level=2,
            skillpoints_in_skill=10,
            trained_skill_level=5,
        )

        doctrine_1 = create_skill_set_group(name="Alpha")
        doctrine_2 = create_skill_set_group(name="Bravo", is_doctrine=True)

        # can fly ship 1
        ship_1 = create_skill_set(name="Ship 1")
        create_skill_set_skill(
            skill_set=ship_1,
            eve_type=self.amarr_carrier_skill_type,
            required_level=3,
            recommended_level=5,
        )
        doctrine_1.skill_sets.add(ship_1)
        doctrine_2.skill_sets.add(ship_1)

        # can not fly ship 2
        ship_2 = create_skill_set(name="Ship 2")
        create_skill_set_skill(
            skill_set=ship_2, eve_type=self.amarr_carrier_skill_type, required_level=3
        )
        create_skill_set_skill(
            skill_set=ship_2, eve_type=self.caldari_carrier_skill_type, required_level=3
        )
        doctrine_1.skill_sets.add(ship_2)

        # can fly ship 3 (No SkillSetGroup)
        ship_3 = create_skill_set(name="Ship 3")
        create_skill_set_skill(
            skill_set=ship_3, eve_type=self.amarr_carrier_skill_type, required_level=1
        )

        self.character.update_skill_sets()

        request = self.factory.get(
            reverse("memberaudit:character_skill_sets_data", args=[self.character.pk])
        )
        request.user = self.user
        response = character_skill_sets_data(request, self.character.pk)
        self.assertEqual(response.status_code, 200)
        data = json_response_to_python_2(response)
        self.assertEqual(len(data), 4)

        row = data[0]
        self.assertEqual(row["group"], "[Ungrouped]")
        self.assertEqual(row["skill_set_name"], "Ship 3")
        self.assertTrue(row["has_required"])
        self.assertEqual(row["failed_required_skills"], "-")
        url = reverse(
            "memberaudit:character_skill_set_details",
            args=[self.character.pk, ship_3.id],
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
            args=[self.character.pk, ship_1.id],
        )
        self.assertIn(url, row["action"])

        row = data[2]
        self.assertEqual(row["group"], "Alpha")
        self.assertEqual(row["skill_set_name"], "Ship 2")
        self.assertFalse(row["has_required"])
        self.assertIn("Caldari Carrier&nbsp;III", row["failed_required_skills"])
        url = reverse(
            "memberaudit:character_skill_set_details",
            args=[self.character.pk, ship_2.id],
        )
        self.assertIn(url, row["action"])

        row = data[3]
        self.assertEqual(row["group"], "Doctrine: Bravo")
        self.assertEqual(row["skill_set_name"], "Ship 1")
        self.assertTrue(row["has_required"])
        self.assertEqual(row["failed_required_skills"], "-")
        url = reverse(
            "memberaudit:character_skill_set_details",
            args=[self.character.pk, ship_1.id],
        )
        self.assertIn(url, row["action"])

    def test_need_permission_to_see_data(self):
        # given
        request = self.factory.get(
            reverse("memberaudit:character_skill_sets_data", args=[self.character.pk])
        )
        request.user = self.user
        # when
        response = character_skill_sets_data(request, self.character.pk)
        # then
        self.assertEqual(response.status_code, 302)


class TestSkillSetsDetails(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        load_eveuniverse()
        load_entities()
        cls.character = create_memberaudit_character(1001)
        cls.user = cls.character.eve_character.character_ownership.user

    def test_should_show_details(self):
        # given
        amarr_carrier = EveType.objects.get(name="Amarr Carrier")
        caldari_carrier = EveType.objects.get(name="Caldari Carrier")
        gallente_carrier = EveType.objects.get(name="Gallente Carrier")
        minmatar_carrier = EveType.objects.get(name="Minmatar Carrier")
        create_character_skill(
            character=self.character,
            eve_type=amarr_carrier,
            active_skill_level=4,
            skillpoints_in_skill=10,
            trained_skill_level=4,
        )
        create_character_skill(
            character=self.character,
            eve_type=caldari_carrier,
            active_skill_level=2,
            skillpoints_in_skill=10,
            trained_skill_level=2,
        )
        create_character_skill(
            character=self.character,
            eve_type=gallente_carrier,
            active_skill_level=4,
            skillpoints_in_skill=10,
            trained_skill_level=4,
        )
        skill_set = create_skill_set()
        create_skill_set_skill(
            skill_set=skill_set,
            eve_type=amarr_carrier,
            required_level=3,
            recommended_level=5,
        )
        create_skill_set_skill(
            skill_set=skill_set,
            eve_type=caldari_carrier,
            required_level=None,
            recommended_level=3,
        )
        create_skill_set_skill(
            skill_set=skill_set,
            eve_type=gallente_carrier,
            required_level=3,
            recommended_level=None,
        )
        create_skill_set_skill(
            skill_set=skill_set,
            eve_type=minmatar_carrier,
            required_level=None,
            recommended_level=None,
        )
        self.user = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_skill_sets", self.user
        )
        request = self.factory.get(
            reverse(
                "memberaudit:character_skill_set_details",
                args=[self.character.pk, skill_set.pk],
            )
        )
        request.user = self.user
        # when
        response = character_skill_set_details(request, self.character.pk, skill_set.pk)
        # then
        self.assertEqual(response.status_code, 200)
        text = response_text(response)
        self.assertIn(skill_set.name, text)
        self.assertIn(amarr_carrier.name, text)
        self.assertIn(caldari_carrier.name, text)
        self.assertIn(gallente_carrier.name, text)
        self.assertIn(minmatar_carrier.name, text)
        soup = BeautifulSoup(text, features="html.parser")
        missing_skills_str = soup.find(id="div-missing-skills").get_text()
        self.assertIn("Amarr Carrier V", missing_skills_str)
        self.assertIn("Caldari Carrier III", missing_skills_str)
        self.assertIn("Minmatar Carrier I", missing_skills_str)
        self.assertNotIn("Gallente Carrier", missing_skills_str)

    def test_need_permission_to_see_data(self):
        # given
        skill_set = create_skill_set()
        request = self.factory.get(
            reverse(
                "memberaudit:character_skill_set_details",
                args=[self.character.pk, skill_set.pk],
            )
        )

        request.user = self.user
        # when
        response = character_skill_sets_data(request, self.character.pk)
        # then
        self.assertEqual(response.status_code, 302)


class TestSkillAndSkillqueue(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        load_eveuniverse()
        cls.amarr_carrier_skill_type = EveType.objects.get(id=24311)
        cls.caldari_carrier_skill_type = EveType.objects.get(id=24312)
        cls.gallente_carrier_skill_type = EveType.objects.get(id=24313)
        cls.minmatar_carrier_skill_type = EveType.objects.get(id=24314)
        load_entities()
        cls.character = create_memberaudit_character(1001)
        cls.user = cls.character.eve_character.character_ownership.user

    def test_character_skills_data(self):
        create_character_skill(
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
        response = character_skills_data(request, self.character.pk)
        self.assertEqual(response.status_code, 200)
        data = json_response_to_python_2(response)
        self.assertEqual(len(data), 1)
        row = data[0]
        self.assertEqual(row["group"], "Spaceship Command")
        self.assertEqual(row["skill"], "Amarr Carrier")
        self.assertEqual(row["level"], 1)

    def test_character_skillqueue_data_1(self):
        """Char has skills in training"""
        finish_date_1 = now() + dt.timedelta(days=3)
        create_character_skillqueue_entry(
            character=self.character,
            eve_type=self.amarr_carrier_skill_type,
            finish_date=finish_date_1,
            finished_level=5,
            queue_position=0,
            start_date=now() - dt.timedelta(days=1),
        )
        finish_date_2 = now() + dt.timedelta(days=10)
        create_character_skillqueue_entry(
            character=self.character,
            eve_type=self.caldari_carrier_skill_type,
            finish_date=finish_date_2,
            finished_level=5,
            queue_position=1,
            start_date=now() - dt.timedelta(days=1),
        )
        request = self.factory.get(
            reverse("memberaudit:character_skillqueue_data", args=[self.character.pk])
        )
        request.user = self.user
        response = character_skillqueue_data(request, self.character.pk)
        self.assertEqual(response.status_code, 200)
        data = json_response_to_python_2(response)
        self.assertEqual(len(data), 2)

        row = data[0]
        self.assertEqual(row["skill"], "Amarr Carrier&nbsp;V [ACTIVE]")
        self.assertEqual(row["finished"]["sort"], finish_date_1.isoformat())
        self.assertTrue(row["is_active"])

        row = data[1]
        self.assertEqual(row["skill"], "Caldari Carrier&nbsp;V")
        self.assertEqual(row["finished"]["sort"], finish_date_2.isoformat())
        self.assertFalse(row["is_active"])

    def test_character_skillqueue_data_2(self):
        """Char has no skills in training"""
        create_character_skillqueue_entry(
            character=self.character,
            eve_type=self.amarr_carrier_skill_type,
            finished_level=5,
            queue_position=0,
        )
        request = self.factory.get(
            reverse("memberaudit:character_skillqueue_data", args=[self.character.pk])
        )
        request.user = self.user
        response = character_skillqueue_data(request, self.character.pk)
        self.assertEqual(response.status_code, 200)
        data = json_response_to_python_2(response)
        self.assertEqual(len(data), 1)
        row = data[0]
        self.assertEqual(row["skill"], "Amarr Carrier&nbsp;V")
        self.assertIsNone(row["finished"]["sort"])
        self.assertFalse(row["is_active"])


class TestStandings(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        load_entities()
        cls.character = create_memberaudit_character(1001)
        cls.user = cls.character.eve_character.character_ownership.user

    def test_should_produce_character_standings_data(self):
        # given
        npc_corp = EveEntity.objects.get(id=2901)
        create_character_standing(
            character=self.character, eve_entity=npc_corp, standing=5.0
        )
        request = self.factory.get(
            reverse("memberaudit:character_standings_data", args=[self.character.pk])
        )
        request.user = self.user
        # when
        response = character_standings_data(request, self.character.pk)
        # then
        self.assertEqual(response.status_code, 200)
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
        load_eveuniverse()
        load_entities()
        cls.character = create_memberaudit_character(1001)
        cls.user = cls.character.eve_character.character_ownership.user

    def test_should_return_correct_character_titles(self):
        # given
        create_character_title(character=self.character, name="Bravo", title_id=2)
        create_character_title(character=self.character, name="Alpha", title_id=1)
        request = self.factory.get(
            reverse("memberaudit:character_roles_data", args=[self.character.pk])
        )
        request.user = self.user
        # when
        response = character_titles_data(request, self.character.pk)
        # then
        self.assertEqual(response.status_code, 200)
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
        self.assertEqual(response.status_code, 200)
        data = json_response_to_python_2(response)
        self.assertEqual(data, [])


class TestWallet(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        load_eveuniverse()
        load_entities()
        load_locations()
        cls.character = create_memberaudit_character(1001)
        cls.user = cls.character.eve_character.character_ownership.user

    def test_character_wallet_journal_data(self):
        # given
        create_character_wallet_journal_entry(
            character=self.character,
            entry_id=1,
            amount=1000000,
            balance=10000000,
            context_id_type=CharacterWalletJournalEntry.CONTEXT_ID_TYPE_UNDEFINED,
            date=now(),
            description="dummy",
            first_party=EveEntity.objects.get(id=1001),
            second_party=EveEntity.objects.get(id=1002),
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
        self.assertEqual(response.status_code, 200)
        data = json_response_to_python_2(response)
        self.assertEqual(len(data), 1)
        row = data[0]
        self.assertEqual(row["amount"], 1000000.00)
        self.assertEqual(row["balance"], 10000000.00)

    def test_character_wallet_transaction_data(self):
        my_date = now()
        create_character_wallet_transaction(
            character=self.character,
            client=EveEntity.objects.get(id=1002),
            date=my_date,
            location=Location.objects.get(id=60003760),
            quantity=3,
            eve_type=EveType.objects.get(id=603),
            unit_price=450000.99,
        )
        request = self.factory.get(
            reverse(
                "memberaudit:character_wallet_transactions_data",
                args=[self.character.pk],
            )
        )
        request.user = self.user
        response = character_wallet_transactions_data(request, self.character.pk)
        self.assertEqual(response.status_code, 200)
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
