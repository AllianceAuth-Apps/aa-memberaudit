from eveuniverse.tests.testdata.factories_2 import EveTypeFactory

from app_utils.testing import NoSocketsTestCase

from memberaudit.core.skill_plans import NoSkillsIdentified, SkillPlan
from memberaudit.core.skills import Skill

text_1 = """
Caldari Core Systems 5
Caldari Strategic Cruiser 3
"""

text_2 = """
Caldari Core Systems V
Caldari Strategic Cruiser III
"""

text_3 = """
Caldari Core Systems
Caldari Strategic Cruiser 3
"""

text_4 = """
Caldari Core Systems 99
Caldari Strategic Cruiser 3
"""

text_5 = """
Mind Reading 3
Caldari Strategic Cruiser 3
"""

text_6 = """
Mind Reading 3
"""

text_7 = """Amarr Cruiser III"""


class TestSkillPlan(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.caldari_core_systems = EveTypeFactory(name="Caldari Core Systems")
        cls.caldari_strategic_cruiser = EveTypeFactory(name="Caldari Strategic Cruiser")

    def test_should_create_skill_plan_in_eve_client_style(self):
        # when
        result, issues = SkillPlan.create_from_plain_text("dummy", text_1)

        # then
        self.assertFalse(issues)
        expected = SkillPlan(
            "dummy",
            [
                Skill(self.caldari_core_systems, 5),
                Skill(self.caldari_strategic_cruiser, 3),
            ],
        )
        self.assertEqual(result, expected)

    def test_should_create_skill_plan_in_eve_mon_style(self):
        # when
        result, issues = SkillPlan.create_from_plain_text("dummy", text_2)

        # then
        self.assertFalse(issues)
        expected = SkillPlan(
            "dummy",
            [
                Skill(self.caldari_core_systems, 5),
                Skill(self.caldari_strategic_cruiser, 3),
            ],
        )
        self.assertEqual(result, expected)

    def test_should_report_issues_with_missing_skill_level_and_still_use_rest(self):
        # when
        result, issues = SkillPlan.create_from_plain_text("dummy", text_3)

        # then
        self.assertIn("Caldari Core Systems", issues[0])
        expected = SkillPlan(
            "dummy",
            [
                Skill(self.caldari_strategic_cruiser, 3),
            ],
        )
        self.assertEqual(result, expected)

    def test_should_report_issues_with_invalid_skill_level(self):
        # when
        result, issues = SkillPlan.create_from_plain_text("dummy", text_4)

        # then
        self.assertIn("Caldari Core Systems", issues[0])
        expected = SkillPlan(
            "dummy",
            [
                Skill(self.caldari_strategic_cruiser, 3),
            ],
        )
        self.assertEqual(result, expected)

    def test_should_report_issues_with_unknown_skill_name(self):
        # when
        result, issues = SkillPlan.create_from_plain_text("dummy", text_5)
        # then
        self.assertIn("Mind Reading", issues[0])
        expected = SkillPlan(
            "dummy",
            [
                Skill(self.caldari_strategic_cruiser, 3),
            ],
        )
        self.assertEqual(result, expected)

    def test_should_raise_exception_when_no_skills_identified(self):
        # when
        with self.assertRaises(NoSkillsIdentified):
            SkillPlan.create_from_plain_text("dummy", text_6)

    def test_should_create_skill_plan_with_double_skills(self):
        """Test related to a bug, where creating the skill plan failed,
        because the skill type 'Amarr Cruiser' exists twice.
        """
        # given
        EveTypeFactory(name="Amarr Cruiser", published=True)
        EveTypeFactory(name="Amarr Cruiser", published=False)
        # when
        result, issues = SkillPlan.create_from_plain_text("dummy", text_7)
        # then
        self.assertFalse(issues)
        skill = result.skills[0]
        self.assertEqual(skill.eve_type.name, "Amarr Cruiser")
        self.assertEqual(skill.level, 3)
