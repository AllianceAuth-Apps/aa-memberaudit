import datetime as dt
from unittest.mock import patch

from django.test import TestCase

from memberaudit.helpers import data_retention_cutoff

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
