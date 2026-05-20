import datetime as dt

import pook

from django.utils.timezone import now
from eveuniverse.tests.testdata.factories_2 import (
    EveBloodlineFactory,
    EveEntityAllianceFactory,
    EveEntityCorporationFactory,
    EveFactionFactory,
    EveRaceFactory,
)

from memberaudit.models import (
    CharacterCloneInfo,
    CharacterCorporationHistory,
    CharacterDetails,
    CharacterFwStats,
    CharacterJumpClone,
)
from memberaudit.tests.testdata.factories_2 import (
    CharacterCloneInfoFactory,
    CharacterCorporationHistoryFactory,
    CharacterDetailsFactory,
    CharacterFactory,
    CharacterFwStatsFactory,
    CharacterImplantFactory,
    CharacterJumpCloneFactory,
    CharacterJumpCloneImplantFactory,
    CyberimplantTypeFactory,
    LocationStationFactory,
    make_esi_url,
)
from memberaudit.tests.testdata.load_esi_testdata import esi_testdata
from memberaudit.tests.utils import TestCaseWithClearCache, extract


class TestCharacter_UpdateCorporationHistory(TestCaseWithClearCache):
    @pook.on
    def test_can_create_from_scratch(self):
        # given
        character = CharacterFactory()
        corporation_1 = EveEntityCorporationFactory()
        record_id_1 = 1
        start_date_1 = now() - dt.timedelta(days=30)
        corporation_2 = EveEntityCorporationFactory()
        start_date_2 = now() - dt.timedelta(days=5)
        record_id_2 = 2
        pook.get(
            make_esi_url(f"characters/{character.character_id}/corporationhistory"),
            reply=200,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "corporation_id": corporation_2.id,
                    "record_id": record_id_2,
                    "start_date": start_date_2.isoformat(),
                },
                {
                    "corporation_id": corporation_1.id,
                    "record_id": record_id_1,
                    "start_date": start_date_1.isoformat(),
                },
            ],
        )

        # when
        character.update_corporation_history()

        # then
        self.assertEqual(character.corporation_history.count(), 2)

        obj_1: CharacterCorporationHistory = character.corporation_history.get(
            record_id=record_id_1
        )
        self.assertEqual(obj_1.corporation, corporation_1)
        self.assertFalse(obj_1.is_deleted)
        self.assertEqual(obj_1.start_date, start_date_1)

        obj_2: CharacterCorporationHistory = character.corporation_history.get(
            record_id=record_id_2
        )
        self.assertEqual(obj_2.corporation, corporation_2)
        self.assertFalse(obj_2.is_deleted)
        self.assertEqual(obj_2.start_date, start_date_2)

    @pook.on
    def test_can_update_existing_history(self):
        # given
        character = CharacterFactory()
        entry_1 = CharacterCorporationHistoryFactory()
        corporation_2 = EveEntityCorporationFactory()
        start_date_2 = entry_1.start_date + dt.timedelta(days=5)
        record_id_2 = entry_1.record_id + 42
        pook.get(
            make_esi_url(f"characters/{character.character_id}/corporationhistory"),
            reply=200,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "corporation_id": corporation_2.id,
                    "record_id": record_id_2,
                    "start_date": start_date_2.isoformat(),
                },
                {
                    "corporation_id": entry_1.corporation.id,
                    "record_id": entry_1.record_id,
                    "start_date": entry_1.start_date.isoformat(),
                },
            ],
        )

        # when
        character.update_corporation_history()

        # then
        self.assertEqual(character.corporation_history.count(), 2)

        obj: CharacterCorporationHistory = character.corporation_history.get(
            record_id=record_id_2
        )
        self.assertEqual(obj.corporation, corporation_2)
        self.assertFalse(obj.is_deleted)
        self.assertEqual(obj.start_date, start_date_2)

    @pook.on
    def test_should_handle_empty_response(self):
        # given
        character = CharacterFactory()
        pook.get(
            make_esi_url(f"characters/{character.character_id}/corporationhistory"),
            reply=200,
            response_headers={"X-Pages": "1"},
            response_json=[],
        )

        # when
        character.update_corporation_history()

        # then
        self.assertEqual(character.corporation_history.count(), 0)


class TestCharacter_UpdateCharacterDetails(TestCaseWithClearCache):
    @pook.on
    def test_can_create_minimal_details(self):
        # given
        character = CharacterFactory()
        birthday = now()
        bloodline = EveBloodlineFactory()
        corporation = EveEntityCorporationFactory()
        name = "Bruce Wayne"
        race = EveRaceFactory()
        pook.get(
            make_esi_url(f"characters/{character.character_id}"),
            reply=200,
            response_json={
                "birthday": birthday.isoformat(),
                "bloodline_id": bloodline.id,
                "corporation_id": corporation.id,
                "gender": "male",
                "name": name,
                "race_id": race.id,
            },
        )

        # when
        character.update_character_details()

        # then
        details: CharacterDetails = character.details
        self.assertEqual(details.birthday, birthday)
        self.assertEqual(details.eve_bloodline, bloodline)
        self.assertEqual(details.corporation, corporation)
        self.assertEqual(details.eve_race, race)
        self.assertEqual(details.gender, CharacterDetails.GENDER_MALE)
        self.assertEqual(details.name, name)

    @pook.on
    def test_can_create_full_details(self):
        # given
        character = CharacterFactory()
        alliance = EveEntityAllianceFactory()
        birthday = now()
        bloodline = EveBloodlineFactory()
        corporation = EveEntityCorporationFactory()
        description = "description"
        faction = EveFactionFactory()
        name = "Bruce Wayne"
        race = EveRaceFactory()
        security_status = -9.9
        title = "title"
        pook.get(
            make_esi_url(f"characters/{character.character_id}"),
            reply=200,
            response_headers={"X-Pages": "1"},
            response_json={
                "alliance_id": alliance.id,
                "birthday": birthday.isoformat(),
                "bloodline_id": bloodline.id,
                "corporation_id": corporation.id,
                "description": description,
                "faction_id": faction.id,
                "gender": "male",
                "name": name,
                "race_id": race.id,
                "security_status": security_status,
                "title": title,
            },
        )

        # when
        character.update_character_details()

        # then
        details: CharacterDetails = character.details
        self.assertEqual(details.alliance, alliance)
        self.assertEqual(details.birthday, birthday)
        self.assertEqual(details.corporation, corporation)
        self.assertEqual(details.description, description)
        self.assertEqual(details.eve_bloodline, bloodline)
        self.assertEqual(details.eve_faction, faction)
        self.assertEqual(details.eve_race, race)
        self.assertEqual(details.gender, CharacterDetails.GENDER_MALE)
        self.assertEqual(details.name, name)
        self.assertEqual(details.security_status, security_status)
        self.assertEqual(details.title, title)

    @pook.on
    def test_can_update_existing_data(self):
        # given
        character = CharacterFactory()
        details = CharacterDetailsFactory(character=character)
        alliance = EveEntityAllianceFactory()
        corporation = EveEntityCorporationFactory()
        description = "description"
        faction = EveFactionFactory()
        name = "Bruce Wayne"
        security_status = -9.9
        title = "title"
        pook.get(
            make_esi_url(f"characters/{character.character_id}"),
            reply=200,
            response_headers={"X-Pages": "1"},
            response_json={
                "alliance_id": alliance.id,
                "birthday": details.birthday.isoformat(),
                "bloodline_id": details.eve_bloodline.id,
                "corporation_id": corporation.id,
                "description": description,
                "faction_id": faction.id,
                "gender": "male",
                "name": name,
                "race_id": details.eve_race.id,
                "security_status": security_status,
                "title": title,
            },
        )

        # when
        character.update_character_details()

        # then
        details.refresh_from_db()
        self.assertEqual(details.alliance, alliance)
        self.assertEqual(details.corporation, corporation)
        self.assertEqual(details.description, description)
        self.assertEqual(details.eve_faction, faction)
        self.assertEqual(details.gender, CharacterDetails.GENDER_MALE)
        self.assertEqual(details.name, name)
        self.assertEqual(details.security_status, security_status)
        self.assertEqual(details.title, title)

    @pook.on
    def test_can_handle_bug_1(self):
        # given
        character = CharacterFactory()
        EveBloodlineFactory(id=1)
        EveEntityCorporationFactory(id=2001)
        EveRaceFactory(id=1)
        pook.get(
            make_esi_url(f"characters/{character.character_id}"),
            reply=200,
            response_headers={"X-Pages": "1"},
            response_json=esi_testdata["Character"]["get_characters_character_id"][
                "1002"
            ],
        )

        # when
        character.update_character_details()

        # then
        details: CharacterDetails = character.details
        self.assertNotEqual(details.description[:2], "u'")

    @pook.on
    def test_can_handle_bug_2(self):
        # given
        character = CharacterFactory()
        EveBloodlineFactory(id=1)
        EveEntityCorporationFactory(id=2002)
        EveRaceFactory(id=1)
        pook.get(
            make_esi_url(f"characters/{character.character_id}"),
            reply=200,
            response_headers={"X-Pages": "1"},
            response_json=esi_testdata["Character"]["get_characters_character_id"][
                "1003"
            ],
        )

        # when
        character.update_character_details()

        # then
        details: CharacterDetails = character.details
        self.assertNotEqual(details.description[:2], "u'")

    @pook.on
    def test_can_handle_bug_3(self):
        # given
        character = CharacterFactory()
        EveBloodlineFactory(id=1)
        EveEntityCorporationFactory(id=2101)
        EveRaceFactory(id=1)
        pook.get(
            make_esi_url(f"characters/{character.character_id}"),
            reply=200,
            response_headers={"X-Pages": "1"},
            response_json=esi_testdata["Character"]["get_characters_character_id"][
                "1101"
            ],
        )

        # when
        character.update_character_details()

        # then
        details: CharacterDetails = character.details
        self.assertNotEqual(details.description[:2], "u'")


class TestCharacter_UpdateFwStats(TestCaseWithClearCache):
    @pook.on
    def test_should_create_stats_for_enlisted(self):
        # given
        character = CharacterFactory()
        faction = EveFactionFactory()
        enlisted_on = now()
        current_rank = 3
        highest_rank = 4
        kills_last_week = 893
        kills_total = 684350
        kills_yesterday = 136
        victory_points_last_week = 102640
        victory_points_total = 52658260
        victory_points_yesterday = 15980
        pook.get(
            make_esi_url(f"characters/{character.character_id}/fw/stats"),
            reply=200,
            response_headers={"X-Pages": "1"},
            response_json={
                "current_rank": current_rank,
                "enlisted_on": enlisted_on.isoformat(),
                "faction_id": faction.id,
                "highest_rank": highest_rank,
                "kills": {
                    "last_week": kills_last_week,
                    "total": kills_total,
                    "yesterday": kills_yesterday,
                },
                "victory_points": {
                    "last_week": victory_points_last_week,
                    "total": victory_points_total,
                    "yesterday": victory_points_yesterday,
                },
            },
        )
        # when
        character.update_fw_stats()

        # then
        stats: CharacterFwStats = character.fw_stats
        self.assertEqual(stats.current_rank, current_rank)
        self.assertEqual(stats.enlisted_on, enlisted_on)
        self.assertEqual(stats.faction, faction)
        self.assertEqual(stats.highest_rank, highest_rank)
        self.assertEqual(stats.kills_last_week, kills_last_week)
        self.assertEqual(stats.kills_total, kills_total)
        self.assertEqual(stats.kills_yesterday, kills_yesterday)
        self.assertEqual(stats.victory_points_last_week, victory_points_last_week)
        self.assertEqual(stats.victory_points_total, victory_points_total)
        self.assertEqual(stats.victory_points_yesterday, victory_points_yesterday)

    @pook.on
    def test_should_update_stats_for_enlisted(self):
        # given
        character = CharacterFactory()
        stats = CharacterFwStatsFactory(character=character)
        current_rank = 3
        highest_rank = 4
        kills_last_week = 893
        kills_total = 684350
        kills_yesterday = 136
        victory_points_last_week = 102640
        victory_points_total = 52658260
        victory_points_yesterday = 15980
        pook.get(
            make_esi_url(f"characters/{character.character_id}/fw/stats"),
            reply=200,
            response_headers={"X-Pages": "1"},
            response_json={
                "current_rank": current_rank,
                "enlisted_on": stats.enlisted_on.isoformat(),
                "faction_id": stats.faction.id,
                "highest_rank": highest_rank,
                "kills": {
                    "last_week": kills_last_week,
                    "total": kills_total,
                    "yesterday": kills_yesterday,
                },
                "victory_points": {
                    "last_week": victory_points_last_week,
                    "total": victory_points_total,
                    "yesterday": victory_points_yesterday,
                },
            },
        )

        # when
        character.update_fw_stats()

        # then
        stats.refresh_from_db()
        self.assertEqual(stats.current_rank, current_rank)
        self.assertEqual(stats.highest_rank, highest_rank)
        self.assertEqual(stats.kills_last_week, kills_last_week)
        self.assertEqual(stats.kills_total, kills_total)
        self.assertEqual(stats.kills_yesterday, kills_yesterday)
        self.assertEqual(stats.victory_points_last_week, victory_points_last_week)
        self.assertEqual(stats.victory_points_total, victory_points_total)
        self.assertEqual(stats.victory_points_yesterday, victory_points_yesterday)

    @pook.on
    def test_should_create_stats_for_unlisted(self):
        # given
        character = CharacterFactory()
        kills_last_week = 893
        kills_total = 684350
        kills_yesterday = 136
        victory_points_last_week = 102640
        victory_points_total = 52658260
        victory_points_yesterday = 15980
        pook.get(
            make_esi_url(f"characters/{character.character_id}/fw/stats"),
            reply=200,
            response_headers={"X-Pages": "1"},
            response_json={
                "kills": {
                    "last_week": kills_last_week,
                    "total": kills_total,
                    "yesterday": kills_yesterday,
                },
                "victory_points": {
                    "last_week": victory_points_last_week,
                    "total": victory_points_total,
                    "yesterday": victory_points_yesterday,
                },
            },
        )
        # when
        character.update_fw_stats()

        # then
        stats: CharacterFwStats = character.fw_stats
        self.assertEqual(stats.kills_last_week, kills_last_week)
        self.assertEqual(stats.kills_total, kills_total)
        self.assertEqual(stats.kills_yesterday, kills_yesterday)
        self.assertEqual(stats.victory_points_last_week, victory_points_last_week)
        self.assertEqual(stats.victory_points_total, victory_points_total)
        self.assertEqual(stats.victory_points_yesterday, victory_points_yesterday)


class TestCharacter_UpdateImplants(TestCaseWithClearCache):
    @pook.on
    def test_can_create_implants(self):
        character = CharacterFactory()
        implant = CyberimplantTypeFactory()
        pook.get(
            make_esi_url(f"characters/{character.character_id}/implants"),
            reply=200,
            response_json=[implant.id],
        )

        # when
        character.update_implants()

        # then
        self.assertEqual(character.implants.count(), 1)
        got = extract(character.implants, "eve_type_id")
        self.assertSetEqual(got, {implant.id})

    @pook.on
    def test_can_update_implants(self):
        character = CharacterFactory()
        implant_type = CyberimplantTypeFactory()
        pook.get(
            make_esi_url(f"characters/{character.character_id}/implants"),
            reply=200,
            response_json=[implant_type.id],
        )

        # when
        character.update_implants()

        # then
        got = extract(character.implants, "eve_type_id")
        self.assertSetEqual(got, {implant_type.id})

    @pook.on
    def test_add_implants(self):
        character = CharacterFactory()
        implant_1 = CharacterImplantFactory(character=character)
        implant_2_type = CyberimplantTypeFactory()
        pook.get(
            make_esi_url(f"characters/{character.character_id}/implants"),
            reply=200,
            response_json=[implant_2_type.id, implant_1.eve_type.id],
        )

        # when
        character.update_implants()

        # then
        got = extract(character.implants, "eve_type_id")
        self.assertSetEqual(got, {implant_2_type.id, implant_1.eve_type.id})

    @pook.on
    def test_remove_implants(self):
        character = CharacterFactory()
        implant_1 = CharacterImplantFactory(character=character)
        CharacterImplantFactory(character=character)  # to be removed
        pook.get(
            make_esi_url(f"characters/{character.character_id}/implants"),
            reply=200,
            response_json=[implant_1.eve_type.id],
        )

        # when
        character.update_implants()

        # then
        got = extract(character.implants, "eve_type_id")
        self.assertSetEqual(got, {implant_1.eve_type.id})

    @pook.on
    def test_remove_all_implants(self):
        character = CharacterFactory()
        CharacterImplantFactory(character=character)  # to be removed
        pook.get(
            make_esi_url(f"characters/{character.character_id}/implants"),
            reply=200,
            response_json=[],
        )

        # when
        character.update_implants()

        # then
        got = extract(character.implants, "eve_type_id")
        self.assertSetEqual(got, set())


class TestCharacter_UpdateJumpClones(TestCaseWithClearCache):
    @pook.on
    def test_should_create_from_scratch(self):
        # given
        character = CharacterFactory()
        clone_id = 1
        clone_location = LocationStationFactory()
        clone_name = "name"
        home_location = LocationStationFactory()
        implant_type = CyberimplantTypeFactory()
        last_clone_jump_date = now()
        last_station_change_date = now()
        pook.get(
            make_esi_url(f"characters/{character.character_id}/clones"),
            reply=200,
            response_json={
                "home_location": {
                    "location_id": home_location.id,
                    "location_type": "station",
                },
                "jump_clones": [
                    {
                        "implants": [implant_type.id],
                        "jump_clone_id": clone_id,
                        "location_id": clone_location.id,
                        "location_type": "station",
                        "name": clone_name,
                    }
                ],
                "last_clone_jump_date": last_clone_jump_date.isoformat(),
                "last_station_change_date": last_station_change_date.isoformat(),
            },
        )
        # when
        character.update_jump_clones()

        # then
        self.assertEqual(character.jump_clones.count(), 1)
        clone: CharacterJumpClone = character.jump_clones.first()
        self.assertEqual(clone.location, clone_location)
        self.assertEqual(clone.jump_clone_id, clone_id)
        self.assertEqual(clone.name, clone_name)
        got = {
            type_id for type_id in clone.implants.values_list("eve_type_id", flat=True)
        }
        self.assertEqual(got, {implant_type.id})

        info: CharacterCloneInfo = character.clone_info
        self.assertEqual(info.home_location, home_location)
        self.assertEqual(info.last_clone_jump_date, last_clone_jump_date)
        self.assertEqual(info.last_station_change_date, last_station_change_date)

    @pook.on
    def test_should_update_existing(self):
        # given
        character = CharacterFactory()
        info = CharacterCloneInfoFactory(character=character)
        jump_clone = CharacterJumpCloneFactory(character=character)
        CharacterJumpCloneImplantFactory(jump_clone=jump_clone)

        clone_id = 1
        clone_location = LocationStationFactory()
        clone_name = "name"
        home_location = LocationStationFactory()
        implant_type = CyberimplantTypeFactory()
        last_clone_jump_date = now()
        last_station_change_date = now()
        pook.get(
            make_esi_url(f"characters/{character.character_id}/clones"),
            reply=200,
            response_json={
                "home_location": {
                    "location_id": home_location.id,
                    "location_type": "station",
                },
                "jump_clones": [
                    {
                        "implants": [implant_type.id],
                        "jump_clone_id": clone_id,
                        "location_id": clone_location.id,
                        "location_type": "station",
                        "name": clone_name,
                    }
                ],
                "last_clone_jump_date": last_clone_jump_date.isoformat(),
                "last_station_change_date": last_station_change_date.isoformat(),
            },
        )
        # when
        character.update_jump_clones()

        # then
        self.assertEqual(character.jump_clones.count(), 1)
        jump_clone_2: CharacterJumpClone = character.jump_clones.first()
        self.assertEqual(jump_clone_2.location, clone_location)
        self.assertEqual(jump_clone_2.jump_clone_id, clone_id)
        self.assertEqual(jump_clone_2.name, clone_name)
        got = {
            type_id
            for type_id in jump_clone_2.implants.values_list("eve_type_id", flat=True)
        }
        self.assertEqual(got, {implant_type.id})

        info.refresh_from_db()
        self.assertEqual(info.home_location, home_location)
        self.assertEqual(info.last_clone_jump_date, last_clone_jump_date)
        self.assertEqual(info.last_station_change_date, last_station_change_date)
