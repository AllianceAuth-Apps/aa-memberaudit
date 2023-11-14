from typing import NamedTuple
from unittest import TestCase

from memberaudit.core.standings import Standing, calc_effective_standing


class TestCharacterContactStandingLevel(TestCase):
    class MyTestCase(NamedTuple):
        standing: float
        expected_result: str

    def test_should_determine_correct_standing(self):
        # given
        test_cases = [
            self.MyTestCase(9.9, Standing.EXCELLENT),
            self.MyTestCase(4.9, Standing.GOOD),
            self.MyTestCase(0.0, Standing.NEUTRAL),
            self.MyTestCase(-4.9, Standing.BAD),
            self.MyTestCase(-9.9, Standing.TERRIBLE),
        ]
        for test_case in test_cases:
            with self.subTest(standing=test_case.standing):
                # when
                standing = Standing.from_value(test_case.standing)
                # then
                self.assertEqual(standing, test_case.expected_result)


class TestCalcEffectiveStanding(TestCase):
    def test_should_calc_correct_standing(self):
        # given
        class MyTestCase(NamedTuple):
            unadjusted_standing: float
            skill_level: int
            skill_modifier: float
            max_possible_standing: int
            effective_standing: float

        test_cases = [
            MyTestCase(
                unadjusted_standing=0.9,
                skill_level=2,
                skill_modifier=0.04,
                max_possible_standing=10,
                effective_standing=1.628,
            ),
            MyTestCase(
                unadjusted_standing=7.49,
                skill_level=5,
                skill_modifier=0.04,
                max_possible_standing=10,
                effective_standing=7.99,
            ),
            MyTestCase(
                unadjusted_standing=-4.76,
                skill_level=5,
                skill_modifier=0.04,
                max_possible_standing=10,
                effective_standing=-1.81,
            ),
            MyTestCase(
                unadjusted_standing=-2.29,
                skill_level=5,
                skill_modifier=0.04,
                max_possible_standing=10,
                effective_standing=0.17,
            ),
            MyTestCase(
                unadjusted_standing=4.99,
                skill_level=3,
                skill_modifier=0.04,
                max_possible_standing=10,
                effective_standing=5.59,
            ),
        ]
        for num, test_case in enumerate(test_cases):
            with self.subTest(num=num):
                # when
                result = calc_effective_standing(
                    test_case.unadjusted_standing,
                    test_case.skill_level,
                    test_case.skill_modifier,
                    test_case.max_possible_standing,
                )
                # then
                self.assertAlmostEqual(result, test_case.effective_standing, 2)
