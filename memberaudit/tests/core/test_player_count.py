import pook

from memberaudit.core import player_count
from memberaudit.tests.testdata.factories_2 import make_esi_url
from memberaudit.tests.utils import TestCaseWithClearCache

MODULE_PATH = "memberaudit.core.player_count"


class TestPlayerCount(TestCaseWithClearCache):
    @pook.on
    def test_should_return_player_count_when_available(self):
        # given
        pook.get(
            make_esi_url("status"),
            reply=200,
            response_json={
                "players": 12345,
                "server_version": "1132976",
                "start_time": "2017-01-02T12:34:56Z",
            },
        )
        player_count.clear_cache()

        # when
        got = player_count.get()

        # then
        self.assertEqual(got, 12345)

    @pook.on
    def test_should_return_player_count_from_cache(self):
        # given
        pook.get(  # this route is be used once only
            make_esi_url("status"),
            reply=200,
            response_json={
                "players": 12345,
                "server_version": "1132976",
                "start_time": "2017-01-02T12:34:56Z",
            },
        )
        player_count.clear_cache()
        player_count.get()

        # when
        got = player_count.get()

        # then
        self.assertEqual(got, 12345)

    @pook.on
    def test_should_return_none_when_esi_return_error_code(self):
        # given
        pook.get(
            make_esi_url("status"),
            reply=500,
            response_json={"error": "some error"},
        )
        player_count.clear_cache()

        # when
        got = player_count.get()

        # then
        self.assertIsNone(got)
