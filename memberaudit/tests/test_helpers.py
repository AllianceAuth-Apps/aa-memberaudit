import datetime as dt
from unittest.mock import patch

from eveuniverse.tests.testdata.factories_2 import (
    EveEntityCharacterFactory,
    ShipTypeFactory,
)

from app_utils.testing import NoSocketsTestCase

from memberaudit.helpers import (
    arabic_number_to_roman,
    data_retention_cutoff,
    determine_task_priority,
    eve_entity_ids_from_objs,
    implant_slot_num,
)
from memberaudit.tests.testdata.factories_2 import (
    CharacterWalletJournalEntryFactory,
    CyberimplantTypeFactory,
)

MODULE_PATH = "memberaudit.helpers"


class TaskStub:
    def __init__(self, *, properties: dict = None) -> None:
        if not properties:
            properties = {}
        self.request = {"properties": properties}


class TestDataRetentionCutoff(NoSocketsTestCase):
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


class TestImplantSlotNum(NoSocketsTestCase):
    def test_should_return_slot_num(self):
        # given
        implant = CyberimplantTypeFactory(slot_num=2)
        # when/then
        self.assertEqual(implant_slot_num(implant), 2)

    def test_should_return_0_when_no_slot_found(self):
        # given
        implant = ShipTypeFactory()
        # when/then
        self.assertEqual(implant_slot_num(implant), 0)


class TestDetermineTaskPriority(NoSocketsTestCase):
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


class TestEveEntityIdsFromObjs(NoSocketsTestCase):
    def test_should_return_ids_from_all_objs(self):
        # given
        entity_1 = EveEntityCharacterFactory()
        entity_2 = EveEntityCharacterFactory()
        entity_3 = EveEntityCharacterFactory()
        obj_1 = CharacterWalletJournalEntryFactory(
            first_party=entity_1, second_party=entity_2
        )
        obj_2 = CharacterWalletJournalEntryFactory(
            first_party=entity_3, second_party=entity_2
        )
        # when
        result = eve_entity_ids_from_objs([obj_1, obj_2])
        # then
        expected = {entity_1.id, entity_2.id, entity_3.id}
        self.assertSetEqual(result, expected)

    def test_should_return_empty_set_when_no_objs_provided(self):
        # when
        result = eve_entity_ids_from_objs([])
        # then
        expected = set()
        self.assertSetEqual(result, expected)


class TestArabicNumberToRoman(NoSocketsTestCase):
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
