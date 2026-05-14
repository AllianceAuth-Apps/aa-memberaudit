import datetime as dt
from http import HTTPStatus
from unittest.mock import patch

import pook

from django.utils.timezone import now
from eveuniverse.tests.testdata.factories_2 import (
    EvePlanetFactory,
    EveSolarSystemFactory,
    EveTypeFactory,
    ShipTypeFactory,
)

from app_utils.testing import NoSocketsTestCase

from memberaudit.models import (
    CharacterMiningLedgerEntry,
    CharacterOnlineStatus,
    CharacterPlanet,
    CharacterRole,
    CharacterShip,
    CharacterSkill,
    CharacterSkillpoints,
    CharacterSkillqueueEntry,
)
from memberaudit.tests.testdata.factories_2 import (
    CharacterFactory,
    CharacterMiningLedgerEntryFactory,
    CharacterOnlineStatusFactory,
    CharacterPlanetFactory,
    CharacterRoleFactory,
    CharacterShipFactory,
    CharacterSkillFactory,
    CharacterSkillqueueEntryFactory,
    NavigationSkillTypeFactory,
    make_esi_url,
)
from memberaudit.tests.utils import TestCaseWithClearCache, extract

MODELS_PATH = "memberaudit.models"


class TestCharacter_UpdateMiningLedger(TestCaseWithClearCache):
    @pook.on
    def test_should_add_new_entry_from_scratch(self):
        # given
        character = CharacterFactory()
        solar_system = EveSolarSystemFactory()
        ore_type = EveTypeFactory()
        date = now().date()
        quantity = 7004
        pook.get(
            make_esi_url(f"characters/{character.character_id}/mining"),
            reply=HTTPStatus.OK,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "date": date.isoformat(),
                    "quantity": quantity,
                    "solar_system_id": solar_system.id,
                    "type_id": ore_type.id,
                }
            ],
        )

        # when
        character.update_mining_ledger()

        # then
        self.assertEqual(character.mining_ledger.count(), 1)
        obj: CharacterMiningLedgerEntry = character.mining_ledger.first()
        self.assertEqual(obj.date, date)
        self.assertEqual(obj.eve_type, ore_type)
        self.assertEqual(obj.eve_solar_system, solar_system)
        self.assertEqual(obj.quantity, quantity)

    @pook.on
    def test_should_update_existing_entries(self):
        # given
        character = CharacterFactory()
        entry = CharacterMiningLedgerEntryFactory(character=character)
        quantity = 7004
        pook.get(
            make_esi_url(f"characters/{character.character_id}/mining"),
            reply=HTTPStatus.OK,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "date": entry.date.isoformat(),
                    "quantity": quantity,
                    "solar_system_id": entry.eve_solar_system.id,
                    "type_id": entry.eve_type.id,
                }
            ],
        )

        # when
        character.update_mining_ledger()

        # then
        entry.refresh_from_db()
        self.assertEqual(entry.quantity, quantity)


class TestCharacter_UpdateOnlineStatus(TestCaseWithClearCache):
    @pook.on
    def test_create_online_status(self):
        # given
        character = CharacterFactory()
        last_login = now() - dt.timedelta(hours=3)
        last_logout = now()
        logins = 7
        pook.get(
            make_esi_url(f"characters/{character.character_id}/online"),
            reply=HTTPStatus.OK,
            response_json={
                "last_login": last_login.isoformat(),
                "last_logout": last_logout.isoformat(),
                "logins": logins,
                "online": True,
            },
        )

        # when
        character.update_online_status()

        # then
        status: CharacterOnlineStatus = character.online_status
        self.assertEqual(status.last_login, last_login)
        self.assertEqual(status.last_logout, last_logout)
        self.assertEqual(status.logins, logins)

    @pook.on
    def test_update_existing_online_status(self):
        # given
        character = CharacterFactory()
        status = CharacterOnlineStatusFactory(character=character)
        last_login = now() - dt.timedelta(hours=3)
        last_logout = now()
        logins = 7
        pook.get(
            make_esi_url(f"characters/{character.character_id}/online"),
            reply=HTTPStatus.OK,
            response_json={
                "last_login": last_login.isoformat(),
                "last_logout": last_logout.isoformat(),
                "logins": logins,
                "online": True,
            },
        )

        # when
        character.update_online_status()

        # then
        status.refresh_from_db()
        self.assertEqual(status.last_login, last_login)
        self.assertEqual(status.last_logout, last_logout)
        self.assertEqual(status.logins, logins)


class TestCharacter_UpdatePlanets(TestCaseWithClearCache):
    @pook.on
    def test_should_create_new_planets_from_scratch(self):
        # given
        character = CharacterFactory()
        eve_planet = EvePlanetFactory()
        last_update = now()
        num_pins = 20
        upgrade_level = 2
        pook.get(
            make_esi_url(f"characters/{character.character_id}/planets"),
            reply=HTTPStatus.OK,
            response_json=[
                {
                    "last_update": last_update.isoformat(),
                    "num_pins": num_pins,
                    "owner_id": character.character_id,
                    "planet_id": eve_planet.id,
                    "planet_type": "barren",
                    "solar_system_id": eve_planet.eve_solar_system.id,
                    "upgrade_level": upgrade_level,
                }
            ],
        )

        # when
        character.update_planets()

        # then
        self.assertEqual(character.planets.count(), 1)
        planet: CharacterPlanet = character.planets.first()
        self.assertEqual(planet.eve_planet, eve_planet)
        self.assertEqual(planet.last_update_at, last_update)
        self.assertEqual(planet.num_pins, num_pins)
        self.assertEqual(planet.upgrade_level, upgrade_level)

    @pook.on
    def test_should_update_existing_planets(self):
        # given
        character = CharacterFactory()
        planet = CharacterPlanetFactory(character=character)
        last_update = now()
        num_pins = 20
        upgrade_level = 2
        pook.get(
            make_esi_url(f"characters/{character.character_id}/planets"),
            reply=HTTPStatus.OK,
            response_json=[
                {
                    "last_update": last_update.isoformat(),
                    "num_pins": num_pins,
                    "owner_id": character.character_id,
                    "planet_id": planet.eve_planet.id,
                    "planet_type": "barren",
                    "solar_system_id": planet.eve_planet.eve_solar_system.id,
                    "upgrade_level": upgrade_level,
                }
            ],
        )

        # when
        character.update_planets()

        # then
        planet.refresh_from_db()
        self.assertEqual(planet.last_update_at, last_update)
        self.assertEqual(planet.num_pins, num_pins)
        self.assertEqual(planet.upgrade_level, upgrade_level)

    @pook.on
    def test_should_remove_stale_planets(self):
        # given
        character = CharacterFactory()
        CharacterPlanetFactory(character=character)  # to be removed
        planet = CharacterPlanetFactory(character=character)
        pook.get(
            make_esi_url(f"characters/{character.character_id}/planets"),
            reply=HTTPStatus.OK,
            response_json=[
                {
                    "last_update": planet.last_update_at.isoformat(),
                    "num_pins": planet.num_pins,
                    "owner_id": character.character_id,
                    "planet_id": planet.eve_planet.id,
                    "planet_type": "barren",
                    "solar_system_id": planet.eve_planet.eve_solar_system.id,
                    "upgrade_level": planet.upgrade_level,
                }
            ],
        )

        # when
        character.update_planets()

        # then
        got = extract(character.planets, "eve_planet__id")
        want = {planet.eve_planet.id}
        self.assertSetEqual(got, want)


@patch(MODELS_PATH + ".characters.MEMBERAUDIT_FEATURE_ROLES_ENABLED", True)
class TestCharacter_UpdateRoles(TestCaseWithClearCache):
    @pook.on
    def test_should_add_new_role_from_scratch(self):
        # given
        character = CharacterFactory()
        pook.get(
            make_esi_url(f"characters/{character.character_id}/roles"),
            reply=HTTPStatus.OK,
            response_json={
                "roles": ["Station_Manager"],
            },
        )

        # when
        character.update_roles()

        # then
        self.assertEqual(character.roles.count(), 1)
        obj: CharacterRole = character.roles.first()
        self.assertEqual(obj.role, CharacterRole.Role.STATION_MANAGER)
        self.assertEqual(obj.location, CharacterRole.Location.UNIVERSAL)

    @pook.on
    def test_should_update_existing_roles(self):
        # given
        character = CharacterFactory()
        CharacterRoleFactory(
            character=character, role=CharacterRole.Role.DIPLOMAT
        )  # to be removed
        CharacterRoleFactory(
            character=character, role=CharacterRole.Role.COMMUNICATIONS_OFFICER
        )  # to be kept
        pook.get(
            make_esi_url(f"characters/{character.character_id}/roles"),
            reply=HTTPStatus.OK,
            response_json={
                "roles": ["Station_Manager", "Communications_Officer"],
            },
        )

        # when
        character.update_roles()

        # then
        got = extract(character.roles, "role")
        want = {
            CharacterRole.Role.COMMUNICATIONS_OFFICER,
            CharacterRole.Role.STATION_MANAGER,
        }
        self.assertSetEqual(got, want)

    @pook.on
    def test_should_support_all_roles(self):
        # given
        character = CharacterFactory()
        pook.get(
            make_esi_url(f"characters/{character.character_id}/roles"),
            reply=HTTPStatus.OK,
            response_json={
                "roles": [
                    "Account_Take_1",
                    "Account_Take_2",
                    "Account_Take_3",
                    "Account_Take_4",
                    "Account_Take_5",
                    "Account_Take_6",
                    "Account_Take_7",
                    "Accountant",
                    "Auditor",
                    "Brand_Manager",
                    "Communications_Officer",
                    "Config_Equipment",
                    "Config_Starbase_Equipment",
                    "Container_Take_1",
                    "Container_Take_2",
                    "Container_Take_3",
                    "Container_Take_4",
                    "Container_Take_5",
                    "Container_Take_6",
                    "Container_Take_7",
                    "Contract_Manager",
                    "Deliveries_Container_Take",
                    "Deliveries_Query",
                    "Deliveries_Take",
                    "Diplomat",
                    "Director",
                    "Factory_Manager",
                    "Fitting_Manager",
                    "Hangar_Query_1",
                    "Hangar_Query_2",
                    "Hangar_Query_3",
                    "Hangar_Query_4",
                    "Hangar_Query_5",
                    "Hangar_Query_6",
                    "Hangar_Query_7",
                    "Hangar_Take_1",
                    "Hangar_Take_2",
                    "Hangar_Take_3",
                    "Hangar_Take_4",
                    "Hangar_Take_5",
                    "Hangar_Take_6",
                    "Hangar_Take_7",
                    "Junior_Accountant",
                    "Personnel_Manager",
                    "Project_Manager",
                    "Rent_Factory_Facility",
                    "Rent_Office",
                    "Rent_Research_Facility",
                    "Security_Officer",
                    "Skill_Plan_Manager",
                    "Starbase_Defense_Operator",
                    "Starbase_Fuel_Technician",
                    "Station_Manager",
                    "Trader",
                ],
            },
        )

        # when
        character.update_roles()

        # then
        self.assertEqual(character.roles.count(), 54)


class TestCharacter_UpdateShip(TestCaseWithClearCache):
    @pook.on
    def test_should_create_new(self):
        # given
        character = CharacterFactory()
        ship_item_id = 1000000016991
        ship_name = "Shooter Boy"
        ship_type = ShipTypeFactory()
        pook.get(
            make_esi_url(f"characters/{character.character_id}/ship"),
            reply=HTTPStatus.OK,
            response_json={
                "ship_item_id": ship_item_id,
                "ship_name": ship_name,
                "ship_type_id": ship_type.id,
            },
        )

        # when
        character.update_ship()

        # then
        ship: CharacterShip = character.ship
        self.assertEqual(ship.item_id, ship_item_id)
        self.assertEqual(ship.eve_type, ship_type)
        self.assertEqual(ship.name, ship_name)

    @pook.on
    def test_should_update_existing(self):
        # given
        character = CharacterFactory()
        ship = CharacterShipFactory(character=character)
        ship_item_id = 1000000016991
        ship_name = "Shooter Boy"
        ship_type = ShipTypeFactory()
        pook.get(
            make_esi_url(f"characters/{character.character_id}/ship"),
            reply=HTTPStatus.OK,
            response_json={
                "ship_item_id": ship_item_id,
                "ship_name": ship_name,
                "ship_type_id": ship_type.id,
            },
        )

        # when
        character.update_ship()

        # then
        ship.refresh_from_db()
        self.assertEqual(ship.item_id, ship_item_id)
        self.assertEqual(ship.eve_type, ship_type)
        self.assertEqual(ship.name, ship_name)

    @pook.on
    def test_should_ignore_error_500(self):
        # given
        character = CharacterFactory()
        ship_item_id = 1000000016991
        ship_name = "Shooter Boy"
        ship_type = ShipTypeFactory()
        ship = CharacterShipFactory(
            character=character,
            item_id=ship_item_id,
            name=ship_name,
            eve_type=ship_type,
        )
        pook.get(
            make_esi_url(f"characters/{character.character_id}/ship"),
            reply=HTTPStatus.INTERNAL_SERVER_ERROR,
            response_json={
                "error": "Undefined 404 response. Original message: Ship not found"
            },
        )

        # when
        character.update_ship()

        # then
        ship.refresh_from_db()
        self.assertEqual(ship.item_id, ship_item_id)
        self.assertEqual(ship.eve_type, ship_type)
        self.assertEqual(ship.name, ship_name)


class TestCharacter_UpdateSkills(TestCaseWithClearCache):
    @pook.on
    def test_can_create_new_skills(self):
        # given
        character = CharacterFactory()
        skill_type = NavigationSkillTypeFactory()
        active_skill_level = 1
        skillpoints_in_skill = 1000
        trained_skill_level = 2
        total_sp = 10_000_000
        unallocated_sp = 1_000_000
        pook.get(
            make_esi_url(f"characters/{character.character_id}/skills"),
            reply=HTTPStatus.OK,
            response_json={
                "skills": [
                    {
                        "active_skill_level": active_skill_level,
                        "skill_id": skill_type.id,
                        "skillpoints_in_skill": skillpoints_in_skill,
                        "trained_skill_level": trained_skill_level,
                    }
                ],
                "total_sp": total_sp,
                "unallocated_sp": unallocated_sp,
            },
        )

        # when
        character.update_skills()

        # then
        skillpoints: CharacterSkillpoints = character.skillpoints
        self.assertEqual(skillpoints.total, total_sp)
        self.assertEqual(skillpoints.unallocated, unallocated_sp)

        self.assertEqual(character.skills.count(), 1)
        skill: CharacterSkill = character.skills.first()
        self.assertEqual(skill.active_skill_level, active_skill_level)
        self.assertEqual(skill.eve_type, skill_type)
        self.assertEqual(skill.skillpoints_in_skill, skillpoints_in_skill)
        self.assertEqual(skill.trained_skill_level, trained_skill_level)

    @pook.on
    def test_can_update_existing_skills(self):
        # given
        character = CharacterFactory()
        skill = CharacterSkillFactory(character=character)
        active_skill_level = 1
        skillpoints_in_skill = 1000
        trained_skill_level = 2
        total_sp = 10_000_000
        unallocated_sp = 1_000_000
        pook.get(
            make_esi_url(f"characters/{character.character_id}/skills"),
            reply=HTTPStatus.OK,
            response_json={
                "skills": [
                    {
                        "active_skill_level": active_skill_level,
                        "skill_id": skill.eve_type.id,
                        "skillpoints_in_skill": skillpoints_in_skill,
                        "trained_skill_level": trained_skill_level,
                    }
                ],
                "total_sp": total_sp,
                "unallocated_sp": unallocated_sp,
            },
        )

        # when
        character.update_skills()

        # then

        skill.refresh_from_db()
        self.assertEqual(skill.active_skill_level, active_skill_level)
        self.assertEqual(skill.skillpoints_in_skill, skillpoints_in_skill)
        self.assertEqual(skill.trained_skill_level, trained_skill_level)

    @pook.on
    def test_can_delete_obsolete_skills(self):
        # given
        character = CharacterFactory()
        CharacterSkillFactory(character=character)  # to be removed
        skill_type = NavigationSkillTypeFactory()
        active_skill_level = 1
        skillpoints_in_skill = 1000
        trained_skill_level = 2
        total_sp = 10_000_000
        unallocated_sp = 1_000_000
        pook.get(
            make_esi_url(f"characters/{character.character_id}/skills"),
            reply=HTTPStatus.OK,
            response_json={
                "skills": [
                    {
                        "active_skill_level": active_skill_level,
                        "skill_id": skill_type.id,
                        "skillpoints_in_skill": skillpoints_in_skill,
                        "trained_skill_level": trained_skill_level,
                    }
                ],
                "total_sp": total_sp,
                "unallocated_sp": unallocated_sp,
            },
        )

        # when
        character.update_skills()

        # then
        got = extract(character.skills, "eve_type__id")
        want = {skill_type.id}
        self.assertSetEqual(got, want)


class TestCharacter_UpdateSkillQueue(TestCaseWithClearCache):
    @pook.on
    def test_can_create_new_entry(self):
        # given
        character = CharacterFactory()
        finished_level = 4
        level_end_sp = 1000
        level_start_sp = 100
        training_start_sp = 50
        queue_position = 1
        skill_type = NavigationSkillTypeFactory()
        start_date = now()
        finish_date = start_date + dt.timedelta(hours=1)
        pook.get(
            make_esi_url(f"characters/{character.character_id}/skillqueue"),
            reply=HTTPStatus.OK,
            response_json=[
                {
                    "finish_date": finish_date.isoformat(),
                    "finished_level": finished_level,
                    "level_end_sp": level_end_sp,
                    "level_start_sp": level_start_sp,
                    "queue_position": queue_position,
                    "skill_id": skill_type.id,
                    "start_date": start_date.isoformat(),
                    "training_start_sp": training_start_sp,
                }
            ],
        )
        # when
        character.update_skill_queue()

        # then
        self.assertEqual(character.skillqueue.count(), 1)
        entry: CharacterSkillqueueEntry = character.skillqueue.first()
        self.assertEqual(entry.eve_type, skill_type)
        self.assertEqual(entry.finish_date, finish_date)
        self.assertEqual(entry.finished_level, finished_level)
        self.assertEqual(entry.level_end_sp, level_end_sp)
        self.assertEqual(entry.level_start_sp, level_start_sp)
        self.assertEqual(entry.start_date, start_date)
        self.assertEqual(entry.training_start_sp, training_start_sp)

    @pook.on
    def test_can_update_existing_entry(self):
        # given
        character = CharacterFactory()
        entry_1 = CharacterSkillqueueEntryFactory(character=character)
        finished_level = 4
        level_end_sp = 1000
        level_start_sp = 100
        training_start_sp = 50
        queue_position = 1
        start_date = now()
        finish_date = start_date + dt.timedelta(hours=1)
        pook.get(
            make_esi_url(f"characters/{character.character_id}/skillqueue"),
            reply=HTTPStatus.OK,
            response_json=[
                {
                    "finish_date": finish_date.isoformat(),
                    "finished_level": finished_level,
                    "level_end_sp": level_end_sp,
                    "level_start_sp": level_start_sp,
                    "queue_position": queue_position,
                    "skill_id": entry_1.eve_type.id,
                    "start_date": start_date.isoformat(),
                    "training_start_sp": training_start_sp,
                }
            ],
        )
        # when
        character.update_skill_queue()

        # then
        self.assertEqual(character.skillqueue.count(), 1)
        entry_2: CharacterSkillqueueEntry = character.skillqueue.first()
        self.assertEqual(entry_2.finish_date, finish_date)
        self.assertEqual(entry_2.finished_level, finished_level)
        self.assertEqual(entry_2.level_end_sp, level_end_sp)
        self.assertEqual(entry_2.level_start_sp, level_start_sp)
        self.assertEqual(entry_2.start_date, start_date)
        self.assertEqual(entry_2.training_start_sp, training_start_sp)

    @pook.on
    def test_should_remove_stale_entries(self):
        # given
        character = CharacterFactory()
        CharacterSkillqueueEntryFactory(character=character)
        pook.get(
            make_esi_url(f"characters/{character.character_id}/skillqueue"),
            reply=HTTPStatus.OK,
            response_json=[],
        )
        # when
        character.update_skill_queue()

        # then
        self.assertEqual(character.skillqueue.count(), 0)


class TestCharacterSkillqueueEntryManager(NoSocketsTestCase):
    def test_return_skills_when_training_is_active(self):
        # given
        character = CharacterFactory()
        CharacterSkillqueueEntryFactory(
            character=character,
            finish_date=now() + dt.timedelta(days=1),
            finished_level=4,
            start_date=now() - dt.timedelta(days=1),
        )

        # when
        got = character.skillqueue.active_skills()

        # then
        self.assertEqual(got.count(), 1)

    def test_should_return_empty_when_training_not_active(self):
        # given
        character = CharacterFactory()
        CharacterSkillqueueEntryFactory(
            finished_level=4,
            start_date=now() - dt.timedelta(days=1),
        )

        # when
        got = character.skillqueue.active_skills()

        # then
        self.assertEqual(got.count(), 0)
