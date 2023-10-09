from django.test import TestCase
from eveuniverse.models import EveEntity

from memberaudit.constants import EveFactionId
from memberaudit.models import CharacterFwStats

from ..testdata.factories import (
    create_character_fw_stats,
    create_character_standing,
    create_character_title,
    create_character_wallet_journal_entry,
)
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
        obj = create_character_fw_stats(character=self.character, current_rank=4)
        # when/then
        self.assertEqual(obj.current_rank_name(), "Major")

    def test_should_return_rank_name_when_not_found(self):
        # given
        obj = create_character_fw_stats(character=self.character, faction=None)
        # when/then
        self.assertEqual(obj.current_rank_name(), "")


class TestCharacterStanding(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        cls.character = create_memberaudit_character(1001)

    def test_effective_standing_with_connections(self):
        # given
        eve_entity = EveEntity.objects.get(id=1901)
        obj = create_character_standing(self.character, eve_entity, standing=4.99)
        # when
        result = obj.effective_standing(3, 0, 0)
        # then
        self.assertAlmostEqual(result, 5.59, 2)

    def test_effective_standing_with_diplomacy(self):
        # given
        eve_entity = EveEntity.objects.get(id=1901)
        obj = create_character_standing(self.character, eve_entity, standing=-4.76)
        # when
        result = obj.effective_standing(0, 0, 5)
        # then
        self.assertAlmostEqual(result, -1.81, 2)


class TestCharacterTitle(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        cls.character = create_memberaudit_character(1001)

    def test_should_return_str(self):
        # given
        obj = create_character_title(character=self.character, name="Dummy")
        # when
        result = str(obj)
        # then
        self.assertIn("Dummy", result)


class TestCharacterWalletJournals(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        cls.character = create_memberaudit_character(1001)

    def test_should_return_eve_entity_ids(self):
        # given
        obj = create_character_wallet_journal_entry(
            character=self.character, first_party_id=1001, second_party_id=1002
        )
        # when
        result = obj.eve_entity_ids()
        # then
        expected = {1001, 1002}
        self.assertSetEqual(result, expected)
