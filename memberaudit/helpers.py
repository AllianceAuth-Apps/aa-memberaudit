"""Helpers for Member Audit."""

import datetime as dt
import itertools
import json
import os
from typing import Any, Iterable, Optional, Set

from celery import Task

from django.core.serializers.json import DjangoJSONEncoder
from django.utils.timezone import now
from eveuniverse.models import EveEntity, EveType

from app_utils.datetime import datetime_round_hour

from memberaudit.app_settings import MEMBERAUDIT_DATA_RETENTION_LIMIT
from memberaudit.constants import EveDogmaAttributeId


class EveEntityIdsMixin:
    """Add EveEntity related features."""

    def eve_entity_ids(self) -> Set[int]:
        """Return IDs of all existing EveEntity objects for this object."""
        ids = set()
        for field in self._meta.get_fields():
            if field.is_relation and issubclass(field.related_model, EveEntity):
                value = getattr(self, field.attname)
                if value:
                    ids.add(value)
        return ids


def eve_entity_ids_from_objs(objs: Iterable[Any]) -> Set[int]:
    """Return all EveEntity IDs from objs. Will return an empty set when objs is empty.

    Expects objs to have the `EveEntityIdsMixin`.
    """
    if not objs:
        return set()

    entity_ids_list = [obj.eve_entity_ids() for obj in objs]
    return set(itertools.chain.from_iterable(entity_ids_list))


def data_retention_cutoff() -> Optional[dt.datetime]:
    """Return cutoff datetime for data retention of None if unlimited."""
    if MEMBERAUDIT_DATA_RETENTION_LIMIT is None:
        return None
    return datetime_round_hour(
        now() - dt.timedelta(days=MEMBERAUDIT_DATA_RETENTION_LIMIT)
    )


def store_debug_data_to_disk(character, lst: Any, name: str):
    """Store character related data as JSON file to disk (for debugging).

    Will store under memberaudit_logs/{DATE}/{CHARACTER_PK}_{NAME}.json
    """
    today_str = now().strftime("%Y%m%d")
    now_str = now().strftime("%Y%m%d%H%M")
    path = f"memberaudit_log/{today_str}"
    if not os.path.isdir(path):
        os.makedirs(path)

    fullpath = os.path.join(path, f"character_{character.pk}_{name}_{now_str}.json")
    try:
        with open(fullpath, "w", encoding="utf-8") as file:
            json.dump(lst, file, cls=DjangoJSONEncoder, sort_keys=True, indent=4)

    except OSError:
        pass


def implant_slot_num(implant_type: EveType) -> int:  # TODO: Refactor into model
    """Return slot number for an implant. Or 0 if not found."""
    dogma_attributes = {
        obj.eve_dogma_attribute_id: obj.value
        for obj in implant_type.dogma_attributes.all()
    }
    try:
        slot_num = int(dogma_attributes[EveDogmaAttributeId.IMPLANT_SLOT])
    except KeyError:
        slot_num = 0
    return slot_num


def determine_task_priority(task_obj: Task) -> Optional[int]:
    """Return priority of give task or None if not defined."""
    properties = task_obj.request.get("properties") or {}
    return properties.get("priority")
