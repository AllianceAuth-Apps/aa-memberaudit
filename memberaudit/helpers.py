"""Helpers for Member Audit."""

import datetime as dt
from typing import Optional

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
