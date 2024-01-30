"""Provide cached access to the current player count of the Eve server."""

from typing import Optional

from django.core.cache import cache

from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag

from memberaudit import __title__
from memberaudit.providers import esi

logger = LoggerAddTag(get_extension_logger(__name__), __title__)

_CACHE_KEY = "memberaudit-eve-status"
_TIMEOUT = 30 * 60


def player_count() -> Optional[int]:
    """Return cached player count from ESI or None if offline."""
    try:
        return int(cache.get(_CACHE_KEY))
    except TypeError:
        return None


def update():
    """Update status from ESI."""
    current_player_count = _fetch_player_count()
    cache.set(key=_CACHE_KEY, value=current_player_count, timeout=_TIMEOUT)
    logger.info("Updated player count from ESI")


def _fetch_player_count() -> Optional[int]:
    try:
        result: dict = esi.client.Status.get_status().results()
    except OSError:
        return None

    return result.get("players")
