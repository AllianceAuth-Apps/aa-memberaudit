import json
from pathlib import Path
from unittest.mock import patch

import requests_mock

from app_utils.testing import NoSocketsTestCase

from memberaudit.core import esi_status
from memberaudit.models import Character

MODULE_PATH = "memberaudit.core.esi_status"


class TestEndpoint(NoSocketsTestCase):
    def test_should_not_allow_invalid_creation(self):
        cases = [
            ("", ""),
            ("xxx", "/characters/{character_id}"),
            ("", "/characters/{character_id}"),
            ("get", ""),
        ]
        for method, route in cases:
            with self.subTest(method=method, route=route):
                with self.assertRaises(ValueError):
                    esi_status._Endpoint(method=method, route=route)

    def test_can_create_from_dict(self):
        ep = esi_status._Endpoint.from_dict(
            {
                "endpoint": "esi-assets",
                "method": "get",
                "route": "/characters/{character_id}/assets/",
                "status": "green",
                "tags": ["Assets"],
            },
        )
        self.assertEqual(ep.method, "get")
        self.assertEqual(ep.route, "/characters/{character_id}/assets/")


@patch(MODULE_PATH + "._unavailable_sections", spec=True)
@patch(MODULE_PATH + ".cache.set", spec=True)
@patch(MODULE_PATH + ".cache.get", spec=True)
class TestUnavailableSections(NoSocketsTestCase):
    def test_should_return_from_cache(
        self, mock_cache_get, mock_cache_set, mock_unavailable_sections
    ):
        mock_cache_get.return_value = {Character.UpdateSection.ASSETS}
        x = esi_status.unavailable_sections()
        self.assertSetEqual(x, {Character.UpdateSection.ASSETS})

    def test_should_update_cache_and_return_new_value(
        self, mock_cache_get, mock_cache_set, mock_unavailable_sections
    ):
        mock_cache_get.return_value = None
        mock_unavailable_sections.return_value = {Character.UpdateSection.ASSETS}
        x = esi_status.unavailable_sections()
        self.assertSetEqual(x, {Character.UpdateSection.ASSETS})
        self.assertTrue(mock_cache_set.called)

    def test_should_none_on_failure(
        self, mock_cache_get, mock_cache_set, mock_unavailable_sections
    ):
        mock_cache_get.return_value = None
        mock_unavailable_sections.return_value = None
        x = esi_status.unavailable_sections()
        self.assertIsNone(x)
        self.assertFalse(mock_cache_set.called)


@requests_mock.Mocker()
class TestUnavailableSections2(NoSocketsTestCase):
    def test_should_return_unavailable_sections_as_reported_by_ESI(
        self, requests_mocker
    ):
        # given
        requests_mocker.register_uri(
            "GET",
            url="https://esi.evetech.net/status.json?version=latest",
            json=[
                {
                    "endpoint": "esi-mail",
                    "method": "get",
                    "route": "/characters/{character_id}/mail/",
                    "status": "green",
                    "tags": ["Mail"],
                },
                {
                    "endpoint": "esi-loyalty",
                    "method": "get",
                    "route": "/characters/{character_id}/loyalty/points/",
                    "status": "red",
                    "tags": ["Loyalty"],
                },
                {
                    "endpoint": "esi-loyalty",
                    "method": "get",
                    "route": "/characters/{character_id}/loyalty/points/xy/",
                    "status": "green",
                    "tags": ["Loyalty"],
                },
            ],
        )
        # when
        got = esi_status._unavailable_sections()
        # then
        want = {Character.UpdateSection.LOYALTY}
        self.assertEqual(want, got)

    def test_should_return_an_empty_set_when_all_sections_available(
        self, requests_mocker
    ):
        # given
        requests_mocker.register_uri(
            "GET",
            url="https://esi.evetech.net/status.json?version=latest",
            json=[
                {
                    "endpoint": "esi-mail",
                    "method": "get",
                    "route": "/characters/{character_id}/mail/",
                    "status": "green",
                    "tags": ["Mail"],
                },
                {
                    "endpoint": "esi-loyalty",
                    "method": "get",
                    "route": "/characters/{character_id}/loyalty/points/",
                    "status": "green",
                    "tags": ["Loyalty"],
                },
            ],
        )
        # when
        got = esi_status._unavailable_sections()
        # then
        want = set()
        self.assertEqual(want, got)

    def test_should_report_when_esi_status_could_not_be_fetched(self, requests_mocker):
        # given
        requests_mocker.register_uri(
            "GET",
            url="https://esi.evetech.net/status.json?version=latest",
            status_code=500,
        )
        # when
        got = esi_status._unavailable_sections()
        # then
        self.assertIsNone(got)

    def test_should_return_as_error_when_no_endpoints_are_returned(
        self, requests_mocker
    ):
        # given
        requests_mocker.register_uri(
            "GET",
            url="https://esi.evetech.net/status.json?version=latest",
            json=[],
        )
        # when
        got = esi_status._unavailable_sections()
        # then
        self.assertIsNone(got)


@requests_mock.Mocker()
class TestFetchStatus(NoSocketsTestCase):
    def test_can_fetch_status(self, requests_mocker):
        # given
        requests_mocker.register_uri(
            "GET",
            url="https://esi.evetech.net/status.json?version=latest",
            json=[
                {
                    "endpoint": "esi-mail",
                    "method": "get",
                    "route": "/characters/{character_id}/mail/",
                    "status": "green",
                    "tags": ["Mail"],
                }
            ],
        )
        # when
        got = esi_status._fetch_status()
        # then
        want = [
            {
                "endpoint": "esi-mail",
                "method": "get",
                "route": "/characters/{character_id}/mail/",
                "status": "green",
                "tags": ["Mail"],
            }
        ]
        self.assertListEqual(want, got)

    def test_should_report_http_error(self, requests_mocker):
        # given
        requests_mocker.register_uri(
            "GET",
            url="https://esi.evetech.net/status.json?version=latest",
            status_code=500,
        )
        # when
        got = esi_status._fetch_status()
        # then
        self.assertIsNone(got)

    def test_should_report_json_error(self, requests_mocker):
        # given
        requests_mocker.register_uri(
            "GET",
            url="https://esi.evetech.net/status.json?version=latest",
            text="this is not json",
        )
        # when
        got = esi_status._fetch_status()
        # then
        self.assertIsNone(got)


@patch(MODULE_PATH + ".sleep", lambda x: None)
@requests_mock.Mocker()
class TestGetEsiStatus(NoSocketsTestCase):
    def test_should_return_response_when_ok(self, requests_mocker):
        requests_mocker.register_uri(
            "GET",
            url="https://esi.evetech.net/status.json?version=latest",
            text="ok",
        )
        # when
        got = esi_status._get_esi_status()
        # then
        self.assertTrue(got.ok)
        self.assertEqual(got.text, "ok")
        self.assertEqual(requests_mocker.call_count, 1)

    def test_should_return_most_errors_directly(self, requests_mocker):
        requests_mocker.register_uri(
            "GET",
            url="https://esi.evetech.net/status.json?version=latest",
            status_code=500,
        )
        # when
        got = esi_status._get_esi_status()
        # then
        self.assertEqual(got.status_code, 500)
        self.assertEqual(requests_mocker.call_count, 1)

    def test_should_retry_on_specific_errors(self, requests_mocker):
        requests_mocker.register_uri(
            "GET",
            url="https://esi.evetech.net/status.json?version=latest",
            status_code=503,
        )
        # when
        got = esi_status._get_esi_status()
        # then
        self.assertEqual(got.status_code, 503)
        self.assertEqual(requests_mocker.call_count, 3)


class TestSectionEndpointsDef(NoSocketsTestCase):
    def test_all_sections_must_have_endpoints_defined(self):
        excluded = {Character.UpdateSection.SKILL_SETS}
        for s in Character.UpdateSection:
            if s in excluded:
                continue
            if s not in esi_status._REQUIRED_ENDPOINTS_FOR_SECTIONS:
                self.fail(f"does not cover section: {s}")
            if len(esi_status._REQUIRED_ENDPOINTS_FOR_SECTIONS[s]) == 0:
                self.fail(f"missing endpoints definition for section: {s}")

    def test_section_endpoints_must_be_valid(self):
        # given
        p = Path(__file__).parent / "esi_status_example.json"
        with p.open("r", encoding="utf8") as f:
            status = json.load(f)
        valid_endpoints = {(ep["method"], ep["route"]) for ep in status}
        for s, endpoints in esi_status._REQUIRED_ENDPOINTS_FOR_SECTIONS.items():
            endpoints: list[esi_status._Endpoint]
            for ep in endpoints:
                if (ep.method, ep.route) not in valid_endpoints:
                    self.fail(f"{s}: invalid route: {ep}")
