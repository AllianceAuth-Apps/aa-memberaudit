import datetime as dt
from unittest.mock import patch

import pytz

from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils.timezone import now
from eveuniverse.models import EveEntity, EveType

from allianceauth.eveonline.models import EveCharacter
from app_utils.testing import (
    create_user_from_evecharacter,
    generate_invalid_pk,
    response_text,
)

from memberaudit.models import CharacterAsset, CharacterContract, Location
from memberaudit.tests.testdata.factories import (
    create_character,
    create_character_asset,
    create_character_attributes,
    create_character_contact,
    create_character_contract,
    create_character_contract_item,
    create_character_corporation_history,
    create_character_fw_stats,
    create_character_implant,
    create_character_loyalty_entry,
    create_eve_market_price,
)
from memberaudit.tests.testdata.load_entities import load_entities
from memberaudit.tests.testdata.load_eveuniverse import load_eveuniverse
from memberaudit.tests.testdata.load_locations import load_locations
from memberaudit.tests.utils import (
    create_memberaudit_character,
    json_response_to_dict_2,
    json_response_to_python_2,
)
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


class TestCharacterViewer(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        load_entities()
        cls.character = create_memberaudit_character(1001)
        cls.user = cls.character.user

    def test_can_open_character_main_view_for_normal_character(self):
        # given
        request = self.factory.get(
            reverse("memberaudit:character_viewer", args=[self.character.pk])
        )
        request.user = self.user
        # when
        response = character_viewer(request, self.character.pk)
        # then
        self.assertEqual(response.status_code, 200)

    def test_can_open_character_main_view_for_orphan(self):
        # given
        character = create_character(EveCharacter.objects.get(character_id=1121))
        user, _ = create_user_from_evecharacter(
            1002,
            permissions=[
                "memberaudit.basic_access",
                "memberaudit.view_everything",
                "memberaudit.characters_access",
            ],
        )
        request = self.factory.get(
            reverse("memberaudit:character_viewer", args=[character.pk])
        )
        request.user = user
        # when
        response = character_viewer(request, character.pk)
        # then
        self.assertEqual(response.status_code, 200)

    def test_character_attribute_data(self):
        create_character_attributes(
            character=self.character,
            last_remap_date="2020-10-24T09:00:00Z",
            bonus_remaps=3,
            charisma=100,
            intelligence=101,
            memory=102,
            perception=103,
            willpower=104,
        )

        request = self.factory.get(
            reverse("memberaudit:character_attribute_data", args=[self.character.pk])
        )

        request.user = self.user
        response = character_attribute_data(request, self.character.pk)
        self.assertEqual(response.status_code, 200)


class TestCharacterFwStats(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        load_eveuniverse()
        load_entities()
        cls.character = create_memberaudit_character(1001)
        cls.user = cls.character.user

    def test_should_load_with_stats(self):
        # given
        create_character_fw_stats(character=self.character).save()
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


class TestCharacterAssets(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        load_eveuniverse()
        load_entities()
        load_locations()
        cls.character = create_memberaudit_character(1001)
        cls.user = cls.character.user
        cls.jita_44 = Location.objects.get(id=60003760)
        cls.structure_1 = Location.objects.get(id=1000000000001)

    def test_character_assets_data_1(self):
        container = create_character_asset(
            character=self.character,
            item_id=1,
            location=self.jita_44,
            eve_type=EveType.objects.get(id=20185),
            is_singleton=True,
            name="Trucker",
            quantity=1,
        )
        create_character_asset(
            character=self.character,
            item_id=2,
            parent=container,
            eve_type=EveType.objects.get(id=603),
            is_singleton=False,
            quantity=1,
        )

        request = self.factory.get(
            reverse("memberaudit:character_assets_data", args=[self.character.pk])
        )
        request.user = self.user
        response = character_assets_data(request, self.character.pk)
        self.assertEqual(response.status_code, 200)
        data = json_response_to_python_2(response)
        self.assertEqual(len(data), 1)
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
        create_character_asset(
            character=self.character,
            item_id=1,
            location=self.jita_44,
            eve_type=EveType.objects.get(id=20185),
            is_singleton=False,
            name="",
            quantity=1,
        )
        request = self.factory.get(
            reverse("memberaudit:character_assets_data", args=[self.character.pk])
        )
        request.user = self.user
        response = character_assets_data(request, self.character.pk)
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
        obj1 = EveType.objects.get(id=603)
        obj2 = EveType.objects.get(id=20185)
        create_character_asset(
            character=self.character,
            item_id=1,
            location=self.jita_44,
            eve_type=obj1,
            is_singleton=False,
            name="",
            quantity=5,
        )
        create_character_asset(
            character=self.character,
            item_id=2,
            location=self.jita_44,
            eve_type=obj2,
            is_singleton=False,
            name="",
            quantity=3,
        )
        create_eve_market_price(eve_type=obj1, average_price=11111)
        create_eve_market_price(eve_type=obj2, average_price=555555555)
        request = self.factory.get(
            reverse("memberaudit:character_assets_data", args=[self.character.pk])
        )
        request.user = self.user
        response = character_assets_data(request, self.character.pk)
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
        parent_asset = create_character_asset(
            character=self.character,
            item_id=1,
            location=self.jita_44,
            eve_type=EveType.objects.get(id=20185),
            is_singleton=True,
            name="Trucker",
            quantity=1,
        )
        create_character_asset(
            character=self.character,
            item_id=2,
            parent=parent_asset,
            eve_type=EveType.objects.get(id=603),
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
        response = character_asset_container(
            request, self.character.pk, parent_asset.pk
        )
        self.assertEqual(response.status_code, 200)

    def test_character_asset_children_error(self):
        parent_asset_pk = generate_invalid_pk(CharacterAsset)
        request = self.factory.get(
            reverse(
                "memberaudit:character_asset_container",
                args=[self.character.pk, parent_asset_pk],
            )
        )
        request.user = self.user
        response = character_asset_container(
            request, self.character.pk, parent_asset_pk
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("not found for character", response_text(response))

    def test_character_asset_children_data(self):
        parent_asset = create_character_asset(
            character=self.character,
            item_id=1,
            location=self.jita_44,
            eve_type=EveType.objects.get(id=20185),
            is_singleton=True,
            name="Trucker",
            quantity=1,
        )
        create_character_asset(
            character=self.character,
            item_id=2,
            parent=parent_asset,
            eve_type=EveType.objects.get(id=603),
            is_singleton=True,
            name="My Precious",
            quantity=1,
        )
        create_character_asset(
            character=self.character,
            item_id=3,
            parent=parent_asset,
            eve_type=EveType.objects.get(id=19540),
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
        response = character_asset_container_data(
            request, self.character.pk, parent_asset.pk
        )
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


class TestCharacterDataViewsOther(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        load_eveuniverse()
        load_entities()
        cls.character = create_memberaudit_character(1001)
        cls.user = cls.character.user

    def test_character_contacts_data(self):
        create_character_contact(
            character=self.character,
            eve_entity=EveEntity.objects.get(id=1101),
            standing=-10,
            is_blocked=True,
        )
        create_character_contact(
            character=self.character,
            eve_entity=EveEntity.objects.get(id=2001),
            standing=10,
        )

        request = self.factory.get(
            reverse("memberaudit:character_contacts_data", args=[self.character.pk])
        )
        request.user = self.user
        response = character_contacts_data(request, self.character.pk)
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
        create_character_loyalty_entry(
            character=self.character,
            corporation=EveEntity.objects.get(id=2101),
            loyalty_points=99,
        )
        request = self.factory.get(
            reverse("memberaudit:character_loyalty_data", args=[self.character.pk])
        )
        request.user = self.user
        response = character_loyalty_data(request, self.character.pk)
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
        date_1 = now() - dt.timedelta(days=60)
        create_character_corporation_history(
            character=self.character,
            record_id=1,
            corporation=EveEntity.objects.get(id=2101),
            start_date=date_1,
        )
        date_2 = now() - dt.timedelta(days=20)
        create_character_corporation_history(
            character=self.character,
            record_id=2,
            corporation=EveEntity.objects.get(id=2001),
            start_date=date_2,
            is_deleted=True,
        )
        request = self.factory.get(
            reverse(
                "memberaudit:character_corporation_history", args=[self.character.pk]
            )
        )
        request.user = self.user
        response = character_corporation_history(request, self.character.pk)

        self.assertEqual(response.status_code, 200)
        text = response.content.decode("utf-8")
        self.assertIn(EveEntity.objects.get(id=2101).name, text)
        self.assertIn(EveEntity.objects.get(id=2001).name, text)
        self.assertIn("(Closed)", text)

    def test_character_character_implants_data(self):
        implant_1 = create_character_implant(
            character=self.character,
            eve_type=EveType.objects.get(name="High-grade Snake Gamma"),
        )
        implant_2 = create_character_implant(
            character=self.character,
            eve_type=EveType.objects.get(name="High-grade Snake Alpha"),
        )
        implant_3 = create_character_implant(
            character=self.character,
            eve_type=EveType.objects.get(name="High-grade Snake Beta"),
        )
        request = self.factory.get(
            reverse("memberaudit:character_implants_data", args=[self.character.pk])
        )
        request.user = self.user
        response = character_implants_data(request, self.character.pk)
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


class TestCharacterContracts(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        load_eveuniverse()
        load_entities()
        load_locations()
        cls.character = create_memberaudit_character(1001)
        cls.user = cls.character.user
        cls.jita_44 = Location.objects.get(id=60003760)
        cls.structure_1 = Location.objects.get(id=1000000000001)
        cls.high_grade_snake_alpha_type = EveType.objects.get(id=19540)
        cls.high_grade_snake_bravo_type = EveType.objects.get(id=19551)

    @patch(MODULE_PATH + ".now")
    def test_character_contracts_data_1(self, mock_now):
        """items exchange single item"""
        date_issued = dt.datetime(2020, 10, 8, 16, 45, tzinfo=pytz.utc)
        date_now = date_issued + dt.timedelta(days=1)
        date_expired = date_now + dt.timedelta(days=2, hours=3)
        mock_now.return_value = date_now
        contract = create_character_contract(
            character=self.character,
            contract_id=42,
            availability=CharacterContract.AVAILABILITY_PERSONAL,
            contract_type=CharacterContract.TYPE_ITEM_EXCHANGE,
            assignee=EveEntity.objects.get(id=1002),
            date_issued=date_issued,
            date_expired=date_expired,
            for_corporation=False,
            issuer=EveEntity.objects.get(id=1001),
            issuer_corporation=EveEntity.objects.get(id=2001),
            status=CharacterContract.STATUS_IN_PROGRESS,
            start_location=self.jita_44,
            end_location=self.jita_44,
            title="Dummy info",
        )
        create_character_contract_item(
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
        contract = create_character_contract(
            character=self.character,
            availability=CharacterContract.AVAILABILITY_PUBLIC,
            contract_id=42,
            contract_type=CharacterContract.TYPE_ITEM_EXCHANGE,
            assignee=EveEntity.objects.get(id=1002),
            date_issued=date_issued,
            date_expired=date_expired,
            for_corporation=False,
            issuer=EveEntity.objects.get(id=1001),
            issuer_corporation=EveEntity.objects.get(id=2001),
            status=CharacterContract.STATUS_IN_PROGRESS,
            title="Dummy info",
            start_location=self.jita_44,
            end_location=self.jita_44,
        )
        create_character_contract_item(
            contract=contract,
            record_id=1,
            eve_type=self.high_grade_snake_alpha_type,
        )
        create_character_contract_item(
            contract=contract,
            record_id=2,
            eve_type=self.high_grade_snake_bravo_type,
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
        contract = create_character_contract(
            character=self.character,
            contract_id=42,
            availability=CharacterContract.AVAILABILITY_PERSONAL,
            contract_type=CharacterContract.TYPE_COURIER,
            assignee=EveEntity.objects.get(id=1002),
            date_issued=date_issued,
            date_expired=date_expired,
            for_corporation=False,
            issuer=EveEntity.objects.get(id=1001),
            issuer_corporation=EveEntity.objects.get(id=2001),
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
        contract = create_character_contract(
            character=self.character,
            contract_id=42,
            availability=CharacterContract.AVAILABILITY_PERSONAL,
            contract_type=CharacterContract.TYPE_ITEM_EXCHANGE,
            assignee=EveEntity.objects.get(id=1002),
            date_issued=date_issued,
            date_expired=date_expired,
            for_corporation=False,
            issuer=EveEntity.objects.get(id=1001),
            issuer_corporation=EveEntity.objects.get(id=2001),
            status=CharacterContract.STATUS_IN_PROGRESS,
            start_location=self.jita_44,
            end_location=self.jita_44,
            title="Dummy info",
        )
        create_character_contract_item(
            contract=contract,
            record_id=1,
            is_included=True,
            is_singleton=False,
            quantity=3,
            eve_type=self.high_grade_snake_alpha_type,
        )
        create_character_contract_item(
            contract=contract,
            record_id=2,
            is_included=False,
            is_singleton=False,
            quantity=3,
            eve_type=self.high_grade_snake_bravo_type,
        )
        create_eve_market_price(
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
        contract = create_character_contract(
            character=self.character,
            contract_id=42,
            availability=CharacterContract.AVAILABILITY_PERSONAL,
            contract_type=CharacterContract.TYPE_ITEM_EXCHANGE,
            assignee=EveEntity.objects.get(id=1002),
            date_issued=date_issued,
            date_expired=date_expired,
            for_corporation=False,
            issuer=EveEntity.objects.get(id=1001),
            issuer_corporation=EveEntity.objects.get(id=2001),
            status=CharacterContract.STATUS_IN_PROGRESS,
            start_location=self.jita_44,
            end_location=self.jita_44,
            title="Dummy info",
        )
        create_character_contract_item(
            contract=contract,
            record_id=1,
            is_included=True,
            is_singleton=True,
            quantity=1,
            raw_quantity=-2,
            eve_type=self.high_grade_snake_alpha_type,
        )
        create_character_contract_item(
            contract=contract,
            record_id=2,
            is_included=True,
            is_singleton=False,
            quantity=3,
            eve_type=self.high_grade_snake_bravo_type,
        )
        create_eve_market_price(
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
        contract = create_character_contract(
            character=self.character,
            contract_id=42,
            availability=CharacterContract.AVAILABILITY_PERSONAL,
            contract_type=CharacterContract.TYPE_ITEM_EXCHANGE,
            assignee=EveEntity.objects.get(id=1002),
            date_issued=date_issued,
            date_expired=date_expired,
            for_corporation=False,
            issuer=EveEntity.objects.get(id=1001),
            issuer_corporation=EveEntity.objects.get(id=2001),
            status=CharacterContract.STATUS_IN_PROGRESS,
            start_location=self.jita_44,
            end_location=self.jita_44,
            title="Dummy info",
        )
        create_character_contract_item(
            contract=contract,
            record_id=1,
            is_included=False,
            is_singleton=False,
            quantity=3,
            eve_type=self.high_grade_snake_alpha_type,
        )
        create_character_contract_item(
            contract=contract,
            record_id=2,
            is_included=True,
            is_singleton=False,
            quantity=3,
            eve_type=self.high_grade_snake_bravo_type,
        )
        create_eve_market_price(
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
