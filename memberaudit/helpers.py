"""Helpers for Member Audit."""

import datetime as dt
import itertools
from typing import Any, Iterable, NamedTuple, Optional, Set

from celery import Task

from django.apps import apps
from django.forms.models import model_to_dict
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


def arabic_number_to_roman(value) -> str:
    """Map to convert arabic to roman numbers (1 to 5 only)"""
    my_map = {0: "-", 1: "I", 2: "II", 3: "III", 4: "IV", 5: "V"}
    try:
        return my_map[value]
    except KeyError:
        return "-"


class UpdateSectionResult(NamedTuple):
    """A result of an attempted section update."""

    is_changed: Optional[bool]
    is_updated: bool
    data: Any = None


def character_section_models():
    """Return all character section models."""
    my_app = apps.get_app_config("memberaudit")
    my_character_models = [
        model_class
        for model_class in my_app.get_models()
        if model_class.__name__.startswith("Character")
    ]

    return my_character_models


def model_to_dict_safely(obj) -> dict:
    """Convert a model ot dict in a safe manner."""
    fields = [field.name for field in obj._meta.fields]
    result = model_to_dict(obj, fields=fields)
    return result
