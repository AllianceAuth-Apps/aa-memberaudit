"""Helpers for Member Audit."""

import datetime as dt
import json
import os
from typing import Any, Optional

from django.core.serializers.json import DjangoJSONEncoder
from django.utils.timezone import now

from app_utils.datetime import datetime_round_hour

from memberaudit.app_settings import MEMBERAUDIT_DATA_RETENTION_LIMIT


def data_retention_cutoff() -> Optional[dt.datetime]:
    """returns cutoff datetime for data retention of None if unlimited"""
    if MEMBERAUDIT_DATA_RETENTION_LIMIT is None:
        return None
    return datetime_round_hour(
        now() - dt.timedelta(days=MEMBERAUDIT_DATA_RETENTION_LIMIT)
    )


def store_debug_data_to_disk(character, lst: Any, name: str):
    """Store character related data as JSON file to disk. For debugging

    Will store under memberaudit_logs/{DATE}/{CHARACTER_PK}_{NAME}.json
    """
    today_str = now().strftime("%Y%m%d")
    now_str = now().strftime("%Y%m%d%H%M")
    path = f"memberaudit_log/{today_str}"
    if not os.path.isdir(path):
        os.makedirs(path)

    fullpath = os.path.join(path, f"character_{character.pk}_{name}_{now_str}.json")
    try:
        with open(fullpath, "w", encoding="utf-8") as f:
            json.dump(lst, f, cls=DjangoJSONEncoder, sort_keys=True, indent=4)

    except OSError:
        pass
