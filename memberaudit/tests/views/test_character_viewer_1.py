import datetime as dt
from unittest.mock import patch

import pytz

from django.test import RequestFactory
from django.urls import reverse
from django.utils.timezone import now
from eveuniverse.tests.testdata.factories_2 import (
    EveEntityCharacterFactory,
    EveEntityCorporationFactory,
    EveMarketPriceFactory,
    EveSolarSystemHighSecFactory,
    EveSolarSystemLowSecFactory,
    EveTypeFactory,
    ShipTypeFactory,
)

from app_utils.testdata_factories import UserMainFactory
from app_utils.testing import NoSocketsTestCase, generate_invalid_pk, response_text

from memberaudit.models import CharacterAsset, CharacterContract
from memberaudit.tests.testdata.factories_2 import (
    CharacterAssetFactory,
    CharacterAttributesFactory,
    CharacterContactFactory,
    CharacterContractCourierFactory,
    CharacterContractItemExchangeFactory,
    CharacterContractItemFactory,
    CharacterCorporationHistoryFactory,
    CharacterFactory,
    CharacterFwStatsFactory,
    CharacterImplantFactory,
    CharacterLoyaltyEntryFactory,
    CharacterOrphanFactory,
    CyberimplantTypeFactory,
    LocationStationFactory,
    LocationStructureFactory,
    UserMainBasicAccessFactory,
)
from memberaudit.tests.utils import json_response_to_dict_2, json_response_to_python_2
from memberaudit.views.character_viewer_1 import (
    character_asset_container,
    character_asset_container_data,
    character_assets_data,
    character_attribute_data,
    character_contacts_data,
    character_contract_details,
    character_contract_items_included_data,
    character_contract_items_requested_data,
    character_contracts_data,
    character_corporation_history,
    character_fw_stats,
    character_implants_data,
    character_loyalty_data,
    character_viewer,
)

MODULE_PATH = "memberaudit.views.character_viewer_1"


class TestCharacterViewer(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()

    def test_can_open_character_main_view_for_normal_character(self):
        # given
        user = UserMainBasicAccessFactory()
        character = CharacterFactory(user=user)
        request = self.factory.get(
            reverse("memberaudit:character_viewer", args=[character.pk])
        )
        request.user = user
        # when
        response = character_viewer(request, character.pk)
        # then
        self.assertEqual(response.status_code, 200)

    def test_can_open_character_main_view_for_orphan(self):
        # given
        user = UserMainFactory(
            permissions__=[
                "memberaudit.basic_access",
                "memberaudit.view_everything",
                "memberaudit.characters_access",
            ]
        )
        character = CharacterOrphanFactory()
        request = self.factory.get(
            reverse("memberaudit:character_viewer", args=[character.pk])
        )
        request.user = user
        # when
        response = character_viewer(request, character.pk)
        # then
        self.assertEqual(response.status_code, 200)

    def test_character_attribute_data(self):
        # given
        user = UserMainBasicAccessFactory()
        character = CharacterFactory(user=user)
        CharacterAttributesFactory(
            character=character,
            last_remap_date="2020-10-24T09:00:00Z",
            bonus_remaps=3,
            charisma=100,
            intelligence=101,
            memory=102,
            perception=103,
            willpower=104,
        )
        request = self.factory.get(
            reverse("memberaudit:character_attribute_data", args=[character.pk])
        )
        request.user = user

        # when
        response = character_attribute_data(request, character.pk)

        # then
        self.assertEqual(response.status_code, 200)


class TestCharacterFwStats(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        cls.user = UserMainBasicAccessFactory()
        cls.character = CharacterFactory(user=cls.user)

    def test_should_load_with_stats(self):
        # given
        CharacterFwStatsFactory(character=self.character)
        request = self.factory.get(
            reverse("memberaudit:character_fw_stats", args=[self.character.pk])
        )
        request.user = self.user

        # when
        response = character_fw_stats(request, self.character.pk)

        # then
        self.assertEqual(response.status_code, 200)

    def test_should_load_without_stats(self):
        # given
        request = self.factory.get(
            reverse("memberaudit:character_fw_stats", args=[self.character.pk])
        )
        request.user = self.user

        # when
        response = character_fw_stats(request, self.character.pk)

        # then
        self.assertEqual(response.status_code, 200)


class TestCharacterAssets(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        cls.user = UserMainBasicAccessFactory()
        cls.character = CharacterFactory(user=cls.user)
        cls.structure_1 = LocationStructureFactory(id=1000000000001)
        jita = EveSolarSystemHighSecFactory(
            id=30000142,
            name="Jita",
            eve_constellation__id=20000020,
            eve_constellation__name="Kimotoro",
            eve_constellation__eve_region__id=10000002,
            eve_constellation__eve_region__name="The Forge",
        )
        cls.jita_44 = LocationStationFactory(
            id=60003760,
            name="Jita IV - Moon 4 - Caldari Navy Assembly Plant",
            eve_solar_system=jita,
        )
        cls.merlin_type = ShipTypeFactory(
            id=603,
            name="Merlin",
            eve_group__id=25,
            eve_group__name="Frigate",
            volume=16500.0,
        )
        cls.charon_type = ShipTypeFactory(
            id=20185,
            name="Charon",
            eve_group__id=513,
            eve_group__name="Freighter",
            volume=16250000.0,
        )
        cls.high_grade_snake_alpha_type = EveTypeFactory(
            id=19540,
            name="High-grade Snake Alpha",
            eve_group__id=300,
            eve_group__name="Cyberimplant",
            volume=1.0,
        )

    def test_character_assets_data_1(self):
        # given
        container = CharacterAssetFactory(
            character=self.character,
            item_id=1,
            location=self.jita_44,
            eve_type=self.charon_type,
            is_singleton=True,
            name="Trucker",
            quantity=1,
        )
        CharacterAssetFactory(
            character=self.character,
            item_id=2,
            parent=container,
            eve_type=self.merlin_type,
            is_singleton=False,
            quantity=1,
        )
        request = self.factory.get(
            reverse("memberaudit:character_assets_data", args=[self.character.pk])
        )
        request.user = self.user

        # when
        response = character_assets_data(request, self.character.pk)

        # then
        self.assertEqual(response.status_code, 200)
        data = json_response_to_python_2(response)
        self.assertEqual(len(data), 2)
        row = data[0]
        self.assertEqual(row["item_id"], 1)
        self.assertEqual(
            row["location"],
            "Jita IV - Moon 4 - Caldari Navy Assembly Plant (1) (0.0 ISK)",
        )
        self.assertEqual(row["name"]["sort"], "Trucker")
        self.assertEqual(row["quantity"], "")
        self.assertEqual(row["group"], "Charon")
        self.assertEqual(row["volume"], 16250000.0)
        self.assertEqual(row["solar_system"], "Jita")
        self.assertEqual(row["region"], "The Forge")
        self.assertTrue(row["actions"])

    def test_character_assets_data_2(self):
        # given
        CharacterAssetFactory(
            character=self.character,
            item_id=1,
            location=self.jita_44,
            eve_type=self.charon_type,
            is_singleton=False,
            name="",
            quantity=1,
        )
        request = self.factory.get(
            reverse("memberaudit:character_assets_data", args=[self.character.pk])
        )
        request.user = self.user

        # when
        response = character_assets_data(request, self.character.pk)

        # then
        self.assertEqual(response.status_code, 200)
        data = json_response_to_python_2(response)
        self.assertEqual(len(data), 1)
        row = data[0]
        self.assertEqual(row["item_id"], 1)
        self.assertEqual(
            row["location"],
            "Jita IV - Moon 4 - Caldari Navy Assembly Plant (1) (0.0 ISK)",
        )
        self.assertEqual(row["name"]["sort"], "Charon")
        self.assertEqual(row["quantity"], 1)
        self.assertEqual(row["group"], "Freighter")
        self.assertEqual(row["volume"], 16250000.0)
        self.assertFalse(row["actions"])

    def test_character_assets_data_3(self):
        # given
        obj1 = self.merlin_type
        obj2 = self.charon_type
        CharacterAssetFactory(
            character=self.character,
            item_id=1,
            location=self.jita_44,
            eve_type=obj1,
            is_singleton=False,
            name="",
            quantity=5,
        )
        CharacterAssetFactory(
            character=self.character,
            item_id=2,
            location=self.jita_44,
            eve_type=obj2,
            is_singleton=False,
            name="",
            quantity=3,
        )
        EveMarketPriceFactory(eve_type=obj1, average_price=11111)
        EveMarketPriceFactory(eve_type=obj2, average_price=555555555)
        request = self.factory.get(
            reverse("memberaudit:character_assets_data", args=[self.character.pk])
        )
        request.user = self.user

        # when
        response = character_assets_data(request, self.character.pk)

        # then
        self.assertEqual(response.status_code, 200)
        data = json_response_to_python_2(response)
        self.assertEqual(len(data), 2)
        row = data[0]
        self.assertEqual(row["item_id"], 1)
        self.assertEqual(
            row["location"],
            "Jita IV - Moon 4 - Caldari Navy Assembly Plant (2) (1.7b ISK)",
        )
        self.assertEqual(row["name"]["sort"], "Merlin")
        self.assertEqual(row["quantity"], 5)
        self.assertEqual(row["group"], "Frigate")
        self.assertEqual(row["volume"], 16500.0)
        self.assertFalse(row["actions"])

        row = data[1]
        self.assertEqual(row["item_id"], 2)
        self.assertEqual(
            row["location"],
            "Jita IV - Moon 4 - Caldari Navy Assembly Plant (2) (1.7b ISK)",
        )
        self.assertEqual(row["name"]["sort"], "Charon")
        self.assertEqual(row["quantity"], 3)
        self.assertEqual(row["group"], "Freighter")
        self.assertEqual(row["volume"], 16250000.0)
        self.assertFalse(row["actions"])

    def test_character_asset_children_normal(self):
        # given
        parent_asset = CharacterAssetFactory(
            character=self.character,
            item_id=1,
            location=self.jita_44,
            eve_type=self.charon_type,
            is_singleton=True,
            name="Trucker",
            quantity=1,
        )
        CharacterAssetFactory(
            character=self.character,
            item_id=2,
            parent=parent_asset,
            eve_type=self.merlin_type,
            is_singleton=True,
            name="My Precious",
            quantity=1,
        )
        request = self.factory.get(
            reverse(
                "memberaudit:character_asset_container",
                args=[self.character.pk, parent_asset.pk],
            )
        )
        request.user = self.user

        # when
        response = character_asset_container(
            request, self.character.pk, parent_asset.pk
        )

        # then
        self.assertEqual(response.status_code, 200)

    def test_character_asset_children_error(self):
        # given
        parent_asset_pk = generate_invalid_pk(CharacterAsset)
        request = self.factory.get(
            reverse(
                "memberaudit:character_asset_container",
                args=[self.character.pk, parent_asset_pk],
            )
        )
        request.user = self.user

        # when
        response = character_asset_container(
            request, self.character.pk, parent_asset_pk
        )

        # then
        self.assertEqual(response.status_code, 200)
        self.assertIn("not found for character", response_text(response))

    def test_character_asset_children_data(self):
        # given
        parent_asset = CharacterAssetFactory(
            character=self.character,
            item_id=1,
            location=self.jita_44,
            eve_type=self.charon_type,
            is_singleton=True,
            name="Trucker",
            quantity=1,
        )
        CharacterAssetFactory(
            character=self.character,
            item_id=2,
            parent=parent_asset,
            eve_type=self.merlin_type,
            is_singleton=True,
            name="My Precious",
            quantity=1,
        )
        CharacterAssetFactory(
            character=self.character,
            item_id=3,
            parent=parent_asset,
            eve_type=self.high_grade_snake_alpha_type,
            is_singleton=False,
            quantity=3,
        )
        request = self.factory.get(
            reverse(
                "memberaudit:character_asset_container_data",
                args=[self.character.pk, parent_asset.pk],
            )
        )
        request.user = self.user

        # when
        response = character_asset_container_data(
            request, self.character.pk, parent_asset.pk
        )

        # then
        self.assertEqual(response.status_code, 200)
        data = json_response_to_python_2(response)
        self.assertEqual(len(data), 2)

        row = data[0]
        self.assertEqual(row["item_id"], 2)
        self.assertEqual(row["name"]["sort"], "My Precious")
        self.assertEqual(row["quantity"], "")
        self.assertEqual(row["group"], "Merlin")
        self.assertEqual(row["volume"], 16500.0)

        row = data[1]
        self.assertEqual(row["item_id"], 3)
        self.assertEqual(row["name"]["sort"], "High-grade Snake Alpha")
        self.assertEqual(row["quantity"], 3)
        self.assertEqual(row["group"], "Cyberimplant")
        self.assertEqual(row["volume"], 1.0)


class TestCharacterDataViewsOther(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        cls.user = UserMainBasicAccessFactory()
        cls.character = CharacterFactory(user=cls.user)
        cls.entity_1101 = EveEntityCharacterFactory(id=1101, name="Lex Luther")
        cls.entity_2001 = EveEntityCorporationFactory(
            id=2001, name="Wayne Technologies"
        )
        cls.entity_2101 = EveEntityCorporationFactory(id=2101, name="Lexcorp")

    def test_character_contacts_data(self):
        # given
        CharacterContactFactory(
            character=self.character,
            eve_entity=self.entity_1101,
            standing=-10,
            is_blocked=True,
        )
        CharacterContactFactory(
            character=self.character,
            eve_entity=self.entity_2001,
            standing=10,
        )

        request = self.factory.get(
            reverse("memberaudit:character_contacts_data", args=[self.character.pk])
        )
        request.user = self.user

        # when
        response = character_contacts_data(request, self.character.pk)

        # then
        self.assertEqual(response.status_code, 200)
        data = json_response_to_dict_2(response)

        self.assertEqual(len(data), 2)

        row = data[1101]
        self.assertEqual(row["name"]["sort"], "Lex Luther")
        self.assertEqual(row["standing"], -10)
        self.assertEqual(row["type"], "Character")
        self.assertEqual(row["is_watched"], False)
        self.assertEqual(row["is_blocked"], True)
        self.assertEqual(row["group_name"], "Terrible Standing")

        row = data[2001]
        self.assertEqual(row["name"]["sort"], "Wayne Technologies")
        self.assertEqual(row["standing"], 10)
        self.assertEqual(row["type"], "Corporation")
        self.assertEqual(row["is_watched"], False)
        self.assertEqual(row["is_blocked"], False)
        self.assertEqual(row["group_name"], "Excellent Standing")

    def test_character_loyalty_data(self):
        # given
        CharacterLoyaltyEntryFactory(
            character=self.character,
            corporation=self.entity_2101,
            loyalty_points=99,
        )
        request = self.factory.get(
            reverse("memberaudit:character_loyalty_data", args=[self.character.pk])
        )
        request.user = self.user

        # when
        response = character_loyalty_data(request, self.character.pk)

        # then
        self.assertEqual(response.status_code, 200)
        data = json_response_to_python_2(response)
        self.assertEqual(len(data), 1)
        row = data[0]
        self.assertEqual(row["corporation"]["sort"], "Lexcorp")
        self.assertEqual(row["loyalty_points"], 99)

    def test_character_corporation_history(self):
        """
        when corp history contains two corporations
        and one corp is deleted,
        then both corporation names can be found in the view data
        """
        # given
        date_1 = now() - dt.timedelta(days=60)
        CharacterCorporationHistoryFactory(
            character=self.character,
            record_id=1,
            corporation=self.entity_2101,
            start_date=date_1,
        )
        date_2 = now() - dt.timedelta(days=20)
        CharacterCorporationHistoryFactory(
            character=self.character,
            record_id=2,
            corporation=self.entity_2001,
            start_date=date_2,
            is_deleted=True,
        )
        request = self.factory.get(
            reverse(
                "memberaudit:character_corporation_history", args=[self.character.pk]
            )
        )
        request.user = self.user

        # wen
        response = character_corporation_history(request, self.character.pk)

        # then
        self.assertEqual(response.status_code, 200)
        text = response.content.decode("utf-8")
        self.assertIn(self.entity_2101.name, text)
        self.assertIn(self.entity_2001.name, text)
        self.assertIn("(Closed)", text)

    def test_character_character_implants_data(self):
        # given
        implant_1 = CharacterImplantFactory(
            character=self.character,
            eve_type=CyberimplantTypeFactory(name="High-grade Snake Gamma", slot_num=3),
        )
        implant_2 = CharacterImplantFactory(
            character=self.character,
            eve_type=CyberimplantTypeFactory(name="High-grade Snake Alpha", slot_num=1),
        )
        implant_3 = CharacterImplantFactory(
            character=self.character,
            eve_type=CyberimplantTypeFactory(name="High-grade Snake Beta", slot_num=2),
        )
        request = self.factory.get(
            reverse("memberaudit:character_implants_data", args=[self.character.pk])
        )
        request.user = self.user

        # when
        response = character_implants_data(request, self.character.pk)

        # then
        self.assertEqual(response.status_code, 200)

        data = json_response_to_dict_2(response)
        self.assertSetEqual(
            set(data.keys()), {implant_1.pk, implant_2.pk, implant_3.pk}
        )
        self.assertIn(
            "High-grade Snake Gamma",
            data[implant_1.pk]["implant"]["display"],
        )
        self.assertEqual(data[implant_1.pk]["implant"]["sort"], 3)


class TestCharacterContracts(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        cls.user = UserMainBasicAccessFactory()
        cls.character = CharacterFactory(user=cls.user)
        jita = EveSolarSystemHighSecFactory(
            id=30000142,
            name="Jita",
            eve_constellation__id=20000020,
            eve_constellation__name="Kimotoro",
            eve_constellation__eve_region__id=10000002,
            eve_constellation__eve_region__name="The Forge",
        )
        cls.jita_44 = LocationStationFactory(
            id=60003760,
            name="Jita IV - Moon 4 - Caldari Navy Assembly Plant",
            eve_solar_system=jita,
        )
        amamake = EveSolarSystemLowSecFactory(
            id=30002537,
            name="Amamake",
            eve_constellation__id=20000372,
            eve_constellation__name="Hed",
            eve_constellation__eve_region__id=10000030,
            eve_constellation__eve_region__name="Heimatar",
        )
        cls.structure_1 = LocationStructureFactory(
            id=1000000000001, name="Test Structure Alpha", eve_solar_system=amamake
        )
        cls.high_grade_snake_alpha_type = CyberimplantTypeFactory(
            id=19540, name="High-grade Snake Alpha"
        )
        cls.high_grade_snake_beta_type = CyberimplantTypeFactory(
            id=19551, name="High-grade Snake Beta"
        )
        cls.entity_1001 = EveEntityCharacterFactory(id=1001, name="Bruce Wayne")
        cls.entity_1002 = EveEntityCharacterFactory(id=1002, name="Clark Kent")
        cls.entity_2001 = EveEntityCorporationFactory(
            id=2001, name="Wayne Technologies"
        )

    @patch(MODULE_PATH + ".now")
    def test_character_contracts_data_1(self, mock_now):
        """items exchange single item"""
        date_issued = dt.datetime(2020, 10, 8, 16, 45, tzinfo=pytz.utc)
        date_now = date_issued + dt.timedelta(days=1)
        date_expired = date_now + dt.timedelta(days=2, hours=3)
        mock_now.return_value = date_now
        contract = CharacterContractItemExchangeFactory(
            character=self.character,
            contract_id=42,
            availability=CharacterContract.AVAILABILITY_PERSONAL,
            assignee=self.entity_1002,
            date_issued=date_issued,
            date_expired=date_expired,
            for_corporation=False,
            issuer=self.entity_1001,
            issuer_corporation=self.entity_2001,
            status=CharacterContract.STATUS_IN_PROGRESS,
            start_location=self.jita_44,
            title="Dummy info",
            items=False,
        )
        CharacterContractItemFactory(
            contract=contract, quantity=1, eve_type=self.high_grade_snake_alpha_type
        )

        # main view
        request = self.factory.get(
            reverse("memberaudit:character_contracts_data", args=[self.character.pk])
        )
        request.user = self.user
        response = character_contracts_data(request, self.character.pk)
        self.assertEqual(response.status_code, 200)
        data = json_response_to_python_2(response)
        self.assertEqual(len(data), 1)
        row = data[0]
        self.assertEqual(row["contract_id"], 42)
        self.assertEqual(row["summary"], "High-grade Snake Alpha")
        self.assertEqual(row["type"], "Item Exchange")
        self.assertEqual(row["from"], "Bruce Wayne")
        self.assertEqual(row["to"], "Clark Kent")
        self.assertEqual(row["status"], "in progress")
        self.assertEqual(row["date_issued"], date_issued.isoformat())
        self.assertEqual(row["time_left"], "2\xa0days, 3\xa0hours")
        self.assertEqual(row["info"], "Dummy info")

        # details view
        request = self.factory.get(
            reverse(
                "memberaudit:character_contract_details",
                args=[self.character.pk, contract.pk],
            )
        )
        request.user = self.user
        response = character_contract_details(request, self.character.pk, contract.pk)
        self.assertEqual(response.status_code, 200)

    @patch(MODULE_PATH + ".now")
    def test_character_contracts_data_2(self, mock_now):
        """items exchange multiple item"""
        date_issued = dt.datetime(2020, 10, 8, 16, 45, tzinfo=pytz.utc)
        date_now = date_issued + dt.timedelta(days=1)
        date_expired = date_now + dt.timedelta(days=2, hours=3)
        mock_now.return_value = date_now
        contract = CharacterContractItemExchangeFactory(
            character=self.character,
            availability=CharacterContract.AVAILABILITY_PUBLIC,
            contract_id=42,
            assignee=self.entity_1002,
            date_issued=date_issued,
            date_expired=date_expired,
            for_corporation=False,
            issuer=self.entity_1001,
            issuer_corporation=self.entity_2001,
            status=CharacterContract.STATUS_IN_PROGRESS,
            title="Dummy info",
            start_location=self.jita_44,
            items=False,
        )
        CharacterContractItemFactory(
            contract=contract,
            record_id=1,
            eve_type=self.high_grade_snake_alpha_type,
        )
        CharacterContractItemFactory(
            contract=contract,
            record_id=2,
            eve_type=self.high_grade_snake_beta_type,
        )
        request = self.factory.get(
            reverse("memberaudit:character_contracts_data", args=[self.character.pk])
        )

        # main view
        request.user = self.user
        response = character_contracts_data(request, self.character.pk)
        self.assertEqual(response.status_code, 200)
        data = json_response_to_python_2(response)
        self.assertEqual(len(data), 1)
        row = data[0]
        self.assertEqual(row["contract_id"], 42)
        self.assertEqual(row["summary"], "[Multiple Items]")
        self.assertEqual(row["type"], "Item Exchange")

        # details view
        request = self.factory.get(
            reverse(
                "memberaudit:character_contract_details",
                args=[self.character.pk, contract.pk],
            )
        )
        request.user = self.user
        response = character_contract_details(request, self.character.pk, contract.pk)
        self.assertEqual(response.status_code, 200)

    @patch(MODULE_PATH + ".now")
    def test_character_contracts_data_3(self, mock_now):
        """courier contract"""
        date_issued = dt.datetime(2020, 10, 8, 16, 45, tzinfo=pytz.utc)
        date_now = date_issued + dt.timedelta(days=1)
        date_expired = date_now + dt.timedelta(days=2, hours=3)
        mock_now.return_value = date_now
        contract = CharacterContractCourierFactory(
            character=self.character,
            contract_id=42,
            availability=CharacterContract.AVAILABILITY_PERSONAL,
            assignee=self.entity_1002,
            date_issued=date_issued,
            date_expired=date_expired,
            for_corporation=False,
            issuer=self.entity_1001,
            issuer_corporation=self.entity_2001,
            status=CharacterContract.STATUS_IN_PROGRESS,
            title="Dummy info",
            start_location=self.jita_44,
            end_location=self.structure_1,
            volume=10,
            days_to_complete=3,
            reward=10000000,
            collateral=500000000,
        )

        # main view
        request = self.factory.get(
            reverse("memberaudit:character_contracts_data", args=[self.character.pk])
        )
        request.user = self.user
        response = character_contracts_data(request, self.character.pk)
        self.assertEqual(response.status_code, 200)
        data = json_response_to_python_2(response)
        self.assertEqual(len(data), 1)
        row = data[0]
        self.assertEqual(row["contract_id"], 42)
        self.assertEqual(row["summary"], "Jita >> Amamake (10 m3)")
        self.assertEqual(row["type"], "Courier")

        # details view
        request = self.factory.get(
            reverse(
                "memberaudit:character_contract_details",
                args=[self.character.pk, contract.pk],
            )
        )
        request.user = self.user
        response = character_contract_details(request, self.character.pk, contract.pk)
        self.assertEqual(response.status_code, 200)

    def test_character_contract_details_error(self):
        contract_pk = generate_invalid_pk(CharacterContract)
        request = self.factory.get(
            reverse(
                "memberaudit:character_contract_details",
                args=[self.character.pk, contract_pk],
            )
        )
        request.user = self.user
        response = character_contract_details(request, self.character.pk, contract_pk)
        self.assertEqual(response.status_code, 200)
        self.assertIn("not found for character", response_text(response))

    @patch(MODULE_PATH + ".now")
    def test_items_included_data_normal(self, mock_now):
        """items exchange single item"""
        date_issued = dt.datetime(2020, 10, 8, 16, 45, tzinfo=pytz.utc)
        date_now = date_issued + dt.timedelta(days=1)
        date_expired = date_now + dt.timedelta(days=2, hours=3)
        mock_now.return_value = date_now
        contract = CharacterContractItemExchangeFactory(
            character=self.character,
            contract_id=42,
            availability=CharacterContract.AVAILABILITY_PERSONAL,
            assignee=self.entity_1002,
            date_issued=date_issued,
            date_expired=date_expired,
            for_corporation=False,
            issuer=self.entity_1001,
            issuer_corporation=self.entity_2001,
            status=CharacterContract.STATUS_IN_PROGRESS,
            start_location=self.jita_44,
            title="Dummy info",
            items=False,
        )
        CharacterContractItemFactory(
            contract=contract,
            record_id=1,
            is_included=True,
            is_singleton=False,
            quantity=3,
            eve_type=self.high_grade_snake_alpha_type,
        )
        CharacterContractItemFactory(
            contract=contract,
            record_id=2,
            is_included=False,
            is_singleton=False,
            quantity=3,
            eve_type=self.high_grade_snake_beta_type,
        )
        EveMarketPriceFactory(
            eve_type=self.high_grade_snake_alpha_type, average_price=5000000
        )
        request = self.factory.get(
            reverse(
                "memberaudit:character_contract_items_included_data",
                args=[self.character.pk, contract.pk],
            )
        )
        request.user = self.user
        response = character_contract_items_included_data(
            request, self.character.pk, contract.pk
        )
        self.assertEqual(response.status_code, 200)
        data = json_response_to_dict_2(response)

        self.assertSetEqual(set(data.keys()), {1})
        obj = data[1]
        self.assertEqual(obj["name"]["sort"], "High-grade Snake Alpha")
        self.assertEqual(obj["quantity"], 3)
        self.assertEqual(obj["group"], "Cyberimplant")
        self.assertEqual(obj["category"], "Implant")
        self.assertEqual(obj["price"], 5000000)
        self.assertEqual(obj["total"], 15000000)
        self.assertFalse(obj["is_blueprint_copy"])

    @patch(MODULE_PATH + ".now")
    def test_items_included_data_bpo(self, mock_now):
        """items exchange single item, which is an BPO"""
        date_issued = dt.datetime(2020, 10, 8, 16, 45, tzinfo=pytz.utc)
        date_now = date_issued + dt.timedelta(days=1)
        date_expired = date_now + dt.timedelta(days=2, hours=3)
        mock_now.return_value = date_now
        contract = CharacterContractItemExchangeFactory(
            character=self.character,
            contract_id=42,
            availability=CharacterContract.AVAILABILITY_PERSONAL,
            contract_type=CharacterContract.TYPE_ITEM_EXCHANGE,
            assignee=self.entity_1002,
            date_issued=date_issued,
            date_expired=date_expired,
            for_corporation=False,
            issuer=self.entity_1001,
            issuer_corporation=self.entity_2001,
            status=CharacterContract.STATUS_IN_PROGRESS,
            start_location=self.jita_44,
            title="Dummy info",
            items=False,
        )
        CharacterContractItemFactory(
            contract=contract,
            record_id=1,
            is_included=True,
            is_singleton=True,
            quantity=1,
            raw_quantity=-2,
            eve_type=self.high_grade_snake_alpha_type,
        )
        CharacterContractItemFactory(
            contract=contract,
            record_id=2,
            is_included=True,
            is_singleton=False,
            quantity=3,
            eve_type=self.high_grade_snake_beta_type,
        )
        EveMarketPriceFactory(
            eve_type=self.high_grade_snake_alpha_type, average_price=5000000
        )
        request = self.factory.get(
            reverse(
                "memberaudit:character_contract_items_included_data",
                args=[self.character.pk, contract.pk],
            )
        )
        request.user = self.user
        response = character_contract_items_included_data(
            request, self.character.pk, contract.pk
        )
        self.assertEqual(response.status_code, 200)
        data = json_response_to_dict_2(response)

        self.assertSetEqual(set(data.keys()), {1, 2})
        obj = data[1]
        self.assertEqual(obj["name"]["sort"], "High-grade Snake Alpha [BPC]")
        self.assertEqual(obj["quantity"], "")
        self.assertEqual(obj["group"], "Cyberimplant")
        self.assertEqual(obj["category"], "Implant")
        self.assertIsNone(obj["price"])
        self.assertIsNone(obj["total"])
        self.assertTrue(obj["is_blueprint_copy"])

    @patch(MODULE_PATH + ".now")
    def test_items_requested_data_normal(self, mock_now):
        """items exchange single item"""
        date_issued = dt.datetime(2020, 10, 8, 16, 45, tzinfo=pytz.utc)
        date_now = date_issued + dt.timedelta(days=1)
        date_expired = date_now + dt.timedelta(days=2, hours=3)
        mock_now.return_value = date_now
        contract = CharacterContractItemExchangeFactory(
            character=self.character,
            contract_id=42,
            availability=CharacterContract.AVAILABILITY_PERSONAL,
            contract_type=CharacterContract.TYPE_ITEM_EXCHANGE,
            assignee=self.entity_1002,
            date_issued=date_issued,
            date_expired=date_expired,
            for_corporation=False,
            issuer=self.entity_1001,
            issuer_corporation=self.entity_2001,
            status=CharacterContract.STATUS_IN_PROGRESS,
            start_location=self.jita_44,
            end_location=self.jita_44,
            title="Dummy info",
            items=False,
        )
        CharacterContractItemFactory(
            contract=contract,
            record_id=1,
            is_included=False,
            is_singleton=False,
            quantity=3,
            eve_type=self.high_grade_snake_alpha_type,
        )
        CharacterContractItemFactory(
            contract=contract,
            record_id=2,
            is_included=True,
            is_singleton=False,
            quantity=3,
            eve_type=self.high_grade_snake_beta_type,
        )
        EveMarketPriceFactory(
            eve_type=self.high_grade_snake_alpha_type, average_price=5000000
        )
        request = self.factory.get(
            reverse(
                "memberaudit:character_contract_items_requested_data",
                args=[self.character.pk, contract.pk],
            )
        )
        request.user = self.user
        response = character_contract_items_requested_data(
            request, self.character.pk, contract.pk
        )
        self.assertEqual(response.status_code, 200)
        data = json_response_to_dict_2(response)

        self.assertSetEqual(set(data.keys()), {1})
        obj = data[1]
        self.assertEqual(obj["name"]["sort"], "High-grade Snake Alpha")
        self.assertEqual(obj["quantity"], 3)
        self.assertEqual(obj["group"], "Cyberimplant")
        self.assertEqual(obj["category"], "Implant")
        self.assertEqual(obj["price"], 5000000)
        self.assertEqual(obj["total"], 15000000)
        self.assertFalse(obj["is_blueprint_copy"])
