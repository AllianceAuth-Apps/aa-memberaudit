import csv
import datetime as dt
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zipfile import ZipFile

from django.utils.timezone import now
from eveuniverse.tests.testdata.factories_2 import EveEntityCharacterFactory

from app_utils.testdata_factories import (
    EveAllianceInfoFactory,
    EveCharacterFactory,
    EveCorporationInfoFactory,
    UserMainFactory,
)
from app_utils.testing import NoSocketsTestCase

from memberaudit.core.data_exporters import (
    ContractExporter,
    ContractItemExporter,
    DataExporter,
    WalletJournalExporter,
    export_topic_to_archive,
    file_to_zip,
    topics_and_export_files,
)
from memberaudit.models import CharacterWalletJournalEntry
from memberaudit.tests.testdata.factories_2 import (
    CharacterContractItemExchangeFactory,
    CharacterContractItemFactory,
    CharacterFactory,
    CharacterOrphanFactory,
    CharacterWalletJournalEntryFactory,
)

MODULE_PATH = "memberaudit.core.data_exporters"


class TestExportTopicToArchive(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.character = CharacterFactory()

    def test_should_export_contract(self):
        with TemporaryDirectory() as tmpdirname:
            # given
            CharacterContractItemExchangeFactory(character=self.character)

            # when
            result = export_topic_to_archive(
                topic="contract", destination_folder=tmpdirname
            )
            # then
            output_file = Path(result)
            self.assertTrue(output_file.exists())
            self.assertEqual("memberaudit_contract.zip", output_file.name)

    def test_should_export_contract_item(self):
        with TemporaryDirectory() as tmpdirname:
            # given
            CharacterContractItemExchangeFactory(character=self.character)

            # when
            result = export_topic_to_archive(
                topic="contract-item", destination_folder=tmpdirname
            )
            # then
            output_file = Path(result)
            self.assertTrue(output_file.exists())
            self.assertEqual("memberaudit_contract-item.zip", output_file.name)

    def test_should_export_wallet_journal(self):
        with TemporaryDirectory() as tmpdirname:
            # given
            CharacterWalletJournalEntryFactory(character=self.character)

            # when
            result = export_topic_to_archive(
                topic="wallet-journal", destination_folder=tmpdirname
            )
            # then
            output_file = Path(result)
            self.assertTrue(output_file.exists())
            self.assertEqual("memberaudit_wallet-journal.zip", output_file.name)

    def test_should_not_export_wallet_journal_when_no_data(self):
        with TemporaryDirectory() as tmpdirname:
            # when
            result = export_topic_to_archive(
                topic="wallet-journal", destination_folder=tmpdirname
            )
            # then
            self.assertEqual("", result)


class TestZipFile(NoSocketsTestCase):
    def test_should_zip_file_into_archive(self):
        with TemporaryDirectory() as tmpdirname_1, TemporaryDirectory() as tmpdirname_2:
            # given
            source_file = Path(tmpdirname_1) / "test.csv"
            with source_file.open("w") as fp:
                fp.write("test file")
            destination = Path(tmpdirname_2)
            # when
            zip_file = file_to_zip(source_file, destination)
            # then
            with ZipFile(zip_file, "r") as myzip:
                namelist = myzip.namelist()
            self.assertIn(source_file.name, namelist)


class NotTopicExporter(DataExporter):
    def format_obj(self, *args, **kwargs):
        return {}

    def get_queryset(self, *args, **kwargs):
        return None


class InvalidTopicExporter(NotTopicExporter):
    topic = "invalid_topic"


class TestDataExporter(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.character = CharacterFactory(
            user=UserMainFactory(
                main_character__character=EveCharacterFactory(
                    character_name="Bruce Wayne",
                    corporation=EveCorporationInfoFactory(
                        corporation_name="Wayne Technologies",
                        alliance=EveAllianceInfoFactory(alliance_ticker="WYN"),
                    ),
                ),
            )
        )
        cls.orphan = CharacterOrphanFactory()

    def test_should_create_exporters(self):
        # given
        exporter_map = {
            "contract": ContractExporter,
            "contract-item": ContractItemExporter,
            "wallet-journal": WalletJournalExporter,
        }
        # when/then
        for topic, ExporterClass in exporter_map.items():
            obj = DataExporter.create_exporter(topic)
            # then
            self.assertIsInstance(obj, ExporterClass)

    def test_should_not_create_exporters(self):
        with self.assertRaises(ValueError):
            DataExporter.create_exporter("not-implemented")

    def test_should_return_topics(self):
        self.assertListEqual(
            DataExporter.topics(), ["contract", "contract-item", "wallet-journal"]
        )

    def test_can_not_init_exporter_without_topic(self):
        with self.assertRaises(ValueError):
            NotTopicExporter()

    def test_can_not_init_exporter_with_invalid_topic(self):
        with self.assertRaises(ValueError):
            InvalidTopicExporter()

    def test_should_return_title(self):
        # given
        exporter = DataExporter.create_exporter("wallet-journal")
        # when/then
        self.assertEqual(exporter.title, "Wallet Journal")

    def test_should_show_count(self):
        # given
        CharacterWalletJournalEntryFactory(character=self.character)
        exporter = DataExporter.create_exporter("wallet-journal")
        # when/then
        self.assertEqual(exporter.count(), 1)

    def test_should_have_data(self):
        # given
        CharacterWalletJournalEntryFactory(character=self.character)
        exporter = DataExporter.create_exporter("wallet-journal")
        # when/then
        self.assertTrue(exporter.has_data())

    def test_should_create_csv_file_for_contract(self):
        # given
        CharacterContractItemExchangeFactory(character=self.character, contract_id=42)
        CharacterContractItemExchangeFactory(character=self.orphan, contract_id=69)
        exporter = DataExporter.create_exporter("contract")

        # when
        data = self._write_to_file(exporter)

        # then
        self.assertEqual(len(data), 2)
        obj = data["Bruce Wayne"]
        self.assertEqual(obj["owner character"], "Bruce Wayne")
        self.assertEqual(obj["owner corporation"], "Wayne Technologies")
        self.assertEqual(obj["contract id"], "42")
        # TODO: test all properties and all contract types

    def test_should_create_csv_file_for_contract_item(self):
        # given
        contract = CharacterContractItemExchangeFactory(
            character=self.character, items=False
        )
        CharacterContractItemFactory(
            contract=contract, record_id=12, quantity=1, eve_type__name="Merlin"
        )
        exporter = DataExporter.create_exporter("contract-item")
        # when
        data = self._write_to_file(exporter, "record id")
        # then
        self.assertEqual(len(data), 1)
        obj = data["12"]
        self.assertEqual(obj["contract pk"], str(contract.pk))
        self.assertEqual(obj["record id"], "12")
        self.assertEqual(obj["type"], "Merlin")
        self.assertEqual(obj["quantity"], "1")
        # TODO: test all properties and all contract types

    def test_should_create_csv_file_for_wallet_journal(self):
        # given
        entity_1001 = EveEntityCharacterFactory(id=1001, name="Bruce Wayne")
        entity_1002 = EveEntityCharacterFactory(id=1002, name="Clark Kent")
        entity_1101 = EveEntityCharacterFactory(id=1101, name="Lex Luther")
        CharacterWalletJournalEntryFactory(
            amount=1000000.0,
            balance=20000000.0,
            character=self.character,
            context_id=1002,
            context_id_type=CharacterWalletJournalEntry.CONTEXT_ID_TYPE_CHARACTER_ID,
            date=dt.datetime(2021, 12, 1, 12, 30, tzinfo=dt.timezone.utc),
            description="test description",
            entry_id=42,
            first_party=entity_1001,
            ref_type="player_donation",
            reason="test reason",
            second_party=entity_1002,
            tax=0.05,
            tax_receiver=entity_1101,
        )
        CharacterWalletJournalEntryFactory(
            amount=1000000.0,
            balance=20000000.0,
            character=self.orphan,
            context_id=1002,
            context_id_type=CharacterWalletJournalEntry.CONTEXT_ID_TYPE_CHARACTER_ID,
            date=dt.datetime(2021, 12, 1, 12, 30, tzinfo=dt.timezone.utc),
            description="test description",
            entry_id=69,
            first_party_id=1001,
            ref_type="player_donation",
            reason="test reason",
            second_party=entity_1002,
            tax=0.05,
            tax_receiver=entity_1101,
        )
        exporter = DataExporter.create_exporter("wallet-journal")
        # when
        data = self._write_to_file(exporter)
        # then
        self.assertEqual(len(data), 2)
        obj = data["Bruce Wayne"]
        self.assertEqual(obj["owner character"], "Bruce Wayne")
        self.assertEqual(obj["owner corporation"], "Wayne Technologies")
        self.assertEqual(obj["amount"], "1000000.0")
        self.assertEqual(obj["balance"], "20000000.0")
        self.assertEqual(obj["date"], "2021-12-01 12:30:00")
        self.assertEqual(obj["description"], "test description")
        self.assertEqual(obj["entry id"], "42")
        self.assertEqual(obj["first party"], "Bruce Wayne")
        self.assertEqual(obj["ref type"], "Player Donation")
        self.assertEqual(obj["second party"], "Clark Kent")
        self.assertEqual(obj["reason"], "test reason")
        self.assertEqual(obj["context_id"], "1002")
        self.assertEqual(obj["context_id_type"], "character ID")
        self.assertEqual(obj["tax"], "0.05")
        self.assertEqual(obj["tax_receiver"], "Lex Luther")

    def _write_to_file(self, exporter, key="owner character") -> dict:
        with TemporaryDirectory() as tmpdirname:
            output_file = exporter.write_to_file(tmpdirname)
            self.assertTrue(output_file.exists())
            with output_file.open("r") as csv_file:
                reader = csv.DictReader(csv_file)
                return {row[key]: row for row in reader}


class TestTopicsAndExportFiles(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.character = CharacterFactory()

    @patch(MODULE_PATH + ".MEMBERAUDIT_DATA_EXPORT_MIN_UPDATE_AGE", 60)
    def test_should_return_correct_list(self):
        with TemporaryDirectory() as tmpdirname:
            # given
            contract = CharacterContractItemExchangeFactory(character=self.character)
            contract_item_file = Path(tmpdirname) / "memberaudit_contract-item.zip"
            contract_item_file.touch()
            new_ts = (now() - dt.timedelta(minutes=10)).timestamp()
            os.utime(contract_item_file, (new_ts, new_ts))
            contract_file = Path(tmpdirname) / "memberaudit_contract.zip"
            contract_file.touch()
            contract_file_dt = now() - dt.timedelta(minutes=61)
            new_ts = contract_file_dt.timestamp()
            os.utime(contract_file, (new_ts, new_ts))
            wrong_file = Path(tmpdirname) / "memberaudit.zip"
            wrong_file.touch()

            # when
            result = topics_and_export_files(tmpdirname)
            result_2 = {obj["value"]: obj for obj in result}

            # then
            self.assertListEqual(
                list(result_2.keys()), ["contract", "contract-item", "wallet-journal"]
            )
            contract = result_2["contract"]
            self.assertEqual(contract["value"], "contract")
            self.assertEqual(contract["title"], "Contract")
            self.assertEqual(contract["rows"], 1)
            self.assertEqual(contract["last_updated_at"], contract_file_dt)
            self.assertTrue(contract["has_file"])
            self.assertTrue(contract["update_allowed"])
            contract_item = result_2["contract-item"]
            self.assertTrue(contract_item["has_file"])
            self.assertAlmostEqual(
                contract_item["last_updated_at"],
                now(),
                delta=dt.timedelta(minutes=10, seconds=10),
            )
            self.assertFalse(contract_item["update_allowed"])
            wallet_journal = result_2["wallet-journal"]
            self.assertFalse(wallet_journal["has_file"])
            self.assertEqual(wallet_journal["rows"], 0)
