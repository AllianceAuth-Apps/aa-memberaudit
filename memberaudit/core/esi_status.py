"""Determine which character sections are currently reported as broken by ESI."""

import random
from time import sleep
from typing import List, Set, Tuple

import requests
from requests.exceptions import RequestException

from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag

from memberaudit import __title__, __version__
from memberaudit.models import Character

logger = LoggerAddTag(get_extension_logger(__name__), __title__)

ESI_STATUS_JSON_URL = "https://esi.evetech.net/status.json?version=latest"
TIMEOUT = (5, 30)
MAX_RETRIES = 3

# TODO: Add endpoints effecting multiple sections, e.g. universe/names
# TODO: Add all endpoints
SECTION_2_ENDPOINTS = {
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


def broken_sections() -> Tuple[Set[Character.UpdateSection], bool]:
    """Returns a set of all sections which endpoints are currently reported
    as "red" by ESI and reports whether there was an error fetching
    the current status from ESI.
    An empty set means that all sections are available.
    """
    status, ok = _fetch_status()
    if not ok:
        return set(), False

    sections = _determine_broken_sections(status)
    return sections, True


def _fetch_status() -> Tuple[List[dict], bool]:
    try:
        r = _request_esi_status()
        r.raise_for_status()
        status = r.json()
    except RequestException as exc:
        logger.warning(f"Failed to get ESI status. Error: {exc}")
        return [], False
    return status, True


def _request_esi_status() -> requests.Response:
    """Fetch current ESI status. Retry on common HTTP errors."""
    retry_count = 0
    while True:
        response = requests.get(
            ESI_STATUS_JSON_URL,
            timeout=TIMEOUT,
            headers={"User-Agent": f"{__package__};{__version__}"},
        )
        if response.status_code not in {
            502,  # HTTPBadGateway
            503,  # HTTPServiceUnavailable
            504,  # HTTPGatewayTimeout
        }:
            break

        retry_count += 1
        if retry_count > MAX_RETRIES:
            break

        logger.warning(
            "HTTP status code %s - Try %s/%s",
            response.status_code,
            retry_count,
            MAX_RETRIES,
        )

        wait_secs = 0.1 * (random.uniform(2, 4) ** (retry_count - 1))
        sleep(wait_secs)

    return response


def _determine_broken_sections(status):
    sections = set()
    red_endpoints = [ep for ep in status if ep["status"] == "red"]
    for section, ep in SECTION_2_ENDPOINTS.items():
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
