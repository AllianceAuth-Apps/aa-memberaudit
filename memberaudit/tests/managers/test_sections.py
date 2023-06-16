import datetime as dt
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils.dateparse import parse_datetime
from django.utils.timezone import now
from eveuniverse.models import (
    EveEntity,
    EveMarketPrice,
    EvePlanet,
    EveSolarSystem,
    EveType,
)

from app_utils.esi_testing import EsiClientStub, EsiEndpoint, build_http_error
from app_utils.testing import NoSocketsTestCase

from memberaudit.core.xml_converter import eve_xml_to_html
from memberaudit.models import (
    Character,
    CharacterAsset,
    CharacterContact,
    CharacterContactLabel,
    CharacterContract,
    CharacterContractBid,
    CharacterCorporationHistory,
    CharacterDetails,
    CharacterFwStats,
    CharacterJumpClone,
    CharacterLocation,
    CharacterLoyaltyEntry,
    CharacterMailLabel,
    CharacterPlanet,
    CharacterSkill,
    CharacterWalletJournalEntry,
    Location,
)

from ..testdata.esi_client_stub import esi_client_stub
from ..testdata.factories import (
    create_character_contract,
    create_character_contract_bid,
    create_character_mining_ledger_entry,
    create_character_planet,
)
from ..testdata.load_entities import load_entities
from ..testdata.load_eveuniverse import load_eveuniverse
from ..testdata.load_locations import load_locations
from ..utils import CharacterUpdateTestDataMixin, create_memberaudit_character

MODULE_PATH = "memberaudit.managers.sections"


class TestCharacterAssetManager(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        load_locations()
        cls.character = create_memberaudit_character(1001)
        cls.jita_44 = Location.objects.get(id=60003760)
        cls.merlin = EveType.objects.get(id=603)

    def test_can_calculate_pricing(self):
        CharacterAsset.objects.create(
            character=self.character,
            item_id=1100000000666,
            location=self.jita_44,
            eve_type=self.merlin,
            is_singleton=False,
            quantity=5,
        )
        EveMarketPrice.objects.create(eve_type=self.merlin, average_price=500000)
        asset = CharacterAsset.objects.annotate_pricing().first()
        self.assertEqual(asset.price, 500000)
        self.assertEqual(asset.total, 2500000)

    def test_does_not_price_blueprint_copies(self):
        CharacterAsset.objects.create(
            character=self.character,
            item_id=1100000000666,
            location=self.jita_44,
            eve_type=self.merlin,
            is_blueprint_copy=True,
            is_singleton=False,
            quantity=1,
        )
        EveMarketPrice.objects.create(eve_type=self.merlin, average_price=500000)
        asset = CharacterAsset.objects.annotate_pricing().first()
        self.assertIsNone(asset.price)
        self.assertIsNone(asset.total)


class TestCharacterUpdateBase(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        load_locations()
        cls.character_1001 = create_memberaudit_character(1001)
        cls.character_1002 = create_memberaudit_character(1002)
        cls.corporation_2001 = EveEntity.objects.get(id=2001)
        cls.corporation_2002 = EveEntity.objects.get(id=2002)
        cls.token = (
            cls.character_1001.eve_character.character_ownership.user.token_set.first()
        )
        cls.jita = EveSolarSystem.objects.get(id=30000142)
        cls.jita_44 = Location.objects.get(id=60003760)
        cls.amamake = EveSolarSystem.objects.get(id=30002537)
        cls.structure_1 = Location.objects.get(id=1000000000001)


class TestCharacterContactLabelManager(TestCharacterUpdateBase):
    def test_should_do_nothing(self):
        # when
        CharacterContactLabel.objects._update_or_create_objs(
            character=self.character_1001, labels=[]
        )
        # then
        self.assertEqual(CharacterContactLabel.objects.count(), 0)


@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
@patch(MODULE_PATH + ".esi")
class TestCharacterUpdateContacts(CharacterUpdateTestDataMixin, NoSocketsTestCase):
    def test_update_contact_labels_1(self, mock_esi):
        """can create new contact labels from scratch"""
        mock_esi.client = esi_client_stub

        self.character_1001.update_contact_labels()
        self.assertEqual(self.character_1001.contact_labels.count(), 2)

        label = self.character_1001.contact_labels.get(label_id=1)
        self.assertEqual(label.name, "friend")

        label = self.character_1001.contact_labels.get(label_id=2)
        self.assertEqual(label.name, "pirate")

    def test_update_contact_labels_2(self, mock_esi):
        """can remove obsolete labels"""
        mock_esi.client = esi_client_stub
        CharacterContactLabel.objects.create(
            character=self.character_1001, label_id=99, name="Obsolete"
        )

        self.character_1001.update_contact_labels()
        self.assertEqual(
            {x.label_id for x in self.character_1001.contact_labels.all()}, {1, 2}
        )

    def test_update_contact_labels_3(self, mock_esi):
        """can update existing labels"""
        mock_esi.client = esi_client_stub
        CharacterContactLabel.objects.create(
            character=self.character_1001, label_id=1, name="Obsolete"
        )

        self.character_1001.update_contact_labels()
        self.assertEqual(
            {x.label_id for x in self.character_1001.contact_labels.all()}, {1, 2}
        )

        label = self.character_1001.contact_labels.get(label_id=1)
        self.assertEqual(label.name, "friend")

    def test_update_contact_labels_4(self, mock_esi):
        """when data from ESI has not changed, then skip update"""
        mock_esi.client = esi_client_stub

        self.character_1001.update_contact_labels()
        label = self.character_1001.contact_labels.get(label_id=1)
        label.name = "foe"
        label.save()

        self.character_1001.update_contact_labels()

        self.assertEqual(self.character_1001.contact_labels.count(), 2)
        label = self.character_1001.contact_labels.get(label_id=1)
        self.assertEqual(label.name, "foe")

    def test_update_contact_labels_5(self, mock_esi):
        """when data from ESI has not changed and update is forced, then do update"""
        mock_esi.client = esi_client_stub

        self.character_1001.update_contact_labels()
        label = self.character_1001.contact_labels.get(label_id=1)
        label.name = "foe"
        label.save()

        self.character_1001.update_contact_labels(force_update=True)

        self.assertEqual(self.character_1001.contact_labels.count(), 2)
        label = self.character_1001.contact_labels.get(label_id=1)
        self.assertEqual(label.name, "friend")

    def test_update_contacts_1(self, mock_esi):
        """can create contacts"""
        mock_esi.client = esi_client_stub
        CharacterContactLabel.objects.create(
            character=self.character_1001, label_id=1, name="friend"
        )
        CharacterContactLabel.objects.create(
            character=self.character_1001, label_id=2, name="pirate"
        )

        self.character_1001.update_contacts()

        self.assertEqual(self.character_1001.contacts.count(), 2)

        obj = self.character_1001.contacts.get(eve_entity_id=1101)
        self.assertEqual(obj.eve_entity.category, EveEntity.CATEGORY_CHARACTER)
        self.assertFalse(obj.is_blocked)
        self.assertTrue(obj.is_watched)
        self.assertEqual(obj.standing, -10)
        self.assertEqual({x.label_id for x in obj.labels.all()}, {2})

        obj = self.character_1001.contacts.get(eve_entity_id=2002)
        self.assertEqual(obj.eve_entity.category, EveEntity.CATEGORY_CORPORATION)
        self.assertFalse(obj.is_blocked)
        self.assertFalse(obj.is_watched)
        self.assertEqual(obj.standing, 5)
        self.assertEqual(obj.labels.count(), 0)

    def test_update_contacts_2(self, mock_esi):
        """can remove obsolete contacts"""
        mock_esi.client = esi_client_stub
        CharacterContactLabel.objects.create(
            character=self.character_1001, label_id=1, name="friend"
        )
        CharacterContactLabel.objects.create(
            character=self.character_1001, label_id=2, name="pirate"
        )
        CharacterContact.objects.create(
            character=self.character_1001,
            eve_entity=EveEntity.objects.get(id=3101),
            standing=-5,
        )

        self.character_1001.update_contacts()

        self.assertEqual(
            {x.eve_entity_id for x in self.character_1001.contacts.all()}, {1101, 2002}
        )

    def test_update_contacts_3(self, mock_esi):
        """can update existing contacts"""
        mock_esi.client = esi_client_stub
        CharacterContactLabel.objects.create(
            character=self.character_1001, label_id=2, name="pirate"
        )
        my_label = CharacterContactLabel.objects.create(
            character=self.character_1001, label_id=1, name="Dummy"
        )
        my_contact = CharacterContact.objects.create(
            character=self.character_1001,
            eve_entity=EveEntity.objects.get(id=1101),
            is_blocked=True,
            is_watched=False,
            standing=-5,
        )
        my_contact.labels.add(my_label)

        self.character_1001.update_contacts()

        obj = self.character_1001.contacts.get(eve_entity_id=1101)
        self.assertEqual(obj.eve_entity.category, EveEntity.CATEGORY_CHARACTER)
        self.assertFalse(obj.is_blocked)
        self.assertTrue(obj.is_watched)
        self.assertEqual(obj.standing, -10)
        self.assertEqual({x.label_id for x in obj.labels.all()}, {2})

    def test_update_contacts_4(self, mock_esi):
        """when ESI data has not changed, then skip update"""
        mock_esi.client = esi_client_stub
        CharacterContactLabel.objects.create(
            character=self.character_1001, label_id=1, name="friend"
        )
        CharacterContactLabel.objects.create(
            character=self.character_1001, label_id=2, name="pirate"
        )

        self.character_1001.update_contacts()
        obj = self.character_1001.contacts.get(eve_entity_id=1101)
        obj.is_watched = False
        obj.save()

        self.character_1001.update_contacts()

        obj = self.character_1001.contacts.get(eve_entity_id=1101)
        self.assertFalse(obj.is_watched)

    def test_update_contacts_5(self, mock_esi):
        """when ESI data has not changed and update is forced, then update"""
        mock_esi.client = esi_client_stub
        CharacterContactLabel.objects.create(
            character=self.character_1001, label_id=1, name="friend"
        )
        CharacterContactLabel.objects.create(
            character=self.character_1001, label_id=2, name="pirate"
        )

        self.character_1001.update_contacts()
        obj = self.character_1001.contacts.get(eve_entity_id=1101)
        obj.is_watched = False
        obj.save()

        self.character_1001.update_contacts(force_update=True)

        obj = self.character_1001.contacts.get(eve_entity_id=1101)
        self.assertTrue(obj.is_watched)


class TestCharacterContractBidManager(TestCharacterUpdateBase):
    def test_should_do_nothing_when_there_are_no_bids(self):
        # given
        contract = create_character_contract(
            character=self.character_1001, contract_type=CharacterContract.TYPE_AUCTION
        )
        # when
        CharacterContractBid.objects.update_for_contract(
            contract=contract, bids_list=dict()
        )
        # then
        self.assertEqual(CharacterContractBid.objects.count(), 0)

    def test_should_do_nothing_when_there_are_no_new_bids(self):
        # given
        contract = create_character_contract(
            character=self.character_1001, contract_type=CharacterContract.TYPE_AUCTION
        )
        bidder = EveEntity.objects.get(id=1002)
        bid = create_character_contract_bid(contract=contract, bidder=bidder)
        bids_list = {
            bid.bid_id: {
                "amount": bid.amount,
                "bid_id": bid.bid_id,
                "bidder_id": bidder.id,
                "date_bid": bid.date_bid,
            }
        }
        # when
        CharacterContractBid.objects.update_for_contract(
            contract=contract, bids_list=bids_list
        )
        # then
        self.assertEqual(CharacterContractBid.objects.count(), 1)


@patch(MODULE_PATH + ".esi")
class TestCharacterCorporationHistoryManager(
    CharacterUpdateTestDataMixin, NoSocketsTestCase
):
    def test_can_create_from_scratch(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        # when
        CharacterCorporationHistory.objects.update_or_create_esi(self.character_1001)
        # then
        self.assertEqual(self.character_1001.corporation_history.count(), 2)

        obj = self.character_1001.corporation_history.get(record_id=500)
        self.assertEqual(obj.corporation, self.corporation_2001)
        self.assertTrue(obj.is_deleted)
        self.assertEqual(obj.start_date, parse_datetime("2016-06-26T20:00:00Z"))

        obj = self.character_1001.corporation_history.get(record_id=501)
        self.assertEqual(obj.corporation, self.corporation_2002)
        self.assertFalse(obj.is_deleted)
        self.assertEqual(obj.start_date, parse_datetime("2016-07-26T20:00:00Z"))

    def test_can_update_existing_history(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        self.character_1001.corporation_history.create(
            record_id=500, corporation=self.corporation_2002, start_date=now()
        )
        # when
        CharacterCorporationHistory.objects.update_or_create_esi(self.character_1001)
        # then
        self.assertEqual(self.character_1001.corporation_history.count(), 2)

        obj = self.character_1001.corporation_history.get(record_id=500)
        self.assertEqual(obj.corporation, self.corporation_2001)
        self.assertTrue(obj.is_deleted)
        self.assertEqual(obj.start_date, parse_datetime("2016-06-26T20:00:00Z"))

    def test_should_skip_update_when_data_on_ESI_has_not_changed(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        self.character_1001.update_corporation_history()
        obj = self.character_1001.corporation_history.get(record_id=500)
        obj.corporation = self.corporation_2002
        obj.save()
        # when
        CharacterCorporationHistory.objects.update_or_create_esi(self.character_1001)
        # then
        obj = self.character_1001.corporation_history.get(record_id=500)
        self.assertEqual(obj.corporation, self.corporation_2002)

    def test_should_update_always_when_forced(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        self.character_1001.update_corporation_history()
        obj = self.character_1001.corporation_history.get(record_id=500)
        obj.corporation = self.corporation_2002
        obj.save()
        # when
        CharacterCorporationHistory.objects.update_or_create_esi(
            self.character_1001, force_update=True
        )
        # then
        obj = self.character_1001.corporation_history.get(record_id=500)
        self.assertEqual(obj.corporation, self.corporation_2001)

    def test_should_handle_empty_response(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        # when
        CharacterCorporationHistory.objects.update_or_create_esi(self.character_1002)
        # then
        self.assertEqual(self.character_1001.corporation_history.count(), 0)


@patch(MODULE_PATH + ".eve_xml_to_html")
@patch(MODULE_PATH + ".esi")
class TestCharacterDetailManager(CharacterUpdateTestDataMixin, NoSocketsTestCase):
    def test_can_create_from_scratch(self, mock_esi, mock_eve_xml_to_html):
        # given
        mock_esi.client = esi_client_stub
        mock_eve_xml_to_html.side_effect = lambda x: eve_xml_to_html(x)
        # when
        CharacterDetails.objects.update_or_create_esi(self.character_1001)
        # then
        self.assertEqual(self.character_1001.details.eve_ancestry.id, 11)
        self.assertEqual(
            self.character_1001.details.birthday, parse_datetime("2015-03-24T11:37:00Z")
        )
        self.assertEqual(self.character_1001.details.eve_bloodline_id, 1)
        self.assertEqual(self.character_1001.details.corporation, self.corporation_2001)
        self.assertEqual(self.character_1001.details.description, "Scio me nihil scire")
        self.assertEqual(
            self.character_1001.details.gender, CharacterDetails.GENDER_MALE
        )
        self.assertEqual(self.character_1001.details.name, "Bruce Wayne")
        self.assertEqual(self.character_1001.details.eve_race.id, 1)
        self.assertEqual(
            self.character_1001.details.title, "All round pretty awesome guy"
        )
        self.assertTrue(mock_eve_xml_to_html.called)

    def test_can_update_existing_data(self, mock_esi, mock_eve_xml_to_html):
        # given
        mock_esi.client = esi_client_stub
        mock_eve_xml_to_html.side_effect = lambda x: eve_xml_to_html(x)
        CharacterDetails.objects.create(
            character=self.character_1001,
            birthday=now(),
            corporation=self.corporation_2002,
            description="Change me",
            eve_bloodline_id=1,
            eve_race_id=1,
            name="Change me also",
        )
        # when
        self.character_1001.update_character_details()
        # then
        self.character_1001.details.refresh_from_db()
        self.assertEqual(self.character_1001.details.eve_ancestry_id, 11)
        self.assertEqual(
            self.character_1001.details.birthday, parse_datetime("2015-03-24T11:37:00Z")
        )
        self.assertEqual(self.character_1001.details.eve_bloodline_id, 1)
        self.assertEqual(self.character_1001.details.corporation, self.corporation_2001)
        self.assertEqual(self.character_1001.details.description, "Scio me nihil scire")
        self.assertEqual(
            self.character_1001.details.gender, CharacterDetails.GENDER_MALE
        )
        self.assertEqual(self.character_1001.details.name, "Bruce Wayne")
        self.assertEqual(self.character_1001.details.eve_race.id, 1)
        self.assertEqual(
            self.character_1001.details.title, "All round pretty awesome guy"
        )
        self.assertTrue(mock_eve_xml_to_html.called)

    def test_skip_update_1(self, mock_esi, mock_eve_xml_to_html):
        """when data from ESI has not changed, then skip update"""
        # given
        mock_esi.client = esi_client_stub
        mock_eve_xml_to_html.side_effect = lambda x: eve_xml_to_html(x)
        self.character_1001.update_character_details()
        self.character_1001.details.name = "John Doe"
        self.character_1001.details.save()
        # when
        self.character_1001.update_character_details()
        # then
        self.character_1001.details.refresh_from_db()
        self.assertEqual(self.character_1001.details.name, "John Doe")

    def test_skip_update_2(self, mock_esi, mock_eve_xml_to_html):
        """when data from ESI has not changed and update is forced, then do update"""
        # given
        mock_esi.client = esi_client_stub
        mock_eve_xml_to_html.side_effect = lambda x: eve_xml_to_html(x)
        self.character_1001.update_character_details()
        self.character_1001.details.name = "John Doe"
        self.character_1001.details.save()
        # when
        self.character_1001.update_character_details(force_update=True)
        # then
        self.character_1001.details.refresh_from_db()
        self.assertEqual(self.character_1001.details.name, "Bruce Wayne")

    def test_can_handle_u_bug_1(self, mock_esi, mock_eve_xml_to_html):
        # given
        mock_esi.client = esi_client_stub
        mock_eve_xml_to_html.side_effect = lambda x: eve_xml_to_html(x)
        # when
        self.character_1002.update_character_details()
        # then
        self.assertNotEqual(self.character_1002.details.description[:2], "u'")

    def test_can_handle_u_bug_2(self, mock_esi, mock_eve_xml_to_html):
        # given
        mock_esi.client = esi_client_stub
        mock_eve_xml_to_html.side_effect = lambda x: eve_xml_to_html(x)
        character = create_memberaudit_character(1003)
        # when
        character.update_character_details()
        # then
        self.assertNotEqual(character.details.description[:2], "u'")

    def test_can_handle_u_bug_3(self, mock_esi, mock_eve_xml_to_html):
        # given
        mock_esi.client = esi_client_stub
        mock_eve_xml_to_html.side_effect = lambda x: eve_xml_to_html(x)
        character = create_memberaudit_character(1101)
        # when
        character.update_character_details()
        # then
        self.assertNotEqual(character.details.description[:2], "u'")

    # @patch(MANAGERS_PATH + ".sections.get_or_create_esi_or_none")
    # def test_esi_ancestry_bug(
    #     self, mock_get_or_create_esi_or_none, mock_esi, mock_eve_xml_to_html
    # ):
    #     """when esi ancestry endpoint returns http error then ignore it and carry on"""

    #     def my_get_or_create_esi_or_none(prop_name: str, dct: dict, Model: type):
    #         if issubclass(Model, EveAncestry):
    #             raise HTTPInternalServerError(
    #                 response=BravadoResponseStub(500, "Test exception")
    #             )
    #         return get_or_create_esi_or_none(prop_name=prop_name, dct=dct, Model=Model)

    #     mock_esi.client = esi_client_stub
    #     mock_eve_xml_to_html.side_effect = lambda x: eve_xml_to_html(x)
    #     mock_get_or_create_esi_or_none.side_effect = my_get_or_create_esi_or_none

    #     self.character_1001.update_character_details()
    #     self.assertIsNone(self.character_1001.details.eve_ancestry)
    #     self.assertEqual(
    #         self.character_1001.details.birthday, parse_datetime("2015-03-24T11:37:00Z")
    #     )
    #     self.assertEqual(self.character_1001.details.eve_bloodline_id, 1)
    #     self.assertEqual(self.character_1001.details.corporation, self.corporation_2001)
    #     self.assertEqual(self.character_1001.details.description, "Scio me nihil scire")
    #     self.assertEqual(
    #         self.character_1001.details.gender, CharacterDetails.GENDER_MALE
    #     )
    #     self.assertEqual(self.character_1001.details.name, "Bruce Wayne")
    #     self.assertEqual(self.character_1001.details.eve_race.id, 1)
    #     self.assertEqual(
    #         self.character_1001.details.title, "All round pretty awesome guy"
    #     )
    #     self.assertTrue(mock_eve_xml_to_html.called)


@patch(MODULE_PATH + ".esi")
class TestCharacterFwStatsManager(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        cls.character_1001 = create_memberaudit_character(1001)
        cls.endpoints = [
            EsiEndpoint(
                "Faction_Warfare",
                "get_characters_character_id_fw_stats",
                "character_id",
                needs_token=True,
                data={
                    "1001": {
                        "current_rank": 3,
                        "enlisted_on": dt.datetime(
                            2023, 3, 21, 15, 0, tzinfo=dt.timezone.utc
                        ),
                        "faction_id": 500001,
                        "highest_rank": 4,
                        "kills": {
                            "last_week": 893,
                            "total": 684350,
                            "yesterday": 136,
                        },
                        "victory_points": {
                            "last_week": 102640,
                            "total": 52658260,
                            "yesterday": 15980,
                        },
                    }
                },
            ),
        ]
        cls.esi_client_stub = EsiClientStub.create_from_endpoints(cls.endpoints)

    def test_should_add_new_entry_from_scratch(self, mock_esi):
        # given
        mock_esi.client = self.esi_client_stub
        # when
        with patch(MODULE_PATH + ".data_retention_cutoff", lambda: None):
            CharacterFwStats.objects.update_or_create_esi(self.character_1001)
        # then
        obj: CharacterFwStats = self.character_1001.fw_stats
        self.assertEqual(obj.current_rank, 3)
        self.assertEqual(
            obj.enlisted_on, dt.datetime(2023, 3, 21, 15, 0, tzinfo=dt.timezone.utc)
        )
        self.assertEqual(obj.faction_id, 500001)
        self.assertEqual(obj.highest_rank, 4)
        self.assertEqual(obj.kills_last_week, 893)
        self.assertEqual(obj.kills_total, 684350)
        self.assertEqual(obj.kills_yesterday, 136)
        self.assertEqual(obj.victory_points_last_week, 102640)
        self.assertEqual(obj.victory_points_total, 52658260)
        self.assertEqual(obj.victory_points_yesterday, 15980)

    def test_should_update_existing_entries(self, mock_esi):
        # given
        mock_esi.client = self.esi_client_stub
        CharacterFwStats.objects.create(
            character=self.character_1001,
            kills_last_week=0,
            kills_total=0,
            kills_yesterday=0,
            victory_points_last_week=0,
            victory_points_total=0,
            victory_points_yesterday=0,
        )
        # when
        with patch(MODULE_PATH + ".data_retention_cutoff", lambda: None):
            CharacterFwStats.objects.update_or_create_esi(self.character_1001)
        # then
        self.character_1001.refresh_from_db()
        obj: CharacterFwStats = self.character_1001.fw_stats
        self.assertEqual(obj.current_rank, 3)
        self.assertEqual(
            obj.enlisted_on, dt.datetime(2023, 3, 21, 15, 0, tzinfo=dt.timezone.utc)
        )
        self.assertEqual(obj.faction_id, 500001)
        self.assertEqual(obj.highest_rank, 4)
        self.assertEqual(obj.kills_last_week, 893)
        self.assertEqual(obj.kills_total, 684350)
        self.assertEqual(obj.kills_yesterday, 136)
        self.assertEqual(obj.victory_points_last_week, 102640)
        self.assertEqual(obj.victory_points_total, 52658260)
        self.assertEqual(obj.victory_points_yesterday, 15980)

    def test_should_add_new_entry_from_scratch_for_unlisted(self, mock_esi):
        # given
        endpoints = [
            EsiEndpoint(
                "Faction_Warfare",
                "get_characters_character_id_fw_stats",
                "character_id",
                needs_token=True,
                data={
                    "1001": {
                        "kills": {
                            "last_week": 0,
                            "total": 684350,
                            "yesterday": 0,
                        },
                        "victory_points": {
                            "last_week": 0,
                            "total": 52658260,
                            "yesterday": 0,
                        },
                    }
                },
            ),
        ]
        mock_esi.client = EsiClientStub.create_from_endpoints(endpoints)
        # when
        with patch(MODULE_PATH + ".data_retention_cutoff", lambda: None):
            CharacterFwStats.objects.update_or_create_esi(self.character_1001)
        # then
        obj: CharacterFwStats = self.character_1001.fw_stats
        self.assertIsNone(obj.current_rank)
        self.assertIsNone(obj.enlisted_on)
        self.assertIsNone(obj.faction)
        self.assertIsNone(obj.highest_rank)
        self.assertEqual(obj.kills_last_week, 0)
        self.assertEqual(obj.kills_total, 684350)
        self.assertEqual(obj.kills_yesterday, 0)
        self.assertEqual(obj.victory_points_last_week, 0)
        self.assertEqual(obj.victory_points_total, 52658260)
        self.assertEqual(obj.victory_points_yesterday, 0)

    # FIXME: Test stopped working after moving it over
    # @patch(MODULE_PATH + ".CharacterFwStats.objects.update_for_character")
    # def test_should_not_update_when_not_changed(
    #     self, mock_update_for_character, mock_esi
    # ):
    #     # given
    #     mock_esi.client = self.esi_client_stub
    #     # when
    #     with patch(
    #         MODULE_PATH + ".Character.has_section_changed"
    #     ) as mock_has_section_changed:
    #         mock_has_section_changed.return_value = False
    #         CharacterFwStats.objects.update_or_create_esi(self.character_1001)
    #     # then
    #     self.assertFalse(mock_update_for_character.called)


@patch(MODULE_PATH + ".esi")
class TestCharacterImplantsManager(CharacterUpdateTestDataMixin, NoSocketsTestCase):
    def test_update_implants_1(self, mock_esi):
        """can create implants from scratch"""
        mock_esi.client = esi_client_stub

        self.character_1001.update_implants()
        self.assertEqual(self.character_1001.implants.count(), 3)
        self.assertSetEqual(
            set(self.character_1001.implants.values_list("eve_type_id", flat=True)),
            {19540, 19551, 19553},
        )

    def test_update_implants_2(self, mock_esi):
        """can deal with no implants returned from ESI"""
        mock_esi.client = esi_client_stub

        self.character_1002.update_implants()
        self.assertEqual(self.character_1002.implants.count(), 0)

    def test_update_implants_3(self, mock_esi):
        """when data from ESI has not changed, then skip update"""
        mock_esi.client = esi_client_stub

        self.character_1001.update_implants()
        self.character_1001.implants.get(eve_type_id=19540).delete()

        self.character_1001.update_implants()
        self.assertFalse(
            self.character_1001.implants.filter(eve_type_id=19540).exists()
        )

    def test_update_implants_4(self, mock_esi):
        """when data from ESI has not changed and update is forced, then do update"""
        mock_esi.client = esi_client_stub

        self.character_1001.update_implants()
        self.character_1001.implants.get(eve_type_id=19540).delete()

        self.character_1001.update_implants(force_update=True)
        self.assertTrue(self.character_1001.implants.filter(eve_type_id=19540).exists())


@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
@patch(MODULE_PATH + ".esi")
class TestCharacterUpdateJumpClones(CharacterUpdateTestDataMixin, NoSocketsTestCase):
    def test_can_update_with_implants(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        # when
        CharacterJumpClone.objects.update_or_create_esi(self.character_1001)
        # then
        self.assertEqual(self.character_1001.jump_clones.count(), 1)
        obj = self.character_1001.jump_clones.get(jump_clone_id=12345)
        self.assertEqual(obj.location, self.jita_44)
        self.assertEqual(
            {x for x in obj.implants.values_list("eve_type", flat=True)},
            {19540, 19551, 19553},
        )

    def test_can_update_without_implants(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        # when
        CharacterJumpClone.objects.update_or_create_esi(self.character_1002)
        # then
        self.assertEqual(self.character_1002.jump_clones.count(), 1)
        obj = self.character_1002.jump_clones.get(jump_clone_id=12345)
        self.assertEqual(obj.location, self.jita_44)
        self.assertEqual(obj.implants.count(), 0)

    def test_skip_update_when_no_new_data(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        CharacterJumpClone.objects.update_or_create_esi(self.character_1001)
        obj = self.character_1001.jump_clones.get(jump_clone_id=12345)
        obj.location = self.structure_1
        obj.save()
        # when
        CharacterJumpClone.objects.update_or_create_esi(self.character_1001)
        # then
        obj = self.character_1001.jump_clones.get(jump_clone_id=12345)
        self.assertEqual(obj.location, self.structure_1)

    def test_update_always_when_forced(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        CharacterJumpClone.objects.update_or_create_esi(self.character_1001)
        obj = self.character_1001.jump_clones.get(jump_clone_id=12345)
        obj.location = self.structure_1
        obj.save()
        # when
        CharacterJumpClone.objects.update_or_create_esi(
            self.character_1001, force_update=True
        )
        # then
        obj = self.character_1001.jump_clones.get(jump_clone_id=12345)
        self.assertEqual(obj.location, self.jita_44)


@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
@patch(MODULE_PATH + ".esi")
class TestCharacterLocationManager(CharacterUpdateTestDataMixin, NoSocketsTestCase):
    def test_update_location_1(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        # when
        CharacterLocation.objects.update_or_create_esi(self.character_1001)
        # then
        self.assertEqual(self.character_1001.location.eve_solar_system, self.jita)
        self.assertEqual(self.character_1001.location.location, self.jita_44)

    def test_update_location_2(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        # when
        CharacterLocation.objects.update_or_create_esi(self.character_1002)
        # then
        self.assertEqual(self.character_1002.location.eve_solar_system, self.amamake)
        self.assertEqual(self.character_1002.location.location, self.structure_1)


@patch(MODULE_PATH + ".esi")
class TestCharacterLoyaltyManager(CharacterUpdateTestDataMixin, NoSocketsTestCase):
    def test_can_create_from_scratch(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        # when
        CharacterLoyaltyEntry.objects.update_or_create_esi(self.character_1001)
        # then
        self.assertEqual(self.character_1001.loyalty_entries.count(), 1)
        obj = self.character_1001.loyalty_entries.get(corporation_id=2002)
        self.assertEqual(obj.loyalty_points, 100)

    def test_can_update_existing_entries(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        self.character_1001.loyalty_entries.create(
            corporation=self.corporation_2001, loyalty_points=200
        )
        # when
        CharacterLoyaltyEntry.objects.update_or_create_esi(self.character_1001)
        # then
        self.assertEqual(self.character_1001.loyalty_entries.count(), 1)
        obj = self.character_1001.loyalty_entries.get(corporation=self.corporation_2002)
        self.assertEqual(obj.loyalty_points, 100)

    def test_should_skip_update_when_no_change(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        CharacterLoyaltyEntry.objects.update_or_create_esi(self.character_1001)
        obj = self.character_1001.loyalty_entries.get(corporation=self.corporation_2002)
        obj.loyalty_points = 200
        obj.save()
        # when
        CharacterLoyaltyEntry.objects.update_or_create_esi(self.character_1001)
        # then
        obj = self.character_1001.loyalty_entries.get(corporation=self.corporation_2002)
        self.assertEqual(obj.loyalty_points, 200)

    def test_should_always_update_when_forced(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        CharacterLoyaltyEntry.objects.update_or_create_esi(self.character_1001)
        obj = self.character_1001.loyalty_entries.get(corporation=self.corporation_2002)
        obj.loyalty_points = 200
        obj.save()
        # when
        CharacterLoyaltyEntry.objects.update_or_create_esi(
            self.character_1001, force_update=True
        )
        # then
        obj = self.character_1001.loyalty_entries.get(corporation=self.corporation_2002)
        self.assertEqual(obj.loyalty_points, 100)

    def test_should_thread_http_500_as_empty_loyalty_list(self, mock_esi):
        # given
        exception = build_http_error(
            500, '{"error":"Unhandled internal error encountered!"}'
        )
        mock_esi.client.Loyalty.get_characters_character_id_loyalty_points.side_effect = (
            exception
        )
        self.character_1001.loyalty_entries.create(
            corporation=self.corporation_2001, loyalty_points=100
        )
        # when
        CharacterLoyaltyEntry.objects.update_or_create_esi(self.character_1001)
        # then
        self.assertEqual(self.character_1001.loyalty_entries.count(), 1)
        obj = self.character_1001.loyalty_entries.get(corporation=self.corporation_2001)
        self.assertEqual(obj.loyalty_points, 100)


class TestCharacterMailLabelManager(TestCharacterUpdateBase):
    def test_normal(self):
        label_1 = CharacterMailLabel.objects.create(
            character=self.character_1001, label_id=1, name="Alpha"
        )
        label_2 = CharacterMailLabel.objects.create(
            character=self.character_1001, label_id=2, name="Bravo"
        )
        labels = CharacterMailLabel.objects.get_all_labels()
        self.assertDictEqual(
            labels, {label_1.label_id: label_1, label_2.label_id: label_2}
        )

    def test_empty(self):
        labels = CharacterMailLabel.objects.get_all_labels()
        self.assertDictEqual(labels, dict())


@patch(MODULE_PATH + ".esi")
class TestCharacterMiningLedgerManager(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        cls.character_1001 = create_memberaudit_character(1001)
        cls.endpoints = [
            EsiEndpoint(
                "Industry",
                "get_characters_character_id_mining",
                "character_id",
                needs_token=True,
                data={
                    "1001": [
                        {
                            "date": "2017-09-19",
                            "quantity": 7004,
                            "solar_system_id": 30002537,
                            "type_id": 17471,
                        },
                        {
                            "date": "2017-09-18",
                            "quantity": 5199,
                            "solar_system_id": 30002537,
                            "type_id": 17471,
                        },
                    ]
                },
            ),
        ]
        cls.esi_client_stub = EsiClientStub.create_from_endpoints(cls.endpoints)

    def test_should_add_new_entry_from_scratch(self, mock_esi):
        # given
        mock_esi.client = self.esi_client_stub
        # when
        self.character_1001.update_mining_ledger()
        # then
        self.assertEqual(self.character_1001.mining_ledger.count(), 2)
        obj = self.character_1001.mining_ledger.first()
        self.assertEqual(obj.date, dt.date(2017, 9, 19))
        self.assertEqual(obj.eve_type, EveType.objects.get(name="Dense Veldspar"))
        self.assertEqual(
            obj.eve_solar_system, EveSolarSystem.objects.get(name="Amamake")
        )
        self.assertEqual(obj.quantity, 7004)

    def test_should_update_existing_entries(self, mock_esi):
        # given
        mock_esi.client = self.esi_client_stub
        create_character_mining_ledger_entry(
            character=self.character_1001,
            date=dt.date(2017, 9, 19),
            eve_solar_system=EveSolarSystem.objects.get(name="Amamake"),
            eve_type=EveType.objects.get(name="Dense Veldspar"),
            quantity=5,
        )
        # when
        self.character_1001.update_mining_ledger()
        # then
        self.assertEqual(self.character_1001.mining_ledger.count(), 2)
        obj = self.character_1001.mining_ledger.get(
            date=dt.date(2017, 9, 19),
            eve_solar_system=EveSolarSystem.objects.get(name="Amamake"),
            eve_type=EveType.objects.get(name="Dense Veldspar"),
        )
        self.assertEqual(obj.quantity, 7004)


@patch(MODULE_PATH + ".esi")
class TestCharacterPlanetManager(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        cls.character_1001 = create_memberaudit_character(1001)
        cls.endpoints = [
            EsiEndpoint(
                "Planetary_Interaction",
                "get_characters_character_id_planets",
                "character_id",
                needs_token=True,
                data={
                    "1001": [
                        {
                            "last_update": "2016-11-28T16:42:51Z",
                            "num_pins": 1,
                            "owner_id": 1001,
                            "planet_id": 40161463,
                            "planet_type": "barren",
                            "solar_system_id": 30002537,
                            "upgrade_level": 0,
                        }
                    ]
                },
            ),
        ]
        cls.esi_client_stub = EsiClientStub.create_from_endpoints(cls.endpoints)

    def test_should_add_new_planet(self, mock_esi):
        # given
        mock_esi.client = self.esi_client_stub
        # when
        self.character_1001.update_planets()
        # then
        self.assertEqual(self.character_1001.planets.count(), 1)
        obj: CharacterPlanet = self.character_1001.planets.first()
        self.assertIsInstance(obj.last_update_at, dt.datetime)
        self.assertEqual(obj.eve_planet, EvePlanet.objects.get(id=40161463))
        self.assertEqual(obj.num_pins, 1)
        self.assertEqual(obj.upgrade_level, 0)

    def test_should_update_existing_entries(self, mock_esi):
        # given
        mock_esi.client = self.esi_client_stub
        create_character_planet(character=self.character_1001)
        # when
        self.character_1001.update_planets()
        # then
        self.assertEqual(self.character_1001.planets.count(), 1)
        obj: CharacterPlanet = self.character_1001.planets.first()
        self.assertIsInstance(obj.last_update_at, dt.datetime)
        self.assertEqual(obj.eve_planet, EvePlanet.objects.get(id=40161463))
        self.assertEqual(obj.num_pins, 1)
        self.assertEqual(obj.upgrade_level, 0)


@patch(MODULE_PATH + ".esi")
class TestCharacterSkillsManager(CharacterUpdateTestDataMixin, NoSocketsTestCase):
    def test_can_create_new_skills(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        # when
        CharacterSkill.objects.update_or_create_esi(character=self.character_1001)
        # then
        self.assertEqual(self.character_1001.skillpoints.total, 30_000)
        self.assertEqual(self.character_1001.skillpoints.unallocated, 1_000)
        self.assertSetEqual(
            set(self.character_1001.skills.values_list("eve_type_id", flat=True)),
            {24311, 24312},
        )
        skill = self.character_1001.skills.get(eve_type_id=24311)
        self.assertEqual(skill.active_skill_level, 3)
        self.assertEqual(skill.skillpoints_in_skill, 20_000)
        self.assertEqual(skill.trained_skill_level, 4)

        skill = self.character_1001.skills.get(eve_type_id=24312)
        self.assertEqual(skill.active_skill_level, 1)
        self.assertEqual(skill.skillpoints_in_skill, 10_000)
        self.assertEqual(skill.trained_skill_level, 1)

    def test_caen_update_existing_skills(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        CharacterSkill.objects.create(
            character=self.character_1001,
            eve_type=EveType.objects.get(id=24311),
            active_skill_level=1,
            skillpoints_in_skill=1,
            trained_skill_level=1,
        )
        # when
        CharacterSkill.objects.update_or_create_esi(character=self.character_1001)
        # then
        self.assertEqual(self.character_1001.skills.count(), 2)
        skill = self.character_1001.skills.get(eve_type_id=24311)
        self.assertEqual(skill.active_skill_level, 3)
        self.assertEqual(skill.skillpoints_in_skill, 20_000)
        self.assertEqual(skill.trained_skill_level, 4)

    def test_can_delete_obsolete_skills(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        CharacterSkill.objects.create(
            character=self.character_1001,
            eve_type=EveType.objects.get(id=20185),
            active_skill_level=1,
            skillpoints_in_skill=1,
            trained_skill_level=1,
        )
        # when
        CharacterSkill.objects.update_or_create_esi(character=self.character_1001)
        # then
        self.assertSetEqual(
            set(self.character_1001.skills.values_list("eve_type_id", flat=True)),
            {24311, 24312},
        )

    def test_update_skills_4(self, mock_esi):
        """when ESI info has not changed, then do not update local data"""
        # given
        mock_esi.client = esi_client_stub
        self.character_1001.reset_update_section(Character.UpdateSection.SKILLS)
        self.character_1001.update_skills()
        skill = self.character_1001.skills.get(eve_type_id=24311)
        skill.active_skill_level = 4
        skill.save()
        # when
        CharacterSkill.objects.update_or_create_esi(character=self.character_1001)
        # then
        skill.refresh_from_db()
        self.assertEqual(skill.active_skill_level, 4)

    def test_update_skills_5(self, mock_esi):
        """when ESI info has not changed and update forced, then update local data"""
        # given
        mock_esi.client = esi_client_stub
        self.character_1001.reset_update_section(Character.UpdateSection.SKILLS)
        # when
        CharacterSkill.objects.update_or_create_esi(character=self.character_1001)
        # then
        skill = self.character_1001.skills.get(eve_type_id=24311)
        skill.active_skill_level = 4
        skill.save()
        self.character_1001.update_skills(force_update=True)
        skill = self.character_1001.skills.get(eve_type_id=24311)
        self.assertEqual(skill.active_skill_level, 3)


@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
@patch(MODULE_PATH + ".esi")
class TestCharacterWalletJournalManager(
    CharacterUpdateTestDataMixin, NoSocketsTestCase
):
    # def test_update_wallet_balance(self, mock_esi):
    #     mock_esi.client = esi_client_stub

    #     self.character_1001.update_wallet_balance()
    #     self.assertEqual(self.character_1001.wallet_balance.total, 123456789)

    @patch(MODULE_PATH + ".data_retention_cutoff", lambda: None)
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

    @patch(MODULE_PATH + ".data_retention_cutoff", lambda: None)
    def test_update_wallet_journal_2(self, mock_esi):
        """can add entry to existing wallet journal"""
        mock_esi.client = esi_client_stub
        CharacterWalletJournalEntry.objects.create(
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

    @patch(MODULE_PATH + ".data_retention_cutoff", lambda: None)
    def test_update_wallet_journal_3(self, mock_esi):
        """does not update existing entries"""
        mock_esi.client = esi_client_stub
        CharacterWalletJournalEntry.objects.create(
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
            MODULE_PATH + ".data_retention_cutoff",
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
        CharacterWalletJournalEntry.objects.create(
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
            MODULE_PATH + ".data_retention_cutoff",
            lambda: dt.datetime(2018, 3, 11, 20, 5, tzinfo=dt.timezone.utc)
            - dt.timedelta(days=20),
        ):
            self.character_1001.update_wallet_journal()

        self.assertSetEqual(
            set(self.character_1001.wallet_journal.values_list("entry_id", flat=True)),
            {89, 91},
        )
