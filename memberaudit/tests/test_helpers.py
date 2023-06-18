import datetime as dt
from unittest.mock import patch

from django.test import TestCase
from eveuniverse.models import EveType

from memberaudit.helpers import data_retention_cutoff, implant_slot_num

from .testdata.load_eveuniverse import load_eveuniverse

MODULE_PATH = "memberaudit.helpers"


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
    def setUpClass(cls) -> None:
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
