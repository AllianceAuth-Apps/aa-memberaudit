import datetime as dt
from http import HTTPStatus
from unittest.mock import patch

import pook

from django.utils.timezone import now
from eveuniverse.tests.testdata.factories_2 import (
    EveEntityCharacterFactory,
    EveEntityCorporationFactory,
    EveTypeFactory,
)

from memberaudit.models import (
    CharacterWalletBalance,
    CharacterWalletJournalEntry,
    CharacterWalletTransaction,
)
from memberaudit.tests.testdata.factories_2 import (
    CharacterFactory,
    CharacterWalletBalanceFactory,
    CharacterWalletJournalEntryFactory,
    CharacterWalletTransactionFactory,
    LocationStationFactory,
    make_esi_url,
)
from memberaudit.tests.utils import TestCaseWithClearCache, extract

MANAGERS_PATH = "memberaudit.managers.character_sections_3"


class TestCharacter_UpdateWalletBalance(TestCaseWithClearCache):
    @pook.on
    def test_can_create_new(self):
        # given
        character = CharacterFactory()
        total = 123.45
        pook.get(
            make_esi_url(f"characters/{character.character_id}/wallet"),
            reply=HTTPStatus.OK,
            response_headers={"X-Pages": "1"},
            response_json=total,
        )

        # when
        character.update_wallet_balance()

        # then
        balance: CharacterWalletBalance = character.wallet_balance
        self.assertEqual(float(balance.total), total)

    @pook.on
    def test_can_update_existing(self):
        # given
        character = CharacterFactory()
        balance = CharacterWalletBalanceFactory(character=character)
        total = 123.45
        pook.get(
            make_esi_url(f"characters/{character.character_id}/wallet"),
            reply=HTTPStatus.OK,
            response_headers={"X-Pages": "1"},
            response_json=total,
        )

        # when
        character.update_wallet_balance()

        # then
        balance.refresh_from_db()
        self.assertEqual(float(balance.total), total)


class TestCharacter_UpdateWalletJournal(TestCaseWithClearCache):
    @pook.on
    def test_can_create_from_scratch(self):
        # given
        character = CharacterFactory()
        amount = 123.45
        balance = 10_000
        context_id = 888
        context_id_type = CharacterWalletJournalEntry.CONTEXT_ID_TYPE_ALLIANCE_ID
        date = now()
        description = "description"
        entry_id = 42
        first_party = EveEntityCharacterFactory()
        reason = "reason"
        ref_type = "acceleration_gate_fee"
        second_party = EveEntityCharacterFactory()
        tax = 0.12
        tax_receiver = EveEntityCorporationFactory()
        pook.get(
            make_esi_url(f"characters/{character.character_id}/wallet/journal"),
            reply=HTTPStatus.OK,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "amount": amount,
                    "balance": balance,
                    "context_id_type": "alliance_id",
                    "context_id": context_id,
                    "date": date.isoformat(),
                    "description": description,
                    "first_party_id": first_party.id,
                    "id": entry_id,
                    "reason": reason,
                    "ref_type": ref_type,
                    "second_party_id": second_party.id,
                    "tax_receiver_id": tax_receiver.id,
                    "tax": tax,
                }
            ],
        )

        # when
        character.update_wallet_journal()

        # then
        self.assertEqual(character.wallet_journal.count(), 1)
        entry: CharacterWalletJournalEntry = character.wallet_journal.first()
        self.assertEqual(float(entry.amount), amount)
        self.assertEqual(entry.context_id_type, context_id_type)
        self.assertEqual(entry.context_id, context_id)
        self.assertEqual(float(entry.balance), balance)
        self.assertEqual(entry.date, date)
        self.assertEqual(entry.description, description)
        self.assertEqual(entry.entry_id, entry_id)
        self.assertEqual(entry.first_party, first_party)
        self.assertEqual(entry.reason, reason)
        self.assertEqual(entry.ref_type, ref_type)
        self.assertEqual(entry.second_party, second_party)
        self.assertEqual(entry.tax_receiver, tax_receiver)
        self.assertEqual(float(entry.tax), tax)

    @pook.on
    def test_can_add_entries(self):
        # given
        character = CharacterFactory()
        entry_1 = CharacterWalletJournalEntryFactory(character=character, entry_id=1)
        entry_2_id = 2
        pook.get(
            make_esi_url(f"characters/{character.character_id}/wallet/journal"),
            reply=HTTPStatus.OK,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "amount": 123.45,
                    "balance": 10_000,
                    "date": now().isoformat(),
                    "description": "description",
                    "first_party_id": EveEntityCharacterFactory().id,
                    "id": entry_2_id,
                    "reason": "readon",
                    "ref_type": "acceleration_gate_fee",
                }
            ],
        )

        # when
        character.update_wallet_journal()

        # then
        got = extract(character.wallet_journal, "entry_id")
        want = {entry_1.entry_id, entry_2_id}
        self.assertSetEqual(got, want)

    @pook.on
    def test_should_not_update_existing(self):
        # given
        character = CharacterFactory()
        amount = 123.45
        balance = 10_000
        date = now() - dt.timedelta(days=3)
        description = "description"
        entry_id = 42
        first_party = EveEntityCharacterFactory()
        reason = "reason"
        ref_type = "acceleration_gate_fee"
        entry = CharacterWalletJournalEntryFactory(
            character=character,
            entry_id=entry_id,
            amount=amount,
            balance=balance,
            date=date,
            description=description,
            first_party=first_party,
            reason=reason,
            ref_type=ref_type,
        )
        pook.get(
            make_esi_url(f"characters/{character.character_id}/wallet/journal"),
            reply=HTTPStatus.OK,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "amount": 1,
                    "balance": 2,
                    "date": now().isoformat(),
                    "description": "description-2",
                    "first_party_id": EveEntityCharacterFactory().id,
                    "id": entry.entry_id,
                    "reason": "reason-2",
                    "ref_type": "player_donation",
                }
            ],
        )

        # when
        character.update_wallet_journal()

        # then
        entry.refresh_from_db()
        self.assertEqual(float(entry.amount), amount)
        self.assertEqual(float(entry.balance), balance)
        self.assertEqual(entry.date, date)
        self.assertEqual(entry.description, description)
        self.assertEqual(entry.entry_id, entry_id)
        self.assertEqual(entry.first_party, first_party)
        self.assertEqual(entry.reason, reason)
        self.assertEqual(entry.ref_type, ref_type)

    @pook.on
    def test_should_not_store_entries_that_are_older_then_retention_limit(self):
        # given
        data_retention_cutoff = now() - dt.timedelta(days=30)
        character = CharacterFactory()
        entry_1 = CharacterWalletJournalEntryFactory(character=character, entry_id=1)
        entry_2_id = 2
        date_2 = data_retention_cutoff - dt.timedelta(seconds=1)
        pook.get(
            make_esi_url(f"characters/{character.character_id}/wallet/journal"),
            reply=HTTPStatus.OK,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "amount": 123.45,
                    "balance": 10_000,
                    "date": date_2.isoformat(),
                    "description": "description",
                    "first_party_id": EveEntityCharacterFactory().id,
                    "id": entry_2_id,
                    "reason": "reason",
                    "ref_type": "acceleration_gate_fee",
                }
            ],
        )

        # when
        with patch(
            MANAGERS_PATH + ".data_retention_cutoff", lambda: data_retention_cutoff
        ):
            character.update_wallet_journal()

        # then
        got = extract(character.wallet_journal, "entry_id")
        want = {entry_1.entry_id}
        self.assertSetEqual(got, want)

    @pook.on
    def test_should_remove_entries_from_storage_that_are_older_then_retention_limit(
        self,
    ):
        # given
        data_retention_cutoff = now() - dt.timedelta(days=30)
        character = CharacterFactory()
        entry_1 = CharacterWalletJournalEntryFactory(character=character)
        CharacterWalletJournalEntryFactory(
            character=character, date=data_retention_cutoff - dt.timedelta(seconds=1)
        )  # to be removed
        pook.get(
            make_esi_url(f"characters/{character.character_id}/wallet/journal"),
            reply=HTTPStatus.OK,
            response_headers={"X-Pages": "1"},
            response_json=[],
        )

        # when
        with patch(
            MANAGERS_PATH + ".data_retention_cutoff", lambda: data_retention_cutoff
        ):
            character.update_wallet_journal()

        # then
        got = extract(character.wallet_journal, "entry_id")
        want = {entry_1.entry_id}
        self.assertSetEqual(got, want)


class TestCharacter_UpdateWalletTransactions(TestCaseWithClearCache):
    @pook.on
    def test_should_add_wallet_transactions_from_scratch(self):
        # given
        character = CharacterFactory()
        client = EveEntityCharacterFactory()
        date = now()
        is_buy = True
        is_personal = True
        location = LocationStationFactory()
        quantity = 3
        transaction_id = 42
        eve_type = EveTypeFactory()
        unit_price = 123.45
        pook.get(
            make_esi_url(f"characters/{character.character_id}/wallet/transactions"),
            reply=HTTPStatus.OK,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "client_id": client.id,
                    "date": date.isoformat(),
                    "is_buy": is_buy,
                    "is_personal": is_personal,
                    "journal_ref_id": 0,
                    "location_id": location.id,
                    "quantity": quantity,
                    "transaction_id": transaction_id,
                    "type_id": eve_type.id,
                    "unit_price": unit_price,
                }
            ],
        )
        # when
        character.update_wallet_transactions()

        # then
        self.assertEqual(character.wallet_transactions.count(), 1)
        obj: CharacterWalletTransaction = character.wallet_transactions.first()
        self.assertEqual(obj.client, client)
        self.assertEqual(obj.date, date)
        self.assertEqual(obj.is_buy, is_buy)
        self.assertEqual(obj.is_personal, is_personal)
        self.assertIsNone(obj.journal_ref)
        self.assertEqual(obj.location, location)
        self.assertEqual(obj.quantity, quantity)
        self.assertEqual(obj.eve_type, eve_type)
        self.assertEqual(float(obj.unit_price), unit_price)

    @pook.on
    def test_should_add_wallet_transactions_from_scratch_with_journL_ref(self):
        # given
        character = CharacterFactory()
        entry = CharacterWalletJournalEntryFactory(character=character)
        client = EveEntityCharacterFactory()
        date = now()
        is_buy = True
        is_personal = True
        location = LocationStationFactory()
        quantity = 3
        transaction_id = 42
        eve_type = EveTypeFactory()
        unit_price = 123.45
        pook.get(
            make_esi_url(f"characters/{character.character_id}/wallet/transactions"),
            reply=HTTPStatus.OK,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "client_id": client.id,
                    "date": date.isoformat(),
                    "is_buy": is_buy,
                    "is_personal": is_personal,
                    "journal_ref_id": entry.entry_id,
                    "location_id": location.id,
                    "quantity": quantity,
                    "transaction_id": transaction_id,
                    "type_id": eve_type.id,
                    "unit_price": unit_price,
                }
            ],
        )
        # when
        character.update_wallet_transactions()

        # then
        self.assertEqual(character.wallet_transactions.count(), 1)
        obj: CharacterWalletTransaction = character.wallet_transactions.first()
        self.assertEqual(obj.client, client)
        self.assertEqual(obj.date, date)
        self.assertEqual(obj.is_buy, is_buy)
        self.assertEqual(obj.is_personal, is_personal)
        self.assertEqual(obj.journal_ref, entry)
        self.assertEqual(obj.location, location)
        self.assertEqual(obj.quantity, quantity)
        self.assertEqual(obj.eve_type, eve_type)
        self.assertEqual(float(obj.unit_price), unit_price)

    @pook.on
    def test_should_add_wallet_transactions_to_existing(self):
        # given
        character = CharacterFactory()
        transaction_1 = CharacterWalletTransactionFactory(character=character)
        transaction_2_id = 2
        pook.get(
            make_esi_url(f"characters/{character.character_id}/wallet/transactions"),
            reply=HTTPStatus.OK,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "client_id": EveEntityCharacterFactory().id,
                    "date": now().isoformat(),
                    "is_buy": True,
                    "is_personal": True,
                    "journal_ref_id": 0,
                    "location_id": LocationStationFactory().id,
                    "quantity": 3,
                    "transaction_id": transaction_2_id,
                    "type_id": EveTypeFactory().id,
                    "unit_price": 12.34,
                }
            ],
        )
        # when
        character.update_wallet_transactions()

        # then
        got = extract(character.wallet_transactions, "transaction_id")
        want = {transaction_1.transaction_id, transaction_2_id}
        self.assertSetEqual(got, want)

    @pook.on
    def test_should_not_update_existing_transactions(self):
        # given
        character = CharacterFactory()
        client = EveEntityCharacterFactory()
        date = now() - dt.timedelta(hours=3)
        is_buy = True
        is_personal = True
        location = LocationStationFactory()
        quantity = 3
        transaction_id = 42
        eve_type = EveTypeFactory()
        unit_price = 123.45
        transaction = CharacterWalletTransactionFactory(
            character=character,
            client=client,
            date=date,
            eve_type=eve_type,
            is_buy=is_buy,
            is_personal=is_personal,
            location=location,
            quantity=quantity,
            transaction_id=transaction_id,
            unit_price=unit_price,
        )
        pook.get(
            make_esi_url(f"characters/{character.character_id}/wallet/transactions"),
            reply=HTTPStatus.OK,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "client_id": EveEntityCharacterFactory().id,
                    "date": now().isoformat(),
                    "is_buy": True,
                    "is_personal": True,
                    "journal_ref_id": 0,
                    "location_id": LocationStationFactory().id,
                    "quantity": 3,
                    "transaction_id": transaction.transaction_id,
                    "type_id": EveTypeFactory().id,
                    "unit_price": 12.34,
                }
            ],
        )
        # when
        character.update_wallet_transactions()

        # then
        self.assertEqual(character.wallet_transactions.count(), 1)
        obj: CharacterWalletTransaction = character.wallet_transactions.first()
        self.assertEqual(obj.client, client)
        self.assertEqual(obj.date, date)
        self.assertEqual(obj.is_buy, is_buy)
        self.assertEqual(obj.is_personal, is_personal)
        self.assertIsNone(obj.journal_ref)
        self.assertEqual(obj.location, location)
        self.assertEqual(obj.quantity, quantity)
        self.assertEqual(obj.eve_type, eve_type)
        self.assertEqual(float(obj.unit_price), unit_price)

    @pook.on
    def test_should_not_store_entries_that_are_older_then_retention_limit(self):
        # given
        data_retention_cutoff = now() - dt.timedelta(days=30)
        character = CharacterFactory()
        transaction_1 = CharacterWalletTransactionFactory(character=character)
        transaction_2_id = 2
        date_2 = data_retention_cutoff - dt.timedelta(seconds=1)
        pook.get(
            make_esi_url(f"characters/{character.character_id}/wallet/transactions"),
            reply=HTTPStatus.OK,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "client_id": EveEntityCharacterFactory().id,
                    "date": date_2.isoformat(),
                    "is_buy": True,
                    "is_personal": True,
                    "journal_ref_id": 0,
                    "location_id": LocationStationFactory().id,
                    "quantity": 3,
                    "transaction_id": transaction_2_id,
                    "type_id": EveTypeFactory().id,
                    "unit_price": 12.34,
                }
            ],
        )
        # when
        with patch(
            MANAGERS_PATH + ".data_retention_cutoff", lambda: data_retention_cutoff
        ):
            character.update_wallet_transactions()

        # then
        got = extract(character.wallet_transactions, "transaction_id")
        want = {transaction_1.transaction_id}
        self.assertSetEqual(got, want)

    @pook.on
    def test_should_remove_entries_from_storage_that_are_older_then_retention_limit(
        self,
    ):
        # given
        data_retention_cutoff = now() - dt.timedelta(days=30)
        character = CharacterFactory()
        CharacterWalletTransactionFactory(
            character=character, date=data_retention_cutoff - dt.timedelta(seconds=1)
        )  # to be removed
        transaction_2_id = 2
        pook.get(
            make_esi_url(f"characters/{character.character_id}/wallet/transactions"),
            reply=HTTPStatus.OK,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "client_id": EveEntityCharacterFactory().id,
                    "date": now().isoformat(),
                    "is_buy": True,
                    "is_personal": True,
                    "journal_ref_id": 0,
                    "location_id": LocationStationFactory().id,
                    "quantity": 3,
                    "transaction_id": transaction_2_id,
                    "type_id": EveTypeFactory().id,
                    "unit_price": 12.34,
                }
            ],
        )
        # when
        with patch(
            MANAGERS_PATH + ".data_retention_cutoff", lambda: data_retention_cutoff
        ):
            character.update_wallet_transactions()

        # then
        got = extract(character.wallet_transactions, "transaction_id")
        want = {transaction_2_id}
        self.assertSetEqual(got, want)
