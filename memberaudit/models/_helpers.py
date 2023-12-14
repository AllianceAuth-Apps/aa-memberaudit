"""Helpers for models."""

import json
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.utils.timezone import now

from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag

from memberaudit import __title__

logger = LoggerAddTag(get_extension_logger(__name__), __title__)


def store_debug_data_to_disk(character, lst: Any, name: str):
    """Store character related data as JSON file to disk (for debugging).

    Will store under temp/memberaudit_logs/{DATE}/{CHARACTER_PK}_{NAME}.json
    """
    today_str = now().strftime("%Y%m%d")
    path = Path(settings.BASE_DIR) / "temp" / "memberaudit_log" / today_str
    path.mkdir(parents=True, exist_ok=True)

    now_str = now().strftime("%Y%m%d%H%M")
    file_path = path / f"character_{character.pk}_{name}_{now_str}.json"
    try:
        with file_path.open("w", encoding="utf-8") as file:
            json.dump(lst, file, cls=DjangoJSONEncoder, sort_keys=True, indent=4)

        logger.info("Wrote debug data to: %s", file_path)

    except OSError:
        logger.exception("Failed to write debug data to: %s", file_path)
