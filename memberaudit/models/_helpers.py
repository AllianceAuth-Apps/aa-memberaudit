"""Helpers for models."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.utils.timezone import now

from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag

from memberaudit import __title__
from memberaudit.app_settings import (
    MEMBERAUDIT_STORE_ESI_DATA_CHARACTERS,
    MEMBERAUDIT_STORE_ESI_DATA_SECTIONS,
)

if TYPE_CHECKING:
    from memberaudit.models import Character

logger = LoggerAddTag(get_extension_logger(__name__), __title__)


def store_character_data_to_disk(
    character: Character, data: Any, section: Character.UpdateSection, suffix: str = ""
) -> Path:
    """Store character data to disk in JSON files for debugging.

    Returns path to created data file.
    """
    from memberaudit.models import Character

    if (
        MEMBERAUDIT_STORE_ESI_DATA_SECTIONS
        and section.value not in MEMBERAUDIT_STORE_ESI_DATA_SECTIONS
    ):
        return

    if (
        MEMBERAUDIT_STORE_ESI_DATA_CHARACTERS
        and character.id not in MEMBERAUDIT_STORE_ESI_DATA_CHARACTERS
    ):
        return

    path = _create_path_if_it_not_exists()
    try:
        section_obj = Character.UpdateSection(section)
    except TypeError:
        logger.exception("Failed to write debug data")
        return

    file_path = _generate_file_path(character, section_obj, suffix, path)
    _write_data(data, file_path)
    return file_path


def _create_path_if_it_not_exists() -> Path:
    today_str = now().strftime("%Y%m%d")
    path = Path(settings.BASE_DIR) / "temp" / "memberaudit_log" / today_str
    path.mkdir(parents=True, exist_ok=True)
    return path


def _generate_file_path(character, section, suffix, path) -> Path:
    now_str = now().strftime("%Y%m%d%H%M")
    name = f"{section.value}_{suffix}" if suffix else section.value
    file_name = f"character_{character.pk}_{name}_{now_str}.json"
    file_path = path / file_name
    return file_path


def _write_data(data, file_path):
    try:
        with file_path.open("w", encoding="utf-8") as file:
            json.dump(data, file, cls=DjangoJSONEncoder, sort_keys=True, indent=4)

        logger.info("Wrote debug data to: %s", file_path)

    except OSError:
        logger.exception("Failed to write debug data to: %s", file_path)
