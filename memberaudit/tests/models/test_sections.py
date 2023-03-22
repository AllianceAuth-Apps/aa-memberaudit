from django.test import TestCase

from memberaudit.constants import EveFactionId
from memberaudit.models import CharacterFwStats

from ..testdata.factories import create_fw_stats
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
