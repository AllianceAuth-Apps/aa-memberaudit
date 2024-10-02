"""Determine which character sections are currently reported as unavailable by ESI."""

import dataclasses
import random
from http import HTTPStatus
from time import sleep
from typing import Any, Dict, List, Optional, Set

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


@dataclasses.dataclass
class _Endpoint:
    """A ESI endpoint."""

    method: str
    route: str

    def __post_init__(self):
        if not self.method or not self.route or self.method not in {"get", "post"}:
            raise ValueError(f"invalid: {self}")

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "_Endpoint":
        """Create a new object from a dict."""
        return cls(method=d["method"], route=d["route"])


_REQUIRED_ENDPOINTS_FOR_SECTIONS = {
    Character.UpdateSection.ASSETS: [
        _Endpoint("get", "/characters/{character_id}/assets/"),
        _Endpoint("post", "/characters/{character_id}/assets/names/"),
    ],
    Character.UpdateSection.ATTRIBUTES: [
        _Endpoint("get", "/characters/{character_id}/attributes/"),
    ],
    Character.UpdateSection.CHARACTER_DETAILS: [
        _Endpoint("get", "/characters/{character_id}/"),
    ],
    Character.UpdateSection.CONTACTS: [
        _Endpoint("get", "/characters/{character_id}/contacts/"),
    ],
    Character.UpdateSection.CONTRACTS: [
        _Endpoint("get", "/characters/{character_id}/contracts/"),
        _Endpoint("get", "/characters/{character_id}/contracts/{contract_id}/bids/"),
        _Endpoint("get", "/characters/{character_id}/contracts/{contract_id}/items/"),
    ],
    Character.UpdateSection.CORPORATION_HISTORY: [
        _Endpoint("get", "/characters/{character_id}/corporationhistory/"),
    ],
    Character.UpdateSection.FW_STATS: [
        _Endpoint("get", "/characters/{character_id}/fw/stats/"),
    ],
    Character.UpdateSection.IMPLANTS: [
        _Endpoint("get", "/characters/{character_id}/implants/"),
    ],
    Character.UpdateSection.JUMP_CLONES: [
        _Endpoint("get", "/characters/{character_id}/clones/"),
    ],
    Character.UpdateSection.LOCATION: [
        _Endpoint("get", "/characters/{character_id}/location/"),
    ],
    Character.UpdateSection.LOYALTY: [
        _Endpoint("get", "/characters/{character_id}/loyalty/points/"),
    ],
    Character.UpdateSection.MAILS: [
        _Endpoint("get", "/characters/{character_id}/mail/"),
        _Endpoint("get", "/characters/{character_id}/mail/labels/"),
        _Endpoint("get", "/characters/{character_id}/mail/lists/"),
        _Endpoint("get", "/characters/{character_id}/mail/{mail_id}/"),
    ],
    Character.UpdateSection.MINING_LEDGER: [
        _Endpoint("get", "/characters/{character_id}/mining/"),
    ],
    Character.UpdateSection.ONLINE_STATUS: [
        _Endpoint("get", "/characters/{character_id}/online/"),
    ],
    Character.UpdateSection.PLANETS: [
        _Endpoint("get", "/characters/{character_id}/planets/"),
    ],
    Character.UpdateSection.ROLES: [
        _Endpoint("get", "/characters/{character_id}/roles/"),
    ],
    Character.UpdateSection.SHIP: [
        _Endpoint("get", "/characters/{character_id}/ship/"),
    ],
    Character.UpdateSection.SKILLS: [
        _Endpoint("get", "/characters/{character_id}/skills/"),
    ],
    Character.UpdateSection.SKILL_QUEUE: [
        _Endpoint("get", "/characters/{character_id}/skillqueue/"),
    ],
    Character.UpdateSection.STANDINGS: [
        _Endpoint("get", "/characters/{character_id}/standings/"),
    ],
    Character.UpdateSection.TITLES: [
        _Endpoint("get", "/characters/{character_id}/titles/"),
    ],
    Character.UpdateSection.WALLET_BALLANCE: [
        _Endpoint("get", "/characters/{character_id}/wallet/"),
    ],
    Character.UpdateSection.WALLET_JOURNAL: [
        _Endpoint("get", "/characters/{character_id}/wallet/journal/"),
    ],
    Character.UpdateSection.WALLET_TRANSACTIONS: [
        _Endpoint("get", "/characters/{character_id}/wallet/transactions/"),
    ],
}
"""Endpoints which must be available for an endpoint to function."""


def unavailable_sections() -> Optional[Set[Character.UpdateSection]]:
    """Returns a set of all sections which endpoints are currently
    reported as "red" by ESI. Returns None if there was a failure.

    An empty set means that all sections are available.

    Results are cached.
    """
    status = cache.get(_CACHE_KEY)
    if status:
        return status

    status = _unavailable_sections()
    if status is None:
        return None

    cache.set(key=_CACHE_KEY, value=status, timeout=_CACHE_TIMEOUT)
    return status


def _unavailable_sections() -> Optional[Set[Character.UpdateSection]]:
    status = _fetch_status()
    if not status:
        return None

    sections = _determine_unavailable_sections(status)
    return sections


def _fetch_status() -> Optional[List[Dict[str, Any]]]:
    try:
        r = _get_esi_status()
        r.raise_for_status()
        status = r.json()
    except RequestException as exc:
        logger.warning(f"Failed to get ESI status. Error: {exc}")
        return None
    return status


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


def _determine_unavailable_sections(
    status: List[Dict[str, Any]]
) -> Set[Character.UpdateSection]:
    sections: Set[Character.UpdateSection] = set()
    red_endpoints = [_Endpoint.from_dict(ep) for ep in status if ep["status"] == "red"]
    for section, ep in _REQUIRED_ENDPOINTS_FOR_SECTIONS.items():
        if _is_section_broken(ep, red_endpoints):
            sections.add(section)
    return sections


def _is_section_broken(
    section_endpoints: List[_Endpoint], red_endpoints: List[_Endpoint]
) -> bool:
    for sep in section_endpoints:
        for rep in red_endpoints:
            if rep.method == sep.method and rep.route == sep.route:
                return True
    return False


def clear_cache():
    """Clear cache."""
    cache.delete(_CACHE_KEY)
