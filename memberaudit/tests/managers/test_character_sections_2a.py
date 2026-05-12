import datetime as dt
from unittest.mock import patch

from django.test import override_settings
from django.utils.dateparse import parse_datetime
from django.utils.timezone import now
from eveuniverse.models import EveEntity, EveType

from app_utils.esi_testing import EsiClientStub, EsiEndpoint
from app_utils.testing import NoSocketsTestCase

from memberaudit.core.xml_converter import eve_xml_to_html
from memberaudit.models import (
    CharacterCloneInfo,
    CharacterCorporationHistory,
    CharacterDetails,
    CharacterFwStats,
    CharacterJumpClone,
    Location,
)
from memberaudit.tests.testdata.esi_client_stub import esi_client_stub
from memberaudit.tests.testdata.factories import (
    create_character_clone_info,
    create_character_corporation_history,
    create_character_details,
    create_character_from_user,
    create_character_fw_stats,
    create_character_jump_clone,
    create_character_jump_clone_implant,
)
from memberaudit.tests.testdata.load_entities import load_entities
from memberaudit.tests.testdata.load_eveuniverse import load_eveuniverse
from memberaudit.tests.testdata.load_locations import load_locations
from memberaudit.tests.utils import (
    create_memberaudit_character,
    create_user_from_evecharacter_with_access,
)

MODULE_PATH = "memberaudit.managers.character_sections_2"


@patch(MODULE_PATH + ".esi")
class TestCharacterCorporationHistoryManager(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities()
        cls.character_1001 = create_memberaudit_character(1001)
        cls.character_1002 = create_memberaudit_character(1002)
        cls.corporation_2001 = EveEntity.objects.get(id=2001)
        cls.corporation_2002 = EveEntity.objects.get(id=2002)

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
        create_character_corporation_history(
            character=self.character_1001,
            record_id=500,
            corporation=self.corporation_2002,
            start_date=now(),
        )

        # when
        CharacterCorporationHistory.objects.update_or_create_esi(self.character_1001)

        # then
        self.assertEqual(self.character_1001.corporation_history.count(), 2)

        obj = self.character_1001.corporation_history.get(record_id=500)
        self.assertEqual(obj.corporation, self.corporation_2001)
        self.assertTrue(obj.is_deleted)
        self.assertEqual(obj.start_date, parse_datetime("2016-06-26T20:00:00Z"))

    def test_can_remove_obsolete_entries(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        create_character_corporation_history(
            character=self.character_1001,
            record_id=499,
            corporation=EveEntity.objects.get(id=2101),
        )

        # when
        CharacterCorporationHistory.objects.update_or_create_esi(self.character_1001)

        # then
        record_ids = set(
            self.character_1001.corporation_history.values_list("record_id", flat=True)
        )
        self.assertSetEqual(record_ids, {500, 501})

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
class TestCharacterDetailManager(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        cls.character_1001 = create_memberaudit_character(1001)
        cls.character_1002 = create_memberaudit_character(1002)
        cls.corporation_2001 = EveEntity.objects.get(id=2001)
        cls.corporation_2002 = EveEntity.objects.get(id=2002)

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
        create_character_details(
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
            obj.enlisted_on,
            dt.datetime(2023, 3, 21, 15, 0, tzinfo=dt.timezone.utc),
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
        create_character_fw_stats(
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
            obj.enlisted_on,
            dt.datetime(2023, 3, 21, 15, 0, tzinfo=dt.timezone.utc),
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
class TestCharacterImplantManager(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        cls.character_1001 = create_memberaudit_character(1001)
        cls.character_1002 = create_memberaudit_character(1002)

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
class TestCharacterJumpClonesManager(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        load_locations()
        cls.jita_44 = Location.objects.get(id=60003760)
        cls.structure_1 = Location.objects.get(id=1000000000001)
        cls.user_1001, _ = create_user_from_evecharacter_with_access(1001)
        cls.user_1002, _ = create_user_from_evecharacter_with_access(1002)
        cls.snakes_alpha = EveType.objects.get(name="High-grade Snake Alpha")
        cls.snakes_beta = EveType.objects.get(name="High-grade Snake Beta")

    def test_should_create_from_scratch(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        character_1001 = create_character_from_user(self.user_1001)

        # when
        CharacterJumpClone.objects.update_or_create_esi(character_1001)

        # then
        self.assertEqual(character_1001.jump_clones.count(), 1)
        obj: CharacterJumpClone = character_1001.jump_clones.get(jump_clone_id=12345)
        self.assertEqual(obj.location, self.jita_44)
        self.assertEqual(
            {type_id for type_id in obj.implants.values_list("eve_type_id", flat=True)},
            {19540, 19551, 19553},
        )

        obj: CharacterCloneInfo = character_1001.clone_info
        self.assertEqual(obj.home_location, self.structure_1)
        self.assertEqual(
            obj.last_clone_jump_date,
            dt.datetime(2017, 1, 1, 10, 10, 10, tzinfo=dt.timezone.utc),
        )
        self.assertEqual(
            obj.last_station_change_date,
            dt.datetime(2017, 1, 2, 11, 10, 10, tzinfo=dt.timezone.utc),
        )

    def test_should_update_existing(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        character_1001 = create_character_from_user(self.user_1001)
        create_character_clone_info(
            character_1001,
            home_location_id=1000000000002,
            last_clone_jump_date=dt.datetime(
                2016, 1, 1, 10, 10, 10, tzinfo=dt.timezone.utc
            ),
            last_station_change_date=dt.datetime(
                2016, 1, 2, 11, 10, 10, tzinfo=dt.timezone.utc
            ),
        )
        jump_clone = create_character_jump_clone(
            character=character_1001, location=self.jita_44
        )
        create_character_jump_clone_implant(
            jump_clone=jump_clone, eve_type=self.snakes_alpha
        )
        create_character_jump_clone_implant(
            jump_clone=jump_clone, eve_type=self.snakes_beta
        )

        # when
        CharacterJumpClone.objects.update_or_create_esi(character_1001)

        # then
        character_1001.refresh_from_db()
        self.assertEqual(character_1001.jump_clones.count(), 1)
        obj: CharacterJumpClone = character_1001.jump_clones.get(jump_clone_id=12345)
        self.assertEqual(obj.location, self.jita_44)
        self.assertEqual(
            {type_id for type_id in obj.implants.values_list("eve_type_id", flat=True)},
            {19540, 19551, 19553},
        )

        obj: CharacterCloneInfo = character_1001.clone_info
        self.assertEqual(obj.home_location, self.structure_1)
        self.assertEqual(
            obj.last_clone_jump_date,
            dt.datetime(2017, 1, 1, 10, 10, 10, tzinfo=dt.timezone.utc),
        )
        self.assertEqual(
            obj.last_station_change_date,
            dt.datetime(2017, 1, 2, 11, 10, 10, tzinfo=dt.timezone.utc),
        )

    def test_can_update_without_implants(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        character_1002 = create_character_from_user(self.user_1002)

        # when
        CharacterJumpClone.objects.update_or_create_esi(character_1002)

        # then
        self.assertEqual(character_1002.jump_clones.count(), 1)
        obj = character_1002.jump_clones.get(jump_clone_id=12345)
        self.assertEqual(obj.location, self.jita_44)
        self.assertEqual(obj.implants.count(), 0)

    def test_skip_update_when_no_new_data(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        character_1001 = create_character_from_user(self.user_1001)
        CharacterJumpClone.objects.update_or_create_esi(character_1001)
        obj = character_1001.jump_clones.get(jump_clone_id=12345)
        obj.location = self.structure_1
        obj.save()

        # when
        CharacterJumpClone.objects.update_or_create_esi(character_1001)

        # then
        obj = character_1001.jump_clones.get(jump_clone_id=12345)
        self.assertEqual(obj.location, self.structure_1)

    def test_update_always_when_forced(self, mock_esi):
        # given
        mock_esi.client = esi_client_stub
        character_1001 = create_character_from_user(self.user_1001)
        CharacterJumpClone.objects.update_or_create_esi(character_1001)
        obj = character_1001.jump_clones.get(jump_clone_id=12345)
        obj.location = self.structure_1
        obj.save()

        # when
        CharacterJumpClone.objects.update_or_create_esi(
            character_1001, force_update=True
        )

        # then
        obj = character_1001.jump_clones.get(jump_clone_id=12345)
        self.assertEqual(obj.location, self.jita_44)
