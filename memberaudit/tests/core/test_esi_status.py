from unittest import skip
from unittest.mock import patch

import requests_mock

from app_utils.testing import NoSocketsTestCase

from memberaudit.core import esi_status
from memberaudit.models import Character

MODULE_PATH = "memberaudit.core.esi_status"


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


@skip("while not complete")  # FIXME
class TestEnsureAllSectionsAreCovered(NoSocketsTestCase):
    def test_should_cover_all_sections(self):
        for s in Character.UpdateSection:
            if s not in esi_status._SECTION_2_ENDPOINTS:
                self.fail(f"esi status: does not cover section: {s}")
            if len(esi_status._SECTION_2_ENDPOINTS[s]) == 0:
                self.fail(f"esi status: missing endpoints definition for section: {s}")
