"""Managers for character section models (2/3)."""

# pylint: disable=missing-class-docstring

from __future__ import annotations

import ast
from typing import TYPE_CHECKING, Any, Dict, List, Set

from bravado.exception import HTTPNotFound

from django.db import models, transaction
from esi.models import Token
from eveuniverse.models import (
    EveAncestry,
    EveBloodline,
    EveEntity,
    EveFaction,
    EveRace,
    EveSolarSystem,
    EveType,
)

from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag

from memberaudit import __title__
from memberaudit.app_settings import (
    MEMBERAUDIT_BULK_METHODS_BATCH_SIZE,
    MEMBERAUDIT_MAX_MAILS,
)
from memberaudit.core.xml_converter import eve_xml_to_html
from memberaudit.decorators import fetch_token_for_character
from memberaudit.helpers import UpdateSectionResult, data_retention_cutoff
from memberaudit.models._helpers import store_character_data_to_disk_when_enabled
from memberaudit.providers import esi
from memberaudit.utils import (
    get_or_create_esi_or_none,
    get_or_create_or_none,
    get_or_none,
)

from ._common import GenericUpdateComplexObjMixin, GenericUpdateSimpleObjMixin

if TYPE_CHECKING:
    from memberaudit.models import Character, CharacterMail

logger = LoggerAddTag(get_extension_logger(__name__), __title__)


class CharacterCorporationHistoryManager(GenericUpdateComplexObjMixin, models.Manager):
    def update_or_create_esi(
        self, character: Character, force_update: bool = False
    ) -> UpdateSectionResult:
        """Update or create corporation history for character."""

        return character.update_section_if_changed(
            section=character.UpdateSection.CORPORATION_HISTORY,
            fetch_func=self._fetch_data_from_esi,
            store_func=self._update_or_create_objs,
            force_update=force_update,
        )

    def _fetch_data_from_esi(self, character: Character) -> List[dict]:
        logger.info("%s: Fetching corporation history from ESI", character)
        history = esi.client.Character.get_characters_character_id_corporationhistory(
            character_id=character.eve_character.character_id,
        ).results()

        return history

    def _update_or_create_objs(
        self, character: Character, esi_data: List[dict]
    ) -> Set[int]:
        def make_obj_from_esi_entry(character: Character, entry: dict):
            corporation = get_or_create_or_none("corporation_id", entry, EveEntity)
            obj = self.model(
                character=character,
                record_id=entry["record_id"],
                corporation=corporation,
                is_deleted=entry.get("is_deleted"),
                start_date=entry["start_date"],
            )
            return obj

        new_eve_entity_ids = self._update_or_create_objs_generic(
            character,
            esi_data,
            model_key_field="record_id",
            fields_for_update=("corporation_id", "is_deleted", "start_date"),
            make_obj_from_esi_entry=make_obj_from_esi_entry,
            return_new_eve_entities=True,
        )
        return new_eve_entity_ids


class CharacterDetailsManager(models.Manager):
    def update_or_create_esi(
        self, character: Character, force_update: bool = False
    ) -> UpdateSectionResult:
        """Update or create character details from ESI."""
        return character.update_section_if_changed(
            section=character.UpdateSection.CHARACTER_DETAILS,
            fetch_func=self._fetch_data_from_esi,
            store_func=self._update_or_create_objs,
            force_update=force_update,
        )

    def _fetch_data_from_esi(self, character: Character):
        logger.info("%s: Fetching character details from ESI", character)
        details = esi.client.Character.get_characters_character_id(
            character_id=character.eve_character.character_id,
        ).results()

        return details

    def _update_or_create_objs(self, character: Character, details) -> Set[int]:
        description = (
            details.get("description", "") if details.get("description") else ""
        )

        # TODO: remove when fixed
        # temporary fix to address u-bug in ESI endpoint for character bio
        # workaround to address syntax error bug (#77)
        # see also: https://github.com/esi/esi-issues/issues/1265
        if description and description.startswith("u'") and description.endswith("'"):
            try:
                description = ast.literal_eval(description)
            except SyntaxError:
                logger.warning("Failed to convert description with u-bug.")
                description = ""

        if description:
            eve_xml_to_html(description)  # resolve entities early
        gender = (
            self.model.GENDER_MALE
            if details.get("gender") == "male"
            else self.model.GENDER_FEMALE
        )

        # TODO: Remove once issue is fixed
        # Workaround because of ESI issue #1264
        eve_ancestry = get_or_none("ancestry_id", details, EveAncestry)

        obj, _ = self.update_or_create(
            character=character,
            defaults={
                "alliance": get_or_create_or_none("alliance_id", details, EveEntity),
                "birthday": details.get("birthday"),
                "eve_ancestry": eve_ancestry,
                "eve_bloodline": get_or_create_esi_or_none(
                    "bloodline_id", details, EveBloodline
                ),
                "eve_faction": get_or_create_esi_or_none(
                    "faction_id", details, EveFaction
                ),
                "eve_race": get_or_create_esi_or_none("race_id", details, EveRace),
                "corporation": get_or_create_or_none(
                    "corporation_id", details, EveEntity
                ),
                "description": description,
                "gender": gender,
                "name": details.get("name", ""),
                "security_status": details.get("security_status"),
                "title": details.get("title", "") if details.get("title") else "",
            },
        )
        return obj.eve_entity_ids()


class CharacterFwStatsManager(models.Manager):
    def update_or_create_esi(
        self, character: Character, force_update: bool = False
    ) -> UpdateSectionResult:
        """Update or create fw stats for a character from ESI."""

        return character.update_section_if_changed(
            section=character.UpdateSection.FW_STATS,
            fetch_func=self._fetch_data_from_esi,
            store_func=self._update_or_create_objs,
            force_update=force_update,
        )

    @fetch_token_for_character("esi-characters.read_fw_stats.v1")
    def _fetch_data_from_esi(self, character: Character, token: Token):
        logger.info("%s: Fetching FW stats from ESI", character)
        stats = esi.client.Faction_Warfare.get_characters_character_id_fw_stats(
            character_id=character.eve_character.character_id,
            token=token.valid_access_token(),
        ).results()
        return stats

    def _update_or_create_objs(self, character: Character, stats: dict):
        if faction_id := stats.get("faction_id"):
            faction, _ = EveFaction.objects.get_or_create_esi(id=faction_id)
        else:
            faction = None
        self.update_or_create(
            character=character,
            defaults={
                "current_rank": stats.get("current_rank"),
                "enlisted_on": stats.get("enlisted_on"),
                "faction": faction,
                "highest_rank": stats.get("highest_rank"),
                "kills_last_week": stats["kills"]["last_week"],
                "kills_total": stats["kills"]["total"],
                "kills_yesterday": stats["kills"]["yesterday"],
                "victory_points_last_week": stats["victory_points"]["last_week"],
                "victory_points_total": stats["victory_points"]["total"],
                "victory_points_yesterday": stats["victory_points"]["yesterday"],
            },
        )


class CharacterImplantManager(models.Manager):
    def update_or_create_esi(
        self, character: Character, force_update: bool = False
    ) -> UpdateSectionResult:
        """Update or create implants for a character from ESI."""
        return character.update_section_if_changed(
            section=character.UpdateSection.IMPLANTS,
            fetch_func=self._fetch_data_from_esi,
            store_func=self._update_or_create_objs,
            force_update=force_update,
        )

    @fetch_token_for_character("esi-clones.read_implants.v1")
    def _fetch_data_from_esi(self, character: Character, token: Token) -> List[int]:
        logger.info("%s: Fetching implants from ESI", character)
        implant_type_ids = esi.client.Clones.get_characters_character_id_implants(
            character_id=character.eve_character.character_id,
            token=token.valid_access_token(),
        ).results()
        return implant_type_ids

    def _update_or_create_objs(self, character: Character, implant_type_ids: List[int]):
        if not implant_type_ids:
            self.filter(character=character).delete()
            logger.info("%s: Character has no implants", character)

        EveType.objects.bulk_get_or_create_esi(ids=implant_type_ids)

        # bulk delete & create is fine here, since characters mostly switch
        # between clones, and rarely replace some implants of their current clone
        with transaction.atomic():
            self.filter(character=character).delete()
            implants = [
                self.model(
                    character=character, eve_type=EveType.objects.get(id=eve_type_id)
                )
                for eve_type_id in implant_type_ids
            ]
            logger.info("%s: Storing %s implants", character, len(implants))
            self.bulk_create(implants, batch_size=MEMBERAUDIT_BULK_METHODS_BATCH_SIZE)


class CharacterJumpCloneManager(models.Manager):
    def update_or_create_esi(
        self, character: Character, force_update: bool = False
    ) -> UpdateSectionResult:
        """Update or create jump clones for a character from ESI."""

        return character.update_section_if_changed(
            section=character.UpdateSection.JUMP_CLONES,
            fetch_func=self._fetch_data_from_esi,
            store_func=self._update_or_create_objs,
            force_update=force_update,
        )

    @fetch_token_for_character("esi-clones.read_clones.v1")
    def _fetch_data_from_esi(self, character: Character, token: Token):
        logger.info("%s: Fetching jump clones from ESI", character)
        jump_clones_info = esi.client.Clones.get_characters_character_id_clones(
            character_id=character.eve_character.character_id,
            token=token.valid_access_token(),
        ).results()
        return jump_clones_info

    # TODO: Replace delete & create with update
    @fetch_token_for_character("esi-universe.read_structures.v1")
    def _update_or_create_objs(
        self, character: Character, token: Token, jump_clones_info: dict
    ):
        from memberaudit.models import CharacterJumpCloneImplant, Location

        self._update_or_create_clone_info(character, token, jump_clones_info)

        jump_clones_list = jump_clones_info.get("jump_clones")
        if jump_clones_list:
            self._prefetch_locations(token, jump_clones_list)

        with transaction.atomic():
            self.filter(character=character).delete()
            if not jump_clones_list:
                logger.info("%s: No jump clones", character)
                return

            logger.info("%s: Storing %s jump clones", character, len(jump_clones_list))
            jump_clones = [
                self.model(
                    character=character,
                    jump_clone_id=record.get("jump_clone_id"),
                    location=get_or_none("location_id", record, Location),
                    name=record.get("name") if record.get("name") else "",
                )
                for record in jump_clones_list
            ]
            self.bulk_create(
                jump_clones, batch_size=MEMBERAUDIT_BULK_METHODS_BATCH_SIZE
            )
            implants = []
            for jump_clone_info in jump_clones_list:
                if jump_clone_info.get("implants"):
                    for implant in jump_clone_info["implants"]:
                        jump_clone = character.jump_clones.get(
                            jump_clone_id=jump_clone_info.get("jump_clone_id")
                        )
                        implants.append(
                            CharacterJumpCloneImplant(
                                jump_clone=jump_clone,
                                eve_type=EveType.objects.get(id=implant),
                            )
                        )

            CharacterJumpCloneImplant.objects.bulk_create(
                implants, batch_size=MEMBERAUDIT_BULK_METHODS_BATCH_SIZE
            )

    def _update_or_create_clone_info(
        self, character: Character, token: Token, jump_clones_info: dict
    ):
        from memberaudit.models import CharacterCloneInfo, Location

        home_location_data = jump_clones_info.get("home_location")
        if home_location_data and (
            home_location_id := home_location_data.get("location_id")
        ):
            home_location, _ = Location.objects.get_or_create_esi_async(
                id=home_location_id, token=token
            )
        else:
            home_location = None

        return CharacterCloneInfo.objects.update_or_create(
            character=character,
            defaults={
                "home_location": home_location,
                "last_clone_jump_date": jump_clones_info.get("last_clone_jump_date"),
                "last_station_change_date": jump_clones_info.get(
                    "last_station_change_date"
                ),
            },
        )

    def _prefetch_locations(self, token, jump_clones_list):
        """Prefetch related objects ahead of transaction."""

        from memberaudit.models import Location

        incoming_location_ids = {
            record["location_id"]
            for record in jump_clones_list
            if "location_id" in record
        }
        Location.objects.create_missing_esi(incoming_location_ids, token)

        for jump_clone_info in jump_clones_list:
            if jump_clone_info.get("implants"):
                EveType.objects.bulk_get_or_create_esi(
                    ids=jump_clone_info.get("implants", [])
                )


class CharacterLocationManager(models.Manager):
    def update_or_create_esi(
        self, character: Character, force_update: bool = False
    ) -> UpdateSectionResult:
        """Update or create location for a character from ESI."""

        return character.update_section_if_changed(
            section=character.UpdateSection.LOCATION,
            fetch_func=self._fetch_data_from_esi,
            store_func=self._update_or_create_objs,
            force_update=force_update,
        )

    @fetch_token_for_character(
        ["esi-location.read_location.v1", "esi-universe.read_structures.v1"]
    )
    def _fetch_data_from_esi(self, character: Character, token):
        logger.info("%s: Fetching location from ESI", character)
        location_info = esi.client.Location.get_characters_character_id_location(
            character_id=character.eve_character.character_id,
            token=token.valid_access_token(),
        ).results()
        return location_info

    @fetch_token_for_character(
        ["esi-location.read_location.v1", "esi-universe.read_structures.v1"]
    )
    def _update_or_create_objs(self, character: Character, token: Token, location_info):
        from memberaudit.models.general import Location

        solar_system_id = location_info["solar_system_id"]
        eve_solar_system, _ = EveSolarSystem.objects.get_or_create_esi(
            id=solar_system_id
        )

        if station_id := location_info.get("station_id"):
            location, _ = Location.objects.get_or_create_esi(id=station_id, token=token)

        elif structure_id := location_info.get("structure_id"):
            location, _ = Location.objects.get_or_create_esi_async(
                id=structure_id, token=token
            )

        else:
            location, _ = Location.objects.get_or_create_esi(
                id=solar_system_id, token=token
            )

        self.update_or_create(
            character=character,
            defaults={"eve_solar_system": eve_solar_system, "location": location},
        )


class CharacterLoyaltyEntryManager(GenericUpdateSimpleObjMixin, models.Manager):
    def update_or_create_esi(
        self, character: Character, force_update: bool = False
    ) -> UpdateSectionResult:
        """Update or create loyalty entries for a character from ESI."""
        return character.update_section_if_changed(
            section=character.UpdateSection.LOYALTY,
            fetch_func=self._fetch_data_from_esi,
            store_func=self._update_or_create_objs,
            force_update=force_update,
        )

    @fetch_token_for_character("esi-characters.read_loyalty.v1")
    def _fetch_data_from_esi(self, character: Character, token: Token) -> List[dict]:
        logger.info("%s: Fetching loyalty entries from ESI", character)
        loyalty_entries = esi.client.Loyalty.get_characters_character_id_loyalty_points(
            character_id=character.eve_character.character_id,
            token=token.valid_access_token(),
        ).results()

        return loyalty_entries

    def _update_or_create_objs(
        self, character: Character, esi_data: List[dict]
    ) -> Set[int]:
        def make_obj_from_esi_entry(character, key, value):
            obj = self.model(
                character=character,
                corporation=EveEntity.objects.get_or_create(id=key)[0],
                loyalty_points=value,
            )
            return obj

        return self._update_or_create_objs_generic(
            character,
            esi_data,
            esi_fields=("corporation_id", "loyalty_points"),
            model_fields=("corporation_id", "loyalty_points"),
            make_obj_from_esi_entry=make_obj_from_esi_entry,
            return_new_eve_entities=True,
        )


class CharacterMailManager(models.Manager):
    def update_or_create_headers_esi(
        self, character: Character, force_update: bool = False
    ):
        """Update or create mail headers for a character from ESI."""
        return character.update_section_if_changed(
            section=character.UpdateSection.MAILS,
            fetch_func=self._fetch_data_from_esi,
            store_func=self._update_or_create_objs,
            force_update=force_update,
        )

    @fetch_token_for_character("esi-mail.read_mail.v1")
    def _fetch_data_from_esi(self, character: Character, token: Token) -> dict:
        last_mail_id = None
        mail_headers_all = []
        page = 1
        while True:
            logger.info("%s: Fetching mail headers from ESI - page %s", character, page)
            mail_headers = esi.client.Mail.get_characters_character_id_mail(
                character_id=character.eve_character.character_id,
                last_mail_id=last_mail_id,
                token=token.valid_access_token(),
            ).results()

            mail_headers_all += mail_headers
            if len(mail_headers) < 50 or len(mail_headers_all) >= MEMBERAUDIT_MAX_MAILS:
                break

            last_mail_id = min((mail["mail_id"] for mail in mail_headers))
            page += 1

        cutoff_datetime = data_retention_cutoff()
        mail_headers_all_2 = {
            obj["mail_id"]: obj
            for obj in mail_headers_all
            if cutoff_datetime is None
            or not obj.get("timestamp")
            or obj.get("timestamp") > cutoff_datetime
        }
        logger.debug(
            "%s: Received %s mail headers from ESI", character, len(mail_headers_all_2)
        )
        return mail_headers_all_2

    def _update_or_create_objs(self, character: Character, mail_headers):
        if cutoff_datetime := data_retention_cutoff():
            self.filter(character=character, timestamp__lt=cutoff_datetime).delete()

        self._preload_mail_senders(mail_headers=mail_headers)

        with transaction.atomic():
            incoming_ids = set(mail_headers.keys())
            existing_ids = set(
                self.filter(character=character).values_list("mail_id", flat=True)
            )
            create_ids = incoming_ids.difference(existing_ids)
            if create_ids:
                self._create_mail_headers(
                    character=character,
                    mail_headers=mail_headers,
                    create_ids=create_ids,
                )

            update_ids = incoming_ids.difference(create_ids)
            if update_ids:
                self._update_mail_headers(
                    character=character,
                    mail_headers=mail_headers,
                    update_ids=update_ids,
                )

            if not create_ids and not update_ids:
                logger.info("%s: No mails", character)

    def _preload_mail_senders(self, mail_headers):
        from memberaudit.models import MailEntity

        incoming_ids = {o["from"] for o in mail_headers.values()}
        existing_ids = set(MailEntity.objects.values_list("id", flat=True))
        create_ids = incoming_ids.difference(existing_ids)
        for mail_entity_id in create_ids:
            MailEntity.objects.get_or_create_esi_async(id=mail_entity_id)

    def _create_mail_headers(
        self, character: Character, mail_headers: dict, create_ids
    ) -> None:
        from memberaudit.models import MailEntity

        logger.info("%s: Create %s new mail headers", character, len(create_ids))
        new_mail_headers_list = {
            mail_info["mail_id"]: mail_info
            for mail_id, mail_info in mail_headers.items()
            if mail_id in create_ids
        }

        self._add_missing_mailing_lists_from_recipients(
            character=character, new_mail_headers_list=new_mail_headers_list
        )

        # create headers
        new_headers = []
        for mail_id, header in new_mail_headers_list.items():
            new_headers.append(
                self.model(
                    character=character,
                    mail_id=mail_id,
                    sender=get_or_none("from", header, MailEntity),
                    is_read=bool(header.get("is_read")),
                    subject=header.get("subject", ""),
                    timestamp=header.get("timestamp"),
                )
            )

        self.bulk_create(new_headers, batch_size=MEMBERAUDIT_BULK_METHODS_BATCH_SIZE)

        # add recipients and labels
        labels = character.mail_labels.get_all_labels()
        for mail_id, header in new_mail_headers_list.items():
            mail_obj = self.filter(character=character).get(mail_id=mail_id)
            recipients = []
            recipient_type_map = {
                "alliance": MailEntity.Category.ALLIANCE,
                "character": MailEntity.Category.CHARACTER,
                "corporation": MailEntity.Category.CORPORATION,
                "mailing_list": MailEntity.Category.MAILING_LIST,
            }
            for recipient_info in header.get("recipients"):
                recipient, _ = MailEntity.objects.get_or_create(
                    id=recipient_info.get("recipient_id"),
                    defaults={
                        "category": recipient_type_map[
                            recipient_info.get("recipient_type")
                        ]
                    },
                )
                recipients.append(recipient)

            mail_obj.recipients.set(recipients, clear=True)
            MailEntity.objects.bulk_update_names(recipients, keep_names=True)
            self._update_labels_of_mail(
                character=character,
                mail=mail_obj,
                label_ids=header.get("labels"),
                labels=labels,
            )

    def _add_missing_mailing_lists_from_recipients(
        self, character: Character, new_mail_headers_list
    ):
        """Add mailing lists from recipients that are not part of the known
        mailing lists."""
        from memberaudit.models import MailEntity

        incoming_ids = set()
        for header in new_mail_headers_list.values():
            for recipient in header.get("recipients"):
                if recipient.get("recipient_type") == "mailing_list":
                    incoming_ids.add(recipient.get("recipient_id"))

        existing_ids = set(
            MailEntity.objects.filter(
                category=MailEntity.Category.MAILING_LIST
            ).values_list("id", flat=True)
        )
        create_ids = incoming_ids.difference(existing_ids)
        if create_ids:
            logger.info(
                "%s: Adding %s unknown mailing lists from recipients",
                character,
                len(create_ids),
            )
            for list_id in create_ids:
                MailEntity.objects.get_or_create(
                    id=list_id, defaults={"category": MailEntity.Category.MAILING_LIST}
                )

    def _update_labels_of_mail(
        self, character: Character, mail, label_ids: List[int], labels: list
    ) -> None:
        """Update the labels of a mail object from a dict."""
        mail.labels.clear()
        if label_ids:
            labels_to_add = []
            for label_id in label_ids:
                try:
                    labels_to_add.append(labels[label_id])
                except KeyError:
                    logger.info(
                        "%s: Unknown mail label with ID %s for mail %s",
                        character,
                        label_id,
                        mail,
                    )

            mail.labels.add(*labels_to_add)

    def _update_mail_headers(
        self, character: Character, mail_headers: dict, update_ids
    ) -> None:
        logger.info("%s: Updating %s mail headers", character, len(update_ids))
        mail_pks = self.filter(character=character, mail_id__in=update_ids).values_list(
            "pk", flat=True
        )
        labels = character.mail_labels.get_all_labels()
        mails = self.in_bulk(mail_pks)
        for mail in mails.values():
            mail_header = mail_headers.get(mail.mail_id)
            if mail_header:
                mail.is_read = bool(mail_header.get("is_read"))
                self._update_labels_of_mail(
                    character=character,
                    mail=mail,
                    label_ids=mail_header.get("labels"),
                    labels=labels,
                )

        self.bulk_update(mails.values(), ["is_read"])

    def update_or_create_body_esi(
        self, character: Character, mail: CharacterMail, force_update: bool = False
    ) -> UpdateSectionResult:
        """Update or create mail body for a character from ESI."""
        try:
            mail_body = self._fetch_mail_body_from_esi(character, mail)
        except HTTPNotFound:
            logger.info(
                "%s: Mail %s was deleted in game. Removing mail header.",
                character,
                mail,
            )
            mail.delete()
            return UpdateSectionResult(is_changed=True, is_updated=True)

        is_changed = mail.body != mail_body
        if is_changed or force_update:
            mail.body = mail_body
            mail.save()
            is_updated = True
            eve_xml_to_html(mail.body)  # resolve names early
        else:
            is_updated = False

        store_character_data_to_disk_when_enabled(
            character=character,
            data=mail_body,
            section="mails",
            suffix=f"body-{mail.mail_id}",
        )

        return UpdateSectionResult(is_changed=is_changed, is_updated=is_updated)

    def _fetch_mail_body_from_esi(
        self, character: Character, mail: CharacterMail
    ) -> str:
        logger.info(
            "%s: Fetching mail body from ESI for mail ID %d", character, mail.mail_id
        )
        token = character.fetch_token("esi-mail.read_mail.v1")
        mail_body = esi.client.Mail.get_characters_character_id_mail_mail_id(
            character_id=character.eve_character.character_id,
            mail_id=mail.mail_id,
            token=token.valid_access_token(),
        ).result()

        return mail_body.get("body", "")


class CharacterMailLabelManager(models.Manager):
    def get_all_labels(self) -> Dict[int, Any]:
        """Return all label objects as dict by label_id."""
        label_pks = self.values_list("pk", flat=True)
        return {label.label_id: label for label in self.in_bulk(label_pks).values()}

    def update_or_create_esi(
        self, character: Character, force_update: bool = False
    ) -> UpdateSectionResult:
        """Update or create mail labels for a character from ESI."""
        return character.update_section_if_changed(
            section=character.UpdateSection.MAILS,
            fetch_func=self._fetch_data_from_esi,
            store_func=self._update_or_create_objs,
            force_update=force_update,
            hash_num=3,
        )

    @fetch_token_for_character("esi-mail.read_mail.v1")
    def _fetch_data_from_esi(self, character: Character, token: Token) -> dict:
        from memberaudit.models import CharacterMailUnreadCount

        logger.info("%s: Fetching mail labels from ESI", character)
        mail_labels_info = esi.client.Mail.get_characters_character_id_mail_labels(
            character_id=character.eve_character.character_id,
            token=token.valid_access_token(),
        ).results()

        if mail_labels_info.get("total_unread_count"):
            CharacterMailUnreadCount.objects.update_or_create(
                character=character,
                defaults={"total": mail_labels_info.get("total_unread_count")},
            )

        mail_labels = mail_labels_info.get("labels")
        if not mail_labels:
            return {}
        return {obj["label_id"]: obj for obj in mail_labels if "label_id" in obj}

    @transaction.atomic()
    def _update_or_create_objs(self, character: Character, mail_labels_list: dict):
        logger.info("%s: Storing %s mail labels", character, len(mail_labels_list))
        incoming_ids = set(mail_labels_list.keys())
        existing_ids = set(
            self.filter(character=character).values_list("label_id", flat=True)
        )
        obsolete_ids = existing_ids.difference(incoming_ids)
        if obsolete_ids:
            self.filter(character=character, label_id__in=obsolete_ids).delete()

        create_ids = incoming_ids.difference(existing_ids)
        if create_ids:
            self._create_new_mail_labels(
                character=character,
                mail_labels_list=mail_labels_list,
                label_ids=create_ids,
            )

        update_ids = incoming_ids.difference(create_ids)
        if update_ids:
            self._update_existing_mail_labels(
                character=character,
                mail_labels_list=mail_labels_list,
                label_ids=update_ids,
            )

    def _create_new_mail_labels(
        self, character: Character, mail_labels_list: dict, label_ids: set
    ):
        new_labels = [
            self.model(
                character=character,
                label_id=label.get("label_id"),
                color=label.get("color"),
                name=label.get("name"),
                unread_count=label.get("unread_count"),
            )
            for label_id, label in mail_labels_list.items()
            if label_id in label_ids
        ]
        self.bulk_create(new_labels, batch_size=MEMBERAUDIT_BULK_METHODS_BATCH_SIZE)

    def _update_existing_mail_labels(
        self, character: Character, mail_labels_list: dict, label_ids: set
    ):
        logger.info("%s: Updating %s mail labels", character, len(label_ids))
        update_pks = list(
            self.filter(character=character, label_id__in=label_ids).values_list(
                "pk", flat=True
            )
        )
        labels = self.in_bulk(update_pks)
        for label in labels.values():
            record = mail_labels_list.get(label.label_id)
            if record:
                label.name = record.get("name")
                label.color = record.get("color")
                label.unread_count = record.get("unread_count")

        self.bulk_update(
            labels.values(),
            fields=["name", "color", "unread_count"],
            batch_size=MEMBERAUDIT_BULK_METHODS_BATCH_SIZE,
        )
