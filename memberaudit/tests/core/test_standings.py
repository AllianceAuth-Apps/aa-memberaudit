from typing import NamedTuple
from unittest import TestCase

from memberaudit.core.standings import Standing

from ..testdata.load_entities import load_entities


class TestCharacterContactStandingLevel(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        load_entities()

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
