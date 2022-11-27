"""
Test auth_hooks
"""

# Standard Library
from http import HTTPStatus

# Django
from django.test import TestCase
from django.urls import reverse

from app_utils.testing import create_fake_user


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

        # User cannot access bulletins
        cls.user_1001 = create_fake_user(1001, "Peter Parker")

        # User can access bulletins
        cls.user_1002 = create_fake_user(
            1002, "Bruce Wayne", permissions=["memberaudit.basic_access"]
        )

        cls.html_menu = f"""
            <li>
                <a class href="{reverse('memberaudit:index')}">
                    <i class="far fa-address-card fa-fw fa-fw"></i> Member Audit
                </a>
            </li>
        """

    def test_render_hook_success(self):
        """
        Test should show the link to the app in the navigation to user with access
        :return:
        :rtype:
        """

        self.client.force_login(self.user_1002)
        response = self.client.get(reverse("authentication:dashboard"))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertContains(response, "Member Audit", html=True)  # Link name
        self.assertContains(response, "/member-audit/", html=True)  # Link slug
        self.assertContains(response, self.html_menu, html=True)

        # Test custom app name
        with self.settings(MEMBERAUDIT_APP_NAME="これが監査です"):
            response = self.client.get(reverse("authentication:dashboard"))

            expected_custom_html_menu = """
                <li>
                    <a class href="/koregajian-cha-desu/">
                        <i class="far fa-address-card fa-fw fa-fw"></i> これが監査です
                    </a>
                </li>
            """

            self.assertEqual(response.status_code, HTTPStatus.OK)
            self.assertContains(response, "これが監査です", html=True)
            self.assertContains(response, "/koregajian-cha-desu/", html=True)
            self.assertContains(response, expected_custom_html_menu, html=True)

    def test_render_hook_fail(self):
        """
        Test should not show the link to the app in the navigation to user without access
        :return:
        :rtype:
        """

        self.client.force_login(self.user_1001)

        response = self.client.get(reverse("authentication:dashboard"))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertNotContains(response, self.html_menu, html=True)
