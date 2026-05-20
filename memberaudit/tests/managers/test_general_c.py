from eveuniverse.models import EveType

from app_utils.testing import NoSocketsTestCase

from memberaudit.models import SkillSet
from memberaudit.tests.testdata.factories import (
    create_fitting,
    create_skill,
    create_skill_plan,
)
from memberaudit.tests.testdata.factories_2 import SkillSetGroupFactory
from memberaudit.tests.testdata.load_eveuniverse import load_eveuniverse


class TestSkillSetManager(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        cls.fitting = create_fitting(name="My fitting")

    def test_should_create_new_skill_set_from_fitting(self):
        # when
        skill_set: SkillSet
        skill_set, created = SkillSet.objects.update_or_create_from_fitting(
            fitting=self.fitting
        )

        # then
        self.assertTrue(created)
        self.assertEqual(skill_set.name, "My fitting")
        self.assertEqual(skill_set.ship_type.name, "Tristan")
        skills_str = {skill.required_skill_str for skill in skill_set.skills.all()}
        self.assertSetEqual(
            skills_str,
            {
                "Small Autocannon Specialization I",
                "Gunnery II",
                "Weapon Upgrades IV",
                "Light Drone Operation V",
                "Small Projectile Turret V",
                "Gallente Frigate I",
                "Propulsion Jamming II",
                "Drones V",
                "Amarr Drone Specialization I",
            },
        )

    def test_should_create_new_skill_set_from_fitting_and_assign_to_group(self):
        # given
        skill_set_group = SkillSetGroupFactory()

        # when
        skill_set, created = SkillSet.objects.update_or_create_from_fitting(
            fitting=self.fitting, skill_set_group=skill_set_group
        )
        # then
        self.assertTrue(created)
        self.assertIn(skill_set, skill_set_group.skill_sets.all())

    def test_should_create_new_skill_set_from_skill_plan(self):
        # given
        skills = [
            create_skill(
                eve_type=EveType.objects.get(name="Small Autocannon Specialization"),
                level=1,
            ),
            create_skill(
                eve_type=EveType.objects.get(name="Light Drone Operation"),
                level=5,
            ),
        ]
        skill_plan = create_skill_plan(name="My skill plan", skills=skills)

        # when
        skill_set: SkillSet
        skill_set, created = SkillSet.objects.update_or_create_from_skill_plan(
            skill_plan=skill_plan
        )

        # then
        self.assertTrue(created)
        self.assertEqual(skill_set.name, "My skill plan")
        skills_str = {skill.required_skill_str for skill in skill_set.skills.all()}
        self.assertSetEqual(
            skills_str,
            {"Small Autocannon Specialization I", "Light Drone Operation V"},
        )

    def test_should_create_new_skill_set_from_skill_plan_and_assign_to_group(self):
        # given
        skills = [
            create_skill(
                eve_type=EveType.objects.get(name="Small Autocannon Specialization"),
                level=1,
            ),
            create_skill(
                eve_type=EveType.objects.get(name="Light Drone Operation"),
                level=5,
            ),
        ]
        skill_plan = create_skill_plan(name="My skill plan", skills=skills)
        skill_set_group = SkillSetGroupFactory()

        # when
        skill_set, created = SkillSet.objects.update_or_create_from_skill_plan(
            skill_plan=skill_plan, skill_set_group=skill_set_group
        )

        # then
        self.assertTrue(created)
        self.assertIn(skill_set, skill_set_group.skill_sets.all())
