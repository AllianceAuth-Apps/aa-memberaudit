from typing import NamedTuple

from django.test import TestCase
from eveuniverse.models import EveEntity

from memberaudit.constants import EveFactionId
from memberaudit.models import CharacterContact, CharacterFwStats

from ..testdata.factories import create_character_contact, create_fw_stats
from ..utils import create_memberaudit_character, load_entities, load_eveuniverse


class TestCharacterFwStatsRankNameGeneric(TestCase):
    def test_should_return_rank_name_when_found(self):
        # when
        result = CharacterFwStats.rank_name_generic(EveFactionId.CALDARI_STATE, 4)
        # then
        self.assertEqual(result, "Major")

    def test_should_raise_error_for_unknown_faction(self):
        # when/then
        with self.assertRaises(ValueError):
            CharacterFwStats.rank_name_generic(42, 4)

    def test_should_raise_error_for_invalid_rank(self):
        # when/then
        with self.assertRaises(ValueError):
            CharacterFwStats.rank_name_generic(EveFactionId.CALDARI_STATE, 42)


class TestCharacterFwStatsRankNameObject(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        cls.character = create_memberaudit_character(1121)

    def test_should_return_rank_name_when_found(self):
        # given
        obj = create_fw_stats(character=self.character, current_rank=4)
        # when/then
        self.assertEqual(obj.current_rank_name(), "Major")

    def test_should_return_rank_name_when_not_found(self):
        # given
        obj = create_fw_stats(character=self.character, faction=None)
        # when/then
        self.assertEqual(obj.current_rank_name(), "")


class TestCharacterContactStandingLevel(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        load_eveuniverse()
        load_entities()

    class MyTestCase(NamedTuple):
        standing: float
        expected_result: str

    def test_should_determine_correct_standing(self):
        # given
        character = create_memberaudit_character(1001)
        contact_character = EveEntity.objects.get(id=1101)

        test_cases = [
            self.MyTestCase(9.9, CharacterContact.STANDING_EXCELLENT),
            self.MyTestCase(4.9, CharacterContact.STANDING_GOOD),
            self.MyTestCase(0.0, CharacterContact.STANDING_NEUTRAL),
            self.MyTestCase(-4.9, CharacterContact.STANDING_BAD),
            self.MyTestCase(-9.9, CharacterContact.STANDING_TERRIBLE),
        ]
        for test_case in test_cases:
            with self.subTest(standing=test_case.standing):
                contact = create_character_contact(
                    character=character,
                    eve_entity=contact_character,
                    standing=test_case.standing,
                )
                self.assertEqual(contact.standing_level, test_case.expected_result)
                contact.delete()
