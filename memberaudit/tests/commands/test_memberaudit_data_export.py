import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command

from app_utils.testing import NoSocketsTestCase

from memberaudit.tests.testdata.factories_2 import (
    CharacterContractItemExchangeFactory,
    CharacterFactory,
)


class TestDataExport(NoSocketsTestCase):
    def test_should_export_contract_item(self):
        with tempfile.TemporaryDirectory() as tmp_dir_name:
            # given
            character = CharacterFactory()
            CharacterContractItemExchangeFactory(character=character)
            out = StringIO()
            # when
            call_command(
                "memberaudit_data_export",
                "contract-item",
                "--destination",
                tmp_dir_name,
                stdout=out,
            )
            # then
            output_file = Path(tmp_dir_name) / Path(
                "memberaudit_contract-item"
            ).with_suffix(".csv")
            self.assertTrue(output_file.exists())
