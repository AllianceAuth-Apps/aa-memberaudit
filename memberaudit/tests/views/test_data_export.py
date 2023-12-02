from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.http import Http404
from django.test import RequestFactory, TestCase
from django.urls import reverse

from app_utils.testing import create_user_from_evecharacter

from memberaudit.tests.testdata.load_entities import load_entities
from memberaudit.views.data_export import (
    data_export,
    data_export_run_update,
    download_export_file,
)

MODULE_PATH = "memberaudit.views.data_export"


class TestDataExport(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        load_entities()

    def test_should_open_exports_page_with_permission(self):
        # given
        user, _ = create_user_from_evecharacter(
            1122, permissions=["memberaudit.basic_access", "memberaudit.exports_access"]
        )
        request = self.factory.get(reverse("memberaudit:data_export"))
        request.user = user
        # when
        response = data_export(request)
        # then
        self.assertEqual(response.status_code, 200)

    def test_should_not_open_exports_page_without_permission(self):
        # given
        user, _ = create_user_from_evecharacter(
            1122, permissions=["memberaudit.basic_access"]
        )
        request = self.factory.get(reverse("memberaudit:data_export"))
        request.user = user
        # when
        response = data_export(request)
        # then
        self.assertEqual(response.status_code, 302)

    @patch(MODULE_PATH + ".data_exporters.default_destination")
    def test_should_return_export_file(self, mock_default_destination):
        with TemporaryDirectory() as tmp_dir_name:
            # given
            contract_item_file = Path(tmp_dir_name) / "memberaudit_contract-item.zip"
            with contract_item_file.open(mode="w") as _:
                pass
            mock_default_destination.return_value = Path(tmp_dir_name)
            user, _ = create_user_from_evecharacter(
                1122,
                permissions=["memberaudit.basic_access", "memberaudit.exports_access"],
            )
            request = self.factory.get(
                reverse("memberaudit:download_export_file", args=["contract-item"])
            )
            request.user = user
            # when
            response = download_export_file(request, "contract-item")
            # then
            self.assertEqual(response.status_code, 200)

    @patch(MODULE_PATH + ".data_exporters.default_destination")
    def test_should_raise_404_when_export_file_not_found(
        self, mock_default_destination
    ):
        with TemporaryDirectory() as tmpdirname:
            # given
            mock_default_destination.return_value = Path(tmpdirname)
            user, _ = create_user_from_evecharacter(
                1122,
                permissions=["memberaudit.basic_access", "memberaudit.exports_access"],
            )
            request = self.factory.get(
                reverse("memberaudit:download_export_file", args=["contract-item"])
            )
            request.user = user
            # when/then
            with self.assertRaises(Http404):
                download_export_file(request, "contract-item")

    @patch(MODULE_PATH + ".messages")
    @patch(MODULE_PATH + ".tasks.export_data_for_topic")
    def test_should_start_export_task(
        self, mock_task_export_data_for_topic, mock_messages_plus
    ):
        # given
        user, _ = create_user_from_evecharacter(
            1122, permissions=["memberaudit.basic_access", "memberaudit.exports_access"]
        )
        request = self.factory.get(
            reverse("memberaudit:data_export_run_update", args=["contract-item"])
        )
        request.user = user
        # when
        response = data_export_run_update(request, "contract-item")
        # then
        self.assertEqual(response.status_code, 302)
        self.assertTrue(mock_task_export_data_for_topic.delay.called)
        _, kwargs = mock_task_export_data_for_topic.delay.call_args
        self.assertEqual(kwargs["topic"], "contract-item")
        self.assertEqual(kwargs["user_pk"], user.pk)
        self.assertTrue(mock_messages_plus.info.called)
