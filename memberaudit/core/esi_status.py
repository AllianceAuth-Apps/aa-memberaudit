"""Determine which character sections are currently reported as unavailable by ESI."""

import random
from http import HTTPStatus
from time import sleep
from typing import List, Set, Tuple

import requests
from requests.exceptions import RequestException

from django.core.cache import cache

from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag

from memberaudit import __title__, __version__
from memberaudit.models import Character

logger = LoggerAddTag(get_extension_logger(__name__), __title__)

_CACHE_KEY = "memberaudit-esi-status"
_CACHE_TIMEOUT = 120
_ESI_STATUS_JSON_URL = "https://esi.evetech.net/status.json?version=latest"
_MAX_RETRIES = 3
_REQUEST_TIMEOUT = (5, 30)

# TODO: Add endpoints effecting multiple sections, e.g. universe/names
# TODO: Add all endpoints
_SECTION_2_ENDPOINTS = {
    Character.UpdateSection.LOYALTY: [
        {
            "endpoint": "esi-loyalty",
            "method": "get",
            "route": "/characters/{character_id}/loyalty/points/",
            "status": "red",
            "tags": ["Loyalty"],
        },
    ],
    Character.UpdateSection.MAILS: [
        {
            "method": "get",
            "route": "/characters/{character_id}/mail/",
        },
        {
            "method": "get",
            "route": "/characters/{character_id}/mail/",
        },
        {
            "method": "get",
            "route": "/characters/{character_id}/mail/labels/",
        },
        {
            "method": "get",
            "route": "/characters/{character_id}/mail/lists/",
        },
        {
            "method": "get",
            "route": "/characters/{character_id}/mail/{mail_id}/",
        },
    ],
}


def unavailable_sections() -> Tuple[Set[Character.UpdateSection], bool]:
    """Returns a set of all sections which endpoints are currently
    reported as "red" by ESI
    and reports whether there was an error fetching the current status from ESI.

    An empty set means that all sections are available.

    Results are cached.
    """
    status = cache.get(_CACHE_KEY)
    if status:
        return status, True

    status, ok = _unavailable_sections()
    if not ok:
        return set(), False

    cache.set(key=_CACHE_KEY, value=status, timeout=_CACHE_TIMEOUT)
    return status, True


def _unavailable_sections() -> Tuple[Set[Character.UpdateSection], bool]:
    status, ok = _fetch_status()
    if not ok or not status:
        return set(), False

    sections = _determine_unavailable_sections(status)
    return sections, True


def _fetch_status() -> Tuple[List[dict], bool]:
    try:
        r = _get_esi_status()
        r.raise_for_status()
        status = r.json()
    except RequestException as exc:
        logger.warning(f"Failed to get ESI status. Error: {exc}")
        return [], False
    return status, True


def _get_esi_status() -> requests.Response:
    """Fetch current ESI status. Retry on common HTTP errors."""
    retry_count = 0
    while True:
        response = requests.get(
            _ESI_STATUS_JSON_URL,
            timeout=_REQUEST_TIMEOUT,
            headers={"User-Agent": f"{__package__};{__version__}"},
        )
        if response.status_code not in {
            HTTPStatus.BAD_GATEWAY,
            HTTPStatus.SERVICE_UNAVAILABLE,
            HTTPStatus.GATEWAY_TIMEOUT,
        }:
            break

        retry_count += 1
        if retry_count == _MAX_RETRIES:
            break

        wait_secs = 0.1 * (random.uniform(2, 4) ** retry_count)
        logger.warning(
            "HTTP status code %s - Try %s/%s - Delay %f",
            response.status_code,
            retry_count,
            _MAX_RETRIES,
            wait_secs,
        )
        sleep(wait_secs)

    return response


def _determine_unavailable_sections(status):
    sections = set()
    red_endpoints = [ep for ep in status if ep["status"] == "red"]
    for section, ep in _SECTION_2_ENDPOINTS.items():
        if _is_section_broken(ep, red_endpoints):
            sections.add(section)
    return sections


def _is_section_broken(
    section_endpoints: List[dict], red_endpoints: List[dict]
) -> bool:
    for r in section_endpoints:
        for x in red_endpoints:
            if x["method"] == r["method"] and x["route"] == r["route"]:
                return True
    return False


def clear_cache():
    """Clear cache."""
    cache.delete(_CACHE_KEY)
