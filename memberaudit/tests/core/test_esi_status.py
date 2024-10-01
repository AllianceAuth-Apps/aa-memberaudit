from unittest.mock import patch

import requests_mock

from app_utils.testing import NoSocketsTestCase

from memberaudit.core import esi_status
from memberaudit.models import Character

MODULE_PATH = "memberaudit.core.esi_status"


@requests_mock.Mocker()
class TestUnavailableSections(NoSocketsTestCase):
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
            ],
        )
        # when
        got, ok = esi_status.unavailable_sections()
        # then
        self.assertTrue(ok)
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
        got, ok = esi_status.unavailable_sections()
        # then
        self.assertTrue(ok)
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
        _, ok = esi_status.unavailable_sections()
        # then
        self.assertFalse(ok)


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
        got, ok = esi_status._fetch_status()
        # then
        self.assertTrue(ok)
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
        _, ok = esi_status._fetch_status()
        # then
        self.assertFalse(ok)

    def test_should_report_json_error(self, requests_mocker):
        # given
        requests_mocker.register_uri(
            "GET",
            url="https://esi.evetech.net/status.json?version=latest",
            text="this is not json",
        )
        # when
        _, ok = esi_status._fetch_status()
        # then
        self.assertFalse(ok)


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
