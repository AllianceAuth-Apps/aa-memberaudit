import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command

from app_utils.testing import NoSocketsTestCase

from memberaudit.tests.testdata.factories import (
    create_character_contract,
    create_character_contract_item,
)
from memberaudit.tests.testdata.load_entities import load_entities
from memberaudit.tests.testdata.load_eveuniverse import load_eveuniverse
from memberaudit.tests.utils import create_memberaudit_character

DATA_EXPORTERS_PATH = "memberaudit.core.data_exporters"


class TestDataExport(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities()
        load_eveuniverse()
        cls.character_1001 = create_memberaudit_character(1001)

    def test_should_export_contract_item(self):
        with tempfile.TemporaryDirectory() as tmp_dir_name:
            # given
            contract = create_character_contract(character=self.character_1001)
            create_character_contract_item(contract=contract, record_id=12)
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
