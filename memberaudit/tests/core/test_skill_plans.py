from eveuniverse.models import EveType

from app_utils.testing import NoSocketsTestCase

from memberaudit.core.skill_plans import NoSkillsIdentified, SkillPlan
from memberaudit.core.skills import Skill
from memberaudit.tests.testdata.load_eveuniverse import load_eveuniverse


class TestSkillPlan(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()

    def test_should_create_skill_plan_in_eve_client_style(self):
        # given
        text = """
        Caldari Core Systems 5
        Caldari Strategic Cruiser 3
        """
        # when
        result, issues = SkillPlan.create_from_plain_text("dummy", text)
        # then
        self.assertFalse(issues)
        expected = SkillPlan(
            "dummy",
            [
                Skill(EveType.objects.get(name="Caldari Core Systems"), 5),
                Skill(EveType.objects.get(name="Caldari Strategic Cruiser"), 3),
            ],
        )
        self.assertEqual(result, expected)

    def test_should_create_skill_plan_in_eve_mon_style(self):
        # given
        text = """
        Caldari Core Systems V
        Caldari Strategic Cruiser III
        """
        # when
        result, issues = SkillPlan.create_from_plain_text("dummy", text)
        # then
        self.assertFalse(issues)
        expected = SkillPlan(
            "dummy",
            [
                Skill(EveType.objects.get(name="Caldari Core Systems"), 5),
                Skill(EveType.objects.get(name="Caldari Strategic Cruiser"), 3),
            ],
        )
        self.assertEqual(result, expected)

    def test_should_report_issues_with_missing_skill_level_and_still_use_rest(self):
        # given
        text = """
        Caldari Core Systems
        Caldari Strategic Cruiser 3
        """
        # when
        result, issues = SkillPlan.create_from_plain_text("dummy", text)
        # then
        self.assertIn("Caldari Core Systems", issues[0])
        expected = SkillPlan(
            "dummy",
            [
                Skill(EveType.objects.get(name="Caldari Strategic Cruiser"), 3),
            ],
        )
        self.assertEqual(result, expected)

    def test_should_report_issues_with_invalid_skill_level(self):
        # given
        text = """
        Caldari Core Systems 99
        Caldari Strategic Cruiser 3
        """
        # when
        result, issues = SkillPlan.create_from_plain_text("dummy", text)
        # then
        self.assertIn("Caldari Core Systems", issues[0])
        expected = SkillPlan(
            "dummy",
            [
                Skill(EveType.objects.get(name="Caldari Strategic Cruiser"), 3),
            ],
        )
        self.assertEqual(result, expected)

    def test_should_report_issues_with_unknown_skill_name(self):
        # given
        text = """
        Mind Reading 3
        Caldari Strategic Cruiser 3
        """
        # when
        result, issues = SkillPlan.create_from_plain_text("dummy", text)
        # then
        self.assertIn("Mind Reading", issues[0])
        expected = SkillPlan(
            "dummy",
            [
                Skill(EveType.objects.get(name="Caldari Strategic Cruiser"), 3),
            ],
        )
        self.assertEqual(result, expected)

    def test_should_raise_exception_when_no_skills_identified(self):
        # given
        text = """
        Mind Reading 3
        """
        # when
        with self.assertRaises(NoSkillsIdentified):
            SkillPlan.create_from_plain_text("dummy", text)

    def test_should_create_skill_plan_with_double_skills(self):
        """Test related to a bug, where creating the skill plan failed,
        because the skill type 'Amarr Cruiser' exists twice.
        """
        # given
        text = """Amarr Cruiser III"""
        # when
        result, issues = SkillPlan.create_from_plain_text("dummy", text)
        # then
        self.assertFalse(issues)
        skill = result.skills[0]
        self.assertEqual(skill.eve_type.name, "Amarr Cruiser")
        self.assertEqual(skill.level, 3)
