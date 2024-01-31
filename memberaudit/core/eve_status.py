"""Provide cached access to the current player count of the Eve server."""

from typing import Optional

from django.core.cache import cache

from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag

from memberaudit import __title__
from memberaudit.providers import esi

logger = LoggerAddTag(get_extension_logger(__name__), __title__)

_CACHE_KEY = "memberaudit-eve-status"
_TIMEOUT = 1 * 60


def player_count() -> Optional[int]:
    """Return cached player count from ESI or None if offline."""
    return cache.get_or_set(
        key=_CACHE_KEY, default=_fetch_player_count, timeout=_TIMEOUT
    )


def clear_cache():
    """Clear cache."""
    cache.delete(_CACHE_KEY)


def _fetch_player_count() -> Optional[int]:
    try:
        result: dict = esi.client.Status.get_status().results()
    except OSError:
        return None

    return result.get("players")
