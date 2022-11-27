"""
Test auth_hooks
"""

# Standard Library
from http import HTTPStatus

# Django
from django.test import TestCase, modify_settings
from django.urls import reverse

# AA Member Audit
from memberaudit.app_settings import MEMBERAUDIT_APP_NAME
from memberaudit.tests.testdata.load_entities import load_entities
from memberaudit.tests.testdata.load_eveuniverse import load_eveuniverse
from memberaudit.tests.testdata.load_locations import load_locations
from memberaudit.tests.utils import create_user_from_evecharacter_with_access


class TestHooks(TestCase):
    """
    Test the app hook into allianceauth
    """

    @classmethod
    def setUpClass(cls) -> None:
        """
        Set up groups and users
        """

        super().setUpClass()

        load_eveuniverse()
        load_entities()
        load_locations()

        cls.html_menu = f"""
            <li>
                <a class href="{reverse('memberaudit:index')}">
                    <i class="far fa-address-card fa-fw fa-fw"></i>
                    {MEMBERAUDIT_APP_NAME}
                </a>
            </li>
        """

    def setUp(self) -> None:
        self.user_with_access, _ = create_user_from_evecharacter_with_access(1002)

    def test_render_hook_success_with_default_name(self):
        """
        Test should show the link to the app in the navigation to user with access
        :return:
        :rtype:
        """

        self.client.force_login(self.user_with_access)

        response = self.client.get(reverse("memberaudit:index"))

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertContains(response, self.html_menu, html=True)

    @modify_settings(MEMBERAUDIT_APP_NAME="これが監査です")
    def test_render_hook_success_with_custom_name(self):
        """
        Test should show the link to the app in the navigation to user with access with
        a custom app name. これが監査です is Japanese for "This is the audit". This
        should result in "koregajian-cha-desu" as app slug
        :return:
        :rtype:
        """

        self.client.force_login(self.user_with_access)

        response = self.client.get(reverse("memberaudit:index"))
        expected_html_menu = f"""
            <li>
                <a class href="{reverse('memberaudit:index')}">
                    <i class="far fa-address-card fa-fw fa-fw"></i>
                    {MEMBERAUDIT_APP_NAME}
                </a>
            </li>
        """

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertContains(response, MEMBERAUDIT_APP_NAME, html=True)
        self.assertContains(response, "koregajian-cha-desu", html=True)
        self.assertContains(response, expected_html_menu, html=True)

    # def test_render_hook_fail(self):
    #     """
    #     Test should not show the link to the app in the
    #     navigation to user without access
    #     :return:
    #     :rtype:
    #     """
    #
    #     self.client.force_login(self.user_1001)
    #
    #     response = self.client.get(reverse("memberaudit:index"))
    #
    #     self.assertEqual(response.status_code, HTTPStatus.OK)
    #     self.assertNotContains(response, self.html_menu, html=True)
