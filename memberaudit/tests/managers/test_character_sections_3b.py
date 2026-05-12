import datetime as dt
from collections import namedtuple
from unittest.mock import patch

from django.test import override_settings
from django.utils.dateparse import parse_datetime
from django.utils.timezone import now
from eveuniverse.models import EveEntity, EveType

from app_utils.esi_testing import EsiClientStub, EsiEndpoint
from app_utils.testing import NoSocketsTestCase

from memberaudit.models import (
    CharacterSkillSetCheck,
    CharacterStanding,
    CharacterWalletBalance,
    CharacterWalletJournalEntry,
    CharacterWalletTransaction,
    Location,
)
from memberaudit.tests.testdata.esi_client_stub import esi_client_stub
from memberaudit.tests.testdata.factories import (
    create_character_skill,
    create_character_skill_set_check,
    create_character_standing,
    create_character_title,
    create_character_wallet_journal_entry,
    create_skill_set,
    create_skill_set_group,
    create_skill_set_skill,
)
from memberaudit.tests.testdata.load_entities import load_entities
from memberaudit.tests.testdata.load_eveuniverse import load_eveuniverse
from memberaudit.tests.testdata.load_locations import load_locations
from memberaudit.tests.utils import create_memberaudit_character

MODELS_PATH = "memberaudit.models"
MANAGERS_PATH = "memberaudit.managers.character_sections_3"


class TestCharacterSkillSetCheckManager(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        cls.character = create_memberaudit_character(1001)
        cls.user = cls.character.eve_character.character_ownership.user
        # amarr carrier skill set
        cls.amarr_carrier_skill_type = EveType.objects.get(name="Amarr Carrier")
        cls.amarr_carrier_skill_set = create_skill_set()
        cls.amarr_carrier_skill_set_skill = create_skill_set_skill(
            skill_set=cls.amarr_carrier_skill_set,
            eve_type=cls.amarr_carrier_skill_type,
            required_level=3,
            recommended_level=5,
        )
        # caldari carrier skill set
        cls.caldari_carrier_skill_type = EveType.objects.get(name="Caldari Carrier")
        cls.caldari_carrier_skill_set = create_skill_set()
        cls.caldari_carrier_skill_set_skill = create_skill_set_skill(
            skill_set=cls.caldari_carrier_skill_set,
            eve_type=cls.caldari_carrier_skill_type,
            required_level=3,
            recommended_level=5,
        )

    def test_should_record_character_has_all_required_but_missing_recommended_skills(
        self,
    ):
        # given
        create_character_skill(self.character, eve_type=self.amarr_carrier_skill_type)
        # when
        self.character.update_skill_sets()
        # then
        obj: CharacterSkillSetCheck = self.character.skill_set_checks.filter(
            skill_set=self.amarr_carrier_skill_set
        ).first()
        self.assertTrue(obj.can_fly)
        self.assertEqual(obj.failed_required_skills.count(), 0)
        self.assertIn(
            self.amarr_carrier_skill_set_skill, obj.failed_recommended_skills.all()
        )
        obj: CharacterSkillSetCheck = self.character.skill_set_checks.filter(
            skill_set=self.caldari_carrier_skill_set
        ).first()
        self.assertFalse(obj.can_fly)

    def test_should_record_character_is_missing_all_skills(self):
        # given
        create_character_skill(
            self.character, eve_type=self.amarr_carrier_skill_type, active_skill_level=1
        )
        # when
        self.character.update_skill_sets()
        # then
        obj: CharacterSkillSetCheck = self.character.skill_set_checks.filter(
            skill_set=self.amarr_carrier_skill_set
        ).first()
        self.assertFalse(obj.can_fly)
        self.assertIn(
            self.amarr_carrier_skill_set_skill, obj.failed_required_skills.all()
        )
        self.assertIn(
            self.amarr_carrier_skill_set_skill, obj.failed_recommended_skills.all()
        )
        obj: CharacterSkillSetCheck = self.character.skill_set_checks.filter(
            skill_set=self.caldari_carrier_skill_set
        ).first()
        self.assertFalse(obj.can_fly)

    def test_should_update_existing_skill_set_check(self):
        # given
        create_character_skill(
            character=self.character,
            eve_type=self.amarr_carrier_skill_type,
            active_skill_level=5,
        )
        skill_set_check = create_character_skill_set_check(
            character=self.character, skill_set=self.amarr_carrier_skill_set
        )
        skill_set_check.failed_required_skills.add(self.amarr_carrier_skill_set_skill)
        skill_set_check.failed_recommended_skills.add(
            self.amarr_carrier_skill_set_skill
        )
        # when
        self.character.update_skill_sets()
        # then
        obj: CharacterSkillSetCheck = self.character.skill_set_checks.filter(
            skill_set=self.amarr_carrier_skill_set
        ).first()
        self.assertTrue(obj.can_fly)
        self.assertEqual(obj.failed_required_skills.count(), 0)
        self.assertEqual(obj.failed_recommended_skills.count(), 0)
        obj: CharacterSkillSetCheck = self.character.skill_set_checks.filter(
            skill_set=self.caldari_carrier_skill_set
        ).first()
        self.assertFalse(obj.can_fly)


class TestCharacterUpdateSkillSets(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        cls.character = create_memberaudit_character(1001)
        cls.amarr_carrier_skill_type = EveType.objects.get(id=24311)
        cls.caldari_carrier_skill_type = EveType.objects.get(id=24312)

    def test_has_all_skills(self):
        # given
        create_character_skill(
            character=self.character,
            eve_type=self.amarr_carrier_skill_type,
            active_skill_level=5,
            skillpoints_in_skill=10,
            trained_skill_level=5,
        )
        create_character_skill(
            character=self.character,
            eve_type=self.caldari_carrier_skill_type,
            active_skill_level=5,
            skillpoints_in_skill=10,
            trained_skill_level=5,
        )
        skill_set = create_skill_set()
        create_skill_set_skill(
            skill_set=skill_set,
            eve_type=self.amarr_carrier_skill_type,
            required_level=5,
        )
        create_skill_set_skill(
            skill_set=skill_set,
            eve_type=self.caldari_carrier_skill_type,
            required_level=3,
        )
        skill_set_group = create_skill_set_group()
        skill_set_group.skill_sets.add(skill_set)

        # when
        result = self.character.update_skill_sets()

        # then
        self.assertTrue(result.is_updated)
        self.assertEqual(self.character.skill_set_checks.count(), 1)
        first = self.character.skill_set_checks.first()
        self.assertEqual(first.skill_set.pk, skill_set.pk)
        self.assertEqual(first.failed_required_skills.count(), 0)

    def test_one_skill_below(self):
        # given
        create_character_skill(
            character=self.character,
            eve_type=self.amarr_carrier_skill_type,
            active_skill_level=5,
            skillpoints_in_skill=10,
            trained_skill_level=5,
        )
        create_character_skill(
            character=self.character,
            eve_type=self.caldari_carrier_skill_type,
            active_skill_level=2,
            skillpoints_in_skill=10,
            trained_skill_level=5,
        )
        skill_set = create_skill_set()
        create_skill_set_skill(
            skill_set=skill_set,
            eve_type=self.amarr_carrier_skill_type,
            required_level=5,
        )
        skill_2 = create_skill_set_skill(
            skill_set=skill_set,
            eve_type=self.caldari_carrier_skill_type,
            required_level=3,
        )
        skill_set_group = create_skill_set_group()
        skill_set_group.skill_sets.add(skill_set)

        # when
        result = self.character.update_skill_sets()

        # then
        self.assertTrue(result.is_updated)
        self.assertEqual(self.character.skill_set_checks.count(), 1)
        first = self.character.skill_set_checks.first()
        self.assertEqual(first.skill_set.pk, skill_set.pk)
        required_skill_pks = {obj.pk for obj in first.failed_required_skills.all()}
        self.assertEqual(required_skill_pks, {skill_2.pk})

    def test_misses_one_skill(self):
        # given
        create_character_skill(
            character=self.character,
            eve_type=self.amarr_carrier_skill_type,
            active_skill_level=5,
            skillpoints_in_skill=10,
            trained_skill_level=5,
        )
        skill_set = create_skill_set()
        create_skill_set_skill(
            skill_set=skill_set,
            eve_type=self.amarr_carrier_skill_type,
            required_level=5,
        )
        skill_2 = create_skill_set_skill(
            skill_set=skill_set,
            eve_type=self.caldari_carrier_skill_type,
            required_level=3,
        )
        skill_set_group = create_skill_set_group()
        skill_set_group.skill_sets.add(skill_set)

        # when
        result = self.character.update_skill_sets()

        # then
        self.assertTrue(result.is_updated)

        self.assertEqual(self.character.skill_set_checks.count(), 1)
        first = self.character.skill_set_checks.first()
        self.assertEqual(first.skill_set.pk, skill_set.pk)
        required_skill_pks = {obj.pk for obj in first.failed_required_skills.all()}
        self.assertSetEqual(required_skill_pks, {skill_2.pk})

    def test_passed_required_and_misses_recommended_skill(self):
        # given
        create_character_skill(
            character=self.character,
            eve_type=self.amarr_carrier_skill_type,
            active_skill_level=4,
            skillpoints_in_skill=10,
            trained_skill_level=4,
        )
        skill_set = create_skill_set()
        skill_1 = create_skill_set_skill(
            skill_set=skill_set,
            eve_type=self.amarr_carrier_skill_type,
            required_level=3,
            recommended_level=5,
        )

        # when
        result = self.character.update_skill_sets()

        # then
        self.assertTrue(result.is_updated)

        self.assertEqual(self.character.skill_set_checks.count(), 1)
        first = self.character.skill_set_checks.first()
        self.assertEqual(first.skill_set.pk, skill_set.pk)
        required_skill_pks = {obj.pk for obj in first.failed_required_skills.all()}
        self.assertSetEqual(required_skill_pks, set())
        recommended_skill_pks = {
            obj.pk for obj in first.failed_recommended_skills.all()
        }
        self.assertSetEqual(recommended_skill_pks, {skill_1.pk})

    def test_misses_recommended_skill_only(self):
        # given
        create_character_skill(
            character=self.character,
            eve_type=self.amarr_carrier_skill_type,
            active_skill_level=4,
            skillpoints_in_skill=10,
            trained_skill_level=4,
        )
        skill_set = create_skill_set()
        skill_1 = create_skill_set_skill(
            skill_set=skill_set,
            eve_type=self.amarr_carrier_skill_type,
            recommended_level=5,
        )

        # when
        result = self.character.update_skill_sets()

        # then
        self.assertTrue(result.is_updated)

        self.assertEqual(self.character.skill_set_checks.count(), 1)
        first = self.character.skill_set_checks.first()
        self.assertEqual(first.skill_set.pk, skill_set.pk)
        required_skill_pks = {obj.pk for obj in first.failed_required_skills.all()}
        self.assertSetEqual(required_skill_pks, set())
        recommended_skill_pks = {
            obj.pk for obj in first.failed_recommended_skills.all()
        }
        self.assertSetEqual(recommended_skill_pks, {skill_1.pk})

    def test_misses_all_skills(self):
        # given
        skill_set = create_skill_set()
        skill_1 = create_skill_set_skill(
            skill_set=skill_set,
            eve_type=self.amarr_carrier_skill_type,
            required_level=5,
        )
        skill_2 = create_skill_set_skill(
            skill_set=skill_set,
            eve_type=self.caldari_carrier_skill_type,
            required_level=3,
        )
        skill_set_group = create_skill_set_group()
        skill_set_group.skill_sets.add(skill_set)

        # when
        result = self.character.update_skill_sets()

        # then
        self.assertTrue(result.is_updated)

        self.assertEqual(self.character.skill_set_checks.count(), 1)
        first = self.character.skill_set_checks.first()
        self.assertEqual(first.skill_set.pk, skill_set.pk)
        skill_pks = {obj.pk for obj in first.failed_required_skills.all()}
        self.assertSetEqual(skill_pks, {skill_1.pk, skill_2.pk})

    def test_does_not_require_doctrine_definition(self):
        # given
        skill_set = create_skill_set()
        skill_1 = create_skill_set_skill(
            skill_set=skill_set,
            eve_type=self.amarr_carrier_skill_type,
            required_level=5,
        )
        skill_2 = create_skill_set_skill(
            skill_set=skill_set,
            eve_type=self.caldari_carrier_skill_type,
            required_level=3,
        )

        # when
        result = self.character.update_skill_sets()

        # then
        self.assertTrue(result.is_updated)

        self.assertEqual(self.character.skill_set_checks.count(), 1)
        first = self.character.skill_set_checks.first()
        self.assertEqual(first.skill_set.pk, skill_set.pk)
        skill_pks = {obj.pk for obj in first.failed_required_skills.all()}
        self.assertSetEqual(skill_pks, {skill_1.pk, skill_2.pk})

    def test_should_handle_no_skills(self):
        # when
        result = self.character.update_skill_sets()
        # then
        self.assertTrue(result.is_updated)


@patch(MANAGERS_PATH + ".esi")
class TestCharacterStandingManager(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        cls.character_1001 = create_memberaudit_character(1001)
        cls.character_1002 = create_memberaudit_character(1002)

    def test_can_create_from_scratch(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        # when
        CharacterStanding.objects.update_or_create_esi(self.character_1001)
        # then
        self.assertEqual(self.character_1001.standings.count(), 3)

        entry = self.character_1001.standings.get(eve_entity_id=1901)
        self.assertEqual(entry.standing, 0.1)

        entry = self.character_1001.standings.get(eve_entity_id=2901)
        self.assertEqual(entry.standing, 0)

        entry = self.character_1001.standings.get(eve_entity_id=500001)
        self.assertEqual(entry.standing, -1)

    def test_can_update_existing(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        npc_corp = EveEntity.objects.get(id=2901)
        create_character_standing(self.character_1001, npc_corp, standing=-5)
        # when
        CharacterStanding.objects.update_or_create_esi(self.character_1001)
        # then
        self.assertEqual(self.character_1001.standings.count(), 3)

        entry = self.character_1001.standings.get(eve_entity_id=1901)
        self.assertEqual(entry.standing, 0.1)

        entry = self.character_1001.standings.get(eve_entity_id=2901)
        self.assertEqual(entry.standing, 0)

        entry = self.character_1001.standings.get(eve_entity_id=500001)
        self.assertEqual(entry.standing, -1)

    def test_can_handle_no_standings(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        # when
        CharacterStanding.objects.update_or_create_esi(self.character_1002)
        # then
        self.assertEqual(self.character_1002.standings.count(), 0)

    def test_can_remove_obsolete_standings(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        obsolete_standing = create_character_standing(
            self.character_1001, EveEntity.objects.get(id=1101), standing=-5
        )
        # when
        CharacterStanding.objects.update_or_create_esi(self.character_1001)

        # then
        self.assertEqual(self.character_1001.standings.count(), 3)

        entry = self.character_1001.standings.get(eve_entity_id=1901)
        self.assertEqual(entry.standing, 0.1)

        entry = self.character_1001.standings.get(eve_entity_id=2901)
        self.assertEqual(entry.standing, 0)

        entry = self.character_1001.standings.get(eve_entity_id=500001)
        self.assertEqual(entry.standing, -1)

        self.assertFalse(
            self.character_1001.standings.filter(
                eve_entity_id=obsolete_standing.eve_entity.id
            ).exists()
        )


@patch(MANAGERS_PATH + ".esi")
class TestCharacterTitleManager(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        cls.character_1001 = create_memberaudit_character(1001)

    def test_should_add_new_title_from_scratch(self, mock_esi):
        # given
        endpoints = [
            EsiEndpoint(
                "Character",
                "get_characters_character_id_titles",
                "character_id",
                needs_token=True,
                data={"1001": [{"name": "Awesome Title", "title_id": 1}]},
            ),
        ]
        mock_esi.client = EsiClientStub.create_from_endpoints(endpoints)
        # when
        self.character_1001.update_titles()
        # then
        self.assertEqual(self.character_1001.titles.count(), 1)
        obj = self.character_1001.titles.first()
        self.assertEqual(obj.name, "Awesome Title")
        self.assertEqual(obj.title_id, 1)

    def test_should_update_existing_titles(self, mock_esi):
        # given
        endpoints = [
            EsiEndpoint(
                "Character",
                "get_characters_character_id_titles",
                "character_id",
                needs_token=True,
                data={"1001": [{"name": "Awesome Title", "title_id": 1}]},
            ),
        ]
        mock_esi.client = EsiClientStub.create_from_endpoints(endpoints)
        create_character_title(
            character=self.character_1001, name="Old title", title_id=1
        )
        # when
        self.character_1001.update_titles()
        # then
        obj = self.character_1001.titles.get(title_id=1)
        self.assertEqual(obj.name, "Awesome Title")

    def test_should_replace_existing_titles(self, mock_esi):
        # given
        endpoints = [
            EsiEndpoint(
                "Character",
                "get_characters_character_id_titles",
                "character_id",
                needs_token=True,
                data={"1001": [{"name": "Awesome Title", "title_id": 2}]},
            ),
        ]
        mock_esi.client = EsiClientStub.create_from_endpoints(endpoints)
        create_character_title(
            character=self.character_1001, name="Old title", title_id=1
        )
        # when
        self.character_1001.update_titles()
        # then
        self.assertEqual(self.character_1001.titles.count(), 1)
        obj = self.character_1001.titles.get(title_id=2)
        self.assertEqual(obj.name, "Awesome Title")

    def test_should_remove_existing_titles(self, mock_esi):
        # given
        endpoints = [
            EsiEndpoint(
                "Character",
                "get_characters_character_id_titles",
                "character_id",
                needs_token=True,
                data={"1001": []},
            ),
        ]
        mock_esi.client = EsiClientStub.create_from_endpoints(endpoints)
        create_character_title(
            character=self.character_1001, name="Old title", title_id=1
        )
        # when
        self.character_1001.update_titles()
        # then
        self.assertEqual(self.character_1001.titles.count(), 0)

    def test_should_remove_xml_from_titles_and_strip(self, mock_esi):
        create_character_title(
            character=self.character_1001, name="Old title", title_id=1
        )
        X = namedtuple("X", ["title", "want"])
        cases = [
            X("<color=0xFFee82ee> Awesome Title ", "Awesome Title"),
            X("<color=0xFFee82ee> Officer", "Officer"),
            X("<color=0xff649abb>Officer</color>", "Officer"),
        ]
        for tc in cases:
            with self.subTest(title=tc.title):
                endpoints = [
                    EsiEndpoint(
                        "Character",
                        "get_characters_character_id_titles",
                        "character_id",
                        needs_token=True,
                        data={"1001": [{"name": tc.title, "title_id": 1}]},
                    ),
                ]
                mock_esi.client = EsiClientStub.create_from_endpoints(endpoints)
                # when
                self.character_1001.update_titles()
                # then
                obj = self.character_1001.titles.get(title_id=1)
                self.assertEqual(obj.name, tc.want)


@patch(MANAGERS_PATH + ".esi")
class TestCharacterWalletBalanceManager(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities()
        cls.character_1001 = create_memberaudit_character(1001)

    def test_update_wallet_balance(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        # when
        CharacterWalletBalance.objects.update_or_create_esi(self.character_1001)
        # then
        self.assertEqual(self.character_1001.wallet_balance.total, 123456789)


@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
@patch(MANAGERS_PATH + ".esi")
class TestCharacterWalletJournalManager(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities()
        cls.character_1001 = create_memberaudit_character(1001)

    @patch(MANAGERS_PATH + ".data_retention_cutoff", lambda: None)
    def test_update_wallet_journal_1(self, mock_esi):
        """can create wallet journal entry from scratch"""
        mock_esi.client = esi_client_stub

        self.character_1001.update_wallet_journal()

        self.assertSetEqual(
            set(self.character_1001.wallet_journal.values_list("entry_id", flat=True)),
            {89, 91},
        )
        obj = self.character_1001.wallet_journal.get(entry_id=89)
        self.assertEqual(obj.amount, -100_000)
        self.assertEqual(float(obj.balance), 500_000.43)
        self.assertEqual(obj.context_id, 4)
        self.assertEqual(obj.context_id_type, obj.CONTEXT_ID_TYPE_CONTRACT_ID)
        self.assertEqual(obj.date, parse_datetime("2018-02-23T14:31:32Z"))
        self.assertEqual(obj.description, "Contract Deposit")
        self.assertEqual(obj.first_party.id, 2001)
        self.assertEqual(obj.reason, "just for fun")
        self.assertEqual(obj.ref_type, "contract_deposit")
        self.assertEqual(obj.second_party.id, 2002)

        obj = self.character_1001.wallet_journal.get(entry_id=91)
        self.assertEqual(
            obj.ref_type, "agent_mission_time_bonus_reward_corporation_tax"
        )

    @patch(MANAGERS_PATH + ".data_retention_cutoff", lambda: None)
    def test_update_wallet_journal_2(self, mock_esi):
        """can add entry to existing wallet journal"""
        mock_esi.client = esi_client_stub
        create_character_wallet_journal_entry(
            character=self.character_1001,
            entry_id=1,
            amount=1_000_000,
            balance=10_000_000,
            context_id_type=CharacterWalletJournalEntry.CONTEXT_ID_TYPE_UNDEFINED,
            date=now(),
            description="dummy",
            first_party=EveEntity.objects.get(id=1001),
            second_party=EveEntity.objects.get(id=1002),
        )

        self.character_1001.update_wallet_journal()

        self.assertSetEqual(
            set(self.character_1001.wallet_journal.values_list("entry_id", flat=True)),
            {1, 89, 91},
        )

        obj = self.character_1001.wallet_journal.get(entry_id=89)
        self.assertEqual(obj.amount, -100_000)
        self.assertEqual(float(obj.balance), 500_000.43)
        self.assertEqual(obj.context_id, 4)
        self.assertEqual(obj.context_id_type, obj.CONTEXT_ID_TYPE_CONTRACT_ID)
        self.assertEqual(obj.date, parse_datetime("2018-02-23T14:31:32Z"))
        self.assertEqual(obj.description, "Contract Deposit")
        self.assertEqual(obj.first_party.id, 2001)
        self.assertEqual(obj.ref_type, "contract_deposit")
        self.assertEqual(obj.second_party.id, 2002)

    @patch(MANAGERS_PATH + ".data_retention_cutoff", lambda: None)
    def test_update_wallet_journal_3(self, mock_esi):
        """does not update existing entries"""
        mock_esi.client = esi_client_stub
        create_character_wallet_journal_entry(
            character=self.character_1001,
            entry_id=89,
            amount=1_000_000,
            balance=10_000_000,
            context_id_type=CharacterWalletJournalEntry.CONTEXT_ID_TYPE_UNDEFINED,
            date=now(),
            description="dummy",
            first_party=EveEntity.objects.get(id=1001),
            second_party=EveEntity.objects.get(id=1002),
        )

        self.character_1001.update_wallet_journal()

        self.assertSetEqual(
            set(self.character_1001.wallet_journal.values_list("entry_id", flat=True)),
            {89, 91},
        )
        obj = self.character_1001.wallet_journal.get(entry_id=89)
        self.assertEqual(obj.amount, 1_000_000)
        self.assertEqual(float(obj.balance), 10_000_000)
        self.assertEqual(
            obj.context_id_type, CharacterWalletJournalEntry.CONTEXT_ID_TYPE_UNDEFINED
        )
        self.assertEqual(obj.description, "dummy")
        self.assertEqual(obj.first_party.id, 1001)
        self.assertEqual(obj.second_party.id, 1002)

    def test_update_wallet_journal_4(self, mock_esi):
        """When new wallet entry is older than retention limit, then do not store it"""
        mock_esi.client = esi_client_stub

        with patch(
            MANAGERS_PATH + ".data_retention_cutoff",
            lambda: dt.datetime(2018, 3, 11, 20, 5, tzinfo=dt.timezone.utc)
            - dt.timedelta(days=10),
        ):
            self.character_1001.update_wallet_journal()

        self.assertSetEqual(
            set(self.character_1001.wallet_journal.values_list("entry_id", flat=True)),
            {91},
        )

    def test_update_wallet_journal_5(self, mock_esi):
        """When wallet existing entry is older than retention limit, then delete it"""
        mock_esi.client = esi_client_stub
        create_character_wallet_journal_entry(
            character=self.character_1001,
            entry_id=55,
            amount=1_000_000,
            balance=10_000_000,
            context_id_type=CharacterWalletJournalEntry.CONTEXT_ID_TYPE_UNDEFINED,
            date=dt.datetime(2018, 2, 11, 20, 5, tzinfo=dt.timezone.utc),
            description="dummy",
            first_party=EveEntity.objects.get(id=1001),
            second_party=EveEntity.objects.get(id=1002),
        )

        with patch(
            MANAGERS_PATH + ".data_retention_cutoff",
            lambda: dt.datetime(2018, 3, 11, 20, 5, tzinfo=dt.timezone.utc)
            - dt.timedelta(days=20),
        ):
            self.character_1001.update_wallet_journal()

        self.assertSetEqual(
            set(self.character_1001.wallet_journal.values_list("entry_id", flat=True)),
            {89, 91},
        )


@patch(MANAGERS_PATH + ".esi")
class TestCharacterWalletTransactionManager(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        load_locations()
        cls.character_1001 = create_memberaudit_character(1001)

    def test_should_add_wallet_transactions_from_scratch(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        # when
        with patch(MANAGERS_PATH + ".data_retention_cutoff", lambda: None):
            CharacterWalletTransaction.objects.update_or_create_esi(self.character_1001)
        # then
        expected = set(
            self.character_1001.wallet_transactions.values_list(
                "transaction_id", flat=True
            )
        )
        self.assertSetEqual(expected, {42})
        obj = self.character_1001.wallet_transactions.get(transaction_id=42)
        self.assertEqual(obj.client, EveEntity.objects.get(id=1003))
        self.assertEqual(obj.date, parse_datetime("2016-10-24T09:00:00Z"))
        self.assertTrue(obj.is_buy)
        self.assertTrue(obj.is_personal)
        self.assertIsNone(obj.journal_ref)
        self.assertEqual(obj.location, Location.objects.get(id=60003760))
        self.assertEqual(obj.quantity, 3)
        self.assertEqual(obj.eve_type, EveType.objects.get(id=603))
        self.assertEqual(float(obj.unit_price), 450000.99)

    def test_should_add_wallet_transactions_from_scratch_with_journal_ref(
        self, mock_esi
    ):
        # given
        mock_esi.client = esi_client_stub
        journal_entry = create_character_wallet_journal_entry(
            character=self.character_1001,
            entry_id=67890,
            amount=450000.99,
            balance=10_000_000,
            context_id_type=CharacterWalletJournalEntry.CONTEXT_ID_TYPE_UNDEFINED,
            date=parse_datetime("2016-10-24T09:00:00Z"),
            description="dummy",
            first_party=EveEntity.objects.get(id=1001),
            second_party=EveEntity.objects.get(id=1003),
        )
        # when
        with patch(MANAGERS_PATH + ".data_retention_cutoff", lambda: None):
            CharacterWalletTransaction.objects.update_or_create_esi(self.character_1001)
        # then
        expected = set(
            self.character_1001.wallet_transactions.values_list(
                "transaction_id", flat=True
            )
        )

        self.assertSetEqual(expected, {42})
        obj = self.character_1001.wallet_transactions.get(transaction_id=42)
        self.assertEqual(obj.journal_ref, journal_entry)
