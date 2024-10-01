import requests_mock

from app_utils.testing import NoSocketsTestCase

from memberaudit.core import esi_status
from memberaudit.models import Character


@requests_mock.Mocker()
class TestBrokenSections(NoSocketsTestCase):
    def test_normal(self, requests_mocker):
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
        got, ok = esi_status.broken_sections()
        # then
        self.assertTrue(ok)
        want = {Character.UpdateSection.LOYALTY}
        self.assertEqual(want, got)
