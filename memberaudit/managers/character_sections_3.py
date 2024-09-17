"""Managers for character section models (3/3)."""

# pylint: disable=missing-class-docstring,not-callable

from __future__ import annotations

from typing import TYPE_CHECKING, List, Set

from django.db import models, transaction
from django.db.models import ExpressionWrapper, F
from django.utils.html import strip_tags
from esi.models import Token
from eveuniverse.models import EveEntity, EvePlanet, EveSolarSystem, EveType

from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag

from memberaudit import __title__
from memberaudit.app_settings import MEMBERAUDIT_BULK_METHODS_BATCH_SIZE
from memberaudit.decorators import fetch_token_for_character
from memberaudit.helpers import (
    UpdateSectionResult,
    data_retention_cutoff,
    eve_entity_ids_from_objs,
)
from memberaudit.managers._common import GenericUpdateComplexObjMixin
from memberaudit.providers import esi
from memberaudit.utils import (
    get_or_create_esi_or_none,
    get_or_create_or_none,
    get_or_none,
)

from ._common import GenericUpdateSimpleObjMixin

if TYPE_CHECKING:
    from memberaudit.models import Character, CharacterSkillqueueEntry

logger = LoggerAddTag(get_extension_logger(__name__), __title__)


class CharacterMiningLedgerEntryQueryset(models.QuerySet):
    def annotate_pricing(self) -> models.QuerySet:
        """Annotate price and total columns."""
        return (
            self.select_related("eve_type__market_price")
            .annotate(price=F("eve_type__market_price__average_price"))
            .annotate(
                total=ExpressionWrapper(
                    F("eve_type__market_price__average_price") * F("quantity"),
                    output_field=models.FloatField(),
                ),
            )
        )


class CharacterMiningLedgerEntryManagerBase(models.Manager):
    def update_or_create_esi(
        self, character: Character, force_update: bool = False
    ) -> UpdateSectionResult:
        """Update or create mining ledger for a character from ESI."""

        return character.update_section_if_changed(
            section=character.UpdateSection.MINING_LEDGER,
            fetch_func=self._fetch_data_from_esi,
            store_func=self._update_or_create_objs,
            force_update=force_update,
        )

    @fetch_token_for_character("esi-industry.read_character_mining.v1")
    def _fetch_data_from_esi(self, character: Character, token: Token):
        logger.info("%s: Fetching mining ledger from ESI", character)
        entries = esi.client.Industry.get_characters_character_id_mining(
            character_id=character.eve_character.character_id,
            token=token.valid_access_token(),
        ).results()
        return entries

    def _update_or_create_objs(self, character: Character, entries):
        # preload solar systems
        solar_system_ids = {entry["solar_system_id"] for entry in entries}
        for solar_system_id in solar_system_ids:
            EveSolarSystem.objects.get_or_create_esi(id=solar_system_id)

        # preload eve types
        type_ids = {entry["type_id"] for entry in entries}
        for type_id in type_ids:
            EveType.objects.get_or_create_esi(id=type_id)

        # store entries
        for entry in entries:
            self.update_or_create(
                character=character,
                date=entry["date"],
                eve_solar_system_id=entry["solar_system_id"],
                eve_type_id=entry["type_id"],
                defaults={"quantity": entry["quantity"]},
            )


CharacterMiningLedgerEntryManager = CharacterMiningLedgerEntryManagerBase.from_queryset(
    CharacterMiningLedgerEntryQueryset
)


class CharacterOnlineStatusManager(models.Manager):
    def update_or_create_esi(
        self, character: Character, force_update: bool = False
    ) -> UpdateSectionResult:
        """Update or create online status for a character from ESI."""
        return character.update_section_if_changed(
            section=character.UpdateSection.ONLINE_STATUS,
            fetch_func=self._fetch_data_from_esi,
            store_func=self._update_or_create_objs,
            force_update=force_update,
        )

    @fetch_token_for_character("esi-location.read_online.v1")
    def _fetch_data_from_esi(self, character: Character, token):
        logger.info("%s: Fetching online status from ESI", character)
        online_info = esi.client.Location.get_characters_character_id_online(
            character_id=character.eve_character.character_id,
            token=token.valid_access_token(),
        ).results()

        return online_info

    def _update_or_create_objs(self, character: Character, online_info):
        self.update_or_create(
            character=character,
            defaults={
                "last_login": online_info.get("last_login"),
                "last_logout": online_info.get("last_logout"),
                "logins": online_info.get("logins"),
            },
        )


class CharacterRoleManager(models.Manager):
    def update_or_create_esi(
        self, character: Character, force_update: bool = False
    ) -> UpdateSectionResult:
        """Update or create roles for a character from ESI."""

        return character.update_section_if_changed(
            section=character.UpdateSection.ROLES,
            fetch_func=self._fetch_data_from_esi,
            store_func=self._update_or_create_objs,
            force_update=force_update,
        )

    @fetch_token_for_character("esi-characters.read_corporation_roles.v1")
    def _fetch_data_from_esi(self, character: Character, token: Token) -> dict:
        """Update the character's roles"""

        logger.info("%s: Fetching roles from ESI", character)
        roles_data = esi.client.Character.get_characters_character_id_roles(
            character_id=character.eve_character.character_id,
            token=token.valid_access_token(),
        ).results()
        return roles_data

    @transaction.atomic()
    def _update_or_create_objs(self, character: Character, roles_data: dict):
        from memberaudit.models import CharacterRole

        Role = CharacterRole.Role
        roles_map = {
            "Account_Take_1": Role.ACCOUNT_TAKE_1,
            "Account_Take_2": Role.ACCOUNT_TAKE_2,
            "Account_Take_3": Role.ACCOUNT_TAKE_3,
            "Account_Take_4": Role.ACCOUNT_TAKE_4,
            "Account_Take_5": Role.ACCOUNT_TAKE_5,
            "Account_Take_6": Role.ACCOUNT_TAKE_6,
            "Account_Take_7": Role.ACCOUNT_TAKE_7,
            "Accountant": Role.ACCOUNTANT,
            "Auditor": Role.AUDITOR,
            "Communications_Officer": Role.COMMUNICATIONS_OFFICER,
            "Config_Equipment": Role.CONFIG_EQUIPMENT,
            "Config_Starbase_Equipment": Role.CONFIG_STARBASE_EQUIPMENT,
            "Container_Take_1": Role.CONTAINER_TAKE_1,
            "Container_Take_2": Role.CONTAINER_TAKE_2,
            "Container_Take_3": Role.CONTAINER_TAKE_3,
            "Container_Take_4": Role.CONTAINER_TAKE_4,
            "Container_Take_5": Role.CONTAINER_TAKE_5,
            "Container_Take_6": Role.CONTAINER_TAKE_6,
            "Container_Take_7": Role.CONTAINER_TAKE_7,
            "Contract_Manager": Role.CONTRACT_MANAGER,
            "Diplomat": Role.DIPLOMAT,
            "Director": Role.DIRECTOR,
            "Factory_Manager": Role.FACTORY_MANAGER,
            "Fitting_Manager": Role.FITTING_MANAGER,
            "Hangar_Query_1": Role.HANGAR_QUERY_1,
            "Hangar_Query_2": Role.HANGAR_QUERY_2,
            "Hangar_Query_3": Role.HANGAR_QUERY_3,
            "Hangar_Query_4": Role.HANGAR_QUERY_4,
            "Hangar_Query_5": Role.HANGAR_QUERY_5,
            "Hangar_Query_6": Role.HANGAR_QUERY_6,
            "Hangar_Query_7": Role.HANGAR_QUERY_7,
            "Hangar_Take_1": Role.HANGAR_TAKE_1,
            "Hangar_Take_2": Role.HANGAR_TAKE_2,
            "Hangar_Take_3": Role.HANGAR_TAKE_3,
            "Hangar_Take_4": Role.HANGAR_TAKE_4,
            "Hangar_Take_5": Role.HANGAR_TAKE_5,
            "Hangar_Take_6": Role.HANGAR_TAKE_6,
            "Hangar_Take_7": Role.HANGAR_TAKE_7,
            "Junior_Accountant": Role.JUNIOR_ACCOUNTANT,
            "Personnel_Manager": Role.PERSONNEL_MANAGER,
            "Rent_Factory_Facility": Role.RENT_FACTORY_FACILITY,
            "Rent_Office": Role.RENT_OFFICE,
            "Rent_Research_Facility": Role.RENT_RESEARCH_FACILITY,
            "Security_Officer": Role.SECURITY_OFFICER,
            "Skill_Plan_Manager": Role.SKILL_PLAN_MANAGER,
            "Starbase_Defense_Operator": Role.STARBASE_DEFENSE_OPERATOR,
            "Starbase_Fuel_Technician": Role.STARBASE_FUEL_TECHNICIAN,
            "Station_Manager": Role.STATION_MANAGER,
            "Trader": Role.TRADER,
        }
        Location = CharacterRole.Location
        location_map = {
            "roles": Location.UNIVERSAL,
            "roles_at_base": Location.BASE,
            "roles_at_hq": Location.HQ,
            "roles_at_other": Location.OTHER,
        }
        to_remove = list(
            self.filter(character=character).values_list("location", "role")
        )
        to_add = []
        for location_name, roles in roles_data.items():
            location = location_map[location_name]
            for role_name in roles:
                try:
                    role = roles_map[role_name]
                except KeyError:
                    logger.warning("Ignoring unknown role: %s", role_name)
                    continue

                if (location, role) in to_remove:
                    # if we already have the role, don't remove it
                    to_remove.remove((location, role))
                else:
                    # if we don't have the role, prepare to add it
                    to_add.append(
                        self.model(character=character, role=role, location=location)
                    )
        if to_add:
            self.bulk_create(to_add)
            logger.info("%s: Added %d new roles", character, len(to_add))

        if to_remove:
            for location, role in to_remove:
                self.filter(character=character, location=location, role=role).delete()
            logger.info("%s: Removed %d obsolete roles", character, len(to_add))


class CharacterPlanetManager(GenericUpdateComplexObjMixin, models.Manager):
    def update_or_create_esi(
        self, character: Character, force_update: bool = False
    ) -> UpdateSectionResult:
        """Update or create planets for a character from ESI."""
        return character.update_section_if_changed(
            section=character.UpdateSection.PLANETS,
            fetch_func=self._fetch_data_from_esi,
            store_func=self._update_or_create_objs,
            force_update=force_update,
        )

    @fetch_token_for_character("esi-planets.manage_planets.v1")
    def _fetch_data_from_esi(self, character: Character, token: Token) -> List[dict]:
        logger.info("%s: Fetching planets from ESI", character)
        planets_data = (
            esi.client.Planetary_Interaction.get_characters_character_id_planets(
                character_id=character.eve_character.character_id,
                token=token.valid_access_token(),
            ).results()
        )

        return planets_data

    def _update_or_create_objs(
        self, character: Character, esi_data: List[dict]
    ) -> Set[int]:
        def make_obj_from_esi_entry(character: Character, entry: dict):
            eve_planet = EvePlanet.objects.get_or_create_esi(id=entry["planet_id"])[0]
            obj = self.model(
                character=character,
                eve_planet=eve_planet,
                num_pins=entry["num_pins"],
                upgrade_level=entry["upgrade_level"],
                last_update_at=entry["last_update"],
            )
            return obj

        self._update_or_create_objs_generic(
            character,
            esi_data,
            model_key_field="eve_planet_id",
            fields_for_update=("num_pins", "upgrade_level", "last_update_at"),
            make_obj_from_esi_entry=make_obj_from_esi_entry,
        )


class CharacterShipManager(models.Manager):
    def update_or_create_esi(
        self, character: Character, force_update: bool = False
    ) -> UpdateSectionResult:
        """Update or create ship for a character from ESI."""
        return character.update_section_if_changed(
            section=character.UpdateSection.SHIP,
            fetch_func=self._fetch_data_from_esi,
            store_func=self._update_or_create_objs,
            force_update=force_update,
        )

    @fetch_token_for_character("esi-location.read_ship_type.v1")
    def _fetch_data_from_esi(self, character: Character, token: Token):
        logger.info("%s: Fetching ship from ESI", character)
        ship_info = esi.client.Location.get_characters_character_id_ship(
            character_id=character.eve_character.character_id,
            token=token.valid_access_token(),
        ).results()
        return ship_info

    def _update_or_create_objs(self, character: Character, ship_info):
        ship_type_id = ship_info.get("ship_type_id")
        if not ship_type_id:
            self.filter(character=character).delete()
            return

        eve_type, _ = EveType.objects.get_or_create_esi(id=ship_type_id)
        self.update_or_create(
            character=character,
            defaults={
                "item_id": ship_info["ship_item_id"],
                "eve_type": eve_type,
                "name": ship_info["ship_name"],
            },
        )


class CharacterSkillqueueEntryManager(models.Manager):
    def update_or_create_esi(
        self, character: Character, force_update: bool = False
    ) -> UpdateSectionResult:
        """Update or create skills queue for a character from ESI."""
        return character.update_section_if_changed(
            section=character.UpdateSection.SKILL_QUEUE,
            fetch_func=self._fetch_data_from_esi,
            store_func=self._update_or_create_objs,
            force_update=force_update,
        )

    @fetch_token_for_character("esi-skills.read_skillqueue.v1")
    def _fetch_data_from_esi(self, character: Character, token) -> List[dict]:
        logger.info("%s: Fetching skill queue from ESI", character)
        skillqueue = esi.client.Skills.get_characters_character_id_skillqueue(
            character_id=character.eve_character.character_id,
            token=token.valid_access_token(),
        ).results()

        return skillqueue

    def _update_or_create_objs(self, character: Character, skillqueue: List[dict]):
        entries = self._compile_objs(character, skillqueue)
        self._write_objs(character, entries)

    def _compile_objs(self, character: Character, skillqueue: List[dict]):
        if not skillqueue:
            return []

        entries = [
            self.model(
                character=character,
                eve_type=get_or_create_esi_or_none("skill_id", entry, EveType),
                finish_date=entry.get("finish_date"),
                finished_level=entry.get("finished_level"),
                level_end_sp=entry.get("level_end_sp"),
                level_start_sp=entry.get("level_start_sp"),
                queue_position=entry.get("queue_position"),
                start_date=entry.get("start_date"),
                training_start_sp=entry.get("training_start_sp"),
            )
            for entry in skillqueue
        ]
        return entries

    @transaction.atomic()
    def _write_objs(
        self, character: Character, entries: List[CharacterSkillqueueEntry]
    ):
        self.filter(character=character).delete()
        if not entries:
            logger.info("%s: Skill queue is empty", character)
            return

        self.bulk_create(entries, batch_size=MEMBERAUDIT_BULK_METHODS_BATCH_SIZE)
        logger.info("%s: Updated skill queue of size %s", character, len(entries))


class CharacterSkillManager(models.Manager):
    def update_or_create_esi(
        self, character: Character, force_update: bool = False
    ) -> UpdateSectionResult:
        """Update or create skills for a character from ESI."""
        return character.update_section_if_changed(
            section=character.UpdateSection.SKILLS,
            fetch_func=self._fetch_data_from_esi,
            store_func=self._update_or_create_objs,
            force_update=force_update,
        )

    @fetch_token_for_character("esi-skills.read_skills.v1")
    def _fetch_data_from_esi(self, character: Character, token: Token) -> dict:
        logger.info("%s: Fetching skills from ESI", character)
        skills_info = esi.client.Skills.get_characters_character_id_skills(
            character_id=character.eve_character.character_id,
            token=token.valid_access_token(),
        ).results()
        return skills_info

    def _preload_types(self, skills_list: dict):
        if skills_list:
            incoming_ids = set(skills_list.keys())
            existing_ids = set(self.values_list("eve_type_id", flat=True))
            new_ids = incoming_ids.difference(existing_ids)
            EveType.objects.bulk_get_or_create_esi(ids=list(new_ids))

    def _update_or_create_objs(self, character: Character, skills_info: dict):
        from memberaudit.models import CharacterSkillpoints

        CharacterSkillpoints.objects.update_or_create(
            character=character,
            defaults={
                "total": skills_info.get("total_sp"),
                "unallocated": skills_info.get("unallocated_sp"),
            },
        )

        skills_list = {
            obj["skill_id"]: obj
            for obj in skills_info.get("skills", [])
            if "skill_id" in obj
        }
        self._preload_types(skills_list)

        with transaction.atomic():
            incoming_ids = set(skills_list.keys())
            existing_ids = set(
                self.filter(character=character).values_list("eve_type_id", flat=True)
            )
            obsolete_ids = existing_ids.difference(incoming_ids)
            if obsolete_ids:
                logger.info(
                    "%s: Removing %s obsolete skills", character, len(obsolete_ids)
                )
                self.filter(character=character, eve_type_id__in=obsolete_ids).delete()

            create_ids = None
            update_ids = None
            if skills_list:
                create_ids = incoming_ids.difference(existing_ids)
                if create_ids:
                    self._create_from_dict(
                        character=character,
                        skills_list=skills_list,
                        create_ids=create_ids,
                    )

                update_ids = incoming_ids.difference(create_ids)
                if update_ids:
                    self._update_from_dict(
                        character=character,
                        skills_list=skills_list,
                        update_ids=update_ids,
                    )

            if not obsolete_ids and not create_ids and not update_ids:
                logger.info("%s: Skills have not changed", character)

    def _create_from_dict(
        self, character: Character, skills_list: dict, create_ids: set
    ):
        logger.info("%s: Storing %s new skills", character, len(create_ids))
        skills = [
            self.model(
                character=character,
                eve_type=EveType.objects.get(id=skill_info.get("skill_id")),
                active_skill_level=skill_info.get("active_skill_level"),
                skillpoints_in_skill=skill_info.get("skillpoints_in_skill"),
                trained_skill_level=skill_info.get("trained_skill_level"),
            )
            for skill_id, skill_info in skills_list.items()
            if skill_id in create_ids
        ]
        self.bulk_create(skills, batch_size=MEMBERAUDIT_BULK_METHODS_BATCH_SIZE)

    def _update_from_dict(
        self, character: Character, skills_list: dict, update_ids: set
    ):
        logger.info("%s: Updating %s skills", character, len(update_ids))
        update_pks = list(
            self.filter(character=character, eve_type_id__in=update_ids).values_list(
                "pk", flat=True
            )
        )
        skills = self.in_bulk(update_pks)
        for skill in skills.values():
            skill_info = skills_list.get(skill.eve_type_id)
            if skill_info:
                skill.active_skill_level = skill_info.get("active_skill_level")
                skill.skillpoints_in_skill = skill_info.get("skillpoints_in_skill")
                skill.trained_skill_level = skill_info.get("trained_skill_level")

        self.bulk_update(
            skills.values(),
            fields=[
                "active_skill_level",
                "skillpoints_in_skill",
                "trained_skill_level",
            ],
            batch_size=MEMBERAUDIT_BULK_METHODS_BATCH_SIZE,
        )

    def find_active_skill_level(self, skill_id: int) -> int:
        """Return active skill level for a skill or 0 if not found."""
        try:
            skill = self.get(eve_type_id=skill_id)
        except self.model.DoesNotExist:
            return 0
        return skill.active_skill_level


class CharacterSkillSetCheckManager(models.Manager):
    # TODO: Replace delete & create with update
    @transaction.atomic()
    def update_for_character(self, character: Character) -> UpdateSectionResult:
        """Update or create skill sets for a character."""
        from memberaudit.models import SkillSet

        character_skills = {
            obj["eve_type_id"]: obj["active_skill_level"]
            for obj in character.skills.values("eve_type_id", "active_skill_level")
        }
        self.filter(character=character).delete()
        skill_sets_qs = SkillSet.objects.prefetch_related(
            "skills", "skills__eve_type"
        ).all()
        skill_sets_count = skill_sets_qs.count()
        if skill_sets_count == 0:
            logger.info("%s: No skill sets defined", character)
            return UpdateSectionResult(is_changed=None, is_updated=True)

        logger.info("%s: Checking %s skill sets", character, skill_sets_count)
        skill_set_checks = [
            self.model(character=character, skill_set=skill_set)
            for skill_set in skill_sets_qs
        ]
        self.bulk_create(
            skill_set_checks, batch_size=MEMBERAUDIT_BULK_METHODS_BATCH_SIZE
        )

        # add failed recommended / required skills to objects if any
        obj_pks = list(self.filter(character=character).values_list("pk", flat=True))
        skill_set_checks = self.in_bulk(obj_pks)
        checks_by_skill_set_id = {
            obj.skill_set_id: obj for obj in skill_set_checks.values()
        }

        # required skills
        for skill_set in skill_sets_qs:
            failed_skills = self._identify_failed_skills(
                skill_set, character_skills, "required"
            )
            if failed_skills:
                checks_by_skill_set_id[skill_set.id].failed_required_skills.add(
                    *failed_skills
                )

        # required skills
        for skill_set in skill_sets_qs:
            failed_skills = self._identify_failed_skills(
                skill_set, character_skills, "recommended"
            )
            if failed_skills:
                checks_by_skill_set_id[skill_set.id].failed_recommended_skills.add(
                    *failed_skills
                )

        return UpdateSectionResult(is_changed=None, is_updated=True)

    @staticmethod
    def _identify_failed_skills(
        skill_set, character_skills: dict, level_name: str
    ) -> list:
        failed_skills = []
        kwargs = {f"{level_name}_level__isnull": False}
        for skill in skill_set.skills.filter(**kwargs):
            eve_type_id = skill.eve_type_id
            if eve_type_id not in character_skills or character_skills[
                eve_type_id
            ] < getattr(skill, f"{level_name}_level"):
                failed_skills.append(skill)

        return failed_skills


class CharacterStandingManager(GenericUpdateSimpleObjMixin, models.Manager):
    def update_or_create_esi(
        self, character: Character, force_update: bool = False
    ) -> UpdateSectionResult:
        """Update or create standing for a character from ESI."""

        return character.update_section_if_changed(
            section=character.UpdateSection.STANDINGS,
            fetch_func=self._fetch_data_from_esi,
            store_func=self._update_or_create_objs,
            force_update=force_update,
        )

    @fetch_token_for_character("esi-characters.read_standings.v1")
    def _fetch_data_from_esi(self, character: Character, token: Token) -> List[dict]:
        logger.info("%s: Fetching character standings from ESI", character)
        standings = esi.client.Character.get_characters_character_id_standings(
            character_id=character.eve_character.character_id,
            token=token.valid_access_token(),
        ).results()

        return standings

    def _update_or_create_objs(
        self, character: Character, esi_data: List[dict]
    ) -> Set[int]:
        def make_obj_from_esi_entry(character, key, value):
            obj = self.model(
                character=character,
                eve_entity=EveEntity.objects.get_or_create(id=key)[0],
                standing=value,
            )
            return obj

        return self._update_or_create_objs_generic(
            character,
            esi_data,
            esi_fields=("from_id", "standing"),
            model_fields=("eve_entity_id", "standing"),
            make_obj_from_esi_entry=make_obj_from_esi_entry,
            return_new_eve_entities=True,
        )


class CharacterTitleManager(GenericUpdateSimpleObjMixin, models.Manager):
    def update_or_create_esi(
        self, character: Character, force_update: bool = False
    ) -> UpdateSectionResult:
        """Update or create titles for a character from ESI."""

        return character.update_section_if_changed(
            section=character.UpdateSection.TITLES,
            fetch_func=self._fetch_data_from_esi,
            store_func=self._update_or_create_objs,
            force_update=force_update,
        )

    @fetch_token_for_character("esi-characters.read_titles.v1")
    def _fetch_data_from_esi(self, character: Character, token: Token) -> dict:
        """Update the character's roles"""

        logger.info("%s: Fetching titles from ESI", character)
        titles_data = esi.client.Character.get_characters_character_id_titles(
            character_id=character.eve_character.character_id,
            token=token.valid_access_token(),
        ).results()
        return titles_data

    def _update_or_create_objs(
        self, character: Character, esi_data: List[dict]
    ) -> Set[int]:
        def make_obj_from_esi_entry(character, key, value):
            name_sanitized = strip_tags(value).strip()[:100]
            obj = self.model(character=character, title_id=key, name=name_sanitized)
            return obj

        self._update_or_create_objs_generic(
            character,
            esi_data,
            esi_fields=("title_id", "name"),
            model_fields=("title_id", "name"),
            make_obj_from_esi_entry=make_obj_from_esi_entry,
        )


class CharacterWalletBalanceManager(models.Manager):
    def update_or_create_esi(
        self, character: Character, force_update: bool = False
    ) -> UpdateSectionResult:
        """Update or create wallet balance for a character from ESI."""
        return character.update_section_if_changed(
            section=character.UpdateSection.WALLET_BALLANCE,
            fetch_func=self._fetch_data_from_esi,
            store_func=self._update_or_create_objs,
            force_update=force_update,
        )

    @fetch_token_for_character("esi-wallet.read_character_wallet.v1")
    def _fetch_data_from_esi(self, character: Character, token):
        logger.info("%s: Fetching wallet balance from ESI", character)
        balance = esi.client.Wallet.get_characters_character_id_wallet(
            character_id=character.eve_character.character_id,
            token=token.valid_access_token(),
        ).results()
        return balance

    def _update_or_create_objs(self, character: Character, balance):
        self.update_or_create(character=character, defaults={"total": balance})


class CharacterWalletJournalEntryManager(models.Manager):
    def update_or_create_esi(
        self, character: Character, force_update: bool = False
    ) -> UpdateSectionResult:
        """Update or create wallet journal entries for character from ESI.

        Note: Does not update unknown EveEntities.
        """
        return character.update_section_if_changed(
            section=character.UpdateSection.WALLET_JOURNAL,
            fetch_func=self._fetch_data_from_esi,
            store_func=self._update_or_create_objs,
            force_update=force_update,
        )

    @fetch_token_for_character("esi-wallet.read_character_wallet.v1")
    def _fetch_data_from_esi(self, character: Character, token: Token):
        logger.info("%s: Fetching wallet journal from ESI", character)
        journal = esi.client.Wallet.get_characters_character_id_wallet_journal(
            character_id=character.eve_character.character_id,
            token=token.valid_access_token(),
        ).results()
        return journal

    def _update_or_create_objs(self, character: Character, journal):
        cutoff_datetime = data_retention_cutoff()
        entries_list = {
            obj.get("id"): obj
            for obj in journal
            if cutoff_datetime is None or obj.get("date") > cutoff_datetime
        }
        if cutoff_datetime:
            self.filter(character=character, date__lt=cutoff_datetime).delete()

        with transaction.atomic():
            incoming_ids = set(entries_list.keys())
            existing_ids = set(self.values_list("entry_id", flat=True))
            create_ids = incoming_ids.difference(existing_ids)
            if not create_ids:
                logger.info("%s: No new wallet journal entries", character)
                return set()

            logger.info(
                "%s: Adding %s new wallet journal entries", character, len(create_ids)
            )
            entries = [
                self.model(
                    character=character,
                    entry_id=entry_id,
                    amount=row.get("amount"),
                    balance=row.get("balance"),
                    context_id=row.get("context_id"),
                    context_id_type=(
                        self.model.match_context_type_id(row.get("context_id_type"))
                    ),
                    date=row.get("date"),
                    description=row.get("description"),
                    first_party=get_or_create_or_none("first_party_id", row, EveEntity),
                    reason=row.get("reason", ""),
                    ref_type=row.get("ref_type"),
                    second_party=get_or_create_or_none(
                        "second_party_id", row, EveEntity
                    ),
                    tax=row.get("tax"),
                    tax_receiver=row.get("tax_receiver"),
                )
                for entry_id, row in entries_list.items()
                if entry_id in create_ids
            ]
            self.bulk_create(entries, batch_size=MEMBERAUDIT_BULK_METHODS_BATCH_SIZE)

        return eve_entity_ids_from_objs(entries)


class CharacterWalletTransactionManager(models.Manager):
    def update_or_create_esi(
        self, character: Character, force_update: bool = False
    ) -> UpdateSectionResult:
        """Update or create wallet transactions for a character from ESI."""
        return character.update_section_if_changed(
            section=character.UpdateSection.WALLET_TRANSACTIONS,
            fetch_func=self._fetch_data_from_esi,
            store_func=self._update_or_create_objs,
            force_update=force_update,
        )

    @fetch_token_for_character("esi-wallet.read_character_wallet.v1")
    def _fetch_data_from_esi(self, character: Character, token):
        logger.info("%s: Fetching wallet transactions from ESI", character)
        transactions = (
            esi.client.Wallet.get_characters_character_id_wallet_transactions(
                character_id=character.eve_character.character_id,
                token=token.valid_access_token(),
            ).results()
        )
        return transactions

    @fetch_token_for_character("esi-universe.read_structures.v1")
    def _update_or_create_objs(
        self, character: Character, token: Token, transactions
    ) -> Set[int]:
        from memberaudit.models import Location

        cutoff_datetime = data_retention_cutoff()
        transaction_list = {
            obj.get("transaction_id"): obj
            for obj in transactions
            if cutoff_datetime is None or obj.get("date") > cutoff_datetime
        }
        if cutoff_datetime:
            self.filter(character=character, date__lt=cutoff_datetime).delete()

        incoming_location_ids = {
            row.get("location_id") for row in transaction_list.values()
        }
        Location.objects.create_missing_esi(incoming_location_ids, token)
        type_ids = {row.get("type_id") for row in transaction_list.values()}
        EveType.objects.bulk_get_or_create_esi(ids=list(type_ids))

        eve_entity_ids = self._bulk_update_or_create(character, transaction_list)
        return eve_entity_ids

    @transaction.atomic()
    def _bulk_update_or_create(
        self, character: Character, transaction_list
    ) -> Set[int]:
        from memberaudit.models import Location

        incoming_ids = set(transaction_list.keys())
        existing_ids = set(self.values_list("transaction_id", flat=True))
        create_ids = incoming_ids.difference(existing_ids)
        if not create_ids:
            logger.info("%s: No new wallet transactions", character)
            return set()

        logger.info(
            "%s: Adding %s new wallet transactions",
            character,
            len(create_ids),
        )
        entries = []
        for transaction_id, row in transaction_list.items():
            if transaction_id in create_ids:
                try:
                    journal_entry = character.wallet_journal.get(
                        entry_id=row.get("journal_ref_id")
                    )
                except character.wallet_journal.model.DoesNotExist:
                    journal_entry = None
                entries.append(
                    self.model(
                        character=character,
                        transaction_id=transaction_id,
                        client=get_or_create_or_none("client_id", row, EveEntity),
                        date=row.get("date"),
                        is_buy=row.get("is_buy"),
                        is_personal=row.get("is_personal"),
                        journal_ref=journal_entry,
                        location=get_or_none("location_id", row, Location),
                        eve_type=EveType.objects.get(id=row.get("type_id")),
                        quantity=row.get("quantity"),
                        unit_price=row.get("unit_price"),
                    )
                )
        self.bulk_create(entries, batch_size=MEMBERAUDIT_BULK_METHODS_BATCH_SIZE)
        return eve_entity_ids_from_objs(entries)
