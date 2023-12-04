import datetime as dt
from unittest.mock import patch

from django.test import TestCase
from eveuniverse.models import EveType

from memberaudit.helpers import (
    arabic_number_to_roman,
    data_retention_cutoff,
    determine_task_priority,
    eve_entity_ids_from_objs,
    implant_slot_num,
)

from .testdata.factories import create_character_wallet_journal_entry
from .testdata.load_entities import load_entities
from .testdata.load_eveuniverse import load_eveuniverse
from .utils import create_memberaudit_character

MODULE_PATH = "memberaudit.helpers"


class TaskStub:
    def __init__(self, *, properties: dict = None) -> None:
        if not properties:
            properties = {}
        self.request = {"properties": properties}


class TestDataRetentionCutoff(TestCase):
    @patch(MODULE_PATH + ".MEMBERAUDIT_DATA_RETENTION_LIMIT", 10)
    def test_limit_is_set(self):
        with patch(MODULE_PATH + ".now") as mock_now:
            mock_now.return_value = dt.datetime(2020, 12, 19, 16, 15)
            self.assertEqual(data_retention_cutoff(), dt.datetime(2020, 12, 9, 16, 0))

    @patch(MODULE_PATH + ".MEMBERAUDIT_DATA_RETENTION_LIMIT", None)
    def test_limit_not_set(self):
        with patch(MODULE_PATH + ".now") as mock_now:
            mock_now.return_value = dt.datetime(2020, 12, 19, 16, 15)
            self.assertIsNone(data_retention_cutoff())


class TestImplantSlotNum(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()

    def test_should_return_slot_num(self):
        # given
        implant = EveType.objects.get(name="High-grade Snake Beta")
        # when/then
        self.assertEqual(implant_slot_num(implant), 2)

    def test_should_return_0_when_no_slot_found(self):
        # given
        implant = EveType.objects.get(name="Merlin")
        # when/then
        self.assertEqual(implant_slot_num(implant), 0)


class TestDetermineTaskPriority(TestCase):
    def test_should_return_task_priority_when_it_exists(self):
        # given
        task = TaskStub(properties={"priority": 3})
        # when/then
        self.assertEqual(determine_task_priority(task), 3)

    def test_should_return_none_when_no_task_priority_exists(self):
        # given
        task = TaskStub()
        # when/then
        self.assertIsNone(determine_task_priority(task))


class TestEveEntityIdsFromObjs(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        cls.character = create_memberaudit_character(1001)

    def test_should_return_ids_from_all_objs(self):
        # given
        obj_1 = create_character_wallet_journal_entry(
            character=self.character, first_party_id=1001, second_party_id=1002
        )
        obj_2 = create_character_wallet_journal_entry(
            character=self.character, first_party_id=1101, second_party_id=1002
        )
        # when
        result = eve_entity_ids_from_objs([obj_1, obj_2])
        # then
        expected = {1001, 1002, 1101}
        self.assertSetEqual(result, expected)

    def test_should_return_empty_set_when_no_objs_provided(self):
        # when
        result = eve_entity_ids_from_objs([])
        # then
        expected = set()
        self.assertSetEqual(result, expected)


class TestArabicNumberToRoman(TestCase):
    def test_should_convert_correctly(self):
        # given
        cases = [
            (0, "-"),
            (1, "I"),
            (2, "II"),
            (3, "III"),
            (4, "IV"),
            (5, "V"),
            (99, "-"),
            (-1, "-"),
            ("wrong", "-"),
        ]
        for input, expected_result in cases:
            with self.subTest(input=input):
                # when/then
                self.assertEqual(arabic_number_to_roman(input), expected_result)
