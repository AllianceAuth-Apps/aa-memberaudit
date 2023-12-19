import datetime as dt

from django.test import TestCase
from django.utils.timezone import now
from eveuniverse.models import EveEntity, EveSolarSystem, EveType

from app_utils.testing import NoSocketsTestCase

from memberaudit.constants import EveFactionId
from memberaudit.models import (
    CharacterContract,
    CharacterFwStats,
    CharacterWalletJournalEntry,
    Location,
)
from memberaudit.tests.testdata.factories import (
    create_character_clone_info,
    create_character_contract,
    create_character_contract_item,
    create_character_fw_stats,
    create_character_ship,
    create_character_standing,
    create_character_title,
    create_character_wallet_journal_entry,
    create_eve_market_price,
)
from memberaudit.tests.testdata.load_entities import load_entities
from memberaudit.tests.testdata.load_eveuniverse import load_eveuniverse
from memberaudit.tests.testdata.load_locations import load_locations
from memberaudit.tests.utils import create_memberaudit_character


class TestCharacterCloneInfo(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        load_locations()
        cls.character_1001 = create_memberaudit_character(1001)

    def test_str(self):
        # given
        obj = create_character_clone_info(self.character_1001)

        # when/then
        self.assertTrue(repr(obj))


class TestCharacterContract(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        load_locations()
        cls.character_1001 = create_memberaudit_character(1001)
        cls.character_1002 = create_memberaudit_character(1002)
        cls.token = (
            cls.character_1001.eve_character.character_ownership.user.token_set.first()
        )
        cls.jita = EveSolarSystem.objects.get(id=30000142)
        cls.jita_44 = Location.objects.get(id=60003760)
        cls.amamake = EveSolarSystem.objects.get(id=30002537)
        cls.structure_1 = Location.objects.get(id=1000000000001)
        cls.snake_alpha_type = EveType.objects.get(name="High-grade Snake Alpha")
        cls.snake_beta_type = EveType.objects.get(name="High-grade Snake Beta")

    def setUp(self) -> None:
        self.contract = create_character_contract(
            character=self.character_1001,
            contract_id=42,
            availability=CharacterContract.AVAILABILITY_PERSONAL,
            contract_type=CharacterContract.TYPE_ITEM_EXCHANGE,
            date_issued=now(),
            date_expired=now() + dt.timedelta(days=3),
            for_corporation=False,
            issuer=EveEntity.objects.get(id=1001),
            issuer_corporation=EveEntity.objects.get(id=2001),
            status=CharacterContract.STATUS_OUTSTANDING,
            start_location=self.jita_44,
            end_location=self.jita_44,
        )
        self.contract_completed = create_character_contract(
            character=self.character_1001,
            contract_id=43,
            availability=CharacterContract.AVAILABILITY_PERSONAL,
            contract_type=CharacterContract.TYPE_ITEM_EXCHANGE,
            date_issued=now() - dt.timedelta(days=3),
            date_completed=now() - dt.timedelta(days=2),
            date_expired=now() - dt.timedelta(days=1),
            for_corporation=False,
            issuer=EveEntity.objects.get(id=1001),
            issuer_corporation=EveEntity.objects.get(id=2001),
            status=CharacterContract.STATUS_FINISHED,
            start_location=self.jita_44,
            end_location=self.jita_44,
        )

    def test_str(self):
        self.assertEqual(str(self.contract), f"{self.character_1001}-42")

    def test_is_completed(self):
        self.assertFalse(self.contract.is_completed)
        self.assertTrue(self.contract_completed.is_completed)

    def test_has_expired(self):
        self.assertFalse(self.contract.has_expired)
        self.assertTrue(self.contract_completed.has_expired)

    def test_hours_issued_2_completed(self):
        self.assertIsNone(self.contract.hours_issued_2_completed)
        self.assertEqual(self.contract_completed.hours_issued_2_completed, 24)

    def test_summary_one_item_1(self):
        create_character_contract_item(
            contract=self.contract,
            record_id=1,
            is_included=True,
            is_singleton=False,
            quantity=1,
            eve_type=self.snake_alpha_type,
        )
        self.assertEqual(self.contract.summary(), "High-grade Snake Alpha")

    def test_summary_one_item_2(self):
        create_character_contract_item(
            contract=self.contract,
            record_id=1,
            is_included=True,
            is_singleton=False,
            quantity=1,
            eve_type=self.snake_alpha_type,
        )
        create_character_contract_item(
            contract=self.contract,
            record_id=2,
            is_included=False,
            is_singleton=False,
            quantity=1,
            eve_type=self.snake_beta_type,
        )
        self.assertEqual(self.contract.summary(), "High-grade Snake Alpha")

    def test_summary_multiple_item(self):
        create_character_contract_item(
            contract=self.contract,
            record_id=1,
            is_included=True,
            is_singleton=False,
            quantity=1,
            eve_type=self.snake_alpha_type,
        ),
        create_character_contract_item(
            contract=self.contract,
            record_id=2,
            is_included=True,
            is_singleton=False,
            quantity=1,
            eve_type=self.snake_beta_type,
        )
        self.assertEqual(self.contract.summary(), "[Multiple Items]")

    def test_summary_no_items(self):
        self.assertEqual(self.contract.summary(), "(no items)")

    def test_can_calculate_pricing_1(self):
        """calculate price and total for normal item"""
        create_character_contract_item(
            contract=self.contract,
            record_id=1,
            is_included=True,
            is_singleton=False,
            quantity=2,
            eve_type=self.snake_alpha_type,
        ),
        create_eve_market_price(eve_type=self.snake_alpha_type, average_price=5000000)
        qs = self.contract.items.annotate_pricing()
        item_1 = qs.get(record_id=1)
        self.assertEqual(item_1.price, 5000000)
        self.assertEqual(item_1.total, 10000000)

    def test_can_calculate_pricing_2(self):
        """calculate price and total for BPO"""
        create_character_contract_item(
            contract=self.contract,
            record_id=1,
            is_included=True,
            is_singleton=False,
            quantity=1,
            raw_quantity=-2,
            eve_type=self.snake_alpha_type,
        ),
        create_eve_market_price(eve_type=self.snake_alpha_type, average_price=5000000)
        qs = self.contract.items.annotate_pricing()
        item_1 = qs.get(record_id=1)
        self.assertIsNone(item_1.price)
        self.assertIsNone(item_1.total)


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
    def setUpClass(cls):
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


class TestCharacterShip(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        cls.character_1001 = create_memberaudit_character(1001)
        cls.user = cls.character_1001.eve_character.character_ownership.user

    def test_str(self):
        # given
        create_character_ship(
            character=self.character_1001, eve_type=EveType.objects.get(id=603)
        )
        # when
        result = str(self.character_1001.ship)
        # then
        self.assertIn("Bruce Wayne", result)
        self.assertIn("Merlin", result)


class TestCharacterStanding(TestCase):
    @classmethod
    def setUpClass(cls):
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
    def setUpClass(cls):
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
    def setUpClass(cls):
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


class TestCharacterWalletJournalEntry(NoSocketsTestCase):
    def test_match_context_type_id(self):
        self.assertEqual(
            CharacterWalletJournalEntry.match_context_type_id("character_id"),
            CharacterWalletJournalEntry.CONTEXT_ID_TYPE_CHARACTER_ID,
        )
        self.assertEqual(
            CharacterWalletJournalEntry.match_context_type_id("contract_id"),
            CharacterWalletJournalEntry.CONTEXT_ID_TYPE_CONTRACT_ID,
        )
        self.assertEqual(
            CharacterWalletJournalEntry.match_context_type_id(None),
            CharacterWalletJournalEntry.CONTEXT_ID_TYPE_UNDEFINED,
        )
