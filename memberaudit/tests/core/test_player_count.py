from unittest.mock import patch

from django.test import TestCase

from app_utils.esi_testing import EsiClientStub, EsiEndpoint

from memberaudit.core.player_count import _fetch_player_count, clear_cache, get

MODULE_PATH = "memberaudit.core.player_count"


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
        clear_cache()

        # when
        result = get()

        # then
        self.assertEqual(result, 12345)

    def test_should_return_player_count_from_cache(self, mock_esi):
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
        clear_cache()
        get()

        # when
        with patch(
            MODULE_PATH + "._fetch_player_count", wraps=_fetch_player_count
        ) as spy:
            result = get()

            # then
            self.assertEqual(result, 12345)
            self.assertFalse(spy.called)

    def test_should_return_none_when_esi_offline(self, mock_esi):
        # given
        endpoints = [EsiEndpoint("Status", "get_status", http_error_code=500)]
        mock_esi.client = EsiClientStub.create_from_endpoints(endpoints)
        clear_cache()

        # when
        result = get()

        # then
        self.assertIsNone(result)
