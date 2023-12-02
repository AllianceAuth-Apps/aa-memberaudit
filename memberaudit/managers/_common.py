"""Logic shared by managers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Dict, List, Sequence, Set

from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag

from memberaudit import __title__
from memberaudit.app_settings import MEMBERAUDIT_BULK_METHODS_BATCH_SIZE

if TYPE_CHECKING:
    from memberaudit.models import Character


logger = LoggerAddTag(get_extension_logger(__name__), __title__)


class GenericObjUpdateMixin:
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
    ) -> Set[int]:
        """Update or create objs from esi data."""
        if not esi_data:
            self.filter(character=character).delete()
            logger.info("%s: No %s", character, self.model._meta.verbose_name_plural)
            return set()

        current_entries = {obj[0]: obj[1] for obj in self.values_list(*model_fields)}
        incoming_entries = {obj[esi_fields[0]]: obj[esi_fields[1]] for obj in esi_data}

        new_eve_entity_ids = self._create_new_objs(
            character, current_entries, incoming_entries, make_obj_from_esi_entry
        )
        self._update_modified_objs(
            character, current_entries, incoming_entries, model_fields
        )
        self._delete_obsolete_objs(
            character, current_entries, incoming_entries, model_fields
        )

        return new_eve_entity_ids

    def _create_new_objs(
        self, character, current_entries, incoming_entries, make_obj_from_esi_entry
    ) -> Set[int]:
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
        self, character, current_entries, incoming_entries, model_fields
    ) -> None:
        modified_entries = {
            key: value
            for key, value in incoming_entries.items()
            if key in current_entries and current_entries[key] != value
        }
        if not modified_entries:
            return

        params = {"character": character, f"{model_fields[0]}__in": modified_entries}
        objs = self.filter(**params).in_bulk()
        for obj in objs.values():
            setattr(obj, model_fields[1], modified_entries[obj.corporation_id])

        self.bulk_update(
            objs.values(),
            fields=[model_fields[1]],
            batch_size=MEMBERAUDIT_BULK_METHODS_BATCH_SIZE,
        )
        logger.info(
            "%s: Updated %d %s",
            character,
            len(objs),
            self.model._meta.verbose_name_plural,
        )

    def _delete_obsolete_objs(
        self, character, current_entries, incoming_entries, model_fields
    ) -> None:
        obsolete_entries = {
            key: value
            for key, value in current_entries.items()
            if key not in incoming_entries
        }
        if not obsolete_entries:
            return

        params = {"character": character, f"{model_fields[0]}__in": obsolete_entries}
        self.filter(**params).delete()
        logger.info(
            "%s: Removed %d obsolete %s",
            character,
            len(obsolete_entries),
            self.model._meta.verbose_name_plural,
        )
