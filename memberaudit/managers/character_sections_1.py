"""Managers for character section models (1/3)."""

# pylint: disable=missing-class-docstring,not-callable

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, List, Set

from django.db import DatabaseError, models, transaction
from django.db.models import Case, ExpressionWrapper, F, Value, When
from esi.models import Token
from eveuniverse.models import EveEntity, EveType

from allianceauth.services.hooks import get_extension_logger
from app_utils.helpers import chunks
from app_utils.logging import LoggerAddTag

from memberaudit import __title__
from memberaudit.app_settings import MEMBERAUDIT_BULK_METHODS_BATCH_SIZE
from memberaudit.decorators import fetch_token_for_character
from memberaudit.helpers import (
    UpdateSectionResult,
    data_retention_cutoff,
    eve_entity_ids_from_objs,
    model_to_dict_safely,
)
from memberaudit.models._helpers import store_character_data_to_disk_when_enabled
from memberaudit.providers import esi
from memberaudit.utils import (
    get_or_create_esi_or_none,
    get_or_create_or_none,
    get_or_none,
)

from ._common import GenericUpdateSimpleObjMixin

if TYPE_CHECKING:
    from memberaudit.models import Character, CharacterAsset


logger = LoggerAddTag(get_extension_logger(__name__), __title__)


class CharacterAssetQuerySet(models.QuerySet):
    def item_ids(self) -> Set[int]:
        """Return item IDs for objects in this queryset."""
        return set(self.values_list("item_id", flat=True))

    def annotate_pricing(self) -> models.QuerySet:
        """Return qs with annotated price and total columns."""
        return (
            self.select_related("eve_type__market_price")
            .annotate(
                price=Case(
                    When(
                        is_blueprint_copy=True,
                        then=Value(None),
                    ),
                    default=F("eve_type__market_price__average_price"),
                )
            )
            .annotate(
                total=Case(
                    When(
                        is_blueprint_copy=True,
                        then=Value(None),
                    ),
                    default=ExpressionWrapper(
                        F("eve_type__market_price__average_price") * F("quantity"),
                        output_field=models.FloatField(),
                    ),
                )
            )
        )


class CharacterAssetManagerBase(models.Manager):
    def fetch_from_esi(self, character: Character, force_update: bool = False):
        """Fetch assets from ESI and preload related objects from ESI."""
        return character.update_section_if_changed(
            section=character.UpdateSection.ASSETS,
            fetch_func=self._fetch_data_from_esi,
            store_func=None,
            force_update=force_update,
        )

    @fetch_token_for_character("esi-assets.read_assets.v1")
    def _fetch_data_from_esi(self, character: Character, token: Token) -> list:
        """Fetch character assets with names from ESI and return it."""
        asset_data = self._fetching_assets_from_esi(character, token)

        # add names to assets
        item_ids = list(asset_data.keys())
        asset_names = self._fetching_asset_names_from_esi(character, token, item_ids)
        for item_id in item_ids:
            asset_data[item_id]["name"] = asset_names.get(item_id, "")

        return sorted(asset_data.values(), key=lambda o: o["item_id"])

    def _fetching_assets_from_esi(self, character: Character, token: Token):
        logger.info("%s: Fetching assets from ESI", character)
        asset_list = esi.client.Assets.get_characters_character_id_assets(
            character_id=character.eve_character.character_id,
            token=token.valid_access_token(),
        ).results()
        asset_data = {int(item["item_id"]): item for item in asset_list}
        return asset_data

    def _fetching_asset_names_from_esi(
        self, character: Character, token: Token, item_ids: List[int]
    ):
        logger.info("%s: Fetching asset names from ESI", character)
        names = []
        for asset_ids_chunk in chunks(item_ids, 999):
            names += esi.client.Assets.post_characters_character_id_assets_names(
                character_id=character.eve_character.character_id,
                token=token.valid_access_token(),
                item_ids=asset_ids_chunk,
            ).results()

        asset_names = {
            int(item["item_id"]): item["name"]
            for item in names
            if item["name"] != "None"
        }

        return asset_names

    def preload_objects_from_esi(
        self, character: Character, asset_list: list
    ) -> UpdateSectionResult:
        """Preloads objects needed to build the asset tree."""

        logger.info("%s: Preloading objects for asset tree", character)

        if not asset_list:
            return UpdateSectionResult(is_changed=None, is_updated=False)

        is_updated = self._fetch_missing_types_from_esi(character, asset_list)
        is_updated |= self._create_missing_locations(character, asset_list)

        return UpdateSectionResult(is_changed=None, is_updated=is_updated)

    def _fetch_missing_types_from_esi(
        self, character: Character, asset_list: list
    ) -> bool:
        required_ids = {item["type_id"] for item in asset_list if "type_id" in item}
        existing_ids = set(EveType.objects.values_list("id", flat=True))
        missing_ids = required_ids.difference(existing_ids)
        if not missing_ids:
            return False

        EveType.objects.bulk_get_or_create_esi(ids=list(missing_ids))
        logger.info(
            "%s: Fetched %s missing types from ESI", character, len(missing_ids)
        )
        return True

    def _create_missing_locations(self, character: Character, asset_list: list) -> bool:
        from memberaudit.models import Location

        asset_item_ids = {asset["item_id"] for asset in asset_list}
        incoming_location_ids = {
            item["location_id"]
            for item in asset_list
            if "location_id" in item and item["location_id"] not in asset_item_ids
        }
        if not incoming_location_ids:
            return False

        current_location_ids = set(Location.objects.values_list("id", flat=True))
        missing_location_ids = incoming_location_ids - current_location_ids
        if not missing_location_ids:
            return False

        token = character.fetch_token("esi-universe.read_structures.v1")
        Location.objects.create_missing_esi(
            location_ids=missing_location_ids, token=token
        )
        return True

    def bulk_create_with_fallback(
        self, objs: Iterable[CharacterAsset], batch_size: int = None
    ) -> List[CharacterAsset]:
        """Create objs in bulk safely and return newly created objs."""
        try:
            added_objs = self.bulk_create(objs, batch_size=batch_size)
        except DatabaseError:
            logger.warning(
                "Bulk create with %d %s failed. "
                "Falling back on creating them one by one.",
                len(objs),
                self.model._meta.verbose_name_plural,
                exc_info=True,
            )
            added_objs = []
            for obj in objs:
                try:
                    obj.save(force_insert=True)
                except DatabaseError:
                    obj_as_dict = model_to_dict_safely(obj)
                    logger.exception(
                        "Failed to create %s: %s",
                        self.model._meta.verbose_name,
                        obj_as_dict,
                    )
                else:
                    added_objs.append(obj)

        return added_objs


CharacterAssetManager = CharacterAssetManagerBase.from_queryset(CharacterAssetQuerySet)


class CharacterAttributesManager(models.Manager):
    def update_or_create_esi(
        self, character: Character, force_update: bool = False
    ) -> UpdateSectionResult:
        """Update or create attributes for a character from ESI."""
        return character.update_section_if_changed(
            section=character.UpdateSection.ATTRIBUTES,
            fetch_func=self._fetch_data_from_esi,
            store_func=self._update_or_create_objs,
            force_update=force_update,
        )

    @fetch_token_for_character("esi-skills.read_skills.v1")
    def _fetch_data_from_esi(self, character: Character, token):
        logger.info("%s: Fetching attributes from ESI", character)
        attribute_data = esi.client.Skills.get_characters_character_id_attributes(
            character_id=character.eve_character.character_id,
            token=token.valid_access_token(),
        ).results()
        return attribute_data

    def _update_or_create_objs(self, character: Character, attribute_data):
        self.update_or_create(
            character=character,
            defaults={
                "accrued_remap_cooldown_date": attribute_data.get(
                    "accrued_remap_cooldown_date"
                ),
                "last_remap_date": attribute_data.get("last_remap_date"),
                "bonus_remaps": attribute_data.get("bonus_remaps"),
                "charisma": attribute_data.get("charisma"),
                "intelligence": attribute_data.get("intelligence"),
                "memory": attribute_data.get("memory"),
                "perception": attribute_data.get("perception"),
                "willpower": attribute_data.get("willpower"),
            },
        )


class CharacterContactLabelManager(GenericUpdateSimpleObjMixin, models.Manager):
    def update_or_create_esi(
        self, character: Character, force_update: bool = False
    ) -> UpdateSectionResult:
        """Update or create assets for a character from ESI."""

        return character.update_section_if_changed(
            section=character.UpdateSection.CONTACTS,
            fetch_func=self._fetch_data_from_esi,
            store_func=self._update_or_create_objs,
            force_update=force_update,
            hash_num=2,
        )

    @fetch_token_for_character("esi-characters.read_contacts.v1")
    def _fetch_data_from_esi(self, character: Character, token) -> List[dict]:
        logger.info("%s: Fetching contact labels from ESI", character)
        labels = esi.client.Contacts.get_characters_character_id_contacts_labels(
            character_id=character.eve_character.character_id,
            token=token.valid_access_token(),
        ).results()
        return labels

    def _update_or_create_objs(
        self, character: Character, esi_data: List[dict]
    ) -> Set[int]:
        def make_obj_from_esi_entry(character, key, value):
            obj = self.model(character=character, label_id=key, name=value)
            return obj

        self._update_or_create_objs_generic(
            character,
            esi_data,
            esi_fields=("label_id", "label_name"),
            model_fields=("label_id", "name"),
            make_obj_from_esi_entry=make_obj_from_esi_entry,
        )


class CharacterContactManager(models.Manager):
    def update_or_create_esi(
        self, character: Character, force_update: bool = False
    ) -> UpdateSectionResult:
        """Update or create assets for a character from ESI."""
        return character.update_section_if_changed(
            section=character.UpdateSection.CONTACTS,
            fetch_func=self._fetch_data_from_esi,
            store_func=self._update_or_create_objs,
            force_update=force_update,
        )

    @fetch_token_for_character("esi-characters.read_contacts.v1")
    def _fetch_data_from_esi(self, character: Character, token):
        logger.info("%s: Fetching contacts from ESI", character)
        contacts_data = esi.client.Contacts.get_characters_character_id_contacts(
            character_id=character.eve_character.character_id,
            token=token.valid_access_token(),
        ).results()
        return contacts_data

    @transaction.atomic()
    def _update_or_create_objs(self, character: Character, contacts_data) -> Set[int]:
        """Update or create new contact objects from provided data.

        Return EveEntity IDs in newly created contacts.
        """
        contacts_list = (
            {int(obj["contact_id"]): obj for obj in contacts_data}
            if contacts_data
            else {}
        )
        incoming_ids = set(contacts_list.keys())
        existing_ids = set(
            self.filter(character=character).values_list("eve_entity_id", flat=True)
        )
        obsolete_ids = existing_ids.difference(incoming_ids)
        if obsolete_ids:
            logger.info(
                "%s: Removing %s obsolete contacts", character, len(obsolete_ids)
            )
            self.filter(character=character, eve_entity_id__in=obsolete_ids).delete()

        create_ids = incoming_ids.difference(existing_ids)
        if create_ids:
            self._create_new_contacts(
                character=character,
                contacts_list=contacts_list,
                contact_ids=list(create_ids),
            )

        update_ids = incoming_ids.difference(create_ids)
        if update_ids:
            self._update_existing_contacts(
                character=character,
                contacts_list=contacts_list,
                contact_ids=list(update_ids),
            )

        if not obsolete_ids and not create_ids and not update_ids:
            logger.info("%s: Contacts have not changed", character)

        return create_ids

    def _create_new_contacts(
        self, character: Character, contacts_list: dict, contact_ids: list
    ):
        logger.info("%s: Storing %s new contacts", character, len(contact_ids))
        new_contacts_list = {
            contact_id: obj
            for contact_id, obj in contacts_list.items()
            if contact_id in contact_ids
        }
        new_contacts = [
            self.model(
                character=character,
                eve_entity=get_or_create_or_none("contact_id", contact_data, EveEntity),
                is_blocked=contact_data.get("is_blocked"),
                is_watched=contact_data.get("is_watched"),
                standing=contact_data.get("standing"),
            )
            for contact_data in new_contacts_list.values()
        ]
        self.bulk_create(new_contacts, batch_size=MEMBERAUDIT_BULK_METHODS_BATCH_SIZE)
        self._update_contact_contact_labels(
            character=character,
            contacts_list=contacts_list,
            contact_ids=contact_ids,
            is_new=True,
        )

    def _update_contact_contact_labels(
        self, character: Character, contacts_list: dict, contact_ids: list, is_new=False
    ):
        from memberaudit.models import CharacterContactLabel

        for contact_id, contact_data in contacts_list.items():
            if contact_id in contact_ids and contact_data.get("label_ids"):
                character_contact = self.filter(character=character).get(
                    eve_entity_id=contact_id
                )
                if not is_new:
                    character_contact.labels.clear()

                labels = []
                for label_id in contact_data.get("label_ids"):
                    try:
                        label = character.contact_labels.get(label_id=label_id)
                    except CharacterContactLabel.DoesNotExist:
                        # sometimes label IDs on contacts
                        # do not refer to actual labels
                        logger.info(
                            "%s: Unknown contact label with id %s",
                            character,
                            label_id,
                        )
                    else:
                        labels.append(label)

                    character_contact.labels.add(*labels)

    def _update_existing_contacts(
        self, character: Character, contacts_list: dict, contact_ids: list
    ):
        logger.info("%s: Updating %s contacts", character, len(contact_ids))
        update_contact_pks = list(
            self.filter(character=character, eve_entity_id__in=contact_ids).values_list(
                "pk", flat=True
            )
        )
        contacts = self.in_bulk(update_contact_pks)
        for contact in contacts.values():
            contact_data = contacts_list.get(contact.eve_entity_id)
            if contact_data:
                contact.is_blocked = contact_data.get("is_blocked")
                contact.is_watched = contact_data.get("is_watched")
                contact.standing = contact_data.get("standing")

        self.bulk_update(
            contacts.values(),
            fields=["is_blocked", "is_watched", "standing"],
            batch_size=MEMBERAUDIT_BULK_METHODS_BATCH_SIZE,
        )
        self._update_contact_contact_labels(
            character=character, contacts_list=contacts_list, contact_ids=contact_ids
        )


class CharacterContractManager(models.Manager):
    def update_or_create_esi(
        self, character: Character, force_update: bool = False
    ) -> UpdateSectionResult:
        """Update or create contracts for a character from ESI."""
        return character.update_section_if_changed(
            section=character.UpdateSection.CONTRACTS,
            fetch_func=self._fetch_data_from_esi,
            store_func=self._update_or_create_objs,
            force_update=force_update,
        )

    @fetch_token_for_character("esi-contracts.read_character_contracts.v1")
    def _fetch_data_from_esi(self, character: Character, token: Token) -> dict:
        logger.info("%s: Fetching contracts from ESI", character)
        contracts_data = esi.client.Contracts.get_characters_character_id_contracts(
            character_id=character.eve_character.character_id,
            token=token.valid_access_token(),
        ).results()

        store_character_data_to_disk_when_enabled(
            character=character, data=contracts_data, section="contracts"
        )

        cutoff_datetime = data_retention_cutoff()
        contracts_list = {
            obj.get("contract_id"): obj
            for obj in contracts_data
            if cutoff_datetime is None or obj.get("date_expired") > cutoff_datetime
        }
        return contracts_list

    @fetch_token_for_character("esi-universe.read_structures.v1")
    def _update_or_create_objs(
        self, character: Character, token: Token, contracts_list
    ) -> Set[int]:
        """Update or create new contract objects from provided data.

        Return EveEntity IDs in newly created contracts.
        """
        from memberaudit.models import Location

        if cutoff_datetime := data_retention_cutoff():
            character.contracts.filter(date_expired__lt=cutoff_datetime).delete()

        existing_ids = set(character.contracts.values_list("contract_id", flat=True))
        incoming_location_ids = {
            obj["start_location_id"]
            for contract_id, obj in contracts_list.items()
            if contract_id not in existing_ids
        }
        incoming_location_ids |= {
            obj["end_location_id"] for obj in contracts_list.values()
        }
        Location.objects.create_missing_esi(incoming_location_ids, token)

        with transaction.atomic():
            incoming_ids = set(contracts_list.keys())
            existing_ids = set(
                self.filter(character=character).values_list("contract_id", flat=True)
            )
            create_ids = incoming_ids.difference(existing_ids)
            if create_ids:
                new_entity_ids = self._create_new_contracts(
                    character=character,
                    contracts_list=contracts_list,
                    contract_ids=create_ids,
                )
            else:
                new_entity_ids = set()

            update_ids = incoming_ids.difference(create_ids)
            if update_ids:
                self._update_existing_contracts(
                    character=character,
                    contracts_list=contracts_list,
                    contract_ids=update_ids,
                )
            return new_entity_ids

    def _create_new_contracts(
        self, character: Character, contracts_list: dict, contract_ids: Set[int]
    ) -> Set[int]:
        from memberaudit.models import Location

        logger.info("%s: Storing %s new contracts", character, len(contract_ids))
        new_contracts = []
        for contract_id in contract_ids:
            contract_data = contracts_list.get(contract_id)
            if contract_data:
                new_contracts.append(
                    self.model(
                        character=character,
                        contract_id=contract_data.get("contract_id"),
                        acceptor=get_or_create_or_none(
                            "acceptor_id", contract_data, EveEntity
                        ),
                        assignee=get_or_create_or_none(
                            "assignee_id", contract_data, EveEntity
                        ),
                        availability=self.model.ESI_AVAILABILITY_MAP[
                            contract_data.get("availability")
                        ],
                        buyout=contract_data.get("buyout"),
                        collateral=contract_data.get("collateral"),
                        contract_type=self.model.ESI_TYPE_MAP.get(
                            contract_data.get("type"),
                            self.model.TYPE_UNKNOWN,
                        ),
                        date_accepted=contract_data.get("date_accepted"),
                        date_completed=contract_data.get("date_completed"),
                        date_expired=contract_data.get("date_expired"),
                        date_issued=contract_data.get("date_issued"),
                        days_to_complete=contract_data.get("days_to_complete"),
                        end_location=get_or_none(
                            "end_location_id", contract_data, Location
                        ),
                        for_corporation=contract_data.get("for_corporation"),
                        issuer_corporation=get_or_create_or_none(
                            "issuer_corporation_id", contract_data, EveEntity
                        ),
                        issuer=get_or_create_or_none(
                            "issuer_id", contract_data, EveEntity
                        ),
                        price=contract_data.get("price"),
                        reward=contract_data.get("reward"),
                        start_location=get_or_none(
                            "start_location_id", contract_data, Location
                        ),
                        status=self.model.ESI_STATUS_MAP[contract_data.get("status")],
                        title=contract_data.get("title", ""),
                        volume=contract_data.get("volume"),
                    )
                )

        self.bulk_create(new_contracts, batch_size=MEMBERAUDIT_BULK_METHODS_BATCH_SIZE)
        return eve_entity_ids_from_objs(new_contracts)

    def _update_existing_contracts(
        self, character: Character, contracts_list: dict, contract_ids: set
    ) -> None:
        logger.info("%s: Updating %s contracts", character, len(contract_ids))
        update_contract_pks = list(
            self.filter(character=character, contract_id__in=contract_ids).values_list(
                "pk", flat=True
            )
        )
        contracts = self.in_bulk(update_contract_pks)
        for contract in contracts.values():
            contract_data = contracts_list.get(contract.contract_id)
            if contract_data:
                contract.acceptor = get_or_create_or_none(
                    "acceptor_id", contract_data, EveEntity
                )
                contract.acceptor_corporation = get_or_create_or_none(
                    "acceptor_corporation_id", contract_data, EveEntity
                )
                contract.date_accepted = contract_data.get("date_accepted")
                contract.date_completed = contract_data.get("date_completed")
                contract.status = self.model.ESI_STATUS_MAP[contract_data.get("status")]

        self.bulk_update(
            contracts.values(),
            fields=[
                "acceptor",
                "acceptor_corporation",
                "date_accepted",
                "date_completed",
                "status",
            ],
            batch_size=MEMBERAUDIT_BULK_METHODS_BATCH_SIZE,
        )


class CharacterContractBidManager(models.Manager):
    @fetch_token_for_character("esi-contracts.read_character_contracts.v1")
    def update_or_create_esi(self, character: Character, token: Token, contract):
        """Update or create contract bids for a contract from ESI."""
        if contract.contract_type != contract.TYPE_AUCTION:
            logger.warning(
                "%s, %s: Can not update bids. Wrong contract type.",
                character,
                contract.contract_id,
            )
            return

        logger.info(
            "%s, %s: Fetching contract bids from ESI", character, contract.contract_id
        )
        bids_data = (
            esi.client.Contracts.get_characters_character_id_contracts_contract_id_bids(
                character_id=character.eve_character.character_id,
                contract_id=contract.contract_id,
                token=token.valid_access_token(),
            ).results()
        )

        store_character_data_to_disk_when_enabled(
            character=character, data=bids_data, section="contracts", suffix="bids"
        )

        bids_list = {int(obj["bid_id"]): obj for obj in bids_data if "bid_id" in obj}
        self._update_or_create_objs(contract, bids_list)

    @transaction.atomic()
    def _update_or_create_objs(self, contract, bids_list: dict) -> Set[int]:
        """Update or create new contract objects from provided data.

        Return EveEntity IDs in newly created contracts.
        """
        incoming_ids = set(bids_list.keys())
        existing_ids = set(
            self.filter(contract=contract).values_list("bid_id", flat=True)
        )
        create_ids = incoming_ids.difference(existing_ids)
        if not create_ids:
            logger.info(
                "%s, %s: No new contract bids to add",
                contract.character,
                contract.contract_id,
            )
            return set()

        logger.info(
            "%s, %s: Storing %s new contract bids",
            contract.character,
            contract.contract_id,
            len(create_ids),
        )
        bids = [
            self.model(
                contract=contract,
                bid_id=bid.get("bid_id"),
                amount=bid.get("amount"),
                bidder=get_or_create_or_none("bidder_id", bid, EveEntity),
                date_bid=bid.get("date_bid"),
            )
            for bid_id, bid in bids_list.items()
            if bid_id in create_ids
        ]
        self.bulk_create(bids, batch_size=MEMBERAUDIT_BULK_METHODS_BATCH_SIZE)
        new_entity_ids = {obj.bidder_id for obj in bids}
        return new_entity_ids


class CharacterContractItemQuerySet(models.QuerySet):
    def annotate_pricing(self) -> models.QuerySet:
        """Return qs with annotated price and total columns."""
        return (
            self.select_related("eve_type__market_price")
            .annotate(
                price=Case(
                    When(
                        raw_quantity=-2,
                        then=Value(None),
                    ),
                    default=F("eve_type__market_price__average_price"),
                )
            )
            .annotate(
                total=Case(
                    When(
                        raw_quantity=-2,
                        then=Value(None),
                    ),
                    default=ExpressionWrapper(
                        F("eve_type__market_price__average_price") * F("quantity"),
                        output_field=models.FloatField(),
                    ),
                )
            )
        )


class CharacterContractItemManagerBase(models.Manager):
    @fetch_token_for_character("esi-contracts.read_character_contracts.v1")
    def update_or_create_esi(self, character: Character, token: Token, contract):
        """Update or create contract items for a contract from ESI."""
        if contract.contract_type not in [
            contract.TYPE_ITEM_EXCHANGE,
            contract.TYPE_AUCTION,
        ]:
            logger.warning(
                "%s, %s: Can not update items. Wrong contract type.",
                character,
                contract.contract_id,
            )
            return

        items_data = self._fetch_data_from_esi(character, token, contract)
        self._update_or_create_objs(contract, items_data)

    def _fetch_data_from_esi(self, character: Character, token: Token, contract):
        logger.info(
            "%s, %s: Fetching contract items from ESI", character, contract.contract_id
        )
        my_esi = esi.client.Contracts
        items_data = my_esi.get_characters_character_id_contracts_contract_id_items(
            character_id=character.eve_character.character_id,
            contract_id=contract.contract_id,
            token=token.valid_access_token(),
        ).results()

        store_character_data_to_disk_when_enabled(
            character=character, data=items_data, section="contracts", suffix="items"
        )

        return items_data

    def _update_or_create_objs(self, contract, items_data):
        logger.info(
            "%s, %s: Storing %s contract items",
            self,
            contract.contract_id,
            len(items_data),
        )
        items = [  # TODO: Access ESI data with keys, not get() for all mandatory fields
            self.model(
                contract=contract,
                record_id=item.get("record_id"),
                is_included=item.get("is_included"),
                is_singleton=item.get("is_singleton"),
                quantity=item.get("quantity"),
                raw_quantity=item.get("raw_quantity"),
                eve_type=get_or_create_esi_or_none("type_id", item, EveType),
            )
            for item in items_data
            if "record_id" in item
        ]
        # delete & create is fine here, since contracts items are never updated
        with transaction.atomic():
            self.filter(contract=contract).delete()
            self.bulk_create(items, batch_size=MEMBERAUDIT_BULK_METHODS_BATCH_SIZE)


CharacterContractItemManager = CharacterContractItemManagerBase.from_queryset(
    CharacterContractItemQuerySet
)
