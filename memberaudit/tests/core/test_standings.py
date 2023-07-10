from typing import NamedTuple
from unittest import TestCase

from memberaudit.core.standings import Standing, calc_effective_standing


class TestCharacterContactStandingLevel(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

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
        unadjusted_standing = 0.9
        skill_level = 2
        skill_modifier = 0.04
        max_possible_standing = 10
        # when
        result = calc_effective_standing(
            unadjusted_standing, skill_level, skill_modifier, max_possible_standing
        )
        # then
        # 0.9 +(10-0.9)*0.04*2=
        self.assertAlmostEqual(result, 1.628, 3)
