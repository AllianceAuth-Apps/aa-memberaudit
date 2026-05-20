import datetime as dt
from http import HTTPStatus
from unittest.mock import patch

import pook

from django.test import override_settings
from django.utils.timezone import now
from eveuniverse.tests.testdata.factories_2 import ShipTypeFactory

from memberaudit import tasks
from memberaudit.models import Character, CharacterUpdateStatus
from memberaudit.tests.testdata.factories_2 import CharacterFactory, make_esi_url
from memberaudit.tests.utils import TestCaseWithClearCache

TASKS_PATH = "memberaudit.tasks"


@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
class TestTasks(TestCaseWithClearCache):
    @pook.on
    def test_can_update_character(self):
        # given
        character = CharacterFactory()
        section = Character.UpdateSection.SHIP
        pook.get(
            "https://esi.evetech.net/meta/status",
            reply=HTTPStatus.OK,
            response_headers={"X-Compatibility-Date": "2025-12-16"},
            response_json={
                "routes": [
                    {
                        "method": "GET",
                        "path": "/characters/{character_id}/ship",
                        "status": "OK",
                    }
                ]
            },
        )
        start_time = now() - dt.timedelta(hours=3)
        pook.get(
            "https://esi.evetech.net/latest/status/",
            reply=HTTPStatus.OK,
            response_headers={
                "X-Esi-Error-Limit-Remain": "40",
                "X-Esi-Error-Limit-Reset": "30",
            },
            response_json={
                "players": 12345,
                "server_version": "1132976",
                "start_time": start_time.isoformat(),
            },
        )
        ship_item_id = 1000000016991
        ship_name = "Shooter Boy"
        ship_type = ShipTypeFactory()
        pook.get(
            make_esi_url(f"characters/{character.character_id}/ship"),
            reply=HTTPStatus.OK,
            response_json={
                "ship_item_id": ship_item_id,
                "ship_name": ship_name,
                "ship_type_id": ship_type.id,
            },
        )

        # when
        with patch(TASKS_PATH + ".enabled_sections_by_stale_minutes") as m:
            m.return_value = [section]
            tasks.update_all_characters()

        # then
        status: CharacterUpdateStatus = character.update_status_set.get(section=section)
        self.assertTrue(status.is_success)
