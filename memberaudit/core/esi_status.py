"""Determine which character sections are currently reported as unavailable by ESI."""

import dataclasses
import random
from http import HTTPStatus
from time import sleep
from typing import Any, Dict, List, Optional, Set

import requests
from requests.exceptions import RequestException

from django.conf import settings
from django.core.cache import cache

from allianceauth.services.hooks import get_extension_logger

from memberaudit import __version__
from memberaudit.models import Character

logger = get_extension_logger(__name__)

_CACHE_KEY = "memberaudit-esi-status"
_CACHE_TIMEOUT = 120
_ESI_STATUS_JSON_URL = "https://esi.evetech.net/meta/status"
_COMPATIBILITY_DATE = "2025-12-16"
_MAX_RETRIES = 3
_REQUEST_TIMEOUT = (5, 30)


@dataclasses.dataclass
class _Endpoint:
    """A ESI endpoint."""

    method: str
    path: str

    def __post_init__(self):
        if not self.method or not self.path or self.method not in {"GET", "POST"}:
            raise ValueError(f"invalid: {self}")

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "_Endpoint":
        """Create a new object from a dict."""
        return cls(method=d["method"], path=d["path"])


_REQUIRED_ENDPOINTS_FOR_SECTIONS = {
    Character.UpdateSection.ASSETS: [
        _Endpoint("GET", "/characters/{character_id}/assets"),
        _Endpoint("POST", "/characters/{character_id}/assets/names"),
    ],
    Character.UpdateSection.ATTRIBUTES: [
        _Endpoint("GET", "/characters/{character_id}/attributes"),
    ],
    Character.UpdateSection.CHARACTER_DETAILS: [
        _Endpoint("GET", "/characters/{character_id}"),
    ],
    Character.UpdateSection.CONTACTS: [
        _Endpoint("GET", "/characters/{character_id}/contacts"),
    ],
    Character.UpdateSection.CONTRACTS: [
        _Endpoint("GET", "/characters/{character_id}/contracts"),
        _Endpoint("GET", "/characters/{character_id}/contracts/{contract_id}/bids"),
        _Endpoint("GET", "/characters/{character_id}/contracts/{contract_id}/items"),
    ],
    Character.UpdateSection.CORPORATION_HISTORY: [
        _Endpoint("GET", "/characters/{character_id}/corporationhistory"),
    ],
    Character.UpdateSection.FW_STATS: [
        _Endpoint("GET", "/characters/{character_id}/fw/stats"),
    ],
    Character.UpdateSection.IMPLANTS: [
        _Endpoint("GET", "/characters/{character_id}/implants"),
    ],
    Character.UpdateSection.JUMP_CLONES: [
        _Endpoint("GET", "/characters/{character_id}/clones"),
    ],
    Character.UpdateSection.LOCATION: [
        _Endpoint("GET", "/characters/{character_id}/location"),
    ],
    Character.UpdateSection.LOYALTY: [
        _Endpoint("GET", "/characters/{character_id}/loyalty/points"),
    ],
    Character.UpdateSection.MAILS: [
        _Endpoint("GET", "/characters/{character_id}/mail"),
        _Endpoint("GET", "/characters/{character_id}/mail/labels"),
        _Endpoint("GET", "/characters/{character_id}/mail/lists"),
        _Endpoint("GET", "/characters/{character_id}/mail/{mail_id}"),
    ],
    Character.UpdateSection.MINING_LEDGER: [
        _Endpoint("GET", "/characters/{character_id}/mining"),
    ],
    Character.UpdateSection.ONLINE_STATUS: [
        _Endpoint("GET", "/characters/{character_id}/online"),
    ],
    Character.UpdateSection.PLANETS: [
        _Endpoint("GET", "/characters/{character_id}/planets"),
    ],
    Character.UpdateSection.ROLES: [
        _Endpoint("GET", "/characters/{character_id}/roles"),
    ],
    Character.UpdateSection.SHIP: [
        _Endpoint("GET", "/characters/{character_id}/ship"),
    ],
    Character.UpdateSection.SKILLS: [
        _Endpoint("GET", "/characters/{character_id}/skills"),
    ],
    Character.UpdateSection.SKILL_QUEUE: [
        _Endpoint("GET", "/characters/{character_id}/skillqueue"),
    ],
    Character.UpdateSection.STANDINGS: [
        _Endpoint("GET", "/characters/{character_id}/standings"),
    ],
    Character.UpdateSection.TITLES: [
        _Endpoint("GET", "/characters/{character_id}/titles"),
    ],
    Character.UpdateSection.WALLET_BALLANCE: [
        _Endpoint("GET", "/characters/{character_id}/wallet"),
    ],
    Character.UpdateSection.WALLET_JOURNAL: [
        _Endpoint("GET", "/characters/{character_id}/wallet/journal"),
    ],
    Character.UpdateSection.WALLET_TRANSACTIONS: [
        _Endpoint("GET", "/characters/{character_id}/wallet/transactions"),
    ],
}
"""Endpoints which must be available for an endpoint to function."""


def unavailable_sections() -> Optional[Set[Character.UpdateSection]]:
    """Returns a set of all sections which endpoints are currently
    reported as "red" by ESI. Returns None if there was a failure.

    An empty set means that all sections are available.

    Results are cached.
    """
    with cache.lock("memberaudit-esi-status-lock"):
        return cache.get_or_set(
            _CACHE_KEY,
            _fetch_unavailable_sections,
            timeout=_CACHE_TIMEOUT,
        )


def _fetch_unavailable_sections() -> Optional[Set[Character.UpdateSection]]:
    status = _fetch_status()
    if status is None:
        return None

    sections = _determine_unavailable_sections(status)
    return sections


def _fetch_status() -> Optional[List[Dict[str, Any]]]:
    try:
        r = _get_esi_status()
        r.raise_for_status()
        status = r.json()
    except RequestException as exc:
        logger.warning("Failed to get ESI status. Error: %s", exc)
        return None

    return status


def _get_esi_status() -> requests.Response:
    """Fetch current ESI status. Retry on common HTTP errors."""
    email = getattr(settings, "ESI_USER_CONTACT_EMAIL", "kalkoken87@gmail.com")

    retry_count = 0
    while True:
        response = requests.get(
            _ESI_STATUS_JSON_URL,
            timeout=_REQUEST_TIMEOUT,
            headers={
                "User-Agent": f"aa-memberaudit v{__version__} ({email})",
                "X-Compatibility-Date": _COMPATIBILITY_DATE,
            },
        )
        logger.debug(
            "esi status response: %s %s %s",
            response.status_code,
            response.headers,
            response.text,
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


def _determine_unavailable_sections(
    status: Dict[str, List[Dict[str, Any]]],
) -> Optional[Set[Character.UpdateSection]]:
    routes = status.get("routes", [])
    if not routes:
        return None

    red_endpoints = [_Endpoint.from_dict(ep) for ep in routes if ep["status"] == "Down"]
    sections: Set[Character.UpdateSection] = set()
    for section, ep in _REQUIRED_ENDPOINTS_FOR_SECTIONS.items():
        if _is_section_broken(ep, red_endpoints):
            sections.add(section)
    return sections


def _is_section_broken(
    section_endpoints: List[_Endpoint], red_endpoints: List[_Endpoint]
) -> bool:
    for sep in section_endpoints:
        for rep in red_endpoints:
            if rep.method == sep.method and rep.path == sep.path:
                return True
    return False


def clear_cache():
    """Clear cache."""
    cache.delete(_CACHE_KEY)
