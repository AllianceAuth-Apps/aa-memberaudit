from eveuniverse.models import EveType

from app_utils.testing import NoSocketsTestCase

from memberaudit.core.skills import (
    Skill,
    compress_skills,
    required_skills_from_eve_types,
)
from memberaudit.tests.testdata.load_eveuniverse import load_eveuniverse


def create_skill(**kwargs):
    params = {"eve_type": EveType.objects.get(name="Drones"), "level": 1}
    params.update(kwargs)
    return Skill(**params)


class TestSkill(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()

    def test_can_create_skill_simple(self):
        # when
        drones = EveType.objects.get(name="Drones")
        skill = Skill(eve_type=drones, level=1)
        # then
        self.assertEqual(skill.eve_type, drones)
        self.assertEqual(skill.level, 1)

    def test_can_create_required_skills_from_eve_types(self):
        # when
        archon = EveType.objects.get(name="Tengu")
        skills = required_skills_from_eve_types([archon])
        # then
        skills_str = {str(skill) for skill in skills}
        self.assertSetEqual(
            skills_str,
            {
                "Caldari Core Systems I",
                "Caldari Defensive Systems I",
                "Caldari Offensive Systems I",
                "Caldari Propulsion Systems I",
                "Caldari Strategic Cruiser I",
            },
        )

    def test_str_1(self):
        # given
        drones = EveType.objects.get(name="Drones")
        skill = Skill(eve_type=drones, level=1)
        # when/then
        self.assertEqual(str(skill), "Drones I")

    def test_str_2(self):
        # given
        light_drone_operations = EveType.objects.get(name="Light Drone Operation")
        # when
        skill = Skill(eve_type=light_drone_operations, level=5)
        # then
        self.assertEqual(str(skill), "Light Drone Operation V")

    def test_compress_skills(self):
        # given
        drones = EveType.objects.get(name="Drones")
        gunnery = EveType.objects.get(name="Gunnery")
        skill_1 = create_skill(eve_type=drones, level=1)
        skill_2 = create_skill(eve_type=gunnery, level=1)
        skill_3 = create_skill(eve_type=drones, level=3)
        skills = [skill_1, skill_2, skill_3]
        # when
        results = compress_skills(skills)
        # then
        self.assertEqual(len(results), 2)
        self.assertIn(skill_2, results)
        self.assertIn(skill_3, results)

    def test_can_compare_skills_lesser(self):
        # given
        drones = EveType.objects.get(name="Drones")
        params = [(1, 1, 2, True), (2, 1, 1, False), (3, 2, 1, False)]
        for num, level_1, level_2, expected_result in params:
            with self.subTest(num=num):
                skill_1 = create_skill(eve_type=drones, level=level_1)
                skill_2 = create_skill(eve_type=drones, level=level_2)
                # when/then
                self.assertIs(skill_1 < skill_2, expected_result)

    def test_should_raise_error_for_lesser(self):
        # given
        drones = EveType.objects.get(name="Drones")
        gunnery = EveType.objects.get(name="Gunnery")
        skill_1 = create_skill(eve_type=drones, level=1)
        skill_2 = create_skill(eve_type=gunnery, level=2)
        # when/then
        with self.assertRaises(ValueError):
            self.assertLess(skill_1, skill_2)

    def test_can_compare_skills_lesser_or_equal(self):
        # given
        drones = EveType.objects.get(name="Drones")
        params = [(1, 1, 2, True), (2, 1, 1, True), (3, 2, 1, False)]
        for num, level_1, level_2, expected_result in params:
            with self.subTest(num=num):
                skill_1 = create_skill(eve_type=drones, level=level_1)
                skill_2 = create_skill(eve_type=drones, level=level_2)
                # when/then
                self.assertIs(skill_1 <= skill_2, expected_result)

    def test_should_raise_error_for_lesser_or_equal(self):
        # given
        drones = EveType.objects.get(name="Drones")
        gunnery = EveType.objects.get(name="Gunnery")
        skill_1 = create_skill(eve_type=drones, level=1)
        skill_2 = create_skill(eve_type=gunnery, level=1)
        # when/then
        with self.assertRaises(ValueError):
            self.assertLessEqual(skill_1, skill_2)

    def test_can_compare_skills_greater(self):
        # given
        drones = EveType.objects.get(name="Drones")
        params = [(1, 1, 2, False), (2, 1, 1, False), (3, 2, 1, True)]
        for num, level_1, level_2, expected_result in params:
            with self.subTest(num=num):
                skill_1 = create_skill(eve_type=drones, level=level_1)
                skill_2 = create_skill(eve_type=drones, level=level_2)
                # when/then
                self.assertIs(skill_1 > skill_2, expected_result)

    def test_should_raise_error_for_greater(self):
        # given
        drones = EveType.objects.get(name="Drones")
        gunnery = EveType.objects.get(name="Gunnery")
        skill_1 = create_skill(eve_type=drones, level=1)
        skill_2 = create_skill(eve_type=gunnery, level=2)
        # when/then
        with self.assertRaises(ValueError):
            self.assertGreater(skill_1, skill_2)

    def test_can_compare_skills_greater_or_equal(self):
        # given
        drones = EveType.objects.get(name="Drones")
        params = [(1, 1, 2, False), (2, 1, 1, True), (3, 2, 1, True)]
        for num, level_1, level_2, expected_result in params:
            with self.subTest(num=num):
                skill_1 = create_skill(eve_type=drones, level=level_1)
                skill_2 = create_skill(eve_type=drones, level=level_2)
                # when/then
                self.assertIs(skill_1 >= skill_2, expected_result)

    def test_should_raise_error_for_greater_or_equal(self):
        # given
        drones = EveType.objects.get(name="Drones")
        gunnery = EveType.objects.get(name="Gunnery")
        skill_1 = create_skill(eve_type=drones, level=1)
        skill_2 = create_skill(eve_type=gunnery, level=2)
        # when/then
        with self.assertRaises(ValueError):
            self.assertGreaterEqual(skill_1, skill_2)
