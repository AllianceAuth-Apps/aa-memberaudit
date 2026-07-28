import datetime as dt
from contextlib import ExitStack
from http import HTTPStatus
from unittest.mock import patch

import pook

from django.test import override_settings
from django.utils.timezone import now
from eveuniverse.tests.testdata.factories_2 import (
    EveEntityCharacterFactory,
    EveEntityCorporationFactory,
    EveTypeFactory,
)

from app_utils.testing import NoSocketsTestCase

from memberaudit import tasks
from memberaudit.helpers import UpdateSectionResult
from memberaudit.models import (
    Character,
    CharacterContact,
    CharacterContactLabel,
    CharacterContract,
    CharacterContractItem,
    CharacterUpdateStatus,
)
from memberaudit.tests.testdata.factories_2 import (
    CharacterContractItemExchangeFactory,
    CharacterFactory,
    CharacterOrphanFactory,
    CharacterUpdateStatusFactory,
    ComplianceGroupFactory,
    LocationStationFactory,
    make_esi_url,
)
from memberaudit.tests.utils import TestCaseWithClearCache, extract

MODELS_PATH = "memberaudit.models"
TASKS_PATH = "memberaudit.tasks"


TASK_NAMES: frozenset[str] = frozenset(
    [
        "update_character_assets",
        "update_character_attributes",
        "update_character_character_details",
        "update_character_contacts",
        "update_character_contracts",
        "update_character_corporation_history",
        "update_character_fw_stats",
        "update_character_implants",
        "update_character_jump_clones",
        "update_character_location",
        "update_character_loyalty",
        "update_character_mails",
        "update_character_mining_ledger",
        "update_character_online_status",
        "update_character_planets",
        "update_character_roles",
        "update_character_ship",
        "update_character_skill_queue",
        "update_character_skill_sets",
        "update_character_skills",
        "update_character_standings",
        "update_character_titles",
        "update_character_wallet_balance",
        "update_character_wallet_journal",
        "update_character_wallet_transactions",
    ]
)


@patch(TASKS_PATH + ".unshare_expired_characters", spec=True)
@patch(TASKS_PATH + ".update_compliance_groups_for_all", spec=True)
@patch(TASKS_PATH + ".update_all_characters", spec=True)
@patch(TASKS_PATH + ".update_market_prices", spec=True)
class TestRegularUpdates(NoSocketsTestCase):
    def test_should_run_update_for_all_except_compliance_groups(
        self,
        mock_update_market_prices,
        mock_update_all_characters,
        mock_update_compliance_groups_for_all,
        mock_unshare_expired_characters,
    ):
        # when
        tasks.run_regular_updates()

        # then
        self.assertTrue(mock_update_market_prices.apply_async.called)
        self.assertTrue(mock_update_all_characters.apply_async.called)
        self.assertFalse(mock_update_compliance_groups_for_all.apply_async.called)

    def test_should_also_update_complice_groups_when_defined(
        self,
        mock_update_market_prices,
        mock_update_all_characters,
        mock_update_compliance_groups_for_all,
        mock_unshare_expired_characters,
    ):
        # given
        ComplianceGroupFactory()

        # when
        tasks.run_regular_updates()

        # then
        self.assertTrue(mock_update_market_prices.apply_async.called)
        self.assertTrue(mock_update_all_characters.apply_async.called)
        self.assertTrue(mock_update_compliance_groups_for_all.apply_async.called)

    def test_should_run_unsharing_of_expired_character_when_timeout_is_defined(
        self,
        mock_update_market_prices,
        mock_update_all_characters,
        mock_update_compliance_groups_for_all,
        mock_unshare_expired_characters,
    ):
        # given
        timeout = 3

        with patch(TASKS_PATH + ".MEMBERAUDIT_SHARING_TIMEOUT", timeout):
            # when
            tasks.run_regular_updates()

        # then
        self.assertTrue(mock_update_market_prices.apply_async.called)
        self.assertTrue(mock_update_all_characters.apply_async.called)
        self.assertTrue(mock_unshare_expired_characters.apply_async.called)
        _, kwargs = mock_unshare_expired_characters.apply_async.call_args
        self.assertEqual(kwargs["args"][0], timeout)

    def test_should_not_run_unsharing_of_expired_character_when_timeout_not_defined(
        self,
        mock_update_market_prices,
        mock_update_all_characters,
        mock_update_compliance_groups_for_all,
        mock_unshare_expired_characters,
    ):
        # given
        timeout = 0

        with patch(TASKS_PATH + ".MEMBERAUDIT_SHARING_TIMEOUT", timeout):
            # when
            tasks.run_regular_updates()

        # then
        self.assertTrue(mock_update_market_prices.apply_async.called)
        self.assertTrue(mock_update_all_characters.apply_async.called)
        self.assertFalse(mock_unshare_expired_characters.apply_async.called)


@patch(TASKS_PATH + ".esi_status.unavailable_sections", lambda: set())
@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
class TestUpdateCharacter(NoSocketsTestCase):
    def test_should_update_all_sections(self):
        # given
        character = CharacterFactory()
        with patch(MODELS_PATH + ".characters.MEMBERAUDIT_FEATURE_ROLES_ENABLED", True):
            with ExitStack() as stack:
                mocks = [
                    stack.enter_context(patch(TASKS_PATH + f".{name}", name=name))
                    for name in TASK_NAMES
                ]

                # when
                result = tasks.update_character(character.pk)

                # then
                self.assertTrue(result)
                for m in mocks:
                    with self.subTest(name=m._mock_name):
                        self.assertTrue(m.apply_async.called)

    def test_should_update_enabled_sections_only(self):
        # given
        character = CharacterFactory()
        with patch(
            MODELS_PATH + ".characters.MEMBERAUDIT_FEATURE_ROLES_ENABLED", False
        ):
            with ExitStack() as stack:
                mocks = [
                    stack.enter_context(patch(TASKS_PATH + f".{name}", name=name))
                    for name in TASK_NAMES - {"update_character_roles"}
                ]

                # when
                result = tasks.update_character(character.pk)

                # then
                self.assertTrue(result)
                for m in mocks:
                    with self.subTest(name=m._mock_name):
                        self.assertTrue(m.apply_async.called)

    def test_should_not_update_when_sections_are_current(self):
        # given
        character = CharacterFactory()
        for section in Character.UpdateSection.enabled_sections():
            CharacterUpdateStatusFactory(
                character=character, section=section, is_success=True
            )

        # when
        got = tasks.update_character(character.pk)

        # then
        self.assertFalse(got)

    def test_should_update_section_when_stale(self):
        # given
        character = CharacterFactory()
        sections = Character.UpdateSection.enabled_sections()
        sections.remove(Character.UpdateSection.LOYALTY)
        for section in sections:
            CharacterUpdateStatusFactory(
                character=character, section=section, is_success=True
            )

        CharacterUpdateStatusFactory(
            character=character,
            section=Character.UpdateSection.LOYALTY,
            is_success=True,
            run_finished_at=now() - dt.timedelta(hours=24),
        )

        with patch(TASKS_PATH + ".update_character_loyalty", spec=True) as m:
            # when
            got = tasks.update_character(character.pk)

            # then
            self.assertTrue(got)
            self.assertTrue(m.apply_async.called)

    def test_should_update_section_when_previous_update_failed(self):
        # given
        character = CharacterFactory()
        sections = Character.UpdateSection.enabled_sections()
        sections.remove(Character.UpdateSection.LOYALTY)
        for section in sections:
            CharacterUpdateStatusFactory(
                character=character, section=section, is_success=True
            )

        CharacterUpdateStatusFactory(
            character=character,
            section=Character.UpdateSection.LOYALTY,
            is_success=False,
        )

        with patch(TASKS_PATH + ".update_character_loyalty", spec=True) as m:
            # when
            got = tasks.update_character(character.pk)

            # then
            self.assertTrue(got)
            self.assertTrue(m.apply_async.called)

    def test_should_update_current_sections_when_requested(self):
        # given
        character = CharacterFactory()
        for section in Character.UpdateSection.enabled_sections():
            CharacterUpdateStatusFactory(
                character=character, section=section, is_success=True
            )

        with patch(MODELS_PATH + ".characters.MEMBERAUDIT_FEATURE_ROLES_ENABLED", True):
            with ExitStack() as stack:
                mocks = [
                    stack.enter_context(patch(TASKS_PATH + f".{name}", name=name))
                    for name in TASK_NAMES
                ]

                # when
                result = tasks.update_character(character.pk, ignore_stale=True)

                # then
                self.assertTrue(result)
                for m in mocks:
                    with self.subTest(name=m._mock_name):
                        self.assertTrue(m.apply_async.called)

    def test_should_skip_update_for_orphans(self):
        # given
        character = CharacterOrphanFactory()

        # when
        result = tasks.update_character(character.pk)

        # then
        self.assertFalse(result)


@patch(MODELS_PATH + ".characters.MEMBERAUDIT_FEATURE_ROLES_ENABLED", True)
@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
class TestUpdateCharacter_EsiIssues(NoSocketsTestCase):
    def test_should_not_update_sections_where_esi_endpoint_is_down(self):
        # given
        character = CharacterFactory()
        broken_section = Character.UpdateSection.LOYALTY
        with patch(
            TASKS_PATH + ".esi_status.unavailable_sections", lambda: {broken_section}
        ):
            with ExitStack() as stack:
                mocks = [
                    stack.enter_context(patch(TASKS_PATH + f".{name}", name=name))
                    for name in TASK_NAMES
                ]

                # when
                result = tasks.update_character(character.pk, ignore_stale=True)

                # then
                self.assertTrue(result)
                for m in mocks:
                    with self.subTest(name=m._mock_name):
                        if m._mock_name == "update_character_loyalty":
                            self.assertFalse(m.apply_async.called)
                        else:
                            self.assertTrue(m.apply_async.called)

    def test_should_not_update_when_no_esi_status_available(self):
        # given
        character = CharacterFactory()

        with patch(TASKS_PATH + ".esi_status.unavailable_sections", lambda: None):
            # when
            got = tasks.update_character(character.pk)

            # then
            self.assertFalse(got)


@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
class TestUpdateCharacterContacts(TestCaseWithClearCache):
    @pook.on
    def test_should_report_success_when_update_ok(self):
        # given
        character = CharacterFactory()
        label_id = 7
        pook.get(
            make_esi_url(f"characters/{character.character_id}/contacts/labels"),
            reply=HTTPStatus.OK,
            response_headers={"X-Pages": "1"},
            response_json=[{"label_id": label_id, "label_name": "alpha"}],
        )
        eve_entity = EveEntityCharacterFactory()
        pook.get(
            make_esi_url(f"characters/{character.character_id}/contacts"),
            reply=HTTPStatus.OK,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "contact_id": eve_entity.id,
                    "contact_type": "character",
                    "is_blocked": False,
                    "is_watched": True,
                    "label_ids": [label_id],
                    "standing": 5.0,
                }
            ],
        )

        # when
        tasks.update_character_contacts.delay(character.pk, True)

        # then
        status: CharacterUpdateStatus = character.update_status_set.get(
            section=Character.UpdateSection.CONTACTS
        )
        self.assertTrue(status.is_success)

        contact: CharacterContact = character.contacts.first()
        self.assertEqual(contact.eve_entity, eve_entity)

        label: CharacterContactLabel = character.contact_labels.first()
        self.assertEqual(label.label_id, label_id)


@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
class TestUpdateCharacterContracts(TestCaseWithClearCache):
    @pook.on
    def test_should_record_success_when_update_completed_successfully(self):
        # given
        character = CharacterFactory()
        pook.get(
            make_esi_url(f"characters/{character.character_id}/contracts"),
            reply=HTTPStatus.OK,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "assignee_id": 0,
                    "acceptor_id": 0,
                    "availability": "public",
                    "contract_id": 42,
                    "date_expired": now().isoformat(),
                    "date_issued": now().isoformat(),
                    "end_location_id": LocationStationFactory().id,
                    "for_corporation": False,
                    "issuer_corporation_id": EveEntityCorporationFactory().id,
                    "issuer_id": EveEntityCharacterFactory().id,
                    "reward": 123.45,
                    "start_location_id": LocationStationFactory().id,
                    "status": "outstanding",
                    "type": "courier",
                },
            ],
        )

        # when
        tasks.update_character_contracts.delay(
            character_pk=character.pk, force_update=False
        )

        # then
        status: CharacterUpdateStatus = character.update_status_set.get(
            section=Character.UpdateSection.CONTRACTS
        )
        self.assertTrue(status.is_success)
        self.assertFalse(status.error_message)
        self.assertTrue(status.run_finished_at)
        self.assertTrue(status.update_finished_at)

    @pook.on
    def test_should_store_new_item_exchange_contract_with_items(self):
        # given
        character = CharacterFactory()
        contract_id = 42
        pook.get(
            make_esi_url(f"characters/{character.character_id}/contracts"),
            reply=HTTPStatus.OK,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "assignee_id": 0,
                    "acceptor_id": 0,
                    "availability": "public",
                    "contract_id": contract_id,
                    "date_expired": now().isoformat(),
                    "date_issued": now().isoformat(),
                    "for_corporation": False,
                    "issuer_corporation_id": EveEntityCorporationFactory().id,
                    "issuer_id": EveEntityCharacterFactory().id,
                    "status": "outstanding",
                    "type": "item_exchange",
                }
            ],
        )
        record_id = 1
        quantity = 3
        eve_type = EveTypeFactory()
        pook.get(
            make_esi_url(
                f"characters/{character.character_id}/contracts/{contract_id}/items"
            ),
            reply=HTTPStatus.OK,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "is_included": True,
                    "is_singleton": False,
                    "quantity": quantity,
                    "record_id": record_id,
                    "type_id": eve_type.id,
                }
            ],
        )

        # when
        tasks.update_character_contracts.delay(
            character_pk=character.pk, force_update=False
        )

        # then
        self.assertEqual(character.contracts.count(), 1)
        contract: CharacterContract = character.contracts.first()
        self.assertEqual(contract.contract_id, contract_id)

        self.assertEqual(contract.items.count(), 1)
        item: CharacterContractItem = contract.items.first()
        self.assertEqual(item.record_id, record_id)

    @pook.on
    def test_should_fetch_items_for_new_contracts_only(self):
        # given
        character = CharacterFactory()
        contract_1 = CharacterContractItemExchangeFactory(
            character=character, contract_type=CharacterContract.TYPE_ITEM_EXCHANGE
        )
        contract_2_id = 42
        pook.get(
            make_esi_url(f"characters/{character.character_id}/contracts"),
            reply=HTTPStatus.OK,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "acceptor_id": 0,
                    "assignee_id": 0,
                    "availability": "public",
                    "contract_id": contract_1.contract_id,
                    "date_expired": contract_1.date_expired.isoformat(),
                    "date_issued": contract_1.date_issued.isoformat(),
                    "for_corporation": contract_1.for_corporation,
                    "issuer_corporation_id": contract_1.issuer_corporation.id,
                    "issuer_id": contract_1.issuer.id,
                    "price": contract_1.price,
                    "status": "outstanding",
                    "type": "item_exchange",
                },
                {
                    "assignee_id": 0,
                    "acceptor_id": 0,
                    "availability": "public",
                    "contract_id": contract_2_id,
                    "date_expired": now().isoformat(),
                    "date_issued": now().isoformat(),
                    "for_corporation": False,
                    "issuer_corporation_id": EveEntityCorporationFactory().id,
                    "issuer_id": EveEntityCharacterFactory().id,
                    "status": "outstanding",
                    "type": "item_exchange",
                },
            ],
        )
        record_id = 1
        quantity = 3
        eve_type = EveTypeFactory()
        pook.get(
            make_esi_url(
                f"characters/{character.character_id}/contracts/{contract_2_id}/items"
            ),
            reply=HTTPStatus.OK,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "is_included": True,
                    "is_singleton": False,
                    "quantity": quantity,
                    "record_id": record_id,
                    "type_id": eve_type.id,
                }
            ],
        )
        # only the route for contract_2 is provided.
        # Test would break when it tries to fetch items for contract 1.

        # when
        tasks.update_character_contracts.delay(
            character_pk=character.pk, force_update=False
        )

        # then
        got = extract(character.contracts, "contract_id")
        want = {contract_1.contract_id, contract_2_id}
        self.assertSetEqual(got, want)


@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
@patch(TASKS_PATH + ".Character.update_implants")
class TestUpdateCharacterSection(NoSocketsTestCase):
    def test_should_log_success_and_updated_when_update_succeeded(
        self, mock_update_implants
    ):
        # given
        mock_update_implants.return_value = UpdateSectionResult(True, True)
        character = CharacterFactory()

        # when
        tasks.update_character_implants.delay(
            character_pk=character.pk, force_update=False
        )

        # then
        self.assertTrue(mock_update_implants.called)
        status: CharacterUpdateStatus = character.update_status_set.get(
            section=Character.UpdateSection.IMPLANTS
        )
        self.assertTrue(status.is_success)
        self.assertFalse(status.error_message)
        self.assertTrue(status.run_finished_at)
        self.assertTrue(status.update_started_at)
        self.assertTrue(status.update_finished_at)

    def test_should_pass_though_exceptions_from_update_method(
        self, mock_update_implants
    ):
        # given
        mock_update_implants.side_effect = RuntimeError
        character = CharacterFactory()

        # when
        with self.assertRaises(RuntimeError):
            tasks.update_character_implants.delay(
                character_pk=character.pk, force_update=False
            )

        # then
        self.assertTrue(mock_update_implants.called)
        status: CharacterUpdateStatus = character.update_status_set.get(
            section=Character.UpdateSection.IMPLANTS
        )
        self.assertFalse(status.is_success)
        self.assertTrue(status.error_message)
        self.assertTrue(status.run_finished_at)
        self.assertIsNone(status.update_started_at)
        self.assertIsNone(status.update_finished_at)

    def test_should_clear_previous_errors_when_update_succeeded(
        self, mock_update_implants
    ):
        # given
        mock_update_implants.return_value = UpdateSectionResult(True, True)
        character = CharacterFactory()
        run_finished_at = now() - dt.timedelta(hours=4)
        status = CharacterUpdateStatusFactory(
            character=character,
            section=Character.UpdateSection.IMPLANTS,
            is_success=False,
            error_message="some error",
            run_finished_at=run_finished_at,
        )

        # when
        tasks.update_character_implants.delay(
            character_pk=character.pk, force_update=False
        )

        # then
        self.assertTrue(mock_update_implants.called)
        status.refresh_from_db()
        self.assertTrue(status.is_success)
        self.assertFalse(status.error_message)
        self.assertGreater(status.run_finished_at, run_finished_at)
        self.assertTrue(status.update_started_at)
        self.assertTrue(status.update_finished_at)

    def test_should_log_success_and_leave_update_dates_unchanged_when_no_update_1(
        self, mock_update_implants
    ):
        # given
        mock_update_implants.return_value = UpdateSectionResult(False, False)
        character = CharacterFactory()

        # when
        tasks.update_character_implants.delay(
            character_pk=character.pk, force_update=False
        )

        # then
        self.assertTrue(mock_update_implants.called)
        status: CharacterUpdateStatus = character.update_status_set.get(
            section=Character.UpdateSection.IMPLANTS
        )
        self.assertTrue(status.is_success)
        self.assertFalse(status.error_message)
        self.assertTrue(status.run_finished_at)
        self.assertIsNone(status.update_started_at)
        self.assertIsNone(status.update_finished_at)

    def test_should_log_success_and_leave_update_dates_unchanged_when_no_update_2(
        self, mock_update_implants
    ):
        # given
        mock_update_implants.return_value = UpdateSectionResult(False, False)
        character = CharacterFactory()
        update_started_at = now() - dt.timedelta(hours=4)
        update_finished_at = now() - dt.timedelta(hours=3)
        status = CharacterUpdateStatusFactory(
            character=character,
            section=Character.UpdateSection.IMPLANTS,
            is_success=True,
            update_started_at=update_started_at,
            update_finished_at=update_finished_at,
        )

        # when
        tasks.update_character_implants.delay(
            character_pk=character.pk, force_update=False
        )

        # then
        self.assertTrue(mock_update_implants.called)
        status.refresh_from_db()
        self.assertTrue(status.is_success)
        self.assertFalse(status.error_message)
        self.assertTrue(status.run_finished_at)
        self.assertEqual(status.update_started_at, update_started_at)
        self.assertEqual(status.update_finished_at, update_finished_at)
