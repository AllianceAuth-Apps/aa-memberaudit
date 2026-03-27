import json
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import requests_mock

from app_utils.testing import CacheFake, NoSocketsTestCase

from memberaudit.core import esi_status
from memberaudit.models import Character

MODULE_PATH = "memberaudit.core.esi_status"


class TestEndpoint(NoSocketsTestCase):
    def test_should_not_allow_invalid_creation(self):
        cases = [
            ("", ""),
            ("xxx", "/characters/{character_id}"),
            ("", "/characters/{character_id}"),
            ("GET", ""),
        ]
        for method, path in cases:
            with self.subTest(method=method, path=path):
                with self.assertRaises(ValueError):
                    esi_status._Endpoint(method=method, path=path)

    def test_can_create_from_dict(self):
        ep = esi_status._Endpoint.from_dict(
            {
                "method": "GET",
                "path": "/characters/{character_id}/assets",
                "status": "OK",
            },
        )
        self.assertEqual(ep.method, "GET")
        self.assertEqual(ep.path, "/characters/{character_id}/assets")


class CacheFake2(CacheFake):
    def get_or_set(self, key, default, timeout=None):
        v = self.get(key)
        if v is not None:
            return v
        v = default()
        self.set(key, default, timeout)
        return v

    @contextmanager
    def lock(self, key):
        yield None


@patch(MODULE_PATH + "._fetch_unavailable_sections", spec=True)
@patch(MODULE_PATH + ".cache", new_callable=CacheFake2)
class TestUnavailableSections(NoSocketsTestCase):
    def test_should_fetch_from_api_and_update_cache_when_cache_empty(
        self, _, mock_fetch_unavailable_sections
    ):
        v1 = {Character.UpdateSection.ASSETS}
        mock_fetch_unavailable_sections.return_value = v1
        x = esi_status.unavailable_sections()
        self.assertSetEqual(x, v1)

    def test_should_return_from_cache_when_cache_has_value(
        self, mock_cache: CacheFake2, _
    ):
        mock_cache.set(esi_status._CACHE_KEY, {Character.UpdateSection.ASSETS})
        x = esi_status.unavailable_sections()
        self.assertSetEqual(x, {Character.UpdateSection.ASSETS})

    def test_should_return_none_on_failure(self, _, mock_fetch_unavailable_sections):
        mock_fetch_unavailable_sections.return_value = None
        x = esi_status.unavailable_sections()
        self.assertIsNone(x)


@requests_mock.Mocker()
class TestUnavailableSections2(NoSocketsTestCase):
    def test_should_return_fetch_unavailable_sections_as_reported_by_ESI(
        self, requests_mocker
    ):
        # given
        requests_mocker.register_uri(
            "GET",
            url="https://esi.evetech.net/meta/status",
            request_headers={"X-Compatibility-Date": "2025-12-16"},
            json={
                "routes": [
                    {
                        "method": "GET",
                        "path": "/characters/{character_id}/mail",
                        "status": "OK",
                    },
                    {
                        "method": "GET",
                        "path": "/characters/{character_id}/loyalty/points",
                        "status": "Down",
                    },
                    {
                        "method": "GET",
                        "path": "/characters/{character_id}/loyalty/points/xyz",
                        "status": "OK",
                    },
                ]
            },
        )
        # when
        got = esi_status._fetch_unavailable_sections()
        # then
        want = {Character.UpdateSection.LOYALTY}
        self.assertEqual(want, got)

    def test_should_return_an_empty_set_when_all_sections_available(
        self, requests_mocker
    ):
        # given
        requests_mocker.register_uri(
            "GET",
            url="https://esi.evetech.net/meta/status",
            request_headers={"X-Compatibility-Date": "2025-12-16"},
            json={
                "routes": [
                    {
                        "method": "GET",
                        "path": "/characters/{character_id}/mail",
                        "status": "OK",
                    },
                    {
                        "method": "GET",
                        "path": "/characters/{character_id}/loyalty/points",
                        "status": "OK",
                    },
                ]
            },
        )
        # when
        got = esi_status._fetch_unavailable_sections()
        # then
        want = set()
        self.assertEqual(want, got)

    def test_should_report_when_esi_status_could_not_be_fetched(self, requests_mocker):
        # given
        requests_mocker.register_uri(
            "GET",
            url="https://esi.evetech.net/meta/status",
            request_headers={"X-Compatibility-Date": "2025-12-16"},
            status_code=500,
        )
        # when
        got = esi_status._fetch_unavailable_sections()
        # then
        self.assertIsNone(got)

    def test_should_return_as_error_when_no_endpoints_are_returned(
        self, requests_mocker
    ):
        # given
        requests_mocker.register_uri(
            "GET",
            url="https://esi.evetech.net/meta/status",
            request_headers={"X-Compatibility-Date": "2025-12-16"},
            json={"routes": []},
        )
        # when
        got = esi_status._fetch_unavailable_sections()
        # then
        self.assertIsNone(got)


@requests_mock.Mocker()
class TestFetchStatus(NoSocketsTestCase):
    def test_can_fetch_status(self, requests_mocker):
        # given
        requests_mocker.register_uri(
            "GET",
            url="https://esi.evetech.net/meta/status",
            request_headers={"X-Compatibility-Date": "2025-12-16"},
            json={
                "routes": [
                    {
                        "method": "GET",
                        "path": "/characters/{character_id}/mail",
                        "status": "OK",
                    },
                ]
            },
        )
        # when
        got = esi_status._fetch_status()
        # then
        want = {
            "routes": [
                {
                    "method": "GET",
                    "path": "/characters/{character_id}/mail",
                    "status": "OK",
                },
            ]
        }
        self.assertEqual(want, got)

    def test_should_report_http_error(self, requests_mocker):
        # given
        requests_mocker.register_uri(
            "GET",
            url="https://esi.evetech.net/meta/status",
            request_headers={"X-Compatibility-Date": "2025-12-16"},
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
            url="https://esi.evetech.net/meta/status",
            request_headers={"X-Compatibility-Date": "2025-12-16"},
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
            url="https://esi.evetech.net/meta/status",
            request_headers={"X-Compatibility-Date": "2025-12-16"},
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
            url="https://esi.evetech.net/meta/status",
            request_headers={"X-Compatibility-Date": "2025-12-16"},
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
            url="https://esi.evetech.net/meta/status",
            request_headers={"X-Compatibility-Date": "2025-12-16"},
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

        valid_endpoints = {(ep["method"], ep["path"]) for ep in status["routes"]}
        for s, endpoints in esi_status._REQUIRED_ENDPOINTS_FOR_SECTIONS.items():
            endpoints: list[esi_status._Endpoint]
            for ep in endpoints:
                if (ep.method, ep.path) not in valid_endpoints:
                    self.fail(f"{s}: invalid path: {ep}")
                    self.fail(f"{s}: invalid path: {ep}")
