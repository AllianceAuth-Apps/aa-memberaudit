import datetime as dt
from typing import NamedTuple, Optional

from django.utils.timezone import now
from eveuniverse.tests.testdata.factories_2 import (
    EveEntityCharacterFactory,
    EveTypeFactory,
)

from app_utils.testing import NoSocketsTestCase

from memberaudit.constants import EveFactionId
from memberaudit.models import CharacterFwStats, CharacterWalletJournalEntry
from memberaudit.tests.testdata.factories_2 import (
    CharacterContractCourierFactory,
    CharacterContractItemExchangeFactory,
    CharacterContractItemFactory,
    CharacterFactory,
    CharacterFwStatsFactory,
    CharacterShipFactory,
    CharacterSkillqueueEntryFactory,
    CharacterStandingFactory,
    CharacterTitleFactory,
    CharacterWalletJournalEntryFactory,
)


class TestCharacterContract_Misc(NoSocketsTestCase):
    def test_is_completed(self):
        contract_1 = CharacterContractCourierFactory()
        self.assertFalse(contract_1.is_completed)
        contract_2 = CharacterContractCourierFactory(finished=True)
        self.assertTrue(contract_2.is_completed)

    def test_has_expired(self):
        contract_1 = CharacterContractCourierFactory()
        self.assertFalse(contract_1.has_expired)
        contract_2 = CharacterContractCourierFactory(
            date_expired=now() - dt.timedelta(seconds=1)
        )
        self.assertTrue(contract_2.has_expired)

    def test_hours_issued_2_completed(self):
        contract_1 = CharacterContractCourierFactory()
        self.assertIsNone(contract_1.hours_issued_2_completed)
        contract_2 = CharacterContractCourierFactory(finished=True)
        self.assertEqual(contract_2.hours_issued_2_completed, 3)


class TestCharacterContract_Summary(NoSocketsTestCase):
    def test_summary_one_item_1(self):
        contract = CharacterContractItemExchangeFactory(items=False)
        eve_type = EveTypeFactory(name="High-grade Snake Alpha")
        CharacterContractItemFactory(
            contract=contract,
            is_included=True,
            is_singleton=False,
            quantity=1,
            eve_type=eve_type,
        )
        self.assertEqual(contract.summary(), "High-grade Snake Alpha")

    def test_summary_one_item_2(self):
        contract = CharacterContractItemExchangeFactory(items=False)
        eve_type_1 = EveTypeFactory(name="High-grade Snake Alpha")
        eve_type_2 = EveTypeFactory()
        CharacterContractItemFactory(
            contract=contract, is_included=True, eve_type=eve_type_1
        )
        CharacterContractItemFactory(
            contract=contract, is_included=False, eve_type=eve_type_2
        )
        self.assertEqual(contract.summary(), "High-grade Snake Alpha")

    def test_summary_multiple_item(self):
        contract = CharacterContractItemExchangeFactory(items=False)
        CharacterContractItemFactory(contract=contract),
        CharacterContractItemFactory(contract=contract)
        self.assertEqual(contract.summary(), "[Multiple Items]")

    def test_summary_no_items(self):
        contract = CharacterContractItemExchangeFactory(items=False)
        self.assertEqual(contract.summary(), "(no items)")


class TestCharacterFwStatsRankNameGeneric(NoSocketsTestCase):
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


class TestCharacterFwStatsRankNameObject(NoSocketsTestCase):
    def test_should_return_rank_name_when_found(self):
        # given
        obj = CharacterFwStatsFactory(current_rank=4)
        # when/then
        self.assertEqual(obj.current_rank_name(), "Major")

    def test_should_return_rank_name_when_not_found(self):
        # given
        obj = CharacterFwStatsFactory(faction=None)
        # when/then
        self.assertEqual(obj.current_rank_name(), "")


class TestCharacterShip(NoSocketsTestCase):
    def test_str(self):
        # given
        character = CharacterFactory()
        ship = CharacterShipFactory(character=character)
        # when
        result = str(character.ship)
        # then
        self.assertIn(character.name, result)
        self.assertIn(ship.eve_type.name, result)


class TestCharacterSkillQueueEntry(NoSocketsTestCase):
    def test_should_return_string(self):
        eve_type = EveTypeFactory(name="Amarr Carrier")
        sqe = CharacterSkillqueueEntryFactory(eve_type=eve_type, finished_level=5)
        self.assertIn("Amarr Carrier V", str(sqe))

    def test_should_return_name(self):
        eve_type = EveTypeFactory(name="Amarr Carrier")
        sqe = CharacterSkillqueueEntryFactory(eve_type=eve_type, finished_level=5)
        self.assertIn("Amarr Carrier V", sqe.skill_display())

    def test_can_calculate_is_active(self):
        class X(NamedTuple):
            want: Optional[dt.timedelta]
            start_date: Optional[dt.datetime] = None
            finish_date: Optional[dt.datetime] = None

        now_ = now()
        cases = [
            X(
                start_date=now_ - dt.timedelta(hours=3),
                finish_date=now_ + dt.timedelta(hours=3),
                want=True,
            ),
            X(
                start_date=now_ - dt.timedelta(hours=3),
                finish_date=now_ - dt.timedelta(hours=1),
                want=False,
            ),
            X(
                start_date=now_ + dt.timedelta(hours=1),
                finish_date=now_ + dt.timedelta(hours=3),
                want=False,
            ),
            X(
                start_date=now_ - dt.timedelta(hours=3),
                want=False,
            ),
            X(
                finish_date=now_ + dt.timedelta(hours=3),
                want=False,
            ),
            X(
                want=False,
            ),
        ]
        for i, tc in enumerate(cases, 1):
            with self.subTest("is active", num=i):
                sqe = CharacterSkillqueueEntryFactory(
                    start_date=tc.start_date, finish_date=tc.finish_date
                )
                got = sqe.is_active()
                self.assertIs(tc.want, got)

    def test_can_calculate_completion(self):
        class Case(NamedTuple):
            want: Optional[float] = None
            start_date: Optional[dt.datetime] = None
            finish_date: Optional[dt.datetime] = None
            level_start_sp: int = 0
            level_end_sp: int = 100
            training_start_sp: int = 0
            exception: Optional[Exception] = None

        now_ = now()
        cases = [
            Case(
                start_date=now_ - dt.timedelta(hours=1),
                finish_date=now_ + dt.timedelta(hours=3),
                level_start_sp=0,
                level_end_sp=100,
                training_start_sp=0,
                want=0.25,
            ),
            Case(
                start_date=now_ - dt.timedelta(hours=1),
                finish_date=now_ + dt.timedelta(hours=1),
                level_start_sp=0,
                level_end_sp=100,
                training_start_sp=50,
                want=0.75,
            ),
            Case(
                start_date=now_ - dt.timedelta(hours=2),
                finish_date=now_ + dt.timedelta(hours=1),
                level_start_sp=0,
                level_end_sp=100,
                training_start_sp=25,
                want=0.75,
            ),
            Case(
                start_date=now_ - dt.timedelta(hours=2),
                finish_date=now_ + dt.timedelta(hours=1),
                level_start_sp=100,
                level_end_sp=200,
                training_start_sp=125,
                want=0.75,
            ),
            Case(
                start_date=now_ + dt.timedelta(hours=1),
                finish_date=now_ + dt.timedelta(hours=3),
                want=0,
            ),
            Case(
                start_date=now_ - dt.timedelta(hours=3),
                finish_date=now_ - dt.timedelta(hours=1),
                want=1,
            ),
            Case(
                exception=ValueError,
            ),
            Case(
                start_date=now_ - dt.timedelta(hours=1),
                finish_date=now_ + dt.timedelta(hours=1),
                training_start_sp=None,
                exception=ValueError,
            ),
        ]
        for i, tc in enumerate(cases, 1):
            with self.subTest("completion percent", num=i):
                sqe = CharacterSkillqueueEntryFactory(
                    start_date=tc.start_date,
                    finish_date=tc.finish_date,
                    level_start_sp=tc.level_start_sp,
                    level_end_sp=tc.level_end_sp,
                    training_start_sp=tc.training_start_sp,
                )
                if tc.exception:
                    with self.assertRaises(tc.exception):
                        sqe.completion_percent()
                else:
                    got = sqe.completion_percent()
                    self.assertAlmostEqual(tc.want, got, delta=0.01)

    def test_can_calculate_total_duration(self):
        class Case(NamedTuple):
            want: Optional[dt.timedelta]
            start_date: Optional[dt.datetime] = None
            finish_date: Optional[dt.datetime] = None

        now_ = now()
        cases = [
            Case(
                start_date=now_ + dt.timedelta(hours=1),
                finish_date=now_ + dt.timedelta(hours=3),
                want=dt.timedelta(hours=2),
            ),
            Case(
                start_date=now_ - dt.timedelta(hours=3),
                want=None,
            ),
            Case(
                finish_date=now_ + dt.timedelta(hours=3),
                want=None,
            ),
            Case(
                want=None,
            ),
        ]
        for i, tc in enumerate(cases, 1):
            with self.subTest("total duration", num=i):
                sqe = CharacterSkillqueueEntryFactory(
                    start_date=tc.start_date,
                    finish_date=tc.finish_date,
                )
                got = sqe.total_duration()
                if tc.want is None:
                    self.assertIsNone(got)
                else:
                    self.assertAlmostEqual(tc.want, got, delta=dt.timedelta(seconds=5))

    def test_can_calculate_remaining_duration(self):
        class Case(NamedTuple):
            want: Optional[dt.timedelta]
            start_date: Optional[dt.datetime] = None
            finish_date: Optional[dt.datetime] = None
            level_start_sp: int = 0
            level_end_sp: int = 100
            training_start_sp: int = 0

        now_ = now()
        cases = [
            Case(
                start_date=now_,
                finish_date=now_ + dt.timedelta(hours=3),
                want=dt.timedelta(hours=3),
            ),
            Case(
                start_date=now_ - dt.timedelta(hours=3),
                finish_date=now_ - dt.timedelta(hours=2),
                want=dt.timedelta(seconds=0),
            ),
            Case(
                start_date=now_ - dt.timedelta(hours=3),
                want=None,
            ),
            Case(
                finish_date=now_ + dt.timedelta(hours=3),
                want=None,
            ),
            Case(
                want=None,
            ),
        ]
        for i, tc in enumerate(cases, 1):
            with self.subTest("total duration", num=i):
                sqe = CharacterSkillqueueEntryFactory(
                    start_date=tc.start_date,
                    finish_date=tc.finish_date,
                    level_start_sp=tc.level_start_sp,
                    level_end_sp=tc.level_end_sp,
                    training_start_sp=tc.training_start_sp,
                )
                got = sqe.remaining_duration()
                if tc.want is None:
                    self.assertIsNone(got)
                else:
                    self.assertAlmostEqual(tc.want, got, delta=dt.timedelta(seconds=5))


class TestCharacterStanding(NoSocketsTestCase):
    def test_effective_standing_with_connections(self):
        # given
        obj = CharacterStandingFactory(standing=4.99)
        # when
        result = obj.effective_standing(3, 0, 0)
        # then
        self.assertAlmostEqual(result, 5.59, 2)

    def test_effective_standing_with_diplomacy(self):
        # given
        obj = CharacterStandingFactory(standing=-4.76)
        # when
        result = obj.effective_standing(0, 0, 5)
        # then
        self.assertAlmostEqual(result, -1.81, 2)


class TestCharacterTitle(NoSocketsTestCase):
    def test_should_return_str(self):
        # given
        obj = CharacterTitleFactory(name="Dummy")
        # when
        result = str(obj)
        # then
        self.assertIn("Dummy", result)


class TestCharacterWalletJournals(NoSocketsTestCase):
    def test_should_return_eve_entity_ids(self):
        # given
        party_1 = EveEntityCharacterFactory()
        party_2 = EveEntityCharacterFactory()
        obj = CharacterWalletJournalEntryFactory(
            first_party=party_1, second_party=party_2
        )

        # when
        got = obj.eve_entity_ids()

        # then
        want = {party_1.id, party_2.id}
        self.assertSetEqual(got, want)

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
