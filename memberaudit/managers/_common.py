"""Logic shared by managers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Dict, Iterable, List, Sequence, Set

from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag

from memberaudit import __title__
from memberaudit.app_settings import MEMBERAUDIT_BULK_METHODS_BATCH_SIZE
from memberaudit.helpers import eve_entity_ids_from_objs

if TYPE_CHECKING:
    from memberaudit.models import Character


logger = LoggerAddTag(get_extension_logger(__name__), __title__)


class GenericUpdateSimpleObjMixin:
    """Adds the ability to update objs from ESI data.

    This is a generic implementation that works for any section,
    which data can be represented as a list of key/value pairs.
    """

    def _update_or_create_objs_generic(
        self,
        character: Character,
        esi_data: List[Dict[str, Any]],
        esi_fields: Sequence[str],
        model_fields: Sequence[str],
        make_obj_from_esi_entry: Callable,
        return_new_eve_entities: bool = False,
    ) -> Set[int]:
        """Update or create objs from esi data.

        Optionally returns EveEntity IDs from new objs,
        which can then be resolved in bulk.
        """
        if not esi_data:
            self.filter(character=character).delete()
            logger.info("%s: No %s", character, self.model._meta.verbose_name_plural)
            return set()

        current_entries = {obj[0]: obj[1] for obj in self.values_list(*model_fields)}
        incoming_entries = {obj[esi_fields[0]]: obj[esi_fields[1]] for obj in esi_data}

        new_entries_keys = self._create_new_objs(
            character, current_entries, incoming_entries, make_obj_from_esi_entry
        )
        self._update_modified_objs(
            character,
            current_entries,
            incoming_entries,
            key_field=model_fields[0],
            value_field=model_fields[1],
        )
        self._delete_obsolete_objs(
            character, current_entries, incoming_entries, key_field=model_fields[0]
        )

        if return_new_eve_entities:
            return new_entries_keys

        return set()

    def _create_new_objs(
        self,
        character: Character,
        current_entries: dict,
        incoming_entries: dict,
        make_obj_from_esi_entry: Callable,
    ) -> Set[int]:
        """Create new objects. Returns keys from new objects."""
        new_entries = {
            entity_id: standing
            for entity_id, standing in incoming_entries.items()
            if entity_id not in current_entries
        }
        if not new_entries:
            return set()

        objs = [
            make_obj_from_esi_entry(character, key, value)
            for key, value in new_entries.items()
        ]
        self.bulk_create(objs, batch_size=MEMBERAUDIT_BULK_METHODS_BATCH_SIZE)
        logger.info(
            "%s: Created %d new %s",
            character,
            len(objs),
            self.model._meta.verbose_name_plural,
        )
        return set(new_entries.keys())

    def _update_modified_objs(
        self,
        character: Character,
        current_entries: dict,
        incoming_entries: dict,
        key_field: str,
        value_field: str,
    ) -> None:
        modified_entries = {
            key: value
            for key, value in incoming_entries.items()
            if key in current_entries and current_entries[key] != value
        }
        if not modified_entries:
            return

        params = {"character": character, f"{key_field}__in": modified_entries}
        objs = self.filter(**params).in_bulk()
        for obj in objs.values():
            key = getattr(obj, key_field)
            setattr(obj, value_field, modified_entries[key])

        self.bulk_update(
            objs=objs.values(),
            fields=[value_field],
            batch_size=MEMBERAUDIT_BULK_METHODS_BATCH_SIZE,
        )
        logger.info(
            "%s: Updated %d %s",
            character,
            len(objs),
            self.model._meta.verbose_name_plural,
        )

    def _delete_obsolete_objs(
        self,
        character: Character,
        current_entries: dict,
        incoming_entries: dict,
        key_field: str,
    ) -> None:
        obsolete_entries = {
            key: value
            for key, value in current_entries.items()
            if key not in incoming_entries
        }
        if not obsolete_entries:
            return

        params = {"character": character, f"{key_field}__in": obsolete_entries}
        self.filter(**params).delete()
        logger.info(
            "%s: Removed %d obsolete %s",
            character,
            len(obsolete_entries),
            self.model._meta.verbose_name_plural,
        )


class GenericUpdateComplexObjMixin:
    """Adds the ability to update objs from ESI data.

    This is a generic implementation that works for any section,
    which data has a functional primary key.
    """

    def _update_or_create_objs_generic(
        self,
        character: Character,
        esi_data: List[Dict[str, Any]],
        model_key_field: str,
        fields_for_update: Iterable[str],
        make_obj_from_esi_entry: Callable,
        return_new_eve_entities: bool = False,
    ) -> Set[int]:
        """Update or create objs from esi data."""
        if not esi_data:
            self.filter(character=character).delete()
            logger.info("%s: No %s", character, self.model._meta.verbose_name_plural)
            return set()

        current_objs = {
            getattr(obj, model_key_field): obj
            for obj in self.filter(character=character).in_bulk().values()
        }
        incoming_objs = {
            getattr(obj, model_key_field): obj
            for obj in [make_obj_from_esi_entry(character, entry) for entry in esi_data]
        }

        new_eve_entity_ids = self._create_new_objs(
            character, current_objs, incoming_objs, return_new_eve_entities
        )
        self._update_modified_objs(
            character, current_objs, incoming_objs, fields_for_update
        )
        self._delete_obsolete_objs(
            character, current_objs, incoming_objs, key_field=model_key_field
        )

        if return_new_eve_entities:
            return new_eve_entity_ids

        return set()

    def _create_new_objs(
        self,
        character: Character,
        current_objs: dict,
        incoming_objs: dict,
        return_new_eve_entities: bool,
    ) -> Set[int]:
        new_objs = [
            obj for key, obj in incoming_objs.items() if key not in current_objs
        ]
        if not new_objs:
            return set()

        self.bulk_create(new_objs, batch_size=MEMBERAUDIT_BULK_METHODS_BATCH_SIZE)
        logger.info(
            "%s: Created %d new %s",
            character,
            len(new_objs),
            self.model._meta.verbose_name_plural,
        )

        if return_new_eve_entities:
            return eve_entity_ids_from_objs(new_objs)

        return set()

    def _update_modified_objs(
        self,
        character: Character,
        current_objs: dict,
        incoming_objs: dict,
        fields_for_update: List[str],
    ) -> None:
        modified_objs = []
        for key, incoming_obj in incoming_objs.items():
            if key not in current_objs:
                continue

            current_obj = current_objs[key]
            has_changed = False
            for field in fields_for_update:
                new_value = getattr(incoming_obj, field)
                if getattr(current_obj, field) != new_value:
                    setattr(current_obj, field, new_value)
                    has_changed = True

            if has_changed:
                modified_objs.append(current_obj)

        if not modified_objs:
            return

        self.bulk_update(
            objs=modified_objs,
            fields=fields_for_update,
            batch_size=MEMBERAUDIT_BULK_METHODS_BATCH_SIZE,
        )
        logger.info(
            "%s: Updated %d %s",
            character,
            len(modified_objs),
            self.model._meta.verbose_name_plural,
        )

    def _delete_obsolete_objs(
        self,
        character: Character,
        current_objs: dict,
        incoming_objs: dict,
        key_field: str,
    ) -> None:
        obsolete_obj_ids = {key for key in current_objs if key not in incoming_objs}
        if not obsolete_obj_ids:
            return

        params = {"character": character, f"{key_field}__in": obsolete_obj_ids}
        self.filter(**params).delete()
        logger.info(
            "%s: Removed %d obsolete %s",
            character,
            len(obsolete_obj_ids),
            self.model._meta.verbose_name_plural,
        )
