from unittest.mock import patch

from django.test import TestCase

from app_utils.esi_testing import EsiClientStub, EsiEndpoint

from memberaudit.core.eve_status import player_count, update

MODULE_PATH = "memberaudit.core.eve_status"


@patch(MODULE_PATH + ".esi")
class TestPlayerCount(TestCase):
    def test_should_return_player_count_when_available(self, mock_esi):
        # given
        endpoints = [
            EsiEndpoint(
                "Status",
                "get_status",
                data={
                    "players": 12345,
                    "server_version": "1132976",
                    "start_time": "2017-01-02T12:34:56Z",
                },
            )
        ]
        mock_esi.client = EsiClientStub.create_from_endpoints(endpoints)
        update()

        # when
        result = player_count()

        # then
        self.assertEqual(result, 12345)

    def test_should_return_none_when_esi_offline(self, mock_esi):
        # given
        endpoints = [EsiEndpoint("Status", "get_status", http_error_code=500)]
        mock_esi.client = EsiClientStub.create_from_endpoints(endpoints)
        update()

        # when
        result = player_count()

        # then
        self.assertIsNone(result)
