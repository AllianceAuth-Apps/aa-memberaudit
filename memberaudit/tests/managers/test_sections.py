import datetime as dt
from unittest.mock import patch

from django.test import TestCase
from django.utils.dateparse import parse_datetime
from django.utils.timezone import now
from eveuniverse.models import (
    EveEntity,
    EveMarketPrice,
    EvePlanet,
    EveSolarSystem,
    EveType,
)

from app_utils.esi_testing import EsiClientStub, EsiEndpoint
from app_utils.testing import NoSocketsTestCase

from memberaudit.core.xml_converter import eve_xml_to_html
from memberaudit.models import (
    Character,
    CharacterAsset,
    CharacterContactLabel,
    CharacterContract,
    CharacterContractBid,
    CharacterDetails,
    CharacterMailLabel,
    CharacterPlanet,
    CharacterSkill,
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
        CharacterContactLabel.objects.update_for_character(
            character=self.character_1001, labels=[]
        )
        # then
        self.assertEqual(CharacterContactLabel.objects.count(), 0)


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
